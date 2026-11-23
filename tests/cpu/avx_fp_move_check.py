"""Differential checks, fault-ordering controls, mutation controls and rejection controls for AVX FP add/sub and move AOT."""

import ctypes
from fractions import Fraction
from pathlib import Path
import random
import struct
import sys
from tempfile import TemporaryDirectory

import pefile
from iced_x86 import Code, Decoder, Encoder, Instruction, MemoryOperand, Register as R

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from cpu_avx_fp_move_aot import lift_code, translate
from cpu_leaf_aot import export_rva

MASK32 = 0xFFFFFFFF
MASK64 = 0xFFFFFFFFFFFFFFFF
GUARD_PRE = bytes(0xA0 + (i % 16) for i in range(32))
GUARD_POST = bytes(0xC0 + (i % 16) for i in range(32))
FILL = b"\x5A" * 32

EXPORTS = (
    "op_vaddsubps_xmm_reg",
    "op_vaddsubps_xmm_mem",
    "op_vaddsubps_xmm_mem_plus1",
    "op_vaddsubps_ymm_reg",
    "op_vaddsubps_ymm_mem",
    "op_vaddsubps_ymm_mem_plus1",
    "op_vaddsubps_self",
    "op_vaddsubpd_xmm_reg",
    "op_vaddsubpd_xmm_mem",
    "op_vaddsubpd_xmm_mem_plus1",
    "op_vaddsubpd_ymm_reg",
    "op_vaddsubpd_ymm_mem",
    "op_vaddsubpd_ymm_mem_plus1",
    "op_vmovq_xmm_xmm",
    "op_vmovq_xmm_m64",
    "op_vmovq_m64_xmm",
    "op_vmovq_xmm_r64",
    "op_vmovq_r64_xmm",
    "op_vmaskmovdqu",
    "op_pipeline",
)

ALTERED_EXPORTS = (
    "op_vaddsubps_xmm_reg",
    "op_vaddsubps_ymm_reg",
    "op_vaddsubpd_xmm_reg",
    "op_vmovq_xmm_m64",
    "op_vmaskmovdqu",
)


# --- Independent Python IEEE-754 binary32 / binary64 reference model ---

class _FPFormat:
    def __init__(self, ebits: int, mbits: int):
        self.ebits = ebits
        self.mbits = mbits
        self.bits = 1 + ebits + mbits
        self.bias = (1 << (ebits - 1)) - 1
        self.emax = (1 << ebits) - 1
        self.sign_mask = 1 << (self.bits - 1)
        self.exp_mask = self.emax << mbits
        self.frac_mask = (1 << mbits) - 1
        self.quiet_bit = 1 << (mbits - 1)
        self.indef = self.sign_mask | self.exp_mask | self.quiet_bit
        self.max_finite = ((self.emax - 1) << mbits) | self.frac_mask

    def unpack(self, raw: int):
        sign = (raw >> (self.bits - 1)) & 1
        exp = (raw >> self.mbits) & self.emax
        frac = raw & self.frac_mask
        return sign, exp, frac

    def is_nan(self, raw: int) -> bool:
        _, exp, frac = self.unpack(raw)
        return exp == self.emax and frac != 0

    def is_inf(self, raw: int) -> bool:
        _, exp, frac = self.unpack(raw)
        return exp == self.emax and frac == 0

    def is_zero(self, raw: int) -> bool:
        _, exp, frac = self.unpack(raw)
        return exp == 0 and frac == 0

    def quiet(self, raw: int) -> int:
        return raw | self.quiet_bit

    def to_fraction(self, raw: int) -> Fraction:
        sign, exp, frac = self.unpack(raw)
        if exp == 0:
            mag = Fraction(frac, 1) * (Fraction(1, 2) ** (self.bias - 1 + self.mbits))
        else:
            mag = Fraction((1 << self.mbits) | frac, 1) * (Fraction(2, 1) ** (exp - self.bias - self.mbits))
        return -mag if sign else mag

    @staticmethod
    def _round_rne(mag: Fraction) -> int:
        q, r = divmod(mag.numerator, mag.denominator)
        twice_r = r * 2
        if twice_r > mag.denominator or (twice_r == mag.denominator and (q & 1)):
            q += 1
        return q

    def from_fraction(self, val: Fraction) -> int:
        if val == 0:
            return 0
        sign = 1 if val < 0 else 0
        mag = -val if sign else val
        num, den = mag.numerator, mag.denominator
        e = num.bit_length() - den.bit_length()
        while (num << (-e) if e < 0 else num) < (den << e if e >= 0 else den):
            e -= 1
        while (num << (-(e + 1)) if e + 1 < 0 else num) >= (den << (e + 1) if e + 1 >= 0 else den):
            e += 1
        emin = 1 - self.bias
        if e < emin:
            scaled = mag * (Fraction(2, 1) ** (self.mbits - emin))
            q = self._round_rne(scaled)
            if q == (1 << self.mbits):
                return (sign << (self.bits - 1)) | (1 << self.mbits)
            if q == 0:
                return sign << (self.bits - 1)
            return (sign << (self.bits - 1)) | q
        scaled = mag * (Fraction(2, 1) ** (self.mbits - e))
        q = self._round_rne(scaled)
        if q == (1 << (self.mbits + 1)):
            q >>= 1
            e += 1
        bexp = e + self.bias
        if bexp >= self.emax:
            return (sign << (self.bits - 1)) | self.exp_mask
        return (sign << (self.bits - 1)) | (bexp << self.mbits) | (q & self.frac_mask)

    def add(self, a: int, b: int) -> int:
        if self.is_nan(a):
            return self.quiet(a)
        if self.is_nan(b):
            return self.quiet(b)
        sa, _, _ = self.unpack(a)
        sb, _, _ = self.unpack(b)
        if self.is_inf(a) and self.is_inf(b):
            return self.indef if sa != sb else a
        if self.is_inf(a):
            return a
        if self.is_inf(b):
            return b
        if self.is_zero(a) and self.is_zero(b):
            return (self.sign_mask if sa else 0) if sa == sb else 0
        return self.from_fraction(self.to_fraction(a) + self.to_fraction(b))

    def sub(self, a: int, b: int) -> int:
        if self.is_nan(a):
            return self.quiet(a)
        if self.is_nan(b):
            return self.quiet(b)
        return self.add(a, b ^ self.sign_mask)


F32 = _FPFormat(8, 23)
F64 = _FPFormat(11, 52)


def ref_vaddsubps(a: bytes, b: bytes, wide: bool) -> bytes:
    n = 8 if wide else 4
    xa = struct.unpack(f"<{n}I", a[: n * 4])
    xb = struct.unpack(f"<{n}I", b[: n * 4])
    out = [F32.add(xa[i], xb[i]) if (i & 1) else F32.sub(xa[i], xb[i]) for i in range(n)]
    res = struct.pack(f"<{n}I", *out)
    return res if wide else res + b"\x00" * 16


def ref_vaddsubpd(a: bytes, b: bytes, wide: bool) -> bytes:
    n = 4 if wide else 2
    xa = struct.unpack(f"<{n}Q", a[: n * 8])
    xb = struct.unpack(f"<{n}Q", b[: n * 8])
    out = [F64.add(xa[i], xb[i]) if (i & 1) else F64.sub(xa[i], xb[i]) for i in range(n)]
    res = struct.pack(f"<{n}Q", *out)
    return res if wide else res + b"\x00" * 16


def ref_vmaskmovdqu(src: bytes, mask: bytes, base: bytes) -> bytes:
    out = bytearray(base)
    for i in range(16):
        if mask[i] & 0x80:
            out[i] = src[i]
    return bytes(out)


def reference(name: str, a: bytes, b: bytes, altered: bool = False) -> bytes:
    """Expected 32-byte output region; unwritten bytes keep the FILL pattern."""
    out = bytearray(FILL)
    if name == "op_vaddsubps_xmm_reg":
        src1, src2 = (b, a) if altered else (a, b)
        out[:] = ref_vaddsubps(src1, src2, False)
    elif name == "op_vaddsubps_xmm_mem":
        out[:] = ref_vaddsubps(a, b, False)
    elif name == "op_vaddsubps_xmm_mem_plus1":
        out[:] = ref_vaddsubps(a, b[1:17], False)
    elif name == "op_vaddsubps_ymm_reg":
        src1, src2 = (b, a) if altered else (a, b)
        out[:] = ref_vaddsubps(src1, src2, True)
    elif name == "op_vaddsubps_ymm_mem":
        out[:] = ref_vaddsubps(a, b, True)
    elif name == "op_vaddsubps_ymm_mem_plus1":
        # b is 32B payload; +1 reads b[1:32] + GUARD_POST[0:1]
        out[:] = ref_vaddsubps(a, b[1:32] + GUARD_POST[:1], True)
    elif name == "op_vaddsubps_self":
        out[:] = ref_vaddsubps(a, a, True)
    elif name == "op_vaddsubpd_xmm_reg":
        src1, src2 = (b, a) if altered else (a, b)
        out[:] = ref_vaddsubpd(src1, src2, False)
    elif name == "op_vaddsubpd_xmm_mem":
        out[:] = ref_vaddsubpd(a, b, False)
    elif name == "op_vaddsubpd_xmm_mem_plus1":
        out[:] = ref_vaddsubpd(a, b[1:17], False)
    elif name == "op_vaddsubpd_ymm_reg":
        out[:] = ref_vaddsubpd(a, b, True)
    elif name == "op_vaddsubpd_ymm_mem":
        out[:] = ref_vaddsubpd(a, b, True)
    elif name == "op_vaddsubpd_ymm_mem_plus1":
        out[:] = ref_vaddsubpd(a, b[1:32] + GUARD_POST[:1], True)
    elif name == "op_vmovq_xmm_xmm":
        out[0:8] = b[0:8]
        out[8:32] = b"\x00" * 24
    elif name == "op_vmovq_xmm_m64":
        off = 9 if altered else 1
        out[0:8] = b[off : off + 8]
        out[8:32] = b"\x00" * 24
    elif name == "op_vmovq_m64_xmm":
        out[9:17] = a[0:8]
    elif name == "op_vmovq_xmm_r64":
        out[0:8] = b[0:8]
        out[8:32] = b"\x00" * 24
    elif name == "op_vmovq_r64_xmm":
        out[8:16] = a[0:8]
    elif name == "op_vmaskmovdqu":
        src, mask = (b[:16], a[:16]) if altered else (a[:16], b[:16])
        out[:16] = ref_vmaskmovdqu(src, mask, FILL[:16])
    elif name == "op_pipeline":
        ymm2 = ref_vaddsubps(a, b, True)
        ymm2_z = ymm2[:16] + b"\x00" * 16
        ymm0_z = a[:16] + b"\x00" * 16
        ymm3 = ref_vaddsubpd(ymm2_z, ymm0_z, True)
        xmm4 = b[16:24] + b"\x00" * 8
        out[:] = ref_vmaskmovdqu(xmm4, b[:16], ymm3[:16]) + ymm3[16:32]
    else:
        raise ValueError(f"unknown export {name}")
    return bytes(out)


# --- Test vectors ---

def _pk32(*vals):
    return struct.pack(
        f"<{len(vals)}I",
        *(v if isinstance(v, int) else struct.unpack("<I", struct.pack("<f", v))[0] for v in vals),
    )


def _pk64(*vals):
    return struct.pack(
        f"<{len(vals)}Q",
        *(v if isinstance(v, int) else struct.unpack("<Q", struct.pack("<d", v))[0] for v in vals),
    )


def f32_pairs():
    qnan_p, qnan_n = 0x7FC01234, 0xFFC05678
    snan_p, snan_n = 0x7F800042, 0xFFA00099
    sub_p, sub_n = 0x00400001, 0x80400001
    min_norm = 0x00800000
    max_fin = 0x7F7FFFFF
    pos_z, neg_z = 0x00000000, 0x80000000
    pos_inf, neg_inf = 0x7F800000, 0xFF800000

    pairs = [
        # Finite values, rounding ties, normal->subnormal & subnormal->normal across all 8 lanes
        (_pk32(1.5, -2.25, 1.0, 2.0**-24, 3.5, 0.125, -1.0, -(2.0**-24)),
         _pk32(4.25, 0.75, min_norm, sub_n, -7.5, 2.5, sub_p, sub_p)),
        # Signed zeros in all 4 combinations on even (sub) and odd (add) lanes
        (_pk32(pos_z, pos_z, neg_z, neg_z, pos_z, neg_z, neg_z, pos_z),
         _pk32(pos_z, neg_z, pos_z, neg_z, neg_z, pos_z, neg_z, pos_z)),
        # Infinities, invalid ops (inf - inf, inf + (-inf)), and overflow
        (_pk32(pos_inf, pos_inf, neg_inf, neg_inf, pos_inf, neg_inf, max_fin, max_fin),
         _pk32(pos_inf, neg_inf, neg_inf, pos_inf, neg_inf, pos_inf, max_fin | 0x80000000, max_fin)),
        # NaN precedence (src1 NaN wins over src2 NaN, sNaN gets quieted)
        (_pk32(qnan_p, snan_p, 1.0, 2.0, qnan_n, snan_n, snan_p, 3.0),
         _pk32(snan_n, qnan_n, qnan_p, snan_p, snan_p, qnan_p, 4.0, snan_n)),
        # Unaligned +1 byte-shift checks with NaN/Inf/subnormal boundaries
        (_pk32(snan_p, sub_p, pos_inf, neg_z, qnan_n, max_fin, 1.5, -1.5),
         b"\xAA" + _pk32(qnan_n, sub_n, pos_inf, pos_z, snan_p, max_fin, 2.25)[:28] + b"\x55\x33\x11"),
    ]
    rng = random.Random(0xA7F901)
    for _ in range(8):
        pairs.append((rng.randbytes(32), rng.randbytes(32)))
    return pairs


def f64_pairs():
    qnan_p, qnan_n = 0x7FF8000012345678, 0xFFF8000087654321
    snan_p, snan_n = 0x7FF0000000000042, 0xFFF4000000000099
    sub_p, sub_n = 0x0008000000000001, 0x8008000000000001
    min_norm = 0x0010000000000000
    max_fin = 0x7FEFFFFFFFFFFFFF
    pos_z, neg_z = 0x0000000000000000, 0x8000000000000000
    pos_inf, neg_inf = 0x7FF0000000000000, 0xFFF0000000000000

    pairs = [
        (_pk64(1.5, 2.0**-53, -3.5, -(2.0**-53)),
         _pk64(min_norm, sub_n, sub_p, sub_p)),
        (_pk64(pos_z, neg_z, neg_z, pos_z),
         _pk64(neg_z, neg_z, pos_z, pos_z)),
        (_pk64(pos_inf, pos_inf, neg_inf, max_fin),
         _pk64(pos_inf, neg_inf, neg_inf, max_fin)),
        (_pk64(qnan_p, snan_p, 1.0, 2.0),
         _pk64(snan_n, qnan_n, qnan_p, snan_n)),
        (_pk64(snan_p, sub_p, pos_inf, neg_z),
         b"\xAA" + _pk64(qnan_n, sub_n, pos_inf)[:24] + b"\x55\x33\x11\x77\x99\xBB\xDD"),
    ]
    rng = random.Random(0xA7F902)
    for _ in range(8):
        pairs.append((rng.randbytes(32), rng.randbytes(32)))
    return pairs


def move_pairs():
    pairs = [
        (bytes(range(0x10, 0x30)), bytes(range(0x80, 0xA0))),
        (b"\xFF" * 32, b"\x00" * 32),
        (bytes((0x17 * i + 3) & 0xFF for i in range(32)),
         bytes((0x2B * i + 7) & 0xFF for i in range(32))),
    ]
    rng = random.Random(0xA7F903)
    for _ in range(6):
        pairs.append((rng.randbytes(32), rng.randbytes(32)))
    return pairs


def maskmov_pairs():
    src = bytes(range(0x10, 0x30))
    masks = [
        b"\x00" * 32,
        b"\x7F" * 32,
        b"\x80" * 32,
        b"\xFF" * 32,
        bytes((0x7F if i % 2 == 0 else 0x80) for i in range(32)),
        bytes((0x81 if i % 2 == 0 else 0x01) for i in range(32)),
    ]
    for lane in range(16):
        m = bytearray(b"\x7F" * 32)
        m[lane] = 0x80
        masks.append(bytes(m))
    rng = random.Random(0xA7F904)
    pairs = [(src, m) for m in masks]
    for _ in range(8):
        pairs.append((rng.randbytes(32), rng.randbytes(32)))
    return pairs


def inputs_for(name: str):
    if "vaddsubps" in name:
        return f32_pairs()
    if "vaddsubpd" in name or name == "op_pipeline":
        return f64_pairs()
    if name == "op_vmaskmovdqu":
        return maskmov_pairs()
    return move_pairs()


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
        raise AssertionError(
            f"{label} {name} case {idx}: got {got.hex()} != expected {want.hex()}"
        )


def bind_exports(dll_path: Path, prefix: str = "", names=EXPORTS):
    lib = ctypes.CDLL(str(dll_path.resolve()))
    funcs = {}
    for name in names:
        fn = getattr(lib, prefix + name)
        fn.argtypes = [ctypes.c_uint64, ctypes.c_uint64, ctypes.c_uint64]
        fn.restype = None
        funcs[name] = fn
    return lib, funcs


def check_discarded_read(native_path: Path, lifted_path: Path) -> None:
    payload = bytes(range(32))
    for name in ("op_discarded_read", "op_discarded_read64"):
        for label, dll, prefix in (("native", native_path, ""), ("lifted", lifted_path, "lifted_")):
            _, fns = bind_exports(dll, prefix, (name,))
            fn = fns[name]
            source, ptr, _, _, _ = alloc_aligned_buffer(payload)
            for readable in (True, False):
                result, result_ptr, pre, off, post = alloc_aligned_buffer(FILL)
                try:
                    fn(ptr, ptr if readable else 0, result_ptr)
                except OSError as error:
                    assert not readable and "access violation reading" in str(error).lower(), (name, label, error)
                else:
                    assert readable, f"{label} {name} discarded a faulting read"
                expected = payload[:16] + (payload[:16] if readable else FILL[16:])
                assert_equal_output(
                    label, name, readable, check_guards_and_read(result, pre, off, post, label), expected
                )


def check_differential(native_path: Path, lifted_path: Path, altered_path: Path) -> None:
    lifted_lib, lifted = bind_exports(lifted_path, "lifted_")
    lifted_lib.host_has_avx.restype = ctypes.c_uint32
    if not lifted_lib.host_has_avx():
        print("host lacks AVX/OSXSAVE; skipping native differential check")
        raise SystemExit(77)

    check_discarded_read(native_path, lifted_path)

    _, native = bind_exports(native_path)
    _, altered = bind_exports(altered_path, "lifted_")

    total = 0
    for name in EXPORTS:
        for idx, (a, b) in enumerate(inputs_for(name)):
            want = reference(name, a, b)
            got_n = invoke(native[name], a, b)
            got_l = invoke(lifted[name], a, b)
            assert_equal_output("native", name, idx, got_n, want)
            assert_equal_output("lifted", name, idx, got_l, want)
            total += 1

    # Altered-op negative controls.
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

    # Output mutation negative control.
    sample_a, sample_b = f64_pairs()[0]
    expected = reference("op_pipeline", sample_a, sample_b)
    mutated = bytearray(expected)
    mutated[5] ^= 0x01
    try:
        assert_equal_output("mutation", "op_pipeline", 0, bytes(mutated), expected)
    except AssertionError:
        pass
    else:
        raise AssertionError("mutated output was not caught by comparator")

    print(
        f"{total} native/lifted/reference AVX FP/move cases across {len(EXPORTS)} exports matched "
        f"bit-for-bit; ALTER_OP diverged on {diverged}; dead-read and output mutation controls passed"
    )


# --- Alternate-encoding acceptance & translator rejection controls ---

def encode_seq(*instructions) -> bytes:
    enc = Encoder(64)
    ip = 0x1000
    for ins in instructions:
        ip += enc.encode(ins, ip)
    return enc.take_buffer()


def check_alt_encodings_and_rejections(original_path: Path) -> None:
    ld_xmm0 = Instruction.create_reg_mem(Code.VEX_VMOVUPS_XMM_XMMM128, R.XMM0, MemoryOperand(R.RCX))
    ld_xmm1 = Instruction.create_reg_mem(Code.VEX_VMOVUPS_XMM_XMMM128, R.XMM1, MemoryOperand(R.RDX))
    ld_ymm4 = Instruction.create_reg_mem(Code.VEX_VMOVUPS_YMM_YMMM256, R.YMM4, MemoryOperand(R.RCX))
    ld_ymm5 = Instruction.create_reg_mem(Code.VEX_VMOVDQU_YMM_YMMM256, R.YMM5, MemoryOperand(R.RDX, displ=3, displ_size=1))
    st_xmm0 = Instruction.create_mem_reg(Code.VEX_VMOVUPS_XMMM128_XMM, MemoryOperand(R.R8), R.XMM0)
    st_ymm4 = Instruction.create_mem_reg(Code.VEX_VMOVUPS_YMMM256_YMM, MemoryOperand(R.R8), R.YMM4)
    ret_ins = Instruction.create(Code.RETNQ)

    # Alternate encodings not emitted directly by MASM:
    # F3 0F 7E vmovq xmm, m64; 66 0F D6 vmovq xmm, xmm and m64, xmm;
    # store-form reg-reg vmovups/vmovaps/vmovdqu/vmovdqa; r8 reads; neg disp; r9 rdi save.
    alt_accept = [
        ("vmovq_f3_m64", (
            Instruction.create_reg_mem(Code.VEX_VMOVQ_XMM_XMMM64, R.XMM0, MemoryOperand(R.RDX, displ=8, displ_size=1)),
            st_xmm0, ret_ins)),
        ("vmovq_d6_reg", (
            ld_xmm1, Instruction.create_reg_reg(Code.VEX_VMOVQ_XMMM64_XMM, R.XMM0, R.XMM1),
            st_xmm0, ret_ins)),
        ("vmovq_d6_m64", (
            ld_xmm0, Instruction.create_mem_reg(Code.VEX_VMOVQ_XMMM64_XMM, MemoryOperand(R.R8, displ=16, displ_size=1), R.XMM0),
            ret_ins)),
        ("vmovq_gpr_r10_r8", (
            Instruction.create_reg_reg(Code.VEX_VMOVQ_XMM_RM64, R.XMM0, R.R8),
            Instruction.create_reg_reg(Code.VEX_VMOVQ_RM64_XMM, R.R10, R.XMM0),
            Instruction.create_reg_reg(Code.VEX_VMOVQ_XMM_RM64, R.XMM2, R.R10),
            Instruction.create_mem_reg(Code.VEX_VMOVQ_RM64_XMM, MemoryOperand(R.R8), R.XMM2),
            ret_ins)),
        ("vaddsubps_ymm4_ymm5_neg_disp", (
            ld_ymm4, ld_ymm5,
            Instruction.create_reg_reg_mem(
                Code.VEX_VADDSUBPS_YMM_YMM_YMMM256, R.YMM4, R.YMM5, MemoryOperand(R.R8, displ=-32, displ_size=1)),
            st_ymm4, ret_ins)),
        ("vmov_alt_reg_reg", (
            ld_ymm4,
            Instruction.create_reg_reg(Code.VEX_VMOVUPS_XMMM128_XMM, R.XMM0, R.XMM4),
            Instruction.create_reg_reg(Code.VEX_VMOVAPS_YMMM256_YMM, R.YMM1, R.YMM4),
            Instruction.create_reg_reg(Code.VEX_VMOVDQU_XMMM128_XMM, R.XMM2, R.XMM0),
            Instruction.create_reg_reg(Code.VEX_VMOVDQA_YMMM256_YMM, R.YMM3, R.YMM1),
            Instruction.create_mem_reg(Code.VEX_VMOVDQU_YMMM256_YMM, MemoryOperand(R.R8), R.YMM3),
            ret_ins)),
        ("vmaskmovdqu_r9_save", (
            ld_xmm0, ld_xmm1,
            Instruction.create_reg_reg(Code.MOV_R64_RM64, R.R9, R.RDI),
            Instruction.create_reg_reg(Code.MOV_R64_RM64, R.RDI, R.R8),
            Instruction.create_vmaskmovdqu(64, R.XMM0, R.XMM1),
            Instruction.create_reg_reg(Code.MOV_R64_RM64, R.RDI, R.R9),
            ret_ins)),
    ]
    alt_expected = {
        "vmovq_f3_m64": "ymm0 = {{load64((rdx + 0x8ull)), 0ull, 0ull, 0ull}};",
        "vmovq_d6_reg": "ymm0 = {{ymm1.q[0], 0ull, 0ull, 0ull}};",
        "vmovq_d6_m64": "store64((r8 + 0x10ull), ymm0.q[0]);",
        "vmovq_gpr_r10_r8": "r10 = ymm0.q[0];",
        "vaddsubps_ymm4_ymm5_neg_disp": "op_vaddsubps(ymm5, load256((r8 + 0xffffffffffffffe0ull)), true);",
        "vmov_alt_reg_reg": "ymm0 = copy128(ymm4);",
        "vmaskmovdqu_r9_save": "op_vmaskmovdqu(r8, ymm0, ymm1);",
    }
    for label, seq in alt_accept:
        raw = encode_seq(*seq)
        decoded = list(Decoder(64, raw, ip=0x1000))
        assert len(decoded) == len(seq) and not any(ins.is_invalid for ins in decoded), label
        src, count = lift_code(label, 0x1000, raw)
        assert f"lifted_{label}" in src and count == len(seq), (label, count)
        if alt_expected[label] not in src:
            raise AssertionError(f"{label}: expected {alt_expected[label]!r} in generated C++")

    evex_vmovq = Instruction.create_reg_reg(Code.EVEX_VMOVQ_XMM_RM64, R.XMM0, R.RAX)
    evex_vaddps = Instruction.create_reg_reg_reg(Code.EVEX_VADDPS_XMM_K1Z_XMM_XMMM128B32, R.XMM0, R.XMM1, R.XMM2)
    evex_vaddps.op_mask = R.K1
    seg_load = Instruction.create_reg_mem(Code.VEX_VMOVUPS_XMM_XMMM128, R.XMM0, MemoryOperand(R.RCX))
    seg_load.segment_prefix = R.GS

    unit_cases = [
        # Legacy SSE rejections
        ("legacy_addsubps", encode_seq(ld_xmm0, ld_xmm1, Instruction.create_reg_reg(
            Code.ADDSUBPS_XMM_XMMM128, R.XMM0, R.XMM1), ret_ins), "unsupported legacy SSE encoding"),
        ("legacy_addsubpd", encode_seq(ld_xmm0, ld_xmm1, Instruction.create_reg_reg(
            Code.ADDSUBPD_XMM_XMMM128, R.XMM0, R.XMM1), ret_ins), "unsupported legacy SSE encoding"),
        ("legacy_movq_xmm", encode_seq(ld_xmm1, Instruction.create_reg_reg(
            Code.MOVQ_XMM_XMMM64, R.XMM0, R.XMM1), ret_ins), "unsupported legacy SSE encoding"),
        ("legacy_movq_r64", encode_seq(ld_xmm0, Instruction.create_reg_reg(
            Code.MOVQ_RM64_XMM, R.RAX, R.XMM0), ret_ins), "unsupported legacy SSE encoding"),
        ("legacy_movq_mm", encode_seq(Instruction.create_reg_mem(
            Code.MOVQ_MM_MMM64, R.MM0, MemoryOperand(R.RCX)), ret_ins), "unsupported legacy SSE encoding"),
        ("legacy_maskmovdqu", encode_seq(ld_xmm0, ld_xmm1, Instruction.create_maskmovdqu(
            64, R.XMM0, R.XMM1), ret_ins), "unsupported legacy SSE encoding"),
        # EVEX rejections
        ("evex_vmovq", encode_seq(Instruction.create_reg_mem(
            Code.MOV_R64_RM64, R.RAX, MemoryOperand(R.RCX)), evex_vmovq, ret_ins), "unsupported EVEX instruction"),
        ("evex_vaddps", encode_seq(ld_xmm0, ld_xmm1, Instruction.create_reg_reg(
            Code.VEX_VMOVUPS_XMM_XMMM128, R.XMM2, R.XMM0), evex_vaddps, ret_ins), "unsupported EVEX instruction"),
        # Nonvolatile XMM6..15 / YMM6..15 and GPRs
        ("nonvolatile_xmm6", encode_seq(Instruction.create_reg_mem(
            Code.VEX_VMOVUPS_XMM_XMMM128, R.XMM6, MemoryOperand(R.RCX)), ret_ins), "nonvolatile vector register"),
        ("nonvolatile_ymm15", encode_seq(ld_ymm4, Instruction.create_reg_reg_reg(
            Code.VEX_VADDSUBPS_YMM_YMM_YMMM256, R.YMM15, R.YMM4, R.YMM4), ret_ins), "nonvolatile vector register"),
        ("nonvolatile_rbx_vmovq", encode_seq(ld_xmm0, Instruction.create_reg_reg(
            Code.VEX_VMOVQ_RM64_XMM, R.RBX, R.XMM0), ret_ins), "nonvolatile GPR"),
        ("nonvolatile_rdi_vmovq", encode_seq(ld_xmm0, Instruction.create_reg_reg(
            Code.VEX_VMOVQ_RM64_XMM, R.RDI, R.XMM0), ret_ins), "nonvolatile GPR"),
        # RDI save/restore and vmaskmovdqu policy
        ("vmaskmovdqu_no_r8_rdi", encode_seq(ld_xmm0, ld_xmm1, Instruction.create_vmaskmovdqu(
            64, R.XMM0, R.XMM1), ret_ins), "vmaskmovdqu requires r8-rooted rdi"),
        ("vmaskmovdqu_unsaved_rdi", encode_seq(ld_xmm0, ld_xmm1, Instruction.create_reg_reg(
            Code.MOV_R64_RM64, R.RDI, R.R8), Instruction.create_vmaskmovdqu(
            64, R.XMM0, R.XMM1), ret_ins), "rdi modified without saving"),
        ("vmaskmovdqu_unrestored_rdi", encode_seq(ld_xmm0, ld_xmm1,
            Instruction.create_reg_reg(Code.MOV_R64_RM64, R.R10, R.RDI),
            Instruction.create_reg_reg(Code.MOV_R64_RM64, R.RDI, R.R8),
            Instruction.create_vmaskmovdqu(64, R.XMM0, R.XMM1), ret_ins), "unrestored nonvolatile GPR rdi"),
        ("vmaskmovdqu_non_r8_rdi", encode_seq(ld_xmm0, ld_xmm1,
            Instruction.create_reg_reg(Code.MOV_R64_RM64, R.R10, R.RDI),
            Instruction.create_reg_reg(Code.MOV_R64_RM64, R.RDI, R.RCX),
            ret_ins), "non-r8 or unsaved write to nonvolatile GPR rdi"),
        ("vmaskmovdqu_clobbered_save_slot", encode_seq(ld_xmm0, ld_xmm1,
            Instruction.create_reg_reg(Code.MOV_R64_RM64, R.R10, R.RDI),
            Instruction.create_reg_reg(Code.MOV_R64_RM64, R.RDI, R.R8),
            Instruction.create_reg_reg(Code.VEX_VMOVQ_RM64_XMM, R.R10, R.XMM0),
            Instruction.create_reg_reg(Code.MOV_R64_RM64, R.RDI, R.R10),
            ret_ins), "non-r8 or unsaved write to nonvolatile GPR rdi"),
        ("vmaskmovdqu_edi_override", encode_seq(ld_xmm0, ld_xmm1,
            Instruction.create_reg_reg(Code.MOV_R64_RM64, R.R10, R.RDI),
            Instruction.create_reg_reg(Code.MOV_R64_RM64, R.RDI, R.R8))
            + bytes.fromhex("67c5f9f7c1")
            + encode_seq(Instruction.create_reg_reg(Code.MOV_R64_RM64, R.RDI, R.R10), ret_ins),
            "unsupported vmaskmovdqu target"),
        # Store target / write to r8 / addressing / alignment
        ("store_outside_r8_vmovq", encode_seq(ld_xmm0, Instruction.create_mem_reg(
            Code.VEX_VMOVQ_RM64_XMM, MemoryOperand(R.RCX), R.XMM0), ret_ins), "non-r8 store memory operand"),
        ("store_outside_r8_vmovups", encode_seq(ld_xmm0, Instruction.create_mem_reg(
            Code.VEX_VMOVUPS_XMMM128_XMM, MemoryOperand(R.RDX), R.XMM0), ret_ins), "non-r8 store memory operand"),
        ("write_r8_vmovq", encode_seq(ld_xmm0, Instruction.create_reg_reg(
            Code.VEX_VMOVQ_RM64_XMM, R.R8, R.XMM0), ret_ins), "unsupported write to output buffer pointer r8"),
        ("non_arg_base_rax", encode_seq(Instruction.create_reg_mem(
            Code.VEX_VMOVUPS_XMM_XMMM128, R.XMM0, MemoryOperand(R.RAX)), ret_ins), "unsupported memory base"),
        ("nonvolatile_base_rbx", encode_seq(Instruction.create_reg_mem(
            Code.VEX_VMOVUPS_XMM_XMMM128, R.XMM0, MemoryOperand(R.RBX)), ret_ins), "nonvolatile GPR base"),
        ("clobbered_rcx_read", encode_seq(
            Instruction.create_reg_mem(Code.MOV_R64_RM64, R.RCX, MemoryOperand(R.RDX)),
            ld_xmm0, ret_ins), "memory operand uses clobbered pointer rcx"),
        ("unaligned_vmovaps", encode_seq(Instruction.create_reg_mem(
            Code.VEX_VMOVAPS_XMM_XMMM128, R.XMM0, MemoryOperand(R.RCX, displ=1, displ_size=1)), ret_ins),
            "unaligned 16-byte memory operand"),
        ("rip_rel_mem", encode_seq(ld_xmm0, Instruction.create_reg_reg_mem(
            Code.VEX_VADDSUBPS_XMM_XMM_XMMM128, R.XMM0, R.XMM0, MemoryOperand(R.RIP, displ=0x1020, displ_size=1)),
            ret_ins), "unsupported memory operand"),
        ("indexed_mem", encode_seq(Instruction.create_reg_mem(
            Code.VEX_VMOVUPS_XMM_XMMM128, R.XMM0, MemoryOperand(R.RCX, R.RDX, 4)), ret_ins), "unsupported memory operand"),
        # Prefixes, out-of-scope, undefined, stream boundary
        ("segment_prefix", encode_seq(seg_load, ret_ins), "unsupported instruction prefix"),
        ("lock_prefix", bytes.fromhex("f00fb109") + encode_seq(ret_ins), "unsupported instruction prefix"),
        ("rep_prefix", bytes.fromhex("f3a4") + encode_seq(ret_ins), "unsupported instruction prefix"),
        ("out_of_scope_vaddps", encode_seq(ld_xmm0, ld_xmm1, Instruction.create_reg_reg_reg(
            Code.VEX_VADDPS_XMM_XMM_XMMM128, R.XMM0, R.XMM0, R.XMM1), ret_ins), "unsupported instruction"),
        ("undef_xmm2", encode_seq(ld_xmm0, Instruction.create_reg_reg_reg(
            Code.VEX_VADDSUBPS_XMM_XMM_XMMM128, R.XMM0, R.XMM0, R.XMM2), ret_ins), "undefined vector register ymm2"),
        ("undef_rax", encode_seq(Instruction.create_reg_reg(
            Code.VEX_VMOVQ_XMM_RM64, R.XMM0, R.RAX), ret_ins), "undefined GPR rax"),
        ("missing_ret", encode_seq(ld_xmm0), "missing terminal ret"),
        ("trailing_after_ret", encode_seq(ld_xmm0, ret_ins, ld_xmm1), "unreachable instruction after ret"),
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
        ("pe_legacy_addsubps", unit_map["legacy_addsubps"], "unsupported legacy SSE encoding"),
        ("pe_legacy_maskmovdqu", unit_map["legacy_maskmovdqu"], "unsupported legacy SSE encoding"),
        ("pe_evex_vmovq", unit_map["evex_vmovq"], "unsupported EVEX instruction"),
        ("pe_nonvolatile_ymm15", unit_map["nonvolatile_ymm15"], "nonvolatile vector register"),
        ("pe_unrestored_rdi", unit_map["vmaskmovdqu_unrestored_rdi"], "unrestored nonvolatile GPR rdi"),
        ("pe_store_outside_r8", unit_map["store_outside_r8_vmovq"], "non-r8 store memory operand"),
        ("pe_rip_rel", unit_map["rip_rel_mem"], "unsupported memory operand"),
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
    orig, lifted, alt = (Path(p) for p in sys.argv[1:4])
    check_differential(orig, lifted, alt)
    check_alt_encodings_and_rejections(orig)
