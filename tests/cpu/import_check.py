"""Check named IAT calls in the original and translated PE with isolated Windows loaders."""

import ctypes
from pathlib import Path
import shutil
import struct
import subprocess
import sys
from tempfile import TemporaryDirectory

import pefile

from direct_check import input_pairs, observe, reference, register_probe
from cpu_leaf_aot import bounded_code, export_rva


def import_site(image, entry, provider):
    with pefile.PE(str(image), fast_load=True) as pe:
        start = export_rva(pe, entry)
        code = bounded_code(pe, start)
        pe.parse_data_directories(directories=[1])
        slots = [desc.struct.FirstThunk + 8 * i for desc in pe.DIRECTORY_ENTRY_IMPORT
                 if desc.dll.decode("ascii").casefold() == provider.name.casefold()
                 for i, imp in enumerate(desc.imports) if imp.name == b"mix_args"]
        slot, = slots
        sites = [i for i in range(len(code) - 5) if code[i:i + 2] == b"\xff\x15"
                 and start + i + 6 + struct.unpack_from("<i", code, i + 2)[0] == slot]
        site, = sites
        return pe.get_offset_from_rva(start + site + 2), slot


def load_case(case, native, lifted, probe_path):
    # A fresh process per provider configuration avoids Windows' loaded-module cache.
    expected_error = {"missing": 126, "wrong-export": 127}.get(case)
    if expected_error:
        load = ctypes.WinDLL("kernel32", use_last_error=True).LoadLibraryExW
        load.argtypes = [ctypes.c_wchar_p, ctypes.c_void_p, ctypes.c_uint32]
        load.restype = ctypes.c_void_p
        for path in (native, lifted):
            handle = load(str(path), None, 0x1100)  # DLL_LOAD_DIR | DEFAULT_DIRS
            error = ctypes.get_last_error()
            if handle or error != expected_error:
                raise AssertionError(f"{path.name}: expected loader error {expected_error}, got {handle=}, {error=}")
        print(f"{case}: both callers rejected with Windows error {expected_error}")
        return
    probe = register_probe(str(probe_path))
    original, compiled = (ctypes.CDLL(str(path)) for path in (native, lifted))
    inputs = input_pairs()
    for x, y in inputs:
        actual = observe(probe, compiled.lifted, x, y)
        source = observe(probe, original.call_mix, x, y)
        baseline = reference(x, y, caller=True)
        if actual != source or source != reference(x, y, caller=True, altered=case == "altered"):
            raise AssertionError(f"{case} provider({x:#x}, {y:#x}): {source=} {actual=}")
        if case == "altered" and (actual[0] == baseline[0] or actual[1:] != baseline[1:]):
            raise AssertionError("altered provider must change only the return")
    print(f"{case}: {len(inputs)} argument pairs, guarded trace, register and return checks passed")


def reject(image, provider, reason):
    tool = Path(__file__).resolve().parents[2] / "tools/cpu_call_aot.py"
    output = image.with_suffix(".cpp")
    run = subprocess.run([sys.executable, "-B", str(tool), str(image), "call_mix", str(output),
                          "--bind", str(provider), "mix_args"], capture_output=True, text=True)
    if run.returncode != 1 or reason not in run.stderr or output.exists():
        raise AssertionError(f"expected {reason!r}, got {run.returncode}: {run.stderr}")


def check(native, lifted, provider, altered, probe):
    disp, slot = import_site(native, "call_mix", provider)
    import_site(lifted, "lifted", provider)
    with TemporaryDirectory() as temp:
        for case, implementation in (("normal", provider), ("altered", altered),
                                     ("missing", None), ("wrong-export", probe)):
            folder = Path(temp) / case
            folder.mkdir()
            source = Path(shutil.copy2(native, folder))
            compiled = Path(shutil.copy2(lifted, folder))
            bound = folder / provider.name
            if implementation:
                shutil.copy2(implementation, bound)
            subprocess.run([sys.executable, "-B", __file__, "--load", case, str(source), str(compiled),
                            str(probe)], cwd=folder, check=True)
            identity = f"{provider.name}!mix_args"
            if case == "missing":
                reject(source, bound, f"missing provider for {identity}")
            elif case == "wrong-export":
                reject(source, bound, f"unresolved import {identity}")
            elif case == "normal":
                # Move the RIP-relative call one byte into the same IAT slot.
                data = bytearray(source.read_bytes())
                delta, = struct.unpack_from("<i", data, disp)
                struct.pack_into("<i", data, disp, delta + 1)
                source.write_bytes(data)
                reject(source, bound, f"no unique ordinary import at IAT slot RVA {slot + 1:#x}")


if __name__ == "__main__":
    if sys.argv[1] == "--load":
        load_case(sys.argv[2], *map(Path, sys.argv[3:]))
    else:
        check(*map(Path, sys.argv[1:]))
