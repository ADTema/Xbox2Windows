"""Compare the source-built XMemIsToolsMemAvailable caller under Windows and pe_map.

Exercises both BOOL outcomes:
- Mode FALSE: desktop policy without a tools partition (caller takes retail fallback, exit 42).
- Mode TRUE: console devkit with a tools partition (caller takes tools path, exit 84).
Also verifies that pe_map stops at map time with unresolved import diagnostic on missing provider.
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
    """Run the native caller EXE in a temporary directory where provider_dll is served as xmem.dll."""
    with TemporaryDirectory() as temp:
        temp_dir = Path(temp)
        temp_exe = temp_dir / exe.name
        temp_xmem = temp_dir / "xmem.dll"
        shutil.copyfile(exe, temp_exe)
        shutil.copyfile(provider_dll, temp_xmem)
        proc = subprocess.run([str(temp_exe)], cwd=str(temp_dir), timeout=20)
        return proc.returncode


def compare(mapper_path, exe_path, provider_path, provider_devkit_path):
    mapper_path = Path(mapper_path)
    exe = Path(exe_path)
    provider = Path(provider_path)
    provider_devkit = Path(provider_devkit_path)

    # 1. Verify import descriptor in caller PE image
    imports = imports_by_dll(exe)
    check("xmem.dll imports", imports.get("xmem.dll"), ["XMemIsToolsMemAvailable"])
    print(f"caller imports: {imports}")

    # 2. Mode FALSE: desktop without a tools partition
    native_false = run_native(exe, provider)
    check("native desktop fallback exit", native_false, 42)

    prov_lib = ctypes.WinDLL(str(provider))
    prov_lib.get_tools_mem_call_count.restype = ctypes.c_uint32
    prov_lib.reset_tools_mem_call_count.restype = None
    prov_lib.reset_tools_mem_call_count()

    providers_false = {"xmem.dll": prov_lib}
    mapped_false = run_mapped(mapper_path, exe, providers_false)
    check("mapped desktop fallback exit", mapped_false, 42)
    check("desktop call count", prov_lib.get_tools_mem_call_count(), 2)
    print("mode FALSE (desktop without tools partition): native and mapped exit 42, 2 calls recorded")

    # 3. Mode TRUE: console devkit with a tools partition
    native_true = run_native(exe, provider_devkit)
    check("native devkit exit", native_true, 84)

    prov_devkit_lib = ctypes.WinDLL(str(provider_devkit))
    prov_devkit_lib.get_tools_mem_call_count.restype = ctypes.c_uint32
    prov_devkit_lib.reset_tools_mem_call_count.restype = None
    prov_devkit_lib.reset_tools_mem_call_count()

    providers_true = {"xmem.dll": prov_devkit_lib}
    mapped_true = run_mapped(mapper_path, exe, providers_true)
    check("mapped devkit exit", mapped_true, 84)
    check("devkit call count", prov_devkit_lib.get_tools_mem_call_count(), 2)
    print("mode TRUE (console devkit with tools partition): native and mapped exit 84, 2 calls recorded")

    # 4. Negative control: missing xmem provider fails at map time before entry
    mapper = Mapper(mapper_path)
    base, status, detail, requests = mapper(exe, {})
    if base:
        mapper.release(base)
        raise AssertionError("caller mapped with empty providers")
    check("missing provider status", status, STATUS["unresolved"])
    check("missing provider diagnostic", detail, "unresolved import xmem.dll!XMemIsToolsMemAvailable")
    print(f"negative control: map time refusal before entry: {detail}")


if __name__ == "__main__":
    compare(*sys.argv[1:])
