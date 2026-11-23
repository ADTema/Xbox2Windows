// Desktop d3d12_xs.dll exporting the two root-signature functions the package DLLs import by name.
// Observed call sites (docs/experiments.md):
//   D3D12SerializeVersionedRootSignature: XboxBvhBuilder.dll (0xc2d0/0xc32f) copies a 48-byte
//     descriptor, sets console flag bits 0x03000000 at +0x28, and passes a null error output.
//   D3D12CreateRootSignatureDeserializer: amd_fidelityfx_upscaler_xbox.dll (0x4f88) reads a
//     serialized root signature from an embedded container and retrieves the descriptor interface.
// The main executable also imports D3D12XboxCreateDevice and D3D12ConfigureVirtualMemoryX (#874).
#include "d3d12_xs_range.h"

#include <d3d12.h>
#include <dxgi.h>
#include <wrl/client.h>

#include <algorithm>
#include <atomic>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <new>
#include <vector>

namespace {
// Observed console root-signature flag bits set by XboxBvhBuilder.dll.
// Unobserved bits are left untouched so desktop d3d12.dll still rejects unknown flags.
constexpr std::uint32_t observed_console_flags = 0x03000000u;

static_assert(offsetof(D3D12_VERSIONED_ROOT_SIGNATURE_DESC, Desc_1_0) +
              offsetof(D3D12_ROOT_SIGNATURE_DESC, Flags) == 0x28);
static_assert(offsetof(D3D12_VERSIONED_ROOT_SIGNATURE_DESC, Desc_1_1) +
              offsetof(D3D12_ROOT_SIGNATURE_DESC1, Flags) == 0x28);

// The observed caller zero-fills a 32-byte block, sets only the DWORD at +4 to 3 or 4, and
// configures once per process before it creates the device. The DWORD's meaning is open.
constexpr std::size_t vm_config_bytes = 32;
constexpr std::size_t vm_config_value = 4;
// The caller computes the value as ceil(size / 16 GiB) + 2, so (value - 2) * 16 GiB covers its range
// (16 GiB for 3, 24 GiB rounded up to 32 GiB for 4). Reserved address space has no backing.
constexpr UINT64 vm_range_unit = UINT64{16} << 30;
constexpr UINT64 tile_bytes = UINT64{64} << 10;
// Adapters tested in #874 lose tile mappings at or above 4 GiB inside one reserved buffer.
constexpr UINT64 max_window_bytes = UINT64{4} << 30;

// Configuration and device creation are serialized. `value` is the accepted DWORD, 0 for none.
struct VmState {
    SRWLOCK lock = SRWLOCK_INIT;
    std::uint32_t value = 0;
    bool device_created = false;
};
VmState vm_state;

class GpuRange final : public IX2WGpuRange {
public:
    HRESULT reserve(ID3D12Device* device, UINT64 size) noexcept
    {
        D3D12_FEATURE_DATA_GPU_VIRTUAL_ADDRESS_SUPPORT va{};
        HRESULT hr = device->CheckFeatureSupport(D3D12_FEATURE_GPU_VIRTUAL_ADDRESS_SUPPORT, &va, sizeof(va));
        if (FAILED(hr)) return hr;
        if (va.MaxGPUVirtualAddressBitsPerResource < 17) return E_FAIL;
        // Below 4 GiB, the largest whole number of tiles a resource of this adapter can span.
        const UINT64 per_resource = va.MaxGPUVirtualAddressBitsPerResource >= 64
                                        ? max_window_bytes
                                        : (UINT64{1} << va.MaxGPUVirtualAddressBitsPerResource) - tile_bytes;
        window_ = std::min(max_window_bytes, per_resource) & ~(tile_bytes - 1);
        size_ = size;
        const UINT64 count = (size + window_ - 1) / window_;
        try {
            windows_.reserve(static_cast<std::size_t>(count));
        } catch (const std::bad_alloc&) {
            return E_OUTOFMEMORY;
        }
        for (UINT64 i = 0; i < count; ++i) {
            D3D12_RESOURCE_DESC desc{};
            desc.Dimension = D3D12_RESOURCE_DIMENSION_BUFFER;
            desc.Width = std::min(window_, size - i * window_);
            desc.Height = 1;
            desc.DepthOrArraySize = 1;
            desc.MipLevels = 1;
            desc.SampleDesc.Count = 1;
            desc.Layout = D3D12_TEXTURE_LAYOUT_ROW_MAJOR;
            desc.Flags = D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS;
            Microsoft::WRL::ComPtr<ID3D12Resource> window;
            hr = device->CreateReservedResource(&desc, D3D12_RESOURCE_STATE_COMMON, nullptr, IID_PPV_ARGS(&window));
            if (FAILED(hr)) return hr;
            windows_.push_back(std::move(window));  // capacity reserved above
        }
        return S_OK;
    }

    HRESULT STDMETHODCALLTYPE QueryInterface(REFIID iid, void** out) override
    {
        if (!out) return E_POINTER;
        *out = nullptr;
        if (iid != __uuidof(IUnknown) && iid != __uuidof(IX2WGpuRange)) return E_NOINTERFACE;
        *out = static_cast<IX2WGpuRange*>(this);
        AddRef();
        return S_OK;
    }
    ULONG STDMETHODCALLTYPE AddRef() override { return ++refs_; }
    ULONG STDMETHODCALLTYPE Release() override
    {
        const ULONG left = --refs_;
        if (!left) delete this;
        return left;
    }

    UINT64 STDMETHODCALLTYPE GetSize() override { return size_; }
    UINT64 STDMETHODCALLTYPE GetWindowSize() override { return window_; }
    UINT STDMETHODCALLTYPE GetWindowCount() override { return static_cast<UINT>(windows_.size()); }
    HRESULT STDMETHODCALLTYPE GetWindow(UINT index, ID3D12Resource** window) override
    {
        if (!window) return E_INVALIDARG;
        *window = nullptr;
        if (index >= windows_.size()) return E_INVALIDARG;
        *window = windows_[index].Get();
        (*window)->AddRef();
        return S_OK;
    }
    D3D12_GPU_VIRTUAL_ADDRESS STDMETHODCALLTYPE GetGPUVirtualAddress(UINT64 offset, UINT64 bytes) override
    {
        if (!bytes) bytes = 1;
        if (offset >= size_ || bytes > size_ - offset) return 0;
        const UINT64 index = offset / window_;
        const UINT64 inside = offset - index * window_;
        if (bytes > window_ - inside) return 0;
        return windows_[static_cast<std::size_t>(index)]->GetGPUVirtualAddress() + inside;
    }

private:
    std::atomic<ULONG> refs_{1};
    UINT64 size_ = 0;
    UINT64 window_ = 0;
    std::vector<Microsoft::WRL::ComPtr<ID3D12Resource>> windows_;
};

bool has_range(ID3D12Device* device) noexcept
{
    IUnknown* range = nullptr;
    UINT size = sizeof(range);
    if (FAILED(device->GetPrivateData(__uuidof(IX2WGpuRange), &size, &range))) return false;
    if (range) range->Release();
    return true;
}

// Reserves the configured range and attaches it to the device. Nothing is attached on failure.
HRESULT attach_range(ID3D12Device* device, std::uint32_t value) noexcept
{
    auto* range = new (std::nothrow) GpuRange;
    if (!range) return E_OUTOFMEMORY;
    HRESULT hr = range->reserve(device, (value - 2) * vm_range_unit);
    if (SUCCEEDED(hr)) hr = device->SetPrivateDataInterface(__uuidof(IX2WGpuRange), range);
    range->Release();
    return hr;
}
}

extern "C" HRESULT WINAPI d3d12_xs_SerializeVersionedRootSignature(
    const D3D12_VERSIONED_ROOT_SIGNATURE_DESC* root_signature,
    ID3DBlob** blob,
    ID3DBlob** error_blob)
{
    if (!root_signature) {
        return D3D12SerializeVersionedRootSignature(root_signature, blob, error_blob);
    }
    if (root_signature->Version == D3D_ROOT_SIGNATURE_VERSION_1_1) {
        const auto flags = static_cast<std::uint32_t>(root_signature->Desc_1_1.Flags);
        if (flags & observed_console_flags) {
            D3D12_VERSIONED_ROOT_SIGNATURE_DESC copy = *root_signature;
            copy.Desc_1_1.Flags = static_cast<D3D12_ROOT_SIGNATURE_FLAGS>(flags & ~observed_console_flags);
            return D3D12SerializeVersionedRootSignature(&copy, blob, error_blob);
        }
    } else if (root_signature->Version == D3D_ROOT_SIGNATURE_VERSION_1_0) {
        const auto flags = static_cast<std::uint32_t>(root_signature->Desc_1_0.Flags);
        if (flags & observed_console_flags) {
            D3D12_VERSIONED_ROOT_SIGNATURE_DESC copy = *root_signature;
            copy.Desc_1_0.Flags = static_cast<D3D12_ROOT_SIGNATURE_FLAGS>(flags & ~observed_console_flags);
            return D3D12SerializeVersionedRootSignature(&copy, blob, error_blob);
        }
    }
    return D3D12SerializeVersionedRootSignature(root_signature, blob, error_blob);
}

extern "C" HRESULT WINAPI d3d12_xs_CreateRootSignatureDeserializer(
    LPCVOID src_data,
    SIZE_T src_data_size_in_bytes,
    REFIID deserializer_interface,
    void** deserializer)
{
    return D3D12CreateRootSignatureDeserializer(
        src_data, src_data_size_in_bytes, deserializer_interface, deserializer);
}

extern "C" HRESULT WINAPI d3d12_xs_XboxCreateDevice(
    IUnknown* adapter, const void* parameters, REFIID iid, void** device)
{
    if (!device) return E_POINTER;
    *device = nullptr;
    // This entry supports an explicit desktop consumer of the returned interface.
    // The Xbox parameter block and the Xbox device vtable require their own implementation.
    if (parameters) return E_INVALIDARG;
    if (iid != __uuidof(ID3D12Device)) return E_NOINTERFACE;
    AcquireSRWLockExclusive(&vm_state.lock);
    Microsoft::WRL::ComPtr<ID3D12Device> created;
    HRESULT hr = D3D12CreateDevice(adapter, D3D_FEATURE_LEVEL_12_0, IID_PPV_ARGS(&created));
    // After a configuration, the device carries the reserved range (d3d12_xs_range.h). D3D12 returns
    // the existing device for an adapter that already has one, so a range is attached only once.
    if (SUCCEEDED(hr) && vm_state.value && !has_range(created.Get())) hr = attach_range(created.Get(), vm_state.value);
    if (SUCCEEDED(hr)) {
        vm_state.device_created = true;
        *device = created.Detach();
    }
    ReleaseSRWLockExclusive(&vm_state.lock);
    return hr;
}

extern "C" HRESULT WINAPI d3d12_xs_ConfigureVirtualMemoryX(const void* config)
{
    // Accepts only the observed shape, once, before this shim has created a device. A refusal
    // changes no state; the caller's block is only read.
    if (!config) return E_POINTER;
    unsigned char bytes[vm_config_bytes];
    std::memcpy(bytes, config, sizeof(bytes));
    std::uint32_t value = 0;
    std::memcpy(&value, bytes + vm_config_value, sizeof(value));
    if (value != 3 && value != 4) return E_INVALIDARG;
    for (std::size_t i = 0; i < sizeof(bytes); ++i) {
        if (bytes[i] && (i < vm_config_value || i >= vm_config_value + sizeof(value))) return E_INVALIDARG;
    }
    AcquireSRWLockExclusive(&vm_state.lock);
    const bool accepted = !vm_state.value && !vm_state.device_created;
    if (accepted) vm_state.value = value;
    ReleaseSRWLockExclusive(&vm_state.lock);
    return accepted ? S_OK : DXGI_ERROR_INVALID_CALL;
}
