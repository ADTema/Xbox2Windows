"""Check tools/form_coverage.py: its reference lists (denominators), one fixture-to-instruction example,
and how skipped and failed tests change the count. Needs requirements-dev.txt (iced-x86); no Windows."""
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import form_coverage as fc
import form_reference as fr

ENCODINGS = {"DPP16", "DPP8", "DS", "EXP", "FLAT", "MIMG", "MTBUF", "MUBUF", "SDWA", "SMEM", "SOP1", "SOP2",
             "SOPC", "SOPK", "SOPP", "VINTRP", "VOP1", "VOP2", "VOP3", "VOP3P", "VOPC"}


def check_denominators():
    for name in ("x64_zen2.tsv", "gfx1013.tsv", "rdna2.tsv"):
        lines = (fc.REFERENCE / name).read_text(encoding="utf-8").splitlines()
        count, source = int(lines[0].split()[1]), lines[0]
        assert "Source:" in source and len(lines) - 1 == count == len(set(lines[1:])), name
    # x64: the committed list is exactly what iced-x86 yields for Zen 2 user mode today.
    assert fc.load_reference("x64_zen2.tsv") == fr.x64_forms()
    # gfx: every form sits under a real encoding with a name that encoding allows.
    for name in ("gfx1013.tsv", "rdna2.tsv"):
        reference = fc.load_reference(name)
        assert {group for group, _ in reference} == ENCODINGS, name
        assert ("SOPP", "s_endpgm") in reference and ("EXP", "exp") in reference
    gfx1013, rdna2 = fc.load_reference("gfx1013.tsv"), fc.load_reference("rdna2.tsv")
    assert ("SMEM", "s_atomic_add") in gfx1013 and ("SMEM", "s_atomic_add") not in rdna2
    # The LLVM syntax-doc parser: short headings, operand-less instructions, and the trailing index.
    with tempfile.TemporaryDirectory() as tmp:
        doc = Path(tmp) / "sample.rst"
        doc.write_text("DS\n--\n\n.. parsed-literal::\n\n    ds_nop\n    ds_add_u32     vaddr, vdata\n\n"
                       "SOPP\n----\n\n    s_endpgm\n\n.. toctree::\n    :hidden:\n\n    gfx10_vdst_123\n")
        assert fr.llvm_forms(doc) == {("DS", "ds_nop"), ("DS", "ds_add_u32"), ("SOPP", "s_endpgm")}
        doc.write_text("DPP8\n----\n\n    ds_nop\n")
        try:
            fr.llvm_forms(doc)
        except AssertionError:
            pass
        else:
            raise AssertionError("a form filed under the wrong encoding was accepted")


def check_example():
    """tests/cpu/branch.asm -> eight x64 forms, counted only while cpu_leaf_aot_branches passes."""
    branch = fc.masm_mnemonics((fc.ROOT / "tests/cpu/branch.asm").read_text(encoding="utf-8"))
    assert branch == {"mov", "cmp", "jb", "jae", "add", "jmp", "sub", "ret"}, branch  # jae: INVERT_BRANCH build
    reference = fc.load_reference("x64_zen2.tsv")
    assert fc.x64_forms(branch, reference) == {("Integer", m) for m in branch}

    passed = fc.measure({"cpu_leaf_aot_branches": "pass"})["x64_zen2"]
    skipped = fc.measure({"cpu_leaf_aot_branches": "skip"})["x64_zen2"]
    failed = fc.measure({"cpu_leaf_aot_branches": "fail"})["x64_zen2"]
    assert passed["covered"] == 8 and passed["groups"]["Integer"]["covered"] == 8
    assert skipped["covered"] == 0 and skipped["blocked_by_skip"] == sorted(f"Integer {m}" for m in branch)
    assert failed["covered"] == 0 and failed["blocked_by_skip"] == []
    # A skip never adds coverage, even when another passing fixture already covers the same form.
    both = fc.measure({"cpu_leaf_aot_branches": "skip", "cpu_aot_direct_call": "pass"})["x64_zen2"]
    direct = fc.masm_mnemonics((fc.ROOT / "tests/cpu/direct.asm").read_text(encoding="utf-8"))
    assert both["covered"] == len(fc.x64_forms(direct, reference))
    assert both["blocked_by_skip"] == sorted(f"Integer {m}" for m in branch - direct)

    # gfx1013: _e32 selects the plain encoding, _e64 the VOP3 form; any passing adapter counts.
    gfx = fc.load_reference("gfx1013.tsv")
    assert fc.gfx_forms({"v_interp_p1_f32_e32", "v_fmac_f32_e64", "exp"}, gfx) == {
        ("VINTRP", "v_interp_p1_f32"), ("VOP3", "v_fmac_f32_e64"), ("EXP", "exp")}
    assert fc.fixture_status({"pixel_aot_warp": "pass", "pixel_aot_hardware": "skip"},
                             ("pixel_aot_warp", "pixel_aot_hardware")) == "pass"
    assert fc.fixture_status({"pixel_aot_hardware": "skip"}, ("pixel_aot_warp", "pixel_aot_hardware")) == "skip"


def check_jump_tables():
    """tests/cpu/switch.asm (#86): a skipped cpu_aot_jump_tables run contributes zero covered forms."""
    switch = fc.masm_mnemonics((fc.ROOT / "tests/cpu/switch.asm").read_text(encoding="utf-8"))
    assert switch == {"add", "cmp", "imul", "ja", "jmp", "jne", "lea", "mov", "movsxd", "movzx", "neg", "not",
                      "ret", "sar", "shl", "shr", "sub", "xor"}, sorted(switch)
    assert fc.CPU_FIXTURES["switch"] == "cpu_aot_jump_tables"
    passed = fc.measure({"cpu_aot_jump_tables": "pass"})["x64_zen2"]
    skipped = fc.measure({"cpu_aot_jump_tables": "skip"})["x64_zen2"]
    assert passed["covered"] == len(switch) == 18
    assert skipped["covered"] == 0 and skipped["blocked_by_skip"] == sorted(f"Integer {m}" for m in switch)
    # Next to a passing fixture, the skipped run still adds nothing: only branch.asm's forms count.
    branch = fc.masm_mnemonics((fc.ROOT / "tests/cpu/branch.asm").read_text(encoding="utf-8"))
    mixed = fc.measure({"cpu_aot_jump_tables": "skip", "cpu_leaf_aot_branches": "pass"})["x64_zen2"]
    assert mixed["covered"] == len(branch)
    assert mixed["blocked_by_skip"] == sorted(f"Integer {m}" for m in switch - branch)


def check_parsing():
    with tempfile.TemporaryDirectory() as tmp:
        junit = Path(tmp) / "results.xml"
        junit.write_text('<testsuite><testcase name="a" status="run"/><testcase name="b" status="fail"/>'
                         '<testcase name="c" status="notrun"/></testsuite>', encoding="utf-8")
        assert fc.read_results(junit) == {"a": "pass", "b": "fail", "c": "skip"}
    asm = ("x PROC FRAME\n    .endprolog\nIFDEF A\n    jae short l\nELSE\n    jnz short l\nENDIF\n"
           "l:  mov DWORD PTR [rdx], eax ; c\ng:: ud2\nvalue DQ 0\n    dd 1\n    ret\nx ENDP\nEND\n")
    assert fc.masm_mnemonics(asm) == {"jae", "jne", "mov", "ud2", "ret"}
    source = 'p = ["s_mov_b32 m0, s24", "exp mrt0 v1", "not asm"]\nq = "image_sample v[0:3]\\ns_endpgm"'
    assert fc.gfx_mnemonics(source) == {"s_mov_b32", "exp", "image_sample", "s_endpgm"}
    # Every repository fixture is classified, and the report never calls coverage completion.
    full = fc.measure({})
    assert "not a measure of port completion" in fc.report(full)
    assert full["x64_zen2"]["covered"] == full["gfx1013"]["covered"] == 0


if __name__ == "__main__":
    check_denominators()
    check_example()
    check_jump_tables()
    check_parsing()
    print("form coverage checks passed")
