// Shared WARP/hardware device selection for the shim-draw providers.
// Both providers honor X2W_SHIM_DRAW_ADAPTER (warp default, hardware opts in,
// anything else is a hard error); hardware probing exits 77 when no physical
// D3D12 adapter exists so CTest records a capability skip.
#pragma once
#include <d3d12.h>
#include <dxgi1_6.h>
#include <wrl/client.h>

#include <cstdio>
#include <cstring>

inline void shim_require(HRESULT hr, const char* operation)
{
    if (FAILED(hr)) {
        std::fprintf(stderr, "%s failed (HRESULT 0x%08lx)\n", operation, static_cast<unsigned long>(hr));
        throw hr;
    }
}

inline Microsoft::WRL::ComPtr<ID3D12Device> shim_create_device()
{
    using Microsoft::WRL::ComPtr;
    ComPtr<IDXGIFactory6> factory;
    shim_require(CreateDXGIFactory2(0, IID_PPV_ARGS(&factory)), "CreateDXGIFactory2");
    ComPtr<IDXGIAdapter1> adapter;
    char backend[16]{};
    const auto size = GetEnvironmentVariableA("X2W_SHIM_DRAW_ADAPTER", backend, sizeof(backend));
    if (!size || (size < sizeof(backend) && std::strcmp(backend, "warp") == 0)) {
        shim_require(factory->EnumWarpAdapter(IID_PPV_ARGS(&adapter)), "EnumWarpAdapter");
    } else if (size < sizeof(backend) && std::strcmp(backend, "hardware") == 0) {
        for (UINT i = 0;; ++i) {
            const HRESULT hr = factory->EnumAdapterByGpuPreference(i, DXGI_GPU_PREFERENCE_HIGH_PERFORMANCE,
                                                                   IID_PPV_ARGS(&adapter));
            if (hr == DXGI_ERROR_NOT_FOUND) {
                std::fputs("no D3D12 physical adapter\n", stderr);
                ExitProcess(77);
            }
            shim_require(hr, "EnumAdapterByGpuPreference");
            DXGI_ADAPTER_DESC1 desc{};
            shim_require(adapter->GetDesc1(&desc), "GetDesc1");
            if (!(desc.Flags & DXGI_ADAPTER_FLAG_SOFTWARE)) {
                const HRESULT support = D3D12CreateDevice(adapter.Get(), D3D_FEATURE_LEVEL_11_0,
                                                          __uuidof(ID3D12Device), nullptr);
                if (support != DXGI_ERROR_UNSUPPORTED) {
                    shim_require(support, "Probe physical device");
                    break;
                }
            }
            adapter.Reset();
        }
    } else {
        shim_require(E_INVALIDARG, "Select draw adapter");
    }
    ComPtr<ID3D12Device> device;
    shim_require(D3D12CreateDevice(adapter.Get(), D3D_FEATURE_LEVEL_11_0, IID_PPV_ARGS(&device)),
                 "D3D12CreateDevice");
    return device;
}
