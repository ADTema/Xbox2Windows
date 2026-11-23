#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>

#include "era_physical.h"

#include <iterator>
#include <limits>
#include <map>
#include <mutex>
#include <new>

namespace {
struct Backing {
    HANDLE section;
    ULONG_PTR views = 0;
};

// Keep grant transitions and section views serialized. A grant can outlive all its
// views so its bytes survive unmapping. Its backing is released before reuse.
struct PhysicalMemory {
    std::mutex mutex;
    std::map<ULONG_PTR, Backing> backings;
    std::map<ULONG_PTR, ULONG_PTR> views;

    ~PhysicalMemory()
    {
        for (const auto& view : views)
            UnmapViewOfFile(reinterpret_cast<void*>(view.first));
        for (const auto& backing : backings)
            CloseHandle(backing.second.section);
    }
};

PhysicalMemory memory;
constexpr SIZE_T page_bytes = era_physical::page_bytes;

BOOL physical_result(era_physical::Status status) noexcept
{
    switch (status) {
    case era_physical::Status::ok:
        SetLastError(ERROR_SUCCESS);
        return TRUE;
    case era_physical::Status::exhausted:
        SetLastError(ERROR_NOT_ENOUGH_MEMORY);
        return FALSE;
    default:
        SetLastError(ERROR_INVALID_PARAMETER);
        return FALSE;
    }
}

HANDLE section_for(ULONG_PTR page)
{
    const auto existing = memory.backings.find(page);
    if (existing != memory.backings.end())
        return existing->second.section;
    const HANDLE section = CreateFileMappingW(INVALID_HANDLE_VALUE, nullptr, PAGE_READWRITE,
                                              0, page_bytes, nullptr);
    if (section) {
        try {
            memory.backings.emplace(page, Backing{section});
        } catch (const std::bad_alloc&) {
            CloseHandle(section);
            throw;
        }
    }
    return section;
}

bool map_view(ULONG_PTR address, HANDLE section)
{
    return MapViewOfFile3(section, GetCurrentProcess(), reinterpret_cast<void*>(address), 0,
                          page_bytes, MEM_REPLACE_PLACEHOLDER, PAGE_READWRITE, nullptr, 0) != nullptr;
}

bool unmap_view(ULONG_PTR address)
{
    return UnmapViewOfFile2(GetCurrentProcess(), reinterpret_cast<void*>(address),
                           MEM_PRESERVE_PLACEHOLDER) != FALSE;
}

// Destinations must be caller-owned, page-sized Windows placeholders. Live views
// are owned by this shim until it unmaps them. The caller must not replace them.
template <typename AddressAt>
BOOL map_pages(ULONG_PTR count, const ULONG_PTR* tokens, const AddressAt& address_at) noexcept
{
    if (!count || count > era_physical::capacity_pages)
        return physical_result(era_physical::Status::invalid);
    try {
        const std::lock_guard guard(memory.mutex);
        std::map<ULONG_PTR, ULONG_PTR> batch;
        for (ULONG_PTR i = 0; i < count; ++i) {
            const auto address = address_at(i);
            const auto live = memory.views.find(address);
            if (!address || address % page_bytes ||
                (tokens ? live != memory.views.end() || !era_physical::owns(tokens[i])
                        : live == memory.views.end()))
                return physical_result(era_physical::Status::invalid);
            if (!batch.emplace(address, tokens ? tokens[i] : live->second).second)
                return physical_result(era_physical::Status::invalid);
        }
        if (tokens) {
            for (const auto& [address, page] : batch) {
                if (!section_for(page)) return FALSE;
            }
            auto next = batch.begin();
            for (; next != batch.end(); ++next) {
                if (!map_view(next->first, memory.backings.at(next->second).section)) {
                    const DWORD error = GetLastError();
                    while (next != batch.begin()) {
                        const auto previous = --next;
                        if (!unmap_view(previous->first)) {
                            ++memory.backings.at(previous->second).views;
                            const auto position = std::next(previous);
                            memory.views.insert(batch.extract(previous));
                            next = position;
                        }
                    }
                    SetLastError(error);
                    return FALSE;
                }
            }
            for (const auto& [address, page] : batch)
                ++memory.backings.at(page).views;
            memory.views.merge(batch);
        } else {
            auto next = batch.begin();
            for (; next != batch.end(); ++next) {
                if (!unmap_view(next->first)) {
                    const DWORD error = GetLastError();
                    while (next != batch.begin()) {
                        const auto& [address, page] = *--next;
                        if (!map_view(address, memory.backings.at(page).section)) {
                            --memory.backings.at(page).views;
                            memory.views.erase(address);
                        }
                    }
                    SetLastError(error);
                    return FALSE;
                }
            }
            for (const auto& [address, page] : batch) {
                --memory.backings.at(page).views;
                memory.views.erase(address);
            }
        }
    } catch (const std::bad_alloc&) {
        return physical_result(era_physical::Status::exhausted);
    }
    return physical_result(era_physical::Status::ok);
}
}

extern "C" BOOL WINAPI XMemAllocatePhysicalPages(ULONG_PTR flags, PULONG_PTR count, PULONG_PTR pages)
{
    static_assert(sizeof(ULONG_PTR) == sizeof(std::uint64_t));
    const std::lock_guard guard(memory.mutex);
    return physical_result(era_physical::allocate(flags, reinterpret_cast<std::uint64_t*>(count),
                                                  reinterpret_cast<std::uint64_t*>(pages)));
}

extern "C" BOOL WINAPI XMemFreePhysicalPages(ULONG_PTR count, PULONG_PTR pages)
{
    if (!pages || !count || count > era_physical::capacity_pages)
        return physical_result(era_physical::Status::invalid);
    const std::lock_guard guard(memory.mutex);
    for (ULONG_PTR i = 0; i < count; ++i) {
        const auto backing = memory.backings.find(pages[i]);
        if (backing != memory.backings.end() && backing->second.views)
            return physical_result(era_physical::Status::invalid);
    }
    const auto status = era_physical::release(count, reinterpret_cast<const std::uint64_t*>(pages));
    if (status == era_physical::Status::ok) {
        for (ULONG_PTR i = 0; i < count; ++i) {
            const auto backing = memory.backings.find(pages[i]);
            if (backing != memory.backings.end()) {
                CloseHandle(backing->second.section);
                memory.backings.erase(backing);
            }
        }
    }
    return physical_result(status);
}

extern "C" void* WINAPI XMemMapPhysicalPages(void* base, ULONG_PTR count, const ULONG_PTR* tokens)
{
    const auto address = reinterpret_cast<ULONG_PTR>(base);
    if (!address || count > (std::numeric_limits<ULONG_PTR>::max() - address) / page_bytes) {
        SetLastError(ERROR_INVALID_PARAMETER);
        return nullptr;
    }
    return map_pages(count, tokens, [=](ULONG_PTR i) { return address + i * page_bytes; }) ? base : nullptr;
}

extern "C" BOOL WINAPI XMemMapPhysicalPagesScatter(void* const* addresses, ULONG_PTR count,
                                                   const ULONG_PTR* tokens)
{
    if (!addresses) return physical_result(era_physical::Status::invalid);
    return map_pages(count, tokens, [=](ULONG_PTR i) { return reinterpret_cast<ULONG_PTR>(addresses[i]); });
}
