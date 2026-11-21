// Event sink for the lifecycle fixtures. It is CRT-free and loaded by the test host before the fixture DLLs,
// so it outlives them: the destructors and detach notifications of the DLLs under test can still log here.
#include <windows.h>

#pragma runtime_checks("", off)

namespace {
char g_text[1024];
volatile LONG g_length;
}  // namespace

// Appends "token," to the log. Tokens that do not fit are dropped whole.
extern "C" __declspec(dllexport) void sink_log(const char* token) {
    LONG size = 0;
    while (token[size]) ++size;
    const LONG start = _InterlockedExchangeAdd(&g_length, size + 1);
    if (start + size + 1 > static_cast<LONG>(sizeof(g_text))) return;
    for (LONG i = 0; i < size; ++i) g_text[start + i] = token[i];
    g_text[start + size] = ',';
}

// Copies the log into out (capacity bytes) and returns its length.
extern "C" __declspec(dllexport) unsigned sink_snapshot(char* out, unsigned capacity) {
    LONG length = g_length;
    if (length > static_cast<LONG>(sizeof(g_text))) length = sizeof(g_text);
    if (static_cast<unsigned>(length) > capacity) length = static_cast<LONG>(capacity);
    for (LONG i = 0; i < length; ++i) out[i] = g_text[i];
    return static_cast<unsigned>(length);
}

extern "C" BOOL WINAPI sink_main(HINSTANCE, DWORD, LPVOID) { return TRUE; }
