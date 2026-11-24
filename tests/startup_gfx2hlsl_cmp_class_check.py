"""`v_cmp_class_f32` in tools/startup/gfx2hlsl.py (issue #1797).

usage: startup_gfx2hlsl_cmp_class_check.py

The binary32 class comparison had no lowering, so both census forms were refused - `v_cmp_class_f32_e64 s32,
-1, v4` and the `_e32` spelling - 2 of the remaining refused shaders in the main-game loading-screen cache
(#870). `tools/pixel_aot.py` already carries the ten-class helper; this port lowers the compare through it.

The instruction bytes are **constructed here** from the field layout the checked-in decoder reads
(`tools/disasm_rdna2.py`, VOP3A branch): prefix `0b110101`, opcode in `w0[25:16]`, scalar destination in
`w0[7:0]`, src0 in `w1[8:0]`, src1 in `w1[17:9]`, and source 255 followed by a literal dword.
"""
import os
import struct
import sys

here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(here, '..', 'tools'))
sys.path.insert(0, os.path.join(here, '..', 'tools', 'startup'))
import gfx2hlsl as G  # noqa: E402

failures = []


def check(label, condition, detail=''):
    print(f"{label}: {'ok' if condition else 'MISMATCH'}")
    if not condition:
        failures.append(label)
        if detail:
            print('  ' + detail)


VOPC_CMP_CLASS_F32 = 0x88
VOPC_CMPX_CLASS_F32 = 0x98
VCC_LO = 106
V0, V4 = 0x100, 0x104
INLINE_MINUS_ONE = 193   # inline constant -1, the mask the census shader uses
LITERAL_SOURCE = 255


def encode_vopc(op, sdst, src0, src1, literal=None):
    """Encode a VOPC comparison in its VOP3A form; a source of 255 is followed by its literal dword."""
    w0 = (0b110101 << 26) | ((op & 0x3FF) << 16) | (sdst & 0xFF)
    w1 = (src0 & 0x1FF) | ((src1 & 0x1FF) << 9)
    code = struct.pack('<II', w0, w1)
    if literal is not None:
        code += struct.pack('<I', literal)
    return code


class Pipeline:
    """Just enough pipeline state for one comparison."""

    def __init__(self):
        self.resources, self.notes, self.modified = {}, set(), set()


class Stage(G.Stage):
    """A Stage with no pipeline: enough state for a decoded instruction to be translated."""

    def __init__(self):
        self.lines, self.sym = [], {}
        self.used_s, self.used_v, self.uniform_v = set(), set(), set()
        self.exec_known = True
        self.exports = {}
        self.masks = set()
        self.pipe = Pipeline()


def translate(code):
    decoded = G.decode(code)
    stage = Stage()
    for _offset, _size, name, asm in decoded:
        stage.one(name, asm)
    return [asm for _o, _s, _n, asm in decoded], ' '.join(stage.lines), stage


# 1. The encoder produces the form the decoder reads; a layout change shows up here first.
asm, emitted, stage = translate(encode_vopc(VOPC_CMP_CLASS_F32, VCC_LO, INLINE_MINUS_ONE, V4))
check('encodes and decodes the class compare',
      asm == ['v_cmp_class_f32_e64 vcc_lo, -1, v4'], repr(asm))

# 2. The predicate is the class of the value against the mask, written to VCC for the non-exec form.
check('the all-classes mask matches everything', 'class32(F(v4))' in emitted and '0xffffffffu' in emitted, emitted)
check('the result is written to vcc', emitted.startswith('vcc = '), emitted)

# 3. The execution-mask form writes EXEC and stops the straight-line assumption.
asm, emitted, stage = translate(encode_vopc(VOPC_CMPX_CLASS_F32, VCC_LO, INLINE_MINUS_ONE, V4))
check('the exec-mask class compare writes exec', emitted.startswith('exec = '), emitted)
check('the exec-mask form clears exec_known', stage.exec_known is False)

# 4. A literal mask and a register value reach the helper as an integer and a float operand.
asm, emitted, _stage = translate(encode_vopc(VOPC_CMP_CLASS_F32, VCC_LO, LITERAL_SOURCE, V4,
                                             literal=0x00000300))
check('a literal mask is read as an integer', '0x00000300u' in emitted, emitted)
asm, emitted, _stage = translate(encode_vopc(VOPC_CMP_CLASS_F32, VCC_LO, V0, V4))
check('a register mask is read as an integer', 'class32(F(v4)) & v0' in emitted, emitted)

# 5. The helper is in the preamble the generated shader is built with, with the ten classes from the encoding.
pipe = object.__new__(G.Pipeline)
pipe.uds, pipe.resources, pipe.samplers, pipe.uses_sampler_heap = [], {}, {}, False
common = ' '.join(pipe.common())
check('the class helper is emitted in the common preamble', 'uint class32(float value)' in common, common[:200])
check('the helper separates quiet from signaling NaN', '0x00400000u' in common, common[:200])

if failures:
    print('FAIL')
    for text in failures:
        print('  ' + text)
    sys.exit(1)
print('PASS')