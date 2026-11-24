#pragma once

// The memory question device slot 133 asks before it aliases a buffer at a title address: which
// allocation holds the address, of which memory type, and is every byte from the allocation base to
// the end of the buffer committed in that allocation. Slot 133 used to answer it by measuring the
// whole committed run from the base (one VirtualQuery per region until the run ends) and comparing
// the buffer with that length. The answer depends only on [base, end of buffer), so the walk stops
// there: regions after the buffer cannot change it. Nothing is remembered between calls, because a
// decommit, release or replacement made directly through the Windows API would not be seen.

#include <windows.h>
#include <cstdint>

namespace x2w_startup {

struct PlacedBufferRange {
    void* base = nullptr;   // AllocationBase of the region at the address
    DWORD type = 0;         // MEM_PRIVATE, MEM_MAPPED or MEM_IMAGE at the address
    bool covered = false;   // [base, address + width) is committed and belongs to that allocation
    unsigned queries = 0;   // VirtualQuery calls made, for the stand-in's totals
};

// False when the address is not committed (slot 133 returns E_INVALIDARG). Otherwise covered is
// exactly "offset <= committed bytes from base && width <= committed bytes - offset" for the run
// the full walk measures: the walk proves the same contiguous committed prefix, but only as far as
// the buffer needs.
inline bool measure_placed_buffer(const void* address, std::uint64_t width, PlacedBufferRange& out)
{
    out = PlacedBufferRange{};
    MEMORY_BASIC_INFORMATION info{};
    ++out.queries;
    if (!address || VirtualQuery(address, &info, sizeof(info)) != sizeof(info) || info.State != MEM_COMMIT) return false;
    out.base = info.AllocationBase;
    out.type = info.Type;
    const auto start = reinterpret_cast<std::uintptr_t>(address);
    if (width > UINTPTR_MAX - start) return true;  // the end does not exist; the full walk refuses it too
    const std::uintptr_t end = start + static_cast<std::uintptr_t>(width);
    auto cursor = reinterpret_cast<std::uintptr_t>(out.base);
    MEMORY_BASIC_INFORMATION region{};
    while (cursor < end) {
        ++out.queries;
        if (!VirtualQuery(reinterpret_cast<const void*>(cursor), &region, sizeof(region)) ||
            region.AllocationBase != out.base || region.State != MEM_COMMIT)
            return true;
        cursor = reinterpret_cast<std::uintptr_t>(region.BaseAddress) + region.RegionSize;
    }
    out.covered = true;
    return true;
}

} // namespace x2w_startup
