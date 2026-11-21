"""Recompile a bounded pair of Windows x64 functions with one direct rel32 call."""

import argparse
from pathlib import Path
import struct

import pefile

from cpu_leaf_aot import bounded_code, export_rva


GPR = {0: "rax", 1: "rcx", 2: "rdx", 3: "rbx", 6: "rsi"}
OPERATORS = {0x89: "=", 0x8b: "=", 0x01: "+=", 0x03: "+=",
             0x29: "-=", 0x2b: "-=", 0x31: "^=", 0x33: "^="}


def lift_body(start, code, *, caller):
    # In this profile only RBX/RSI survive the call. The host compiler owns
    # physical register allocation and emits its own ABI frame for each function.
    frame = 40 if caller else 8
    prologue = bytes.fromhex("53 56 48 83 ec") + bytes([frame])
    epilogue = bytes.fromhex("48 83 c4") + bytes([frame]) + bytes.fromhex("5e 5b c3")
    if not code.startswith(prologue) or not code.endswith(epilogue):
        raise ValueError(f"unsupported save/restore frame at RVA {start:#x}")
    body = code[len(prologue):-len(epilogue)]
    available = {"rcx", "rdx", "r8"}
    lines = []
    target = None
    pos = 0
    while pos < len(body):
        rva = start + len(prologue) + pos
        reads = set()
        write = None
        is_call = body[pos] == 0xe8
        if is_call and pos + 5 <= len(body):
            if not caller or target is not None:
                raise ValueError(f"unexpected additional call at RVA {rva:#x}")
            target = rva + 5 + struct.unpack_from("<i", body, pos + 1)[0]
            reads = {"rcx", "rdx", "r8"}
            statement = "rax = lifted_callee(rcx, rdx, r8);"
            write = "rax"
            pos += 5
        elif body[pos:pos + 2] == b"\x49\x89" and pos + 3 <= len(body):
            modrm = body[pos + 2]
            src = GPR.get((modrm >> 3) & 7)
            mode = modrm >> 6
            if modrm & 7 or mode not in (0, 1) or not src or pos + 3 + mode > len(body):
                raise ValueError(f"unsupported output store at RVA {rva:#x}")
            displacement = body[pos + 3] if mode else 0
            if displacement not in (0, 8, 16):
                raise ValueError(f"store outside trace at RVA {rva:#x}")
            reads = {"r8", src}
            statement = f"r8[{displacement // 8}] = {src};"
            pos += 3 + mode
        elif body[pos] == 0x48 and pos + 3 <= len(body):
            opcode, modrm = body[pos + 1:pos + 3]
            reg, rm = (modrm >> 3) & 7, modrm & 7
            if modrm >> 6 != 3 or rm not in GPR:
                raise ValueError(f"unsupported register operand at RVA {rva:#x}")
            write = GPR[rm]
            if opcode == 0x83 and reg in (0, 5) and pos + 4 <= len(body):
                imm = struct.unpack_from("b", body, pos + 3)[0]
                operator = "+=" if reg == 0 else "-="
                source = f"static_cast<word>({imm})"
                pos += 4
            elif opcode in OPERATORS and reg in GPR:
                operator = OPERATORS[opcode]
                source = GPR[reg]
                if opcode & 2:
                    write, source = source, write
                reads.add(source)
                pos += 3
            else:
                raise ValueError(f"unsupported register instruction at RVA {rva:#x}")
            if operator != "=":
                reads.add(write)
            statement = f"{write} {operator} {source};"
        else:
            raise ValueError(f"unsupported or incomplete instruction at RVA {rva:#x}")

        if not reads <= available:
            raise ValueError(f"undefined register at RVA {rva:#x}: {sorted(reads - available)}")
        if is_call:
            available.intersection_update({"rbx", "rsi"})
        if write:
            available.add(write)
        lines.append("    " + statement)

    if "rax" not in available or (caller and target is None):
        raise ValueError(f"missing return value or direct call at RVA {start:#x}")
    name = "lifted" if caller else "lifted_callee"
    signature = f'extern "C" __declspec(dllexport) __declspec(noinline) word {name}(word rcx, word rdx, word* r8)'
    return "\n".join([signature + " {", "    word rax, rbx, rsi;", *lines, "    return rax;", "}"]), target


def translate(image, entry):
    with pefile.PE(str(image), fast_load=True) as pe:
        start = export_rva(pe, entry)
        code = bounded_code(pe, start)
        caller, target = lift_body(start, code, caller=True)
        callee_code = bounded_code(pe, target)
        if target < start + len(code) and start < target + len(callee_code):
            raise ValueError(f"overlapping call target at RVA {target:#x}")
        callee, _ = lift_body(target, callee_code, caller=False)
    return f"#include <cstdint>\nusing word = std::uint64_t;\n{callee}\n\n{caller}\n"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("export")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    try:
        args.output.write_text(translate(args.image, args.export), encoding="utf-8")
    except (OSError, ValueError, pefile.PEFormatError) as error:
        parser.exit(1, f"{error}\n")
