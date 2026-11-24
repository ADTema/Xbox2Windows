// Fixture-only desktop xgameruntime.dll skeleton. It is built into the test
// fixture directory, never beside the normal shims, and does not claim ABI
// completeness: every public thunk below records its component and function,
// then returns E_NOTIMPL until a real implementation lands.
//
// The public names and signatures are taken from the Microsoft GDK reference:
//   XUserAddAsync                       https://learn.microsoft.com/en-us/gaming/gdk/docs/reference/system/xuser/functions/xuseraddasync?view=gdk-2604
//   XGameSaveInitializeProviderAsync    https://learn.microsoft.com/en-us/gaming/gdk/docs/reference/system/xgamesave/functions/xgamesaveinitializeproviderasync?view=gdk-2610
//   XPackageMountWithUiAsync            https://learn.microsoft.com/en-us/gaming/gdk/docs/reference/system/xpackage/functions/xpackagemountwithuiasync?view=gdk-2610
//   XSystemGetConsoleId                 https://learn.microsoft.com/en-us/gaming/gdk/docs/reference/system/xsystem/functions/xsystemgetconsoleid?view=gdk-2604
//   XGameGetXboxTitleId                 https://learn.microsoft.com/en-us/gaming/gdk/docs/reference/system/xgame/functions/xgamegetxboxtitleid?view=gdk-2604
//   XAsyncGetStatus                     https://learn.microsoft.com/en-us/gaming/gdk/docs/reference/system/xasync/functions/xasyncgetstatus?view=gdk-2604
//   XTaskQueueCreate                    https://learn.microsoft.com/en-us/gaming/gdk/docs/reference/system/xtaskqueue/functions/xtaskqueuecreate?view=gdk-2604
//
// The opaque types stand in for the public headers so this skeleton has no GDK
// SDK dependency. WINAPI is explicit on x64 Windows; the platform has one
// function calling convention.
#include <array>
#include <cstddef>
#include <cstdint>

#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>

struct XAsyncBlock;
struct XUserHandleStorage;
using XUserHandle = XUserHandleStorage*;
struct XTaskQueueHandleStorage;
using XTaskQueueHandle = XTaskQueueHandleStorage*;
enum XUserAddOptions : std::uint32_t;
enum XTaskQueueDispatchMode : std::uint32_t;

// Shim-only observability interface. It is not a GDK API. GetLog returns the
// number of entries in the bounded log and copies the oldest available entries;
// ClearLog is used by the load test and for repeatable diagnostics.
struct XGameRuntimeShimLogEntry {
    std::uint32_t sequence;
    HRESULT result;
    const char* component;
    const char* function;
};

static_assert(sizeof(XGameRuntimeShimLogEntry) == 24);
static_assert(offsetof(XGameRuntimeShimLogEntry, sequence) == 0);
static_assert(offsetof(XGameRuntimeShimLogEntry, result) == 4);
static_assert(offsetof(XGameRuntimeShimLogEntry, component) == 8);
static_assert(offsetof(XGameRuntimeShimLogEntry, function) == 16);

// This one list is expanded to define the exported thunks and to populate the
// inspectable metadata table. Adding an entry cannot change one without the
// other. The signatures are the public GDK signatures documented above.
#define XGAMERUNTIME_THUNK_TABLE(X) \
    X(XUserAddAsync, XUser, (XUserAddOptions, XAsyncBlock*)) \
    X(XGameSaveInitializeProviderAsync, XGameSave, (XUserHandle, const char*, bool, XAsyncBlock*)) \
    X(XPackageMountWithUiAsync, XPackage, (const char*, XAsyncBlock*)) \
    X(XSystemGetConsoleId, XSystem, (std::size_t, char*, std::size_t*)) \
    X(XGameGetXboxTitleId, XGame, (std::uint32_t*)) \
    X(XAsyncGetStatus, XAsync, (XAsyncBlock*, bool)) \
    X(XTaskQueueCreate, XTaskQueue, (XTaskQueueDispatchMode, XTaskQueueDispatchMode, XTaskQueueHandle*))

namespace xgameruntime_shim {
constexpr HRESULT not_implemented = static_cast<HRESULT>(0x80004001L);
static_assert(not_implemented == E_NOTIMPL);

struct ThunkEntry {
    const char* name;
    const char* component;
    const char* function;
};

#define XGAMERUNTIME_COUNT_THUNK(name, component, parameters) +1
inline constexpr std::size_t thunk_count = 0 XGAMERUNTIME_THUNK_TABLE(XGAMERUNTIME_COUNT_THUNK);
#undef XGAMERUNTIME_COUNT_THUNK

#define XGAMERUNTIME_TABLE_ROW(name, component, parameters) ThunkEntry{#name, #component, #name},
inline constexpr std::array<ThunkEntry, thunk_count> thunks = {
    XGAMERUNTIME_THUNK_TABLE(XGAMERUNTIME_TABLE_ROW)
};
#undef XGAMERUNTIME_TABLE_ROW

constexpr bool same_text(const char* left, const char* right) noexcept
{
    if (!left || !right) return false;
    while (*left && *right) {
        if (*left++ != *right++) return false;
    }
    return *left == *right;
}

constexpr bool valid_thunk_table(const std::array<ThunkEntry, thunk_count>& table) noexcept
{
    for (std::size_t i = 0; i < table.size(); ++i) {
        if (!table[i].name || !table[i].name[0] || !table[i].component ||
            !table[i].component[0] || !table[i].function || !table[i].function[0]) {
            return false;
        }
        for (std::size_t j = i + 1; j < table.size(); ++j) {
            if (same_text(table[i].name, table[j].name)) return false;
        }
    }
    return true;
}

constexpr bool has_component(const std::array<ThunkEntry, thunk_count>& table,
                             const char* component) noexcept
{
    for (const auto& entry : table) {
        if (same_text(entry.component, component)) return true;
    }
    return false;
}

// A malformed table fails at compile time rather than producing an ambiguous
// export at load time.
static_assert(valid_thunk_table(thunks), "XGameRuntime thunk table has an empty or duplicate name");
static_assert(has_component(thunks, "XUser"));
static_assert(has_component(thunks, "XGameSave"));
static_assert(has_component(thunks, "XPackage"));
static_assert(has_component(thunks, "XSystem"));
static_assert(has_component(thunks, "XGame"));
static_assert(has_component(thunks, "XAsync"));
static_assert(has_component(thunks, "XTaskQueue"));

constexpr std::size_t log_capacity = 64;

struct LogState {
    SRWLOCK lock = SRWLOCK_INIT;
    std::array<XGameRuntimeShimLogEntry, log_capacity> entries{};
    std::size_t first = 0;
    std::size_t count = 0;
    std::uint32_t next_sequence = 1;
};

LogState log_state;

HRESULT record_call(const char* component, const char* function) noexcept
{
    AcquireSRWLockExclusive(&log_state.lock);
    if (log_state.count == log_state.entries.size()) {
        log_state.first = (log_state.first + 1) % log_state.entries.size();
        --log_state.count;
    }
    const auto index = (log_state.first + log_state.count) % log_state.entries.size();
    log_state.entries[index] = XGameRuntimeShimLogEntry{
        log_state.next_sequence++, not_implemented, component, function};
    ++log_state.count;
    ReleaseSRWLockExclusive(&log_state.lock);
    return not_implemented;
}

std::size_t copy_log(XGameRuntimeShimLogEntry* output, std::size_t capacity) noexcept
{
    AcquireSRWLockShared(&log_state.lock);
    const auto copied = output && capacity < log_state.count ? capacity : log_state.count;
    const auto actual_copies = output ? copied : 0;
    for (std::size_t i = 0; i < actual_copies; ++i) {
        output[i] = log_state.entries[(log_state.first + i) % log_state.entries.size()];
    }
    const auto total = log_state.count;
    ReleaseSRWLockShared(&log_state.lock);
    return total;
}

void clear_log() noexcept
{
    AcquireSRWLockExclusive(&log_state.lock);
    log_state.first = 0;
    log_state.count = 0;
    log_state.next_sequence = 1;
    ReleaseSRWLockExclusive(&log_state.lock);
}
}  // namespace xgameruntime_shim

#define XGAMERUNTIME_DEFINE_THUNK(name, component, parameters) \
    extern "C" __declspec(dllexport) HRESULT WINAPI name parameters noexcept \
    { \
        return ::xgameruntime_shim::record_call(#component, #name); \
    }
XGAMERUNTIME_THUNK_TABLE(XGAMERUNTIME_DEFINE_THUNK)
#undef XGAMERUNTIME_DEFINE_THUNK

extern "C" __declspec(dllexport) std::size_t WINAPI XGameRuntimeShimGetLog(
    XGameRuntimeShimLogEntry* entries, std::size_t capacity) noexcept
{
    return xgameruntime_shim::copy_log(entries, capacity);
}

extern "C" __declspec(dllexport) void WINAPI XGameRuntimeShimClearLog() noexcept
{
    xgameruntime_shim::clear_log();
}
