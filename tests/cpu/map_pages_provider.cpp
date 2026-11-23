// Controlled recording provider for XMemMapPhysicalPages and XMemMapPhysicalPagesScatter.
// Validates 64 KiB address alignment, page counts, mapping vs unmapping (NULL page array),
// and records call statistics.
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#include <cstdint>

namespace {
constexpr std::uintptr_t page_alignment_mask = 0xFFFF; // 64 KiB alignment requirement

volatile LONG map_calls = 0;
volatile LONG unmap_calls = 0;
volatile LONG scatter_map_calls = 0;
volatile LONG scatter_unmap_calls = 0;
}

extern "C" __declspec(dllexport) LPVOID WINAPI XMemMapPhysicalPages(
    LPVOID lpAddress,
    ULONG_PTR cPages,
    const ULONG_PTR* rgPages)
{
    const auto address = reinterpret_cast<std::uintptr_t>(lpAddress);
    if (!lpAddress || (address & page_alignment_mask) != 0 || cPages == 0) {
        SetLastError(ERROR_INVALID_PARAMETER);
        return nullptr;
    }

    if (!rgPages) {
        // Unmap request: unbinds physical pages, address reservation remains.
        InterlockedIncrement(&unmap_calls);
        return lpAddress;
    }

    // Map request: binds physical page numbers to virtual address range.
    InterlockedIncrement(&map_calls);
    return lpAddress;
}

extern "C" __declspec(dllexport) BOOL WINAPI XMemMapPhysicalPagesScatter(
    LPVOID* rgVirtualAddresses,
    ULONG_PTR cPages,
    const ULONG_PTR* rgPages)
{
    if (!rgVirtualAddresses || cPages == 0) {
        SetLastError(ERROR_INVALID_PARAMETER);
        return FALSE;
    }

    for (ULONG_PTR i = 0; i < cPages; ++i) {
        const auto addr = reinterpret_cast<std::uintptr_t>(rgVirtualAddresses[i]);
        if (!rgVirtualAddresses[i] || (addr & page_alignment_mask) != 0) {
            SetLastError(ERROR_INVALID_PARAMETER);
            return FALSE;
        }
    }

    if (!rgPages) {
        // Unmap scatter request: unbinds physical pages for all listed virtual addresses.
        InterlockedIncrement(&scatter_unmap_calls);
        return TRUE;
    }

    // Map scatter request: binds each physical page to corresponding virtual address.
    InterlockedIncrement(&scatter_map_calls);
    return TRUE;
}

extern "C" __declspec(dllexport) uint32_t WINAPI get_map_pages_call_count(void)
{
    return static_cast<uint32_t>(map_calls);
}

extern "C" __declspec(dllexport) uint32_t WINAPI get_map_pages_unmap_count(void)
{
    return static_cast<uint32_t>(unmap_calls);
}

extern "C" __declspec(dllexport) uint32_t WINAPI get_scatter_map_call_count(void)
{
    return static_cast<uint32_t>(scatter_map_calls);
}

extern "C" __declspec(dllexport) uint32_t WINAPI get_scatter_unmap_count(void)
{
    return static_cast<uint32_t>(scatter_unmap_calls);
}

extern "C" __declspec(dllexport) void WINAPI reset_map_pages_records(void)
{
    InterlockedExchange(&map_calls, 0);
    InterlockedExchange(&unmap_calls, 0);
    InterlockedExchange(&scatter_map_calls, 0);
    InterlockedExchange(&scatter_unmap_calls, 0);
}
