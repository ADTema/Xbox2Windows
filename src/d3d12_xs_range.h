#pragma once

#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <d3d12.h>

// The GPU range a successful D3D12ConfigureVirtualMemoryX reserves for the next device that
// d3d12_xs.dll creates (#874). The title keeps a CPU range A and a range B of the same size and maps
// B's 64 KiB pages to physical pages through a queue. On desktop D3D12 the range is a set of reserved
// buffers ("windows"); a caller maps their tiles with ID3D12CommandQueue::UpdateTileMappings.
//
// The range is attached to the device as private data under __uuidof(IX2WGpuRange), so any user of
// the device can read it in any module:
//     IX2WGpuRange* range = nullptr;
//     UINT size = sizeof(range);
//     device->GetPrivateData(__uuidof(IX2WGpuRange), &size, &range);  // adds a reference
// A device created without a configuration has none (DXGI_ERROR_NOT_FOUND).
//
// Ownership: the windows are device children and hold the device, and the device's private data holds
// the range. The device is therefore not destroyed by releasing it. Its owner calls Close() before its
// final Release; Close() releases the windows and removes the private data.
struct __declspec(uuid("c0b6a313-7c1e-4273-b375-cd666d84f420")) IX2WGpuRange : IUnknown {
    // Bytes covered by all windows together; 0 after Close().
    virtual UINT64 STDMETHODCALLTYPE GetSize() = 0;
    // Bytes of each window; every window but the last has this size.
    virtual UINT64 STDMETHODCALLTYPE GetWindowSize() = 0;
    virtual UINT STDMETHODCALLTYPE GetWindowCount() = 0;
    // The reserved buffer of window `index`, with a reference added. It starts at range offset
    // index * GetWindowSize(). Returns E_INVALIDARG for an index out of range or a null output.
    virtual HRESULT STDMETHODCALLTYPE GetWindow(UINT index, ID3D12Resource** window) = 0;
    // GPU virtual address of [offset, offset + bytes) when the span lies inside one window; 0 otherwise.
    // A byte count of 0 is treated as 1.
    virtual D3D12_GPU_VIRTUAL_ADDRESS STDMETHODCALLTYPE GetGPUVirtualAddress(UINT64 offset, UINT64 bytes) = 0;
    // Removes the range from its device's private data and releases the windows. Afterwards the range is
    // empty. Calling it again does nothing.
    virtual void STDMETHODCALLTYPE Close() = 0;
};

// Used by d3d12_xs.dll and its tests (src/d3d12_xs_range.cpp).
namespace d3d12_xs_range {
// Creates one window; the default calls ID3D12Device::CreateReservedResource.
using CreateWindowFn = HRESULT (*)(ID3D12Device* device, const D3D12_RESOURCE_DESC& desc, ID3D12Resource** window);

// Reserves `size` bytes in windows of at most 4 GiB, or less where the adapter's per-resource limit
// is lower. On failure returns the HRESULT with *range null, and every window created so far is
// released.
HRESULT create(ID3D12Device* device, UINT64 size, IX2WGpuRange** range, CreateWindowFn create_window = nullptr) noexcept;
// create() and attach the range to the device's private data. Nothing is attached on failure.
HRESULT attach(ID3D12Device* device, UINT64 size, CreateWindowFn create_window = nullptr) noexcept;
// Whether the device carries a range.
bool attached(ID3D12Device* device) noexcept;
}
