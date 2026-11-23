"""Compare an EXE's own TLS template and TLS callbacks under a Windows launch and under pe_map_run.

cpu_exe_tls is a CRT-free EXE whose image holds an initialized TLS template that spans a page boundary
(the int and 8 KiB array of tests/cpu/tls_value.cpp) and two TLS callbacks in table order. It prints one
ordered startup log: the callbacks on process attach, the entry point, the main thread's own
observations, then thread attach and detach of two workers that are alive at the same time, and the
exit code (tests/cpu/exe_tls.cpp describes the format). The test launches the EXE with Windows and, in a
child process, maps it with pe_map_image and starts it with pe_map_run. The log and the exit code must
be identical, and must match the expected log, which this script derives from the fixture's rules.

Two negative controls patch copies of the built EXE with the #883 helpers: a swapped callback table
and a template zeroed from its first page boundary. Each must be rejected under both loaders with a
diagnostic that names the callback order or the template.
"""

import argparse
import ctypes
import json
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory

from native_map_check import Mapper, Resolver
from native_tls_value_check import TLS_VALUE, layout, swap_callbacks, written, zero_second_page

TIMEOUT = 30  # per process; longer than the 10 s waits inside the EXE, so its failure code is observed
MAIN_WRITE, A_WRITE, B_WRITE = 20, 50, 60
PROCESS_ATTACH, THREAD_ATTACH, THREAD_DETACH = "1", "2", "3"


def expected_log():
    """The log the fixture must print when every block starts from the template, in its fixed order."""
    fresh, main, a, b = (f"{v:x}" for v in (TLS_VALUE, written(MAIN_WRITE), written(A_WRITE), written(B_WRITE)))

    def callbacks(thread, reason, value):
        return [f"{thread}{reason}1={value}", f"{thread}{reason}3={value}"]

    events = [*callbacks("m", PROCESS_ATTACH, fresh), "E", f"mf={fresh}", f"mw={main}",
              *callbacks("a", THREAD_ATTACH, fresh), f"af={fresh}", f"aw={a}",
              *callbacks("b", THREAD_ATTACH, fresh), f"bf={fresh}", f"bw={b}",
              f"al={a}", *callbacks("a", THREAD_DETACH, a),
              f"bl={b}", *callbacks("b", THREAD_DETACH, b),
              f"ml={main}", f"X={main}"]
    return " ".join(events)


def problems(result):
    """Every way one launch departs from the expected log; empty when it matches.

    Each problem starts with "template" when a thread saw something other than its own copy of the
    template, or "callback order" when the two TLS callbacks ran against the table order."""
    if result["log"] is None:
        return [f"no startup log (exit {result['exit']:#x}): {result}"]
    expected = expected_log().split()
    events = result["log"].split()
    found = []
    # Callbacks: per thread and reason, the caller order and the value each one saw.
    calls, wanted = {}, {}
    for event, target in ((e, calls) for e in events):
        if len(event) > 3 and event[3] == "=" and event[1] in "0123":
            target.setdefault(event[:2], []).append((event[2], event[4:]))
    for event in expected:
        if len(event) > 3 and event[3] == "=" and event[1] in "0123":
            wanted.setdefault(event[:2], []).append((event[2], event[4:]))
    if set(calls) != set(wanted):
        found.append(f"notifications for {sorted(calls)}, expected {sorted(wanted)}")
    for key, seen in calls.items():
        callers = [caller for caller, _ in seen]
        if sorted(callers) != ["1", "3"]:
            found.append(f"{key}: callers {callers}, expected 1 and 3 once each")
        elif callers != ["1", "3"]:
            found.append(f"callback order: {key} ran callers {callers}; the table has 1 before 3")
        values = [value for _, value in seen]
        expected_values = [value for _, value in wanted.get(key, [])]
        if key in wanted and values != expected_values:
            found.append(f"template: callbacks on {key} observed {values}, expected {expected_values}")
    # The threads' own observations and the exit code.
    own = {e.split("=")[0]: e.split("=")[1] for e in events if "=" in e and e[1] in "fwlX="}
    for event in expected:
        if "=" in event and event[1] in "fwl=":
            name, value = event.split("=")
            if own.get(name) != value:
                found.append(f"template: {name} observed {own.get(name)}, expected {value}")
    if result["exit"] != written(MAIN_WRITE):
        found.append(f"template: exit code {result['exit']:#x}, expected {written(MAIN_WRITE):#x}")
    if not found and events != expected:
        found.append(f"log order: {result['log']!r}, expected {expected_log()!r}")
    return found


def observed(done):
    lines = done.stdout.decode().splitlines()
    log = next((line[4:].strip() for line in lines if line.startswith("LOG:")), None)
    return {"log": log, "exit": done.returncode & 0xffffffff, "stderr": done.stderr.decode()}


def native(exe):
    with TemporaryDirectory() as temp:
        copy = Path(temp) / "cpu_exe_tls.exe"
        shutil.copy(exe, copy)
        return observed(subprocess.run([str(copy)], capture_output=True, timeout=TIMEOUT))


def mapped(mapper, exe):
    """pe_map in a child process; its stdout belongs to the guest, the child's result goes to a file."""
    with TemporaryDirectory() as temp:
        result_file = Path(temp) / "result.json"
        done = subprocess.run([sys.executable, "-B", __file__, "--run", str(mapper), str(exe), str(result_file)],
                              capture_output=True, timeout=TIMEOUT)
        if not result_file.exists():
            return {**observed(done), "failure": f"child exited {done.returncode:#x} without a result"}
        child = json.loads(result_file.read_text())
        result = {**observed(done), **child}
        result["exit"] = child["exit"]  # the guest's exit code, returned by pe_map_run
        return result


def run(mapper_path, exe, result_file):
    """Child: map the EXE with its kernel32 imports bound to the host, start it, release it."""
    mapper = Mapper(mapper_path)
    start = ctypes.CDLL(str(mapper_path)).pe_map_run
    start.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]
    start.restype = ctypes.c_int
    system = {}

    def resolve(dll, name, ordinal):
        module = system.setdefault(dll.decode(), ctypes.WinDLL(dll.decode()))
        return ctypes.cast(getattr(module, name.decode()), ctypes.c_void_p).value if name else None

    callback = Resolver(resolve)
    status, detail = ctypes.c_uint32(0xffffffff), ctypes.create_string_buffer(256)
    base = mapper.map(str(exe), callback, ctypes.byref(status), detail, len(detail))
    result = {"failure": None, "started": None, "exit": 0xdeadbeef}
    if not base:
        result["failure"] = [status.value, detail.value.decode()]
    else:
        exit_code = ctypes.c_uint32(0xdeadbeef)
        result["started"] = start(base, ctypes.byref(exit_code))
        result["exit"] = exit_code.value
        sys.stdout.flush()
        result["released"] = mapper.release(base) == 1
    Path(result_file).write_text(json.dumps(result))


def check(mapper, exe):
    info = layout(exe)
    rva, length = info["template"]
    positions = [info["table"].index(c) if c in info["table"] else None for c in info["ours"]]
    if None in positions or positions[0] > positions[1]:
        raise AssertionError(f"callback table {[hex(c) for c in info['table']]} does not hold "
                             f"{[hex(c) for c in info['ours']]} in that order")
    print(f"template: RVA {rva:#x}, {length} bytes; the array crosses the page boundary at RVA "
          f"{info['boundary']:#x} with words {info['below']:#010x} | {info['above']:#010x}; "
          f"the callbacks are entries {positions[0]} and {positions[1]} of {len(info['table'])} in the table")

    nat, map_ = native(exe), mapped(mapper, exe)
    print(f"native: LOG:{nat['log']} exit {nat['exit']:#x}")
    print(f"mapped: LOG:{map_['log']} exit {map_['exit']:#x}")
    for label, result in (("native", nat), ("mapped", map_)):
        found = problems(result)
        if result["stderr"]:
            found.append(f"stderr {result['stderr']!r}")
        if label == "mapped" and (map_.get("failure") or map_.get("started") != 1 or not map_.get("released")):
            found.append(f"pe_map: failure {map_.get('failure')}, started {map_.get('started')}, "
                         f"released {map_.get('released')}")
        if found:
            raise AssertionError(f"{label}: " + "; ".join(found))
    if (nat["log"], nat["exit"]) != (map_["log"], map_["exit"]):
        raise AssertionError(f"native and mapped differ: {nat} != {map_}")
    print("native and pe_map_run print the same log and exit code: both callbacks run in table order on process "
          "attach and on thread attach and detach of two concurrent workers, every thread starts from the "
          f"template and keeps its own writes ({MAIN_WRITE}, {A_WRITE}, {B_WRITE})")

    controls = {"swapped callback table": (swap_callbacks, "callback order"),
                "template zeroed from its page boundary": (zero_second_page, "template")}
    with TemporaryDirectory() as temporary:
        for label, (edit, reason) in controls.items():
            copy = Path(temporary) / f"cpu_exe_tls_{reason.replace(' ', '_')}.exe"
            edit(exe, copy, info)
            for target, result in (("native", native(copy)), ("mapped", mapped(mapper, copy))):
                found = problems(result)
                if not any(problem.startswith(reason) for problem in found):
                    raise AssertionError(f"negative control '{label}' was not detected under {target} "
                                         f"(expected a '{reason}' diagnostic): {found}")
                print(f"negative control '{label}' rejected under {target}: {found[0]}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--run":
        run(*sys.argv[2:5])
    else:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument("mapper", type=Path)
        parser.add_argument("exe", type=Path)
        arguments = parser.parse_args()
        check(arguments.mapper, arguments.exe)
