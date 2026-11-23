"""Validate the logical-window shaders, composed ballot lowering, and rejection paths."""
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import spirv_address_window as window

fixture = Path(__file__).with_name("subtract.spvasm")
original = fixture.read_text(encoding="utf-8")
adapted = window.lower(original)
assert "OpMemoryModel Logical GLSL450" in adapted
assert "OpConvertUToPtr" not in adapted and "OpUGreaterThanEqual" in adapted
# The range check applies to the indexed address, with a strict bound.
assert "%x2w_address_p0_range = OpULessThan %bool %x2w_address_p0_address %x2w_end" in adapted.splitlines()

# A direct word cast is checked from its own address.
direct = original.replace(
    "%v1 = OpConvertUToPtr %_ptr_PSB_arr %a1\n"
    "%p1 = OpAccessChain %_ptr_PSB_uint %v1 %c0",
    "%p1 = OpConvertUToPtr %_ptr_PSB_uint %a1",
)
assert direct != original
assert "%x2w_address_p1_low = OpBitwiseAnd %ulong %a1 %x2w_mask" in window.lower(direct).splitlines()

# Add a ballot read whose bit controls the value written through the physical address.
combined = (original
    .replace("OpCapability Shader\n", "OpCapability Shader\nOpCapability GroupNonUniformBallot\n", 1)
    .replace("%main = OpFunction",
             "%ballot_type = OpTypeVector %uint 4\n"
             "%ballot_mask = OpConstantComposite %ballot_type %c1 %c2 %c3 %c4\n"
             "%main = OpFunction", 1)
    .replace("OpStore %p2 %d Aligned 4",
             "%ballot_bit = OpGroupNonUniformBallotBitExtract %bool %c3 %ballot_mask %c0\n"
             "%selected = OpSelect %uint %ballot_bit %d %c0\n"
             "OpStore %p2 %selected Aligned 4", 1))
assert "OpGroupNonUniformBallotBitExtract" in combined

for source, reason in (
    (original.replace("%d ", "%x2w_d "), "identifier prefix"),
    (combined.replace("%ballot_mask ", "%x2w_ballot_c0 "), "ballot lowering ID"),
    (original.replace("OpDecorate %UserData Block", "OpDecorate %user_data DescriptorSet 2\nOpDecorate %UserData Block"),
     "descriptor sets"),
    (original.replace("OpStore %p2 %d", "%leak = OpConvertPtrToU %ulong %p2\nOpStore %p2 %d"),
     "physical word pointer"),
    (original.replace("OpTypePointer PhysicalStorageBuffer %uint", "OpTypePointer PhysicalStorageBuffer %ulong"),
     "scalar layout"),
    (original.replace("OpDecorate %UserData Block",
                      "OpDecorate %user_data DescriptorSet 1\nOpDecorate %UserData Block"),
     "descriptor sets"),
    (original.replace('OpEntryPoint GLCompute %main "main" %user_data',
                      'OpEntryPoint GLCompute %main "main" %user_data\n'
                      'OpEntryPoint GLCompute %main "other" %user_data'),
     "expected one shader entry point"),
    (original.replace("OpDecorate %rt_uint ArrayStride 4", "OpDecorate %rt_uint ArrayStride 8"),
     "scalar layout"),
    (original.replace("%main = OpFunction",
                      "%unexpected_pc = OpTypePointer PushConstant %uint\n%main = OpFunction"),
     "unrecognized push-constant declaration"),
):
    try:
        window.lower(source)
    except ValueError as error:
        assert reason in str(error), error
    else:
        raise AssertionError(f"accepted invalid profile: {reason}")

with tempfile.TemporaryDirectory() as directory:
    target = Path(directory) / "window.spv"
    tool = [sys.executable, "-B", str(ROOT / "tools" / "spirv_address_window.py")]
    subprocess.run([*tool, fixture, target], check=True)
    valid = target.read_bytes()
    assert valid[:4] == bytes.fromhex("03022307")
    broken = Path(directory) / "broken.spvasm"
    broken.write_text(original.replace("%b = OpLoad %uint %p1", "%b = OpLoad %uint %undefined"), encoding="utf-8")
    failed = subprocess.run([*tool, broken, target], capture_output=True)
    assert failed.returncode and target.read_bytes() == valid

    # This input name previously overlapped the temporaries for %ballot_bit.
    renamed = combined.replace("%p2 ", "%ballot_ballot_bit ")
    assert renamed != combined
    for label, source in (("combined", combined), ("renamed_pointer", renamed), ("direct", direct)):
        mixed = Path(directory) / f"{label}.spvasm"
        mixed.write_text(source, encoding="utf-8")
        mixed_target = Path(directory) / f"{label}.spv"
        subprocess.run([*tool, mixed, mixed_target], check=True)
        assert mixed_target.read_bytes()[:4] == bytes.fromhex("03022307")
    lowered = window.lower(combined)
    assert "OpMemoryModel Logical GLSL450" in lowered
    assert "OpGroupNonUniformBallotBitExtract" not in lowered
    assert "OpConvertUToPtr" not in lowered
print("physical, logical and combined SPIR-V validated; rejection cases passed")
