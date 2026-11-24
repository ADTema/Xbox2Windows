"""Source-built NGG primitive-shader cases: an identity triangle against single-change contrasts (#1723).

  (no arguments)        encode, decode and run every case, pure Python

The vertex programs of the shader-archive census that tools/startup/gfx2hlsl.py refuses use the gfx10 NGG
protocol: one lane of wave 0 writes the vertex and primitive counts to LDS, waits on s_barrier and sends
GS_ALLOC_REQ (s_sendmsg 9, m0 = primitives << 12 | vertices); the other waves of the group read the counts back
after the barrier. Thread t = 64 * wave + lane exports vertex t (pos0, param0) when t < vertices and primitive t
(export target 20) when t < primitives. The primitive word holds three 10-bit group vertex indices at bits 0, 10
and 20, the layout tools/mesh_entry_aot.py already decodes (with the same m0 split). Bit 31 as the null-primitive
flag is a modelling assumption of this fixture, not checked against hardware or a cited source here; only the
'null' case depends on it. Edge-flag bits are not used.

Every case is one program built from documented gfx1013 encodings, decoded with tools/disasm_rdna2.py (the
decoded text must equal the source line) and executed by a small reference model of those semantics: wave64,
exec masks, scalar branches, one LDS per group, s_barrier, GS_ALLOC_REQ and the three export kinds. The same
decoded words also run under two candidate interpretations of what a lowering could do:

  pass  - each lane alone: LDS is private to the lane, GS_ALLOC_REQ and primitive exports are ignored, and the
          exported vertices form a triangle list in thread order;
  lane  - each lane alone as above, but the allocated counts and the primitive exports are honoured.

The cases separate cleanly when the identity triangle gives the same result under the model and both
interpretations, and each contrast differs from the model in exactly the fields its single change predicts:

  identity    3 vertices, 1 primitive (0,1,2), parameters from the lane's own index, an own-lane LDS round trip
  broadcast   + lane 0 writes one LDS word, s_barrier, every lane adds it to its parameter
  reversed    + the primitive is (2,1,0)
  null        + two primitives are allocated and the second is exported as null
  two_waves   66 vertices, 22 primitives in a group of two waves: wave 1 learns the counts only through LDS

Negative controls: a changed DS offset must fail the decode comparison, and five planted model faults (10-bit index fields read as 8-bit fields at 8-bit steps, the null bit ignored, the
vertex and primitive counts swapped, the wave offset of the thread index dropped, s_barrier ignored with wave 1
run first) must each change at least one expected result. The expected results are written out below from the
encoding, not computed by the model.

The words are not reassembled here: no llvm-mc binary mode yet, so the encodings rest on the opcode tables of
tools/disasm_rdna2.py. This is a semantic fixture for classification; it is not a lowering and it makes no
claim about the console's own compiler beyond the protocol above.
"""
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import disasm_rdna2 as D  # noqa: E402

U32 = 0xffffffff
WAVE = (1 << 64) - 1


# ---------------------------------------------------------------- encoder (gfx10 formats, RDNA 2 ISA chapter 13)
def opcode(table, name):
    return next(op for op, info in table.items() if info[0] == name)


def ssrc(x):
    """scalar/vector source operand code: sN, vN, exec, m0, inline integer 0..64 / -1..-16, 1.0, else literal"""
    if isinstance(x, str):
        if x.startswith('v'):
            return 256 + int(x[1:]), None
        return {'exec': 126, 'm0': 124, 'vcc': 106, '1.0': 242, '4.0': 246}.get(x) or int(x[1:]), None
    if 0 <= x <= 64:
        return 128 + x, None
    if -16 <= x < 0:
        return 192 - x, None
    return 255, x & U32


def words(*ws, lit=None):
    return list(ws) + ([] if lit is None else [lit])


def sop1(name, dst, src):
    s, lit = ssrc(src)
    return words(0xbe800000 | ssrc(dst)[0] << 16 | opcode(D.SOP1_OPS, name) << 8 | s, lit=lit)


def sop2(name, dst, a, b):
    (sa, la), (sb, lb) = ssrc(a), ssrc(b)
    return words(0x80000000 | opcode(D.SOP2_OPS, name) << 23 | ssrc(dst)[0] << 16 | sb << 8 | sa, lit=la if la is not None else lb)


def sopc(name, a, b):
    return words(0xbf000000 | opcode(D.SOPC_OPS, name) << 16 | ssrc(b)[0] << 8 | ssrc(a)[0])


def sopp(name, imm=0):
    return words(0xbf800000 | opcode(D.SOPP_OPS, name) << 16 | (imm & 0xffff))


def vop1(name, dst, src):
    s, lit = ssrc(src)
    return words(0x7e000000 | int(dst[1:]) << 17 | opcode(D.VOP1_OPS, name) << 9 | s, lit=lit)


def vop2(name, dst, a, b):
    s, lit = ssrc(a)
    return words(opcode(D.VOP2_OPS, name) << 25 | int(dst[1:]) << 17 | int(b[1:]) << 9 | s, lit=lit)


def vopc(name, a, b):
    s, lit = ssrc(a)
    return words(0x7c000000 | opcode(D.VOPC_OPS, name) << 17 | int(b[1:]) << 9 | s, lit=lit)


def vop3(name, dst, *src):
    op = opcode(D.VOP3_NATIVE_OPS, name)
    codes = [ssrc(x)[0] for x in src] + [0] * (3 - len(src))
    return words(0xd4000000 | op << 16 | int(dst[1:]), codes[2] << 18 | codes[1] << 9 | codes[0])


def ds(name, addr, data=None, dst=None, offset=0):
    op = opcode(D.DS_OPS, name)
    return words(0xd8000000 | op << 18 | offset, (int(dst[1:]) if dst else 0) << 24 | (int(data[1:]) if data else 0) << 8 | int(addr[1:]))


def exp(target, srcs, done=False):
    en = sum(1 << i for i, s in enumerate(srcs) if s != 'off')
    vs = [0 if s == 'off' else int(s[1:]) for s in srcs]
    return words(0xf8000000 | done << 11 | target << 4 | en, vs[3] << 24 | vs[2] << 16 | vs[1] << 8 | vs[0])


PRIM, POS0, PARAM0 = 20, 12, 32

# Encoder outputs against the golden byte vectors of tests/rdna2_tools_check.py (written as bytes there and checked
# against the decoder, not reassembled). VOP3 (v_mbcnt_*, v_lshl_or_b32), VOPC v_cmpx and export target 20 have no
# vector there.
GOLDEN = [
    ('7e04b2be', sop1('s_mov_b64', 's50', 'exec')),
    ('01028093', sop2('s_bfe_u32', 's0', 's1', 's2')),
    ('030090bf', sopp('s_sendmsg', 3)),
    ('000081bf', sopp('s_endpgm')),
    ('010d007e', vop1('v_cvt_f32_u32_e32', 'v0', 'v1')),
    ('0c05587e', vop1('v_readfirstlane_b32', 's44', 'v12')),
    ('01050602', vop2('v_cndmask_b32_e32', 'v3', 'v1', 'v2')),
    ('01050a16', vop2('v_mul_u32_u24_e32', 'v5', 'v1', 'v2')),
    ('cf0000f804030201', exp(POS0, ['v4', 'v3', 'v2', 'v1'])),
    ('800034d802080000', ds('ds_write_b32', 'v2', data='v8', offset=128)),
    ('4000d8d802000018', ds('ds_read_b32', 'v2', dst='v24', offset=64)),
]


# ---------------------------------------------------------------- the cases
def program(change=None):
    """-> list of (expected disassembly, words); change is None or one contrast name"""
    two = change == 'two_waves'
    nv, npr = (66, 22) if two else (3, 2 if change == 'null' else 1)
    code = [
        # preamble: lane 0 of wave 0 publishes the counts, sends GS_ALLOC_REQ; other waves read them back
        ('s_mov_b64 exec, 1', sop1('s_mov_b64', 's126', 1)),
        ('s_mov_b64 s[8:9], exec', sop1('s_mov_b64', 's8', 'exec')),
        ('s_bfe_u32 s10, s3, 0x40018', sop2('s_bfe_u32', 's10', 's3', 0x40018)),
        ('s_cmp_eq_u32 s10, 0', sopc('s_cmp_eq_u32', 's10', 0)),
        ('s_cbranch_scc0 label_READ', None),
        ('s_movk_i32 s4, 0x%x' % nv, None),
        ('s_movk_i32 s5, 0x%x' % npr, None),
        ('v_mov_b32_e32 v1, s4', vop1('v_mov_b32_e32', 'v1', 's4')),
        ('v_mov_b32_e32 v2, s5', vop1('v_mov_b32_e32', 'v2', 's5')),
        ('v_mov_b32_e32 v3, 0', vop1('v_mov_b32_e32', 'v3', 0)),
        ('ds_write_b32 v3, v1', ds('ds_write_b32', 'v3', data='v1')),
        ('ds_write_b32 v3, v2 offset:4', ds('ds_write_b32', 'v3', data='v2', offset=4)),
        ('s_waitcnt lgkmcnt(0)', None),
        ('s_barrier 0x0', sopp('s_barrier')),
        ('s_lshl_b32 s6, s5, 12', sop2('s_lshl_b32', 's6', 's5', 12)),
        ('s_or_b32 m0, s6, s4', sop2('s_or_b32', 'm0', 's6', 's4')),
        ('s_sendmsg 0x9', sopp('s_sendmsg', 9)),
        ('s_branch label_MAIN', None),
        ('label_READ: s_barrier 0x0', sopp('s_barrier')),
        ('v_mov_b32_e32 v3, 0', vop1('v_mov_b32_e32', 'v3', 0)),
        ('ds_read_b32 v1, v3', ds('ds_read_b32', 'v3', dst='v1')),
        ('ds_read_b32 v2, v3 offset:4', ds('ds_read_b32', 'v3', dst='v2', offset=4)),
        ('s_waitcnt lgkmcnt(0)', None),
        ('v_readfirstlane_b32 s4, v1', vop1('v_readfirstlane_b32', 's4', 'v1')),
        ('v_readfirstlane_b32 s5, v2', vop1('v_readfirstlane_b32', 's5', 'v2')),
        # thread index and per-lane values
        ('label_MAIN: s_mov_b64 exec, -1', sop1('s_mov_b64', 's126', -1)),
        ('s_lshl_b32 s11, s10, 6', sop2('s_lshl_b32', 's11', 's10', 6)),
        ('v_mbcnt_lo_u32_b32 v0, -1, s11', vop3('v_mbcnt_lo_u32_b32', 'v0', -1, 's11')),
        ('v_mbcnt_hi_u32_b32 v0, -1, v0', vop3('v_mbcnt_hi_u32_b32', 'v0', -1, 'v0')),
        ('v_cvt_f32_u32_e32 v5, v0', vop1('v_cvt_f32_u32_e32', 'v5', 'v0')),
        # own-lane LDS round trip at a lane-dependent address (16 + 4t)
        ('v_lshlrev_b32_e32 v8, 2, v0', vop2('v_lshlrev_b32_e32', 'v8', 2, 'v0')),
        ('ds_write_b32 v8, v5 offset:16', ds('ds_write_b32', 'v8', data='v5', offset=16)),
        ('s_waitcnt lgkmcnt(0)', None),
        ('ds_read_b32 v5, v8 offset:16', ds('ds_read_b32', 'v8', dst='v5', offset=16)),
        ('s_waitcnt lgkmcnt(0)', None),
    ]
    if change == 'broadcast':
        code += [
            ('s_mov_b64 exec, 1', sop1('s_mov_b64', 's126', 1)),
            ('v_mov_b32_e32 v9, 8', vop1('v_mov_b32_e32', 'v9', 8)),
            ('v_mov_b32_e32 v10, 4.0', vop1('v_mov_b32_e32', 'v10', '4.0')),
            ('ds_write_b32 v9, v10', ds('ds_write_b32', 'v9', data='v10')),
            ('s_mov_b64 exec, -1', sop1('s_mov_b64', 's126', -1)),
            ('s_waitcnt lgkmcnt(0)', None),
            ('s_barrier 0x0', sopp('s_barrier')),
            ('v_mov_b32_e32 v9, 8', vop1('v_mov_b32_e32', 'v9', 8)),
            ('ds_read_b32 v10, v9', ds('ds_read_b32', 'v9', dst='v10')),
            ('s_waitcnt lgkmcnt(0)', None),
            ('v_add_f32_e32 v5, v5, v10', vop2('v_add_f32_e32', 'v5', 'v5', 'v10')),
        ]
    code += [
        # vertex t < vertices: position (t, t & 1, 0, 1), param0 = t (+ the broadcast word)
        ('v_cmpx_gt_u32_e32 s4, v0', vopc('v_cmpx_gt_u32_e32', 's4', 'v0')),
        ('s_cbranch_execz label_PRIM', None),
        ('v_cvt_f32_u32_e32 v1, v0', vop1('v_cvt_f32_u32_e32', 'v1', 'v0')),
        ('v_and_b32_e32 v2, 1, v0', vop2('v_and_b32_e32', 'v2', 1, 'v0')),
        ('v_cvt_f32_u32_e32 v2, v2', vop1('v_cvt_f32_u32_e32', 'v2', 'v2')),
        ('v_mov_b32_e32 v3, 0', vop1('v_mov_b32_e32', 'v3', 0)),
        ('v_mov_b32_e32 v4, 1.0', vop1('v_mov_b32_e32', 'v4', '1.0')),
        ('exp pos0 v1, v2, v3, v4 done', exp(POS0, ['v1', 'v2', 'v3', 'v4'], True)),
        ('exp param0 v5, v5, v5, v5', exp(PARAM0, ['v5'] * 4)),
        # primitive t < primitives: (3t, 3t+1, 3t+2), or reversed, or null for t == 1
        ('label_PRIM: s_mov_b64 exec, -1', sop1('s_mov_b64', 's126', -1)),
        ('v_cmpx_gt_u32_e32 s5, v0', vopc('v_cmpx_gt_u32_e32', 's5', 'v0')),
        ('s_cbranch_execz label_END', None),
        ('v_mul_u32_u24_e32 v6, 3, v0', vop2('v_mul_u32_u24_e32', 'v6', 3, 'v0')),
        ('v_add_nc_u32_e32 v7, 1, v6', vop2('v_add_nc_u32_e32', 'v7', 1, 'v6')),
        ('v_add_nc_u32_e32 v8, 2, v6', vop2('v_add_nc_u32_e32', 'v8', 2, 'v6')),
    ]
    first, last = ('v8', 'v6') if change == 'reversed' else ('v6', 'v8')
    code += [
        ('v_lshl_or_b32 v7, v7, 10, %s' % first, vop3('v_lshl_or_b32', 'v7', 'v7', 10, first)),
        ('v_lshl_or_b32 v6, %s, 20, v7' % last, vop3('v_lshl_or_b32', 'v6', last, 20, 'v7')),
    ]
    if change == 'null':
        code += [
            ('v_cmp_eq_u32_e32 vcc_lo, 1, v0', vopc('v_cmp_eq_u32_e32', 1, 'v0')),
            ('v_mov_b32_e32 v9, 0x80000000', vop1('v_mov_b32_e32', 'v9', 0x80000000)),
            ('v_cndmask_b32_e32 v9, 0, v9, vcc_lo', vop2('v_cndmask_b32_e32', 'v9', 0, 'v9')),
            ('v_or_b32_e32 v6, v6, v9', vop2('v_or_b32_e32', 'v6', 'v6', 'v9')),
        ]
    code += [
        ('exp target_20 v6, off, off, off done', exp(PRIM, ['v6', 'off', 'off', 'off'], True)),
        ('label_END: s_endpgm', sopp('s_endpgm')),
    ]
    return resolve(code)


def resolve(code):
    """fill in waits, s_movk and branches; branch targets are labels in the source text"""
    out, at, offs = [], {}, []
    for text, w in code:
        label, _, body = text.rpartition(': ')
        name = body.split()[0]
        if w is None:
            if name == 's_waitcnt':
                w = sopp('s_waitcnt', 0xc07f)  # lgkmcnt(0), vmcnt and expcnt at their maxima
            elif name == 's_movk_i32':
                d, k = body.split(' ', 1)[1].split(', ')
                w = words(0xb0000000 | opcode(D.SOPK_OPS, 's_movk_i32') << 23 | int(d[1:]) << 16 | int(k, 16))
            else:
                w = [0]  # branch, patched below
        if label:
            at[label] = sum(len(x[1]) for x in out) * 4
        out.append([body, w])
    pc = 0
    for item in out:
        body, w = item
        if body.startswith(('s_branch', 's_cbranch')):
            name, label = body.split()
            item[1] = sopp(name, (at[label] - pc - 4) // 4)
            item[0] = '%s label_0x%x' % (name, at[label])
        pc += 4 * len(item[1])
    return out


def assemble(code):
    return b''.join(struct.pack('<%dI' % len(w), *w) for _, w in code)


def check_decode(code):
    blob, off = assemble(code), 0
    for text, w in code:
        n, name, asm, _ = D.decode_instruction(blob, off)
        assert n == 4 * len(w) and asm == text, 'decoded %r, expected %r at +0x%x' % (asm, text, off)
        off += n
    return blob


# ---------------------------------------------------------------- reference model and interpretations
class Group:
    """One NGG thread group. mode: 'ngg' (reference), 'pass' or 'lane'; fault: planted model error or None."""

    def __init__(self, blob, waves, mode='ngg', fault=None):
        self.ins, off = {}, 0
        while off < len(blob):
            n, name, asm, _ = D.decode_instruction(blob, off)
            self.ins[off] = (n, name, asm)
            off += n
        self.mode, self.fault, self.nwaves = mode, fault, waves
        self.lds = {}
        self.alloc = None
        self.vertices, self.params, self.prims = {}, {}, {}

    def run(self):
        waves = [dict(pc=0, s={3: w << 24}, v=[{} for _ in range(64)], exec=WAVE, scc=0, vcc=0, m0=0, w=w, done=False)
                 for w in range(self.nwaves)]
        order = waves[::-1] if self.fault == 'no_barrier' else waves
        while not all(w['done'] for w in waves):
            for w in order:
                while not w['done'] and not self.step(w):
                    pass
        return self.result()

    # operand access
    def sval(self, w, t):
        if t == 'exec':
            return w['exec']
        if t in ('vcc', 'vcc_lo'):
            return w['vcc']
        if t.startswith('s['):
            lo = int(t[2:].split(':')[0])
            return w['s'].get(lo, 0) | w['s'].get(lo + 1, 0) << 32
        if t.startswith('s'):
            return w['s'].get(int(t[1:]), 0)
        floats = {'1.0': 0x3f800000, '4.0': 0x40800000}
        return floats[t] if t in floats else int(t, 0) & U32

    def vval(self, w, t, lane):
        return w['v'][lane].get(int(t[1:]), 0) if t.startswith('v') and t[1:].isdigit() else self.sval(w, t) & U32

    def lanes(self, w):
        return [i for i in range(64) if w['exec'] >> i & 1]

    def step(self, w):
        """execute one instruction; True when the wave waits at a barrier"""
        n, name, asm = self.ins[w['pc']]
        w['pc'] += n
        rest = asm.split(' ', 1)[1] if ' ' in asm else ''
        if name == 'exp':
            target, rest = rest.split(' ', 1)
        op = [t.split()[0] for t in rest.split(', ')] if rest else []
        f = lambda x: struct.unpack('<f', struct.pack('<I', x & U32))[0]  # noqa: E731
        u = lambda x: struct.unpack('<I', struct.pack('<f', x))[0]  # noqa: E731
        if name == 's_endpgm':
            w['done'] = True
        elif name == 's_barrier':
            return self.fault != 'no_barrier'
        elif name in ('s_waitcnt',):
            pass
        elif name.startswith(('s_branch', 's_cbranch')):
            take = {'s_branch': True, 's_cbranch_scc0': not w['scc'], 's_cbranch_scc1': bool(w['scc']),
                    's_cbranch_execz': not w['exec']}[name]
            if take:
                w['pc'] = int(op[0].split('_0x')[1], 16)
        elif name == 's_sendmsg':
            assert op == ['0x9'], asm
            if self.mode != 'pass':
                assert w['w'] == 0 and self.alloc is None, 'GS_ALLOC_REQ outside wave 0 or repeated'
                m0 = w['m0']
                v, p = m0 & 0xfff, m0 >> 12
                self.alloc = (p, v) if self.fault == 'swap_counts' else (v, p)
        elif name == 's_mov_b64':
            val = self.sval(w, op[1]) & WAVE if op[1] in ('exec',) or op[1].startswith('s[') else (
                WAVE if op[1] == '-1' else int(op[1], 0))
            if op[0] == 'exec':
                w['exec'] = val
            else:
                lo = int(op[0][2:].split(':')[0])
                w['s'][lo], w['s'][lo + 1] = val & U32, val >> 32
        elif name.startswith('s_'):
            a = [self.sval(w, t) for t in op[1:]]
            if name == 's_movk_i32':
                r = a[0]
            elif name == 's_bfe_u32':
                r = a[0] >> (a[1] & 31) & ((1 << (a[1] >> 16 & 127)) - 1)
            elif name == 's_lshl_b32':
                r = a[0] << (a[1] & 31) & U32
            elif name == 's_or_b32':
                r = a[0] | a[1]
            elif name == 's_cmp_eq_u32':
                w['scc'] = int(self.sval(w, op[0]) == a[0])
                return False
            else:
                raise AssertionError('model lacks ' + asm)
            if name != 's_movk_i32':
                w['scc'] = int(r != 0)
            if op[0] == 'm0':
                w['m0'] = r
            else:
                w['s'][int(op[0][1:])] = r
        elif name == 'v_readfirstlane_b32':
            w['s'][int(op[0][1:])] = self.vval(w, op[1], self.lanes(w)[0])
        elif name.startswith('v_cmp'):
            mask = 0
            for i in self.lanes(w):
                a, b = (self.vval(w, t, i) for t in (op[-2], op[-1]))
                if {'gt': a > b, 'eq': a == b}[name.split('_')[2]]:
                    mask |= 1 << i
            if name.startswith('v_cmpx'):
                w['exec'] = mask
            else:
                w['vcc'] = mask
        elif name.startswith('ds_'):
            off = int(asm.split('offset:')[1]) if 'offset:' in asm else 0
            for i in self.lanes(w):
                lds = self.lds if self.mode == 'ngg' else self.lds.setdefault((w['w'], i), {})
                if name == 'ds_write_b32':
                    lds[self.vval(w, op[0], i) + off] = self.vval(w, op[1], i)
                else:
                    w['v'][i][int(op[0][1:])] = lds.get(self.vval(w, op[1], i) + off, 0)
        elif name == 'exp':
            for i in self.lanes(w):
                t = i if self.fault == 'lane_index' else 64 * w['w'] + i
                if target == 'pos0':
                    self.vertices[t] = tuple(f(self.vval(w, x, i)) for x in op)
                elif target == 'param0':
                    self.params[t] = f(self.vval(w, op[0], i))
                elif target == 'target_20':
                    self.prims[t] = self.vval(w, op[0], i)
                else:
                    raise AssertionError('model lacks ' + asm)
        elif name.startswith('v_'):
            for i in self.lanes(w):
                a = [self.vval(w, t, i) for t in op[1:]]
                if name == 'v_mov_b32_e32':
                    r = a[0]
                elif name == 'v_cvt_f32_u32_e32':
                    r = u(float(a[0]))
                elif name == 'v_add_f32_e32':
                    r = u(f(a[0]) + f(a[1]))
                elif name == 'v_mbcnt_lo_u32_b32':
                    r = bin(a[0] & ((1 << min(i, 32)) - 1)).count('1') + a[1]
                elif name == 'v_mbcnt_hi_u32_b32':
                    r = bin(a[0] & ((1 << max(i - 32, 0)) - 1)).count('1') + a[1]
                elif name == 'v_lshlrev_b32_e32':
                    r = a[1] << (a[0] & 31)
                elif name == 'v_and_b32_e32':
                    r = a[0] & a[1]
                elif name == 'v_or_b32_e32':
                    r = a[0] | a[1]
                elif name == 'v_mul_u32_u24_e32':
                    r = (a[0] & 0xffffff) * (a[1] & 0xffffff)
                elif name == 'v_add_nc_u32_e32':
                    r = a[0] + a[1]
                elif name == 'v_lshl_or_b32':
                    r = a[0] << (a[1] & 31) | a[2]
                elif name == 'v_cndmask_b32_e32':
                    r = a[1] if w['vcc'] >> i & 1 else a[0]
                else:
                    raise AssertionError('model lacks ' + asm)
                w['v'][i][int(op[0][1:])] = r & U32
        else:
            raise AssertionError('model lacks ' + asm)
        return False

    def result(self):
        bits = 8 if self.fault == 'index_bits' else 10
        if self.mode == 'pass':
            nv = len(self.vertices)
            counts = (nv, nv // 3)
            tris = [(3 * t, 3 * t + 1, 3 * t + 2) for t in range(nv // 3)]
        else:
            counts = self.alloc
            nv, npr = counts
            if self.mode == 'ngg':
                assert set(self.vertices) == set(range(nv)) and set(self.prims) == set(range(npr)),                     'exports do not match the allocation'
            tris = []
            for t in sorted(k for k in self.prims if k < npr):
                word = self.prims[t]
                if word >> 31 and self.fault != 'ignore_null':
                    continue
                tris.append(tuple(word >> (bits * k) & ((1 << bits) - 1) for k in range(3)))
        verts = [self.vertices.get(t) for t in range(counts[0])]
        winding = []
        for tri in tris:
            p = [verts[k] if k < len(verts) else None for k in tri]
            if None in p:
                winding.append('invalid')
                continue
            area = (p[1][0] - p[0][0]) * (p[2][1] - p[0][1]) - (p[2][0] - p[0][0]) * (p[1][1] - p[0][1])
            winding.append('ccw' if area > 0 else 'cw' if area < 0 else 'degenerate')
        return dict(counts=counts, positions=verts, params=[self.params.get(t) for t in range(counts[0])],
                    prims=tris, winding=winding)


# ---------------------------------------------------------------- expectations (from the encoding, not the model)
def pos(t):
    return (float(t), float(t & 1), 0.0, 1.0)


IDENTITY = dict(counts=(3, 1), positions=[pos(t) for t in range(3)], params=[0.0, 1.0, 2.0], prims=[(0, 1, 2)],
                winding=['cw'])  # (0,0) -> (1,1) -> (2,0) turns clockwise with y up
EXPECTED = {
    None: IDENTITY,
    'broadcast': dict(IDENTITY, params=[4.0, 5.0, 6.0]),
    'reversed': dict(IDENTITY, prims=[(2, 1, 0)], winding=['ccw']),
    'null': dict(IDENTITY, counts=(3, 2)),
    'two_waves': dict(counts=(66, 22), positions=[pos(t) for t in range(66)], params=[float(t) for t in range(66)],
                      prims=[(3 * t, 3 * t + 1, 3 * t + 2) for t in range(22)],
                      winding=['cw' if t % 2 == 0 else 'ccw' for t in range(22)]),
}
WAVES = {'two_waves': 2}
# fields in which each interpretation must differ from the reference model, per case
PREDICTED = {
    None: {'pass': set(), 'lane': set()},
    'broadcast': {'pass': {'params'}, 'lane': {'params'}},
    'reversed': {'pass': {'prims', 'winding'}, 'lane': set()},
    'null': {'pass': {'counts'}, 'lane': set()},
    # wave 1 never learns the counts: vertices 64 and 65 are missing, so primitive 21 (63, 64, 65) is invalid
    'two_waves': {'pass': {'counts', 'positions', 'params', 'prims', 'winding'},
                  'lane': {'positions', 'params', 'winding'}},
}
FAULTS = ('index_bits', 'ignore_null', 'swap_counts', 'lane_index', 'no_barrier')


def evaluate(blob, case, mode='ngg', fault=None):
    try:
        return Group(blob, WAVES.get(case, 1), mode, fault).run()
    except AssertionError as error:
        return dict(error=str(error))


def main():
    failures = ['encoder gives %s, pinned %s' % (struct.pack('<%dI' % len(w), *w).hex(), want)
                for want, w in GOLDEN if struct.pack('<%dI' % len(w), *w).hex() != want]
    blobs = {case: check_decode(program(case)) for case in EXPECTED}
    bad = program(None)
    bad[11][1] = ds('ds_write_b32', 'v3', data='v2', offset=8)  # count word written one slot too far
    try:
        check_decode(bad)
        failures.append('a changed DS offset still decoded to the source text')
    except AssertionError:
        pass
    for case, blob in blobs.items():
        ref = evaluate(blob, case)
        if ref != EXPECTED[case]:
            failures.append('%s: reference model %r' % (case, {k: v for k, v in ref.items() if EXPECTED[case].get(k) != v}))
            continue
        for mode in ('pass', 'lane'):
            got = evaluate(blob, case, mode)
            diff = {k for k in ref if got.get(k) != ref[k]}
            if diff != PREDICTED[case][mode]:
                failures.append('%s/%s differs in %s, predicted %s' % (case, mode, sorted(diff), sorted(PREDICTED[case][mode])))
    for fault in FAULTS:
        caught = [case for case, blob in blobs.items() if evaluate(blob, case, fault=fault) != EXPECTED[case]]
        if not caught:
            failures.append('planted fault %s passed every case' % fault)
    if failures:
        print('\n'.join(failures))
        return 1
    print('%d cases decoded and separated; %d planted model faults detected' % (len(blobs), len(FAULTS)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
