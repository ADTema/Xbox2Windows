"""Lift acyclic pointer checks and early returns across AMD64 chained unwind ranges."""

import argparse
from pathlib import Path

import pefile
from iced_x86 import Code, Decoder, OpKind, Register as R

from cpu_leaf_aot import export_rva
from cpu_ranges import function_ranges, image_bytes


SAVED = {reg: f"saved_{reg}" for reg in (R.RBX, R.RBP, R.RDI, R.RSI, R.R12, R.R13, R.R14, R.R15)}
GPRS = set(SAVED) | {R.RAX, R.RCX, R.RDX, R.R8, R.R9, R.R10, R.R11}


def translate(image, name, partial=False):
    with pefile.PE(str(image), fast_load=True) as pe:
        entry = export_rva(pe, name)
        ranges = function_ranges(pe, entry)
        instructions = {}
        for begin, end in ranges:
            for ins in Decoder(64, image_bytes(pe, begin, end - begin, executable=True), ip=begin):
                if ins.is_invalid:
                    raise ValueError(f"invalid instruction in owned range at {ins.ip:#x}")
                instructions[ins.ip] = ins

    stops = set()
    returns = []
    lines = []
    steps = 0
    def walk(ip, regs, stack, sp, visited, indent):
        nonlocal steps
        while True:
            if ip not in instructions:
                raise ValueError(f"edge outside owned instruction boundaries at {ip:#x}")
            steps += 1
            if ip in visited or len(visited) >= 256 or steps > 2048:
                raise ValueError(f"cycle or early-return profile limit at {ip:#x}")
            visited.add(ip)
            ins = instructions[ip]
            code = ins.code
            dst, src = ins.op0_register, ins.op1_register
            reg_dst, reg_src = dst in GPRS, src in regs
            if ins.has_segment_prefix or ins.has_lock_prefix or ins.has_rep_prefix or ins.has_repne_prefix:
                raise ValueError(f"unsupported instruction prefix at {ip:#x}")
            base, disp = ins.memory_base, ins.memory_displacement
            simple = ins.memory_index == R.NONE
            slot = sp + disp
            if code == Code.PUSH_R64 and dst in regs:
                sp -= 8
                stack[sp] = regs[dst]
            elif code == Code.POP_R64 and reg_dst and sp in stack:
                regs[dst] = stack.pop(sp)
                sp += 8
            elif code in (Code.ADD_RM64_IMM8, Code.SUB_RM64_IMM8) and dst == R.RSP:
                delta = ins.immediate8to64
                sp += delta if code == Code.ADD_RM64_IMM8 else -delta
                if not -4096 <= sp <= 0 or sp % 8:
                    raise ValueError(f"unsupported stack adjustment at {ip:#x}")
                stack = {k: v for k, v in stack.items() if k >= sp}
            elif code in (Code.MOV_RM64_R64, Code.MOV_R64_RM64) and reg_dst and reg_src:
                regs[dst] = regs[src]
            elif (code == Code.MOV_RM64_R64 and ins.op0_kind == OpKind.MEMORY
                  and simple and base == R.RSP and reg_src and sp <= slot <= 32 and slot and slot % 8 == 0):
                stack[slot] = regs[src]
            elif code == Code.MOV_R64_RM64 and reg_dst and simple and base == R.RSP and slot in stack:
                regs[dst] = stack[slot]
            elif (code in (Code.MOV_R64_RM64, Code.LEA_R64_M) and reg_dst and simple
                  and base in regs and regs[base] not in SAVED.values()):
                address = f"({regs[base]} + {disp}ull)"
                if code == Code.MOV_R64_RM64:
                    var = f"load_{ip:x}"
                    lines.append(indent + f"const word {var} = read_word({address});")
                    regs[dst] = var
                else:
                    regs[dst] = address
            elif code == Code.MOV_R32_IMM32 and dst == R.EAX:
                regs[R.RAX] = str(ins.immediate32)
            elif code == Code.TEST_RM64_R64 and dst == src and reg_src and regs[src] not in SAVED.values():
                branch = instructions.get(ins.next_ip)
                if branch is None or branch.code not in (Code.JE_REL8_64, Code.JE_REL32_64):
                    raise ValueError(f"expected JE after TEST at {ip:#x}")
                lines.append(indent + f"if ({regs[src]} == 0) {{")
                walk(branch.near_branch_target, regs.copy(), stack.copy(), sp, visited.copy(), indent + "    ")
                lines.append(indent + "}")
                ip = branch.next_ip
                continue
            elif code in (Code.JMP_REL8_64, Code.JMP_REL32_64):
                ip = ins.near_branch_target
                continue
            elif code == Code.RETNQ:
                if sp or any(regs[r] != v for r, v in SAVED.items()) or regs.get(R.RAX) in (None, *SAVED.values()):
                    raise ValueError(f"unrestored state or unknown return at {ip:#x}")
                returns.append(ip)
                lines.extend([indent + f"*output = {regs[R.RAX]};", indent + "return 1;"])
                return
            elif code == Code.CALL_RM64 and partial:
                stops.add(ip)
                lines.append(indent + "return 0;")
                return
            else:
                raise ValueError(f"unsupported operation at {ip:#x}: {ins}")
            ip = ins.next_ip

    walk(entry, {**SAVED, R.RCX: "first", R.RDX: "second"}, {}, 0, set(), "    ")
    source = """#include <cstdint>
#include <cstring>
using word = std::uint64_t;
static word read_word(word address) {
    word value;
    std::memcpy(&value, reinterpret_cast<const void*>(address), sizeof(value));
    return value;
}
extern "C" __declspec(dllexport) word try_lifted(word first, word second, word* output) {
"""
    return source + "\n".join(lines) + "\n}\n", ranges, returns, stops


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("export")
    parser.add_argument("output", type=Path)
    parser.add_argument("--partial", action="store_true", help="return status 0 at an indirect call")
    args = parser.parse_args()
    try:
        source, ranges, returns, stops = translate(args.image, args.export, args.partial)
        args.output.write_text(source, encoding="utf-8")
        print(f"{len(ranges)} owned ranges, {len(returns)} return paths, indirect stops: {sorted(stops)}")
    except (ValueError, OSError, pefile.PEFormatError) as error:
        parser.exit(1, f"{error}\n")
