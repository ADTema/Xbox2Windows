"""Inventory PE metadata and compare it with exports advertised on this x64 Windows host."""

import argparse
from collections import Counter, defaultdict
import ctypes
from functools import cache
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
from tempfile import NamedTemporaryFile

import pefile


# The linked tests exercise desktop behavior; none provides a Scarlett oracle.
EXPERIMENTS = {
    ("xmem.dll", "XMemAlloc"): "era_heap_allocation, era_heap_failure, era_heap_concurrency",
    ("xmem.dll", "XMemFree"): "era_heap_allocation, era_heap_concurrency",
    ("xmem.dll", "XMemVirtualQuery"): "desktop_memory_query: Windows page states; Scarlett ABI unverified",
    ("xmem.dll", "XMemGetWorkingSetStatistics"): "desktop_memory_query: Windows process counters; Scarlett scope and units unverified",
    ("d3d12_xs.dll", "D3D12SerializeVersionedRootSignature"): "desktop_root_signature",
    ("d3d12_xs.dll", "D3D12CreateRootSignatureDeserializer"): "desktop_root_signature",
}


def label(raw):
    return raw.decode("ascii", errors="backslashreplace") if raw is not None else None


def api_sets(system):
    # Read the v6 namespace and its per-importer overrides from the host image.
    with pefile.PE(str(system / "apisetschema.dll"), fast_load=True) as pe:
        section = next(s for s in pe.sections if s.Name.rstrip(b"\0") == b".apiset")
        data = section.get_data()
    version, _, _, count, entries, _, _ = struct.unpack_from("<7I", data)
    if version != 6:
        raise ValueError(f"Unsupported Windows API-set schema {version}")

    def name(offset, size):
        return data[offset:offset + size].decode("utf-16-le").lower()

    contracts = {}
    for i in range(count):
        _, start, _, hashed_size, values, number = struct.unpack_from("<6I", data, entries + i * 24)
        hosts = {}
        for j in range(number):
            _, alias, alias_size, host, host_size = struct.unpack_from("<5I", data, values + j * 20)
            hosts[name(alias, alias_size)] = name(host, host_size)
        contracts[name(start, hashed_size)] = hosts
    return contracts


def exports(pe):
    directory = getattr(pe, "DIRECTORY_ENTRY_EXPORT", None)
    if not directory:
        return []
    return [dict(ordinal=s.ordinal, name=label(s.name), forwarder=label(s.forwarder))
            for s in directory.symbols if s.address]


def export_keys(rows):
    keys = {f"#{row['ordinal']}" for row in rows}
    keys.update(row["name"] for row in rows if row["name"] is not None)
    return keys


def resolve_desktop(dll, symbol, importer, contracts, system_exports):
    """Follow System32 export forwarders without loading any DLL."""
    chain = []
    seen = set()
    while True:
        aliases = contracts.get(dll.rpartition("-")[0]) if dll.startswith(("api-", "ext-")) else None
        host = dll if aliases is None else aliases.get(importer, aliases.get("", ""))
        step = dict(dll=dll, provider=host or None, symbol=symbol)
        chain.append(step)
        if (host, symbol) in seen:
            status = "forwarder_cycle"
            break
        seen.add((host, symbol))
        table = system_exports(host)
        if table is None:
            status = "provider_not_found"
            break
        if symbol not in table:
            status = "export_not_found"
            break
        target = table[symbol]
        if target is None:
            status = "export_present"
            break
        step["forwarder"] = target
        module, separator, name = target.partition(".")
        if name.lower().startswith("dll."):
            name = name[4:]
        if not separator or not module or not name:
            status = "invalid_forwarder"
            break
        dll, symbol, importer = module.lower() + ".dll", name, host
    return dict(status=status, chain=chain)


def read_rva(pe, rva, size):
    section = pe.get_section_by_rva(rva)
    data = section.get_data(rva, size) if section else b""
    if len(data) != size:
        raise ValueError(f"Import data at RVA {rva:#x} is outside the file's sections")
    return data


def read_name(pe, rva):
    section = pe.get_section_by_rva(rva)
    name, terminator, _ = (section.get_data(rva, 0x10000) if section else b"").partition(b"\0")
    if not terminator:
        raise ValueError(f"Unterminated import name at RVA {rva:#x}")
    return name


def import_tables(pe, path):
    """Read import descriptors and lookup tables as stored.

    pefile skips lookup entries whose names fall outside its function-name character set and
    entries for ordinal 0, drops a descriptor left empty by either, and names ordinal imports
    from a few system DLLs. The inventory keeps every entry exactly as the image requests it.
    """
    wide = pe.OPTIONAL_HEADER.Magic == 0x20B
    width, by_ordinal = (8, 1 << 63) if wide else (4, 1 << 31)
    directories = pe.OPTIONAL_HEADER.DATA_DIRECTORY
    imports = []
    for kind, index, layout in (("normal", 1, struct.Struct("<5I")), ("delay", 13, struct.Struct("<8I"))):
        if index >= len(directories) or not (directories[index].VirtualAddress or directories[index].Size):
            continue
        rva, found = directories[index].VirtualAddress, 0
        while True:
            fields = layout.unpack(read_rva(pe, rva, layout.size))
            rva += layout.size
            if kind == "normal":
                original_first_thunk, _, _, name, first_thunk = fields
                lookup, base = original_first_thunk or first_thunk, 0
            else:
                attributes, name, _, _, lookup = fields[:5]
                # Version 1 delay descriptors hold RVAs. Older ones hold virtual addresses.
                base = 0 if attributes & 1 else pe.OPTIONAL_HEADER.ImageBase
            if not name:
                break
            found += 1
            module = label(read_name(pe, name - base)).lower()
            entry = lookup - base
            while value := int.from_bytes(read_rva(pe, entry, width), "little"):
                entry += width
                symbol = (f"#{value & 0xFFFF}" if value & by_ordinal
                          else label(read_name(pe, ((value - base) & 0x7FFFFFFF) + 2)))
                imports.append((kind, module, symbol))
        if not found:
            raise ValueError(f"Could not parse {kind} imports in {path}")
    return imports


def parse_image(path):
    with pefile.PE(str(path), fast_load=True) as pe:
        pe.parse_data_directories(directories=[0])
        imports = import_tables(pe, path)
        with path.open("rb") as f:
            digest = hashlib.file_digest(f, "sha256").hexdigest()
        info = {
            "machine": pefile.MACHINE_TYPE.get(pe.FILE_HEADER.Machine, hex(pe.FILE_HEADER.Machine)),
            "sha256": digest, "exports": exports(pe), "parse_warnings": pe.get_warnings(),
        }
    return info, imports


def scan(root, *, extra_image=None):
    system = Path(os.environ["SystemRoot"]) / "System32"
    process, native = ctypes.c_ushort(), ctypes.c_ushort()
    if not ctypes.windll.kernel32.IsWow64Process2(
            ctypes.c_void_p(-1), ctypes.byref(process), ctypes.byref(native)):
        raise ctypes.WinError()
    if process.value != 0 or native.value != 0x8664:
        raise ValueError("Use a native x64 Windows Python for the desktop comparison")
    contracts = api_sets(system)
    system_images = {p.name.lower(): p for p in system.glob("*.dll")}

    @cache
    def system_exports(name):
        if name not in system_images:
            return None
        with pefile.PE(str(system_images[name]), fast_load=True) as pe:
            pe.parse_data_directories(directories=[0])
            table = {}
            for row in exports(pe):
                table[f"#{row['ordinal']}"] = row["forwarder"]
                if row["name"] is not None:
                    table[row["name"]] = row["forwarder"]
            return table

    images = {}
    edges = []
    bundled = defaultdict(list)
    paths = {p.relative_to(root).as_posix(): p for p in root.rglob("*")
             if p.suffix.lower() in {".dll", ".exe"} and p.is_file()}
    if extra_image:
        relative, candidate = extra_image
        present = next((p for name, p in paths.items() if name.casefold() == relative.casefold()), None)
        if present and present.resolve() != candidate.resolve():
            raise ValueError(f"Another file already occupies {relative}")
        if not present:
            paths = {name: path for name, path in paths.items() if path.resolve() != candidate.resolve()}
            paths[relative] = candidate
    for relative, path in sorted(paths.items()):
        images[relative], imports = parse_image(path)
        bundled[Path(relative).name.lower()].append((relative, export_keys(images[relative]["exports"])))
        edges.extend((relative, *imp) for imp in imports)
    if not images:
        raise ValueError(f"No DLLs or EXEs under {root}")

    rows = []
    for image, kind, dll, symbol in sorted(set(edges)):
        resolution = resolve_desktop(dll, symbol, Path(image).name.lower(), contracts, system_exports)
        first = resolution["chain"][0]
        # Keep desktop_export as the first-hop comparison for existing report readers.
        status = "export_present" if "forwarder" in first else resolution["status"]
        candidate = None
        if dll == "d3d12_xs.dll" and "d3d12.dll" in system_images and symbol in system_exports("d3d12.dll"):
            candidate = "d3d12.dll"
        rows.append({
            "image": image, "kind": kind, "dll": dll, "symbol": symbol,
            "bundle_exports_in": sorted(p for p, keys in bundled[dll] if symbol in keys),
            "desktop_provider": first["provider"], "desktop_export": status, "desktop_candidate": candidate,
            "desktop_resolution": resolution,
        })
    unresolved = [r for r in rows if r["desktop_resolution"]["status"] != "export_present" and not r["bundle_exports_in"]]
    return {
        "schema": 1, "host_windows_build": sys.getwindowsversion().build, "pefile": pefile.__version__,
        "behavior": "Scarlett behavior unverified for every import. Static export matches include forwarders.",
        "scope": "Static PE directory entries only. Dynamic lookups and object methods are unknown.",
        "summary": {
            "images": len(images), "edges": len(rows), "import_modules": len({r["dll"] for r in rows}),
            "distinct_imports": len({(r["dll"], r["symbol"]) for r in rows}),
            "normal": sum(r["kind"] == "normal" for r in rows),
            "delay": sum(r["kind"] == "delay" for r in rows),
            "by_ordinal": sum(r["symbol"].startswith("#") for r in rows),
            "exports": sum(len(i["exports"]) for i in images.values()),
            "desktop_results": dict(Counter(r["desktop_export"] for r in rows)),
            "desktop_terminal_results": dict(Counter(r["desktop_resolution"]["status"] for r in rows)),
            "desktop_forwarded_edges": sum(len(r["desktop_resolution"]["chain"]) > 1 for r in rows),
        },
        "unresolved_edges": [dict(r, desktop_experiment=EXPERIMENTS.get((r["dll"], r["symbol"])))
                             for r in unresolved],
        "images": images, "imports": rows,
    }


def changes(old, new):
    if old["schema"] != new["schema"]:
        raise ValueError("Inventory schema mismatch")

    def edges(report):
        return {(r["image"], r["kind"], r["dll"], r["symbol"]) for r in report["imports"]}

    before, after = edges(old), edges(new)
    previous, current = old["images"], new["images"]
    return {
        "added_images": sorted(current.keys() - previous.keys()),
        "removed_images": sorted(previous.keys() - current.keys()),
        "changed_images": sorted(p for p in previous.keys() & current.keys()
                                 if previous[p]["sha256"] != current[p]["sha256"]),
        "added_edges": sorted(after - before), "removed_edges": sorted(before - after),
        "newly_required_modules": sorted({e[2] for e in after} - {e[2] for e in before}),
        "newly_required_symbols": sorted({e[2:] for e in after} - {e[2:] for e in before}),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--baseline", type=Path)
    args = parser.parse_args()
    root = args.directory.resolve(strict=True)
    output = args.output.resolve()
    if output.is_relative_to(root) or (args.baseline and output == args.baseline.resolve()):
        parser.error("Choose an output outside the input tree and separate from the baseline")
    result = scan(root)
    if args.baseline:
        result["diff"] = changes(json.loads(args.baseline.read_text(encoding="utf-8")), result)
    output.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=output.parent, mode="w", encoding="utf-8", delete=False) as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
        f.write("\n")
    Path(f.name).replace(output)
    print(f"{len(result['images'])} images | {len(result['imports'])} import edges | {output}")
    print(f"Desktop terminal results: {result['summary']['desktop_terminal_results']} | "
          f"forwarded edges: {result['summary']['desktop_forwarded_edges']}")


if __name__ == "__main__":
    main()
