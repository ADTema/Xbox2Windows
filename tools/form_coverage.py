"""Count which instruction forms the translation tests cover.

Usage:
    ctest --preset dev --no-tests=error --output-junit <repo>/out/test-results.xml
    python tools/form_coverage.py out/test-results.xml [--json out/coverage.json]

This measures instruction-form coverage only: which forms from a reference list appear in a
source-built fixture whose translation test passed. It is not a measure of how complete a port is;
covering a form in one fixture does not prove every operand variant or any title behavior.

Rules:
- A fixture's forms are covered only when its test passed. A skipped or failed test (or one that is
  not registered) leaves them uncovered; forms held back only by a skip are listed separately.
- Reference lists (denominators) live in docs/coverage/ and are produced by tools/form_reference.py.
Python standard library only.
"""
import argparse
import ast
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "docs" / "coverage"

# The test that proves each CPU fixture was translated. Fixtures that run unchanged (not translated)
# map to None: their forms are known but never covered. A new .asm must be classified here.
CPU_FIXTURES = {
    "branch": "cpu_leaf_aot_branches",
    "direct": "cpu_aot_direct_call",
    "chained": "cpu_aot_chained_ranges",
    "callback": "cpu_aot_object_callback",
    "destroy": "cpu_aot_destroy_contract",
    "create_context": "cpu_aot_context_lifecycle",
    "bink_heap": "cpu_aot_bink_heap",
    "heap_layout": "cpu_aot_heap_layout",
    "version_query": "cpu_aot_version_query",
    "switch": "cpu_aot_jump_tables",
    "register_probe": None,  # measurement harness
    "two_imports": None,     # mapped and run unchanged by pe_map
    "reloc_route": None,     # mapped and run unchanged by pe_map
    "seh_route": None,       # mapped and run unchanged by pe_map
    "tls_route": None,       # mapped and run unchanged by pe_map
}
# Python files under tests/ whose strings contain gfx1013 assembly, and the CTest tests that translate
# and draw them. () means a fixture with no CTest test (ffx_dispatch_aot_check.py needs LLVM 15 and runs
# only in the Linux CI job); None means the strings are not fixtures. New files must be classified here.
SHADER_FIXTURES = {
    "pixel_aot_check.py": ("pixel_aot_warp", "pixel_aot_hardware"),
    "ffx_dispatch_aot_check.py": (),
    "form_coverage_check.py": None,  # this tool's own test data
}

MASM_DIRECTIVES = {"ifdef", "ifndef", "if", "else", "elseif", "endif", "end", "public", "extern",
                   "externdef", "include", "includelib", "option", "align", "even", "org", "assume"}
MASM_DEFINERS = {"proc", "endp", "label", "equ", "db", "dw", "dd", "dq", "byte", "word", "dword",
                 "qword", "segment", "ends", "struct", "macro", "endm", "textequ"}
# MASM condition-code spellings -> iced-x86's canonical mnemonic suffix.
CONDITION_ALIASES = {"z": "e", "nz": "ne", "c": "b", "nae": "b", "nc": "ae", "nb": "ae", "nbe": "a",
                     "na": "be", "nge": "l", "nl": "ge", "nle": "g", "ng": "le", "pe": "p", "po": "np"}
GFX = re.compile(r"(s|v|image|buffer|ds|global|flat|scratch)_[a-z0-9_]+|exp")


def masm_mnemonics(text):
    """Instruction mnemonics in MASM source; both arms of IFDEF/ELSE count (both variants are built)."""
    found = set()
    for line in text.splitlines():
        line = re.sub(r"^\s*\w+::?", "", line.split(";", 1)[0]).strip()  # local or global label
        words = line.lower().split()
        if (not words or words[0].startswith(".") or words[0] in MASM_DIRECTIVES | MASM_DEFINERS
                or (len(words) > 1 and words[1] in MASM_DEFINERS and words[2:3] != ["ptr"])):
            continue
        found.add(x64_canonical(words[0]))
    return found


def x64_canonical(mnemonic):
    for prefix in ("cmov", "set", "j"):
        if mnemonic.startswith(prefix) and mnemonic[len(prefix):] in CONDITION_ALIASES:
            return prefix + CONDITION_ALIASES[mnemonic[len(prefix):]]
    return mnemonic


def gfx_mnemonics(source):
    """First word of each line of gfx1013 assembly found in a Python file's string constants."""
    found = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            for line in node.value.splitlines():
                word = line.strip().split(" ", 1)[0]
                if GFX.fullmatch(word):
                    found.add(word)
    return found


def gfx_forms(mnemonics, reference):
    """Reference forms a fixture mnemonic selects: _e32 is the plain encoding, _e64 is VOP3."""
    wanted = {m if m.endswith("_e64") else m.removesuffix("_e32") for m in mnemonics}
    return {form for form in reference if form[1] in wanted}


def x64_forms(mnemonics, reference):
    return {form for form in reference if form[1] in mnemonics}


def load_reference(name):
    lines = (REFERENCE / name).read_text(encoding="utf-8").splitlines()
    return {tuple(line.split("\t")) for line in lines if line and not line.startswith("#")}


def read_results(junit):
    """CTest JUnit status per test: pass, fail or skip (CTest writes skips as status="notrun")."""
    status = {"run": "pass", "fail": "fail", "notrun": "skip"}
    return {case.get("name"): status.get(case.get("status"), "fail")
            for case in ET.parse(junit).getroot().iter("testcase")}


def fixture_status(results, tests):
    """pass if any listed test passed, skip if none passed but one skipped, otherwise fail/absent."""
    states = [results.get(t) for t in tests if t]
    if "pass" in states:
        return "pass"
    return "skip" if "skip" in states else "fail" if "fail" in states else "absent"


def summarize(reference, fixtures, select):
    """fixtures: {name: (mnemonics, status)}. Returns covered/known counts and per-group detail."""
    covered = set().union(set(), *(select(m, reference) for m, s in fixtures.values() if s == "pass"))
    skipped = set().union(set(), *(select(m, reference) for m, s in fixtures.values() if s == "skip")) - covered
    known = set().union(set(), *(select(m, reference) for m, _ in fixtures.values()))
    groups = {}
    for group, form in sorted(reference):
        g = groups.setdefault(group, {"covered": 0, "total": 0})
        g["total"] += 1
        g["covered"] += (group, form) in covered
    unmatched = sorted(m for m in set().union(set(), *(m for m, _ in fixtures.values()))
                       if not select({m}, reference))
    return {"covered": len(covered), "total": len(reference), "known_in_fixtures": len(known),
            "blocked_by_skip": sorted(f"{g} {f}" for g, f in skipped), "groups": groups,
            "fixture_forms_not_in_reference": unmatched}


def measure(results):
    cpu = {}
    for asm in sorted((ROOT / "tests" / "cpu").glob("*.asm")):
        if asm.stem not in CPU_FIXTURES:
            raise SystemExit(f"Classify the new CPU fixture {asm.name} in CPU_FIXTURES")
        test = CPU_FIXTURES[asm.stem]
        status = fixture_status(results, [test]) if test else "not translated"
        cpu[asm.name] = (masm_mnemonics(asm.read_text(encoding="utf-8")), status)
    shaders = {}
    for py in sorted((ROOT / "tests").glob("*.py")):
        if found := gfx_mnemonics(py.read_text(encoding="utf-8")):
            if py.name not in SHADER_FIXTURES:
                raise SystemExit(f"Classify {py.name}, which contains gfx1013 assembly, in SHADER_FIXTURES")
            tests = SHADER_FIXTURES[py.name]
            if tests is not None:
                shaders[py.name] = (found, fixture_status(results, tests) if tests else "no CTest test")
    x64 = load_reference("x64_zen2.tsv")
    return {
        "note": "Instruction-form coverage of source-built fixtures; not a measure of port completion.",
        "tests": {s: sum(v == s for v in results.values()) for s in ("pass", "fail", "skip")},
        "fixtures": {name: status for name, (_, status) in {**cpu, **shaders}.items()},
        "x64_zen2": summarize(x64, cpu, x64_forms),
        "gfx1013": summarize(load_reference("gfx1013.tsv"), shaders, gfx_forms),
        "gfx1030": summarize(load_reference("rdna2.tsv"), shaders, gfx_forms),
    }


def report(m):
    t = m["tests"]
    lines = [m["note"], f"Tests: {t['pass']} passed, {t['fail']} failed, {t['skip']} skipped.", ""]
    for key, label in (("x64_zen2", "x64 (Zen 2 user-mode mnemonics)"), ("gfx1013", "gfx1013 forms"),
                       ("gfx1030", "gfx1030 (RDNA2) forms")):
        r = m[key]
        lines.append(f"{label}: {r['covered']} of {r['total']} covered "
                     f"({r['known_in_fixtures']} appear in fixtures; {len(r['blocked_by_skip'])} held back by skips)")
    return "\n".join(lines)


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("junit", type=Path)
    parser.add_argument("--json", type=Path, help="also write the full result, per group, as JSON")
    args = parser.parse_args(argv)
    m = measure(read_results(args.junit))
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(m, indent=1) + "\n", encoding="utf-8")
    print(report(m))


if __name__ == "__main__":
    main(sys.argv[1:])
