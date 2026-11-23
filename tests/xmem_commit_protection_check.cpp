// Source-built x64 check for the second commit/protection case on #870:
// compares ordinary committed pages (MEM_PRIVATE) against a live shared-page view
// (MEM_MAPPED via desktop xmem.dll physical-page mappings) for CPU read/write
// accessibility, write-protection transitions (PAGE_READWRITE <-> PAGE_READONLY
// <-> PAGE_NOACCESS), aliasing visibility, and state preservation after failed
// allocation or failed reprotection.
//
// Scope:
// - Separate from the first-commit alignment/zero-fill/rounding fixture
//   (xmem_committed_memory), #888 (reserve-only), and #874 (device/queue).
// - Uses synthetic 64 KiB page patterns only.
// - Proposed desktop policy (not established for console):
//   * Ordinary committed pages use Win32 VirtualAlloc (MEM_PRIVATE).
//   * Live shared-page views use xmem.dll XMemAllocatePhysicalPages +
//     XMemMapPhysicalPages / XMemMapPhysicalPagesScatter over caller-owned
//     Windows placeholders (MEM_MAPPED), with per-view VirtualProtect.
//   * Unsupported XMemVirtualAlloc second-commit combinations are refused with
//     ERROR_INVALID_PARAMETER without disturbing existing state.

#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>

#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstring>

#include "era_physical.h"

extern "C" __declspec(dllimport) BOOL WINAPI XMemAllocatePhysicalPages(ULONG_PTR flags, PULONG_PTR count,
                                                                     PULONG_PTR pages);
extern "C" __declspec(dllimport) BOOL WINAPI XMemFreePhysicalPages(ULONG_PTR count, PULONG_PTR pages);
extern "C" __declspec(dllimport) void* WINAPI XMemMapPhysicalPages(void* base, ULONG_PTR count,
                                                                   const ULONG_PTR* tokens);
extern "C" __declspec(dllimport) BOOL WINAPI XMemMapPhysicalPagesScatter(void* const* addresses, ULONG_PTR count,
                                                                         const ULONG_PTR* tokens);
extern "C" __declspec(dllimport) void* WINAPI XMemVirtualAlloc(void* address, SIZE_T bytes, DWORD allocation_type,
                                                               ULONGLONG attributes, DWORD protection);
extern "C" __declspec(dllimport) BOOL XMemVirtualQuery(HANDLE process, LPCVOID address, void* buffer);

namespace {
constexpr SIZE_T page_bytes = static_cast<SIZE_T>(era_physical::page_bytes);
constexpr ULONG_PTR mem_64k_pages = static_cast<ULONG_PTR>(era_physical::mem_64k_pages);
constexpr SIZE_T probe_offsets[] = {0, 4096, page_bytes / 2, page_bytes - sizeof(std::uint32_t)};

struct QueryBuffer {
    MEMORY_BASIC_INFORMATION info;
    unsigned char tail[16];
};
static_assert(offsetof(QueryBuffer, tail) == 0x30 && sizeof(QueryBuffer) == 64);

struct FaultInfo {
    bool faulted = false;
    DWORD code = 0;
    ULONG_PTR access_type = 0;  // 0 = read, 1 = write
    ULONG_PTR fault_address = 0;
};

DWORD capture_fault(EXCEPTION_POINTERS* ep, FaultInfo* out) noexcept
{
    out->faulted = true;
    out->code = ep->ExceptionRecord->ExceptionCode;
    if (ep->ExceptionRecord->NumberParameters >= 2) {
        out->access_type = ep->ExceptionRecord->ExceptionInformation[0];
        out->fault_address = ep->ExceptionRecord->ExceptionInformation[1];
    }
    return EXCEPTION_EXECUTE_HANDLER;
}

FaultInfo probe_write_u32(volatile std::uint32_t* ptr, std::uint32_t value) noexcept
{
    FaultInfo info{};
    __try {
        *ptr = value;
    } __except (capture_fault(GetExceptionInformation(), &info)) {
    }
    return info;
}

FaultInfo probe_read_u32(const volatile std::uint32_t* ptr, std::uint32_t* out_value) noexcept
{
    FaultInfo info{};
    __try {
        *out_value = *ptr;
    } __except (capture_fault(GetExceptionInformation(), &info)) {
    }
    return info;
}

volatile std::uint32_t* word_at(void* base, SIZE_T offset) noexcept
{
    return reinterpret_cast<volatile std::uint32_t*>(static_cast<unsigned char*>(base) + offset);
}

bool write_pattern(void* page, std::uint32_t seed) noexcept
{
    for (std::size_t i = 0; i < sizeof(probe_offsets) / sizeof(probe_offsets[0]); ++i) {
        const auto expected = seed ^ static_cast<std::uint32_t>(i * 0x11111111u);
        const FaultInfo fault = probe_write_u32(word_at(page, probe_offsets[i]), expected);
        if (fault.faulted) return false;
    }
    return true;
}

bool check_pattern(void* page, std::uint32_t seed) noexcept
{
    for (std::size_t i = 0; i < sizeof(probe_offsets) / sizeof(probe_offsets[0]); ++i) {
        std::uint32_t observed = 0;
        const FaultInfo fault = probe_read_u32(word_at(page, probe_offsets[i]), &observed);
        const auto expected = seed ^ static_cast<std::uint32_t>(i * 0x11111111u);
        if (fault.faulted || observed != expected) return false;
    }
    return true;
}

bool check_query(const void* address, DWORD expected_state, DWORD expected_protect, DWORD expected_type) noexcept
{
    MEMORY_BASIC_INFORMATION info{};
    if (VirtualQuery(address, &info, sizeof(info)) != sizeof(info)) return false;
    if (info.State != expected_state || info.Protect != expected_protect || info.Type != expected_type) return false;

    QueryBuffer xmem_query{};
    if (!XMemVirtualQuery(GetCurrentProcess(), address, &xmem_query)) return false;
    return xmem_query.info.State == expected_state && xmem_query.info.Protect == expected_protect &&
           xmem_query.info.Type == expected_type;
}

// Reserves two adjacent 64 KiB Windows placeholders: [base, base + 64 KiB) and
// [base + 64 KiB, base + 128 KiB). The second slot stays unmapped as a boundary
// control for cross-region VirtualProtect checks.
struct TwoPlaceholders {
    void* first = nullptr;
    void* second = nullptr;

    bool create() noexcept
    {
        void* base = VirtualAlloc2(GetCurrentProcess(), nullptr, 2 * page_bytes,
                                   MEM_RESERVE | MEM_RESERVE_PLACEHOLDER, PAGE_NOACCESS, nullptr, 0);
        if (!base) return false;
        if (!VirtualFree(base, page_bytes, MEM_RELEASE | MEM_PRESERVE_PLACEHOLDER)) {
            VirtualFree(base, 0, MEM_RELEASE);
            return false;
        }
        first = base;
        second = static_cast<unsigned char*>(base) + page_bytes;
        return true;
    }

    ~TwoPlaceholders()
    {
        if (first) VirtualFree(first, 0, MEM_RELEASE);
        if (second) VirtualFree(second, 0, MEM_RELEASE);
    }
};

bool check_ordinary_commit_protection()
{
    // Reserve 2 pages, commit page 0, leave page 1 reserved (uncommitted).
    void* base = VirtualAlloc(nullptr, 2 * page_bytes, MEM_RESERVE, PAGE_NOACCESS);
    if (!base) {
        std::printf("ordinary: reserve failed error=%lu\n", GetLastError());
        return false;
    }
    auto* page0 = static_cast<unsigned char*>(base);
    auto* page1 = page0 + page_bytes;
    bool ok = true;

    void* committed = VirtualAlloc(page0, page_bytes, MEM_COMMIT, PAGE_READWRITE);
    if (committed != page0 || !check_query(page0, MEM_COMMIT, PAGE_READWRITE, MEM_PRIVATE) ||
        !check_query(page1, MEM_RESERVE, 0, MEM_PRIVATE)) {
        std::printf("ordinary: initial commit/query mismatch\n");
        VirtualFree(base, 0, MEM_RELEASE);
        return false;
    }

    constexpr std::uint32_t seed_a = 0x2468ace1u;
    constexpr std::uint32_t seed_b = 0x13579bdfu;
    if (!write_pattern(page0, seed_a) || !check_pattern(page0, seed_a)) {
        std::printf("ordinary: initial read/write failed\n");
        VirtualFree(base, 0, MEM_RELEASE);
        return false;
    }

    // Transition PAGE_READWRITE -> PAGE_READONLY.
    DWORD old_protect = 0;
    if (!VirtualProtect(page0, page_bytes, PAGE_READONLY, &old_protect) || old_protect != PAGE_READWRITE ||
        !check_query(page0, MEM_COMMIT, PAGE_READONLY, MEM_PRIVATE) || !check_pattern(page0, seed_a)) {
        std::printf("ordinary: PAGE_READONLY transition failed\n");
        ok = false;
    }

    // Negative control: writing to PAGE_READONLY must raise EXCEPTION_ACCESS_VIOLATION
    // and leave stored sentinel bytes untouched.
    const FaultInfo ro_write = probe_write_u32(word_at(page0, probe_offsets[1]), 0xdeadbeefu);
    if (!ro_write.faulted || ro_write.code != EXCEPTION_ACCESS_VIOLATION || ro_write.access_type != 1 ||
        ro_write.fault_address != reinterpret_cast<ULONG_PTR>(word_at(page0, probe_offsets[1])) ||
        !check_pattern(page0, seed_a)) {
        std::printf("ordinary: PAGE_READONLY write control mismatch faulted=%d code=0x%lx type=%llu\n",
                    ro_write.faulted ? 1 : 0, ro_write.code, static_cast<unsigned long long>(ro_write.access_type));
        ok = false;
    }

    // Transition PAGE_READONLY -> PAGE_NOACCESS.
    if (!VirtualProtect(page0, page_bytes, PAGE_NOACCESS, &old_protect) || old_protect != PAGE_READONLY ||
        !check_query(page0, MEM_COMMIT, PAGE_NOACCESS, MEM_PRIVATE)) {
        std::printf("ordinary: PAGE_NOACCESS transition failed\n");
        ok = false;
    }

    // Negative controls: both read and write on PAGE_NOACCESS must fault.
    std::uint32_t dummy = 0;
    const FaultInfo na_read = probe_read_u32(word_at(page0, probe_offsets[0]), &dummy);
    const FaultInfo na_write = probe_write_u32(word_at(page0, probe_offsets[0]), 0xbadc0de0u);
    if (!na_read.faulted || na_read.code != EXCEPTION_ACCESS_VIOLATION || na_read.access_type != 0 ||
        !na_write.faulted || na_write.code != EXCEPTION_ACCESS_VIOLATION || na_write.access_type != 1) {
        std::printf("ordinary: PAGE_NOACCESS read/write control mismatch\n");
        ok = false;
    }

    // Restore PAGE_NOACCESS -> PAGE_READWRITE and verify bytes survived intact.
    if (!VirtualProtect(page0, page_bytes, PAGE_READWRITE, &old_protect) || old_protect != PAGE_NOACCESS ||
        !check_query(page0, MEM_COMMIT, PAGE_READWRITE, MEM_PRIVATE) || !check_pattern(page0, seed_a) ||
        !write_pattern(page0, seed_b) || !check_pattern(page0, seed_b)) {
        std::printf("ordinary: restore PAGE_READWRITE failed\n");
        ok = false;
    }

    // Failed reprotection controls: invalid flag (0), conflicting flags, and spanning into
    // uncommitted page 1 must fail and leave page 0's protection and bytes intact.
    SetLastError(ERROR_SUCCESS);
    const BOOL bad_zero = VirtualProtect(page0, page_bytes, 0, &old_protect);
    const DWORD err_zero = GetLastError();
    SetLastError(ERROR_SUCCESS);
    const BOOL bad_conflict = VirtualProtect(page0, page_bytes, PAGE_READWRITE | PAGE_READONLY, &old_protect);
    const DWORD err_conflict = GetLastError();
    SetLastError(ERROR_SUCCESS);
    const BOOL bad_span = VirtualProtect(page0, 2 * page_bytes, PAGE_READONLY, &old_protect);
    const DWORD err_span = GetLastError();
    if (bad_zero || err_zero != ERROR_INVALID_PARAMETER || bad_conflict || err_conflict != ERROR_INVALID_PARAMETER ||
        bad_span || err_span != ERROR_INVALID_ADDRESS ||
        !check_query(page0, MEM_COMMIT, PAGE_READWRITE, MEM_PRIVATE) || !check_pattern(page0, seed_b)) {
        std::printf("ordinary: failed reprotection control mismatch errs=(%lu,%lu,%lu)\n", err_zero, err_conflict,
                    err_span);
        ok = false;
    }

    // Failed commit past reservation boundary must fail and leave page 0 committed + intact
    // and page 1 uncommitted.
    SetLastError(ERROR_SUCCESS);
    void* over_commit = VirtualAlloc(page0, 3 * page_bytes, MEM_COMMIT, PAGE_READWRITE);
    const DWORD err_over = GetLastError();
    if (over_commit != nullptr || err_over != ERROR_INVALID_ADDRESS ||
        !check_query(page0, MEM_COMMIT, PAGE_READWRITE, MEM_PRIVATE) ||
        !check_query(page1, MEM_RESERVE, 0, MEM_PRIVATE) || !check_pattern(page0, seed_b)) {
        std::printf("ordinary: failed over-commit control mismatch ptr=%p err=%lu\n", over_commit, err_over);
        ok = false;
    }

    // Idempotent re-commit on ordinary MEM_PRIVATE committed page succeeds, and MEM_DECOMMIT
    // returns it to MEM_RESERVE.
    SetLastError(ERROR_SUCCESS);
    void* recommit = VirtualAlloc(page0, page_bytes, MEM_COMMIT, PAGE_READWRITE);
    if (recommit != page0 || !check_pattern(page0, seed_b)) {
        std::printf("ordinary: idempotent recommit failed err=%lu\n", GetLastError());
        ok = false;
    }
    if (!VirtualFree(page0, page_bytes, MEM_DECOMMIT) || !check_query(page0, MEM_RESERVE, 0, MEM_PRIVATE)) {
        std::printf("ordinary: MEM_DECOMMIT failed err=%lu\n", GetLastError());
        ok = false;
    }

    VirtualFree(base, 0, MEM_RELEASE);
    std::printf("ordinary_commit_protection: %s (bad_zero=%lu bad_conflict=%lu bad_span=%lu over_commit=%lu)\n",
                ok ? "PASS" : "FAIL", err_zero, err_conflict, err_span, err_over);
    return ok;
}

bool check_shared_view_protection(DWORD& out_mapped_decommit_error)
{
    out_mapped_decommit_error = ERROR_SUCCESS;

    ULONG_PTR count = 1;
    ULONG_PTR token = 0;
    if (!XMemAllocatePhysicalPages(mem_64k_pages, &count, &token) || count != 1 || token == 0) {
        std::printf("shared: XMemAllocatePhysicalPages failed err=%lu\n", GetLastError());
        return false;
    }

    TwoPlaceholders slots_a;
    TwoPlaceholders slots_b;
    if (!slots_a.create() || !slots_b.create()) {
        std::printf("shared: placeholder creation failed err=%lu\n", GetLastError());
        XMemFreePhysicalPages(1, &token);
        return false;
    }

    void* view1 = slots_a.first;
    void* view2 = slots_b.first;
    bool ok = true;

    if (XMemMapPhysicalPages(view1, 1, &token) != view1 || !XMemMapPhysicalPagesScatter(&view2, 1, &token)) {
        std::printf("shared: mapping views failed err=%lu\n", GetLastError());
        XMemMapPhysicalPages(view1, 1, nullptr);
        XMemFreePhysicalPages(1, &token);
        return false;
    }

    if (!check_query(view1, MEM_COMMIT, PAGE_READWRITE, MEM_MAPPED) ||
        !check_query(view2, MEM_COMMIT, PAGE_READWRITE, MEM_MAPPED)) {
        std::printf("shared: initial VirtualQuery/XMemVirtualQuery mismatch\n");
        ok = false;
    }

    // Live shared-page aliasing: write via view1, observe immediately via view2.
    constexpr std::uint32_t seed_1 = 0x55aa33ccu;
    constexpr std::uint32_t seed_2 = 0x9966a55au;
    constexpr std::uint32_t seed_3 = 0x71234567u;
    if (!write_pattern(view1, seed_1) || !check_pattern(view2, seed_1)) {
        std::printf("shared: initial alias visibility failed\n");
        ok = false;
    }

    // Protect view1 to PAGE_READONLY; view2 must remain PAGE_READWRITE (per-view protection).
    DWORD old_protect = 0;
    if (!VirtualProtect(view1, page_bytes, PAGE_READONLY, &old_protect) || old_protect != PAGE_READWRITE ||
        !check_query(view1, MEM_COMMIT, PAGE_READONLY, MEM_MAPPED) ||
        !check_query(view2, MEM_COMMIT, PAGE_READWRITE, MEM_MAPPED) || !check_pattern(view1, seed_1)) {
        std::printf("shared: PAGE_READONLY transition on view1 failed\n");
        ok = false;
    }

    // Negative control: writing through PAGE_READONLY view1 faults and leaves bytes untouched.
    const FaultInfo ro_write = probe_write_u32(word_at(view1, probe_offsets[2]), 0x0badf00du);
    if (!ro_write.faulted || ro_write.code != EXCEPTION_ACCESS_VIOLATION || ro_write.access_type != 1 ||
        ro_write.fault_address != reinterpret_cast<ULONG_PTR>(word_at(view1, probe_offsets[2])) ||
        !check_pattern(view1, seed_1) || !check_pattern(view2, seed_1)) {
        std::printf("shared: view1 PAGE_READONLY write control mismatch\n");
        ok = false;
    }

    // Live shared-page discrepancy: writing through still-RW view2 succeeds and updates
    // what PAGE_READONLY view1 reads.
    if (!write_pattern(view2, seed_2) || !check_pattern(view1, seed_2)) {
        std::printf("shared: write through view2 not observed through RO view1\n");
        ok = false;
    }

    // Protect view1 to PAGE_NOACCESS: both read and write through view1 must fault, while
    // view2 remains readable and writable.
    if (!VirtualProtect(view1, page_bytes, PAGE_NOACCESS, &old_protect) || old_protect != PAGE_READONLY ||
        !check_query(view1, MEM_COMMIT, PAGE_NOACCESS, MEM_MAPPED) ||
        !check_query(view2, MEM_COMMIT, PAGE_READWRITE, MEM_MAPPED)) {
        std::printf("shared: PAGE_NOACCESS transition on view1 failed\n");
        ok = false;
    }
    std::uint32_t dummy = 0;
    const FaultInfo na_read = probe_read_u32(word_at(view1, probe_offsets[0]), &dummy);
    const FaultInfo na_write = probe_write_u32(word_at(view1, probe_offsets[0]), 0xfeedfaceu);
    if (!na_read.faulted || na_read.code != EXCEPTION_ACCESS_VIOLATION || na_read.access_type != 0 ||
        !na_write.faulted || na_write.code != EXCEPTION_ACCESS_VIOLATION || na_write.access_type != 1 ||
        !check_pattern(view2, seed_2) || !write_pattern(view2, seed_3)) {
        std::printf("shared: PAGE_NOACCESS isolation control mismatch\n");
        ok = false;
    }

    // Restore view1 to PAGE_READWRITE and confirm it observes seed_3 written via view2.
    if (!VirtualProtect(view1, page_bytes, PAGE_READWRITE, &old_protect) || old_protect != PAGE_NOACCESS ||
        !check_query(view1, MEM_COMMIT, PAGE_READWRITE, MEM_MAPPED) || !check_pattern(view1, seed_3)) {
        std::printf("shared: restore view1 PAGE_READWRITE failed\n");
        ok = false;
    }

    // Failed reprotection controls on live shared view: invalid flag (0) and spanning into
    // unmapped placeholder slots_a.second must fail and leave view1/view2 intact.
    SetLastError(ERROR_SUCCESS);
    const BOOL bad_zero = VirtualProtect(view1, page_bytes, 0, &old_protect);
    const DWORD err_zero = GetLastError();
    SetLastError(ERROR_SUCCESS);
    const BOOL bad_span = VirtualProtect(view1, 2 * page_bytes, PAGE_READONLY, &old_protect);
    const DWORD err_span = GetLastError();
    if (bad_zero || err_zero != ERROR_INVALID_PARAMETER || bad_span || err_span != ERROR_INVALID_ADDRESS ||
        !check_query(view1, MEM_COMMIT, PAGE_READWRITE, MEM_MAPPED) || !check_pattern(view1, seed_3) ||
        !check_pattern(view2, seed_3)) {
        std::printf("shared: failed reprotection control mismatch errs=(%lu,%lu)\n", err_zero, err_span);
        ok = false;
    }

    // Observable behavior vs ordinary committed pages:
    // - VirtualAlloc(..., MEM_COMMIT, PAGE_READWRITE) on a live MEM_MAPPED view succeeds
    //   idempotently while keeping MEM_MAPPED and stored bytes intact.
    // - VirtualFree(..., MEM_DECOMMIT) succeeds on ordinary MEM_PRIVATE pages, but fails on
    //   a live MEM_MAPPED view (leaving both views, bytes, and protections intact).
    SetLastError(ERROR_SUCCESS);
    void* mapped_recommit = VirtualAlloc(view1, page_bytes, MEM_COMMIT, PAGE_READWRITE);
    if (mapped_recommit != view1 || !check_query(view1, MEM_COMMIT, PAGE_READWRITE, MEM_MAPPED) ||
        !check_pattern(view1, seed_3) || !check_pattern(view2, seed_3)) {
        std::printf("shared: VirtualAlloc(MEM_COMMIT) on mapped view mismatch ptr=%p err=%lu\n", mapped_recommit,
                    GetLastError());
        ok = false;
    }
    SetLastError(ERROR_SUCCESS);
    const BOOL mapped_decommit = VirtualFree(view1, page_bytes, MEM_DECOMMIT);
    out_mapped_decommit_error = GetLastError();
    if (mapped_decommit || out_mapped_decommit_error != ERROR_INVALID_PARAMETER ||
        !check_query(view1, MEM_COMMIT, PAGE_READWRITE, MEM_MAPPED) ||
        !check_query(view2, MEM_COMMIT, PAGE_READWRITE, MEM_MAPPED) || !check_pattern(view1, seed_3) ||
        !check_pattern(view2, seed_3)) {
        std::printf("shared: VirtualFree(MEM_DECOMMIT) on mapped view control mismatch ok=%d err=%lu\n",
                    mapped_decommit ? 1 : 0, out_mapped_decommit_error);
        ok = false;
    }

    // Failed XMemVirtualAlloc (unsupported second-commit combinations) and failed xmem
    // remap/free while mapped must fail and leave both live views intact.
    SetLastError(ERROR_SUCCESS);
    void* refused_commit = XMemVirtualAlloc(nullptr, page_bytes, MEM_RESERVE | MEM_COMMIT, 0x21, PAGE_READWRITE);
    const DWORD err_xva_commit = GetLastError();
    SetLastError(ERROR_SUCCESS);
    void* refused_ro = XMemVirtualAlloc(view1, page_bytes, MEM_COMMIT, 0x21, PAGE_READONLY);
    const DWORD err_xva_ro = GetLastError();
    SetLastError(ERROR_SUCCESS);
    void* refused_remap = XMemMapPhysicalPages(view1, 1, &token);
    const DWORD err_remap = GetLastError();
    SetLastError(ERROR_SUCCESS);
    const BOOL refused_free = XMemFreePhysicalPages(1, &token);
    const DWORD err_free = GetLastError();
    if (refused_commit != nullptr || err_xva_commit != ERROR_INVALID_PARAMETER || refused_ro != nullptr ||
        err_xva_ro != ERROR_INVALID_PARAMETER || refused_remap != nullptr || err_remap != ERROR_INVALID_PARAMETER ||
        refused_free || err_free != ERROR_INVALID_PARAMETER ||
        !check_query(view1, MEM_COMMIT, PAGE_READWRITE, MEM_MAPPED) ||
        !check_query(view2, MEM_COMMIT, PAGE_READWRITE, MEM_MAPPED) || !check_pattern(view1, seed_3) ||
        !check_pattern(view2, seed_3)) {
        std::printf("shared: failed xmem allocation/free preservation mismatch errs=(%lu,%lu,%lu,%lu)\n",
                    err_xva_commit, err_xva_ro, err_remap, err_free);
        ok = false;
    }

    // Unmap both views, remap view1, and confirm bytes survive unmap/remap while the grant lives.
    if (XMemMapPhysicalPages(view1, 1, nullptr) != view1 || !XMemMapPhysicalPagesScatter(&view2, 1, nullptr) ||
        XMemMapPhysicalPages(view1, 1, &token) != view1 || !check_pattern(view1, seed_3)) {
        std::printf("shared: unmap/remap persistence check failed err=%lu\n", GetLastError());
        ok = false;
    }

    if (XMemMapPhysicalPages(view1, 1, nullptr) != view1 || !XMemFreePhysicalPages(1, &token)) {
        std::printf("shared: cleanup unmap/free failed err=%lu\n", GetLastError());
        ok = false;
    }

    std::printf(
        "shared_view_protection: %s (bad_zero=%lu bad_span=%lu mapped_decommit=%lu xva_commit=%lu xva_ro=%lu)\n",
        ok ? "PASS" : "FAIL", err_zero, err_span, out_mapped_decommit_error, err_xva_commit, err_xva_ro);
    return ok;
}
}  // namespace

int main()
{
    const bool ordinary_ok = check_ordinary_commit_protection();
    DWORD mapped_decommit_error = ERROR_SUCCESS;
    const bool shared_ok = check_shared_view_protection(mapped_decommit_error);
    const bool passed = ordinary_ok && shared_ok;

    std::printf(
        "first_observable_discrepancy: ordinary_commit=MEM_PRIVATE(0x20000, MEM_DECOMMIT succeeds, no VA aliasing) "
        "vs live_shared_view=MEM_MAPPED(0x40000, MEM_DECOMMIT refused err=%lu, live VA aliasing with per-view "
        "VirtualProtect isolation and byte persistence across unmap/remap)\n",
        mapped_decommit_error);
    std::printf("xmem_commit_protection: %s\n", passed ? "PASS" : "FAIL");
    return passed ? 0 : 1;
}
