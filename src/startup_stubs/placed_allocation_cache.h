#pragma once

// Allocation extents for buffers placed at title addresses (device slot 133). Measuring an
// allocation walks every region from its base with VirtualQuery; an allocation with many regions
// (alternating protections, for example) costs one query per region on every placement. The cache
// remembers the measured committed extent of private allocations so a later placement inside one
// costs two queries instead of a walk.
//
// A remembered extent is trusted only after a check against the current address space: the region
// at the placement address and the region at the buffer's last byte must both be committed and
// belong to the remembered allocation base, and the address must still be private memory. A block
// that was released and replaced by a smaller one at the same base fails one of the two checks, as
// does a placeholder split inside the buffer. Only a placement that fits inside the remembered
// extent is served from the cache; anything else is measured again, which also picks up pages
// committed after the first measurement.

#include <windows.h>
#include <cstdint>
#include <iterator>
#include <map>

namespace x2w_startup {

struct AllocationExtent {
    void* base = nullptr;   // AllocationBase of the region at the address
    SIZE_T bytes = 0;       // committed bytes from base, in contiguous regions of that allocation
    DWORD type = 0;         // MEM_PRIVATE, MEM_MAPPED or MEM_IMAGE at the address
};

// The uncached measurement used by slot 133: false when the address is not committed.
inline bool measure_allocation(const void* address, AllocationExtent& out)
{
    MEMORY_BASIC_INFORMATION info{};
    if (!address || VirtualQuery(address, &info, sizeof(info)) != sizeof(info) || info.State != MEM_COMMIT) return false;
    out.base = info.AllocationBase;
    out.type = info.Type;
    out.bytes = 0;
    MEMORY_BASIC_INFORMATION region{};
    for (auto* cursor = static_cast<char*>(out.base);
         VirtualQuery(cursor, &region, sizeof(region)) && region.AllocationBase == out.base && region.State == MEM_COMMIT;
         cursor += region.RegionSize)
        out.bytes += region.RegionSize;
    return true;
}

// How a remembered extent is checked before use. Slot 133 uses full; the other two exist only for
// the negative controls in tests/startup_placed_allocation_cache_check.cpp.
enum class ExtentCheck { full, address_only, none };

class PlacedAllocationCache {
public:
    explicit PlacedAllocationCache(ExtentCheck check = ExtentCheck::full) noexcept : check_(check) {}
    PlacedAllocationCache(const PlacedAllocationCache&) = delete;
    PlacedAllocationCache& operator=(const PlacedAllocationCache&) = delete;

    // Same result as measure_allocation for the allocation containing address. width is the
    // buffer's byte width; only a buffer inside a remembered extent is served without a walk.
    bool measure(const void* address, std::uint64_t width, AllocationExtent& out)
    {
        if (!address) return false;
        const auto start = reinterpret_cast<std::uintptr_t>(address);
        const std::uint64_t span = width ? width : 1;
        if (span - 1 <= UINTPTR_MAX - start) {
            const std::uintptr_t last = start + static_cast<std::uintptr_t>(span - 1);
            AllocationExtent known;
            bool found = false;
            AcquireSRWLockShared(&lock_);
            auto it = entries_.upper_bound(start);
            if (it != entries_.begin()) {
                --it;
                const std::uintptr_t base = it->first;
                if (last - base < it->second.bytes) {  // start >= base, so [start, last] lies inside
                    known = it->second;
                    found = true;
                }
            }
            ReleaseSRWLockShared(&lock_);
            if (found && still_valid(known, address, reinterpret_cast<const void*>(last))) {
                InterlockedIncrement64(&hits_);
                out = known;
                return true;
            }
            if (found) forget(known.base);
        }
        InterlockedIncrement64(&walks_);
        if (!measure_allocation(address, out)) return false;
        // Remember only a private allocation whose committed run reaches the address: the extent
        // slot 133 can place into. Other results are returned and measured again next time.
        const auto base = reinterpret_cast<std::uintptr_t>(out.base);
        if (out.type == MEM_PRIVATE && start - base < out.bytes) remember(out);
        return true;
    }

    LONG64 walks() const noexcept { return walks_; }
    LONG64 hits() const noexcept { return hits_; }
    std::size_t entries() const noexcept
    {
        AcquireSRWLockShared(&lock_);
        const std::size_t count = entries_.size();
        ReleaseSRWLockShared(&lock_);
        return count;
    }

private:
    bool still_valid(const AllocationExtent& known, const void* first, const void* last) const
    {
        if (check_ == ExtentCheck::none) return true;
        MEMORY_BASIC_INFORMATION info{};
        if (VirtualQuery(first, &info, sizeof(info)) != sizeof(info) || info.State != MEM_COMMIT ||
            info.AllocationBase != known.base || info.Type != known.type)
            return false;
        // One region covers the whole buffer: the second query would return the same answer.
        if (check_ == ExtentCheck::address_only ||
            static_cast<const char*>(last) < static_cast<const char*>(info.BaseAddress) + info.RegionSize)
            return true;
        return VirtualQuery(last, &info, sizeof(info)) == sizeof(info) && info.State == MEM_COMMIT &&
               info.AllocationBase == known.base;
    }

    void remember(const AllocationExtent& extent)
    {
        const auto base = reinterpret_cast<std::uintptr_t>(extent.base);
        AcquireSRWLockExclusive(&lock_);
        try {
            // Drop remembered extents that overlap the new one; they describe older allocations.
            auto it = entries_.upper_bound(base);
            if (it != entries_.begin() && std::prev(it)->first + std::prev(it)->second.bytes > base) --it;
            while (it != entries_.end() && it->first < base + extent.bytes) it = entries_.erase(it);
            entries_.emplace(base, extent);
        } catch (...) {
            // Out of memory: the next placement measures again.
        }
        ReleaseSRWLockExclusive(&lock_);
    }

    void forget(void* base)
    {
        AcquireSRWLockExclusive(&lock_);
        entries_.erase(reinterpret_cast<std::uintptr_t>(base));
        ReleaseSRWLockExclusive(&lock_);
    }

    mutable SRWLOCK lock_ = SRWLOCK_INIT;
    std::map<std::uintptr_t, AllocationExtent> entries_;
    volatile LONG64 walks_ = 0;
    volatile LONG64 hits_ = 0;
    const ExtentCheck check_;
};

} // namespace x2w_startup
