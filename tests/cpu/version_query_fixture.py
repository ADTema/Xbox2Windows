"""Lift an independent MASM query and compare both Windows entry points."""
from pathlib import Path
import sys

import pefile

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from cpu_leaf_aot import export_rva
from cpu_ranges import function_ranges
from ffx_version_query import HEADER, lower, region
from version_query_check import check


def emit(image, output):
    with pefile.PE(str(image), fast_load=True) as pe:
        begin = export_rva(pe, "fixture_query")
        (interval,) = function_ranges(pe, begin)
        label = export_rva(pe, "fixture_name")
        name = pe.get_string_at_rva(label, 64)
        code = lower(region(pe, *interval), ["rcx = reinterpret_cast<word>(query);"],
                     {label: "reinterpret_cast<word>(name)"}, {}, {})
    data = ", ".join(map(str, name + b"\0"))
    output.write_text(HEADER + f"static const char name[] = {{{data}}};\n"
                      + 'extern "C" __declspec(dllexport) uint32_t query_versions(Query* query) {\n'
                      + code + "\n}\n", encoding="ascii")


if __name__ == "__main__":
    mode, native, other = sys.argv[1:]
    if mode == "emit":
        emit(Path(native), Path(other))
    elif mode == "check":
        for path, symbol in ((native, "fixture_query"), (other, "query_versions")):
            check(Path(path), symbol, 0xabcd000000001234, "fixture-7")
    else:
        raise ValueError(mode)
