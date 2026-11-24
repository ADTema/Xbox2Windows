"""Exercise large batches of physical pages in the production xmem shim.

Pages are slots of shared sections, and adjacent pages of one batch share a view. This check maps
a batch that spans two sections, unmaps pages from the middle of it, moves them elsewhere, reuses
freed pages, and reads a page from a second thread while the main thread unmaps its neighbours.
usage: xmem_page_runs_check.py <xmem.dll> [pages]
"""
import ctypes as C
from pathlib import Path
import sys
import threading
import time

PAGE_BYTES = 65536
PHYSICAL_64K = 0x20400000
STARTUP_RESERVE = 0x20402000
WIN_RELEASE = 0x8000


def bind(library, name, args, result):
    function = getattr(library, name)
    function.argtypes, function.restype = args, result
    return function


def main(path, total=6000):
    library = C.WinDLL(str(Path(path).resolve()), use_last_error=True, winmode=0x900)
    kernel = C.WinDLL("kernelbase.dll", use_last_error=True)
    pointer, number, dword = C.c_void_p, C.c_size_t, C.c_ulong
    allocate = bind(library, "XMemAllocatePhysicalPages", [number, C.POINTER(number), C.POINTER(number)], C.c_int)
    release = bind(library, "XMemFreePhysicalPages", [number, C.POINTER(number)], C.c_int)
    contiguous = bind(library, "XMemMapPhysicalPages", [pointer, number, C.POINTER(number)], pointer)
    scatter = bind(library, "XMemMapPhysicalPagesScatter", [C.POINTER(pointer), number, C.POINTER(number)], C.c_int)
    reserve_startup = bind(library, "XMemVirtualAlloc", [pointer, number, dword, number, dword], pointer)
    free = bind(kernel, "VirtualFree", [pointer, number, dword], C.c_int)

    def word(address):
        return C.c_uint32.from_address(address)

    assert total > 4200, "the batch has to span two 4096-page sections"
    whole = reserve_startup(None, 16 << 30, STARTUP_RESERVE, 0x21, 4)
    assert whole, C.get_last_error()
    base = whole + PAGE_BYTES
    try:
        count, pages = number(total), (number * total)()
        assert allocate(PHYSICAL_64K, C.byref(count), pages) and count.value == total
        started = time.perf_counter()
        assert contiguous(base, total, pages) == base, C.get_last_error()
        mapped_in = time.perf_counter() - started
        for i in range(total):
            word(base + i * PAGE_BYTES).value = 0xC0DE0000 + i
            word(base + i * PAGE_BYTES + PAGE_BYTES - 4).value = i

        def intact(skip=()):
            for i in range(total):
                if i in skip:
                    continue
                at = base + i * PAGE_BYTES
                assert word(at).value == 0xC0DE0000 + i and word(at + PAGE_BYTES - 4).value == i, f"page {i} lost its bytes"

        intact()
        # Unmap single pages from the middle of the batch, on both sides of the section boundary.
        holes = [100, 101, 4095, 4096, total - 1]
        addresses = (pointer * len(holes))(*[base + i * PAGE_BYTES for i in holes])
        assert scatter(addresses, len(holes), None), C.get_last_error()
        intact(skip=set(holes))
        # The same pages mapped somewhere else show the bytes written through the batch.
        elsewhere = base + (total + 16) * PAGE_BYTES
        moved = (number * len(holes))(*[pages[i] for i in holes])
        assert contiguous(elsewhere, len(holes), moved) == elsewhere, C.get_last_error()
        for slot, i in enumerate(holes):
            assert word(elsewhere + slot * PAGE_BYTES).value == 0xC0DE0000 + i, f"moved page {i}"
        assert contiguous(elsewhere, len(holes), None) == elsewhere
        # And back where they were: the batch is whole again.
        assert scatter(addresses, len(holes), moved), C.get_last_error()
        intact()

        # A reader on one page while its neighbour is unmapped and mapped again and again. The
        # neighbour shares a view with the reader's page, so every unmap takes that view away for a
        # moment; the reader must only ever see its own bytes.
        reader_page, toggled = 2000, 2001
        stop, seen, wrong = threading.Event(), [0], [0]

        def read_loop():
            at = base + reader_page * PAGE_BYTES
            while not stop.is_set():
                if word(at).value != 0xC0DE0000 + reader_page:
                    wrong[0] += 1
                seen[0] += 1

        reader = threading.Thread(target=read_loop)
        reader.start()
        one_address, one_page = (pointer * 1)(base + toggled * PAGE_BYTES), (number * 1)(pages[toggled])
        toggles = 0
        deadline = time.perf_counter() + 2.0
        while time.perf_counter() < deadline:
            assert scatter(one_address, 1, None), C.get_last_error()
            assert scatter(one_address, 1, one_page), C.get_last_error()
            toggles += 1
        stop.set()
        reader.join(10)
        assert not reader.is_alive() and seen[0] > 0 and wrong[0] == 0, (seen[0], wrong[0])
        intact()

        # Freed pages come back zero-filled.
        assert not release(total, pages), "released a mapped grant"
        assert contiguous(base, total, None) == base
        assert release(total, pages)
        again, fresh = number(64), (number * 64)()
        assert allocate(PHYSICAL_64K, C.byref(again), fresh) and again.value == 64
        assert contiguous(base, 64, fresh) == base, C.get_last_error()
        for i in range(64):
            at = base + i * PAGE_BYTES
            assert word(at).value == 0 and word(at + PAGE_BYTES - 4).value == 0, f"reused page {i} is not zero"
        assert contiguous(base, 64, None) == base and release(64, fresh)
    finally:
        free(whole, 0, WIN_RELEASE)
    print(f"xmem_page_runs: PASS ({total} pages mapped in {mapped_in * 1000:.0f} ms, {len(holes)} holes, "
          f"{toggles} neighbour toggles under {seen[0]} reads, reuse zeroed)")


if __name__ == "__main__":
    main(sys.argv[1], *(int(a) for a in sys.argv[2:3]))
