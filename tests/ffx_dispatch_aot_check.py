"""Source-built instruction regressions for the dispatch translator."""
from pathlib import Path
import struct
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from ffx_dispatch_aot import disassemble, predecessor, translate
from ffx_scratch_reference import network


def asint(x):
    x &= 0xffffffff
    return x - 0x100000000 if x & 0x80000000 else x


def bfe_u_hlsl(src, offset, width):
    # Match HLSL SM6 32-bit shift masking (& 31) in tests/ffx_dispatch_io.hlsli.
    count = min(width & 0xffffffff, 32)
    shift = (32 - count) & 31
    return ((src & 0xffffffff) >> (offset & 31)) & (0xffffffff >> shift) if count != 0 else 0


def bfe_i_hlsl(src, offset, width):
    count = min(width & 0xffffffff, 32)
    shift = (32 - count) & 31
    shifted = asint(src) >> (offset & 31)
    aligned = ((shifted & 0xffffffff) << shift) & 0xffffffff
    return (asint(aligned) >> shift) & 0xffffffff if count != 0 else 0


def rdna_bfe(src, offset, width, signed_ext):
    offset &= 31
    width = min(width, 32)
    if width == 0:
        return 0
    bits = [(src >> i) & 1 for i in range(32)]
    msb = bits[31] if signed_ext else 0
    field = [bits[offset + i] if offset + i < 32 else msb for i in range(width)]
    fill = field[-1] if signed_ext else 0
    return sum(bit << i for i, bit in enumerate(field + [fill] * (32 - width)))


def check_bfe(assembler, objcopy, library):
    hlsli = (Path(__file__).resolve().parent / "ffx_dispatch_io.hlsli").read_text(encoding="ascii")
    assert "0xffffffffu >> ((32u - count) & 31u)" in hlsli
    assert "asint(uint(shifted) << shift) >> shift" in hlsli
    for src in (0, 1, 0x12345678, 0x7000000f, 0x8000000f, 0x00000080, 0xffffffff):
        for offset in (0, 1, 4, 16, 24, 28, 31, 36):
            for width in (0, 1, 4, 8, 16, 31, 32, 40, 127):
                assert bfe_u_hlsl(src, offset, width & 31) == rdna_bfe(src, offset, width & 31, False)
                assert bfe_i_hlsl(src, offset, width & 31) == rdna_bfe(src, offset, width & 31, True)
                assert bfe_u_hlsl(src, offset, width & 127) == rdna_bfe(src, offset, width & 127, False)
                assert bfe_i_hlsl(src, offset, width & 127) == rdna_bfe(src, offset, width & 127, True)
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        source, obj, binary = (root / ("bfe." + ext) for ext in ("s", "o", "bin"))
        source.write_text("v_bfe_u32 v4, v0, 28, 8\n"
                          "v_bfe_u32 v5, v0, v1, v2\n"
                          "v_bfe_i32 v6, v0, 28, 8\n"
                          "v_bfe_i32 v7, v0, v1, v2\n"
                          "s_bfe_u32 s4, s0, 0x40200004\n"
                          "s_bfe_u32 s5, s0, s1\n"
                          "s_bfe_i32 s6, s0, 0x8001c\n"
                          "s_bfe_i32 s7, s0, s1\n"
                          "s_bfe_u32 s8, s0, -1\n"
                          "s_endpgm\n", encoding="ascii")
        subprocess.run([assembler, "-triple=amdgcn--amdpal", "-mcpu=gfx1013", "-filetype=obj",
                        source, "-o", obj], check=True)
        subprocess.run([objcopy, "-O", "binary", "--only-section=.text", obj, binary], check=True)
        code = binary.read_bytes()
    instructions = disassemble(code, library, offsets=True)
    expected = (
        "v4 = bfe_u(v0,0x1cu,(0x8u&31u));",
        "v5 = bfe_u(v0,v1,(v2&31u));",
        "v6 = bfe_i(v0,0x1cu,(0x8u&31u));",
        "v7 = bfe_i(v0,v1,(v2&31u));",
        "s4 = bfe_u(s0,0x40200004u,((0x40200004u>>16)&127u));",
        "s5 = bfe_u(s0,s1,((s1>>16)&127u));",
        "s6 = bfe_i(s0,0x8001cu,((0x8001cu>>16)&127u));",
        "s7 = bfe_i(s0,s1,((s1>>16)&127u));",
        "s8 = bfe_u(s0,0xffffffffu,((0xffffffffu>>16)&127u));",
    )
    for shader in (translate("rcas", instructions, code), predecessor("pass25", instructions, b"")):
        for line in expected:
            assert line in shader


def main(assembler, objcopy, library):
    # A signed i8 dot product, replicated low half, clamp and byte insert
    # have independent integer answers on these source-owned test operands.
    fixture = ["buffer_load_dwordx4 v[0:3], v4, s[8:11], 0 offen",
               "v_dot4_i32_i8 v0, v0, 0x01010101, 7",
               "v_dot4_i32_i8 v1, v1, -6, 0 op_sel_hi:[1,0,1]",
               "v_cvt_pk_u8_f32 v2, v2, 2, v3",
               "buffer_store_dwordx4 v[0:3], v4, s[8:11], 0 offen"]
    operands = [[0x7f0080ff, 0x01020304, 0x43960000, 0x12345678]]
    assert network(list(enumerate(fixture)), operands, b"", 24) == [5, (-40)&0xffffffff, 0x12ff5678, 0x12345678]
    # Literal low half decrements x; its zero high half must leave y unchanged.
    # LLVM 15 prints this literal as -1 when disassembling a packed add.
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        source, obj, binary = (root / ("fixture." + ext) for ext in ("s", "o", "bin"))
        source.write_text("v_pk_add_u16 v4, v0, 1\n"
                          "image_load v[5:6], v4, s[24:31] dmask:0x7 dim:SQ_RSRC_IMG_2D unorm a16 d16\n"
                          "s_endpgm\n", encoding="ascii")
        subprocess.run([assembler, "-triple=amdgcn--amdpal", "-mcpu=gfx1013", "-filetype=obj",
                        source, "-o", obj], check=True)
        subprocess.run([objcopy, "-O", "binary", "--only-section=.text", obj, binary], check=True)
        assembled = binary.read_bytes()
    # llvm-mc canonicalizes a spelling of 0xffff to the short inline -1
    # form. Select the VOP3P literal source explicitly and append its DWORD.
    operands, = struct.unpack_from("<I", assembled, 4)
    assert (operands >> 9) & 511 == 129
    literal_src1 = (operands & ~(511 << 9)) | (255 << 9)
    code = assembled[:4] + struct.pack("<II", literal_src1, 0xffff) + assembled[8:]
    instructions = disassemble(code, library, offsets=True)
    hlsl = translate("rcas", instructions, code)
    assert "0xffffu >> 16" in hlsl and "0xffffffffu" not in hlsl
    assert "load16(uint2(v4 & 65535u, v4>>16))" in hlsl
    check_bfe(assembler, objcopy, library)


if __name__ == "__main__":
    main(*sys.argv[1:])
