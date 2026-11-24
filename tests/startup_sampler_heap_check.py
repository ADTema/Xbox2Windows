"""Run-time sampler heap indexing in tools/startup/gfx2hlsl.py (#1143).

  (no arguments)                       translation controls, pure Python
  binary <llvm-mc>                     reassemble the fixture source and compare it with the words below
  draw <dxc> <offscreen_check> <warp|hardware> [fxc]
                                       translate, compile (DXC ps_6_0, and FXC ps_5_1 when given) and
                                       draw: the readback must name the sampler table entry the offset selects

The fixture is a source-built gfx1013 vertex+pixel pair. Its pixel stage loads a texture descriptor
from table 0 and four sampler words from the sampler heap at the byte offset in root constant 1 (s9),
then samples at (1.25, 0.5) and exports the result. tests/startup_sampler_heap.cpp binds a 2048-entry
point-sampler table: entry 0 wraps (0.25), entry 1 clamps (0.75), entries 2 to 2046 use a black border
(0.0), and entry 2047, the fallback for unaligned or out-of-range offsets, uses a border of 0.5.
"""
import os
import re
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'tools' / 'startup'))
import gfx2hlsl as G  # noqa: E402

# Pixel stage: s8 = descriptor table 0, s9 = root constant 1 (the byte offset), s10 = sampler heap.
PS_SOURCE = """\
s_load_dwordx8 s[16:23], s[8:9], 0x0
s_load_dwordx4 s[24:27], s[10:11], s9
v_mov_b32 v0, 0x3fa00000
v_mov_b32 v1, 0.5
s_waitcnt lgkmcnt(0)
image_sample v[0:3], v[0:1], s[16:23], s[24:27] dmask:0xf dim:SQ_RSRC_IMG_2D
s_waitcnt vmcnt(0)
exp mrt0 v0, v1, v2, v3 done vm
s_endpgm
"""
PS_WORDS = bytes.fromhex(
    '04040cf4000000fa' '050608f400000012' 'ff02007e0000a03f' 'f002027e' '7fc08cbf'
    '080f80f00000c400' '703f8cbf' '0f1800f800010203' '000081bf')

# The same load at the constant byte offset 0x10. gfx2hlsl still refuses a constant sampler heap
# offset in both modes; on in-box WARP 10.0.19041.5794 a constant index into the sampler table read
# entry 0 with DXC and FXC while any run-time index read the right entry, so constant offsets are a
# separate step.
CONST_SOURCE = PS_SOURCE.replace('s[10:11], s9', 's[10:11], 0x10')
CONST_WORDS = PS_WORDS.replace(bytes.fromhex('050608f400000012'), bytes.fromhex('050608f4100000fa'))

# The run-time load, then s_mov_b32 s25, 0: the sample's s[24:27] no longer holds one heap load.
MIXED_SOURCE = PS_SOURCE.replace('v_mov_b32 v0, 0x3fa00000\n', 's_mov_b32 s25, 0\nv_mov_b32 v0, 0x3fa00000\n')
MIXED_WORDS = PS_WORDS.replace(bytes.fromhex('ff02007e0000a03f'), bytes.fromhex('800399be' 'ff02007e0000a03f'))

VS_SOURCE = """\
v_mov_b32 v4, 1.0
v_mov_b32 v5, 0
exp pos0 v5, v5, v5, v4 done
s_endpgm
"""
VS_WORDS = bytes.fromhex('f202087e' '80020a7e' 'cf0800f805050504' '000081bf')

# Desktop full-screen triangle for the draw; the translated pixel stage reads only SV_Position.
FULLSCREEN_VS = """\
float4 main(uint id : SV_VertexID) : SV_Position
{
    return float4(id == 1 ? 3.0 : -1.0, id == 2 ? -3.0 : 1.0, 0.0, 1.0);
}
"""

SAMPLER_HEAP_FLAG = 0x800  # D3D12_ROOT_SIGNATURE_FLAG_SAMPLER_HEAP_DIRECTLY_INDEXED


def root_blob(flags=SAMPLER_HEAP_FLAG):
    """A DXBC container with one RTS0 part: parameter 0 a descriptor table, parameter 1 one root constant."""
    params = [(0, 0), (1, 0)]  # (type, visibility)
    poff = 24
    coff = poff + 12 * len(params)
    rts0 = struct.pack('<6I', 2, len(params), poff, 0, 0, flags)
    rts0 += struct.pack('<3I', 0, 0, coff + 12) + struct.pack('<3I', 1, 0, coff)
    rts0 += struct.pack('<3I', 0, 0, 1)        # constants: b0, space 0, one value
    rts0 += struct.pack('<5I', 0, 0, 0, 0, 0)  # table body (gfx2hlsl does not read it)
    part = b'RTS0' + struct.pack('<I', len(rts0)) + rts0
    return (b'DXBC' + bytes(16) + struct.pack('<III', 1, 32 + 4 + len(part), 1) + struct.pack('<I', 36) + part)


def translate(ps_words, sampler_heap):
    return G.Pipeline(VS_WORDS, ps_words, root_blob(), sampler_heap=sampler_heap)


def controls():
    # Opt-in: the run-time offset indexes the table; no shortcut note, no static sampler.
    pipe = translate(PS_WORDS, True)
    ps, manifest = pipe.hlsl_ps(), pipe.manifest()
    assert 'SamplerState qh[2048] : register(s0, space1);' in ps, ps
    m = re.search(r'(\w+)\.Sample\(qh\[x2w_sampler_entry\((s\d+)\)\], ', ps)
    assert m, ps
    assert re.search(r'\b%s = ud1;' % m.group(2), ps), ps
    guard = ('uint x2w_sampler_entry(uint offset) { return (offset & 15u) != 0 || offset >= 32752u ? 2047u : '
             'offset >> 4; }')
    assert guard in ps, ps
    assert 'udsrc 1 rootconst 1 0' in manifest and 'smpheap 2048 1 fallback 2047' in manifest, manifest
    assert not re.search(r'^smp ', manifest, re.M) and not pipe.notes, (manifest, pipe.notes)
    print('run-time offset: qh[x2w_sampler_entry(%s)] with %s = ud1 (root constant 1); unaligned or >= 32752 reads '
          'entry 2047; manifest smpheap 2048 1 fallback 2047' % (m.group(2), m.group(2)))

    # A constant heap offset is still refused, with or without the table.
    for heap in (True, False):
        try:
            translate(CONST_WORDS, heap)
        except G.Unsupported as error:
            assert 'sampler from a descriptor' in str(error), error
        else:
            raise AssertionError('constant sampler heap offset accepted (table %s)' % heap)
    print('constant offset 0x10: still refused in both modes')

    # Default (X2W_SAMPLER_HEAP unset): today's shortcut, a static all-zero sampler and a note.
    pipe = translate(PS_WORDS, False)
    assert 'qh[' not in pipe.hlsl_ps() and 'smpheap' not in pipe.manifest(), pipe.manifest()
    assert 'smp 0 0x0 0x0 0x0 0x0' in pipe.manifest(), pipe.manifest()
    assert pipe.notes == {'dynamic sampler index replaced by a default sampler'}, pipe.notes
    print('opt-out: default sampler shortcut unchanged')
    os.environ['X2W_SAMPLER_HEAP'] = '1'
    try:
        assert G.Pipeline(VS_WORDS, PS_WORDS, root_blob()).uses_sampler_heap
    finally:
        del os.environ['X2W_SAMPLER_HEAP']
    print('X2W_SAMPLER_HEAP=1 selects the table')

    # A sampler operand whose words no longer all come from the heap load is refused.
    try:
        translate(MIXED_WORDS, True)
    except G.Unsupported as error:
        assert 'mixes sampler heap words' in str(error), error
    else:
        raise AssertionError('sampler operand with an overwritten heap word accepted')
    print('refused: s25 overwritten between the heap load and the sample')


def assemble(llvm_mc, source):
    run = subprocess.run([llvm_mc, '-arch=amdgcn', '-mcpu=gfx1013', '-show-encoding'], input=source,
                         capture_output=True, text=True, check=True)
    words = bytearray()
    for line in run.stdout.splitlines():
        m = re.search(r'encoding: \[([^\]]*)\]', line)
        if m:
            words += bytes(int(b, 16) for b in m.group(1).split(','))
    return bytes(words)


def check_binary(llvm_mc):
    for name, source, words in (('pixel', PS_SOURCE, PS_WORDS), ('constant pixel', CONST_SOURCE, CONST_WORDS),
                                ('mixed pixel', MIXED_SOURCE, MIXED_WORDS),
                                ('vertex', VS_SOURCE, VS_WORDS)):
        built = assemble(llvm_mc, source)
        if built != words:
            raise AssertionError('%s fixture: assembled %s, recorded %s' % (name, built.hex(), words.hex()))
    print('fixture words match llvm-mc')


def compile_hlsl(compiler, kind, source, out, profile, directory):
    path = directory / ('%s.hlsl' % out)
    path.write_text(source, encoding='ascii')
    if kind == 'fxc':
        args = [compiler, '/nologo', '/T', profile, '/E', 'main', '/Fo', str(directory / ('%s.cso' % out)), str(path)]
    else:
        args = [compiler, '-T', profile, '-E', 'main', '-Fo', str(directory / ('%s.cso' % out)), str(path)]
    subprocess.run(args, check=True, capture_output=True, text=True)
    return directory / ('%s.cso' % out)


def check_draw(dxc, renderer, adapter, fxc=None):
    # (pixel words, table byte offset, expected red bits)
    # Entries 0, 1 and 2, the last title entry (2046), the first out-of-range offset (2047 * 16), the
    # largest offset and an unaligned one; the last three must read the fallback entry's 0.5 border.
    cases = [(0, 0x3e800000), (16, 0x3f400000), (32, 0x00000000), (2046 * 16, 0x00000000),
             (2047 * 16, 0x3f000000), (0xfffffff0, 0x3f000000), (8, 0x3f000000)]
    compilers = [('dxc', dxc, 'vs_6_0', 'ps_6_0')] + ([('fxc', fxc, 'vs_5_1', 'ps_5_1')] if fxc else [])
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        for kind, compiler, vs_profile, ps_profile in compilers:
            vs = compile_hlsl(compiler, kind, FULLSCREEN_VS, 'fullscreen_%s' % kind, vs_profile, directory)
            shader = compile_hlsl(compiler, kind, translate(PS_WORDS, True).hlsl_ps(), 'ps_%s' % kind, ps_profile, directory)
            # Negative control: the run-time shader with its index dropped must lose entry 1.
            guarded = translate(PS_WORDS, True).hlsl_ps()
            dropped = re.sub(r'qh\[x2w_sampler_entry\(s\d+\)\]', 'qh[0]', guarded)
            assert dropped != guarded
            mutant = compile_hlsl(compiler, kind, dropped, 'ps_dropped_%s' % kind, ps_profile, directory)
            for offset, expected, dropped_index in [c + (False,) for c in cases] + [(16, 0x3f400000, True)]:
                run = subprocess.run([renderer, adapter, '--startup-sampler-heap', str(vs),
                                      str(mutant if dropped_index else shader), str(offset), '%08x' % expected],
                                     capture_output=True, text=True)
                sys.stdout.write(run.stdout)
                label = 'dropped index' if dropped_index else 'run-time offset'
                if dropped_index:
                    if run.returncode == 0 or 'mismatch offset=16 expected=3f400000 actual=3e800000' not in run.stderr:
                        raise AssertionError('%s %s: control did not fail at entry 1\n%s\n%s'
                                             % (kind, label, run.stdout, run.stderr))
                    print('%s %s: fails at entry 1 as expected' % (kind, label), flush=True)
                    continue
                if run.returncode == 77:
                    print(run.stdout + run.stderr)
                    sys.exit(77)
                if run.returncode:
                    raise AssertionError('%s %s offset %d\n%s\n%s' % (kind, label, offset, run.stdout, run.stderr))
                print('%s %s offset %d: %08x' % (kind, label, offset, expected), flush=True)


def main():
    if len(sys.argv) == 1:
        controls()
        return
    mode, *args = sys.argv[1:]
    if mode == 'binary':
        check_binary(*args)
    elif mode == 'draw':
        controls()
        check_draw(*args)
    else:
        raise SystemExit(__doc__)


if __name__ == '__main__':
    main()
