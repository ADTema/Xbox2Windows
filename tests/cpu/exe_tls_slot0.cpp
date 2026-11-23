// CRT-free EXE compiled with /GA whose own TLS block must sit in TLS slot 0 of every thread.
//
// With /GA the compiler assumes the EXE's TLS index is 0: every __declspec(thread) access reads
// gs:[58h] (ThreadLocalStoragePointer) and then the first entry, without loading _tls_index. Under
// a Windows launch the EXE does own index 0. A loader that maps the EXE into a process whose slot 0
// belongs to someone else must therefore install the image's block in slot 0 of each thread, or the
// image reads and writes another module's block. The rule and the shape of this fixture follow
// MoonYueya's notes on issue #870; the code is this repository's own.
//
// The template holds t_value (7) and t_array, 0x1400 bytes of 0xFF, so it is larger than one page.
// in_slot0() compares slot 0 with the entry at _tls_index without touching either block, so it is
// safe whoever owns slot 0. Only when the image owns slot 0 does a thread read its template copy,
// write the whole array and validate the process heap.
//
// The log, one line on standard output:
//   <thread><reason>=<s><t>   a TLS callback: thread m (initial), a or b; reason 1 process attach,
//                             2 thread attach, 3 thread detach; s = y/n slot 0 is the image's block;
//                             t = y/n the block holds the template, - when not checked
//   <thread>:<s><t><w><h>     a thread's own check: slot 0, template, whole-array write read back,
//                             HeapValidate after the write (- when not checked)
//   X=<exit code>             the number of n results
// Workers a and b run one after the other, so the order is fixed. Threads the EXE did not start
// are left out. A failed setup ends the process with 0xE0000002 (CreateThread), 0xE0000003 (wait)
// or 0xE0000006 (event log overflow).
#include <windows.h>
#include <intrin.h>

#include <cstdint>

#pragma runtime_checks("", off)

// The TLS support the C runtime's tlssup provides, for an EXE linked without it.
extern "C" {
ULONG _tls_index = 0;
#pragma data_seg(".tls")
char _tls_start = 0;
#pragma data_seg(".tls$ZZZ")
char _tls_end = 0;
#pragma data_seg()
#pragma section(".CRT$XLA", read)
#pragma section(".CRT$XLZ", read)
__declspec(allocate(".CRT$XLA")) PIMAGE_TLS_CALLBACK __xl_a = nullptr;
__declspec(allocate(".CRT$XLZ")) PIMAGE_TLS_CALLBACK __xl_z = nullptr;
extern const IMAGE_TLS_DIRECTORY64 _tls_used = {
    reinterpret_cast<ULONGLONG>(&_tls_start), reinterpret_cast<ULONGLONG>(&_tls_end),
    reinterpret_cast<ULONGLONG>(&_tls_index), reinterpret_cast<ULONGLONG>(&__xl_a + 1), 0, 0};
}

namespace {
constexpr unsigned ARRAY_BYTES = 0x1400;

struct Array {
    unsigned char bytes[ARRAY_BYTES];
};

constexpr Array make_array() {
    Array array{};
    for (unsigned i = 0; i < ARRAY_BYTES; ++i) array.bytes[i] = 0xFF;
    return array;
}
}  // namespace

__declspec(thread) int t_value = 7;
__declspec(thread) Array t_array = make_array();

namespace {
constexpr UINT CREATE_FAILED = 0xE0000002u, WAIT_FAILED_CODE = 0xE0000003u, LOG_FULL = 0xE0000006u;
constexpr DWORD WAIT_MS = 10000;

// Slot 0 holds the same block as the entry at _tls_index. Reads only the pointer array.
bool in_slot0() {
    void** slots = reinterpret_cast<void**>(__readgsqword(0x58));
    return slots && slots[0] && slots[0] == slots[_tls_index];
}

// Reached through slot 0 (/GA); only called when in_slot0().
bool template_intact() {
    if (t_value != 7) return false;
    for (unsigned i = 0; i < ARRAY_BYTES; ++i)
        if (t_array.bytes[i] != 0xFF) return false;
    return true;
}

bool write_array(unsigned char tag) {
    // An explicit store: at /O2 MSVC turns a byte loop into a memset call, which a CRT-free EXE cannot link.
    __stosb(t_array.bytes, tag, ARRAY_BYTES);
    t_value = tag;
    for (unsigned i = 0; i < ARRAY_BYTES; ++i)
        if (t_array.bytes[i] != tag) return false;
    return t_value == tag;
}

struct Event {
    DWORD thread;
    char kind;  // '1'..'3' a callback reason, ':' a thread's own check
    char results[4];
};

Event g_events[32];
volatile LONG g_count;
DWORD g_threads[3];  // initial thread, worker A, worker B
volatile LONG g_failures;

char yes_no(bool value) {
    if (!value) InterlockedIncrement(&g_failures);
    return value ? 'y' : 'n';
}

void record(char kind, char a, char b, char c, char d) {
    const LONG index = InterlockedIncrement(&g_count) - 1;
    if (index >= static_cast<LONG>(sizeof(g_events) / sizeof(g_events[0]))) ExitProcess(LOG_FULL);
    g_events[index] = {GetCurrentThreadId(), kind, {a, b, c, d}};
}

bool own_thread() {
    const DWORD thread = GetCurrentThreadId();
    return thread == g_threads[1] || thread == g_threads[2];
}

void NTAPI callback(PVOID, DWORD reason, PVOID) {
    if (reason == DLL_PROCESS_DETACH) return;  // not logged: the log is written before the process ends
    // Thread notifications for threads the EXE did not start (a host's own threads) are not checked: those
    // threads do not run the EXE's code. Their IDs are never in g_threads, which is filled before a worker runs.
    if (reason != DLL_PROCESS_ATTACH && !own_thread()) return;
    const bool slot = in_slot0();
    // On thread detach the thread has already written its copy, so only slot 0 is checked.
    const char intact = slot && reason != DLL_THREAD_DETACH ? yes_no(template_intact()) : '-';
    record(static_cast<char>('0' + reason), yes_no(slot), intact, 0, 0);
}

// A thread's own check: slot 0, its template copy, a whole-array write and the process heap.
void check(unsigned char tag) {
    const bool slot = in_slot0();
    if (!slot) {
        record(':', yes_no(false), '-', '-', '-');
        return;
    }
    const char intact = yes_no(template_intact());
    const char wrote = yes_no(write_array(tag));
    record(':', 'y', intact, wrote, yes_no(HeapValidate(GetProcessHeap(), 0, nullptr) != FALSE));
}
}  // namespace

#pragma section(".CRT$XLB", read)
extern "C" __declspec(allocate(".CRT$XLB")) PIMAGE_TLS_CALLBACK p_exe_slot0_callback = callback;

namespace {
DWORD WINAPI worker(void* tag) {
    check(static_cast<unsigned char>(reinterpret_cast<ULONG_PTR>(tag)));
    return 0;
}

char g_line[32 * 12];
unsigned g_length;

void put(char c) { g_line[g_length++] = c; }

char thread_name(DWORD thread) {
    for (int i = 0; i < 3; ++i)
        if (g_threads[i] == thread) return "mab"[i];
    return 0;
}
}  // namespace

extern "C" DWORD WINAPI exe_entry(void*) {
    g_threads[0] = GetCurrentThreadId();
    check(0x11);
    for (int i = 0; i < 2; ++i) {
        // Suspended, so the thread ID is known before its attach callback runs.
        HANDLE thread = CreateThread(nullptr, 0, worker, reinterpret_cast<void*>(static_cast<ULONG_PTR>(0x22 + i * 0x11)),
                                     CREATE_SUSPENDED, &g_threads[1 + i]);
        if (!thread) ExitProcess(CREATE_FAILED);
        ResumeThread(thread);
        if (WaitForSingleObject(thread, WAIT_MS) != WAIT_OBJECT_0) ExitProcess(WAIT_FAILED_CODE);
        CloseHandle(thread);
    }
    const DWORD failures = static_cast<DWORD>(g_failures);

    put('L'), put('O'), put('G'), put(':');
    const LONG count = g_count;
    for (LONG i = 0; i < count; ++i) {
        const Event& event = g_events[i];
        const char name = thread_name(event.thread);
        if (!name) continue;
        put(name);
        put(event.kind == ':' ? ':' : event.kind);
        if (event.kind != ':') put('=');
        for (char result : event.results)
            if (result) put(result);
        put(' ');
    }
    put('X'), put('=');
    put(static_cast<char>('0' + (failures > 9 ? 9 : failures)));
    put('\n');
    DWORD written = 0;
    WriteFile(GetStdHandle(STD_OUTPUT_HANDLE), g_line, g_length, &written, nullptr);
    return failures;
}
