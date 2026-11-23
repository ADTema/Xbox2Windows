"""Differential checks, mutated-C++ controls, ALTER_IMM controls, and rejection controls for LAHF AOT."""

import ctypes
from pathlib import Path
import random
import re
import struct
import sys
from tempfile import TemporaryDirectory

import pefile
from iced_x86 import Code, Decoder, Encoder, Instruction, MemoryOperand, Register as R

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from cpu_integer_flags_aot import PRELUDE, lift_code, translate
from cpu_leaf_aot import bounded_code, export_rva

MASK64 = 0xFFFFFFFFFFFFFFFF
GUARD_PRE = bytes(0xA0 + (i % 16) for i in range(32))
GUARD_POST = bytes(0xC0 + (i % 16) for i in range(32))
FILL = b"\x5A" * 32

DIFF_SPECS = {
    "op_add8_lahf": ("add", 8, None),
    "op_add16_lahf": ("add", 16, None),
    "op_add32_lahf": ("add", 32, None),
    "op_add64_lahf": ("add", 64, None),
    "op_sub8_lahf": ("sub", 8, None),
    "op_sub16_lahf": ("sub", 16, None),
    "op_sub32_lahf": ("sub", 32, None),
    "op_sub64_lahf": ("sub", 64, None),
    "op_cmp8_lahf": ("cmp", 8, None),
    "op_cmp16_lahf": ("cmp", 16, None),
    "op_cmp32_lahf": ("cmp", 32, None),
    "op_cmp64_lahf": ("cmp", 64, None),
    "op_add8_al_lahf": ("add_al", 8, 5),
    "op_add32_imm_lahf": ("add", 32, (17, 1)),
    "op_sub32_imm_lahf": ("sub", 32, (15, 1)),
    "op_cmp64_imm_lahf": ("cmp", 64, (17, 1)),
}

EXPORTS = tuple(DIFF_SPECS.keys())
ALTERED_EXPORTS = (
    "op_add8_al_lahf",
    "op_add32_imm_lahf",
    "op_sub32_imm_lahf",
    "op_cmp64_imm_lahf",
)

EXTRA_CONTROL_HELPERS = """
static inline bool calc_pf_full(std::uint64_t val) {
    val ^= val >> 32u;
    val ^= val >> 16u;
    val ^= val >> 8u;
    val ^= val >> 4u;
    val ^= val >> 2u;
    val ^= val >> 1u;
    return (val & 1ull) == 0ull;
}

static inline std::uint8_t pack_lahf_no_bit1(bool cf, bool pf, bool af, bool zf, bool sf) {
    return static_cast<std::uint8_t>(
        (sf ? 0x80u : 0u) |
        (zf ? 0x40u : 0u) |
        (af ? 0x10u : 0u) |
        (pf ? 0x04u : 0u) |
        (cf ? 0x01u : 0u));
}

static inline std::uint64_t op_add_flags_bit4(
        unsigned bits, std::uint64_t a, std::uint64_t b,
        bool& cf, bool& pf, bool& af, bool& zf, bool& sf, bool& of) {
    const std::uint64_t m = width_mask(bits);
    const std::uint64_t ua = a & m;
    const std::uint64_t ub = b & m;
    const std::uint64_t res = (ua + ub) & m;
    cf = res < ua;
    af = ((ua ^ ub ^ res) & 0x20ull) != 0ull;
    pf = calc_pf(res);
    zf = res == 0ull;
    sf = ((res >> (bits - 1u)) & 1ull) != 0ull;
    of = ((((ua ^ res) & (ub ^ res)) >> (bits - 1u)) & 1ull) != 0ull;
    return res;
}

static inline std::uint64_t op_sub_flags_full_pf(
        unsigned bits, std::uint64_t a, std::uint64_t b,
        bool& cf, bool& pf, bool& af, bool& zf, bool& sf, bool& of) {
    const std::uint64_t m = width_mask(bits);
    const std::uint64_t ua = a & m;
    const std::uint64_t ub = b & m;
    const std::uint64_t res = (ua - ub) & m;
    cf = ua < ub;
    af = ((ua ^ ub ^ res) & 0x10ull) != 0ull;
    pf = calc_pf_full(res);
    zf = res == 0ull;
    sf = ((res >> (bits - 1u)) & 1ull) != 0ull;
    of = ((((ua ^ ub) & (ua ^ res)) >> (bits - 1u)) & 1ull) != 0ull;
    return res;
}
"""

# Mutated-C++ negative controls: (base_export, control_name, regex, replacement)
CPP_MUTATIONS = (
    ("op_add32_lahf", "ctrl_af_bit4", re.compile(r"\bop_add_flags\("), "op_add_flags_bit4("),
    ("op_sub32_lahf", "ctrl_pf_full_width", re.compile(r"\bop_sub_flags\("), "op_sub_flags_full_pf("),
    ("op_cmp32_lahf", "ctrl_lahf_bit1_cleared", re.compile(r"\bpack_lahf\("), "pack_lahf_no_bit1("),
    (
        "op_add32_lahf",
        "ctrl_lahf_clobber_rax",
        re.compile(r"rax = \(rax & ~0xff00ull\) \| \(static_cast<word>\(pack_lahf\(cf, pf, af, zf, sf\)\) << 8u\);"),
        "rax = (static_cast<word>(pack_lahf(cf, pf, af, zf, sf)) << 8u);",
    ),
    (
        "op_sub64_lahf",
        "ctrl_lahf_keep_old_ah",
        re.compile(r"rax = \(rax & ~0xff00ull\) \| \(static_cast<word>\(pack_lahf\(cf, pf, af, zf, sf\)\) << 8u\);"),
        "rax = rax | (static_cast<word>(pack_lahf(cf, pf, af, zf, sf)) << 8u);",
    ),
    (
        "op_cmp64_lahf",
        "ctrl_lahf_clobber_flags",
        re.compile(r"rax = \(rax & ~0xff00ull\) \| \(static_cast<word>\(pack_lahf\(cf, pf, af, zf, sf\)\) << 8u\);"),
        "rax = (rax & ~0xff00ull) | (static_cast<word>(pack_lahf(cf, pf, af, zf, sf)) << 8u); "
        "cf = !cf; pf = !pf; zf = !zf; sf = !sf; of = !of;",
    ),
)


# --- Independent Python ISA reference model ---

def calc_pf(val: int) -> int:
    return int(((val & 0xFF).bit_count() % 2) == 0)


def add_flags(bits: int, a: int, b: int):
    mask = (1 << bits) - 1
    ua = a & mask
    ub = b & mask
    total = ua + ub
    res = total & mask
    cf = int((total >> bits) != 0)
    af = int(((ua ^ ub ^ res) & 0x10) != 0)
    pf = calc_pf(res)
    zf = int(res == 0)
    sf = int(((res >> (bits - 1)) & 1) != 0)
    of = int((((ua ^ res) & (ub ^ res)) >> (bits - 1)) & 1)
    return res, (cf, pf, af, zf, sf, of)


def sub_flags(bits: int, a: int, b: int):
    mask = (1 << bits) - 1
    ua = a & mask
    ub = b & mask
    diff = ua - ub
    res = diff & mask
    cf = int(diff < 0)
    af = int(((ua ^ ub ^ res) & 0x10) != 0)
    pf = calc_pf(res)
    zf = int(res == 0)
    sf = int(((res >> (bits - 1)) & 1) != 0)
    of = int((((ua ^ ub) & (ua ^ res)) >> (bits - 1)) & 1)
    return res, (cf, pf, af, zf, sf, of)


def pack_lahf(flags) -> int:
    cf, pf, af, zf, sf = flags[:5]
    return (sf << 7) | (zf << 6) | (af << 4) | (pf << 2) | 0x02 | cf


def apply_lahf(rax: int, flags) -> int:
    return (rax & ~0xFF00) | (pack_lahf(flags) << 8)


def pack_lahf_and_flags(rax: int, flags) -> bytes:
    cf, pf, af, zf, sf, of = flags
    out = bytearray(FILL)
    struct.pack_into("<Q", out, 0, apply_lahf(rax, flags) & MASK64)
    out[8:13] = bytes((cf, pf, zf, sf, of))
    return bytes(out)


def u64s(buf: bytes):
    return struct.unpack("<4Q", buf)


def pack_u64s(*vals) -> bytes:
    return struct.pack("<4Q", *(v & MASK64 for v in vals))


def pack_out(*qwords) -> bytes:
    out = bytearray(FILL)
    for i, val in enumerate(qwords):
        struct.pack_into("<Q", out, i * 8, val & MASK64)
    return bytes(out)


def reference(name: str, a_bytes: bytes, b_bytes: bytes, altered: bool = False) -> bytes:
    a0, _, _, _ = u64s(a_bytes)
    b0, b1, _, _ = u64s(b_bytes)
    kind, bits, imm_spec = DIFF_SPECS[name]
    if kind == "add_al":
        rhs = imm_spec if altered else (b0 & 0xFF)
        al_res, flags = add_flags(8, a0, rhs)
        rax = (a0 & ~0xFF) | al_res
        return pack_lahf_and_flags(rax, flags)
    rhs = (imm_spec[1] if altered else imm_spec[0]) if imm_spec is not None else b1
    if kind == "add":
        _, flags = add_flags(bits, b0, rhs)
    else:
        _, flags = sub_flags(bits, b0, rhs)
    return pack_lahf_and_flags(a0, flags)


# --- Test vectors ---

RAX_PATTERNS = (
    0x123456789ABCDEF0,
    0xFFFFFFFFFFFF000F,
    0x000000000000FF80,
    0xDEADBEEFCAFE2855,
)


def pairs_for_width(bits: int):
    mask = (1 << bits) - 1
    sign = 1 << (bits - 1)
    edges = [
        # AF=1 without carry out of top bit
        (0x0F, 0x01),
        (0x08, 0x08),
        (0x10, 0x01),
        (0x20, 0x01),
        # AF=1 with carry/borrow out of top bit
        (mask, 0x01),
        (mask - 7, 0x08),
        (0x00, 0x01),
        (0x0F, mask),
        # AF=0 with carry/borrow out of bit 4 (catches bit-4 AF mutation)
        (0x10, 0x10),
        (0x11, 0x11),
        (0x20, 0x10),
        (0x30, 0x10),
        # Zero, sign, signed overflow, parity edges
        (0x00, 0x00),
        (0x01, 0x01),
        (sign - 1, 0x01),
        (sign, 0x01),
        (sign, sign),
        (mask, 0x00),
        (mask, mask),
    ]
    if bits >= 16:
        # Low-byte parity diverges from full-width parity
        edges.extend([
            (0x0100, 0x0000),
            (0x0103, 0x0000),
            (0x0101, 0x0000),
            (0x0100, 0x0001),
            (0x0301, 0x0100),
        ])
    rng = random.Random(0x1A4F00 + bits)
    for _ in range(6):
        edges.append((rng.getrandbits(bits), rng.getrandbits(bits)))
    return [
        (pack_u64s(RAX_PATTERNS[i % len(RAX_PATTERNS)], 0, 0, 0), pack_u64s(a, b, 0, 0))
        for i, (a, b) in enumerate(edges)
    ]


def inputs_for(name: str):
    _, bits, _ = DIFF_SPECS[name]
    return pairs_for_width(bits)


# --- 32-byte guarded buffer helpers ---

def alloc_aligned_buffer(payload: bytes, align: int = 32):
    total = len(GUARD_PRE) + len(payload) + len(GUARD_POST) + align
    buf = ctypes.create_string_buffer(total)
    base_addr = ctypes.addressof(buf)
    start_after_guard = base_addr + len(GUARD_PRE)
    pad = (align - start_after_guard % align) % align
    payload_off = len(GUARD_PRE) + pad
    pre_off = payload_off - len(GUARD_PRE)
    post_off = payload_off + len(payload)
    buf[pre_off:payload_off] = GUARD_PRE
    buf[payload_off:post_off] = payload
    buf[post_off : post_off + len(GUARD_POST)] = GUARD_POST
    return buf, base_addr + payload_off, pre_off, payload_off, post_off


def check_guards_and_read(buf, pre_off: int, payload_off: int, post_off: int, label: str) -> bytes:
    raw = buf.raw
    if raw[pre_off:payload_off] != GUARD_PRE or raw[post_off : post_off + len(GUARD_POST)] != GUARD_POST:
        raise AssertionError(f"32-byte guard bytes corrupted around {label}")
    return raw[payload_off:post_off]


def invoke(fn, a: bytes, b: bytes) -> bytes:
    buf_a, ptr_a, a_pre, a_off, a_post = alloc_aligned_buffer(a)
    buf_b, ptr_b, b_pre, b_off, b_post = alloc_aligned_buffer(b)
    buf_out, ptr_out, o_pre, o_off, o_post = alloc_aligned_buffer(FILL)
    fn(ptr_a, ptr_b, ptr_out)
    check_guards_and_read(buf_a, a_pre, a_off, a_post, "input_a")
    check_guards_and_read(buf_b, b_pre, b_off, b_post, "input_b")
    return check_guards_and_read(buf_out, o_pre, o_off, o_post, "output")


def assert_equal_output(label: str, name: str, idx, got: bytes, want: bytes) -> None:
    if got != want:
        raise AssertionError(f"{label} {name} case {idx}: got {got.hex()} != expected {want.hex()}")


def bind_exports(dll_path: Path, prefix: str = "", names=EXPORTS):
    lib = ctypes.CDLL(str(dll_path.resolve()))
    funcs = {}
    for name in names:
        fn = getattr(lib, prefix + name)
        fn.argtypes = [ctypes.c_uint64, ctypes.c_uint64, ctypes.c_uint64]
        fn.restype = None
        funcs[name] = fn
    return lib, funcs


def emit_controls(original_path: Path, output_path: Path) -> None:
    """Emit mutated-C++ negative control exports into output_path."""
    parts = [PRELUDE, EXTRA_CONTROL_HELPERS]
    with pefile.PE(str(original_path), fast_load=True) as pe:
        for base_name, ctrl_name, pattern, replacement in CPP_MUTATIONS:
            entry = export_rva(pe, base_name)
            src, _ = lift_code(base_name, entry, bounded_code(pe, entry))
            mutated, count = pattern.subn(replacement, src)
            if count == 0:
                raise AssertionError(f"mutation {ctrl_name} matched 0 occurrences in {base_name}")
            mutated = mutated.replace(f"lifted_{base_name}", ctrl_name, 1)
            parts.append(mutated)
    output_path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def check_discarded_read(native_path: Path, lifted_path: Path) -> None:
    payload = pack_u64s(0x1122334455667788, 0, 0, 0)
    for label, dll, prefix in (("native", native_path, ""), ("lifted", lifted_path, "lifted_")):
        _, fns = bind_exports(dll, prefix, ("op_discarded_read",))
        fn = fns["op_discarded_read"]
        source, ptr, _, _, _ = alloc_aligned_buffer(payload)
        for readable in (True, False):
            result, result_ptr, pre, off, post = alloc_aligned_buffer(FILL)
            try:
                fn(ptr, ptr if readable else 0, result_ptr)
            except OSError as error:
                assert not readable and "access violation reading" in str(error).lower(), (label, error)
            else:
                assert readable, f"{label} op_discarded_read discarded a faulting read"
            expected = pack_out(0x1122334455667788, 0x1122334455667788) if readable else pack_out(0x1122334455667788)
            assert_equal_output(
                label, "op_discarded_read", readable, check_guards_and_read(result, pre, off, post, label), expected
            )
        _ = source


def check_differential(native_path: Path, lifted_path: Path, altered_path: Path, controls_path: Path) -> None:
    lifted_lib, lifted = bind_exports(lifted_path, "lifted_")
    lifted_lib.host_has_lahf.argtypes = []
    lifted_lib.host_has_lahf.restype = ctypes.c_uint32
    if not lifted_lib.host_has_lahf():
        print("Host CPU lacks LAHF/SAHF in 64-bit mode (CPUID 80000001H:ECX[0]); skipping native differential check.")
        raise SystemExit(77)

    check_discarded_read(native_path, lifted_path)

    _, native = bind_exports(native_path)
    _, altered = bind_exports(altered_path, "lifted_")
    _, controls = bind_exports(controls_path, "", tuple(c[1] for c in CPP_MUTATIONS))

    total = 0
    for name in EXPORTS:
        for idx, (a, b) in enumerate(inputs_for(name)):
            want = reference(name, a, b)
            got_n = invoke(native[name], a, b)
            got_l = invoke(lifted[name], a, b)
            assert_equal_output("native", name, idx, got_n, want)
            assert_equal_output("lifted", name, idx, got_l, want)
            total += 1

    # ALTER_IMM controls
    diverged = {}
    for name in ALTERED_EXPORTS:
        diffs = 0
        for idx, (a, b) in enumerate(inputs_for(name)):
            want_alt = reference(name, a, b, altered=True)
            want_orig = reference(name, a, b)
            got_alt = invoke(altered[name], a, b)
            assert_equal_output("altered", name, idx, got_alt, want_alt)
            if got_alt != want_orig:
                diffs += 1
        if not diffs:
            raise AssertionError(f"altered control {name} did not diverge from original")
        diverged[name] = diffs

    # Mutated-C++ controls (bit-4 AF, full-width PF, bit-1 cleared, RAX clobber, old AH kept, flag clobber)
    ctrl_diverged = {}
    for base_name, ctrl_name, _, _ in CPP_MUTATIONS:
        diffs = 0
        for a, b in inputs_for(base_name):
            want_orig = reference(base_name, a, b)
            got_ctrl = invoke(controls[ctrl_name], a, b)
            if got_ctrl != want_orig:
                diffs += 1
        if not diffs:
            raise AssertionError(f"mutated-C++ control {ctrl_name} did not diverge from {base_name}")
        ctrl_diverged[ctrl_name] = diffs

    # Output mutation negative control
    sample_a, sample_b = inputs_for("op_add32_lahf")[0]
    expected = reference("op_add32_lahf", sample_a, sample_b)
    mutated = bytearray(expected)
    mutated[1] ^= 0x10
    try:
        assert_equal_output("mutation", "op_add32_lahf", 0, bytes(mutated), expected)
    except AssertionError:
        pass
    else:
        raise AssertionError("mutated output was not caught by comparator")

    print(
        f"{total} native/lifted/reference LAHF cases across {len(EXPORTS)} exports matched bit-for-bit; "
        f"ALTER_IMM diverged on {diverged}; C++ mutations diverged on {ctrl_diverged}; "
        f"dead-read and output mutation controls passed"
    )


# --- Alternate-encoding acceptance & rejection controls ---

def encode_seq(*instructions) -> bytes:
    enc = Encoder(64)
    ip = 0x1000
    for ins in instructions:
        ip += enc.encode(ins, ip)
    return enc.take_buffer()


def check_alt_encodings_and_rejections(original_path: Path) -> None:
    ld_rax = Instruction.create_reg_mem(Code.MOV_R64_RM64, R.RAX, MemoryOperand(R.RCX))
    ld_r9 = Instruction.create_reg_mem(Code.MOV_R64_RM64, R.R9, MemoryOperand(R.RDX))
    st_r8_rax = Instruction.create_mem_reg(Code.MOV_RM64_R64, MemoryOperand(R.R8), R.RAX)
    st_r8_8_setb = Instruction.create_mem(Code.SETB_RM8, MemoryOperand(R.R8, displ=8, displ_size=1))
    ret_ins = Instruction.create(Code.RETNQ)

    alt_accept = [
        ("add_ah_imm8_lahf", (
            ld_rax,
            Instruction.create_reg_i32(Code.ADD_RM8_IMM8, R.AH, 1),
            Instruction.create(Code.LAHF),
            st_r8_rax,
            st_r8_8_setb,
            ret_ins)),
        ("mov_neg_disp_r8_read", (
            Instruction.create_reg_mem(Code.MOV_R64_RM64, R.RAX, MemoryOperand(R.R8, displ=-8, displ_size=1)),
            Instruction.create_reg_i32(Code.ADD_EAX_IMM32, R.EAX, 1),
            Instruction.create(Code.LAHF),
            Instruction.create_reg_i32(Code.MOV_R32_IMM32, R.R9D, 0),
            Instruction.create_reg(Code.SETB_RM8, R.R9L),
            st_r8_rax,
            ret_ins)),
        ("cmp_al_imm8_setg", (
            ld_rax,
            Instruction.create_reg_i32(Code.CMP_AL_IMM8, R.AL, 5),
            Instruction.create(Code.LAHF),
            st_r8_rax,
            Instruction.create_mem(Code.SETG_RM8, MemoryOperand(R.R8, displ=8, displ_size=1)),
            ret_ins)),
    ]
    alt_expected = {
        "add_ah_imm8_lahf": "op_add_flags(8u,",
        "mov_neg_disp_r8_read": "load_mem<std::uint64_t>((r8 + 0xfffffffffffffff8ull))",
        "cmp_al_imm8_setg": "((!zf && (sf == of)) ? 1u : 0u)",
    }
    for label, seq in alt_accept:
        raw = encode_seq(*seq)
        decoded = list(Decoder(64, raw, ip=0x1000))
        assert len(decoded) == len(seq) and not any(ins.is_invalid for ins in decoded), label
        src, count = lift_code(label, 0x1000, raw)
        assert f"lifted_{label}" in src and count == len(seq), (label, count)
        if alt_expected[label] not in src:
            raise AssertionError(f"{label}: expected {alt_expected[label]!r} in generated C++")

    seg_mov = Instruction.create_reg_mem(Code.MOV_R64_RM64, R.RAX, MemoryOperand(R.RCX))
    seg_mov.segment_prefix = R.GS

    unit_cases = [
        # Out-of-scope flag-stack and other integer flag instructions
        ("out_of_scope_pushf", encode_seq(Instruction.create(Code.PUSHFW), ret_ins), "unsupported instruction"),
        ("out_of_scope_popf", encode_seq(Instruction.create(Code.POPFW), ret_ins), "unsupported instruction"),
        ("out_of_scope_pushfq", encode_seq(Instruction.create(Code.PUSHFQ), ret_ins), "unsupported instruction"),
        ("out_of_scope_popfq", encode_seq(Instruction.create(Code.POPFQ), ret_ins), "unsupported instruction"),
        ("out_of_scope_sahf", encode_seq(ld_rax, Instruction.create(Code.SAHF), Instruction.create(Code.LAHF), ret_ins),
         "unsupported instruction"),
        ("out_of_scope_inc", encode_seq(ld_rax, Instruction.create_reg(Code.INC_RM32, R.EAX),
                                        Instruction.create(Code.LAHF), ret_ins), "unsupported instruction"),
        ("out_of_scope_dec", encode_seq(ld_rax, Instruction.create_reg(Code.DEC_RM32, R.EAX),
                                        Instruction.create(Code.LAHF), ret_ins), "unsupported instruction"),
        ("out_of_scope_neg", encode_seq(ld_rax, Instruction.create_reg(Code.NEG_RM32, R.EAX),
                                        Instruction.create(Code.LAHF), ret_ins), "unsupported instruction"),
        ("out_of_scope_adc", encode_seq(ld_rax, Instruction.create_reg_i32(Code.ADC_EAX_IMM32, R.EAX, 1),
                                        Instruction.create(Code.LAHF), ret_ins), "unsupported instruction"),
        ("out_of_scope_sbb", encode_seq(ld_rax, Instruction.create_reg_i32(Code.SBB_EAX_IMM32, R.EAX, 1),
                                        Instruction.create(Code.LAHF), ret_ins), "unsupported instruction"),
        ("out_of_scope_clc", encode_seq(ld_rax, Instruction.create(Code.CLC), Instruction.create(Code.LAHF), ret_ins),
         "unsupported instruction"),
        ("out_of_scope_stc", encode_seq(ld_rax, Instruction.create(Code.STC), Instruction.create(Code.LAHF), ret_ins),
         "unsupported instruction"),
        ("out_of_scope_cmc", encode_seq(ld_rax, Instruction.create(Code.CMC), Instruction.create(Code.LAHF), ret_ins),
         "unsupported instruction"),
        ("out_of_scope_push_rax", encode_seq(ld_rax, Instruction.create_reg(Code.PUSH_R64, R.RAX), ret_ins),
         "unsupported instruction"),
        ("out_of_scope_pop_rax", encode_seq(Instruction.create_reg(Code.POP_R64, R.RAX), ret_ins),
         "unsupported instruction"),
        # Refusal controls per #1022: AND, XOR, TEST, SHL, IMUL before LAHF
        ("refuse_lahf_after_and", encode_seq(
            ld_rax, ld_r9, Instruction.create_reg_reg(Code.AND_R64_RM64, R.RAX, R.R9),
            Instruction.create(Code.LAHF), ret_ins), "unsupported instruction"),
        ("refuse_lahf_after_xor", encode_seq(
            ld_rax, Instruction.create_reg_reg(Code.XOR_R32_RM32, R.EAX, R.EAX),
            Instruction.create(Code.LAHF), ret_ins), "unsupported instruction"),
        ("refuse_lahf_after_test", encode_seq(
            ld_rax, ld_r9, Instruction.create_reg_reg(Code.TEST_RM64_R64, R.RAX, R.R9),
            Instruction.create(Code.LAHF), ret_ins), "unsupported instruction"),
        ("refuse_lahf_after_shl", encode_seq(
            ld_rax, Instruction.create_reg_i32(Code.SHL_RM32_IMM8, R.EAX, 1),
            Instruction.create(Code.LAHF), ret_ins), "unsupported instruction"),
        ("refuse_lahf_after_imul", encode_seq(
            ld_rax, ld_r9, Instruction.create_reg_reg(Code.IMUL_R64_RM64, R.RAX, R.R9),
            Instruction.create(Code.LAHF), ret_ins), "unsupported instruction"),
        # Undefined flags / GPRs
        ("undef_lahf_entry", encode_seq(ld_rax, Instruction.create(Code.LAHF), ret_ins), "undefined flag cf"),
        ("undef_setb_entry", encode_seq(st_r8_8_setb, ret_ins), "undefined flag cf"),
        ("undef_setg_entry", encode_seq(
            Instruction.create_mem(Code.SETG_RM8, MemoryOperand(R.R8, displ=8, displ_size=1)), ret_ins),
         "undefined flag zf"),
        ("undef_lahf_rax", encode_seq(
            Instruction.create_reg_reg(Code.CMP_R64_RM64, R.RCX, R.RDX), Instruction.create(Code.LAHF), ret_ins),
         "undefined GPR rax"),
        ("partial_write_undef_rax", encode_seq(
            Instruction.create_reg_i32(Code.MOV_R8_IMM8, R.AL, 1), ret_ins),
         "partial write to undefined GPR rax"),
        ("partial_setb_undef_r9", encode_seq(
            ld_rax, Instruction.create_reg_i32(Code.ADD_EAX_IMM32, R.EAX, 1),
            Instruction.create_reg(Code.SETB_RM8, R.R9L), ret_ins),
         "partial write to undefined GPR r9"),
        # Memory operands in ADD/SUB/CMP (register-only arithmetic slice)
        ("arith_mem_dst", encode_seq(
            ld_rax, Instruction.create_mem_reg(Code.ADD_RM64_R64, MemoryOperand(R.R8), R.RAX), ret_ins),
         "unsupported arithmetic destination"),
        ("arith_mem_src", encode_seq(
            ld_rax, Instruction.create_reg_mem(Code.ADD_R64_RM64, R.RAX, MemoryOperand(R.RDX)), ret_ins),
         "unsupported arithmetic memory operand"),
        # Prefixes, VEX, nonvolatile GPRs, RSP arithmetic, non-leaf branches/calls/joins, addressing, stream
        ("segment_prefix", encode_seq(seg_mov, ret_ins), "unsupported instruction prefix"),
        ("lock_prefix", bytes.fromhex("f00fb109") + encode_seq(ret_ins), "unsupported instruction prefix"),
        ("rep_prefix", bytes.fromhex("f3a4") + encode_seq(ret_ins), "unsupported instruction prefix"),
        ("vex_vzeroupper", encode_seq(Instruction.create(Code.VEX_VZEROUPPER), ret_ins),
         "unsupported vector-encoded instruction"),
        ("nonvolatile_rbx", encode_seq(Instruction.create_reg_mem(
            Code.MOV_R64_RM64, R.RBX, MemoryOperand(R.RCX)), ret_ins), "nonvolatile GPR"),
        ("nonvolatile_rdi", encode_seq(Instruction.create_reg_reg(
            Code.MOV_R64_RM64, R.RDI, R.RCX), ret_ins), "nonvolatile GPR"),
        ("direct_rsp_add", encode_seq(Instruction.create_reg_i32(Code.ADD_RM64_IMM8, R.RSP, 8), ret_ins),
         "unsupported stack pointer operand"),
        ("branch_jmp", encode_seq(Instruction.create_branch(Code.JMP_REL8_64, 0x1010), ret_ins),
         "unsupported instruction"),
        ("branch_je_join", encode_seq(
            ld_rax, Instruction.create_reg_reg(Code.CMP_R64_RM64, R.RCX, R.RDX),
            Instruction.create_branch(Code.JE_REL8_64, 0x1010),
            Instruction.create_reg_i32(Code.ADD_EAX_IMM32, R.EAX, 1),
            Instruction.create(Code.LAHF), ret_ins),
         "unsupported instruction"),
        ("call_then_lahf", encode_seq(
            ld_rax, Instruction.create_branch(Code.CALL_REL32_64, 0x1020),
            Instruction.create(Code.LAHF), ret_ins),
         "unsupported instruction"),
        ("store_outside_r8", encode_seq(ld_rax, Instruction.create_mem_reg(
            Code.MOV_RM64_R64, MemoryOperand(R.RCX), R.RAX), ret_ins), "non-r8 store memory operand"),
        ("write_r8", encode_seq(ld_rax, Instruction.create_reg_reg(
            Code.MOV_R64_RM64, R.R8, R.RAX), ret_ins), "unsupported write to output buffer pointer r8"),
        ("clobbered_rcx_read", encode_seq(
            Instruction.create_reg_i32(Code.MOV_R32_IMM32, R.ECX, 1), ld_rax, ret_ins),
         "clobbered pointer rcx"),
        ("rip_rel_mem", encode_seq(Instruction.create_reg_mem(
            Code.MOV_R64_RM64, R.RAX, MemoryOperand(R.RIP, displ=0x1020, displ_size=1)), ret_ins),
         "unsupported memory operand"),
        ("indexed_mem", encode_seq(Instruction.create_reg_mem(
            Code.MOV_R64_RM64, R.RAX, MemoryOperand(R.RCX, R.RDX, 4)), ret_ins),
         "unsupported memory operand"),
        ("ret_imm16", encode_seq(Instruction.create_i32(Code.RETNQ_IMM16, 8)), "unsupported instruction"),
        ("missing_ret", encode_seq(ld_rax), "missing terminal ret"),
        ("trailing_after_ret", encode_seq(ld_rax, ret_ins, ld_r9), "unreachable instruction after ret"),
        ("empty_stream", b"", "truncated instruction stream"),
        ("invalid_bytes", bytes.fromhex("fffe") + encode_seq(ret_ins), "invalid instruction"),
    ]

    for label, raw, expected_reason in unit_cases:
        try:
            lift_code(label, 0x1000, raw)
        except ValueError as exc:
            if expected_reason not in str(exc):
                raise AssertionError(f"{label}: expected {expected_reason!r}, got {exc!r}") from exc
        else:
            raise AssertionError(f"{label}: translator unexpectedly accepted rejected control")

    # End-to-end PE patching controls on a copy of the built native DLL.
    pe_bytes = original_path.read_bytes()
    with pefile.PE(data=pe_bytes, fast_load=True) as pe:
        entry = export_rva(pe, "op_add64_lahf")
        file_off = pe.get_offset_from_rva(entry)
        pdata = pe.OPTIONAL_HEADER.DATA_DIRECTORY[3]
        records = pe.get_data(pdata.VirtualAddress, pdata.Size)
        rec_idx = next(
            i for i in range(0, len(records), 12)
            if struct.unpack_from("<I", records, i)[0] == entry
        )
        pdata_end_off = pe.get_offset_from_rva(pdata.VirtualAddress + rec_idx + 4)
        orig_end = struct.unpack_from("<I", records, rec_idx + 4)[0]
        max_len = orig_end - entry

    unit_map = {lbl: raw for lbl, raw, _ in unit_cases}
    pe_patches = [
        ("pe_out_of_scope_pushf", unit_map["out_of_scope_pushf"], "unsupported instruction"),
        ("pe_out_of_scope_popfq", unit_map["out_of_scope_popfq"], "unsupported instruction"),
        ("pe_refuse_test_lahf", unit_map["refuse_lahf_after_test"], "unsupported instruction"),
        ("pe_refuse_inc_lahf", unit_map["out_of_scope_inc"], "unsupported instruction"),
        ("pe_undef_lahf_entry", unit_map["undef_lahf_entry"], "undefined flag cf"),
        ("pe_nonvolatile_rbx", unit_map["nonvolatile_rbx"], "nonvolatile GPR"),
        ("pe_branch_je_join", unit_map["branch_je_join"], "unsupported instruction"),
        ("pe_call_then_lahf", unit_map["call_then_lahf"], "unsupported instruction"),
        ("pe_store_outside_r8", unit_map["store_outside_r8"], "non-r8 store memory operand"),
        ("pe_trailing_after_ret", unit_map["trailing_after_ret"], "unreachable instruction after ret"),
    ]
    with TemporaryDirectory() as folder:
        patched_path = Path(folder) / "patched.dll"
        for label, patch, expected_reason in pe_patches:
            if len(patch) > max_len:
                raise AssertionError(f"{label}: patch ({len(patch)} bytes) exceeds op_add64_lahf ({max_len})")
            damaged = bytearray(pe_bytes)
            damaged[file_off : file_off + len(patch)] = patch
            struct.pack_into("<I", damaged, pdata_end_off, entry + len(patch))
            patched_path.write_bytes(damaged)
            try:
                translate(patched_path, ["op_add64_lahf"])
            except ValueError as exc:
                if expected_reason not in str(exc):
                    raise AssertionError(f"{label}: expected {expected_reason!r}, got {exc!r}") from exc
            else:
                raise AssertionError(f"{label}: PE translate accepted rejected patch")

    print(
        f"{len(alt_accept)} alternate-encoding lift checks, {len(unit_cases)} unit rejection controls, "
        f"and {len(pe_patches)} PE-patched rejection controls passed"
    )


if __name__ == "__main__":
    if sys.argv[1] == "emit-controls":
        emit_controls(Path(sys.argv[2]), Path(sys.argv[3]))
    else:
        orig, lifted, alt, ctrls = (Path(p) for p in sys.argv[1:5])
        check_alt_encodings_and_rejections(orig)
        check_differential(orig, lifted, alt, ctrls)
