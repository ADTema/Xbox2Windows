"""Check pe_run_package.py --trap-missing against a source-built EXE.

The EXE imports trap_fixture.dll!trap_fixture_alpha and !trap_fixture_beta, which no
package provides, and reads its mode from TRAP_FIXTURE_MODE (see trap_missing_exe.cpp).

- Without --trap-missing the runner refuses the package before mapping, as before.
- With it, the call to alpha ends the process with trap 1 and names that import; the
  call to beta ends it with trap 2. Neither trap returns to the caller (0xBAD).
- When the EXE calls neither, its own exit code is reported and both traps are unhit.
- --trap-missing cannot be combined with --preflight-only.
"""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "pe_run_package.py"
sys.path.insert(0, str(ROOT / "tools"))
from pe_run_package import TRAP_EXIT_BASE  # noqa: E402

EXE = "trap_missing_exe.exe"
ALPHA = "trap_fixture.dll!trap_fixture_alpha"
BETA = "trap_fixture.dll!trap_fixture_beta"
HEADER = ("trap-missing: 2 unresolved external(s) bound to terminating traps; "
          "diagnostic only, not providers")
LISTING = [HEADER, f"  trap 1 (exit {TRAP_EXIT_BASE | 1:#x}): {ALPHA}",
           f"  trap 2 (exit {TRAP_EXIT_BASE | 2:#x}): {BETA}"]
TIMEOUT = 60


def run(mapper, package, *flags, mode=None):
    env = dict(os.environ)
    env.pop("TRAP_FIXTURE_MODE", None)
    if mode is not None:
        env["TRAP_FIXTURE_MODE"] = mode
    command = [sys.executable, "-B", str(TOOL), str(mapper), str(package), EXE,
               "--system", "kernel32.dll", *flags]
    done = subprocess.run(command, capture_output=True, text=True, env=env, timeout=TIMEOUT)
    return done.returncode & 0xFFFFFFFF, done.stdout, done.stderr.splitlines()


def expect(label, actual, expected):
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected!r}, got {actual!r}")


def check(mapper, exe):
    with TemporaryDirectory() as temp:
        package = Path(temp)
        shutil.copyfile(exe, package / EXE)

        code, out, err = run(mapper, package)
        expect("default exit", code, 1)
        expect("default stdout", out, "")
        expect("default stderr", err,
               [f"2 unresolved external symbol(s), first {EXE}: {ALPHA}"])
        print("default: refused before mapping with 2 unresolved externals")

        for mode, number, label in ((None, 1, ALPHA), ("alpha", 1, ALPHA), ("beta", 2, BETA)):
            code, out, err = run(mapper, package, "--trap-missing", mode=mode)
            expect(f"{mode} exit", code, TRAP_EXIT_BASE | number)
            expect(f"{mode} stdout", out, "")
            expect(f"{mode} stderr", err, [*LISTING, f"trap {number}: {EXE}: {label}"])
            print(f"mode {mode or 'unset'}: trap {number} named {label} and ended the process with {code:#x}")

        code, out, err = run(mapper, package, "--trap-missing", mode="none")
        expect("none exit", code, 0)
        expect("none stderr", err, LISTING)
        expect("none result", json.loads(out), {
            "image_order": [EXE], "entry_executed": True, "exit_code": 0x7A0,
            "unhit_traps": [ALPHA, BETA],
        })
        print("mode none: the EXE returned 0x7a0 and both traps were reported unhit")

        code, out, err = run(mapper, package, "--trap-missing", "--preflight-only")
        expect("combined exit", code, 2)
        if not any("not allowed with argument" in line for line in err):
            raise AssertionError(f"combined flags: {err!r}")
        print("--trap-missing with --preflight-only: refused by the argument parser")

        expect("package contents", sorted(p.name for p in package.iterdir()), [EXE])
    print("trap-missing checks passed")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: trap_missing_check.py PE_MAP_DLL TRAP_MISSING_EXE")
    check(Path(sys.argv[1]).resolve(strict=True), Path(sys.argv[2]).resolve(strict=True))
