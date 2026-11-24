#pragma once
#include <cstdint>
#include <d3d12.h>
#include <dxgi.h>
#include <wrl/client.h>

int prepare_stream_pipeline(const char* vs_path, const char* ps_path, const char* root_path,
                            bool hardware, bool textured, Microsoft::WRL::ComPtr<IDXGIAdapter>& adapter,
                            void*& device, void*& pso);

int read_stream_target(ID3D12Device* desktop, ID3D12Resource* target, const char* pixels);

struct StreamTarget {
    Microsoft::WRL::ComPtr<ID3D12Resource> target;
    Microsoft::WRL::ComPtr<ID3D12DescriptorHeap> rtv_heap;
    void* list{};
    void* queue{};
    void* allocator{};
    void* fence{};
};
int open_stream_target(ID3D12Device* desktop, void* guest, void* pso, UINT width, UINT height,
                       DXGI_FORMAT format, UINT scissor_width, StreamTarget& state);
using StreamWord = std::uint64_t;
StreamWord invoke(void*, unsigned, StreamWord = 0, StreamWord = 0, StreamWord = 0, StreamWord = 0,
                  StreamWord = 0, StreamWord = 0, StreamWord = 0, StreamWord = 0);
