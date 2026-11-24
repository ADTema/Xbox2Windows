"""2D array images in tools/startup/gfx2hlsl.py (dim:SQ_RSRC_IMG_2D_ARRAY).

  (no arguments)                       translation controls, pure Python
  binary <llvm-mc>                     reassemble the fixture sources and compare them with the words below
  draw <dxc> <offscreen_check> <warp|hardware> [fxc]
                                       translate, compile (DXC ps_6_0, and FXC ps_5_1 when given) and
                                       draw: the readback must name the texel of the slice that was selected

Two source-built gfx1013 pixel stages. Both load a texture descriptor from table 0 and take the slice
from root constant 1 (s9). The sample stage builds an all-zero inline sampler and samples at
x = 0.75, y = 0.25 with image_sample. The load stage converts the slice to an integer and reads
texel (1, 0) with image_load, which needs no sampler. tests/startup_image_3d.cpp, run as
--startup-image-2d-array, binds a 2x2 R32G32B32A32_FLOAT texture with two slices whose texel
(x, y, slice) holds ((1 + x + 2y + 4 * slice) / 8, x, y, slice).
"""
import re
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'tools' / 'startup'))
import gfx2hlsl as G  # noqa: E402
from startup_image_3d_check import FULLSCREEN_VS, VS_WORDS, assemble, compile_hlsl, root_blob, texel  # noqa: E402
import subprocess  # noqa: E402

SAMPLE_SOURCE = """\
s_load_dwordx8 s[16:23], s[8:9], 0x0
s_mov_b32 s24, 0
s_mov_b32 s25, 0
s_mov_b32 s26, 0
s_mov_b32 s27, 0
v_mov_b32 v0, 0x3f400000
v_mov_b32 v1, 0x3e800000
v_mov_b32 v2, s9
s_waitcnt lgkmcnt(0)
image_sample v[0:3], v[0:2], s[16:23], s[24:27] dmask:0xf dim:SQ_RSRC_IMG_2D_ARRAY
s_waitcnt vmcnt(0)
exp mrt0 v0, v1, v2, v3 done vm
s_endpgm
"""
SAMPLE_ARRAY = bytes.fromhex('280f80f00000c400')
SAMPLE_WORDS = bytes.fromhex(
    '04040cf4000000fa' '800398be' '800399be' '80039abe' '80039bbe' 'ff02007e0000403f' 'ff02027e0000803e'
    '0902047e' '7fc08cbf') + SAMPLE_ARRAY + bytes.fromhex('703f8cbf' '0f1800f800010203' '000081bf')
# The same program with only the dim field changed.
SOURCE_3D = SAMPLE_SOURCE.replace('dim:SQ_RSRC_IMG_2D_ARRAY', 'dim:SQ_RSRC_IMG_3D')
WORDS_3D = SAMPLE_WORDS.replace(SAMPLE_ARRAY, bytes.fromhex('100f80f00000c400'))
SOURCE_MSAA = SAMPLE_SOURCE.replace('dim:SQ_RSRC_IMG_2D_ARRAY', 'dim:SQ_RSRC_IMG_2D_MSAA')
WORDS_MSAA = SAMPLE_WORDS.replace(SAMPLE_ARRAY, bytes.fromhex('300f80f00000c400'))
SOURCE_LZ = SAMPLE_SOURCE.replace('image_sample ', 'image_sample_lz ')
WORDS_LZ = SAMPLE_WORDS.replace(SAMPLE_ARRAY, bytes.fromhex('280f9cf00000c400'))

LOAD_SOURCE = """\
s_load_dwordx8 s[16:23], s[8:9], 0x0
v_mov_b32 v0, 1
v_mov_b32 v1, 0
v_mov_b32 v2, s9
v_cvt_i32_f32 v2, v2
s_waitcnt lgkmcnt(0)
image_load v[0:3], v[0:2], s[16:23] dmask:0xf dim:SQ_RSRC_IMG_2D_ARRAY
s_waitcnt vmcnt(0)
exp mrt0 v0, v1, v2, v3 done vm
s_endpgm
"""
LOAD_WORDS = bytes.fromhex(
    '04040cf4000000fa' '8102007e' '8002027e' '0902047e' '0211047e' '7fc08cbf' '280f00f000000400' '703f8cbf'
    '0f1800f800010203' '000081bf')

SAMPLE_CALL = 'r0.Sample(q0, float3(F(v0), F(v1), F(v2)))'
LOAD_CALL = 'r0.Load(int4(v0, v1, v2, 0))'


def translate(ps_words):
    return G.Pipeline(VS_WORDS, ps_words, root_blob())


def controls():
    # image_sample: a Texture2DArray, with the slice as the third component of the coordinate.
    pipe = translate(SAMPLE_WORDS)
    ps, manifest = pipe.hlsl_ps(), pipe.manifest()
    assert 'Texture2DArray<float4> r0 : register(t0);' in ps and 'Texture3D' not in ps and 'Texture2D<' not in ps, ps
    assert 't = %s;' % SAMPLE_CALL in ps, ps
    assert re.search(r'\bv2 = ud1;', ps), ps
    assert 'srv 0 tex2da table 0 0' in manifest and 'udsrc 1 rootconst 1 0' in manifest, manifest
    assert not pipe.notes, pipe.notes
    print('image_sample: Texture2DArray r0, %s with v2 = ud1 (root constant 1); manifest srv 0 tex2da' % SAMPLE_CALL)

    # image_sample_lz: the same coordinate at level 0.
    ps = translate(WORDS_LZ).hlsl_ps()
    assert 't = r0.SampleLevel(q0, float3(F(v0), F(v1), F(v2)), 0);' in ps and 'Texture2DArray<float4> r0' in ps, ps
    print('image_sample_lz: SampleLevel(q0, float3(F(v0), F(v1), F(v2)), 0)')

    # image_load: integer texel and slice, mip 0, and no sampler.
    pipe = translate(LOAD_WORDS)
    ps, manifest = pipe.hlsl_ps(), pipe.manifest()
    assert 'Texture2DArray<float4> r0 : register(t0);' in ps, ps
    assert 't = %s;' % LOAD_CALL in ps and 'SamplerState' not in ps, ps
    assert 'srv 0 tex2da table 0 0' in manifest and 'smp ' not in manifest, manifest
    print('image_load: %s; manifest srv 0 tex2da, no sampler' % LOAD_CALL)

    # Only the dim field differs: the 3D form keeps its own type and manifest kind.
    pipe = translate(WORDS_3D)
    assert 'Texture3D<float4> r0 : register(t0);' in pipe.hlsl_ps() and 'srv 0 tex3d table 0 0' in pipe.manifest()
    print('dim 3D (same words, dim field changed): still Texture3D, manifest srv 0 tex3d')

    # A multisampled 2D image is still refused rather than sampled as an array.
    try:
        translate(WORDS_MSAA)
    except G.Unsupported as error:
        assert 'image dimension SQ_RSRC_IMG_2D_MSAA' in str(error), error
    else:
        raise AssertionError('dim:SQ_RSRC_IMG_2D_MSAA accepted')
    print('dim 2D MSAA: refused')


def check_binary(llvm_mc):
    for name, source, words in (('array sample', SAMPLE_SOURCE, SAMPLE_WORDS), ('array sample_lz', SOURCE_LZ, WORDS_LZ),
                                ('array load', LOAD_SOURCE, LOAD_WORDS), ('3D sample', SOURCE_3D, WORDS_3D),
                                ('MSAA sample', SOURCE_MSAA, WORDS_MSAA)):
        built = assemble(llvm_mc, source)
        if built != words:
            raise AssertionError('%s fixture: assembled %s, recorded %s' % (name, built.hex(), words.hex()))
    print('fixture words match llvm-mc')


def check_draw(dxc, renderer, adapter, fxc=None):
    # (stage, call, cases, mutants). x = 0.75, y = 0.25 (sample) and texel (1, 0) (load) select column 1,
    # row 0; the root constant selects the slice. A slice coordinate is not normalized: 0.25 rounds to
    # slice 0 and 0.75 to slice 1. Each mutant edits the translated HLSL and must read another texel.
    stages = [
        ('sample', SAMPLE_WORDS, SAMPLE_CALL,
         [('0', texel(1, 0, 0)), ('1', texel(1, 0, 1)), ('0.25', texel(1, 0, 0)), ('0.75', texel(1, 0, 1))],
         [('slice fixed to 0', SAMPLE_CALL.replace('F(v2)', '0.0'), '1', texel(1, 0, 0)),
          ('x and y exchanged', 'r0.Sample(q0, float3(F(v1), F(v0), F(v2)))', '1', texel(0, 1, 1))]),
        ('load', LOAD_WORDS, LOAD_CALL,
         [('0', texel(1, 0, 0)), ('1', texel(1, 0, 1))],
         [('slice fixed to 0', LOAD_CALL.replace('v2, 0)', '0, 0)'), '1', texel(1, 0, 0)),
          ('x and slice exchanged', 'r0.Load(int4(v2, v1, v0, 0))', '0', texel(0, 0, 1))]),
    ]
    compilers = [('dxc', dxc, 'vs_6_0', 'ps_6_0')] + ([('fxc', fxc, 'vs_5_1', 'ps_5_1')] if fxc else [])
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        for kind, compiler, vs_profile, ps_profile in compilers:
            vs = compile_hlsl(compiler, kind, FULLSCREEN_VS, 'fullscreen_%s' % kind, vs_profile, directory)
            for stage, words, call, cases, mutants in stages:
                translated = translate(words).hlsl_ps()
                shader = compile_hlsl(compiler, kind, translated, 'ps_%s_%s' % (stage, kind), ps_profile, directory)
                for z, expected in cases:
                    run = subprocess.run([renderer, adapter, '--startup-image-2d-array', str(vs), str(shader), z, expected],
                                         capture_output=True, text=True)
                    sys.stdout.write(run.stdout)
                    if run.returncode == 77:
                        print(run.stdout + run.stderr)
                        sys.exit(77)
                    if run.returncode:
                        raise AssertionError('%s %s slice=%s\n%s\n%s' % (kind, stage, z, run.stdout, run.stderr))
                    print('%s %s slice=%s: %s' % (kind, stage, z, expected), flush=True)
                for label, mutated, z, actual in mutants:
                    source = translated.replace(call, mutated)
                    assert source != translated, (stage, label)
                    mutant = compile_hlsl(compiler, kind, source, 'ps_mutant_%s_%s' % (stage, kind), ps_profile, directory)
                    expected = dict(cases)[z]
                    run = subprocess.run([renderer, adapter, '--startup-image-2d-array', str(vs), str(mutant), z, expected],
                                         capture_output=True, text=True)
                    sys.stdout.write(run.stdout)
                    if run.returncode == 0 or 'actual=%s' % actual not in run.stderr:
                        raise AssertionError('%s %s %s: control did not read texel %s\n%s\n%s'
                                             % (kind, stage, label, actual, run.stdout, run.stderr))
                    print('%s %s %s: fails as expected, reads %s' % (kind, stage, label, actual), flush=True)


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
