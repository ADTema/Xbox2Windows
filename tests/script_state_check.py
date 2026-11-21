"""Source-built paged record for state hierarchy, typed values and lexical hashes."""
from pathlib import Path
import struct
import sys
import tempfile
import unittest
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from script_state_probe import inspect, inspect_tree, joaat


def fixture(*, damage_value=False, self_parent=False):
    example = "synthetic_orbit"
    def attr(name, spelling, raw, kind):
        return struct.pack("<IIIBBH", joaat(name), joaat(spelling), raw, kind, 1, 0)

    attrs = b"".join((
        attr("id", example, 0, 5), attr("priority", "9", 9, 3),
        attr("blendduration", "37", 37, 3),
        attr("orbitdistance", "1.500000", 0x40000000 if damage_value else 0x3fc00000, 2),
        attr("pitchlimits", "-0.250000,0.500000,0.000000", 0, 1),
        attr("headinglimits", "-1.000000,1.000000,0.000000", 1, 1),
    ))
    nodes = b"".join(struct.pack("<I5H2B", joaat(name), parent, 0, 0, 0, start, count, 1)
                     for name, parent, start, count in (("state", 65535, 0, 1),
                                                        ("fixture_child", int(self_parent), 1, 5)))
    vecs = struct.pack("<6f", -0.25, 0.5, 0, -1, 1, 0)
    root = b"".join(struct.pack("<IIQ", n, n, ref) for n, ref in ((6, 2), (0, 0), (2, 4), (0, 0), (2, 3)))
    blocks = (root, attrs, nodes, vecs)
    instances = bytearray()
    for kind, blob in enumerate(blocks, 1):
        instances.extend(struct.pack("<IIQ", kind, len(blob), 0xaaaaaaaaaaaaaaaa))
    for blob in blocks:
        instances.extend(bytes(-(len(instances) + 8) % 16))
        instances.extend(blob)
    definitions = ((80, (("attributes", 0, 0x5c),)), (16, (("name", 0, 0x4a), ("valueHash", 4, 0x4a))),
                   (16, (("name", 0, 0x4a), ("parentIndex", 4, 0x13), ("attributeCount", 14, 0x11))),
                   (12, tuple((s, i * 4, 0x14) for i, s in enumerate("xyz"))))
    schema = b"".join(struct.pack("<IIIIQIHH", kind, 0, 0, 0, 0, size, 0, len(fields))
                      for kind, (size, fields) in enumerate(definitions, 1))
    schema += b"".join(struct.pack("<IIBBHI", joaat(s), off, code, 0, 0, 0)
                       for _, fields in definitions for s, off, code in fields)
    header = bytearray(80)
    header[:5] = b"0DRPz"
    struct.pack_into("<I", header, 16, 1)
    struct.pack_into("<3H", header, 56, 4, 0, 4)
    body = bytearray()
    for tag, part in ((b"PSIN", instances), (b"LSCH", schema), (b"LENM", b""), (b"LSNS", bytes(65536)),
                      (b"LGID", b""), (b"LRSC", header)):
        body += struct.pack(">4sI", tag, len(part) + 8) + part
    body += struct.pack(">4sII8x", b"CHKS", 20, len(body) + 20)
    archive = bytearray(b"9FPR")
    for i in range(0, len(body), 65536):
        archive += bytes(-len(archive) % 16)
        archive += zlib.compress(body[i:i + 65536])
    return archive


class DuplicateStateIdTests(unittest.TestCase):
    def test_duplicate_state_id_is_rejected(self):
        # Two label-kind id attributes on one state: the replay raises, so the probe must not let the last win.
        nodes = [(joaat("state"), 65535, 0, 0, 0, 0, 2, 1)]
        attrs = [(joaat("id"), joaat(label), 0, 5, 1, 0) for label in ("first", "second")]
        with self.assertRaisesRegex(ValueError, "Duplicate state ID"):
            inspect_tree(nodes, attrs, b"", joaat("second"))


class ScriptStateTests(unittest.TestCase):
    def run_probe(self, **options):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "original.rpf"
            path.write_bytes(fixture(**options))
            return inspect(path, "synthetic_orbit")

    def test_linked_values(self):
        result = self.run_probe()
        self.assertEqual(result["counts"]["all_five_literals_verified"], 1)
        self.assertEqual(result["first_verified_example"]["orbitdistance"], "1.500000")

    def test_different_binary_value(self):
        result = self.run_probe(damage_value=True)
        self.assertEqual(result["counts"]["camera_parameter_sets"], 1)
        self.assertIsNone(result["first_verified_example"])

    def test_parent_cycle(self):
        with self.assertRaisesRegex(ValueError, "parent index"):
            self.run_probe(self_parent=True)


if __name__ == "__main__":
    unittest.main()
