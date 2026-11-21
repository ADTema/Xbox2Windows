#include "bvh_fixture.h"
#include "pixel_aot_vs.h"
#include <algorithm>
#include <cmath>
#include <fstream>
#include <iterator>

using namespace bvh_fixture;

namespace {
// Includes UNORM values on both sides of a binary16 rounding midpoint.
constexpr std::array<UINT, 8> ramp{0, 16, 37, 64, 101, 153, 219, 254};

D3D12_RESOURCE_DESC texture_desc(UINT side, DXGI_FORMAT format, D3D12_RESOURCE_FLAGS flags)
{
    D3D12_RESOURCE_DESC desc{};
    desc.Dimension = D3D12_RESOURCE_DIMENSION_TEXTURE2D;
    desc.Width = desc.Height = side;
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
}

void check_translated_pixel(ID3D12Device* device, const char* path, bool swapRB)
{
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

    auto srcDesc = texture_desc(8, DXGI_FORMAT_R8G8B8A8_UNORM, D3D12_RESOURCE_FLAG_NONE);
    auto dstDesc = texture_desc(64, desc.RTVFormats[0], D3D12_RESOURCE_FLAG_ALLOW_RENDER_TARGET);
    auto texture = resource(device, srcDesc, D3D12_HEAP_TYPE_DEFAULT, D3D12_RESOURCE_STATE_COPY_DEST);
    const D3D12_CLEAR_VALUE clear{desc.RTVFormats[0], {-1, -1, -1, -1}};
    auto target = resource(device, dstDesc, D3D12_HEAP_TYPE_DEFAULT, D3D12_RESOURCE_STATE_RENDER_TARGET, &clear);
    D3D12_PLACED_SUBRESOURCE_FOOTPRINT sourceLayout{}, resultLayout{};
    UINT64 sourceBytes, resultBytes;
    device->GetCopyableFootprints(&srcDesc, 0, 1, 0, &sourceLayout, nullptr, nullptr, &sourceBytes);
    device->GetCopyableFootprints(&dstDesc, 0, 1, 0, &resultLayout, nullptr, nullptr, &resultBytes);
    std::vector<Word> colors(sourceBytes / 4);
    for (UINT y = 0; y < ramp.size(); ++y) {
        for (UINT x = 0; x < ramp.size(); ++x) {
            colors[y * sourceLayout.Footprint.RowPitch / 4 + x] = ramp[x] | (ramp[y] << 8) | 0xff800000u;
        }
    }
    auto staging = upload(device, colors);
    auto back = make_buffer(device, resultBytes, D3D12_HEAP_TYPE_READBACK, D3D12_RESOURCE_STATE_COPY_DEST);
    D3D12_DESCRIPTOR_HEAP_DESC heapDesc{};
    heapDesc.NumDescriptors = 1;
    heapDesc.Type = D3D12_DESCRIPTOR_HEAP_TYPE_RTV;
    ComPtr<ID3D12DescriptorHeap> rtvs, srvs;
    check(device->CreateDescriptorHeap(&heapDesc, IID_PPV_ARGS(&rtvs)), "Pixel target heap");
    heapDesc.Type = D3D12_DESCRIPTOR_HEAP_TYPE_CBV_SRV_UAV;
    heapDesc.Flags = D3D12_DESCRIPTOR_HEAP_FLAG_SHADER_VISIBLE;
    check(device->CreateDescriptorHeap(&heapDesc, IID_PPV_ARGS(&srvs)), "Pixel texture heap");
    const auto rtv = rtvs->GetCPUDescriptorHandleForHeapStart();
    device->CreateRenderTargetView(target.Get(), nullptr, rtv);
    device->CreateShaderResourceView(texture.Get(), nullptr, srvs->GetCPUDescriptorHandleForHeapStart());
    ComputeCommands cmd(device, pso.Get(), D3D12_COMMAND_LIST_TYPE_DIRECT);
    auto* list = cmd.list.Get();
    D3D12_TEXTURE_COPY_LOCATION src{}, dst{};
    src.pResource = staging.Get();
    src.Type = D3D12_TEXTURE_COPY_TYPE_PLACED_FOOTPRINT;
    src.PlacedFootprint = sourceLayout;
    dst.pResource = texture.Get();
    dst.Type = D3D12_TEXTURE_COPY_TYPE_SUBRESOURCE_INDEX;
    list->CopyTextureRegion(&dst, 0, 0, 0, &src, nullptr);
    transition(list, texture.Get(), D3D12_RESOURCE_STATE_COPY_DEST, D3D12_RESOURCE_STATE_PIXEL_SHADER_RESOURCE);
    ID3D12DescriptorHeap* heaps[]{srvs.Get()};
    list->SetDescriptorHeaps(1, heaps);
    list->SetGraphicsRootSignature(root.Get());
    list->SetGraphicsRootDescriptorTable(0, srvs->GetGPUDescriptorHandleForHeapStart());
    const D3D12_VIEWPORT viewport{0,0,64,64,0,1};
    const D3D12_RECT scissor{0,0,64,64};
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
    for (UINT y = 0; y < 64; ++y) {
        for (UINT x = 0; x < 64; ++x) {
            std::array<float, 4> expected{
                expected_channel(ramp[x / 8]), expected_channel(ramp[y / 8]), expected_channel(128), 1.0f};
            if (swapRB) std::swap(expected[0], expected[2]);
            const auto offset = y * resultLayout.Footprint.RowPitch / 4 + x * 4;
            if (std::memcmp(words.data() + offset, expected.data(), sizeof(expected)) != 0) {
                std::fprintf(stderr, "pixel_mismatch x=%u y=%u\n", x, y);
                throw std::runtime_error("AOT color export differs from CPU reference");
            }
        }
    }
    std::puts("pixels=4096 channels=16384 max_absolute_error=0");
}
