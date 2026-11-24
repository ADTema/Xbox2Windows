"""Draw one-texel 2D and 3D textures published by address (device slot 70) and check refused descriptions.

Each run draws eight 1x4 columns from a translated pixel shader that loads texel (0, 0, 0):
  0  RGBA8, layout UNKNOWN            1  RGBA8, layout 0x105 (another address)
  2  the column-0 texel rewritten and published again; it must read the new value
  3  after ten refused descriptions (2x1, two mips, two slices, four samples, XOR layout 0x115, BC1, R8,
     a UAV flag, the other view dimension, a two-mip view): the column-2 view must be unchanged
  4  B8G8R8A8, layout 0x100           5  R16G16B16A16_FLOAT, layout 0x105
  6  a zero address after column 5: refused, column 5's view stays
  7  the column-0 address and description again
Usage: startup_single_element_srv_check.py <startup_stream_consumer> <hardware|warp>
Without the single-element path every column except 3 and 6 reads a null view (zero).
"""
from pathlib import Path
import sys
import tempfile

from startup_address_srv_check import draw_texture

A = (0x11, 0x22, 0x33, 0xff)
B = (0xc0, 0x40, 0x80, 0xff)
C = (0x5a, 0xa5, 0x3c, 0xff)
BGRA = (0xf0, 0x20, 0x10, 0xff)
HALF = (64, 191, 255, 255)  # 0.25, 0.75, 1, 1 as UNORM8


def expected():
    columns = [A, B, C, C, BGRA, HALF, HALF, C]
    return bytes(c for _ in range(4) for column in columns for c in column)


def check(directory, consumer, backend, dimension):
    texture, load = ("Texture3D", "int4(0, 0, 0, 0)") if dimension == "3d" else ("Texture2D", "int3(0, 0, 0)")
    hlsl = (f"{texture}<float4> t : register(t0);\n"
            "float4 main(float4 p : SV_Position) : SV_Target {\n"
            f"  return t.Load({load});\n}}\n")
    kind = "tex3d" if dimension == "3d" else "tex2d"
    actual = draw_texture(directory, consumer, backend, hlsl, {"X2W_TEST_SINGLE_ELEMENT": dimension}, kind)
    if actual is None:
        return 77
    want = expected()
    if actual != want:
        for i in range(0, len(want), 4):
            if actual[i:i + 4] != want[i:i + 4]:
                raise AssertionError(f"{dimension} column {(i // 4) % 8} row {i // 32}: actual {actual[i:i + 4].hex()} "
                                     f"expected {want[i:i + 4].hex()}")
        raise AssertionError(f"{dimension}: readback length {len(actual)}, expected {len(want)}")
    print(f"{backend} {dimension}: 8 columns of one-texel views exact, ten refused descriptions kept the previous view")
    return 0


if __name__ == "__main__":
    for dimension in ("2d", "3d"):
        with tempfile.TemporaryDirectory() as temporary:
            result = check(Path(temporary), *sys.argv[1:], dimension)
            if result:
                sys.exit(result)
