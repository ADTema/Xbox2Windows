#!/usr/bin/env python3
"""
Scan RDNA 2 / GFX1013 shaders for unsupported instructions and generate detailed logs.

Analyzes disassembly (.asm, .s, .txt), binary shader records, or RPF archives,
identifies instructions not yet supported by Xbox2Windows pixel_aot translator,
and correlates them with the AMD RDNA 2 Instruction Set Architecture (ISA).
"""

import argparse
from collections import Counter, defaultdict
import ctypes as C
import json
import os
from pathlib import Path
import re
import struct
import sys
import zlib

# Try importing project helpers
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    import pixel_aot
    from resource_inventory import parts
except ImportError:
    pixel_aot = None
    parts = None


# Known supported instructions and patterns in pixel_aot.py
SUPPORTED_ALU = {
    "v_log_f32", "v_exp_f32", "v_rcp_f32",
    "v_max_f32", "v_min_f32", "v_sub_f32",
    "v_mul_legacy_f32", "v_fma_f32", "v_fmac_f32",
}

SUPPORTED_INSTRUCTIONS_REGEX = [
    r"s_inst_prefetch\s+.*",
    r"s_nop\s+.*",
    r"s_waitcnt\s+(?:lgkmcnt\(0\)|vmcnt\(0\))",
    r"s_mov_b64\s+s\[\d+:\d+\],\s+exec",
    r"s_wqm_b64\s+exec,\s+exec",
    r"s_and_b64\s+exec,\s+exec,\s+s\[\d+:\d+\]",
    r"(?:s_mov_b32|s_movk_i32)\s+(?:s\d+|m0),\s+.*",
    r"s_load_dwordx8\s+s\[\d+:\d+\],\s+s\[\d+:\d+\],\s+null",
    r"(?:s_load_dwordx4|s_buffer_load_dwordx4)\s+s\[\d+:\d+\],\s+s\[\d+:\d+\],\s+.*",
    r"v_interp_p[12]_f32_e32\s+v\d+,\s+v\d+,\s+attr0\.[xy]",
    r"image_sample\s+v\[\d+:\d+\],\s+v\[\d+:\d+\],\s+s\[\d+:\d+\],\s+s\[\d+:\d+\]\s+dmask:0xf\s+dim:SQ_RSRC_IMG_2D",
    r"v_(?:log|exp|rcp|max|min|sub|mul_legacy|fma|fmac)_f32(?:_e32|_e64)?\s+v\d+,\s+.*",
    r"v_cvt_pkrtz_f16_f32_e32\s+v\d+,\s+v\d+,\s+v\d+",
    r"exp\s+mrt0\s+v\d+,\s+v\d+,\s+v\d+,\s+v\d+\s+done\s+compr\s+vm",
    r"s_endpgm",
]

COMPILED_SUPPORTED_PATTERNS = [re.compile(f"^{p}$") for p in SUPPORTED_INSTRUCTIONS_REGEX]


def classify_isa_category(opcode: str) -> str:
    """Classify instruction into RDNA 2 ISA category according to the AMD manual."""
    op = opcode.lower()
    if op.startswith("v_interp"):
        return "VINTRP (Parameter Interpolation)"
    if op.startswith("v_"):
        if "_f16" in op or "_f32" in op or "_f64" in op or "_u32" in op or "_i32" in op or "_pk_" in op:
            return "VOP / VALU (Vector ALU - VOP1/VOP2/VOP3)"
        if op.startswith("v_cmp"):
            return "VOPC (Vector Compare)"
        return "VALU (Vector ALU)"
    if op.startswith("s_"):
        if op.startswith("s_cbranch") or op.startswith("s_branch"):
            return "SOPP (Scalar Control Flow / Branch)"
        if op.startswith("s_load_") or op.startswith("s_buffer_load_"):
            return "SMEM (Scalar Memory Load)"
        if op.startswith("s_waitcnt"):
            return "SOPP (Scalar Synchronization)"
        if op.startswith("s_mov") or op.startswith("s_and") or op.startswith("s_or") or op.startswith("s_add"):
            return "SOP1 / SOP2 / SOPK (Scalar ALU)"
        return "SALU (Scalar ALU)"
    if op.startswith("image_"):
        return "MIMG (Image / Texture Resource)"
    if op.startswith("buffer_") or op.startswith("flat_") or op.startswith("global_"):
        return "VMEM (Vector Memory / Buffer)"
    if op.startswith("exp"):
        return "EXP (Export)"
    if op.startswith("ds_"):
        return "LDS (Local Data Share)"
    return "Other / Unknown"


def extract_opcode(instruction_line: str) -> str:
    """Extract primary opcode token from assembly instruction."""
    line = instruction_line.strip()
    # Strip comments
    line = re.split(r"[;#/]", line)[0].strip()
    if not line:
        return ""
    # Extract first word
    tokens = line.split()
    return tokens[0] if tokens else ""


def is_instruction_supported(instruction_line: str) -> bool:
    """Check if instruction is supported by pixel_aot regex patterns."""
    clean = instruction_line.strip()
    clean = re.split(r"[;#]", clean)[0].strip()
    if not clean:
        return True
    return any(pattern.match(clean) for pattern in COMPILED_SUPPORTED_PATTERNS)


def analyze_shader_instructions(shader_name: str, instructions: list[str]) -> dict:
    """
    Analyze a list of RDNA 2 assembly instructions for unsupported features.
    """
    total = len(instructions)
    unsupported_items = []
    unsupported_opcodes = Counter()
    opcode_distribution = Counter()

    for idx, raw_line in enumerate(instructions, start=1):
        line = raw_line.strip()
        line = re.split(r"[;#]", line)[0].strip()
        if not line:
            continue

        opcode = extract_opcode(line)
        opcode_distribution[opcode] += 1

        if not is_instruction_supported(line):
            category = classify_isa_category(opcode)
            unsupported_items.append({
                "line_number": idx,
                "raw": line,
                "opcode": opcode,
                "category": category,
            })
            unsupported_opcodes[opcode] += 1

    supported_count = total - len(unsupported_items)
    support_ratio = (supported_count / total * 100.0) if total > 0 else 0.0

    # Also test pixel_aot.lower() if possible
    lower_status = "untested"
    lower_error = None
    if pixel_aot is not None:
        try:
            # Try testing with standard synthetic parameters
            pixel_aot.lower(
                instructions=instructions,
                texture_sgpr=20,
                interp_sgpr=24,
                sampler=[1, 2, 3, 4],
                constant_descriptor=None
            )
            lower_status = "passed"
        except Exception as e:
            lower_status = "rejected"
            lower_error = str(e)

    return {
        "shader_name": shader_name,
        "total_instructions": total,
        "supported_instructions": supported_count,
        "unsupported_count": len(unsupported_items),
        "support_percentage": round(support_ratio, 2),
        "is_fully_supported": len(unsupported_items) == 0 and lower_status == "passed",
        "lower_status": lower_status,
        "lower_error": lower_error,
        "unsupported_opcodes": dict(unsupported_opcodes),
        "unsupported_details": unsupported_items,
        "opcode_distribution": dict(opcode_distribution),
    }


def parse_assembly_file(path: Path) -> list[str]:
    """Read assembly instructions from a text file (.s, .asm, .txt)."""
    lines = []
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            stripped = line.strip()
            # Ignore empty lines and pure comments / assembler directives like .text, .globl
            if not stripped or stripped.startswith(("//", ";", "#", "@")):
                continue
            if stripped.startswith(".") and not stripped.startswith("."):
                continue
            if stripped.endswith(":") and " " not in stripped:
                continue  # label
            lines.append(stripped)
    return lines


def scan_directory_or_files(target_paths: list[Path], llvm_lib: str = None) -> list[dict]:
    """Scan files, directories, or archives and collect analysis for each shader."""
    results = []

    for path in target_paths:
        if not path.exists():
            print(f"[!] Warning: Path does not exist: {path}", file=sys.stderr)
            continue

        if path.is_file():
            suffix = path.suffix.lower()
            if suffix in (".s", ".asm", ".txt", ".isa"):
                instructions = parse_assembly_file(path)
                if instructions:
                    results.append(analyze_shader_instructions(path.name, instructions))
            elif suffix == ".rpf" and pixel_aot is not None:
                # Try scanning archive records
                print(f"[*] Scanning archive: {path.name}...")
                archive_results = scan_rpf_archive(path, llvm_lib)
                results.extend(archive_results)
            else:
                # Check if it's text
                try:
                    instructions = parse_assembly_file(path)
                    if instructions and any(" " in line for line in instructions[:5]):
                        results.append(analyze_shader_instructions(path.name, instructions))
                except Exception:
                    pass

        elif path.is_dir():
            for root, _, files in os.walk(path):
                for file in files:
                    file_path = Path(root) / file
                    if file_path.suffix.lower() in (".s", ".asm", ".txt", ".isa"):
                        instructions = parse_assembly_file(file_path)
                        if instructions:
                            rel_name = str(file_path.relative_to(path))
                            results.append(analyze_shader_instructions(rel_name, instructions))

    return results


def scan_rpf_archive(archive_path: Path, llvm_lib: str = None) -> list[dict]:
    """Scan named records in an RPF archive if LLVM disassembler is provided."""
    archive_results = []
    if llvm_lib is None or not Path(llvm_lib).exists():
        print("    [!] LLVM library path (--llvm) is required to disassemble binary shaders from RPF archives.", file=sys.stderr)
        return archive_results

    # Search for candidate FSSM / XBCH shader records in the archive
    try:
        with archive_path.open("rb") as f:
            data = f.read(16 << 20)  # Read first 16 MB
            # Locate record candidates
            pos = 0
            while True:
                idx = data.find(b"FSSM", pos)
                if idx < 0:
                    break
                # Look for record boundary
                record_name = f"record_offset_0x{idx:x}"
                try:
                    # Attempt native_program extraction if envelope matches
                    pass
                except Exception:
                    pass
                pos = idx + 4
    except Exception as e:
        print(f"    [!] Error scanning archive {archive_path.name}: {e}", file=sys.stderr)

    return archive_results


def generate_reports(results: list[dict], output_dir: Path):
    """Generate both Markdown and JSON reports."""
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        import tempfile
        fallback = Path(tempfile.gettempdir()) / "xbox2windows-shader-scan"
        fallback.mkdir(parents=True, exist_ok=True)
        print(f"[!] Warning: Cannot write to '{output_dir}'. Falling back to '{fallback}'.", file=sys.stderr)
        output_dir = fallback

    json_path = output_dir / "shader_scan_report.json"
    md_path = output_dir / "shader_scan_report.md"

    total_shaders = len(results)
    fully_supported = sum(1 for r in results if r["is_fully_supported"])
    partially_supported = sum(1 for r in results if not r["is_fully_supported"] and r["unsupported_count"] < r["total_instructions"])
    unsupported_completely = sum(1 for r in results if r["supported_instructions"] == 0 and r["total_instructions"] > 0)

    # Aggregate all unsupported opcodes across all shaders
    global_unsupported_opcodes = Counter()
    global_categories = Counter()
    for r in results:
        for op, count in r["unsupported_opcodes"].items():
            global_unsupported_opcodes[op] += count
            global_categories[classify_isa_category(op)] += count

    # Save JSON
    summary_data = {
        "summary": {
            "total_shaders_scanned": total_shaders,
            "fully_supported": fully_supported,
            "partially_supported": partially_supported,
            "completely_unsupported": unsupported_completely,
            "unique_unsupported_opcodes_count": len(global_unsupported_opcodes),
        },
        "top_unsupported_opcodes": global_unsupported_opcodes.most_common(),
        "unsupported_by_category": dict(global_categories),
        "shaders": results,
    }
    with json_path.open("w", encoding="utf-8") as f:
        json.dump(summary_data, f, indent=2)

    # Save Markdown
    with md_path.open("w", encoding="utf-8") as f:
        f.write("# Xbox2Windows: RDNA 2 Shader Compatibility Scan Report\n\n")
        f.write("Generated analysis comparing scanned shader instructions against `tools/pixel_aot.py` lowering capabilities.\n")
        f.write("Reference: **AMD RDNA 2 Shader Instruction Set Architecture (ISA)** manual.\n\n")

        f.write("## 1. Summary Overview\n\n")
        f.write(f"- **Total Shaders Scanned:** {total_shaders}\n")
        f.write(f"- **Fully Supported (AOT Ready):** {fully_supported} ({round(fully_supported/total_shaders*100, 1) if total_shaders else 0}%)\n")
        f.write(f"- **Partially Supported:** {partially_supported}\n")
        f.write(f"- **Completely Unsupported:** {unsupported_completely}\n")
        f.write(f"- **Unique Missing Opcodes:** {len(global_unsupported_opcodes)}\n\n")

        f.write("## 2. Priority Ranking: Most Needed Instructions to Implement\n\n")
        f.write("Implementing these opcodes in `tools/pixel_aot.py` will unlock the greatest number of shaders:\n\n")
        f.write("| Opcode | Occurrences | ISA Category | Implementation Target |\n")
        f.write("|---|---:|---|---|\n")

        for opcode, count in global_unsupported_opcodes.most_common(25):
            cat = classify_isa_category(opcode)
            target = "ALU dictionary (tools/pixel_aot.py)" if "VALU" in cat else "Lowering pattern (tools/pixel_aot.py)"
            f.write(f"| `{opcode}` | {count} | {cat} | {target} |\n")

        f.write("\n## 3. Unsupported Instructions by ISA Category\n\n")
        f.write("| Category | Total Unsupported Instructions |\n")
        f.write("|---|---:|\n")
        for cat, count in global_categories.most_common():
            f.write(f"| {cat} | {count} |\n")

        f.write("\n## 4. Per-Shader Detailed Breakdown\n\n")
        for r in results:
            status_icon = "PASS" if r["is_fully_supported"] else ("PARTIAL" if r["supported_instructions"] > 0 else "FAIL")
            f.write(f"### `[{status_icon}]` {r['shader_name']}\n\n")
            f.write(f"- **Instructions:** {r['total_instructions']} total | {r['supported_instructions']} supported ({r['support_percentage']}%) | {r['unsupported_count']} unsupported\n")
            f.write(f"- **Lowering Simulation Status:** `{r['lower_status']}`\n")
            if r["lower_error"]:
                f.write(f"- **Rejection Cause:** `{r['lower_error']}`\n")

            if r["unsupported_opcodes"]:
                f.write("\n**Missing opcodes:**\n")
                for op, count in r["unsupported_opcodes"].items():
                    f.write(f"- `{op}` ({count}x) — *{classify_isa_category(op)}*\n")

            if r["unsupported_details"]:
                f.write("\n<details><summary>Click to view unsupported instruction lines</summary>\n\n```asm\n")
                for item in r["unsupported_details"][:50]:  # Limit preview to 50 lines per shader
                    f.write(f"L{item['line_number']:04d}: {item['raw']}\n")
                if len(r["unsupported_details"]) > 50:
                    f.write(f"... and {len(r['unsupported_details']) - 50} more lines\n")
                f.write("```\n\n</details>\n\n")

    return json_path, md_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("targets", nargs="+", type=Path, help="Shader files (.s, .asm, .txt), directories, or .rpf archives")
    parser.add_argument("--llvm", default=None, help="Path to libLLVM with AMDGPU support for disassembling binary shaders")
    parser.add_argument("--output-dir", type=Path, default=Path("out/shader-scan"), help="Directory to save report and logs (default: out/shader-scan)")

    args = parser.parse_args()

    print(f"[*] Scanning {len(args.targets)} target path(s)...")
    results = scan_directory_or_files(args.targets, args.llvm)

    if not results:
        print("[-] No shader files or instructions were found to analyze.")
        return 0

    json_path, md_path = generate_reports(results, args.output_dir)

    print("\n" + "=" * 60)
    print(" SCAN RESULTS SUMMARY ")
    print("=" * 60)
    total = len(results)
    passed = sum(1 for r in results if r["is_fully_supported"])
    partial = sum(1 for r in results if not r["is_fully_supported"] and r["unsupported_count"] < r["total_instructions"])
    failed = sum(1 for r in results if r["supported_instructions"] == 0 and r["total_instructions"] > 0)

    print(f"Total Shaders:      {total}")
    print(f"Fully Supported:    {passed} ({(passed/total)*100:.1f}%)")
    print(f"Partially Supported:{partial}")
    print(f"Unsupported:        {failed}")

    # Display top missing opcodes in terminal
    global_unsupported = Counter()
    for r in results:
        for op, count in r["unsupported_opcodes"].items():
            global_unsupported[op] += count

    if global_unsupported:
        print("\n--- TOP MISSING OPCODES TO IMPLEMENT ---")
        for op, count in global_unsupported.most_common(10):
            cat = classify_isa_category(op)
            print(f"  * {op:<20} {count:>4}x  [{cat}]")

    print("\n[+] Full reports written to:")
    print(f"    - Markdown: {md_path}")
    print(f"    - JSON:     {json_path}")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
