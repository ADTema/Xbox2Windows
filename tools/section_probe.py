"""Count bounded zlib streams containing a complete table of tagged sections."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import struct
import zlib


def sections(data):
    """Return four-character tags when big-endian section lengths exactly cover the buffer."""
    tags = []
    offset = 0
    while offset + 8 <= len(data):
        tag, size = struct.unpack_from(">4sI", data, offset)
        if not re.fullmatch(b"[A-Z0-9_]{4}", tag) or size < 8 or offset + size > len(data):
            return ()
        tags.append(tag.decode("ascii"))
        offset += size
    return tuple(tags) if offset == len(data) else ()


def scan_window(data, base, first, last):
    valid = 0
    layouts = Counter()
    # A common RFC 1950 header with a 32 KiB history and no preset dictionary.
    for m in re.finditer(b"\x78[\x01\x5e\x9c\xda]", data):
        pos = m.start()
        if (base + pos) % 16:
            continue
        decoder = zlib.decompressobj()
        try:
            decoded = decoder.decompress(memoryview(data)[pos:pos + (256 << 10)], (256 << 10) + 1)
        except zlib.error:
            continue
        if not decoder.eof or len(decoded) > 256 << 10:
            continue
        valid += 1
        if decoded.startswith(first.encode("ascii")):
            tags = sections(decoded)
            if tags and tags[0] == first and tags[-1] == last:
                layouts[" ".join(tags)] += 1
    return valid, layouts


def inspect(path, first, last):
    size = path.stat().st_size
    window = 8 << 20
    # Merge overlapping windows on small files so a stream is counted only once.
    spans = []
    for start in (0, max(0, (size-window)//2), max(0, size-window)):
        end = min(size, start + window)
        if spans and start <= spans[-1][1]:
            spans[-1][1] = end
        else:
            spans.append([start, end])
    valid = 0
    layouts = Counter()
    with path.open("rb") as stream:
        for start, end in spans:
            stream.seek(start)
            count, found = scan_window(stream.read(end-start), start, first, last)
            valid += count
            layouts.update(found)
    return {"file":path.name, "bytes_sampled":sum(b-a for a,b in spans),
            "valid_zlib":valid, "section_records":sum(layouts.values()), "layouts":layouts}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archives", type=Path, nargs="+")
    parser.add_argument("--first", required=True)
    parser.add_argument("--last", required=True)
    args = parser.parse_args()
    print(json.dumps([inspect(p, args.first, args.last) for p in args.archives], indent=2))
