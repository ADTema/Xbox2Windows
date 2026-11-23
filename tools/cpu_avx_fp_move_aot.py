"""Lift bounded Windows x64 leaf functions with AVX FP add/sub and move forms to C++.

Each export uses the leaf ABI void fn(word rcx, word rdx, word r8), where rcx,
rdx and r8 carry flat host pointers to caller-owned buffers (rcx and rdx are
inputs, r8 is the output). YMM0..YMM5 are modeled as portable 256-bit value
structs (four 64-bit lanes); every VEX.128 write to XMM0..XMM5 zeroes
[255:128], and vmovq XMM writes zero [255:64]. Volatile scratch GPRs
(rax, r9, r10, r11) support vmovq GPR transfers, rdi save/restore around
vmaskmovdqu, and 64-bit flat load/store glue.

Supported AVX instructions (docs/coverage/x64_zen2.tsv group AVX):
  - Packed alternating subtract/add: vaddsubps (XMM & YMM, reg & m128/m256),
    vaddsubpd (XMM & YMM, reg & m128/m256)
  - Quadword / GPR move: vmovq (all 5 VEX.128 operand shapes: xmm<-xmm,
    xmm<-m64, m64<-xmm, xmm<-r64, r64<-xmm)
  - Conditional byte store: vmaskmovdqu (VEX.128 xmm1, xmm2 to implicit [rdi],
    requiring rdi save/restore via a volatile scratch GPR around mov rdi, r8)

Transport/ABI glue: vmovups, vmovaps, vmovdqu, vmovdqa (128/256-bit load, store
and register copy), vzeroupper, 64-bit mov (volatile GPR <-> [base + disp],
volatile GPR reg-reg, and rdi save/set-to-r8/restore), and terminal ret.

Legacy SSE forms (addsubps, addsubpd, movq, maskmovdqu), EVEX encodings,
nonvolatile registers (XMM6..15, YMM6..15, RBX/RBP/RSI/R12..R15/RSP and
unrestored or non-r8 RDI), non-argument memory bases, stores outside r8,
unaligned vmovaps/vmovdqa memory operands, prefixes, RIP-relative addressing,
branches, and trailing bytes after ret are rejected.
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

VOLATILE_XMM = {getattr(R, f"XMM{i}"): i for i in range(6)}
VOLATILE_YMM = {getattr(R, f"YMM{i}"): i for i in range(6)}
NONVOLATILE_VEC = (
    {getattr(R, f"XMM{i}") for i in range(6, 16)}
    | {getattr(R, f"YMM{i}") for i in range(6, 16)}
)

SCRATCH_GPR64 = {R.RAX: "rax", R.R9: "r9", R.R10: "r10", R.R11: "r11"}
VOLATILE_GPR64 = {**ARGUMENTS, **SCRATCH_GPR64}
NONVOLATILE_GPR = {
    R.RBX, R.EBX, R.BL, R.BH,
    R.RBP, R.EBP, R.BPL,
    R.RSI, R.ESI, R.SIL,
    R.RDI, R.EDI, R.DIL,
    R.RSP, R.ESP, R.SPL,
    R.R12, R.R12D, R.R12L,
    R.R13, R.R13D, R.R13L,
    R.R14, R.R14D, R.R14L,
    R.R15, R.R15D, R.R15L,
}

ADDSUB_SPECS = {
    Code.VEX_VADDSUBPS_XMM_XMM_XMMM128: ("op_vaddsubps", False),
    Code.VEX_VADDSUBPS_YMM_YMM_YMMM256: ("op_vaddsubps", True),
    Code.VEX_VADDSUBPD_XMM_XMM_XMMM128: ("op_vaddsubpd", False),
    Code.VEX_VADDSUBPD_YMM_YMM_YMMM256: ("op_vaddsubpd", True),
}

VMOVQ_CODES = {
    Code.VEX_VMOVQ_XMM_XMMM64,
    Code.VEX_VMOVQ_XMMM64_XMM,
    Code.VEX_VMOVQ_XMM_RM64,
    Code.VEX_VMOVQ_RM64_XMM,
}

FULL_VEC_LOAD_CODES = {
    Code.VEX_VMOVUPS_XMM_XMMM128: (False, False),
    Code.VEX_VMOVUPS_YMM_YMMM256: (True, False),
    Code.VEX_VMOVDQU_XMM_XMMM128: (False, False),
    Code.VEX_VMOVDQU_YMM_YMMM256: (True, False),
    Code.VEX_VMOVAPS_XMM_XMMM128: (False, True),
    Code.VEX_VMOVAPS_YMM_YMMM256: (True, True),
    Code.VEX_VMOVDQA_XMM_XMMM128: (False, True),
    Code.VEX_VMOVDQA_YMM_YMMM256: (True, True),
}

FULL_VEC_STORE_CODES = {
    Code.VEX_VMOVUPS_XMMM128_XMM: (False, False),
    Code.VEX_VMOVUPS_YMMM256_YMM: (True, False),
    Code.VEX_VMOVDQU_XMMM128_XMM: (False, False),
    Code.VEX_VMOVDQU_YMMM256_YMM: (True, False),
    Code.VEX_VMOVAPS_XMMM128_XMM: (False, True),
    Code.VEX_VMOVAPS_YMMM256_YMM: (True, True),
    Code.VEX_VMOVDQA_XMMM128_XMM: (False, True),
    Code.VEX_VMOVDQA_YMMM256_YMM: (True, True),
}

LEGACY_SSE_REJECT_CODES = {
    Code.ADDSUBPS_XMM_XMMM128,
    Code.ADDSUBPD_XMM_XMMM128,
    Code.MOVQ_XMM_XMMM64,
    Code.MOVQ_XMMM64_XMM,
    Code.MOVQ_XMM_RM64,
    Code.MOVQ_RM64_XMM,
    Code.MOVQ_MM_MMM64,
    Code.MOVQ_MMM64_MM,
    Code.MASKMOVDQU_RDI_XMM_XMM,
}

ALLOWED_CODES = {
    Code.RETNQ,
    Code.VEX_VZEROUPPER,
    Code.MOV_R64_RM64,
    Code.MOV_RM64_R64,
    Code.VEX_VMASKMOVDQU_RDI_XMM_XMM,
    *ADDSUB_SPECS,
    *VMOVQ_CODES,
    *FULL_VEC_LOAD_CODES,
    *FULL_VEC_STORE_CODES,
}


PRELUDE = """#include <atomic>
#include <cstdint>
#include <cstring>
#include <limits>
#include <intrin.h>

#if defined(_MSC_VER) && !defined(__clang__)
#pragma fp_contract(off)
#else
#pragma STDC FP_CONTRACT OFF
#endif

extern "C" __declspec(dllexport) std::uint32_t host_has_avx() {
    int info[4]{};
    __cpuid(info, 1);
    const int need = (1 << 27) | (1 << 28);
    if ((info[2] & need) != need) return 0u;
    return (_xgetbv(0) & 6u) == 6u ? 1u : 0u;
}

using word = std::uint64_t;

struct Vec256 {
    std::uint64_t q[4];
};

// Guest reads can fault even when the translated result is dead. Keep surrounding guest
// writes on their original side of the read when the compiler inlines these helpers.
static inline std::uint64_t load64(word address) {
    std::atomic_signal_fence(std::memory_order_seq_cst);
    const auto value = *reinterpret_cast<const volatile std::uint64_t __unaligned*>(address);
    std::atomic_signal_fence(std::memory_order_seq_cst);
    return value;
}

static inline Vec256 load128(word address) {
    std::atomic_signal_fence(std::memory_order_seq_cst);
    const auto* p = reinterpret_cast<const volatile std::uint64_t __unaligned*>(address);
    const std::uint64_t q0 = p[0];
    const std::uint64_t q1 = p[1];
    std::atomic_signal_fence(std::memory_order_seq_cst);
    return {{q0, q1, 0ull, 0ull}};
}

static inline Vec256 load256(word address) {
    std::atomic_signal_fence(std::memory_order_seq_cst);
    const auto* p = reinterpret_cast<const volatile std::uint64_t __unaligned*>(address);
    const std::uint64_t q0 = p[0];
    const std::uint64_t q1 = p[1];
    const std::uint64_t q2 = p[2];
    const std::uint64_t q3 = p[3];
    std::atomic_signal_fence(std::memory_order_seq_cst);
    return {{q0, q1, q2, q3}};
}

static inline void store64(word address, std::uint64_t val) {
    std::memcpy(reinterpret_cast<void*>(address), &val, 8);
}

static inline void store128(word address, const Vec256& v) {
    std::memcpy(reinterpret_cast<void*>(address), v.q, 16);
}

static inline void store256(word address, const Vec256& v) {
    std::memcpy(reinterpret_cast<void*>(address), v.q, 32);
}

static inline Vec256 copy128(const Vec256& v) {
    return {{v.q[0], v.q[1], 0ull, 0ull}};
}

static inline std::uint32_t lane32(const Vec256& v, unsigned i) {
    return static_cast<std::uint32_t>(v.q[i >> 1] >> ((i & 1u) * 32u));
}

static inline void set_lane32(Vec256& v, unsigned i, std::uint32_t val) {
    const unsigned shift = (i & 1u) * 32u;
    v.q[i >> 1] = (v.q[i >> 1] & ~(0xffffffffull << shift)) | (static_cast<std::uint64_t>(val) << shift);
}

// Preserve x86 src1-first NaN quieting/precedence and real-indefinite QNaN on invalid ops.
template <class Float, class Bits>
static inline Bits fp_arith(Bits a, Bits b, bool is_add) {
    const Bits quiet = static_cast<Bits>(1) << (std::numeric_limits<Float>::digits - 2);
    Float x, y;
    std::memcpy(&x, &a, sizeof(x));
    std::memcpy(&y, &b, sizeof(y));
    if (x != x) return a | quiet;
    if (y != y) return b | quiet;
    const Float r = is_add ? (x + y) : (x - y);
    if (r != r) return static_cast<Bits>(~(quiet - 1));
    Bits out;
    std::memcpy(&out, &r, sizeof(out));
    return out;
}

static inline Vec256 op_vaddsubps(const Vec256& a, const Vec256& b, bool wide) {
    Vec256 out{};
    const unsigned lanes = wide ? 8u : 4u;
    for (unsigned i = 0; i < lanes; ++i) {
        set_lane32(out, i, fp_arith<float, std::uint32_t>(lane32(a, i), lane32(b, i), (i & 1u) != 0u));
    }
    return out;
}

static inline Vec256 op_vaddsubpd(const Vec256& a, const Vec256& b, bool wide) {
    Vec256 out{};
    const unsigned lanes = wide ? 4u : 2u;
    for (unsigned i = 0; i < lanes; ++i) {
        out.q[i] = fp_arith<double, std::uint64_t>(a.q[i], b.q[i], (i & 1u) != 0u);
    }
    return out;
}

static inline void op_vmaskmovdqu(word address, const Vec256& src, const Vec256& mask) {
    std::uint8_t src_bytes[16]{};
    std::uint8_t mask_bytes[16]{};
    std::memcpy(src_bytes, src.q, 16);
    std::memcpy(mask_bytes, mask.q, 16);
    auto* dst = reinterpret_cast<volatile std::uint8_t*>(address);
    for (unsigned i = 0; i < 16u; ++i) {
        if ((mask_bytes[i] & 0x80u) != 0u) {
            std::atomic_signal_fence(std::memory_order_seq_cst);
            dst[i] = src_bytes[i];
        }
    }
}
"""


def vec_index(register, ins):
    """Map XMM0..XMM5 or YMM0..YMM5 to (index, is_ymm), rejecting all others."""
    if register in VOLATILE_XMM:
        return VOLATILE_XMM[register], False
    if register in VOLATILE_YMM:
        return VOLATILE_YMM[register], True
    if register in NONVOLATILE_VEC:
        raise ValueError(f"nonvolatile vector register {register} at RVA {ins.ip:#x}: {ins}")
    raise ValueError(f"unsupported vector register {register} at RVA {ins.ip:#x}: {ins}")


def gpr64_name(register, ins):
    """Map volatile 64-bit GPRs to C++ names, rejecting nonvolatile and sub-64-bit GPRs."""
    if register in VOLATILE_GPR64:
        return VOLATILE_GPR64[register]
    if register in NONVOLATILE_GPR:
        raise ValueError(f"nonvolatile GPR {register} at RVA {ins.ip:#x}: {ins}")
    raise ValueError(f"unsupported GPR {register} at RVA {ins.ip:#x}: {ins}")


def flat_address(ins, clobbered_ptrs, *, expected_bytes=None, alignment=1, write=False):
    """Lower a flat [base + disp] pointer operand rooted in an unclobbered argument GPR64."""
    base = ins.memory_base
    if (
        ins.is_ip_rel_memory_operand
        or base in (R.NONE, R.RIP, R.EIP, R.RSP, R.ESP)
        or ins.memory_index != R.NONE
        or not RegisterExt.is_gpr64(base)
    ):
        raise ValueError(f"unsupported memory operand at RVA {ins.ip:#x}: {ins}")
    if base in NONVOLATILE_GPR:
        raise ValueError(f"nonvolatile GPR base {base} in memory operand at RVA {ins.ip:#x}: {ins}")
    if base not in ARGUMENTS:
        raise ValueError(f"unsupported memory base {base} at RVA {ins.ip:#x}: {ins}")
    if base in clobbered_ptrs:
        raise ValueError(f"memory operand uses clobbered pointer {ARGUMENTS[base]} at RVA {ins.ip:#x}: {ins}")
    if write and base != R.R8:
        raise ValueError(f"non-r8 store memory operand at RVA {ins.ip:#x}: {ins}")
    if expected_bytes is not None and MemorySizeExt.size(ins.memory_size) != expected_bytes:
        raise ValueError(f"expected {expected_bytes}-byte memory operand at RVA {ins.ip:#x}: {ins}")
    disp = ins.memory_displacement & ((1 << 64) - 1)
    if disp % alignment:
        raise ValueError(f"unaligned {alignment}-byte memory operand at RVA {ins.ip:#x}: {ins}")
    name = ARGUMENTS[base]
    return f"({name} + {disp:#x}ull)" if disp else name


def lift_code(name, start, raw):
    """Decode and lift one bounded straight-line AVX FP add/sub and move leaf function."""
    instructions = list(Decoder(64, raw, ip=start))
    if not instructions or instructions[-1].next_ip != start + len(raw):
        raise ValueError(f"truncated instruction stream in {name} at RVA {start:#x}")
    if any(ins.is_invalid for ins in instructions):
        bad = next(ins for ins in instructions if ins.is_invalid)
        raise ValueError(f"invalid instruction at RVA {bad.ip:#x}")

    used_vec = set()
    defined_vec = set()
    used_gpr = set()
    defined_gpr = {"rcx", "rdx", "r8"}
    clobbered_ptrs = set()
    # Track caller's nonvolatile RDI across save/set-to-r8/restore for vmaskmovdqu.
    caller_rdi_holders = {"rdi"}
    rdi_expr = None
    statements = []
    returned = False

    def read_vec(op_index, ins, *, require_xmm=False):
        if ins.op_kind(op_index) != OpKind.REGISTER:
            raise ValueError(f"expected register operand {op_index} at RVA {ins.ip:#x}: {ins}")
        idx, wide = vec_index(ins.op_register(op_index), ins)
        if require_xmm and wide:
            raise ValueError(f"unexpected YMM operand in VEX.128 instruction at RVA {ins.ip:#x}: {ins}")
        if idx not in defined_vec:
            raise ValueError(f"undefined vector register ymm{idx} at RVA {ins.ip:#x}: {ins}")
        used_vec.add(idx)
        return f"ymm{idx}", wide

    def write_vec(op_index, ins, *, require_xmm=False):
        if ins.op_kind(op_index) != OpKind.REGISTER:
            raise ValueError(f"expected register destination at RVA {ins.ip:#x}: {ins}")
        idx, wide = vec_index(ins.op_register(op_index), ins)
        if require_xmm and wide:
            raise ValueError(f"unexpected YMM destination in VEX.128 instruction at RVA {ins.ip:#x}: {ins}")
        used_vec.add(idx)
        return idx, f"ymm{idx}", wide

    def read_gpr(op_index, ins):
        if ins.op_kind(op_index) != OpKind.REGISTER:
            raise ValueError(f"expected GPR operand {op_index} at RVA {ins.ip:#x}: {ins}")
        reg_name = gpr64_name(ins.op_register(op_index), ins)
        if reg_name not in defined_gpr:
            raise ValueError(f"undefined GPR {reg_name} at RVA {ins.ip:#x}: {ins}")
        used_gpr.add(reg_name)
        return reg_name

    def write_gpr(op_index, ins, *, scratch_only=False):
        if ins.op_kind(op_index) != OpKind.REGISTER:
            raise ValueError(f"expected GPR destination at RVA {ins.ip:#x}: {ins}")
        reg = ins.op_register(op_index)
        reg_name = gpr64_name(reg, ins)
        if reg_name == "r8":
            raise ValueError(f"unsupported write to output buffer pointer r8 at RVA {ins.ip:#x}: {ins}")
        if scratch_only and reg not in SCRATCH_GPR64:
            raise ValueError(f"expected volatile scratch GPR destination at RVA {ins.ip:#x}: {ins}")
        return reg_name

    def clobber_gpr(reg_name):
        caller_rdi_holders.discard(reg_name)
        if reg_name == "rcx":
            clobbered_ptrs.add(R.RCX)
        elif reg_name == "rdx":
            clobbered_ptrs.add(R.RDX)

    for ins in instructions:
        if returned:
            raise ValueError(f"unreachable instruction after ret at RVA {ins.ip:#x}: {ins}")
        if ins.has_lock_prefix or ins.has_rep_prefix or ins.has_repne_prefix or ins.has_segment_prefix:
            raise ValueError(f"unsupported instruction prefix at RVA {ins.ip:#x}: {ins}")
        op_code = ins.op_code()
        if (
            op_code.encoding == EncodingKind.EVEX
            or ins.op_mask != R.NONE
            or ins.zeroing_masking
            or ins.is_broadcast
        ):
            raise ValueError(f"unsupported EVEX instruction at RVA {ins.ip:#x}: {ins}")
        if ins.code in LEGACY_SSE_REJECT_CODES:
            raise ValueError(f"unsupported legacy SSE encoding at RVA {ins.ip:#x}: {ins}")
        if ins.code not in ALLOWED_CODES:
            raise ValueError(f"unsupported instruction at RVA {ins.ip:#x}: {ins}")

        if ins.code == Code.RETNQ:
            if "rdi" not in caller_rdi_holders:
                raise ValueError(f"unrestored nonvolatile GPR rdi at ret RVA {ins.ip:#x}: {ins}")
            statements.append("return;")
            returned = True

        elif ins.code == Code.VEX_VZEROUPPER:
            for idx in sorted(defined_vec):
                statements.append(f"ymm{idx}.q[2] = 0ull; ymm{idx}.q[3] = 0ull;")

        elif ins.code in ADDSUB_SPECS:
            helper, wide = ADDSUB_SPECS[ins.code]
            src1, _ = read_vec(1, ins, require_xmm=not wide)
            if ins.op2_kind == OpKind.MEMORY:
                expected = 32 if wide else 16
                addr = flat_address(ins, clobbered_ptrs, expected_bytes=expected)
                src2 = f"{'load256' if wide else 'load128'}({addr})"
            else:
                src2, _ = read_vec(2, ins, require_xmm=not wide)
            dst_idx, dst, _ = write_vec(0, ins, require_xmm=not wide)
            statements.append(f"{dst} = {helper}({src1}, {src2}, {'true' if wide else 'false'});")
            defined_vec.add(dst_idx)

        elif ins.code in VMOVQ_CODES:
            if ins.op0_kind == OpKind.MEMORY:
                src, _ = read_vec(1, ins, require_xmm=True)
                addr = flat_address(ins, clobbered_ptrs, expected_bytes=8, write=True)
                statements.append(f"store64({addr}, {src}.q[0]);")
            elif ins.op1_kind == OpKind.MEMORY:
                addr = flat_address(ins, clobbered_ptrs, expected_bytes=8)
                dst_idx, dst, _ = write_vec(0, ins, require_xmm=True)
                statements.append(f"{dst} = {{{{load64({addr}), 0ull, 0ull, 0ull}}}};")
                defined_vec.add(dst_idx)
            elif ins.code == Code.VEX_VMOVQ_XMM_RM64:
                src_gpr = read_gpr(1, ins)
                dst_idx, dst, _ = write_vec(0, ins, require_xmm=True)
                statements.append(f"{dst} = {{{{{src_gpr}, 0ull, 0ull, 0ull}}}};")
                defined_vec.add(dst_idx)
            elif ins.code == Code.VEX_VMOVQ_RM64_XMM:
                src, _ = read_vec(1, ins, require_xmm=True)
                dst_gpr = write_gpr(0, ins)
                clobber_gpr(dst_gpr)
                used_gpr.add(dst_gpr)
                statements.append(f"{dst_gpr} = {src}.q[0];")
                defined_gpr.add(dst_gpr)
            else:
                src, _ = read_vec(1, ins, require_xmm=True)
                dst_idx, dst, _ = write_vec(0, ins, require_xmm=True)
                statements.append(f"{dst} = {{{{{src}.q[0], 0ull, 0ull, 0ull}}}};")
                defined_vec.add(dst_idx)

        elif ins.code == Code.VEX_VMASKMOVDQU_RDI_XMM_XMM:
            if ins.op0_kind != OpKind.MEMORY_SEG_RDI or ins.memory_segment != R.DS:
                raise ValueError(f"unsupported vmaskmovdqu target at RVA {ins.ip:#x}: {ins}")
            if rdi_expr != "r8":
                raise ValueError(f"vmaskmovdqu requires r8-rooted rdi at RVA {ins.ip:#x}: {ins}")
            src, _ = read_vec(1, ins, require_xmm=True)
            mask, _ = read_vec(2, ins, require_xmm=True)
            statements.append(f"op_vmaskmovdqu({rdi_expr}, {src}, {mask});")

        elif ins.code in FULL_VEC_LOAD_CODES:
            wide, aligned = FULL_VEC_LOAD_CODES[ins.code]
            expected = 32 if wide else 16
            align = expected if aligned else 1
            if ins.op1_kind == OpKind.MEMORY:
                addr = flat_address(ins, clobbered_ptrs, expected_bytes=expected, alignment=align)
                dst_idx, dst, _ = write_vec(0, ins, require_xmm=not wide)
                statements.append(f"{dst} = {'load256' if wide else 'load128'}({addr});")
                defined_vec.add(dst_idx)
            else:
                src, _ = read_vec(1, ins, require_xmm=not wide)
                dst_idx, dst, _ = write_vec(0, ins, require_xmm=not wide)
                statements.append(f"{dst} = {src};" if wide else f"{dst} = copy128({src});")
                defined_vec.add(dst_idx)

        elif ins.code in FULL_VEC_STORE_CODES:
            wide, aligned = FULL_VEC_STORE_CODES[ins.code]
            expected = 32 if wide else 16
            align = expected if aligned else 1
            if ins.op0_kind == OpKind.MEMORY:
                src, _ = read_vec(1, ins, require_xmm=not wide)
                addr = flat_address(ins, clobbered_ptrs, expected_bytes=expected, alignment=align, write=True)
                statements.append(f"{'store256' if wide else 'store128'}({addr}, {src});")
            else:
                src, _ = read_vec(1, ins, require_xmm=not wide)
                dst_idx, dst, _ = write_vec(0, ins, require_xmm=not wide)
                statements.append(f"{dst} = {src};" if wide else f"{dst} = copy128({src});")
                defined_vec.add(dst_idx)

        elif ins.code in (Code.MOV_R64_RM64, Code.MOV_RM64_R64):
            if ins.op0_kind == OpKind.REGISTER and ins.op1_kind == OpKind.REGISTER:
                op0_reg = ins.op0_register
                op1_reg = ins.op1_register
                if not (RegisterExt.is_gpr64(op0_reg) and RegisterExt.is_gpr64(op1_reg)):
                    raise ValueError(f"unsupported mov operand width at RVA {ins.ip:#x}: {ins}")
                if op1_reg == R.RDI:
                    dst_gpr = write_gpr(0, ins, scratch_only=True)
                    if "rdi" not in caller_rdi_holders:
                        raise ValueError(f"cannot save clobbered rdi at RVA {ins.ip:#x}: {ins}")
                    caller_rdi_holders.add(dst_gpr)
                elif op0_reg == R.RDI:
                    if op1_reg == R.R8:
                        if not any(s in caller_rdi_holders for s in SCRATCH_GPR64.values()):
                            raise ValueError(f"rdi modified without saving to volatile scratch at RVA {ins.ip:#x}: {ins}")
                        caller_rdi_holders.discard("rdi")
                        rdi_expr = "r8"
                    elif op1_reg in SCRATCH_GPR64 and SCRATCH_GPR64[op1_reg] in caller_rdi_holders:
                        caller_rdi_holders.add("rdi")
                        rdi_expr = None
                    else:
                        raise ValueError(f"non-r8 or unsaved write to nonvolatile GPR rdi at RVA {ins.ip:#x}: {ins}")
                else:
                    src_gpr = read_gpr(1, ins)
                    dst_gpr = write_gpr(0, ins)
                    clobber_gpr(dst_gpr)
                    used_gpr.add(dst_gpr)
                    statements.append(f"{dst_gpr} = {src_gpr};")
                    defined_gpr.add(dst_gpr)
            elif ins.op0_kind == OpKind.REGISTER and ins.op1_kind == OpKind.MEMORY:
                dst_gpr = write_gpr(0, ins)
                addr = flat_address(ins, clobbered_ptrs, expected_bytes=8)
                clobber_gpr(dst_gpr)
                used_gpr.add(dst_gpr)
                statements.append(f"{dst_gpr} = load64({addr});")
                defined_gpr.add(dst_gpr)
            elif ins.op0_kind == OpKind.MEMORY and ins.op1_kind == OpKind.REGISTER:
                src_gpr = read_gpr(1, ins)
                addr = flat_address(ins, clobbered_ptrs, expected_bytes=8, write=True)
                statements.append(f"store64({addr}, {src_gpr});")
            else:
                raise ValueError(f"unsupported mov operands at RVA {ins.ip:#x}: {ins}")

        else:
            raise ValueError(f"unsupported instruction at RVA {ins.ip:#x}: {ins}")

    if not returned:
        raise ValueError(f"missing terminal ret in {name} at RVA {start + len(raw):#x}")

    decls = [f"    Vec256 ymm{idx}{{}};" for idx in sorted(used_vec)]
    for gpr in ("rax", "r9", "r10", "r11"):
        if gpr in used_gpr:
            decls.append(f"    word {gpr} = 0ull;")
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
