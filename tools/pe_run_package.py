"""Load an acyclic, source-built x64 Windows PE package through pe_map."""
import argparse
from collections import defaultdict
from contextlib import ExitStack
import ctypes as C
from ctypes import wintypes as W
import hashlib
import json
import os
from pathlib import Path
import sys

from pe_package_preflight import inspect

# --trap-missing exit codes are TRAP_EXIT_BASE | trap number (1-based, in sorted dll!symbol order).
TRAP_EXIT_BASE = 0xE7A00000
TRAP_LIMIT = 0xFFFF
_TRAP_CALLBACKS = []  # Process lifetime: trap thunks must outlive every guest thread.


def plan(report, *, allow_external=True):
    """Resolve the entire import graph before any guest attachment.

    The default keeps external host imports as unverified candidates. Set
    allow_external=False for a strict closed-package plan: every reachable
    import must terminate in an export bundled in the package. This pure check
    runs before any module is loaded or mapped.
    """
    accepted = {"bundled_export_present"}
    if allow_external:
        accepted.update(("external_unverified", "forwarded_external_unverified"))
    routes = defaultdict(dict)
    needs = defaultdict(set)
    for row in report["imports"]:
        image, name = row["image"], (row["dll"].casefold(), row["symbol"])
        if row["status"] not in accepted:
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


def bind_traps(kernel, missing_keys):
    """Bind each unresolved external to a numbered trap for a diagnostic run.

    A trap never returns to its caller: it writes its number and name to stderr and
    terminates the process with TRAP_EXIT_BASE | number. No DLL is loaded or written,
    so a trap cannot be mistaken for a provider. Returns (addresses, callbacks, labels);
    keep the callbacks alive for the whole run.
    """
    if len(missing_keys) > TRAP_LIMIT:
        raise ValueError(f"--trap-missing supports at most {TRAP_LIMIT} traps, got {len(missing_keys)}")
    terminate = prototype(kernel, "TerminateProcess", [W.HANDLE, W.UINT], W.BOOL)
    current = prototype(kernel, "GetCurrentProcess", [], W.HANDLE)
    trap_type = C.WINFUNCTYPE(None)
    addresses, callbacks, labels = {}, [], []
    for number, key in enumerate(sorted(missing_keys), 1):
        label = f"{key[0]}!{key[1]}"
        message = f"trap {number}: {', '.join(sorted(missing_keys[key]))}: {label}\n".encode("ascii", "replace")

        def hit(message=message, code=TRAP_EXIT_BASE | number):
            # os.write is unbuffered, so the line is out before the process ends.
            os.write(2, message)
            terminate(current(), code)

        trap = trap_type(hit)
        callbacks.append(trap)
        addresses[key] = C.cast(trap, C.c_void_p).value
        labels.append(label)
    return addresses, callbacks, labels


def run(root, report, mapper, shims, system, *, preflight_only=False, pin_shims=(), trap_missing=False):
    order, routes = plan(report)
    callback = C.WINFUNCTYPE(C.c_void_p, C.c_char_p, C.c_char_p, C.c_uint32)
    kernel = C.WinDLL("kernel32", use_last_error=True)
    load = prototype(kernel, "LoadLibraryExW", [W.LPCWSTR, W.HANDLE, W.DWORD], W.HMODULE)
    release_host = prototype(kernel, "FreeLibrary", [W.HMODULE], W.BOOL)
    find = prototype(kernel, "GetProcAddress", [W.HMODULE, C.c_void_p], C.c_void_p)
    pin_module = prototype(kernel, "GetModuleHandleExW", [W.DWORD, C.c_void_p, C.POINTER(W.HMODULE)], W.BOOL)
    modules, addresses = {}, {}
    if set(pin_shims) - shims.keys():
        raise ValueError("Pinned providers must be named with --shim")
    if trap_missing and preflight_only:
        raise ValueError("--trap-missing applies to execution mode, not --preflight-only")
    trap_labels = []
    with ExitStack() as stack:
        missing, missing_keys = [], defaultdict(set)
        for image in order:
            for terminal in routes[image].values():
                if terminal.get("package"):
                    continue
                dll, symbol = terminal["dll"].casefold(), terminal["symbol"]
                key = (dll, symbol)
                if key in addresses:
                    if not addresses[key]:
                        missing_keys[key].add(image)
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
                    missing_keys[key].add(image)
        if missing and trap_missing:
            trap_addresses, trap_callbacks, trap_labels = bind_traps(kernel, missing_keys)
            # A guest worker may still reach a trap after the entry returns.
            _TRAP_CALLBACKS.extend(trap_callbacks)
            addresses.update(trap_addresses)
            sys.stderr.write(f"trap-missing: {len(trap_labels)} unresolved external(s) bound to terminating "
                             "traps; diagnostic only, not providers\n")
            for number, label in enumerate(trap_labels, 1):
                sys.stderr.write(f"  trap {number} (exit {TRAP_EXIT_BASE | number:#x}): {label}\n")
            sys.stderr.flush()
        elif missing and not preflight_only:
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
        ordinal_routes = any(terminal.get("package") and terminal["symbol"].startswith("#")
                             for bindings in routes.values() for terminal in bindings.values())
        export_ordinal = None
        if ordinal_routes:
            try:
                export_ordinal = prototype(lib, "pe_map_export_ordinal", [C.c_void_p, C.c_uint32], C.c_void_p)
            except AttributeError as exc:
                raise ValueError("bundled ordinal imports require a mapper with pe_map_export_ordinal") from exc
        for name in sorted(pin_shims):
            module = modules.get(name)
            if not module:
                raise ValueError(f"{name}: pinned provider is not in the resolved import plan")
        # Provider workers may outlive guest return. Balance LoadLibrary normally
        # but retain these modules until the isolated process itself exits.
        pin_from_address = 0x1 | 0x4  # GET_MODULE_HANDLE_EX_FLAG_PIN | GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS
        for name in sorted(pin_shims):
            handle = W.HMODULE()
            if not pin_module(pin_from_address, modules[name], C.byref(handle)):
                raise ValueError(f"{name}: cannot pin provider ({C.get_last_error()})")
            release_host(handle)
        map_image = prototype(lib, "pe_map_image",
                              [W.LPCWSTR, callback, C.POINTER(C.c_uint32), C.c_char_p, C.c_size_t], C.c_void_p)
        export = prototype(lib, "pe_map_export", [C.c_void_p, C.c_char_p], C.c_void_p)
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
        result = {"image_order": order, "entry_executed": True, "exit_code": code.value}
        if trap_missing:
            # Reaching this point means no trap was called.
            result["unhit_traps"] = trap_labels
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mapper", type=Path)
    parser.add_argument("package", type=Path)
    parser.add_argument("entry")
    parser.add_argument("--shim", action="append", nargs=2, default=[], metavar=("DLL", "PATH"))
    parser.add_argument("--pin-shim", action="append", default=[], metavar="DLL",
                        help="keep a named external shim loaded until this process exits")
    parser.add_argument("--system", action="append", default=[], metavar="DLL")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--preflight-only", action="store_true")
    mode.add_argument("--trap-missing", action="store_true",
                      help="diagnostic: bind each unresolved external to a trap that names it on stderr and "
                           f"terminates the process with {TRAP_EXIT_BASE:#x} | trap number")
    options = parser.parse_args()
    try:
        root = options.package.resolve(strict=True)
        shims = {name.casefold(): Path(path).resolve(strict=True) for name, path in options.shim}
        system = {name.casefold() for name in options.system}
        if any(Path(name).name != name for name in system):
            raise ValueError("System providers must be DLL basenames")
        report = inspect(root, options.entry)
        result = run(root, report, options.mapper.resolve(), shims, system,
                     preflight_only=options.preflight_only,
                     pin_shims={name.casefold() for name in options.pin_shim},
                     trap_missing=options.trap_missing)
    except (ValueError, OSError) as exc:
        parser.exit(1, f"{exc}\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
