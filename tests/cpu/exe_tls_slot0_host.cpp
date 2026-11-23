// CRT-free host that maps tests/cpu/exe_tls_slot0.cpp with pe_map and starts it, either as the main
// image (pe_map_run_main) or as a plain mapped EXE (pe_map_run).
//
// The host is an EXE with its own TLS directory and one thread-local sentinel, so under Windows its
// block is the one in TLS slot 0. While the image is installed as the main image, slot 0 of every
// thread holds the image's block, so the host does not touch its own thread-locals between the start
// and the release. It reads slot 0 only through the TEB, never through a thread-local access.
//
// Usage: cpu_exe_tls_slot0_host <pe_map.dll> <image> main|plain
// After the guest's own LOG line, the host prints one line:
//   HOST: mode=<m> started=<0|1> exit=<hex> installed_main=<y/n> installed_existing=<y/n>
//         reuse=<y/n> stale_dropped_on_reuse=<y/n> host_tls=<y/n> existing_host_tls=<y/n>
//         heap_valid=<y/n> stats=<installed>,<restored>,<stale>,<mismatched>,<records>,<active>
// installed_*: slot 0 of the calling thread and of a thread that existed before the start holds
// the image's block after the start. A host thread that held the image's block is then ended with
// TerminateThread (no detach), which leaves a stale record. reuse: one of up to REUSE_ATTEMPTS later
// threads got the dead thread's ID. Thread IDs come from a system-wide table that hands freed IDs out
// again only after other free IDs, so reuse cannot be forced and is often not observed.
// stale_dropped_on_reuse: when reuse was observed, pe_map dropped the dead thread's record as that ID
// attached again and gave the new thread the image's block. Without reuse, release drops the record. host_tls / existing_host_tls: after release, slot 0 holds the host's block again and the
// sentinel reads its original value on the calling thread and on the existing thread.
// Exit code 0 when the host could run every step, 2 for a usage or setup failure.
#include <windows.h>
#include <intrin.h>

#include <cstddef>
#include <cstdint>

#pragma runtime_checks("", off)

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

__declspec(thread) std::uint64_t t_host_sentinel = 0x0123456789abcdefull;

namespace {
using Resolver = void*(__cdecl*)(const char* dll, const char* name, std::uint32_t ordinal);
using MapImage = void*(__cdecl*)(const wchar_t*, Resolver, std::uint32_t*, char*, std::size_t);
using Run = int(__cdecl*)(void*, std::uint32_t*);
using Release = int(__cdecl*)(void*);
using Stats = void(__cdecl*)(std::int64_t*);
using QueryThread = LONG(NTAPI*)(HANDLE, ULONG, void*, ULONG, ULONG*);

struct BasicInformation {  // THREAD_BASIC_INFORMATION
    LONG exit_status;
    void* teb;
    void* process;
    void* thread;
    ULONG_PTR affinity;
    LONG priority;
    LONG base_priority;
};

QueryThread g_query;

// TEB.NtTib.Self; winnt.h's inline NtCurrentTeb is compiled with the runtime checks of a Debug build.
void* current_teb() { return reinterpret_cast<void*>(__readgsqword(0x30)); }
HMODULE g_kernel;

int ascii_equal(const char* a, const char* b) {
    for (; *a && *b; ++a, ++b) {
        char x = *a, y = *b;
        if (x >= 'A' && x <= 'Z') x = static_cast<char>(x + 32);
        if (y >= 'A' && y <= 'Z') y = static_cast<char>(y + 32);
        if (x != y) return 0;
    }
    return *a == *b;
}

// Binds kernel32.dll only; any other import stays unresolved and fails the map.
void* __cdecl resolve(const char* dll, const char* name, std::uint32_t) {
    if (!name || !ascii_equal(dll, "kernel32.dll")) return nullptr;
    return reinterpret_cast<void*>(GetProcAddress(g_kernel, name));
}

void* teb_of(HANDLE thread) {
    BasicInformation info{};
    return g_query(thread, 0, &info, sizeof(info), nullptr) >= 0 ? info.teb : nullptr;
}

void** slots_of(void* teb) { return teb ? *reinterpret_cast<void***>(static_cast<std::uint8_t*>(teb) + 0x58) : nullptr; }

void* slot(void* teb, DWORD index) {
    void** slots = slots_of(teb);
    return slots ? slots[index] : nullptr;
}

bool holds_image_block(void* teb, DWORD index) {
    void** slots = slots_of(teb);
    return slots && slots[index] && slots[0] == slots[index];
}

// A thread that exists before the start: reports its slot 0 and sentinel, waits, checks them again.
struct Existing {
    HANDLE ready, resume, done;
    void* host_block;     // slot 0 before the start
    bool sentinel_after;  // the sentinel after release
    void* block_after;    // slot 0 after release
};

DWORD WINAPI existing_thread(void* parameter) {
    auto* self = static_cast<Existing*>(parameter);
    self->host_block = slot(current_teb(), 0);
    SetEvent(self->ready);
    WaitForSingleObject(self->resume, INFINITE);  // released only after pe_map_release
    self->block_after = slot(current_teb(), 0);
    self->sentinel_after = t_host_sentinel == 0x0123456789abcdefull;
    SetEvent(self->done);
    return 0;
}

constexpr int REUSE_ATTEMPTS = 1000;
char g_detail[256];  // pe_map_image's failure detail; a global, since a zeroed local becomes memset at /O2
char g_line[512];
unsigned g_length;

void put(char c) {
    if (g_length < sizeof(g_line)) g_line[g_length++] = c;
}
void put(const char* text) {
    for (; *text; ++text) put(*text);
}
void put_flag(const char* name, bool value) {
    put(' ');
    put(name);
    put('=');
    put(value ? 'y' : 'n');
}
void put_number(std::uint64_t value, bool hex) {
    char digits[20];
    int n = 0;
    const unsigned base = hex ? 16 : 10;
    do {
        digits[n++] = "0123456789abcdef"[value % base];
        value /= base;
    } while (value);
    while (n) put(digits[--n]);
}

int fail_setup(const char* what) {
    put("HOST: setup failed: ");
    put(what);
    put('\n');
    DWORD written = 0;
    WriteFile(GetStdHandle(STD_OUTPUT_HANDLE), g_line, g_length, &written, nullptr);
    return 2;
}

// Arguments: the command line split on spaces (paths without spaces).
int split(wchar_t* line, wchar_t** out, int capacity) {
    int count = 0;
    bool quoted = false;
    wchar_t* start = nullptr;
    for (wchar_t* p = line;; ++p) {
        const wchar_t c = *p;
        const bool end = c == 0 || (!quoted && c == L' ');
        if (c == L'"') {
            quoted = !quoted;
            *p = 0;
            if (!start) start = p + 1;
            continue;
        }
        if (end) {
            if (start && count < capacity) out[count++] = start;
            start = nullptr;
            if (c == 0) break;
            *p = 0;
        } else if (!start) {
            start = p;
        }
    }
    return count;
}

DWORD tls_index_of(void* base) {
    auto* bytes = static_cast<std::uint8_t*>(base);
    const auto* nt = reinterpret_cast<const IMAGE_NT_HEADERS64*>(bytes + reinterpret_cast<IMAGE_DOS_HEADER*>(bytes)->e_lfanew);
    const auto& entry = nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_TLS];
    const auto* tls = reinterpret_cast<const IMAGE_TLS_DIRECTORY64*>(bytes + entry.VirtualAddress);
    return *reinterpret_cast<const DWORD*>(tls->AddressOfIndex);
}
}  // namespace

extern "C" int host_entry() {
    g_kernel = GetModuleHandleW(L"kernel32.dll");
    g_query = reinterpret_cast<QueryThread>(GetProcAddress(GetModuleHandleW(L"ntdll.dll"), "NtQueryInformationThread"));
    wchar_t* argv[8];
    const int argc = split(GetCommandLineW(), argv, 8);
    if (argc != 4 || !g_query) ExitProcess(fail_setup("usage: host <pe_map.dll> <image> main|plain"));
    const bool main_mode = argv[3][0] == L'm';

    HMODULE mapper = LoadLibraryW(argv[1]);
    if (!mapper) ExitProcess(fail_setup("cannot load pe_map"));
    auto map = reinterpret_cast<MapImage>(GetProcAddress(mapper, "pe_map_image"));
    auto run = reinterpret_cast<Run>(GetProcAddress(mapper, main_mode ? "pe_map_run_main" : "pe_map_run"));
    auto release = reinterpret_cast<Release>(GetProcAddress(mapper, "pe_map_release"));
    auto stats = reinterpret_cast<Stats>(GetProcAddress(mapper, "pe_map_main_tls_stats"));
    if (!map || !run || !release || !stats) ExitProcess(fail_setup("missing pe_map export"));

    void* const my_teb = current_teb();
    const bool sentinel_before = t_host_sentinel == 0x0123456789abcdefull;  // the last host TLS access until release
    void* const my_host_block = slot(my_teb, 0);

    Existing existing{CreateEventW(nullptr, TRUE, FALSE, nullptr), CreateEventW(nullptr, TRUE, FALSE, nullptr),
                      CreateEventW(nullptr, TRUE, FALSE, nullptr), nullptr, false, nullptr};
    HANDLE existing_handle = CreateThread(nullptr, 0, existing_thread, &existing, 0, nullptr);
    if (!existing_handle || WaitForSingleObject(existing.ready, 10000) != WAIT_OBJECT_0)
        ExitProcess(fail_setup("existing thread"));
    void* const existing_teb = teb_of(existing_handle);

    std::uint32_t status = 0;
    void* base = map(argv[2], resolve, &status, g_detail, sizeof(g_detail));
    if (!base) ExitProcess(fail_setup(g_detail[0] ? g_detail : "map failed"));
    const DWORD index = tls_index_of(base);

    std::uint32_t exit_code = 0xdeadbeef;
    const int started = run(base, &exit_code);
    const bool installed_main = holds_image_block(my_teb, index);
    const bool installed_existing = holds_image_block(existing_teb, index);

    // A host thread that held the image's block ends without a detach; a later thread reuses its ID.
    bool reuse = false, dropped = false;
    if (main_mode && started) {
        const auto sleep = reinterpret_cast<LPTHREAD_START_ROUTINE>(GetProcAddress(g_kernel, "Sleep"));
        DWORD dead_id = 0;
        HANDLE dead = CreateThread(nullptr, 0, sleep, reinterpret_cast<void*>(static_cast<ULONG_PTR>(INFINITE)), 0, &dead_id);
        void* const dead_teb = dead ? teb_of(dead) : nullptr;
        for (int i = 0; i < 200 && dead_teb && !holds_image_block(dead_teb, index); ++i) Sleep(5);
        const bool dead_installed = dead_teb && holds_image_block(dead_teb, index);
        if (dead) {
            TerminateThread(dead, 0);
            WaitForSingleObject(dead, 10000);
            CloseHandle(dead);
            Sleep(100);  // lets the kernel free the dead thread's ID
        }
        std::int64_t before[6];
        stats(before);
        // Thread IDs come from a system-wide table, so a freed ID returns only after other free IDs;
        // threads with another ID are ended before they run (they never attach) and the search goes on.
        for (int attempt = 0; dead_installed && attempt < REUSE_ATTEMPTS && !reuse; ++attempt) {
            DWORD id = 0;
            HANDLE next = CreateThread(nullptr, 0, sleep, reinterpret_cast<void*>(static_cast<ULONG_PTR>(1000)),
                                       CREATE_SUSPENDED, &id);
            if (!next) break;
            if (id != dead_id) {
                TerminateThread(next, 0);
                WaitForSingleObject(next, 10000);
                CloseHandle(next);
                continue;
            }
            reuse = true;
            ResumeThread(next);
            void* const teb = teb_of(next);
            for (int i = 0; i < 200 && !holds_image_block(teb, index); ++i) Sleep(5);
            const bool installed = holds_image_block(teb, index);
            std::int64_t after[6];
            stats(after);
            dropped = installed && after[2] == before[2] + 1;
            WaitForSingleObject(next, 10000);  // Sleep(1000) returns; the detach restores its slot 0
            CloseHandle(next);
        }
    }

    const int released = release(base);
    // From here on the host's block is back in slot 0, so the host may read its thread-locals.
    const bool host_tls = released == 1 && slot(my_teb, 0) == my_host_block && sentinel_before &&
                          t_host_sentinel == 0x0123456789abcdefull;
    SetEvent(existing.resume);
    WaitForSingleObject(existing.done, 10000);
    WaitForSingleObject(existing_handle, 10000);
    const bool existing_host_tls = existing.block_after == existing.host_block && existing.sentinel_after;
    const bool heap_valid = HeapValidate(GetProcessHeap(), 0, nullptr) != FALSE;
    std::int64_t counters[6];
    stats(counters);

    put("HOST: mode=");
    put(main_mode ? "main" : "plain");
    put(" started=");
    put_number(static_cast<std::uint64_t>(started), false);
    put(" exit=");
    put_number(exit_code, true);
    put_flag("installed_main", installed_main);
    put_flag("installed_existing", installed_existing);
    put_flag("reuse", reuse);
    put_flag("stale_dropped_on_reuse", dropped);
    put_flag("host_tls", host_tls);
    put_flag("existing_host_tls", existing_host_tls);
    put_flag("heap_valid", heap_valid);
    put(" stats=");
    for (int i = 0; i < 6; ++i) {
        if (i) put(',');
        put_number(static_cast<std::uint64_t>(counters[i]), false);
    }
    put('\n');
    DWORD written = 0;
    WriteFile(GetStdHandle(STD_OUTPUT_HANDLE), g_line, g_length, &written, nullptr);
    ExitProcess(0);
}
