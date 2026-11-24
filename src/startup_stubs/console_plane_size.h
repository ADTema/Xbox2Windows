// Experimental (docs/startup-runtime.md): console allocation sizes for two texture families whose
// desktop sizes are larger.
//
// A console executable reserves memory of its own for every placed texture, sized by the device's
// allocation-info answer, and can take all of it from one fixed block. Desktop answers are larger
// for depth with stencil (D32_FLOAT_S8X24 takes 8 bytes a texel on desktop; the console keeps a
// 4-byte depth plane and a 1-byte stencil plane) and for multisampled textures (4 MiB placement
// alignment, 64 KiB on the console). With the desktop answers the block can run out.
//
// The size answered here is every plane padded to whole 64 KiB tiles and rounded up to 64 KiB. A
// tile holds 64 KiB of samples: 128 x 128 texels at 4 bytes a texel, 256 x 128 at 2, 256 x 256 at
// 1, and 64 x 64 at 4 bytes with four samples.
#pragma once

#include <d3d12.h>

#include <cstdint>

namespace x2w_startup {
namespace plane_detail {
// One plane of width x height texels, padded to 64 KiB tiles. bytes is texel bytes times samples
// and must be a power of two up to 64 KiB.
inline std::uint64_t plane_bytes(std::uint64_t width, std::uint64_t height, std::uint64_t bytes, std::uint64_t slices)
{
    unsigned texels_log2 = 16;
    for (std::uint64_t b = bytes; b > 1; b >>= 1) --texels_log2;
    const std::uint64_t tile_width = std::uint64_t{1} << ((texels_log2 + 1) / 2), tile_height = std::uint64_t{1} << (texels_log2 / 2);
    const std::uint64_t padded_width = (width + tile_width - 1) / tile_width * tile_width;
    const std::uint64_t padded_height = (height + tile_height - 1) / tile_height * tile_height;
    return (padded_width * padded_height * bytes * slices + 0xFFFF) & ~std::uint64_t{0xFFFF};
}

// Texel bytes of the colour formats answered for multisampling; 0 for every other format.
inline unsigned colour_texel_bytes(unsigned format)
{
    if (format >= 9 && format <= 14) return 8;    // R16G16B16A16
    if (format >= 23 && format <= 32) return 4;   // R10G10B10A2, R11G11B10, R8G8B8A8
    if (format >= 87 && format <= 93) return 4;   // B8G8R8A8, B8G8R8X8
    return 0;
}
}  // namespace plane_detail

// Replaces info with the console size for a single-mip 2D texture that is depth with stencil
// (R32G8X24 family, or the console's 16-bit depth with stencil, formats 118-120) or multisampled
// in one of the colour formats above. Returns false and leaves info alone for every other
// description, and when the console size would not be smaller than a valid desktop answer.
inline bool console_plane_size(const D3D12_RESOURCE_DESC& desc, D3D12_RESOURCE_ALLOCATION_INFO& info)
{
    using namespace plane_detail;
    if (desc.Dimension != D3D12_RESOURCE_DIMENSION_TEXTURE2D || desc.MipLevels > 1 || !desc.Width || !desc.Height) return false;
    const unsigned format = static_cast<unsigned>(desc.Format);
    const bool d32s8 = format >= 19 && format <= 22, d16s8 = format >= 118 && format <= 120;
    const std::uint64_t samples = desc.SampleDesc.Count ? desc.SampleDesc.Count : 1;
    const std::uint64_t slices = desc.DepthOrArraySize ? desc.DepthOrArraySize : 1;
    if (samples != 1 && samples != 2 && samples != 4 && samples != 8) return false;
    std::uint64_t size = 0;
    if (d32s8) {
        size = plane_bytes(desc.Width, desc.Height, 4 * samples, slices) + plane_bytes(desc.Width, desc.Height, samples, slices);
    } else if (d16s8) {
        size = plane_bytes(desc.Width, desc.Height, 2 * samples, slices) + plane_bytes(desc.Width, desc.Height, samples, slices);
    } else if (samples > 1 && colour_texel_bytes(format)) {
        size = plane_bytes(desc.Width, desc.Height, colour_texel_bytes(format) * samples, slices);
    } else {
        return false;
    }
    if (info.SizeInBytes != ~0ull && size >= info.SizeInBytes && info.Alignment <= 0x10000) return false;
    info.SizeInBytes = size;
    info.Alignment = 0x10000;
    return true;
}
}  // namespace x2w_startup
