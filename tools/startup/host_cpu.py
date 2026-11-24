"""Rewrites for x64 instructions a console executable uses and the host CPU may lack.

The startup debugger (debug_launch.py, X2W_HOST_CPU=1) calls these when the main image raises an
illegal-instruction exception. Each site is rewritten once, in the running process only:

- CLWB m8 (66 [REX] 0F AE /6) becomes CLFLUSHOPT m8 (/7): same bytes apart from one ModRM bit.
  Both write the line back; CLFLUSHOPT also evicts it, which no program can observe.
- MONITORX (0F 01 FA) becomes a 3-byte NOP and MWAITX (0F 01 FB) becomes PAUSE; NOP. MWAITX may
  return at any time, so a caller already has to re-check its condition in a loop.
- CLZERO (0F 01 FC) and the immediate SSE4a forms INSERTQ xmm, xmm, len, idx (F2 0F 78 /r ib ib)
  and EXTRQ xmm, len, idx (66 0F 78 /0 ib ib) become a jump to a stub with the same effect. The
  stubs keep every other register and the flags. Instructions the 5-byte jump overwrites are moved
  behind the stub (plan_replacement).

Limits: xmm0-7 only for the SSE4a forms (no REX prefix); the register forms of INSERTQ and EXTRQ
(0F 79) are not handled; bits 127:64 of an SSE4a destination, undefined after the original
instruction, keep their value. A thread that is inside the overwritten bytes of a jump site while
another thread faults on it is not accounted for.
"""
import struct

CLZERO = b"\x0f\x01\xfc"

# push rax; push rcx; mov ecx, 6; shrx rax, rax, rcx; shlx rax, rax, rcx (rax &= ~63, flags kept);
# mov qword [rax + 0..56], 0; pop rcx; pop rax
CLZERO_STUB = (bytes.fromhex("5051b906000000c4e2f3f7c0c4e2f1f7c048c70000000000") +
               b"".join(bytes.fromhex("48c740%02x00000000" % d) for d in range(8, 64, 8)) + bytes.fromhex("5958"))


def clwb_rewrite(code):
    """(offset, byte) that turns CLWB m8 at the start of code into CLFLUSHOPT m8, or None."""
    if len(code) < 4 or code[0] != 0x66:
        return None
    at = 2 if 0x40 <= code[1] <= 0x4F else 1
    if code[at:at + 2] != b"\x0f\xae" or len(code) <= at + 2:
        return None
    modrm = code[at + 2]
    if (modrm >> 3) & 7 != 6 or modrm >> 6 == 3:
        return None
    return at + 2, bytes([modrm | 0x08])


def wait_rewrite(code):
    """Three replacement bytes for MONITORX or MWAITX at the start of code, or None."""
    if code[:3] == b"\x0f\x01\xfa":
        return b"\x0f\x1f\x00"  # nop dword ptr [rax]
    if code[:3] == b"\x0f\x01\xfb":
        return b"\xf3\x90\x90"  # pause; nop
    return None


def sse4a_stub(code):
    """Stub for the immediate INSERTQ or EXTRQ at the start of code (6 bytes), or None."""
    if len(code) < 6 or code[1:3] != b"\x0f\x78" or code[0] not in (0xF2, 0x66) or code[3] < 0xC0:
        return None
    width, offset = (code[4] & 63) or 64, code[5] & 63
    if offset + width > 64:
        return None  # undefined result on the processor
    mask = (1 << width) - 1
    if code[0] == 0xF2:
        dest, src = (code[3] >> 3) & 7, code[3] & 7
        body = (bytes([0x66, 0x48, 0x0F, 0x7E, 0xC0 | src << 3]) +                       # movq rax, xmm_src
                b"\x48\xb9" + struct.pack("<Q", mask) + b"\x48\x21\xc8" +                # and rax, mask
                (bytes([0x48, 0xC1, 0xE0, offset]) if offset else b"") +                 # shl rax, offset
                bytes([0x66, 0x48, 0x0F, 0x7E, 0xC0 | dest << 3 | 2]) +                  # movq rdx, xmm_dest
                b"\x48\xb9" + struct.pack("<Q", ~(mask << offset) & (1 << 64) - 1) + b"\x48\x21\xca" +
                b"\x48\x09\xc2")                                                         # or rdx, rax
    else:
        if (code[3] >> 3) & 7:
            return None
        dest = code[3] & 7
        body = (bytes([0x66, 0x48, 0x0F, 0x7E, 0xC0 | dest << 3 | 2]) +                  # movq rdx, xmm_dest
                (bytes([0x48, 0xC1, 0xEA, offset]) if offset else b"") +                 # shr rdx, offset
                b"\x48\xb9" + struct.pack("<Q", mask) + b"\x48\x21\xca")                 # and rdx, mask
    # pushfq; push rax; push rcx; push rdx ... pinsrq xmm_dest, rdx, 0; pop rdx; pop rcx; pop rax; popfq
    return (b"\x9c\x50\x51\x52" + body + bytes([0x66, 0x48, 0x0F, 0x3A, 0x22, 0xC0 | dest << 3 | 2, 0x00]) +
            b"\x5a\x59\x58\x9d")


def stub_for(code):
    """(instruction length, stub bytes) for an instruction that needs a stub, or None."""
    if code[:3] == CLZERO:
        return 3, CLZERO_STUB
    stub = sse4a_stub(code)
    return (6, stub) if stub else None


def plan_replacement(code, site, length, stub, stub_address):
    """Replace the instruction of `length` bytes at `site` (whose bytes start `code`) with `stub`.

    Returns (bytes for stub_address, bytes for site) or None. The site gets a 5-byte JMP rel32 padded
    with NOPs to an instruction boundary. The instructions it overwrites besides the replaced one
    are re-encoded for their new address behind the stub, followed by a jump back. Needs iced-x86
    only when instructions have to move.
    """
    total, moved = length, b""
    if length < 5:
        import iced_x86
        decoder = iced_x86.Decoder(64, bytes(code[length:]), ip=site + length)
        instructions = []
        while total < 5:
            if not decoder.can_decode:
                return None
            instruction = decoder.decode()
            if instruction.code == iced_x86.Code.INVALID:
                return None
            instructions.append(instruction)
            total += instruction.len
        instructions.append(iced_x86.Instruction.create_branch(iced_x86.Code.JMP_REL32_64, site + total))
        encoder = iced_x86.BlockEncoder(64)
        encoder.add_many(instructions)
        moved = encoder.encode(stub_address + len(stub))
    else:
        back = site + total - (stub_address + len(stub) + 5)
        if not -2**31 <= back < 2**31:
            return None
        moved = b"\xe9" + struct.pack("<i", back)
    forward = stub_address - (site + 5)
    if not -2**31 <= forward < 2**31:
        return None
    return stub + moved, b"\xe9" + struct.pack("<i", forward) + b"\x90" * (total - 5)
