"""Differential checks and a rejection control for a fourth integer argument in R9."""

import ctypes
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

import pefile
from iced_x86 import Decoder, Mnemonic, Register

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from cpu_switch_aot import translate
from cpu_leaf_aot import export_rva
from direct_check import GUARDS, MASK, SENTINELS, Word, input_pairs

NAMES = ("r9_mix", "r9_loop", "no_r9", "r9_scratch")
# Exports that never read the incoming R9: the fourth argument must not change any of their results.
CONTROLS = ("no_r9", "r9_scratch")
# R9D = 0 with and without upper bits, loop counts 1 to 64 (one under a set sign bit), counts above
# 64, and all ones.
FOURTHS = (0, 1, 2, 64, 65, (1 << 32) - 1, 1 << 32, 1 << 63, (1 << 63) | 3, MASK)


def register_probe4(probe_path):
    probe4 = ctypes.CDLL(probe_path).probe4
    probe4.argtypes = [ctypes.c_void_p, Word, Word, ctypes.POINTER(Word), Word, ctypes.POINTER(Word)]
    probe4.restype = Word
    return probe4


def observe4(probe4, fn, x, y, z):
    """Return value, guarded trace and sampled RBX/RSI after fn(x, y, trace, z)."""
    trace = (Word * 5)(GUARDS[0], MASK, MASK, MASK, GUARDS[1])
    regs = (Word * 2)()
    output = ctypes.cast(ctypes.byref(trace, ctypes.sizeof(Word)), ctypes.POINTER(Word))
    result = probe4(fn, x, y, output, z, regs)
    return result, tuple(trace), tuple(regs)


def reference(name, x, y, z):
    """RAX and the guarded trace after name(x, y, trace, z); an untouched word keeps the fill."""
    trace = [MASK] * 3
    if name == "r9_mix":
        rax, trace[0] = (x + 2 * z - y) & MASK, z
    elif name == "r9_loop":
        count = z & 0xffffffff
        if 1 <= count <= 64:
            rax, trace[0] = (x + count * y) & MASK, 0
        else:
            rax, trace[0] = x, z
    elif name == "no_r9":
        rax = trace[0] = (x - y) & MASK
    elif name == "r9_scratch":
        low = x & 0xff
        rax, trace[0] = (low + y) & MASK, (y - low) & MASK
    return rax, (GUARDS[0], *trace, GUARDS[1])


def check(probe_path, original_path, lifted_path):
    probe4 = register_probe4(probe_path)
    # probe4 samples RBX and RSI through its sixth argument; clobber_control zeroes both.
    sampled = observe4(probe4, ctypes.CDLL(probe_path).clobber_control, 1, 2, 3)[2]
    if sampled != (0, 0):
        raise AssertionError(f"probe4 missed the register clobber: {sampled}")
    print("control clobber_control through probe4: RBX and RSI sampled as 0 and 0")
    _, functions = translate(original_path, list(NAMES))
    widths = [function.return_width for function in functions]
    if widths != [8] * len(NAMES):
        raise AssertionError(f"return widths {widths}")
    native, lifted = ctypes.CDLL(original_path), ctypes.CDLL(lifted_path)
    inputs = input_pairs()
    for name in NAMES:
        varied = 0
        for x, y in inputs:
            seen = set()
            for z in FOURTHS:
                want = (*reference(name, x, y, z), SENTINELS)
                for label, function in (("native", getattr(native, name)), ("translated", getattr(lifted, "lifted_" + name))):
                    got = observe4(probe4, function, x, y, z)
                    if got != want:
                        raise AssertionError(f"{label} {name}({x:#x}, {y:#x}, trace, {z:#x}) = {got}, expected {want}")
                    seen.add(got)
            varied += len(seen) > 1
        if name in CONTROLS:
            if varied:
                raise AssertionError(f"{name}: the fourth argument changed the result for {varied} pairs")
            print(f"control {name}: identical results for all {len(FOURTHS)} fourth arguments on each of "
                  f"{len(inputs)} pairs, native and translated")
        else:
            print(f"{name}: the fourth argument changes the result on {varied} of {len(inputs)} pairs")
    print(f"{len(NAMES) * len(inputs) * len(FOURTHS)} calls per side match the reference on return, guarded trace, "
          "RBX and RSI")


def check_rejection(original_path):
    """lea rax, [rcx+r9*2] in r9_mix patched to lea rax, [rcx+r10*2]: R10 is not an argument register."""
    data = Path(original_path).read_bytes()
    with pefile.PE(data=data, fast_load=True) as pe:
        entry = export_rva(pe, "r9_mix")
        lea = Decoder(64, pe.get_data(entry, 0x10), ip=entry).decode()
        offset = pe.get_offset_from_rva(lea.ip)
    patch = bytes.fromhex("4a 8d 04 51")
    replacement = Decoder(64, patch, ip=lea.ip).decode()
    same = lambda i: (i.mnemonic, i.op0_register, i.memory_base, i.memory_index_scale, i.memory_displacement, i.len)
    if (lea.memory_index, replacement.memory_index) != (Register.R9, Register.R10) or lea.mnemonic != Mnemonic.LEA \
            or same(lea) != same(replacement) or len(patch) != lea.len:
        raise AssertionError(f"r9_mix: {lea} and {replacement} differ in more than the index register")
    change = f"{lea} -> {replacement}"
    with TemporaryDirectory() as folder:
        path = Path(folder) / "control.dll"
        damaged = bytearray(data)
        damaged[offset:offset + lea.len] = patch
        path.write_bytes(damaged)
        try:
            translate(path, ["r9_mix"])
        except ValueError as exc:
            if "undefined register r10" not in str(exc):
                raise AssertionError(f"r9_mix ({change}): expected 'undefined register r10', got {exc}") from exc
            print(f"rejected r9_mix ({change}): {exc}")
        else:
            raise AssertionError(f"accepted control r9_mix ({change})")


if __name__ == "__main__":
    check(*sys.argv[1:])
    check_rejection(sys.argv[2])
