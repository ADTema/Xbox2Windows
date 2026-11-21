"""Test the published fixed-symbol rANS model against an eight-lane BCPack prefix.

The default header is interleaved at an eight-byte stride. `lane_stride=6` reads
eight contiguous six-byte records for diagnostics.
"""
import argparse
import json
from pathlib import Path


LOWER = 1 << 24
SCALE = 1 << 16
EXCEPTIONS = {0xdc: 4, 0xdd: 8, 0xde: 32}
LANE_STRIDES = (6, 8)


def lane_record(prefix, lane, lane_stride):
    """Return the six bytes for one lane in the selected header layout."""
    if lane_stride == 8:
        return prefix[lane::8]
    return prefix[lane * lane_stride:(lane + 1) * lane_stride]


def scan_lanes(prefix, *, lane_stride=8):
    """Report each lane's mode and budget without attempting a decode."""
    if len(prefix) != 48:
        raise ValueError("Expected a 48-byte prefix")
    if lane_stride not in LANE_STRIDES:
        raise ValueError("Expected lane stride 6 or 8")
    lanes = []
    for lane in range(8):
        mode, budget, *state_bytes = lane_record(prefix, lane, lane_stride)
        lanes.append({
            "lane": lane,
            "mode": mode,
            "budget": budget,
            "state": bytes(state_bytes).hex(),
            "known_constant_mode": mode in EXCEPTIONS,
        })
    return lanes


def probe(prefix, blocks, *, prefetch_mask=0, prefetch=b"", next_mask=0, next_bytes=b"",
          lane_stride=8):
    if len(prefix) != 48 or not 1 <= blocks <= 1 << 20:
        raise ValueError("Expected a 48-byte prefix and a positive bounded block count")
    if lane_stride not in LANE_STRIDES:
        raise ValueError("Expected lane stride 6 or 8")
    if not 0 <= prefetch_mask <= 255 or len(prefetch) != prefetch_mask.bit_count():
        raise ValueError("Expected one first-round byte per participating lane")
    if not 0 <= next_mask <= 255 or len(next_bytes) != next_mask.bit_count():
        raise ValueError("Expected one second-round byte per participating lane")
    rounds = ((prefetch_mask, prefetch, 48), (next_mask, next_bytes, 48 + len(prefetch)))
    matches = []
    for lane in range(8):
        mode, budget, *state_bytes = lane_record(prefix, lane, lane_stride)
        if mode not in EXCEPTIONS:
            continue
        freq = SCALE - EXCEPTIONS[mode]
        state = LOWER
        emitted = []
        for _ in range(blocks):
            if state >= (LOWER // SCALE) * 256 * freq:
                emitted.append(state & 255)
                state >>= 8
            quotient, remainder = divmod(state, freq)
            state = quotient * SCALE + remainder + 1
        # Encoding runs backwards. The last emitted byte is consumed first.
        refill_bytes = emitted[::-1]
        refills = len(refill_bytes)
        if budget != refills + 3 or state != int.from_bytes(state_bytes, "big"):
            continue
        status = "header_match"
        if refills == 0:
            for _ in range(blocks):
                quotient, slot = divmod(state, SCALE)
                if not 1 <= slot <= freq:
                    raise ValueError("Predicted constant lane contains an escape")
                state = freq * quotient + slot - 1
                if state < LOWER:
                    raise ValueError("Decoder requires an unbudgeted input byte")
            if state != LOWER:
                raise ValueError("Incorrect rANS terminal state")
            status = "verified_constant_lane"
        match = {"lane": lane, "mode": mode, "refill_bytes": refills, "status": status}
        # Each round in which the lane reads takes its next refill byte, whichever round that is.
        reads = 0
        for mask, data, start in rounds:
            if not mask & (1 << lane):
                continue
            index = (mask & ((1 << lane) - 1)).bit_count()
            if reads < refills:
                name = ("first", "second")[reads]
                match[f"{name}_refill_offset"] = start + index
                match[f"{name}_refill_matches"] = data[index] == refill_bytes[reads]
            else:
                # The header budget leaves this lane no byte for the read.
                match.setdefault("unbudgeted_read_offsets", []).append(start + index)
            reads += 1
        matches.append(match)
    return matches


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("packet", type=Path)
    parser.add_argument("--blocks", type=int,
                        help="Independent block count for the stream; required unless --scan-lanes is used")
    parser.add_argument("--prefetch-mask", type=lambda s: int(s, 0), default=0, choices=range(256),
                        metavar="MASK", help="Bit i means lane i reads a byte in the first round after the header")
    parser.add_argument("--next-mask", type=lambda s: int(s, 0), default=0, choices=range(256),
                        metavar="MASK", help="Bit i means lane i reads a byte in the immediately following round")
    parser.add_argument("--lane-stride", type=int, choices=LANE_STRIDES, default=8,
                        help="Header layout: 8 for the interleaved default, 6 for contiguous six-byte records")
    parser.add_argument("--scan-lanes", action="store_true",
                        help="Print each lane's mode and budget without attempting a decode")
    args = parser.parse_args()
    if not args.scan_lanes and args.blocks is None:
        parser.error("--blocks is required unless --scan-lanes is used")
    with args.packet.open("rb") as stream:
        prefix = stream.read(48)
        prefetch = stream.read(args.prefetch_mask.bit_count())
        next_bytes = stream.read(args.next_mask.bit_count())
        if args.scan_lanes:
            result = {"lane_stride": args.lane_stride,
                      "lanes": scan_lanes(prefix, lane_stride=args.lane_stride)}
        else:
            result = probe(prefix, args.blocks, prefetch_mask=args.prefetch_mask, prefetch=prefetch,
                           next_mask=args.next_mask, next_bytes=next_bytes,
                           lane_stride=args.lane_stride)
        print(json.dumps(result, indent=2))
