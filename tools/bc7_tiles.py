"""Convert one non-XOR GFX10 4 KiB standard-swizzle BC7 surface to BC block rows."""


def linearize_4k_s(payload, width, height):
    if width <= 0 or height <= 0:
        raise ValueError("Expected positive pixel dimensions")
    columns, rows = (width + 3) // 4, (height + 3) // 4
    tile_pitch = (columns + 15) // 16
    if len(payload) != tile_pitch * ((rows + 15) // 16) * 4096:
        raise ValueError("Expected complete, padded 4 KiB tiles for one surface")
    output = bytearray(columns * rows * 16)
    for y in range(rows):
        for x in range(columns):
            tile = (y // 16) * tile_pitch + x // 16
            # Block index bits from low to high: y0 y1 x0 x1 y2 x2 y3 x3.
            local = ((y & 3) | ((x & 3) << 2) | ((y & 4) << 2)
                     | ((x & 4) << 3) | ((y & 8) << 3) | ((x & 8) << 4))
            src = tile * 4096 + local * 16
            dst = (y * columns + x) * 16
            output[dst:dst + 16] = payload[src:src + 16]
    return bytes(output)
