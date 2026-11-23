"""Differential checks, mutated-C++ controls, ALTER_IMM controls, and rejection controls for integer flags AOT."""

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
from cpu_leaf_aot import export_rva

MASK8 = 0xFF
MASK16 = 0xFFFF
MASK32 = 0xFFFFFFFF
MASK64 = 0xFFFFFFFFFFFFFFFF
GUARD_PRE = bytes(0xA0 + (i % 16) for i in range(32))
GUARD_POST = bytes(0xC0 + (i % 16) for i in range(32))
FILL = b"\x5A" * 32

EXPORTS = (
    "op_lahf_preserve",
    "op_lahf_add",
    "op_lahf_sub",
    "op_lahf_adc_sbb",
    "op_lahf_inc_dec_neg",
    "op_lahf_cmp_clc_cmc",
    "op_pushf_flags",
    "op_pushf_stride",
    "op_popf_stride",
    "op_popfq_pushfq_roundtrip",
    "op_pipeline",
)

ALTERED_EXPORTS = (
    "op_lahf_preserve",
    "op_lahf_add",
    "op_lahf_sub",
    "op_pushf_flags",
    "op_popfq_pushfq_roundtrip",
)

# Mutated-C++ negative controls: (base_export, control_name, regex, replacement, test_inputs_fn_name)
CPP_MUTATIONS = (
    ("op_lahf_preserve", "ctrl_wrong_af", re.compile(r"pack_lahf\(cf, pf, af, zf, sf\)"), "pack_lahf(cf, pf, false, zf, sf)"),
    ("op_lahf_sub", "ctrl_wrong_pf", re.compile(r"pack_lahf\(cf, pf, af, zf, sf\)"), "pack_lahf(cf, false, af, zf, sf)"),
    ("op_pushf_flags", "ctrl_wrong_if", re.compile(r"pack_flags16\(cf, pf, af, zf, sf, df, of\)"), "static_cast<std::uint16_t>(pack_flags16(cf, pf, af, zf, sf, df, of) & ~0x0200u)"),
    (
        "op_pushf_stride",
        "ctrl_wrong_pushf_stride",
        re.compile(r"push_u16\(stack, sp, pack_flags16\(cf, pf, af, zf, sf, df, of\)\);"),
        "push_u64(stack, sp, static_cast<std::uint64_t>(pack_flags16(cf, pf, af, zf, sf, df, of)));",
    ),
    (
        "op_popf_stride",
        "ctrl_wrong_popf_stride",
        re.compile(r"unpack_flags16\(pop_u16\(stack, sp\),"),
        "unpack_flags16(static_cast<std::uint16_t>(pop_u64(stack, sp)),",
    ),
    (
        "op_lahf_preserve",
        "ctrl_lahf_clobber_rax",
        re.compile(r"rax = \(rax & ~0xff00ull\) \| \(static_cast<word>\(pack_lahf\(cf, pf, af, zf, sf\)\) << 8u\);"),
        "rax = (static_cast<word>(pack_lahf(cf, pf, af, zf, sf)) << 8u);",
    ),
)


# --- Independent Python ISA reference model ---

def calc_pf(val: int) -> int:
    return int(((val & 0xFF).bit_count() % 2) == 0)


def add_flags(bits: int, a: int, b: int, cin: int = 0):
    mask = (1 << bits) - 1
    ua = a & mask
    ub = b & mask
    total = ua + ub + cin
    res = total & mask
    cf = int((total >> bits) != 0)
    af = int(((ua ^ ub ^ res) & 0x10) != 0)
    pf = calc_pf(res)
    zf = int(res == 0)
    sf = int(((res >> (bits - 1)) & 1) != 0)
    of = int((((ua ^ res) & (ub ^ res)) >> (bits - 1)) & 1)
    return res, (cf, pf, af, zf, sf, of)


def sub_flags(bits: int, a: int, b: int, bin_: int = 0):
    mask = (1 << bits) - 1
    ua = a & mask
    ub = b & mask
    diff = ua - ub - bin_
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


def pack_flags16(flags, df: int) -> int:
    cf, pf, af, zf, sf, of = flags
    return (of << 11) | (df << 10) | 0x0202 | (sf << 7) | (zf << 6) | (af << 4) | (pf << 2) | cf


def pack_flags64(flags, df: int, id_bit: int) -> int:
    return pack_flags16(flags, df) | (id_bit << 21)


def unpack_flags16(val: int):
    cf = (val >> 0) & 1
    pf = (val >> 2) & 1
    af = (val >> 4) & 1
    zf = (val >> 6) & 1
    sf = (val >> 7) & 1
    df = (val >> 10) & 1
    of = (val >> 11) & 1
    return (cf, pf, af, zf, sf, of), df


def unpack_flags64(val: int):
    flags, df = unpack_flags16(val & 0xFFFF)
    id_bit = (val >> 21) & 1
    return flags, df, id_bit


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
    a0, a1, a2, a3 = u64s(a_bytes)
    b0, b1, b2, b3 = u64s(b_bytes)
    if name == "op_lahf_preserve":
        _, flags = add_flags(32, b0, 1 if altered else 17)
        return pack_out(apply_lahf(a0, flags))
    if name == "op_lahf_add":
        imm = 5 if altered else (b0 & 0xFF)
        al_res, flags = add_flags(8, a0, imm)
        rax = (a0 & ~0xFF) | al_res
        return pack_out(apply_lahf(rax, flags))
    if name == "op_lahf_sub":
        _, flags = sub_flags(32, b0, 1 if altered else 15)
        return pack_out(apply_lahf(a0, flags))
    if name == "op_lahf_adc_sbb":
        _, f0 = add_flags(32, b0, 0, cin=1)
        _, f1 = sub_flags(32, b0, 0, bin_=1)
        _, f2 = add_flags(32, b1, b2, cin=0)
        return pack_out(apply_lahf(a0, f0), apply_lahf(a0, f1), apply_lahf(a0, f2))
    if name == "op_lahf_inc_dec_neg":
        _, f_inc = add_flags(32, b0, 1)
        f_inc = (0, *f_inc[1:])  # clc + inc preserves CF=0
        _, f_dec = sub_flags(32, b0, 1)
        f_dec = (1, *f_dec[1:])  # stc + dec preserves CF=1
        _, f_neg = sub_flags(32, 0, b0)
        return pack_out(apply_lahf(a0, f_inc), apply_lahf(a0, f_dec), apply_lahf(a0, f_neg))
    if name == "op_lahf_cmp_clc_cmc":
        _, f_cmp = sub_flags(32, b0, b1)
        f_cmc = (f_cmp[0] ^ 1, *f_cmp[1:])
        f_clc = (0, *f_cmp[1:])
        return pack_out(apply_lahf(a0, f_cmp), apply_lahf(a0, f_cmc), apply_lahf(a0, f_clc))
    if name == "op_pushf_flags":
        _, flags = sub_flags(64, a0, b0)
        df = 1 if altered else 0
        return pack_out(pack_flags16(flags, df))
    if name == "op_pushf_stride":
        _, flags = add_flags(32, b0, b1)
        f16 = pack_flags16(flags, 0)
        r10 = f16 | ((a0 & 0xFFFFFFFFFFFF) << 16)
        return pack_out(r10, a0)
    if name == "op_popf_stride":
        flags, df = unpack_flags16(b0 & 0xFFFF)
        f16 = pack_flags16(flags, df)
        return pack_out(f16, a0, a0)
    if name == "op_popfq_pushfq_roundtrip":
        val = (a0 ^ 1) if altered else a0
        flags, df, id_bit = unpack_flags64(val)
        f64 = pack_flags64(flags, df, id_bit)
        return pack_out(f64, b0, b0)
    if name == "op_pipeline":
        _, df, id_bit = unpack_flags64(a0)
        _, f_add = add_flags(64, b1, b2)
        rax = apply_lahf(b0, f_add)
        r10 = pack_flags64(f_add, df, id_bit)
        return pack_out(rax, r10)
    raise ValueError(f"unknown export {name}")


# --- Test vectors (all keep TF=0, AC=0, IOPL=0, NT=0, RF=0, VM=0, VIF=0, VIP=0) ---

def lahf_pairs():
    rax_patterns = [
        0x123456789ABCDEF0,
        0xFFFFFFFFFFFF000F,
        0x000000000000FF80,
        0xDEADBEEFCAFEBABE,
    ]
    # Nibble carry/borrow edges (0x0F, 0x10, 0x00, 0xFF, parity, signed edges)
    vals = [0x00, 0x01, 0x0F, 0x10, 0x1E, 0x1F, 0x7F, 0x80, 0xFF, 0x100, 0x7FFFFFFF, 0x80000000, 0xFFFFFFFF]
    pairs = []
    for i, b0 in enumerate(vals):
        rax = rax_patterns[i % len(rax_patterns)]
        b1 = vals[(i * 3 + 5) % len(vals)]
        b2 = vals[(i * 7 + 2) % len(vals)]
        pairs.append((pack_u64s(rax, 0, 0, 0), pack_u64s(b0, b1, b2, 0)))
    rng = random.Random(0xF1A901)
    for _ in range(8):
        pairs.append((pack_u64s(rng.getrandbits(64), 0, 0, 0),
                      pack_u64s(rng.getrandbits(64), rng.getrandbits(64), rng.getrandbits(64), 0)))
    return pairs


def flags16_pairs():
    # Safe 16-bit flag masks: CF/PF/AF/ZF/SF/DF/OF only (TF=bit 8=0, IOPL=0, NT=0)
    safe_mask = 0x0CD5
    flag_bits = (0, 2, 4, 6, 7, 10, 11)
    pairs = []
    for b in flag_bits:
        f = (1 << b) | 0x0202
        pairs.append((pack_u64s(0x1122334455667788, 0, 0, 0), pack_u64s(f, 0, 0, 0)))
    pairs.append((pack_u64s(0xAABBCCDDEEFF0011, 0, 0, 0), pack_u64s(0x0202, 0, 0, 0)))
    pairs.append((pack_u64s(0x0123456789ABCDEF, 0, 0, 0), pack_u64s(safe_mask | 0x0202, 0, 0, 0)))
    rng = random.Random(0xF1A902)
    for _ in range(8):
        f = (rng.getrandbits(16) & safe_mask) | 0x0202
        pairs.append((pack_u64s(rng.getrandbits(64), 0, 0, 0), pack_u64s(f, 0, 0, 0)))
    return pairs


def flags64_pairs():
    # Test ID=0 and ID=1 explicitly alongside DF=0/1 and all CF/PF/AF/ZF/SF/OF combinations (TF=0)
    safe_mask = 0x00200CD5
    pairs = []
    for id_bit in (0, 1):
        for df_bit in (0, 1):
            for low in (0x0202, 0x0001, 0x0010, 0x0044, 0x0880, 0x08D5):
                val = ((low & 0x08D5) | 0x0202 | (df_bit << 10) | (id_bit << 21)) & safe_mask | 0x0202
                pairs.append((pack_u64s(val, 0, 0, 0), pack_u64s(0xCAFEBABE12345678, 0, 0, 0)))
    # Finish with ID=1 restored cleanly
    pairs.append((pack_u64s(0x00200202, 0, 0, 0), pack_u64s(0x0102030405060708, 0, 0, 0)))
    return pairs


def pipeline_pairs():
    edges = [
        (0x00000202, 0x1122334455667788, 0x000000000000000F, 0x0000000000000001),
        (0x00200602, 0xAABBCCDDEEFF0011, 0x7FFFFFFFFFFFFFFF, 0x0000000000000001),
        (0x00200202, 0x00000000000000FF, 0x8000000000000000, 0x8000000000000000),
        (0x00000402, 0x123456789ABCDEF0, 0xFFFFFFFFFFFFFFFF, 0x0000000000000001),
    ]
    pairs = [(pack_u64s(f, 0, 0, 0), pack_u64s(rax, b1, b2, 0)) for f, rax, b1, b2 in edges]
    rng = random.Random(0xF1A903)
    for _ in range(6):
        f = ((rng.getrandbits(22) & 0x00200CD5) | 0x0202)
        pairs.append((pack_u64s(f, 0, 0, 0),
                      pack_u64s(rng.getrandbits(64), rng.getrandbits(64), rng.getrandbits(64), 0)))
    # Restore ID=1 cleanly at end
    pairs.append((pack_u64s(0x00200202, 0, 0, 0), pack_u64s(0, 1, 2, 0)))
    return pairs


def inputs_for(name: str):
    if name == "op_popf_stride":
        return flags16_pairs()
    if name == "op_popfq_pushfq_roundtrip":
        return flags64_pairs()
    if name == "op_pipeline":
        return pipeline_pairs()
    if name == "op_pushf_flags":
        edges = [
            (0, 0), (0, 1), (1, 0), (0x0F, 0x10), (0x10, 0x0F),
            (0x7FFFFFFFFFFFFFFF, 0x8000000000000000),
            (0x8000000000000000, 0x7FFFFFFFFFFFFFFF),
            (0xFFFFFFFFFFFFFFFF, 0x0000000000000001),
        ]
        pairs = [(pack_u64s(a, 0, 0, 0), pack_u64s(b, 0, 0, 0)) for a, b in edges]
        rng = random.Random(0xF1A904)
        for _ in range(8):
            pairs.append((pack_u64s(rng.getrandbits(64), 0, 0, 0), pack_u64s(rng.getrandbits(64), 0, 0, 0)))
        return pairs
    return lahf_pairs()


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
    prelude = PRELUDE
    parts = [prelude]
    with pefile.PE(str(original_path), fast_load=True) as pe:
        for base_name, ctrl_name, pattern, replacement in CPP_MUTATIONS:
            entry = export_rva(pe, base_name)
            from cpu_leaf_aot import bounded_code
            src, _ = lift_code(base_name, entry, bounded_code(pe, entry))
            mutated, count = pattern.subn(replacement, src)
            if count == 0:
                raise AssertionError(f"mutation {ctrl_name} matched 0 occurrences in {base_name}")
            mutated = mutated.replace(f"lifted_{base_name}", ctrl_name, 1)
            # Ensure wrong_popf_stride cannot touch past stack[256] in C++
            mutated = mutated.replace("std::uint8_t stack[256]{};", "std::uint8_t stack[512]{};")
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
    check_discarded_read(native_path, lifted_path)

    _, native = bind_exports(native_path)
    _, lifted = bind_exports(lifted_path, "lifted_")
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

    # Mutated-C++ controls (wrong AF, PF, IF, pushf/popf stride, lahf clobbering RAX)
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
    sample_a, sample_b = pipeline_pairs()[0]
    expected = reference("op_pipeline", sample_a, sample_b)
    mutated = bytearray(expected)
    mutated[1] ^= 0x10
    try:
        assert_equal_output("mutation", "op_pipeline", 0, bytes(mutated), expected)
    except AssertionError:
        pass
    else:
        raise AssertionError("mutated output was not caught by comparator")

    print(
        f"{total} native/lifted/reference integer-flag cases across {len(EXPORTS)} exports matched bit-for-bit; "
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
    ret_ins = Instruction.create(Code.RETNQ)

    alt_accept = [
        ("push_pop_ff_8f", (
            ld_rax,
            Instruction.create_reg(Code.PUSH_RM64, R.RAX),
            Instruction.create_reg(Code.POP_RM64, R.R9),
            Instruction.create_mem_reg(Code.MOV_RM64_R64, MemoryOperand(R.R8), R.R9),
            ret_ins)),
        ("pushf_popf_flags", (
            ld_rax, ld_r9,
            Instruction.create_reg_reg(Code.ADD_R64_RM64, R.RAX, R.R9),
            Instruction.create(Code.PUSHFW),
            Instruction.create(Code.POPFW),
            Instruction.create(Code.CLD),
            Instruction.create(Code.LAHF),
            st_r8_rax, ret_ins)),
        ("mov_neg_disp_r8_read", (
            Instruction.create_reg_mem(Code.MOV_R64_RM64, R.RAX, MemoryOperand(R.R8, displ=-8, displ_size=1)),
            Instruction.create_reg_i32(Code.ADD_EAX_IMM32, R.EAX, 1),
            Instruction.create(Code.LAHF),
            st_r8_rax, ret_ins)),
        ("stack_read_disp8", (
            ld_rax, ld_r9,
            Instruction.create_reg(Code.PUSH_R64, R.RAX),
            Instruction.create_reg(Code.PUSH_R64, R.R9),
            Instruction.create_reg_mem(Code.MOV_R64_RM64, R.R10, MemoryOperand(R.RSP, displ=8, displ_size=1)),
            Instruction.create_reg(Code.POP_R64, R.R9),
            Instruction.create_reg(Code.POP_R64, R.RAX),
            Instruction.create_mem_reg(Code.MOV_RM64_R64, MemoryOperand(R.R8), R.R10),
            ret_ins)),
        ("sahf_lahf_chain", (
            ld_rax,
            Instruction.create(Code.SAHF),
            Instruction.create(Code.LAHF),
            st_r8_rax, ret_ins)),
    ]
    alt_expected = {
        "push_pop_ff_8f": "pop_u64(stack, sp)",
        "pushf_popf_flags": "push_u16(stack, sp, pack_flags16(",
        "mov_neg_disp_r8_read": "load_mem<std::uint64_t>((r8 + 0xfffffffffffffff8ull))",
        "stack_read_disp8": "stack_load<std::uint64_t>(stack, sp + 8u)",
        "sahf_lahf_chain": "unpack_lahf(",
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

    # 33 x pushfq = 264 bytes > 256 byte local stack limit
    overflow_seq = tuple([ld_rax, Instruction.create_reg(Code.PUSH_R64, R.RAX), Instruction.create(Code.POPFQ)]
                         + [Instruction.create(Code.PUSHFQ)] * 33
                         + [Instruction.create(Code.POPFQ)] * 33 + [ret_ins])

    unit_cases = [
        # Unbalanced RSP / stack overflow / stack underflow / OOB stack read
        ("unbalanced_push_rax", encode_seq(ld_rax, Instruction.create_reg(Code.PUSH_R64, R.RAX), ret_ins),
         "unbalanced stack pointer"),
        ("unbalanced_pushf", encode_seq(ld_rax, Instruction.create_reg_i32(Code.ADD_EAX_IMM32, R.EAX, 1),
                                        Instruction.create(Code.PUSHFW), ret_ins),
         "unbalanced stack pointer"),
        ("unbalanced_pushfq", encode_seq(ld_rax, Instruction.create_reg(Code.PUSH_R64, R.RAX),
                                         Instruction.create(Code.POPFQ), Instruction.create(Code.PUSHFQ),
                                         Instruction.create(Code.CLD), ret_ins),
         "unbalanced stack pointer"),
        ("stack_underflow_popfq", encode_seq(Instruction.create(Code.POPFQ), Instruction.create(Code.CLD), ret_ins),
         "local stack underflow"),
        ("stack_underflow_popf", encode_seq(Instruction.create(Code.POPFW), Instruction.create(Code.CLD), ret_ins),
         "local stack underflow"),
        ("stack_underflow_pop_r64", encode_seq(Instruction.create_reg(Code.POP_R64, R.RAX), ret_ins),
         "local stack underflow"),
        ("stack_overflow", encode_seq(*overflow_seq), "local stack overflow"),
        ("stack_oob_read", encode_seq(
            ld_rax, Instruction.create_reg(Code.PUSH_R64, R.RAX),
            Instruction.create_reg_mem(Code.MOV_R64_RM64, R.R9, MemoryOperand(R.RSP, displ=8, displ_size=1)),
            Instruction.create_reg(Code.POP_R64, R.RAX), ret_ins),
         "stack read out of local bounds"),
        # DF = 1 or dynamic DF at ret
        ("df_one_std_ret", encode_seq(Instruction.create(Code.STD), ret_ins), "direction flag may be non-zero"),
        ("df_dynamic_popf_ret", encode_seq(
            ld_rax, Instruction.create_reg(Code.PUSH_R16, R.AX), Instruction.create(Code.POPFW), ret_ins),
         "direction flag may be non-zero"),
        ("df_dynamic_popfq_ret", encode_seq(
            ld_rax, Instruction.create_reg(Code.PUSH_R64, R.RAX), Instruction.create(Code.POPFQ), ret_ins),
         "direction flag may be non-zero"),
        # Undefined flag reads
        ("undef_lahf_entry", encode_seq(ld_rax, Instruction.create(Code.LAHF), ret_ins), "undefined flag cf"),
        ("undef_lahf_after_and_af", encode_seq(
            ld_rax, ld_r9, Instruction.create_reg_reg(Code.AND_R64_RM64, R.RAX, R.R9),
            Instruction.create(Code.LAHF), ret_ins),
         "undefined flag af"),
        ("undef_lahf_after_xor_af", encode_seq(
            ld_rax, Instruction.create_reg_reg(Code.XOR_R32_RM32, R.EAX, R.EAX),
            Instruction.create(Code.LAHF), ret_ins),
         "undefined flag af"),
        ("undef_lahf_after_clc", encode_seq(ld_rax, Instruction.create(Code.CLC), Instruction.create(Code.LAHF), ret_ins),
         "undefined flag pf"),
        ("undef_pushf_after_sahf_of", encode_seq(
            ld_rax, Instruction.create(Code.SAHF), Instruction.create(Code.PUSHFW),
            Instruction.create(Code.POPFW), Instruction.create(Code.CLD), ret_ins),
         "undefined flag of"),
        ("undef_pushfq_without_popfq_id", encode_seq(
            ld_rax, Instruction.create_reg_i32(Code.ADD_EAX_IMM32, R.EAX, 1),
            Instruction.create(Code.PUSHFQ), Instruction.create_reg(Code.POP_R64, R.R9), ret_ins),
         "undefined flag id"),
        ("undef_cmc_entry", encode_seq(Instruction.create(Code.CMC), ret_ins), "undefined flag cf"),
        ("undef_adc_entry", encode_seq(ld_rax, Instruction.create_reg_i32(Code.ADC_EAX_IMM32, R.EAX, 1), ret_ins),
         "undefined flag cf"),
        ("undef_sbb_entry", encode_seq(ld_rax, Instruction.create_reg_i32(Code.SBB_EAX_IMM32, R.EAX, 1), ret_ins),
         "undefined flag cf"),
        # Undefined GPR / partial write to undefined GPR
        ("undef_lahf_rax", encode_seq(
            Instruction.create_reg_reg(Code.CMP_R64_RM64, R.RCX, R.RDX), Instruction.create(Code.LAHF), ret_ins),
         "undefined GPR rax"),
        ("partial_write_undef_rax", encode_seq(
            Instruction.create_reg_i32(Code.MOV_R8_IMM8, R.AL, 1), ret_ins),
         "partial write to undefined GPR rax"),
        # Prefixes, VEX, nonvolatile GPRs, RSP arithmetic, non-leaf branches/calls, addressing, stream
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
        ("branch_je", encode_seq(
            Instruction.create_reg_reg(Code.CMP_R64_RM64, R.RCX, R.RDX),
            Instruction.create_branch(Code.JE_REL8_64, 0x1010), ret_ins),
         "unsupported instruction"),
        ("call_rel", encode_seq(Instruction.create_branch(Code.CALL_REL32_64, 0x1020), ret_ins),
         "unsupported instruction"),
        ("store_outside_r8", encode_seq(ld_rax, Instruction.create_mem_reg(
            Code.MOV_RM64_R64, MemoryOperand(R.RCX), R.RAX), ret_ins), "non-r8 store memory operand"),
        ("write_r8", encode_seq(ld_rax, Instruction.create_reg_reg(
            Code.MOV_R64_RM64, R.R8, R.RAX), ret_ins), "unsupported write to output buffer pointer r8"),
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
        entry = export_rva(pe, "op_pipeline")
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
        ("pe_unbalanced_pushf", unit_map["unbalanced_pushf"], "unbalanced stack pointer"),
        ("pe_stack_underflow_popfq", unit_map["stack_underflow_popfq"], "local stack underflow"),
        ("pe_df_one_std_ret", unit_map["df_one_std_ret"], "direction flag may be non-zero"),
        ("pe_undef_lahf_and_af", unit_map["undef_lahf_after_and_af"], "undefined flag af"),
        ("pe_undef_pushfq_id", unit_map["undef_pushfq_without_popfq_id"], "undefined flag id"),
        ("pe_nonvolatile_rbx", unit_map["nonvolatile_rbx"], "nonvolatile GPR"),
        ("pe_branch_je", unit_map["branch_je"], "unsupported instruction"),
        ("pe_call_rel", unit_map["call_rel"], "unsupported instruction"),
        ("pe_store_outside_r8", unit_map["store_outside_r8"], "non-r8 store memory operand"),
        ("pe_trailing_after_ret", unit_map["trailing_after_ret"], "unreachable instruction after ret"),
    ]
    with TemporaryDirectory() as folder:
        patched_path = Path(folder) / "patched.dll"
        for label, patch, expected_reason in pe_patches:
            if len(patch) > max_len:
                raise AssertionError(f"{label}: patch ({len(patch)} bytes) exceeds op_pipeline ({max_len})")
            damaged = bytearray(pe_bytes)
            damaged[file_off : file_off + len(patch)] = patch
            struct.pack_into("<I", damaged, pdata_end_off, entry + len(patch))
            patched_path.write_bytes(damaged)
            try:
                translate(patched_path, ["op_pipeline"])
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
        check_differential(orig, lifted, alt, ctrls)
        check_alt_encodings_and_rejections(orig)
