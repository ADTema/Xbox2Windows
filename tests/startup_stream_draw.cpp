#include <d3d12.h>
#include <dxgi1_4.h>
#include <wrl/client.h>

#include <array>
#include <cstdint>
#include <cstdio>
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

struct StreamTarget {
    ComPtr<ID3D12Resource> texture, readback;
    D3D12_PLACED_SUBRESOURCE_FOOTPRINT footprint{};
    UINT row_bytes = 0;
};

int check_stream_draw(IDXGIAdapter* adapter, void* guest, void* pso, const char* pixels,
                      DXGI_FORMAT format, UINT export_word)
{
    const bool legacy = format == DXGI_FORMAT_UNKNOWN;
    const bool integer = format == DXGI_FORMAT_R32_UINT || format == DXGI_FORMAT_R32_SINT;
    const UINT width = legacy ? 8 : 1, height = legacy ? 4 : 1, count = integer ? 2 : 1;
    ComPtr<ID3D12Device> desktop;
    if (FAILED(D3D12CreateDevice(adapter, D3D_FEATURE_LEVEL_12_0, IID_PPV_ARGS(&desktop)))) return 20;
    D3D12_HEAP_PROPERTIES heap{D3D12_HEAP_TYPE_DEFAULT};
    // The wrapped heap gives the stand-in a descriptor shadow for the typed RTV.
    const struct {
        D3D12_DESCRIPTOR_HEAP_DESC desc;
        Word backing, bytes;
    } rtv_desc{{D3D12_DESCRIPTOR_HEAP_TYPE_RTV, count}, 0, 0};
    void* rtv_heap = nullptr;
    if (FAILED(static_cast<HRESULT>(invoke(guest, 14, arg(&rtv_desc), arg(&__uuidof(ID3D12DescriptorHeap)),
                                           arg(&rtv_heap))))) return 22;
    const SIZE_T first_rtv = invoke(rtv_heap, 9);
    const auto stride = desktop->GetDescriptorHandleIncrementSize(D3D12_DESCRIPTOR_HEAP_TYPE_RTV);
    std::array<StreamTarget, 2> targets;
    std::array<D3D12_CPU_DESCRIPTOR_HANDLE, 2> rtvs{};
    const float clear[] = {0, 0, 1, 1};
    for (UINT i = 0; i < count; ++i) {
        auto& target = targets[i];
        const auto view_format = i || legacy ? DXGI_FORMAT_R8G8B8A8_UNORM : format;
        const auto resource_format = !i && integer ? DXGI_FORMAT_R32_TYPELESS : view_format;
        D3D12_RESOURCE_DESC desc{D3D12_RESOURCE_DIMENSION_TEXTURE2D, 0, width, height, 1, 1,
            resource_format, {1, 0}, D3D12_TEXTURE_LAYOUT_UNKNOWN, D3D12_RESOURCE_FLAG_ALLOW_RENDER_TARGET};
        const D3D12_CLEAR_VALUE optimized_clear{view_format, {0, 0, 1, 1}};
        if (FAILED(desktop->CreateCommittedResource(&heap, D3D12_HEAP_FLAG_NONE, &desc,
                D3D12_RESOURCE_STATE_COMMON, &optimized_clear, IID_PPV_ARGS(&target.texture)))) return 21;
        D3D12_RENDER_TARGET_VIEW_DESC view{view_format, D3D12_RTV_DIMENSION_TEXTURE2D, {}};
        rtvs[i] = {first_rtv + SIZE_T{i} * stride};
        invoke(guest, 20, arg(target.texture.Get()), arg(&view), rtvs[i].ptr);
        target.row_bytes = width * (view_format == DXGI_FORMAT_R32G32B32A32_FLOAT ? 16 : 4);
    }

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

    const D3D12_VIEWPORT viewport{0, 0, static_cast<float>(width), static_cast<float>(height), 0, 1};
    const D3D12_RECT left{0, 0, static_cast<LONG>(legacy ? width / 2 : width), static_cast<LONG>(height)};
    invoke(list, 139, arg(allocator));
    for (UINT i = 0; i < count; ++i) invoke(list, 52, rtvs[i].ptr, arg(clear));
    invoke(list, 50, count, arg(rtvs.data()));
    invoke(list, 21, 1, arg(&viewport));
    invoke(list, 22, 1, arg(&left));
    invoke(list, 20, D3D_PRIMITIVE_TOPOLOGY_TRIANGLELIST);
    invoke(list, 25, arg(pso));
    if (export_word) invoke(list, 40, 0, 1, arg(&export_word), 0);
    invoke(list, 12, 3, 1);
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

    heap.Type = D3D12_HEAP_TYPE_READBACK;
    for (UINT i = 0; i < count; ++i) {
        auto& target = targets[i];
        UINT64 total = 0;
        const auto desc = target.texture->GetDesc();
        desktop->GetCopyableFootprints(&desc, 0, 1, 0, &target.footprint, nullptr, nullptr, &total);
        const D3D12_RESOURCE_DESC buffer{D3D12_RESOURCE_DIMENSION_BUFFER, 0, total, 1, 1, 1,
                                   DXGI_FORMAT_UNKNOWN, {1, 0}, D3D12_TEXTURE_LAYOUT_ROW_MAJOR};
        if (FAILED(desktop->CreateCommittedResource(&heap, D3D12_HEAP_FLAG_NONE, &buffer,
                    D3D12_RESOURCE_STATE_COPY_DEST, nullptr, IID_PPV_ARGS(&target.readback)))) return 27;
        D3D12_TEXTURE_COPY_LOCATION destination{target.readback.Get(), D3D12_TEXTURE_COPY_TYPE_PLACED_FOOTPRINT};
        destination.PlacedFootprint = target.footprint;
        D3D12_TEXTURE_COPY_LOCATION source{target.texture.Get(), D3D12_TEXTURE_COPY_TYPE_SUBRESOURCE_INDEX};
        copy->CopyTextureRegion(&destination, 0, 0, 0, &source, nullptr);
    }
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
    std::ofstream out(pixels, std::ios::binary);
    for (UINT i = 0; i < count; ++i) {
        auto& target = targets[i];
        void* memory = nullptr;
        if (FAILED(target.readback->Map(0, nullptr, &memory))) return 32;
        for (UINT y = 0; y < height; ++y)
            out.write(static_cast<const char*>(memory) + y * target.footprint.Footprint.RowPitch, target.row_bytes);
        target.readback->Unmap(0, nullptr);
    }
    return out ? 0 : 33;
}
