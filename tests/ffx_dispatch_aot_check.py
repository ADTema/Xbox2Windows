"""Source-built instruction regressions for the dispatch translator."""
from pathlib import Path
import re
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


def eval_generated(shader, init):
    env = {f"s{i}": 0 for i in range(16)}
    env.update({f"v{i}": 0 for i in range(16)})
    env.update(scc=0, exec_lo=1, bfe_u=bfe_u_hlsl, bfe_i=bfe_i_hlsl, **init)
    for raw in shader.splitlines():
        if not raw.startswith("    "):
            continue
        line = raw.strip()
        if line.startswith("if (exec_lo) { ") and line.endswith(" }"):
            line = line[len("if (exec_lo) { "):-2]
        for part in line.split(";"):
            part = part.strip()
            if not part or "," in part.split("=", 1)[0]:
                continue
            lhs, rhs = (x.strip() for x in part.split("=", 1))
            py_rhs = re.sub(r"\b(0x[0-9a-fA-F]+|\d+)u\b", r"\1", rhs)
            if "?" in py_rhs:
                cond, rest = py_rhs.split("?", 1)
                t_val, f_val = rest.split(":", 1)
                val = eval(t_val, {"__builtins__": {}}, env) if eval(cond, {"__builtins__": {}}, env) else eval(f_val, {"__builtins__": {}}, env)
            else:
                val = int(eval(py_rhs, {"__builtins__": {}}, env))
            env[lhs] = val & 0xffffffff
    return env


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
                          "v_bfe_u32 v11, v0, v1, v2\n"
                          "v_cndmask_b32_e64 v8, v1, v2, src_scc\n"
                          "s_cselect_b32 s9, s2, s3\n"
                          "s_bfe_i32 s6, s0, 0x8001c\n"
                          "v_cndmask_b32_e64 v9, v1, v2, src_scc\n"
                          "s_bfe_i32 s7, s0, s1\n"
                          "s_cselect_b32 s10, s2, s3\n"
                          "s_bfe_u32 s8, s0, -1\n"
                          "s_endpgm\n", encoding="ascii")
        subprocess.run([assembler, "-triple=amdgcn--amdpal", "-mcpu=gfx1013", "-filetype=obj",
                        source, "-o", obj], check=True)
        subprocess.run([objcopy, "-O", "binary", "--only-section=.text", obj, binary], check=True)
        code = binary.read_bytes()
        scc_src, scc_obj, scc_bin = (root / ("bfe_scc." + ext) for ext in ("s", "o", "bin"))
        scc_src.write_text("s_cmp_eq_i32 s0, s11\n"
                           "s_bfe_u32 s4, s0, s1\n"
                           "v_cndmask_b32_e64 v8, v1, v2, src_scc\n"
                           "s_cselect_b32 s9, s2, s3\n"
                           "s_cmp_lg_i32 s0, s11\n"
                           "s_bfe_i32 s6, s0, s1\n"
                           "v_cndmask_b32_e64 v9, v1, v2, src_scc\n"
                           "s_cselect_b32 s10, s2, s3\n"
                           "s_endpgm\n", encoding="ascii")
        subprocess.run([assembler, "-triple=amdgcn--amdpal", "-mcpu=gfx1013", "-filetype=obj",
                        scc_src, "-o", scc_obj], check=True)
        subprocess.run([objcopy, "-O", "binary", "--only-section=.text", scc_obj, scc_bin], check=True)
        scc_code = scc_bin.read_bytes()
    instructions = disassemble(code, library, offsets=True)
    expected = (
        "v4 = bfe_u(v0,0x1cu,(0x8u&31u));",
        "v5 = bfe_u(v0,v1,(v2&31u));",
        "v6 = bfe_i(v0,0x1cu,(0x8u&31u));",
        "v7 = bfe_i(v0,v1,(v2&31u));",
        "s4 = bfe_u(s0,0x40200004u,((0x40200004u>>16)&127u)); scc = s4 != 0u;",
        "s5 = bfe_u(s0,s1,((s1>>16)&127u)); scc = s5 != 0u;",
        "v8 = scc?v2:v1;",
        "s9 = scc?s2:s3;",
        "s6 = bfe_i(s0,0x8001cu,((0x8001cu>>16)&127u)); scc = s6 != 0u;",
        "v9 = scc?v2:v1;",
        "s7 = bfe_i(s0,s1,((s1>>16)&127u)); scc = s7 != 0u;",
        "s10 = scc?s2:s3;",
        "s8 = bfe_u(s0,0xffffffffu,((0xffffffffu>>16)&127u)); scc = s8 != 0u;",
    )
    for shader in (translate("rcas", instructions, code), predecessor("pass25", instructions, b"")):
        for line in expected:
            assert line in shader
        for v_line in expected[:4]:
            assert v_line + " scc" not in shader
        # Vector BFE between s_bfe_u32 and SCC consumers must not clobber SCC.
        zero_field = eval_generated(shader, dict(s0=0x0000000f, s1=0x00040004, v0=0xff, v1=1, v2=4, s2=22, s3=33))
        assert (zero_field["s5"], zero_field["v11"], zero_field["v8"], zero_field["s9"]) == (0, 0xf, 1, 33)
        nonzero_field = eval_generated(shader, dict(s0=0x800000f0, s1=0x00040004, v0=0, v1=0, v2=32, s2=22, s3=33))
        assert (nonzero_field["s5"], nonzero_field["v11"], nonzero_field["v8"], nonzero_field["s9"]) == (0xf, 0, 32, 22)
        assert (nonzero_field["s6"], nonzero_field["v9"]) == ((-8) & 0xffffffff, 32)

    scc_ins = disassemble(scc_code, library, offsets=True)
    scc_hlsl = translate("rcas", scc_ins, scc_code)
    # Zero extract after s_cmp_eq_i32 (scc=1) must clear SCC before consumers run.
    cleared = eval_generated(scc_hlsl, dict(s0=0x0000000f, s11=0x0000000f, s1=0x00040004, v1=101, v2=202, s2=303, s3=404))
    assert (cleared["s4"], cleared["v8"], cleared["s9"]) == (0, 101, 404)
    assert (cleared["s6"], cleared["v9"], cleared["s10"]) == (0, 101, 404)
    # Width 0 after s_cmp_eq_i32 (scc=1) also clears SCC to 0.
    width_zero = eval_generated(scc_hlsl, dict(s0=0xffffffff, s11=0xffffffff, s1=0x00000004, v1=101, v2=202, s2=303, s3=404))
    assert (width_zero["s4"], width_zero["v8"], width_zero["s9"]) == (0, 101, 404)
    # Nonzero signed/unsigned extracts after s_cmp_lg_i32 (scc=0) set SCC to 1.
    set_neg = eval_generated(scc_hlsl, dict(s0=0x8000000f, s11=0x8000000f, s1=0x0008001c, v1=101, v2=202, s2=303, s3=404))
    assert (set_neg["s4"], set_neg["v8"], set_neg["s9"]) == (8, 202, 303)
    assert (set_neg["s6"], set_neg["v9"], set_neg["s10"]) == ((-8) & 0xffffffff, 202, 303)


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
