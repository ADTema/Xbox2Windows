"""Compare the source-built XMemMapPhysicalPages caller under Windows and pe_map.

Exercises both contiguous mapping and scatter mapping contracts:
- XMemMapPhysicalPages: 64 KiB alignment check, valid map, valid unmap (NULL page array), and unaligned/null refusals.
- XMemMapPhysicalPagesScatter: valid scatter map, valid scatter unmap (NULL page array), and null array refusal.
- Negative control: pe_map stops before entry when xmem.dll provider is missing.
"""

import ctypes
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory

import pefile

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mapped_exe_chain_check import run_mapped
from native_map_check import Mapper, STATUS


def imports_by_dll(image):
    with pefile.PE(str(image), fast_load=True) as pe:
        pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"]])
        return {module.dll.decode().casefold(): sorted(imp.name.decode() for imp in module.imports if imp.name)
                for module in pe.DIRECTORY_ENTRY_IMPORT}


def check(label, actual, expected):
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected!r}, got {actual!r}")


def run_native(exe, provider_dll):
    """Run native caller EXE in temporary directory where provider_dll is served as xmem.dll."""
    with TemporaryDirectory() as temp:
        temp_dir = Path(temp)
        temp_exe = temp_dir / exe.name
        temp_xmem = temp_dir / "xmem.dll"
        shutil.copyfile(exe, temp_exe)
        shutil.copyfile(provider_dll, temp_xmem)
        proc = subprocess.run([str(temp_exe)], cwd=str(temp_dir), timeout=20)
        return proc.returncode


def compare(mapper_path, exe_path, provider_path):
    mapper_path = Path(mapper_path)
    exe = Path(exe_path)
    provider = Path(provider_path)

    # 1. Verify import descriptor in caller PE image
    imports = imports_by_dll(exe)
    check("xmem.dll imports", imports.get("xmem.dll"), ["XMemMapPhysicalPages", "XMemMapPhysicalPagesScatter"])
    print(f"caller imports: {imports}")

    # 2. Native execution under Windows loader
    native_code = run_native(exe, provider)
    check("native mapping exit code", native_code, 0x870)

    prov_lib = ctypes.WinDLL(str(provider))
    prov_lib.get_map_pages_call_count.restype = ctypes.c_uint32
    prov_lib.get_map_pages_unmap_count.restype = ctypes.c_uint32
    prov_lib.get_scatter_map_call_count.restype = ctypes.c_uint32
    prov_lib.get_scatter_unmap_count.restype = ctypes.c_uint32
    prov_lib.reset_map_pages_records.restype = None

    # Reset records before mapped run
    prov_lib.reset_map_pages_records()

    # 3. Mapped execution under pe_map
    providers = {"xmem.dll": prov_lib}
    mapped_code = run_mapped(mapper_path, exe, providers)
    check("mapped mapping exit code", mapped_code, 0x870)
    check("mapped matches native", mapped_code, native_code)

    # Verify provider recorded calls: 1 map + 1 unmap for contiguous, 1 map + 1 unmap for scatter
    check("contiguous map calls", prov_lib.get_map_pages_call_count(), 1)
    check("contiguous unmap calls", prov_lib.get_map_pages_unmap_count(), 1)
    check("scatter map calls", prov_lib.get_scatter_map_call_count(), 1)
    check("scatter unmap calls", prov_lib.get_scatter_unmap_count(), 1)
    print("contiguous and scatter mapping: native and mapped exit 0x870, calls recorded")

    # 4. Negative control: missing xmem provider fails at map time before entry
    mapper = Mapper(mapper_path)
    base, status, detail, requests = mapper(exe, {})
    if base:
        mapper.release(base)
        raise AssertionError("caller mapped with empty providers")
    check("missing provider status", status, STATUS["unresolved"])
    if not detail.startswith("unresolved import xmem.dll!XMemMapPhysicalPages"):
        raise AssertionError(f"unexpected diagnostic detail: {detail}")
    print(f"negative control: map time refusal before entry: {detail}")


if __name__ == "__main__":
    compare(*sys.argv[1:])
