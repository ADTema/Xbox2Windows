"""End-to-end CLI checks with locally compiled PE fixtures. Never load a fixture."""

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory

import pefile

TOOLS = Path(__file__).resolve().parents[2] / "tools"
sys.path.insert(0, str(TOOLS))
from pe_inventory import scan


def check(folder, fixture, provider):
    root = folder / "build"
    root.mkdir()
    shutil.copyfile(provider, root / provider.name)
    slot = "main.exe"
    (root / "MicrosoftGame.Config").write_text(
        '<Game><ExecutableList><Executable TargetDeviceFamily="Scarlett" Name="main.exe"/></ExecutableList></Game>')
    (root / "layout.xml").write_text(
        '<Package><Chunk Id="1001"><FileGroup DestinationPath="/" Include="main.exe"/></Chunk></Package>')
    # A standard multifile v1 torrent with one piece crossing the fixture files.
    files = sorted(root.iterdir())
    piece = hashlib.sha1(b"".join(p.read_bytes() for p in files)).digest()
    entries = b"".join(
        b"d6:lengthi%de4:pathl%d:%see" %
        (p.stat().st_size, len(p.name), p.name.encode("ascii")) for p in files)
    torrent = root / "fixture.torrent"
    torrent.write_bytes(b"d4:infod5:filesl" + entries +
                        b"e4:name5:build12:piece lengthi16777216e6:pieces20:" + piece + b"ee")
    integrity = folder / "integrity.json"
    subprocess.run([sys.executable, "-B", str(TOOLS / "verify_build.py"), str(root),
                    "--output", str(integrity)], check=True, capture_output=True)
    baseline = folder / "baseline.json"
    baseline.write_text(json.dumps(scan(root)))
    original = baseline.read_bytes()
    reports = folder / "reports"

    def run(expected_exit, *args):
        before = set(reports.glob("*.json"))
        result = subprocess.run([sys.executable, "-B", str(TOOLS / "intake_exe.py"), "--build", str(root),
                                 "--baseline", str(baseline), "--integrity", str(integrity),
                                 "--reports", str(reports), *args], capture_output=True, text=True)
        assert result.returncode == expected_exit, (result.stdout, result.stderr)
        new, = set(reports.glob("*.json")) - before
        assert baseline.read_bytes() == original
        return json.loads(new.read_text(encoding="utf-8"))

    assert run(3)["status"] == "awaiting_executable"
    report = run(0, fixture)
    assert report["diff"]["added_images"] == [slot]
    assert report["package"]["old_pieces"]["matched"] == 1
    assert report["diff"]["changed_images"] == report["diff"]["removed_images"] == []
    assert report["candidate"]["sha256"] == hashlib.sha256(fixture.read_bytes()).hexdigest()
    assert report["pe"]["entry_rva"] and report["pe"]["entry_section"] == ".text"
    assert report["pe"]["tls"]["callbacks_rva"] and report["pe"]["tls"]["template_start_va"]
    startup = report["pe"]["startup"]
    locations = startup["locations"]
    assert [loc["role"] for loc in locations] == ["tls_callback"] * (len(locations) - 1) + ["entry"]
    assert [loc["rva"] for loc in locations] == report["pe"]["tls"]["callbacks_rva"] + [report["pe"]["entry_rva"]]
    with pefile.PE(str(fixture)) as pe:
        functions = [record.struct for record in pe.DIRECTORY_ENTRY_EXCEPTION]
        assert startup["exception_table"] == "indexed" and startup["runtime_functions"] == len(functions)
        for loc in locations:
            assert loc["file_offset"] == pe.get_offset_from_rva(loc["rva"])
            match = next((f for f in functions if f.BeginAddress <= loc["rva"] < f.EndAddress), None)
            assert loc["runtime_function"] == (dict(begin_rva=match.BeginAddress, end_rva=match.EndAddress,
                unwind_data_rva=match.UnwindData) if match else None)
        directory = pe.OPTIONAL_HEADER.DATA_DIRECTORY[3]
        directory.Size -= 1
        incomplete = folder / "incomplete-directory.exe"
        pe.write(str(incomplete))
        directory.VirtualAddress = directory.Size = 0
        absent = folder / "no-directory.exe"
        pe.write(str(absent))
    incomplete_startup = run(0, incomplete)["pe"]["startup"]
    assert incomplete_startup["exception_table"] == "unusable"
    absent_startup = run(0, absent)["pe"]["startup"]
    assert absent_startup["exception_table"] == "absent"
    assert all(loc["runtime_function"] is None for loc in absent_startup["locations"])
    for result in (absent_startup, incomplete_startup):
        assert [loc["file_offset"] for loc in result["locations"]] == [loc["file_offset"] for loc in locations]
    paths = report["dependency_paths"]
    assert paths["reachable"][provider.name] == dict(conditional=False, path=[slot, provider.name], reasons=["normal"])
    assert any(f["dll"] == "intake_delay.dll" and f["conditional"] and f["reasons"] == ["delay"]
               for f in paths["findings"])
    loader = "amd_fidelityfx_loader_xbox.dll"
    normal, = [f for f in paths["findings"] if f["dll"] == loader and f["symbol"] == "ffxQuery"]
    assert normal["path"] == [slot] and normal["reasons"] == ["normal"] and not normal["conditional"]
    assert normal["problem"] == "provider_not_found" and normal["desktop_chain"] == [
        dict(dll=loader, provider=loader, symbol="ffxQuery")]
    assert not any(f["dll"] == "amd_fidelityfx_framegeneration_xbox.dll" for f in paths["findings"])
    edges = {(r["kind"], r["dll"], r["symbol"]): r for r in report["inventory"]["imports"] if r["image"] == slot}
    for symbol in ("named_value", "#77"):
        assert edges["normal", provider.name, symbol]["bundle_exports_in"] == [provider.name]
    delayed = edges["delay", "intake_delay.dll", "delayed_value"]
    assert not delayed["bundle_exports_in"] and delayed["desktop_export"] == "provider_not_found"
    assert not (root / slot).exists()
    truncated = folder / "truncated.exe"
    truncated.write_bytes(fixture.read_bytes()[:-256])
    assert "Section extends" in run(2, truncated)["error"]
    bad_tls = folder / "bad-tls.exe"
    with pefile.PE(str(fixture)) as pe:
        table_va = pe.DIRECTORY_ENTRY_TLS.struct.AddressOfCallBacks
        pe.set_qword_at_rva(table_va - pe.OPTIONAL_HEADER.ImageBase, 1)
        pe.write(str(bad_tls))
    assert "RVA" in run(2, bad_tls)["error"]
    staged = root / "incoming.exe"
    shutil.copyfile(fixture, staged)
    assert run(0, staged)["diff"]["added_images"] == [slot]
    staged.unlink()
    shutil.copyfile(fixture, root / slot)
    assert run(0)["diff"]["added_images"] == [slot]
    assert "occupies" in run(2, fixture)["error"]
    torrent.write_bytes(b"different")
    assert "Torrent hash differs" in run(2)["error"]


if __name__ == "__main__":
    with TemporaryDirectory() as temporary:
        check(Path(temporary), Path(sys.argv[1]), Path(sys.argv[2]))
