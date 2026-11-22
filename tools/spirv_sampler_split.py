"""Split a sampler shared by comparison and ordinary sampling in the bridge's named SPIR-V profile.

SPIRV-Cross declares one HLSL sampler per SPIR-V sampler variable. When one variable feeds both
OpImageSampleDrefExplicitLod and OpImageSampleExplicitLod, it emits a SamplerComparisonState and
passes it to an ordinary SampleLevel call, which DXC rejects. This pass keeps the comparison
sampler at its original binding and moves only the ordinary uses to a new sampler variable at a
binding the caller supplies. The caller (the host) owns that binding and must bind an ordinary
sampler there. Modules without a mixed sampler are returned unchanged.

The profile is limited to direct, non-array float32 Texture2D sampling in a single compute entry
point, at a constant LOD of zero, from a standalone UniformConstant sampler listed in the
entry-point interface. Anything else is rejected with a specific diagnostic.
"""
import argparse
from collections import defaultdict
from pathlib import Path
import shlex
import sys

PREFIX = "%x2w_plain_sampler"
ZERO = {"0", "0.0", "0x0p+0", "-0", "-0.0", "-0x0p+0"}


def _tokens(line):
    lexer = shlex.shlex(line, posix=False)
    lexer.commenters = ";"
    lexer.whitespace_split = True
    return list(lexer)


def split_comparison_sampler(assembly, ordinary_binding):
    """Return (assembly, mapping). mapping is None when no sampler has mixed uses."""
    if ordinary_binding < 0:
        raise ValueError("Ordinary sampler binding must be nonnegative")
    lines = assembly.splitlines()
    parsed = [_tokens(line) for line in lines]
    definitions = {words[0]: words[2:] for words in parsed if len(words) >= 3 and words[1] == "="}
    defined_at = {words[0]: i for i, words in enumerate(parsed) if len(words) >= 3 and words[1] == "="}
    entries = [i for i, words in enumerate(parsed) if words[:1] == ["OpEntryPoint"]]
    if len(entries) != 1 or parsed[entries[0]][1] != "GLCompute":
        raise ValueError("Sampler split requires a single GLCompute entry point")
    entry = entries[0]

    bindings = {}
    descriptor_sets = {}
    for i, words in enumerate(parsed):
        if len(words) == 4 and words[0] == "OpDecorate" and words[2] == "Binding":
            bindings[words[1]] = (i, int(words[3], 0))
        elif len(words) == 4 and words[0] == "OpDecorate" and words[2] == "DescriptorSet":
            descriptor_sets[words[1]] = int(words[3], 0)

    uses = defaultdict(list)
    for words in parsed:
        args = words[2:] if len(words) >= 3 and words[1] == "=" else words
        if args and args[0] not in {"OpName", "OpDecorate", "OpMemberName", "OpMemberDecorate"}:
            for operand in args[1:]:
                if definitions.get(operand, [])[:1] == ["OpSampledImage"]:
                    uses[operand].append(args)

    kinds_by_sampler = defaultdict(set)
    ordinary_images = defaultdict(list)
    for image, definition in definitions.items():
        if definition[:1] != ["OpSampledImage"]:
            continue
        sampled_type, _, loaded = definition[1:]
        load = definitions.get(loaded, [])
        if len(load) != 3 or load[0] != "OpLoad":
            raise ValueError(f"{image}: sampler must be loaded directly from a variable")
        sampler_type, sampler = load[1:]
        variable = definitions.get(sampler, [])
        if (len(variable) != 3 or variable[0] != "OpVariable" or variable[2] != "UniformConstant"
                or definitions.get(variable[1]) != ["OpTypePointer", "UniformConstant", sampler_type]
                or definitions.get(sampler_type) != ["OpTypeSampler"]):
            raise ValueError(f"{image}: sampler must be a standalone UniformConstant variable")

        sampled = definitions.get(sampled_type, [])
        texture = definitions.get(sampled[1], []) if sampled[:1] == ["OpTypeSampledImage"] else []
        # OpTypeImage <sampled type> 2D <depth> <arrayed> <ms> <sampled> <format>
        if (len(texture) != 8 or texture[0] != "OpTypeImage"
                or definitions.get(texture[1]) != ["OpTypeFloat", "32"]
                or texture[2] != "2D" or texture[4:] != ["0", "0", "1", "Unknown"]):
            raise ValueError(f"{image}: only non-array float32 Texture2D sampling is supported")

        kinds = set()
        for use in uses[image]:
            ordinary = use[0] == "OpImageSampleExplicitLod" and len(use) == 6
            compare = use[0] == "OpImageSampleDrefExplicitLod" and len(use) == 7
            if not (ordinary or compare) or use[2] != image or use[-2] != "Lod":
                raise ValueError(f"{image}: only explicit-LOD ordinary and depth-comparison sampling is supported")
            lod = definitions.get(use[-1], [])
            if len(lod) != 3 or lod[:2] != ["OpConstant", texture[1]] or lod[2] not in ZERO:
                raise ValueError(f"{image}: {use[0]} requires a constant LOD of zero")
            kinds.add("ordinary" if ordinary else "compare")
        if len(kinds) > 1:
            raise ValueError(f"{image}: one sampled image is used for both sampling kinds")
        kinds_by_sampler[sampler] |= kinds
        if kinds == {"ordinary"}:
            ordinary_images[sampler].append((image, sampler_type))

    mixed = [sampler for sampler, kinds in kinds_by_sampler.items() if len(kinds) == 2]
    if not mixed:
        return assembly, None
    if len(mixed) != 1:
        raise ValueError("Sampler split supports one sampler with mixed uses per module")
    sampler = mixed[0]
    if sampler not in parsed[entry][4:]:
        raise ValueError(f"{sampler}: sampler must be listed in the entry-point interface")
    if sampler not in bindings or sampler not in descriptor_sets:
        raise ValueError(f"{sampler}: sampler needs a DescriptorSet and Binding decoration")
    binding_line, comparison_binding = bindings[sampler]
    descriptor_set = descriptor_sets[sampler]
    for variable, (_, slot) in bindings.items():
        if descriptor_sets.get(variable) == descriptor_set and slot == ordinary_binding:
            raise ValueError(f"Ordinary sampler binding {ordinary_binding} is occupied in set "
                             f"{descriptor_set} by {variable}")
    if any(word.startswith(PREFIX) for words in parsed for word in words):
        raise ValueError("Reserved sampler split ID is already in use")

    lines[entry] = " ".join([*parsed[entry], PREFIX])
    lines[binding_line] += (f"\nOpDecorate {PREFIX} DescriptorSet {descriptor_set}"
                            f"\nOpDecorate {PREFIX} Binding {ordinary_binding}")
    lines[defined_at[sampler]] += f"\n{PREFIX} = OpVariable {definitions[sampler][1]} UniformConstant"
    for index, (image, sampler_type) in enumerate(ordinary_images[sampler]):
        i = defined_at[image]
        load = f"{PREFIX}_{index}"
        lines[i] = f"{load} = OpLoad {sampler_type} {PREFIX}\n" + " ".join([*parsed[i][:-1], load])
    mapping = {"descriptor_set": descriptor_set, "comparison_binding": comparison_binding,
               "ordinary_binding": ordinary_binding}
    return "\n".join(lines) + "\n", mapping


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("input", type=Path, help="SPIR-V assembly")
    parser.add_argument("output", type=Path, help="lowered SPIR-V assembly")
    parser.add_argument("--ordinary-binding", type=int, required=True,
                        help="free binding, in the comparison sampler's descriptor set, for the ordinary sampler")
    args = parser.parse_args()
    try:
        assembly, mapping = split_comparison_sampler(args.input.read_text(encoding="utf-8"),
                                                     args.ordinary_binding)
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    args.output.write_text(assembly, encoding="utf-8", newline="\n")
    if mapping:
        print(" ".join(f"{key}={value}" for key, value in mapping.items()))
    else:
        print("unchanged: no sampler with mixed uses")
    return 0


if __name__ == "__main__":
    sys.exit(main())
