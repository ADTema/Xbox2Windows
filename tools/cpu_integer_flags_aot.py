"""Lift bounded Windows x64 leaf functions with integer flag and stack-flag forms to C++.

Each export uses the leaf ABI void fn(word rcx, word rdx, word r8), where rcx,
rdx and r8 carry flat host pointers to caller-owned buffers (rcx and rdx are
inputs, r8 is the output). Volatile GPRs (rax, rcx, rdx, r8, r9, r10, r11) are
modeled across 8-, 16-, 32- and 64-bit views (including high-byte ah/ch/dh),
along with a bounded 256-byte local stack and RFLAGS (CF, PF, AF, ZF, SF, OF,
DF, ID, plus fixed bit 1 and ring-3 IF = 0x0202).

Supported uncovered Integer forms (5 forms from docs/coverage/x64_zen2.tsv):
  - lahf: write (SF<<7)|(ZF<<6)|(AF<<4)|(PF<<2)|0x02|CF to AH, preserving AL and RAX[63:16]
  - pushf / popf: 2-byte stack stride (RSP -/+ 2) for low 16-bit FLAGS
  - pushfq / popfq: 8-byte stack stride (RSP -/+ 8) for 64-bit RFLAGS (including ID bit 21)

Support instructions: sahf, clc, stc, cmc, cld, std, push/pop (16/64-bit
volatile GPRs), mov (8/16/32/64-bit volatile GPRs, immediates, flat [rcx/rdx/r8
+ disp] reads, [r8 + disp] writes, and initialized [rsp + disp] local stack
reads), add, adc, sub, sbb, cmp, inc, dec, neg, and, or, xor, test, and
terminal ret.

Policy and rejections:
  - Definedness tracking on all GPRs, local stack bytes, and individual flags:
    logical ops (and/or/xor/test) leave AF undefined, inc/dec preserve CF, sahf
    leaves OF/DF/ID unchanged, popf leaves ID unchanged; reading an undefined
    flag or GPR rejects.
  - Stack pointer must stay within [-256, 0] and balance back to 0 at ret.
  - Direction flag DF starts 0 at entry and must be statically 0 (cld) at ret.
  - Nonvolatile GPRs, direct RSP arithmetic, branches/calls, prefixes, VEX/EVEX,
    RIP-relative/indexed addressing, non-r8 stores, and trailing bytes reject.
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


LOCAL_STACK_BYTES = 256
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

ARITH_BINARY = {M.ADD, M.ADC, M.SUB, M.SBB, M.CMP}
LOGIC_BINARY = {M.AND, M.OR, M.XOR, M.TEST}
ARITH_UNARY = {M.INC, M.DEC, M.NEG}

PRELUDE = """#include <atomic>
#include <cstddef>
#include <cstdint>
#include <cstring>

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

template <class T>
static inline T stack_load(const std::uint8_t* stack, std::size_t off) {
    T value{};
    std::memcpy(&value, stack + off, sizeof(T));
    return value;
}

static inline void push_u16(std::uint8_t* stack, std::size_t& sp, std::uint16_t val) {
    sp -= 2u;
    std::memcpy(stack + sp, &val, 2);
}

static inline std::uint16_t pop_u16(const std::uint8_t* stack, std::size_t& sp) {
    std::uint16_t val = 0u;
    std::memcpy(&val, stack + sp, 2);
    sp += 2u;
    return val;
}

static inline void push_u64(std::uint8_t* stack, std::size_t& sp, std::uint64_t val) {
    sp -= 8u;
    std::memcpy(stack + sp, &val, 8);
}

static inline std::uint64_t pop_u64(const std::uint8_t* stack, std::size_t& sp) {
    std::uint64_t val = 0ull;
    std::memcpy(&val, stack + sp, 8);
    sp += 8u;
    return val;
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

static inline std::uint16_t pack_flags16(
        bool cf, bool pf, bool af, bool zf, bool sf, bool df, bool of) {
    return static_cast<std::uint16_t>(
        (of ? 0x0800u : 0u) |
        (df ? 0x0400u : 0u) |
        0x0202u |
        (sf ? 0x0080u : 0u) |
        (zf ? 0x0040u : 0u) |
        (af ? 0x0010u : 0u) |
        (pf ? 0x0004u : 0u) |
        (cf ? 0x0001u : 0u));
}

static inline std::uint64_t pack_flags64(
        bool cf, bool pf, bool af, bool zf, bool sf, bool df, bool of, bool id) {
    return static_cast<std::uint64_t>(pack_flags16(cf, pf, af, zf, sf, df, of)) |
           (id ? 0x00200000ull : 0ull);
}

static inline void unpack_lahf(std::uint8_t ah, bool& cf, bool& pf, bool& af, bool& zf, bool& sf) {
    cf = (ah & 0x01u) != 0u;
    pf = (ah & 0x04u) != 0u;
    af = (ah & 0x10u) != 0u;
    zf = (ah & 0x40u) != 0u;
    sf = (ah & 0x80u) != 0u;
}

static inline void unpack_flags16(
        std::uint16_t f, bool& cf, bool& pf, bool& af, bool& zf, bool& sf, bool& df, bool& of) {
    cf = (f & 0x0001u) != 0u;
    pf = (f & 0x0004u) != 0u;
    af = (f & 0x0010u) != 0u;
    zf = (f & 0x0040u) != 0u;
    sf = (f & 0x0080u) != 0u;
    df = (f & 0x0400u) != 0u;
    of = (f & 0x0800u) != 0u;
}

static inline void unpack_flags64(
        std::uint64_t f, bool& cf, bool& pf, bool& af, bool& zf, bool& sf, bool& df, bool& of, bool& id) {
    unpack_flags16(static_cast<std::uint16_t>(f), cf, pf, af, zf, sf, df, of);
    id = (f & 0x00200000ull) != 0ull;
}

static inline std::uint64_t width_mask(unsigned bits) {
    return bits == 64u ? ~0ull : ((1ull << bits) - 1ull);
}

static inline std::uint64_t op_add_flags(
        unsigned bits, std::uint64_t a, std::uint64_t b, bool cin,
        bool& cf, bool& pf, bool& af, bool& zf, bool& sf, bool& of) {
    const std::uint64_t m = width_mask(bits);
    const std::uint64_t ua = a & m;
    const std::uint64_t ub = b & m;
    const std::uint64_t s1 = (ua + ub) & m;
    const bool c1 = s1 < ua;
    const std::uint64_t res = (s1 + (cin ? 1ull : 0ull)) & m;
    const bool c2 = res < s1;
    cf = c1 || c2;
    af = ((ua ^ ub ^ res) & 0x10ull) != 0ull;
    pf = calc_pf(res);
    zf = res == 0ull;
    sf = ((res >> (bits - 1u)) & 1ull) != 0ull;
    of = ((((ua ^ res) & (ub ^ res)) >> (bits - 1u)) & 1ull) != 0ull;
    return res;
}

static inline std::uint64_t op_sub_flags(
        unsigned bits, std::uint64_t a, std::uint64_t b, bool bin,
        bool& cf, bool& pf, bool& af, bool& zf, bool& sf, bool& of) {
    const std::uint64_t m = width_mask(bits);
    const std::uint64_t ua = a & m;
    const std::uint64_t ub = b & m;
    const std::uint64_t d1 = (ua - ub) & m;
    const bool b1 = ua < ub;
    const std::uint64_t res = (d1 - (bin ? 1ull : 0ull)) & m;
    const bool b2 = d1 < (bin ? 1ull : 0ull);
    cf = b1 || b2;
    af = ((ua ^ ub ^ res) & 0x10ull) != 0ull;
    pf = calc_pf(res);
    zf = res == 0ull;
    sf = ((res >> (bits - 1u)) & 1ull) != 0ull;
    of = ((((ua ^ ub) & (ua ^ res)) >> (bits - 1u)) & 1ull) != 0ull;
    return res;
}

static inline std::uint64_t op_logic_flags(
        unsigned bits, std::uint64_t res,
        bool& cf, bool& pf, bool& zf, bool& sf, bool& of) {
    const std::uint64_t m = width_mask(bits);
    const std::uint64_t r = res & m;
    cf = false;
    of = false;
    pf = calc_pf(r);
    zf = r == 0ull;
    sf = ((r >> (bits - 1u)) & 1ull) != 0ull;
    return r;
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


def signed_disp64(ins):
    raw = ins.memory_displacement & ((1 << 64) - 1)
    return raw - (1 << 64) if raw >= (1 << 63) else raw


def c_type_for_bits(bits):
    return {8: "std::uint8_t", 16: "std::uint16_t", 32: "std::uint32_t", 64: "std::uint64_t"}[bits]


def operand_size_bits(ins, op_index):
    kind = ins.op_kind(op_index)
    if kind == OpKind.REGISTER:
        return GPR_SPECS[ins.op_register(op_index)][1] if ins.op_register(op_index) in GPR_SPECS else RegisterExt.size(ins.op_register(op_index)) * 8
    if kind == OpKind.MEMORY:
        return MemorySizeExt.size(ins.memory_size) * 8
    raise ValueError(f"cannot determine width for operand {op_index} at RVA {ins.ip:#x}: {ins}")


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
    """Decode and lift one bounded straight-line integer-flags leaf function."""
    instructions = list(Decoder(64, raw, ip=start))
    if not instructions or instructions[-1].next_ip != start + len(raw):
        raise ValueError(f"truncated instruction stream in {name} at RVA {start:#x}")
    if any(ins.is_invalid for ins in instructions):
        bad = next(ins for ins in instructions if ins.is_invalid)
        raise ValueError(f"invalid instruction at RVA {bad.ip:#x}")

    defined_gpr = {"rcx", "rdx", "r8"}
    used_gpr = set()
    clobbered_ptrs = set()

    sp_offset = 0
    stack_init = set()
    used_stack = False

    defined_flags = {"df"}
    df_state = "zero"  # "zero", "one", or "dynamic"
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
            or base in (R.NONE, R.RIP, R.EIP, R.ESP)
            or ins.memory_index != R.NONE
            or not RegisterExt.is_gpr64(base)
        ):
            raise ValueError(f"unsupported memory operand at RVA {ins.ip:#x}: {ins}")
        nbytes = MemorySizeExt.size(ins.memory_size)
        if nbytes not in (1, 2, 4, 8):
            raise ValueError(f"unsupported memory width {nbytes} at RVA {ins.ip:#x}: {ins}")
        bits = nbytes * 8
        ctype = c_type_for_bits(bits)
        if base == R.RSP:
            if write:
                raise ValueError(f"unsupported direct write to local stack operand at RVA {ins.ip:#x}: {ins}")
            disp = signed_disp64(ins)
            if disp < 0 or sp_offset + disp + nbytes > 0 or sp_offset + disp < -LOCAL_STACK_BYTES:
                raise ValueError(f"stack read out of local bounds at RVA {ins.ip:#x}: {ins}")
            if any((sp_offset + disp + b) not in stack_init for b in range(nbytes)):
                raise ValueError(f"uninitialized local stack read at RVA {ins.ip:#x}: {ins}")
            nonlocal used_stack
            used_stack = True
            return "stack", f"stack_load<{ctype}>(stack, sp + {disp}u)", bits, ctype
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
        return "arg", addr, bits, ctype

    def read_operand(ins, op_index, bits):
        kind = ins.op_kind(op_index)
        if kind == OpKind.REGISTER:
            expr, reg_bits = read_reg(ins.op_register(op_index), ins)
            if reg_bits != bits:
                raise ValueError(f"operand width mismatch at RVA {ins.ip:#x}: {ins}")
            return expr
        if kind == OpKind.MEMORY:
            loc, arg, mem_bits, ctype = mem_access(ins, write=False)
            if mem_bits != bits:
                raise ValueError(f"memory width mismatch at RVA {ins.ip:#x}: {ins}")
            return arg if loc == "stack" else f"load_mem<{ctype}>({arg})"
        if kind in IMMEDIATE_KINDS:
            return f"{imm_value(ins, op_index, bits):#x}ull"
        raise ValueError(f"unsupported operand {op_index} at RVA {ins.ip:#x}: {ins}")

    def require_flags(flags, ins):
        for flag in flags:
            if flag not in defined_flags:
                raise ValueError(f"undefined flag {flag} read at RVA {ins.ip:#x}: {ins}")
            used_flags.add(flag)

    def push_bytes(nbytes, ins):
        nonlocal sp_offset, used_stack
        if sp_offset - nbytes < -LOCAL_STACK_BYTES:
            raise ValueError(f"local stack overflow at RVA {ins.ip:#x}: {ins}")
        for b in range(sp_offset - nbytes, sp_offset):
            stack_init.add(b)
        sp_offset -= nbytes
        used_stack = True

    def pop_bytes(nbytes, ins):
        nonlocal sp_offset, used_stack
        if sp_offset + nbytes > 0:
            raise ValueError(f"local stack underflow at RVA {ins.ip:#x}: {ins}")
        if any(b not in stack_init for b in range(sp_offset, sp_offset + nbytes)):
            raise ValueError(f"uninitialized stack read at RVA {ins.ip:#x}: {ins}")
        for b in range(sp_offset, sp_offset + nbytes):
            stack_init.discard(b)
        sp_offset += nbytes
        used_stack = True

    for ins in instructions:
        if returned:
            raise ValueError(f"unreachable instruction after ret at RVA {ins.ip:#x}: {ins}")
        if ins.has_lock_prefix or ins.has_rep_prefix or ins.has_repne_prefix or ins.has_segment_prefix:
            raise ValueError(f"unsupported instruction prefix at RVA {ins.ip:#x}: {ins}")
        if ins.op_code().encoding in (EncodingKind.VEX, EncodingKind.EVEX, EncodingKind.XOP):
            raise ValueError(f"unsupported vector-encoded instruction at RVA {ins.ip:#x}: {ins}")

        mnemonic = ins.mnemonic

        if ins.code == Code.RETNQ:
            if sp_offset != 0:
                raise ValueError(f"unbalanced stack pointer at ret RVA {ins.ip:#x}: offset {sp_offset}")
            if df_state != "zero":
                raise ValueError(f"direction flag may be non-zero at ret RVA {ins.ip:#x}: {ins}")
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

        elif ins.code == Code.SAHF:
            if "rax" not in defined_gpr:
                raise ValueError(f"undefined GPR rax at RVA {ins.ip:#x}: {ins}")
            used_gpr.add("rax")
            used_flags.update(("cf", "pf", "af", "zf", "sf"))
            defined_flags.update(("cf", "pf", "af", "zf", "sf"))
            statements.append("unpack_lahf(static_cast<std::uint8_t>(rax >> 8u), cf, pf, af, zf, sf);")

        elif ins.code == Code.PUSHFW:
            require_flags(("cf", "pf", "af", "zf", "sf", "df", "of"), ins)
            push_bytes(2, ins)
            statements.append("push_u16(stack, sp, pack_flags16(cf, pf, af, zf, sf, df, of));")

        elif ins.code == Code.POPFW:
            pop_bytes(2, ins)
            used_flags.update(("cf", "pf", "af", "zf", "sf", "df", "of"))
            defined_flags.update(("cf", "pf", "af", "zf", "sf", "df", "of"))
            df_state = "dynamic"
            statements.append("unpack_flags16(pop_u16(stack, sp), cf, pf, af, zf, sf, df, of);")

        elif ins.code == Code.PUSHFQ:
            require_flags(("cf", "pf", "af", "zf", "sf", "df", "of", "id"), ins)
            push_bytes(8, ins)
            statements.append("push_u64(stack, sp, pack_flags64(cf, pf, af, zf, sf, df, of, id));")

        elif ins.code == Code.POPFQ:
            pop_bytes(8, ins)
            used_flags.update(("cf", "pf", "af", "zf", "sf", "df", "of", "id"))
            defined_flags.update(("cf", "pf", "af", "zf", "sf", "df", "of", "id"))
            df_state = "dynamic"
            statements.append("unpack_flags64(pop_u64(stack, sp), cf, pf, af, zf, sf, df, of, id);")

        elif ins.code == Code.CLC:
            used_flags.add("cf")
            defined_flags.add("cf")
            statements.append("cf = false;")

        elif ins.code == Code.STC:
            used_flags.add("cf")
            defined_flags.add("cf")
            statements.append("cf = true;")

        elif ins.code == Code.CMC:
            require_flags(("cf",), ins)
            statements.append("cf = !cf;")

        elif ins.code == Code.CLD:
            used_flags.add("df")
            defined_flags.add("df")
            df_state = "zero"
            statements.append("df = false;")

        elif ins.code == Code.STD:
            used_flags.add("df")
            defined_flags.add("df")
            df_state = "one"
            statements.append("df = true;")

        elif mnemonic == M.PUSH:
            if ins.op0_kind != OpKind.REGISTER:
                raise ValueError(f"unsupported push operand at RVA {ins.ip:#x}: {ins}")
            expr, bits = read_reg(ins.op0_register, ins)
            if bits == 64:
                push_bytes(8, ins)
                statements.append(f"push_u64(stack, sp, {expr});")
            elif bits == 16:
                push_bytes(2, ins)
                statements.append(f"push_u16(stack, sp, static_cast<std::uint16_t>({expr}));")
            else:
                raise ValueError(f"unsupported push width at RVA {ins.ip:#x}: {ins}")

        elif mnemonic == M.POP:
            if ins.op0_kind != OpKind.REGISTER:
                raise ValueError(f"unsupported pop operand at RVA {ins.ip:#x}: {ins}")
            _, bits, _, _ = reg_info(ins.op0_register, ins)
            if bits == 64:
                pop_bytes(8, ins)
                stmt = write_reg_stmt(ins.op0_register, "pop_u64(stack, sp)", ins)
            elif bits == 16:
                pop_bytes(2, ins)
                stmt = write_reg_stmt(ins.op0_register, "pop_u16(stack, sp)", ins)
            else:
                raise ValueError(f"unsupported pop width at RVA {ins.ip:#x}: {ins}")
            statements.append(stmt)

        elif mnemonic == M.MOV and ins.op_count == 2:
            if ins.op0_kind == OpKind.REGISTER:
                bits = GPR_SPECS[ins.op0_register][1] if ins.op0_register in GPR_SPECS else reg_info(ins.op0_register, ins)[1]
                rhs = read_operand(ins, 1, bits)
                statements.append(write_reg_stmt(ins.op0_register, rhs, ins))
            elif ins.op0_kind == OpKind.MEMORY:
                loc, addr, bits, ctype = mem_access(ins, write=True)
                assert loc == "arg"
                rhs = read_operand(ins, 1, bits)
                statements.append(f"store_mem<{ctype}>({addr}, static_cast<{ctype}>({rhs}));")
            else:
                raise ValueError(f"unsupported mov operands at RVA {ins.ip:#x}: {ins}")

        elif mnemonic in ARITH_BINARY and ins.op_count == 2:
            if ins.op0_kind != OpKind.REGISTER:
                raise ValueError(f"unsupported arithmetic destination at RVA {ins.ip:#x}: {ins}")
            if mnemonic in (M.ADC, M.SBB):
                require_flags(("cf",), ins)
            lhs, bits = read_reg(ins.op0_register, ins)
            rhs = read_operand(ins, 1, bits)
            used_flags.update(("cf", "pf", "af", "zf", "sf", "of"))
            defined_flags.update(("cf", "pf", "af", "zf", "sf", "of"))
            helper = "op_add_flags" if mnemonic in (M.ADD, M.ADC) else "op_sub_flags"
            carry_arg = "cf" if mnemonic in (M.ADC, M.SBB) else "false"
            call = f"{helper}({bits}u, {lhs}, {rhs}, {carry_arg}, cf, pf, af, zf, sf, of)"
            if mnemonic == M.CMP:
                statements.append(f"(void){call};")
            else:
                statements.append(write_reg_stmt(ins.op0_register, call, ins))

        elif mnemonic in ARITH_UNARY and ins.op_count == 1:
            if ins.op0_kind != OpKind.REGISTER:
                raise ValueError(f"unsupported unary arithmetic operand at RVA {ins.ip:#x}: {ins}")
            lhs, bits = read_reg(ins.op0_register, ins)
            if mnemonic == M.NEG:
                used_flags.update(("cf", "pf", "af", "zf", "sf", "of"))
                defined_flags.update(("cf", "pf", "af", "zf", "sf", "of"))
                call = f"op_sub_flags({bits}u, 0ull, {lhs}, false, cf, pf, af, zf, sf, of)"
            else:
                used_flags.update(("pf", "af", "zf", "sf", "of"))
                defined_flags.update(("pf", "af", "zf", "sf", "of"))
                helper = "op_add_flags" if mnemonic == M.INC else "op_sub_flags"
                statements.append("{ bool unused_cf = false;")
                call = f"{helper}({bits}u, {lhs}, 1ull, false, unused_cf, pf, af, zf, sf, of)"
                statements.append(write_reg_stmt(ins.op0_register, call, ins) + " (void)unused_cf; }")
                continue
            statements.append(write_reg_stmt(ins.op0_register, call, ins))

        elif mnemonic in LOGIC_BINARY and ins.op_count == 2:
            if ins.op0_kind != OpKind.REGISTER:
                raise ValueError(f"unsupported logical destination at RVA {ins.ip:#x}: {ins}")
            lhs, bits = read_reg(ins.op0_register, ins)
            rhs = read_operand(ins, 1, bits)
            used_flags.update(("cf", "pf", "zf", "sf", "of"))
            defined_flags.update(("cf", "pf", "zf", "sf", "of"))
            defined_flags.discard("af")
            op_sym = {M.AND: "&", M.OR: "|", M.XOR: "^", M.TEST: "&"}[mnemonic]
            call = f"op_logic_flags({bits}u, static_cast<word>({lhs}) {op_sym} static_cast<word>({rhs}), cf, pf, zf, sf, of)"
            if mnemonic == M.TEST:
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
    for flag in ("cf", "pf", "af", "zf", "sf", "df", "of", "id"):
        if flag in used_flags:
            decls.append(f"    bool {flag} = false;")
    if used_stack:
        decls.append(f"    alignas(16) std::uint8_t stack[{LOCAL_STACK_BYTES}]{{}};")
        decls.append(f"    std::size_t sp = {LOCAL_STACK_BYTES}u;")
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
