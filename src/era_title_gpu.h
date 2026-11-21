#pragma once

#include "era_gpu_alias.h"
#include "era_title_va.h"

#include <cstddef>
#include <cstdint>
#include <vector>

// Graphics allocations as the title's GPU sees them.
// On the console a graphics allocation is GPU-visible at its CPU address as soon as it exists.
// This process-wide registry tracks graphics allocations (the desktop xmem.dll routes its graphics
// memory types through it). Once a D3D12 device is attached, each allocation is opened as an
// era_gpu_alias heap and its title range is mapped in an era_title_va::Table:
// - allocations that exist at attach time are aliased then;
// - later ones are aliased when they are tracked.
// A D3D12 layer can then translate title GPU addresses, find the buffer and offset behind one, or
// take a snapshot for the shader lookup (src/title_va_lookup.hlsli).
//
// All functions are thread-safe. The registry does not wait for GPU work: releasing memory the GPU
// still uses is a title error on the console as well.
namespace era_title_gpu {
// Records a graphics allocation and registers it with era_query as GPU-intended. With a device
// attached it is also aliased; if aliasing fails the allocation stays tracked without a desktop
// GPU address. Returns false for null, empty, wrapping or overlapping input, or allocation failure.
bool track(void* base, std::size_t bytes) noexcept;
// Drops the allocation's alias, translation and era_query registration. Returns false when base
// is not a tracked allocation.
bool untrack(void* base) noexcept;

// Uses `device` for every tracked allocation and for later ones. Returns:
// - S_OK when every tracked allocation is aliased;
// - E_INVALIDARG for a null device;
// - E_NOTIMPL, without changing anything, when the device does not support existing heaps;
// - otherwise the first aliasing failure, after trying every allocation.
// Attaching the same device again retries allocations that are not aliased. Attaching a different
// device drops every alias first.
HRESULT attach(ID3D12Device* device) noexcept;
// Drops every alias and the device. Tracked allocations stay tracked.
void detach() noexcept;

// Desktop GPU virtual address of [title_address, title_address + bytes), or 0 when the span is not
// inside one aliased allocation. A byte count of 0 is treated as 1.
std::uint64_t translate(std::uint64_t title_address, std::uint64_t bytes = 1) noexcept;
// The aliasing buffer and byte offset for [title_address, title_address + bytes). The buffer is
// returned with a reference added. Returns false when the span is not inside one aliased allocation.
bool locate(std::uint64_t title_address, std::uint64_t bytes, ID3D12Resource** buffer,
            std::uint64_t* offset) noexcept;

struct ShaderView {
    std::vector<era_title_va::ShaderRange> ranges;  // slot i aliases resources[i]
    std::vector<Microsoft::WRL::ComPtr<ID3D12Resource>> resources;
};
// The aliased allocations packed for TitleLookup, with their buffers in slot order. Returns false
// when an allocation cannot be packed (4 GiB or longer) or on allocation failure.
bool shader_view(ShaderView& view) noexcept;

struct Counts {
    std::size_t tracked;
    std::size_t aliased;
};
Counts counts() noexcept;
}
