# Reproducing BCPack texture exports offline

The two measurements use `data/ttdb/ui/ttdb_ui.ttpf`, length 845,115,648 bytes, SHA-256 `dc983ed7f6b78d1693fa5757f17c03bafb790e851594fdf4d412579b61d867f6`. Use the local pool for the archive examples. The synthetic checks need only Python and the [source listings included with this document](bcpack-offline-source.md). The original checkout commands, version identifiers and export measurements are in [the experiment record](experiments.md#exporting-two-ttpf-entries-to-dds). The [decoder test reference](bcpack-decoder-tests.md) includes six complete compressed streams and their expected bytes.

## Prepare the offline tools

From the root of this checkout, run the following PowerShell block with Python 3.14.2. It reads the local Markdown appendix, verifies the SHA-256 of every source listing, writes the eight files to a fresh directory and runs the twelve synthetic checks. The test runner should print `Ran 12 tests` and `OK`.

```powershell
$out = New-Item -ItemType Directory -Path out/bcpack-offline-run -ErrorAction Stop
@'
import hashlib
import re
import sys
from pathlib import Path

base = Path(sys.argv[1])
doc = Path("docs/bcpack-offline-source.md").read_text(encoding="utf-8")
expected = {"LICENSE", "history_snapshot.py", "tools/bcpack.py", "tools/bcpack_tables.py",
            "tools/bcpack_tables_bptc.py", "tools/tex_headers.py", "tools/ttpf_mips.py",
            "tests/test_bcpack.py"}
parts = re.findall(r"^## ([^\n]+)\n\nSHA-256 `([a-f0-9]{64})`\n\n````(?:text|python)\n(.*?)^````$", doc, re.M | re.S)
assert len(parts) == len(expected) and {name for name, _, _ in parts} == expected
for name, digest, listing in parts:
    data = listing.encode("utf-8")
    assert hashlib.sha256(data).hexdigest() == digest, name
    path = base / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
'@ | python -IB - "$out"
if ($LASTEXITCODE -ne 0) { throw 'Source integrity check failed' }
python -IB "$out/tests/test_bcpack.py" -v
```

## Read the physical and virtual ranges

Read little-endian integers. Check the four-byte magic `RDS5` at offset 0. The 32-bit count at offset 4 includes two administrative entries. At offset 8, the low 56 bits give the virtual size and the high byte is 22 for this layout. The table starts at offset 24, contains `count-1` eight-byte values, and ends with a boundary sentinel. For each adjacent pair, apply the following arithmetic separately to the current value and the next. All offsets in the table below are bytes from the beginning of their respective address spaces.

```python
def boundary(v):
    physical = (v & 0x03ffffff) << 8
    virtual = ((v >> 30) & 0x3fffff) << 12
    return physical, virtual

start, logical = boundary(current)
end, logical_end = boundary(following)
codec = (current >> 26) & 15
packed_bytes = end - start - (current >> 52)
decoded_bytes = logical_end - logical
```

Verify the sentinel's physical and virtual positions against file length and declared virtual size. Check that both spans are positive. Codec 0 copies stored bytes, codec 8 uses zlib, and codecs 1, 3, 4, 5, 6 and 7 use BCPack. Codec 2 is unsupported by this implementation. Read exactly `packed_bytes` starting at `start`. Supply `decoded_bytes` to the decoder. The original issue's offset correction matters above 4 GiB. For example, `0x1d000000` selects codec 7 at byte 4,294,967,296.

| Pool entry | Physical start | Compressed bytes | Trailing pad | Virtual start | Decoded bytes | Codec |
|---:|---:|---:|---:|---:|---:|---:|
| 0 | 738,560 | 87,933 | 899 | 643,072 | 131,072 | 1 |
| 8253 | 693,308,160 | 123,888 | 272 | 1,146,396,672 | 131,072 | 7 |

Round the end of the RDS5 table up to a 256-byte boundary to find the embedded `ETPF` header. Verify version 634. Read the texture count and record-area length at offsets +8 and +12. Descriptor `i` begins at `ETPF+16+16*i`. Interpret it as four little-endian 32-bit words `a,b,c,d`. Width and height are `1+(a & 0x3fff)` and `1+((a >> 14) & 0x3fff)`. The mip count is `(a >> 28)+(b & 7)`. DXGI format is `(b >> 3) & 127`, depth is `1+((b >> 10) & 2047)`, and dimension is `(b >> 21) & 3`. The mode is `b >> 23` and the virtual base is `(c & 0x1fffff) << 12`. Map each requested mip or slice span into the decoded chunks by virtual range. Each example here uses one whole chunk.

## Decode symbols and restore blocks

The [format table](experiments.md#bcpack-decoding-by-bc-format) gives each lane width. Each lane emits `decoded_bytes / 8` symbols. The [test reference](bcpack-decoder-tests.md#constructing-the-compressed-stream) specifies the fragment headers, state, byte order and eight-byte feeder. For decoding, select the frequency row for the fragment width and model. Look up the symbol covering `x & 65535`, then advance with `x = f*(x >> 16) + (x & 65535) - c` using the adjusted frequency and cumulative start for that symbol. When the state falls below `2^24`, shift in the lane's next byte. The feeder, flush boundary and terminal state checks in the listing determine which physical byte belongs to which lane. Successful entropy termination alone says nothing about the initial endpoint colours.

For block reconstruction, signed residuals use `(v >> 1) ^ -(v & 1)`. Apply the residual modulo the field's bit width to the selected predictor. A positive distance reaching before the first block addresses initial history. BC1 reconstructs two RGB565 endpoints and maps four quadrant ranks to sixteen selectors. BC3 combines alpha predictor residuals and alpha selector pairs with RGB565 endpoints and four colour quadrants. BC4 uses one endpoint pair and eight ranked selector pairs. BC5 reconstructs the two channels separately and stores the red block first. BC6H and BC7 track endpoint and index predictors separately. The selected mode determines the endpoint precision, partitions and reduced-width anchor selectors. BC7 additionally uses configuration rank, rotation, index selection and mode-specific p-bits. The complete table values and field-packing branches for each mode are in the local listings for `bcpack_tables.py`, `bcpack_tables_bptc.py` and `bcpack.py`. Six strict input/output examples allow byte comparisons at this step, before writing a DDS.

## Undo the 2D tiling and write a DDS

Both examples use one 64 KiB-tiled mip, with tile origin (0,0). Entry 0 contains 128 × 128 BC1 blocks, each eight bytes. One tile spans 128 × 64 blocks. Entry 8253 contains 128 × 64 BC7 blocks, each sixteen bytes. One tile spans 64 × 64 blocks. For block coordinates `(x,y)`, the tile base is `65536*((y//tile_h)*(padded_blocks_w//tile_w)+x//tile_w)`. Build the within-tile byte address from the following sequence, reading left to right from the least significant address bit. A positive value `s` copies bit `s-1` of x, a negative value copies bit `-s-1` of y, and zero leaves the address bit clear.

| Element | 16 address-bit sources in order |
|---|---|
| BC1, 8 bytes | 0,0,0,1,-1,2,3,-2,-3,4,-4,5,-5,6,-6,7 |
| BC7, 16 bytes | 0,0,0,0,1,-1,2,-2,-3,3,-4,4,-5,5,-6,6 |

Copy the block from tile base plus within-tile offset to `(y*blocks_w+x)*element_bytes`. For other descriptors, the listings implement 4 KiB patterns, packed-mip origins, face and slice strides, and volume layouts with their checks. Preserve each descriptor's DXGI format. In these two single-mip 2D examples, write a 128-byte little-endian DDS prefix starting with `DDS `, header size 124, flags `0x81007`, height, width, top-level linear size 131,072, depth 0 and mip count 1. Use pixel format size 32, flags 4 and FourCC `DX10` at offset 76, and caps `0x1000` at offset 108. Append the five DX10 words `[format,3,0,1,0]` (format 71 or 98), then the linear blocks. The resulting files are each 148 + 131,072 bytes.

## Run both archive cases

In the same PowerShell session, set the pool path to your local copy. Compare its length and hash with the first paragraph. The normal exporter uses strict mode by default. The second call should report inferred BC7 signature rank 149, return 2 and leave no output file.

```powershell
$pool = (Resolve-Path 'game-files/ttdb_ui.ttpf').Path
(Get-Item $pool).Length
Get-FileHash $pool -Algorithm SHA256
$exporter = "$out/tools/ttpf_mips.py"
python -IB $exporter layout $pool 0
python -IB $exporter export $pool 0 "$out/strict-0.dds"
Get-FileHash "$out/strict-0.dds" -Algorithm SHA256
python -IB $exporter layout $pool 8253
python -IB $exporter export $pool 8253 "$out/strict-8253.dds"
$LASTEXITCODE
Test-Path "$out/strict-8253.dds"
```

For entry 8253, build the JSON from the local calibration listing. Each initial slot has 24 endpoint fields and 32 selector fields. Preserve the known-bit counts, confirmed-bit counts and last-resort flags alongside values. The snapshot supplies this example's shared calibration. The observed pixel colours still need an independent Xbox comparison.

```powershell
@'
import json
import runpy
import sys
from pathlib import Path

out = Path(sys.argv[1])
table = runpy.run_path(str(out / "history_snapshot.py"))["load_bc7"]()
bc7 = {
    "historyEndpoints": table["history_endpoints"],
    "historyEndpointBits": table["history_endpoint_bits"],
    "historyEndpointConfirmedBits": table["history_endpoint_confirmed_bits"],
    "historyIndices": table["history_indices"],
    "historyIndexBits": table["history_index_bits"],
    "historyIndexConfirmedBits": table["history_index_confirmed_bits"],
    "historyEndpointLastResort": sorted(table["last_resort"]),
}
(out / "history.json").write_text(json.dumps({"bc7": bc7}), encoding="utf-8")
'@ | python -IB - "$out"
python -IB $exporter export $pool 8253 "$out/fitted-8253.dds" --allow-provisional --history "$out/history.json"
Get-FileHash "$out/fitted-8253.dds" -Algorithm SHA256
```

| Entry and mode | Expected outcome |
|---|---|
| 0, strict | SHA-256 `cd39c88921eb395ad633b1bd9ee05a160f693bea8b1e85ad8543bc9cd272022a` |
| 8253, strict | Exit 2 and `Test-Path` returns `False` |
| 8253, fitted | SHA-256 `84e7abf023a568056178f6353d8e86e5d848e536e2aa92f1a028266231b1e15f` |

These hashes identify the complete DDS bytes for this pool and calibration revision. They cover two entries. Measurements for the remaining textures and the original console pixel values require separate evidence.
