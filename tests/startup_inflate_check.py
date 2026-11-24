"""Check the DirectStorage stand-in's zlib decoder (src/startup_stubs/inflate.h) against CPython's zlib.

The stand-in inflates zlib requests with its own RFC 1950/1951 decoder. The stub consumer only
feeds it stored blocks, a fixed block that repeats one byte at distance 1, and single-byte runs.
This check decodes streams that CPython's zlib encodes from seeded synthetic data with stored,
fixed and dynamic Huffman blocks (including a sparse alphabet whose block header needs all three
code-length repeat codes), back-references across the 32 KiB window and a sync flush between
blocks. Each decoded result must equal the input. The controls are streams the decoder must reject
without writing past the destination: one byte too little capacity and a truncated stream.

The distance bound is checked on bare deflate data, so neither the zlib header nor the Adler-32
check can reject it: after four literals, a match at distance 4 decodes and the same block with
distance 5 is rejected before the match copies anything.

The decoder looks Huffman codes up to 10 bits long up in a table. A differential case decodes 900
seeded random streams (sources, levels, strategies and flushes mixed; some with codes longer than the
table), each at exact capacity, one byte short, truncated and with flipped bits, and requires status,
size and bytes equal to the same probe built to decode one bit at a time, and to CPython's zlib except
where inflate.h decodes past an incomplete code set that zlib rejects. The control is the probe built with
one wrong table entry, which must differ on some case.

A boundary case runs small streams at every capacity up to one past their size and truncated to every
length: matches at distances 1 to 16 around the decoder's copy widths, stored blocks of 0 and 65535
bytes and stored blocks at every bit position. tests/startup_inflate_probe.cpp runs the decoder; no GPU
and no game files are involved.
"""
from pathlib import Path
import random
import struct
import subprocess
import sys
import tempfile
import zlib


def corpus(rng, size):
    # Random literals and copies of 3..258 bytes from 1..32000 bytes back, both log-uniform, so an
    # encoder emits most length and distance codes with their extra bits.
    data = bytearray(rng.randbytes(4096))
    while len(data) < size:
        if rng.random() < 0.3:
            data += rng.randbytes(rng.randint(1, 40))
            continue
        length = round(3 * 86 ** rng.random())
        start = len(data) - min(len(data), round(32000 ** rng.random()))
        for i in range(length):
            data.append(data[start + i])
    return bytes(data[:size])


def compress(data, level=9, strategy=zlib.Z_DEFAULT_STRATEGY):
    encoder = zlib.compressobj(level, zlib.DEFLATED, 15, 9, strategy)
    return encoder.compress(data) + encoder.flush()


def first_block_type(stream, mode="zlib"):
    return (stream[2 if mode == "zlib" else 0] >> 1) & 3


class Bits:
    """Deflate bit order: fields least significant bit first, Huffman codes most significant bit first."""

    def __init__(self):
        self.value = 0
        self.count = 0

    def put(self, value, count):
        self.value |= value << self.count
        self.count += count

    def code(self, code, count):
        self.put(int(format(code, "0%db" % count)[::-1], 2), count)

    def to_bytes(self):
        return self.value.to_bytes((self.count + 7) // 8, "little")


def words(rng, size):
    # Lowercase words and spaces: most literal codes are unused, so the dynamic block header needs
    # the zero-run codes 17 and 18 as well as code 16.
    out = bytearray()
    while len(out) < size:
        out += bytes(rng.choice(b"abcdefghijklmnopqrstuvwxyz") for _ in range(rng.randint(1, 9))) + b" "
    return bytes(out[:size])


def fixed_match_block(literals, distance_code, extra_bits, extra_value):
    # Bare deflate data, one final fixed block: the literals, a length-3 match, end of block.
    bits = Bits()
    bits.put(1, 1)
    bits.put(1, 2)
    for literal in literals:
        bits.code(0x30 + literal, 8)
    bits.code(257 - 256, 7)
    bits.code(distance_code, 5)
    bits.put(extra_value, extra_bits)
    bits.code(256 - 256, 7)
    return bits.to_bytes()


def reference(stream, mode):
    return zlib.decompress(stream, 15 if mode == "zlib" else -15)


def reference_rejects(stream, mode="zlib"):
    try:
        reference(stream, mode)
    except zlib.error:
        return True
    return False


def run(probe, work, name, stream, capacity, mode):
    source, output = work / (name + "." + mode), work / (name + ".out")
    source.write_bytes(stream)
    result = subprocess.run([str(probe), mode, str(source), str(capacity), str(output)],
                            capture_output=True, text=True, timeout=60)
    return result, output


def expect_decoded(probe, work, name, stream, data, capacity=None, mode="zlib"):
    assert reference(stream, mode) == data, name + ": the reference decoder disagrees with the input"
    capacity = len(data) if capacity is None else capacity
    result, output = run(probe, work, name, stream, capacity, mode)
    assert result.returncode == 0, "%s: exit %d: %s%s" % (name, result.returncode, result.stdout, result.stderr)
    assert result.stdout.strip() == "inflated %d" % len(data), "%s: %s" % (name, result.stdout.strip())
    decoded = output.read_bytes()
    if decoded != data:
        first = next((i for i, (a, b) in enumerate(zip(decoded, data)) if a != b), min(len(decoded), len(data)))
        raise AssertionError("%s: first mismatch at byte %d of %d" % (name, first, len(data)))
    print("%-22s block %d, %6d -> %6d bytes, decoded" % (name, first_block_type(stream, mode), len(stream), len(data)))


def expect_rejected(probe, work, name, stream, capacity, mode="zlib", decoded_before=None, invalid=True):
    # invalid: the stream itself is damaged, so the reference decoder must reject it too.
    assert not invalid or reference_rejects(stream, mode), name + ": the reference decoder accepted the stream"
    result, _ = run(probe, work, name, stream, capacity, mode)
    want = "rejected" if decoded_before is None else "rejected after %d bytes" % decoded_before
    assert result.returncode == 1 and result.stdout.strip() == want, \
        "%s: exit %d: %s%s" % (name, result.returncode, result.stdout, result.stderr)
    print("%-22s %6d bytes, capacity %6d, %s" % (name, len(stream), capacity, want))


OK, INSUFFICIENT, CORRUPT, BAD_CHECKSUM = range(4)  # x2w_inflate::InflateStatus
STATUS = ["ok", "insufficient_output", "corrupt_stream", "bad_checksum"]


def canonical(lengths):
    table, code = {}, 0
    for n in range(1, 16):
        for symbol, length in enumerate(lengths):
            if length == n:
                table[n, code] = symbol
                code += 1
        code <<= 1
    return table


def longest_code(stream):
    # Longest literal/length or distance code of the first block when it is a dynamic one, else 0.
    value, pos = int.from_bytes(stream[2:], "little"), 0

    def get(n):
        nonlocal pos
        pos += n
        return (value >> (pos - n)) & ((1 << n) - 1)

    get(1)
    if get(2) != 2:
        return 0
    nlen, ndist, ncode = get(5) + 257, get(5) + 1, get(4) + 4
    order = [16, 17, 18, 0, 8, 7, 9, 6, 10, 5, 11, 4, 12, 3, 13, 2, 14, 1, 15]
    code_lengths = [0] * 19
    for i in range(ncode):
        code_lengths[order[i]] = get(3)
    table, lengths = canonical(code_lengths), []
    while len(lengths) < nlen + ndist:
        n = code = 0
        while (n, code) not in table:
            code, n = code << 1 | get(1), n + 1
        symbol = table[n, code]
        if symbol < 16:
            lengths.append(symbol)
        elif symbol == 16:
            lengths += [lengths[-1]] * (3 + get(2))
        else:
            lengths += [0] * (3 + get(3) if symbol == 17 else 11 + get(7))
    return max(lengths)


def expected_status(stream, capacity):
    # CPython's zlib run as inflate_zlib_ex classifies: header, deflate data up to capacity + 1 bytes,
    # end of data, Adler-32. None where zlib rejects a code set as "invalid ... set": inflate.h rejects
    # over-subscribed sets too but accepts incomplete ones, so it may decode on from there.
    if len(stream) < 6 or stream[0] & 0x0F != 8 or (stream[0] << 8 | stream[1]) % 31 or stream[1] & 0x20:
        return CORRUPT, b""
    decoder = zlib.decompressobj(-15)
    try:
        out = decoder.decompress(stream[2:], capacity + 1)
    except zlib.error as error:
        return (None if " set" in str(error) else CORRUPT), b""
    if len(out) > capacity:
        return INSUFFICIENT, b""
    if not decoder.eof or len(decoder.unused_data) < 4:
        return CORRUPT, b""
    if int.from_bytes(decoder.unused_data[:4], "big") != zlib.adler32(out):
        return BAD_CHECKSUM, out
    return OK, out


ACCESS_VIOLATION = 0xC0000005  # the probe's input and destination each end at a no-access page


def run_batch(probe, work, name, cases, overrun=False):
    # overrun: an access past an input or destination returns a message instead of failing.
    records, results = work / (name + ".records"), work / (name + ".results")
    records.write_bytes(b"".join(struct.pack("<II", capacity, len(stream)) + stream for stream, capacity in cases))
    result = subprocess.run([str(probe), "batch", str(records), str(results)], capture_output=True, text=True,
                            timeout=60)
    if overrun and result.returncode == ACCESS_VIOLATION:
        return "access violation past an input or destination"
    assert result.returncode == 0, "%s: exit %d: %s%s" % (name, result.returncode, result.stdout, result.stderr)
    data, at, decoded = results.read_bytes(), 0, []
    for _ in cases:
        size = int.from_bytes(data[at + 1:at + 5], "little")
        decoded.append((data[at], data[at + 5:at + 5 + size]))
        at += 5 + size
    assert at == len(data), name + ": trailing result bytes"
    return decoded


def random_cases(rng, streams):
    # Seeded streams of up to 12 KiB from several sources, levels and strategies, some with a flush
    # between blocks; each at exact capacity, one byte short, truncated and with one to three bits flipped.
    strategies = [zlib.Z_DEFAULT_STRATEGY, zlib.Z_FILTERED, zlib.Z_HUFFMAN_ONLY, zlib.Z_RLE, zlib.Z_FIXED]
    sources = [
        lambda n: rng.randbytes(n),
        lambda n: corpus(rng, n),
        lambda n: words(rng, n),
        # Geometric byte values: rare symbols get codes longer than the decoder's table.
        lambda n: bytes(min(255, int(rng.expovariate(rng.choice([0.3, 0.6, 1.2])))) for _ in range(n)),
    ]
    cases, long_codes = [], 0
    for _ in range(streams):
        data = rng.choice(sources)(rng.choice([rng.randint(0, 300), rng.randint(300, 12288)]))
        encoder = zlib.compressobj(rng.randint(0, 9), zlib.DEFLATED, 15, 9, rng.choice(strategies))
        if len(data) > 64 and rng.random() < 0.3:
            cut = rng.randrange(len(data))
            stream = encoder.compress(data[:cut]) + encoder.flush(rng.choice([zlib.Z_SYNC_FLUSH, zlib.Z_FULL_FLUSH]))
            stream += encoder.compress(data[cut:]) + encoder.flush()
        else:
            stream = encoder.compress(data) + encoder.flush()
        long_codes += longest_code(stream) > 10
        cases.append((stream, len(data)))
        if data:
            cases.append((stream, len(data) - 1))
        cases.append((stream[:rng.randrange(len(stream))], len(data)))
        damaged = bytearray(stream)
        for _ in range(rng.randint(1, 3)):
            damaged[rng.randrange(2, len(damaged))] ^= 1 << rng.randrange(8)
        cases.append((bytes(damaged), len(data) + rng.choice([0, 0, 64])))
    return cases, long_codes


def compare(name, cases, fast, slow, truncated_stored=False):
    # Equal to the bit-at-a-time build in every case, and to CPython's zlib where it classifies the code sets.
    # truncated_stored: inflate.h checks a stored block's length against the input before the output, so a
    # truncated stored block that would not fit either is corrupt_stream where zlib, copying the bytes it
    # has, reports insufficient output first.
    compared = lenient = 0
    for index, ((stream, capacity), got, reference) in enumerate(zip(cases, fast, slow)):
        assert got == reference, "%s case %d: %s %d bytes, bit-at-a-time %s %d bytes" % (
            name, index, STATUS[got[0]], len(got[1]), STATUS[reference[0]], len(reference[1]))
        status, out = expected_status(stream, capacity)
        if truncated_stored and status == INSUFFICIENT and got[0] == CORRUPT and reference_rejects(stream):
            lenient += 1
            continue
        if status is None:
            if got[0] != CORRUPT:
                lenient += 1
                continue
            status = CORRUPT
        assert (got[0], got[1] if got[0] in (OK, BAD_CHECKSUM) else b"") == (status, out), \
            "%s case %d: %s, zlib %s" % (name, index, STATUS[got[0]], STATUS[status])
        compared += 1
    counts = [sum(1 for status, _ in fast if status == s) for s in range(4)]
    return compared, lenient, ", ".join("%s %d" % (STATUS[s], counts[s]) for s in range(4))


def expect_differential(probe, bitwise, work, rng):
    streams = 900
    cases, long_codes = random_cases(rng, streams)
    assert long_codes >= 20, "only %d streams have codes longer than 10 bits" % long_codes
    fast, slow = run_batch(probe, work, "random", cases), run_batch(bitwise, work, "random_bitwise", cases)
    compared, lenient, counts = compare("random", cases, fast, slow)
    print("%d random streams (%d with codes over 10 bits) as %d cases: equal to bit-at-a-time decoding in all, "
          "to zlib in %d (%d decoded past an incomplete code set zlib rejects); %s" % (
              streams, long_codes, len(cases), compared, lenient, counts))
    return cases, slow


def zlib_wrap(raw, data):
    return b"\x78\x01" + raw + zlib.adler32(data).to_bytes(4, "big")


def stored_after_fixed(literals, stored):
    # A fixed block of literals, so the stored block that follows starts at any bit position, then a
    # final fixed block whose length-3 match at distance 1 reaches back into the stored bytes.
    bits = Bits()
    bits.put(0, 1)
    bits.put(1, 2)
    for literal in literals:
        bits.code(0x30 + literal, 8) if literal < 144 else bits.code(0x190 + literal - 144, 9)
    bits.code(0, 7)
    bits.put(0, 1)
    bits.put(0, 2)
    bits.put(0, -bits.count % 8)
    bits.put(len(stored) | (len(stored) ^ 0xFFFF) << 16, 32)
    for byte in stored:
        bits.put(byte, 8)
    bits.put(1, 1)
    bits.put(1, 2)
    bits.code(1, 7)
    bits.code(0, 5)
    bits.code(0, 7)
    data = literals + stored + (literals + stored)[-1:] * 3
    return zlib_wrap(bits.to_bytes(), data), data


def boundary_cases(rng):
    # Streams whose ends meet every output capacity and input length: matches at each distance from 1 to 16
    # with lengths around 8 and 16 bytes and up to 258, some after a sync flush; stored blocks of 0 and 65535
    # bytes and stored blocks at every bit position. Each runs at every capacity up to one past its size
    # and truncated to every length, at full capacity and at a random one.
    streams = []
    for distance in range(1, 17):
        for strategy in (zlib.Z_DEFAULT_STRATEGY, zlib.Z_FIXED):
            data = bytearray(rng.randbytes(40))
            for length in list(range(3, 20)) + [24, 31, 32, 33, 258]:
                pattern = rng.randbytes(distance)
                data += (pattern * (length // distance + 2))[:distance + length] + rng.randbytes(1)
            encoder = zlib.compressobj(9, zlib.DEFLATED, 15, 9, strategy)
            if distance % 4 == 0:
                cut = rng.randrange(len(data))
                stream = encoder.compress(data[:cut]) + encoder.flush(zlib.Z_SYNC_FLUSH)
                stream += encoder.compress(data[cut:]) + encoder.flush()
            else:
                stream = encoder.compress(data) + encoder.flush()
            streams.append((stream, bytes(data)))
    for count in range(8):
        # count 9-bit literal codes put the stored block at bit position count + 2 modulo 8.
        for stored in (b"", rng.randbytes(1), rng.randbytes(300)):
            literals = bytes(rng.randrange(144, 256) for _ in range(count))
            literals += bytes(rng.randrange(144) for _ in range(rng.randint(1, 300)))
            streams.append(stored_after_fixed(literals, stored))
    cases = []
    for stream, data in streams:
        assert reference(stream, "zlib") == data
        cases += [(stream, capacity) for capacity in range(len(data) + 2)]
        cases += [(stream[:cut], capacity) for cut in range(len(stream))
                  for capacity in (len(data), rng.randrange(len(data) + 1))]
    big = rng.randbytes(65535)
    stream = zlib_wrap(b"\x01\xff\xff\x00\x00" + big, big)
    assert reference(stream, "zlib") == big
    cases += [(stream, capacity) for capacity in (0, 1, 65534, 65535, 65536)]
    cases += [(stream[:cut], 65535) for cut in range(len(stream) - 12, len(stream))]
    return cases, len(streams) + 1


def expect_boundaries(probe, bitwise, work, rng):
    cases, streams = boundary_cases(rng)
    fast, slow = run_batch(probe, work, "boundary", cases), run_batch(bitwise, work, "boundary_bitwise", cases)
    compared, lenient, counts = compare("boundary", cases, fast, slow, truncated_stored=True)
    print("%d boundary streams as %d cases: equal to bit-at-a-time decoding in all, to zlib in %d (%d truncated "
          "in a stored block that does not fit either); %s" % (streams, len(cases), compared, lenient, counts))
    return cases, slow


def expect_faulty_caught(faulty, work, cases, reference):
    got = run_batch(faulty, work, "random_faulty", cases)
    wrong = sum(1 for a, b in zip(got, reference) if a != b)
    assert wrong, "the faulty-table control decoded every random case like the reference"
    print("faulty-table control: %d of %d random cases differ from bit-at-a-time decoding, caught" % (wrong, len(cases)))


def expect_margin_caught(faulty, work, cases):
    # The fast loop entered one output byte short of the longest match: a 258-byte match 257 bytes before
    # the capacity writes past the destination.
    got = run_batch(faulty, work, "boundary_margin", cases, overrun=True)
    assert isinstance(got, str), "the faulty-margin control decoded every boundary case within its destination"
    print("faulty-margin control: %s, caught" % got)


def main(probe, bitwise, faulty, faulty_margin):
    probe, bitwise, faulty = Path(probe).resolve(), Path(bitwise).resolve(), Path(faulty).resolve()
    faulty_margin = Path(faulty_margin).resolve()
    rng = random.Random(1149)
    text = corpus(rng, 96 * 1024)
    noise = rng.randbytes(70000)
    with tempfile.TemporaryDirectory() as temporary:
        work = Path(temporary)

        stored = zlib.compress(noise, 0)
        assert first_block_type(stored) == 0
        expect_decoded(probe, work, "stored", stored, noise)

        fixed = compress(text, strategy=zlib.Z_FIXED)
        assert first_block_type(fixed) == 1
        expect_decoded(probe, work, "fixed", fixed, text)

        dynamic = compress(text)
        assert first_block_type(dynamic) == 2
        expect_decoded(probe, work, "dynamic", dynamic, text)
        expect_decoded(probe, work, "dynamic_spare_capacity", dynamic, text, len(text) + 4096)
        sparse = words(rng, 32 * 1024)
        sparse_stream = compress(sparse)
        assert first_block_type(sparse_stream) == 2
        expect_decoded(probe, work, "dynamic_sparse", sparse_stream, sparse)

        # A sync flush ends the first part with an empty stored block; the second part copies from the
        # first across it, so the decoder must keep its window and bit position over the boundary.
        head, tail = noise[:20000], noise[5000:9000] + noise[100:3000] + text[:8192]
        encoder = zlib.compressobj(6)
        flushed = encoder.compress(head) + encoder.flush(zlib.Z_SYNC_FLUSH)
        assert flushed.endswith(b"\x00\x00\xff\xff")
        flushed += encoder.compress(tail) + encoder.flush()
        expect_decoded(probe, work, "sync_flush", flushed, head + tail)

        expect_decoded(probe, work, "empty", zlib.compress(b""), b"")

        # Controls: streams that do not fit or cannot be decoded are rejected.
        expect_rejected(probe, work, "dynamic_short_capacity", dynamic, len(text) - 1, invalid=False)
        expect_rejected(probe, work, "dynamic_truncated", dynamic[:len(dynamic) // 2], len(text))

        # The distance bound, on bare deflate data with room to spare: after "ABCD", distance 4 (code 3)
        # starts the match at the first output byte; distance 5 (code 4, extra bit 0) starts it one byte
        # before the output and must be rejected with only the four literals decoded.
        expect_decoded(probe, work, "raw_distance_4", fixed_match_block(b"ABCD", 3, 0, 0), b"ABCDABC", 64, "raw")
        expect_rejected(probe, work, "raw_distance_5", fixed_match_block(b"ABCD", 4, 1, 0), 64, "raw", 4)
        # The same with input and capacity to spare, so the decoder's fast loop meets the match.
        expect_rejected(probe, work, "raw_distance_5_fast", fixed_match_block(b"ABCD", 4, 1, 0) + bytes(32), 4096,
                        "raw", 4)

        cases, reference = expect_differential(probe, bitwise, work, rng)
        expect_faulty_caught(faulty, work, cases, reference)
        # Its own seed, so the random case keeps its streams.
        cases, _ = expect_boundaries(probe, bitwise, work, random.Random(1149 + 1))
        expect_margin_caught(faulty_margin, work, cases)
    print("inflate.h matches zlib %s in 8 cases and rejects 3 controls" % zlib.ZLIB_RUNTIME_VERSION)


if __name__ == "__main__":
    if len(sys.argv) != 5:
        sys.exit("usage: startup_inflate_check.py <startup_inflate_probe.exe> <startup_inflate_probe_bitwise.exe> "
                 "<startup_inflate_probe_faulty.exe> <startup_inflate_probe_faulty_margin.exe>")
    main(*sys.argv[1:])
