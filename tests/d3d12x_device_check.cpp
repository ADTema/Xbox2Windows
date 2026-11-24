// Loads the built d3d12_xs.dll by explicit path and calls its exported device creation entry.
// The fixture is source-built and does not load or inspect a title.
#include <windows.h>
#include <d3d12.h>
#include <dxgi1_6.h>
#include <wrl/client.h>

#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <cwchar>
#include <string>
#include <string_view>

using Microsoft::WRL::ComPtr;

namespace {

using XboxCreateDevice = HRESULT(WINAPI*)(IUnknown*, const void*, REFIID, void**);

constexpr GUID unknown_iid = {0x7c0e1a10, 0x5f2d, 0x4b7a,
                              {0x9a, 0x51, 0x3d, 0x9c, 0x6b, 0x2e, 0x8f, 0x01}};

struct AdapterChoice {
    ComPtr<IDXGIFactory6> factory;
    ComPtr<IDXGIAdapter1> adapter;
    DXGI_ADAPTER_DESC1 desc{};
};

bool contains_ignoring_case(const wchar_t* text, const wchar_t* part)
{
    const std::size_t length = std::wcslen(part);
    for (; *text; ++text) {
        if (_wcsnicmp(text, part, length) == 0) return true;
    }
    return false;
}

// Same selection convention as the existing D3D12 fixtures: WARP on request, otherwise the first
// non-software adapter in high-performance order. XBOX2WINDOWS_ADAPTER filters by description.
int select_adapter(bool warp, AdapterChoice& choice)
{
    HRESULT hr = CreateDXGIFactory2(0, IID_PPV_ARGS(&choice.factory));
    if (FAILED(hr)) {
        std::fprintf(stderr, "CreateDXGIFactory2 failed: 0x%08lx\n", static_cast<unsigned long>(hr));
        return 1;
    }
    if (warp) {
        hr = choice.factory->EnumWarpAdapter(IID_PPV_ARGS(&choice.adapter));
        if (FAILED(hr) || !choice.adapter) {
            std::fprintf(stderr, "WARP adapter unavailable: 0x%08lx\n", static_cast<unsigned long>(hr));
            return 1;
        }
        hr = choice.adapter->GetDesc1(&choice.desc);
        if (FAILED(hr)) {
            std::fprintf(stderr, "WARP adapter description failed: 0x%08lx\n", static_cast<unsigned long>(hr));
            return 1;
        }
        return 0;
    }

    wchar_t wanted[128]{};
    const DWORD filter = GetEnvironmentVariableW(L"XBOX2WINDOWS_ADAPTER", wanted, 128);
    if (filter >= 128) {
        std::fputs("XBOX2WINDOWS_ADAPTER is longer than 127 characters\n", stderr);
        return 1;
    }
    for (UINT index = 0;; ++index) {
        hr = choice.factory->EnumAdapterByGpuPreference(
            index, DXGI_GPU_PREFERENCE_HIGH_PERFORMANCE, IID_PPV_ARGS(choice.adapter.ReleaseAndGetAddressOf()));
        if (hr == DXGI_ERROR_NOT_FOUND) {
            if (filter) {
                std::fprintf(stderr, "No D3D12 hardware adapter matches XBOX2WINDOWS_ADAPTER=%ls\n", wanted);
                return 1;
            }
            std::fputs("No physical D3D12 adapter available\n", stderr);
            return 77;
        }
        if (FAILED(hr)) {
            std::fprintf(stderr, "EnumAdapterByGpuPreference failed: 0x%08lx\n", static_cast<unsigned long>(hr));
            return 1;
        }
        hr = choice.adapter->GetDesc1(&choice.desc);
        if (FAILED(hr)) {
            std::fprintf(stderr, "GetDesc1 failed: 0x%08lx\n", static_cast<unsigned long>(hr));
            return 1;
        }
        if (choice.desc.Flags & DXGI_ADAPTER_FLAG_SOFTWARE) continue;
        if (filter && !contains_ignoring_case(choice.desc.Description, wanted)) {
            std::fprintf(stderr, "XBOX2WINDOWS_ADAPTER: skipping %ls\n", choice.desc.Description);
            continue;
        }
        return 0;
    }
}

bool enable_debug_layer()
{
    ComPtr<ID3D12Debug> debug;
    if (FAILED(D3D12GetDebugInterface(IID_PPV_ARGS(&debug))) || !debug) return false;
    debug->EnableDebugLayer();
    return true;
}

void print_environment(const AdapterChoice& choice, bool warp, bool debug)
{
    std::printf("backend=%s adapter=%ls vendor=%04x device=%04x\n", warp ? "warp" : "hardware",
                choice.desc.Description, choice.desc.VendorId, choice.desc.DeviceId);
    LARGE_INTEGER driver{};
    if (SUCCEEDED(choice.adapter->CheckInterfaceSupport(__uuidof(IDXGIDevice), &driver))) {
        std::printf("driver=%u.%u.%u.%u\n", HIWORD(driver.HighPart), LOWORD(driver.HighPart),
                    HIWORD(driver.LowPart), LOWORD(driver.LowPart));
    } else {
        std::puts("driver=unavailable via DXGI");
    }
    using RtlGetVersionFn = LONG(WINAPI*)(OSVERSIONINFOW*);
    const auto rtl_get_version = reinterpret_cast<RtlGetVersionFn>(
        GetProcAddress(GetModuleHandleW(L"ntdll.dll"), "RtlGetVersion"));
    OSVERSIONINFOW os{};
    os.dwOSVersionInfoSize = sizeof(os);
    if (rtl_get_version && rtl_get_version(&os) == 0) {
        std::printf("windows=%lu.%lu.%lu\n", os.dwMajorVersion, os.dwMinorVersion, os.dwBuildNumber);
    } else {
        std::puts("windows=unavailable");
    }
    std::printf("debug_layer=%s\n", debug ? "enabled" : "unavailable");
}

HMODULE load_shim(const char* path, XboxCreateDevice& create)
{
    const int length = MultiByteToWideChar(CP_ACP, 0, path, -1, nullptr, 0);
    if (length <= 0) {
        std::fputs("Cannot convert the d3d12_xs.dll path\n", stderr);
        return nullptr;
    }
    std::wstring wide(static_cast<std::size_t>(length), L'\0');
    if (!MultiByteToWideChar(CP_ACP, 0, path, -1, wide.data(), length)) {
        std::fputs("Cannot convert the d3d12_xs.dll path\n", stderr);
        return nullptr;
    }
    HMODULE module = LoadLibraryExW(wide.c_str(), nullptr,
                                    LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR | LOAD_LIBRARY_SEARCH_SYSTEM32);
    if (!module) {
        std::fprintf(stderr, "LoadLibraryExW(%ls) failed: %lu\n", wide.c_str(),
                     static_cast<unsigned long>(GetLastError()));
        return nullptr;
    }
    create = reinterpret_cast<XboxCreateDevice>(GetProcAddress(module, "D3D12XboxCreateDevice"));
    if (!create) {
        std::fputs("d3d12_xs.dll does not export D3D12XboxCreateDevice\n", stderr);
        FreeLibrary(module);
        return nullptr;
    }
    HMODULE owner = nullptr;
    if (!GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                            reinterpret_cast<LPCWSTR>(create), &owner) ||
        owner != module) {
        std::fputs("D3D12XboxCreateDevice does not resolve inside d3d12_xs.dll\n", stderr);
        FreeLibrary(module);
        return nullptr;
    }
    return module;
}

int create_checks(XboxCreateDevice create, IUnknown* adapter, const LUID& expected_luid)
{
    void* raw = nullptr;
    const HRESULT hr = create(adapter, nullptr, __uuidof(ID3D12Device), &raw);
    if (hr != S_OK || !raw) {
        std::fprintf(stderr, "D3D12XboxCreateDevice create failed: 0x%08lx\n",
                     static_cast<unsigned long>(hr));
        return 1;
    }
    ComPtr<ID3D12Device> device;
    device.Attach(static_cast<ID3D12Device*>(raw));

    const LUID actual_luid = device->GetAdapterLuid();
    if (actual_luid.LowPart != expected_luid.LowPart || actual_luid.HighPart != expected_luid.HighPart) {
        std::fprintf(stderr, "device LUID {%08lx:%08lx} does not match adapter {%08lx:%08lx}\n",
                     static_cast<unsigned long>(actual_luid.HighPart),
                     static_cast<unsigned long>(actual_luid.LowPart),
                     static_cast<unsigned long>(expected_luid.HighPart),
                     static_cast<unsigned long>(expected_luid.LowPart));
        return 1;
    }
    if (device->GetNodeCount() != 1) {
        std::fprintf(stderr, "GetNodeCount returned %u\n", device->GetNodeCount());
        return 1;
    }
    ComPtr<ID3D12Fence> fence;
    const HRESULT fence_hr = device->CreateFence(0, D3D12_FENCE_FLAG_NONE, IID_PPV_ARGS(&fence));
    if (fence_hr != S_OK || !fence || fence->GetCompletedValue() != 0) {
        std::fprintf(stderr, "CreateFence failed: 0x%08lx\n", static_cast<unsigned long>(fence_hr));
        return 1;
    }
    std::printf("device_create=S_OK node_count=1 fence=S_OK luid={%08lx:%08lx}\n",
                static_cast<unsigned long>(actual_luid.HighPart),
                static_cast<unsigned long>(actual_luid.LowPart));
    return 0;
}

int negative_checks(XboxCreateDevice create, IUnknown* adapter)
{
    HRESULT hr = create(adapter, nullptr, __uuidof(ID3D12Device), nullptr);
    if (hr != E_POINTER) {
        std::fprintf(stderr, "null device output: hr=0x%08lx\n", static_cast<unsigned long>(hr));
        return 1;
    }

    const std::uint32_t parameters[16]{};
    void* device = reinterpret_cast<void*>(static_cast<std::uintptr_t>(0x1234));
    hr = create(adapter, parameters, __uuidof(ID3D12Device), &device);
    if (hr != E_INVALIDARG || device) {
        std::fprintf(stderr, "parameter block: hr=0x%08lx output=%p\n",
                     static_cast<unsigned long>(hr), device);
        return 1;
    }

    device = reinterpret_cast<void*>(static_cast<std::uintptr_t>(0x1234));
    hr = create(adapter, nullptr, unknown_iid, &device);
    if (hr != E_NOINTERFACE || device) {
        std::fprintf(stderr, "unknown IID: hr=0x%08lx output=%p\n",
                     static_cast<unsigned long>(hr), device);
        return 1;
    }
    std::puts("null_device=E_POINTER unknown_iid=0x80004002 output=null");
    return 0;
}

}  // namespace

int main(int argc, char** argv)
{
    if (argc != 4) {
        std::fprintf(stderr, "usage: %s <path-to-d3d12_xs.dll> <create|negative> <warp|hardware>\n",
                     argv[0]);
        return 2;
    }
    const std::string_view scenario = argv[2];
    const std::string_view backend = argv[3];
    if ((scenario != "create" && scenario != "negative") ||
        (backend != "warp" && backend != "hardware")) {
        std::fputs("unknown scenario or backend\n", stderr);
        return 2;
    }
    const bool warp = backend == "warp";

    XboxCreateDevice create = nullptr;
    HMODULE shim = load_shim(argv[1], create);
    if (!shim) return 1;

    AdapterChoice choice;
    const int selected = select_adapter(warp, choice);
    if (selected) {
        FreeLibrary(shim);
        return selected;
    }
    const bool debug = enable_debug_layer();
    print_environment(choice, warp, debug);

    const int result = scenario == "create"
                           ? create_checks(create, choice.adapter.Get(), choice.desc.AdapterLuid)
                           : negative_checks(create, choice.adapter.Get());
    FreeLibrary(shim);
    std::printf("d3d12x_device_check %s %s: %s\n", argv[2], argv[3], result == 0 ? "PASS" : "FAIL");
    return result;
}
