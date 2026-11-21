"""Compare native and translated arithmetic used to size the descriptor heaps."""
import ctypes
from pathlib import Path
import sys

import pefile

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from cpu_leaf_aot import export_rva
from cpu_ranges import function_ranges
from ffx_version_query import INTEGER_HEADER, lower, region


def emit(image, output):
    with pefile.PE(str(image), fast_load=True) as pe:
        (bounds,) = function_ranges(pe, export_rva(pe, "heap_layout"))
        code = lower(region(pe, *bounds), ["rcx = count; rdx = reinterpret_cast<word>(sizes);"], {}, {}, {})
    output.write_text(INTEGER_HEADER + 'extern "C" __declspec(dllexport) word heap_layout(uint32_t count, '
                      'uint32_t* sizes) {\n' + code + '\n}\n', encoding="ascii")


def check(image):
    lib = ctypes.CDLL(str(image.resolve()))
    layout = lib.heap_layout
    uint = ctypes.c_uint32
    layout.argtypes, layout.restype = [uint, ctypes.POINTER(uint)], ctypes.c_uint64
    for count in (0, 1, 2, 17, 0x80000001, 0xffffffff):
        sizes = (uint * 2)()
        result = layout(count, sizes)
        expected = (uint(count << 9).value, uint(count * 0x19000 + 0x10000).value,
                    uint(count * 0xbe000).value | 0x1100)
        if (*sizes, result) != expected:
            raise AssertionError(f"{image.name}: count {count:#x} yielded {(*sizes, result)}, expected {expected}")


if __name__ == "__main__":
    mode, native, other = sys.argv[1:]
    if mode == "emit":
        emit(Path(native), Path(other))
    elif mode == "check":
        check(Path(native))
        check(Path(other))
    else:
        raise ValueError(mode)
