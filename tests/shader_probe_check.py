"""Exercise both desktop validator modes, text analysis, and the native root reader using owned shaders."""

import json
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from probe_roots import parts, validate_shader


def main():
    probe, root, tables, without_root = map(Path, sys.argv[1:])
    for path, params, samplers in ((root, 3, 0), (tables, 6, 1)):
        data = path.read_bytes()
        sections = parts(data)
        result = json.loads(subprocess.check_output([str(probe)], input=data))
        assert result["legacy_hr"] == result["versioned_hr"] == result["original_serialize_hr"] == "0x00000000"
        assert (result["parameters"], result["samplers"], result["flags"]) == (params, samplers, 0)
        checks = validate_shader(probe, data, sections[b"DXIL"])
        assert checks["container"]["status"] == checks["module"]["status"] == "0x00000000"
        assert checks["ir"]["target_triple"] == "dxil-ms-dx" and not checks["ir"]["xbox_call_sites"]
        assert checks["ir"]["dx_op_call_sites"]
    result = json.loads(subprocess.check_output([str(probe)], input=without_root.read_bytes()))
    assert result["legacy_hr"] != "0x00000000" and result["versioned_hr"] != "0x00000000"
    assert "original_serialize_hr" not in result


if __name__ == "__main__":
    main()
