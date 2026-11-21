#include <d3d12.h>
#include <dxgi1_6.h>
#include <wrl/client.h>
#include <fcntl.h>
#include <io.h>
#include <cstdio>
#include <iostream>
#include <iterator>
#include <string_view>
#include <vector>
using Microsoft::WRL::ComPtr;

int main(int argc, char** argv)
{
    const bool warpOnly = argc == 2 && std::string_view(argv[1]) == "--warp-only";
    if (argc != 1 && !warpOnly) return 1;
    _setmode(_fileno(stdin), _O_BINARY);
    std::vector<char> input{std::istreambuf_iterator<char>(std::cin), {}};
    ComPtr<ID3D12VersionedRootSignatureDeserializer> reader;
    if (input.empty() || FAILED(D3D12CreateVersionedRootSignatureDeserializer(
        input.data(), input.size(), IID_PPV_ARGS(&reader)))) return 2;
    const auto* source = reader->GetUnconvertedRootSignatureDesc();
    if (!source || source->Version != D3D_ROOT_SIGNATURE_VERSION_1_1) return 3;

    ComPtr<IDXGIFactory6> factory;
    ComPtr<IDXGIAdapter1> hardware, warp;
    if (FAILED(CreateDXGIFactory2(0, IID_PPV_ARGS(&factory))) ||
        FAILED(factory->EnumWarpAdapter(IID_PPV_ARGS(&warp)))) return 4;
    DXGI_ADAPTER_DESC1 adapter{};
    ComPtr<ID3D12Device> gpuDevice, warpDevice;
    if (!warpOnly) {
        for (UINT index = 0; ; ++index) {
            if (FAILED(factory->EnumAdapterByGpuPreference(index, DXGI_GPU_PREFERENCE_HIGH_PERFORMANCE,
                    IID_PPV_ARGS(hardware.ReleaseAndGetAddressOf())))) {
                std::fputs("No compatible hardware adapter. Use --warp-only for WARP.\n", stderr);
                return 5;
            }
            if (FAILED(hardware->GetDesc1(&adapter))) return 5;
            if (!(adapter.Flags & DXGI_ADAPTER_FLAG_SOFTWARE) &&
                SUCCEEDED(D3D12CreateDevice(hardware.Get(), D3D_FEATURE_LEVEL_11_0, IID_PPV_ARGS(&gpuDevice)))) break;
        }
    }
    if (FAILED(D3D12CreateDevice(warp.Get(), D3D_FEATURE_LEVEL_11_0, IID_PPV_ARGS(&warpDevice)))) return 6;

    constexpr unsigned observed = 0x03000000;
    unsigned original = source->Desc_1_1.Flags;
    for (unsigned clear : {0u, 0x01000000u, 0x02000000u, observed}) {
        if (clear & ~original) continue;
        auto descriptor = *source;
        descriptor.Desc_1_1.Flags = static_cast<D3D12_ROOT_SIGNATURE_FLAGS>(original & ~clear);
        ComPtr<ID3DBlob> serialized;
        HRESULT serialize = D3D12SerializeVersionedRootSignature(&descriptor, &serialized, nullptr);
        std::printf("{\"remaining_flags\":%u,\"cleared\":%u,\"serialize\":\"0x%08lx\"",
                    original & ~clear, clear, static_cast<unsigned long>(serialize));
        if (gpuDevice) std::printf(",\"adapter_id\":\"%04x:%04x\"", adapter.VendorId, adapter.DeviceId);
        if (SUCCEEDED(serialize)) {
            for (auto* device : {gpuDevice.Get(), warpDevice.Get()}) {
                if (!device) continue;
                ComPtr<ID3D12RootSignature> root;
                HRESULT hr = device->CreateRootSignature(0, serialized->GetBufferPointer(),
                    serialized->GetBufferSize(), IID_PPV_ARGS(&root));
                std::printf(",\"%s\":\"0x%08lx\"", device == gpuDevice.Get() ? "hardware" : "warp",
                            static_cast<unsigned long>(hr));
            }
        }
        std::puts("}");
    }
}
