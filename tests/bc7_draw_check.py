"""Draw an original tiled BC7 mode-6 fixture with the translated copy program."""
from pathlib import Path
import struct
import subprocess
import sys
import tempfile

from pixel_aot_check import assembly, translate
from bc7_tiles import linearize_4k_s


def make_block(x, y):
    # Mode 6, one subset. Even endpoint bytes give zero for both endpoint P bits.
    start = (x * 8, y * 6, 24, 60)
    end = (224, 196, 152, 254)
    bits = 1 << 6
    shift = 7
    for a, b in zip(start, end):
        bits |= ((a >> 1) | ((b >> 1) << 7)) << shift
        shift += 14
    shift += 2
    colors = bytearray()
    weights = (0, 4, 9, 13, 17, 21, 26, 30, 34, 38, 43, 47, 51, 55, 60, 64)
    for index, weight in enumerate(weights):
        bits |= index << shift
        shift += 3 if index == 0 else 4
        colors.extend(((64 - weight) * a + weight * b + 32) >> 6 for a, b in zip(start, end))
    return bits.to_bytes(16, "little"), colors


def fixture(columns=20, rows=18):
    # Cross both 4 KiB tile boundaries and exercise padded D3D12 upload rows.
    width, height = columns * 4, rows * 4
    tile_pitch = (columns + 15) // 16
    tile_count = tile_pitch * ((rows + 15) // 16)
    tiled = bytearray(tile_count * 4096)
    linear = bytearray(columns * rows * 16)
    expected = bytearray(width * height * 4)
    for tile in range(tile_count):
        for index in range(256):
            x = (tile % tile_pitch) * 16 + ((index >> 2) & 3) + ((index >> 3) & 4) + ((index >> 4) & 8)
            y = (tile // tile_pitch) * 16 + (index & 3) + ((index >> 2) & 4) + ((index >> 3) & 8)
            if x >= columns or y >= rows:
                continue
            block, colors = make_block(x, y)
            src = tile * 4096 + index * 16
            tiled[src:src+16] = block
            dst = (y * columns + x) * 16
            linear[dst:dst+16] = block
            for row in range(4):
                pos = ((y * 4 + row) * width + x * 4) * 4
                expected[pos:pos+16] = colors[row*16:(row+1)*16]
    converted = linearize_4k_s(tiled, width, height)
    assert converted == linear
    return struct.pack("<4sII", b"BC7C", width, height), converted, expected


def main():
    compiler, renderer, backend = sys.argv[1:]
    with tempfile.TemporaryDirectory() as directory:
        work = Path(directory)
        shader, source = work / "copy.cso", work / "copy.hlsl"
        source.write_text(translate(assembly(False)), encoding="ascii")
        subprocess.run([compiler, "-T", "ps_6_0", "-E", "main", "-Fo", shader, source], check=True)
        header, rows, expected = fixture()
        case, output = work / "input.case", work / "actual.rgba"
        case.write_bytes(header + rows + expected)
        draw = [renderer, backend, "--check-bc7", shader, case]
        result = subprocess.run([*draw, output])
        if result.returncode:
            return result.returncode
        assert output.read_bytes() == expected
        lower = work / "mip1.case"
        header, rows, expected = fixture(10, 9)
        lower.write_bytes(header + rows + expected)
        mip_draw = [renderer, backend, "--check-bc7-mip1", shader, case, lower]
        subprocess.run(mip_draw, check=True)
        lower.write_bytes(header + rows[16:] + rows[:16] + expected)
        wrong = subprocess.run(mip_draw, capture_output=True, text=True)
        if wrong.returncode != 1 or "pixel_mismatch" not in wrong.stderr:
            raise AssertionError("Moving BC7 blocks must change the readback")
    return 0


if __name__ == "__main__":
    sys.exit(main())
