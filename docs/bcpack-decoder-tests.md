# BCPack synthetic decoder checks

Leonida’s `tests/test_bcpack.py` constructs compressed streams from chosen symbols or BC blocks and compares the decoder’s output with the original symbols or independently packed block fields. These measurements use revision `b0befb4b88d6640354940117448ea19d52507584`. The original test file’s SHA-256 is `3033c40b1b2ced9e3973bbee30fe23241952ab410e766351c3a30269aad88520`. A separate source snapshot preserves the test, its three imported decoder modules and the upstream GPLv3 license. Extract the snapshot and run `python -IB tests/test_bcpack.py -v` from its root. All 12 tests passed on Windows with Python 3.14.2 using just those files and the standard library. [Original source](https://github.com/ItsNotRexed/Leonida/blob/b0befb4b88d6640354940117448ea19d52507584/tests/test_bcpack.py) · [Preserved source ZIP](https://github.com/wish131400/Xbox2Windows/archive/85b05fce98ee7685b1b49b2bad07360813808b38.zip)

## Constructing the compressed stream

1. Choose the output blocks and encode each field as a symbol on its format’s lane. A signed delta maps to `2*d` for nonnegative values and `-2*d-1` for negative values. To split an interleaved field, collect even bits into one value and odd bits into the other. For paired BC6H/BC7 selector deltas, rows 0–2 put the second pixel in the even positions. Row 3 puts the first pixel there.
2. Encode a lane’s symbols in reverse order. For symbol `s`, take `p = bit_length(s)`, frequency `f = freq[p]`, lower bound `b = 0` for `p = 0` or `2^(p-1)` otherwise, and cumulative start `c = base[p] + f*(s-b)`. When `c = 0`, set `c = 1` and decrement `f`. While the state `x >= f * 65536`, emit its low byte and shift right by eight. Then set `x = floor(x/f)*65536 + c + (x mod f)`. A flush fragment ends at decoder state `2^24`.
3. The first header byte carries the width reduction in bits 7–6, extended length in bit 5, flush in bit 4 and model selector in bits 3–0. Short payloads store length minus 1 in one byte. Long payloads store length minus 257 in two little-endian bytes. A fresh lane state starts with the encoder state in big-endian order followed by renormalization bytes in reverse emission order. A flush can omit up to eight trailing zero bytes, leaving at least one payload byte. A non-flush boundary can carry state into a fragment with a different probability model.
4. Interleave the lane byte streams in decoder consumption order. In each clock the feeder visits ascending lane numbers and grants at most eight byte requests. A lane with a pending symbol and a full output slot stalls. Release a symbol tuple when each active lane has supplied its slot, allowing finished lanes to retire. Compare the independently supplied decoded byte length, all symbols and the number of physical bytes consumed.

## Twelve checks at the pinned revision

| Test in `test_bcpack.py` | Input and required observation |
|---|---|
| `test_all_160_tables_valid_and_invertible` | Exercise widths 1–10 and model selectors 0–15. At symbols 0, 1, midpoint and maximum, lookup must recover the chosen symbol and advancing the constructed state must give 256 times its adjusted frequency. |
| `test_round_trip_12_and_16_lanes` | For codecs 1, 3, 4, 5, 6 and 7 generate 24 symbols per lane. Symbol at lane `i`, position `j` is `(13*i + 7*j) mod 2^width`, model selector `3*i mod 15`. All lanes must match. Three appended zero bytes are excluded from the consumed length. |
| `test_multi_fragment_flush_and_non_flush_and_3byte_header` | Use 400 BC1 symbols per lane. Lane 0 flushes after 100 symbols and changes width reduction from 2 to 3 and selector from 2 to 5. Lane 2 changes model from 1 to 4 after 150 symbols across a non-flush boundary. Large fragments exercise extended headers. All symbols and the consumed length must match. |
| `test_rejects_corrupt_and_trailing_data` | Start with eight zero symbols on each of 12 BC1 lanes. Independently append byte 01, drop two bytes, invert the last byte, request codec 99, or request 60 decoded bytes. Each case must raise a decoder error. |
| `test_unsupported_codec_rebuild_raises` | With empty input and 16 requested output bytes, codec 2 raises an unsupported-codec exception at block reconstruction and a decoder error at lane decoding. |
| `test_bc1_confirmed_and_provisional_history` | Three RGB565 blocks use distances 0, 1 and 3, exercising the zero base, preceding block and confirmed initial slot 255. All 24 bytes match with no warnings. Distance 250 from block 0 uses fitted slot 6. Strict mode refuses it. Provisional mode reproduces the chosen eight bytes and reports `BC1 history 6`. |
| `test_bc3_round_trip` | From the zero-distance predictor, reconstruct alpha endpoints 135 and 120, selector word `0123456789ab`, two RGB565 endpoints and four colour-selector rows. Compare all 16 bytes and require an empty provisional-label set. |
| `test_bc4_round_trip` | The initial endpoint pair (128,128) predicts (130,120), which predicts (140,110). The 3-bit selectors vary with row and column. Check both complete blocks. Separately, fitted slot 25 must be rejected in strict mode and yield its endpoint pair and label in provisional mode. |
| `test_bc5_round_trip` | Select the lowest confirmed history slot for four channel endpoints. The next block uses the first as its predictor. Apply wrapped endpoint deltas and distinct 48-bit selector patterns independently to red and green. Compare both complete blocks. |
| `test_bc6h_round_trip_and_provisional` | Compare three packed blocks in modes 1 (partition 5), 13 and 14. The latter two reference the preceding block. Exercise the endpoint bit permutations and reduced-width anchor selectors. Missing external history raises a diagnostic mentioning `--history` for the strict single-block case and the three-block provisional chain. Using the supplied table, slot 17 is confirmed, 42 fitted and 43 has a last-resort endpoint. Check the returned labels, confirmed/fitted output comparison and rejection of an invalid mode-11 anchor. |
| `test_bc7_config_completeness_and_empty_defaults` | Require 285 distinct configurations across modes 0–7 plus sentinel (255,255,0,0) at rank 285. The ten inferred ranks belong to mode 2. The default BC6H history classes and BC7 history bit-depths are zero. The default BC7 last-resort set is empty. |
| `test_bc7_round_trip_and_provisional` | Compare four packed outputs covering mode 6 with endpoint p-bits, mode 1 partition 3 with shared p-bits and a dynamic reference, mode 4 rotation 2 with index selection 1 and two selector planes, and the all-zero special case. Exercise rejection and labelling of an inferred signature, missing history on a three-block chain, confirmed slot 11, fitted slot 19 and partial slot 27 with six known bits and a last-resort flag. Inconsistent shared p-bits in mode 1 must raise a decoder error. |

The source also provides helpers to encode chosen BC1 blocks with a reference distance for each block, and chosen BC7 mode-6 blocks with optional initial endpoint history for the first block. For example, a BC1 block at index `i` with reference distance `d > i` uses initial history slot `256+i-d`. BC7 mode 6 packs a 3-bit selector for pixel 0 and 4-bit selectors for the remaining 15 pixels. A round trip through a fitted predictor can reproduce the chosen synthetic bytes even when that predictor’s value for a real texture remains uncertain.

## Fixed comparison bytes for independent decoders

Each example below is the first successful strict reconstruction in its format’s block test. The test first constructs the expected fields and asserts equality. Each input is one complete BCPack stream. Hex line breaks are for readability. Pass the codec number and decoded length to the candidate decoder, then compare the full byte string in stored block order. DDS headers and texture tiling are covered separately by the [archive export measurements](experiments.md#exporting-two-ttpf-entries-to-dds).

### BC1

Codec 1, 84 compressed bytes, 24 decoded bytes.

Compressed input

```text
1010101010101010040503040304050401018004808004800103000211300111
00000c0000000404040409032a33081206030905000510100404101001010404
00000101efb900000d0d6d3b1f1f868604040211
```

Expected blocks

```text
00f8e007123456781ff81f00aabbccddffff00000055aaff
```

### BC3

Codec 3, 75 compressed bytes, 16 decoded bytes.

Compressed input

```text
1010101010101010040403030303040301010110101010040000000000000400
02020e74f0b0445001010f90c85c002002021110101010030303031004010100
0000005030fb733010b631
```

Expected blocks

```text
8778ab89674523014329c11012345678
```

### BC4

Codec 4, 73 compressed bytes, 16 decoded bytes.

Compressed input

```text
1010101010101010030403030303030301010101101010100102000000000000
0000040f3cd4a89004031413f4cce89402101010100303030310101010000000
00d4c890ecccd094ac
```

Expected blocks

```text
827888168d1a3bd68c6e77e972e5c429
```

### BC5

Codec 5, 95 compressed bytes, 32 decoded bytes.

Compressed input

```text
1010101010101010040505050505050501010101010101010000000000000000
60020402a4d48c2581030501687ca80011030a06688c6c261010101005050505
01010101000000009cccfc347c68f41490a47cd4020704e0e82018b4e4b088
```

Expected blocks

```text
877bab89674523017d36547698badcfe8c776655443322118038ccbbaa998877
```

### BC6H

Codec 6, 151 compressed bytes, 48 decoded bytes.

Compressed input

```text
1010101010101010060607070705050501010101014040400000000000000a01
02031518073a001803030e03123145290504141d390c30201010101010101010
07070707070707061010100101010140101010000000000d0844180e122b3603
2c485c39050e2a7302020218eb87ea04030339293504040486e2644474128711
08081a6c853c1e02022991e409090916bf499605111111
```

Expected blocks

```text
68a452e3298f4a6662a5d867a630f521ab4ad5249831b0a3cb397e814bf6a20d
2f83110aba764f99e668c1492fa7d5b0
```

### BC7

Codec 7, 196 compressed bytes, 64 decoded bytes.

Compressed input

```text
101010101010101007070a0a0a0a0a0a01010101010101010000020202040402
0203ca745d1f00000302db3e483d05030505420a2500282e1010101010101010
0a08090a0a0a0a07010101010101010102000103020202000007006dbd0eeea2
03010512d1e11106440906080810172b05053f3b0d053226382b0e000b0a251e
1529180f091c0e0923251e121e2803031217030e0a041000262a192a00000000
0000003300000000680202030303030341410509030303030202020202414111
02020202
```

Expected blocks

```text
405952f78992e0e1a62fc7941eb6850d0e2925c6622c15d58283d987c6aed4a3
d035e9c3fc4a5f6c36727ce311573a8300000000000000000000000000000000
```
