#!/usr/bin/env python3
"""
Extract shaders from Xbox Scarlett shaders.rpf archive.

Extracts DXBC containers and raw AMD GFX1013 (RDNA 2) machine code binaries
organized by shader stage (pixel, vertex, compute, mesh, geometry).
"""

import argparse
from collections import Counter
import hashlib
import json
import mmap
import os
from pathlib import Path
import re
import struct
import sys
import time
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from resource_inventory import parts
except ImportError:
    parts = None


STAGE_NAMES = {
    0: "pixel",
    1: "vertex",
    2: "geometry",
    3: "hull",
    4: "domain",
    5: "compute",
    6: "library",
    13: "mesh",
    14: "amplification",
}


def sanitize_filename(name: str) -> str:
    """Sanitize shader record name for valid Windows/Linux filesystem usage."""
    # Replace characters not allowed in filenames
    clean = re.sub(r'[<>:"/\\|?*]', '_', name)
    clean = clean.strip(". ")
    return clean if clean else "unnamed_shader"


def extract_native_rdna2_code(program: bytes) -> bytes | None:
    """Extract raw AMD GFX1013 / RDNA 2 machine code from DXIL XDAT/XBCH/FSSM sections."""
    try:
        table_idx = program.index(b"XDAT", 24)
    except ValueError:
        return None

    if table_idx + 12 > len(program):
        return None
    count, = struct.unpack_from("<I", program, table_idx + 4)
    if table_idx + 12 + count * 12 > len(program):
        return None

    entries = struct.iter_unpack("<3I", program[table_idx + 12:table_idx + 12 + count * 12])
    native_entries = [(o, n) for tag, o, n in entries if tag == 13]
    if not native_entries:
        return None

    offset, length = native_entries[0]
    if offset + length > len(program) or length < 24 or program[offset:offset + 4] != b"XBCH":
        return None

    size, = struct.unpack_from("<I", program, offset + 16)
    try:
        image = zlib.decompress(program[offset + 24:offset + length], 15)
    except zlib.error:
        return None

    if len(image) < 196 or image[:4] != b"FSSM":
        return None

    start = struct.unpack_from("<I", image, 192)[0] + 40
    if start < 196 or start % 4 or start + 4 > len(image):
        return None

    # Locate s_endpgm (0xbf810000 in little-endian: \0\0\x81\xbf)
    ends = [i + 4 for i in range(start, len(image) - 3, 4) if image[i:i + 4] == b"\0\0\x81\xbf"]
    if not ends:
        return None

    return image[start:ends[-1]]


def extract_shaders(
    archive_path: Path,
    output_dir: Path,
    target_stages: set[str] | None = None,
    limit: int | None = None,
    extract_format: str = "native",
):
    """
    Scan shaders.rpf and extract shaders into organized folders.
    """
    output_dir = output_dir.resolve()
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        import tempfile
        fallback = Path(tempfile.gettempdir()) / "xbox2windows-shaders"
        fallback.mkdir(parents=True, exist_ok=True)
        print(f"[!] Warning: Cannot write to '{output_dir}'. Falling back to '{fallback}'.", file=sys.stderr)
        output_dir = fallback

    print(f"[*] Opening archive: {archive_path.name} ({archive_path.stat().st_size / (1024*1024):.1f} MB)...")
    start_time = time.time()

    names_pattern = re.compile(rb"[!-~]{4,}")
    stage_counters = Counter()
    stage_name_counts = Counter()
    extracted_records = []
    total_found = 0
    extracted_count = 0

    with archive_path.open("rb") as f, mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as data:
        data_len = len(data)
        cursor = 0

        while match := names_pattern.search(data, cursor):
            cursor = match.end()
            if cursor + 18 > data_len or data[cursor] != 0:
                continue

            stored, _, repeated, decoded = struct.unpack_from("<4I", data, cursor + 2)
            if not (16 < stored <= 8 << 20 and stored == repeated and cursor + 18 + stored <= data_len):
                continue

            record_name = match.group().decode("ascii", "replace")
            start_payload = cursor + 18
            cursor = start_payload + stored
            total_found += 1

            # Decompress raw-DEFLATE container
            try:
                blob = zlib.decompress(data[start_payload:start_payload + stored], -15)
            except zlib.error:
                continue

            if len(blob) != decoded:
                continue

            # Parse DXBC sections
            if parts is not None:
                try:
                    sections = parts(blob)
                except ValueError:
                    continue
            else:
                continue

            program = sections.get(b"DXIL", b"")
            if len(program) < 24:
                continue

            kind = struct.unpack_from("<H", program, 2)[0]
            stage = STAGE_NAMES.get(kind, f"stage_{kind}")
            stage_counters[stage] += 1

            # Filter by stage if requested
            if target_stages and stage not in target_stages and "all" not in target_stages:
                continue

            # Extract native RDNA 2 code
            native_code = extract_native_rdna2_code(program)

            # Stage folder
            stage_dir = output_dir / stage
            stage_dir.mkdir(parents=True, exist_ok=True)

            safe_name = sanitize_filename(record_name)
            name_occ = stage_name_counts[(stage, safe_name)]
            stage_name_counts[(stage, safe_name)] += 1
            file_stem = safe_name if name_occ == 0 else f"{safe_name}_{name_occ}"

            record_info = {
                "name": record_name,
                "stage": stage,
                "dxbc_size": len(blob),
                "native_size": len(native_code) if native_code else 0,
            }

            # Save formats
            if extract_format in ("dxbc", "both"):
                dxbc_path = stage_dir / f"{file_stem}.dxbc"
                with dxbc_path.open("wb") as out_f:
                    out_f.write(blob)
                record_info["dxbc_file"] = f"{stage}/{file_stem}.dxbc"

            if extract_format in ("native", "both"):
                if native_code:
                    bin_path = stage_dir / f"{file_stem}.bin"
                    with bin_path.open("wb") as out_f:
                        out_f.write(native_code)
                    record_info["native_file"] = f"{stage}/{file_stem}.bin"
                    record_info["sha256"] = hashlib.sha256(native_code).hexdigest()
                else:
                    # Fallback to dxbc if native code not unpackable
                    dxbc_path = stage_dir / f"{file_stem}.dxbc"
                    with dxbc_path.open("wb") as out_f:
                        out_f.write(blob)
                    record_info["dxbc_file"] = f"{stage}/{file_stem}.dxbc"

            extracted_records.append(record_info)
            extracted_count += 1

            if extracted_count % 1000 == 0:
                elapsed = time.time() - start_time
                print(f"    [+] Extracted {extracted_count} shaders ({elapsed:.1f}s)...")

            if limit is not None and extracted_count >= limit:
                print(f"[*] Reached limit of {limit} shaders.")
                break

    # Save manifest.json
    manifest_path = output_dir / "manifest.json"
    manifest_data = {
        "archive": archive_path.name,
        "total_extracted": extracted_count,
        "format": extract_format,
        "stage_distribution": dict(stage_counters),
        "shaders": extracted_records,
    }
    with manifest_path.open("w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2)

    elapsed = time.time() - start_time
    print("\n" + "=" * 60)
    print(" EXTRACTION COMPLETED ")
    print("=" * 60)
    print(f"Total Shaders Found:     {total_found}")
    print(f"Total Shaders Extracted: {extracted_count}")
    print(f"Time Elapsed:            {elapsed:.2f} seconds")
    print("\nExtracted by Stage:")
    for stg, cnt in stage_counters.most_common():
        print(f"  * {stg:<15}: {cnt:>5}")
    print(f"\n[+] Shaders directory: {output_dir}")
    print(f"[+] Manifest file:     {manifest_path}")
    print("=" * 60)

    return output_dir, manifest_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path, help="Path to shaders.rpf file")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("shaders"),
        help="Target folder for extracted shaders (default: shaders)",
    )
    parser.add_argument(
        "--stage",
        nargs="+",
        default=["all"],
        choices=["all", "pixel", "vertex", "compute", "mesh", "geometry"],
        help="Filter by shader stage (default: all)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional maximum number of shaders to extract (e.g. 50 or 500)",
    )
    parser.add_argument(
        "--format",
        choices=["native", "dxbc", "both"],
        default="native",
        help="Extraction format: 'native' (raw AMD RDNA 2 .bin, default), 'dxbc' (DXBC container), or 'both'",
    )

    args = parser.parse_args()

    if not args.archive.is_file():
        print(f"[-] Error: File not found: {args.archive}", file=sys.stderr)
        return 1

    target_stages = set(args.stage)
    extract_shaders(
        archive_path=args.archive,
        output_dir=args.output_dir,
        target_stages=target_stages,
        limit=args.limit,
        extract_format=args.format,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
