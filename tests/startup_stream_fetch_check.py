"""A slot-86 vertex shader that starts by calling the driver's fetch routine draws from the stream's input layout.

Source-built gfx1013 code only. The vertex shader begins with s_swappc_b64 s[4:5], s[4:5], then s_inst_prefetch, and
exports pos0 from v4-v7 and param0 from v8-v10. Its container lists two fetch records (input register 0 -> v4,
register 1 -> v8, three components each) and its input signature names them POSITION and TEXCOORD. The stream's
input layout declares TEXCOORD at offset 0 and POSITION after it (D3D12_APPEND_ALIGNED_ELEMENT), both float3.

Cases on an 8x4 target cleared to blue with a red pixel shader:
  fetch:    POSITION covers pixels [1, 3) x [1, 3); exactly those are red.
  swapped:  the generated fetch with the two records' registers exchanged (a mutation) draws the TEXCOORD
            rectangle [0, 4) x [0, 1) instead, so the exact check above fails.
  no layout: the same stream without the INPUT_LAYOUT subobject is refused by the translator and not drawn.
  unwritten: a vertex shader that exports v12, which no record fetches, is refused.
  z only:   a record that reads only z (mask 0x4) with count 3 translates; with count 2 it is refused.
"""
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import zlib

from startup_stream_check import gfx2hlsl
from startup_stream_draw_check import pixel, vop1

WIDTH, HEIGHT = 8, 4
RED, BLUE = bytes((255, 0, 0, 255)), bytes((0, 0, 255, 255))
SWAPPC, PREFETCH, WAIT_VM, ENDPGM = 0xbe842104, 0xbfa00003, 0xbf8c3f70, 0xbf810000
RECORDS = [(6, 0, 0x7, 4, 2), (6, 1, 0x7, 8, 2)]
INPUTS = [("POSITION", 0, 0x7), ("TEXCOORD", 1, 0x7)]
LAYOUT_LINE = "x2w-draw stream input layout: 2 elements (format/slot/offset/class) 6/0/0/0 6/0/4294967295/0"


def vertex(param_first=8, records=RECORDS):
    # exp pos0 v4, v5, v6, v7 done; exp param0 v<first>, v<first+1>, v<first+2>, v7.
    words = [SWAPPC, PREFETCH, vop1(1, 7, 242), WAIT_VM, 0xf80008cf, 0x07060504,
             0xf800020f, param_first | (param_first + 1) << 8 | (param_first + 2) << 16 | 7 << 24, ENDPGM]
    return fetch_container(words, records)


def fetch_container(words, records):
    """A vertex container with an FSSM header of 0x2f8 bytes (fetch records at +0x138) and an ISG1 part."""
    code = struct.pack("<%dI" % len(words), *words)
    base = 0x2f8
    extent = (40 + len(code) + 4 + 15) & ~15
    image = bytearray(base + extent)
    image[:4] = b"FSSM"
    struct.pack_into("<I", image, 4, 0x101)
    struct.pack_into("<QQ", image, 192, base, extent)
    struct.pack_into("<Q", image, 232, len(image))
    for i, record in enumerate(records):
        image[0x138 + 5 * i:0x13d + 5 * i] = bytes(record)
    image[base + 40:base + 40 + len(code)] = code
    padding = (len(image) - base - 40 - len(code)) // 4
    image[base + 40 + len(code):] = struct.pack("<I", 0xbf9f0000) * padding
    native = b"XBCH" + bytes(12) + struct.pack("<II", len(image), 0) + zlib.compress(bytes(image))
    program = (struct.pack("<HH", 0, 1) + bytes(20) + b"XDAT" + struct.pack("<5I", 1, 0, 13, 48, len(native)) + native)
    names = b""
    entries = b""
    first = 8 + 32 * len(INPUTS)
    for name, register, mask in INPUTS:
        entries += struct.pack("<6IBBHI", 0, first + len(names), 0, 0, 3, register, mask, mask, 0, 0)
        names += name.encode("ascii") + b"\0"
    signature = struct.pack("<II", len(INPUTS), 8) + entries + names
    sections = [b"ISG1" + struct.pack("<I", len(signature)) + signature, b"DXIL" + struct.pack("<I", len(program)) + program]
    table = 32 + 4 * len(sections)
    offsets, at = [], table
    for section in sections:
        offsets.append(at)
        at += len(section)
    header = b"DXBC" + bytes(16) + struct.pack("<3I", 1, at, len(sections)) + struct.pack("<%dI" % len(offsets), *offsets)
    return header + b"".join(sections)


def expected(inside):
    return b"".join(RED if inside(x, y) else BLUE for y in range(HEIGHT) for x in range(WIDTH))


def first_difference(actual, want):
    for index in range(0, len(want), 4):
        if actual[index:index + 4] != want[index:index + 4]:
            return "pixel (%d, %d) is %s, expected %s" % (index // 4 % WIDTH, index // 4 // WIDTH,
                                                         actual[index:index + 4].hex(), want[index:index + 4].hex())
    return None


FETCHED = expected(lambda x, y: 1 <= x < 3 and 1 <= y < 3)
SWAPPED = expected(lambda x, y: 0 <= x < 4 and y < 1)


class Run:
    def __init__(self, directory, consumer, backend, vs_bytes, layout):
        self.cache = directory / "cache"
        self.cache.mkdir(parents=True)
        self.vs, ps, self.root, self.output = (directory / name for name in ("vs", "ps", "root", "pixels"))
        self.vs.write_bytes(vs_bytes)
        ps.write_bytes(pixel(False))
        self.args = [consumer, self.vs, ps, self.root]
        self.backend = backend
        self.env = dict(os.environ, X2W_D3D12_PERMISSIVE="1", X2W_D3D12_LIST_NOOP="1", X2W_D3D12_RENDER="1",
                        X2W_SHADER_CACHE=str(self.cache), X2W_TEST_VERTEX_FETCH="1")
        self.env.setdefault("X2W_D3D12_DEBUG", "0")
        if layout:
            self.env["X2W_TEST_INPUT_LAYOUT"] = "1"
        else:
            self.env.pop("X2W_TEST_INPUT_LAYOUT", None)
        subprocess.run(self.args, env=self.env, check=True)
        requests = sorted(self.cache.glob("req_*.a"))
        assert len(requests) == 1, requests
        self.key = int(requests[0].name[4:20], 16)

    def draw(self):
        result = subprocess.run(self.args + [self.backend, self.output], env=self.env, capture_output=True, text=True)
        print(result.stdout, end="")
        return result


def check(directory, consumer, backend):
    # fetch: the request carries the layout and the readback is exact.
    run = Run(directory / "fetch", consumer, backend, vertex(), True)
    name = run.cache / ("req_%016x" % run.key)
    layout = (name.parent / (name.name + ".ia")).read_bytes()
    assert layout == b"ia1 2\nTEXCOORD 0 6 0 0 0 0\nPOSITION 0 6 0 4294967295 0 0\n", layout
    assert run.key == gfx2hlsl.pipeline_key(run.vs.read_bytes(), (run.vs.parent / "ps").read_bytes(),
                                            run.root.read_bytes(), layout), "request key does not include the layout"
    status = gfx2hlsl.translate_request(str(run.cache), run.key)
    assert status == "ok", status
    result = run.draw()
    if backend == "hardware" and result.returncode == 77:
        print("No D3D12 feature-level 12 hardware adapter")
        return 77
    if result.returncode or "-> drawn;" not in result.stderr:
        raise RuntimeError(f"fetch draw failed on {backend}: {result.returncode}\n{result.stderr}")
    if LAYOUT_LINE not in result.stderr:
        raise AssertionError("missing layout diagnostic:\n" + result.stderr)
    difference = first_difference(run.output.read_bytes(), FETCHED)
    if difference:
        raise AssertionError(f"fetch: {difference}")
    print(f"{backend} fetch: all {WIDTH * HEIGHT} pixels exact")

    # swapped: the same request translated with the records' registers exchanged must not pass.
    swapped = Run(directory / "swapped", consumer, backend, vertex(), True)
    original = gfx2hlsl.stream_fetch

    def exchange(*args):
        fetch = original(*args)
        fetch[0]["vgpr"], fetch[1]["vgpr"] = fetch[1]["vgpr"], fetch[0]["vgpr"]
        return fetch
    gfx2hlsl.stream_fetch = exchange
    try:
        status = gfx2hlsl.translate_request(str(swapped.cache), swapped.key)
    finally:
        gfx2hlsl.stream_fetch = original
    assert status == "ok", status
    result = swapped.draw()
    if result.returncode or "-> drawn;" not in result.stderr:
        raise RuntimeError(f"swapped draw failed on {backend}: {result.returncode}\n{result.stderr}")
    actual = swapped.output.read_bytes()
    if not first_difference(actual, FETCHED):
        raise AssertionError("swapped: the mutated fetch passed the exact check")
    difference = first_difference(actual, SWAPPED)
    if difference:
        raise AssertionError(f"swapped: {difference}")
    print(f"{backend} swapped registers: the exact check fails; the TEXCOORD rectangle is drawn instead")

    # no layout: refused by the translator, so the runtime has no translation and draws nothing.
    bare = Run(directory / "bare", consumer, backend, vertex(), False)
    assert not list(bare.cache.glob("*.ia"))
    status = gfx2hlsl.translate_request(str(bare.cache), bare.key)
    assert status == "unsupported: vertex stage calls a fetch routine and the pipeline declares no input layout", status
    result = bare.draw()
    if "-> drawn;" in result.stderr:
        raise AssertionError("a vertex shader with a fetch call and no layout was drawn")
    print(f"{backend} no layout: refused ({status[13:]})")

    # unwritten: an export of v12, which nothing fetches or writes, is refused.
    unwritten = Run(directory / "unwritten", consumer, backend, vertex(param_first=12), True)
    status = gfx2hlsl.translate_request(str(unwritten.cache), unwritten.key)
    assert status == "unsupported: vertex stage reads v12, which neither the fetch nor the program writes", status
    print(f"{backend} unwritten register: refused ({status[13:]})")

    # z only: the count reaches the highest component read; a mask above the count is refused.
    for count, want in ((3, "ok"), (2, "unsupported: unverified vertex fetch record 0600040401")):
        records = [(6, 0, 0x4, 4, count - 1), RECORDS[1]]
        z_only = Run(directory / ("z%d" % count), consumer, backend, vertex(records=records), True)
        status = gfx2hlsl.translate_request(str(z_only.cache), z_only.key)
        assert status == want, status
    print(f"{backend} z-only record: count 3 translates, count 2 refused")
    return 0


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as temp:
        sys.exit(check(Path(temp), *sys.argv[1:]))
