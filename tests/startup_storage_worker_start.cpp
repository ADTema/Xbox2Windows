// A DirectStorage queue whose worker cannot be started keeps the deferred-completion contract
// (#1199, item 3): Enqueue never completes a status entry or signals a fence, and Submit does.
//
// Two failures are made on demand inside the stand-in, which this test compiles into itself instead
// of loading as a DLL, so it shares the test's allocator and CreateThread:
//   - CreateThread is redirected, for the stand-in's translation unit only, to a function that can
//     fail every thread creation (both the committed-stack attempt and the default-stack attempt);
//   - operator new is replaced with one that, when armed with N, throws std::bad_alloc from the N-th
//     throwing-form allocation on the calling thread and then disarms itself, so exactly one
//     allocation fails and everything after it (logging, library internals, recovery) behaves
//     normally. Which allocation that is differs between standard libraries (a std::deque allocates
//     in its constructor on some and at its first push_back on others), so the test sweeps N.
//
// Checks, each on a fresh queue: with no worker, before Submit the status entry is still pending, the
// fence is not signaled and the destination is untouched; after Submit the status entry holds a
// failure and the fence is signaled. A worker that cannot start at Enqueue but can at Submit runs the
// entries normally. For every N at Enqueue and every N at Submit no exception reaches the caller,
// nothing completes inside Enqueue, and afterwards the request either completed with correct data or
// completed with a failure, the fence was signaled exactly once, and a later request on the same queue
// returns correct data. A crash or an unhandled exception names the stage it happened in.
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>

#include <atomic>
#include <cstdint>
#include <cstdio>
#include <csignal>
#include <cstdlib>
#include <exception>
#include <new>
#include <typeinfo>
#include <vector>

namespace {
std::atomic<bool> fail_thread_creation{false};
std::atomic<int> thread_attempts{0};
thread_local int fail_countdown = 0;  // 0: disarmed; N: the N-th throwing-form allocation throws
std::atomic<int> global_countdown{0};  // same, counted over every thread of the process
bool sweep_all_threads = false;        // which of the two countdowns arm() sets
std::atomic<int> thrown{0};
DWORD main_thread_id = 0;

void arm(int nth)
{
    if (sweep_all_threads) global_countdown = nth;
    else fail_countdown = nth;
}
void disarm()
{
    fail_countdown = 0;
    global_countdown = 0;
}

HANDLE WINAPI creator_under_test(LPSECURITY_ATTRIBUTES attributes, SIZE_T stack, LPTHREAD_START_ROUTINE start,
                                 LPVOID parameter, DWORD flags, LPDWORD id)
{
    ++thread_attempts;
    if (fail_thread_creation) {
        SetLastError(ERROR_NOT_ENOUGH_MEMORY);
        return nullptr;
    }
    return CreateThread(attributes, stack, start, parameter, flags, id);
}
}  // namespace

void* operator new(std::size_t size)
{
    if (fail_countdown > 0 && --fail_countdown == 0) {
        ++thrown;
        throw std::bad_alloc();
    }
    if (global_countdown.load(std::memory_order_relaxed) > 0 && global_countdown.fetch_sub(1) == 1) {
        ++thrown;
        throw std::bad_alloc();
    }
    if (void* memory = std::malloc(size ? size : 1)) return memory;
    throw std::bad_alloc();
}
void* operator new(std::size_t size, const std::nothrow_t&) noexcept { return std::malloc(size ? size : 1); }
void operator delete(void* memory) noexcept { std::free(memory); }
void operator delete(void* memory, std::size_t) noexcept { std::free(memory); }
void operator delete(void* memory, const std::nothrow_t&) noexcept { std::free(memory); }

#define CreateThread creator_under_test
#include "startup_stubs/xcrdapi.cpp"
#undef CreateThread

namespace {

constexpr LONG pending_status = static_cast<LONG>(0x8000000A);
constexpr DWORD completion_timeout_ms = 15000;
constexpr unsigned char untouched = 0xAA;

using CreateStatusArrayFn = long(__stdcall*)(void*, unsigned, const char*, const void*, void**);
using CreateQueueFn = long(__stdcall*)(void*, const void*, const void*, void**);
using EnqueueRequestFn = void(__stdcall*)(void*, const void*);
using EnqueueStatusFn = void(__stdcall*)(void*, void*, unsigned);
using EnqueueSignalFn = void(__stdcall*)(void*, void*, std::uint64_t);
using SubmitFn = void(__stdcall*)(void*);
using IsCompleteFn = bool(__stdcall*)(void*, unsigned);
using GetHResultFn = long(__stdcall*)(void*, unsigned);

struct MockFence {
    void** vtable;
    int signals = 0;
    std::uint64_t value = 0;
    static long __stdcall signal(void* self, std::uint64_t value)
    {
        auto* fence = static_cast<MockFence*>(self);
        ++fence->signals;
        fence->value = value;
        return 0;
    }
};

struct Vtables {
    void* fence[11] = {};
    Vtables() { fence[10] = reinterpret_cast<void*>(&MockFence::signal); }
};

std::uint32_t adler32(const unsigned char* data, std::size_t size)
{
    std::uint32_t a = 1, b = 0;
    for (std::size_t i = 0; i < size; ++i) {
        a = (a + data[i]) % 65521;
        b = (b + a) % 65521;
    }
    return (b << 16) | a;
}

// A zlib stream of one stored block (size at most 65535).
std::vector<unsigned char> stored_zlib(const std::vector<unsigned char>& plain)
{
    const auto size = static_cast<unsigned>(plain.size());
    std::vector<unsigned char> out{0x78, 0x01, 0x01, static_cast<unsigned char>(size), static_cast<unsigned char>(size >> 8),
                                   static_cast<unsigned char>(~size), static_cast<unsigned char>((~size) >> 8)};
    out.insert(out.end(), plain.begin(), plain.end());
    const std::uint32_t sum = adler32(plain.data(), plain.size());
    for (int shift = 24; shift >= 0; shift -= 8) out.push_back(static_cast<unsigned char>(sum >> shift));
    return out;
}

struct Fixture {
    Object* factory = nullptr;
    std::vector<unsigned char> plain, stream;
    Vtables vtables;
    const char* error = nullptr;

    struct Queue {
        Object* queue = nullptr;
        Object* status = nullptr;
        MockFence fence;
    };

    bool create(Queue& q, Vtables& v) const
    {
        void* status = nullptr;
        void* queue = nullptr;
        unsigned char description[0x20] = {};
        *reinterpret_cast<std::uint16_t*>(description + 8) = 16;
        if (reinterpret_cast<CreateStatusArrayFn>(factory->vtable[5])(factory, 4, "Status", nullptr, &status) != 0 ||
            reinterpret_cast<CreateQueueFn>(factory->vtable[10])(factory, description, nullptr, &queue) != 0)
            return false;
        q.status = static_cast<Object*>(status);
        q.queue = static_cast<Object*>(queue);
        q.fence.vtable = v.fence;
        return true;
    }

    void request(const Queue& q, std::vector<unsigned char>& destination) const
    {
        unsigned char bytes[0x48] = {};
        *reinterpret_cast<std::uint64_t*>(bytes + 0x00) = 1 | 0x400000;
        *reinterpret_cast<unsigned char**>(bytes + 0x08) = destination.data();
        *reinterpret_cast<unsigned*>(bytes + 0x18) = static_cast<unsigned>(destination.size());
        *reinterpret_cast<const unsigned char**>(bytes + 0x20) = stream.data();
        *reinterpret_cast<unsigned*>(bytes + 0x30) = static_cast<unsigned>(stream.size());
        *reinterpret_cast<unsigned*>(bytes + 0x38) = static_cast<unsigned>(plain.size());
        reinterpret_cast<EnqueueRequestFn>(q.queue->vtable[3])(q.queue, bytes);
    }
    void status_entry(const Queue& q, unsigned index) const
    {
        reinterpret_cast<EnqueueStatusFn>(q.queue->vtable[4])(q.queue, q.status, index);
    }
    void signal(Queue& q, std::uint64_t value) const
    {
        reinterpret_cast<EnqueueSignalFn>(q.queue->vtable[5])(q.queue, &q.fence, value);
    }
    void submit(const Queue& q) const { reinterpret_cast<SubmitFn>(q.queue->vtable[6])(q.queue); }
    bool complete(const Queue& q, unsigned index) const
    {
        return reinterpret_cast<IsCompleteFn>(q.status->vtable[3])(q.status, index);
    }
    long hresult(const Queue& q, unsigned index) const
    {
        return reinterpret_cast<GetHResultFn>(q.status->vtable[4])(q.status, index);
    }
    bool wait(const Queue& q, unsigned index) const
    {
        const DWORD start = GetTickCount();
        while (!complete(q, index)) {
            if (GetTickCount() - start > completion_timeout_ms) return false;
            Sleep(5);
        }
        return true;
    }
};

bool fail(const char* what)
{
    std::fprintf(stderr, "FAIL: %s\n", what);
    return false;
}

bool untouched_bytes(const std::vector<unsigned char>& bytes)
{
    for (unsigned char byte : bytes)
        if (byte != untouched) return false;
    return true;
}

// Requests, a status entry and a fence signal are enqueued; nothing may complete until Submit. Enough
// requests are enqueued to cross a block boundary of the queue's lists. fail_nth arms the N-th
// allocation to fail during the whole sequence (0: none).
constexpr int requests_per_run = 4;

// Every step of a sweep names itself on stderr before it runs, so the last line before a crash names
// the exact sweep, allocation number and call.
const char* sweep_name = "none";
int sweep_n = 0, sweep_m = 0;
void trace(const char* step, int index = -1)
{
    if (index >= 0)
        std::fprintf(stderr, "sweep=%s N=%d submit_N=%d all_threads=%d step=%s #%d\n", sweep_name, sweep_n, sweep_m,
                     sweep_all_threads ? 1 : 0, step, index);
    else
        std::fprintf(stderr, "sweep=%s N=%d submit_N=%d all_threads=%d step=%s\n", sweep_name, sweep_n, sweep_m,
                     sweep_all_threads ? 1 : 0, step);
    std::fflush(stderr);
}

bool enqueue_without_effects(Fixture& f, Fixture::Queue& q, std::vector<unsigned char>& destination, int fail_nth)
{
    try {
        trace("arm_enqueue");
        arm(fail_nth);
        for (int i = 0; i < requests_per_run; ++i) {
            trace("enqueue_request", i + 1);
            f.request(q, destination);
        }
        trace("enqueue_status");
        f.status_entry(q, 0);
        trace("enqueue_signal");
        f.signal(q, 7);
        disarm();
        trace("enqueue_done");
    } catch (...) {
        disarm();
        return fail("an exception left an Enqueue call");
    }
    trace("check_enqueue");
    if (f.complete(q, 0) || f.hresult(q, 0) != pending_status) return fail("the status entry completed inside Enqueue");
    if (q.fence.signals != 0 || q.fence.value != 0) return fail("the fence was signaled inside Enqueue");
    if (!untouched_bytes(destination)) return fail("the destination changed inside Enqueue");
    return true;
}

bool failed_at_submit(Fixture& f, Fixture::Queue& q)
{
    if (!f.complete(q, 0) || f.hresult(q, 0) >= 0) return fail("Submit did not complete the status entry with a failure");
    if (q.fence.signals != 1 || q.fence.value != 7) return fail("Submit did not signal the fence once with its value");
    return true;
}

bool serves_next_request(Fixture& f, Fixture::Queue& q)
{
    std::vector<unsigned char> destination(f.plain.size(), untouched);
    f.request(q, destination);
    f.status_entry(q, 1);
    f.submit(q);
    if (!f.wait(q, 1)) return fail("a request after the failure never completed");
    if (f.hresult(q, 1) != 0 || destination != f.plain) return fail("a request after the failure returned wrong data");
    return true;
}

// Both CreateThread attempts fail at Enqueue and at Submit.
bool worker_cannot_start(Fixture& f)
{
    Fixture::Queue q;
    if (!f.create(q, f.vtables)) return fail("cannot create the queue");
    std::vector<unsigned char> destination(f.plain.size(), untouched);
    fail_thread_creation = true;
    thread_attempts = 0;
    const bool effects_deferred = enqueue_without_effects(f, q, destination, 0);
    const int attempts = thread_attempts;
    f.submit(q);
    fail_thread_creation = false;
    if (!effects_deferred) return false;
    if (attempts < 2) return fail("the worker start did not try both stack sizes");
    if (!failed_at_submit(f, q)) return false;
    if (!untouched_bytes(destination)) return fail("the failed request changed its destination");
    return serves_next_request(f, q);
}

// The worker cannot start at Enqueue but can by Submit: the entries run normally.
bool worker_starts_at_submit(Fixture& f)
{
    Fixture::Queue q;
    if (!f.create(q, f.vtables)) return fail("cannot create the queue");
    std::vector<unsigned char> destination(f.plain.size(), untouched);
    fail_thread_creation = true;
    const bool effects_deferred = enqueue_without_effects(f, q, destination, 0);
    fail_thread_creation = false;
    if (!effects_deferred) return false;
    f.submit(q);
    if (!f.wait(q, 0) || f.hresult(q, 0) != 0 || destination != f.plain) return fail("the retried worker did not run the request");
    const DWORD start = GetTickCount();
    while (q.fence.signals == 0 && GetTickCount() - start < completion_timeout_ms) Sleep(5);
    if (q.fence.signals != 1 || q.fence.value != 7) return fail("the retried worker did not signal the fence");
    return true;
}

// One allocation fails at Enqueue (the fail_enqueue-th) and one at Submit (the fail_submit-th); 0 means
// none. A later request completing means every earlier entry has run or failed, since the worker runs
// entries in order and failures are completed inside Submit.
bool one_allocation_fails(Fixture& f, int fail_enqueue, int fail_submit, int& thrown_at_enqueue, int& thrown_at_submit)
{
    sweep_n = fail_enqueue;
    sweep_m = fail_submit;
    sweep_name = fail_submit == 0 ? "enqueue" : fail_enqueue == 0 ? "submit" : "both";
    trace("create");
    Fixture::Queue q;
    if (!f.create(q, f.vtables)) return fail("cannot create the queue");
    std::vector<unsigned char> destination(f.plain.size(), untouched);
    thrown = 0;
    // On every thread, the queue's worker must not run during Enqueue, or its own allocations would
    // be counted: the creator hook holds it off until Submit.
    fail_thread_creation = sweep_all_threads;
    const bool enqueued = enqueue_without_effects(f, q, destination, fail_enqueue);
    fail_thread_creation = false;
    if (!enqueued) return false;
    thrown_at_enqueue += thrown;
    thrown = 0;
    try {
        trace("submit");
        arm(fail_submit);
        f.submit(q);
        disarm();
        trace("submit_done");
    } catch (...) {
        disarm();
        return fail("an exception left Submit");
    }
    thrown_at_submit += thrown;
    trace("serve_next_request");
    if (!serves_next_request(f, q)) return false;
    trace("check_result");
    if (!f.complete(q, 0)) return fail("the status entry stayed pending after later work completed");
    if (f.hresult(q, 0) == 0) {
        if (destination != f.plain) return fail("a successful status entry has no data");
    } else if (f.hresult(q, 0) > 0 || (!untouched_bytes(destination) && destination != f.plain)) {
        return fail("a failed request left partial data or a success-like status");
    }
    if (q.fence.signals != 1 || q.fence.value != 7) return fail("the fence was not signaled exactly once");
    return true;
}

// Every allocation point of Enqueue and of Submit is failed once, alone and in combination. The
// first stage fails allocations of the calling thread only; the second counts allocations of every
// thread of the process (the queue's worker included once Submit starts it).
bool allocation_sweep(Fixture& f, int sweep, bool all_threads)
{
    sweep_all_threads = all_threads;
    int thrown_at_enqueue = 0, thrown_at_submit = 0;
    for (int at_enqueue = 0; at_enqueue <= sweep; ++at_enqueue)
        for (int at_submit = 0; at_submit <= sweep; ++at_submit)
            if (!one_allocation_fails(f, at_enqueue, at_submit, thrown_at_enqueue, thrown_at_submit)) {
                std::fprintf(stderr, "  (allocation %d at Enqueue, allocation %d at Submit)\n", at_enqueue, at_submit);
                return false;
            }
    if (thrown_at_enqueue == 0 || thrown_at_submit == 0)
        return fail("the control never failed an allocation: the sweep did not reach the queue's storage");
    std::printf("allocation sweep (%s): %d failures at Enqueue, %d at Submit\n", all_threads ? "all threads" : "main thread",
                thrown_at_enqueue, thrown_at_submit);
    sweep_all_threads = false;
    return true;
}

bool every_allocation_can_fail(Fixture& f) { return allocation_sweep(f, 10, false); }
bool every_allocation_on_every_thread_can_fail(Fixture& f) { return allocation_sweep(f, 12, true); }

// A request with page tokens copies them into a vector at Enqueue: that allocation may fail too.
bool page_tokens_allocation_fails(Fixture& f)
{
    static ULONG_PTR title[1] = {0x10000};
    sweep_name = "tokens";
    sweep_m = 0;
    for (int fail_nth = 1; fail_nth <= 10; ++fail_nth) {
        sweep_n = fail_nth;
        trace("create");
        Fixture::Queue q;
        if (!f.create(q, f.vtables)) return fail("cannot create the queue");
        unsigned char bytes[0x48] = {};
        *reinterpret_cast<std::uint64_t*>(bytes + 0x00) = 1 | (1ull << 21);
        *reinterpret_cast<ULONG_PTR**>(bytes + 0x08) = title;
        *reinterpret_cast<unsigned*>(bytes + 0x18) = 16;
        try {
            trace("arm_enqueue");
            arm(fail_nth);
            trace("enqueue_request", 1);
            reinterpret_cast<EnqueueRequestFn>(q.queue->vtable[3])(q.queue, bytes);
            trace("enqueue_status");
            f.status_entry(q, 0);
            disarm();
        } catch (...) {
            disarm();
            return fail("an exception left EnqueueRequest with page tokens");
        }
        if (f.complete(q, 0)) return fail("the status entry completed inside Enqueue");
    }
    return true;
}

// A crash is never silent: whatever ends the process names the stage it was in.
const char* volatile current_stage = "start";

// Nothing here allocates: fixed buffers and fprintf only, and both countdowns are disarmed first.
void print_frame(const void* address)
{
    HMODULE module = nullptr;
    char path[MAX_PATH] = "?";
    if (GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                           static_cast<LPCWSTR>(address), &module) &&
        module) {
        const DWORD length = GetModuleFileNameA(module, path, MAX_PATH);
        if (length == 0 || length >= MAX_PATH) std::snprintf(path, sizeof path, "?");
        const char* name = path;
        for (const char* p = path; *p; ++p)
            if (*p == '\\' || *p == '/') name = p + 1;
        std::fprintf(stderr, "    %s+0x%llx\n", name,
                     static_cast<unsigned long long>(static_cast<const char*>(address) - reinterpret_cast<const char*>(module)));
    } else {
        std::fprintf(stderr, "    %p\n", address);
    }
}

void report_end(const char* what, unsigned long code)
{
    const int armed_here = fail_countdown;
    const int armed_global = global_countdown.load();
    disarm();
    std::fprintf(stderr, "FAIL: %s (0x%08lx) during stage \"%s\"\n", what, code, current_stage);
    std::fprintf(stderr, "  last sweep=%s N=%d submit_N=%d all_threads=%d\n", sweep_name, sweep_n, sweep_m,
                 sweep_all_threads ? 1 : 0);
    std::fprintf(stderr, "  thread=%lu main_thread=%lu on_main=%d countdown_this_thread=%d countdown_global=%d thrown=%d\n",
                 GetCurrentThreadId(), main_thread_id, GetCurrentThreadId() == main_thread_id ? 1 : 0, armed_here,
                 armed_global, thrown.load());
    std::exception_ptr in_flight = std::current_exception();
    if (!in_flight) {
        std::fprintf(stderr, "  no in-flight exception: noexcept/destructor/thread-entry/rethrow-without-active\n");
    } else {
        try {
            std::rethrow_exception(in_flight);
        } catch (const std::exception& error) {
            std::fprintf(stderr, "  in-flight exception: %s: %s\n", typeid(error).name(), error.what());
        } catch (...) {
            std::fprintf(stderr, "  in-flight exception: non-std exception\n");
        }
    }
    void* frames[32] = {};
    const USHORT count = RtlCaptureStackBackTrace(0, 32, frames, nullptr);
    std::fprintf(stderr, "  stack (%u frames, module+offset):\n", static_cast<unsigned>(count));
    for (USHORT i = 0; i < count; ++i) print_frame(frames[i]);
    std::fflush(stderr);
}

[[noreturn]] void on_terminate()
{
    report_end("std::terminate", 0);
    std::_Exit(1);
}

void on_abort(int)
{
    report_end("abort", 0);
    std::_Exit(1);
}

LONG WINAPI on_unhandled(EXCEPTION_POINTERS* info)
{
    report_end("unhandled exception", info && info->ExceptionRecord ? info->ExceptionRecord->ExceptionCode : 0);
    TerminateProcess(GetCurrentProcess(), 1);
    return EXCEPTION_EXECUTE_HANDLER;
}

#ifdef _MSC_VER
void on_invalid_parameter(const wchar_t*, const wchar_t*, const wchar_t*, unsigned, std::uintptr_t)
{
    report_end("invalid parameter", 0);
    std::_Exit(1);
}
#endif

void install_crash_reports()
{
    SetErrorMode(SEM_FAILCRITICALERRORS | SEM_NOGPFAULTERRORBOX);
    std::set_terminate(on_terminate);
    std::signal(SIGABRT, on_abort);
    SetUnhandledExceptionFilter(on_unhandled);
#ifdef _MSC_VER
    _set_invalid_parameter_handler(on_invalid_parameter);
    _set_abort_behavior(0, _WRITE_ABORT_MSG | _CALL_REPORTFAULT);
#endif
}

bool stage(const char* name, bool (*run)(Fixture&), Fixture& f)
{
    current_stage = name;
    std::fprintf(stderr, "stage: %s\n", name);
    std::fflush(stderr);
    return run(f);
}

}  // namespace

int main()
{
    main_thread_id = GetCurrentThreadId();
    install_crash_reports();
    void* factory = nullptr;
    if (DStorageGetFactory(nullptr, &factory) != 0 || !factory) return fail("cannot get the factory"), 1;
    Fixture f;
    f.factory = static_cast<Object*>(factory);
    f.plain.resize(60000);
    for (std::size_t i = 0; i < f.plain.size(); ++i) f.plain[i] = static_cast<unsigned char>((i % 251) ^ 0x5a);
    f.stream = stored_zlib(f.plain);

    if (!stage("worker_cannot_start", worker_cannot_start, f)) return 1;
    if (!stage("worker_starts_at_submit", worker_starts_at_submit, f)) return 1;
    if (!stage("every_allocation_can_fail", every_allocation_can_fail, f)) return 1;
    if (!stage("every_allocation_on_every_thread_can_fail", every_allocation_on_every_thread_can_fail, f)) return 1;
    if (!stage("page_tokens_allocation_fails", page_tokens_allocation_fails, f)) return 1;
    std::puts("a queue that cannot start its worker or allocate completes status and fences at Submit, and recovers");
    return 0;
}
