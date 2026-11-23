#pragma once

#include <cstdint>

// Desktop bookkeeping for title physical pages, as handed out by XMemAllocatePhysicalPages and
// returned by XMemFreePhysicalPages (call shapes from the public Microsoft Xbox GDK samples; see
// docs/experiments.md). A page is a 64 KiB unit named by an opaque nonzero page number. Nothing is
// committed here: mapping the pages to virtual memory is a separate interface, not modeled yet.
//
// Established by the public samples: 64 KiB pages with MEM_64K_PAGES, an in/out count and a page
// array, a BOOL result, and release of the same count and array.
// Proposed desktop policy, not established for the console (#880):
// - Only MEM_64K_PAGES is accepted. Any other flag bit, including the upper 32 bits, is refused.
// - A request succeeds completely or not at all; a successful call leaves the count unchanged.
// - On failure the count is set to 0 and the page array is left untouched.
// - A release must name every page of one or more live grants, each exactly once, in any order.
//   A short or long count, a page freed twice, a page number that was never issued, a duplicate
//   entry or part of a grant (partial release) is refused, and a refused release changes nothing.
namespace era_physical {
constexpr std::uint64_t mem_64k_pages = 0x20400000;  // MEM_LARGE_PAGES | MEM_PHYSICAL
constexpr std::uint64_t page_bytes = std::uint64_t{64} << 10;
constexpr std::uint64_t capacity_pages = std::uint64_t{1} << 18;  // 16 GiB of 64 KiB pages

enum class Status { ok, invalid, exhausted };

// On success writes count page numbers to pages. On failure sets *count to 0 (when count is not
// null) and leaves pages untouched (proposed desktop policy).
Status allocate(std::uint64_t flags, std::uint64_t* count, std::uint64_t* pages) noexcept;
Status release(std::uint64_t count, const std::uint64_t* pages) noexcept;
// Pages currently granted, for tests.
std::uint64_t granted_pages() noexcept;
}
