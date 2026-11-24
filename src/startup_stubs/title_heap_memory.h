// Experimental (docs/startup-runtime.md): when a descriptor heap that the executable created
// without memory of its own gets plain memory of ours as its CPU side.
//
// A view heap always does, so that the view ids written there travel with the executable's own
// memory copies. Any other heap does when the desktop heap's CPU start is not pointer-aligned. A
// desktop handle is opaque, and a translation layer may keep tag bits in its low bits (measured:
// sampler heaps start at ...007 through vkd3d-proton). A console executable treats the start as an
// address; with such a start, the source handle it later passed to CopyDescriptorsSimple for the
// shader-visible sampler heap had 0xfd in its top byte, and the copy faulted in the layer.
#pragma once

#include <d3d12.h>

#include <cstdint>

namespace x2w_startup {
inline bool heap_needs_title_memory(D3D12_DESCRIPTOR_HEAP_TYPE type, std::uint64_t desktop_cpu_start)
{
    return type == D3D12_DESCRIPTOR_HEAP_TYPE_CBV_SRV_UAV || (desktop_cpu_start & (alignof(void*) - 1)) != 0;
}
}  // namespace x2w_startup
