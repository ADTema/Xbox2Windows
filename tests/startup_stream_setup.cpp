#include <d3d12.h>
#include <dxgi1_6.h>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <wrl/client.h>

#include <array>
#include <fstream>
#include <iterator>
#include <string>
#include <vector>

#include "startup_stream_setup.h"

using Microsoft::WRL::ComPtr;
extern "C" __declspec(dllimport) HRESULT WINAPI D3D12XboxCreateDevice(IUnknown*, const void*, REFIID, void**);

struct alignas(8) Stage {
    D3D12_PIPELINE_STATE_SUBOBJECT_TYPE tag;
    D3D12_SHADER_BYTECODE shader;
};
struct alignas(8) Root {
    D3D12_PIPELINE_STATE_SUBOBJECT_TYPE tag;
    ID3D12RootSignature* signature;
};
struct Stream {
    Stage ps;
    Root root;
    Stage vs;
};

int prepare_stream_pipeline(const char* vs_path, const char* ps_path, const char* root_path,
                            bool hardware, bool textured, Microsoft::WRL::ComPtr<IDXGIAdapter>& adapter,
                            void*& device, void*& pso)
{
    std::ifstream vs_file(vs_path, std::ios::binary), ps_file(ps_path, std::ios::binary);
    std::vector<char> vs{std::istreambuf_iterator<char>(vs_file), {}};
    std::vector<char> ps{std::istreambuf_iterator<char>(ps_file), {}};
    if (vs.empty() || ps.empty()) return 3;

    ComPtr<IDXGIFactory4> factory;
    if (FAILED(CreateDXGIFactory1(IID_PPV_ARGS(&factory)))) return 4;
    if (hardware) {
        ComPtr<IDXGIFactory6> factory6;
        if (FAILED(factory.As(&factory6))) return 77;
        for (UINT n = 0;; ++n) {
            ComPtr<IDXGIAdapter1> candidate;
            HRESULT hr = factory6->EnumAdapterByGpuPreference(n, DXGI_GPU_PREFERENCE_HIGH_PERFORMANCE, IID_PPV_ARGS(&candidate));
            if (hr == DXGI_ERROR_NOT_FOUND) return 77;
            if (FAILED(hr)) return 4;
            DXGI_ADAPTER_DESC1 desc{};
            if (FAILED(candidate->GetDesc1(&desc))) return 4;
            if (!(desc.Flags & DXGI_ADAPTER_FLAG_SOFTWARE) &&
                SUCCEEDED(D3D12CreateDevice(candidate.Get(), D3D_FEATURE_LEVEL_12_0, __uuidof(ID3D12Device), nullptr))) {
                adapter = candidate;
                break;
            }
        }
    } else if (FAILED(factory->EnumWarpAdapter(IID_PPV_ARGS(&adapter)))) return 4;
    DXGI_ADAPTER_DESC desc{};
    LARGE_INTEGER driver{};
    if (FAILED(adapter->GetDesc(&desc))) return 4;
    adapter->CheckInterfaceSupport(__uuidof(IDXGIDevice), &driver);
    std::printf("adapter=%ls driver=%u.%u.%u.%u\n", desc.Description,
        HIWORD(driver.HighPart), LOWORD(driver.HighPart), HIWORD(driver.LowPart), LOWORD(driver.LowPart));
    std::array<unsigned char, 64> parameters{};
    if (FAILED(D3D12XboxCreateDevice(adapter.Get(), parameters.data(), __uuidof(ID3D12Device), &device))) return 5;

    D3D12_ROOT_SIGNATURE_DESC root_desc{};
    const D3D12_DESCRIPTOR_RANGE srv{D3D12_DESCRIPTOR_RANGE_TYPE_SRV, 1, 0, 0, 0};
    D3D12_ROOT_PARAMETER table{};
    if (textured) {
        table.ParameterType = D3D12_ROOT_PARAMETER_TYPE_DESCRIPTOR_TABLE;
        table.DescriptorTable = {1, &srv};
        table.ShaderVisibility = D3D12_SHADER_VISIBILITY_PIXEL;
        root_desc.NumParameters = 1;
        root_desc.pParameters = &table;
    }
    ComPtr<ID3DBlob> blob;
    if (FAILED(D3D12SerializeRootSignature(&root_desc, D3D_ROOT_SIGNATURE_VERSION_1, &blob, nullptr))) return 6;
    std::ofstream(root_path, std::ios::binary).write(static_cast<const char*>(blob->GetBufferPointer()), blob->GetBufferSize());
    using CreateRoot = HRESULT (WINAPI*)(void*, UINT, const void*, SIZE_T, REFIID, void**);
    using CreateStream = HRESULT (WINAPI*)(void*, const D3D12_PIPELINE_STATE_STREAM_DESC*, REFIID, void**);
    auto** slots = *static_cast<void***>(device);
    ID3D12RootSignature* root = nullptr;
    if (FAILED(reinterpret_cast<CreateRoot>(slots[16])(device, 0, blob->GetBufferPointer(), blob->GetBufferSize(),
                                                        __uuidof(ID3D12RootSignature), reinterpret_cast<void**>(&root)))) return 7;

    Stream stream{{D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_PS, {ps.data(), ps.size()}},
                  {D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_ROOT_SIGNATURE, root},
                  {D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_VS, {vs.data(), vs.size()}}};
    auto submit = [&](SIZE_T bytes) {
        D3D12_PIPELINE_STATE_STREAM_DESC desc{bytes, &stream};
        const auto hr = reinterpret_cast<CreateStream>(slots[86])(device, &desc, __uuidof(ID3D12PipelineState), &pso);
        return SUCCEEDED(hr) && pso;
    };
    // A truncated last shader must not publish a partial request, even with readable backing memory.
    if (!submit(sizeof(stream) - 8)) return 8;
    if (GetEnvironmentVariableW(L"X2W_TEST_TRUNCATED_ONLY", nullptr, 0)) return 0;
    if (!submit(sizeof(stream))) return 9;
    return 0;
}

int read_stream_target(ID3D12Device* desktop, ID3D12Resource* target, const char* pixels)
{
    const auto target_desc = target->GetDesc();
    const auto width = target_desc.Width;
    const auto height = target_desc.Height;
    const bool rgba = target_desc.Format == DXGI_FORMAT_R8G8B8A8_UNORM;
    D3D12_COMMAND_QUEUE_DESC queue_desc{};
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
    D3D12_HEAP_PROPERTIES heap{D3D12_HEAP_TYPE_READBACK};
    ComPtr<ID3D12Resource> readback;
    if (FAILED(desktop->CreateCommittedResource(&heap, D3D12_HEAP_FLAG_NONE, &buffer,
                D3D12_RESOURCE_STATE_COPY_DEST, nullptr, IID_PPV_ARGS(&readback)))) return 27;
    D3D12_TEXTURE_COPY_LOCATION destination{readback.Get(), D3D12_TEXTURE_COPY_TYPE_PLACED_FOOTPRINT};
    destination.PlacedFootprint = footprint;
    D3D12_TEXTURE_COPY_LOCATION source{target, D3D12_TEXTURE_COPY_TYPE_SUBRESOURCE_INDEX};
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
        out.write(static_cast<const char*>(memory) + y * footprint.Footprint.RowPitch, width * (rgba ? 4 : 1));
    readback->Unmap(0, nullptr);
    return out ? 0 : 33;
}

using Word = std::uint64_t;
template<class T> Word arg(T* value) { return reinterpret_cast<Word>(value); }
Word invoke(void* object, unsigned index, Word a, Word b, Word c, Word d,
            Word e, Word f, Word g, Word h)
{
    using Slot = Word (WINAPI*)(void*, Word, Word, Word, Word, Word, Word, Word, Word);
    return reinterpret_cast<Slot>((*static_cast<void***>(object))[index])(object, a, b, c, d, e, f, g, h);
}

int open_stream_target(ID3D12Device* desktop, void* guest, void* pso, UINT width, UINT height,
                       DXGI_FORMAT format, UINT scissor_width, StreamTarget& state)
{
    D3D12_HEAP_PROPERTIES heap{D3D12_HEAP_TYPE_DEFAULT};
    D3D12_RESOURCE_DESC target_desc{D3D12_RESOURCE_DIMENSION_TEXTURE2D, 0, width, height, 1, 1,
        format, {1, 0}, D3D12_TEXTURE_LAYOUT_UNKNOWN, D3D12_RESOURCE_FLAG_ALLOW_RENDER_TARGET};
    const bool rgba = format == DXGI_FORMAT_R8G8B8A8_UNORM;
    const D3D12_CLEAR_VALUE clear{format, {0, 0, 1, rgba ? 1.0f : 0.0f}};
    auto& target = state.target;
    if (FAILED(desktop->CreateCommittedResource(&heap, D3D12_HEAP_FLAG_NONE, &target_desc,
                                                D3D12_RESOURCE_STATE_COMMON, &clear, IID_PPV_ARGS(&target)))) return 21;
    D3D12_DESCRIPTOR_HEAP_DESC rtv_desc{D3D12_DESCRIPTOR_HEAP_TYPE_RTV, 1};
    auto& rtv_heap = state.rtv_heap;
    if (FAILED(desktop->CreateDescriptorHeap(&rtv_desc, IID_PPV_ARGS(&rtv_heap)))) return 22;
    const auto rtv = rtv_heap->GetCPUDescriptorHandleForHeapStart();
    invoke(guest, 20, arg(target.Get()), 0, rtv.ptr);

    auto& list = state.list;
    auto& queue = state.queue;
    auto& allocator = state.allocator;
    auto& fence = state.fence;
    D3D12_COMMAND_QUEUE_DESC queue_desc{};
    const unsigned list_desc[] = {D3D12_COMMAND_LIST_TYPE_DIRECT, 2, 1, 0};
    if (FAILED(static_cast<HRESULT>(invoke(guest, 8, arg(&queue_desc), arg(&__uuidof(ID3D12CommandQueue)), arg(&queue)))) ||
        FAILED(static_cast<HRESULT>(invoke(guest, 9, D3D12_COMMAND_LIST_TYPE_DIRECT, arg(&__uuidof(ID3D12CommandAllocator)), arg(&allocator)))) ||
        FAILED(static_cast<HRESULT>(invoke(guest, 73, arg(list_desc), arg(allocator), 0, arg(&__uuidof(ID3D12GraphicsCommandList)), arg(&list)))) ||
        FAILED(static_cast<HRESULT>(invoke(guest, 36, 0, 0, arg(&__uuidof(ID3D12Fence)), arg(&fence))))) return 23;

    const D3D12_VIEWPORT viewport{0, 0, static_cast<float>(width), static_cast<float>(height), 0, 1};
    const D3D12_RECT rect{0, 0, static_cast<LONG>(scissor_width), static_cast<LONG>(height)};
    invoke(list, 139, arg(allocator));
    invoke(list, 52, rtv.ptr, arg(clear.Color));
    invoke(list, 50, 1, arg(&rtv));
    invoke(list, 21, 1, arg(&viewport));
    invoke(list, 22, 1, arg(&rect));
    invoke(list, 20, D3D_PRIMITIVE_TOPOLOGY_TRIANGLELIST);
    invoke(list, 25, arg(pso));
    return 0;
}
