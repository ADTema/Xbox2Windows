"""Measure progress from the repository and a CTest JUnit file; write the dashboard, badges and history.

Usage: ctest --preset dev --no-tests=error --output-junit <repo>/out/test-results.xml
       python tools/progress.py out/test-results.xml
       python tools/progress.py --self-test

Every number is counted, not estimated:
- Reference coverage: instruction forms from docs/progress/reference/*.tsv (generated from LLVM's and
  iced-x86's instruction tables by tools/progress_reference.py) that appear in a fixture whose
  translation test passed.
- Fixture coverage: forms used by fixtures we wrote, handled when such a fixture's test passed. This
  total grows as we add fixtures, so percentages read "of the cases we know about".
"""
import ast
import datetime
import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from progress_svg import render

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "progress"
GREEN, YELLOW, RED, BLUE = "#2ea043", "#d29922", "#f85149", "#1f6feb"

# Which test proves each CPU fixture was lifted correctly. Fixtures that are only run natively (not
# translated) map to None: their instructions count as known but not handled. A new .asm file must be
# added here, so coverage can't silently go stale.
CPU_LIFTED_BY = {
    "branch": "cpu_leaf_aot_branches",
    "direct": "cpu_aot_direct_call",
    "chained": "cpu_aot_chained_ranges",
    "callback": "cpu_aot_object_callback",
    "destroy": "cpu_aot_destroy_contract",
    "create_context": "cpu_aot_context_lifecycle",
    "bink_heap": "cpu_aot_bink_heap",
    "heap_layout": "cpu_aot_heap_layout",
    "version_query": "cpu_aot_version_query",
    "register_probe": None,  # measurement harness
    "reloc_route": None,     # mapped and run unchanged by pe_map
    "seh_route": None,       # mapped and run unchanged by pe_map
    "tls_route": None,       # mapped and run unchanged by pe_map
}
# Python files holding gfx1013 assembly fixtures, and the Windows tests that translate and draw them.
# ffx_dispatch_aot_check.py needs LLVM 15 and runs only in the Linux CI job, so it has no CTest test.
SHADER_VERIFIED_BY = {
    "pixel_aot_check.py": r"^pixel_aot_(warp|hardware)$",
}
TEST_AREAS = [("CPU translation", r"^cpu_"), ("Shader translation", r"^(pixel_aot|bc7_draw|shader_metadata)_"),
              ("GPU hardware", r"_hardware$"), ("GPU WARP", r"_warp$"), ("PE, script, heap", r"")]
MASM_DIRECTIVES = {"ifdef", "ifndef", "if", "else", "elseif", "endif", "end", "public", "extern",
                   "externdef", "include", "includelib", "option", "align", "even", "org", "assume"}
MASM_DEFINERS = {"proc", "endp", "label", "equ", "db", "dw", "dd", "dq", "byte", "word", "dword",
                 "qword", "segment", "ends", "struct", "macro", "endm", "textequ"}
# MASM condition-code spellings -> iced-x86's canonical mnemonic suffix.
CONDITION_ALIASES = {"z": "e", "nz": "ne", "c": "b", "nae": "b", "nc": "ae", "nb": "ae", "nbe": "a",
                     "na": "be", "nge": "l", "nl": "ge", "nle": "g", "ng": "le", "pe": "p", "po": "np"}
GFX = re.compile(r"(s|v|image|buffer|ds|global|flat|scratch)_[a-z0-9_]+|exp")
THROW = re.compile(r"\braise\b.*(unsupported|unknown|not supported)", re.I)


def masm_mnemonics(text):
    found = set()
    for line in text.splitlines():
        line = re.sub(r"^\s*\w+::?", "", line.split(";", 1)[0]).strip()  # local or global label
        words = line.lower().split()
        if (not words or words[0].startswith(".") or words[0] in MASM_DIRECTIVES | MASM_DEFINERS
                or (len(words) > 1 and words[1] in MASM_DEFINERS and words[2:3] != ["ptr"])):
            continue
        found.add(words[0])
    return found


def x64_canonical(mnemonic):
    for prefix in ("cmov", "set", "j"):
        if mnemonic.startswith(prefix) and mnemonic[len(prefix):] in CONDITION_ALIASES:
            return prefix + CONDITION_ALIASES[mnemonic[len(prefix):]]
    return mnemonic


def gfx_mnemonics(source):
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


def load_reference(name):
    lines = (OUT / "reference" / name).read_text(encoding="utf-8").splitlines()
    return {tuple(line.split("\t")) for line in lines if line and not line.startswith("#")}


def read_results(junit):
    status = {"run": "pass", "fail": "fail", "notrun": "skip"}
    return {case.get("name"): status.get(case.get("status"), "fail")
            for case in ET.parse(junit).getroot().iter("testcase")}


def coverage(fixtures, verified):
    """fixtures: {name: mnemonics}; verified: {name: bool}. Returns (handled, known) sets."""
    known = set().union(*fixtures.values())
    handled = set().union(*(m for name, m in fixtures.items() if verified[name]))
    return handled, known


def reference_coverage(reference, handled):
    groups = {}
    for group, form in reference:
        g = groups.setdefault(group, {"done": 0, "total": 0})
        g["total"] += 1
        g["done"] += (group, form) in handled
    return {"done": sum(g["done"] for g in groups.values()), "total": len(reference), "groups": groups}


def measure(results):
    cpu = {}
    for asm in sorted((ROOT / "tests" / "cpu").glob("*.asm")):
        if asm.stem not in CPU_LIFTED_BY:
            raise SystemExit(f"Classify new CPU fixture {asm.name} in CPU_LIFTED_BY")
        cpu[asm.stem] = {x64_canonical(m) for m in masm_mnemonics(asm.read_text(encoding="utf-8"))}
    cpu_handled, cpu_known = coverage(cpu, {n: results.get(CPU_LIFTED_BY[n]) == "pass" for n in cpu})

    shaders = {py.name: found for py in sorted((ROOT / "tests").glob("*.py"))
               if (found := gfx_mnemonics(py.read_text(encoding="utf-8")))}
    shader_ok = {name: any(results.get(t) == "pass" for t in results
                           if name in SHADER_VERIFIED_BY and re.match(SHADER_VERIFIED_BY[name], t))
                 for name in shaders}
    shader_handled, shader_known = coverage(shaders, shader_ok) if shaders else (set(), set())

    x64_ref = load_reference("x64_zen2.tsv")
    refs = {
        "x64": reference_coverage(x64_ref, {f for f in x64_ref if f[1] in cpu_handled}),
        "gfx1013": reference_coverage(r := load_reference("gfx1013.tsv"), gfx_forms(shader_handled, r)),
        "rdna2": reference_coverage(r := load_reference("rdna2.tsv"), gfx_forms(shader_handled, r)),
    }

    areas, claimed = [], set()
    for label, pattern in TEST_AREAS:
        names = [t for t in results if t not in claimed and re.search(pattern, t)]
        claimed.update(names)
        areas.append({"label": label, **{s: sum(results[t] == s for t in names) for s in ("pass", "skip", "fail")}})

    throws = {}
    for py in sorted((ROOT / "tools").glob("*.py")):
        if not py.stem.startswith("progress"):
            if count := sum(bool(THROW.search(line)) for line in py.read_text(encoding="utf-8").splitlines()):
                throws[py.name] = count

    return {
        "tests": {s: sum(v == s for v in results.values()) for s in ("pass", "fail", "skip")} | {"total": len(results)},
        "areas": areas,
        "refs": refs,
        "fixtures": {"x64": {"done": len(cpu_handled), "total": len(cpu_known), "missing": sorted(cpu_known - cpu_handled)},
                     "gfx1013": {"done": len(shader_handled), "total": len(shader_known),
                                 "missing": sorted(shader_known - shader_handled)}},
        "throws": throws,
    }


def pct(done, total):
    return f"{100 * done / total:.1f}%" if total else "n/a"


def badge(label, value, color):
    lw, vw = 6 * len(label) + 10, 6 * len(value) + 10
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{lw + vw}" height="20" role="img" '
            f'aria-label="{label}: {value}"><title>{label}: {value}</title>'
            f'<rect width="{lw}" height="20" fill="#555"/><rect x="{lw}" width="{vw}" height="20" fill="{color}"/>'
            f'<g fill="#fff" font-family="Verdana,DejaVu Sans,sans-serif" font-size="11" text-anchor="middle">'
            f'<text x="{lw / 2}" y="14">{label}</text><text x="{lw + vw / 2}" y="14">{value}</text></g></svg>\n')


def dashboard_data(m, commit):
    t, refs, fx = m["tests"], m["refs"], m["fixtures"]
    badges = [
        ("tests", f"{t['pass']}/{t['total']} pass, {t['fail']} fail", GREEN if not t["fail"] else RED),
        ("x64 Zen 2", f"{refs['x64']['done']}/{refs['x64']['total']}", BLUE),
        ("gfx1013", f"{refs['gfx1013']['done']}/{refs['gfx1013']['total']}", BLUE),
        ("RDNA2", f"{refs['rdna2']['done']}/{refs['rdna2']['total']}", BLUE),
        ("fixture forms", f"{fx['x64']['done'] + fx['gfx1013']['done']}/{fx['x64']['total'] + fx['gfx1013']['total']}",
         GREEN),
    ]
    titles = {"x64": "x64 (Zen 2) instruction kinds lifted", "gfx1013": "gfx1013 reference forms translated",
              "rdna2": "RDNA2 (gfx1030) reference forms translated"}
    return {
        "title": "Xbox2Windows progress",
        "subtitle": "Counted from code and test results, not estimated. A form counts once a fixture using it "
                    "passes its translation test.",
        "badges": [{"label": label, "value": value, "color": color} for label, value, color in badges],
        "treemaps": [{"title": f"{titles[k]}: {pct(r['done'], r['total'])} ({r['done']}/{r['total']})",
                      "groups": r["groups"]} for k, r in refs.items()],
        "bars": [
            {"title": f"Tests by area ({t['total']})",
             "rows": [{"label": a["label"], "text": f"{a['pass']}/{a['pass'] + a['skip'] + a['fail']}",
                       "segments": [{"value": a["pass"], "color": GREEN}, {"value": a["skip"], "color": YELLOW},
                                    {"value": a["fail"], "color": RED}]} for a in m["areas"]],
             "legend": [{"text": "pass", "color": GREEN}, {"text": "skip", "color": YELLOW},
                        {"text": "fail", "color": RED}]},
            {"title": f"Unsupported-instruction throw sites ({sum(m['throws'].values())})",
             "rows": [{"label": name, "text": str(n), "segments": [{"value": n, "color": YELLOW}]}
                      for name, n in sorted(m["throws"].items(), key=lambda kv: -kv[1])]},
        ],
        "lists": [{"title": f"Forms our fixtures use that no passing translation covers "
                            f"({len(fx['x64']['missing']) + len(fx['gfx1013']['missing'])})",
                   "items": {"x64": fx["x64"]["missing"], "gfx1013": fx["gfx1013"]["missing"]}}],
        "footer": f"Generated by tools/progress.py at commit {commit} on {datetime.date.today().isoformat()}",
    }


def write(m):
    OUT.mkdir(parents=True, exist_ok=True)
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                            capture_output=True, text=True).stdout.strip()
    data = dashboard_data(m, commit)
    (OUT / "dashboard.svg").write_text(render(data), encoding="utf-8")
    t, refs = m["tests"], m["refs"]
    for name, label, value, color in [
            ("tests", "tests", data["badges"][0]["value"], data["badges"][0]["color"]),
            ("cpu", "x64 Zen 2", f"{pct(refs['x64']['done'], refs['x64']['total'])} of known forms", BLUE),
            ("shaders", "gfx1013", f"{pct(refs['gfx1013']['done'], refs['gfx1013']['total'])} of known forms", BLUE)]:
        (OUT / f"badge-{name}.svg").write_text(badge(label, value, color), encoding="utf-8")

    history_file = OUT / "history.json"
    history = json.loads(history_file.read_text(encoding="utf-8")) if history_file.exists() else []
    entry = {"date": datetime.date.today().isoformat(), "commit": commit, "tests": t,
             "refs": {k: {"done": r["done"], "total": r["total"]} for k, r in refs.items()},
             "fixtures": {k: {"done": f["done"], "total": f["total"]} for k, f in m["fixtures"].items()}}
    numbers = lambda e: {k: v for k, v in e.items() if k not in ("date", "commit")}
    if history and numbers(history[-1]) == numbers(entry):
        history[-1] = entry  # same numbers: refresh the date/commit instead of adding a row
    else:
        history.append(entry)
    history_file.write_text(json.dumps(history, indent=1) + "\n", encoding="utf-8")

    def cell(h, key, sub):
        v = h.get(key, {}).get(sub)
        return f"{v['done']}/{v['total']}" if v else "—"

    rows = "\n".join(
        f"| {h['date']} | `{h['commit']}` | {h['tests']['pass']}/{h['tests']['total']} ({h['tests']['fail']} fail, "
        f"{h['tests']['skip']} skip) | {cell(h, 'refs', 'x64')} | {cell(h, 'refs', 'gfx1013')} | "
        f"{cell(h, 'refs', 'rdna2')} |" for h in reversed(history))
    fx = m["fixtures"]
    (OUT / "PROGRESS.md").write_text(f"""# Progress

![Progress dashboard](dashboard.svg)

Generated by `tools/progress.py` from a full CTest run (`ctest --preset dev --no-tests=error
--output-junit <repo>/out/test-results.xml`, then `python tools/progress.py out/test-results.xml`).
Every number is counted, and a run on another machine or adapter can give different test results.

| Metric | Now | Measured as |
|---|---|---|
| Tests | {t['pass']} pass, {t['fail']} fail, {t['skip']} skipped, of {t['total']} | CTest JUnit results |
| x64 (Zen 2) kinds | {refs['x64']['done']}/{refs['x64']['total']} ({pct(refs['x64']['done'], refs['x64']['total'])}) | iced-x86 mnemonics Zen 2 runs in user mode, used by a `tests/cpu/*.asm` fixture whose lifting test passed |
| gfx1013 forms | {refs['gfx1013']['done']}/{refs['gfx1013']['total']} ({pct(refs['gfx1013']['done'], refs['gfx1013']['total'])}) | LLVM 15 gfx1013 instruction forms (per encoding) used by a fixture whose translate-and-draw test passed |
| RDNA2 forms | {refs['rdna2']['done']}/{refs['rdna2']['total']} ({pct(refs['rdna2']['done'], refs['rdna2']['total'])}) | Same, against LLVM 15's gfx1030 list |
| Fixture forms | x64 {fx['x64']['done']}/{fx['x64']['total']}, gfx1013 {fx['gfx1013']['done']}/{fx['gfx1013']['total']} | Forms our own fixtures use; grows as we add fixtures |

Limits: a form counts once any passing fixture contains it, even in a helper the translator didn't lift,
and one passing case doesn't prove every operand variant. The gfx1013 forms only in
`tests/ffx_dispatch_aot_check.py` are verified in upstream's Linux CI (LLVM 15), not on this machine.

## History

| Date | Commit | Tests | x64 Zen 2 | gfx1013 | RDNA2 |
|---|---|---|---|---|---|
{rows}
""", encoding="utf-8")


def self_test():
    asm = ("x PROC FRAME\n    .endprolog\nIFDEF A\n    jae short l\nELSE\n    jnz short l\nENDIF\n"
           "l:  mov DWORD PTR [rdx], eax ; c\ng:: ud2\nvalue DQ 0\n    dd 1\n    ret\nx ENDP\nEND\n")
    found = {x64_canonical(m) for m in masm_mnemonics(asm)}
    assert found == {"jae", "jne", "mov", "ud2", "ret"}, found
    src = 'p = ["s_mov_b32 m0, s24", "exp mrt0 v1", "not asm", "v_fma_f32 v1, v2, v3, v4"]\nq = "image_sample v[0:3]\\ns_endpgm"'
    assert gfx_mnemonics(src) == {"s_mov_b32", "exp", "v_fma_f32", "image_sample", "s_endpgm"}
    ref = {("VOP1", "v_log_f32"), ("VOP3", "v_log_f32_e64"), ("VOP2", "v_fmac_f32"), ("EXP", "exp")}
    assert gfx_forms({"v_log_f32_e32", "v_fmac_f32_e64", "exp"}, ref) == {("VOP1", "v_log_f32"), ("EXP", "exp")}
    assert coverage({"a": {"x", "y"}, "b": {"y", "z"}}, {"a": True, "b": False}) == ({"x", "y"}, {"x", "y", "z"})
    cov = reference_coverage(ref, {("EXP", "exp")})
    assert cov["done"] == 1 and cov["groups"]["EXP"] == {"done": 1, "total": 1}
    print("progress self-test passed")


if __name__ == "__main__":
    if sys.argv[1:] == ["--self-test"]:
        self_test()
    elif len(sys.argv) == 2:
        write(measure(read_results(sys.argv[1])))
        print((OUT / "PROGRESS.md").read_text(encoding="utf-8").split("## History")[0])
    else:
        raise SystemExit(__doc__)
