"""Compare every mapped section of the register probe with the Windows loader, including a copy with no file offset."""

import argparse
import ctypes
from ctypes import wintypes
from pathlib import Path
import struct
from tempfile import TemporaryDirectory

import pefile

from native_map_check import Mapper, STATUS

POINTER_TO_RAW_DATA = 20  # offset in IMAGE_SECTION_HEADER
kernel = ctypes.WinDLL("kernel32", use_last_error=True)
kernel.LoadLibraryExW.argtypes = [wintypes.LPCWSTR, wintypes.HANDLE, wintypes.DWORD]
kernel.LoadLibraryExW.restype = ctypes.c_void_p
kernel.FreeLibrary.argtypes = [ctypes.c_void_p]


def layout(image):
    """Return (name, rva, span) for each section; refuse images whose load would run code."""
    with pefile.PE(str(image), fast_load=True) as pe:
        if pe.OPTIONAL_HEADER.AddressOfEntryPoint or pe.OPTIONAL_HEADER.DATA_DIRECTORY[1].Size:
            raise AssertionError(f"{image.name}: needs no entry point and no imports to be loaded safely")
        return [(s.Name.rstrip(b"\0").decode(), s.VirtualAddress, s.Misc_VirtualSize or s.SizeOfRawData)
                for s in pe.sections]


def clear_file_offset(source, target, name):
    """Copy source with one section's PointerToRawData set to zero; SizeOfRawData is kept."""
    data = bytearray(source.read_bytes())
    with pefile.PE(data=bytes(data), fast_load=True) as pe:
        section = next(s for s in pe.sections if s.Name.rstrip(b"\0") == name.encode())
        own = bytes(data[section.PointerToRawData:section.PointerToRawData + section.Misc_VirtualSize])
        if not section.SizeOfRawData or not any(own):
            raise AssertionError(f"{name}: needs nonzero file data so a zero fill is observable")
        struct.pack_into("<I", data, section.get_file_offset() + POINTER_TO_RAW_DATA, 0)
    target.write_bytes(data)


def read(base, sections):
    return {name: bytes((ctypes.c_ubyte * span).from_address(base + rva)) for name, rva, span in sections}


def windows_sections(image, sections):
    module = kernel.LoadLibraryExW(str(image), None, 0)
    if not module:
        raise AssertionError(f"{image.name}: LoadLibraryExW failed with {ctypes.get_last_error()}")
    try:
        return read(module, sections)
    finally:
        kernel.FreeLibrary(module)


def mapped_sections(mapper, image, sections):
    base, status, detail, requests = mapper(image, {})
    if status != STATUS["ok"] or not base or requests:
        raise AssertionError(f"{image.name}: map returned {status} ({detail}), requests {requests}")
    try:
        return read(base, sections)
    finally:
        mapper.release(base)


def compare(mapper, case, image, sections):
    native = windows_sections(image, sections)
    mapped = mapped_sections(mapper, image, sections)
    for name, _, span in sections:
        if mapped[name] != native[name]:
            header = image.read_bytes()[:span]
            source = "file bytes from offset 0" if mapped[name] == header else "different bytes"
            raise AssertionError(f"{case}: pe_map {name} holds {source}, Windows {name} differs")
    print(f"{case}: {len(sections)} sections match the Windows loader byte for byte")
    return native


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mapper", type=Path)
    parser.add_argument("probe", type=Path, help="source-built image with no entry point and no imports")
    parser.add_argument("--section", default=".rsrc")
    args = parser.parse_args()
    mapper = Mapper(args.mapper)
    sections = layout(args.probe)

    with TemporaryDirectory() as folder:
        original = Path(folder) / "section_original.dll"
        original.write_bytes(args.probe.read_bytes())
        before = compare(mapper, "unpatched", original, sections)

        patched = Path(folder) / "section_no_file_offset.dll"
        clear_file_offset(args.probe, patched, args.section)
        after = compare(mapper, f"{args.section} PointerToRawData 0", patched, sections)
        if any(after[args.section]) or after[args.section] == before[args.section]:
            raise AssertionError(f"Windows no longer zero-fills {args.section} without a file offset")
        changed = [name for name, _, _ in sections if name != args.section and after[name] != before[name]]
        if changed:
            raise AssertionError(f"patching {args.section} changed other sections: {changed}")
        print(f"{args.section} without a file offset is zero-filled by both loaders")


if __name__ == "__main__":
    main()
