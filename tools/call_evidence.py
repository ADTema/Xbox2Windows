"""Inventory static call sites and embedded shader-container metadata in the three graphics DLLs."""

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess

import pefile

from pe_inventory import EXPERIMENTS
from resource_inventory import dxil_program

NAMES = ("Bink2Scarlett.dll", "XboxBvhBuilder.dll", "amd_fidelityfx_upscaler_xbox.dll")
INSTRUCTION = re.compile(r"^\s*([\dA-F]{16}):\s+(\w+)\s+(.*)$", re.I)
ADDRESS = re.compile(r"\[([0-9a-f]{16})h\]", re.I)


def instruction_refs(path, base):
    output = subprocess.check_output(["dumpbin", "/nologo", "/disasm:nobytes", str(path)])
    memory, branches = defaultdict(list), defaultdict(list)
    for line in output.decode("ascii", "replace").splitlines():
        match = INSTRUCTION.match(line)
        if not match:
            continue
        va, op, operands = match.groups()
        rva = int(va, 16) - base
        target = ADDRESS.search(operands)
        if target:
            memory[int(target[1], 16) - base].append((rva, op))
        if op in ("call", "jmp") and re.fullmatch("[0-9a-fA-F]{16}", operands):
            branches[int(operands, 16) - base].append((rva, op))
    return memory, branches


def shader_containers(data, pe, memory):
    base = pe.OPTIONAL_HEADER.ImageBase
    rows = []
    for marker in re.finditer(b"DXBC", data):
        off = marker.start()
        if off + 32 > len(data):
            continue
        version, size, count = struct.unpack_from("<3I", data, off + 20)
        if version != 1 or not 1 <= count <= 128 or not 32 + count * 4 <= size <= len(data) - off:
            continue
        parts, root = [], None
        end = 32 + count * 4
        for i in range(count):
            rel, = struct.unpack_from("<I", data, off + 32 + i * 4)
            if rel < end or rel + 8 > size:
                break
            tag, length = struct.unpack_from("<4sI", data, off + rel)
            end = rel + 8 + length
            if end > size:
                break
            parts.append(tag.decode("ascii", "replace"))
            if tag == b"RTS0" and length >= 24:
                ver, nparam, _, nsampler, _, flags = struct.unpack_from("<6I", data, off + rel + 8)
                root = dict(version=ver, parameter_count=nparam, static_sampler_count=nsampler, flags=hex(flags))
        else:
            rva = pe.get_rva_from_offset(off)
            refs = []
            for ref in re.finditer(re.escape(struct.pack("<Q", base + rva)), data):
                pos = ref.start()
                if pos >= 8 and struct.unpack_from("<I", data, pos - 8)[0] == size:
                    slot = pe.get_rva_from_offset(pos)
                    refs.append(dict(pointer_slot=hex(slot), size_slot=hex(slot - 8),
                                     pointer_code_refs=[hex(a) for a, _ in memory[slot]],
                                     size_code_refs=[hex(a) for a, _ in memory[slot - 8]]))
            rows.append(dict(rva=hex(rva), bytes=size, parts=parts, root_header=root,
                             framed_dxil=dxil_program(data, off), size_pointer_pairs=refs,
                             direct_code_refs=[hex(a) for a, _ in memory[rva]]))
    return rows


def inspect(path):
    data = path.read_bytes()
    with pefile.PE(data=data, fast_load=True) as pe:
        pe.parse_data_directories(directories=[1])
        base = pe.OPTIONAL_HEADER.ImageBase
        memory, branches = instruction_refs(path, base)
        calls = {}
        for desc in pe.DIRECTORY_ENTRY_IMPORT:
            for imp in desc.imports:
                name = imp.name.decode("ascii") if imp.name else ""
                if (desc.dll.decode("ascii").lower(), name) not in EXPERIMENTS:
                    continue
                slot = imp.address - base
                sites = []
                for site, op in memory[slot]:
                    if op in ("call", "jmp"):
                        sites.append(dict(rva=hex(site), operation=op,
                                          upstream=[hex(a) for a, _ in branches[site]] if op == "jmp" else []))
                calls[name] = dict(iat_rva=hex(slot), sites=sites)
        return dict(sha256=hashlib.sha256(data).hexdigest(), calls=calls,
                    containers=shader_containers(data, pe, memory))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    root = args.directory.resolve(strict=True)
    output = Path(__file__).resolve().parents[1] / "out/calls/six-apis.json"
    if output.resolve().is_relative_to(root):
        parser.error("Choose a build directory separate from the report directory")
    rows = {name: inspect(root / name) for name in NAMES}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
