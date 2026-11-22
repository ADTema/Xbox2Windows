// A DLL whose implicit TLS data template holds every kind of thread-local the loader must place:
// an initialized value, a zero-filled value, a 64-byte aligned array, a pointer that carries a
// base relocation inside the template, a zero-filled range longer than a page and a C++
// thread_local with a dynamic initializer. Built with the static MSVC runtime, so the TLS
// directory, _tls_index and the dynamic-initializer callback are the linker's and the CRT's own.
//
// The harness loads it with LoadLibraryW and with pe_map and compares what each thread observes.
#include <windows.h>

#include <cstdint>

extern "C" unsigned long _tls_index;  // written by whoever loads the image

int g_anchor = 41;
int g_dynamic_runs = 0;

static int next_dynamic() { return 100 + static_cast<int>(InterlockedIncrement(reinterpret_cast<LONG*>(&g_dynamic_runs))); }

__declspec(thread) int t_init = 7;
__declspec(thread) int t_zero;
__declspec(thread) std::uint64_t t_wide = 0x1122334455667788ull;
__declspec(thread) int* t_pointer = &g_anchor;
__declspec(thread) __declspec(align(64)) unsigned char t_aligned[64] = {0x5a, 1, 2, 3};
__declspec(thread) unsigned char t_big[0x3000];
thread_local int t_dynamic = next_dynamic();

struct Snapshot {
    std::int32_t init;
    std::int32_t zero;
    std::uint64_t wide;
    std::uint32_t pointer_ok;      // t_pointer == &g_anchor and *t_pointer == 41
    std::uint32_t aligned_offset;  // address of t_aligned modulo 64
    std::uint32_t aligned_first;   // t_aligned[0]
    std::uint32_t big_sum;         // sum of t_big
    std::uint32_t dynamic_nonzero; // t_dynamic was initialized on this thread
    std::uint32_t index;           // _tls_index
    std::uint64_t block;           // address of t_init, to tell two threads' blocks apart
};

extern "C" __declspec(dllexport) void tls_data_snapshot(Snapshot* out) {
    out->init = t_init;
    out->zero = t_zero;
    out->wide = t_wide;
    out->pointer_ok = t_pointer == &g_anchor && *t_pointer == 41;
    out->aligned_offset = static_cast<std::uint32_t>(reinterpret_cast<std::uintptr_t>(&t_aligned[0]) % 64);
    out->aligned_first = t_aligned[0];
    std::uint32_t sum = 0;
    for (unsigned char byte : t_big) sum += byte;
    out->big_sum = sum;
    out->dynamic_nonzero = t_dynamic > 100;
    out->index = _tls_index;
    out->block = reinterpret_cast<std::uint64_t>(&t_init);
}

// Changes this thread's copy only.
extern "C" __declspec(dllexport) void tls_data_write(int value) {
    t_init = value;
    t_zero = value + 1;
    t_wide = static_cast<std::uint64_t>(value) + 2;
    t_aligned[0] = static_cast<unsigned char>(value + 3);
    t_big[sizeof(t_big) - 1] = static_cast<unsigned char>(value + 4);
}

// Thread start routine: records what a new thread sees, then what it sees after its own write.
extern "C" __declspec(dllexport) DWORD WINAPI tls_data_worker(LPVOID parameter) {
    auto* out = static_cast<Snapshot*>(parameter);
    tls_data_snapshot(&out[0]);
    tls_data_write(50);
    tls_data_snapshot(&out[1]);
    return 0;
}

BOOL WINAPI DllMain(HINSTANCE, DWORD, LPVOID) { return TRUE; }
