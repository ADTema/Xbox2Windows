#pragma once

#include <d3d12.h>

#include <climits>
#include <cstddef>

// A logical address window backed by a byte range of an already-owned buffer.
// The caller keeps the resource alive. resource_offset is the window's first
// byte within the resource.
struct RawUavWindow {
    UINT64 logical_base;
    UINT64 bytes;
    UINT64 resource_offset;
    UINT64 resource_width;
};

// A store resolved to one window: the raw UAV that covers exactly that window
// and the byte offset of the store inside it.
struct RawUavStore {
    std::size_t window;
    UINT offset;
    D3D12_UNORDERED_ACCESS_VIEW_DESC view;
};

// Resolve a 4-byte (scalar) or 16-byte (four-DWORD) store at a logical address.
// The address must carry the store's declared alignment, and the whole store
// must fit in a single window. Anything else, including an address outside
// every window, returns E_INVALIDARG before a descriptor reaches the driver.
inline HRESULT resolve_raw_uav_store(const RawUavWindow* windows, std::size_t count, UINT64 address,
                                     UINT store_bytes, RawUavStore& result)
{
    constexpr UINT64 element_bytes = sizeof(UINT32);
    if (!windows || (store_bytes != 4 && store_bytes != 16) || address % store_bytes) return E_INVALIDARG;
    for (std::size_t i = 0; i < count; ++i) {
        const RawUavWindow& window = windows[i];
        if (address < window.logical_base || address - window.logical_base >= window.bytes) continue;
        const UINT64 offset = address - window.logical_base;
        if (store_bytes > window.bytes - offset) return E_INVALIDARG;
        if (!window.bytes || window.bytes % element_bytes || window.bytes / element_bytes > UINT_MAX ||
            window.resource_offset % D3D12_RAW_UAV_SRV_BYTE_ALIGNMENT ||
            window.resource_offset > window.resource_width ||
            window.bytes > window.resource_width - window.resource_offset)
            return E_INVALIDARG;

        result = {};
        result.window = i;
        result.offset = static_cast<UINT>(offset);
        result.view.Format = DXGI_FORMAT_R32_TYPELESS;
        result.view.ViewDimension = D3D12_UAV_DIMENSION_BUFFER;
        result.view.Buffer.FirstElement = window.resource_offset / element_bytes;
        result.view.Buffer.NumElements = static_cast<UINT>(window.bytes / element_bytes);
        result.view.Buffer.Flags = D3D12_BUFFER_UAV_FLAG_RAW;
        return S_OK;
    }
    return E_INVALIDARG;
}
