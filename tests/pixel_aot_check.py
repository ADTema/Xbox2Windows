"""Exercise offline pixel translation with two independently assembled test programs."""
from pathlib import Path
import math
import struct
import subprocess
import sys
import tempfile
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from pixel_aot import disassemble, lower, native_program


def assembly(swap):
    red, blue = ("v14", "v12") if swap else ("v12", "v14")
    return [
        "s_mov_b64 s[50:51], exec",
        "s_wqm_b64 exec, exec",
        "s_mov_b32 m0, s24",
        "v_interp_p1_f32_e32 v8, v0, attr0.x",
        "v_interp_p1_f32_e32 v9, v0, attr0.y",
        "v_interp_p2_f32_e32 v9, v1, attr0.y",
        "v_interp_p2_f32_e32 v8, v1, attr0.x",
        "s_and_b64 exec, exec, s[50:51]",
        "s_mov_b32 s21, 0",
        "s_load_dwordx8 s[28:35], s[20:21], null",
        "s_mov_b32 s40, 1",
        "s_mov_b32 s41, 2",
        "s_mov_b32 s42, 3",
        "s_mov_b32 s43, 4",
        "s_waitcnt lgkmcnt(0)",
        "image_sample v[12:15], v[8:9], s[28:35], s[40:43] dmask:0xf dim:SQ_RSRC_IMG_2D",
        "s_waitcnt vmcnt(0)",
        f"v_cvt_pkrtz_f16_f32_e32 v16, {red}, v13",
        f"v_cvt_pkrtz_f16_f32_e32 v17, {blue}, v15",
        "exp mrt0 v16, v16, v17, v17 done compr vm",
        "s_endpgm",
    ]


DUAL_CASES = ("forward", "reverse", "reuse")


def dual_program(case="forward", *, swap_weights=False):
    program = assembly(False)
    first = next(i for i, line in enumerate(program) if line.startswith("image_sample"))
    sample_a = program[first]
    sample_b = sample_a.replace("v[12:15]", "v[20:23]").replace("s[28:35]", "s[56:63]")
    load_b = "s_load_dwordx8 s[56:63], s[20:21], 0x20"
    if case == "reuse":
        # Finish A before reloading the same descriptor registers for B.
        program[first:first+1] = [sample_a, "s_waitcnt vmcnt(0)",
                                  load_b.replace("56:63", "28:35"), "s_waitcnt lgkmcnt(0)",
                                  sample_b.replace("56:63", "28:35")]
    elif case in ("forward", "reverse"):
        program[first:first+1] = [sample_a, sample_b] if case == "forward" else [sample_b, sample_a]
        program.insert(program.index("s_mov_b32 s40, 1"), load_b)
    else:
        raise ValueError(f"Unknown dual-texture case: {case}")
    pos = program.index("v_cvt_pkrtz_f16_f32_e32 v16, v12, v13")
    a, b = ("0x3e800000", "0x3f400000") if swap_weights else ("0x3f400000", "0x3e800000")
    ops = []
    for i in range(4):
        ops.extend([f"v_mul_legacy_f32_e32 v{12+i}, {a}, v{12+i}",
                    f"v_fma_f32 v{12+i}, {b}, v{20+i}, v{12+i}"])
    program[pos:pos] = ops
    return program


def translate_dual(instructions):
    return lower(instructions, 20, 24, [1, 2, 3, 4], second_texture_offset=32)


def envelope(code, name=b"fixture"):
    program_start = 256
    image = bytearray(program_start) + code
    image[:4] = b"FSSM"
    struct.pack_into("<I", image, 192, program_start - 40)
    native = b"XBCH" + bytes(12) + struct.pack("<II", len(image), 0) + zlib.compress(image)
    program = (bytes(24) + b"XDAT" + struct.pack("<II", 1, 0)
               + struct.pack("<III", 13, 48, len(native)) + native)
    blob = (b"DXBC" + bytes(16) + struct.pack("<4I", 1, 44 + len(program), 1, 36)
            + b"DXIL" + struct.pack("<I", len(program)) + program)
    encoder = zlib.compressobj(wbits=-15)
    payload = encoder.compress(blob) + encoder.flush()
    return (bytes([len(name) + 1]) + name + b"\0\0"
            + struct.pack("<4I", len(payload), 0, len(payload), len(blob)) + payload)


def must_reject(function, *args):
    try:
        function(*args)
    except (ValueError, KeyError):
        return
    raise AssertionError(f"{function.__name__} accepted invalid input")


def translate(instructions):
    return lower(instructions, 20, 24, [1, 2, 3, 4], constant_descriptor=64)


def curve():
    program = assembly(False)
    pos = program.index("s_mov_b32 s40, 1")
    program.insert(pos, "s_load_dwordx4 s[44:47], s[20:21], 0x40")
    pos = program.index("s_waitcnt vmcnt(0)")
    program[pos:pos] = [
        "s_buffer_load_dwordx4 s[44:47], s[44:47], 0xc",
        "s_waitcnt lgkmcnt(0)",
    ]
    pos = program.index("v_cvt_pkrtz_f16_f32_e32 v16, v12, v13")
    program[pos:pos] = [
        "v_max_f32_e32 v18, s46, v12",
        "v_log_f32_e32 v18, v18",
        "v_rcp_f32_e32 v19, s44",
        "v_mul_legacy_f32_e32 v18, v19, v18",
        "v_exp_f32_e32 v18, v18",
        "v_sub_f32_e32 v19, 1.0, v13",
        "v_fma_f32 v12, s45, v18, -v19",
        "v_fmac_f32_e32 v12, s47, v13",
        "v_min_f32_e32 v12, 1.0, v12",
        "v_mul_legacy_f32_e64 v12, v12, 1.0 clamp",
    ]
    return program


def half_rtz(x):
    bits, = struct.unpack("<H", struct.pack("<e", x))
    rounded, = struct.unpack("<e", struct.pack("<H", bits))
    return struct.unpack("<e", struct.pack("<H", bits - (rounded > x)))[0]


def curve_case(directory, gain):
    gamma, floor, mix = 2.0, .125, .25
    case = bytearray(256)
    struct.pack_into("<4f", case, 12, gamma, gain, floor, mix)
    ramp = (0, 16, 37, 64, 101, 153, 219, 254)
    for y in ramp:
        for x in ramp:
            g = y / 255
            r = gain * math.sqrt(max(floor, x / 255)) - (1 - g) + mix * g
            case.extend(struct.pack("<4f", half_rtz(min(1, max(0, r))), half_rtz(g), half_rtz(128/255), 1))
    path = directory / "curve.case"
    path.write_bytes(case)
    return path


def check_controls(directory):
    archive = directory / "input.bin"
    code = bytes.fromhex("000080bf 000081bf")  # s_nop 0 followed by s_endpgm
    record = envelope(code)
    archive.write_bytes(b"another_fixture\0" + record)
    assert native_program(archive, "fixture")[1] == code
    long_name = b"synthetic_pixel_with_a_printable_length"
    archive.write_bytes(envelope(code, long_name))
    assert native_program(archive, long_name.decode())[1] == code
    for invalid in (record[:-1], record + b"\0" + record, envelope(code + code)):
        archive.write_bytes(invalid)
        must_reject(native_program, archive, "fixture")

    # LLVM 15 prints "exp mrt0 v16, ..."; newer LLVM prints "exp mrt0, v16, ...".
    for program in (assembly(False), assembly(True), curve()):
        modern = [line.replace("exp mrt0 ", "exp mrt0, ") for line in program]
        assert modern != program
        assert translate(modern) == translate(program)
        must_reject(translate, [line.replace("exp mrt0 ", "exp mrt0,, ") for line in program])

    program = assembly(False)
    for old, new in (("s_mov_b32 s21, 0", "s_mov_b32 s21, 1"),
                     ("s_mov_b32 s40, 1", "s_mov_b32 s40, 8"),
                     ("attr0.y", "attr1.y"),
                     ("s_wqm_b64 exec, exec", "s_branch 0")):
        must_reject(translate, [line.replace(old, new) for line in program])
    must_reject(translate, program[:-1])
    for wait in ("s_waitcnt vmcnt(0)", "s_waitcnt lgkmcnt(0)"):
        must_reject(translate, [line for line in program if line != wait])
    for old, new in (("0x40", "0x48"), ("0xc", "0xfe"), ("0xc", "0x100"),
                     ("s_waitcnt lgkmcnt(0)", "s_nop 0"), ("s[44:47], 0xc", "s[40:43], 0xc")):
        must_reject(translate, [line.replace(old, new) for line in curve()])


def check_binary(directory, assembler, objcopy, library):
    fixtures = [(assembly(False), translate), (assembly(True), translate), (curve(), translate)]
    fixtures.extend((dual_program(case), translate_dual) for case in DUAL_CASES)
    fixtures.append((dual_program(swap_weights=True), translate_dual))
    for instructions, lower_fixture in fixtures:
        source = directory / "fixture.s"
        obj = directory / "fixture.o"
        binary = directory / "fixture.bin"
        source.write_text("\n".join(instructions) + "\n", encoding="ascii")
        subprocess.run([assembler, "-triple=amdgcn--amdpal", "-mcpu=gfx1013",
                        "-filetype=obj", source, "-o", obj], check=True)
        subprocess.run([objcopy, "-O", "binary", "--only-section=.text", obj, binary], check=True)
        archive = directory / "fixture.rpf"
        archive.write_bytes(envelope(binary.read_bytes()))
        _, native = native_program(archive, "fixture")
        assert native == binary.read_bytes()
        assert lower_fixture(disassemble(native, library)) == lower_fixture(instructions)


def check_render(directory, compiler, renderer, backend):
    for swap in (False, True):
        source = directory / "fixture.hlsl"
        shader = directory / "fixture.cso"
        source.write_text(translate(assembly(swap)), encoding="ascii")
        subprocess.run([compiler, "-T", "ps_6_0", "-E", "main", "-Fo", shader, source], check=True)
        draw = [renderer, backend, "--check-pixel", shader]
        result = subprocess.run([*draw, "bgra" if swap else "rgba"])
        if result.returncode:
            return result.returncode
        if swap:
            wrong = subprocess.run([*draw, "rgba"], capture_output=True, text=True)
            if wrong.returncode != 1 or "pixel_mismatch" not in wrong.stderr:
                raise AssertionError("The renderer failed to detect the changed channel order")
    source.write_text(translate(curve()), encoding="ascii")
    subprocess.run([compiler, "-Gis", "-T", "ps_6_0", "-E", "main", "-Fo", shader, source], check=True)
    for gain in (.75, 1.125):
        case = curve_case(directory, gain)
        draw = [renderer, backend, "--check-pixel-case", shader, case]
        subprocess.run(draw, check=True)
    corrupted = bytearray(case.read_bytes())
    struct.pack_into("<f", corrupted, 16, 0.0)
    case.write_bytes(corrupted)
    wrong = subprocess.run(draw, capture_output=True, text=True)
    if wrong.returncode != 1 or "pixel_mismatch" not in wrong.stderr:
        raise AssertionError("Stale reference accepted after changing the bound constants")
    capture = directory / "blend.rgba"
    draw = [renderer, backend, "--dual-pixel", shader, capture]
    for case in DUAL_CASES:
        source.write_text(translate_dual(dual_program(case)), encoding="ascii")
        subprocess.run([compiler, "-Gis", "-T", "ps_6_0", "-E", "main", "-Fo", shader, source], check=True)
        subprocess.run(draw, check=True)
    wrong = subprocess.run([renderer, backend, "--dual-pixel-swapped", shader, capture], capture_output=True, text=True)
    if wrong.returncode != 1 or "pixel_mismatch" not in wrong.stderr:
        raise AssertionError("Swapped texture bindings escaped detection")
    source.write_text(translate_dual(dual_program(swap_weights=True)), encoding="ascii")
    subprocess.run([compiler, "-Gis", "-T", "ps_6_0", "-E", "main", "-Fo", shader, source], check=True)
    wrong = subprocess.run(draw, capture_output=True, text=True)
    if wrong.returncode != 1 or "pixel_mismatch" not in wrong.stderr:
        raise AssertionError("Swapped blend weights escaped detection")
    return 0


def main():
    mode, *args = sys.argv[1:]
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        check_controls(directory)
        if mode == "binary":
            check_binary(directory, *args)
        elif mode == "draw":
            return check_render(directory, *args)
        else:
            raise ValueError("Expected binary or draw mode")


if __name__ == "__main__":
    sys.exit(main())
