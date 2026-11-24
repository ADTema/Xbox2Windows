// Experimental (docs/startup-runtime.md): a stand-in format for 16-bit packed textures that the
// adapter cannot use the way the description asks.
//
// A console executable creates B5G5R5A1_UNORM and B4G4R4A4_UNORM textures as render targets and
// for unordered access. An adapter may not support that (measured: neither format as a render
// target or typed UAV on an NVIDIA adapter through vkd3d-proton); the description is then refused,
// the allocation-info answer is all ones and the executable gets no texture. Such a texture
// becomes R8G8B8A8_UNORM, which holds every value the packed format can, and views of it follow.
// null_texture_view.h covers the same two formats for views without a resource.
#pragma once

#include <d3d12.h>

namespace x2w_startup {
inline bool packed_target_format(DXGI_FORMAT format)
{
    return format == DXGI_FORMAT_B5G5R5A1_UNORM || format == DXGI_FORMAT_B4G4R4A4_UNORM;
}

// The format to create a texture with. support1(format) returns the adapter's
// D3D12_FORMAT_SUPPORT1 bits for a format, or 0 when the query fails. The format changes only for
// a packed format whose description asks for render-target or unordered-access use that the
// adapter lacks while R8G8B8A8_UNORM has it.
template <class Support1>
DXGI_FORMAT packed_target_stand_in(const D3D12_RESOURCE_DESC& desc, Support1&& support1)
{
    if (desc.Dimension == D3D12_RESOURCE_DIMENSION_UNKNOWN || desc.Dimension == D3D12_RESOURCE_DIMENSION_BUFFER ||
        !packed_target_format(desc.Format))
        return desc.Format;
    UINT required = 0;
    if (desc.Flags & D3D12_RESOURCE_FLAG_ALLOW_RENDER_TARGET) required |= D3D12_FORMAT_SUPPORT1_RENDER_TARGET;
    if (desc.Flags & D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS) required |= D3D12_FORMAT_SUPPORT1_TYPED_UNORDERED_ACCESS_VIEW;
    if (!required || (static_cast<UINT>(support1(desc.Format)) & required) == required) return desc.Format;
    if ((static_cast<UINT>(support1(DXGI_FORMAT_R8G8B8A8_UNORM)) & required) != required) return desc.Format;
    return DXGI_FORMAT_R8G8B8A8_UNORM;
}

// The format for a view of resource_format that was described with view_format: a packed view of a
// stand-in texture reads the stand-in's format.
inline DXGI_FORMAT packed_view_format(DXGI_FORMAT view_format, DXGI_FORMAT resource_format)
{
    return packed_target_format(view_format) && resource_format == DXGI_FORMAT_R8G8B8A8_UNORM ? DXGI_FORMAT_R8G8B8A8_UNORM
                                                                                                : view_format;
}
}  // namespace x2w_startup
