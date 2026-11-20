"""Inspect a candidate as the manifest's Scarlett executable, using only file reads."""

import argparse
import hashlib
import json
from pathlib import Path
import struct
from tempfile import NamedTemporaryFile
import xml.etree.ElementTree as ET

import pefile

from dependency_paths import trace

from pe_inventory import changes, scan
from verify_build import read_layout

PROJECT = Path(__file__).resolve().parents[1]


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def inside(root, name):
    path = (root / name).resolve()
    if not path.is_relative_to(root) or path == root or Path(name).is_absolute():
        raise ValueError(f"Invalid package path: {name}")
    return path


def inspect_executable(path):
    size = path.stat().st_size
    with pefile.PE(str(path), fast_load=True) as pe:
        hdr = pe.OPTIONAL_HEADER
        if (pe.FILE_HEADER.Machine != 0x8664 or hdr.Magic != 0x20B or
                not pe.FILE_HEADER.Characteristics & 2 or pe.FILE_HEADER.Characteristics & 0x2000):
            raise ValueError("Expected an x64 PE32+ executable")
        if (not pe.sections or len(pe.sections) != pe.FILE_HEADER.NumberOfSections or
                hdr.SizeOfHeaders < pe.sections[-1].get_file_offset() + 40 or hdr.SizeOfHeaders > size):
            raise ValueError("Incomplete PE headers or section table")
        for section in pe.sections:
            if section.SizeOfRawData and section.PointerToRawData + section.SizeOfRawData > size:
                raise ValueError("Section extends beyond end of file")

        def section_for(rva, length, *, executable=False):
            for s in pe.sections:
                offset = rva - s.VirtualAddress
                if (0 <= offset and offset + length <= s.SizeOfRawData and
                        rva + length <= hdr.SizeOfImage and
                        (not executable or s.Characteristics & 0x20000000)):
                    return s
            raise ValueError(f"Unmapped or unsuitable RVA {rva:#x}")

        def read_rva(rva, length):
            section_for(rva, length)
            data = pe.get_data(rva, length)
            if len(data) != length:
                raise ValueError(f"Truncated data at RVA {rva:#x}")
            return data

        entry = hdr.AddressOfEntryPoint
        entry_section = section_for(entry, 1, executable=True) if entry else None
        tls = None
        if len(hdr.DATA_DIRECTORY) > 9:
            d = hdr.DATA_DIRECTORY[9]
            if d.VirtualAddress or d.Size:
                if not d.VirtualAddress or d.Size < 40:
                    raise ValueError("Incomplete TLS directory")
                start, end, index, callbacks, zero_fill, flags = struct.unpack(
                    "<4Q2I", read_rva(d.VirtualAddress, 40))
                callback_rvas = []
                if callbacks:
                    table = callbacks - hdr.ImageBase
                    section = section_for(table, 8)
                    slots = (section.VirtualAddress + section.SizeOfRawData - table) // 8
                    for i in range(min(slots, 65536)):
                        va, = struct.unpack("<Q", read_rva(table + i * 8, 8))
                        if not va:
                            break
                        rva = va - hdr.ImageBase
                        section_for(rva, 1, executable=True)
                        callback_rvas.append(rva)
                    else:
                        raise ValueError("Unterminated TLS callback table or inspection limit reached")
                tls = dict(directory_rva=d.VirtualAddress, template_start_va=start, template_end_va=end,
                           index_va=index, callback_table_va=callbacks, callbacks_rva=callback_rvas,
                           zero_fill=zero_fill, characteristics=flags)
        return dict(machine="AMD64", format="PE32+", image_base=hdr.ImageBase, entry_rva=entry,
                    entry_section=entry_section.Name.rstrip(b"\0").decode("ascii", "replace")
                    if entry_section else None, tls=tls)


def collect(root, candidate, baseline, integrity, report):
    config = ET.parse(root / "MicrosoftGame.Config")
    slots = [e.attrib["Name"].replace("\\", "/") for e in config.iter("Executable")
             if e.get("TargetDeviceFamily", "").casefold() == "scarlett"]
    if len(slots) != 1:
        raise ValueError("Expected one Scarlett executable in MicrosoftGame.Config")
    slot, = slots
    installed = inside(root, slot)
    previous = json.loads(integrity.read_text(encoding="utf-8"))
    if previous["directory"] != root.name or not previous["torrent_payload_passed"]:
        raise ValueError("No passing historical integrity report for this build")
    torrent = inside(root, previous["torrent"])
    if digest(torrent) != previous["torrent_sha256"]:
        raise ValueError("Torrent hash differs from historical verification")
    _, targets = read_layout(inside(root, previous["layout"]["source"]))
    if slot not in targets or targets[slot] != previous["layout"]["absent_from_torrent"].get(slot):
        raise ValueError("Manifest slot and verified missing torrent entry disagree")
    old = json.loads(baseline.read_text(encoding="utf-8"))
    if old.get("schema") != 1 or any(p.casefold() == slot.casefold() for p in old["images"]):
        raise ValueError("Expected pre-EXE inventory")
    report["package"] = dict(build=root.name, slot=slot, chunks=targets[slot],
                             torrent_sha256=previous["torrent_sha256"], old_pieces=previous["pieces"],
                             verified_utc=previous.get("finished_utc"), candidate_covered_by_torrent=False,
                             baseline_sha256=digest(baseline), baseline_images=len(old["images"]))
    path = candidate if candidate is not None else installed
    report["candidate"] = {"path": str(path)}
    if not path.exists() and candidate is None:
        report["status"] = "awaiting_executable"
        return 3
    report["candidate"].update(size=path.stat().st_size, sha256=digest(path))
    report["pe"] = inspect_executable(path)
    current = scan(root, extra_image=(slot, path))
    candidate_key = next(k for k in current["images"] if k.casefold() == slot.casefold())
    if current["images"][candidate_key]["sha256"] != report["candidate"]["sha256"]:
        raise ValueError("Candidate changed during intake")
    report["diff"] = changes(old, current)
    report["dependency_paths"] = trace(current, candidate_key)
    report["inventory"] = current
    report["status"] = "inspected"
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate", type=Path, nargs="?", help="Separate file, or omit to use the manifest path")
    parser.add_argument("--build", type=Path)
    parser.add_argument("--baseline", type=Path, default=PROJECT / "out/dependencies/pre-exe.json")
    parser.add_argument("--integrity", type=Path)
    parser.add_argument("--reports", type=Path, default=PROJECT / "out/intake")
    args = parser.parse_args(argv)
    if args.build is None:
        builds = list((PROJECT / "game-files").glob("*/MicrosoftGame.Config"))
        if len(builds) != 1:
            parser.error("Use --build to select a package")
        args.build = builds[0].parent
    root = args.build.resolve()
    reports = args.reports.resolve()
    if reports.is_relative_to(root) or reports.is_relative_to(PROJECT / "game-files"):
        parser.error("Choose a report directory outside game files")
    integrity = args.integrity or PROJECT / "out/integrity" / (root.name + ".json")
    report = {"schema": 1, "status": "error"}
    try:
        code = collect(root, args.candidate.resolve() if args.candidate else None,
                       args.baseline, integrity, report)
    except (OSError, ValueError, KeyError, ET.ParseError, pefile.PEFormatError, struct.error) as exc:
        report["error"] = str(exc)
        code = 2
    reports.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(mode="w", suffix=".tmp", dir=reports, encoding="utf-8", delete=False) as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
        f.write("\n")
    dest = Path(f.name).with_suffix("." + report["status"] + ".json")
    Path(f.name).rename(dest)
    print(f"{report['status']} | {dest}")
    if "error" in report:
        print(report["error"])
    return code


if __name__ == "__main__":
    raise SystemExit(main())
