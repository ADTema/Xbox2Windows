"""Map source-built x64 images without LoadLibrary, bind imports to host shims and compare calls."""

import argparse
import ctypes
from ctypes import wintypes
from pathlib import Path
import struct
import sys
from tempfile import TemporaryDirectory

import pefile

from direct_check import input_pairs, observe, reference, register_probe

Resolver = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint32)
STATUS = {"ok": 0, "format": 2, "unresolved": 5, "unsupported": 6}  # MapStatus in tools/pe_map.cpp
kernel = ctypes.WinDLL("kernel32", use_last_error=True)
kernel.GetProcAddress.argtypes = [wintypes.HMODULE, ctypes.c_void_p]
kernel.GetProcAddress.restype = ctypes.c_void_p
lookup_entry = kernel.RtlLookupFunctionEntry
lookup_entry.argtypes = [ctypes.c_uint64, ctypes.POINTER(ctypes.c_uint64), ctypes.c_void_p]
lookup_entry.restype = ctypes.c_void_p


class Mapper:
    def __init__(self, path):
        lib = ctypes.CDLL(str(path))
        self.map = lib.pe_map_image
        self.map.argtypes = [ctypes.c_wchar_p, Resolver, ctypes.POINTER(ctypes.c_uint32),
                             ctypes.c_char_p, ctypes.c_size_t]
        self.map.restype = ctypes.c_void_p
        self.export = lib.pe_map_export
        self.export.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        self.export.restype = ctypes.c_void_p
        self.release = lib.pe_map_release
        self.release.argtypes = [ctypes.c_void_p]

    def __call__(self, image, bindings):
        """Map image; bindings maps a lower-case DLL name to the module that serves its imports."""
        requests = []

        def resolve(dll, name, ordinal):
            requests.append((dll.decode(), name.decode() if name else ordinal))
            module = bindings.get(dll.decode().casefold())
            if module is None:
                return None
            return kernel.GetProcAddress(module._handle, name if name else ordinal)

        callback = Resolver(resolve)
        status = ctypes.c_uint32(0xffffffff)
        detail = ctypes.create_string_buffer(256)
        base = self.map(str(image), callback, ctypes.byref(status), detail, len(detail))
        return base, status.value, detail.value.decode(), requests


def describe(image):
    with pefile.PE(str(image)) as pe:
        exports = {e.name.decode(): e.address for e in pe.DIRECTORY_ENTRY_EXPORT.symbols if e.name}
        dir64 = [e.rva for block in getattr(pe, "DIRECTORY_ENTRY_BASERELOC", [])
                 for e in block.entries if e.type == pefile.RELOCATION_TYPE["IMAGE_REL_BASED_DIR64"]]
        stored = {rva: pe.get_qword_at_rva(rva) for rva in dir64}
        iat = {}
        for desc in pe.DIRECTORY_ENTRY_IMPORT:
            for i, imp in enumerate(desc.imports):
                iat[desc.struct.FirstThunk + 8 * i] = imp.name.decode() if imp.name else imp.ordinal
        return pe.OPTIONAL_HEADER.ImageBase, exports, stored, iat


def check_mapping(mapper, case, image, provider, symbol, probe, natives, shim=None):
    preferred, exports, stored, iat = describe(image)
    dll = provider.name.casefold()
    module = ctypes.CDLL(str(shim or provider))
    base, status, detail, requests = mapper(image, {dll: module})
    if status != STATUS["ok"] or not base:
        raise AssertionError(f"{case}: map failed with {status}: {detail}")
    try:
        if base == preferred:
            raise AssertionError(f"{case}: mapped at the preferred base {preferred:#x}")
        if [(name.casefold(), item) for name, item in requests] != [(dll, symbol)]:
            raise AssertionError(f"{case}: unexpected import requests {requests}")
        bound = kernel.GetProcAddress(module._handle, symbol.encode() if isinstance(symbol, str) else symbol)
        slot, = iat
        if ctypes.c_uint64.from_address(base + slot).value != bound:
            raise AssertionError(f"{case}: IAT slot {slot:#x} does not hold the shim export")
        header = ctypes.c_uint32.from_address(base + 0x3c).value  # e_lfanew
        if ctypes.c_uint64.from_address(base + header + 0x30).value != base:  # OptionalHeader.ImageBase
            raise AssertionError(f"{case}: mapped headers keep the preferred ImageBase")
        if case.startswith(("named", "ordinal")) and stored:
            raise AssertionError(f"{case}: import fixture unexpectedly has DIR64 relocations")
        for rva, value in stored.items():
            relocated = ctypes.c_uint64.from_address(base + rva).value
            if relocated != value - preferred + base:
                raise AssertionError(f"{case}: DIR64 at {rva:#x} holds {relocated:#x}")
        fn = mapper.export(base, b"call_mix")
        if fn != base + exports["call_mix"]:
            raise AssertionError(f"{case}: export lookup returned {fn}")
        image_base = ctypes.c_uint64()
        if not lookup_entry(fn, ctypes.byref(image_base), None) or image_base.value != base:
            raise AssertionError(f"{case}: .pdata entry for call_mix is not registered")
        inputs = input_pairs()
        for x, y in inputs:
            actual = observe(probe, fn, x, y)
            expected = reference(x, y, caller=True, altered=shim is not None)
            if actual != expected:
                raise AssertionError(f"{case}({x:#x}, {y:#x}): {actual=} {expected=}")
            if shim is None:
                for name, native in natives:
                    if observe(probe, native, x, y) != actual:
                        raise AssertionError(f"{case}({x:#x}, {y:#x}): {name} differs from mapped image")
    finally:
        mapper.release(base)
    if lookup_entry(fn, ctypes.byref(image_base), None):
        raise AssertionError(f"{case}: function table survived release")
    against = ", ".join(name for name, _ in natives) if shim is None else "altered shim reference"
    print(f"{case}: mapped at {base:#x} (preferred {preferred:#x}), {len(stored)} DIR64 relocation(s), "
          f"{len(inputs)} argument pairs match {against}")


def check_rejections(mapper, image, provider, symbol):
    identity = f"{provider.name}!" + (symbol if isinstance(symbol, str) else f"#{symbol}")
    base, status, detail, _ = mapper(image, {})
    if base or status != STATUS["unresolved"] or detail != f"unresolved import {identity}":
        raise AssertionError(f"unbound import: {base=} {status=} {detail=}")
    with pefile.PE(str(image)) as pe:
        entry = pe.OPTIONAL_HEADER.get_field_absolute_offset("AddressOfEntryPoint")
        imports = pe.OPTIONAL_HEADER.DATA_DIRECTORY[1].get_field_absolute_offset("VirtualAddress")
        size = pe.OPTIONAL_HEADER.SizeOfImage
    bindings = {provider.name.casefold(): ctypes.CDLL(str(provider))}
    for field, value, expected, message in ((entry, 0x1000, "unsupported", "entry point"),
                                            (imports, size - 4, "format", "import directory outside image")):
        data = bytearray(image.read_bytes())
        struct.pack_into("<I", data, field, value)
        with TemporaryDirectory() as temp:
            damaged = Path(temp) / image.name
            damaged.write_bytes(data)
            base, status, detail, requests = mapper(damaged, bindings)
        if base or status != STATUS[expected] or detail != message or requests:
            raise AssertionError(f"{message} control: {base=} {status=} {detail=} {requests=}")
    print(f"{image.name}: rejected unbound {identity}, an entry point and an import directory outside the image")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mapper", type=Path)
    parser.add_argument("probe", type=Path)
    parser.add_argument("--named", type=Path, nargs=4, metavar=("ORIGINAL", "LIFTED", "PROVIDER", "ALTERED"),
                        required=True)
    parser.add_argument("--ordinal", type=Path, nargs=4, metavar=("ORIGINAL", "LIFTED", "PROVIDER", "ALTERED"),
                        required=True)
    parser.add_argument("--reloc", type=Path, nargs=3, metavar=("ORIGINAL", "PROVIDER", "ALTERED"), required=True)
    args = parser.parse_args()
    mapper = Mapper(args.mapper)
    probe = register_probe(str(args.probe))
    for case, paths, symbol in (("named", args.named, "mix_args"), ("ordinal", args.ordinal, 77)):
        original, lifted, provider, altered = paths
        natives = [("native LoadLibrary", ctypes.CDLL(str(original)).call_mix),
                   ("lifted DLL", ctypes.CDLL(str(lifted)).lifted)]
        check_mapping(mapper, case, original, provider, symbol, probe, natives)
        check_mapping(mapper, f"{case} with altered shim", original, provider, symbol, probe, [], altered)
        check_rejections(mapper, original, provider, symbol)
    original, provider, altered = args.reloc
    natives = [("native LoadLibrary", ctypes.CDLL(str(original)).call_mix)]
    if len(describe(original)[2]) != 1:
        raise AssertionError("relocation fixture must have exactly one DIR64 entry")
    check_mapping(mapper, "relocated", original, provider, "mix_args", probe, natives)
    check_mapping(mapper, "relocated with altered shim", original, provider, "mix_args", probe, [], altered)


if __name__ == "__main__":
    sys.exit(main())
