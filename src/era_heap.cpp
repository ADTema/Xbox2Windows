#include "era_heap.h"

#include <algorithm>
#include <cstring>
#include <limits>
#include <malloc.h>

#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>

namespace era_heap {
namespace {
constexpr std::uint32_t heap = 0;
constexpr std::uint32_t graphics_first = 1;
constexpr std::uint32_t graphics_last = 6;

bool is_graphics(std::uint32_t memory_type) noexcept
{
    return memory_type >= graphics_first && memory_type <= graphics_last;
}

std::size_t allocation_granularity() noexcept
{
    SYSTEM_INFO info{};
    GetSystemInfo(&info);
    return info.dwAllocationGranularity;
}
}

Fields decode(std::uint64_t attributes) noexcept
{
    return {
        static_cast<std::uint32_t>(attributes & 0x3fff),
        static_cast<std::uint32_t>((attributes >> 14) & 0x3),
        static_cast<std::uint32_t>((attributes >> 16) & 0xff),
        static_cast<std::uint32_t>((attributes >> 24) & 0x1f),
        static_cast<std::uint32_t>((attributes >> 29) & 0xf),
        attributes >> 33,
    };
}

void* allocate(std::size_t bytes, std::uint64_t attributes) noexcept
{
    const auto fields = decode(attributes);
    // Object type and allocator ID are tags. SlimEra's default heap ignores them.
    if (bytes == 0 || fields.reserved != 0 || fields.page_size == 3) {
        return nullptr;
    }
    const auto alignment = std::size_t{1} << std::max(4u, fields.alignment);
    // Leave room for CRT alignment bookkeeping even for deliberately oversized input.
    const auto limit = static_cast<std::size_t>(std::numeric_limits<std::ptrdiff_t>::max());
    if (bytes > limit - alignment - sizeof(void*)) {
        return nullptr;
    }

    if (fields.memory_type == heap) {
        // As in SlimEra, the page size does not affect heap requests.
        void* allocation = _aligned_malloc(bytes, alignment);
        if (allocation) {
            std::memset(allocation, 0, bytes);
        }
        return allocation;
    }

    if (is_graphics(fields.memory_type)) {
        // SlimEra commits graphics memory as a separate virtual allocation. The desktop
        // places it on an allocation-granularity boundary (64 KiB on x64 Windows), which
        // covers 4 KB and 64 KB pages. Larger page sizes or alignments are not honored here.
        constexpr std::size_t page_bytes[]{std::size_t{4} << 10, std::size_t{64} << 10, std::size_t{4} << 20};
        if (std::max(page_bytes[fields.page_size], alignment) > allocation_granularity()) {
            return nullptr;
        }
        // Committed pages are zero-filled by the system.
        return VirtualAlloc(nullptr, bytes, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    }

    // Physical memory types need title physical pages, which this experiment does not model.
    return nullptr;
}

void release(void* allocation) noexcept
{
    _aligned_free(allocation);
}

void release_with_attributes(void* allocation, std::uint64_t attributes) noexcept
{
    if (!allocation) {
        return;
    }
    const auto memory_type = decode(attributes).memory_type;
    if (memory_type == heap) {
        _aligned_free(allocation);
    } else if (is_graphics(memory_type)) {
        VirtualFree(allocation, 0, MEM_RELEASE);
    }
}
}
