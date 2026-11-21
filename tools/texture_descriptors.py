"""Summarize the ETPF texture descriptors in the first raw range of an RDS5 archive."""
import argparse
from collections import Counter
from collections.abc import Iterator
from itertools import pairwise
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


class Tables(NamedTuple):
    archive: PagedResource
    metadata: PagedResource
    boundaries: int
    records: int
    logical_size: int


class PageMap(NamedTuple):
    logical_offset: int
    file_offset: int


def boundary(data: bytes, offset: int = 0) -> Boundary:
    low, high = struct.unpack_from("<II", data, offset)
    return Boundary((low & 0x03ffffff) * 256,
                    ((high & 0xfffff) * 4 + (low >> 30)) * 4096,
                    (low >> 26) & 15)


def read_tables(stream: BinaryIO) -> Tables:
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
    return Tables(archive, metadata, count, records, logical_size)


def page_address(location: int, logical_size: int) -> int:
    address = (location & 0x1fffff) * 4096
    if address >= logical_size:
        raise ValueError("ETPF descriptor page outside the declared logical archive")
    return address


def inventory(stream: BinaryIO) -> Counter[Descriptor]:
    tables = read_tables(stream)
    table_bytes = tables.records * 16
    counts: Counter[Descriptor] = Counter()
    for offset in range(0, table_bytes, 4096):
        batch = tables.metadata.read(16 + offset, min(4096, table_bytes - offset))
        for shape, flags, location in struct.iter_unpack("<III4x", batch):
            page_address(location, tables.logical_size)
            item = Descriptor((shape & 0x3fff) + 1, ((shape >> 14) & 0x3fff) + 1,
                              (flags >> 3) & 127, flags >> 24)
            counts[item] += 1
    return counts


def iter_boundaries(tables: Tables) -> Iterator[Boundary]:
    table_bytes = tables.boundaries * 8
    if table_bytes > 1 << 20:
        raise ValueError("RDS5 boundary table exceeds 1 MiB mapping budget")
    for offset in range(0, table_bytes, 4096):
        batch = tables.archive.read(16 + offset, min(4096, table_bytes - offset))
        for position in range(0, len(batch), 8):
            yield boundary(batch, position)


def raw_page_map(stream: BinaryIO, index: int) -> PageMap:
    tables = read_tables(stream)
    if not 0 <= index < tables.records:
        raise ValueError("Descriptor index outside the ETPF table")
    location, = struct.unpack("<I", tables.metadata.read(16 + index * 16 + 8, 4))
    address = page_address(location, tables.logical_size)
    mapped: PageMap | None = None
    for left, right in pairwise(iter_boundaries(tables)):
        if right.stored <= left.stored or right.logical <= left.logical:
            raise ValueError("RDS5 boundaries must increase in both address spaces")
        if left.logical <= address < right.logical:
            if left.codec:
                raise ValueError("Descriptor page belongs to a coded RDS5 range")
            if right.stored - left.stored != right.logical - left.logical:
                raise ValueError("Raw mapping requires equal stored and logical range sizes")
            mapped = PageMap(address, left.stored + address - left.logical)
    if mapped is None:
        raise ValueError("Descriptor page has no RDS5 range")
    return mapped


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--raw-page-map", type=int, metavar="INDEX",
                        help="Report offsets of a zero-based descriptor's first 4 KiB page in an equal-size raw range")
    args = parser.parse_args()
    try:
        with args.archive.open("rb") as file:
            if args.raw_page_map is None:
                counts = inventory(file)
                print(json.dumps({"descriptor_count": sum(counts.values()), "groups": [
                    {**item._asdict(), "count": counts[item]} for item in sorted(counts)
                ]}, indent=2))
            else:
                print(json.dumps(raw_page_map(file, args.raw_page_map)._asdict(), indent=2))
    except (OSError, ValueError) as exc:
        parser.exit(1, f"{args.archive}: {exc}\n")
