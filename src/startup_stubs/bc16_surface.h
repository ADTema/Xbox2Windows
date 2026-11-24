#pragma once

#include <d3d12.h>
#include <cstdint>
#include <cstring>

namespace x2w_startup {
struct Bc16Surface {
    static constexpr UINT block_texels = 4, block_bytes = 16;
    static constexpr UINT tile_blocks = 16, tile_bytes = tile_blocks * tile_blocks * block_bytes;

    const UINT columns, rows, tile_columns, tile_rows;

    explicit Bc16Surface(const D3D12_RESOURCE_DESC& desc)
        : columns((static_cast<UINT>(desc.Width) + block_texels - 1) / block_texels),
          rows((desc.Height + block_texels - 1) / block_texels),
          tile_columns((columns + tile_blocks - 1) / tile_blocks),
          tile_rows((rows + tile_blocks - 1) / tile_blocks)
    {
    }

    UINT padded_width() const { return tile_columns * tile_blocks * block_texels; }
    UINT padded_height() const { return tile_rows * tile_blocks * block_texels; }
    UINT padded_row_bytes() const { return tile_columns * tile_blocks * block_bytes; }
    std::uint64_t size() const { return std::uint64_t{tile_columns} * tile_rows * tile_bytes; }

    std::uint64_t block_offset(UINT column, UINT row) const
    {
        const UINT x = column % tile_blocks, y = row % tile_blocks;
        // GFX10 4 KiB standard non-XOR 16-byte block order: y0 y1 x0 x1 y2 x2 y3 x3.
        const UINT block = (y & 3) | ((x & 3) << 2) | ((y & 4) << 2) |
                           ((x & 4) << 3) | ((y & 8) << 3) | ((x & 8) << 4);
        const std::uint64_t tile = std::uint64_t{row / tile_blocks} * tile_columns + column / tile_blocks;
        return tile * tile_bytes + block * block_bytes;
    }
};

inline void copy_4k_s_to_rows(unsigned char* destination, UINT pitch, const unsigned char* source,
                              const Bc16Surface& surface)
{
    for (UINT y = 0; y < surface.rows; ++y) {
        auto* row = destination + std::uint64_t{y} * pitch;
        for (UINT x = 0; x < surface.columns; ++x)
            std::memcpy(row + x * surface.block_bytes, source + surface.block_offset(x, y), surface.block_bytes);
    }
}
}  // namespace x2w_startup
