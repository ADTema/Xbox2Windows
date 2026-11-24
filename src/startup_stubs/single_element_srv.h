#pragma once

#include <d3d12.h>

namespace x2w_startup {
// One texel, one mip, one sample, 2D or 3D. In every layout accepted here the only element sits at offset 0
// of the title memory: UNKNOWN, linear (0x100) and the swizzle modes without pipe/bank XOR (0x101..0x10B; a
// swizzle address is block index * block size + a bit pattern of the coordinates, both zero at the origin).
// XOR modes (0x110 and up) can move the origin by the surface's pipe/bank XOR and are refused. Formats are
// plain colour formats whose element is one texel with the same bytes on desktop; R8_UNORM keeps its placed-
// texture path, and block-compressed, planar, depth and packed console formats are refused. Returns the
// element size in bytes, or 0 when the description is not such a texture.
inline UINT single_element_bytes(const D3D12_RESOURCE_DESC& r)
{
    const UINT layout = static_cast<UINT>(r.Layout);
    if ((r.Dimension != D3D12_RESOURCE_DIMENSION_TEXTURE2D && r.Dimension != D3D12_RESOURCE_DIMENSION_TEXTURE3D) ||
        r.Width != 1 || r.Height != 1 || r.DepthOrArraySize != 1 || r.MipLevels != 1 || r.SampleDesc.Count != 1 ||
        r.SampleDesc.Quality != 0 || (layout != 0 && (layout < 0x100 || layout > 0x10B)))
        return 0;
    // GPU-written textures are never uploaded from title memory.
    if (r.Flags & (D3D12_RESOURCE_FLAG_ALLOW_RENDER_TARGET | D3D12_RESOURCE_FLAG_ALLOW_DEPTH_STENCIL |
                   D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS | D3D12_RESOURCE_FLAG_DENY_SHADER_RESOURCE))
        return 0;
    switch (r.Format) {
    case DXGI_FORMAT_R32G32B32A32_FLOAT:
        return 16;
    case DXGI_FORMAT_R16G16B16A16_FLOAT: case DXGI_FORMAT_R16G16B16A16_UNORM:
        return 8;
    case DXGI_FORMAT_R10G10B10A2_UNORM: case DXGI_FORMAT_R11G11B10_FLOAT: case DXGI_FORMAT_R8G8B8A8_UNORM:
    case DXGI_FORMAT_R8G8B8A8_UNORM_SRGB: case DXGI_FORMAT_R8G8B8A8_UINT: case DXGI_FORMAT_R8G8B8A8_SNORM:
    case DXGI_FORMAT_R8G8B8A8_SINT: case DXGI_FORMAT_R16G16_FLOAT: case DXGI_FORMAT_R16G16_UNORM:
    case DXGI_FORMAT_R32_FLOAT: case DXGI_FORMAT_B8G8R8A8_UNORM: case DXGI_FORMAT_B8G8R8A8_UNORM_SRGB:
        return 4;
    case DXGI_FORMAT_R8G8_UNORM: case DXGI_FORMAT_R16_FLOAT: case DXGI_FORMAT_R16_UNORM:
        return 2;
    case DXGI_FORMAT_A8_UNORM:
        return 1;
    default:
        return 0;
    }
}

// The view must name the whole texture with its own format, dimension and the default mapping.
inline bool supports_single_element_srv(const D3D12_RESOURCE_DESC& r, const D3D12_SHADER_RESOURCE_VIEW_DESC& v)
{
    if (!single_element_bytes(r) || v.Format != r.Format ||
        v.Shader4ComponentMapping != D3D12_DEFAULT_SHADER_4_COMPONENT_MAPPING)
        return false;
    if (r.Dimension == D3D12_RESOURCE_DIMENSION_TEXTURE3D)
        return v.ViewDimension == D3D12_SRV_DIMENSION_TEXTURE3D && v.Texture3D.MostDetailedMip == 0 &&
               v.Texture3D.MipLevels == 1 && v.Texture3D.ResourceMinLODClamp == 0.0f;
    return v.ViewDimension == D3D12_SRV_DIMENSION_TEXTURE2D && v.Texture2D.MostDetailedMip == 0 &&
           v.Texture2D.MipLevels == 1 && v.Texture2D.PlaneSlice == 0 && v.Texture2D.ResourceMinLODClamp == 0.0f;
}
}  // namespace x2w_startup
