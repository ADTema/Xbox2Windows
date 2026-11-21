#!/usr/bin/env python3
"""Check the per-chunk layout summary emitted by verify_build.compare_layout."""

import sys
import tempfile
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "tools"))

from verify_build import compare_layout, decode_torrent

LAYOUT = r"""<?xml version="1.0" encoding="utf-8"?>
<Package>
  <Chunk Id="1000">
    <FileGroup SourcePath=".\" DestinationPath="\" Include="MicrosoftGame.Config" />
  </Chunk>
  <Chunk Id="1001">
    <FileGroup SourcePath=".\..\..\content\" DestinationPath="\" Include="game_scarlett_master.exe" />
  </Chunk>
  <Chunk Id="3009" Marker="Launch">
    <FileGroup SourcePath=".\" DestinationPath="\" Include="Update.alignmentchunk" />
  </Chunk>
</Package>
"""


def main():
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "layout_test.xml"
        path.write_text(LAYOUT, encoding="utf-8")
        report = compare_layout(
            path,
            {"MicrosoftGame.Config", "Update.alignmentchunk"},
            {"MicrosoftGame.Config", "Update.alignmentchunk"},
        )
    assert report["target_count"] == 3, report
    assert report["launch_marker"] == "3009", report
    assert report["absent_from_disk"] == {"game_scarlett_master.exe": ["1001"]}, report
    assert report["absent_from_torrent"] == {"game_scarlett_master.exe": ["1001"]}, report
    assert report["torrent_paths_outside_layout"] == [], report
    chunks = {chunk["id"]: chunk for chunk in report["chunk_summary"]}
    assert chunks["1001"]["absent_from_disk"] == ["game_scarlett_master.exe"], chunks
    assert chunks["1001"]["absent_from_torrent"] == ["game_scarlett_master.exe"], chunks
    assert chunks["3009"]["marker"] == "Launch", chunks
    assert chunks["3009"]["absent_from_disk"] == [], chunks
    check_decode_torrent()
    print("layout chunk summary ok")


def check_decode_torrent():
    valid = (
        b"d"
        b"7:comment0:"
        b"4:infod"
        b"5:filesld6:lengthi0e4:pathl9:empty.bin"
        b"eed6:lengthi128e4:pathl3:sub8:data.pak"
        b"eee"
        b"12:piece lengthi262144e"
        b"6:pieces20:" + bytes(range(20)) +
        b"e"
        b"6:offseti-7e"
        b"e"
    )
    decoded = decode_torrent(valid)
    assert decoded[b"comment"] == b""
    assert decoded[b"offset"] == -7
    assert decoded[b"info"][b"piece length"] == 262144
    assert len(decoded[b"info"][b"files"]) == 2
    assert decode_torrent(b"d1:Z1:x1:a1:ye") == {b"Z": b"x", b"a": b"y"}

    for malformed in (
        b"",
        b"ie",
        b"i-0e",
        b"i00e",
        b"i03e",
        b"i-03e",
        b"i+3e",
        b"i 3e",
        b"i3 e",
        b"i1_0e",
        b"i3",
        b"00:",
        b"01:a",
        b"1_0:aaaaaaaaaa",
        b"1 :a",
        b"3:ab",
        b"3abc",
        b"d1:b1:x1:a1:ye",
        b"d1:a1:y1:Z1:xe",
        b"d1:a1:x1:a1:ye",
        b"di1e1:xe",
        b"d1:a1:x",
        b"l1:x",
        b"i0ei1e",
    ):
        try:
            decode_torrent(malformed)
        except ValueError:
            pass
        else:
            raise AssertionError(f"Accepted malformed bencode: {malformed!r}")


if __name__ == "__main__":
    main()
