"""Reject unresolved xbox.* intrinsic calls before a PSO submission.

The gate reads the read-only inventory from `probe_roots.xbox_intrinsic_inventory()` and keeps
the three groups apart on purpose: a symbol a module only declares, or one that only metadata
mentions, is not a call and does not block submission. What blocks is a call the adapter cannot
resolve. A refused module never reaches the submission callable.

The default status table lowers nothing: this repository ships no verified lowering, so an
unresolved call is refused rather than guessed at. An adapter injects its own `status_of(name)`
and reports LOWERED only for a builtin whose lowering it validated.
"""

import argparse
import json
from pathlib import Path
import sys

from probe_roots import XBOX_PREFIX, xbox_intrinsic_inventory

LOWERED = "LOWERED"
UNRESOLVED = "UNRESOLVED"
ALLOW = "ALLOW"
REJECT = "REJECT"
NOT_CHECKED = "NOT_CHECKED"


def default_status_of(name):
    """No builtin is lowered in this repository, so every called name stays unresolved."""
    return UNRESOLVED, "no-verified-lowering-in-this-repository"


def status_table(lowered=()):
    """Build an adapter status table; the caller owns the proof for each name it lowers."""
    lowered = frozenset(lowered)

    def status_of(name):
        if name in lowered:
            return LOWERED, "verified-by-adapter"
        return default_status_of(name)

    return status_of


def decide(inventory, status_of=None):
    """Turn a module's inventory into ALLOW or REJECT, naming the calls that block."""
    status_of = status_of or default_status_of
    blocking, resolved = [], []
    for symbol in sorted(inventory["calls"]):
        builtin = symbol[len(XBOX_PREFIX):] if symbol.startswith(XBOX_PREFIX) else symbol
        status, unblocks = status_of(builtin)
        entry = {"name": symbol, "builtin": builtin, "sites": inventory["calls"][symbol]}
        if status == LOWERED:
            resolved.append(entry)
        else:
            entry["status"] = status
            entry["unblocks"] = unblocks
            blocking.append(entry)
    verdict = REJECT if blocking else ALLOW
    names = [entry["name"] for entry in blocking]
    if verdict == REJECT:
        message = f"REJECT: {len(names)} unresolved xbox.* call(s): {', '.join(names)}"
    elif resolved:
        message = "ALLOW: verified lowering for " + ", ".join(entry["builtin"] for entry in resolved)
    else:
        message = (
            f"ALLOW: no unresolved xbox.* calls "
            f"(declarations={len(inventory['declarations'])}, metadata_only={len(inventory['metadata_only'])})"
        )
    return {
        "verdict": verdict,
        "reason": "unresolved-xbox-calls" if blocking else "no-unresolved-xbox-calls",
        "message": message,
        "calls": inventory["calls"],
        "declarations": inventory["declarations"],
        "metadata_only": inventory["metadata_only"],
        "blocking": blocking,
        "resolved": resolved,
        "reported_names": names,
        "checked": True,
    }


def not_checked(reason):
    """Record that no module was examined, so a caller cannot read it as a cleared module.

    A submission path that has no disassembly of the final module reports this instead of
    gating nothing: the verdict stays distinct from ALLOW and `checked` is False, so a
    caller cannot treat it as cleared.
    """
    return {
        "verdict": NOT_CHECKED,
        "reason": reason,
        "message": f"NOT_CHECKED: the final module was not disassembled ({reason})",
        "checked": False,
        "calls": {},
        "declarations": [],
        "metadata_only": [],
        "blocking": [],
        "resolved": [],
        "reported_names": [],
    }


def check_text(text, status_of=None):
    """Gate a module given as disassembly text."""
    return decide(xbox_intrinsic_inventory(text), status_of)


def check_container(probe, blob, program, status_of=None, optional_modes=()):
    """Gate a DXBC container by disassembling its DXIL part through the validator probe."""
    from probe_roots import validate_shader

    checks = validate_shader(probe, blob, program, optional_modes=optional_modes)
    decision = decide(checks["ir"]["xbox_intrinsics"], status_of)
    decision["validation"] = checks
    return decision


def gate_submission(decision, module_text, submit):
    """Submit only for an ALLOW verdict; REJECT and NOT_CHECKED reach `submit` zero times."""
    decision["submitted"] = decision["verdict"] == ALLOW
    if decision["submitted"]:
        submit(module_text)
    return decision


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command")
    text = sub.add_parser("check-text", help="Gate a module given as disassembly text")
    text.add_argument("path", type=Path, help="Disassembly text file ('-' for standard input)")
    text.add_argument("--lowered", action="append", default=None,
                      help="Builtin the adapter reports as LOWERED (repeatable)")
    shader = sub.add_parser("check", help="Gate a DXBC container through a validator probe")
    shader.add_argument("input", type=Path, help="DXBC container")
    shader.add_argument("--probe", type=Path, help="root_probe.exe path")
    shader.add_argument("--lowered", action="append", default=None,
                        help="Builtin the adapter reports as LOWERED (repeatable)")
    args = parser.parse_args()

    if args.command not in ("check-text", "check"):
        parser.print_help(sys.stderr)
        return 2

    status_of = status_table(args.lowered) if args.lowered else None
    try:
        if args.command == "check-text":
            body = (sys.stdin.read() if str(args.path) == "-"
                    else args.path.read_text(encoding="utf-8", errors="replace"))
            decision = check_text(body, status_of)
        else:
            if not args.probe:
                parser.error("check requires --probe")
            from resource_inventory import parts

            raw = args.input.read_bytes()
            sections = parts(raw)
            if b"DXIL" not in sections:
                raise ValueError("DXBC container has no DXIL part")
            decision = check_container(args.probe.resolve(strict=True), raw, sections[b"DXIL"],
                                       status_of)
    except (ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(decision["message"])
    print(json.dumps(decision, indent=2))
    return 0 if decision["verdict"] == ALLOW else 1


if __name__ == "__main__":
    sys.exit(main())
