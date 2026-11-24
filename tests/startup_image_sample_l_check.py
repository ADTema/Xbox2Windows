"""Explicit-LOD image_sample_l in tools/startup/gfx2hlsl.py.

  (no arguments)     translation controls, pure Python
  binary <llvm-mc>   reassemble every fixture source and compare it with the recorded words

Each fixture is a source-built gfx1013 pixel stage that sets up v0 = 0.5, v1 = 0.25, v2 = 1.0, v3 = 2.0 and then
runs one image instruction on a texture from descriptor table 0 and an all-zero constant sampler. The lowering must
sample the level held in the LAST address register as SampleLevel(..., level): the contiguous 2D form takes it from
v2, the NSA form from v3 (so it is not just "the third register"), and the 3D form from v3. Forms the lowering does
not model are refused with their own message instead of being sampled at a wrong level.
"""
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'tools' / 'startup'))
sys.path.insert(0, str(HERE))
import gfx2hlsl as G  # noqa: E402
from startup_sampler_heap_check import VS_WORDS, assemble, root_blob  # noqa: E402

PRE = """\
s_load_dwordx8 s[16:23], s[8:9], 0x0
s_mov_b32 s24, 0
s_mov_b32 s25, 0
s_mov_b32 s26, 0
s_mov_b32 s27, 0
v_mov_b32 v0, 0.5
v_mov_b32 v1, 0x3e800000
v_mov_b32 v2, 1.0
v_mov_b32 v3, 2.0
s_waitcnt lgkmcnt(0)
"""
POST = """\
s_waitcnt vmcnt(0)
exp mrt0 v4, v5, v6, v7 done vm
s_endpgm
"""
IMAGE = {
    'plain': 'image_sample_l v[4:7], v[0:2], s[16:23], s[24:27] dmask:0xf dim:SQ_RSRC_IMG_2D',
    'nsa': 'image_sample_l v[4:7], [v0, v1, v3], s[16:23], s[24:27] dmask:0xf dim:SQ_RSRC_IMG_2D',
    'three': 'image_sample_l v[4:7], v[0:3], s[16:23], s[24:27] dmask:0xf dim:SQ_RSRC_IMG_3D',
    'lz': 'image_sample_lz v[4:7], v[0:1], s[16:23], s[24:27] dmask:0xf dim:SQ_RSRC_IMG_2D',
    'offset': 'image_sample_l_o v[4:7], v[0:3], s[16:23], s[24:27] dmask:0xf dim:SQ_RSRC_IMG_2D',
    'compare': 'image_sample_c_l v[4:7], v[0:3], s[16:23], s[24:27] dmask:0xf dim:SQ_RSRC_IMG_2D',
    'gather': 'image_gather4_l v[4:7], v[0:2], s[16:23], s[24:27] dmask:0x1 dim:SQ_RSRC_IMG_2D',
    'cube': 'image_sample_l v[4:7], v[0:3], s[16:23], s[24:27] dmask:0xf dim:SQ_RSRC_IMG_CUBE',
    'a16': 'image_sample_l v[4:7], v[0:1], s[16:23], s[24:27] dmask:0xf dim:SQ_RSRC_IMG_2D a16',
    'tfe': 'image_sample_l v[4:5], v[0:2], s[16:23], s[24:27] dmask:0x1 dim:SQ_RSRC_IMG_2D tfe',
    'unorm': 'image_sample_l v[4:7], v[0:2], s[16:23], s[24:27] dmask:0xf dim:SQ_RSRC_IMG_2D unorm',
}
WORDS = {
    'tfe': bytes.fromhex(
        '04040cf4000000fa800398be800399be80039abe80039bbef002007eff02027e'
        '0000803ef202047ef402067e7fc08cbf080191f00004c400703f8cbf0f1800f8'
        '04050607000081bf'),
    'a16': bytes.fromhex(
        '04040cf4000000fa800398be800399be80039abe80039bbef002007eff02027e'
        '0000803ef202047ef402067e7fc08cbf080f90f00004c440703f8cbf0f1800f8'
        '04050607000081bf'),
    'plain': bytes.fromhex(
        '04040cf4000000fa800398be800399be80039abe80039bbef002007eff02027e'
        '0000803ef202047ef402067e7fc08cbf080f90f00004c400703f8cbf0f1800f8'
        '04050607000081bf'),
    'nsa': bytes.fromhex(
        '04040cf4000000fa800398be800399be80039abe80039bbef002007eff02027e'
        '0000803ef202047ef402067e7fc08cbf0a0f90f00004c40001030000703f8cbf'
        '0f1800f804050607000081bf'),
    'three': bytes.fromhex(
        '04040cf4000000fa800398be800399be80039abe80039bbef002007eff02027e'
        '0000803ef202047ef402067e7fc08cbf100f90f00004c400703f8cbf0f1800f8'
        '04050607000081bf'),
    'lz': bytes.fromhex(
        '04040cf4000000fa800398be800399be80039abe80039bbef002007eff02027e'
        '0000803ef202047ef402067e7fc08cbf080f9cf00004c400703f8cbf0f1800f8'
        '04050607000081bf'),
    'offset': bytes.fromhex(
        '04040cf4000000fa800398be800399be80039abe80039bbef002007eff02027e'
        '0000803ef202047ef402067e7fc08cbf080fd0f00004c400703f8cbf0f1800f8'
        '04050607000081bf'),
    'compare': bytes.fromhex(
        '04040cf4000000fa800398be800399be80039abe80039bbef002007eff02027e'
        '0000803ef202047ef402067e7fc08cbf080fb0f00004c400703f8cbf0f1800f8'
        '04050607000081bf'),
    'gather': bytes.fromhex(
        '04040cf4000000fa800398be800399be80039abe80039bbef002007eff02027e'
        '0000803ef202047ef402067e7fc08cbf080110f10004c400703f8cbf0f1800f8'
        '04050607000081bf'),
    'cube': bytes.fromhex(
        '04040cf4000000fa800398be800399be80039abe80039bbef002007eff02027e'
        '0000803ef202047ef402067e7fc08cbf180f90f00004c400703f8cbf0f1800f8'
        '04050607000081bf'),
    'unorm': bytes.fromhex(
        '04040cf4000000fa800398be800399be80039abe80039bbef002007eff02027e'
        '0000803ef202047ef402067e7fc08cbf081f90f00004c400703f8cbf0f1800f8'
        '04050607000081bf'),
}


def source(name):
    return PRE + IMAGE[name] + '\n' + POST


def stage(name):
    return G.Pipeline(VS_WORDS, WORDS[name], root_blob(flags=0)).hlsl_ps()


def refused(name, text):
    try:
        stage(name)
    except G.Unsupported as error:
        assert text in str(error), (name, str(error))
    else:
        raise AssertionError('%s was accepted' % name)


def level_register(ps, texture_kind):
    """The u, v, optional w and level registers named by the SampleLevel call."""
    m = re.search(r'\w+\.SampleLevel\(\w+, float%d\(F\((v\d+)\), F\((v\d+)\)(?:, F\((v\d+)\))?\), F\((v\d+)\)\);'
                  % (3 if texture_kind == '3d' else 2), ps)
    assert m, ps
    return m.groups()


def controls():
    plain = level_register(stage('plain'), '2d')
    assert plain == ('v0', 'v1', None, 'v2'), plain
    assert 'Texture2D' in stage('plain')
    nsa = level_register(stage('nsa'), '2d')
    assert nsa == ('v0', 'v1', None, 'v3'), nsa  # the level is the last address register, not the third one
    three = level_register(stage('three'), '3d')
    assert three == ('v0', 'v1', 'v2', 'v3'), three
    assert 'Texture3D' in stage('three')
    print('plain 2D level v2; NSA 2D level v3; 3D level v3')

    # The old level-zero form is a different lowering: its call has literal level 0 and no register level.
    lz = stage('lz')
    assert re.search(r'SampleLevel\(\w+, float2\(F\(v0\), F\(v1\)\), 0\)', lz), lz
    assert lz != stage('plain')
    print('image_sample_lz keeps level 0; image_sample_l reads the register')

    refused('offset', 'image_sample_l_o')
    refused('compare', 'image_sample_c_l')
    refused('gather', 'image_gather4_l')
    refused('cube', 'image dimension SQ_RSRC_IMG_CUBE')
    refused('unorm', 'image_sample_l modifier unorm')
    refused('tfe', 'image_sample_l modifier tfe')  # the extra status register is not modelled
    refused('a16', 'image_sample_l modifier a16')  # packed 16-bit address: v[0:1] holds u, v and the level as halves
    print('refused: offset, compare, gather, cube, unorm, a16, tfe')


def check_binary(llvm_mc):
    for name in WORDS:
        built = assemble(llvm_mc, source(name))
        # Only the instruction under test differs from the shared preamble and epilogue.
        if built != WORDS[name]:
            raise AssertionError('%s fixture: assembled %s, recorded %s' % (name, built.hex(), WORDS[name].hex()))
    print('fixture words match llvm-mc')


if __name__ == '__main__':
    if len(sys.argv) == 1:
        controls()
    elif sys.argv[1] == 'binary' and len(sys.argv) == 3:
        check_binary(sys.argv[2])
    else:
        sys.exit(__doc__)
