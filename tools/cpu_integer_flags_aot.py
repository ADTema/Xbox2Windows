"""Lift bounded Windows x64 leaf functions for same-block ADD/SUB/CMP -> LAHF to C++.

Each export uses the leaf ABI void fn(word rcx, word rdx, word r8), where rcx,
rdx and r8 carry flat host pointers to caller-owned buffers (rcx and rdx are
inputs, r8 is the output). Volatile GPRs (rax, rcx, rdx, r8, r9, r10, r11) are
modeled across 8-, 16-, 32- and 64-bit views (including high-byte ah/ch/dh),
along with per-flag definedness tracking for CF, PF, AF, ZF, SF and OF.

Supported uncovered Integer form (docs/coverage/x64_zen2.tsv):
  - lahf: write (SF<<7)|(ZF<<6)|(AF<<4)|(PF<<2)|0x02|CF to AH, preserving AL
    and RAX[63:16] without modifying any flags

Supported instructions:
  - Register-destination ADD, SUB and CMP at 8, 16, 32 and 64 bits (register or
    immediate source), defining CF, PF, AF, ZF, SF and OF
  - LAHF in the same basic block (requires CF, PF, AF, ZF, SF and RAX defined)
  - SETcc live flag consumers to 8-bit volatile GPR or [r8 + disp] (requires
    each consumed flag to be defined)
  - MOV (8/16/32/64-bit volatile GPRs, immediates, flat [rcx/rdx/r8 + disp]
    reads with dead-read ordering, and [r8 + disp] writes)
  - Terminal RET (RETNQ)

Out-of-scope / rejected:
  - PUSHF, POPF, PUSHFQ, POPFQ, SAHF, INC, DEC, NEG, ADC, SBB, CLC/STC/CMC,
    AND/OR/XOR/TEST, shifts, multiplies, nonvolatile GPRs, RSP/stack ops,
    branches, calls, instruction prefixes, VEX/EVEX/XOP encodings, non-r8
    stores, RIP-relative/indexed addressing, undefined flag/GPR reads, and
    trailing/missing-ret streams.
"""

import argparse
from pathlib import Path

import pefile
from iced_x86 import (
    Code,
    Decoder,
    EncodingKind,
    MemorySizeExt,
    Mnemonic as M,
    OpKind,
    Register as R,
    RegisterExt,
)

from cpu_leaf_aot import bounded_code, export_rva


ARGUMENTS = {R.RCX: "rcx", R.RDX: "rdx", R.R8: "r8"}

# (base_name, bits, shift, mask)
GPR_SPECS = {
    R.RAX: ("rax", 64, 0, 0xFFFFFFFFFFFFFFFF),
    R.EAX: ("rax", 32, 0, 0xFFFFFFFF),
    R.AX: ("rax", 16, 0, 0xFFFF),
    R.AL: ("rax", 8, 0, 0xFF),
    R.AH: ("rax", 8, 8, 0xFF),
    R.RCX: ("rcx", 64, 0, 0xFFFFFFFFFFFFFFFF),
    R.ECX: ("rcx", 32, 0, 0xFFFFFFFF),
    R.CX: ("rcx", 16, 0, 0xFFFF),
    R.CL: ("rcx", 8, 0, 0xFF),
    R.CH: ("rcx", 8, 8, 0xFF),
    R.RDX: ("rdx", 64, 0, 0xFFFFFFFFFFFFFFFF),
    R.EDX: ("rdx", 32, 0, 0xFFFFFFFF),
    R.DX: ("rdx", 16, 0, 0xFFFF),
    R.DL: ("rdx", 8, 0, 0xFF),
    R.DH: ("rdx", 8, 8, 0xFF),
    R.R8: ("r8", 64, 0, 0xFFFFFFFFFFFFFFFF),
    R.R8D: ("r8", 32, 0, 0xFFFFFFFF),
    R.R8W: ("r8", 16, 0, 0xFFFF),
    R.R8L: ("r8", 8, 0, 0xFF),
    R.R9: ("r9", 64, 0, 0xFFFFFFFFFFFFFFFF),
    R.R9D: ("r9", 32, 0, 0xFFFFFFFF),
    R.R9W: ("r9", 16, 0, 0xFFFF),
    R.R9L: ("r9", 8, 0, 0xFF),
    R.R10: ("r10", 64, 0, 0xFFFFFFFFFFFFFFFF),
    R.R10D: ("r10", 32, 0, 0xFFFFFFFF),
    R.R10W: ("r10", 16, 0, 0xFFFF),
    R.R10L: ("r10", 8, 0, 0xFF),
    R.R11: ("r11", 64, 0, 0xFFFFFFFFFFFFFFFF),
    R.R11D: ("r11", 32, 0, 0xFFFFFFFF),
    R.R11W: ("r11", 16, 0, 0xFFFF),
    R.R11L: ("r11", 8, 0, 0xFF),
}

NONVOLATILE_GPRS = {
    R.RBX, R.EBX, R.BX, R.BL, R.BH,
    R.RBP, R.EBP, R.BP, R.BPL,
    R.RSI, R.ESI, R.SI, R.SIL,
    R.RDI, R.EDI, R.DI, R.DIL,
    R.R12, R.R12D, R.R12W, R.R12L,
    R.R13, R.R13D, R.R13W, R.R13L,
    R.R14, R.R14D, R.R14W, R.R14L,
    R.R15, R.R15D, R.R15W, R.R15L,
}

STACK_POINTER_REGS = {R.RSP, R.ESP, R.SP, R.SPL}

IMMEDIATE_KINDS = {
    OpKind.IMMEDIATE8,
    OpKind.IMMEDIATE16,
    OpKind.IMMEDIATE32,
    OpKind.IMMEDIATE64,
    OpKind.IMMEDIATE8TO16,
    OpKind.IMMEDIATE8TO32,
    OpKind.IMMEDIATE8TO64,
    OpKind.IMMEDIATE32TO64,
}

ARITH_PRODUCERS = {M.ADD, M.SUB, M.CMP}

SETCC_SPECS = {
    Code.SETO_RM8: (("of",), "of"),
    Code.SETNO_RM8: (("of",), "!of"),
    Code.SETB_RM8: (("cf",), "cf"),
    Code.SETAE_RM8: (("cf",), "!cf"),
    Code.SETE_RM8: (("zf",), "zf"),
    Code.SETNE_RM8: (("zf",), "!zf"),
    Code.SETBE_RM8: (("cf", "zf"), "cf || zf"),
    Code.SETA_RM8: (("cf", "zf"), "!cf && !zf"),
    Code.SETS_RM8: (("sf",), "sf"),
    Code.SETNS_RM8: (("sf",), "!sf"),
    Code.SETP_RM8: (("pf",), "pf"),
    Code.SETNP_RM8: (("pf",), "!pf"),
    Code.SETL_RM8: (("sf", "of"), "sf != of"),
    Code.SETGE_RM8: (("sf", "of"), "sf == of"),
    Code.SETLE_RM8: (("zf", "sf", "of"), "zf || (sf != of)"),
    Code.SETG_RM8: (("zf", "sf", "of"), "!zf && (sf == of)"),
}

PRELUDE = """#include <atomic>
#include <cstdint>
#include <cstring>
#include <intrin.h>

extern "C" __declspec(dllexport) std::uint32_t host_has_lahf() {
    int regs[4]{};
    __cpuid(regs, static_cast<int>(0x80000000u));
    if (static_cast<std::uint32_t>(regs[0]) < 0x80000001u) return 0u;
    __cpuid(regs, static_cast<int>(0x80000001u));
    return (static_cast<std::uint32_t>(regs[2]) & 1u) != 0u ? 1u : 0u;
}

using word = std::uint64_t;

// Guest reads can fault even when the translated result is dead. Keep surrounding guest
// writes on their original side of the read when the compiler inlines these helpers.
template <class T>
static inline T load_mem(word address) {
    std::atomic_signal_fence(std::memory_order_seq_cst);
    const T value = *reinterpret_cast<const volatile T __unaligned*>(address);
    std::atomic_signal_fence(std::memory_order_seq_cst);
    return value;
}

template <class T>
static inline void store_mem(word address, T value) {
    std::memcpy(reinterpret_cast<void*>(address), &value, sizeof(T));
}

static inline bool calc_pf(std::uint64_t val) {
    unsigned x = static_cast<std::uint8_t>(val);
    x ^= x >> 4u;
    x ^= x >> 2u;
    x ^= x >> 1u;
    return (x & 1u) == 0u;
}

static inline std::uint8_t pack_lahf(bool cf, bool pf, bool af, bool zf, bool sf) {
    return static_cast<std::uint8_t>(
        (sf ? 0x80u : 0u) |
        (zf ? 0x40u : 0u) |
        (af ? 0x10u : 0u) |
        (pf ? 0x04u : 0u) |
        0x02u |
        (cf ? 0x01u : 0u));
}

static inline std::uint64_t width_mask(unsigned bits) {
    return bits == 64u ? ~0ull : ((1ull << bits) - 1ull);
}

static inline std::uint64_t op_add_flags(
        unsigned bits, std::uint64_t a, std::uint64_t b,
        bool& cf, bool& pf, bool& af, bool& zf, bool& sf, bool& of) {
    const std::uint64_t m = width_mask(bits);
    const std::uint64_t ua = a & m;
    const std::uint64_t ub = b & m;
    const std::uint64_t res = (ua + ub) & m;
    cf = res < ua;
    af = ((ua ^ ub ^ res) & 0x10ull) != 0ull;
    pf = calc_pf(res);
    zf = res == 0ull;
    sf = ((res >> (bits - 1u)) & 1ull) != 0ull;
    of = ((((ua ^ res) & (ub ^ res)) >> (bits - 1u)) & 1ull) != 0ull;
    return res;
}

static inline std::uint64_t op_sub_flags(
        unsigned bits, std::uint64_t a, std::uint64_t b,
        bool& cf, bool& pf, bool& af, bool& zf, bool& sf, bool& of) {
    const std::uint64_t m = width_mask(bits);
    const std::uint64_t ua = a & m;
    const std::uint64_t ub = b & m;
    const std::uint64_t res = (ua - ub) & m;
    cf = ua < ub;
    af = ((ua ^ ub ^ res) & 0x10ull) != 0ull;
    pf = calc_pf(res);
    zf = res == 0ull;
    sf = ((res >> (bits - 1u)) & 1ull) != 0ull;
    of = ((((ua ^ ub) & (ua ^ res)) >> (bits - 1u)) & 1ull) != 0ull;
    return res;
}
"""


def reg_info(register, ins):
    """Map volatile GPRs to (base_name, bits, shift, mask), rejecting nonvolatile and RSP."""
    if register in GPR_SPECS:
        return GPR_SPECS[register]
    if register in NONVOLATILE_GPRS:
        raise ValueError(f"nonvolatile GPR {register} at RVA {ins.ip:#x}: {ins}")
    if register in STACK_POINTER_REGS:
        raise ValueError(f"unsupported stack pointer operand {register} at RVA {ins.ip:#x}: {ins}")
    raise ValueError(f"unsupported register {register} at RVA {ins.ip:#x}: {ins}")


def c_type_for_bits(bits):
    return {8: "std::uint8_t", 16: "std::uint16_t", 32: "std::uint32_t", 64: "std::uint64_t"}[bits]


def imm_value(ins, op_index, bits):
    kind = ins.op_kind(op_index)
    if kind == OpKind.IMMEDIATE8:
        val = ins.immediate8
    elif kind == OpKind.IMMEDIATE16:
        val = ins.immediate16
    elif kind == OpKind.IMMEDIATE32:
        val = ins.immediate32
    elif kind == OpKind.IMMEDIATE64:
        val = ins.immediate64
    elif kind == OpKind.IMMEDIATE8TO16:
        val = ins.immediate8to16 & 0xFFFF
    elif kind == OpKind.IMMEDIATE8TO32:
        val = ins.immediate8to32 & 0xFFFFFFFF
    elif kind == OpKind.IMMEDIATE8TO64:
        val = ins.immediate8to64 & 0xFFFFFFFFFFFFFFFF
    elif kind == OpKind.IMMEDIATE32TO64:
        val = ins.immediate32to64 & 0xFFFFFFFFFFFFFFFF
    else:
        raise ValueError(f"expected immediate operand {op_index} at RVA {ins.ip:#x}: {ins}")
    return val & ((1 << bits) - 1)


def lift_code(name, start, raw):
    """Decode and lift one bounded straight-line ADD/SUB/CMP -> LAHF leaf function."""
    instructions = list(Decoder(64, raw, ip=start))
    if not instructions or instructions[-1].next_ip != start + len(raw):
        raise ValueError(f"truncated instruction stream in {name} at RVA {start:#x}")
    if any(ins.is_invalid for ins in instructions):
        bad = next(ins for ins in instructions if ins.is_invalid)
        raise ValueError(f"invalid instruction at RVA {bad.ip:#x}")

    defined_gpr = {"rcx", "rdx", "r8"}
    used_gpr = set()
    clobbered_ptrs = set()

    defined_flags = set()
    used_flags = set()

    statements = []
    returned = False

    def read_reg(reg, ins):
        base, bits, shift, mask = reg_info(reg, ins)
        if base not in defined_gpr:
            raise ValueError(f"undefined GPR {base} at RVA {ins.ip:#x}: {ins}")
        used_gpr.add(base)
        if bits == 64:
            return base, 64
        expr = f"((({base} >> {shift}u) & {mask:#x}ull))" if shift else f"({base} & {mask:#x}ull)"
        return f"static_cast<{c_type_for_bits(bits)}>({expr})", bits

    def write_reg_stmt(reg, expr, ins):
        base, bits, shift, mask = reg_info(reg, ins)
        if base == "r8":
            raise ValueError(f"unsupported write to output buffer pointer r8 at RVA {ins.ip:#x}: {ins}")
        if base == "rcx":
            clobbered_ptrs.add(R.RCX)
        elif base == "rdx":
            clobbered_ptrs.add(R.RDX)
        used_gpr.add(base)
        if bits == 64:
            defined_gpr.add(base)
            return f"{base} = static_cast<word>({expr});"
        if bits == 32:
            defined_gpr.add(base)
            return f"{base} = static_cast<word>(static_cast<std::uint32_t>({expr}));"
        if base not in defined_gpr:
            raise ValueError(f"partial write to undefined GPR {base} at RVA {ins.ip:#x}: {ins}")
        clear_mask = (~(mask << shift)) & 0xFFFFFFFFFFFFFFFF
        return f"{base} = ({base} & {clear_mask:#x}ull) | ((static_cast<word>({expr}) & {mask:#x}ull) << {shift}u);"

    def mem_access(ins, *, write=False):
        base = ins.memory_base
        if (
            ins.is_ip_rel_memory_operand
            or base in (R.NONE, R.RIP, R.EIP, R.RSP, R.ESP)
            or ins.memory_index != R.NONE
            or not RegisterExt.is_gpr64(base)
        ):
            raise ValueError(f"unsupported memory operand at RVA {ins.ip:#x}: {ins}")
        nbytes = MemorySizeExt.size(ins.memory_size)
        if nbytes not in (1, 2, 4, 8):
            raise ValueError(f"unsupported memory width {nbytes} at RVA {ins.ip:#x}: {ins}")
        if base in NONVOLATILE_GPRS:
            raise ValueError(f"nonvolatile GPR base {base} in memory operand at RVA {ins.ip:#x}: {ins}")
        if base not in ARGUMENTS:
            raise ValueError(f"unsupported memory base {base} at RVA {ins.ip:#x}: {ins}")
        if base in clobbered_ptrs:
            raise ValueError(f"memory operand uses clobbered pointer {ARGUMENTS[base]} at RVA {ins.ip:#x}: {ins}")
        if write and base != R.R8:
            raise ValueError(f"non-r8 store memory operand at RVA {ins.ip:#x}: {ins}")
        disp = ins.memory_displacement & ((1 << 64) - 1)
        name_base = ARGUMENTS[base]
        addr = f"({name_base} + {disp:#x}ull)" if disp else name_base
        return addr, nbytes * 8, c_type_for_bits(nbytes * 8)

    def read_operand(ins, op_index, bits, *, allow_mem=True):
        kind = ins.op_kind(op_index)
        if kind == OpKind.REGISTER:
            expr, reg_bits = read_reg(ins.op_register(op_index), ins)
            if reg_bits != bits:
                raise ValueError(f"operand width mismatch at RVA {ins.ip:#x}: {ins}")
            return expr
        if kind == OpKind.MEMORY:
            if not allow_mem:
                raise ValueError(f"unsupported arithmetic memory operand at RVA {ins.ip:#x}: {ins}")
            addr, mem_bits, ctype = mem_access(ins, write=False)
            if mem_bits != bits:
                raise ValueError(f"memory width mismatch at RVA {ins.ip:#x}: {ins}")
            return f"load_mem<{ctype}>({addr})"
        if kind in IMMEDIATE_KINDS:
            return f"{imm_value(ins, op_index, bits):#x}ull"
        raise ValueError(f"unsupported operand {op_index} at RVA {ins.ip:#x}: {ins}")

    def require_flags(flags, ins):
        for flag in flags:
            if flag not in defined_flags:
                raise ValueError(f"undefined flag {flag} read at RVA {ins.ip:#x}: {ins}")
            used_flags.add(flag)

    for ins in instructions:
        if returned:
            raise ValueError(f"unreachable instruction after ret at RVA {ins.ip:#x}: {ins}")
        if ins.has_lock_prefix or ins.has_rep_prefix or ins.has_repne_prefix or ins.has_segment_prefix:
            raise ValueError(f"unsupported instruction prefix at RVA {ins.ip:#x}: {ins}")
        if ins.op_code().encoding in (EncodingKind.VEX, EncodingKind.EVEX, EncodingKind.XOP):
            raise ValueError(f"unsupported vector-encoded instruction at RVA {ins.ip:#x}: {ins}")

        mnemonic = ins.mnemonic

        if ins.code == Code.RETNQ:
            statements.append("return;")
            returned = True

        elif ins.code == Code.LAHF:
            require_flags(("cf", "pf", "af", "zf", "sf"), ins)
            if "rax" not in defined_gpr:
                raise ValueError(f"undefined GPR rax at RVA {ins.ip:#x}: {ins}")
            used_gpr.add("rax")
            statements.append(
                "rax = (rax & ~0xff00ull) | (static_cast<word>(pack_lahf(cf, pf, af, zf, sf)) << 8u);"
            )

        elif ins.code in SETCC_SPECS:
            req_flags, cond_expr = SETCC_SPECS[ins.code]
            require_flags(req_flags, ins)
            val_expr = f"(({cond_expr}) ? 1u : 0u)"
            if ins.op0_kind == OpKind.REGISTER:
                statements.append(write_reg_stmt(ins.op0_register, val_expr, ins))
            elif ins.op0_kind == OpKind.MEMORY:
                addr, mem_bits, ctype = mem_access(ins, write=True)
                if mem_bits != 8:
                    raise ValueError(f"expected 8-bit destination for {ins} at RVA {ins.ip:#x}")
                statements.append(f"store_mem<{ctype}>({addr}, static_cast<{ctype}>({val_expr}));")
            else:
                raise ValueError(f"unsupported setcc destination at RVA {ins.ip:#x}: {ins}")

        elif mnemonic == M.MOV and ins.op_count == 2:
            if ins.op0_kind == OpKind.REGISTER:
                bits = reg_info(ins.op0_register, ins)[1]
                rhs = read_operand(ins, 1, bits, allow_mem=True)
                statements.append(write_reg_stmt(ins.op0_register, rhs, ins))
            elif ins.op0_kind == OpKind.MEMORY:
                addr, bits, ctype = mem_access(ins, write=True)
                rhs = read_operand(ins, 1, bits, allow_mem=False)
                statements.append(f"store_mem<{ctype}>({addr}, static_cast<{ctype}>({rhs}));")
            else:
                raise ValueError(f"unsupported mov operands at RVA {ins.ip:#x}: {ins}")

        elif mnemonic in ARITH_PRODUCERS and ins.op_count == 2:
            if ins.op0_kind != OpKind.REGISTER:
                raise ValueError(f"unsupported arithmetic destination at RVA {ins.ip:#x}: {ins}")
            lhs, bits = read_reg(ins.op0_register, ins)
            rhs = read_operand(ins, 1, bits, allow_mem=False)
            used_flags.update(("cf", "pf", "af", "zf", "sf", "of"))
            defined_flags.update(("cf", "pf", "af", "zf", "sf", "of"))
            helper = "op_add_flags" if mnemonic == M.ADD else "op_sub_flags"
            call = f"{helper}({bits}u, {lhs}, {rhs}, cf, pf, af, zf, sf, of)"
            if mnemonic == M.CMP:
                statements.append(f"(void){call};")
            else:
                statements.append(write_reg_stmt(ins.op0_register, call, ins))

        else:
            raise ValueError(f"unsupported instruction at RVA {ins.ip:#x}: {ins}")

    if not returned:
        raise ValueError(f"missing terminal ret in {name} at RVA {start + len(raw):#x}")

    decls = []
    for gpr in ("rax", "r9", "r10", "r11"):
        if gpr in used_gpr:
            decls.append(f"    word {gpr} = 0ull;")
    for flag in ("cf", "pf", "af", "zf", "sf", "of"):
        if flag in used_flags:
            decls.append(f"    bool {flag} = false;")
    body = [f"    {stmt}" for stmt in statements]
    lines = [
        f'extern "C" __declspec(dllexport) void lifted_{name}(word rcx, word rdx, word r8) {{',
        "    (void)rcx; (void)rdx; (void)r8;",
        *decls,
        *body,
        "}",
    ]
    return "\n".join(lines), len(instructions)


def lift(pe, name):
    entry = export_rva(pe, name)
    raw = bounded_code(pe, entry)
    source, count = lift_code(name, entry, raw)
    return source, entry, count


def translate_pe(pe, names):
    if pe.FILE_HEADER.Machine != 0x8664 or pe.OPTIONAL_HEADER.Magic != 0x20B:
        raise ValueError("expected AMD64 PE32+")
    lifted = [lift(pe, name) for name in names]
    source = PRELUDE + "\n".join(f"\n{text}" for text, _, _ in lifted) + "\n"
    meta = [(name, entry, count) for name, (_, entry, count) in zip(names, lifted)]
    return source, meta


def translate(image, names):
    with pefile.PE(str(image), fast_load=True) as pe:
        return translate_pe(pe, names)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("image", type=Path)
    parser.add_argument("exports", help="comma-separated export names")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    try:
        source, meta = translate(args.image, args.exports.split(","))
        args.output.write_text(source, encoding="utf-8")
        for name, entry, count in meta:
            print(f"{name} at RVA {entry:#x}: {count} instructions")
    except (ValueError, OSError, pefile.PEFormatError) as error:
        parser.exit(1, f"{error}\n")
