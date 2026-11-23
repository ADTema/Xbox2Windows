// CRT-free host that maps tests/cpu/exe_tls_slot0.cpp with pe_map and starts it as the main image
// (pe_map_run_main) or, as a control, as a plain mapped EXE (pe_map_run).
//
// The host is an EXE with its own TLS directory and one thread-local sentinel, so under Windows its
// block is the one in TLS slot 0. A thread reads its sentinel only while it does not participate in the
// main image; slot 0 itself is read through the TEB.
//
// Usage: cpu_exe_tls_slot0_host <pe_map.dll> <image> <scenario>
//   main       start the image, let a host thread enter and leave, release on the starting thread
//   alive      as main, but a host participant is still inside the image at release (uncertain)
//   exited     as main, but a host participant is ended with TerminateThread before release
//   untracked  as main, but after the start MAIN_TRACKED host threads enter; the last finds the
//              participant table full, so release cannot inspect it (uncertain)
//   plain      start the image with pe_map_run (control): slot 0 keeps the host's block
// In every scenario a reader thread that never participates samples its own slot 0 and sentinel from
// before the map until after release.
//
// After the guest's own LOG line, the host prints one line:
//   HOST: scenario=<s> started=<0|1> exit=<hex> installed_main=<y/n> reader_untouched=<y/n>
//         reader_samples=<n> participant=<y/n|-> host_tls=<y/n> carrier_after_release=<y/n>
//         heap_valid=<y/n> stats=<installed>,<restored>,<exited>,<uncertain>,<pending>,<active>,
//         <last release>,<untracked>
// installed_main: after the start, the starting thread's slot 0 holds the image's block.
// participant: the host participant(s) saw the image's block after entering and their own block and
// sentinel after leaving ('-' when the scenario has none that leaves).
// host_tls: after release the starting thread's slot 0 and sentinel are the host's again.
// carrier_after_release: the TLS carrier is still loaded right after pe_map_release.
// Exit code 0 when the host could run every step, 2 for a usage or setup failure.
#include <windows.h>
#include <intrin.h>
#include <psapi.h>

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
constexpr std::uint64_t SENTINEL = 0x0123456789abcdefull;
constexpr int MAIN_TRACKED = 64;  // the participant table size in tools/pe_map.cpp

using Resolver = void*(__cdecl*)(const char* dll, const char* name, std::uint32_t ordinal);
using MapImage = void*(__cdecl*)(const wchar_t*, Resolver, std::uint32_t*, char*, std::size_t);
using Run = int(__cdecl*)(void*, std::uint32_t*);
using Release = int(__cdecl*)(void*);
using Join = int(__cdecl*)();
using Stats = void(__cdecl*)(std::int64_t*);

HMODULE g_kernel;
Join g_enter, g_leave;
DWORD g_index;  // the image's TLS index (the carrier's)
char g_detail[256];

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

// winnt.h's inline NtCurrentTeb is compiled with the runtime checks of a Debug build.
void** my_slots() { return *reinterpret_cast<void***>(__readgsqword(0x30) + 0x58); }
void* my_slot0() {
    void** slots = my_slots();
    return slots ? slots[0] : nullptr;
}
bool holds_image_block() {
    void** slots = my_slots();
    return slots && slots[g_index] && slots[0] == slots[g_index];
}

// Never participates: samples its own slot 0 and sentinel until told to stop.
volatile LONG g_stop_reader;
volatile LONG g_reader_bad;
volatile LONG g_reader_samples;
HANDLE g_reader_ready;

DWORD WINAPI reader(void*) {
    void* const own = my_slot0();
    SetEvent(g_reader_ready);
    while (!InterlockedCompareExchange(&g_stop_reader, 0, 0)) {
        if (my_slot0() != own || t_host_sentinel != SENTINEL) InterlockedIncrement(&g_reader_bad);
        InterlockedIncrement(&g_reader_samples);
        SwitchToThread();
    }
    return 0;
}

// A host participant: enters, checks, waits for its cue, leaves, checks again.
struct Participant {
    HANDLE entered, cue;
    void* own;
    bool entered_ok, left_ok;
};

DWORD WINAPI participant(void* parameter) {
    auto* self = static_cast<Participant*>(parameter);
    self->own = my_slot0();
    self->entered_ok = g_enter() == 1 && holds_image_block();
    SetEvent(self->entered);
    WaitForSingleObject(self->cue, INFINITE);
    self->left_ok = g_leave() == 1 && my_slot0() == self->own && t_host_sentinel == SENTINEL;
    return 0;
}

Participant g_parts[MAIN_TRACKED];
HANDLE g_part_threads[MAIN_TRACKED];

bool start_participant(int i) {
    g_parts[i] = {CreateEventW(nullptr, TRUE, FALSE, nullptr), CreateEventW(nullptr, TRUE, FALSE, nullptr), nullptr,
                  false, false};
    g_part_threads[i] = CreateThread(nullptr, 0, participant, &g_parts[i], 0, nullptr);
    return g_part_threads[i] && WaitForSingleObject(g_parts[i].entered, 10000) == WAIT_OBJECT_0;
}

bool finish_participant(int i) {
    SetEvent(g_parts[i].cue);
    const bool joined = WaitForSingleObject(g_part_threads[i], 10000) == WAIT_OBJECT_0;
    CloseHandle(g_part_threads[i]);
    return joined && g_parts[i].entered_ok && g_parts[i].left_ok;
}

// Whether a module whose file name contains pe_map_tls_ (the carrier) is loaded.
HMODULE g_modules[512];

bool carrier_loaded() {
    HMODULE* modules = g_modules;
    DWORD needed = 0;
    if (!K32EnumProcessModules(GetCurrentProcess(), modules, sizeof(g_modules), &needed)) return false;
    const wchar_t marker[] = L"pe_map_tls_";
    for (DWORD i = 0; i < needed / sizeof(HMODULE) && i < 512; ++i) {
        wchar_t name[MAX_PATH];
        const DWORD length = GetModuleFileNameW(modules[i], name, MAX_PATH);
        for (DWORD at = 0; at + 11 <= length; ++at) {
            DWORD k = 0;
            while (k < 11 && name[at + k] == marker[k]) ++k;
            if (k == 11) return true;
        }
    }
    return false;
}

char g_line[512];
unsigned g_length;

void put(char c) {
    if (g_length < sizeof(g_line)) g_line[g_length++] = c;
}
void put(const char* text) {
    for (; *text; ++text) put(*text);
}
void put_flag(const char* name, int value) {  // 1 y, 0 n, -1 -
    put(' ');
    put(name);
    put('=');
    put(value < 0 ? '-' : value ? 'y' : 'n');
}
void put_number(std::int64_t value, bool hex) {
    if (value < 0) {
        put('-');
        value = -value;
    }
    char digits[20];
    int n = 0;
    const unsigned base = hex ? 16 : 10;
    auto v = static_cast<std::uint64_t>(value);
    do {
        digits[n++] = "0123456789abcdef"[v % base];
        v /= base;
    } while (v);
    while (n) put(digits[--n]);
}

void flush() {
    DWORD written = 0;
    WriteFile(GetStdHandle(STD_OUTPUT_HANDLE), g_line, g_length, &written, nullptr);
}

int fail_setup(const char* what) {
    put("HOST: setup failed: ");
    put(what);
    put('\n');
    flush();
    return 2;
}

int split(wchar_t* line, wchar_t** out, int capacity) {
    int count = 0;
    bool quoted = false;
    wchar_t* start = nullptr;
    for (wchar_t* p = line;; ++p) {
        const wchar_t c = *p;
        if (c == L'"') {
            quoted = !quoted;
            *p = 0;
            if (!start) start = p + 1;
            continue;
        }
        if (c == 0 || (!quoted && c == L' ')) {
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
    const auto* nt =
        reinterpret_cast<const IMAGE_NT_HEADERS64*>(bytes + reinterpret_cast<IMAGE_DOS_HEADER*>(bytes)->e_lfanew);
    const auto& entry = nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_TLS];
    const auto* tls = reinterpret_cast<const IMAGE_TLS_DIRECTORY64*>(bytes + entry.VirtualAddress);
    return *reinterpret_cast<const DWORD*>(tls->AddressOfIndex);
}

bool same(const wchar_t* a, const wchar_t* b) {
    for (; *a && *a == *b; ++a, ++b) {
    }
    return *a == *b;
}
}  // namespace

extern "C" int host_entry() {
    g_kernel = GetModuleHandleW(L"kernel32.dll");
    wchar_t* argv[8];
    const int argc = split(GetCommandLineW(), argv, 8);
    if (argc != 4) ExitProcess(fail_setup("usage: host <pe_map.dll> <image> main|alive|exited|untracked|plain"));
    const wchar_t* scenario = argv[3];
    const bool plain = same(scenario, L"plain");
    const bool alive = same(scenario, L"alive"), exited = same(scenario, L"exited"),
               untracked = same(scenario, L"untracked");
    if (!plain && !alive && !exited && !untracked && !same(scenario, L"main")) ExitProcess(fail_setup("scenario"));

    HMODULE mapper = LoadLibraryW(argv[1]);
    if (!mapper) ExitProcess(fail_setup("cannot load pe_map"));
    auto map = reinterpret_cast<MapImage>(GetProcAddress(mapper, "pe_map_image"));
    auto run = reinterpret_cast<Run>(GetProcAddress(mapper, plain ? "pe_map_run" : "pe_map_run_main"));
    auto release = reinterpret_cast<Release>(GetProcAddress(mapper, "pe_map_release"));
    auto stats = reinterpret_cast<Stats>(GetProcAddress(mapper, "pe_map_main_tls_stats"));
    g_enter = reinterpret_cast<Join>(GetProcAddress(mapper, "pe_map_main_thread_enter"));
    g_leave = reinterpret_cast<Join>(GetProcAddress(mapper, "pe_map_main_thread_leave"));
    if (!map || !run || !release || !stats || !g_enter || !g_leave) ExitProcess(fail_setup("missing pe_map export"));

    const bool sentinel_before = t_host_sentinel == SENTINEL;  // the last host TLS access until release
    void* const my_host_block = my_slot0();
    g_reader_ready = CreateEventW(nullptr, TRUE, FALSE, nullptr);
    HANDLE reader_thread = CreateThread(nullptr, 0, reader, nullptr, 0, nullptr);
    if (!reader_thread || WaitForSingleObject(g_reader_ready, 10000) != WAIT_OBJECT_0) ExitProcess(fail_setup("reader"));

    std::uint32_t status = 0;
    void* base = map(argv[2], resolve, &status, g_detail, sizeof(g_detail));
    if (!base) ExitProcess(fail_setup(g_detail[0] ? g_detail : "map failed"));
    g_index = tls_index_of(base);

    std::uint32_t exit_code = 0xdeadbeef;
    const int started = run(base, &exit_code);
    const bool installed_main = holds_image_block();

    // Host participants.
    int participant_ok = -1;
    int count = 0;
    if (!plain && started) {
        count = untracked ? MAIN_TRACKED : 1;
        for (int i = 0; i < count; ++i)
            if (!start_participant(i)) ExitProcess(fail_setup("participant"));
        if (exited) {
            TerminateThread(g_part_threads[0], 0);  // inside the image, never leaves
            WaitForSingleObject(g_part_threads[0], 10000);
            CloseHandle(g_part_threads[0]);
            participant_ok = g_parts[0].entered_ok;
            count = 0;
        }
    }
    // In alive and untracked, the last participant stays inside the image across the release.
    const int stay = (alive || untracked) && count ? count - 1 : -1;
    bool leave_ok = true;
    for (int i = 0; i < count; ++i)
        if (i != stay) leave_ok = finish_participant(i) && leave_ok;

    const int released = release(base);
    const bool carrier_after_release = carrier_loaded();
    if (stay >= 0) leave_ok = finish_participant(stay) && leave_ok;
    if (count) participant_ok = leave_ok;

    // From here on the starting thread has the host's block back, so the host may read its thread-locals.
    const bool host_tls = released == 1 && my_slot0() == my_host_block && sentinel_before && t_host_sentinel == SENTINEL;
    InterlockedExchange(&g_stop_reader, 1);
    WaitForSingleObject(reader_thread, 10000);
    const bool reader_untouched = g_reader_bad == 0 && g_reader_samples > 0;
    const bool heap_valid = HeapValidate(GetProcessHeap(), 0, nullptr) != FALSE;
    std::int64_t counters[8];
    stats(counters);

    put("HOST: scenario=");
    for (const wchar_t* c = scenario; *c; ++c) put(static_cast<char>(*c));
    put(" started=");
    put_number(started, false);
    put(" exit=");
    put_number(exit_code, true);
    put_flag("installed_main", installed_main);
    put_flag("reader_untouched", reader_untouched);
    put(" reader_samples=");
    put_number(g_reader_samples, false);
    put_flag("participant", participant_ok);
    put_flag("host_tls", host_tls);
    put_flag("carrier_after_release", carrier_after_release);
    put_flag("heap_valid", heap_valid);
    put(" stats=");
    for (int i = 0; i < 8; ++i) {
        if (i) put(',');
        put_number(counters[i], false);
    }
    put('\n');
    flush();
    ExitProcess(0);
}
