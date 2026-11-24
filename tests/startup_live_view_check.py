"""Check that the live viewer reports only what a frame heartbeat establishes."""

import contextlib
import io
from pathlib import Path
import runpy
import sys
import tempfile
import unittest
from unittest import mock


class LiveViewCheck(unittest.TestCase):
    def test_frame_heartbeat_does_not_claim_draws_were_dropped(self):
        viewer = Path(__file__).resolve().parents[1] / "tools" / "startup" / "live_view.py"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "trap.log").write_text(
                "x2w-d3d12 heartbeat: 60 frames presented in 2.0 s (30.0 fps overall)\n",
                encoding="utf-8",
            )
            (root / "finished.txt").write_text("finished\n", encoding="utf-8")
            output = io.StringIO()
            with mock.patch.object(sys, "argv", [str(viewer), directory]), \
                    mock.patch("os.system"), mock.patch("time.sleep"), \
                    contextlib.redirect_stdout(output):
                runpy.run_path(str(viewer), run_name="__main__")

        self.assertIn("60 frames presented, 30.0 fps", output.getvalue())
        self.assertNotIn("every draw dropped", output.getvalue())


if __name__ == "__main__":
    unittest.main()
