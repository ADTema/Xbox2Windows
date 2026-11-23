"""Main-image TLS slot 0: a /GA EXE under a Windows launch, and under pe_map_run_main with explicit participants.

cpu_exe_tls_slot0 is a CRT-free EXE compiled with /GA, so its thread-local accesses read slot 0 of
ThreadLocalStoragePointer without loading _tls_index (tests/cpu/exe_tls_slot0.cpp). Its TLS callback and
each of its threads (the initial thread and two workers) check whether slot 0 holds the image's block;
only then does a thread check its template copy, write the whole 0x1400-byte array and validate the heap.
The rule and the fixture shape follow MoonYueya's notes on issue #870.

Two modes, registered as two tests, keep the evidence separate:

windows: the EXE launched by Windows, where it owns index 0. The log is the expected guest log.

mapped: cpu_exe_tls_slot0_host, a CRT-free host whose own TLS block owns slot 0, maps the EXE and starts
it in one process per scenario (tests/cpu/exe_tls_slot0_host.cpp). In every scenario a reader thread that
never participates samples its own slot 0 and sentinel from before the map until after release and must
never see them change.
- main: pe_map_run_main; the guest log equals the Windows log; a host thread enters and leaves; release
  is accepted once.
- alive: a host participant is still entered at the first release, which returns 2 and changes nothing;
  after it leaves, the second release is accepted.
- exited: a host participant is ended with TerminateThread. Release confirms the exit from its thread
  handle and is accepted.
- untracked: MAIN_TRACKED host threads enter, so the last finds the participant table full and has no
  handle. It cannot be inspected, so the first release is refused until it leaves (the deterministic
  inspection-failure case).
- paused: cpu_exe_tls_slot0_pause's worker c pauses inside the image's code. The first release is refused
  with the image still committed, its unwind data registered, its carrier loaded and slot 0 unchanged; c
  then resumes, finds its own block and values, returns, and the second release is accepted.
- plain (negative control): pe_map_run leaves the host's block in slot 0, so every slot-0 check fails.
Every accepted release must leave the image freed, its unwind data gone and its carrier unloaded, and a
further release must return 0.
"""

import argparse
from pathlib import Path
import re
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory

TIMEOUT = 60
EXPECTED = "m1=yy m:yyyy a2=yy a:yyyy a3=y- b2=yy b:yyyy b3=y- X=0"
PLAIN = "m1=n- m:n--- a2=n- a:n--- a3=n- b2=n- b:n--- b3=n- X=8"
MAIN_TRACKED = 64
PAUSED = EXPECTED.replace(" X=0", " c2=yy c:yyyy X=0")
# stats: installed, restored, exited, refused releases, pending, active, last release (1 accepted), untracked.
# Participants: the starting thread, the guest's workers (a, b and, paused, c) and the host's participants.
SCENARIOS = {
    "main": {"stats": [4, 4, 0, 0, 0, 0, 1, 0], "refused": None, "participant": True, "resumed": None},
    "alive": {"stats": [4, 4, 0, 1, 0, 0, 1, 0], "refused": True, "participant": True, "resumed": None},
    "exited": {"stats": [4, 3, 1, 0, 0, 0, 1, 0], "refused": None, "participant": True, "resumed": None},
    "untracked": {"stats": [3 + MAIN_TRACKED, 3 + MAIN_TRACKED, 0, 1, 0, 0, 1, 0], "refused": True,
                  "participant": True, "resumed": None},
    "paused": {"stats": [5, 5, 0, 1, 0, 0, 1, 0], "refused": True, "participant": True, "resumed": True},
    "plain": {"stats": [0, 0, 0, 0, 0, 0, -1, 0], "refused": None, "participant": None, "resumed": None},
}


def run(command):
    done = subprocess.run(command, capture_output=True, timeout=TIMEOUT)
    text = done.stdout.decode(errors="replace")
    result = {"exit": done.returncode & 0xffffffff, "stderr": done.stderr.decode(), "stdout": text,
              "log": next((line[4:].strip() for line in text.splitlines() if line.startswith("LOG:")), None),
              "host": next((line for line in text.splitlines() if line.startswith("HOST:")), None)}
    if result["host"] and "setup failed" not in result["host"]:
        fields = dict(re.findall(r"(\w+)=(\S+)", result["host"]))
        result["fields"] = fields
        result["stats"] = [int(v) for v in fields["stats"].split(",")]
    return result


def flag(fields, name):
    return {"y": True, "n": False, "-": None}[fields[name]]


def windows(exe):
    with TemporaryDirectory() as temp:
        copy = Path(temp) / Path(exe).name
        shutil.copy(exe, copy)
        result = run([str(copy)])
    print(f"windows: LOG:{result['log']} exit {result['exit']:#x}")
    if (result["log"], result["exit"], result["stderr"]) != (EXPECTED, 0, ""):
        raise AssertionError(f"Windows launch: {result}")
    print("windows: the EXE owns index 0, so slot 0 holds its block on every thread and callback; "
          "template intact, whole-array writes read back, heap valid")


def mapped(mapper, exe, host, paused_exe):
    for scenario, want in SCENARIOS.items():
        image = paused_exe if scenario == "paused" else exe
        result = run([str(host), str(mapper), str(image), scenario])
        print(f"{scenario}: LOG:{result['log']}")
        print(f"{scenario}: {result['host']}")
        if "fields" not in result or result["exit"] or result["stderr"]:
            raise AssertionError(f"{scenario}: host failed: {result}")
        fields = result["fields"]
        problems = []
        log = {"plain": PLAIN, "paused": PAUSED}.get(scenario, EXPECTED)
        if result["log"] != log:
            problems.append(f"guest log {result['log']!r}, expected {log!r}")
        if fields["started"] != "1" or int(fields["exit"], 16) != (8 if scenario == "plain" else 0):
            problems.append(f"started {fields['started']}, guest exit {fields['exit']}")
        if flag(fields, "installed_main") != (scenario != "plain"):
            problems.append(f"installed_main {fields['installed_main']}")
        if not flag(fields, "reader_untouched"):
            problems.append("the non-participating reader saw its slot 0 or sentinel change")
        if flag(fields, "participant") != want["participant"]:
            problems.append(f"participant {fields['participant']}")
        if not flag(fields, "host_tls") or not flag(fields, "heap_valid"):
            problems.append(f"host_tls {fields['host_tls']}, heap_valid {fields['heap_valid']}")
        if flag(fields, "refused") != want["refused"] or flag(fields, "intact_on_refusal") != want["refused"]:
            problems.append(f"refused {fields['refused']}, intact_on_refusal {fields['intact_on_refusal']}: "
                            f"expected {'a refusal with image, unwind data and carrier intact' if want['refused'] else 'none'}")
        if flag(fields, "resumed") != want["resumed"]:
            problems.append(f"resumed {fields['resumed']}")
        if not flag(fields, "cleaned") or not flag(fields, "second_release"):
            problems.append(f"cleaned {fields['cleaned']}, second_release {fields['second_release']}: expected one "
                            "final cleanup (image freed, unwind data gone, carrier unloaded) and a further release 0")
        if result["stats"] != want["stats"]:
            problems.append(f"counters {result['stats']} != {want['stats']} (installed, restored, exited, "
                            "refused, pending, active, last release, untracked)")
        if problems:
            raise AssertionError(f"{scenario}: " + "; ".join(problems))
    print("mapped: the guest log equals the Windows log under pe_map_run_main; the non-participating reader's "
          "slot 0 and sentinel never changed; a participant still entered, without a handle, or paused inside the "
          "image made the first release return 2 with the image, unwind data and carrier intact; once it left, one "
          "release freed everything and a further release returned 0; an exited participant was confirmed from its "
          "handle; plain pe_map_run fails every slot-0 check")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    sub.add_parser("windows").add_argument("exe", type=Path)
    m = sub.add_parser("mapped")
    m.add_argument("mapper", type=Path)
    m.add_argument("exe", type=Path)
    m.add_argument("host", type=Path)
    m.add_argument("paused_exe", type=Path, help="the fixture built with PAUSED_WORKER")
    arguments = parser.parse_args()
    if arguments.mode == "windows":
        windows(arguments.exe)
    else:
        mapped(arguments.mapper, arguments.exe, arguments.host, arguments.paused_exe)
    sys.exit(0)
