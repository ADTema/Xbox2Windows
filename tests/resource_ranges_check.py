"""Byte-for-byte controls for logical asset reads and bounded section probes."""
import io
import json
from pathlib import Path
import struct
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from paged_resource import PagedResource, Segment
from section_probe import inspect as inspect_sections
from section_probe import scan_window, sections
from texture_descriptors import inventory


class ShortReadStream(io.BytesIO):
    def read(self, size: int = -1, /) -> bytes:
        return super().read(min(size, 3) if size >= 0 else size)


def descriptor_archive() -> bytearray:
    archive = bytearray(9216)
    struct.pack_into("<4sIQ", archive, 0, b"RDS5", 3, 16384)
    # Boundaries give stored offsets 256, 8960, 9216 and virtual offsets
    # 0, 8192, 16384. The second chunk is outside the metadata inventory.
    struct.pack_into("<6I", archive, 16, 1, 0x70000000, (2 << 30) | (8 << 26) | 35, 0,
                     (5 << 26) | 36, 1)
    struct.pack_into("<4sIII", archive, 256, b"ETPF", 0, 258, 0)
    for index in range(257):
        # 44x12, DXGI 99, marker byte 2 and virtual page 3.
        struct.pack_into("<4I", archive, 272 + index * 16, 0x2C02B, 0x02000318, 3, 0)
    # Transposed dimensions and a different format after the first 4 KiB read.
    struct.pack_into("<4I", archive, 272 + 257 * 16, 0xAC00B, 0x238, 2, 0)
    return archive


class ResourceChecks(unittest.TestCase):
    def test_texture_descriptor_inventory(self) -> None:
        tool = Path(__file__).resolve().parents[1] / "tools" / "texture_descriptors.py"
        with TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic.ttpf"
            path.write_bytes(descriptor_archive())
            result = subprocess.run([sys.executable, "-B", tool, path], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {
            "descriptor_count": 258,
            "groups": [
                {"width": 12, "height": 44, "dxgi_format": 71, "mip_marker": 0, "count": 1},
                {"width": 44, "height": 12, "dxgi_format": 99, "mip_marker": 2, "count": 257},
            ],
        })

    def test_texture_descriptor_bounds(self) -> None:
        for label, offset, replacement in (
            ("RDS5 header", 0, b"TEST"),
            ("boundary table", 4, struct.pack("<I", 32)),
            ("raw metadata", 16, struct.pack("<I", 1 | (8 << 26))),
            ("stored range", 24, struct.pack("<I", (2 << 30) | 40)),
            ("stored table length", 24, struct.pack("<I", (2 << 30) | 2)),
            ("virtual range", 28, struct.pack("<I", 2)),
            ("ETPF header", 256, b"JUNK"),
            ("descriptor table", 264, struct.pack("<I", 512)),
            ("descriptor page", 272 + 257 * 16 + 8, struct.pack("<I", 4)),
        ):
            with self.subTest(label=label):
                archive = descriptor_archive()
                archive[offset:offset + len(replacement)] = replacement
                with self.assertRaises(ValueError):
                    inventory(io.BytesIO(archive))
        with self.assertRaises(ValueError):
            inventory(io.BytesIO(descriptor_archive()[:-1]))

        archive = descriptor_archive()
        archive.extend(bytes((1 << 20) + 16384 - len(archive)))
        struct.pack_into("<Q", archive, 8, len(archive))
        struct.pack_into("<4I", archive, 24, (2 << 30) | 4144, 64, 4160, 65)
        struct.pack_into("<I", archive, 264, 65537)
        with self.assertRaisesRegex(ValueError, "budget"):
            inventory(io.BytesIO(archive))

    def test_texture_descriptor_read_scope(self) -> None:
        class MetadataOnly(io.BytesIO):
            def read(self, size: int = -1, /) -> bytes:
                start = self.tell()
                if not (0 <= size <= 4096 and
                        (start + size <= 40 or 256 <= start <= start + size <= 272 + 258 * 16)):
                    raise AssertionError(f"Unexpected read of {size} bytes at {start}")
                return super().read(size)

        # Following bytes need not be part of the declared archive.
        stream = MetadataOnly(descriptor_archive() + bytes(256))
        self.assertEqual(sum(inventory(stream).values()), 258)

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
        self.assertEqual(scan_window(bytes(15) + packet, 1, "HEAD", "FOOT"), (1, {"HEAD FOOT": 1}))
        self.assertEqual(scan_window(packet, 0, "OTHER", "FOOT"), (1, {}))
        self.assertEqual(scan_window(packet[:-1], 0, "HEAD", "FOOT"), (0, {}))
        for data in (doc + b"x", doc[:-1], doc[:4] + bytes(4), doc[:12] + b"\0" * 8):
            self.assertFalse(sections(data))

    def test_section_probe_counts_smaller_zlib_windows(self) -> None:
        doc = struct.pack(">4sI4s4sI", b"HEAD", 12, b"data", b"FOOT", 8)
        packets = []
        for window_bits in range(9, 16):
            compressor = zlib.compressobj(wbits=window_bits)
            packets.append(compressor.compress(doc) + compressor.flush())
        dictionary = zlib.compressobj(wbits=9, zdict=b"HEAD data FOOT")
        packets.append(dictionary.compress(doc) + dictionary.flush())
        archive = b"".join(packet + bytes(-len(packet) % 16) for packet in packets)
        archive += b"\0" + packets[0]
        with TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic-sections.bin"
            path.write_bytes(archive)
            report = inspect_sections(path, "HEAD", "FOOT")
        self.assertEqual(report["valid_zlib"], 7)
        self.assertEqual(report["section_records"], 7)
        self.assertEqual(report["layouts"], {"HEAD FOOT": 7})


if __name__ == "__main__":
    unittest.main()
