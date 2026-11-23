"""Load an acyclic, source-built x64 Windows PE package through pe_map."""
import argparse
from collections import defaultdict
from contextlib import ExitStack
import ctypes as C
from ctypes import wintypes as W
import hashlib
import json
from pathlib import Path
import sys

from pe_package_preflight import inspect


def plan(report):
    """Resolve the entire import graph before any guest attachment."""
    routes = defaultdict(dict)
    needs = defaultdict(set)
    for row in report["imports"]:
        image, name = row["image"], (row["dll"].casefold(), row["symbol"])
        if row["status"] not in ("bundled_export_present", "external_unverified",
                                 "forwarded_external_unverified"):
            raise ValueError(f"{image}: {name[0]}!{name[1]}: {row['status']}")
        chain = row["chain"]
        for caller, provider in zip([image, *(step["provider"] for step in chain)], chain):
            if provider.get("package") and caller != provider["provider"]:
                needs[caller].add(provider["provider"])
        terminal = chain[-1]
        if terminal.get("package") and terminal["provider"] == image:
            raise ValueError(f"{image}: self import needs deferred DLL attachment")
        old = routes[image].setdefault(name, terminal)
        if old != terminal:
            raise ValueError(f"{image}: conflicting bindings for {name[0]}!{name[1]}")

    order = []
    pending = set(report["reachable"])
    while pending:
        finished = sorted(image for image in pending if not needs[image] & pending)
        if not finished:
            raise ValueError("bundled dependency cycle: " + ", ".join(sorted(pending)))
        order.extend(finished)
        pending.difference_update(finished)
    if order[-1] != report["entry"]:
        raise ValueError("entry is a dependency of a bundled image")
    return order, routes


def prototype(lib, name, args, result):
    function = getattr(lib, name)
    function.argtypes, function.restype = args, result
    return function


def run(root, report, mapper, shims, system, *, preflight_only=False):
    order, routes = plan(report)
    callback = C.WINFUNCTYPE(C.c_void_p, C.c_char_p, C.c_char_p, C.c_uint32)
    kernel = C.WinDLL("kernel32", use_last_error=True)
    load = prototype(kernel, "LoadLibraryExW", [W.LPCWSTR, W.HANDLE, W.DWORD], W.HMODULE)
    release_host = prototype(kernel, "FreeLibrary", [W.HMODULE], W.BOOL)
    find = prototype(kernel, "GetProcAddress", [W.HMODULE, C.c_void_p], C.c_void_p)
    modules, addresses = {}, {}
    with ExitStack() as stack:
        missing = []
        for image in order:
            for terminal in routes[image].values():
                if terminal.get("package"):
                    continue
                dll, symbol = terminal["dll"].casefold(), terminal["symbol"]
                key = (dll, symbol)
                if key in addresses:
                    continue
                if dll not in modules:
                    module = (load(str(shims[dll]), None, 0x900) if dll in shims else
                              load(dll, None, 0x800) if dll in system else None)
                    modules[dll] = module
                    if module:
                        stack.callback(release_host, module)
                module = modules[dll]
                needle = (int(symbol[1:]) if symbol.startswith("#")
                          else C.cast(C.c_char_p(symbol.encode("ascii")), C.c_void_p))
                addresses[key] = find(module, needle) if module else None
                if not addresses[key]:
                    missing.append(f"{image}: {dll}!{symbol}")
        if missing and not preflight_only:
            raise ValueError(f"{len(missing)} unresolved external symbol(s), first {missing[0]}")
        if preflight_only:
            return {"image_order": order, "external_bindings": len(addresses) - len(missing),
                    "missing": missing, "entry_executed": False}

        # Recheck the reachable files before the first guest attach.
        for image in order:
            with (root / image).open("rb") as source:
                digest = hashlib.file_digest(source, "sha256").hexdigest()
            if digest != report["images"][image]["sha256"]:
                raise ValueError(f"{image}: file changed after inventory")

        lib = C.WinDLL(str(mapper), winmode=0x900)
        map_image = prototype(lib, "pe_map_image",
                              [W.LPCWSTR, callback, C.POINTER(C.c_uint32), C.c_char_p, C.c_size_t], C.c_void_p)
        export = prototype(lib, "pe_map_export", [C.c_void_p, C.c_char_p], C.c_void_p)
        export_ordinal = prototype(lib, "pe_map_export_ordinal", [C.c_void_p, C.c_uint32], C.c_void_p)
        unmap = prototype(lib, "pe_map_release", [C.c_void_p], C.c_int)
        start = prototype(lib, "pe_map_run", [C.c_void_p, C.POINTER(C.c_uint32)], C.c_int)
        mapped = {}
        for image in order:
            imports = {}
            for key, terminal in routes[image].items():
                symbol = terminal["symbol"]
                if terminal.get("package"):
                    provider = terminal["provider"]
                    imports[key] = (export_ordinal(mapped[provider], int(symbol[1:]))
                                    if symbol.startswith("#") else
                                    export(mapped[provider], symbol.encode("ascii")))
                    if not imports[key]:
                        raise ValueError(f"{image}: mapped export {provider}!{symbol} unavailable")
                else:
                    imports[key] = addresses[terminal["dll"].casefold(), symbol]

            @callback
            def resolve(dll, name, ordinal):
                try:
                    symbol = name.decode("ascii") if name else f"#{ordinal}"
                    return imports.get((dll.decode("ascii").casefold(), symbol))
                except UnicodeDecodeError:
                    return None

            status, detail = C.c_uint32(), C.create_string_buffer(512)
            mapped[image] = map_image(str(root / image), resolve, C.byref(status), detail, len(detail))
            if not mapped[image]:
                raise ValueError(f"{image}: mapper refused ({status.value}): {detail.value.decode(errors='replace')}")
            stack.callback(unmap, mapped[image])
        code = C.c_uint32()
        if not start(mapped[report["entry"]], C.byref(code)):
            raise ValueError("mapper refused the EXE start")
        return {"image_order": order, "entry_executed": True, "exit_code": code.value}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mapper", type=Path)
    parser.add_argument("package", type=Path)
    parser.add_argument("entry")
    parser.add_argument("--shim", action="append", nargs=2, default=[], metavar=("DLL", "PATH"))
    parser.add_argument("--system", action="append", default=[], metavar="DLL")
    parser.add_argument("--preflight-only", action="store_true")
    options = parser.parse_args()
    try:
        root = options.package.resolve(strict=True)
        shims = {name.casefold(): Path(path).resolve(strict=True) for name, path in options.shim}
        system = {name.casefold() for name in options.system}
        if any(Path(name).name != name for name in system):
            raise ValueError("System providers must be DLL basenames")
        report = inspect(root, options.entry)
        result = run(root, report, options.mapper.resolve(), shims, system,
                     preflight_only=options.preflight_only)
    except (ValueError, OSError) as exc:
        parser.exit(1, f"{exc}\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
