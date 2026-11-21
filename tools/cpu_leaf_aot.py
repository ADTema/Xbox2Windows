"""Lift a bounded AMD64 leaf function with the fixture's (uint32, uint32*) ABI to C++."""

import argparse
from pathlib import Path
import struct

import pefile


def export_rva(pe, name):
    if pe.FILE_HEADER.Machine != 0x8664 or pe.OPTIONAL_HEADER.Magic != 0x20B:
        raise ValueError("expected AMD64 PE32+")
    pe.parse_data_directories(directories=[0, 3])  # exports and runtime functions
    exports = getattr(pe, "DIRECTORY_ENTRY_EXPORT", None)
    matches = [e.address for e in exports.symbols if e.name == name.encode("ascii")
               and not e.forwarder] if exports else []
    if len(matches) != 1:
        raise ValueError(f"expected one local export named {name}")
    return matches[0]


def bounded_code(pe, start):
    ends = [f.struct.EndAddress for f in getattr(pe, "DIRECTORY_ENTRY_EXCEPTION", [])
            if f.struct.BeginAddress == start]
    if len(ends) != 1 or ends[0] <= start:
        raise ValueError(f"no unique function interval at RVA {start:#x}")
    section = pe.get_section_by_rva(start)
    size = ends[0] - start
    if (not section or not section.Characteristics & 0x20000000
            or ends[0] - section.VirtualAddress > min(section.Misc_VirtualSize, section.SizeOfRawData)):
        raise ValueError(f"function outside file-backed executable section at RVA {start:#x}")
    data = pe.get_data(start, size)
    if len(data) != size:
        raise ValueError(f"truncated function at RVA {start:#x}")
    return data


def function_bytes(image, name):
    with pefile.PE(str(image), fast_load=True) as pe:
        start = export_rva(pe, name)
        return start, bounded_code(pe, start)


def translate(start, code):
    # This profile initializes EAX from ECX before either branch. A compare and
    # its immediate consumer form one operation, so flags never cross a join.
    if not code.startswith((b"\x8b\xc1", b"\x89\xc8")):
        raise ValueError(f"expected mov eax, ecx at RVA {start:#x}")
    statements = {}
    targets = set()
    offset = 2
    while offset < len(code):
        pos = offset
        rva = start + pos
        prefix = code[pos:pos + 2]
        opcode = code[pos]
        jump = False
        if prefix == b"\x83\xf8" and pos + 5 <= len(code) and code[pos + 3] in (0x72, 0x73):
            limit = struct.unpack_from("b", code, pos + 2)[0] & 0xffffffff
            condition = "<" if code[pos + 3] == 0x72 else ">="
            offset += 5
            jump = True
            statement = f"if (eax {condition} {limit}u) "
        elif opcode == 0xeb and pos + 2 <= len(code):
            offset += 2
            jump = True
            statement = ""
        elif prefix in (b"\x83\xc0", b"\x83\xe8") and pos + 3 <= len(code):
            immediate = struct.unpack_from("b", code, pos + 2)[0] & 0xffffffff
            operator = "+=" if prefix[1] == 0xc0 else "-="
            statement = f"eax {operator} {immediate}u;"
            offset += 3
        elif prefix == b"\x89\x02":
            statement = "*output = eax;"
            offset += 2
        elif opcode == 0xc3:
            statement = "return eax;"
            offset += 1
        else:
            raise ValueError(f"unsupported or incomplete instruction at RVA {rva:#x}")
        if jump:
            displacement = struct.unpack_from("b", code, offset - 1)[0]
            target = offset + displacement
            if target < offset or target >= len(code):
                raise ValueError(f"expected forward in-function branch at RVA {rva:#x}")
            targets.add(target)
            statement += f"goto loc_{target:x};"
        statements[pos] = statement

    invalid = targets.difference(statements)
    if invalid:
        raise ValueError(f"branch into an instruction at RVA {start + min(invalid):#x}")
    if not statements or statements[pos] != "return eax;":
        raise ValueError(f"missing terminal return at RVA {start + len(code):#x}")
    lines = ["#include <cstdint>",
             'extern "C" __declspec(dllexport) std::uint32_t lifted(std::uint32_t input, std::uint32_t* output) {',
             "    std::uint32_t eax = input;"]
    for pos, statement in statements.items():
        if pos in targets:
            lines.append(f"loc_{pos:x}:")
        lines.append("    " + statement)
    return "\n".join([*lines, "}", ""])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("export")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    try:
        rva, code = function_bytes(args.image, args.export)
        args.output.write_text(translate(rva, code), encoding="utf-8")
    except (ValueError, OSError, pefile.PEFormatError) as error:
        parser.exit(1, f"{error}\n")
