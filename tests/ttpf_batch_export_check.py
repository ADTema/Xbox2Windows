"""Unit and regression tests for ttpf_batch_export."""

import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import MagicMock
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import ttpf_batch_export as batch


class MockPool:
    def __init__(self, path: str):
        self.path = path
        self.textures = 6

    def close(self):
        pass


class MockTtpfModule:
    BC_FORMATS = {71, 98}

    @staticmethod
    def Pool(path: str):
        return MockPool(path)

    @staticmethod
    def analyze(pool, index: int) -> dict:
        if index == 0:
            # Valid BC1 texture
            return {
                "layout": {"size": 131072},
                "available": [True],
                "full_chain": True,
                "descriptor": {"format": 71, "width": 512, "height": 512, "mips": 1},
                "shape": "2d",
            }
        elif index == 1:
            # Valid BC7 texture requiring provisional calibration
            return {
                "layout": {"size": 131072},
                "available": [True],
                "full_chain": True,
                "descriptor": {"format": 98, "width": 512, "height": 256, "mips": 1},
                "shape": "2d",
            }
        elif index == 2:
            # Uncompressed format
            return {
                "layout": {"size": 65536},
                "available": [True],
                "full_chain": True,
                "descriptor": {"format": 28, "width": 128, "height": 128, "mips": 1},
                "shape": "2d",
            }
        elif index == 3:
            # Incomplete codec chain
            return {
                "layout": {"size": 65536},
                "available": [False],
                "full_chain": False,
                "descriptor": {"format": 71, "width": 256, "height": 256, "mips": 1},
                "shape": "2d",
            }
        elif index == 4:
            # Missing layout / blocked
            return {"blocked": "allocation span mismatch"}
        else:
            # Broken export
            return {
                "layout": {"size": 131072},
                "available": [True],
                "full_chain": True,
                "descriptor": {"format": 98, "width": 256, "height": 256, "mips": 1},
                "shape": "2d",
            }

    @staticmethod
    def export(pool, index: int, out_path: str, *, allow_provisional: bool = False, history=None) -> int:
        target = Path(out_path)
        if index == 0:
            # Strict mode succeeds
            target.write_bytes(b"DDS_STRICT_BC1_DATA")
            return 0
        elif index == 1:
            # Fails in strict, succeeds with provisional
            if allow_provisional:
                target.write_bytes(b"DDS_PROVISIONAL_BC7_DATA")
                return 0
            return 2
        elif index == 5:
            # Always fails
            return 2
        return 0


class BatchExportTests(unittest.TestCase):
    def test_parse_indices(self):
        self.assertEqual(batch.parse_indices("0,8253"), [0, 8253])
        self.assertEqual(batch.parse_indices("0-3, 5, 10-12"), [0, 1, 2, 3, 5, 10, 11, 12])
        self.assertEqual(batch.parse_indices("0-10", total_count=4), [0, 1, 2, 3])
        self.assertEqual(batch.parse_indices("  2, , 4 "), [2, 4])
        with self.assertRaises(ValueError):
            batch.parse_indices("10-2")

    def test_export_texture_entry_strict(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            pool = MockPool("mock.ttpf")
            res = batch.export_texture_entry(pool, 0, out_dir, allow_provisional=False,
                                             ttpf_module=MockTtpfModule)
            self.assertEqual(res["status"], "success")
            self.assertEqual(res["mode"], "strict")
            self.assertEqual(res["format_name"], "BC1")
            self.assertEqual(res["sha256"], hashlib.sha256(b"DDS_STRICT_BC1_DATA").hexdigest())
            self.assertTrue((out_dir / "tex_00000.dds").exists())

    def test_export_texture_entry_provisional_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            pool = MockPool("mock.ttpf")
            # Strict only -> fails
            res_strict = batch.export_texture_entry(pool, 1, out_dir, allow_provisional=False,
                                                    ttpf_module=MockTtpfModule)
            self.assertEqual(res_strict["status"], "failed")

            # With allow_provisional -> retries and succeeds
            res_prov = batch.export_texture_entry(pool, 1, out_dir, allow_provisional=True,
                                                  ttpf_module=MockTtpfModule)
            self.assertEqual(res_prov["status"], "success")
            self.assertEqual(res_prov["mode"], "provisional")
            self.assertEqual(res_prov["format_name"], "BC7")
            self.assertEqual(res_prov["sha256"], hashlib.sha256(b"DDS_PROVISIONAL_BC7_DATA").hexdigest())

    def test_export_texture_entry_uncompressed_and_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            pool = MockPool("mock.ttpf")
            res_uncompressed = batch.export_texture_entry(pool, 2, out_dir, ttpf_module=MockTtpfModule)
            self.assertEqual(res_uncompressed["status"], "uncompressed")

            res_codec = batch.export_texture_entry(pool, 3, out_dir, ttpf_module=MockTtpfModule)
            self.assertEqual(res_codec["status"], "unsupported_codec")

            res_layout = batch.export_texture_entry(pool, 4, out_dir, ttpf_module=MockTtpfModule)
            self.assertEqual(res_layout["status"], "no_layout")

    def test_cached_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            pool = MockPool("mock.ttpf")
            dds_file = out_dir / "tex_00000.dds"
            dds_file.write_bytes(b"EXISTING_DATA")
            res = batch.export_texture_entry(pool, 0, out_dir, skip_existing=True,
                                             ttpf_module=MockTtpfModule)
            self.assertEqual(res["status"], "cached")
            self.assertEqual(res["sha256"], hashlib.sha256(b"EXISTING_DATA").hexdigest())

    def test_manifest_generation(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "dds_out"
            manifest_file = out_dir / "manifest.json"
            dummy_pool = Path(tmp) / "test.ttpf"
            dummy_pool.write_bytes(b"DUMMY_POOL")

            # Patch load_tools to return MockTtpfModule
            orig_load = batch.load_tools
            try:
                batch.load_tools = lambda *args, **kwargs: MockTtpfModule
                summary = batch.batch_export(
                    pool_path=dummy_pool,
                    out_dir=out_dir,
                    indices=[0, 1, 2, 4],
                    allow_provisional=True,
                    skip_existing=True,
                    manifest_path=manifest_file,
                )
                self.assertEqual(summary["total_textures"], 6)
                self.assertEqual(summary["processed"], 4)
                self.assertEqual(summary["stats"]["strict"], 1)
                self.assertEqual(summary["stats"]["provisional"], 1)
                self.assertEqual(summary["stats"]["skipped"], 2)

                self.assertTrue(manifest_file.exists())
                manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
                self.assertEqual(len(manifest), 4)
                self.assertEqual([m["index"] for m in manifest], [0, 1, 2, 4])
                self.assertEqual(manifest[0]["mode"], "strict")
                self.assertEqual(manifest[1]["mode"], "provisional")
            finally:
                batch.load_tools = orig_load

    @unittest.skipUnless(os.environ.get("BCPACK_REFERENCE_TOOLS") or os.environ.get("TTPF_TOOLS_DIR"),
                         "optional local ttpf tools directory")
    def test_reference_tools_available(self):
        mod = batch.load_tools()
        self.assertIsNotNone(mod)
        self.assertTrue(hasattr(mod, "Pool"))
        self.assertTrue(hasattr(mod, "analyze"))
        self.assertTrue(hasattr(mod, "export"))


if __name__ == "__main__":
    unittest.main()
