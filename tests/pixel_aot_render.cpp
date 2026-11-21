#include "bvh_fixture.h"
#include "pixel_aot_vs.h"
#include <algorithm>
#include <charconv>
#include <cmath>
#include <fstream>
#include <iterator>
#include <string_view>

using namespace bvh_fixture;

namespace {
// Includes UNORM values on both sides of a binary16 rounding midpoint.
constexpr std::array<UINT, 8> ramp{0, 16, 37, 64, 101, 153, 219, 254};

D3D12_RESOURCE_DESC texture_desc(UINT width, UINT height, DXGI_FORMAT format, D3D12_RESOURCE_FLAGS flags)
{
    D3D12_RESOURCE_DESC desc{};
    desc.Dimension = D3D12_RESOURCE_DIMENSION_TEXTURE2D;
    desc.Width = width;
    desc.Height = height;
    desc.DepthOrArraySize = desc.MipLevels = desc.SampleDesc.Count = 1;
    desc.Format = format;
    desc.Flags = flags;
    return desc;
}

float expected_channel(UINT byte)
{
    if (!byte) return 0;
    // Fixture inputs are zero or normal positive half values. Truncate the exact
    // UNORM fraction to the 11 significant bits of a binary16 MRT export.
    const double value = byte / 255.0;
    int exponent;
    std::frexp(value, &exponent);
    const double scale = std::ldexp(1.0, 11 - exponent);
    return static_cast<float>(std::floor(value * scale) / scale);
}
using Color = std::array<float, 4>;

struct PixelInput {
    UINT width, height, scale;
    DXGI_FORMAT format;
    std::vector<BYTE> rows;
    std::vector<Color> expected;
    std::vector<BYTE> secondRows;
    std::vector<Word> constants = std::vector<Word>(64);
};

struct MipDraw {
    UINT sampledLevel;
    UINT scale;
    UINT requestedMip = 0;
    bool reportMip = false;
};

void draw_verified(ID3D12Device* device, const char* path, const std::vector<PixelInput>& levels,
                   UINT firstResident, const std::vector<MipDraw>& draws, const char* capture)
{
    const auto& input = levels.front();
    auto cb = upload(device, input.constants);
    std::ifstream file(path, std::ios::binary);
    std::vector<char> ps{std::istreambuf_iterator<char>(file), {}};
    if (ps.empty() || file.bad()) throw std::runtime_error("Cannot read compiled pixel shader");
    ComPtr<ID3D12RootSignature> root;
    check(device->CreateRootSignature(0, pixel_aot_vs, sizeof(pixel_aot_vs), IID_PPV_ARGS(&root)), "Pixel root");
    D3D12_GRAPHICS_PIPELINE_STATE_DESC desc{};
    desc.pRootSignature = root.Get();
    desc.VS = {pixel_aot_vs, sizeof(pixel_aot_vs)};
    desc.PS = {ps.data(), ps.size()};
    desc.RasterizerState.FillMode = D3D12_FILL_MODE_SOLID;
    desc.RasterizerState.CullMode = D3D12_CULL_MODE_NONE;
    desc.RasterizerState.DepthClipEnable = TRUE;
    auto& blend = desc.BlendState.RenderTarget[0];
    blend.SrcBlend = blend.SrcBlendAlpha = D3D12_BLEND_ONE;
    blend.DestBlend = blend.DestBlendAlpha = D3D12_BLEND_ZERO;
    blend.BlendOp = blend.BlendOpAlpha = D3D12_BLEND_OP_ADD;
    blend.LogicOp = D3D12_LOGIC_OP_NOOP;
    blend.RenderTargetWriteMask = D3D12_COLOR_WRITE_ENABLE_ALL;
    desc.SampleMask = UINT_MAX;
    desc.PrimitiveTopologyType = D3D12_PRIMITIVE_TOPOLOGY_TYPE_TRIANGLE;
    desc.NumRenderTargets = desc.SampleDesc.Count = 1;
    desc.RTVFormats[0] = DXGI_FORMAT_R32G32B32A32_FLOAT;
    ComPtr<ID3D12PipelineState> pso;
    check(device->CreateGraphicsPipelineState(&desc, IID_PPV_ARGS(&pso)), "Translated pixel pipeline");

    auto srcDesc = texture_desc(input.width << firstResident, input.height << firstResident,
                                input.format, D3D12_RESOURCE_FLAG_NONE);
    const UINT residentCount = static_cast<UINT>(levels.size());
    srcDesc.MipLevels = static_cast<UINT16>(firstResident + residentCount);
    auto texture = resource(device, srcDesc, D3D12_HEAP_TYPE_DEFAULT, D3D12_RESOURCE_STATE_COPY_DEST);
    const D3D12_CLEAR_VALUE clear{desc.RTVFormats[0], {-1, -1, -1, -1}};
    std::vector<D3D12_PLACED_SUBRESOURCE_FOOTPRINT> layouts(residentCount);
    UINT64 sourceBytes = 0;
    std::vector<UINT> rows(residentCount);
    std::vector<UINT64> rowBytes(residentCount);
    device->GetCopyableFootprints(&srcDesc, firstResident, residentCount, 0, layouts.data(), rows.data(), rowBytes.data(), &sourceBytes);
    std::vector<BYTE> colors(sourceBytes);
    for (UINT level = 0; level < residentCount; ++level) {
        const auto& packed = levels[level].rows;
        if (rowBytes[level] * rows[level] != packed.size()) throw std::runtime_error("Invalid texture row size");
        for (UINT y = 0; y < rows[level]; ++y) {
            auto offset = layouts[level].Offset + size_t(y) * layouts[level].Footprint.RowPitch;
            std::memcpy(colors.data() + offset, packed.data() + y * rowBytes[level], rowBytes[level]);
        }
    }
    auto staging = upload(device, colors);
    ComPtr<ID3D12Resource> secondTexture, secondStaging;
    if (!input.secondRows.empty()) {
        if (residentCount != 1 || firstResident || input.secondRows.size() != input.rows.size())
            throw std::runtime_error("Invalid second texture extent");
        for (UINT y = 0; y < rows[0]; ++y)
            std::memcpy(colors.data() + y * layouts[0].Footprint.RowPitch,
                        input.secondRows.data() + y * rowBytes[0], rowBytes[0]);
        secondStaging = upload(device, colors);
        secondTexture = resource(device, srcDesc, D3D12_HEAP_TYPE_DEFAULT, D3D12_RESOURCE_STATE_COPY_DEST);
    }
    D3D12_DESCRIPTOR_HEAP_DESC heapDesc{};
    heapDesc.NumDescriptors = 1;
    heapDesc.Type = D3D12_DESCRIPTOR_HEAP_TYPE_RTV;
    ComPtr<ID3D12DescriptorHeap> rtvs, srvs;
    check(device->CreateDescriptorHeap(&heapDesc, IID_PPV_ARGS(&rtvs)), "Pixel target heap");
    heapDesc.Type = D3D12_DESCRIPTOR_HEAP_TYPE_CBV_SRV_UAV;
    heapDesc.NumDescriptors = 2;
    heapDesc.Flags = D3D12_DESCRIPTOR_HEAP_FLAG_SHADER_VISIBLE;
    check(device->CreateDescriptorHeap(&heapDesc, IID_PPV_ARGS(&srvs)), "Pixel texture heap");
    const auto rtv = rtvs->GetCPUDescriptorHandleForHeapStart();
    D3D12_SHADER_RESOURCE_VIEW_DESC view{};
    view.Format = input.format;
    view.ViewDimension = D3D12_SRV_DIMENSION_TEXTURE2D;
    view.Shader4ComponentMapping = D3D12_DEFAULT_SHADER_4_COMPONENT_MAPPING;
    view.Texture2D.MostDetailedMip = firstResident;
    view.Texture2D.MipLevels = residentCount;
    device->CreateShaderResourceView(texture.Get(), &view, srvs->GetCPUDescriptorHandleForHeapStart());
    auto secondHandle = srvs->GetCPUDescriptorHandleForHeapStart();
    secondHandle.ptr += device->GetDescriptorHandleIncrementSize(heapDesc.Type);
    device->CreateShaderResourceView(secondTexture.Get(), &view, secondHandle);

    bool textureUploaded = false;
    for (const auto& req : draws) {
        if (req.reportMip)
            std::printf("requested_mip=%u sampled_mip=%u ", req.requestedMip, req.sampledLevel + firstResident);
        const auto& sampled = levels.at(req.sampledLevel);
        const UINT width = sampled.width * req.scale, height = sampled.height * req.scale;
        auto dstDesc = texture_desc(width, height, desc.RTVFormats[0], D3D12_RESOURCE_FLAG_ALLOW_RENDER_TARGET);
        auto target = resource(device, dstDesc, D3D12_HEAP_TYPE_DEFAULT, D3D12_RESOURCE_STATE_RENDER_TARGET, &clear);
        D3D12_PLACED_SUBRESOURCE_FOOTPRINT resultLayout{};
        UINT64 resultBytes = 0;
        device->GetCopyableFootprints(&dstDesc, 0, 1, 0, &resultLayout, nullptr, nullptr, &resultBytes);
        auto back = make_buffer(device, resultBytes, D3D12_HEAP_TYPE_READBACK, D3D12_RESOURCE_STATE_COPY_DEST);
        device->CreateRenderTargetView(target.Get(), nullptr, rtv);
        ComputeCommands cmd(device, pso.Get(), D3D12_COMMAND_LIST_TYPE_DIRECT);
        auto* list = cmd.list.Get();
        D3D12_TEXTURE_COPY_LOCATION src{}, dst{};
        if (!textureUploaded) {
            src.pResource = staging.Get();
            src.Type = D3D12_TEXTURE_COPY_TYPE_PLACED_FOOTPRINT;
            dst.pResource = texture.Get();
            dst.Type = D3D12_TEXTURE_COPY_TYPE_SUBRESOURCE_INDEX;
            for (UINT level = 0; level < residentCount; ++level) {
                src.PlacedFootprint = layouts[level];
                dst.SubresourceIndex = firstResident + level;
                list->CopyTextureRegion(&dst, 0, 0, 0, &src, nullptr);
            }
            transition(list, texture.Get(), D3D12_RESOURCE_STATE_COPY_DEST, D3D12_RESOURCE_STATE_PIXEL_SHADER_RESOURCE);
            if (secondTexture) {
                src.pResource = secondStaging.Get();
                dst.pResource = secondTexture.Get();
                list->CopyTextureRegion(&dst, 0, 0, 0, &src, nullptr);
                transition(list, secondTexture.Get(), D3D12_RESOURCE_STATE_COPY_DEST, D3D12_RESOURCE_STATE_PIXEL_SHADER_RESOURCE);
            }
            textureUploaded = true;
        }
        ID3D12DescriptorHeap* heaps[]{srvs.Get()};
        list->SetDescriptorHeaps(1, heaps);
        list->SetGraphicsRootSignature(root.Get());
        list->SetGraphicsRootDescriptorTable(0, srvs->GetGPUDescriptorHandleForHeapStart());
        list->SetGraphicsRootConstantBufferView(1, cb->GetGPUVirtualAddress());
        const D3D12_VIEWPORT viewport{0,0,float(width),float(height),0,1};
        const D3D12_RECT scissor{0,0,LONG(width),LONG(height)};
        list->RSSetViewports(1, &viewport);
        list->RSSetScissorRects(1, &scissor);
        list->OMSetRenderTargets(1, &rtv, FALSE, nullptr);
        list->ClearRenderTargetView(rtv, clear.Color, 0, nullptr);
        list->IASetPrimitiveTopology(D3D_PRIMITIVE_TOPOLOGY_TRIANGLELIST);
        list->DrawInstanced(3,1,0,0);
        transition(list, target.Get(), D3D12_RESOURCE_STATE_RENDER_TARGET, D3D12_RESOURCE_STATE_COPY_SOURCE);
        src.pResource = target.Get();
        src.Type = D3D12_TEXTURE_COPY_TYPE_SUBRESOURCE_INDEX;
        src.SubresourceIndex = 0;
        dst.pResource = back.Get();
        dst.Type = D3D12_TEXTURE_COPY_TYPE_PLACED_FOOTPRINT;
        dst.PlacedFootprint = resultLayout;
        list->CopyTextureRegion(&dst, 0,0,0, &src, nullptr);
        cmd.submit_and_wait(device);
        auto words = read(back.Get(), resultBytes/4);
        std::vector<BYTE> image;
        if (capture) image.reserve(size_t(width) * height * 4);
        for (UINT y = 0; y < height; ++y) {
            for (UINT x = 0; x < width; ++x) {
                const auto& expected = sampled.expected[(y / req.scale) * sampled.width + x / req.scale];
                const auto offset = y * resultLayout.Footprint.RowPitch / 4 + x * 4;
                Color actual;
                std::memcpy(actual.data(), words.data() + offset, sizeof(actual));
                if (std::memcmp(actual.data(), expected.data(), sizeof(actual)) != 0) {
                    std::fprintf(stderr, "pixel_mismatch x=%u y=%u\n", x, y);
                    for (size_t c = 0; c < actual.size(); ++c)
                        std::fprintf(stderr, "channel=%zu expected=%g actual=%g\n", c, expected[c], actual[c]);
                    throw std::runtime_error("AOT color export differs from CPU reference");
                }
                if (capture) {
                    for (float value : actual) image.push_back(static_cast<BYTE>(std::lround(value * 255)));
                }
            }
        }
        if (capture) {
            std::ofstream output(capture, std::ios::binary);
            output.write(reinterpret_cast<const char*>(image.data()), image.size());
            output.close();
            if (!output) throw std::runtime_error("Cannot save GPU readback");
        }
        std::printf("pixels=%u channels=%u max_absolute_error=0\n", width * height, width * height * 4);
    }
}

void draw_verified(ID3D12Device* device, const char* path, const std::vector<PixelInput>& levels,
                   UINT firstResident, UINT sampledLevel, const char* capture)
{
    draw_verified(device, path, levels, firstResident, {{sampledLevel, levels.at(sampledLevel).scale}}, capture);
}
}

void check_translated_pixel(ID3D12Device* device, const char* path, bool swapRB, const char* reference)
{
    PixelInput input{8, 8, 8, DXGI_FORMAT_R8G8B8A8_UNORM};
    for (auto g : ramp) {
        for (auto r : ramp) {
            input.rows.insert(input.rows.end(), {BYTE(r), BYTE(g), 128, 255});
            Color expected{expected_channel(r), expected_channel(g), expected_channel(128), 1};
            if (swapRB) std::swap(expected[0], expected[2]);
            input.expected.push_back(expected);
        }
    }
    if (reference) {
        std::ifstream file(reference, std::ios::binary);
        file.read(reinterpret_cast<char*>(input.constants.data()), input.constants.size() * sizeof(Word));
        file.read(reinterpret_cast<char*>(input.expected.data()), input.expected.size() * sizeof(Color));
        if (!file || file.peek() != std::char_traits<char>::eof())
            throw std::runtime_error("Expected a 256-byte constant buffer and 64 float4 reference colors");
    }
    std::vector<PixelInput> levels;
    levels.push_back(std::move(input));
    draw_verified(device, path, levels, 0, 0, nullptr);
}

void check_dual_pixel(ID3D12Device* device, const char* shader, const char* capture, bool swap)
{
    PixelInput input{8, 8, 8, DXGI_FORMAT_R8G8B8A8_UNORM};
    for (auto blue : ramp) {
        for (auto red : ramp) {
            input.rows.insert(input.rows.end(), {BYTE(red), 0, 0, 255});
            input.secondRows.insert(input.secondRows.end(), {0, 0, BYTE(blue), 255});
            // The two nonzero channels use exact power-of-two scaling after UNORM conversion.
            input.expected.push_back({expected_channel(red * 3) / 4, 0, expected_channel(blue) / 4, 1});
        }
    }
    if (swap) std::swap(input.rows, input.secondRows);
    draw_verified(device, shader, {input}, 0, 0, capture);
}

namespace {
PixelInput read_bc7_case(const char* fixture)
{
    std::ifstream file(fixture, std::ios::binary);
    std::array<char,4> magic{};
    UINT w = 0, h = 0;
    file.read(magic.data(), 4);
    file.read(reinterpret_cast<char*>(&w), sizeof(w));
    file.read(reinterpret_cast<char*>(&h), sizeof(h));
    if (!file || std::memcmp(magic.data(), "BC7C", 4) || !w || !h || w % 4 || h % 4 ||
        w > 4096 || h > 4096 || size_t(w) * h > 4 * 1024 * 1024)
        throw std::runtime_error("Invalid single-level BC7 case dimensions or header");
    PixelInput input{w, h, 1, DXGI_FORMAT_BC7_UNORM};
    const size_t pixels = size_t(w) * h;
    input.rows.resize(pixels);  // 16 bytes per 4x4 block
    file.read(reinterpret_cast<char*>(input.rows.data()), input.rows.size());
    std::vector<std::array<BYTE,4>> reference(pixels);
    file.read(reinterpret_cast<char*>(reference.data()), pixels * 4);
    if (!file || file.peek() != std::char_traits<char>::eof())
        throw std::runtime_error("BC7 block rows or RGBA reference have incorrect size");
    input.expected.reserve(pixels);
    for (const auto& rgba : reference) {
        input.expected.push_back({expected_channel(rgba[0]), expected_channel(rgba[1]),
                                  expected_channel(rgba[2]), expected_channel(rgba[3])});
    }
    return input;
}
}

void check_bc7_pixel(ID3D12Device* device, const char* shader, const char* fixture,
                     const char* capture, const char* mip1)
{
    std::vector<PixelInput> levels;
    levels.push_back(read_bc7_case(fixture));
    if (mip1) {
        auto lower = read_bc7_case(mip1);
        if (lower.width * 2 != levels.front().width || lower.height * 2 != levels.front().height)
            throw std::runtime_error("Expected a half-size BC7 mip");
        levels.push_back(std::move(lower));
    }
    draw_verified(device, shader, levels, 0, static_cast<UINT>(levels.size() - 1), capture);
}

void check_bc7_tail(ID3D12Device* device, const char* shader, const char* firstMip, int count, char** paths)
{
    const std::string_view arg(firstMip);
    UINT first = 0;
    const auto parsed = std::from_chars(arg.data(), arg.data() + arg.size(), first);
    if (parsed.ec != std::errc{} || parsed.ptr != arg.data() + arg.size() || first > 10)
        throw std::runtime_error("Invalid first resident mip");
    std::vector<PixelInput> levels;
    for (int i = 0; i < count; ++i) {
        auto level = read_bc7_case(paths[i]);
        if (levels.empty()) {
            const UINT width = level.width << first, height = level.height << first;
            if (width > 4096 || height > 4096 || UINT64(width) * height > 4 * 1024 * 1024)
                throw std::runtime_error("Logical BC7 texture exceeds fixture bounds");
        } else if (levels.back().width / 2 != level.width || levels.back().height / 2 != level.height) {
            throw std::runtime_error("Expected consecutive BC7 mip sizes");
        }
        levels.push_back(std::move(level));
    }
    // Changing the viewport exercises the copy shader's implicit LOD with the same SRV range.
    std::vector<MipDraw> draws;
    for (UINT mip = 0; mip < first + levels.size(); ++mip) {
        const UINT scale = mip < first ? 1u << (first - mip) : 1u;
        const UINT selected = mip < first ? 0 : mip - first;
        draws.push_back({selected, scale, mip, true});
    }
    draw_verified(device, shader, levels, first, draws, nullptr);
}
