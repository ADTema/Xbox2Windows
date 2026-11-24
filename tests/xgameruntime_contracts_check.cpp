// Synthetic title-level check for the implemented synchronous XUser and
// XGameSave subset. The DLL is loaded from its explicit fixture path; the
// negative controls call XPackage/XGame stubs and must remain E_NOTIMPL.
#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <cwchar>
#include <filesystem>
#include <iterator>

#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>

namespace {
namespace fs = std::filesystem;

constexpr HRESULT not_implemented = static_cast<HRESULT>(0x80004001L);
constexpr std::uint64_t synthetic_user_id = 0x0009000000000001ull;

struct XAsyncBlock;
namespace xgameruntime_shim {
struct XUserHandleStorage;
struct XGameSaveProviderStorage;
struct XGameSaveContainerStorage;
struct XGameSaveUpdateStorage;
}
using XUserHandle = xgameruntime_shim::XUserHandleStorage*;
using XGameSaveProviderHandle = xgameruntime_shim::XGameSaveProviderStorage*;
using XGameSaveContainerHandle = xgameruntime_shim::XGameSaveContainerStorage*;
using XGameSaveUpdateHandle = xgameruntime_shim::XGameSaveUpdateStorage*;

struct XGameSaveBlobInfo {
    const char* name;
    std::uint32_t size;
};

struct XGameSaveBlob {
    XGameSaveBlobInfo info;
    std::uint8_t* data;
};

struct XGameRuntimeShimLogEntry {
    std::uint32_t sequence;
    HRESULT result;
    const char* component;
    const char* function;
};

using FindUserById = HRESULT(WINAPI*)(std::uint64_t, XUserHandle*);
using GetUserId = HRESULT(WINAPI*)(XUserHandle, std::uint64_t*);
using DuplicateUserHandle = HRESULT(WINAPI*)(XUserHandle, XUserHandle*);
using CloseUserHandle = void(WINAPI*)(XUserHandle);
using InitializeProvider = HRESULT(WINAPI*)(XUserHandle, const char*, bool,
                                            XGameSaveProviderHandle*);
using CreateContainer = HRESULT(WINAPI*)(XGameSaveProviderHandle, const char*,
                                        XGameSaveContainerHandle*);
using CreateUpdate = HRESULT(WINAPI*)(XGameSaveContainerHandle, const char*,
                                      XGameSaveUpdateHandle*);
using SubmitBlobWrite = HRESULT(WINAPI*)(XGameSaveUpdateHandle, const char*,
                                        const std::uint8_t*, std::size_t);
using SubmitUpdate = HRESULT(WINAPI*)(XGameSaveUpdateHandle);
using ReadBlobData = HRESULT(WINAPI*)(XGameSaveContainerHandle, const char**,
                                      std::uint32_t*, std::size_t, XGameSaveBlob*);
using CloseProvider = void(WINAPI*)(XGameSaveProviderHandle);
using CloseContainer = void(WINAPI*)(XGameSaveContainerHandle);
using CloseUpdate = void(WINAPI*)(XGameSaveUpdateHandle);
using PackageMount = HRESULT(WINAPI*)(const char*, XAsyncBlock*);
using GameGetXboxTitleId = HRESULT(WINAPI*)(std::uint32_t*);
using GetLog = std::size_t(WINAPI*)(XGameRuntimeShimLogEntry*, std::size_t);
using ClearLog = void(WINAPI*)();

fs::path normalized_path(const fs::path& path)
{
    std::error_code error;
    const auto canonical = fs::weakly_canonical(path, error);
    return error ? fs::absolute(path).lexically_normal() : canonical;
}

bool same_path(const fs::path& left, const fs::path& right)
{
    return _wcsicmp(normalized_path(left).c_str(), normalized_path(right).c_str()) == 0;
}

bool fixture_path_checks(const wchar_t* dll_path, const wchar_t* fixture_dir,
                         const wchar_t* normal_shim_dir)
{
    const fs::path dll = dll_path;
    const fs::path fixture = fixture_dir;
    const fs::path normal = normal_shim_dir;
    if (dll.filename() != L"xgameruntime.dll" || !same_path(dll.parent_path(), fixture)) {
        std::printf("FAIL: DLL is not at its fixture path %ls\n", fixture.c_str());
        return false;
    }
    if (fs::exists(normal / L"xgameruntime.dll")) {
        std::printf("FAIL: normal shim directory contains xgameruntime.dll\n");
        return false;
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
        std::printf("FAIL: export %s is not owned by the fixture DLL\n", name);
        return false;
    }
    proc = reinterpret_cast<Proc>(found);
    return true;
}

bool contract_checks(HMODULE module)
{
    FindUserById find_user = nullptr;
    GetUserId get_user_id = nullptr;
    DuplicateUserHandle duplicate_user = nullptr;
    CloseUserHandle close_user = nullptr;
    InitializeProvider initialize_provider = nullptr;
    CreateContainer create_container = nullptr;
    CreateUpdate create_update = nullptr;
    SubmitBlobWrite submit_blob_write = nullptr;
    SubmitUpdate submit_update = nullptr;
    ReadBlobData read_blob_data = nullptr;
    CloseProvider close_provider = nullptr;
    CloseContainer close_container = nullptr;
    CloseUpdate close_update = nullptr;
    PackageMount package_mount = nullptr;
    GameGetXboxTitleId game_get_title_id = nullptr;

    if (!find_proc(module, "XUserFindUserById", find_user) ||
        !find_proc(module, "XUserGetId", get_user_id) ||
        !find_proc(module, "XUserDuplicateHandle", duplicate_user) ||
        !find_proc(module, "XUserCloseHandle", close_user) ||
        !find_proc(module, "XGameSaveInitializeProvider", initialize_provider) ||
        !find_proc(module, "XGameSaveCreateContainer", create_container) ||
        !find_proc(module, "XGameSaveCreateUpdate", create_update) ||
        !find_proc(module, "XGameSaveSubmitBlobWrite", submit_blob_write) ||
        !find_proc(module, "XGameSaveSubmitUpdate", submit_update) ||
        !find_proc(module, "XGameSaveReadBlobData", read_blob_data) ||
        !find_proc(module, "XGameSaveCloseProvider", close_provider) ||
        !find_proc(module, "XGameSaveCloseContainer", close_container) ||
        !find_proc(module, "XGameSaveCloseUpdate", close_update) ||
        !find_proc(module, "XPackageMountWithUiAsync", package_mount) ||
        !find_proc(module, "XGameGetXboxTitleId", game_get_title_id)) {
        return false;
    }

    XUserHandle user = nullptr;
    XUserHandle duplicate = nullptr;
    std::uint64_t user_id = 0;
    if (FAILED(find_user(synthetic_user_id, &user)) || !user ||
        FAILED(get_user_id(user, &user_id)) || user_id != synthetic_user_id ||
        FAILED(duplicate_user(user, &duplicate)) || !duplicate ||
        FAILED(get_user_id(duplicate, &user_id)) || user_id != synthetic_user_id) {
        std::printf("FAIL: XUser identity or handle lifecycle\n");
        return false;
    }
    close_user(duplicate);

    XGameSaveProviderHandle provider = nullptr;
    XGameSaveContainerHandle container = nullptr;
    XGameSaveUpdateHandle update = nullptr;
    constexpr char configuration_id[] = "synthetic-scid";
    constexpr char container_name[] = "slot";
    constexpr char blob_name[] = "save.bin";
    constexpr std::uint8_t payload[] = {0x10, 0x20, 0x30, 0x40, 0x50, 0x60};
    if (FAILED(initialize_provider(user, configuration_id, false, &provider)) || !provider ||
        FAILED(create_container(provider, container_name, &container)) || !container ||
        FAILED(create_update(container, container_name, &update)) || !update ||
        FAILED(submit_blob_write(update, blob_name, payload, sizeof(payload))) ||
        FAILED(submit_update(update))) {
        std::printf("FAIL: XGameSave initialize or write contract\n");
        return false;
    }

    alignas(XGameSaveBlob) std::uint8_t storage[512]{};
    auto* blobs = reinterpret_cast<XGameSaveBlob*>(storage);
    const char* blob_names[] = {blob_name};
    std::uint32_t count = 1;
    if (FAILED(read_blob_data(container, blob_names, &count, sizeof(storage), blobs)) ||
        count != 1 || !blobs[0].info.name || std::strcmp(blobs[0].info.name, blob_name) != 0 ||
        blobs[0].info.size != sizeof(payload) || !blobs[0].data ||
        std::memcmp(blobs[0].data, payload, sizeof(payload)) != 0) {
        std::printf("FAIL: XGameSave read contract\n");
        return false;
    }
    close_update(update);
    close_container(container);
    close_provider(provider);
    close_user(user);

    // The negative controls stay logged stubs, not implemented contracts.
    if (package_mount(nullptr, nullptr) != not_implemented ||
        game_get_title_id(nullptr) != not_implemented) {
        std::printf("FAIL: negative stub result\n");
        return false;
    }
    return true;
}

bool log_checks(HMODULE module, std::size_t expected_calls)
{
    GetLog get_log = nullptr;
    ClearLog clear_log = nullptr;
    if (!find_proc(module, "XGameRuntimeShimGetLog", get_log) ||
        !find_proc(module, "XGameRuntimeShimClearLog", clear_log)) {
        return false;
    }
    std::array<XGameRuntimeShimLogEntry, 32> entries{};
    const std::size_t count = get_log(entries.data(), entries.size());
    if (count != expected_calls) {
        std::printf("FAIL: log has %zu entries, expected %zu\n", count, expected_calls);
        return false;
    }
    bool saw_user = false;
    bool saw_save = false;
    bool saw_package = false;
    bool saw_game = false;
    constexpr const char* implemented_names[] = {
        "XUserFindUserById", "XUserGetId", "XUserDuplicateHandle", "XUserCloseHandle",
        "XGameSaveInitializeProvider", "XGameSaveCreateContainer", "XGameSaveCreateUpdate",
        "XGameSaveSubmitBlobWrite", "XGameSaveSubmitUpdate", "XGameSaveReadBlobData",
        "XGameSaveCloseProvider", "XGameSaveCloseContainer", "XGameSaveCloseUpdate"};
    std::array<bool, std::size(implemented_names)> implemented_seen{};
    for (std::size_t i = 0; i < count; ++i) {
        const auto& entry = entries[i];
        if (!entry.component || !entry.function) return false;
        const bool user_component = std::strcmp(entry.component, "XUser") == 0;
        const bool save_component = std::strcmp(entry.component, "XGameSave") == 0;
        if ((user_component || save_component) && entry.result == not_implemented) {
            std::printf("FAIL: implemented contract logged E_NOTIMPL: %s\n", entry.function);
            return false;
        }
        if (user_component) saw_user = true;
        if (save_component) saw_save = true;
        if (std::strcmp(entry.function, "XPackageMountWithUiAsync") == 0) {
            saw_package = entry.result == not_implemented;
        }
        if (std::strcmp(entry.function, "XGameGetXboxTitleId") == 0) {
            saw_game = entry.result == not_implemented;
        }
        for (std::size_t j = 0; j < std::size(implemented_names); ++j) {
            if (std::strcmp(entry.function, implemented_names[j]) == 0) {
                if (entry.result == not_implemented) {
                    std::printf("FAIL: implemented name logged E_NOTIMPL: %s\n", entry.function);
                    return false;
                }
                implemented_seen[j] = true;
            }
        }
    }
    if (!saw_user || !saw_save || !saw_package || !saw_game ||
        std::find(implemented_seen.begin(), implemented_seen.end(), false) != implemented_seen.end()) {
        std::printf("FAIL: log does not contain positive and negative controls\n");
        return false;
    }
    return true;
}

bool run(const wchar_t* dll_path, const wchar_t* fixture_dir, const wchar_t* normal_shim_dir)
{
    if (!fixture_path_checks(dll_path, fixture_dir, normal_shim_dir)) return false;
    HMODULE module = LoadLibraryW(dll_path);
    if (!module) {
        std::printf("FAIL: LoadLibraryW(%ls) error=%lu\n", dll_path, GetLastError());
        return false;
    }
    ClearLog clear_log = nullptr;
    const bool has_log = find_proc(module, "XGameRuntimeShimClearLog", clear_log);
    if (has_log) clear_log();
    const bool passed = has_log && contract_checks(module) && log_checks(module, 17);
    FreeLibrary(module);
    return passed;
}
}  // namespace

int wmain(int argc, wchar_t** argv)
{
    if (argc != 4) {
        std::printf("usage: xgameruntime_contracts_check <dll> <fixture-dir> <normal-shim-dir>\n");
        return 2;
    }
    const bool passed = run(argv[1], argv[2], argv[3]);
    std::printf("xgameruntime contracts: user=implemented game-save=implemented "
                "negative=E_NOTIMPL x2 %s\n", passed ? "PASS" : "FAIL");
    return passed ? 0 : 1;
}
