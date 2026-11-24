// An allocation failure on the DirectStorage stand-in's queue worker fails that request and leaves
// the worker running (#1199, item 3).
//
// Request buffers are sized from request fields. The failure here is a real one, the same kind a
// job-wide commit cap causes in a startup run: this process joins a job object whose process-memory
// limit is a little above its current commit, then submits a zlib request whose declared inflated
// size is far above the limit. The stand-in's buffer allocation throws std::bad_alloc on the worker.
// The stand-in is a DLL with its own C++ runtime, so replacing operator new here would not reach it;
// the commit limit is the one seam that works the same on the real worker.
//
// Checks, on one queue: a normal request succeeds; the oversized request completes with a failure
// status (within a timeout, destination unchanged); a normal request submitted afterwards succeeds
// with correct data. Returns 77 where the system does not enforce the job limit.
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#include <psapi.h>

#include <cstdint>
#include <cstdio>
#include <vector>

namespace {

using u64 = std::uint64_t;
constexpr int skipped = 77;
constexpr SIZE_T commit_headroom = SIZE_T{256} << 20;     // job limit above the current commit
constexpr unsigned oversized_inflated = 1536u << 20;       // declared inflated size, above the limit
constexpr DWORD completion_timeout_ms = 15000;

struct Object { void** vtable; };
using GetFactoryFn = long(__stdcall*)(const void*, void**);
using CreateStatusArrayFn = long(__stdcall*)(void*, unsigned, const char*, const void*, void**);
using CreateQueueFn = long(__stdcall*)(void*, const void*, const void*, void**);
using EnqueueRequestFn = void(__stdcall*)(void*, const void*);
using EnqueueStatusFn = void(__stdcall*)(void*, void*, unsigned);
using EnqueueSignalFn = void(__stdcall*)(void*, void*, u64);
using SubmitFn = void(__stdcall*)(void*);
using IsCompleteFn = bool(__stdcall*)(void*, unsigned);
using GetHResultFn = long(__stdcall*)(void*, unsigned);

struct MockFence {
    void** vtable;
    bool signaled = false;
    u64 value = 0;
    HANDLE entered = nullptr;  // when set, signal() reports it was entered and then waits for `release`
    HANDLE release = nullptr;
    static long __stdcall signal(void* self, u64 val)
    {
        auto* f = static_cast<MockFence*>(self);
        if (f->entered) {
            SetEvent(f->entered);
            WaitForSingleObject(f->release, completion_timeout_ms);
        }
        f->signaled = true;
        f->value = val;
        return 0;
    }
};

// Calls one queue function on its own thread, started before commit is exhausted (a thread cannot be created
// afterwards). Waits for `go`, runs, then sets `done`.
struct QueueCall {
    Object* queue = nullptr;
    Object* status = nullptr;
    int enqueue_status_index = -1;  // when >= 0, the call first enqueues a status entry for that index
    HANDLE go = CreateEventW(nullptr, TRUE, FALSE, nullptr);
    HANDLE done = CreateEventW(nullptr, TRUE, FALSE, nullptr);
    static DWORD WINAPI run(void* parameter)
    {
        auto* self = static_cast<QueueCall*>(parameter);
        WaitForSingleObject(self->go, completion_timeout_ms);
        if (self->enqueue_status_index >= 0) {
            reinterpret_cast<EnqueueStatusFn>(self->queue->vtable[4])(
                self->queue, self->status, static_cast<unsigned>(self->enqueue_status_index));
        }
        reinterpret_cast<SubmitFn>(self->queue->vtable[6])(self->queue);
        SetEvent(self->done);
        return 0;
    }
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

struct Queue {
    Object* queue = nullptr;
    Object* status = nullptr;

    // Enqueues a memory-source zlib request into a linear destination and a status entry, submits,
    // and waits for the status. Returns false on a timeout; hr receives the status.
    bool run(std::vector<unsigned char>& destination, const std::vector<unsigned char>& stream, unsigned inflated,
             unsigned index, long& hr) const
    {
        unsigned char request[0x48] = {};
        *reinterpret_cast<u64*>(request + 0x00) = 1 | 0x400000;
        *reinterpret_cast<unsigned char**>(request + 0x08) = destination.data();
        *reinterpret_cast<unsigned*>(request + 0x18) = static_cast<unsigned>(destination.size());
        *reinterpret_cast<const unsigned char**>(request + 0x20) = stream.data();
        *reinterpret_cast<unsigned*>(request + 0x30) = static_cast<unsigned>(stream.size());
        *reinterpret_cast<unsigned*>(request + 0x38) = inflated;
        reinterpret_cast<EnqueueRequestFn>(queue->vtable[3])(queue, request);
        reinterpret_cast<EnqueueStatusFn>(queue->vtable[4])(queue, status, index);
        reinterpret_cast<SubmitFn>(queue->vtable[6])(queue);
        const DWORD start = GetTickCount();
        while (!reinterpret_cast<IsCompleteFn>(status->vtable[3])(status, index)) {
            if (GetTickCount() - start > completion_timeout_ms) return false;
            Sleep(5);
        }
        hr = reinterpret_cast<GetHResultFn>(status->vtable[4])(status, index);
        return true;
    }
};

// Limits this process's commit to a little above what it holds now. False where that cannot be done.
bool cap_commit()
{
    PROCESS_MEMORY_COUNTERS counters{};
    if (!GetProcessMemoryInfo(GetCurrentProcess(), &counters, sizeof counters)) return false;
    HANDLE job = CreateJobObjectW(nullptr, nullptr);
    if (!job) return false;
    JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits{};
    limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_PROCESS_MEMORY;
    limits.ProcessMemoryLimit = counters.PeakPagefileUsage + commit_headroom;
    return SetInformationJobObject(job, JobObjectExtendedLimitInformation, &limits, sizeof limits) &&
           AssignProcessToJobObject(job, GetCurrentProcess());
}

}  // namespace

int main(int argc, char** argv)
{
    if (argc != 2) {
        std::fprintf(stderr, "usage: startup_storage_alloc_failure XCRDAPI.dll\n");
        return 2;
    }
    HMODULE library = LoadLibraryA(argv[1]);
    auto* get_factory = library ? reinterpret_cast<GetFactoryFn>(GetProcAddress(library, "DStorageGetFactory")) : nullptr;
    void* factory_ptr = nullptr;
    if (!get_factory || get_factory(nullptr, &factory_ptr) != 0 || !factory_ptr) {
        std::fprintf(stderr, "cannot load the DirectStorage stand-in\n");
        return 1;
    }
    auto* factory = static_cast<Object*>(factory_ptr);
    Queue queue;
    void* status_ptr = nullptr;
    void* queue_ptr = nullptr;
    unsigned char description[0x20] = {};
    *reinterpret_cast<std::uint16_t*>(description + 8) = 16;
    if (reinterpret_cast<CreateStatusArrayFn>(factory->vtable[5])(factory, 3, "Status", nullptr, &status_ptr) != 0 ||
        reinterpret_cast<CreateQueueFn>(factory->vtable[10])(factory, description, nullptr, &queue_ptr) != 0) {
        std::fprintf(stderr, "cannot create the queue\n");
        return 1;
    }
    queue.status = static_cast<Object*>(status_ptr);
    queue.queue = static_cast<Object*>(queue_ptr);

    std::vector<unsigned char> plain(60000);
    for (std::size_t i = 0; i < plain.size(); ++i) plain[i] = static_cast<unsigned char>((i % 251) ^ 0x5a);
    const auto stream = stored_zlib(plain);
    const unsigned plain_size = static_cast<unsigned>(plain.size());

    long hr = -1;
    std::vector<unsigned char> first(plain.size(), 0xAA);
    if (!queue.run(first, stream, plain_size, 0, hr) || hr != 0 || first != plain) {
        std::fprintf(stderr, "the baseline request did not succeed (hr 0x%08lx)\n", static_cast<unsigned long>(hr));
        return 1;
    }

    if (!cap_commit()) {
        std::puts("cannot place the process under a commit limit");
        return skipped;
    }
    void* probe = VirtualAlloc(nullptr, oversized_inflated, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE);
    if (probe) {
        VirtualFree(probe, 0, MEM_RELEASE);
        std::puts("the commit limit is not enforced on this system");
        return skipped;
    }

    std::vector<unsigned char> failing(plain.size(), 0xAA);
    if (!queue.run(failing, stream, oversized_inflated, 1, hr)) {
        std::fprintf(stderr, "the request that hit an allocation failure never completed\n");
        return 1;
    }
    if (hr >= 0) {
        std::fprintf(stderr, "the request that hit an allocation failure reported success (hr 0x%08lx)\n",
                     static_cast<unsigned long>(hr));
        return 1;
    }
    for (unsigned char byte : failing)
        if (byte != 0xAA) {
            std::fprintf(stderr, "the failed request changed its destination\n");
            return 1;
        }

    std::vector<unsigned char> after(plain.size(), 0xAA);
    if (!queue.run(after, stream, plain_size, 2, hr) || hr != 0 || after != plain) {
        std::fprintf(stderr, "the worker did not serve a request after the failure (hr 0x%08lx)\n", static_cast<unsigned long>(hr));
        return 1;
    }

    // Also verify that if worker thread creation fails on a fresh queue under commit exhaustion,
    // enqueued status/signal entries complete with failure instead of hanging at E_PENDING, and
    // the queue recovers once commit is freed.
    Queue recovery_queue;
    void* status2_ptr = nullptr;
    void* queue2_ptr = nullptr;
    if (reinterpret_cast<CreateStatusArrayFn>(factory->vtable[5])(factory, 3, "Status2", nullptr, &status2_ptr) != 0 ||
        reinterpret_cast<CreateQueueFn>(factory->vtable[10])(factory, description, nullptr, &queue2_ptr) != 0) {
        std::fprintf(stderr, "cannot create the recovery queue\n");
        return 1;
    }
    recovery_queue.status = static_cast<Object*>(status2_ptr);
    recovery_queue.queue = static_cast<Object*>(queue2_ptr);

    // Two submitters that run while the fence is held: the first completes the failing entries and is inside the
    // fence, the second must return without waiting for it.
    QueueCall first_submit, second_submit;
    first_submit.queue = second_submit.queue = recovery_queue.queue;
    second_submit.status = recovery_queue.status;
    second_submit.enqueue_status_index = 2;
    HANDLE first_thread = CreateThread(nullptr, 0, QueueCall::run, &first_submit, 0, nullptr);
    HANDLE second_thread = CreateThread(nullptr, 0, QueueCall::run, &second_submit, 0, nullptr);
    if (!first_thread || !second_thread || !first_submit.go || !second_submit.go) {
        std::fprintf(stderr, "cannot start the submit threads\n");
        return 1;
    }

    std::vector<unsigned char> during_exhaustion(plain.size(), 0xAA);
    std::vector<unsigned char> after_recovery(plain.size(), 0xAA);
    std::vector<void*> held;
    held.reserve(4096);
    for (SIZE_T chunk : {SIZE_T{1} << 20, SIZE_T{64} << 10}) {
        while (held.size() < held.capacity()) {
            void* p = VirtualAlloc(nullptr, chunk, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE);
            if (!p) break;
            held.push_back(p);
        }
    }
    if (held.size() < held.capacity()) {
        if (void* region = VirtualAlloc(nullptr, SIZE_T{64} << 10, MEM_RESERVE, PAGE_READWRITE)) {
            held.push_back(region);
            for (SIZE_T off = 0; off < (SIZE_T{64} << 10); off += 4096) {
                if (!VirtualAlloc(static_cast<unsigned char*>(region) + off, 4096, MEM_COMMIT, PAGE_READWRITE)) break;
            }
        }
    }

    void* fence_vtable[11] = {};
    fence_vtable[10] = reinterpret_cast<void*>(&MockFence::signal);
    MockFence fence{fence_vtable};
    fence.entered = CreateEventW(nullptr, TRUE, FALSE, nullptr);
    fence.release = CreateEventW(nullptr, TRUE, FALSE, nullptr);

    unsigned char req[0x48] = {};
    *reinterpret_cast<u64*>(req + 0x00) = 1 | 0x400000;
    *reinterpret_cast<unsigned char**>(req + 0x08) = during_exhaustion.data();
    *reinterpret_cast<unsigned*>(req + 0x18) = static_cast<unsigned>(during_exhaustion.size());
    *reinterpret_cast<const unsigned char**>(req + 0x20) = stream.data();
    *reinterpret_cast<unsigned*>(req + 0x30) = static_cast<unsigned>(stream.size());
    *reinterpret_cast<unsigned*>(req + 0x38) = plain_size;

    reinterpret_cast<EnqueueRequestFn>(recovery_queue.queue->vtable[3])(recovery_queue.queue, req);
    reinterpret_cast<EnqueueStatusFn>(recovery_queue.queue->vtable[4])(recovery_queue.queue, recovery_queue.status, 0);
    reinterpret_cast<EnqueueSignalFn>(recovery_queue.queue->vtable[5])(recovery_queue.queue, &fence, 0x1234ull);

    // Submit on one thread; its failing entries complete on that thread and block in the fence. A second Submit
    // with a new deferred entry must return while the fence is held (no queue lock across a fence), and its entry
    // must complete after the fence returns.
    SetEvent(first_submit.go);
    const bool fence_entered = WaitForSingleObject(fence.entered, completion_timeout_ms) == WAIT_OBJECT_0;
    bool second_returned = false;
    if (fence_entered) {
        SetEvent(second_submit.go);
        second_returned = WaitForSingleObject(second_submit.done, 3000) == WAIT_OBJECT_0;
    }
    SetEvent(fence.release);
    const bool first_returned = WaitForSingleObject(first_submit.done, completion_timeout_ms) == WAIT_OBJECT_0;
    WaitForSingleObject(second_submit.done, completion_timeout_ms);

    const bool completed_immediately =
        reinterpret_cast<IsCompleteFn>(recovery_queue.status->vtable[3])(recovery_queue.status, 0);
    const long exhausted_hr =
        reinterpret_cast<GetHResultFn>(recovery_queue.status->vtable[4])(recovery_queue.status, 0);
    const DWORD second_start = GetTickCount();
    while (!reinterpret_cast<IsCompleteFn>(recovery_queue.status->vtable[3])(recovery_queue.status, 2) &&
           GetTickCount() - second_start < completion_timeout_ms) {
        Sleep(5);
    }
    const bool second_completed =
        reinterpret_cast<IsCompleteFn>(recovery_queue.status->vtable[3])(recovery_queue.status, 2);
    const long second_hr = reinterpret_cast<GetHResultFn>(recovery_queue.status->vtable[4])(recovery_queue.status, 2);

    for (void* p : held) VirtualFree(p, 0, MEM_RELEASE);
    held.clear();

    if (!fence_entered || !second_returned || !first_returned || !second_completed || second_hr >= 0) {
        std::fprintf(stderr,
                     "fence held across the queue lock (entered=%d second_returned=%d first_returned=%d "
                     "second_complete=%d second_hr=0x%08lx)\n",
                     fence_entered ? 1 : 0, second_returned ? 1 : 0, first_returned ? 1 : 0, second_completed ? 1 : 0,
                     static_cast<unsigned long>(second_hr));
        return 1;
    }

    if (!completed_immediately || exhausted_hr >= 0 || !fence.signaled || fence.value != 0x1234ull) {
        std::fprintf(stderr,
                     "worker-startup failure did not fail cleanly (complete=%d hr=0x%08lx signaled=%d val=0x%llx)\n",
                     completed_immediately ? 1 : 0, static_cast<unsigned long>(exhausted_hr), fence.signaled ? 1 : 0,
                     static_cast<unsigned long long>(fence.value));
        return 1;
    }

    if (!recovery_queue.run(after_recovery, stream, plain_size, 1, hr) || hr != 0 || after_recovery != plain) {
        std::fprintf(stderr, "the queue did not recover after worker startup failure (hr 0x%08lx)\n",
                     static_cast<unsigned long>(hr));
        return 1;
    }

    std::puts("allocation failure failed the request; the worker served the next one");
    return 0;
}
