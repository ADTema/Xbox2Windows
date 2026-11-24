"""Compute entry registers from COMPUTE_PGM_RSRC2 in tools/compute_store_aot.py (#1544).

  (no arguments)                        decoding and translation controls, pure Python
  binary <llvm-mc>                      assemble the fixture programs for gfx1013
  draw <dxc> <offscreen_check> <warp|hardware>
                                        translate, dispatch and compare the readback

Each fixture program is a source-built gfx1013 wave program whose COMPUTE_PGM_RSRC2 enables two
user SGPRs (the table pointer s[0:1]), the group X ID (s2) and TG_SIZE (s3). Every thread stores
its dispatch-thread X and its TG_SIZE word to dword pair tid.x of the output:

    s_mov_b32 s1, 0
    s_load_dwordx4 s[12:15], s[0:1], null
    v_lshl_add_u32 v4, s2, log2(n), v0      dispatch thread = group * n + local
    v_mov_b32 v6, v4
    v_mov_b32 v7, s3                         TG_SIZE
    buffer_store_dwordx2 v[6:7], v4, s[12:15], 0 idxen  (stride 8)

TG_SIZE is the group's wave count in bits 5:0 and the wave's index within the group in bits 11:6,
the layout Mesa reads on GFX6-10. The expected words below are computed from that definition, not
from the translator. The cases cover one wave, several waves and a partial last wave, at wave32
and wave64. The draw also runs the same programs with the wave index moved to bit 20 (the field
Mesa reads on GFX10.3) and requires a mismatch, so the readback separates the two layouts.
"""
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "tools"))
import compute_store_aot as aot  # noqa: E402

SENTINEL = 0xc5c5c5c5
USER_SGPR_2, TGID_X, TGID_Y, TGID_Z, TG_SIZE_EN = 2 << 1, 1 << 7, 1 << 8, 1 << 9, 1 << 10
RSRC2 = USER_SGPR_2 | TGID_X | TG_SIZE_EN  # 0x484


def program(threads):
    shift = threads.bit_length() - 1
    return [
        "s_mov_b32 s1, 0",
        "s_load_dwordx4 s[12:15], s[0:1], null",
        f"v_lshl_add_u32 v4, s2, {shift}, v0",
        "v_mov_b32_e32 v6, v4",
        "v_mov_b32_e32 v7, s3",
        "s_waitcnt lgkmcnt(0)",
        "buffer_store_dwordx2 v[6:7], v4, s[12:15], 0 idxen",
        "s_endpgm",
    ]


# (name, threads per group, wave size, groups dispatched)
CASES = [
    ("one_wave32", 32, 32, 3),
    ("two_waves32", 64, 32, 2),
    ("four_waves32", 128, 32, 1),
    ("partial_wave32", 16, 32, 3),
    ("one_wave64", 64, 64, 2),
    ("partial_wave64", 32, 64, 3),
]


def binding(wave):
    return dict(table_reg=0, descriptor_offset=0, stride=8, rsrc2=RSRC2, wave_size=wave)


def expected(threads, wave, groups):
    """Readback from the definition: tid.x and TG_SIZE = waves | (local // wave) << 6."""
    waves = -(-threads // wave)
    words = []
    for group in range(groups):
        for local in range(threads):
            words += [group * threads + local, waves | (local // wave) << 6]
    return words + [SENTINEL] * (320 - len(words))


def rejects(message, function, *args, **kwargs):
    try:
        function(*args, **kwargs)
    except ValueError as error:
        assert message in str(error), (message, error)
        return
    raise AssertionError(f"accepted; expected {message!r}")


def controls():
    # Register placement: user SGPRs, then the enabled group IDs in X, Y, Z order, then TG_SIZE.
    assert aot.entry_registers(RSRC2) == (2, {0: 2}, 3, 1)
    assert aot.entry_registers((4 << 1) | TGID_X | TGID_Y | TGID_Z | TG_SIZE_EN | (2 << 11)) == (
        4, {0: 4, 1: 5, 2: 6}, 7, 3)
    assert aot.entry_registers((3 << 1) | TGID_Y | TGID_Z | TG_SIZE_EN) == (3, {1: 3, 2: 4}, 5, 1)
    assert aot.entry_registers(USER_SGPR_2) == (2, {}, None, 1)
    rejects("thread-ID component count", aot.entry_registers, RSRC2 | 3 << 11)
    print("entry_registers: user SGPRs, then group X/Y/Z, then TG_SIZE; TIDIG_COMP_CNT 0-2")

    # The TG_SIZE word, and its use in a store.
    source = aot.lower(program(64), 64, **binding(32))
    assert "uint gindex : SV_GroupIndex" in source, source
    assert "uint2(tid.x, (2u | ((gindex >> 5u) << 6u)))" in source, source
    assert "(1u | ((gindex >> 6u) << 6u))" in aot.lower(program(64), 64, **binding(64))
    print("TG_SIZE: waves | (SV_GroupIndex >> log2(wave)) << 6")

    # Without rsrc2 the program's s3 is not TG_SIZE, and s2 is a group ID only if named.
    rejects("Unresolved scalar move source", aot.lower, program(64), 64, table_reg=0, descriptor_offset=0,
            stride=8, group_reg=2)
    # Refusals.
    rejects("do not also give group registers", aot.lower, program(64), 64, **binding(32), group_reg=2)
    rejects("needs a wave size", aot.lower, program(64), 64, **dict(binding(32), wave_size=None))
    rejects("only with COMPUTE_PGM_RSRC2", aot.lower, program(64), 64, table_reg=0, descriptor_offset=0,
            stride=8, group_reg=2, wave_size=32)
    rejects("within the user SGPRs", aot.lower, program(64), 64,
            **dict(binding(32), rsrc2=(1 << 1) | TGID_X | TG_SIZE_EN))
    # A 4x4 pitched store (the PITCH program of compute_store_check.py): ten user SGPRs with the table
    # at s[8:9] put the group IDs in s10 and s11, as that test names them by hand. TIDIG_COMP_CNT binds
    # v1 (local Y) only when it enables the Y component.
    pitch = ["s_mov_b32 s9, 0", "s_load_dwordx4 s[12:15], s[8:9], null",
             "v_lshl_add_u32 v3, s10, 2, v0", "v_lshl_add_u32 v4, s11, 2, v1",
             "v_lshlrev_b32_e32 v5, 3, v3", "v_mad_u32_u24 v6, 0x48, v4, v5",
             "v_mov_b32_e32 v8, v3", "v_mov_b32_e32 v9, v4", "s_waitcnt lgkmcnt(0)",
             "buffer_store_dwordx2 v[8:9], v6, s[12:15], 0 offen", "s_endpgm"]
    xy = (10 << 1) | TGID_X | TGID_Y | (1 << 11)
    by_hand = aot.lower(pitch, (4, 4, 1), table_reg=8, descriptor_offset=0, group_reg=10, group_reg_y=11)
    assert aot.lower(pitch, (4, 4, 1), table_reg=8, descriptor_offset=0, rsrc2=xy) == by_hand
    rejects("Unverified dispatch index", aot.lower, pitch, (4, 4, 1), table_reg=8, descriptor_offset=0,
            rsrc2=xy & ~(3 << 11))
    print("controls: group registers and wave size only with rsrc2; table in the user SGPRs; v1 only with TIDIG >= 1")


def check_binary(llvm_mc):
    for name, threads, _, _ in CASES:
        run = subprocess.run([llvm_mc, "-arch=amdgcn", "-mcpu=gfx1013", "-show-encoding"],
                             input="\n".join(program(threads)) + "\n", capture_output=True, text=True)
        if run.returncode or "error" in run.stderr:
            raise AssertionError(f"{name}: {run.stderr}")
    print("fixture programs assemble for gfx1013")


def check_draw(directory, dxc, renderer, backend):
    controls()
    for name, threads, wave, groups in CASES:
        source = aot.lower(program(threads), threads, **binding(wave))
        for variant, text in (("", source), ("_bit20", source.replace("<< 6u))", "<< 20u))"))):
            src, cso, case = (directory / f"{name}{variant}.{ext}" for ext in ("hlsl", "cso", "case"))
            src.write_text(text, encoding="ascii")
            subprocess.run([dxc, "-T", "cs_6_0", "-E", "main", "-Fo", str(cso), str(src)], check=True)
            case.write_bytes(struct.pack("<321I", groups, *expected(threads, wave, groups)))
            run = subprocess.run([renderer, backend, "--compute-store-case", str(cso), str(case)],
                                 capture_output=True, text=True)
            if run.returncode == 77:
                print(run.stdout + run.stderr)
                return 77
            multi_wave = threads > wave
            if not variant:
                if run.returncode:
                    raise AssertionError(f"{name}\n{run.stdout}\n{run.stderr}")
                debug = next((line for line in (run.stdout + run.stderr).splitlines() if "debug_errors=" in line), "")
                print(f"{name}: {groups} groups of {threads} at wave{wave} exact {debug.strip()}")
            elif multi_wave:
                # A later wave's index sits in bits 11:6, so the bit-20 layout must read differently.
                if run.returncode != 1 or "expected=" not in run.stderr:
                    raise AssertionError(f"{name}: the bit-20 layout was not detected\n{run.stderr}")
                print(f"{name}: wave index at bit 20 mismatches, as required")
    return 0


def main():
    if len(sys.argv) == 1:
        controls()
        return 0
    mode, *args = sys.argv[1:]
    if mode == "binary":
        check_binary(*args)
        return 0
    if mode == "draw":
        with tempfile.TemporaryDirectory() as tmp:
            return check_draw(Path(tmp), *args)
    raise SystemExit(__doc__)


if __name__ == "__main__":
    sys.exit(main())
