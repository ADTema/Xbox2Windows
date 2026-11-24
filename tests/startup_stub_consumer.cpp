// Source-built consumer for the startup trap stubs. Imports by name from chad.dll, xg_xs.dll and
// xmem.dll and calls the export the first argument selects. (XMemTransferMemory and
// D3D12ConfigureVirtualMemoryX have real implementations in the shims and their own tests.)
//   none     -> returns 0 without calling a stub (control)
//   chad     -> XDspActivate(0x11, 0x22, 0x33, 0x44)
//   xg_xs    -> XGSuggestSwizzleMode(0x55, 0, 0, 0)
//   physical -> XMemAllocatePhysicalPages/XMemFreePhysicalPages round trip (no trap expected)
#include <cstdint>
#include <cstdio>
#include <cstring>

using u64 = std::uint64_t;

extern "C" __declspec(dllimport) u64 XDspActivate(u64, u64, u64, u64);
extern "C" __declspec(dllimport) u64 XGSuggestSwizzleMode(u64, u64, u64, u64);
extern "C" __declspec(dllimport) int XMemAllocatePhysicalPages(u64 flags, std::size_t* count, u64* pages);
extern "C" __declspec(dllimport) int XMemFreePhysicalPages(std::size_t count, u64* pages);

int main(int argc, char** argv)
{
    if (argc != 2) return 2;
    const char* which = argv[1];
    if (!std::strcmp(which, "none")) return 0;
    if (!std::strcmp(which, "chad")) return static_cast<int>(XDspActivate(0x11, 0x22, 0x33, 0x44));
    if (!std::strcmp(which, "xg_xs")) return static_cast<int>(XGSuggestSwizzleMode(0x55, 0, 0, 0));
    if (!std::strcmp(which, "physical")) {
        std::size_t count = 4;
        u64 pages[4] = {};
        if (!XMemAllocatePhysicalPages(0x20400000ull /* 64 KiB pages */, &count, pages) || count != 4) return 3;
        for (u64 page : pages)
            if (!page) return 4;
        if (!XMemFreePhysicalPages(count, pages)) return 5;
        if (XMemFreePhysicalPages(count, pages)) return 6;  // double free must be refused
        std::puts("physical ok");
        return 0;
    }
    return 2;
}
