#pragma once

#include <cstddef>
#include <cstdint>

// Desktop experiment for the alignment-only subset of the public ERA heap model.
namespace era_heap {
void* allocate(std::size_t bytes, std::uint64_t attributes) noexcept;
void release(void* allocation) noexcept;
}
