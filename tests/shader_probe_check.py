"""Exercise both desktop validator modes, text analysis, and the native root reader using owned shaders."""

import json
from pathlib import Path
import subprocess
import sys

import pefile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from probe_roots import packing_evidence, parts, validate_shader

SKIP = 77
E_INVALIDARG = "0x80070057"


def file_version(path):
    with pefile.PE(str(path), fast_load=True) as pe:
        pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_RESOURCE"]])
        info = pe.VS_FIXEDFILEINFO[0]
    return info.FileVersionMS >> 16, info.FileVersionMS & 0xFFFF, info.FileVersionLS >> 16, info.FileVersionLS & 0xFFFF


def main():
    positive = "{ i32, i32, i32 } { i32 2139095039, i32 2139095039, i32 2139095039 }"
    negative = positive.replace("2139095039", "-8388609")
    store = "call void @xbox.global_store_dwordx3_with_cache(i32 362, i64 "
    fixture = f"""
define void @first() {{
    %sel = and i32 %index, 3
    %v = call i32 @xbox.V_ALIGNBYTE_B32(i32 332, i32 %a, i32 %b, i32 %sel)
    {store}%base, {positive}, i32 undef, i32 undef)
    %end = add i64 %base, 12
    {store}%end, {negative}, i32 undef, i32 undef)
    {store}%other, {positive}, i32 undef, i32 undef)
    {store}%end, {negative}, i32 undef, i32 undef)
}}
define void @second() {{
    %v = call i32 @xbox.V_ALIGNBYTE_B32(i32 332, i32 %a, i32 %b, i32 %sel)
}}
"""
    evidence = packing_evidence(fixture)
    assert evidence["alignbyte_selectors"] == {"and_3": 1, "other_or_unknown": 1}
    assert evidence["adjacent_extrema_store_pairs"] == 1
    assert evidence["store_addresses"] == {"dwordx3:other_or_unknown": 2, "dwordx3:add_12": 2}
    probe, root, tables, without_root, validator = map(Path, sys.argv[1:])
    refused = []
    for path, params, samplers in ((root, 3, 0), (tables, 6, 1)):
        data = path.read_bytes()
        sections = parts(data)
        result = json.loads(subprocess.check_output([str(probe)], input=data))
        assert result["legacy_hr"] == result["versioned_hr"] == result["original_serialize_hr"] == "0x00000000"
        assert (result["parameters"], result["samplers"], result["flags"]) == (params, samplers, 0)
        checks = validate_shader(probe, data, sections[b"DXIL"], optional_modes=("module",))
        assert checks["container"]["status"] == "0x00000000"
        if "status" in checks["module"]:
            assert checks["module"]["status"] == "0x00000000"
        else:
            refused.append(checks["module"]["call_hr"])
        assert checks["ir"]["target_triple"] == "dxil-ms-dx" and not checks["ir"]["xbox_call_sites"]
        assert checks["ir"]["dx_op_call_sites"]
    result = json.loads(subprocess.check_output([str(probe)], input=without_root.read_bytes()))
    assert result["legacy_hr"] != "0x00000000" and result["versioned_hr"] != "0x00000000"
    assert "original_serialize_hr" not in result
    if refused:
        # DXC 1.8.2407 and older ship a dxil.dll numbered 101.x that returns E_INVALIDARG for
        # DxcValidatorFlags_ModuleOnly. Starting with 1.8.2502 the same call validates the module.
        version = file_version(validator)
        assert refused == [E_INVALIDARG] * 2 and version[0] == 101, (refused, version)
        print(f"Module-only validation skipped: {validator.name} {'.'.join(map(str, version))} "
              f"returned {E_INVALIDARG}. Configure with DXC 1.8.2502 or newer to run it.")
        return SKIP
    return 0


if __name__ == "__main__":
    sys.exit(main())
