"""Translate the two Bink leaf functions that build grouped allocation descriptors."""
import argparse
from pathlib import Path

import pefile
from iced_x86 import Mnemonic as M

from bink_heap_aot import leaf_body
from cpu_leaf_aot import export_rva
from ffx_version_query import INTEGER_HEADER, checked_image, lower


BINK_SHA256 = "9eaf045d004cd7d6a8382aaff0c6ea23a29fec4ef8bfacd726b54f5bc26fafd0"


def generate(image: Path, package: bool) -> str:
    with (checked_image(image, BINK_SHA256) if package else pefile.PE(str(image), fast_load=True)) as pe:
        init, append = ((0x25b80, 0x25b20) if package else
                        (export_rva(pe, "group_init"), export_rva(pe, "group_append")))
        init_body = lower(leaf_body(pe, init, {}), ["rcx = group; rdx = capacity;"], {}, {}, {})
        append_code = leaf_body(pe, append, {})
        # Expose the capacity breakpoint as a status to the desktop test.
        stops = {ins.ip: "return 0;" for ins in append_code if ins.mnemonic == M.INT3}
        if len(stops) != 1:
            raise ValueError("expected one capacity breakpoint")
        stops.update({ins.ip: "return 1;" for ins in append_code if ins.mnemonic == M.RET})
        append_body = lower(append_code, ["rcx = group; rdx = destination; r8 = size;"],
                            {}, {}, {}, host_ops=stops)
    return (INTEGER_HEADER
            + 'extern "C" __declspec(dllexport) word group_init(word group, uint32_t capacity) {\n'
            + init_body + '\n}\n'
            + 'extern "C" __declspec(dllexport) word group_append(word group, word destination, word size) {\n'
            + append_body + '\n}\n')


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--package", action="store_true")
    args = parser.parse_args()
    if args.output.suffix.lower() != ".cpp" or args.output.resolve() == args.image.resolve():
        parser.error("choose a distinct .cpp output")
    args.output.write_text(generate(args.image, args.package), encoding="ascii")
