"""Check that opening a physical-page slab does not charge its whole size to system commit (#1199).

Mapping a few pages must commit about those pages, not the 256 MiB slab that holds them.
usage: xmem_mapped_pages_commit_check.py <xmem_shim.dll>
"""
import ctypes as C
from ctypes import wintypes as W
from pathlib import Path
import sys

PAGE_BYTES = 65536
PHYSICAL_64K = 0x20400000
WIN_RESERVE = 0x2000
RESERVE_PLACEHOLDER = 0x40000
WIN_RELEASE = 0x8000
NOACCESS = 1
MAPPED_PAGES = 16
SLAB_BYTES = 256 << 20
# Other processes move system commit a little while this runs; a whole slab is 256 MiB.
LIMIT_BYTES = 32 << 20


class PerformanceInformation(C.Structure):
    _fields_ = [("cb", W.DWORD)] + [(name, C.c_size_t) for name in (
        "CommitTotal", "CommitLimit", "CommitPeak", "PhysicalTotal", "PhysicalAvailable", "SystemCache",
        "KernelTotal", "KernelPaged", "KernelNonpaged", "PageSize", "HandleCount", "ProcessCount",
        "ThreadCount")]


def bind(library, name, args, result):
    function = getattr(library, name)
    function.argtypes, function.restype = args, result
    return function


def main(path):
    library = C.WinDLL(str(Path(path).resolve()), use_last_error=True, winmode=0x900)
    kernel = C.WinDLL("kernelbase.dll", use_last_error=True)
    psapi = C.WinDLL("kernel32.dll", use_last_error=True)
    pointer, number = C.c_void_p, C.c_size_t
    performance = bind(psapi, "K32GetPerformanceInfo", [C.POINTER(PerformanceInformation), W.DWORD], C.c_int)
    allocate = bind(library, "XMemAllocatePhysicalPages", [number, C.POINTER(number), C.POINTER(number)], C.c_int)
    release = bind(library, "XMemFreePhysicalPages", [number, C.POINTER(number)], C.c_int)
    contiguous = bind(library, "XMemMapPhysicalPages", [pointer, number, C.POINTER(number)], pointer)
    reserve = bind(kernel, "VirtualAlloc2", [pointer, pointer, number, C.c_ulong, C.c_ulong, pointer, C.c_ulong],
                   pointer)
    free = bind(kernel, "VirtualFree", [pointer, number, C.c_ulong], C.c_int)

    def commit_bytes():
        info = PerformanceInformation()
        info.cb = C.sizeof(info)
        assert performance(C.byref(info), info.cb), C.get_last_error()
        return info.CommitTotal * info.PageSize

    size = MAPPED_PAGES * PAGE_BYTES
    base = reserve(pointer(-1), None, size, WIN_RESERVE | RESERVE_PLACEHOLDER, NOACCESS, None, 0)
    assert base, C.get_last_error()
    count, pages = number(MAPPED_PAGES), (number * MAPPED_PAGES)()
    try:
        assert allocate(PHYSICAL_64K, C.byref(count), pages) and count.value == MAPPED_PAGES
        before = commit_bytes()
        mapped = contiguous(base, MAPPED_PAGES, pages)
        assert mapped == base, C.get_last_error()
        grown = commit_bytes() - before
        print(f"commit grew by {grown >> 20} MiB for {MAPPED_PAGES} mapped pages (a slab is {SLAB_BYTES >> 20} MiB)")
        assert grown < LIMIT_BYTES, f"mapping {MAPPED_PAGES} pages committed {grown >> 20} MiB: the slab is charged whole"

        # The pages are usable and start zero-filled.
        view = (C.c_ubyte * size).from_address(mapped)
        assert not any(view[::4096]), "a fresh page is not zero-filled"
        view[0], view[size - 1] = 0x5A, 0xA5
        assert view[0] == 0x5A and view[size - 1] == 0xA5
        assert contiguous(base, MAPPED_PAGES, None) == base
    finally:
        free(base, 0, WIN_RELEASE)
        release(count.value, pages)
    print("ok")


if __name__ == "__main__":
    main(sys.argv[1])
