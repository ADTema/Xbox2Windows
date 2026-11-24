#include "desktop_gpu.h"
#include "descriptor_window_submissions_cs.h"

#include <array>
#include <cstdint>
#include <cstdio>
#include <cstring>

using Microsoft::WRL::ComPtr;

namespace {
constexpr UINT descriptor_count = D3D12_MAX_SHADER_VISIBLE_DESCRIPTOR_HEAP_SIZE_TIER_1;
constexpr std::uint32_t first_word = 0x13579bdf;
constexpr std::uint32_t second_word = 0x2468ace0;
constexpr std::uint32_t untouched = 0xa5a5a5a5;
constexpr UINT word_bytes = sizeof(std::uint32_t);
constexpr UINT input_stride_words = D3D12_RAW_UAV_SRV_BYTE_ALIGNMENT / word_bytes;
using Words = std::array<std::uint32_t, 2>;

ComPtr<ID3D12RootSignature> create_root(ID3D12Device* device)
{
    const D3D12_DESCRIPTOR_RANGE range{D3D12_DESCRIPTOR_RANGE_TYPE_SRV, 1, 0, 0, 0};
    D3D12_ROOT_PARAMETER params[3]{};
    params[0].ParameterType = D3D12_ROOT_PARAMETER_TYPE_DESCRIPTOR_TABLE;
    params[0].DescriptorTable = {1, &range};
    params[1].ParameterType = D3D12_ROOT_PARAMETER_TYPE_UAV;
    params[1].Descriptor = {0, 0};
    params[2].ParameterType = D3D12_ROOT_PARAMETER_TYPE_32BIT_CONSTANTS;
    params[2].Constants = {0, 0, 1};
    D3D12_ROOT_SIGNATURE_DESC desc{};
    desc.NumParameters = _countof(params);
    desc.pParameters = params;
    ComPtr<ID3DBlob> signature;
    check(D3D12SerializeRootSignature(&desc, D3D_ROOT_SIGNATURE_VERSION_1, &signature, nullptr),
          "Serialize descriptor-window root signature");
    ComPtr<ID3D12RootSignature> root;
    check(device->CreateRootSignature(0, signature->GetBufferPointer(), signature->GetBufferSize(), IID_PPV_ARGS(&root)),
          "Create descriptor-window root signature");
    return root;
}

void compare_words(UINT64 fence_value, const Words& actual, const Words& expected)
{
    std::printf("descriptor_windows fence=%llu words=%08x,%08x expected=%08x,%08x\n",
                fence_value, actual[0], actual[1], expected[0], expected[1]);
    if (actual != expected) throw std::runtime_error("Descriptor-window readback differs from reference");
}
}

void check_descriptor_window_submissions(ID3D12Device* device, bool stale)
{
    const auto root = create_root(device);
    D3D12_COMPUTE_PIPELINE_STATE_DESC pipeline_desc{};
    pipeline_desc.pRootSignature = root.Get();
    pipeline_desc.CS = {descriptor_window_submissions_cs, sizeof(descriptor_window_submissions_cs)};
    ComPtr<ID3D12PipelineState> pipeline;
    check(device->CreateComputePipelineState(&pipeline_desc, IID_PPV_ARGS(&pipeline)),
          "Create descriptor-window compute pipeline");

    D3D12_DESCRIPTOR_HEAP_DESC heap_desc{};
    heap_desc.Type = D3D12_DESCRIPTOR_HEAP_TYPE_CBV_SRV_UAV;
    heap_desc.NumDescriptors = descriptor_count;
    heap_desc.Flags = D3D12_DESCRIPTOR_HEAP_FLAG_SHADER_VISIBLE;
    ComPtr<ID3D12DescriptorHeap> heap;
    const HRESULT heap_hr = device->CreateDescriptorHeap(&heap_desc, IID_PPV_ARGS(&heap));
    std::printf("descriptor_windows heap_request=%u create_hresult=0x%08lx\n", descriptor_count,
                static_cast<unsigned long>(heap_hr));
    check(heap_hr, "Create shader-visible descriptor-window heap");
    const UINT stride = device->GetDescriptorHandleIncrementSize(heap_desc.Type);

    constexpr UINT guard_index = input_stride_words + 1;
    std::array<std::uint32_t, guard_index + 2> initial{};
    initial[0] = first_word;
    initial[input_stride_words] = second_word;
    initial[guard_index] = initial[guard_index + 1] = untouched;
    const auto upload = make_buffer(device, sizeof(initial), D3D12_HEAP_TYPE_UPLOAD, D3D12_RESOURCE_STATE_GENERIC_READ);
    void* mapped = nullptr;
    const D3D12_RANGE no_read{0, 0};
    check(upload->Map(0, &no_read, &mapped), "Map descriptor-window inputs");
    std::memcpy(mapped, initial.data(), sizeof(initial));
    const D3D12_RANGE input_written{0, sizeof(initial)};
    upload->Unmap(0, &input_written);
    const auto output = make_buffer(device, sizeof(Words), D3D12_HEAP_TYPE_DEFAULT, D3D12_RESOURCE_STATE_COPY_DEST,
                                    D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS);
    const auto readback = make_buffer(device, sizeof(Words), D3D12_HEAP_TYPE_READBACK, D3D12_RESOURCE_STATE_COPY_DEST);

    constexpr std::array<UINT, 2> windows{0, descriptor_count - 1};
    D3D12_SHADER_RESOURCE_VIEW_DESC srv{};
    srv.Format = DXGI_FORMAT_R32_TYPELESS;
    srv.ViewDimension = D3D12_SRV_DIMENSION_BUFFER;
    srv.Shader4ComponentMapping = D3D12_DEFAULT_SHADER_4_COMPONENT_MAPPING;
    srv.Buffer.NumElements = 1;
    srv.Buffer.Flags = D3D12_BUFFER_SRV_FLAG_RAW;
    for (UINT i = 0; i < windows.size(); ++i) {
        auto handle = heap->GetCPUDescriptorHandleForHeapStart();
        handle.ptr += SIZE_T{windows[i]} * stride;
        srv.Buffer.FirstElement = i * input_stride_words;
        device->CreateShaderResourceView(upload.Get(), &srv, handle);
    }

    ComputeCommands commands(device, pipeline.Get(), D3D12_COMMAND_LIST_TYPE_DIRECT);
    ComPtr<ID3D12Fence> fence;
    check(device->CreateFence(0, D3D12_FENCE_FLAG_NONE, IID_PPV_ARGS(&fence)), "Create descriptor-window fence");
    auto* list = commands.list.Get();
    list->CopyBufferRegion(output.Get(), 0, upload.Get(), guard_index * word_bytes, sizeof(Words));
    const std::array<Words, 2> expected{Words{first_word, untouched}, Words{first_word, stale ? first_word : second_word}};
    auto before = D3D12_RESOURCE_STATE_COPY_DEST;
    for (UINT i = 0; i < windows.size(); ++i) {
        transition(list, output.Get(), before, D3D12_RESOURCE_STATE_UNORDERED_ACCESS);
        list->SetComputeRootSignature(root.Get());
        ID3D12DescriptorHeap* heaps[]{heap.Get()};
        list->SetDescriptorHeaps(1, heaps);
        const UINT slot = windows[stale ? 0 : i];
        auto gpu = heap->GetGPUDescriptorHandleForHeapStart();
        gpu.ptr += UINT64{slot} * stride;
        list->SetComputeRootDescriptorTable(0, gpu);
        list->SetComputeRootUnorderedAccessView(1, output->GetGPUVirtualAddress());
        list->SetComputeRoot32BitConstant(2, i * word_bytes, 0);
        list->Dispatch(1, 1, 1);
        transition(list, output.Get(), D3D12_RESOURCE_STATE_UNORDERED_ACCESS, D3D12_RESOURCE_STATE_COPY_SOURCE);
        list->CopyResource(readback.Get(), output.Get());
        transition(list, output.Get(), D3D12_RESOURCE_STATE_COPY_SOURCE, D3D12_RESOURCE_STATE_COMMON);

        const UINT64 fence_value = UINT64{i} + 1;
        std::printf("descriptor_windows submit=%llu slot=%u\n", fence_value, slot);
        check(list->Close(), "Close descriptor-window list");
        ID3D12CommandList* submitted[]{list};
        commands.queue->ExecuteCommandLists(1, submitted);
        check(commands.queue->Signal(fence.Get(), fence_value), "Signal descriptor-window fence");
        check(fence->SetEventOnCompletion(fence_value, nullptr), "Wait for descriptor-window fence");
        check(device->GetDeviceRemovedReason(), "Complete descriptor-window submission");
        if (fence->GetCompletedValue() != fence_value) throw std::runtime_error("Unexpected descriptor-window fence value");

        Words actual{};
        const D3D12_RANGE read_range{0, sizeof(actual)};
        check(readback->Map(0, &read_range, &mapped), "Map descriptor-window readback");
        std::memcpy(actual.data(), mapped, sizeof(actual));
        readback->Unmap(0, &no_read);
        compare_words(fence_value, actual, expected[i]);
        if (i + 1 < windows.size()) {
            check(commands.allocator->Reset(), "Reset descriptor-window allocator");
            check(list->Reset(commands.allocator.Get(), pipeline.Get()), "Reset descriptor-window list");
            before = D3D12_RESOURCE_STATE_COMMON;
        }
    }
}
