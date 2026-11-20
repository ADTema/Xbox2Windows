#include "era_heap.h"

#include <algorithm>
#include <cstring>
#include <limits>
#include <malloc.h>

namespace era_heap {
void* allocate(std::size_t bytes, std::uint64_t attributes) noexcept
{
    // SlimEra's ERA reference places log2(alignment) in bits 24..28.
    // Only the default heap and untagged allocations are covered by this experiment.
    constexpr std::uint64_t alignment_mask = std::uint64_t{31} << 24;
    if (bytes == 0 || (attributes & ~alignment_mask) != 0) {
        return nullptr;
    }
    const auto exponent = static_cast<unsigned>(attributes >> 24);
    const auto alignment = std::size_t{1} << std::max(4u, exponent);
    // Leave room for CRT alignment bookkeeping even for deliberately oversized input.
    const auto limit = static_cast<std::size_t>(std::numeric_limits<std::ptrdiff_t>::max());
    if (bytes > limit - alignment - sizeof(void*)) {
        return nullptr;
    }
    void* allocation = _aligned_malloc(bytes, alignment);
    if (allocation) {
        std::memset(allocation, 0, bytes);
    }
    return allocation;
}

void release(void* allocation) noexcept
{
    _aligned_free(allocation);
}
}
