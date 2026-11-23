// Loads the built xgameruntime.dll, resolves every thunk in the public table,
// calls each one, and checks the shim's deterministic call log. The unknown
// export lookup is the negative control: a missing export must return null,
// while a present skeleton thunk returns E_NOTIMPL.
#include <array>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstring>

#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>

namespace {
constexpr HRESULT not_implemented = static_cast<HRESULT>(0x80004001L);
static_assert(not_implemented == E_NOTIMPL);

struct XAsyncBlock;
struct XUserHandleStorage;
using XUserHandle = XUserHandleStorage*;
struct XTaskQueueHandleStorage;
using XTaskQueueHandle = XTaskQueueHandleStorage*;
enum class XUserAddOptions : std::uint32_t { None = 0 };
enum class XTaskQueueDispatchMode : std::uint32_t { Manual = 0 };

struct ExpectedThunk {
    const char* name;
    const char* component;
    const char* function;
};

constexpr std::array<ExpectedThunk, 7> expected_thunks{{
    {"XUserAddAsync", "XUser", "XUserAddAsync"},
    {"XGameSaveInitializeProviderAsync", "XGameSave", "XGameSaveInitializeProviderAsync"},
    {"XPackageMountWithUiAsync", "XPackage", "XPackageMountWithUiAsync"},
    {"XSystemGetConsoleId", "XSystem", "XSystemGetConsoleId"},
    {"XGameGetXboxTitleId", "XGame", "XGameGetXboxTitleId"},
    {"XAsyncGetStatus", "XAsync", "XAsyncGetStatus"},
    {"XTaskQueueCreate", "XTaskQueue", "XTaskQueueCreate"},
}};

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

using UserAddAsync = HRESULT(WINAPI*)(XUserAddOptions, XAsyncBlock*);
using GameSaveInitializeProviderAsync = HRESULT(WINAPI*)(XUserHandle, const char*, bool, XAsyncBlock*);
using PackageMountWithUiAsync = HRESULT(WINAPI*)(const char*, XAsyncBlock*);
using SystemGetConsoleId = HRESULT(WINAPI*)(std::size_t, char*, std::size_t*);
using GameGetXboxTitleId = HRESULT(WINAPI*)(std::uint32_t*);
using AsyncGetStatus = HRESULT(WINAPI*)(XAsyncBlock*, bool);
using TaskQueueCreate = HRESULT(WINAPI*)(XTaskQueueDispatchMode, XTaskQueueDispatchMode,
                                         XTaskQueueHandle*);
using GetLog = std::size_t(WINAPI*)(XGameRuntimeShimLogEntry*, std::size_t);
using ClearLog = void(WINAPI*)();

struct LoadedShim {
    HMODULE module = nullptr;

    ~LoadedShim()
    {
        if (module) FreeLibrary(module);
    }
};

bool export_names_are_unique() noexcept
{
    for (std::size_t i = 0; i < expected_thunks.size(); ++i) {
        if (!expected_thunks[i].name[0]) {
            std::printf("FAIL: empty export name at index %zu\n", i);
            return false;
        }
        for (std::size_t j = i + 1; j < expected_thunks.size(); ++j) {
            if (std::strcmp(expected_thunks[i].name, expected_thunks[j].name) == 0) {
                std::printf("FAIL: duplicate export name %s\n", expected_thunks[i].name);
                return false;
            }
        }
    }
    return true;
}

template <typename Proc>
bool find_proc(HMODULE module, const char* name, Proc& proc)
{
    const FARPROC found = GetProcAddress(module, name);
    if (!found) {
        std::printf("FAIL: missing export %s\n", name);
        return false;
    }
    HMODULE owner = nullptr;
    if (!GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS |
                                GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                            reinterpret_cast<LPCWSTR>(found), &owner) ||
        owner != module) {
        std::printf("FAIL: export %s is not owned by the loaded shim\n", name);
        return false;
    }
    proc = reinterpret_cast<Proc>(found);
    return true;
}

bool calls_return_not_implemented(HMODULE module)
{
    UserAddAsync user_add = nullptr;
    GameSaveInitializeProviderAsync game_save_initialize = nullptr;
    PackageMountWithUiAsync package_mount = nullptr;
    SystemGetConsoleId system_get_console_id = nullptr;
    GameGetXboxTitleId game_get_xbox_title_id = nullptr;
    AsyncGetStatus async_get_status = nullptr;
    TaskQueueCreate task_queue_create = nullptr;

    if (!find_proc(module, expected_thunks[0].name, user_add) ||
        !find_proc(module, expected_thunks[1].name, game_save_initialize) ||
        !find_proc(module, expected_thunks[2].name, package_mount) ||
        !find_proc(module, expected_thunks[3].name, system_get_console_id) ||
        !find_proc(module, expected_thunks[4].name, game_get_xbox_title_id) ||
        !find_proc(module, expected_thunks[5].name, async_get_status) ||
        !find_proc(module, expected_thunks[6].name, task_queue_create)) {
        return false;
    }

    struct Call {
        const char* name;
        HRESULT result;
    };
    const std::array<Call, 7> calls{{
        {expected_thunks[0].name, user_add(XUserAddOptions::None, nullptr)},
        {expected_thunks[1].name, game_save_initialize(nullptr, nullptr, false, nullptr)},
        {expected_thunks[2].name, package_mount(nullptr, nullptr)},
        {expected_thunks[3].name, system_get_console_id(0, nullptr, nullptr)},
        {expected_thunks[4].name, game_get_xbox_title_id(nullptr)},
        {expected_thunks[5].name, async_get_status(nullptr, false)},
        {expected_thunks[6].name, task_queue_create(XTaskQueueDispatchMode::Manual,
                                                    XTaskQueueDispatchMode::Manual, nullptr)},
    }};
    for (const auto& call : calls) {
        if (call.result != not_implemented) {
            std::printf("FAIL: %s returned 0x%08lx, expected E_NOTIMPL\n", call.name,
                        static_cast<unsigned long>(call.result));
            return false;
        }
    }
    return true;
}

bool log_matches_calls(HMODULE module)
{
    GetLog get_log = nullptr;
    ClearLog clear_log = nullptr;
    if (!find_proc(module, "XGameRuntimeShimGetLog", get_log) ||
        !find_proc(module, "XGameRuntimeShimClearLog", clear_log)) {
        return false;
    }

    clear_log();
    if (get_log(nullptr, 0) != 0) {
        std::printf("FAIL: log was not empty after clear\n");
        return false;
    }
    if (!calls_return_not_implemented(module)) return false;

    std::array<XGameRuntimeShimLogEntry, expected_thunks.size()> entries{};
    const std::size_t total = get_log(entries.data(), entries.size());
    if (total != entries.size()) {
        std::printf("FAIL: log has %zu entries, expected %zu\n", total, entries.size());
        return false;
    }
    for (std::size_t i = 0; i < entries.size(); ++i) {
        const auto& entry = entries[i];
        if (entry.sequence != i + 1) {
            std::printf("FAIL: log entry %zu has sequence %lu\n", i,
                        static_cast<unsigned long>(entry.sequence));
            return false;
        }
        if (entry.result != not_implemented) {
            std::printf("FAIL: log entry %zu has result 0x%08lx\n", i,
                        static_cast<unsigned long>(entry.result));
            return false;
        }
        if (!entry.component || std::strcmp(entry.component, expected_thunks[i].component) != 0 ||
            !entry.function || std::strcmp(entry.function, expected_thunks[i].function) != 0) {
            std::printf("FAIL: log entry %zu is %s/%s, expected %s/%s\n", i,
                        entry.component ? entry.component : "(null)",
                        entry.function ? entry.function : "(null)", expected_thunks[i].component,
                        expected_thunks[i].function);
            return false;
        }
    }
    return true;
}

bool unknown_export_is_missing(HMODULE module)
{
    constexpr const char* unknown_name = "XGameRuntimeShimExportThatMustNotExist";
    if (GetProcAddress(module, unknown_name) != nullptr) {
        std::printf("FAIL: unknown export %s unexpectedly resolved\n", unknown_name);
        return false;
    }
    return true;
}

bool run_checks(const wchar_t* dll_path)
{
    LoadedShim shim;
    shim.module = LoadLibraryW(dll_path);
    if (!shim.module) {
        std::printf("FAIL: LoadLibraryW(%ls) error=%lu\n", dll_path, GetLastError());
        return false;
    }
    return export_names_are_unique() && unknown_export_is_missing(shim.module) &&
           log_matches_calls(shim.module);
}
}  // namespace

int wmain(int argc, wchar_t** argv)
{
    if (argc != 2) {
        std::printf("usage: xgameruntime_shim_check <xgameruntime.dll>\n");
        return 2;
    }
    const bool passed = run_checks(argv[1]);
    std::printf("Desktop xgameruntime.dll: exports=%zu calls=%zu unknown_export=null log=%zu %s\n",
                expected_thunks.size(), expected_thunks.size(), expected_thunks.size(),
                passed ? "PASS" : "FAIL");
    return passed ? 0 : 1;
}
