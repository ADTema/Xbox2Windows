"""Split the #670 shared comparison/ordinary sampler, compile it and check the GPU readback.

Usage: compare_sampler.py <spirv-as> <spirv-val> <spirv-cross> [<dxc> <offscreen_check> hardware|warp]

Without the last three arguments only the SPIR-V and HLSL stages and the rejection controls run.
"""
from pathlib import Path
import re
import struct
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from spirv_sampler_split import split_comparison_sampler
from spirv_sampler_views import split_sampler_views

ORDINARY_BINDING = 5
SHARED = Path(__file__).with_name("shared_sampler.spvasm").read_text(encoding="utf-8")
# The same module with arrayed (Texture2DArray) images and a float3 coordinate (u, v, layer 0).
SHARED_ARRAY = Path(__file__).with_name("shared_sampler_array.spvasm").read_text(encoding="utf-8")
# The arrayed module reading layer 1 instead of layer 0 (the coordinate's third component becomes 1).
SHARED_ARRAY_LAYER1 = SHARED_ARRAY.replace(
    "%15 = OpConstantComposite %v3float %float_0_25 %float_0_25 %float_0",
    "%float_1 = OpConstant %float 1\n         %15 = OpConstantComposite %v3float %float_0_25 %float_0_25 %float_1")
# 0.25 <= 0.5 passes, 0.75 <= 0.5 fails, ordinary sample of 0.375; the other 13 words are guards.
EXPECTED = [0x3f800000, 0x00000000, 0x3ec00000] + [0xc5c5c5c5] * 13
# Layer 1 of the arrayed textures: 0.25 <= 0.875 and 0.75 <= 0.875 both pass, ordinary sample of 0.3125.
EXPECTED_LAYER1 = [0x3f800000, 0x3f800000, 0x3ea00000] + [0xc5c5c5c5] * 13


def substitute(text, old, new):
    assert text.count(old) == 1, old
    return text.replace(old, new)


def rejected(assembly, binding, reason):
    try:
        split_comparison_sampler(assembly, binding)
    except ValueError as error:
        assert reason in str(error), error
    else:
        raise AssertionError(f"accepted invalid input: {reason}")


def controls(directory):
    lowered, mapping = split_comparison_sampler(SHARED, ORDINARY_BINDING)
    assert mapping == {"descriptor_set": 0, "comparison_binding": 2, "ordinary_binding": ORDINARY_BINDING}, mapping
    # The arrayed variant splits to the same mapping and only the ordinary load moves.
    array_lowered, array_mapping = split_comparison_sampler(SHARED_ARRAY, ORDINARY_BINDING)
    assert array_mapping == mapping, array_mapping
    assert "%x2w_plain_sampler_0 = OpLoad %type_sampler %x2w_plain_sampler" in array_lowered.splitlines()
    assert "OpTypeImage %float 2D 2 1 0 1 Unknown" in array_lowered
    # Modules without a mixed standalone sampler come back byte-for-byte, whatever else they contain.
    separated = substitute(SHARED, "%41 = OpLoad %type_sampler %cmpSampler", "%41 = OpLoad %type_sampler %plainSampler")
    separated_lod = substitute(separated, "%43 = OpImageSampleExplicitLod %v4float %42 %15 Lod %float_0",
                               "%43 = OpImageSampleExplicitLod %v4float %42 %15 Lod %float_0_25")
    table = Path(__file__).with_name("sampler.spvasm").read_text(encoding="utf-8")  # #676 indexed table
    for name, module in (("already separated", separated), ("unrelated nonzero LOD", separated_lod),
                         ("indexed sampler table", table), ("split sampler views", split_sampler_views(table))):
        assert split_comparison_sampler(module, ORDINARY_BINDING) == (module, None), name

    # An unrelated ordinary sample at nonzero LOD on another sampler does not block the split.
    unrelated = substitute(SHARED, "%44 = OpCompositeExtract %float %43 0",
                           "%44 = OpCompositeExtract %float %43 0\n"
                           "%u1 = OpLoad %type_sampler %plainSampler\n"
                           "%u2 = OpSampledImage %type_sampled_image %40 %u1\n"
                           "%u3 = OpImageSampleExplicitLod %v4float %u2 %15 Lod %float_0_25")
    split, mapping = split_comparison_sampler(unrelated, ORDINARY_BINDING)
    assert mapping["ordinary_binding"] == ORDINARY_BINDING
    assert "%u2 = OpSampledImage %type_sampled_image %40 %u1" in split

    # Unsupported uses of the sampler being split are still rejected.
    for binding in (2, 3, 4):
        rejected(SHARED, binding, f"binding {binding} is occupied in set 0")
    # A binding declared without a DescriptorSet decoration still occupies set 0.
    rejected(substitute(SHARED, "OpDecorate %plainSampler DescriptorSet 0\n", ""), 3,
             "binding 3 is occupied in set 0 by %plainSampler")
    # The ordinary sample may not reuse the comparison's sampled image.
    rejected(substitute(SHARED, "%43 = OpImageSampleExplicitLod %v4float %42 ",
                        "%43 = OpImageSampleExplicitLod %v4float %34 "),
             ORDINARY_BINDING, "one sampled image is used for both sampling kinds")
    rejected(substitute(SHARED, "%float_0_75 Lod %float_0", "%float_0_75 Lod %float_0_25"),
             ORDINARY_BINDING, "requires a constant LOD of zero")
    rejected(substitute(SHARED, "%43 = OpImageSampleExplicitLod %v4float %42 %15 Lod %float_0",
                        "%43 = OpImageSampleExplicitLod %v4float %42 %15 Lod %float_0_25"),
             ORDINARY_BINDING, "requires a constant LOD of zero")
    rejected(substitute(SHARED, "%33 = OpLoad %type_sampler %cmpSampler",
                        "%copy = OpCopyObject %_ptr_UniformConstant_type_sampler %cmpSampler\n"
                        "%33 = OpLoad %type_sampler %cmpSampler"),
             ORDINARY_BINDING, "only direct loads are supported")
    rejected(substitute(SHARED, "%33 = OpLoad %type_sampler %cmpSampler",
                        "%33 = OpLoad %type_sampler %cmpSampler\n"
                        "%loaded_copy = OpCopyObject %type_sampler %33"),
             ORDINARY_BINDING, "loaded sampler feeds OpCopyObject")

    # The remaining profile diagnostics.
    rejected(SHARED, -1, "Ordinary sampler binding must be nonnegative")
    rejected(substitute(SHARED, "OpEntryPoint GLCompute", "OpEntryPoint Fragment"),
             ORDINARY_BINDING, "requires a single GLCompute entry point")
    # Only Texture2D and Texture2DArray are in the profile: multisampled and 3D images stay rejected.
    for image in ("OpTypeImage %float 2D 2 0 1 1 Unknown", "OpTypeImage %float 3D 2 0 0 1 Unknown"):
        rejected(substitute(SHARED, "OpTypeImage %float 2D 2 0 0 1 Unknown", image),
                 ORDINARY_BINDING, "only float32 Texture2D and Texture2DArray sampling is supported")
    rejected(substitute(SHARED_ARRAY, "OpTypeImage %float 2D 2 1 0 1 Unknown",
                        "OpTypeImage %float 2D 2 1 1 1 Unknown"),
             ORDINARY_BINDING, "only float32 Texture2D and Texture2DArray sampling is supported")
    rejected(substitute(SHARED, " %cmpSampler %plainSampler %results", " %plainSampler %results"),
             ORDINARY_BINDING, "sampler must be listed in the entry-point interface")
    rejected(substitute(SHARED, "%float_0 = OpConstant %float 0",
                        "%float_0 = OpConstant %float 0\n"
                        "%x2w_plain_sampler_0 = OpConstant %float 0"),
             ORDINARY_BINDING, "Reserved sampler split ID is already in use")

    # Occupancy is per descriptor set: binding 3 is taken in set 0 and free in set 1.
    other_set = substitute(SHARED, "OpDecorate %cmpSampler DescriptorSet 0",
                           "OpDecorate %cmpSampler DescriptorSet 1")
    other_lowered, other_mapping = split_comparison_sampler(other_set, 3)
    assert other_mapping == {"descriptor_set": 1, "comparison_binding": 2, "ordinary_binding": 3}, other_mapping
    assert "OpDecorate %x2w_plain_sampler DescriptorSet 1" in other_lowered.splitlines()
    assert "OpDecorate %x2w_plain_sampler Binding 3" in other_lowered.splitlines()

    tool = [sys.executable, "-B", str(ROOT / "tools" / "spirv_sampler_split.py")]
    source = directory / "shared.spvasm"
    source.write_text(SHARED, encoding="utf-8")
    target = directory / "lowered.spvasm"
    run = subprocess.run([*tool, source, target, "--ordinary-binding", str(ORDINARY_BINDING)],
                         capture_output=True, text=True, check=True)
    assert run.stdout.split() == ["descriptor_set=0", "comparison_binding=2", f"ordinary_binding={ORDINARY_BINDING}"]
    assert target.read_text(encoding="utf-8") == lowered
    occupied = subprocess.run([*tool, source, directory / "occupied.spvasm", "--ordinary-binding", "3"],
                              capture_output=True, text=True)
    assert occupied.returncode == 1 and "occupied" in occupied.stderr, occupied
    assert not (directory / "occupied.spvasm").exists()
    return lowered


def emit(directory, assembler, validator, cross):
    lowered = controls(directory)
    outputs = {}
    array_lowered = split_comparison_sampler(SHARED_ARRAY, ORDINARY_BINDING)[0]
    assert SHARED_ARRAY_LAYER1 != SHARED_ARRAY
    layer1_lowered, layer1_mapping = split_comparison_sampler(SHARED_ARRAY_LAYER1, ORDINARY_BINDING)
    assert layer1_mapping["ordinary_binding"] == ORDINARY_BINDING, layer1_mapping
    for name, assembly in (("shared", SHARED), ("lowered", lowered),
                           ("shared_array", SHARED_ARRAY), ("lowered_array", array_lowered),
                           ("lowered_array_layer1", layer1_lowered)):
        text = directory / f"{name}.spvasm"
        text.write_text(assembly, encoding="utf-8")
        module = directory / f"{name}.spv"
        subprocess.run([assembler, "--target-env", "vulkan1.2", text, "-o", module], check=True)
        subprocess.run([validator, "--target-env", "vulkan1.2", module], check=True)
        hlsl = directory / f"{name}.hlsl"
        subprocess.run([cross, module, "--hlsl", "--shader-model", "60", "--output", hlsl], check=True)
        outputs[name] = hlsl
    source = outputs["lowered"].read_text(encoding="utf-8")
    comparison = re.search(r"SamplerComparisonState\s+(\w+)\s*:\s*register\(s2\b", source)
    ordinary = re.search(rf"SamplerState\s+(\w+)\s*:\s*register\(s{ORDINARY_BINDING}\b", source)
    assert comparison and ordinary, source
    assert source.count(f"SampleCmpLevelZero({comparison[1]},") == 2, source
    assert source.count(f"SampleLevel({ordinary[1]},") == 1, source
    array_source = outputs["lowered_array"].read_text(encoding="utf-8")
    comparison = re.search(r"SamplerComparisonState\s+(\w+)\s*:\s*register\(s2\b", array_source)
    ordinary = re.search(rf"SamplerState\s+(\w+)\s*:\s*register\(s{ORDINARY_BINDING}\b", array_source)
    assert comparison and ordinary and "Texture2DArray" in array_source, array_source
    assert array_source.count(f"SampleCmpLevelZero({comparison[1]},") == 2, array_source
    assert array_source.count(f"SampleLevel({ordinary[1]},") == 1, array_source
    print(f"shared and lowered SPIR-V validated; comparison s2, ordinary s{ORDINARY_BINDING}; controls passed",
          flush=True)
    return outputs


def compile_dxil(directory, dxc, outputs):
    # The unsplit module reproduces the original DXC rejection.
    shared = subprocess.run([dxc, "-T", "cs_6_0", "-E", "main", "-Fo", directory / "shared.dxil", outputs["shared"]],
                            capture_output=True, text=True)
    if shared.returncode == 0 or "no matching member function for call to 'SampleLevel'" not in shared.stderr:
        raise AssertionError(f"Expected the shared-sampler DXC diagnostic\n{shared.stdout}\n{shared.stderr}")
    print("shared-sampler HLSL: DXC rejected SampleLevel as expected", flush=True)
    # The unsplit arrayed module is rejected the same way.
    shared = subprocess.run([dxc, "-T", "cs_6_0", "-E", "main", "-Fo", directory / "shared_array.dxil",
                             outputs["shared_array"]], capture_output=True, text=True)
    if shared.returncode == 0 or "no matching member function for call to 'SampleLevel'" not in shared.stderr:
        raise AssertionError(f"Expected the arrayed shared-sampler DXC diagnostic\n{shared.stdout}\n{shared.stderr}")
    print("arrayed shared-sampler HLSL: DXC rejected SampleLevel as expected", flush=True)
    dxil = {}
    for name in ("lowered", "lowered_array", "lowered_array_layer1"):
        dxil[name] = directory / f"{name}.dxil"
        subprocess.run([dxc, "-T", "cs_6_0", "-E", "main", "-Fo", dxil[name], outputs[name]], check=True)
    print("DXC compiled the lowered module and both arrayed lowered modules (layers 0 and 1)", flush=True)
    return dxil


def with_words(base=None, **words):
    reference = (base or EXPECTED).copy()
    for index, value in words.items():
        reference[int(index[1:])] = value
    return reference


# (name, module, descriptor variant, reference, mismatching words reported on stderr)
DRAWS = [
    ("baseline", "lowered", "baseline", EXPECTED, []),
    # Wrong reference: claim the failing comparison passed.
    ("wrong reference", "lowered", "baseline", with_words(w1=0x3f800000),
     ["word=1 expected=3f800000 actual=00000000"]),
    # s2 switched to GREATER: only the two comparison words change, against the baseline reference.
    ("comparison descriptor vs baseline", "lowered", "comparison-greater", EXPECTED,
     ["word=0 expected=3f800000 actual=00000000", "word=1 expected=00000000 actual=3f800000"]),
    ("comparison descriptor", "lowered", "comparison-greater", with_words(w0=0x00000000, w1=0x3f800000), []),
    # Ordinary sampler clamped to MinLOD 1: only the ordinary word changes, to t1's 1x1 mip (0.625).
    ("ordinary descriptor vs baseline", "lowered", "ordinary-min-lod1", EXPECTED,
     ["word=2 expected=3ec00000 actual=3f200000"]),
    ("ordinary descriptor", "lowered", "ordinary-min-lod1", with_words(w2=0x3f200000), []),
    # Texture2DArray: two-layer t0 and t1 whose layer 1 differs from layer 0 in each sampled texel.
    ("array layer 0", "lowered_array", "array", EXPECTED, []),
    ("array layer 1", "lowered_array_layer1", "array", EXPECTED_LAYER1, []),
    # Layer 1 against layer 0's reference: the second comparison and the ordinary sample change.
    ("array layer 1 vs layer 0", "lowered_array_layer1", "array", EXPECTED,
     ["word=1 expected=00000000 actual=3f800000", "word=2 expected=3ec00000 actual=3ea00000"]),
    # On layer 1, s2 switched to GREATER changes only the comparison words (0.875 is not below 0.25 or 0.75).
    ("array comparison descriptor vs layer 1", "lowered_array_layer1", "array-comparison-greater", EXPECTED_LAYER1,
     ["word=0 expected=3f800000 actual=00000000", "word=1 expected=3f800000 actual=00000000"]),
    ("array comparison descriptor", "lowered_array_layer1", "array-comparison-greater",
     with_words(EXPECTED_LAYER1, w0=0x00000000, w1=0x00000000), []),
    # On layer 1, the ordinary sampler at MinLOD 1 reads layer 1's 1x1 mip (0.5625), not layer 0's (0.625).
    ("array ordinary descriptor vs layer 1", "lowered_array_layer1", "array-ordinary-min-lod1", EXPECTED_LAYER1,
     ["word=2 expected=3ea00000 actual=3f100000"]),
    ("array ordinary descriptor", "lowered_array_layer1", "array-ordinary-min-lod1",
     with_words(EXPECTED_LAYER1, w2=0x3f100000), []),
]


def draw(directory, dxil, renderer, adapter):
    reference = directory / "reference.bin"
    for name, module, variant, expected, mismatches in DRAWS:
        reference.write_bytes(struct.pack("<16I", *expected))
        run = subprocess.run([renderer, adapter, "--spirv-compare-sampler", dxil[module], str(ORDINARY_BINDING),
                              reference, variant], capture_output=True, text=True)
        print(f"[{name}]", run.stdout, run.stderr, flush=True)
        if run.returncode == 77 and name == "baseline":
            return 77
        reported = [line for line in run.stderr.splitlines() if line.startswith("word=")]
        if (run.returncode != int(bool(mismatches)) or reported != mismatches
                or f"descriptors={variant} " not in run.stdout
                or f"compared_words=16 mismatches={len(mismatches)}" not in run.stdout):
            raise RuntimeError(f"Unexpected {name} readback")
    print("wrong reference fails only at word 1; s2 changes only words 0-1; "
          f"s{ORDINARY_BINDING} changes only word 2", flush=True)
    print("Texture2DArray: layer 0 and layer 1 each read their own texels (layer 1 vs layer 0 differs at words 1-2); "
          f"on layer 1, s2 changes only words 0-1 and s{ORDINARY_BINDING} only word 2 (layer 1's mip 1)", flush=True)
    return 0


if __name__ == "__main__":
    if len(sys.argv) not in (4, 7):
        sys.exit(__doc__)
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        outputs = emit(directory, *sys.argv[1:4])
        if len(sys.argv) == 7:
            dxil = compile_dxil(directory, sys.argv[4], outputs)
            sys.exit(draw(directory, dxil, *sys.argv[5:]))
