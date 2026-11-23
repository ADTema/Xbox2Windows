// Source-built consumer for the main executable's A/B range translation (#874).
// The title keeps a CPU range A and a range B of the same size and translates by offset:
// gpu = cpu - A + B, and a GPU address inside [B, B + size) back to cpu = gpu - B + A
// (anything else passes through unchanged). These checks ask whether a desktop D3D12
// device can give A a GPU view that keeps that offset.
//   shared_range      no device: A and B are one reservation, so both directions are the identity
//   device_<adapter>  A is one committed allocation wrapped as a D3D12 heap with one buffer over it
// Returns 0 on pass, 1 on failure, 77 (skip) without the adapter or ID3D12Device3.
#include <windows.h>
#include <d3d12.h>
#include <dxgi1_6.h>
#include <wrl/client.h>

#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string_view>

#include "vm_translation_cs.h"
#include "xmem_test_device.h"

using Microsoft::WRL::ComPtr;
using namespace std::literals;

namespace {
constexpr std::uint64_t range_size = 64ull << 20;
constexpr UINT words = 1024;
constexpr std::uint32_t key = 0x5a5a5a5au;

// Mirrors the title's two helpers.
struct RangePair {
    std::uintptr_t a;
    std::uint64_t b;
    std::uint64_t size;
    std::uint64_t to_gpu(const void* p) const { return reinterpret_cast<std::uintptr_t>(p) - a + b; }
    std::uint64_t to_cpu(std::uint64_t va) const { return va >= b && va - b < size ? va - b + a : va; }
};

unsigned failures = 0;
void expect(bool ok, const char* what)
{
    std::printf("%s %s\n", ok ? "ok" : "FAIL", what);
    failures += !ok;
}

bool shared_range_checks()
{
    // The title's no-device path releases A and B and reserves one range used as both.
    void* a = VirtualAlloc(nullptr, range_size, MEM_RESERVE, PAGE_READWRITE);
    void* b = VirtualAlloc(nullptr, range_size, MEM_RESERVE, PAGE_READWRITE);
    expect(a && b && a != b, "two separate reservations");
    VirtualFree(a, 0, MEM_RELEASE);
    VirtualFree(b, 0, MEM_RELEASE);
    auto* shared = static_cast<std::uint8_t*>(
        VirtualAlloc(nullptr, range_size, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE));
    if (!shared) return false;
    const RangePair pair{reinterpret_cast<std::uintptr_t>(shared), reinterpret_cast<std::uintptr_t>(shared), range_size};

    bool identity = true;
    for (std::uint64_t offset : {0ull, 0x10000ull, range_size / 2, range_size - 4}) {
        const void* p = shared + offset;
        identity &= pair.to_gpu(p) == reinterpret_cast<std::uintptr_t>(p);
        identity &= pair.to_cpu(pair.to_gpu(p)) == reinterpret_cast<std::uintptr_t>(p);
    }
    expect(identity, "A == B: both directions are the identity inside the range");
    const std::uint64_t outside = pair.b + range_size;
    expect(pair.to_cpu(outside) == outside && pair.to_cpu(pair.b - 1) == pair.b - 1,
           "addresses just outside the range pass through");
    VirtualFree(shared, 0, MEM_RELEASE);
    std::printf("shared_range failures=%u\n", failures);
    return failures == 0;
}

struct Gpu {
    ComPtr<ID3D12Device3> device;
    ComPtr<ID3D12CommandQueue> queue;
    ComPtr<ID3D12CommandAllocator> allocator;
    ComPtr<ID3D12GraphicsCommandList> list;
    ComPtr<ID3D12Fence> fence;
    ComPtr<ID3D12RootSignature> root;
    ComPtr<ID3D12PipelineState> pipeline;
    UINT64 value = 0;

    bool init()
    {
        D3D12_COMMAND_QUEUE_DESC queue_desc{};
        queue_desc.Type = D3D12_COMMAND_LIST_TYPE_DIRECT;
        D3D12_ROOT_PARAMETER params[2]{};
        for (UINT i = 0; i < 2; ++i) {
            params[i].ParameterType = D3D12_ROOT_PARAMETER_TYPE_UAV;
            params[i].Descriptor.ShaderRegister = i;
        }
        const D3D12_ROOT_SIGNATURE_DESC root_desc{2, params, 0, nullptr, D3D12_ROOT_SIGNATURE_FLAG_NONE};
        ComPtr<ID3DBlob> blob;
        if (FAILED(device->CreateCommandQueue(&queue_desc, IID_PPV_ARGS(&queue))) ||
            FAILED(device->CreateCommandAllocator(D3D12_COMMAND_LIST_TYPE_DIRECT, IID_PPV_ARGS(&allocator))) ||
            FAILED(device->CreateCommandList(0, D3D12_COMMAND_LIST_TYPE_DIRECT, allocator.Get(), nullptr,
                                             IID_PPV_ARGS(&list))) ||
            FAILED(device->CreateFence(0, D3D12_FENCE_FLAG_NONE, IID_PPV_ARGS(&fence))) ||
            FAILED(D3D12SerializeRootSignature(&root_desc, D3D_ROOT_SIGNATURE_VERSION_1, &blob, nullptr)) ||
            FAILED(device->CreateRootSignature(0, blob->GetBufferPointer(), blob->GetBufferSize(),
                                               IID_PPV_ARGS(&root)))) {
            return false;
        }
        D3D12_COMPUTE_PIPELINE_STATE_DESC pso{};
        pso.pRootSignature = root.Get();
        pso.CS = {vm_translation_cs, sizeof(vm_translation_cs)};
        return SUCCEEDED(device->CreateComputePipelineState(&pso, IID_PPV_ARGS(&pipeline)));
    }

    // One dispatch with both root UAVs given as raw GPU addresses.
    bool dispatch(ID3D12Resource* resource, std::uint64_t src, std::uint64_t dst)
    {
        D3D12_RESOURCE_BARRIER barrier{};
        barrier.Transition.pResource = resource;
        barrier.Transition.Subresource = D3D12_RESOURCE_BARRIER_ALL_SUBRESOURCES;
        barrier.Transition.StateBefore = D3D12_RESOURCE_STATE_COMMON;
        barrier.Transition.StateAfter = D3D12_RESOURCE_STATE_UNORDERED_ACCESS;
        list->ResourceBarrier(1, &barrier);
        list->SetComputeRootSignature(root.Get());
        list->SetPipelineState(pipeline.Get());
        list->SetComputeRootUnorderedAccessView(0, src);
        list->SetComputeRootUnorderedAccessView(1, dst);
        list->Dispatch(words / 64, 1, 1);
        std::swap(barrier.Transition.StateBefore, barrier.Transition.StateAfter);
        list->ResourceBarrier(1, &barrier);
        if (FAILED(list->Close())) return false;
        ID3D12CommandList* lists[] = {list.Get()};
        queue->ExecuteCommandLists(1, lists);
        HANDLE event = CreateEventW(nullptr, FALSE, FALSE, nullptr);
        const bool done = event && SUCCEEDED(queue->Signal(fence.Get(), ++value)) &&
                          SUCCEEDED(fence->SetEventOnCompletion(value, event)) &&
                          WaitForSingleObject(event, 20000) == WAIT_OBJECT_0;
        if (event) CloseHandle(event);
        return done && SUCCEEDED(allocator->Reset()) && SUCCEEDED(list->Reset(allocator.Get(), nullptr));
    }
};

D3D12_RESOURCE_DESC buffer_desc(std::uint64_t size, D3D12_RESOURCE_FLAGS flags)
{
    D3D12_RESOURCE_DESC desc{};
    desc.Dimension = D3D12_RESOURCE_DIMENSION_BUFFER;
    desc.Width = size;
    desc.Height = 1;
    desc.DepthOrArraySize = 1;
    desc.MipLevels = 1;
    desc.SampleDesc.Count = 1;
    desc.Layout = D3D12_TEXTURE_LAYOUT_ROW_MAJOR;
    desc.Flags = flags;
    return desc;
}

void fill(std::uint32_t* words_out, std::uint32_t seed)
{
    for (UINT i = 0; i < words; ++i) words_out[i] = seed + i * 2654435761u;
}

unsigned mismatches(const std::uint32_t* src, const std::uint32_t* dst)
{
    unsigned bad = 0;
    for (UINT i = 0; i < words; ++i) bad += dst[i] != (src[i] ^ key);
    return bad;
}

int device_checks(bool warp)
{
    bool unmatched = false;
    const auto base = create_device(warp, unmatched);
    if (unmatched) return 1;
    Gpu gpu;
    if (!base || FAILED(base.As(&gpu.device))) {
        std::puts(warp ? "No ID3D12Device3 on WARP" : "No hardware adapter with ID3D12Device3");
        return 77;
    }
    if (!gpu.init()) {
        std::puts("compute setup failed");
        return 1;
    }

    // Refusals: a reserve-only range, and an address inside an allocation.
    {
        void* reserved = VirtualAlloc(nullptr, range_size, MEM_RESERVE, PAGE_READWRITE);
        ComPtr<ID3D12Heap> heap;
        const HRESULT hr = gpu.device->OpenExistingHeapFromAddress(reserved, IID_PPV_ARGS(&heap));
        std::printf("reserve-only range hr=0x%08lx\n", static_cast<unsigned long>(hr));
        expect(FAILED(hr), "a reserve-only range cannot be opened as a heap");
        VirtualFree(reserved, 0, MEM_RELEASE);
    }
    auto* a = static_cast<std::uint8_t*>(VirtualAlloc(nullptr, range_size, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE));
    if (!a) return 1;
    {
        ComPtr<ID3D12Heap> heap;
        const HRESULT hr = gpu.device->OpenExistingHeapFromAddress(a + range_size / 2, IID_PPV_ARGS(&heap));
        std::printf("interior address hr=0x%08lx\n", static_cast<unsigned long>(hr));
        expect(FAILED(hr), "an address inside the allocation cannot be opened as a heap");
    }

    // Device path: wrap all of A once and place one buffer over it. Its GPU address is B.
    ComPtr<ID3D12Heap> heap;
    HRESULT hr = gpu.device->OpenExistingHeapFromAddress(a, IID_PPV_ARGS(&heap));
    std::printf("committed range hr=0x%08lx\n", static_cast<unsigned long>(hr));
    if (hr == E_NOTIMPL || hr == DXGI_ERROR_UNSUPPORTED) {
        std::puts("OpenExistingHeapFromAddress unsupported on this adapter");
        VirtualFree(a, 0, MEM_RELEASE);
        return 77;
    }
    ComPtr<ID3D12Resource> whole;
    const auto whole_desc = buffer_desc(range_size, D3D12_RESOURCE_FLAG_ALLOW_CROSS_ADAPTER |
                                                        D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS);
    if (SUCCEEDED(hr)) {
        hr = gpu.device->CreatePlacedResource(heap.Get(), 0, &whole_desc, D3D12_RESOURCE_STATE_COMMON, nullptr,
                                              IID_PPV_ARGS(&whole));
    }
    expect(SUCCEEDED(hr), "wrap the committed range and place one buffer over it");
    if (FAILED(hr)) {
        VirtualFree(a, 0, MEM_RELEASE);
        return 1;
    }
    const RangePair pair{reinterpret_cast<std::uintptr_t>(a), whole->GetGPUVirtualAddress(), range_size};
    std::printf("B != A: %d\n", pair.b != pair.a);

    // CPU -> GPU: the shader sees only addresses computed as p - A + B.
    auto* src = reinterpret_cast<std::uint32_t*>(a + range_size / 2);
    auto* dst = reinterpret_cast<std::uint32_t*>(a + range_size - 0x8000);
    fill(src, 0x10000000u);
    std::memset(dst, 0xcd, words * 4);
    expect(gpu.dispatch(whole.Get(), pair.to_gpu(src), pair.to_gpu(dst)) && mismatches(src, dst) == 0,
           "GPU reads CPU-written words and writes CPU-visible words through p - A + B");

    // GPU -> CPU: a live resource's own GPU address, translated back with va - B + A.
    {
        constexpr std::uint64_t offset = 0x200000;
        ComPtr<ID3D12Resource> part;
        const auto part_desc = buffer_desc(0x10000, D3D12_RESOURCE_FLAG_ALLOW_CROSS_ADAPTER |
                                                        D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS);
        hr = gpu.device->CreatePlacedResource(heap.Get(), offset, &part_desc, D3D12_RESOURCE_STATE_COMMON, nullptr,
                                              IID_PPV_ARGS(&part));
        expect(SUCCEEDED(hr), "place a second live buffer inside the wrapped range");
        if (SUCCEEDED(hr)) {
            const std::uint64_t va = part->GetGPUVirtualAddress();
            std::printf("placed buffer at +0x%llx: gpu - B = 0x%llx\n", static_cast<unsigned long long>(offset),
                        static_cast<unsigned long long>(va - pair.b));
            // A wrong translation is not dereferenced: outside A it would be an arbitrary pointer.
            const std::uint64_t translated = pair.to_cpu(va);
            const bool same_offset = translated == pair.a + offset;
            expect(same_offset, "its GPU address translates to the CPU address at the same offset");
            if (same_offset) {
                auto* cpu = reinterpret_cast<std::uint32_t*>(translated);
                fill(src, 0x30000000u);
                std::memset(cpu, 0xcd, words * 4);
                expect(gpu.dispatch(whole.Get(), pair.to_gpu(src), va) && mismatches(src, cpu) == 0,
                       "GPU writes through the live resource's address are visible at the translated CPU address");
            }
        }
    }

    // Mismatched ranges: an address from another resource passes through, and a wrong B misplaces data.
    {
        ComPtr<ID3D12Resource> other;
        D3D12_HEAP_PROPERTIES props{};
        props.Type = D3D12_HEAP_TYPE_DEFAULT;
        const auto other_desc = buffer_desc(0x10000, D3D12_RESOURCE_FLAG_NONE);
        hr = gpu.device->CreateCommittedResource(&props, D3D12_HEAP_FLAG_NONE, &other_desc,
                                                 D3D12_RESOURCE_STATE_COMMON, nullptr, IID_PPV_ARGS(&other));
        if (SUCCEEDED(hr)) {
            const std::uint64_t va = other->GetGPUVirtualAddress();
            const bool outside = va < pair.b || va - pair.b >= range_size;
            expect(outside && pair.to_cpu(va) == va,
                   "an unrelated buffer's GPU address lies outside [B, B + size) and passes through untranslated");
        } else {
            expect(false, "create an unrelated committed buffer");
        }

        // Both shifted addresses stay inside the wrapped buffer.
        auto* mid_src = reinterpret_cast<std::uint32_t*>(a + range_size / 4);
        auto* mid_dst = reinterpret_cast<std::uint32_t*>(a + range_size / 2);
        const RangePair shifted{pair.a, pair.b + 0x10000, range_size};
        fill(mid_src, 0x50000000u);
        std::memset(mid_dst, 0xcd, words * 4);
        const bool ran = gpu.dispatch(whole.Get(), shifted.to_gpu(mid_src), shifted.to_gpu(mid_dst));
        const unsigned bad = mismatches(mid_src, mid_dst);
        const bool untouched = mid_dst[0] == 0xcdcdcdcdu && mid_dst[words - 1] == 0xcdcdcdcdu;
        std::printf("B shifted by 64 KiB: %u/%u words wrong at the intended destination\n", bad, words);
        expect(ran && bad == words && untouched, "a B off by one 64 KiB page misses the intended words");
    }

    VirtualFree(a, 0, MEM_RELEASE);
    std::printf("device failures=%u\n", failures);
    return failures ? 1 : 0;
}
}

int main(int argc, char** argv)
{
    if (argc != 2) return 2;
    const std::string_view scenario = argv[1];
    int result = 2;
    if (scenario == "shared_range"sv) {
        result = shared_range_checks() ? 0 : 1;
    } else if (scenario == "device_warp"sv) {
        result = device_checks(true);
    } else if (scenario == "device_hardware"sv) {
        result = device_checks(false);
    }
    std::printf("vm_translation %s: %s\n", argv[1], result == 0 ? "PASS" : result == 77 ? "SKIP" : "FAIL");
    return result;
}
