"""Check the experimental xg_xs layout slot with source-built BC7 descriptors."""

import ctypes
import struct
import sys

from gfx10_texture_roundtrip_check import oracle_surface


DESC = struct.Struct("<I4xQQIHHIIIII4x")
LAYOUT_BYTES = 0x18 + 4 * 0x6C8 + 8
GUARD = b"\xa5" * 16
PTR = ctypes.c_void_p
UINT = ctypes.c_uint32
HRESULT = ctypes.c_int32
LAYOUT = ctypes.WINFUNCTYPE(HRESULT, PTR, PTR)
COPY_INTO = ctypes.WINFUNCTYPE(HRESULT, PTR, PTR, UINT, UINT, PTR, UINT, UINT)
RELEASE = ctypes.WINFUNCTYPE(ctypes.c_uint64, PTR)


def expect(label, actual, expected):
    if actual != expected:
        raise RuntimeError(f"{label}: got {actual!r}, expected {expected!r}")


def check_layout(create, width, height, padded_width, padded_height):
    # 2D, default alignment, one slice, one mip, BC7_UNORM, one sample,
    # UNKNOWN layout, and no resource flags.
    desc = ctypes.create_string_buffer(DESC.pack(3, 0, width, height, 1, 1, 98, 1, 0, 0, 0))
    computer = PTR()
    expect("XGCreateTextureComputer HRESULT", create(desc, ctypes.byref(computer), 0, 0), 0)
    if not computer:
        raise RuntimeError("XGCreateTextureComputer returned a null object")
    vtable = ctypes.cast(computer, ctypes.POINTER(ctypes.POINTER(PTR)))[0]
    try:
        storage = ctypes.create_string_buffer(GUARD + b"\xa5" * LAYOUT_BYTES + GUARD)
        expect("GetResourceLayout HRESULT", LAYOUT(vtable[2])(computer, ctypes.byref(storage, len(GUARD))), 0)
        expect("prefix guard", bytes(storage[:len(GUARD)]), GUARD)
        end = len(GUARD) + LAYOUT_BYTES
        expect("suffix guard", bytes(storage[end:end + len(GUARD)]), GUARD)
        layout = storage[len(GUARD):end]

        tiled, _ = oracle_surface(0, width, height)
        span = len(tiled)
        pitch = padded_width // 4 * 16
        label = f"BC7 {width}x{height}"
        expect(f"{label} mip size/offset/slice span", struct.unpack_from("<QQQ", layout, 0x18 + 0x38),
               (span, 0, span))
        expect(f"{label} size/alignment/mips/planes", struct.unpack_from("<QQII", layout),
               (span, 4096, 1, 1))
        expect(f"{label} plane size/slice stride/alignment", struct.unpack_from("<QQQ", layout, 0x18 + 8),
               (span, 0, 4096))
        expect(f"{label} pitch/alignment/padded and visible extent",
               struct.unpack_from("<9I", layout, 0x18 + 0x38 + 0x18),
               (padded_width, pitch, 4096, padded_width, padded_height, 1, width, height, 1))

        sentinel = b"\xa5" * span
        target = ctypes.create_string_buffer(sentinel, span)
        source = ctypes.create_string_buffer(b"\x5a" * span, span)
        result = COPY_INTO(vtable[8])(computer, target, 0, 0, source, pitch, span)
        expect(f"{label} CopyIntoSubresource HRESULT", result & 0xFFFFFFFF, 0x80004001)
        expect(f"{label} refused copy target", target.raw, sentinel)
        print(f"{label}: span={span} offset=0 padded_blocks={padded_width // 4}x{padded_height // 4} "
              f"pitch={pitch} copy=E_NOTIMPL")
    finally:
        RELEASE(vtable[1])(computer)


def main():
    create = ctypes.WinDLL(sys.argv[1]).XGCreateTextureComputer
    create.argtypes = (PTR, ctypes.POINTER(PTR), ctypes.c_uint64, ctypes.c_uint64)
    create.restype = HRESULT
    check_layout(create, 81, 69, 128, 128)
    check_layout(create, 64, 64, 64, 64)


if __name__ == "__main__":
    main()
