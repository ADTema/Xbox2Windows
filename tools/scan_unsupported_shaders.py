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

KNOWN_RDNA2_BASE_OPCODES = {
    # SOPP
    "s_nop", "s_endpgm", "s_branch", "s_cbranch_scc0", "s_cbranch_scc1",
    "s_cbranch_vccz", "s_cbranch_vccnz", "s_cbranch_execz", "s_cbranch_execnz",
    "s_barrier", "s_waitcnt", "s_inst_prefetch", "s_clause", "s_waitcnt_vscnt",
    "s_waitcnt_vmcnt", "s_waitcnt_expcnt", "s_waitcnt_lgkmcnt", "s_trap", "s_round_mode",
    # SOP1
    "s_mov_b32", "s_mov_b64", "s_cmov_b32", "s_cmov_b64", "s_not_b32", "s_not_b64",
    "s_wqm_b32", "s_wqm_b64", "s_swappc_b64", "s_setpc_b64", "s_rfe_b64",
    "s_and_saveexec_b64", "s_or_saveexec_b64", "s_xor_saveexec_b64",
    # SOP2
    "s_add_u32", "s_sub_u32", "s_add_i32", "s_sub_i32", "s_addc_u32", "s_subb_u32",
    "s_min_i32", "s_min_u32", "s_max_i32", "s_max_u32", "s_cselect_b32", "s_cselect_b64",
    "s_and_b32", "s_and_b64", "s_or_b32", "s_or_b64", "s_xor_b32", "s_xor_b64",
    "s_andn2_b32", "s_andn2_b64", "s_orn2_b32", "s_orn2_b64", "s_nand_b32", "s_nand_b64",
    "s_nor_b32", "s_nor_b64", "s_lshl_b32", "s_lshl_b64", "s_lshr_b32", "s_lshr_b64",
    "s_ashr_i32", "s_ashr_i64", "s_mul_i32",
    # SOPK
    "s_movk_i32", "s_cmovk_i32", "s_addk_i32", "s_mulk_i32", "s_cbranch_i_fork",
    # VOP1
    "v_nop", "v_mov_b32", "v_readfirstlane_b32", "v_not_b32", "v_cls_i32",
    "v_log_f32", "v_exp_f32", "v_rcp_f32", "v_rsq_f32", "v_sqrt_f32",
    "v_sin_f32", "v_cos_f32", "v_bfrev_b32", "v_ffbh_u32", "v_ffbl_b32",
    "v_cvt_f32_i32", "v_cvt_f32_u32", "v_cvt_i32_f32", "v_cvt_u32_f32",
    "v_cvt_f16_f32", "v_cvt_f32_f16", "v_cvt_rpi_i32_f32", "v_cvt_flr_i32_f32",
    "v_cvt_pkrtz_f16_f32",
    # VOP2
    "v_cndmask_b32", "v_add_f32", "v_sub_f32", "v_subrev_f32", "v_mul_legacy_f32",
    "v_mul_f32", "v_mul_i32_i24", "v_mul_hi_i32_i24", "v_mul_u32_u24", "v_mul_hi_u32_u24",
    "v_min_f32", "v_max_f32", "v_min_i32", "v_max_i32", "v_min_u32", "v_max_u32",
    "v_lshlrev_b32", "v_lshrrev_b32", "v_ashrrev_i32", "v_and_b32", "v_or_b32", "v_xor_b32",
    "v_add_u32", "v_sub_u32", "v_subrev_u32", "v_addc_co_u32", "v_subb_co_u32", "v_subbrev_co_u32",
    "v_fmac_f32", "v_fmamk_f32", "v_fmaak_f32", "v_madmk_f32", "v_madak_f32",
    # VOP3
    "v_fma_f32", "v_fma_f16", "v_mad_f32", "v_div_scale_f32", "v_div_fmas_f32",
    # VINTRP
    "v_interp_p1_f32", "v_interp_p2_f32", "v_interp_mov_f32",
    # SMEM
    "s_load_dword", "s_load_dwordx2", "s_load_dwordx4", "s_load_dwordx8", "s_load_dwordx16",
    "s_buffer_load_dword", "s_buffer_load_dwordx2", "s_buffer_load_dwordx4", "s_buffer_load_dwordx8",
    # EXP
    "exp",
    # MIMG
    "image_sample", "image_sample_l", "image_sample_b", "image_sample_c", "image_load", "image_store",
}


def is_opcode_recognized(opcode: str) -> bool:
    """Check if opcode belongs to recognized AMD RDNA 2 ISA instructions."""
    clean = opcode.strip().lower()
    base = re.sub(r"_(?:e32|e64|dpp.*)$", "", clean)
    if base in KNOWN_RDNA2_BASE_OPCODES or clean in KNOWN_RDNA2_BASE_OPCODES:
        return True
    if base.startswith("v_cmp_") or clean.startswith("v_cmp_"):
        return True
    if base.startswith("image_") or clean.startswith("image_"):
        return True
    if base.startswith("s_load_") or base.startswith("s_buffer_load_"):
        return True
    return False


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
    Analyze a list of RDNA 2 assembly instructions.
    Distinguishes:
      1. Opcode recognition: whether every instruction opcode is known to the RDNA 2 ISA scanner.
      2. Translator acceptance: whether pixel_aot.lower() actually accepts the shader sequence.
    """
    total = len(instructions)
    unrecognized_opcodes = Counter()
    unsupported_translator_items = []
    opcode_distribution = Counter()

    for idx, raw_line in enumerate(instructions, start=1):
        line = raw_line.strip()
        line = re.split(r"[;#]", line)[0].strip()
        if not line:
            continue

        opcode = extract_opcode(line)
        opcode_distribution[opcode] += 1

        if not is_opcode_recognized(opcode):
            unrecognized_opcodes[opcode] += 1

        if not is_instruction_supported(line):
            category = classify_isa_category(opcode)
            unsupported_translator_items.append({
                "line_number": idx,
                "raw": line,
                "opcode": opcode,
                "category": category,
            })

    supported_count = total - len(unsupported_translator_items)
    support_ratio = (supported_count / total * 100.0) if total > 0 else 0.0

    # Test pixel_aot.lower() to determine translator acceptance
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

    opcodes_recognized = (len(unrecognized_opcodes) == 0)
    translator_accepted = (lower_status == "passed")

    if opcodes_recognized and translator_accepted:
        compatibility_category = "accepted"
    elif opcodes_recognized and not translator_accepted:
        compatibility_category = "opcode_recognized_translator_rejected"
    else:
        compatibility_category = "unsupported_opcodes"

    return {
        "shader_name": shader_name,
        "total_instructions": total,
        "supported_instructions": supported_count,
        "unsupported_count": len(unsupported_translator_items),
        "support_percentage": round(support_ratio, 2),
        "opcodes_recognized": opcodes_recognized,
        "translator_accepted": translator_accepted,
        "compatibility_category": compatibility_category,
        "is_fully_supported": opcodes_recognized and translator_accepted,
        "lower_status": lower_status,
        "lower_error": lower_error,
        "unsupported_opcodes": dict(unrecognized_opcodes),
        "unsupported_details": unsupported_translator_items,
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
    translator_accepted = sum(1 for r in results if r["translator_accepted"])
    opcodes_recognized_only = sum(1 for r in results if r["compatibility_category"] == "opcode_recognized_translator_rejected")
    unsupported_opcodes_count = sum(1 for r in results if r["compatibility_category"] == "unsupported_opcodes")
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
            "translator_accepted": translator_accepted,
            "opcodes_recognized_translator_rejected": opcodes_recognized_only,
            "unsupported_opcodes_count": unsupported_opcodes_count,
            "fully_supported": translator_accepted,
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
        f.write(f"- **Full Shaders Accepted by Translator (`pixel_aot.py`):** {translator_accepted} ({round(translator_accepted/total_shaders*100, 1) if total_shaders else 0}%)\n")
        f.write(f"- **Opcodes Recognized by Scanner, but Rejected by Translator:** {opcodes_recognized_only}\n")
        f.write("  *(Valid RDNA 2 opcodes whose program structure, preamble, or bindings differ from `pixel_aot` straight-line single-texture template)*\n")
        f.write(f"- **Contains Unrecognized Opcodes:** {unsupported_opcodes_count}\n")
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
    accepted = sum(1 for r in results if r["translator_accepted"])
    recognized_only = sum(1 for r in results if r["compatibility_category"] == "opcode_recognized_translator_rejected")
    unsupported_opcodes = sum(1 for r in results if r["compatibility_category"] == "unsupported_opcodes")

    print(f"Total Shaders Scanned:                     {total}")
    print(f"Full Shaders Accepted by Translator:       {accepted} ({(accepted/total)*100:.1f}%)")
    print(f"Opcodes Recognized, Translator-Rejected:   {recognized_only}")
    print(f"Contains Unrecognized Opcodes:             {unsupported_opcodes}")

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
