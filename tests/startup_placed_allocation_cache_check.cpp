// PlacedAllocationCache (src/startup_stubs/placed_allocation_cache.h) without a device. Device slot 133
// measures the allocation that holds a placed buffer; the cache must give the same answer as the
// uncached region walk while walking an allocation once.
//
// 1. A 64 MiB private block with alternating protections on its 64 KiB pages (1024 regions) takes
//    256 placements: every extent and every slot-133 decision equals the uncached path, one walk.
// 2. The block is released and a 1 MiB block is committed at the same base. A placement past the new
//    end, and one that starts inside it but ends past it, must be refused as the uncached path
//    refuses them, not served from the remembered 64 MiB extent.
// 3. A mapped view is refused every time and never remembered.
// 4. Pages committed after the first measurement are seen by the next placement that needs them.
//
// The two controls run with WILL_FAIL and must fail only for their stated reason. --mutate none skips
// the check of remembered extents: it exits 1 only if case 2 serves the placement past the new end
// from the stale extent. --mutate address-only checks only the region at the placement address: it
// exits 1 only if case 2 serves the placement that ends past the new end from the stale extent while
// the placement past the new end is still refused. Either exits 0 (so the control fails) when that
// does not happen or when any other case fails. A setup step the system refuses (an allocation, a
// mapping) is a capability skip, 77, in the controls and a failure in the main check.
#include "startup_stubs/placed_allocation_cache.h"

#include <cstdio>
#include <cstring>

namespace {
using x2w_startup::AllocationExtent;
using x2w_startup::ExtentCheck;
using x2w_startup::PlacedAllocationCache;

constexpr SIZE_T page = 0x10000;
constexpr SIZE_T block_bytes = 64u << 20;
int failures;
int setup_failures;
int replaced_failures;   // failures inside case 2
bool stale_ending;       // case 2 accepted the buffer ending past the new end, unlike the uncached path
bool stale_past;         // case 2 accepted the buffer past the new end, unlike the uncached path

void fail(const char* what, const void* address)
{
    std::fprintf(stderr, "placed allocation cache: %s (address %p)\n", what, address);
    ++failures;
}

void setup_fail(const char* what, const void* address)
{
    std::fprintf(stderr, "placed allocation cache: setup: %s (address %p, error %lu)\n", what, address, GetLastError());
    ++setup_failures;
}

// The rules slot 133 applies to a measured extent before it places a buffer.
bool accepted(bool committed, const AllocationExtent& extent, const void* address, UINT64 width)
{
    if (!committed) return false;
    const UINT64 offset = static_cast<const char*>(address) - static_cast<const char*>(extent.base);
    return !(offset & 0xFFFF) && offset <= extent.bytes && width <= extent.bytes - offset && extent.type == MEM_PRIVATE;
}

// One placement through the cache, compared with the uncached measurement made just before it.
// same_bytes=false: a remembered extent may still carry the byte count of a replaced block when the
// buffer lies inside the new one; the decision, base and type must match regardless.
bool place(PlacedAllocationCache& cache, void* address, UINT64 width, const char* what, bool same_bytes = true)
{
    AllocationExtent expected, got;
    const bool expected_committed = x2w_startup::measure_allocation(address, expected);
    const bool got_committed = cache.measure(address, width, got);
    const bool expected_accept = accepted(expected_committed, expected, address, width);
    const bool got_accept = accepted(got_committed, got, address, width);
    if (got_committed != expected_committed || got_accept != expected_accept ||
        (expected_committed && (got.base != expected.base || (same_bytes && got.bytes != expected.bytes) ||
                                got.type != expected.type))) {
        std::fprintf(stderr, "  %s: expected committed=%d base=%p bytes=0x%zx type=0x%lx accept=%d, "
                     "got committed=%d base=%p bytes=0x%zx type=0x%lx accept=%d\n", what, expected_committed,
                     expected.base, expected.bytes, expected.type, expected_accept, got_committed, got.base, got.bytes,
                     got.type, got_accept);
        fail(what, address);
    }
    return got_accept;
}

// A committed 64 MiB block whose odd 64 KiB pages are read-only: 1024 regions to walk.
char* striped_block(void* at = nullptr)
{
    auto* block = static_cast<char*>(VirtualAlloc(at, block_bytes, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE));
    if (!block) return nullptr;
    DWORD old = 0;
    for (SIZE_T offset = page; offset < block_bytes; offset += 2 * page)
        if (!VirtualProtect(block + offset, page, PAGE_READONLY, &old)) return nullptr;
    return block;
}

// Case 2 for one check mode: remember the 64 MiB extent, then put a 1 MiB block at the same base.
void replaced_block(ExtentCheck check)
{
    PlacedAllocationCache cache(check);
    char* block = striped_block();
    if (!block) return setup_fail("cannot allocate the striped block", nullptr);
    const int before = failures;
    place(cache, block, page, "replaced: first placement");
    VirtualFree(block, 0, MEM_RELEASE);
    char* smaller = static_cast<char*>(VirtualAlloc(block, 1u << 20, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE));
    if (smaller != block) return setup_fail("cannot allocate the smaller block at the same base", block);
    // A buffer wholly inside the new block is accepted as the uncached path accepts it.
    if (!place(cache, smaller + 2 * page, page, "replaced: placement inside the new block first", false))
        fail("placement inside the new block refused", smaller + 2 * page);
    // First a buffer that starts inside the new block: the region at its address still belongs to the
    // same base, so only the region at its last byte shows the change. Then one past the new end.
    if (place(cache, smaller + (512u << 10), 1u << 20, "replaced: placement ending past the new end")) {
        stale_ending = true;
        fail("placement ending past the new end accepted", smaller + (512u << 10));
    }
    if (place(cache, smaller + (2u << 20), page, "replaced: placement past the new end")) {
        stale_past = true;
        fail("placement past the new end accepted", smaller + (2u << 20));
    }
    if (!place(cache, smaller + page, page, "replaced: placement inside the new block"))
        fail("placement inside the new block refused", smaller + page);
    VirtualFree(smaller, 0, MEM_RELEASE);
    replaced_failures = failures - before;
}
} // namespace

int main(int argc, char** argv)
{
    ExtentCheck check = ExtentCheck::full;
    if (argc == 3 && std::strcmp(argv[1], "--mutate") == 0 && std::strcmp(argv[2], "none") == 0)
        check = ExtentCheck::none;
    else if (argc == 3 && std::strcmp(argv[1], "--mutate") == 0 && std::strcmp(argv[2], "address-only") == 0)
        check = ExtentCheck::address_only;
    else if (argc != 1) {
        std::fprintf(stderr, "usage: startup_placed_allocation_cache_check [--mutate none|address-only]\n");
        return 64;
    }

    // Case 1: 256 placements into one striped block, widths of one to four pages.
    do {
        PlacedAllocationCache cache(check);
        char* block = striped_block();
        if (!block) {
            setup_fail("cannot allocate the striped block", nullptr);
            break;
        }
        int accepted_count = 0;
        for (SIZE_T i = 0; i < 256; ++i) {
            char* address = block + i * (block_bytes / 256);
            accepted_count += place(cache, address, (i % 4 + 1) * page, "striped placement");
        }
        // Two placements the slot refuses: misaligned, and a buffer past the end of the block.
        place(cache, block + 0x1000, page, "striped misaligned placement");
        place(cache, block + block_bytes - page, 2 * page, "striped placement past the end");
        std::printf("striped block: %d of 256 accepted, walks %lld, walks saved %lld, entries %zu\n", accepted_count,
                    static_cast<long long>(cache.walks()), static_cast<long long>(cache.hits()), cache.entries());
        if (accepted_count != 256) fail("striped placements refused", block);
        // The placement past the end does not fit the remembered extent and is measured again.
        if (cache.walks() != 2 || cache.hits() != 256 || cache.entries() != 1) fail("walk count", block);
        VirtualFree(block, 0, MEM_RELEASE);
    } while (false);

    // Case 2: a stale extent at a reused base.
    replaced_block(check);

    // Case 3: a mapped view is refused and not remembered.
    {
        PlacedAllocationCache cache(check);
        HANDLE mapping = CreateFileMappingW(INVALID_HANDLE_VALUE, nullptr, PAGE_READWRITE, 0, 1u << 20, nullptr);
        void* view = mapping ? MapViewOfFile(mapping, FILE_MAP_ALL_ACCESS, 0, 0, 0) : nullptr;
        if (!view) {
            setup_fail("cannot map a view", nullptr);
        } else {
            for (int i = 0; i < 2; ++i)
                if (place(cache, view, page, "mapped placement")) fail("mapped placement accepted", view);
            if (cache.walks() != 2 || cache.hits() != 0 || cache.entries() != 0) fail("mapped view remembered", view);
            UnmapViewOfFile(view);
        }
        if (mapping) CloseHandle(mapping);
    }

    // Case 4: a reservation committed in two steps.
    {
        PlacedAllocationCache cache(check);
        auto* reserved = static_cast<char*>(VirtualAlloc(nullptr, 4u << 20, MEM_RESERVE, PAGE_NOACCESS));
        if (!reserved || !VirtualAlloc(reserved, 1u << 20, MEM_COMMIT, PAGE_READWRITE)) {
            setup_fail("cannot commit the reservation", reserved);
        } else {
            place(cache, reserved, page, "partly committed: first placement");
            if (place(cache, reserved + (1u << 20), page, "partly committed: past the committed run"))
                fail("placement into reserved pages accepted", reserved + (1u << 20));
            if (!VirtualAlloc(reserved + (1u << 20), 1u << 20, MEM_COMMIT, PAGE_READWRITE)) {
                setup_fail("cannot commit the second megabyte", reserved);
            } else {
                if (!place(cache, reserved + (1u << 20), page, "partly committed: after the second commit"))
                    fail("placement into newly committed pages refused", reserved + (1u << 20));
                if (!place(cache, reserved + page, page, "partly committed: inside the larger extent"))
                    fail("placement inside the larger extent refused", reserved + page);
            }
        }
        if (reserved) VirtualFree(reserved, 0, MEM_RELEASE);
    }

    if (check != ExtentCheck::full) {
        if (setup_failures) return 77;
        const bool stated = failures == replaced_failures &&
                            (check == ExtentCheck::none ? stale_past : stale_ending && !stale_past);
        std::fprintf(stderr, "placed allocation cache control: %d failure(s), %d in case 2, stale ending %d, "
                     "stale past %d -> %s\n", failures, replaced_failures, stale_ending, stale_past,
                     stated ? "failed for the stated reason" : "did NOT fail for the stated reason");
        return stated ? 1 : 0;
    }
    if (failures || setup_failures) {
        std::fprintf(stderr, "placed allocation cache: %d failure(s), %d setup failure(s)\n", failures, setup_failures);
        return 1;
    }
    std::printf("placed allocation cache: all cases match the uncached path\n");
    return 0;
}
