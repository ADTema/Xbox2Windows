"""Check both gfx1030 image_get_lod results against a CPU footprint model."""
import math
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile

from compute_store_check import assemble
from pixel_aot_check import envelope, pixel_aot, translate, write_record
from pixel_sample_lod_check import base_prefix, compile_ps


QUERY = "image_get_lod v[12:13], v[8:9], s[28:35], s[40:43] dmask:0x3 dim:SQ_RSRC_IMG_2D"


def program():
    lines = base_prefix(quad_scale=True)
    i = lines.index("v_fma_f32 v8, s62, v8, 0")
    lines.insert(i + 1, "v_fma_f32 v9, s63, v9, 0")
    return lines + [QUERY, "s_waitcnt vmcnt(0)", "v_mov_b32_e32 v14, 0.5", "v_mov_b32_e32 v15, 1.0",
                    "exp mrt0 v12, v13, v14, v15 done vm", "s_endpgm"]


def upper_clamp_program():
    # On the two-mip fixture, the horizontal UV scale is 4. Export raw LOD - 2 in
    # red and clamped LOD in green, so the expected color is (0, 1, 0, 1).
    return base_prefix(quad_scale=True) + [
        QUERY, "s_waitcnt vmcnt(0)", "v_subrev_f32_e32 v13, 2.0, v13",
        "v_mov_b32_e32 v14, 0", "v_mov_b32_e32 v15, 1.0",
        "exp mrt0 v13, v12, v14, v15 done vm", "s_endpgm",
    ]


def controls():
    for old, new, diagnostic in (
        ("s_waitcnt vmcnt(0)", "s_nop 0", "Unsupported export"),
        ("s[40:43] dmask", "s[44:47] dmask", "Unsupported texture LOD image or sampler binding"),
        ("dmask:0x3", "dmask:0xf", "Unsupported instruction"),
        ("dim:SQ_RSRC_IMG_2D", "dim:SQ_RSRC_IMG_3D", "Unsupported instruction"),
        (QUERY, "v_mov_b32_e32 v8, 0.5\n" + QUERY, "quad provenance"),
    ):
        changed = [part for line in program() for part in line.replace(old, new).splitlines()]
        try:
            translate(changed)
        except ValueError as error:
            assert diagnostic.casefold() in str(error).casefold(), str(error)
        else:
            raise AssertionError(f"Expected rejection: {diagnostic}")


def binary(directory, assembler, objcopy, library):
    for stem, lines in (("footprint", program()), ("upper-clamp", upper_clamp_program())):
        native = assemble(directory, assembler, objcopy, lines, cpu="gfx1030", features="+wavefrontsize64")
        decoded = pixel_aot.disassemble(native, library, cpu=b"gfx1030", features=b"+wavefrontsize64", offsets=True)
        assert [line for _, line in decoded if line.startswith("image_")] == [QUERY]
        expected = translate(lines)
        assert translate(decoded) == expected
        archive, result = directory / f"{stem}.rpf", directory / f"{stem}-cli.hlsl"
        archive.write_bytes(envelope(native))
        subprocess.run([sys.executable, "-B", pixel_aot.__file__, archive, "fixture", "--llvm", library,
                        "--texture-sgpr", "20", "--interp-sgpr", "24", "--sampler-words", "1", "2", "3", "4",
                        "--constant-descriptor", "0x40", "--output", result], check=True)
        assert result.read_text() == expected
    controls()
    return 0


def draw(directory, compiler, renderer, backend):
    controls()
    source = translate(program())
    cso = compile_ps(compiler, source, directory, "lod")
    case = directory / "lod.case"
    command = [renderer, backend, "--check-pixel-case", cso, case]
    for scale in (0.5, 0.25, 1.0, 2.0):
        raw_lod = math.log2(scale)
        # The viewport and texture are both 8x8. The point sampler has MinLOD=0,
        # and the view has one mip. Negative derivative LODs must remain negative in Y.
        reference = struct.pack("<4f", 0, raw_lod, 0.5, 1)
        case.write_bytes(struct.pack("<4f", 0, 0, scale, scale) + bytes(240) + reference * 64 + struct.pack("<B4I", 2, 0, 0, 8, 8))
        result = subprocess.run(command)
        if result.returncode:
            return result.returncode
        if scale == 0.5:
            mutant = source.replace("CalculateLevelOfDetailUnclamped", "CalculateLevelOfDetail")
            assert mutant != source
            bad_cso = compile_ps(compiler, mutant, directory, "clamp_both")
            bad = subprocess.run([*command[:3], bad_cso, case], capture_output=True, text=True)
            if (bad.returncode != 1 or "pixel_mismatch x=0 y=0" not in bad.stderr
                    or "channel=1 expected=-1 actual=0" not in bad.stderr):
                raise AssertionError(f"Clamping both LODs escaped detection\n{bad.stderr}")
            print(bad.stderr, end="")
    upper = translate(upper_clamp_program())
    cso = compile_ps(compiler, upper, directory, "lod_upper")
    command = [renderer, backend, "--check-pixel-quad-lod"]
    result = subprocess.run([*command, cso])
    if result.returncode:
        return result.returncode
    mutant = upper.replace("CalculateLevelOfDetail(", "CalculateLevelOfDetailUnclamped(")
    assert mutant != upper
    bad_cso = compile_ps(compiler, mutant, directory, "unclamp_both")
    bad = subprocess.run([*command, bad_cso], capture_output=True, text=True)
    if bad.returncode != 1 or "channel=1 expected=1 actual=2" not in bad.stderr:
        raise AssertionError(f"Removing the upper mip clamp escaped detection\n{bad.stderr}")
    print(bad.stderr, end="")
    write_record(os.environ.get("FORM_COVERAGE_RECORD"))
    return 0


if __name__ == "__main__":
    mode, *args = sys.argv[1:]
    with tempfile.TemporaryDirectory() as tmp:
        sys.exit({"binary": binary, "draw": draw}[mode](Path(tmp), *args))
