"""Check straight-line v_readfirstlane_b32 lowering without shader machine code."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tools', 'startup'))
import gfx2hlsl as G  # noqa: E402

failures = []


def check(label, condition, detail=''):
    print(f"{label}: {'ok' if condition else 'MISMATCH  ' + detail}")
    if not condition:
        failures.append(label)


class Pipe:
    """The single resource needed by the buffer-load probe."""

    def resource(self, key, kind):
        return 'r0'


REFUSAL = 'v_readfirstlane_b32 requires a proven uniform source'
READ = 'v_readfirstlane_b32 s9, v7'


def run(*instructions, exec_known=True):
    """Translate disassembly text using the same dispatch and branch scan as a real stage."""
    s = G.Stage.__new__(G.Stage)
    s.pipe, s.lines = Pipe(), []
    s.attrs = {}
    s.sym = {4 + i: ('desc', ('table', 0), 0, i) for i in range(4)}
    s.sym[3] = ('fixed_buffer_word',)
    s.used_s, s.used_v, s.masks = set(), set(), set()
    s.exec_known = exec_known
    s.ins = [(4 * i, 4, asm.split()[0], asm) for i, asm in enumerate(instructions)]
    try:
        s.translate()
    except G.Unsupported as error:
        return str(error)
    return [line for _, lines, _ in s.blocks for line in lines]


# Cover unary scalar inputs, binary and ternary immediate inputs, both encoding suffixes,
# and the fixed buffer word that was already handled before uniformity propagation.
ACCEPTED = [
    ('unsigned conversion', ('v_cvt_u32_f32_e32 v7, s2',),
     ['v7 = uint(max(F(s2), 0.0));']),
    ('signed conversion', ('v_cvt_i32_f32_e32 v7, s2',),
     ['v7 = uint(int(F(s2)));']),
    ('fixed buffer word', ('v_cvt_i32_f32_e32 v7, s3',),
     ['v7 = uint(int(F(s3)));']),
    ('byte conversion', ('v_cvt_f32_ubyte0_e32 v7, s2',),
     ['v7 = U(float(s2 & 255));']),
    ('multiply', ('v_mul_f32_e64 v7, s2, 2.0',),
     ['v7 = U(F(s2) * 2.0);']),
    ('fused multiply-add', ('v_fma_f32 v7, s2, 2.0, 1.0',),
     ['v7 = U(F(s2) * 2.0 + 1.0);']),
    ('literal multiply-add', ('v_fmaak_f32 v7, s2, 2.0, 0x3f800000',),
     ['v7 = U(F(s2) * 2.0 + F(0x3f800000u));']),
    ('reciprocal', ('v_rcp_f32_e32 v7, s2',),
     ['v7 = U(1.0 / F(s2));']),
    ('move', ('v_mov_b32_e32 v7, s2',), ['v7 = s2;']),
    ('literal move', ('v_mov_b32_e32 v7, 0x1234',), ['v7 = 0x00001234u;']),
    ('chain with an in-place write', ('v_mul_f32_e64 v7, s2, 2.0', 'v_cvt_u32_f32_e32 v7, v7'),
     ['v7 = U(F(s2) * 2.0);', 'v7 = uint(max(F(v7), 0.0));']),
]
for label, instructions, lines in ACCEPTED:
    got = run(*instructions, READ)
    check(label, got == lines + ['s9 = v7;'], repr(got))

REFUSED = [
    ('entry VGPR', ('v_mov_b32_e32 v7, v0', READ)),
    ('vcc', ('v_mov_b32_e32 v7, vcc_lo', READ)),
    ('exec', ('v_mov_b32_e32 v7, exec_lo', READ)),
    ('saved exec', ('s_mov_b32 s2, exec_lo', 'v_mov_b32_e32 v7, s2', READ)),
    ('mask through scalar arithmetic',
     ('s_mov_b32 s2, vcc_lo', 's_add_u32 s3, s2, 1', 'v_mov_b32_e32 v7, s3', READ)),
    ('mask through scalar condition',
     ('s_cmp_eq_u32 vcc_lo, 0', 's_cselect_b32 s2, 0, 1', 'v_mov_b32_e32 v7, s2', READ)),
    ('non-listed overwrite', ('v_mov_b32_e32 v7, s2', 'v_add_f32_e64 v7, s2, 1.0', READ)),
    ('SDWA overwrite', ('v_mov_b32_e32 v7, s2',
                        'v_cvt_f32_ubyte0_sdwa v7, s2 src0_sel:DWORD dst_sel:DWORD', READ)),
    ('interpolant overwrite', ('v_mov_b32_e32 v7, s2', 'v_interp_mov_f32 v7, p0, attr0.x', READ)),
    ('VGPR buffer address', ('buffer_load_dword v7, v0, s[4:7], 0 offen', READ)),
    ('branch after read', ('v_mov_b32_e32 v7, s2', READ, 's_branch label_000C', 's_endpgm')),
]
for label, instructions in REFUSED:
    got = run(*instructions)
    check(f'{label} refused', got == REFUSAL, repr(got))
got = run('v_mov_b32_e32 v7, s2', READ, exec_known=False)
check('unknown exec refused', got == REFUSAL, repr(got))

# Remove the allowlist and require the same successful instruction sequences to refuse.
original = G.UNIFORM_VALU
G.UNIFORM_VALU = frozenset()
try:
    for label, instructions, _ in ACCEPTED:
        got = run(*instructions, READ)
        check(f'control: {label} refused without tracking', got == REFUSAL, repr(got))
finally:
    G.UNIFORM_VALU = original

print('Readfirstlane uniformity checks: %d failed' % len(failures))
sys.exit(1 if failures else 0)
