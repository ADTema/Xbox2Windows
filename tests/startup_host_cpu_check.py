"""Checks tools/startup/host_cpu.py by running its replacements on the host processor.

Source-built x64 functions are assembled here byte by byte, patched the way the startup debugger
patches a faulting site, and called. Results are compared with a model of the instruction and, on a
processor that has the original instruction (CPUID), with the unpatched function as well.
Exits 77 on a host that is not x86-64.
"""
import ctypes
import os
import platform
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools", "startup"))
import host_cpu  # noqa: E402

M64 = (1 << 64) - 1
WINDOWS = os.name == "nt"
# The functions below take their arguments in rcx and rdx; System V passes them in rdi and rsi.
PROLOGUE = b"" if WINDOWS else b"\x48\x89\xf9\x48\x89\xf2"


class Arena:
    """One block of executable memory: functions and their stubs stay within rel32 reach."""

    def __init__(self, size=1 << 16):
        if WINDOWS:
            k32 = ctypes.WinDLL("kernel32")
            k32.VirtualAlloc.restype = ctypes.c_void_p
            k32.VirtualAlloc.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint32, ctypes.c_uint32]
            self.base = k32.VirtualAlloc(None, size, 0x3000, 0x40)
        else:
            import mmap
            self.map = mmap.mmap(-1, size, prot=mmap.PROT_READ | mmap.PROT_WRITE | mmap.PROT_EXEC)
            self.base = ctypes.addressof(ctypes.c_char.from_buffer(self.map))
        if not self.base:
            raise OSError("no executable memory")
        self.next, self.end = self.base, self.base + size

    def put(self, data):
        at = self.next
        if at + len(data) > self.end:
            raise OSError("arena full")
        ctypes.memmove(at, bytes(data), len(data))
        self.next = at + ((len(data) + 15) & ~15)
        return at

    def write(self, address, data):
        ctypes.memmove(address, bytes(data), len(data))


ARENA = Arena()
CALL = ctypes.CFUNCTYPE(ctypes.c_uint64, ctypes.c_uint64, ctypes.c_uint64)


def build(before, instruction, after, stub=None, patch=True):
    """A function `PROLOGUE before instruction after`; with patch, the instruction is replaced."""
    code = PROLOGUE + before + instruction + after
    start = ARENA.put(code)
    if patch:
        site = start + len(PROLOGUE) + len(before)
        tail = instruction + after
        if stub is None:
            length, stub = host_cpu.stub_for(tail)
        else:
            length = len(instruction)
        stub_address = ARENA.put(b"\xcc" * (len(stub) + 64))
        plan = host_cpu.plan_replacement(tail, site, length, stub, stub_address)
        assert plan, "no replacement plan"
        stub_bytes, site_bytes = plan
        assert len(stub_bytes) <= len(stub) + 64 and len(site_bytes) >= 5
        ARENA.write(stub_address, stub_bytes)
        ARENA.write(site, site_bytes)
    return CALL(start)


def cpuid(leaf):
    # push rbx; mov eax, ecx; xor ecx, ecx; cpuid; shl rcx, 32; mov eax, ebx; or rax, rcx; pop rbx; ret
    f = build(b"", b"", bytes.fromhex("5389c831c90fa248c1e12089d84809c85bc3"), patch=False)
    value = f(leaf, 0)
    return value & 0xFFFFFFFF, value >> 32  # ebx, ecx


def host_features():
    features = set()
    # Leaves 0x80000001 and 0x80000008 exist on every x86-64 processor.
    _, ecx = cpuid(0x80000001)
    if ecx >> 6 & 1:
        features.add("sse4a")
    ebx, _ = cpuid(0x80000008)
    if ebx & 1:
        features.add("clzero")
    return features


# ---- CLZERO -------------------------------------------------------------------------------------
def clzero_case(stub=None, patch=True):
    """True when a patched `clzero` zeroes exactly its line, keeps CF and runs the moved lea."""
    # mov rax, rcx; stc | clzero | lea rax, [rax + 0x40]; jnc bad; ret; bad: xor eax, eax; ret
    f = build(b"\x48\x89\xc8\xf9", host_cpu.CLZERO, bytes.fromhex("488d40407301c331c0c3"), stub, patch)
    raw = ctypes.create_string_buffer(64 * 5)
    base = (ctypes.addressof(raw) + 63) & ~63
    ctypes.memset(base, 0xAA, 64 * 3)
    pointer = base + 64 + 37  # inside the middle line
    result = f(pointer, 0)
    lines = [ctypes.string_at(base + 64 * i, 64) for i in range(3)]
    return result == pointer + 0x40 and lines == [b"\xaa" * 64, b"\0" * 64, b"\xaa" * 64]


def clzero_moves_rip_relative():
    # | clzero | mov rdx, [rip + 3]; mov rax, rdx; ret; <qword>   (the load moves behind the stub)
    value = 0x1122334455667788
    after = bytes.fromhex("488b1504000000") + bytes.fromhex("4889d0c3") + struct.pack("<Q", value)
    f = build(b"\x48\x89\xc8", host_cpu.CLZERO, after)
    raw = ctypes.create_string_buffer(256)
    return f((ctypes.addressof(raw) + 127) & ~63, 0) == value


# ---- INSERTQ / EXTRQ ----------------------------------------------------------------------------
def movq_to_xmm(xmm, gpr):   # movq xmm, r64
    return bytes([0x66, 0x48, 0x0F, 0x6E, 0xC0 | xmm << 3 | gpr])


def movq_from_xmm(xmm):      # movq rax, xmm
    return bytes([0x66, 0x48, 0x0F, 0x7E, 0xC0 | xmm << 3])


def insertq_model(a, b, width, offset):
    mask = (1 << (width or 64)) - 1
    return (a & ~(mask << offset) | (b & mask) << offset) & M64


def extrq_model(a, width, offset):
    return a >> offset & ((1 << (width or 64)) - 1)


def insertq_function(dest, src, width, offset, patch=True, stub=None):
    instruction = bytes([0xF2, 0x0F, 0x78, 0xC0 | dest << 3 | src, width, offset])
    return build(movq_to_xmm(dest, 1) + movq_to_xmm(src, 2), instruction, movq_from_xmm(dest) + b"\xc3", stub, patch)


def extrq_function(dest, width, offset, patch=True):
    instruction = bytes([0x66, 0x0F, 0x78, 0xC0 | dest, width, offset])
    return build(movq_to_xmm(dest, 1), instruction, movq_from_xmm(dest) + b"\xc3", None, patch)


VALUES = [(0x0123456789ABCDEF, 0xFEDCBA9876543210), (M64, 0), (0, M64), (0x8000000000000001, 0x5555AAAA5555AAAA)]
FIELDS = [(16, 16), (1, 0), (1, 63), (8, 56), (63, 1), (32, 0), (0, 0), (5, 11), (48, 16)]


def sse4a_cases(native):
    checked = 0
    for dest, src in ((0, 1), (1, 0), (3, 7), (7, 2), (5, 5)):
        for width, offset in FIELDS:
            patched = insertq_function(dest, src, width, offset)
            original = insertq_function(dest, src, width, offset, patch=False) if native else None
            for a, b in VALUES:
                if dest == src:
                    a = b  # the second load overwrites the first
                expected = insertq_model(a, b, width, offset)
                got = patched(a, b)
                assert got == expected, f"insertq xmm{dest}, xmm{src}, {width}, {offset}: {got:#x}, expected {expected:#x}"
                if original:
                    assert original(a, b) == expected, f"native insertq differs from the model ({width}, {offset})"
                checked += 1
    for dest in (0, 4, 7):
        for width, offset in FIELDS:
            patched = extrq_function(dest, width, offset)
            original = extrq_function(dest, width, offset, patch=False) if native else None
            for a, _ in VALUES:
                expected = extrq_model(a, width, offset)
                got = patched(a, 0)
                assert got == expected, f"extrq xmm{dest}, {width}, {offset}: {got:#x}, expected {expected:#x}"
                if original:
                    assert original(a, 0) == expected, f"native extrq differs from the model ({width}, {offset})"
                checked += 1
    return checked


def insertq_keeps_registers_and_flags():
    # movq xmm0, rcx; movq xmm1, rdx; stc | insertq xmm0, xmm1, 16, 16 | jnc bad; lea rax, [rcx + rdx]; ret; bad: ...
    f = build(movq_to_xmm(0, 1) + movq_to_xmm(1, 2) + b"\xf9", bytes.fromhex("f20f78c11010"),
              bytes.fromhex("7305488d0411c331c0c3"))
    return f(0x1000, 0x234) == 0x1234


# ---- byte rewrites ------------------------------------------------------------------------------
def rewrites():
    import iced_x86

    def one(code):
        decoder = iced_x86.Decoder(64, bytes(code), ip=0x1000)
        return decoder.decode()

    for code in (bytes.fromhex("660fae30"), bytes.fromhex("66410fae31"), bytes.fromhex("660fae742408"),
                 bytes.fromhex("660fae3500100000"), bytes.fromhex("66420fae34c8")):
        before = one(code)
        assert before.mnemonic == iced_x86.Mnemonic.CLWB, code.hex()
        offset, byte = host_cpu.clwb_rewrite(code)
        after = one(code[:offset] + byte + code[offset + 1:])
        assert after.mnemonic == iced_x86.Mnemonic.CLFLUSHOPT and after.len == before.len == len(code), code.hex()
        for field in ("memory_base", "memory_index", "memory_index_scale", "memory_displacement", "memory_segment"):
            assert getattr(after, field) == getattr(before, field), (code.hex(), field)
        # A host without CLFLUSHOPT: one NOP of the same length, for the CLWB and for its rewrite.
        for flush in (code, code[:offset] + byte + code[offset + 1:]):
            nop = host_cpu.flush_nop(flush)
            assert host_cpu.flush_length(flush) == before.len and len(nop) == before.len, flush.hex()
            decoded = one(nop)
            assert decoded.mnemonic == iced_x86.Mnemonic.NOP and decoded.len == len(nop), (flush.hex(), nop.hex())
    # Every addressing form: the length must match the decoder's, or a NOP would cut an instruction.
    lengths = set()
    for rex in (b"", b"\x41", b"\x42", b"\x43"):
        for modrm in range(0xC0):
            if (modrm >> 3) & 7 not in (6, 7):
                continue
            for sib in ((0x24, 0x25, 0xC8, 0xCD) if modrm & 7 == 4 else (0,)):
                code = b"\x66" + rex + b"\x0f\xae" + bytes([modrm]) + (bytes([sib]) if modrm & 7 == 4 else b"") + bytes(8)
                decoded = one(code)
                assert decoded.mnemonic in (iced_x86.Mnemonic.CLWB, iced_x86.Mnemonic.CLFLUSHOPT), code.hex()
                assert host_cpu.flush_length(code) == decoded.len, (code.hex(), decoded.len)
                assert one(host_cpu.flush_nop(code)).len == decoded.len
                lengths.add(decoded.len)
    assert lengths == set(host_cpu.NOPS), sorted(lengths)
    for refused in (bytes.fromhex("0fae3000"), bytes.fromhex("660faef0"), bytes.fromhex("660fae28"),  # /5
                    bytes.fromhex("660fae"), bytes.fromhex("660fae742408")[:5]):                      # cut short
        assert host_cpu.flush_length(refused) is None and host_cpu.flush_nop(refused) is None, refused.hex()
    for refused in (bytes.fromhex("660fae38"),      # clflushopt already
                    bytes.fromhex("0fae3000"),      # xsaveopt: no 66 prefix
                    bytes.fromhex("660faef0"),      # register form
                    bytes.fromhex("660faf30")):     # another opcode
        assert host_cpu.clwb_rewrite(refused) is None, refused.hex()

    monitorx, mwaitx = host_cpu.wait_rewrite(b"\x0f\x01\xfa"), host_cpu.wait_rewrite(b"\x0f\x01\xfb")
    assert len(monitorx) == 3 and one(monitorx).mnemonic == iced_x86.Mnemonic.NOP and one(monitorx).len == 3
    first = one(mwaitx)
    assert len(mwaitx) == 3 and first.mnemonic == iced_x86.Mnemonic.PAUSE and first.len == 2 and mwaitx[2] == 0x90
    assert host_cpu.wait_rewrite(b"\x0f\x01\xf9") is None and host_cpu.wait_rewrite(host_cpu.CLZERO) is None

    # Encodings the stubs do not cover are refused, not approximated.
    assert host_cpu.sse4a_stub(bytes.fromhex("f20f78c12020")) is not None  # 32 bits at 32 is defined
    for refused in (bytes.fromhex("f20f78c13030"),               # idx + len > 64
                    bytes.fromhex("f20f78011010"),               # not a register operand
                    bytes.fromhex("660f78c81010"),               # extrq with /1
                    bytes.fromhex("f2410f78c110"),               # REX prefix (xmm8-15)
                    bytes.fromhex("f20f79c1c3c3")):              # register-count form
        assert host_cpu.sse4a_stub(refused) is None and host_cpu.stub_for(refused) is None, refused.hex()


def main():
    if platform.machine().lower() not in ("x86_64", "amd64"):
        print("startup_host_cpu: SKIP, host is not x86-64")
        return 77
    features = host_features()
    rewrites()

    assert clzero_case(), "clzero stub"
    assert clzero_moves_rip_relative(), "an instruction moved behind the clzero stub lost its rip-relative operand"
    if "clzero" in features:
        assert clzero_case(patch=False), "native clzero differs from the check"
    # Negative controls: a stub that leaves the last quadword, and one that zeroes the next line too.
    short = host_cpu.CLZERO_STUB.replace(bytes.fromhex("48c7403800000000"), b"")
    long = host_cpu.CLZERO_STUB[:-2] + bytes.fromhex("48c7404000000000") + host_cpu.CLZERO_STUB[-2:]
    assert short != host_cpu.CLZERO_STUB and not clzero_case(short), "a 56-byte clzero stub passed"
    assert not clzero_case(long), "a 72-byte clzero stub passed"

    checked = sse4a_cases("sse4a" in features)
    assert insertq_keeps_registers_and_flags(), "insertq stub changed rcx, rdx or CF"
    # Negative control: the stub for a field 8 bits further along must not pass as this one.
    wrong = host_cpu.sse4a_stub(bytes.fromhex("f20f78c11018"))
    mutant = insertq_function(0, 1, 16, 16, stub=wrong)
    a, b = VALUES[0]
    assert mutant(a, b) != insertq_model(a, b, 16, 16), "a stub for another bit offset passed"

    native = ", ".join(sorted(features)) or "none"
    print(f"startup_host_cpu: PASS ({checked} insertq/extrq results, clzero with two moved-instruction forms, "
          f"5 clwb and 2 wait rewrites, clwb/clflushopt NOPs for every addressing form; native comparison: {native})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
