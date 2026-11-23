"""Batch exporter for TTPF (RDS5) texture pools to DDS with manifest generation.

Accepts an RDS5/ETPF texture pool archive and a range of texture indices. Tries
strict export by default and optionally retries with provisional history
calibration when --allow-provisional is specified. Writes each new export to a
temporary path and publishes it only on successful completion. Records index,
dimensions, codec, strict/provisional status, failure reason, and output DDS
SHA-256 in a structured JSON manifest.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import sys
import time

FORMAT_NAMES = {
    70: "BC1",
    71: "BC1",
    72: "BC1_SRGB",
    73: "BC2",
    74: "BC2",
    75: "BC2_SRGB",
    76: "BC3",
    77: "BC3",
    78: "BC3_SRGB",
    79: "BC4",
    80: "BC4",
    81: "BC4_SNORM",
    82: "BC5",
    83: "BC5",
    84: "BC5_SNORM",
    94: "BC6H",
    95: "BC6H",
    96: "BC6H_SF16",
    97: "BC7",
    98: "BC7",
    99: "BC7_SRGB",
}


def parse_indices(spec: str, total_count: int | None = None) -> list[int]:
    """Parse index specifications like '0,8253', '0-10', or '0-5,10,20-25'."""
    result: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start_str, end_str = part.split("-", 1)
            start, end = int(start_str.strip()), int(end_str.strip())
            if start > end:
                raise ValueError(f"Invalid range '{part}': start ({start}) > end ({end})")
            if total_count is not None:
                end = min(end, total_count - 1)
            result.update(range(start, end + 1))
        else:
            idx = int(part)
            if total_count is None or idx < total_count:
                result.add(idx)
    return sorted(result)


def load_tools(tools_path: Path | None = None):
    """Import ttpf_mips and bcpack from tools_path, environment or sys.path."""
    candidate_paths = []
    if tools_path is not None:
        candidate_paths.append(Path(tools_path).resolve())
    for env_key in ("TTPF_TOOLS_DIR", "BCPACK_REFERENCE_TOOLS"):
        val = os.environ.get(env_key)
        if val:
            candidate_paths.append(Path(val).resolve())
    script_dir = Path(__file__).resolve().parent
    candidate_paths.append(script_dir)

    for path in candidate_paths:
        if path.is_dir() and (path / "ttpf_mips.py").exists():
            if str(path) not in sys.path:
                sys.path.insert(0, str(path))
            break

    try:
        import ttpf_mips
        return ttpf_mips
    except ImportError:
        return None


def export_texture_entry(pool, index: int, out_dir: Path,
                         allow_provisional: bool = False,
                         history: dict | None = None,
                         ttpf_module=None) -> dict:
    """Export one texture entry from the pool to a DDS file and return its manifest entry.

    Writes to a temporary file first and publishes to dds_path only upon success.
    """
    dds_name = f"tex_{index:05d}.dds"
    dds_path = out_dir / dds_name
    temp_path = out_dir / f".tmp_{index}_{os.getpid()}_{time.time_ns()}.dds"

    if ttpf_module is None:
        ttpf_module = load_tools()
    if ttpf_module is None:
        raise RuntimeError("ttpf_mips module is required to export entries")

    analyze_fn = getattr(ttpf_module, "analyze")
    export_fn = getattr(ttpf_module, "export")
    bc_formats = getattr(ttpf_module, "BC_FORMATS", set(FORMAT_NAMES.keys()))

    try:
        a = analyze_fn(pool, index)
    except Exception as exc:
        return {
            "index": index,
            "status": "failed",
            "reason": str(exc),
        }

    if "layout" not in a or "available" not in a:
        return {
            "index": index,
            "status": "no_layout",
            "reason": a.get("blocked", "layout unavailable"),
        }

    d = a.get("descriptor", {})
    shape = a.get("shape", "2d")
    fmt = d.get("format")
    w, h = d.get("width", 0), d.get("height", 0)
    mips = d.get("mips", 0)

    if shape != "volume" and fmt not in bc_formats:
        return {
            "index": index,
            "status": "uncompressed",
            "format": fmt,
            "format_name": FORMAT_NAMES.get(fmt, str(fmt)),
            "shape": shape,
            "width": w,
            "height": h,
        }

    if not a.get("full_chain", False):
        return {
            "index": index,
            "status": "unsupported_codec",
            "format": fmt,
            "format_name": FORMAT_NAMES.get(fmt, str(fmt)),
            "width": w,
            "height": h,
        }

    try:
        # 1. Try strict export first (default)
        mode_used = "strict"
        ret = export_fn(pool, index, str(temp_path), allow_provisional=False)

        # 2. Retry with provisional history only when explicitly opted in
        if ret != 0 and allow_provisional:
            mode_used = "provisional"
            ret = export_fn(pool, index, str(temp_path), allow_provisional=True, history=history)

        if ret != 0 or not temp_path.exists():
            return {
                "index": index,
                "status": "failed",
                "format": fmt,
                "format_name": FORMAT_NAMES.get(fmt, str(fmt)),
                "width": w,
                "height": h,
                "reason": f"export returned exit code {ret}",
            }

        # Atomic publish: move temporary file to final published path
        os.replace(temp_path, dds_path)
        data = dds_path.read_bytes()
        return {
            "index": index,
            "status": "success",
            "mode": mode_used,
            "format": fmt,
            "format_name": FORMAT_NAMES.get(fmt, f"Format {fmt}"),
            "width": w,
            "height": h,
            "mips": mips,
            "dds_size": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "file": dds_name,
        }
    finally:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass


def batch_export(pool_path: Path, out_dir: Path,
                 indices: list[int] | None = None,
                 start: int = 0, count: int | None = None,
                 allow_provisional: bool = False,
                 history_path: Path | None = None,
                 threads: int = 4,
                 manifest_path: Path | None = None,
                 tools_path: Path | None = None) -> dict:
    """Run batch export over a range of texture pool indices and write manifest.json."""
    ttpf = load_tools(tools_path)
    if ttpf is None:
        raise RuntimeError("Could not find ttpf_mips module. Provide --tools-path or set TTPF_TOOLS_DIR.")

    out_dir.mkdir(parents=True, exist_ok=True)
    if manifest_path is None:
        manifest_path = out_dir / "manifest.json"

    history_dict = None
    if allow_provisional and history_path and history_path.exists():
        try:
            history_dict = json.loads(history_path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"Warning: could not read calibration history from {history_path}: {e}", file=sys.stderr)

    pool = ttpf.Pool(str(pool_path))
    total_textures = pool.textures

    if indices is None:
        start_idx = max(0, start)
        end_idx = total_textures if count is None else min(total_textures, start_idx + count)
        target_indices = list(range(start_idx, end_idx))
    else:
        target_indices = [i for i in indices if 0 <= i < total_textures]

    start_time = time.time()
    manifest_entries: list[dict] = []
    stats = {"strict": 0, "provisional": 0, "failed": 0, "skipped": 0}

    def _worker(idx: int) -> dict:
        local_pool = ttpf.Pool(str(pool_path))
        try:
            return export_texture_entry(local_pool, idx, out_dir,
                                        allow_provisional=allow_provisional,
                                        history=history_dict,
                                        ttpf_module=ttpf)
        finally:
            local_pool.close()

    max_workers = max(1, min(threads, len(target_indices) or 1))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_worker, idx): idx for idx in target_indices}
        for future in as_completed(futures):
            res = future.result()
            manifest_entries.append(res)
            st = res.get("status")
            if st == "success":
                mode = res.get("mode")
                if mode == "strict":
                    stats["strict"] += 1
                elif mode == "provisional":
                    stats["provisional"] += 1
            elif st in ("no_layout", "uncompressed", "unsupported_codec"):
                stats["skipped"] += 1
            else:
                stats["failed"] += 1

    pool.close()

    manifest_entries.sort(key=lambda x: x.get("index", 0))
    manifest_path.write_text(json.dumps(manifest_entries, indent=2), encoding="utf-8")
    elapsed = time.time() - start_time

    return {
        "pool": str(pool_path),
        "total_textures": total_textures,
        "processed": len(target_indices),
        "manifest": str(manifest_path),
        "entries": len(manifest_entries),
        "elapsed_seconds": round(elapsed, 3),
        "stats": stats,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pool", type=Path, help="Path to .ttpf texture pool archive")
    parser.add_argument("-o", "--out", type=Path, default=Path("extracted_dds"),
                        help="Output directory for exported DDS files")
    parser.add_argument("--indices", type=str, default=None,
                        help="Comma-separated indices or ranges, e.g. '0,8253' or '0-10'")
    parser.add_argument("--start", type=int, default=0, help="Starting index (default: 0)")
    parser.add_argument("--count", type=int, default=None, help="Number of textures to export")
    parser.add_argument("--allow-provisional", action="store_true", default=False,
                        help="Opt in to fitted provisional history if strict export is rejected")
    parser.add_argument("--history", type=Path, default=None,
                        help="Path to history.json calibration file")
    parser.add_argument("--threads", type=int, default=min(16, os.cpu_count() or 4),
                        help="Number of worker threads")
    parser.add_argument("--manifest", type=Path, default=None,
                        help="Output path for JSON manifest (default: <out>/manifest.json)")
    parser.add_argument("--tools-path", type=Path, default=None,
                        help="Path to directory containing ttpf_mips.py and bcpack.py")
    args = parser.parse_args()

    if not args.pool.exists():
        parser.error(f"Pool not found: {args.pool}")

    indices = parse_indices(args.indices) if args.indices else None

    summary = batch_export(
        pool_path=args.pool,
        out_dir=args.out,
        indices=indices,
        start=args.start,
        count=args.count,
        allow_provisional=args.allow_provisional,
        history_path=args.history,
        threads=args.threads,
        manifest_path=args.manifest,
        tools_path=args.tools_path,
    )

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
