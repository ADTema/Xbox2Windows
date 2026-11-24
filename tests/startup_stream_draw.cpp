#include <d3d12.h>
#include <dxgi1_4.h>
#include <wrl/client.h>

#include <cstdint>
#include <array>
#include <fstream>

using Microsoft::WRL::ComPtr;

// The components under test receive the guest ABI's vtable slots. The observation
// queue and its readback buffer are desktop objects owned only by the fixture.
using Word = std::uint64_t;
template<class T> Word arg(T* value) { return reinterpret_cast<Word>(value); }
Word invoke(void* object, unsigned index, Word a = 0, Word b = 0, Word c = 0, Word d = 0,
            Word e = 0, Word f = 0, Word g = 0, Word h = 0)
{
    using Slot = Word (WINAPI*)(void*, Word, Word, Word, Word, Word, Word, Word, Word);
    return reinterpret_cast<Slot>((*static_cast<void***>(object))[index])(object, a, b, c, d, e, f, g, h);
}

int draw_logical_tables(ID3D12Device* desktop, void* guest, void* list)
{
    constexpr UINT count = 1245184;
    auto accepts = [&](UINT n) {
        const D3D12_DESCRIPTOR_HEAP_DESC desc{D3D12_DESCRIPTOR_HEAP_TYPE_CBV_SRV_UAV, n,
                                             D3D12_DESCRIPTOR_HEAP_FLAG_SHADER_VISIBLE};
        ComPtr<ID3D12DescriptorHeap> probe;
        return SUCCEEDED(desktop->CreateDescriptorHeap(&desc, IID_PPV_ARGS(&probe)));
    };
    if (accepts(count)) return 77;
    UINT boundary = 0, upper = 1048577;
    while (upper - boundary > 1) {
        const UINT n = boundary + (upper - boundary) / 2;
        if (accepts(n)) boundary = n; else upper = n;
    }
    if (!boundary) return 34;
    std::printf("logical views: physical capacity %u, logical count %u\n", boundary, count);
    const UINT stride = static_cast<UINT>(invoke(guest, 15, D3D12_DESCRIPTOR_HEAP_TYPE_CBV_SRV_UAV));
    if (stride < 32) return 34;
    struct Extended {
        D3D12_DESCRIPTOR_HEAP_DESC desc;
        Word cpu, bytes;
    } info{{D3D12_DESCRIPTOR_HEAP_TYPE_CBV_SRV_UAV, count, D3D12_DESCRIPTOR_HEAP_FLAG_SHADER_VISIBLE}, 0, 0};
    void* heaps[2]{};
    Word handles[2]{};
    Extended staging_info{{D3D12_DESCRIPTOR_HEAP_TYPE_CBV_SRV_UAV, 2}, 0, 0};
    void* staging = nullptr;
    if (FAILED(static_cast<HRESULT>(invoke(guest, 14, arg(&staging_info), arg(&__uuidof(ID3D12DescriptorHeap)), arg(&staging))))) return 34;
    const Word staging_cpu = invoke(staging, 9);
    D3D12_SHADER_RESOURCE_VIEW_DESC null_srv{};
    null_srv.Format = DXGI_FORMAT_R32_TYPELESS;
    null_srv.ViewDimension = D3D12_SRV_DIMENSION_BUFFER;
    null_srv.Shader4ComponentMapping = D3D12_DEFAULT_SHADER_4_COMPONENT_MAPPING;
    null_srv.Buffer.NumElements = 1;
    null_srv.Buffer.Flags = D3D12_BUFFER_SRV_FLAG_RAW;
    alignas(256) static std::array<std::array<UINT, 64>, 6> words{};
    for (UINT h = 0; h < 2; ++h) {
        if (FAILED(static_cast<HRESULT>(invoke(guest, 14, arg(&info), arg(&__uuidof(ID3D12DescriptorHeap)), arg(&heaps[h]))))) return 34;
        const Word cpu = invoke(heaps[h], 9);
        handles[h] = invoke(heaps[h], 10);
        if (!cpu || !handles[h]) return 34;
        const UINT slots[] = {boundary - 1, boundary, count - 1};
        for (UINT i = 0; i < 3; ++i) {
            auto& data = words[3 * h + i];
            data[0] = 16 + 96 * h + 16 * i;
            const D3D12_CONSTANT_BUFFER_VIEW_DESC cb{arg(data.data()), static_cast<UINT>(sizeof(data))};
            // Initialize a real native descriptor as well as the fixture's guest view token.
            const Word destination = i < 2 ? staging_cpu + Word{i} * stride : cpu + Word{slots[i]} * stride;
            invoke(guest, 18, 0, arg(&null_srv), destination);
            invoke(guest, 17, arg(&cb), destination);
        }
        const Word destination = cpu + Word{boundary - 1} * stride;
        const UINT two = 2;
        if (h == 0) {
            invoke(guest, 24, two, destination, staging_cpu, D3D12_DESCRIPTOR_HEAP_TYPE_CBV_SRV_UAV);
        } else {
            invoke(guest, 23, 1, arg(&destination), arg(&two), 1, arg(&staging_cpu), arg(&two), D3D12_DESCRIPTOR_HEAP_TYPE_CBV_SRV_UAV);
        }
        // Reject the complete copy: even its first entry must leave the final sentinel intact.
        invoke(guest, 24, two, cpu + Word{count - 1} * stride, staging_cpu, D3D12_DESCRIPTOR_HEAP_TYPE_CBV_SRV_UAV);
    }
    const auto bind = [&](UINT h) { invoke(list, 32, 1, arg(&heaps[h])); };
    const auto table = [&](UINT h, UINT i) { invoke(list, 36, 0, handles[h] + Word{i} * stride); };
    const auto draw = [&](LONG x) {
        const D3D12_RECT strip{x, 0, x + 1, 4};
        invoke(list, 22, 1, arg(&strip));
        invoke(list, 12, 3, 1);
    };
    bind(0);
    table(0, boundary - 1); draw(0);
    table(0, boundary); draw(1);
    table(0, count - 1); draw(2);
    table(0, count); draw(3);
    bind(1);
    table(1, boundary); draw(4);
    bind(0); draw(5);                   // Changing heaps invalidates its previous table.
    table(1, boundary); draw(6);        // A handle belonging to the other heap.
    table(0, boundary); draw(7);
    return 0;
}

int check_stream_draw(IDXGIAdapter* adapter, void* guest, void* pso, const char* pixels)
{
    constexpr UINT width = 8, height = 4;
    ComPtr<ID3D12Device> desktop;
    if (FAILED(D3D12CreateDevice(adapter, D3D_FEATURE_LEVEL_12_0, IID_PPV_ARGS(&desktop)))) return 20;
    D3D12_HEAP_PROPERTIES heap{D3D12_HEAP_TYPE_DEFAULT};
    D3D12_RESOURCE_DESC target_desc{D3D12_RESOURCE_DIMENSION_TEXTURE2D, 0, width, height, 1, 1,
        DXGI_FORMAT_R8G8B8A8_UNORM, {1, 0}, D3D12_TEXTURE_LAYOUT_UNKNOWN, D3D12_RESOURCE_FLAG_ALLOW_RENDER_TARGET};
    ComPtr<ID3D12Resource> target;
    if (FAILED(desktop->CreateCommittedResource(&heap, D3D12_HEAP_FLAG_NONE, &target_desc,
                                                D3D12_RESOURCE_STATE_COMMON, nullptr, IID_PPV_ARGS(&target)))) return 21;
    D3D12_DESCRIPTOR_HEAP_DESC rtv_desc{D3D12_DESCRIPTOR_HEAP_TYPE_RTV, 1};
    ComPtr<ID3D12DescriptorHeap> rtv_heap;
    if (FAILED(desktop->CreateDescriptorHeap(&rtv_desc, IID_PPV_ARGS(&rtv_heap)))) return 22;
    const auto rtv = rtv_heap->GetCPUDescriptorHandleForHeapStart();
    invoke(guest, 20, arg(target.Get()), 0, rtv.ptr);

    void* list = nullptr;
    void* queue = nullptr;
    void* allocator = nullptr;
    void* fence = nullptr;
    D3D12_COMMAND_QUEUE_DESC queue_desc{};
    const unsigned list_desc[] = {D3D12_COMMAND_LIST_TYPE_DIRECT, 2, 1, 0};
    if (FAILED(static_cast<HRESULT>(invoke(guest, 8, arg(&queue_desc), arg(&__uuidof(ID3D12CommandQueue)), arg(&queue)))) ||
        FAILED(static_cast<HRESULT>(invoke(guest, 9, D3D12_COMMAND_LIST_TYPE_DIRECT, arg(&__uuidof(ID3D12CommandAllocator)), arg(&allocator)))) ||
        FAILED(static_cast<HRESULT>(invoke(guest, 73, arg(list_desc), arg(allocator), 0, arg(&__uuidof(ID3D12GraphicsCommandList)), arg(&list)))) ||
        FAILED(static_cast<HRESULT>(invoke(guest, 36, 0, 0, arg(&__uuidof(ID3D12Fence)), arg(&fence))))) return 23;

    const float clear[] = {0, 0, 1, 1};
    const D3D12_VIEWPORT viewport{0, 0, width, height, 0, 1};
    const D3D12_RECT left{0, 0, width / 2, height};
    invoke(list, 139, arg(allocator));
    invoke(list, 52, rtv.ptr, arg(clear));
    invoke(list, 50, 1, arg(&rtv));
    invoke(list, 21, 1, arg(&viewport));
    invoke(list, 22, 1, arg(&left));
    invoke(list, 20, D3D_PRIMITIVE_TOPOLOGY_TRIANGLELIST);
    invoke(list, 25, arg(pso));
    if (GetEnvironmentVariableW(L"X2W_TEST_LOGICAL_VIEW", nullptr, 0)) {
        if (int result = draw_logical_tables(desktop.Get(), guest, list)) return result;
    } else {
        invoke(list, 12, 3, 1);
    }
    invoke(list, 9);
    invoke(queue, 10, 1, arg(&list));
    if (FAILED(static_cast<HRESULT>(invoke(queue, 14, arg(fence), 1)))) return 24;
    const auto deadline = GetTickCount64() + 10000;
    while (invoke(fence, 8) == 0 && GetTickCount64() < deadline) Sleep(1);
    if (invoke(fence, 8) != 1) return 25;

    ComPtr<ID3D12CommandQueue> observer;
    ComPtr<ID3D12CommandAllocator> copy_allocator;
    ComPtr<ID3D12GraphicsCommandList> copy;
    ComPtr<ID3D12Fence> complete;
    if (FAILED(desktop->CreateCommandQueue(&queue_desc, IID_PPV_ARGS(&observer))) ||
        FAILED(desktop->CreateCommandAllocator(D3D12_COMMAND_LIST_TYPE_DIRECT, IID_PPV_ARGS(&copy_allocator))) ||
        FAILED(desktop->CreateCommandList(0, D3D12_COMMAND_LIST_TYPE_DIRECT, copy_allocator.Get(), nullptr, IID_PPV_ARGS(&copy))) ||
        FAILED(desktop->CreateFence(0, D3D12_FENCE_FLAG_NONE, IID_PPV_ARGS(&complete)))) return 26;

    D3D12_PLACED_SUBRESOURCE_FOOTPRINT footprint{};
    UINT64 total = 0;
    desktop->GetCopyableFootprints(&target_desc, 0, 1, 0, &footprint, nullptr, nullptr, &total);
    D3D12_RESOURCE_DESC buffer{D3D12_RESOURCE_DIMENSION_BUFFER, 0, total, 1, 1, 1,
                               DXGI_FORMAT_UNKNOWN, {1, 0}, D3D12_TEXTURE_LAYOUT_ROW_MAJOR};
    heap.Type = D3D12_HEAP_TYPE_READBACK;
    ComPtr<ID3D12Resource> readback;
    if (FAILED(desktop->CreateCommittedResource(&heap, D3D12_HEAP_FLAG_NONE, &buffer,
                D3D12_RESOURCE_STATE_COPY_DEST, nullptr, IID_PPV_ARGS(&readback)))) return 27;
    D3D12_TEXTURE_COPY_LOCATION destination{readback.Get(), D3D12_TEXTURE_COPY_TYPE_PLACED_FOOTPRINT};
    destination.PlacedFootprint = footprint;
    D3D12_TEXTURE_COPY_LOCATION source{target.Get(), D3D12_TEXTURE_COPY_TYPE_SUBRESOURCE_INDEX};
    copy->CopyTextureRegion(&destination, 0, 0, 0, &source, nullptr);
    if (FAILED(copy->Close())) return 28;
    ID3D12CommandList* submit[] = {copy.Get()};
    observer->ExecuteCommandLists(1, submit);
    if (FAILED(observer->Signal(complete.Get(), 1))) return 29;
    HANDLE event = CreateEventW(nullptr, FALSE, FALSE, nullptr);
    if (!event) return 30;
    const bool completed = SUCCEEDED(complete->SetEventOnCompletion(1, event)) &&
                           WaitForSingleObject(event, 10000) == WAIT_OBJECT_0 && complete->GetCompletedValue() == 1;
    CloseHandle(event);
    if (!completed) return 31;
    void* memory = nullptr;
    if (FAILED(readback->Map(0, nullptr, &memory))) return 32;
    std::ofstream out(pixels, std::ios::binary);
    for (UINT y = 0; y < height; ++y)
        out.write(static_cast<const char*>(memory) + y * footprint.Footprint.RowPitch, width * 4);
    readback->Unmap(0, nullptr);
    return out ? 0 : 33;
}
