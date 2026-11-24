"""Drive the standalone audio/input alignment CLI with generated packet statistics."""

import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


TOOL = Path(__file__).resolve().parents[1] / "tools" / "startup_audio_timeline.py"


class TimelineCheck(unittest.TestCase):
    def test_clock_silence_and_missing_coverage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            packets = root / "packets.csv"
            with packets.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.writer(stream)
                writer.writerow(["process_s", "frames", "rms", "peak", "flags"])
                writer.writerows([
                    [4.0, 4800, 0.5, 0.75, 0],
                    [4.1, 4800, 0.25, 0.5, 0],
                    [5.0, 9600, 0, 0, 2],
                    [6.0, 4800, 0, 0, 1],
                    [6.1, 4800, 0, 0, 4],  # Invalid timestamp leaves a gap.
                ])
            inputs = root / "controls.jsonl"
            inputs.write_text("\n".join(json.dumps({"action": action, "qpc": at}) for action, at in [
                ("positive", 104.1),
                ("quiet", 105.1),
                ("gap", 106.1),
                ("missing", 107.1),
                ("ignored", 108.1),
            ]), encoding="utf-8")
            output = subprocess.run(
                [sys.executable, "-B", str(TOOL), str(packets), str(inputs),
                 "--process-origin-qpc", "100", "--before", "0.1", "--after", "0.1",
                 "--action", "positive", "--action", "quiet", "--action", "gap", "--action", "missing"],
                capture_output=True, text=True, check=True,
            )
            events = {row["action"]: row for row in json.loads(output.stdout)["events"]}
        self.assertEqual(set(events), {"positive", "quiet", "gap", "missing"})
        self.assertAlmostEqual(events["positive"]["coverage"], 1)
        self.assertAlmostEqual(events["positive"]["rms_estimate"], ((0.5**2 + 0.25**2) / 2)**0.5)
        self.assertEqual(events["positive"]["packet_peak"], 0.75)
        self.assertAlmostEqual(events["quiet"]["coverage"], 1)
        self.assertEqual(events["quiet"]["rms_estimate"], 0)
        self.assertAlmostEqual(events["gap"]["coverage"], 0.5)
        self.assertEqual(events["gap"]["discontinuities"], 1)
        self.assertEqual(events["missing"]["coverage"], 0)
        self.assertIsNone(events["missing"]["rms_estimate"])


if __name__ == "__main__":
    unittest.main()
