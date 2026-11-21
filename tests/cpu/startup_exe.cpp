// CRT-free EXE importing both DLLs and kernel32. Its TLS callback and entry point log into the first
// DLL; the entry point then runs two worker threads in turn, each with a per-thread value kept by TlsAlloc (an
// explicit slot, not implicit __declspec(thread) data) and writes the whole log to standard output.
// Exit code: b_value() | first worker's value << 8 | second worker's << 16 | main thread's << 24.
#include <windows.h>

#pragma runtime_checks("", off)

extern "C" __declspec(dllimport) void a_log(char event);
extern "C" __declspec(dllimport) unsigned a_snapshot(char* out);
extern "C" __declspec(dllimport) unsigned b_value();

namespace {
DWORD g_slot;
volatile DWORD g_worker_value;
DWORD g_next_value;

DWORD WINAPI worker(void*) {
    TlsSetValue(g_slot, reinterpret_cast<void*>(static_cast<ULONG_PTR>(g_next_value)));
    const DWORD seen = static_cast<DWORD>(reinterpret_cast<ULONG_PTR>(TlsGetValue(g_slot)));
    g_worker_value = seen;
    a_log('w');
    a_log(static_cast<char>('0' + seen));
    return 0;
}

void write_line(HANDLE out, const char* prefix, const char* text, unsigned length) {
    char line[96];
    unsigned n = 0;
    for (; prefix[n]; ++n) line[n] = prefix[n];
    for (unsigned i = 0; i < length; ++i) line[n++] = text[i];
    line[n++] = '\n';
    DWORD written = 0;
    WriteFile(out, line, n, &written, nullptr);
}
}  // namespace

extern "C" void NTAPI tls_callback(PVOID, DWORD reason, PVOID) {
    if (reason == DLL_PROCESS_ATTACH) a_log('t');
}

extern "C" ULONG tls_index_slot;
ULONG tls_index_slot;

#pragma section(".tlscb", read)
extern "C" __declspec(allocate(".tlscb")) PIMAGE_TLS_CALLBACK tls_callbacks[] = {tls_callback, nullptr};

// The linker finds the TLS directory through this name. Pointer members keep it a constant initializer
// with base relocations; the layout is IMAGE_TLS_DIRECTORY64 with an empty data template.
struct TlsDirectory {
    void* start;
    void* end;
    ULONG* index;
    PIMAGE_TLS_CALLBACK* callbacks;
    DWORD zero_fill;
    DWORD characteristics;
};
extern "C" const TlsDirectory _tls_used = {nullptr, nullptr, &tls_index_slot, tls_callbacks, 0, 0};

extern "C" DWORD WINAPI exe_entry(void*) {
    a_log('e');
    g_slot = TlsAlloc();
    TlsSetValue(g_slot, reinterpret_cast<void*>(1));
    DWORD worker_values[2];
    for (DWORD i = 0; i < 2; ++i) {  // two workers one after the other, so the log order is fixed
        g_next_value = 2 + i;
        HANDLE thread = CreateThread(nullptr, 0, worker, nullptr, 0, nullptr);
        WaitForSingleObject(thread, 30000);
        CloseHandle(thread);
        worker_values[i] = g_worker_value;
    }
    const DWORD mine = static_cast<DWORD>(reinterpret_cast<ULONG_PTR>(TlsGetValue(g_slot)));
    a_log('m');
    a_log(static_cast<char>('0' + mine));

    char log[64];
    HANDLE out = GetStdHandle(STD_OUTPUT_HANDLE);
    write_line(out, "LOG:", log, a_snapshot(log));
    return b_value() | (worker_values[0] << 8) | (worker_values[1] << 16) | (mine << 24);
}
