"""Draw 2×2 4 KiB tiled BC3/BC7 textures from guest addresses, including swapped tiles."""
from pathlib import Path
import re
import struct
import sys
import tempfile

from bc7_draw_check import make_block as bc7_block
from bc7_tiles_check import block_index
from startup_address_srv_check import draw_texture

WIDTH, HEIGHT = 128, 128


def bc3_block(x, y):
    # Literal DXT5 endpoint selection, avoiding interpolation tolerances.
    red, green, blue = bool(x & 16), bool(y & 16), bool((x ^ y) & 1)
    alpha = (7 * x + 13 * y) % 256
    color = (0xf800 if red else 0) | (0x07e0 if green else 0) | (0x001f if blue else 0)
    block = struct.pack("<BB6xHHI", alpha, 0, color, 0, 0)
    return block, bytes((255 * red, 255 * green, 255 * blue, alpha)) * 16


def make_surface(encode):
    tiled = bytearray(4 * 4096)
    rgba = bytearray(128 * 128 * 4)
    for y in range(32):
        for x in range(32):
            block, colors = encode(x, y)
            tile = (y // 16) * 2 + x // 16
            start = tile * 4096 + 16 * block_index(x % 16, y % 16)
            tiled[start:start + 16] = block
            for row in range(4):
                start = 4 * ((y * 4 + row) * 128 + x * 4)
                rgba[start:start + 16] = colors[row * 16:row * 16 + 16]
    return tiled, rgba


def source_block(x, y, tile_pitch, swapped):
    """The block of the 2x2 tile grid that a detile with this tile pitch shows at block (x, y)."""
    tile = (y // 16) * tile_pitch + x // 16
    tile ^= swapped
    return (tile % 2) * 16 + x % 16, (tile // 2) * 16 + y % 16


def expected_panels(rgba, width, height, tile_pitch):
    """Four panels of 128x128 texels: views of the first, swapped, first (kept) and first backing."""
    image = bytearray(4 * WIDTH * 4 * HEIGHT)
    for panel, swapped in enumerate((0, 1, 1, 0)):
        for y in range(height):
            for x in range(width):
                bx, by = source_block(x // 4, y // 4, tile_pitch, swapped)
                start = 4 * ((by * 4 + y % 4) * 128 + bx * 4 + x % 4)
                pos = 4 * (y * 4 * WIDTH + panel * WIDTH + x)
                image[pos:pos + 4] = rgba[start:start + 4]
    return bytes(image)  # texels outside the texture load as zero


def check(directory, consumer, backend, fmt, width, height):
    tiled, rgba = make_surface(bc3_block if fmt == "BC3" else bc7_block)
    source = directory / "tiled.bin"
    source.write_bytes(tiled)
    hlsl = ("Texture2D<float4> t : register(t0);\n"
            "float4 main(float4 p : SV_Position) : SV_Target {\n"
            f"  return t.Load(int3(uint(p.x) % {WIDTH}, uint(p.y), 0));\n}}\n")
    trap_log = directory / "trap.log"
    modes = {"X2W_TEST_BC_VIEW": str(source), "X2W_TEST_BC_SIZE": f"{width}x{height}", "X2W_TRAP_LOG": str(trap_log)}
    if fmt == "BC3":
        modes["X2W_TEST_BC3"] = "1"
    actual = draw_texture(directory, consumer, backend, hlsl, modes)
    if actual is None:
        return 77
    if len(actual) != WIDTH * 4 * HEIGHT * 4:
        raise AssertionError(f"{fmt} readback length {len(actual)}")
    expected = expected_panels(rgba, width, height, 2)
    for pos in range(0, len(expected), 4):
        if actual[pos:pos + 4] != expected[pos:pos + 4]:
            y, x = divmod(pos // 4, 4 * WIDTH)
            raise AssertionError(f"{fmt} {width}x{height} panel {x // WIDTH} ({x % WIDTH},{y}) "
                                 f"actual {actual[pos:pos + 4].hex()} expected {expected[pos:pos + 4].hex()}")
    # Controls: exchanged tiles, and for a partial last tile column the tile pitch of the unpadded width.
    swapped = sum(expected[p:p + 4] != expected[p + 4 * WIDTH:p + 4 * WIDTH + 4]
                  for p in range(0, len(expected), 4) if (p // 4) % (4 * WIDTH) < WIDTH)
    if swapped == 0:
        raise AssertionError("Swapping the tiles did not change the reference image")
    columns = width // 4
    unpadded = 0
    if columns % 16:
        wrong = expected_panels(rgba, width, height, columns // 16)
        unpadded = sum(actual[p:p + 4] != wrong[p:p + 4] for p in range(0, len(actual), 4))
        if unpadded == 0:
            raise AssertionError("The unpadded tile pitch did not change the image")
    log = trap_log.read_text(errors="replace")
    refusal = (rf"Device::slot70 unsupported memory SRV arguments: reason=unsupported_description "
               rf"res\{{dim=3 fmt={77 if fmt == 'BC3' else 98} size={width - 2}x{height}x1 ")
    if not re.search(refusal, log):
        raise AssertionError(f"{fmt}: no refusal for {width - 2}x{height} (not whole blocks)")
    partial = re.findall(r"partial-tile BC view (\d+)x(\d+) .*: published, XG-announced write 0", log)
    # One line per first publication at an address: the first backing and the exchanged one.
    if partial != ([] if width % 64 == 0 and height % 64 == 0 else [(str(width), str(height))] * 2):
        raise AssertionError(f"{fmt}: partial-tile lines {partial}")
    print(f"{backend} {fmt} {width}x{height}: {4 * WIDTH * HEIGHT} RGBA pixels exact; exchanged tiles differ in "
          f"{swapped} texels; unpadded tile pitch differs in {unpadded}; {width - 2}x{height} refused")
    return 0


if __name__ == "__main__":
    for fmt, width, height in (("BC3", 128, 128), ("BC7", 128, 128), ("BC3", 100, 68), ("BC7", 100, 68)):
        with tempfile.TemporaryDirectory() as temporary:
            result = check(Path(temporary), *sys.argv[1:], fmt, width, height)
            if result:
                sys.exit(result)
