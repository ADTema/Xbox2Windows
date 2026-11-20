#pragma once
#include <d3d12.h>
#include <wrl/client.h>

void check(HRESULT hr, const char* stage);
Microsoft::WRL::ComPtr<ID3D12Resource> resource(ID3D12Device* device, const D3D12_RESOURCE_DESC& desc,
    D3D12_HEAP_TYPE heap, D3D12_RESOURCE_STATES state, const D3D12_CLEAR_VALUE* clear = nullptr);
void check_compute(ID3D12Device* device, bool tables);
void check_buffer_ops(ID3D12Device* device);
void check_bvh_reads(ID3D12Device* device);
void check_bvh_hits(ID3D12Device* device);
bool check_bvh_differential(ID3D12Device* device);
bool check_bvh_waves(ID3D12Device* device, bool force64);
bool check_ray_query(ID3D12Device* device);

Microsoft::WRL::ComPtr<ID3D12Resource> make_buffer(ID3D12Device* device, UINT64 length, D3D12_HEAP_TYPE heap,
    D3D12_RESOURCE_STATES state, D3D12_RESOURCE_FLAGS flags = D3D12_RESOURCE_FLAG_NONE);
void transition(ID3D12GraphicsCommandList* list, ID3D12Resource* buffer,
                D3D12_RESOURCE_STATES before, D3D12_RESOURCE_STATES after);

struct ComputeCommands {
    ComputeCommands(ID3D12Device* device, ID3D12PipelineState* pipeline);
    void submit_and_wait(ID3D12Device* device);
    Microsoft::WRL::ComPtr<ID3D12CommandQueue> queue;
    Microsoft::WRL::ComPtr<ID3D12CommandAllocator> allocator;
    Microsoft::WRL::ComPtr<ID3D12GraphicsCommandList> list;
};
