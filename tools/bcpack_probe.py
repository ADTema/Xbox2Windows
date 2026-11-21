"""Test the published fixed-symbol rANS model against an eight-lane BCPack prefix."""
import argparse
import json
from pathlib import Path


LOWER = 1 << 24
SCALE = 1 << 16
EXCEPTIONS = {0xdc: 4, 0xdd: 8, 0xde: 32}


def probe(prefix, blocks):
    if len(prefix) != 48 or not 1 <= blocks <= 1 << 20:
        raise ValueError("Expected a 48-byte prefix and a positive bounded block count")
    matches = []
    for lane in range(8):
        mode, budget, *state_bytes = prefix[lane::8]
        if mode not in EXCEPTIONS:
            continue
        freq = SCALE - EXCEPTIONS[mode]
        state = LOWER
        refills = 0
        for _ in range(blocks):
            if state >= (LOWER // SCALE) * 256 * freq:
                state >>= 8
                refills += 1
            quotient, remainder = divmod(state, freq)
            state = quotient * SCALE + remainder + 1
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
        matches.append({"lane": lane, "mode": mode, "refill_bytes": refills, "status": status})
    return matches


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("packet", type=Path)
    parser.add_argument("--blocks", required=True, type=int)
    args = parser.parse_args()
    with args.packet.open("rb") as stream:
        print(json.dumps(probe(stream.read(48), args.blocks), indent=2))
