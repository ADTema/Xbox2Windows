#include "desktop_gpu.h"
#include "CopyBlocks.h"
#include "FillBlocks.h"
#include "NumberBlocks.h"
#include "CopySpan.h"
#include "ResetBounds.h"
#include <array>
#include <algorithm>
#include <cstdio>
#include <cstring>
#include <stdexcept>

using Microsoft::WRL::ComPtr;

namespace {
enum class Operation { copy, fill, number, span };
constexpr UINT capacity = 384;
using Words = std::array<UINT, capacity>;
using Pipelines = std::array<ComPtr<ID3D12PipelineState>, 5>;
constexpr UINT seed = 0xfffffffcu;
constexpr UINT sentinel = 0xcdfa1538u;

void run_case(ID3D12Device* device, ID3D12RootSignature* root, const Pipelines& pipelines,
              Operation op, UINT count, UINT groups, bool reset)
{
    Words source{}, expected;
    expected.fill(sentinel);
    for (UINT i = 0; i < capacity; ++i) source[i] = (0x7133u + i * 97u) ^ (i << 15);
    source[1] = count;
    const UINT active_words = op == Operation::span ? 16 * (count + 1) : 4 * count;
    if (active_words > capacity || groups == 0) throw std::runtime_error("Invalid buffer fixture");
    for (UINT i = 0; i < active_words; ++i) {
        switch (op) {
        case Operation::copy: case Operation::span: expected[i] = source[i]; break;
        case Operation::fill: expected[i] = seed; break;
        case Operation::number: expected[i] = seed + i; break;
        }
    }
    if (reset) {
        std::fill_n(expected.begin() + 4, 3, 0x7f7fffffu);
        std::fill_n(expected.begin() + 7, 3, 0xff7fffffu);
    }
    auto upload = make_buffer(device, 2 * sizeof(Words), D3D12_HEAP_TYPE_UPLOAD, D3D12_RESOURCE_STATE_GENERIC_READ);
    auto output = make_buffer(device, sizeof(Words), D3D12_HEAP_TYPE_DEFAULT, D3D12_RESOURCE_STATE_COMMON,
                              D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS);
    auto readback = make_buffer(device, sizeof(Words), D3D12_HEAP_TYPE_READBACK, D3D12_RESOURCE_STATE_COPY_DEST);
    void* pointer = nullptr;
    const D3D12_RANGE empty{};
    check(upload->Map(0, &empty, &pointer), "Map buffer fixture input");
    std::memcpy(pointer, source.data(), sizeof(source));
    std::fill_n(static_cast<UINT*>(pointer) + capacity, capacity, sentinel);
    upload->Unmap(0, nullptr);
    ComputeCommands commands(device, pipelines[static_cast<size_t>(op)].Get());
    auto* list = commands.list.Get();
    transition(list, output.Get(), D3D12_RESOURCE_STATE_COMMON, D3D12_RESOURCE_STATE_COPY_DEST);
    list->CopyBufferRegion(output.Get(), 0, upload.Get(), sizeof(Words), sizeof(Words));
    transition(list, output.Get(), D3D12_RESOURCE_STATE_COPY_DEST, D3D12_RESOURCE_STATE_UNORDERED_ACCESS);
    list->SetComputeRootSignature(root);
    list->SetComputeRootShaderResourceView(0, upload->GetGPUVirtualAddress());
    list->SetComputeRootUnorderedAccessView(1, output->GetGPUVirtualAddress());
    std::array<UINT, 16> settings{groups * 32, op == Operation::span ? static_cast<UINT>(reset) : count, seed};
    list->SetComputeRoot32BitConstants(2, static_cast<UINT>(settings.size()), settings.data(), 0);
    list->Dispatch(groups, 1, 1);
    if (reset) {
        D3D12_RESOURCE_BARRIER order{};
        order.Type = D3D12_RESOURCE_BARRIER_TYPE_UAV;
        order.UAV.pResource = output.Get();
        list->ResourceBarrier(1, &order);
        list->SetPipelineState(pipelines.back().Get());
        list->Dispatch(1, 1, 1);
    }
    transition(list, output.Get(), D3D12_RESOURCE_STATE_UNORDERED_ACCESS, D3D12_RESOURCE_STATE_COPY_SOURCE);
    list->CopyBufferRegion(readback.Get(), 0, output.Get(), 0, sizeof(Words));
    commands.submit_and_wait(device);
    const D3D12_RANGE range{0, sizeof(Words)};
    check(readback->Map(0, &range, &pointer), "Map buffer operation results");
    const auto* actual = static_cast<const UINT*>(pointer);
    const auto mismatch = std::mismatch(expected.begin(), expected.end(), actual);
    const bool pass = mismatch.first == expected.end();
    if (!pass)
        std::fprintf(stderr, "operation=%u count=%u groups=%u reset=%u word=%zu expected=%08x actual=%08x\n",
                     static_cast<unsigned>(op), count, groups, static_cast<unsigned>(reset),
                     static_cast<size_t>(mismatch.first - expected.begin()), *mismatch.first, *mismatch.second);
    readback->Unmap(0, &empty);
    if (!pass) throw std::runtime_error("Buffer operation disagrees with CPU result");
}
}

void check_buffer_ops(ID3D12Device* device)
{
    const D3D12_SHADER_BYTECODE code[] = {{CopyBlocks, sizeof(CopyBlocks)}, {FillBlocks, sizeof(FillBlocks)},
        {NumberBlocks, sizeof(NumberBlocks)}, {CopySpan, sizeof(CopySpan)}, {ResetBounds, sizeof(ResetBounds)}};
    ComPtr<ID3D12RootSignature> root;
    check(device->CreateRootSignature(0, CopyBlocks, sizeof(CopyBlocks), IID_PPV_ARGS(&root)), "Create buffer ops root");
    Pipelines pipelines;
    for (size_t i = 0; i < pipelines.size(); ++i) {
        D3D12_COMPUTE_PIPELINE_STATE_DESC desc{};
        desc.pRootSignature = root.Get();
        desc.CS = code[i];
        check(device->CreateComputePipelineState(&desc, IID_PPV_ARGS(&pipelines[i])), "Create buffer operation PSO");
    }
    for (auto op : {Operation::copy, Operation::fill, Operation::number})
        for (UINT count : {0u, 1u, 31u, 32u, 33u, 65u}) run_case(device, root.Get(), pipelines, op, count, 3, false);
    for (UINT groups : {1u, 2u})
        for (UINT count : {0u, 16u})
            for (bool reset : {false, true}) run_case(device, root.Get(), pipelines, Operation::span, count, groups, reset);
    std::printf("buffer_cases=26 words_per_case=%u mismatches=0\n", capacity);
}
