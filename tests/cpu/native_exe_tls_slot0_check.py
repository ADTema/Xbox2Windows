"""Check that a mapped EXE started as the main image owns TLS slot 0 in every thread.

cpu_exe_tls_slot0 is a CRT-free EXE compiled with /GA, so its thread-local accesses read slot 0 of
ThreadLocalStoragePointer without loading _tls_index (tests/cpu/exe_tls_slot0.cpp). Its template holds
an int and a 0x1400-byte array of 0xFF. Each of its threads (the initial thread and two workers) and its
TLS callback check whether slot 0 holds the image's block; when it does, the thread checks its template
copy, writes the whole array, reads it back and validates the process heap. The rule and the fixture
shape follow MoonYueya's notes on issue #870.

Runs:
- Windows launch: the EXE owns index 0, so every check passes. This is the expected log.
- cpu_exe_tls_slot0_host ... main: a CRT-free host that owns slot 0 itself (its own TLS directory and a
  thread-local sentinel) maps the EXE and starts it with pe_map_run_main. The guest log must equal the
  Windows log. The host checks that slot 0 of its own thread and of a thread that existed before the start
  holds the image's block after the start; that a host thread ended with TerminateThread leaves a stale
  record that pe_map drops, on the attach of a later thread with the same ID when the host observes such
  reuse (it cannot be forced) and otherwise at release; and that after release slot 0 and the host's
  sentinel are the host's again on both threads, with a valid heap. pe_map's counters must show every
  install restored except the terminated thread's, one stale record and no mismatch.
- cpu_exe_tls_slot0_host ... plain (negative control): the same host starts the EXE with pe_map_run,
  which leaves the host's block in slot 0. Every slot-0 check must fail (tls_in_slot0=no) and nothing is
  installed.
"""

import argparse
from pathlib import Path
import re
import shutil
import subprocess
from tempfile import TemporaryDirectory

TIMEOUT = 60
EXPECTED = "m1=yy m:yyyy a2=yy a:yyyy a3=y- b2=yy b:yyyy b3=y- X=0"
# pe_map_run leaves the host's block in slot 0: every slot-0 check fails and nothing else is checked.
PLAIN = "m1=n- m:n--- a2=n- a:n--- a3=n- b2=n- b:n--- b3=n- X=8"
# installed: initial thread, existing thread, two guest workers and the terminated thread, plus the thread
# that reused its ID when reuse was observed. restored: every install but the terminated thread's.
# stale: the terminated thread's record, dropped when its ID attached again or, without reuse, at release
# (without writing to the dead thread's TEB). No mismatch, no live record and no active image afterwards.
MAIN_STATS = {True: [6, 5, 1, 0, 0, 0], False: [5, 4, 1, 0, 0, 0]}
HOST_FLAGS = ("installed_main", "installed_existing", "reuse", "stale_dropped_on_reuse", "host_tls",
              "existing_host_tls", "heap_valid")
REQUIRED = ("installed_main", "installed_existing", "host_tls", "existing_host_tls", "heap_valid")


def parse(done):
    text = done.stdout.decode(errors="replace")
    log = next((line[4:].strip() for line in text.splitlines() if line.startswith("LOG:")), None)
    host = next((line for line in text.splitlines() if line.startswith("HOST:")), None)
    result = {"log": log, "exit": done.returncode & 0xffffffff, "stdout": text, "stderr": done.stderr.decode()}
    if host and "setup failed" not in host:
        fields = dict(re.findall(r"(\w+)=(\S+)", host))
        result["host"] = {key: fields[key] == "y" for key in HOST_FLAGS}
        result["started"] = int(fields["started"])
        result["guest_exit"] = int(fields["exit"], 16)
        result["stats"] = [int(v) for v in fields["stats"].split(",")]
    return result


def native(exe):
    with TemporaryDirectory() as temp:
        copy = Path(temp) / Path(exe).name
        shutil.copy(exe, copy)
        return parse(subprocess.run([str(copy)], capture_output=True, timeout=TIMEOUT))


def hosted(host, mapper, exe, mode):
    return parse(subprocess.run([str(host), str(mapper), str(exe), mode], capture_output=True, timeout=TIMEOUT))


def require(label, condition, result):
    if not condition:
        raise AssertionError(f"{label}: {result}")


def check(mapper, exe, host):
    nat = native(exe)
    print(f"native: LOG:{nat['log']} exit {nat['exit']:#x}")
    require("native launch", (nat["log"], nat["exit"], nat["stderr"]) == (EXPECTED, 0, ""), nat)

    main = hosted(host, mapper, exe, "main")
    print(f"main image: LOG:{main['log']}")
    print(f"main image: {next(line for line in main['stdout'].splitlines() if line.startswith('HOST:'))}")
    require("main image: host setup", "host" in main and main["exit"] == 0 and not main["stderr"], main)
    require("main image: tls_in_slot0 on every thread and callback (guest log differs from Windows)",
            main["log"] == EXPECTED and main["started"] == 1 and main["guest_exit"] == 0, main)
    failed = [flag for flag in REQUIRED if not main["host"][flag]]
    reuse = main["host"]["reuse"]
    if reuse and not main["host"]["stale_dropped_on_reuse"]:
        failed.append("stale_dropped_on_reuse")
    require(f"main image: host checks failed: {failed}", not failed, main)
    expected_stats = MAIN_STATS[reuse]
    require(f"main image: pe_map counters {main['stats']} != {expected_stats} "
            "(installed, restored, stale, mismatched, live records, active)", main["stats"] == expected_stats, main)
    print("main image: the terminated thread's ID was " + ("reused, and its stale record was dropped on that attach"
          if reuse else "not reused within the attempts (not forced; see the host); its stale record was dropped "
          "at release without writing to the dead thread's TEB"))
    print("main image: the guest log equals the Windows launch; slot 0 held the image's block on the initial "
          "thread, a pre-existing thread, both guest workers and their callbacks; after release the host's block and sentinel were back on both "
          f"host threads and the heap was valid; counters {main['stats']}")

    plain = hosted(host, mapper, exe, "plain")
    print(f"plain pe_map_run (control): LOG:{plain['log']}")
    require("plain control: host setup", "host" in plain and plain["exit"] == 0, plain)
    require("plain control: expected tls_in_slot0=no on every check", plain["log"] == PLAIN, plain)
    require("plain control: slot 0 changed or counters moved",
            not plain["host"]["installed_main"] and not plain["host"]["installed_existing"]
            and plain["host"]["host_tls"] and plain["stats"] == [0, 0, 0, 0, 0, 0], plain)
    print("plain pe_map_run (control): every slot-0 check reports no, so the guest's /GA accesses would reach "
          "the host's block; the guest skipped its writes and the host's slot 0 was untouched")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mapper", type=Path)
    parser.add_argument("exe", type=Path)
    parser.add_argument("host", type=Path)
    arguments = parser.parse_args()
    check(arguments.mapper, arguments.exe, arguments.host)
