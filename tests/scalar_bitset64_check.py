"""Source-built scalar bit-set programs with exact UINT readback references."""
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tools"), str(ROOT / "tests")]
import form_coverage
import pixel_aot_check as pixel
import scan_unsupported_shaders as scanner
from pixel_aot import disassemble

OPS = ("s_bitset0_b64", "s_bitset1_b64")
SOURCES = ("s46", "s60", "s61", "31", "32", "63", "64", "-1")
INDICES = (0, 1, 31, 32, 33, 63, 64, 65, 95, 96, 127, 0xFFFFFFFF)
PAIRS = ((0, 0), (0xFFFFFFFF, 0xFFFFFFFF), (0x12345678, 0x9ABCDEF0),
         (31, 32), (63, 64), (0x7F800001, 0xFF800001))


def program(op, source="s46"):
    return pixel.uncompressed_export([
        "s_mov_b32 s60, s44", "s_mov_b32 s61, s45",
        "s_cmp_eq_u32 s47, 1", f"{op} s[60:61], {source}",
        "s_cselect_b32 s62, 1, 0",
        "v_mov_b32_e32 v12, s60", "v_mov_b32_e32 v13, s61",
        "v_mov_b32_e32 v14, s62", "v_mov_b32_e32 v15, s46",
    ])


def expected(op, source, words):
    low, high, index, flag = words
    index_value = {"s46": index, "s60": low, "s61": high}.get(source)
    if index_value is None:
        index_value = int(source, 0)
    word = low | (high << 32)
    mask = 1 << (index_value & 63)
    result = word & ~mask if op == OPS[0] else word | mask
    return result & 0xFFFFFFFF, result >> 32, int(flag == 1), index


def transport_program(overwrite=False):
    instructions = program(OPS[1])
    at = len(instructions) - 2
    moves = ["v_mov_b32_e32 v20, v12", "v_mov_b32_e32 v12, 1.0"]
    moves += (["v_add_f32_e32 v12, 1.0, v12"] if overwrite else ["v_mov_b32_e32 v12, v20"])
    return instructions[:at] + moves + instructions[at:]


def write_case(path, words, reference):
    constants = bytearray(256)
    struct.pack_into("<4I", constants, 12, *words)
    # Write integer bits directly, including NaN-shaped words; no host float conversion.
    path.write_bytes(constants + struct.pack("<4I", *reference) * 64 + b"\x01")


def controls():
    for op in OPS:
        for source in SOURCES:
            instructions = program(op, source)
            result = pixel.translate_int(instructions)
            assert "& 63u" in result and "& 31u" in result
            assert "uint salu" in result and "uint4 main" in result
            line = f"{op} s[60:61], {source}"
            assert any(pattern.fullmatch(line) for pattern in scanner.COMPILED_SUPPORTED_PATTERNS), line
            # Malformed pairs, special registers and source modifiers stay refused.
            for bad in (f"{op} s[61:62], s46", f"{op} s[60:62], s46",
                        f"{op} s[104:106], s46", f"{op} exec, s46", f"{op} s60, s46",
                        f"{op} s[60:61], v12", f"{op} s[60:61], |s46|",
                        f"{op} s[60:61], 0x100000000", f"{op} s[60:61], s[44:45]",
                        f"{op} s[60:61], s90", f"{op} s[60:61], s20"):
                pixel.must_reject(pixel.translate_int, [bad if value == line else value for value in instructions])
        instructions = program(op)
        # Both old destination words must exist. Do not zero an undefined half.
        for move in ("s_mov_b32 s60, s44", "s_mov_b32 s61, s45"):
            pixel.must_reject(pixel.translate_int, [line for line in instructions if line != move])
        load = instructions.index("s_buffer_load_dwordx4 s[44:47], s[44:47], 0xc") + 1
        for bad in (f"{op} s[44:45], 1", f"{op} s[46:47], s60", f"{op} s[60:61], s46"):
            pixel.must_reject(pixel.translate_int, instructions[:load] + [bad] + instructions[load:])
        # A bit-set must not manufacture SCC if no earlier instruction defined it.
        pixel.must_reject(pixel.translate_int, [line for line in instructions if line != "s_cmp_eq_u32 s47, 1"])

    # Pin boundary semantics independently of HLSL text and the pair decomposition.
    assert expected(OPS[1], "s46", (0, 0, 32, 0)) == (0, 1, 0, 32)
    assert expected(OPS[0], "s46", (0xFFFFFFFF, 0xFFFFFFFF, 63, 1))[:2] == (0xFFFFFFFF, 0x7FFFFFFF)
    assert expected(OPS[1], "s46", (0, 0, 64, 0))[:2] == (1, 0)
    assert expected(OPS[1], "s60", (32, 0, 99, 1)) == (32, 1, 1, 99)
    # Copies keep the raw scalar identity; later floating-point writes must not
    # export the stale integer value associated with an earlier VGPR definition.
    copied = pixel.translate_int(transport_program())
    overwritten = pixel.translate_int(transport_program(True))
    assert copied.split("return uint4(")[-1].startswith("salu")
    assert overwritten.split("return uint4(")[-1].startswith("asuint(alu")
    for target in ("gfx1013", "gfx1030"):
        measured = form_coverage.measure({"pixel_aot_scalar_bitset64_warp": "pass"},
                                        records={"pixel_aot_scalar_bitset64_warp": set(OPS)})[target]
        assert measured["covered"] == 2, measured
        skipped = form_coverage.measure({"pixel_aot_scalar_bitset64_warp": "skip"},
                                       records={"pixel_aot_scalar_bitset64_warp": set(OPS)})[target]
        assert skipped["covered"] == 0 and len(skipped["blocked_by_skip"]) == 2
    print("scalar bitset64 controls passed; two SOP1 forms in both reference lists")


def binary(directory, assembler, objcopy, library):
    for op in OPS:
        for source in SOURCES:
            instructions = program(op, source)
            for cpu in ("gfx1013", "gfx1030"):
                assembly, obj, data = (directory / name for name in ("owned.s", "owned.o", "owned.bin"))
                assembly.write_text("\n".join(instructions) + "\n", encoding="ascii")
                subprocess.run([assembler, "-triple=amdgcn--amdpal", f"-mcpu={cpu}",
                                "-filetype=obj", assembly, "-o", obj], check=True, capture_output=True)
                subprocess.run([objcopy, "-O", "binary", "-j", ".text", obj, data], check=True)
                decoded = disassemble(data.read_bytes(), library, cpu=cpu.encode())
                assert pixel.translate_int(decoded) == pixel.translate_int(instructions), (op, source, cpu)
    for overwrite in (False, True):
        instructions = transport_program(overwrite)
        assembly.write_text("\n".join(instructions) + "\n", encoding="ascii")
        subprocess.run([assembler, "-triple=amdgcn--amdpal", "-mcpu=gfx1013",
                        "-filetype=obj", assembly, "-o", obj], check=True, capture_output=True)
        subprocess.run([objcopy, "-O", "binary", "-j", ".text", obj, data], check=True)
        assert pixel.translate_int(disassemble(data.read_bytes(), library)) == pixel.translate_int(instructions)
    print("34 assembly and lowering round trips passed (32 instruction cases, two transport controls)")


def run_batch(renderer, backend, shader, cases, *, report=False):
    result = subprocess.run([renderer, backend, "--check-pixel-batch", shader,
                             *(path for path, _ in cases)], capture_output=True, text=True)
    if result.returncode == 77:
        result.check_returncode()
    actual = [line for line in result.stdout.splitlines() if line.startswith("case=")]
    wanted = [f"case={i} status={status}" for i, (_, status) in enumerate(cases)]
    if actual != wanted or result.returncode != int(any(status != "pass" for _, status in cases)):
        raise AssertionError(f"Unexpected batch result\n{result.stdout}\n{result.stderr}")
    if report:
        for line in result.stdout.splitlines():
            if line.startswith(("backend=", "adapter=", "driver=")):
                print(line)


def draw(directory, compiler, renderer, backend):
    draws = 0
    for op in OPS:
        for source in SOURCES:
            shader, hlsl = directory / "bitset.cso", directory / "bitset.hlsl"
            hlsl.write_text(pixel.translate_int(program(op, source)), encoding="ascii")
            pixel.compile_shader(compiler, hlsl, shader)
            cases = []
            for low, high in PAIRS:
                for index in INDICES if source == "s46" else (0xDEADBEEF,):
                    for flag in (0, 1):
                        words = low, high, index, flag
                        path = directory / f"case-{len(cases)}.case"
                        write_case(path, words, expected(op, source, words))
                        cases.append((path, "pass"))
            # Wrong references must be detected in the same batch, surrounded by passes.
            words = (0xFFFFFFFF, 0xFFFFFFFF, 32, 1) if op == OPS[0] else (0, 0, 32, 0)
            correct = expected(op, source, words)
            for channel in range(4):
                wrong = list(correct)
                wrong[channel] ^= 1
                path = directory / f"wrong-{channel}.case"
                write_case(path, words, wrong)
                cases.insert(channel * 2 + 1, (path, "mismatch"))
            run_batch(renderer, backend, shader, cases, report=(op == OPS[0] and source == SOURCES[0]))
            draws += len(cases) - 4
        # Swapping clear/set must fail against a detecting reference.
        words = (0xFFFFFFFF, 0xFFFFFFFF, 32, 1)
        path = directory / "mutation.case"
        write_case(path, words, expected(op, "s46", words))
        opposite = OPS[1] if op == OPS[0] else OPS[0]
        hlsl.write_text(pixel.translate_int(program(opposite)), encoding="ascii")
        pixel.compile_shader(compiler, hlsl, shader)
        run_batch(renderer, backend, shader, [(path, "mismatch")])
    for overwrite in (False, True):
        words = (0x7F800001, 0xFF800001, 0, 1)
        reference = list(expected(OPS[1], "s46", words))
        if overwrite:
            reference[0] = 0x40000000  # 1.0f + 1.0f, replacing the earlier integer bits
        hlsl.write_text(pixel.translate_int(transport_program(overwrite)), encoding="ascii")
        pixel.compile_shader(compiler, hlsl, shader)
        write_case(path, words, reference)
        run_batch(renderer, backend, shader, [(path, "pass")])
        draws += 1
    print(f"{draws} exact UINT draws, 64 wrong-reference controls and two operation mutations passed")


def main():
    controls()
    if len(sys.argv) == 1:
        return 0
    with tempfile.TemporaryDirectory() as folder:
        directory = Path(folder)
        mode, *args = sys.argv[1:]
        if mode == "binary":
            binary(directory, *args)
        elif mode == "draw":
            try:
                draw(directory, *args)
            except subprocess.CalledProcessError as error:
                if error.returncode == 77 and str(error.cmd[0]) == str(args[1]):
                    return 77
                raise
        else:
            raise ValueError("Expected binary or draw")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    finally:
        pixel.write_record(os.environ.get("FORM_COVERAGE_RECORD"))
