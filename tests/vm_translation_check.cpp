// Source-built consumer for the main executable's A/B range translation (#874).
// The title keeps a CPU range A and a range B of the same size and translates by offset:
// gpu = cpu - A + B, and a GPU address inside [B, B + size) back to cpu = gpu - B + A
// (anything else passes through unchanged). These checks ask whether a desktop D3D12
// device can give A a GPU view that keeps that offset.
//   shared_range        no device: A and B are one reservation, so both directions are the identity
//   device_<adapter>    A is one committed allocation wrapped as a D3D12 heap with one buffer over it
//   sequence_<adapter>  the title's order through d3d12_xs.dll: configure, create the device, create
//                       the first DIRECT queue, then the device_<adapter> checks on that queue
// Returns 0 on pass, 1 on failure, 77 (skip) without the adapter or ID3D12Device3.
#include <windows.h>
#include <d3d12.h>
#include <dxgi1_6.h>
#include <wrl/client.h>

#include <array>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string_view>

#include "vm_translation_cs.h"
#include "xmem_test_device.h"

extern "C" HRESULT WINAPI D3D12ConfigureVirtualMemoryX(const void* config);
extern "C" HRESULT WINAPI D3D12XboxCreateDevice(IUnknown* adapter, const void* parameters, REFIID iid,
                                                void** device);

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

// Owns a VirtualAlloc range. Objects that use the range are declared after it, so they are released first.
struct VirtualRange {
    std::uint8_t* base = nullptr;
    explicit VirtualRange(void* p) : base(static_cast<std::uint8_t*>(p)) {}
    VirtualRange(const VirtualRange&) = delete;
    VirtualRange& operator=(const VirtualRange&) = delete;
    ~VirtualRange()
    {
        if (base) VirtualFree(base, 0, MEM_RELEASE);
    }
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
        if ((!queue && FAILED(device->CreateCommandQueue(&queue_desc, IID_PPV_ARGS(&queue)))) ||
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

    // Waits for all submitted work, whether or not the last dispatch completed its own wait.
    void wait_idle()
    {
        if (!queue || !fence) return;
        HANDLE event = CreateEventW(nullptr, FALSE, FALSE, nullptr);
        if (event && SUCCEEDED(queue->Signal(fence.Get(), ++value)) &&
            SUCCEEDED(fence->SetEventOnCompletion(value, event))) {
            WaitForSingleObject(event, INFINITE);
        }
        if (event) CloseHandle(event);
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

// The #912 checks on an initialized device and queue.
int translation_checks(Gpu& gpu)
{
    // Refusals: a reserve-only range, and an address inside an allocation.
    {
        const VirtualRange reserved(VirtualAlloc(nullptr, range_size, MEM_RESERVE, PAGE_READWRITE));
        if (!reserved.base) {
            std::puts("setup error: reserve-only VirtualAlloc failed");
            return 1;
        }
        ComPtr<ID3D12Heap> refused;
        const HRESULT hr = gpu.device->OpenExistingHeapFromAddress(reserved.base, IID_PPV_ARGS(&refused));
        std::printf("reserve-only range hr=0x%08lx\n", static_cast<unsigned long>(hr));
        expect(FAILED(hr), "a reserve-only range cannot be opened as a heap");
    }
    const VirtualRange range(VirtualAlloc(nullptr, range_size, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE));
    if (!range.base) {
        std::puts("setup error: committed VirtualAlloc failed");
        return 1;
    }
    std::uint8_t* const a = range.base;
    {
        ComPtr<ID3D12Heap> refused;
        const HRESULT hr = gpu.device->OpenExistingHeapFromAddress(a + range_size / 2, IID_PPV_ARGS(&refused));
        std::printf("interior address hr=0x%08lx\n", static_cast<unsigned long>(hr));
        expect(FAILED(hr), "an address inside the allocation cannot be opened as a heap");
    }

    // Everything below that uses A is declared after `range`. On every return, `idle` waits for
    // submitted work first, then these are released, and only then does `range` free A.
    ComPtr<ID3D12Heap> heap;
    ComPtr<ID3D12Resource> whole, part, other;
    struct Idle {
        Gpu& gpu;
        ~Idle() { gpu.wait_idle(); }
    } idle{gpu};

    // Device path: wrap all of A once and place one buffer over it. Its GPU address is B.
    HRESULT hr = gpu.device->OpenExistingHeapFromAddress(a, IID_PPV_ARGS(&heap));
    std::printf("committed range hr=0x%08lx\n", static_cast<unsigned long>(hr));
    if (hr == E_NOTIMPL || hr == DXGI_ERROR_UNSUPPORTED) {
        std::puts("OpenExistingHeapFromAddress unsupported on this adapter");
        return 77;
    }
    const auto whole_desc = buffer_desc(range_size, D3D12_RESOURCE_FLAG_ALLOW_CROSS_ADAPTER |
                                                        D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS);
    if (SUCCEEDED(hr)) {
        hr = gpu.device->CreatePlacedResource(heap.Get(), 0, &whole_desc, D3D12_RESOURCE_STATE_COMMON, nullptr,
                                              IID_PPV_ARGS(&whole));
    }
    expect(SUCCEEDED(hr), "wrap the committed range and place one buffer over it");
    if (FAILED(hr)) return 1;
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

    std::printf("device failures=%u\n", failures);
    return failures ? 1 : 0;
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
    return translation_checks(gpu);
}

HRESULT create_xbox_device(IUnknown* adapter, REFIID iid, void** device)
{
    return D3D12XboxCreateDevice(adapter, nullptr, iid, device);
}

// The title's 32-byte configuration block between guard bytes, so a write next to it is caught too.
struct ConfigBlock {
    static constexpr std::size_t guard = 16;
    std::array<unsigned char, guard + 32 + guard> bytes{};
    unsigned char* block() { return bytes.data() + guard; }
    void reset(std::uint32_t value)
    {
        bytes.fill(0xa5);
        std::memset(block(), 0, 32);
        std::memcpy(block() + 4, &value, sizeof(value));
    }
};

void expect_configure(ConfigBlock& config, HRESULT expected, const char* what)
{
    const auto before = config.bytes;
    const HRESULT hr = D3D12ConfigureVirtualMemoryX(config.block());
    std::printf("configure hr=0x%08lx: ", static_cast<unsigned long>(hr));
    expect(hr == expected && before == config.bytes, what);
}

// A refused queue request returns no queue.
void expect_queue_refused(ID3D12Device* device, const D3D12_COMMAND_QUEUE_DESC& desc, const char* what)
{
    ID3D12CommandQueue* queue = reinterpret_cast<ID3D12CommandQueue*>(std::uintptr_t{1});
    const HRESULT hr = device->CreateCommandQueue(&desc, __uuidof(ID3D12CommandQueue), reinterpret_cast<void**>(&queue));
    std::printf("queue hr=0x%08lx: ", static_cast<unsigned long>(hr));
    const bool refused = FAILED(hr) && (!queue || queue == reinterpret_cast<ID3D12CommandQueue*>(std::uintptr_t{1}));
    if (SUCCEEDED(hr) && queue) queue->Release();
    expect(refused, what);
}

int sequence_checks(bool warp)
{
    // 1. Configuration before any device, as the title calls it.
    ConfigBlock config;
    {
        const HRESULT hr = D3D12ConfigureVirtualMemoryX(nullptr);
        std::printf("configure hr=0x%08lx: ", static_cast<unsigned long>(hr));
        expect(hr == E_POINTER, "a null block is refused");
    }
    for (std::uint32_t value : {0u, 1u, 2u, 5u, 0x80000003u, 0xffffffffu}) {
        config.reset(value);
        std::printf("value 0x%08x ", value);
        expect_configure(config, E_INVALIDARG, "a value other than 3 or 4 is refused and the block is unchanged");
    }
    for (std::size_t offset : {0u, 3u, 8u, 31u}) {
        config.reset(4);
        config.block()[offset] = 1;
        std::printf("byte +%zu ", offset);
        expect_configure(config, E_INVALIDARG, "a non-zero byte outside +4 is refused and the block is unchanged");
    }
    config.reset(4);
    expect_configure(config, S_OK, "the observed block (4 at +4) is accepted and left unchanged");
    expect_configure(config, DXGI_ERROR_INVALID_CALL, "a second configuration is refused");
    config.reset(3);
    expect_configure(config, DXGI_ERROR_INVALID_CALL, "a second configuration with the other sample is refused");

    // 2. The device through d3d12_xs.dll.
    bool unmatched = false;
    const auto base = create_device(warp, unmatched, create_xbox_device);
    if (unmatched) return 1;
    Gpu gpu;
    if (!base || FAILED(base.As(&gpu.device))) {
        std::puts(warp ? "No ID3D12Device3 on WARP" : "No hardware adapter with ID3D12Device3");
        return 77;
    }
    {
        ComPtr<IDXGIFactory4> factory;
        ComPtr<IDXGIAdapter1> adapter;
        if (FAILED(CreateDXGIFactory1(IID_PPV_ARGS(&factory))) ||
            FAILED(factory->EnumAdapterByLuid(gpu.device->GetAdapterLuid(), IID_PPV_ARGS(&adapter)))) {
            std::puts("setup error: adapter of the created device not found");
            return 1;
        }
        const std::uint32_t parameters[16]{};
        void* device = reinterpret_cast<void*>(std::uintptr_t{1});
        HRESULT hr = D3D12XboxCreateDevice(adapter.Get(), parameters, __uuidof(ID3D12Device), &device);
        std::printf("device hr=0x%08lx: ", static_cast<unsigned long>(hr));
        expect(hr == E_INVALIDARG && !device, "a device request with a parameter block is refused");
        device = reinterpret_cast<void*>(std::uintptr_t{1});
        hr = D3D12XboxCreateDevice(adapter.Get(), nullptr, __uuidof(ID3D12Device3), &device);
        std::printf("device hr=0x%08lx: ", static_cast<unsigned long>(hr));
        expect(hr == E_NOINTERFACE && !device, "a device request for another interface is refused");
    }
    config.reset(4);
    expect_configure(config, DXGI_ERROR_INVALID_CALL, "configuration after device creation is refused");

    D3D12_FEATURE_DATA_GPU_VIRTUAL_ADDRESS_SUPPORT va{};
    if (SUCCEEDED(gpu.device->CheckFeatureSupport(D3D12_FEATURE_GPU_VIRTUAL_ADDRESS_SUPPORT, &va, sizeof(va)))) {
        std::printf("adapter VA bits: per resource %u, per process %u\n", va.MaxGPUVirtualAddressBitsPerResource,
                    va.MaxGPUVirtualAddressBitsPerProcess);
    }

    // 3. The first DIRECT queue with the default description, then refused requests.
    D3D12_COMMAND_QUEUE_DESC queue_desc{};
    queue_desc.Type = D3D12_COMMAND_LIST_TYPE_DIRECT;
    HRESULT hr = gpu.device->CreateCommandQueue(&queue_desc, IID_PPV_ARGS(&gpu.queue));
    std::printf("queue hr=0x%08lx: ", static_cast<unsigned long>(hr));
    expect(SUCCEEDED(hr), "the first DIRECT queue with the default description is created");
    if (FAILED(hr)) return 1;
    {
        D3D12_COMMAND_QUEUE_DESC bad = queue_desc;
        bad.Type = static_cast<D3D12_COMMAND_LIST_TYPE>(0x7fffffff);
        expect_queue_refused(gpu.device.Get(), bad, "a queue of an unknown type is refused");
        bad = queue_desc;
        bad.Priority = 12345;
        expect_queue_refused(gpu.device.Get(), bad, "a queue with an unknown priority is refused");
        bad = queue_desc;
        bad.NodeMask = 1u << 31;
        expect_queue_refused(gpu.device.Get(), bad, "a queue on a node the adapter lacks is refused");
    }
    hr = gpu.device->GetDeviceRemovedReason();
    std::printf("device removed reason hr=0x%08lx: ", static_cast<unsigned long>(hr));
    expect(hr == S_OK, "the refusals leave the device in place");

    // 4. The first queue and the configured device still run the range translation.
    if (!gpu.init()) {
        std::puts("compute setup failed");
        return 1;
    }
    return translation_checks(gpu);
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
    } else if (scenario == "sequence_warp"sv) {
        result = sequence_checks(true);
    } else if (scenario == "sequence_hardware"sv) {
        result = sequence_checks(false);
    }
    std::printf("vm_translation %s: %s\n", argv[1], result == 0 ? "PASS" : result == 77 ? "SKIP" : "FAIL");
    return result;
}
