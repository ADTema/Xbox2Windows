"""Summarize the ETPF texture descriptors in the first raw range of an RDS5 archive."""
import argparse
from collections import Counter
import json
from pathlib import Path
import struct
from typing import BinaryIO, NamedTuple

from paged_resource import PagedResource, Segment


class Descriptor(NamedTuple):
    width: int
    height: int
    dxgi_format: int
    mip_marker: int


class Boundary(NamedTuple):
    stored: int
    logical: int
    codec: int


def boundary(data: bytes, offset: int = 0) -> Boundary:
    low, high = struct.unpack_from("<II", data, offset)
    return Boundary((low & 0x03ffffff) * 256,
                    ((high & 0xfffff) * 4 + (low >> 30)) * 4096,
                    (low >> 26) & 15)


def inventory(stream: BinaryIO) -> Counter[Descriptor]:
    size = stream.seek(0, 2)
    if size < 32:
        raise ValueError("Truncated RDS5 header")
    archive = PagedResource(stream, [Segment(0, size, size, "raw")])
    header = archive.read(0, 32)
    magic, count, size_field = struct.unpack_from("<4sIQ", header)
    logical_size = size_field & ((1 << 40) - 1)
    if magic != b"RDS5" or count < 2:
        raise ValueError("Expected an RDS5 header and at least two boundaries")
    first = boundary(header, 16)
    if first.logical or first.codec:
        raise ValueError("Expected raw metadata at logical offset zero")
    table_end = 16 + count * 8
    if not table_end <= first.stored < size:
        raise ValueError("RDS5 boundary table exceeds the header area")
    last = boundary(archive.read(table_end - 8, 8))
    if last.stored > size or last.logical != logical_size:
        raise ValueError("RDS5 terminal boundary disagrees with archive extents")
    second = boundary(header, 24)
    if not first.stored < second.stored <= last.stored or not 0 < second.logical <= logical_size:
        raise ValueError("Invalid first RDS5 range")

    # The first stored range can include alignment padding beyond its logical end.
    extent = min(second.stored - first.stored, second.logical)
    metadata = PagedResource(stream, [Segment(first.stored, extent, extent, "raw")])
    tag, records = struct.unpack("<4s4xI4x", metadata.read(0, 16))
    if tag != b"ETPF":
        raise ValueError("Expected ETPF at the first RDS5 boundary")
    table_bytes = records * 16
    if table_bytes > min(1 << 20, extent - 16):
        raise ValueError("ETPF descriptor table exceeds its first range or 1 MiB budget")

    counts: Counter[Descriptor] = Counter()
    for offset in range(0, table_bytes, 4096):
        batch = metadata.read(16 + offset, min(4096, table_bytes - offset))
        for shape, flags, location in struct.iter_unpack("<III4x", batch):
            if (location & 0x1fffff) * 4096 >= logical_size:
                raise ValueError("ETPF descriptor page outside the declared logical archive")
            item = Descriptor((shape & 0x3fff) + 1, ((shape >> 14) & 0x3fff) + 1,
                              (flags >> 3) & 127, flags >> 24)
            counts[item] += 1
    return counts


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    args = parser.parse_args()
    try:
        with args.archive.open("rb") as file:
            counts = inventory(file)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"{args.archive}: {exc}\n")
    print(json.dumps({"descriptor_count": sum(counts.values()), "groups": [
        {**item._asdict(), "count": counts[item]} for item in sorted(counts)
    ]}, indent=2))
