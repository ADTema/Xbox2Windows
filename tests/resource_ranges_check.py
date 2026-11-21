"""Byte-for-byte controls for logical asset reads and bounded section probes."""
import io
from pathlib import Path
import struct
import sys
import unittest
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from paged_resource import PagedResource, Segment
from section_probe import scan_window, sections


class ShortReadStream(io.BytesIO):
    def read(self, size: int = -1, /) -> bytes:
        return super().read(min(size, 3) if size >= 0 else size)


class ResourceChecks(unittest.TestCase):
    def test_ranges(self):
        first, middle, last = b"header", b"m" * 93, b"end"
        compressed = zlib.compress(middle)
        stream = io.BytesIO(first + b"pad" + compressed + last)
        reader = PagedResource(stream, [Segment(0, 6, 6, "raw"), Segment(9, len(compressed), 93, "zlib"),
                                        Segment(9 + len(compressed), 3, 3, "raw")])
        reference = first + middle + last
        for pos in range(len(reference) + 1):
            for length in (0, min(5, len(reference)-pos), len(reference)-pos):
                self.assertEqual(reader.read(pos, length), reference[pos:pos+length])
        for pos, size in ((-1, 0), (1, -1), (reader.size, 1)):
            with self.assertRaises(ValueError):
                reader.read(pos, size)
        with self.assertRaises(ValueError):
            reader.read(7, 1, limit=8)

    def test_short_reads_of_intact_segments(self) -> None:
        decoded = b"range data from a synthetic segment"
        for codec, stored, diagnostic in (
            ("raw", decoded, "Truncated segment"),
            ("zlib", zlib.compress(decoded), "Invalid compressed segment"),
        ):
            with self.subTest(codec=codec):
                stream = ShortReadStream(stored)
                reader = PagedResource(stream, [Segment(0, len(stored), len(decoded), codec)])
                self.assertEqual(reader.read(2, len(decoded) - 4), decoded[2:-2])
                stream.truncate(len(stored) - 1)
                with self.assertRaisesRegex(ValueError, diagnostic):
                    reader.read(0, len(decoded))

    def test_invalid_segments(self):
        packet = zlib.compress(b"page")
        for payload, count in ((packet[:-1], 4), (packet + b"extra", 4), (packet, 2), (packet, 8)):
            reader = PagedResource(io.BytesIO(payload), [Segment(0, len(payload), count, "zlib")])
            with self.assertRaises(ValueError):
                reader.read(0, 1)
        for seg in (Segment(0, 1, 2, "raw"), Segment(2, 1, 1, "raw"), Segment(-1, 1, 1, "raw")):
            with self.assertRaises(ValueError):
                PagedResource(io.BytesIO(b"ab"), [seg])
        reader = PagedResource(io.BytesIO(b"abcdef"), [Segment(0, 2, 2, "raw"),
                               Segment(2, 2, 2, "other"), Segment(4, 2, 2, "raw")])
        self.assertEqual(reader.read(4, 2), b"ef")
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            reader.read(1, 2)

    def test_section_windows(self):
        doc = struct.pack(">4sI4s4sI", b"HEAD", 12, b"data", b"FOOT", 8)
        packet = zlib.compress(doc)
        self.assertEqual(scan_window(packet, 16, "HEAD", "FOOT"), (1, {"HEAD FOOT": 1}))
        self.assertEqual(scan_window(packet, 1, "HEAD", "FOOT"), (0, {}))
        self.assertEqual(scan_window(packet, 0, "OTHER", "FOOT"), (1, {}))
        self.assertEqual(scan_window(packet[:-1], 0, "HEAD", "FOOT"), (0, {}))
        for data in (doc + b"x", doc[:-1], doc[:4] + bytes(4), doc[:12] + b"\0" * 8):
            self.assertFalse(sections(data))


if __name__ == "__main__":
    unittest.main()
