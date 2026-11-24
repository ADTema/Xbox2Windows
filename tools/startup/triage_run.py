#!/usr/bin/env python3
"""Summarize a startup log directory (and optional shader cache) into redacted Markdown.

Reads raw logs produced by tools/startup/run.ps1 / debug_launch.py and emits a
title-neutral, path-redacted, address-redacted Markdown summary suitable for a
GitHub issue. Uses only the Python 3 standard library.
"""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
import re
import sys
from typing import Iterable


LOG_EXTENSIONS = {".txt", ".log", ".out"}

DSTORAGE_OK_OUTCOMES = {
    "done",
    "empty",
    "inflated",
    "inflated (larger/short)",
    "inflated (chunked stream piece 0)",
    "inflated (slice from stream cache)",
    "bcpack decoded",
    "inflated + bcpack decoded",
}

# Redaction patterns (applied in order from most specific/broadest path to tokens).
RE_QUOTED_WIN_PATH = re.compile(r'"([A-Za-z]:\\[^"\r\n]+|[A-Za-z]:/[^"\r\n]+|\\\\[^\\"\r\n]+\\[^"\r\n]+)"')
# Unquoted paths: directory components may contain single spaces ("Alice Smith"), the final component may not.
_DIR_COMPONENT = r'(?:[^\\/:"\'<>|\r\n=,()]{1,64}[\\/]+)*'
_LAST_COMPONENT = r'[^\s"\'<>|]*'
RE_WIN_PATH = re.compile(
    r'(?:[A-Za-z]:[\\/]+|\\\\[^\\\s"\'<>|]+\\+)' + _DIR_COMPONENT + _LAST_COMPONENT
)
RE_QUOTED_POSIX_PATH = re.compile(
    r'"(/(?:home|Users|mnt|tmp|var|opt|root|srv|private|Volumes)/[^"\r\n]+)"'
)
RE_POSIX_PATH = re.compile(
    r'/(?:home|Users|mnt|tmp|var|opt|root|srv|private|Volumes)/' + _DIR_COMPONENT + r'[^\s"\'<>|]+'
)
RE_EXE_NAME = re.compile(r'\b[A-Za-z0-9_.\-]+\.exe\b', re.IGNORECASE)
RE_ADDR64 = re.compile(r'\b0x[0-9a-fA-F]{9,}\b')

# Log line patterns matching src/startup_stubs/*.
RE_SLOT70 = re.compile(
    r'x2w-d3d12\s+Device::slot70\b.*?\breason=(\S+)\s+res\{([^}]*)\}\s+view\{([^}]*)\}'
)
RE_KV = re.compile(r'(\w+)=([^\s}]+)')

RE_TRAP_TAG = re.compile(r'^(x2w-(?:trap|noop|continue|fail))\s+(\S+)')
RE_D3D12_PIPELINE_TRAP = re.compile(
    r'x2w-d3d12\s+Device::slot(\d+)\((Create(?:Graphics|Compute)PipelineState)\)'
)
RE_D3D12_IID_PASS = re.compile(r'x2w-d3d12\s+Device::slot(\d+)\s+passes an IID:')
RE_D3D12_VIEW_SKIPPED = re.compile(r'x2w-d3d12\s+Device::slot(\d+)\s+view skipped:\s+(.+)$')
RE_D3D12_FORWARDED_RESULT = re.compile(r'::slot\d+\(.*\)\s*->\s*(0x[0-9a-fA-F]+)\s*$')
RE_D3D12_SLOT_CALL = re.compile(r'x2w-d3d12\s+([A-Za-z0-9_]+::slot\d+)\b')
RE_D3D12_REMOVED = re.compile(
    r'x2w-d3d12\s+DEVICE REMOVED,\s+reason\s+(0x[0-9a-fA-F]+),\s+first noticed after\s+(.+)$'
)
RE_D3D12_DEBUG = re.compile(r'x2w-d3d12-debug\s+\[([^\]]+)\]\s+sev=(\d+)\s+id=(\d+)\s+(.+)$')

RE_DSTORAGE_OUTCOME = re.compile(r'x2w-dstorage\s+options=0x[0-9a-fA-F]+.*?->\s+(.+)$')
RE_DSTORAGE_ENTRY_FAIL = re.compile(
    r'x2w-dstorage\s+entry type\s+\d+\s+failed:\s+(.+?)(?:\s+\(options=0x[0-9a-fA-F]+\))?$'
)
RE_DSTORAGE_ZLIB_FAIL = re.compile(r'x2w-dstorage\s+zlib failure:\s+(.+)$')
RE_DSTORAGE_OPENFILE_FAIL = re.compile(r'x2w-dstorage\s+Factory::OpenFile\s+.*?->\s+(fail\b.*)$')
RE_DSTORAGE_HRESULT = re.compile(
    r'x2w-dstorage\s+StatusArray::GetHResult\s+index=\d+\s+->\s+(0x[0-9a-fA-F]+)'
)
RE_DSTORAGE_SIGNAL = re.compile(
    r'x2w-dstorage\s+Queue::EnqueueSignal\s+.*?->\s+(0x[0-9a-fA-F]+)'
)

RE_RUNTIME_CALL = re.compile(
    r'x2w-(?:runtime|api)\s+([0-9a-fA-F]+::slot\d+)(?:\([^)]*\))?\s+->\s+(0x[0-9a-fA-F]+)'
)
RE_RUNTIME_STORAGE = re.compile(
    r'x2w-runtime\s+persistent local storage:\s+local object instead of\s+(0x[0-9a-fA-F]+)'
)
RE_RUNTIME_GAMESAVE = re.compile(
    r'x2w-runtime\s+game save:\s+update refused\s+\(status\s+(-?\d+)\)'
)


def redact(text: str) -> str:
    """Strip local paths, executable names, and 64-bit addresses from a log snippet."""
    out = RE_QUOTED_WIN_PATH.sub('"<path>"', text)
    out = RE_WIN_PATH.sub("<path>", out)
    out = RE_QUOTED_POSIX_PATH.sub('"<path>"', out)
    out = RE_POSIX_PATH.sub("<path>", out)
    out = RE_EXE_NAME.sub("<exe>", out)
    out = RE_ADDR64.sub("0x<addr>", out)
    return out


def _md_cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def _parse_kv_block(block: str) -> dict[str, str]:
    if block.strip() == "unreadable":
        return {"_unreadable": "1"}
    return dict(RE_KV.findall(block))


def _is_failed_hresult(hex_text: str) -> tuple[bool, str]:
    val = int(hex_text, 16) & 0xFFFFFFFF
    return (val & 0x80000000) != 0, f"0x{val:08x}"


def iter_log_files(log_target: Path) -> list[Path]:
    """Return sorted log files under log_target (or [log_target] if it is a file)."""
    if not log_target.exists():
        return []
    if log_target.is_file():
        return [log_target]
    if not log_target.is_dir():
        return []
    files = [
        p
        for p in log_target.rglob("*")
        if p.is_file() and p.suffix.lower() in LOG_EXTENSIONS
    ]
    files.sort()
    return files


def summarize_lines(lines: Iterable[str]) -> dict[str, Counter]:
    """Aggregate startup telemetry counters from an iterable of log lines."""
    slot70_refusals: Counter[tuple[str, str, str, str, str, str, str]] = Counter()
    d3d12_unhandled: Counter[str] = Counter()
    d3d12_debug: Counter[tuple[str, str, str, str]] = Counter()
    dstorage_failures: Counter[str] = Counter()
    dstorage_hresults: Counter[str] = Counter()
    runtime_failures: Counter[tuple[str, str]] = Counter()

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue

        # 1. slot70 memory SRV refusals
        m = RE_SLOT70.search(line)
        if m:
            reason, res_raw, view_raw = m.group(1), m.group(2), m.group(3)
            res = _parse_kv_block(res_raw)
            view = _parse_kv_block(view_raw)
            if "_unreadable" in res:
                dim = fmt = layout = flags = "unreadable"
            else:
                dim = res.get("dim", "?")
                fmt = res.get("fmt", "?")
                layout = res.get("layout", "?")
                flags = res.get("flags", "?")
            if "_unreadable" in view:
                view_dim = view_fmt = "unreadable"
            else:
                view_dim = view.get("dim", "?")
                view_fmt = view.get("fmt", "?")
            slot70_refusals[(reason, dim, fmt, view_dim, view_fmt, layout, flags)] += 1
            continue

        # 2. x2w-trap / x2w-noop / x2w-continue / x2w-fail
        m = RE_TRAP_TAG.match(line)
        if m:
            tag, target = m.group(1), redact(m.group(2))
            d3d12_unhandled[f"{tag} {target}"] += 1
            continue

        # 3. x2w-d3d12-debug
        m = RE_D3D12_DEBUG.search(line)
        if m:
            ctx, sev, msg_id, msg = m.group(1), m.group(2), m.group(3), redact(m.group(4))
            if len(msg) > 120:
                msg = msg[:117] + "..."
            d3d12_debug[(redact(ctx), sev, msg_id, msg)] += 1
            continue

        # 4. x2w-d3d12 unhandled/trapped/skipped slots & device removed
        if "x2w-d3d12" in line:
            m = RE_D3D12_REMOVED.search(line)
            if m:
                d3d12_unhandled[f"DEVICE REMOVED {m.group(1)} after {redact(m.group(2))}"] += 1
                continue
            m = RE_D3D12_PIPELINE_TRAP.search(line)
            if m:
                d3d12_unhandled[f"Device::slot{m.group(1)}({m.group(2)})"] += 1
                continue
            m = RE_D3D12_IID_PASS.search(line)
            if m:
                d3d12_unhandled[f"Device::slot{m.group(1)} (passes IID)"] += 1
                continue
            m = RE_D3D12_VIEW_SKIPPED.search(line)
            if m:
                d3d12_unhandled[f"Device::slot{m.group(1)} view skipped: {redact(m.group(2))}"] += 1
                continue
            m = RE_D3D12_FORWARDED_RESULT.search(line)
            if m and not _is_failed_hresult(m.group(1))[0]:
                continue  # forward_slot()/create_slot() telemetry of a call the desktop device implemented
            m = RE_D3D12_SLOT_CALL.search(line)
            if m:
                d3d12_unhandled[m.group(1)] += 1
                continue

        # 5. x2w-dstorage failures & status HRESULTs
        if "x2w-dstorage" in line:
            m = RE_DSTORAGE_OUTCOME.search(line)
            if m:
                outcome = m.group(1).strip()
                if outcome not in DSTORAGE_OK_OUTCOMES:
                    dstorage_failures[redact(outcome)] += 1
                continue
            m = RE_DSTORAGE_ENTRY_FAIL.search(line)
            if m:
                dstorage_failures[f"entry failed: {redact(m.group(1))}"] += 1
                continue
            m = RE_DSTORAGE_ZLIB_FAIL.search(line)
            if m:
                dstorage_failures["zlib failure"] += 1
                continue
            m = RE_DSTORAGE_OPENFILE_FAIL.search(line)
            if m:
                dstorage_failures[f"OpenFile: {redact(m.group(1))}"] += 1
                continue
            m = RE_DSTORAGE_HRESULT.search(line)
            if m:
                _, norm_hr = _is_failed_hresult(m.group(1))
                dstorage_hresults[norm_hr] += 1
                continue
            m = RE_DSTORAGE_SIGNAL.search(line)
            if m:
                failed, norm_hr = _is_failed_hresult(m.group(1))
                if failed:
                    dstorage_hresults[norm_hr] += 1
                continue

        # 6. x2w-runtime / x2w-api failing methods / HRESULTs
        if "x2w-runtime" in line or "x2w-api" in line:
            m = RE_RUNTIME_CALL.search(line)
            if m:
                failed, norm_hr = _is_failed_hresult(m.group(2))
                if failed:
                    runtime_failures[(m.group(1), norm_hr)] += 1
                continue
            m = RE_RUNTIME_STORAGE.search(line)
            if m:
                _, norm_hr = _is_failed_hresult(m.group(1))
                runtime_failures[("persistent_local_storage", norm_hr)] += 1
                continue
            m = RE_RUNTIME_GAMESAVE.search(line)
            if m:
                runtime_failures[("game_save_update", f"status {m.group(1)}")] += 1
                continue

    return {
        "slot70_refusals": slot70_refusals,
        "d3d12_unhandled": d3d12_unhandled,
        "d3d12_debug": d3d12_debug,
        "dstorage_failures": dstorage_failures,
        "dstorage_hresults": dstorage_hresults,
        "runtime_failures": runtime_failures,
    }


def summarize_shader_cache(cache_dir: Path | None) -> Counter[str]:
    """Count .fail Unsupported(...) / fxc reasons in X2W_SHADER_CACHE."""
    reasons: Counter[str] = Counter()
    if cache_dir is None or not cache_dir.is_dir():
        return reasons
    for fail_path in sorted(cache_dir.glob("*.fail")):
        try:
            text = fail_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        first_line = ""
        for line in text.splitlines():
            stripped = line.strip()
            if stripped:
                first_line = stripped
                break
        if not first_line:
            first_line = "(empty .fail)"
        cleaned = redact(first_line)
        if len(cleaned) > 120:
            cleaned = cleaned[:117] + "..."
        reasons[cleaned] += 1
    return reasons


def _format_table(
    headers: list[str],
    rows: list[list[object]],
    total_unique: int,
    total_events: int,
    max_items: int,
) -> list[str]:
    if not rows:
        return ["_None observed._", ""]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows[:max_items]:
        lines.append("| " + " | ".join(_md_cell(c) for c in row) + " |")
    if total_unique > max_items:
        lines.append(
            f"_Showing top {max_items} of {total_unique} unique entries ({total_events} total events)._"
        )
    lines.append("")
    return lines


def format_markdown(
    summary: dict[str, Counter],
    shader_failures: Counter[str],
    files_scanned: int,
    shader_cache_provided: bool,
    max_items: int,
) -> str:
    """Render aggregated counters as clean-room Markdown."""
    out: list[str] = [
        "## Startup Run Triage Summary",
        "",
        f"- Log files scanned: `{files_scanned}`",
        f"- `slot70` memory SRV refusals: `{sum(summary['slot70_refusals'].values())}` "
        f"({len(summary['slot70_refusals'])} unique)",
        f"- `x2w-d3d12` / trap slot events: `{sum(summary['d3d12_unhandled'].values())}` "
        f"({len(summary['d3d12_unhandled'])} unique)",
        f"- `x2w-d3d12-debug` messages: `{sum(summary['d3d12_debug'].values())}` "
        f"({len(summary['d3d12_debug'])} unique)",
        f"- `x2w-dstorage` failures: `{sum(summary['dstorage_failures'].values())}` "
        f"({len(summary['dstorage_failures'])} unique)",
        f"- `x2w-runtime` failing calls: `{sum(summary['runtime_failures'].values())}` "
        f"({len(summary['runtime_failures'])} unique)",
    ]
    if shader_cache_provided:
        out.append(
            f"- `X2W_SHADER_CACHE` `.fail` shaders: `{sum(shader_failures.values())}` "
            f"({len(shader_failures)} unique reasons)"
        )
    out.append("")

    # 1. slot70 refusals
    out.extend(["### `Device::slot70` Memory SRV Refusals", ""])
    s70 = summary["slot70_refusals"]
    s70_rows = [
        [count, reason, dim, fmt, vdim, vfmt, layout, flags]
        for (reason, dim, fmt, vdim, vfmt, layout, flags), count in s70.most_common()
    ]
    out.extend(
        _format_table(
            ["Count", "Reason", "Res Dim", "Res Fmt", "View Dim", "View Fmt", "Layout", "Flags"],
            s70_rows,
            len(s70),
            sum(s70.values()),
            max_items,
        )
    )

    # 2. x2w-d3d12 unhandled/stubbed calls & traps
    out.extend(["### Unhandled / Stubbed `x2w-d3d12` & Trap Calls", ""])
    d3d = summary["d3d12_unhandled"]
    d3d_rows = [[count, f"`{call}`"] for call, count in d3d.most_common()]
    out.extend(
        _format_table(
            ["Count", "Call / Slot"],
            d3d_rows,
            len(d3d),
            sum(d3d.values()),
            max_items,
        )
    )

    # 3. x2w-d3d12-debug
    dbg = summary["d3d12_debug"]
    if dbg:
        out.extend(["### `x2w-d3d12-debug` Messages", ""])
        dbg_rows = [
            [count, ctx, sev, msg_id, msg]
            for (ctx, sev, msg_id, msg), count in dbg.most_common()
        ]
        out.extend(
            _format_table(
                ["Count", "Context", "Sev", "ID", "Message (redacted)"],
                dbg_rows,
                len(dbg),
                sum(dbg.values()),
                max_items,
            )
        )

    # 4. x2w-dstorage failures & HRESULTs
    out.extend(["### `x2w-dstorage` Failures & Status HRESULTs", ""])
    ds_fail = summary["dstorage_failures"]
    ds_rows = [[count, reason] for reason, count in ds_fail.most_common()]
    out.extend(
        _format_table(
            ["Count", "Failure Reason"],
            ds_rows,
            len(ds_fail),
            sum(ds_fail.values()),
            max_items,
        )
    )
    ds_hr = summary["dstorage_hresults"]
    if ds_hr:
        hr_rows = [[count, f"`{hr}`"] for hr, count in ds_hr.most_common()]
        out.extend(
            _format_table(
                ["Count", "Status HRESULT"],
                hr_rows,
                len(ds_hr),
                sum(ds_hr.values()),
                max_items,
            )
        )

    # 5. x2w-runtime failing methods / HRESULTs
    out.extend(["### `x2w-runtime` Failing Methods", ""])
    rt = summary["runtime_failures"]
    rt_rows = [[count, f"`{method}`", f"`{hr}`"] for (method, hr), count in rt.most_common()]
    out.extend(
        _format_table(
            ["Count", "Method", "HRESULT / Status"],
            rt_rows,
            len(rt),
            sum(rt.values()),
            max_items,
        )
    )

    # 6. X2W_SHADER_CACHE .fail reasons
    if shader_cache_provided:
        out.extend(["### `X2W_SHADER_CACHE` `.fail` Reasons", ""])
        sh_rows = [[count, f"`{reason}`"] for reason, count in shader_failures.most_common()]
        out.extend(
            _format_table(
                ["Count", "Reason"],
                sh_rows,
                len(shader_failures),
                sum(shader_failures.values()),
                max_items,
            )
        )

    return "\n".join(out)


def triage_run(
    logdir: Path,
    shader_cache: Path | None = None,
    max_items: int = 16,
) -> str:
    """Scan logdir (and optional shader_cache) and return a redacted Markdown summary."""
    log_files = iter_log_files(logdir)

    # run.ps1 / debug_launch.py capture stderr.txt while X2W_TRAP_LOG appends the same lines to trap.log:
    # each trap.log line already present in the sibling stderr.txt is skipped once, so repeats still count.
    mirrored: dict[Path, Counter[str]] = {}
    for path in log_files:
        if path.name.lower() == "trap.log" and (path.parent / "stderr.txt") in log_files:
            seen: Counter[str] = Counter()
            try:
                with (path.parent / "stderr.txt").open("r", encoding="utf-8", errors="replace") as handle:
                    seen.update(line.rstrip("\r\n") for line in handle)
            except OSError:
                pass
            mirrored[path] = seen

    def _line_stream() -> Iterable[str]:
        for path in log_files:
            budget = mirrored.get(path)
            try:
                with path.open("r", encoding="utf-8", errors="replace") as handle:
                    for line in handle:
                        if budget is not None and budget[line.rstrip("\r\n")] > 0:
                            budget[line.rstrip("\r\n")] -= 1
                            continue
                        yield line
            except OSError:
                continue

    summary = summarize_lines(_line_stream())
    shader_failures = summarize_shader_cache(shader_cache)
    return format_markdown(
        summary=summary,
        shader_failures=shader_failures,
        files_scanned=len(log_files),
        shader_cache_provided=shader_cache is not None,
        max_items=max(1, max_items),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Summarize startup logs and optional shader cache into redacted Markdown."
    )
    parser.add_argument("logdir", type=Path, help="Startup log directory or single log file")
    parser.add_argument(
        "--shader-cache",
        type=Path,
        default=None,
        help="Optional X2W_SHADER_CACHE directory containing *.fail files",
    )
    parser.add_argument(
        "--max-items",
        type=int,
        default=16,
        help="Maximum rows per summary table (default: 16)",
    )
    args = parser.parse_args(argv)
    print(triage_run(args.logdir, shader_cache=args.shader_cache, max_items=args.max_items))
    return 0


if __name__ == "__main__":
    sys.exit(main())
