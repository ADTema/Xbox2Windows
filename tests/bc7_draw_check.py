"""Draw source-built BC7 blocks and tiled mode-6 mip levels with the translated copy program."""
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


def check_all_modes(work: Path, renderer: str, backend: str, shader: Path) -> None:
    case = work / "all-modes.case"
    generator = Path(__file__).resolve().parents[1] / "tools" / "bc7_blocks.py"
    subprocess.run([sys.executable, "-B", generator, case], check=True)
    draw = [renderer, backend, "--check-bc7", shader, case]
    subprocess.run(draw, check=True)

    # The first eight blocks cycle through modes 0-7. Flip the low rotation bit
    # of the mode-4 block so its red and alpha channels swap at pixel (16, 0).
    changed = bytearray(case.read_bytes())
    changed[struct.calcsize("<4sII") + 4 * 16] ^= 1 << 5
    case.write_bytes(changed)
    wrong = subprocess.run(draw, capture_output=True, text=True)
    if wrong.returncode != 1 or "pixel_mismatch x=16 y=0" not in wrong.stderr.splitlines():
        raise AssertionError(f"Expected a mode-4 rotation mismatch at (16, 0): {wrong.stderr}")


def write_strip_mip(work: Path, width: int, height: int) -> Path:
    # One block row, with a different endpoint per level of the power-of-two chain.
    block, colors = make_block(width.bit_length(), height)
    columns = (width + 3) // 4
    visible = b"".join((colors[row * 16:row * 16 + 16] * columns)[:width * 4] for row in range(height))
    case = work / f"strip-{width}x{height}.case"
    case.write_bytes(struct.pack("<4sII", b"BC7C", width, height) + block * columns + visible)
    return case


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
        check_all_modes(work, renderer, backend, shader)
        lower = work / "mip1.case"
        header, rows, expected = fixture(10, 9)
        lower.write_bytes(header + rows + expected)
        mip_draw = [renderer, backend, "--check-bc7-mip1", shader, case, lower]
        subprocess.run(mip_draw, check=True)
        lower.write_bytes(header + rows[16:] + rows[:16] + expected)
        wrong = subprocess.run(mip_draw, capture_output=True, text=True)
        if wrong.returncode != 1 or "pixel_mismatch" not in wrong.stderr:
            raise AssertionError("Moving BC7 blocks must change the readback")
        tail = []
        for level, blocks in enumerate((16, 8, 4, 2, 1), start=3):
            mip = work / f"resident{level}.case"
            mip.write_bytes(b"".join(fixture(blocks, blocks)))
            tail.append(mip)
        tail.extend([write_strip_mip(work, 2, 2), write_strip_mip(work, 1, 1)])
        chain = [renderer, backend, "--check-bc7-tail", shader, "3", *tail]
        subprocess.run(chain, check=True)
        header, rows, expected = fixture(4, 4)
        tail[2].write_bytes(header + rows[16:] + rows[:16] + expected)
        wrong = subprocess.run(chain, capture_output=True, text=True)
        if wrong.returncode != 1 or "pixel_mismatch" not in wrong.stderr:
            raise AssertionError("An incorrect middle mip must fail verification")
        # A 4096x4 strip uses all thirteen mip levels while staying small.
        narrow = [write_strip_mip(work, 4096 >> level, max(1, 4 >> level)) for level in range(13)]
        subprocess.run([renderer, backend, "--check-bc7-mip1", shader, *narrow[:2]], check=True)
        narrow_chain = [renderer, backend, "--check-bc7-tail", shader, "0", *narrow]
        subprocess.run(narrow_chain, check=True)
        repeated = subprocess.run([*narrow_chain, narrow[-1]], capture_output=True, text=True)
        if repeated.returncode != 1 or "Expected consecutive BC7 mip sizes" not in repeated.stderr:
            raise AssertionError("A BC7 mip chain must end at 1x1")
        base = subprocess.run([renderer, backend, "--check-bc7", shader, narrow[-2]],
                              capture_output=True, text=True)
        if base.returncode != 1 or "Expected block-aligned BC7 base dimensions" not in base.stderr:
            raise AssertionError("A 2x1 BC7 level is valid only as a subresource")
        stale = bytearray(narrow[-1].read_bytes())
        stale[-4] ^= 0xff  # Change only the expected red channel of the 1x1 mip.
        narrow[-1].write_bytes(stale)
        wrong = subprocess.run(narrow_chain, capture_output=True, text=True)
        if wrong.returncode != 1 or "pixel_mismatch x=0 y=0" not in wrong.stderr.splitlines():
            raise AssertionError("The final 1x1 draw must check its visible texel")
    return 0


if __name__ == "__main__":
    sys.exit(main())
