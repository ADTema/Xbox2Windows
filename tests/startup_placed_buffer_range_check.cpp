// measure_placed_buffer (src/startup_stubs/placed_buffer_range.h) without a device. Device slot 133
// aliases a buffer only if every byte from the allocation base to the end of the buffer is committed
// in that allocation. The walk now stops at the end of the buffer; every decision must equal the one
// the full walk (measure the whole committed run from the base, as slot 133 did before) gives on the
// same memory at the same moment. Each case places a buffer before changing the memory, so state kept
// from an earlier placement would be exposed by the next one.
//
// 1. Striped: a 64 MiB private block whose odd 64 KiB pages are read-only (1024 regions), 256
//    placements plus a misaligned one and one past the end. Prints the region queries per placement
//    of both walks.
// 2. Middle-page decommit: three committed pages, the middle one decommitted. A buffer on the third
//    page (gap before its start), one across all three and one on the first page.
// 3. Recommit: the middle page committed again; the first two buffers are accepted again.
// 4. Gap before the start, far from the buffer: page 1 of eight is decommitted, the buffer is on page 6.
// 5. Same-base replacement: the 64 MiB block is released and a 1 MiB block committed at its base. A
//    buffer inside it, one ending past its end and one past its end.
// 6. A mapped view is refused.
// 7. A reservation committed in two steps.
#include "startup_stubs/placed_buffer_range.h"

#include <cstdio>
#include <cstdint>

namespace {
constexpr SIZE_T page = 0x10000;
constexpr SIZE_T block_bytes = 64u << 20;
int failures;
unsigned long long full_queries, bounded_queries, placements;

void fail(const char* what, const void* address)
{
    std::fprintf(stderr, "placed buffer range: %s (address %p, error %lu)\n", what, address, GetLastError());
    ++failures;
}

// The decision slot 133 made before the change: measure the whole committed run from the base.
struct Full {
    bool committed = false;
    void* base = nullptr;
    DWORD type = 0;
    SIZE_T bytes = 0;
    unsigned queries = 0;
};
Full full_walk(const void* address)
{
    Full r;
    MEMORY_BASIC_INFORMATION info{};
    ++r.queries;
    if (!address || VirtualQuery(address, &info, sizeof(info)) != sizeof(info) || info.State != MEM_COMMIT) return r;
    r.committed = true;
    r.base = info.AllocationBase;
    r.type = info.Type;
    MEMORY_BASIC_INFORMATION region{};
    for (auto* cursor = static_cast<char*>(r.base);
         ++r.queries, VirtualQuery(cursor, &region, sizeof(region)) && region.AllocationBase == r.base &&
                      region.State == MEM_COMMIT;
         cursor += region.RegionSize)
        r.bytes += region.RegionSize;
    return r;
}

UINT64 offset_of(const void* address, const void* base)
{
    return static_cast<const char*>(address) - static_cast<const char*>(base);
}

// One placement: both walks on the same memory, the slot-133 decision from each, compared. expect is
// the decision the case requires (1 alias, 0 refuse), which also checks the reference itself.
bool place(void* address, UINT64 width, int expect, const char* what)
{
    const Full full = full_walk(address);
    x2w_startup::PlacedBufferRange range;
    const bool committed = x2w_startup::measure_placed_buffer(address, width, range);
    const UINT64 offset = full.committed ? offset_of(address, full.base) : 0;
    const bool full_alias = full.committed && !(offset & 0xFFFF) && offset <= full.bytes && width <= full.bytes - offset &&
                            full.type == MEM_PRIVATE;
    const bool alias = committed && !(offset_of(address, range.base) & 0xFFFF) && range.covered &&
                       range.type == MEM_PRIVATE;
    ++placements;
    full_queries += full.queries;
    bounded_queries += range.queries;
    if (committed != full.committed || alias != full_alias || (committed && (range.base != full.base || range.type != full.type))) {
        std::fprintf(stderr, "  %s: full walk committed=%d base=%p type=0x%lx bytes=0x%zx alias=%d; "
                     "bounded walk committed=%d base=%p type=0x%lx covered=%d alias=%d\n", what, full.committed,
                     full.base, full.type, full.bytes, full_alias, committed, range.base, range.type, range.covered, alias);
        fail(what, address);
    } else if (static_cast<int>(alias) != expect) {
        std::fprintf(stderr, "  %s: both walks give alias=%d, the case expects %d\n", what, alias, expect);
        fail(what, address);
    }
    return alias;
}

char* striped_block()
{
    auto* block = static_cast<char*>(VirtualAlloc(nullptr, block_bytes, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE));
    if (!block) return nullptr;
    DWORD old = 0;
    for (SIZE_T offset = page; offset < block_bytes; offset += 2 * page)
        if (!VirtualProtect(block + offset, page, PAGE_READONLY, &old)) return nullptr;
    return block;
}

char* committed_pages(SIZE_T count)
{
    return static_cast<char*>(VirtualAlloc(nullptr, count * page, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE));
}
} // namespace

int main()
{
    // Case 1: striped block.
    if (char* block = striped_block()) {
        const unsigned long long full_before = full_queries, bounded_before = bounded_queries;
        for (SIZE_T i = 0; i < 256; ++i)
            place(block + i * (block_bytes / 256), (i % 4 + 1) * page, 1, "striped placement");
        const double full_avg = (full_queries - full_before) / 256.0, bounded_avg = (bounded_queries - bounded_before) / 256.0;
        place(block + 0x1000, page, 0, "striped misaligned placement");
        place(block + block_bytes - page, 2 * page, 0, "striped placement past the end");
        place(block, page, 1, "striped placement at the base");
        std::printf("striped block (1024 regions), 256 placements spread over it: region queries per placement: "
                    "full walk %.1f, bounded walk %.1f\n", full_avg, bounded_avg);
        VirtualFree(block, 0, MEM_RELEASE);
    } else {
        fail("cannot allocate the striped block", nullptr);
    }

    // Cases 2 and 3: middle-page decommit, then recommit.
    if (char* pages = committed_pages(3)) {
        place(pages, 3 * page, 1, "three pages before the decommit");
        place(pages + 2 * page, page, 1, "third page before the decommit");
        if (!VirtualFree(pages + page, page, MEM_DECOMMIT)) {
            fail("cannot decommit the middle page", pages + page);
        } else {
            place(pages + 2 * page, page, 0, "decommit: buffer after the gap");
            place(pages, 3 * page, 0, "decommit: buffer across the gap");
            place(pages, page, 1, "decommit: buffer before the gap");
            place(pages + page, page, 0, "decommit: buffer on the gap");
            if (!VirtualAlloc(pages + page, page, MEM_COMMIT, PAGE_READWRITE)) {
                fail("cannot commit the middle page again", pages + page);
            } else {
                place(pages + 2 * page, page, 1, "recommit: buffer after the former gap");
                place(pages, 3 * page, 1, "recommit: buffer across the former gap");
            }
        }
        VirtualFree(pages, 0, MEM_RELEASE);
    } else {
        fail("cannot commit three pages", nullptr);
    }

    // Case 4: a gap before the start, five pages before the buffer.
    if (char* pages = committed_pages(8)) {
        place(pages + 6 * page, page, 1, "eight pages before the decommit");
        if (!VirtualFree(pages + page, page, MEM_DECOMMIT)) {
            fail("cannot decommit page 1", pages + page);
        } else {
            place(pages + 6 * page, page, 0, "gap before the start: buffer on page 6");
            place(pages + 6 * page, 2 * page, 0, "gap before the start: buffer on pages 6 and 7");
        }
        VirtualFree(pages, 0, MEM_RELEASE);
    } else {
        fail("cannot commit eight pages", nullptr);
    }

    // Case 5: same-base replacement.
    if (char* block = striped_block()) {
        place(block, page, 1, "replaced: before the release");
        place(block + (512u << 10), 1u << 20, 1, "replaced: buffer ending past 1 MiB before the release");
        VirtualFree(block, 0, MEM_RELEASE);
        char* smaller = static_cast<char*>(VirtualAlloc(block, 1u << 20, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE));
        if (smaller != block) {
            fail("cannot allocate the smaller block at the same base", block);
        } else {
            place(smaller + 2 * page, page, 1, "replaced: buffer inside the new block");
            place(smaller + (512u << 10), 1u << 20, 0, "replaced: buffer ending past the new end");
            place(smaller + (2u << 20), page, 0, "replaced: buffer past the new end");
        }
        if (smaller) VirtualFree(smaller, 0, MEM_RELEASE);
    } else {
        fail("cannot allocate the striped block", nullptr);
    }

    // Case 6: a mapped view.
    {
        HANDLE mapping = CreateFileMappingW(INVALID_HANDLE_VALUE, nullptr, PAGE_READWRITE, 0, 1u << 20, nullptr);
        void* view = mapping ? MapViewOfFile(mapping, FILE_MAP_ALL_ACCESS, 0, 0, 0) : nullptr;
        if (!view) {
            fail("cannot map a view", nullptr);
        } else {
            place(view, page, 0, "mapped view");
            place(view, page, 0, "mapped view again");
            UnmapViewOfFile(view);
        }
        if (mapping) CloseHandle(mapping);
    }

    // Case 7: a reservation committed in two steps.
    if (auto* reserved = static_cast<char*>(VirtualAlloc(nullptr, 4u << 20, MEM_RESERVE, PAGE_NOACCESS))) {
        if (!VirtualAlloc(reserved, 1u << 20, MEM_COMMIT, PAGE_READWRITE)) {
            fail("cannot commit the first megabyte", reserved);
        } else {
            place(reserved, page, 1, "partly committed: first megabyte");
            place(reserved + (1u << 20), page, 0, "partly committed: reserved page");
            place(reserved + (512u << 10), 1u << 20, 0, "partly committed: buffer ending in reserved pages");
            if (!VirtualAlloc(reserved + (1u << 20), 1u << 20, MEM_COMMIT, PAGE_READWRITE)) {
                fail("cannot commit the second megabyte", reserved);
            } else {
                place(reserved + (1u << 20), page, 1, "partly committed: after the second commit");
                place(reserved + (512u << 10), 1u << 20, 1, "partly committed: buffer across both commits");
            }
        }
        VirtualFree(reserved, 0, MEM_RELEASE);
    } else {
        fail("cannot reserve 4 MiB", nullptr);
    }

    std::printf("all %llu placements: region queries full walk %llu, bounded walk %llu\n", placements, full_queries,
                bounded_queries);
    if (failures) {
        std::fprintf(stderr, "placed buffer range: %d failure(s)\n", failures);
        return 1;
    }
    std::printf("placed buffer range: every decision matches the full walk\n");
    return 0;
}
