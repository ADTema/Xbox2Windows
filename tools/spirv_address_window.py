"""Lower the named, DWORD-addressed SPIR-V profile to two logical storage buffers."""
import argparse
from pathlib import Path
import re
import subprocess
import tempfile


from spirv_ballot_extract import lower_ballot_extract
from spirv_sampler_views import split_sampler_views


ID = r"%[A-Za-z0-9_]+"
CAST = re.compile(rf"({ID}) = OpConvertUToPtr %_ptr_PSB_(arr64|arr|ulong|uint) ({ID})")
ACCESS = re.compile(rf"({ID}) = OpAccessChain %_ptr_PSB_uint ({ID}) ({ID})")
WIDE_ACCESS = re.compile(rf"({ID}) = OpAccessChain %_ptr_PSB_ulong ({ID}) ({ID})")
WIDE_POINTER_TYPE = "%_ptr_PSB_ulong = OpTypePointer PhysicalStorageBuffer %ulong"
WIDE_ARRAY_POINTER_TYPE = "%_ptr_PSB_arr64 = OpTypePointer PhysicalStorageBuffer %rt_ulong"
WIDE_ARRAY_DECLARATIONS = ("%rt_ulong = OpTypeRuntimeArray %ulong", "OpDecorate %rt_ulong ArrayStride 8")
# A QWORD access is the plain load or store of one 64-bit value, naturally aligned.
WIDE_MEMORY_OPERANDS = ([], ["Aligned", "8"])
POINTER = re.compile(rf"({ID}) = OpTypePointer (\w+) ({ID})")
WORD_ATOMIC_OPERANDS = {
    "OpAtomicIAdd": 4,
    "OpAtomicExchange": 4,
    "OpAtomicUMin": 4,
    "OpAtomicUMax": 4,
    "OpAtomicAnd": 4,
    "OpAtomicOr": 4,
    "OpAtomicXor": 4,
    "OpAtomicCompareExchange": 6,
}


def address_name(dst):
    # Keep address temporaries separate from the generated x2w_ballot_ IDs.
    return "%x2w_address_" + dst[1:]


def word_pointer(dst, base, index, wide=False):
    """Select the last DWORD offset for an unaligned or unrepresentable address.

    Returns the lines and the ID of the boolean that is true only for an aligned, in-window address.
    A wide (QWORD) pointer selects no substitute: it defines only the DWORD index {address}_word, and the
    access issues in a branch taken for a valid address."""
    name = address_name(dst)
    scale, mask, end = ("%x2w_shift_wide", "%x2w_mask_wide", "%x2w_end_wide") if wide else (
        "%x2w_shift", "%x2w_mask", "%x2w_end")
    lines = []
    addr = base
    if index:
        addr = name + "_address"
        lines.extend([
            f"{name}_index = OpUConvert %ulong {index}",
            f"{name}_delta = OpShiftLeftLogical %ulong {name}_index {scale}",
            f"{addr} = OpIAdd %ulong {base} {name}_delta",
        ])
    lines.extend([
        f"{name}_low = OpBitwiseAnd %ulong {addr} {mask}",
        f"{name}_aligned = OpIEqual %bool {name}_low %x2w_zero64",
        f"{name}_range = OpULessThan %bool {addr} {end}",
        f"{name}_valid = OpLogicalAnd %bool {name}_aligned {name}_range",
    ])
    valid = name + "_valid"
    if index:
        valid = name + "_checked"
        lines.extend([
            f"{name}_nowrap = OpUGreaterThanEqual %bool {addr} {base}",
            f"{valid} = OpLogicalAnd %bool {name}_valid {name}_nowrap",
        ])
    lines.extend([
        f"{name}_word64 = OpShiftRightLogical %ulong {addr} %x2w_shift",
        f"{name}_word = OpUConvert %uint {name}_word64",
    ])
    if wide:
        return lines, valid
    lines.extend([
        f"{name}_selected = OpSelect %uint {valid} {name}_word %x2w_invalid",
        f"{dst} = OpAccessChain %_ptr_PSB_uint %x2w_heap %c0 {name}_selected",
    ])
    return lines, valid


def wide_access(kind, stem, valid, label, word, fields):
    """Lower a QWORD load or store into two DWORD accesses inside a branch taken only for a valid address.

    A load yields zero and a store changes nothing otherwise. Returns the lines and the label that follows."""
    heap = "%_ptr_PSB_uint %x2w_heap %c0"
    lines = [
        f"OpSelectionMerge {stem}_merge None",
        f"OpBranchConditional {valid} {stem}_issue {stem}_merge",
        f"{stem}_issue = OpLabel",
        f"{stem}_next = OpIAdd %uint {word} %x2w_one",
        f"{stem}_low_ptr = OpAccessChain {heap} {word}",
        f"{stem}_high_ptr = OpAccessChain {heap} {stem}_next",
    ]
    if kind == "load":
        lines.extend([
            f"{stem}_low = OpLoad %uint {stem}_low_ptr",
            f"{stem}_high = OpLoad %uint {stem}_high_ptr",
            f"{stem}_low64 = OpUConvert %ulong {stem}_low",
            f"{stem}_high64 = OpUConvert %ulong {stem}_high",
            f"{stem}_high_shifted = OpShiftLeftLogical %ulong {stem}_high64 %x2w_shift_half",
            f"{stem}_value = OpBitwiseOr %ulong {stem}_low64 {stem}_high_shifted",
            f"OpBranch {stem}_merge",
            f"{stem}_merge = OpLabel",
            f"{fields[0]} = OpPhi %ulong {stem}_value {stem}_issue %x2w_zero64 {label}",
        ])
    else:
        lines.extend([
            f"{stem}_low = OpUConvert %uint {fields[2]}",
            f"{stem}_high64 = OpShiftRightLogical %ulong {fields[2]} %x2w_shift_half",
            f"{stem}_high = OpUConvert %uint {stem}_high64",
            f"OpStore {stem}_low_ptr {stem}_low Aligned 4",
            f"OpStore {stem}_high_ptr {stem}_high Aligned 4",
            f"OpBranch {stem}_merge",
            f"{stem}_merge = OpLabel",
        ])
    return lines, stem + "_merge"


def merge_pointer_types(lines):
    # The push-constant and physical pointer types can become the same logical
    # pointer type. SPIR-V validation requires a single such declaration.
    seen = {}
    aliases = {}
    kept = []
    for line in lines:
        match = POINTER.fullmatch(line)
        if match:
            name, storage, pointee = match.groups()
            key = storage, aliases.get(pointee, pointee)
            if key in seen:
                aliases[name] = seen[key]
                continue
            seen[key] = name
        kept.append(line)
    return "\n".join(re.sub(ID, lambda m: aliases.get(m[0], m[0]), line) for line in kept) + "\n"


def lower(assembly):
    lines = [line.strip() for line in split_sampler_views(lower_ballot_extract(assembly)).splitlines() if line.strip()]
    model = "OpMemoryModel PhysicalStorageBuffer64 GLSL450"
    if model not in lines or lines.count("%user_data = OpVariable %_ptr_PC_UserData PushConstant") != 1:
        raise ValueError("expected a physical-address module with the named user-data block")
    # Ballot lowering also emits x2w_ IDs, so check the namespace on the original input.
    if "%x2w_" in assembly or any(re.fullmatch(rf"OpDecorate {ID} DescriptorSet [12]", line) for line in lines):
        raise ValueError("address window needs unused identifier prefix x2w_ and descriptor sets 1 and 2")
    if sum(line.startswith("OpEntryPoint ") for line in lines) != 1:
        raise ValueError("expected one shader entry point")
    required = {"%uint = OpTypeInt 32 0", "%ulong = OpTypeInt 64 0", "%bool = OpTypeBool",
                "%c0 = OpConstant %uint 0", "%rt_uint = OpTypeRuntimeArray %uint",
                "OpDecorate %rt_uint ArrayStride 4", "OpDecorate %UserData Block",
                "%_ptr_PSB_uint = OpTypePointer PhysicalStorageBuffer %uint",
                "%_ptr_PSB_arr = OpTypePointer PhysicalStorageBuffer %rt_uint"}
    if required.difference(lines):
        raise ValueError("unsupported physical pointer or scalar layout")
    annotations = ["OpDecorate %user_data DescriptorSet 1", "OpDecorate %user_data Binding 0",
                   "OpDecorate %user_data NonWritable", "OpDecorate %x2w_heap DescriptorSet 2",
                   "OpDecorate %x2w_heap Binding 0", "OpDecorate %x2w_block Block",
                   "OpMemberDecorate %x2w_block 0 Offset 0"]
    declarations = ["%x2w_block = OpTypeStruct %rt_uint",
                    "%x2w_heap_ptr = OpTypePointer StorageBuffer %x2w_block",
                    "%x2w_heap = OpVariable %x2w_heap_ptr StorageBuffer",
                    "%x2w_shift = OpConstant %uint 2", "%x2w_mask = OpConstant %ulong 3",
                    "%x2w_zero64 = OpConstant %ulong 0", "%x2w_end = OpConstant %ulong 4294967292",
                    "%x2w_invalid = OpConstant %uint 1073741823"]
    output = []
    arrays = {}
    wide_arrays = {}
    wide_words = {}
    valid_of = {}
    label = None
    origin = None
    # A guarded access splits its block, so a successor phi must name the block that now ends in the terminator.
    final_label = {}
    source_phis = []
    wide_accesses = 0
    physical_words = set()
    physical_qwords = set()
    for line in lines:
        cast = CAST.fullmatch(line)
        access = ACCESS.fullmatch(line)
        wide = WIDE_ACCESS.fullmatch(line)
        if access or cast and cast[2] == "uint":
            physical_words.add((access or cast)[1])
        if wide or cast and cast[2] == "ulong":
            physical_qwords.add((wide or cast)[1])
    uses_arrays64 = any(cast and cast[2] == "arr64" for cast in map(CAST.fullmatch, lines))
    if physical_qwords and WIDE_POINTER_TYPE not in lines or uses_arrays64 and (
            WIDE_ARRAY_POINTER_TYPE not in lines or not set(WIDE_ARRAY_DECLARATIONS) <= set(lines)):
        raise ValueError("unsupported physical pointer or scalar layout")
    if physical_qwords:
        declarations += ["%x2w_one = OpConstant %uint 1", "%x2w_shift_wide = OpConstant %uint 3",
                         "%x2w_shift_half = OpConstant %uint 32", "%x2w_mask_wide = OpConstant %ulong 7",
                         # The last valid QWORD ends at the same DWORD as the last valid DWORD access.
                         "%x2w_end_wide = OpConstant %ulong 4294967288"]
    for line in lines:
        if line in ('OpExtension "SPV_KHR_physical_storage_buffer"', "OpCapability PhysicalStorageBufferAddresses",
                    "%_ptr_PSB_arr = OpTypePointer PhysicalStorageBuffer %rt_uint",
                    WIDE_POINTER_TYPE, WIDE_ARRAY_POINTER_TYPE):
            continue
        if line.startswith("OpDecorate ") and annotations:
            output.extend(annotations)
            annotations = []
        if " = OpFunction " in line and declarations:
            output.extend(declarations)
            declarations = []
        if cast := CAST.fullmatch(line):
            dst, kind, addr = cast.groups()
            if kind == "arr":
                arrays[dst] = addr
            elif kind == "arr64":
                wide_arrays[dst] = addr
            elif kind == "ulong":
                new, valid_of[dst] = word_pointer(dst, addr, None, True)
                wide_words[dst] = address_name(dst) + "_word"
                output.extend(new)
            else:
                new, valid_of[dst] = word_pointer(dst, addr, None)
                output.extend(new)
            continue
        if access := ACCESS.fullmatch(line):
            dst, pointer, index = access.groups()
            if pointer not in arrays:
                raise ValueError("unknown physical array pointer")
            new, valid_of[dst] = word_pointer(dst, arrays[pointer], index)
            output.extend(new)
            continue
        if wide := WIDE_ACCESS.fullmatch(line):
            dst, pointer, index = wide.groups()
            if pointer not in wide_arrays:
                raise ValueError("unknown physical array pointer")
            new, valid_of[dst] = word_pointer(dst, wide_arrays[pointer], index, True)
            wide_words[dst] = address_name(dst) + "_word"
            output.extend(new)
            continue
        if opened := re.fullmatch(rf"({ID}) = OpLabel", line):
            label = origin = opened[1]
        ids = set(re.findall(ID, line))
        wide_used = ids & physical_qwords
        if wide_used:
            fields = line.split()
            wide_load = fields[1:4] == ["=", "OpLoad", "%ulong"] and fields[4:5] and fields[4] in wide_used
            wide_store = fields[0] == "OpStore" and fields[1] in wide_used and fields[2] not in wide_used
            operands = fields[5:] if wide_load else fields[3:]
            if ids & physical_words or len(wide_used) != 1 or not (wide_load or wide_store) \
                    or operands not in WIDE_MEMORY_OPERANDS:
                raise ValueError("unhandled physical word pointer use")
            wide_accesses += 1
            kind = "load" if wide_load else "store"
            pointer = fields[4] if wide_load else fields[1]
            stem = "%x2w_" + (f"load_{fields[0][1:]}" if wide_load else f"store_{wide_accesses}")
            new, label = wide_access(kind, stem, valid_of[pointer], label, wide_words[pointer], fields)
            final_label[origin] = label
            output.extend(new)
            continue
        used = ids & physical_words
        atomic_word = False
        if used:
            fields = line.split()
            reads_word = fields[1:4] == ["=", "OpLoad", "%uint"] and fields[4] in used
            writes_word = fields[0] == "OpStore" and fields[1] in used
            # The checked access chain retains the pointer ID. Keep the atomic's
            # result and operands, including scope and memory semantics, intact.
            atomic_word = (len(fields) >= 5 and fields[1] == "=" and fields[3] == "%uint"
                           and fields[4] in used and WORD_ATOMIC_OPERANDS.get(fields[2]) == len(fields) - 4)
            if not (reads_word or writes_word or atomic_word) or len(used) != 1:
                raise ValueError("unhandled physical word pointer use")
        if atomic_word:
            # An address outside the window must not issue an atomic at the substitute index, so the atomic runs
            # only in a branch taken for a valid address; otherwise the result is zero and nothing is written.
            result = fields[0]
            stem = "%x2w_atomic_" + result[1:]
            output.extend([
                f"OpSelectionMerge {stem}_merge None",
                f"OpBranchConditional {valid_of[fields[4]]} {stem}_issue {stem}_merge",
                f"{stem}_issue = OpLabel",
                " ".join([f"{stem}_old", *fields[1:]]),
                f"OpBranch {stem}_merge",
                f"{stem}_merge = OpLabel",
                f"{result} = OpPhi %uint {stem}_old {stem}_issue %c0 {label}",
            ])
            label = stem + "_merge"
            final_label[origin] = label
            continue
        if line == model:
            line = "OpMemoryModel Logical GLSL450"
        elif line.startswith("OpEntryPoint "):
            line += " %x2w_heap"
        elif line == "%_ptr_PSB_uint = OpTypePointer PhysicalStorageBuffer %uint":
            line = "%_ptr_PSB_uint = OpTypePointer StorageBuffer %uint"
        elif "PushConstant" in line:
            if line.split(" = ")[0] not in ("%_ptr_PC_UserData", "%_ptr_PC_uint", "%user_data"):
                raise ValueError("unrecognized push-constant declaration")
            line = line.replace("PushConstant", "StorageBuffer")
        elif any(word in line for word in ("PhysicalStorageBuffer", "OpConvertUToPtr", "OpConvertPtrToU", "%_ptr_PSB_arr")):
            raise ValueError("unhandled physical pointer operation")
        if " = OpPhi " in line:
            source_phis.append(len(output))
        output.append(line)
    for at in source_phis:
        fields = output[at].split()
        fields[5::2] = [final_label.get(parent, parent) for parent in fields[5::2]]
        output[at] = " ".join(fields)
    return merge_pointer_types(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--assembler", default="spirv-as")
    parser.add_argument("--validator", default="spirv-val")
    args = parser.parse_args()
    if args.output.resolve() == args.source.resolve():
        parser.error("use separate input assembly and output binary paths")
    original = args.source.read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory(dir=args.output.parent) as directory:
        path = Path(directory)
        binary = path / "module.spv"

        def validate(source):
            subprocess.run([args.assembler, "--target-env", "vulkan1.2", source, "-o", binary], check=True)
            subprocess.run([args.validator, "--target-env", "vulkan1.2", binary], check=True)

        snapshot = path / "original.spvasm"
        snapshot.write_text(original, encoding="utf-8")
        validate(snapshot)
        adapted = path / "logical.spvasm"
        adapted.write_text(lower(original), encoding="utf-8")
        validate(adapted)
        binary.replace(args.output)


if __name__ == "__main__":
    main()
