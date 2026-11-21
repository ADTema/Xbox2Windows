#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <psapi.h>
#include <cstdio>
#include <memory>
#include <array>
#include <algorithm>
#include <cstddef>

struct ReleaseRegion {
    void operator()(BYTE* p) const { VirtualFree(p, 0, MEM_RELEASE); }
};

struct QueryBuffer {
    MEMORY_BASIC_INFORMATION info;
    std::array<BYTE, 16> tail;
};
static_assert(offsetof(QueryBuffer, tail) == 0x30 && sizeof(QueryBuffer) == 64);
static_assert(offsetof(MEMORY_BASIC_INFORMATION, State) == 0x20);
static_assert(offsetof(MEMORY_BASIC_INFORMATION, Protect) == 0x24);

// Model only the post-query predicates observed in the four BVH callers.
bool caller_accepts(const QueryBuffer& buffer, SIZE_T returned, bool source)
{
    return returned && (buffer.tail[0] & 3) && (buffer.info.State & 0x1000) &&
           (!source || (buffer.info.Protect & 6));
}

bool region_is(BYTE* page_start, BYTE* base, DWORD state, SIZE_T size, DWORD protection,
               SIZE_T offset_in_page = 0)
{
    QueryBuffer buffer{};
    buffer.tail.fill(0xa5);
    auto& info = buffer.info;
    return VirtualQueryEx(GetCurrentProcess(), page_start + offset_in_page, &info, sizeof(buffer)) == sizeof(info) &&
           std::all_of(buffer.tail.begin(), buffer.tail.end(), [](BYTE b) { return b == 0xa5; }) &&
           info.AllocationBase == base && info.BaseAddress == page_start &&
           info.State == state && info.RegionSize == size &&
           (state != MEM_COMMIT || info.Protect == protection);
}

bool check_query_tail(BYTE* address, bool committed, bool sourceReadable)
{
    QueryBuffer buffer{};
    const SIZE_T written = VirtualQueryEx(GetCurrentProcess(), address, &buffer.info, sizeof(buffer));
    if (written != sizeof(buffer.info) || buffer.tail[0] != 0) return false;
    struct Probe { BYTE bits; bool passesMask; };
    constexpr Probe probes[]{{0,false}, {1,true}, {2,true}, {3,true}, {4,false}, {0x80,false}, {0x81,true}};
    for (const auto& probe : probes) {
        buffer.tail[0] = probe.bits; // Synthetic input after the Windows call.
        if (caller_accepts(buffer, written, false) != (committed && probe.passesMask) ||
            caller_accepts(buffer, written, true) != (committed && sourceReadable && probe.passesMask) ||
            caller_accepts(buffer, 0, false) || caller_accepts(buffer, 0, true)) return false;
    }
    std::printf("query_bytes=%zu state=%lx protect=%lx tail_masks=%zu predicates=passed\n",
                written, buffer.info.State, buffer.info.Protect, std::size(probes));
    return true;
}

bool check_short_query(BYTE* address)
{
    QueryBuffer buffer{};
    buffer.tail.fill(0xd7);
    // Exercise the actual desktop failure path and feed its return to both caller predicates.
    SetLastError(ERROR_SUCCESS);
    const SIZE_T written = VirtualQueryEx(GetCurrentProcess(), address, &buffer.info, 1);
    const DWORD error = GetLastError();
    std::printf("short_query_bytes=%zu last_error=%lu\n", written, error);
    return written == 0 && error != ERROR_SUCCESS &&
           std::all_of(buffer.tail.begin(), buffer.tail.end(), [](BYTE b) { return b == 0xd7; }) &&
           !caller_accepts(buffer, written, false) && !caller_accepts(buffer, written, true);
}

bool check_partial_decommit(SIZE_T page)
{
    std::unique_ptr<BYTE, ReleaseRegion> storage(static_cast<BYTE*>(
        VirtualAlloc(nullptr, 4 * page, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE)));
    BYTE* base = storage.get();
    if (!base) return false;
    constexpr BYTE marker = 0xa5;
    std::fill_n(base, 4 * page, marker);

    // The two-byte request spans the middle two pages of the reservation.
    BYTE* boundary = base + 2 * page;
    if (!VirtualFree(boundary - 1, 2, MEM_DECOMMIT) ||
        !region_is(base, base, MEM_COMMIT, page, PAGE_READWRITE) ||
        !region_is(base + page, base, MEM_RESERVE, 2 * page, 0, page - 1) ||
        !region_is(boundary, base, MEM_RESERVE, page, 0) ||
        !region_is(base + 3 * page, base, MEM_COMMIT, page, PAGE_READWRITE)) {
        std::fputs("Two-byte decommit: expected two reserved pages between committed neighbors\n", stderr);
        return false;
    }
    if (VirtualAlloc(boundary - 1, 2, MEM_COMMIT, PAGE_READWRITE) != base + page ||
        !region_is(base, base, MEM_COMMIT, 4 * page, PAGE_READWRITE)) {
        std::fputs("Two-byte recommit: expected one four-page read/write region\n", stderr);
        return false;
    }
    const auto marked = [marker](BYTE byte) { return byte == marker; };
    if (!std::all_of(base, base + page, marked) ||
        !std::all_of(base + page, base + 3 * page, [](BYTE byte) { return byte == 0; }) ||
        !std::all_of(base + 3 * page, base + 4 * page, marked)) {
        std::fputs("Recommitted pages must be zero and neighboring pages must retain their data\n", stderr);
        return false;
    }
    std::printf("decommitted_bytes=%zu recommitted_zero_bytes=%zu preserved_bytes=%zu\n",
                2 * page, 2 * page, 2 * page);
    return true;
}

bool snapshot(const char* stage)
{
    PROCESS_MEMORY_COUNTERS_EX counters{};
    counters.cb = sizeof(counters);
    if (!GetProcessMemoryInfo(GetCurrentProcess(),
                              reinterpret_cast<PROCESS_MEMORY_COUNTERS*>(&counters), sizeof(counters))) {
        return false;
    }
    std::printf("%s: working_set=%zu peak_working_set=%zu private_commit=%zu bytes\n",
                stage, counters.WorkingSetSize, counters.PeakWorkingSetSize, counters.PrivateUsage);
    return counters.WorkingSetSize > 0 && counters.PeakWorkingSetSize >= counters.WorkingSetSize;
}

int main()
{
    SYSTEM_INFO info{};
    GetSystemInfo(&info);
    const SIZE_T page = info.dwPageSize;
    if (!check_partial_decommit(page)) return 1;
    const SIZE_T bytes = 1024 * page;
    std::unique_ptr<BYTE, ReleaseRegion> storage(static_cast<BYTE*>(
        VirtualAlloc(nullptr, bytes + page, MEM_RESERVE, PAGE_NOACCESS)));
    BYTE* base = storage.get();
    if (!base || !region_is(base, base, MEM_RESERVE, bytes + page, 0) ||
        !check_query_tail(base, false, false) || !check_short_query(base) || !snapshot("reserved")) {
        std::fputs("Reserve/query failed\n", stderr);
        return 1;
    }
    if (!VirtualAlloc(base, bytes, MEM_COMMIT, PAGE_READWRITE) ||
        !region_is(base, base, MEM_COMMIT, bytes, PAGE_READWRITE) ||
        !region_is(base + bytes, base, MEM_RESERVE, page, 0) || !check_query_tail(base, true, true)) {
        std::fputs("Committed range or reserved tail differs\n", stderr);
        return 1;
    }
    for (SIZE_T offset = 0; offset < bytes; offset += page) {
        base[offset] = 1;
    }
    PSAPI_WORKING_SET_EX_INFORMATION resident{};
    resident.VirtualAddress = base;
    if (!VirtualLock(base, page)) {
        std::fprintf(stderr, "VirtualLock failed (%lu)\n", GetLastError());
        return 1;
    }
    const BOOL queried = QueryWorkingSetEx(GetCurrentProcess(), &resident, sizeof(resident));
    const BOOL unlocked = VirtualUnlock(base, page);
    if (!queried || !resident.VirtualAttributes.Valid || !unlocked || !snapshot("touched")) {
        std::fputs("Working-set residency query failed\n", stderr);
        return 1;
    }
    DWORD previous = 0;
    if (!VirtualProtect(base, page, PAGE_READONLY, &previous) || previous != PAGE_READWRITE ||
        !region_is(base, base, MEM_COMMIT, page, PAGE_READONLY) ||
        !check_query_tail(base, true, true) ||
        !region_is(base + page, base, MEM_COMMIT, bytes - page, PAGE_READWRITE) ||
        !VirtualProtect(base, page, PAGE_NOACCESS, &previous) || !check_query_tail(base, true, false) ||
        !VirtualFree(base, bytes, MEM_DECOMMIT) ||
        !region_is(base, base, MEM_RESERVE, bytes + page, 0) || !snapshot("decommitted")) {
        std::fputs("Protection/decommit query failed\n", stderr);
        return 1;
    }
    std::printf("page_bytes=%zu touched_bytes=%zu pinned_page_resident=1\n", page, bytes);
    return 0;
}
