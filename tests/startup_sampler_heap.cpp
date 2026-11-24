// Desktop readback for tools/startup/gfx2hlsl.py's run-time sampler heap indexing (#1143).
//
// The translated pixel shader samples r0 : register(t0) through qh[offset / 16], a bounded
// SamplerState table at register(s0, space1), with the byte offset taken from an entry constant
// (cbuffer entry : register(b0)). This draws one pixel with that shader and a source-built
// full-screen vertex shader, then reads the colour back.
//
// The texture is 2x1 R32_FLOAT {0.25, 0.75}, sampled at u = 1.25 by the fixture shader. The table
// holds point samplers: entry 0 wraps (texel 0, 0.25), entry 1 clamps (texel 1, 0.75), and every
// other entry uses a transparent-black border (0.0), so the readback names the entry the shader used.
#include "desktop_gpu.h"

#include <cstdint>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <iterator>
#include <stdexcept>
#include <string>
#include <vector>

using Microsoft::WRL::ComPtr;

namespace {
constexpr UINT heap_size = 2048;   // matches gfx2hlsl.SAMPLER_HEAP_SIZE
constexpr UINT heap_space = 1;     // matches gfx2hlsl.SAMPLER_HEAP_SPACE
constexpr UINT entry_constants = 4;  // ud0..ud3 of the fixture's manifest

std::vector<char> read_blob(const char* path)
{
    std::ifstream file(path, std::ios::binary);
    std::vector<char> bytes((std::istreambuf_iterator<char>(file)), std::istreambuf_iterator<char>());
    if (!file.good() && !file.eof()) throw std::runtime_error(std::string("Cannot read ") + path);
    if (bytes.empty()) throw std::runtime_error(std::string("Empty shader ") + path);
    return bytes;
}

ComPtr<ID3D12RootSignature> create_root(ID3D12Device* device)
{
    const D3D12_DESCRIPTOR_RANGE srv{D3D12_DESCRIPTOR_RANGE_TYPE_SRV, 1, 0, 0, 0};
    const D3D12_DESCRIPTOR_RANGE samplers{D3D12_DESCRIPTOR_RANGE_TYPE_SAMPLER, heap_size, 0, heap_space, 0};
    D3D12_ROOT_PARAMETER params[3]{};
    params[0].ParameterType = D3D12_ROOT_PARAMETER_TYPE_32BIT_CONSTANTS;
    params[0].Constants = {0, 0, entry_constants};
    params[0].ShaderVisibility = D3D12_SHADER_VISIBILITY_PIXEL;
    params[1].ParameterType = D3D12_ROOT_PARAMETER_TYPE_DESCRIPTOR_TABLE;
    params[1].DescriptorTable = {1, &srv};
    params[1].ShaderVisibility = D3D12_SHADER_VISIBILITY_PIXEL;
    params[2].ParameterType = D3D12_ROOT_PARAMETER_TYPE_DESCRIPTOR_TABLE;
    params[2].DescriptorTable = {1, &samplers};
    params[2].ShaderVisibility = D3D12_SHADER_VISIBILITY_PIXEL;
    D3D12_ROOT_SIGNATURE_DESC desc{};
    desc.NumParameters = _countof(params);
    desc.pParameters = params;
    ComPtr<ID3DBlob> signature, errors;
    if (FAILED(D3D12SerializeRootSignature(&desc, D3D_ROOT_SIGNATURE_VERSION_1, &signature, &errors)))
        throw std::runtime_error(errors ? static_cast<const char*>(errors->GetBufferPointer())
                                        : "Serialize sampler heap root signature");
    ComPtr<ID3D12RootSignature> root;
    check(device->CreateRootSignature(0, signature->GetBufferPointer(), signature->GetBufferSize(), IID_PPV_ARGS(&root)),
          "Create sampler heap root signature");
    return root;
}

D3D12_SAMPLER_DESC point_sampler(D3D12_TEXTURE_ADDRESS_MODE mode)
{
    D3D12_SAMPLER_DESC desc{};
    desc.Filter = D3D12_FILTER_MIN_MAG_MIP_POINT;
    desc.AddressU = desc.AddressV = desc.AddressW = mode;
    desc.MaxAnisotropy = 1;
    desc.ComparisonFunc = D3D12_COMPARISON_FUNC_NEVER;
    desc.MaxLOD = D3D12_FLOAT32_MAX;
    return desc;  // BorderColor stays transparent black
}
}  // namespace

float check_startup_sampler_heap(ID3D12Device* device, const char* vertex_path, const char* pixel_path,
                                 std::uint32_t byte_offset)
{
    const auto vs = read_blob(vertex_path);
    const auto ps = read_blob(pixel_path);
    const auto root = create_root(device);

    D3D12_GRAPHICS_PIPELINE_STATE_DESC pd{};
    pd.pRootSignature = root.Get();
    pd.VS = {vs.data(), vs.size()};
    pd.PS = {ps.data(), ps.size()};
    pd.BlendState.RenderTarget[0].RenderTargetWriteMask = D3D12_COLOR_WRITE_ENABLE_ALL;
    pd.SampleMask = UINT_MAX;
    pd.RasterizerState.FillMode = D3D12_FILL_MODE_SOLID;
    pd.RasterizerState.CullMode = D3D12_CULL_MODE_NONE;
    pd.RasterizerState.DepthClipEnable = TRUE;
    pd.PrimitiveTopologyType = D3D12_PRIMITIVE_TOPOLOGY_TYPE_TRIANGLE;
    pd.NumRenderTargets = 1;
    pd.RTVFormats[0] = DXGI_FORMAT_R32G32B32A32_FLOAT;
    pd.SampleDesc.Count = 1;
    ComPtr<ID3D12PipelineState> pipeline;
    check(device->CreateGraphicsPipelineState(&pd, IID_PPV_ARGS(&pipeline)), "Create sampler heap PSO");

    // 2x1 R32_FLOAT {0.25, 0.75}.
    D3D12_RESOURCE_DESC td{};
    td.Dimension = D3D12_RESOURCE_DIMENSION_TEXTURE2D;
    td.Width = 2;
    td.Height = 1;
    td.DepthOrArraySize = 1;
    td.MipLevels = 1;
    td.Format = DXGI_FORMAT_R32_FLOAT;
    td.SampleDesc.Count = 1;
    const auto texture = resource(device, td, D3D12_HEAP_TYPE_DEFAULT, D3D12_RESOURCE_STATE_COPY_DEST);
    D3D12_PLACED_SUBRESOURCE_FOOTPRINT footprint{};
    UINT64 upload_size = 0;
    device->GetCopyableFootprints(&td, 0, 1, 0, &footprint, nullptr, nullptr, &upload_size);
    const auto upload = make_buffer(device, upload_size, D3D12_HEAP_TYPE_UPLOAD, D3D12_RESOURCE_STATE_GENERIC_READ);
    void* mapped = nullptr;
    const D3D12_RANGE none{0, 0};
    check(upload->Map(0, &none, &mapped), "Map sampler heap texels");
    const float texels[2] = {0.25f, 0.75f};
    std::memcpy(static_cast<std::uint8_t*>(mapped) + footprint.Offset, texels, sizeof(texels));
    upload->Unmap(0, nullptr);

    // 1x1 float4 target and its readback.
    D3D12_RESOURCE_DESC rd = td;
    rd.Width = 1;
    rd.Format = DXGI_FORMAT_R32G32B32A32_FLOAT;
    rd.Flags = D3D12_RESOURCE_FLAG_ALLOW_RENDER_TARGET;
    const D3D12_CLEAR_VALUE clear{DXGI_FORMAT_R32G32B32A32_FLOAT, {-1.0f, -1.0f, -1.0f, -1.0f}};
    const auto target = resource(device, rd, D3D12_HEAP_TYPE_DEFAULT, D3D12_RESOURCE_STATE_RENDER_TARGET, &clear);
    D3D12_PLACED_SUBRESOURCE_FOOTPRINT target_footprint{};
    UINT64 readback_size = 0;
    device->GetCopyableFootprints(&rd, 0, 1, 0, &target_footprint, nullptr, nullptr, &readback_size);
    const auto readback = make_buffer(device, readback_size, D3D12_HEAP_TYPE_READBACK, D3D12_RESOURCE_STATE_COPY_DEST);

    D3D12_DESCRIPTOR_HEAP_DESC hd{D3D12_DESCRIPTOR_HEAP_TYPE_CBV_SRV_UAV, 1, D3D12_DESCRIPTOR_HEAP_FLAG_SHADER_VISIBLE};
    ComPtr<ID3D12DescriptorHeap> views, sampler_heap, rtvs;
    check(device->CreateDescriptorHeap(&hd, IID_PPV_ARGS(&views)), "Create sampler heap view heap");
    device->CreateShaderResourceView(texture.Get(), nullptr, views->GetCPUDescriptorHandleForHeapStart());
    hd = {D3D12_DESCRIPTOR_HEAP_TYPE_SAMPLER, heap_size, D3D12_DESCRIPTOR_HEAP_FLAG_SHADER_VISIBLE};
    check(device->CreateDescriptorHeap(&hd, IID_PPV_ARGS(&sampler_heap)), "Create sampler table");
    const UINT stride = device->GetDescriptorHandleIncrementSize(D3D12_DESCRIPTOR_HEAP_TYPE_SAMPLER);
    for (UINT i = 0; i < heap_size; ++i) {
        const auto desc = point_sampler(i == 0 ? D3D12_TEXTURE_ADDRESS_MODE_WRAP
                                        : i == 1 ? D3D12_TEXTURE_ADDRESS_MODE_CLAMP
                                                 : D3D12_TEXTURE_ADDRESS_MODE_BORDER);
        auto handle = sampler_heap->GetCPUDescriptorHandleForHeapStart();
        handle.ptr += SIZE_T{i} * stride;
        device->CreateSampler(&desc, handle);
    }
    hd = {D3D12_DESCRIPTOR_HEAP_TYPE_RTV, 1, D3D12_DESCRIPTOR_HEAP_FLAG_NONE};
    check(device->CreateDescriptorHeap(&hd, IID_PPV_ARGS(&rtvs)), "Create sampler heap RTV heap");
    const auto rtv = rtvs->GetCPUDescriptorHandleForHeapStart();
    device->CreateRenderTargetView(target.Get(), nullptr, rtv);

    ComputeCommands commands(device, pipeline.Get(), D3D12_COMMAND_LIST_TYPE_DIRECT);
    auto* list = commands.list.Get();
    D3D12_TEXTURE_COPY_LOCATION to{texture.Get(), D3D12_TEXTURE_COPY_TYPE_SUBRESOURCE_INDEX};
    D3D12_TEXTURE_COPY_LOCATION from{upload.Get(), D3D12_TEXTURE_COPY_TYPE_PLACED_FOOTPRINT};
    from.PlacedFootprint = footprint;
    list->CopyTextureRegion(&to, 0, 0, 0, &from, nullptr);
    transition(list, texture.Get(), D3D12_RESOURCE_STATE_COPY_DEST, D3D12_RESOURCE_STATE_PIXEL_SHADER_RESOURCE);
    list->ClearRenderTargetView(rtv, clear.Color, 0, nullptr);
    list->SetGraphicsRootSignature(root.Get());
    ID3D12DescriptorHeap* heaps[]{views.Get(), sampler_heap.Get()};
    list->SetDescriptorHeaps(2, heaps);
    // ud0 is the rectangle-list switch (0: plain triangles), ud1 the sampler heap byte offset.
    const std::uint32_t constants[entry_constants] = {0, byte_offset, 0, 0};
    list->SetGraphicsRoot32BitConstants(0, entry_constants, constants, 0);
    list->SetGraphicsRootDescriptorTable(1, views->GetGPUDescriptorHandleForHeapStart());
    list->SetGraphicsRootDescriptorTable(2, sampler_heap->GetGPUDescriptorHandleForHeapStart());
    const D3D12_VIEWPORT viewport{0, 0, 1, 1, 0, 1};
    const D3D12_RECT scissor{0, 0, 1, 1};
    list->RSSetViewports(1, &viewport);
    list->RSSetScissorRects(1, &scissor);
    list->OMSetRenderTargets(1, &rtv, FALSE, nullptr);
    list->IASetPrimitiveTopology(D3D_PRIMITIVE_TOPOLOGY_TRIANGLELIST);
    list->DrawInstanced(3, 1, 0, 0);
    transition(list, target.Get(), D3D12_RESOURCE_STATE_RENDER_TARGET, D3D12_RESOURCE_STATE_COPY_SOURCE);
    D3D12_TEXTURE_COPY_LOCATION out{readback.Get(), D3D12_TEXTURE_COPY_TYPE_PLACED_FOOTPRINT};
    out.PlacedFootprint = target_footprint;
    D3D12_TEXTURE_COPY_LOCATION in{target.Get(), D3D12_TEXTURE_COPY_TYPE_SUBRESOURCE_INDEX};
    list->CopyTextureRegion(&out, 0, 0, 0, &in, nullptr);
    commands.submit_and_wait(device);

    float color[4]{};
    const D3D12_RANGE read{0, sizeof(color)};
    check(readback->Map(0, &read, &mapped), "Map sampler heap readback");
    std::memcpy(color, static_cast<std::uint8_t*>(mapped) + target_footprint.Offset, sizeof(color));
    readback->Unmap(0, &none);
    std::uint32_t bits;
    std::memcpy(&bits, &color[0], sizeof(bits));
    std::printf("startup_sampler_heap offset=%u entry=%u red=%08x (%g)\n", byte_offset, byte_offset / 16, bits, color[0]);
    return color[0];
}
