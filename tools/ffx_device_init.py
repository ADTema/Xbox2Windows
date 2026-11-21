"""Translate the packaged single-context backend from device retention through heap creation."""
import argparse
from pathlib import Path
from uuid import UUID

from iced_x86 import Mnemonic, Register

from cpu_ranges import function_ranges
from ffx_version_query import INTEGER_HEADER, UPSCALER, checked_image, lower, region


def generate(image):
    start, end = 0x27f8, 0x2938
    with checked_image(image, UPSCALER) as pe:
        if not any(lo <= start < end <= hi for lo, hi in function_ranges(pe, 0x2720)):
            raise ValueError("device calls outside backend callback")
        body = region(pe, start, end)
        calls = {}
        for ins in body:
            if ins.mnemonic != Mnemonic.CALL:
                continue
            if ins.memory_base != Register.RAX:
                raise ValueError(f"unexpected device call at {ins.ip:#x}")
            method = {8: "probe.retain(rcx)", 0x70: "probe.create(rcx, rdx, r8, r9)"}[ins.memory_displacement]
            calls[ins.ip] = f"rax = {method};"
        guid = pe.get_data(0x482e0, 16)
        if UUID(bytes_le=guid) != UUID("8efb471d-616c-4f49-90f7-127bb763fa51"):
            raise ValueError("unexpected heap interface")
        code = lower(body, ["rdi = reinterpret_cast<word>(probe.device);",
                            "rbx = reinterpret_cast<word>(probe.scratch.data());"],
                     {0x482e0: "reinterpret_cast<word>(heap_iid)"}, calls, {end: "return;"})
    return INTEGER_HEADER + '\n#include "ffx_device_init.h"\n' + (
        "static const unsigned char heap_iid[] = {" + ", ".join(map(str, guid)) + "};\n"
        "void run_device_slice(FfxDeviceProbe& probe) {\n" + code + "\n}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.output.suffix.lower() != ".cpp" or args.output.resolve() == args.image.resolve():
        parser.error("choose a distinct .cpp output")
    args.output.write_text(generate(args.image), encoding="ascii")
