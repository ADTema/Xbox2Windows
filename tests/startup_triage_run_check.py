"""Tests for tools/startup/triage_run.py using synthetic logs and negative controls."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile


REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLS_STARTUP = REPO_ROOT / "tools" / "startup"
sys.path.insert(0, str(TOOLS_STARTUP))
import triage_run  # noqa: E402


SYNTHETIC_STDERR = """\
x2w-d3d12 Device::slot70 unsupported memory SRV arguments: reason=unsupported_description res{dim=1 fmt=0 size=4096x1x1 mips=1 layout=0x1 flags=0x0 align=0 samples=1/0} view{dim=11 fmt=0 map=0x1688 raw=55667788,11223344,00000000,00000000,00000000,00000000 (acceleration structure views are not supported)} dest=0x00007ff712340000 dest_in_view_heap=1 address=0x00000180deadbeef address_readable=0
x2w-d3d12 Device::slot70 unsupported memory SRV arguments: reason=unsupported_description res{dim=1 fmt=0 size=8192x1x1 mips=1 layout=0x1 flags=0x0 align=0 samples=1/0} view{dim=11 fmt=0 map=0x1688 raw=55667788,11223344,00000000,00000000,00000000,00000000 (acceleration structure views are not supported)} dest=0x00007ff712340080 dest_in_view_heap=1 address=0x00000180cafebabe address_readable=1
x2w-d3d12 Device::slot70 unsupported memory SRV arguments: reason=destination_outside_view_heaps res{dim=3 fmt=98 size=128x128x2 mips=6 layout=0x105 flags=0x300000 align=65536 samples=1/0} view{dim=5 fmt=98 map=0x1688 mostmip=1 mips=5 first=1 count=1 plane=0 clamp=0.5} dest=0x00007ff712341001 dest_in_view_heap=0 address=0x0000018000007000 address_readable=1
x2w-d3d12 Device::slot70 unsupported memory SRV arguments: reason=unreadable_resource res{unreadable} view{unreadable} dest=0x1000 dest_in_view_heap=1 address=0x0 address_readable=0
x2w-noop d3d12_xs!Device::slot44 rcx=0x0000018011112222 rdx=0x0000018033334444 r8=0x0 r9=0x0 ret=sample_app.exe+0x1234 exit=0xe257002c
x2w-trap d3d12_xs!Device::slot99 rcx=0x0000018011112222 rdx=0x0 r8=0x0 r9=0x0 ret=C:\\Users\\alice\\secret\\game.exe+0x4560 exit=0xe2570063
x2w-d3d12 Device::slot10(CreateGraphicsPipelineState) desc=[00 01] riid={1234} -> trap
x2w-d3d12-debug [Device 44] sev=2 id=999 Failed reading C:\\Users\\alice\\secret\\game.exe at 0x00007ff7deadbeef
x2w-dstorage   options=0x1 dest=0x0000018044440000 dest_size=0x1000 source=0x1 offset=0x0 size=0x100 -> zlib failed
x2w-dstorage   options=0x1 dest=0x0000018044441000 dest_size=0x1000 source=0x1 offset=0x200 size=0x100 -> zlib failed
x2w-dstorage   options=0x1 dest=0x0000018044442000 dest_size=0x1000 source=0x1 offset=0x400 size=0x100 -> done
x2w-dstorage Factory::OpenFile path="C:\\Users\\alice\\secret\\data.pak" riid={abcd} -> fail (err 2)
x2w-dstorage StatusArray::GetHResult index=0 -> 0x80004005
x2w-dstorage StatusArray::GetHResult index=1 -> 0x00000000
x2w-runtime 12345678::slot5(0x1, 0x2, 0x3 | 0x4, 0x5) -> 0xffffffff80004005 from +0x100
x2w-runtime 12345678::slot5(0x1, 0x2, 0x3 | 0x4, 0x5) -> 0x80004005 from +0x104
x2w-runtime 12345678::slot6(0x1, 0x2, 0x3 | 0x4, 0x5) -> 0x0 from +0x108
x2w-runtime persistent local storage: local object instead of 0x80070005
"""


def check_aggregation_and_redaction(failures: list[str]) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        logdir = root / "logs"
        logdir.mkdir()
        (logdir / "stderr.txt").write_text(SYNTHETIC_STDERR, encoding="utf-8")

        cache_dir = root / "shader_cache"
        cache_dir.mkdir()
        (cache_dir / "0000000000000001.fail").write_text(
            "image_load_mip tfe\n", encoding="utf-8"
        )
        (cache_dir / "0000000000000002.fail").write_text(
            "image_load_mip tfe\n", encoding="utf-8"
        )
        (cache_dir / "0000000000000003.fail").write_text(
            "fxc ps: /home/alice/secret/shader.hlsl(1,1): error X3000 at 0x00007ff712345678\n",
            encoding="utf-8",
        )

        report = triage_run.triage_run(logdir, shader_cache=cache_dir, max_items=16)

        expected_snippets = [
            "Log files scanned: `1`",
            "| 2 | unsupported_description | 1 | 0 | 11 | 0 | 0x1 | 0x0 |",
            "| 1 | destination_outside_view_heaps | 3 | 98 | 5 | 98 | 0x105 | 0x300000 |",
            "| 1 | unreadable_resource | unreadable | unreadable | unreadable | unreadable | unreadable | unreadable |",
            "| 1 | `x2w-noop d3d12_xs!Device::slot44` |",
            "| 1 | `Device::slot10(CreateGraphicsPipelineState)` |",
            "| 2 | zlib failed |",
            "| 1 | OpenFile: fail (err 2) |",
            "| 1 | `0x80004005` |",
            "| 2 | `12345678::slot5` | `0x80004005` |",
            "| 1 | `persistent_local_storage` | `0x80070005` |",
            "| 2 | `image_load_mip tfe` |",
        ]
        for snippet in expected_snippets:
            if snippet not in report:
                failures.append(f"missing expected summary line: {snippet!r}")

        # Negative controls: sensitive paths, executables, and 64-bit addresses must never leak.
        forbidden = [
            "alice",
            "game.exe",
            "sample_app.exe",
            "C:\\Users",
            "/home/alice",
            "0x00007ff712340000",
            "0x00000180deadbeef",
            "0x00007ff7deadbeef",
            "0x00007ff712345678",
            "data.pak",
        ]
        for secret in forbidden:
            if secret in report:
                failures.append(f"negative control failed: leaked {secret!r} in report")


def check_redaction_helper(failures: list[str]) -> None:
    cases = [
        (r'C:\Users\alice\secret\game.exe', "<path>"),
        (r'"C:\Program Files\My App\title.exe"', '"<path>"'),
        ("/home/alice/dumps/run1/stderr.txt", "<path>"),
        ("/Users/alice/Desktop/tool.exe", "<path>"),
        ("ret=sample_app.exe+0x1234", "ret=<exe>+0x1234"),
        ("ptr=0x00007ff712345678 hr=0x80004005", "ptr=0x<addr> hr=0x80004005"),
    ]
    for raw, want in cases:
        got = triage_run.redact(raw)
        if got != want:
            failures.append(f"redact({raw!r}) = {got!r}, expected {want!r}")


def check_review_regressions(failures: list[str]) -> None:
    # Paths with spaces are redacted whole, in a shader .fail line and in plain text.
    for raw, want in [
        (r"fxc ps: C:\Users\Alice Smith\PrivateTitle\shader.hlsl(1,1): error X3000",
         "fxc ps: <path> error X3000"),
        (r"open C:\Program Files\My App\shader.hlsl failed", "open <path> failed"),
        ("read /home/Alice Smith/cache/x.bin: denied", "read <path> denied"),
    ]:
        got = triage_run.redact(raw)
        if got != want or "Smith" in got or "Program" in got:
            failures.append(f"redact({raw!r}) = {got!r}, expected {want!r}")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        logdir = root / "run"
        logdir.mkdir()
        fail_line = "x2w-dstorage   options=0x1 dest=0x1 dest_size=0x1000 source=0x1 offset=0x0 size=0x100 -> zlib failed\n"
        (logdir / "stderr.txt").write_text(fail_line, encoding="utf-8")
        (logdir / "trap.log").write_text(fail_line, encoding="utf-8")
        report = triage_run.triage_run(logdir)
        if "| 1 | zlib failed |" not in report:
            failures.append("mirrored stderr.txt/trap.log line counted other than once:\n" + report)
        # A genuine repeat (second occurrence only in trap.log) still counts.
        (logdir / "trap.log").write_text(fail_line * 2, encoding="utf-8")
        report = triage_run.triage_run(logdir)
        if "| 2 | zlib failed |" not in report:
            failures.append("repeated trap.log occurrence beyond stderr.txt was dropped:\n" + report)
    # Successful forwarded slots are not "unhandled"; failed ones and untraced calls still are.
    lines = [
        "x2w-d3d12 Device::slot13(0x1, 0x2, 0x3, 0x4, 0x5) -> 0x0\n",
        "x2w-d3d12 Device::slot41(0x1, 0x2, 0x3, 0x4, 0x5) -> 0x0\n",
        "x2w-d3d12 Device::slot14(0x1, 0x2, 0x3, 0x4, 0x5) -> 0x80070057\n",
        "x2w-d3d12 Device::slot15 not implemented\n",
    ]
    unhandled = triage_run.summarize_lines(lines)["d3d12_unhandled"]
    if "Device::slot13" in unhandled or "Device::slot41" in unhandled:
        failures.append(f"successful forwarded slots counted as unhandled: {dict(unhandled)}")
    if "Device::slot14" not in unhandled or "Device::slot15" not in unhandled:
        failures.append(f"failed/untraced slots missing from unhandled: {dict(unhandled)}")


def check_empty_and_missing_dirs(failures: list[str]) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        empty_dir = root / "empty"
        empty_dir.mkdir()
        missing_dir = root / "does_not_exist"

        for target in (empty_dir, missing_dir):
            report = triage_run.triage_run(target, shader_cache=missing_dir)
            if "Log files scanned: `0`" not in report:
                failures.append(f"expected 0 scanned files for {target}")
            if "_None observed._" not in report:
                failures.append(f"expected '_None observed._' for {target}")


def check_cli_invocation(failures: list[str]) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        log_file = Path(tmp) / "single.log"
        log_file.write_text(
            "x2w-dstorage   options=0x1 dest=0x0000018000001000 dest_size=0x10 "
            "source=0x1 offset=0x0 size=0x10 -> read failed\n",
            encoding="utf-8",
        )
        proc = subprocess.run(
            [sys.executable, "-B", str(TOOLS_STARTUP / "triage_run.py"), str(log_file), "--max-items", "4"],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            failures.append(f"CLI exited with {proc.returncode}: {proc.stderr}")
        elif "| 1 | read failed |" not in proc.stdout:
            failures.append(f"CLI output missing expected row: {proc.stdout!r}")


def main() -> int:
    failures: list[str] = []
    check_aggregation_and_redaction(failures)
    check_redaction_helper(failures)
    check_review_regressions(failures)
    check_empty_and_missing_dirs(failures)
    check_cli_invocation(failures)
    for item in failures:
        print("FAIL", item)
    print(f"startup triage_run checks: {len(failures)} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
