"""Measure desktop deserialization of the containers indexed by call_evidence.py."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import sys
from tempfile import NamedTemporaryFile

import pefile

from call_evidence import NAMES

PROJECT = Path(__file__).resolve().parents[1]


def parts(blob):
    if len(blob) < 32 or blob[:4] != b"DXBC":
        raise ValueError("Expected a DXBC container")
    version, size, count = struct.unpack_from("<3I", blob, 20)
    end = 32 + 4 * count
    if version != 1 or size != len(blob) or end > size:
        raise ValueError("Container header disagrees with inventory")
    result = {}
    for index in range(count):
        offset, = struct.unpack_from("<I", blob, 32 + 4 * index)
        if offset < end or offset + 8 > size:
            raise ValueError("Invalid container part offset")
        tag, length = struct.unpack_from("<4sI", blob, offset)
        end = offset + 8 + length
        if end > size or tag in result:
            raise ValueError("Invalid container part")
        result[tag] = blob[offset + 8:end]
    return result


def validate_shader(probe, blob, program):
    if len(program) < 24:
        raise ValueError("Truncated DXIL program")
    _, words, magic, _, offset, size = struct.unpack_from("<II4sIII", program)
    start = 8 + offset
    if (magic != b"DXIL" or offset < 16 or size < 4 or not start + size <= 4 * words <= len(program)
            or program[start:start + 4] != b"BC\xc0\xde"):
        raise ValueError("DXIL program header does not describe a bitcode module")
    checks = {}
    for mode, data in (("container", blob), ("module", program[start:start + size])):
        result = subprocess.run([str(probe), "--" + mode], input=data, capture_output=True,
                                check=True, timeout=10)
        record = json.loads(result.stdout)
        if "status" not in record:
            raise ValueError(f"Validator operation unavailable for {mode}: {record}")
        record["diagnostics"] = result.stderr.decode("utf-8", "replace").rstrip("\0\r\n").splitlines()
        checks[mode] = record
    text = subprocess.run([str(probe), "--disassemble"], input=program[start:start + size],
                          capture_output=True, check=True, timeout=10).stdout.decode("utf-8", "replace")
    triple = re.search(r'^target triple\s*=\s*"([^"]+)"', text, re.M)
    if not triple:
        raise ValueError("DXC disassembly did not identify a target triple")
    calls, standard = Counter(), Counter()
    operand_forms = {}
    for line in text.splitlines():
        instruction = line.partition(";")[0]
        call = re.search(r'\bcall\b[^@\n]*@(?:"([^"]+)"|([\w.$-]+))\s*\(', instruction)
        if call:
            symbol = call[1] or call[2]
            if symbol.startswith("xbox."):
                calls[symbol] += 1
                if ("with_cache" in symbol or any(k in symbol for k in
                        ("Lane", "Swizzle", "Ballot", "MBCNT", "Uniform", "Wave", "CNDMASK"))):
                    operands = instruction[call.end():].split(")", 1)[0]
                    form = re.sub(r"%[\w.]+", "%value", operands)
                    operand_forms.setdefault(symbol, Counter())[form] += 1
            elif symbol.startswith("dx.op."):
                standard[symbol] += 1
    checks["ir"] = dict(target_triple=triple[1], xbox_call_sites=dict(sorted(calls.items())),
                        dx_op_call_sites=dict(sorted(standard.items())), operand_forms=operand_forms)
    return checks


def summarize_operands(modules):
    summary = {}
    for ir in modules:
        for symbol, forms in ir["operand_forms"].items():
            record = summary.setdefault(symbol, {"modules": 0, "sites": 0, "forms": Counter()})
            record["modules"] += 1
            record["sites"] += sum(forms.values())
            record["forms"].update(forms)
    return summary


def measure(build, inventory, probe, fixtures):
    result = {}
    for name in NAMES:
        image = inventory[name]
        if not image["containers"]:
            continue
        data = (build / name).read_bytes()
        sha = hashlib.sha256(data).hexdigest()
        if sha != image["sha256"]:
            raise ValueError(f"Rebuild the call inventory for {name}")
        rows = []
        with pefile.PE(data=data, fast_load=True) as pe:
            for item in image["containers"]:
                blob = pe.get_data(int(item["rva"], 16), item["bytes"])
                sections = parts(blob)
                signature = sections[b"RTS0"]
                native = subprocess.run([str(probe)], input=blob, capture_output=True, check=True, timeout=10)
                row = {"rva": item["rva"], "root_sha256": hashlib.sha256(signature).hexdigest(),
                       "native": json.loads(native.stdout)}
                flags, = struct.unpack_from("<I", signature, 20)
                desktop = signature[:20] + struct.pack("<I", flags & ~0x03000000) + signature[24:]
                row["matching_desktop_fixtures"] = [key for key, payload in fixtures.items() if payload == desktop]
                if b"DXIL" in sections:
                    token, = struct.unpack_from("<I", sections[b"DXIL"])
                    row["program_kind"] = token >> 16
                    row["shader_model"] = f"{(token >> 4) & 15}.{token & 15}"
                    row["validation"] = validate_shader(probe, blob, sections[b"DXIL"])
                rows.append(row)
        keys = ("legacy_hr", "versioned_hr", "original_serialize_hr", "without_observed_bits_hr")
        validation = {mode: dict(Counter(r["validation"][mode]["status"] for r in rows if "validation" in r))
                      for mode in ("container", "module")}
        ir = [r["validation"]["ir"] for r in rows if "validation" in r]
        symbols = Counter(symbol for r in ir for symbol in r["xbox_call_sites"])
        result[name] = dict(sha256=sha, containers=len(rows), unique_root_payloads=len({r["root_sha256"] for r in rows}),
                            dxil_validation=validation,
                            modules_with_xbox_calls=sum(bool(r["xbox_call_sites"]) for r in ir),
                            modules_per_xbox_symbol=dict(symbols.most_common()),
                            static_operands=summarize_operands(ir),
                            fixture_matches=dict(Counter(key for r in rows for key in r["matching_desktop_fixtures"])),
                            results={k: dict(Counter(r["native"].get(k, "not_tested") for r in rows)) for k in keys},
                            entries=rows)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("build", type=Path)
    p.add_argument("--inventory", type=Path, default=PROJECT / "out/calls/six-apis.json")
    p.add_argument("--probe", type=Path, default=PROJECT / "out/build/dev/root_probe.exe")
    p.add_argument("--controls", type=Path, help="Build directory with compute_root.cso and compute_tables.cso")
    args = p.parse_args()
    dest = PROJECT / "out/calls/desktop-roots.json"
    build = args.build.resolve(strict=True)
    if dest.resolve().is_relative_to(build) or dest.resolve() == args.inventory.resolve():
        p.error("Report destination overlaps inputs")
    fixtures = {}
    control_checks = {}
    probe = args.probe.resolve(strict=True)
    if args.controls:
        for name in ("compute_root", "compute_tables"):
            blob = (args.controls / (name + ".cso")).read_bytes()
            sections = parts(blob)
            fixtures[name] = sections[b"RTS0"]
            checks = validate_shader(probe, blob, sections[b"DXIL"])
            if any(checks[k]["status"] != "0x00000000" for k in ("container", "module")):
                raise ValueError(f"Desktop positive control failed for {name}")
            control_checks[name] = checks
    inventory_data = args.inventory.read_bytes()
    result = measure(build, json.loads(inventory_data), probe, fixtures)
    document = dict(schema=1, windows_build=sys.getwindowsversion().build,
                    probe_sha256=hashlib.sha256(probe.read_bytes()).hexdigest(),
                    inventory_sha256=hashlib.sha256(inventory_data).hexdigest(),
                    control_root_sha256={key: hashlib.sha256(b).hexdigest() for key, b in fixtures.items()},
                    control_validation=control_checks, images=result)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(mode="w", dir=dest.parent, delete=False, encoding="utf-8") as f:
        json.dump(document, f, indent=2)
        f.write("\n")
    Path(f.name).replace(dest)
    for name, report in result.items():
        print(name, report["containers"], report["results"])


if __name__ == "__main__":
    main()
