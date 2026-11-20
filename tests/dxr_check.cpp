#include "dxr_fixture.h"
#include "ray_query.h"
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <stdexcept>

using Microsoft::WRL::ComPtr;

namespace dxr_fixture {
bool supported(ID3D12Device* device)
{
    D3D12_FEATURE_DATA_D3D12_OPTIONS5 options{};
    D3D12_FEATURE_DATA_SHADER_MODEL model{D3D_SHADER_MODEL_6_5};
#if defined(OFFSCREEN_AGILITY_620) && defined(__ID3D12Device16_INTERFACE_DEFINED__)
    ComPtr<ID3D12Device16> versioned;
    check(device->QueryInterface(IID_PPV_ARGS(&versioned)), "Get Agility feature query interface");
    check(versioned->CheckFeatureSupport1(D3D12_FEATURE_D3D12_OPTIONS5, &options, sizeof(options), 620), "Query DXR tier");
    check(versioned->CheckFeatureSupport1(D3D12_FEATURE_SHADER_MODEL, &model, sizeof(model), 620), "Query shader model 6.5");
#else
    check(device->CheckFeatureSupport(D3D12_FEATURE_D3D12_OPTIONS5, &options, sizeof(options)), "Query DXR tier");
    check(device->CheckFeatureSupport(D3D12_FEATURE_SHADER_MODEL, &model, sizeof(model)), "Query shader model 6.5");
#endif
    std::printf("dxr_tier=%u shader_model_capped_at_6_5=0x%x\n", options.RaytracingTier, model.HighestShaderModel);
    return options.RaytracingTier >= D3D12_RAYTRACING_TIER_1_1 && model.HighestShaderModel >= D3D_SHADER_MODEL_6_5;
}

D3D12_RAYTRACING_INSTANCE_DESC instance(UINT id, UINT mask, float translateX) {
    D3D12_RAYTRACING_INSTANCE_DESC result{};
    result.Transform[0][0] = result.Transform[1][1] = result.Transform[2][2] = 1;
    result.Transform[0][3] = translateX;
    result.InstanceID = id;
    result.InstanceMask = mask;
    return result;
}

std::vector<bvh_fixture::Word> trace(ID3D12Device* device, const std::vector<Vertex>& vertices,
    std::vector<D3D12_RAYTRACING_INSTANCE_DESC> instances, const std::vector<Ray>& rays) {
    ComPtr<ID3D12Device5> dxr;
    check(device->QueryInterface(IID_PPV_ARGS(&dxr)), "Get DXR device");
    auto vertexBuffer = bvh_fixture::upload(device, vertices);
    auto rayBuffer = bvh_fixture::upload(device, rays);
    D3D12_RAYTRACING_GEOMETRY_DESC geometry{};
    geometry.Type = D3D12_RAYTRACING_GEOMETRY_TYPE_TRIANGLES;
    geometry.Flags = D3D12_RAYTRACING_GEOMETRY_FLAG_OPAQUE;
    geometry.Triangles.VertexBuffer = {vertexBuffer->GetGPUVirtualAddress(), sizeof(Vertex)};
    geometry.Triangles.VertexCount = static_cast<UINT>(vertices.size());
    geometry.Triangles.VertexFormat = DXGI_FORMAT_R32G32B32_FLOAT;
    D3D12_BUILD_RAYTRACING_ACCELERATION_STRUCTURE_DESC bottom{}, top{};
    bottom.Inputs.Type = D3D12_RAYTRACING_ACCELERATION_STRUCTURE_TYPE_BOTTOM_LEVEL;
    bottom.Inputs.DescsLayout = D3D12_ELEMENTS_LAYOUT_ARRAY;
    bottom.Inputs.NumDescs = 1;
    bottom.Inputs.pGeometryDescs = &geometry;
    top.Inputs.Type = D3D12_RAYTRACING_ACCELERATION_STRUCTURE_TYPE_TOP_LEVEL;
    top.Inputs.DescsLayout = D3D12_ELEMENTS_LAYOUT_ARRAY;
    top.Inputs.NumDescs = static_cast<UINT>(instances.size());
    D3D12_RAYTRACING_ACCELERATION_STRUCTURE_PREBUILD_INFO bottom_size{}, top_size{};
    dxr->GetRaytracingAccelerationStructurePrebuildInfo(&bottom.Inputs, &bottom_size);
    dxr->GetRaytracingAccelerationStructurePrebuildInfo(&top.Inputs, &top_size);
    if (!bottom_size.ResultDataMaxSizeInBytes || !top_size.ResultDataMaxSizeInBytes)
        throw std::runtime_error("No acceleration structure prebuild size");
    constexpr auto writable = D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS;
    constexpr auto as_state = D3D12_RESOURCE_STATE_RAYTRACING_ACCELERATION_STRUCTURE;
    auto blas = make_buffer(device, bottom_size.ResultDataMaxSizeInBytes, D3D12_HEAP_TYPE_DEFAULT, as_state, writable);
    auto tlas = make_buffer(device, top_size.ResultDataMaxSizeInBytes, D3D12_HEAP_TYPE_DEFAULT, as_state, writable);
    auto scratch = make_buffer(device, (std::max)(bottom_size.ScratchDataSizeInBytes, top_size.ScratchDataSizeInBytes),
                               D3D12_HEAP_TYPE_DEFAULT, D3D12_RESOURCE_STATE_COMMON, writable);
    bottom.DestAccelerationStructureData = blas->GetGPUVirtualAddress();
    top.DestAccelerationStructureData = tlas->GetGPUVirtualAddress();
    bottom.ScratchAccelerationStructureData = top.ScratchAccelerationStructureData = scratch->GetGPUVirtualAddress();
    for (auto& desc : instances) desc.AccelerationStructure = bottom.DestAccelerationStructureData;
    auto instanceBuffer = bvh_fixture::upload(device, instances);
    top.Inputs.InstanceDescs = instanceBuffer->GetGPUVirtualAddress();
    const UINT result_bytes = static_cast<UINT>(rays.size() * sizeof(bvh_fixture::Row));
    const bvh_fixture::Row sentinel{UINT32_MAX, UINT32_MAX, UINT32_MAX, UINT32_MAX};
    auto initial = bvh_fixture::upload(device, std::vector<bvh_fixture::Row>(rays.size(), sentinel));
    auto results = make_buffer(device, result_bytes, D3D12_HEAP_TYPE_DEFAULT, D3D12_RESOURCE_STATE_COMMON, writable);
    auto readback = make_buffer(device, result_bytes, D3D12_HEAP_TYPE_READBACK, D3D12_RESOURCE_STATE_COPY_DEST);
    ComPtr<ID3D12RootSignature> root;
    check(device->CreateRootSignature(0, ray_query, sizeof(ray_query), IID_PPV_ARGS(&root)), "Create ray query root");
    D3D12_COMPUTE_PIPELINE_STATE_DESC pso{};
    pso.pRootSignature = root.Get();
    pso.CS = {ray_query, sizeof(ray_query)};
    ComPtr<ID3D12PipelineState> pipeline;
    check(device->CreateComputePipelineState(&pso, IID_PPV_ARGS(&pipeline)), "Create ray query pipeline");
    ComputeCommands commands(device, pipeline.Get());
    ComPtr<ID3D12GraphicsCommandList4> list;
    check(commands.list.As(&list), "Get DXR command list");
    transition(list.Get(), results.Get(), D3D12_RESOURCE_STATE_COMMON, D3D12_RESOURCE_STATE_COPY_DEST);
    list->CopyBufferRegion(results.Get(), 0, initial.Get(), 0, result_bytes);
    transition(list.Get(), results.Get(), D3D12_RESOURCE_STATE_COPY_DEST, D3D12_RESOURCE_STATE_UNORDERED_ACCESS);
    transition(list.Get(), scratch.Get(), D3D12_RESOURCE_STATE_COMMON, D3D12_RESOURCE_STATE_UNORDERED_ACCESS);
    D3D12_RESOURCE_BARRIER order{};
    order.Type = D3D12_RESOURCE_BARRIER_TYPE_UAV;
    // Order both the BLAS write and the reused scratch storage before building the TLAS.
    list->BuildRaytracingAccelerationStructure(&bottom, 0, nullptr);
    list->ResourceBarrier(1, &order);
    list->BuildRaytracingAccelerationStructure(&top, 0, nullptr);
    order.UAV.pResource = tlas.Get();
    list->ResourceBarrier(1, &order);
    list->SetComputeRootSignature(root.Get());
    list->SetComputeRootShaderResourceView(0, tlas->GetGPUVirtualAddress());
    list->SetComputeRootUnorderedAccessView(1, results->GetGPUVirtualAddress());
    list->SetComputeRootShaderResourceView(2, rayBuffer->GetGPUVirtualAddress());
    list->Dispatch(static_cast<UINT>(rays.size()), 1, 1);
    transition(list.Get(), results.Get(), D3D12_RESOURCE_STATE_UNORDERED_ACCESS, D3D12_RESOURCE_STATE_COPY_SOURCE);
    list->CopyBufferRegion(readback.Get(), 0, results.Get(), 0, result_bytes);
    commands.submit_and_wait(device);

    return bvh_fixture::read(readback.Get(), rays.size()*4);
}
}

bool check_ray_query(ID3D12Device* device) {
    using namespace dxr_fixture;
    if (!supported(device)) return false;
    const std::vector<Vertex> vertices{{-1,-1,1}, {1,-1,1}, {0,1,1}};
    std::vector<Ray> rays;
    for (UINT i = 0; i < 5; ++i)
        rays.push_back({i >= 3 ? 3.f : (i == 1 ? 1.5f : 0.f), 0, 0, .01f, 0, 0, 1,
                        i == 2 ? .5f : 5.f, i == 3 ? 2u : 1u});
    auto words = trace(device, vertices, {instance(7, 1), instance(11, 2, 3)}, rays);
    constexpr UINT expected_id[]{7, 0, 0, 11, 0};
    UINT mismatches = 0;
    for (UINT i = 0; i < 5; ++i) {
        const UINT* value = words.data() + 4 * i;
        float distance;
        std::memcpy(&distance, value + 3, sizeof(distance));
        const bool hit = expected_id[i] != 0;
        const bool distance_matches = hit ? std::abs(distance - 1.f) < 1e-5f : value[3] == 0;
        if (value[0] != static_cast<UINT>(hit) || value[1] != expected_id[i] || value[2] != 0 || !distance_matches)
            ++mismatches;
        std::printf("ray=%u hit=%u instance=%u primitive=%u distance=%g\n", i, value[0], value[1], value[2], distance);
    }
    if (mismatches) throw std::runtime_error("Ray query disagrees with triangle, distance or mask reference");
    return true;
}
