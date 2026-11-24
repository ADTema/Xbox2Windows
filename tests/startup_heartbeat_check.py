"""Check the DirectStorage heartbeat's commit and physical-page section counters."""
import ctypes as C
from pathlib import Path
import os
import re
import sys
import tempfile
import time

PAGE_BYTES = 65536
PHYSICAL_64K = 0x20400000
WIN_RESERVE = 0x2000
RESERVE_PLACEHOLDER = 0x40000
WIN_RELEASE = 0x8000
NOACCESS = 1
HEARTBEAT = re.compile(
    r"x2w-dstorage heartbeat (\d+) s: .*?commit peak=(\d+) MiB current=(\d+) MiB, "
    r"live physical-page sections=(\d+)")


class MemoryCounters(C.Structure):
    _fields_ = [
        ("cb", C.c_ulong),
        ("PageFaultCount", C.c_ulong),
        ("PeakWorkingSetSize", C.c_size_t),
        ("WorkingSetSize", C.c_size_t),
        ("QuotaPeakPagedPoolUsage", C.c_size_t),
        ("QuotaPagedPoolUsage", C.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", C.c_size_t),
        ("QuotaNonPagedPoolUsage", C.c_size_t),
        ("PagefileUsage", C.c_size_t),
        ("PeakPagefileUsage", C.c_size_t),
        ("PrivateUsage", C.c_size_t),
    ]


def bind(library, name, args, result):
    function = getattr(library, name)
    function.argtypes, function.restype = args, result
    return function


def process_commit():
    psapi = C.WinDLL("psapi.dll", use_last_error=True)
    query = bind(psapi, "GetProcessMemoryInfo", [C.c_void_p, C.POINTER(MemoryCounters), C.c_ulong], C.c_int)
    counters = MemoryCounters()
    counters.cb = C.sizeof(counters)
    assert query(C.c_void_p(-1), C.byref(counters), counters.cb), C.get_last_error()
    return counters.PagefileUsage, counters.PeakPagefileUsage


def main(xmem_path, xcrdapi_path):
    log = Path(tempfile.gettempdir()) / f"x2w-heartbeat-{os.getpid()}.txt"
    log.write_bytes(b"")
    os.environ["X2W_TRAP_LOG"] = str(log)
    library = C.WinDLL(str(Path(xmem_path).resolve()), use_last_error=True, winmode=0x900)
    xcrdapi = C.WinDLL(str(Path(xcrdapi_path).resolve()), use_last_error=True, winmode=0x900)
    kernel = C.WinDLL("kernelbase.dll", use_last_error=True)
    pointer, number = C.c_void_p, C.c_size_t
    allocate = bind(library, "XMemAllocatePhysicalPages", [number, C.POINTER(number), C.POINTER(number)], C.c_int)
    release = bind(library, "XMemFreePhysicalPages", [number, C.POINTER(number)], C.c_int)
    contiguous = bind(library, "XMemMapPhysicalPages", [pointer, number, C.POINTER(number)], pointer)
    get_factory = bind(xcrdapi, "DStorageGetFactory", [C.c_void_p, C.POINTER(C.c_void_p)], C.c_long)
    reserve = bind(kernel, "VirtualAlloc2", [pointer, pointer, number, C.c_ulong, C.c_ulong, pointer, C.c_ulong],
                   pointer)
    free = bind(kernel, "VirtualFree", [pointer, number, C.c_ulong], C.c_int)

    first = reserve(pointer(-1), None, PAGE_BYTES, WIN_RESERVE | RESERVE_PLACEHOLDER, NOACCESS, None, 0)
    second = reserve(pointer(-1), None, PAGE_BYTES, WIN_RESERVE | RESERVE_PLACEHOLDER, NOACCESS, None, 0)
    assert first and second, C.get_last_error()
    count, pages = number(2), (number * 2)()
    one, other = number(0), number(0)
    try:
        # Two live sections are visible while the heartbeat samples.
        assert allocate(PHYSICAL_64K, C.byref(count), pages) and count.value == 2
        one.value, other.value = pages[0], pages[1]
        assert contiguous(first, 1, C.byref(one)) == first
        assert contiguous(second, 1, C.byref(other)) == second
        _, earlier_peak = process_commit()

        factory = C.c_void_p()
        assert get_factory(None, C.byref(factory)) == 0 and factory.value, "DStorageGetFactory failed"

        deadline = time.monotonic() + 25
        match = None
        while match is None and time.monotonic() < deadline:
            match = HEARTBEAT.search(log.read_text(errors="replace"))
            if match is None:
                time.sleep(0.2)
        assert match, "no heartbeat line with commit peak and physical-page sections: " + \
            log.read_text(errors="replace")[-1200:]
        second_mark, peak_mib, current_mib, sections = (int(value) for value in match.groups())
        _, later_peak = process_commit()
        line = log.read_text(errors="replace").splitlines()
        line = next(text for text in line if "x2w-dstorage heartbeat" in text and "commit peak=" in text)
        assert peak_mib >= current_mib > 0, f"implausible commit: peak={peak_mib} MiB current={current_mib} MiB"
        assert sections == 2, f"heartbeat counted {sections} live sections, expected 2"
        assert peak_mib >= earlier_peak // (1 << 20), "heartbeat peak predates the process peak"
        assert peak_mib <= later_peak // (1 << 20), "heartbeat peak exceeds the process peak read afterwards"
        print(f"heartbeat at {second_mark} s: commit peak={peak_mib} MiB current={current_mib} MiB, "
              f"live physical-page sections={sections}")
        print(line.strip())
    finally:
        if count.value:
            contiguous(first, 1, None)
            contiguous(second, 1, None)
            release(2, pages)
        free(first, 0, WIN_RELEASE)
        free(second, 0, WIN_RELEASE)
        try:
            log.unlink()
        except OSError:
            pass


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
