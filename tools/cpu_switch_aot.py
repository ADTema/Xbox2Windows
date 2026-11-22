"""Recompile bounded Windows x64 leaf functions with jump-table dispatch to C++.

Each export takes three integer words in RCX, RDX and R8 and returns RAX. The
translator follows branches and jump-table entries from the export, so data
placed after the code (as MSVC does with its tables) is never decoded. An
indirect JMP is accepted only at the end of one of these sequences, reached by
the fallthrough of an unsigned bound check on the index:

    mov E32, [B+I*4+table]; add E, B; jmp E   B = image base (MSVC)
    movsxd E, [B+I*4];      add E, B; jmp E   B = table      (LLVM)

B must hold the same RIP-relative address on every path, and the index must be
shown to carry the compared value. The generated C++ replaces the dispatch with
a switch over the table targets.

An export listed as "name:4" also takes a fourth integer word in R9: R9 is then
defined at entry and the generated function has a fourth parameter. "name" and
"name:3" take three, and R9 is a scratch register that must be written before it
is read; any other count is rejected. The count is chosen by whoever invokes the
translator, not derived from the machine code, and the host must call the
translated function with the same number of arguments. Stack arguments (the
fifth and later) and floating-point arguments are not supported.

Flags are modeled only between a producer and its consumers (Jcc, SETcc,
CMOVcc) in one straight-line run that no edge enters. Instructions that leave
the flags unchanged (moves, LEA, NOT, SETcc, CMOVcc) may sit between them.

A forward pass records how many low bytes (0, 1, 2 or 8) of each register every
path defines. A read needs as many defined bytes as it uses, and an 8- or 16-bit
write keeps the other bytes of its register. The return width is the number of
consecutive low RAX bytes that are definitely defined at every reachable RET or
RET 0: 0, 1, 2 or 8, the lower bound over joins and over returns. It counts
defined bytes and does not establish a source-language type. It is None when no
RET is reachable, which describes the reachable control flow and makes no
termination claim. The generated source states the width unless it is 8.

A function that makes no call may use its stack. A forward pass gives RSP at
every instruction as entry RSP plus a constant that must agree at joins and be
0 at every RET. PUSH and POP of a nonvolatile register and SUB or ADD RSP by a
multiple of 8 are the only changes of RSP accepted; any other write of RSP is a
dynamic frame, and any use of RSP as a value (MOV RAX, RSP or LEA RAX, [RSP+8])
would let the frame's address escape. Both are rejected. The frame becomes one
byte array per call, from the lowest RSP up to the end of the caller's 32-byte
home space at entry RSP + 40, at most MAX_FRAME bytes, and each RSP-based
operand a load or store at a constant index into it. An access below the
current RSP (Windows x64 has no red zone), of the return address or at or
above entry RSP + 40 (a stack argument) is rejected. A second pass follows
every stack byte: a read needs each byte written on every path, so home space
must be written before it is read. RBX, RBP, RSI, RDI and R12-R15 may be used
when every RET is reached with each one holding its entry value again, saved
and restored by PUSH and POP or by a 64-bit MOV to and from the frame. Their
entry values are not arguments: one may only be saved, and its saved bytes
only restored into the same register. The generated function is C++ that the
host compiler gives its own frame, so exception unwinding through the original
frame layout is not reproduced.
"""

import argparse
from pathlib import Path
import struct

import pefile
from iced_x86 import (ConditionCode as CC, Decoder, FlowControl, InstructionInfoFactory, MemorySizeExt,
                      Mnemonic as M, OpAccess, OpKind, Register as R, RegisterExt)

from cpu_leaf_aot import export_rva
from cpu_ranges import function_ranges, image_bytes


NAMES = {R.RAX: "rax", R.RCX: "rcx", R.RDX: "rdx", R.RBX: "rbx", R.RSP: "rsp", R.RBP: "rbp",
         R.RSI: "rsi", R.RDI: "rdi", R.R8: "r8", R.R9: "r9", R.R10: "r10", R.R11: "r11",
         R.R12: "r12", R.R13: "r13", R.R14: "r14", R.R15: "r15"}
# Integer argument registers in order. An entry takes the first three unless it is listed as "name:4".
ARGUMENT_REGISTERS = (R.RCX, R.RDX, R.R8, R.R9)
ARGUMENT_COUNTS = (3, 4)
DEFAULT_ARGUMENTS = 3
VOLATILE = {R.RAX, R.RCX, R.RDX, R.R8, R.R9, R.R10, R.R11}
NONVOLATILE = tuple(sorted(set(NAMES) - VOLATILE - {R.RSP}))  # RBX, RBP, RSI, RDI, R12-R15
# The caller's home space ends 40 bytes above entry RSP: 8 for the return address and 32 reserved.
HOME_END = 40
# Bytes of the frame array. MSVC calls __chkstk before it allocates a page (4096 bytes) or more, and calls are
# rejected, so the frame of a call-free MSVC function stays below a page.
MAX_FRAME = 4096
HIGH_BYTES = {R.AH, R.BH, R.CH, R.DH}
ALU = {M.ADD: "+", M.SUB: "-", M.AND: "&", M.OR: "|", M.XOR: "^"}
SHIFTS = {M.SHL: "<<", M.SHR: ">>", M.SAR: ">>"}
_CODES = "O NO B AE E NE BE A S NS P NP L GE LE G".split()
SETCC = {getattr(M, "SET" + code) for code in _CODES}
CMOVCC = {getattr(M, "CMOV" + code) for code in _CODES}
# Instructions that neither read nor write the arithmetic flags, besides SETcc and CMOVcc,
# which only read them.
FLAG_NEUTRAL = {M.MOV, M.MOVZX, M.MOVSX, M.MOVSXD, M.LEA, M.NOP, M.NOT, *SETCC, *CMOVCC}
FLAG_PRODUCERS = {*ALU, M.CMP, M.TEST, M.INC, M.DEC}
MAX_FLAG_DISTANCE = 16
CONDITIONS = {CC.E: "e", CC.NE: "ne", CC.B: "b", CC.AE: "ae", CC.BE: "be", CC.A: "a",
              CC.L: "l", CC.GE: "ge", CC.LE: "le", CC.G: "g", CC.S: "s", CC.NS: "ns"}
MAX_CASES = 1024
MAX_INSTRUCTIONS = 4096


def unsigned(width):
    return f"std::uint{width * 8}_t"


def signed(width):
    return f"std::int{width * 8}_t"


def full(register):
    full_register = RegisterExt.full_register(register)
    if full_register not in NAMES:
        raise ValueError(f"unsupported register {register}")
    return full_register


def runtime_functions(pe):
    table = pe.OPTIONAL_HEADER.DATA_DIRECTORY[3]
    if not table.Size:
        return []
    if table.Size % 12:
        raise ValueError("incomplete runtime-function record")
    return [(begin, end) for begin, end, _ in
            struct.iter_unpack("<III", image_bytes(pe, table.VirtualAddress, table.Size))]


def owned_ranges(pe, entry):
    """Unwind-owned intervals, or the export's section for a leaf without unwind data."""
    records = runtime_functions(pe)
    if any(begin <= entry < end for begin, end in records):
        return function_ranges(pe, entry), []
    # Windows x64 leaf functions may omit .pdata. Such a function may use any
    # file-backed bytes of its section that no runtime-function entry owns.
    section = pe.get_section_by_rva(entry)
    if not section or not section.Characteristics & 0x20000000:
        raise ValueError(f"export at RVA {entry:#x} is not in an executable section")
    end = section.VirtualAddress + min(section.Misc_VirtualSize, section.SizeOfRawData)
    return [(section.VirtualAddress, end)], records


class Function:
    def __init__(self, pe, entry):
        self.pe = pe
        self.entry = entry
        ranges, self.foreign = owned_ranges(pe, entry)
        self.ranges = [(begin, end, image_bytes(pe, begin, end - begin, executable=True))
                       for begin, end in ranges]
        self.instructions = {}
        self.owner = {}
        self.ending = {}
        self.successors = {}
        self.dispatches = {}

    def decode(self, ip):
        for begin, end, data in self.ranges:
            if begin <= ip < end:
                ins = Decoder(64, data[ip - begin:], ip=ip).decode()
                if ins.is_invalid or ins.next_ip > end:
                    raise ValueError(f"invalid or truncated instruction at RVA {ip:#x}")
                if any(ip < stop and start < ins.next_ip for start, stop in self.foreign):
                    raise ValueError(f"edge outside owned ranges at RVA {ip:#x}: another function's unwind interval")
                return ins
        raise ValueError(f"edge outside owned ranges at RVA {ip:#x}")

    def claim(self, begin, end, owner, what):
        for address in range(begin, end):
            if self.owner.get(address, owner) != owner:
                raise ValueError(f"{what} at RVA {begin:#x} overlaps RVA {self.owner[address]:#x}")
        for address in range(begin, end):
            self.owner[address] = owner

    def explore(self):
        pending = [self.entry]
        indirect = []
        while pending or indirect:
            if not pending:
                ip = indirect.pop()
                pending.extend(self.dispatch(ip))
                continue
            ip = pending.pop()
            if ip in self.instructions:
                continue
            if self.owner.get(ip, ip) != ip:
                raise ValueError(f"edge at RVA {ip:#x} overlaps an instruction")
            if len(self.instructions) >= MAX_INSTRUCTIONS:
                raise ValueError(f"instruction limit reached at RVA {ip:#x}")
            ins = self.decode(ip)
            self.claim(ip, ins.next_ip, ip, "instruction")
            self.instructions[ip] = ins
            self.ending[ins.next_ip] = ins
            flow = ins.flow_control
            if flow == FlowControl.NEXT:
                targets = [ins.next_ip]
            elif flow == FlowControl.CONDITIONAL_BRANCH and ins.is_jcc_short_or_near:
                targets = [ins.near_branch_target, ins.next_ip]
            elif flow == FlowControl.UNCONDITIONAL_BRANCH and ins.is_jmp_short_or_near:
                targets = [ins.near_branch_target]
            elif flow == FlowControl.RETURN and ins.mnemonic == M.RET and (ins.op_count == 0 or ins.immediate(0) == 0):
                targets = []
            elif flow == FlowControl.INDIRECT_BRANCH and ins.op0_kind == OpKind.REGISTER:
                targets = []
                indirect.append(ip)
            else:
                raise ValueError(f"unsupported control flow at RVA {ip:#x}: {ins}")
            self.successors[ip] = targets
            pending.extend(reversed(targets))
        edges = {target for ip, targets in self.successors.items() for target in targets
                 if target != self.instructions[ip].next_ip
                 or self.instructions[ip].flow_control not in (FlowControl.NEXT, FlowControl.CONDITIONAL_BRANCH)}
        # A conditional branch to its own fallthrough still emits a goto, so its target needs a label.
        edges |= {ins.near_branch_target for ins in self.instructions.values()
                  if ins.flow_control == FlowControl.CONDITIONAL_BRANCH}
        constants = self.constants()
        for ip in self.dispatches:
            self.prove(ip, edges, constants)
        return edges

    def previous(self, ins, what):
        before = self.ending.get(ins.ip)
        if before is None or before.flow_control != FlowControl.NEXT:
            raise ValueError(f"missing {what} before RVA {ins.ip:#x}")
        return before

    def constants(self):
        """RIP-relative addresses that every explored path leaves in a register, per instruction."""
        state = {self.entry: {}}
        work = [self.entry]
        while work:
            ip = work.pop()
            ins = self.instructions.get(ip)
            if ins is None:
                continue
            known = dict(state[ip])
            if ip in self.dispatches:
                known.pop(self.dispatches[ip][4], None)
            elif ins.mnemonic == M.LEA and ins.is_ip_rel_memory_operand and RegisterExt.is_gpr64(ins.op0_register):
                known[ins.op0_register] = ins.ip_rel_memory_address
            elif ins.op_count and ins.op0_kind == OpKind.REGISTER and ins.mnemonic not in (M.CMP, M.TEST):
                known.pop(full(ins.op0_register), None)
            for successor in self.successors.get(ip, ()):
                if successor not in self.instructions:
                    continue
                if successor == self.entry:
                    merged = {}
                elif successor in state:
                    merged = {r: v for r, v in state[successor].items() if known.get(r) == v}
                else:
                    merged = known
                if successor not in state or merged != state[successor]:
                    state[successor] = merged
                    work.append(successor)
        return state

    def dispatch(self, ip):
        jump = self.instructions[ip]
        add = self.previous(jump, "table address add")
        load = self.previous(add, "table entry load")
        target = full(jump.op0_register)
        base = add.op1_register if add.op1_kind == OpKind.REGISTER else None
        if (add.mnemonic != M.ADD or add.op0_kind != OpKind.REGISTER or add.op0_register != target
                or not RegisterExt.is_gpr64(target) or base is None or not RegisterExt.is_gpr64(base)
                or base == target):
            raise ValueError(f"unrecognized indirect jump at RVA {ip:#x}")
        index = load.memory_index
        if (load.op1_kind != OpKind.MEMORY or load.memory_base != base or load.memory_index_scale != 4
                or not RegisterExt.is_gpr64(index) or index == base or load.has_segment_prefix
                or full(load.op0_register) != target):
            raise ValueError(f"unrecognized table load at RVA {load.ip:#x}")
        anchor = self.constants().get(load.ip, {}).get(base)
        if anchor is None:
            raise ValueError(f"table base {NAMES[base]} is not a RIP-relative address at RVA {load.ip:#x}")
        if load.mnemonic == M.MOV and RegisterExt.is_gpr32(load.op0_register):
            # Image-relative entries: the base register holds the image base.
            table, kind = load.memory_displacement, "image"
            if anchor != 0 or not 0 < table < 1 << 31:
                raise ValueError(f"image-relative table without an image base at RVA {load.ip:#x}")
        elif load.mnemonic == M.MOVSXD and load.memory_displacement == 0:
            table, kind = anchor, "relative"
        else:
            raise ValueError(f"unrecognized table load at RVA {load.ip:#x}")

        # The bound check must fall through into the dispatch block.
        bound = load
        between = []
        while True:
            bound = self.ending.get(bound.ip)
            if bound is None:
                raise ValueError(f"unbounded jump-table index at RVA {ip:#x}")
            if bound.flow_control == FlowControl.CONDITIONAL_BRANCH:
                break
            if bound.flow_control != FlowControl.NEXT or len(between) >= 8:
                raise ValueError(f"unbounded jump-table index at RVA {ip:#x}")
            between.append(bound)
        compare = self.ending.get(bound.ip)
        if bound.condition_code not in (CC.A, CC.AE):
            raise ValueError(f"jump-table bound is not an unsigned upper limit at RVA {bound.ip:#x}")
        if (compare is None or compare.mnemonic != M.CMP or compare.op0_kind != OpKind.REGISTER
                or compare.op1_kind not in (OpKind.IMMEDIATE8TO32, OpKind.IMMEDIATE8TO64,
                                            OpKind.IMMEDIATE32, OpKind.IMMEDIATE32TO64)
                or RegisterExt.size(compare.op0_register) not in (4, 8)):
            raise ValueError(f"unbounded jump-table index at RVA {bound.ip:#x}")
        limit = compare.immediate(1) & ((1 << RegisterExt.size(compare.op0_register) * 8) - 1)
        count = limit + 1 if bound.condition_code == CC.A else limit
        if not 0 < count <= MAX_CASES:
            raise ValueError(f"unsupported jump-table size {count} at RVA {compare.ip:#x}")
        entries = struct.unpack(f"<{count}{'I' if kind == 'image' else 'i'}",
                                image_bytes(self.pe, table, 4 * count))
        self.claim(table, table + 4 * count, -table, "jump table")
        targets = [entry if kind == "image" else (table + entry) & 0xffffffff for entry in entries]
        self.dispatches[ip] = (index, targets, (load.ip, add.ip), list(reversed(between)),
                               target, (compare, bound, base, anchor))
        self.successors[ip] = targets
        return list(reversed(targets))

    def prove(self, ip, edges, constants):
        index, _, sequence, window, _, (compare, bound, base, anchor) = self.dispatches[ip]
        if any(address in edges for address in (bound.ip, *(i.ip for i in window), *sequence, ip)):
            raise ValueError(f"second entry into the dispatch block at RVA {ip:#x}")
        if constants.get(sequence[0], {}).get(base) != anchor:
            raise ValueError(f"table base {NAMES[base]} differs on another path to RVA {sequence[0]:#x}")
        # Extend the straight-line window back from the compare while it has a single entry.
        start = compare
        prefix = []
        while start.ip not in edges and start.ip != self.entry and len(prefix) < 16:
            before = self.ending.get(start.ip)
            if before is None or before.flow_control != FlowControl.NEXT:
                break
            prefix.append(before)
            start = before
        values = {}
        counter = iter(range(1 << 30))

        def value(reg):
            if reg not in values:
                values[reg] = (next(counter), "full")
            return values[reg]

        def step(ins):
            if ins.op_count == 0 or ins.op0_kind != OpKind.REGISTER:
                return
            dst = ins.op0_register
            width = RegisterExt.size(dst)
            if ins.mnemonic == M.CMP:
                return
            if ins.mnemonic == M.MOV and ins.op1_kind == OpKind.REGISTER and width in (4, 8):
                number, form = value(full(ins.op1_register))
                values[full(dst)] = (number, form) if width == 8 else (number, "zext32")
            elif (ins.mnemonic == M.MOVSXD and ins.op1_kind == OpKind.REGISTER
                  and RegisterExt.size(ins.op1_register) == 4):
                values[full(dst)] = (value(full(ins.op1_register))[0], "sext32")
            elif ins.mnemonic not in (M.CMP, M.TEST):
                values[full(dst)] = (next(counter), "zext32" if width == 4 else "full")

        for ins in reversed(prefix):
            step(ins)
        bounded, bounded_form = value(full(compare.op0_register))
        compared_width = RegisterExt.size(compare.op0_register)
        for ins in window:
            step(ins)
        number, form = value(index)
        if number != bounded or not (form in ("zext32", "sext32") or (compared_width == 8 and form == bounded_form)):
            raise ValueError(f"jump-table index {NAMES[index]} is not the bounded value at RVA {ip:#x}")


class Lifter:
    def __init__(self):
        self.used = set()
        self.flags = False
        self.frame = {}  # RVA -> index into the frame array of the stack bytes it accesses (from Frame)
        self.adjustments = set()  # RVAs of SUB or ADD RSP, imm

    def slot(self, ins):
        if ins.ip not in self.frame:
            raise ValueError(f"stack access outside the frame model at RVA {ins.ip:#x}")
        return f"reinterpret_cast<word>(frame + {self.frame[ins.ip]})"

    def reg(self, register):
        width = RegisterExt.size(register)
        if register in HIGH_BYTES or width not in (1, 2, 4, 8):
            raise ValueError(f"unsupported register {register}")
        name = NAMES[full(register)]
        self.used.add(full(register))
        return name if width == 8 else f"static_cast<{unsigned(width)}>({name})"

    def address(self, ins):
        if ins.memory_base == R.RSP and ins.ip in self.frame:
            # A constant index into the frame array: RSP itself never becomes a C++ value.
            return self.slot(ins)
        if (ins.memory_base in (R.RIP, R.EIP, R.RSP, R.ESP) or ins.memory_index in (R.RSP, R.ESP)
                or ins.has_segment_prefix or ins.memory_base == R.NONE):
            raise ValueError(f"unsupported memory operand at RVA {ins.ip:#x}")
        parts = [self.reg(ins.memory_base)]
        if ins.memory_index != R.NONE:
            if not RegisterExt.is_gpr64(ins.memory_index):
                raise ValueError(f"unsupported memory index at RVA {ins.ip:#x}")
            parts.append(f"{self.reg(ins.memory_index)} * {ins.memory_index_scale}u")
        displacement = ins.memory_displacement & ((1 << 64) - 1)
        if displacement:
            parts.append(f"{displacement:#x}ull")
        if RegisterExt.is_gpr32(ins.memory_base):
            # A 67h prefix selects 32-bit addressing: the sum wraps at 32 bits and is zero-extended.
            return f"static_cast<std::uint64_t>(static_cast<std::uint32_t>({' + '.join(parts)}))"
        return "(" + " + ".join(parts) + ")"

    def operand(self, ins, number, width):
        kind = ins.op_kind(number)
        if kind == OpKind.REGISTER:
            return self.reg(ins.op_register(number))
        if kind == OpKind.MEMORY:
            return f"load<{unsigned(width)}>({self.address(ins)})"
        if kind in (OpKind.IMMEDIATE8, OpKind.IMMEDIATE8TO16, OpKind.IMMEDIATE8TO32, OpKind.IMMEDIATE8TO64,
                    OpKind.IMMEDIATE16, OpKind.IMMEDIATE32, OpKind.IMMEDIATE32TO64, OpKind.IMMEDIATE64):
            return f"static_cast<{unsigned(width)}>({ins.immediate(number) & ((1 << width * 8) - 1):#x}ull)"
        raise ValueError(f"unsupported operand at RVA {ins.ip:#x}")

    def write(self, ins, width, expression):
        if ins.op0_kind == OpKind.MEMORY:
            return f"store<{unsigned(width)}>({self.address(ins)}, static_cast<{unsigned(width)}>({expression}));"
        register = ins.op0_register
        if register in HIGH_BYTES:
            raise ValueError(f"unsupported register {register}")
        if width not in (1, 2, 4, 8) or RegisterExt.size(register) != width:
            raise ValueError(f"unsupported partial register write at RVA {ins.ip:#x}")
        self.used.add(full(register))
        name = NAMES[full(register)]
        if width < 4:
            # An 8- or 16-bit destination leaves the rest of the register unchanged.
            mask = (1 << width * 8) - 1
            return f"{name} = ({name} & ~{mask:#x}ull) | static_cast<{unsigned(width)}>({expression});"
        return f"{name} = static_cast<{unsigned(width)}>({expression});"

    def width(self, ins):
        if ins.op0_kind == OpKind.REGISTER:
            return RegisterExt.size(ins.op0_register)
        if ins.op0_kind == OpKind.MEMORY:
            return _memory_width(ins)
        return 0

    def condition(self, producer, jcc):
        code = CONDITIONS.get(jcc.condition_code)
        width = self.width(producer)
        u, s = unsigned(width), signed(width)
        if producer.mnemonic in (M.CMP, M.SUB):
            a, b = f"static_cast<{u}>(fa)", f"static_cast<{u}>(fb)"
            result = f"static_cast<{s}>(static_cast<{u}>({a} - {b}))"
            table = {"e": f"{a} == {b}", "ne": f"{a} != {b}", "b": f"{a} < {b}", "ae": f"{a} >= {b}",
                     "be": f"{a} <= {b}", "a": f"{a} > {b}", "l": f"static_cast<{s}>({a}) < static_cast<{s}>({b})",
                     "ge": f"static_cast<{s}>({a}) >= static_cast<{s}>({b})",
                     "le": f"static_cast<{s}>({a}) <= static_cast<{s}>({b})",
                     "g": f"static_cast<{s}>({a}) > static_cast<{s}>({b})",
                     "s": f"{result} < 0", "ns": f"{result} >= 0"}
        else:
            result = f"static_cast<{u}>(fa)"
            table = {"e": f"{result} == 0", "ne": f"{result} != 0",
                     "s": f"static_cast<{s}>({result}) < 0", "ns": f"static_cast<{s}>({result}) >= 0"}
            if producer.mnemonic in (M.TEST, M.AND, M.OR, M.XOR):
                # Logical operations clear CF and OF.
                table.update({"b": "false", "ae": "true", "be": f"{result} == 0", "a": f"{result} != 0",
                              "l": table["s"], "ge": table["ns"],
                              "le": f"{result} == 0 || {table['s']}", "g": f"{result} != 0 && {table['ns']}"})
        if code not in table:
            raise ValueError(f"unsupported condition after {producer.mnemonic} at RVA {jcc.ip:#x}")
        return table[code]

    def statement(self, ins, sets_flags=False, producer=None):
        """Return C++ for one instruction, the low bytes it reads from each full register and the
        width it writes to each full register.

        sets_flags records the flag inputs for a later consumer; producer is the
        instruction whose flags a SETcc or CMOVcc reads."""
        mnemonic = ins.mnemonic
        width = self.width(ins)
        reads, writes = {}, {}

        def read(register):
            reads[full(register)] = max(reads.get(full(register), 0), RegisterExt.size(register))

        def note(*numbers):
            for number in numbers:
                kind = ins.op_kind(number)
                if kind == OpKind.REGISTER:
                    read(ins.op_register(number))
                elif kind == OpKind.MEMORY:
                    for register in (ins.memory_base, ins.memory_index):
                        # A frame access uses RSP's constant offset, not its value (address() rejects the rest).
                        if register not in (R.NONE, R.RSP):
                            read(register)

        if ins.op_count and ins.op0_kind == OpKind.REGISTER:
            writes[full(ins.op0_register)] = width
        elif ins.op_count and ins.op0_kind == OpKind.MEMORY:
            note(0)
        if mnemonic == M.NOP:
            return "", {}, {}
        if mnemonic in (M.PUSH, M.POP):
            # Frame accepts only PUSH and POP of a 64-bit nonvolatile register.
            if mnemonic == M.PUSH:
                note(0)
                return f"store<std::uint64_t>({self.slot(ins)}, {self.reg(ins.op0_register)});", reads, {}
            return self.write(ins, 8, f"load<std::uint64_t>({self.slot(ins)})"), {}, writes
        if ins.ip in self.adjustments:
            # SUB or ADD RSP, imm: Frame knows RSP as a constant offset, so nothing is computed.
            if sets_flags:
                raise ValueError(f"flags of a stack adjustment are read at RVA {ins.ip:#x}")
            return "", {}, {}
        if mnemonic == M.MOV:
            note(1)
            return self.write(ins, width, self.operand(ins, 1, width)), reads, writes
        if mnemonic in (M.MOVZX, M.MOVSX, M.MOVSXD):
            note(1)
            source_width = (RegisterExt.size(ins.op1_register) if ins.op1_kind == OpKind.REGISTER
                            else _memory_width(ins))
            value = self.operand(ins, 1, source_width)
            if mnemonic != M.MOVZX:
                value = f"static_cast<{unsigned(width)}>(static_cast<{signed(width)}>(static_cast<{signed(source_width)}>({value})))"
            return self.write(ins, width, value), reads, writes
        if mnemonic == M.LEA:
            note(1)
            return self.write(ins, width, self.address(ins)), reads, writes
        if mnemonic in (*ALU, M.CMP, M.TEST):
            same = (mnemonic in (M.XOR, M.SUB) and ins.op0_kind == ins.op1_kind == OpKind.REGISTER
                    and ins.op0_register == ins.op1_register)
            if not same:
                note(0, 1)
            a = self.operand(ins, 0, width) if not same else f"static_cast<{unsigned(width)}>(0)"
            b = self.operand(ins, 1, width) if not same else a
            operator = ALU.get(mnemonic, "&")
            lines = []
            if sets_flags:
                self.flags = True
                if mnemonic in (M.CMP, M.SUB):
                    lines.append(f"fa = {a}; fb = {b};")
                else:
                    lines.append(f"fa = static_cast<{unsigned(width)}>({a} {operator} {b});")
            if mnemonic in ALU:
                lines.append(self.write(ins, width, f"{a} {operator} {b}"))
            else:
                writes.clear()
            return " ".join(lines), reads, writes
        if mnemonic in (M.INC, M.DEC, M.NEG, M.NOT):
            note(0)
            a = self.operand(ins, 0, width)
            value = {M.INC: f"{a} + 1u", M.DEC: f"{a} - 1u", M.NEG: f"0u - {a}", M.NOT: f"~{a}"}[mnemonic]
            line = self.write(ins, width, value)
            if sets_flags:
                if mnemonic not in (M.INC, M.DEC):
                    raise ValueError(f"unsupported flag producer at RVA {ins.ip:#x}")
                self.flags = True
                line = f"fa = static_cast<{unsigned(width)}>({value}); " + line
            return line, reads, writes
        if mnemonic in SHIFTS:
            note(0)
            a = self.operand(ins, 0, width)
            # x86 masks the count to six bits for 64-bit operands and to five bits otherwise, so an
            # 8- or 16-bit destination can be shifted by up to 31. The shift is done in 64 bits
            # (count < 64, no host overflow) and the write truncates the result to the destination.
            mask = 63 if width == 8 else 31
            if ins.op1_kind == OpKind.REGISTER:
                if ins.op1_register != R.CL:
                    raise ValueError(f"unsupported shift count at RVA {ins.ip:#x}")
                read(R.CL)
                count = f"({self.reg(R.RCX)} & {mask}u)"
            else:
                count = f"{ins.immediate(1) & mask}u"
            if mnemonic == M.SAR:
                a = f"static_cast<std::int64_t>(static_cast<{signed(width)}>({a}))"
            else:
                a = f"static_cast<std::uint64_t>({a})"
            return self.write(ins, width, f"{a} {SHIFTS[mnemonic]} {count}"), reads, writes
        if mnemonic == M.IMUL and ins.op_count in (2, 3):
            note(*range(ins.op_count))
            if ins.op_count == 2:
                a, b = self.operand(ins, 0, width), self.operand(ins, 1, width)
            else:
                a, b = self.operand(ins, 1, width), self.operand(ins, 2, width)
            if width == 2:
                # Two uint16_t factors would be promoted to int, where 0xffff * 0xffff overflows.
                a, b = f"static_cast<std::uint32_t>({a})", f"static_cast<std::uint32_t>({b})"
            return self.write(ins, width, f"{a} * {b}"), reads, writes
        if mnemonic in SETCC:
            condition = self.condition(producer, ins)
            if ins.op0_kind == OpKind.MEMORY:
                return f"store<std::uint8_t>({self.address(ins)}, static_cast<std::uint8_t>({condition}));", reads, writes
            # A byte write: it keeps bits 8..63 of the full register and does not read them.
            return self.write(ins, 1, condition), reads, writes
        if mnemonic in CMOVCC:
            if width not in (4, 8):
                raise ValueError(f"unsupported partial register write at RVA {ins.ip:#x}")
            note(0, 1)
            condition = self.condition(producer, ins)
            source, destination = self.operand(ins, 1, width), self.operand(ins, 0, width)
            # A 32-bit CMOVcc zero-extends the destination even when the condition is false,
            # and a memory source is read either way.
            if ins.op1_kind == OpKind.MEMORY:
                line = self.write(ins, width, f"({condition}) ? source : {destination}")
                # A volatile read: when the condition folds to false the compiler may not drop the load,
                # which faults on hardware for an inaccessible source.
                source = f"load_always<{unsigned(width)}>({self.address(ins)})"
                return f"{{ const {unsigned(width)} source = {source}; {line} }}", reads, writes
            return self.write(ins, width, f"({condition}) ? {source} : {destination}"), reads, writes
        if mnemonic == M.RET:
            # Which bytes of RAX are a return value is decided by the definedness pass in lift().
            return "return rax;", {}, {}
        raise ValueError(f"unsupported instruction at RVA {ins.ip:#x}: {ins}")


def _memory_width(ins):
    width = MemorySizeExt.size(ins.memory_size)
    if width not in (1, 2, 4, 8):
        raise ValueError(f"unsupported memory width at RVA {ins.ip:#x}")
    return width


INFO = InstructionInfoFactory()
WRITE_ACCESS = {OpAccess.WRITE, OpAccess.READ_WRITE, OpAccess.COND_WRITE, OpAccess.READ_COND_WRITE}


class Frame:
    """RSP as entry RSP + a constant at each instruction, and the stack bytes each instruction accesses.

    offsets: RVA -> RSP - entry RSP before the instruction. accesses: RVA -> (offset of the first byte from entry
    RSP, width, reads, writes). released: RVA -> (RSP before, RSP after) for an ADD RSP or POP, which leaves
    those bytes below RSP, where their contents may change. The frame array starts at entry RSP + start, the lowest offset rounded down to
    8 mod 16: with RSP + 8 a multiple of 16 at entry, as the ABI requires, every array byte then has the address
    residue mod 16 of the stack byte it stands for. It ends with the home space at entry RSP + 40."""

    def __init__(self, function):
        self.offsets, self.accesses, self.adjustments, self.released = {function.entry: 0}, {}, set(), {}
        work = [function.entry]
        while work:
            ip = work.pop()
            after = self.step(function.instructions[ip], self.offsets[ip])
            if after > self.offsets[ip]:
                self.released[ip] = (self.offsets[ip], after)
            for successor in function.successors[ip]:
                if successor not in self.offsets:
                    self.offsets[successor] = after
                    work.append(successor)
                elif self.offsets[successor] != after:
                    raise ValueError(f"stack depth differs at join RVA {successor:#x}: entry RSP"
                                     f"{self.offsets[successor]:+#x} and entry RSP{after:+#x}")
        for ip in sorted(self.offsets):
            if function.instructions[ip].mnemonic == M.RET and self.offsets[ip]:
                raise ValueError(f"stack not balanced at RET RVA {ip:#x}: RSP is entry RSP{self.offsets[ip]:+#x}")
        low = min(self.offsets.values())
        self.start = low - (low + 8) % 16
        self.size = HOME_END - self.start
        if self.size > MAX_FRAME:
            raise ValueError(f"frame of {self.size} bytes exceeds the {MAX_FRAME}-byte bound")

    def access(self, ins, rsp, offset, width, reads, writes):
        if offset < rsp:
            raise ValueError(f"stack access below RSP at RVA {ins.ip:#x}")
        if offset < 8 and offset + width > 0:
            raise ValueError(f"return address slot accessed at RVA {ins.ip:#x}")
        if offset + width > HOME_END:
            raise ValueError(f"unsupported stack argument at RVA {ins.ip:#x}: entry RSP{offset:+#x}")
        self.accesses[ins.ip] = (offset, width, reads, writes)

    def step(self, ins, rsp):
        """RSP after ins; rejects every use of RSP other than a constant change or a frame access."""
        ip, mnemonic = ins.ip, ins.mnemonic
        if mnemonic == M.RET:
            return rsp
        if mnemonic in (M.PUSH, M.POP):
            if ins.op0_kind != OpKind.REGISTER or ins.op0_register not in NONVOLATILE:
                raise ValueError(f"unsupported push or pop at RVA {ip:#x}: {ins}")
            pushed = rsp - 8 if mnemonic == M.PUSH else rsp
            self.access(ins, pushed, pushed, 8, mnemonic == M.POP, mnemonic == M.PUSH)
            return pushed if mnemonic == M.PUSH else rsp + 8
        if (mnemonic in (M.SUB, M.ADD) and ins.op0_kind == OpKind.REGISTER and ins.op0_register == R.RSP
                and ins.op1_kind in (OpKind.IMMEDIATE8TO64, OpKind.IMMEDIATE32TO64)):
            change = ins.immediate(1) & ((1 << 64) - 1)
            change -= (change >> 63) << 64
            after = rsp - change if mnemonic == M.SUB else rsp + change
            if change % 8 or after > 0:
                raise ValueError(f"unsupported stack adjustment at RVA {ip:#x}: {ins}")
            self.adjustments.add(ip)
            return after
        info = INFO.info(ins)
        if any(RegisterExt.full_register(used.register) == R.RSP and used.access in WRITE_ACCESS
               for used in info.used_registers()):
            raise ValueError(f"dynamic frame at RVA {ip:#x}: {ins}")
        if (any(ins.op_kind(n) == OpKind.REGISTER and RegisterExt.full_register(ins.op_register(n)) == R.RSP
                for n in range(ins.op_count))
                or mnemonic == M.LEA and RegisterExt.full_register(ins.memory_base) == R.RSP):
            raise ValueError(f"frame address escapes at RVA {ip:#x}: {ins}")
        if mnemonic != M.NOP and ins.memory_base == R.RSP and OpKind.MEMORY in map(ins.op_kind, range(ins.op_count)):
            used = [memory for memory in info.used_memory() if memory.base == R.RSP]
            if (ins.memory_index != R.NONE or ins.has_segment_prefix or len(used) != 1
                    or used[0].access not in (OpAccess.READ, OpAccess.WRITE, OpAccess.READ_WRITE)):
                raise ValueError(f"unsupported stack operand at RVA {ip:#x}: {ins}")
            displacement = ins.memory_displacement - ((ins.memory_displacement >> 63) << 64)
            self.access(ins, rsp, rsp + displacement, _memory_width(ins), used[0].access != OpAccess.WRITE,
                        used[0].access != OpAccess.READ)
        return rsp


def slot_register(ins):
    """The nonvolatile register that PUSH, POP or a 64-bit MOV copies whole to or from the frame, else None."""
    if ins.mnemonic in (M.PUSH, M.POP):
        return ins.op0_register
    if ins.mnemonic == M.MOV and ins.memory_base == R.RSP:
        for number in (0, 1):
            if ins.op_kind(number) == OpKind.REGISTER and ins.op_register(number) in NONVOLATILE:
                return ins.op_register(number)
    return None


def prove_frame(function, order, effects, frame):
    """Check that every stack byte is written before it is read and that every RET is reached with each
    nonvolatile register holding its entry value, on every path.

    Per stack byte: 1 once a store writes it; 2 + 8 * i + k while it holds byte k of the entry value of
    NONVOLATILE[i], saved by PUSH or MOV [RSP+d] while that register holds its entry value; 0 when not
    written on some path, or released since: when ADD RSP or POP raises RSP, the bytes it leaves below RSP
    become 0 after the POP has read its source, because their contents may change before a later allocation
    brings them back into the frame. Per nonvolatile register: "entry", "written" since entry or the last restore, or
    None when paths disagree. A join keeps what both sides agree on. A save is not a read of the entry value
    as data, so its register read is removed from effects before the register pass."""
    instructions = function.instructions
    saved = {register: bytes(range(2 + 8 * i, 10 + 8 * i)) for i, register in enumerate(NONVOLATILE)}

    def step(ip, status, data):
        status, restored = dict(zip(NONVOLATILE, status)), None
        if ip in frame.accesses:
            offset, width, reads, writes = frame.accesses[ip]
            index, register = offset - frame.start, slot_register(instructions[ip])
            if reads and register is not None and data[index:index + 8] == saved[register]:
                restored = register
            if writes:
                value = saved[register] if register is not None and status[register] == "entry" else b"\1" * width
                data = data[:index] + value + data[index + width:]
        if ip in frame.released:
            low, high = (offset - frame.start for offset in frame.released[ip])
            data = data[:low] + bytes(high - low) + data[high:]
        for register in (*effects[ip][1], *effects[ip][2]):
            if register in status:
                status[register] = "entry" if register == restored else "written"
        return tuple(status.values()), data

    state = {function.entry: (("entry",) * len(NONVOLATILE), bytes(frame.size))}
    work = [function.entry]
    while work:
        ip = work.pop()
        out = step(ip, *state[ip])
        for successor in function.successors[ip]:
            old = state.get(successor)
            new = out if old is None else (tuple(a if a == b else None for a, b in zip(old[0], out[0])),
                                           bytes(a if a == b else 0 for a, b in zip(old[1], out[1])))
            if new != old:
                state[successor] = new
                work.append(successor)
    for ip in order:
        ins, (status, data) = instructions[ip], state[ip]
        status, reads, register = dict(zip(NONVOLATILE, status)), effects[ip][0], slot_register(ins)
        offset, width, loads, stores = frame.accesses.get(ip, (0, 0, False, False))
        if stores and register is not None and status[register] == "entry":
            del reads[register]
        for read in reads:
            if status.get(read, "written") != "written":
                raise ValueError(f"nonvolatile register {NAMES[read]} may hold the caller's value where RVA "
                                 f"{ip:#x} reads it")
        got = data[offset - frame.start:offset - frame.start + width]
        if loads and got != b"\1" * width and not (register is not None and got == saved[register]):
            if 0 in got:
                raise ValueError(f"undefined stack byte at entry RSP{offset + got.index(0):+#x} at RVA {ip:#x}")
            raise ValueError(f"stack bytes at entry RSP{offset:+#x} hold the saved "
                             f"{NAMES[NONVOLATILE[(max(got) - 2) // 8]]}, read as data at RVA {ip:#x}")
        if ins.mnemonic == M.RET:
            for register, value in status.items():
                if value != "entry":
                    raise ValueError(f"nonvolatile register {NAMES[register]} is not restored on every path to "
                                     f"the RET at RVA {ip:#x}")


def flag_producer(function, edges, consumer):
    """The instruction whose flags consumer reads, within one straight-line run."""
    current = consumer
    for _ in range(MAX_FLAG_DISTANCE):
        before = function.ending.get(current.ip)
        if (current.ip in edges or current.ip == function.entry or before is None
                or before.flow_control != FlowControl.NEXT):
            raise ValueError(f"flags cross a join before RVA {consumer.ip:#x}")
        if before.mnemonic not in FLAG_NEUTRAL:
            if before.mnemonic not in FLAG_PRODUCERS:
                raise ValueError(f"unsupported flag producer at RVA {before.ip:#x}")
            return before
        current = before
    raise ValueError(f"flag producer too far before RVA {consumer.ip:#x}")


def lift(pe, name, arguments=DEFAULT_ARGUMENTS):
    """Translate one export that takes the given number of integer arguments, 3 or 4."""
    if not isinstance(arguments, int) or arguments not in ARGUMENT_COUNTS:
        raise ValueError(f"unsupported argument count {arguments!r} for export {name}: expected 3 or 4")
    entry = export_rva(pe, name)
    function = Function(pe, entry)
    function.arguments = ARGUMENT_REGISTERS[:arguments]
    edges = function.explore()
    lifter = Lifter()
    order = sorted(function.instructions)
    instructions = function.instructions
    frame = Frame(function)
    lifter.frame = {ip: access[0] - frame.start for ip, access in frame.accesses.items()}
    lifter.adjustments = frame.adjustments
    producers = {ip: flag_producer(function, edges, ins) for ip, ins in instructions.items()
                 if ins.flow_control == FlowControl.CONDITIONAL_BRANCH or ins.mnemonic in SETCC | CMOVCC}
    sets_flags = {producer.ip for producer in producers.values()}
    loads = {sequence[0]: index for index, _, sequence, _, _, _ in function.dispatches.values()}
    skipped = {ip for _, _, sequence, _, _, _ in function.dispatches.values() for ip in sequence}
    body = {}
    effects = {}
    for ip in order:
        ins = instructions[ip]
        if ins.has_lock_prefix or ins.has_rep_prefix or ins.has_repne_prefix:
            raise ValueError(f"unsupported prefix at RVA {ip:#x}")
        body[ip] = ""
        if ins.flow_control == FlowControl.CONDITIONAL_BRANCH:
            body[ip] = f"if ({lifter.condition(producers[ip], ins)}) goto loc_{ins.near_branch_target:x};"
            effects[ip] = ({}, {}, set())
        elif ins.flow_control == FlowControl.UNCONDITIONAL_BRANCH:
            body[ip] = f"goto loc_{ins.near_branch_target:x};"
            effects[ip] = ({}, {}, set())
        elif ip in function.dispatches:
            index, targets, _, _, target, _ = function.dispatches[ip]
            cases = {}
            for number, destination in enumerate(targets):
                cases.setdefault(destination, []).append(number)
            lines = [f"switch ({lifter.reg(index)}) {{"]
            for destination, numbers in cases.items():
                labels = " ".join(f"case {n}:" for n in numbers)
                lines.append(f"    {labels} goto loc_{destination:x};")
            lines += ["    default: std::abort();", "}"]
            body[ip] = "\n    ".join(lines)
            # The guest jump target has no host meaning after the dispatch.
            effects[ip] = ({}, {}, {target})
        elif ip in skipped:
            # The table load reads the 64-bit index; it and the add leave guest addresses behind.
            effects[ip] = ({loads[ip]: 8} if ip in loads else {}, {}, {full(ins.op0_register)})
        elif ins.mnemonic == M.LEA and ins.is_ip_rel_memory_operand and RegisterExt.is_gpr64(ins.op0_register):
            # A guest address is only usable as a jump-table base, which the switch replaces.
            effects[ip] = ({}, {}, {full(ins.op0_register)})
        else:
            text, reads, writes = lifter.statement(ins, ip in sets_flags, producers.get(ip))
            body[ip] = text
            effects[ip] = (reads, writes, set())
        if R.RSP in set().union(*effects[ip]):
            # Frame rejects every use of RSP whose offset it does not know, so RSP is never a C++ variable.
            raise ValueError(f"unsupported use of rsp at RVA {ip:#x}")
    prove_frame(function, order, effects, frame)

    # Per register: (low bytes defined on every path: 0, 1, 2 or 8; may hold a guest address that
    # the translation does not reproduce). Arguments are defined at entry; joins meet as (min, or).
    state = {ip: dict.fromkeys(NAMES, (8, False)) for ip in order}
    state[entry] = {r: (8 if r in function.arguments else 0, False) for r in NAMES}
    changed = True
    while changed:
        changed = False
        for ip in order:
            _, writes, kills = effects[ip]
            out = dict(state[ip])
            for r, width in writes.items():
                # A 32- or 64-bit write defines all eight bytes; an 8- or 16-bit write keeps the rest.
                out[r] = (8, False) if width >= 4 else (max(out[r][0], width), out[r][1])
            for r in kills:
                out[r] = (0, True)
            for successor in function.successors[ip]:
                old = state[successor]
                merged = {r: (min(old[r][0], out[r][0]), old[r][1] or out[r][1]) for r in NAMES}
                if merged != old:
                    state[successor] = merged
                    changed = True
    widths = []
    for ip in order:
        missing = [r for r, width in effects[ip][0].items() if state[ip][r][0] < width]
        if missing:
            raise ValueError(f"undefined register {NAMES[min(missing)]} at RVA {ip:#x}")
        if instructions[ip].mnemonic == M.RET:
            defined, guest = state[ip][R.RAX]
            if guest:
                raise ValueError(f"return value may hold a guest address at RVA {ip:#x}")
            widths.append(defined)
    # Consecutive low RAX bytes defined at every reachable RET; None when no RET is reachable.
    function.return_width = min(widths) if widths else None

    labels = set(edges)
    if order[0] != entry:
        # Emission follows address order. Code that the function reaches below its entry
        # comes first in the text, so execution has to start with a jump to the entry.
        labels.add(entry)
    for position, ip in enumerate(order):
        ins = instructions[ip]
        following = order[position + 1] if position + 1 < len(order) else None
        if ins.flow_control in (FlowControl.NEXT, FlowControl.CONDITIONAL_BRANCH) and following != ins.next_ip:
            labels.add(ins.next_ip)
    locals_ = sorted((lifter.used | {R.RAX}) - set(function.arguments), key=lambda r: NAMES[r])
    declarations = [f"word {NAMES[r]} = 0;" for r in locals_]
    if lifter.flags:
        declarations.append("word fa = 0, fb = 0;")
    if lifter.frame:
        declarations.append(f"alignas(16) std::uint8_t frame[{frame.size}] = {{}};  "
                            f"// entry RSP{frame.start:+#x} to entry RSP+{HOME_END:#x}")
    text = [f"    goto loc_{entry:x};"] if order[0] != entry else []
    for position, ip in enumerate(order):
        if ip in labels:
            text.append(f"loc_{ip:x}:")
        if body[ip]:
            text.append("    " + body[ip])
        ins = instructions[ip]
        following = order[position + 1] if position + 1 < len(order) else None
        if ins.flow_control in (FlowControl.NEXT, FlowControl.CONDITIONAL_BRANCH) and following != ins.next_ip:
            text.append(f"    goto loc_{ins.next_ip:x};")
    signature = (f'extern "C" __declspec(dllexport) word lifted_{name}'
                 f'({", ".join(f"word {NAMES[r]}" for r in function.arguments)})')
    comment = []
    if function.return_width is None:
        comment = ["// RAX: no reachable normal return"]
    elif function.return_width < 8:
        comment = [f"// RAX: {function.return_width} low byte(s) are defined at every reachable RET"]
    source = [*comment, signature + " {", *("    " + d for d in declarations), *text, "}"]
    return "\n".join(source), function


PRELUDE = """#include <cstdint>
#include <cstdlib>
#include <cstring>
using word = std::uint64_t;
template <class T> static T load(word address) {
    T value;
    std::memcpy(&value, reinterpret_cast<const void*>(address), sizeof(value));
    return value;
}
// A read the compiler must perform even when its value is unused (a CMOVcc memory source).
template <class T> static T load_always(word address) {
    return *reinterpret_cast<const volatile T*>(address);
}
template <class T> static void store(word address, T value) {
    std::memcpy(reinterpret_cast<void*>(address), &value, sizeof(value));
}
"""


def parse_entry(spec):
    """Split an export-list item, "name" or "name:N", into the name and its integer argument count."""
    name, colon, count = spec.partition(":")
    if not colon:
        return name, DEFAULT_ARGUMENTS
    if not (count.isascii() and count.isdigit()):
        raise ValueError(f"unsupported argument count {count!r} for export {name}: expected 3 or 4")
    return name, int(count)


def translate_pe(pe, names):
    if pe.FILE_HEADER.Machine != 0x8664 or pe.OPTIONAL_HEADER.Magic != 0x20B:
        raise ValueError("expected AMD64 PE32+")
    functions = [lift(pe, *parse_entry(name)) for name in names]
    return PRELUDE + "\n".join(f"\n{source}" for source, _ in functions) + "\n", [f for _, f in functions]


def translate(image, names):
    with pefile.PE(str(image), fast_load=True) as pe:
        return translate_pe(pe, names)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("image", type=Path)
    parser.add_argument("exports", help='comma-separated export names; "name:4" translates that export with a '
                                        "fourth integer argument in R9, and the host must pass four")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    try:
        source, functions = translate(args.image, args.exports.split(","))
        args.output.write_text(source, encoding="utf-8")
        for function in functions:
            print(f"RVA {function.entry:#x}: {len(function.instructions)} instructions, "
                  f"{sum(len(d[1]) for d in function.dispatches.values())} table entries, "
                  + ("no reachable normal return" if function.return_width is None else
                     f"{function.return_width} defined RAX byte(s) at every reachable RET"))
    except (ValueError, OSError, pefile.PEFormatError) as error:
        parser.exit(1, f"{error}\n")
