// A DirectStorage queue whose worker cannot be started keeps the deferred-completion contract
// (#1199, item 3): Enqueue never completes a status entry or signals a fence, and Submit does.
//
// Two failures are made on demand inside the stand-in, which this test compiles into itself instead
// of loading as a DLL, so it shares the test's allocator and CreateThread:
//   - CreateThread is redirected, for the stand-in's translation unit only, to a function that can
//     fail every thread creation (both the committed-stack attempt and the default-stack attempt);
//   - operator new is replaced with one that throws std::bad_alloc on the calling thread when armed.
//     The queue's three std::deque members allocate in their constructors, so the construction of
//     the queue's work throws although the work itself is allocated with new (std::nothrow).
//
// Checks, each on a fresh queue: with no worker, before Submit the status entry is still pending, the
// fence is not signaled and the destination is untouched; after Submit the status entry holds a
// failure and the fence is signaled; with a throwing queue construction no exception reaches the caller
// and the same holds; and once the failure is gone a request on the same queue returns correct data.
// A worker that cannot start at Enqueue but can at Submit runs the entries normally.
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
#include <cstdlib>
#include <new>
#include <vector>

namespace {
std::atomic<bool> fail_thread_creation{false};
std::atomic<int> thread_attempts{0};
thread_local bool throw_on_new = false;
std::atomic<int> thrown{0};

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
    if (throw_on_new) {
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

// A request, a status entry and a fence signal are enqueued; nothing may complete until Submit.
// before_enqueue / before_submit let the caller arm a failure around each step.
template <class Arm>
bool enqueue_without_effects(Fixture& f, Fixture::Queue& q, std::vector<unsigned char>& destination, Arm arm)
{
    try {
        arm(true);
        f.request(q, destination);
        f.status_entry(q, 0);
        f.signal(q, 7);
        arm(false);
    } catch (...) {
        arm(false);
        return fail("an exception left an Enqueue call");
    }
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
    const bool effects_deferred = enqueue_without_effects(f, q, destination, [](bool) {});
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
    const bool effects_deferred = enqueue_without_effects(f, q, destination, [](bool) {});
    fail_thread_creation = false;
    if (!effects_deferred) return false;
    f.submit(q);
    if (!f.wait(q, 0) || f.hresult(q, 0) != 0 || destination != f.plain) return fail("the retried worker did not run the request");
    const DWORD start = GetTickCount();
    while (q.fence.signals == 0 && GetTickCount() - start < completion_timeout_ms) Sleep(5);
    if (q.fence.signals != 1 || q.fence.value != 7) return fail("the retried worker did not signal the fence");
    return true;
}

// Constructing the queue's work throws std::bad_alloc, at Enqueue and also at Submit.
bool construction_throws(Fixture& f, bool throw_at_submit)
{
    Fixture::Queue q;
    if (!f.create(q, f.vtables)) return fail("cannot create the queue");
    std::vector<unsigned char> destination(f.plain.size(), untouched);
    thrown = 0;
    const bool effects_deferred = enqueue_without_effects(f, q, destination, [](bool on) { throw_on_new = on; });
    if (!effects_deferred) return false;
    if (thrown == 0) return fail("the queue construction never threw: the control did not reach the deques");
    try {
        throw_on_new = throw_at_submit;
        f.submit(q);
        throw_on_new = false;
    } catch (...) {
        throw_on_new = false;
        return fail("an exception left Submit");
    }
    if (!failed_at_submit(f, q)) return false;
    if (!untouched_bytes(destination)) return fail("the failed request changed its destination");
    return serves_next_request(f, q);
}

}  // namespace

int main()
{
    void* factory = nullptr;
    if (DStorageGetFactory(nullptr, &factory) != 0 || !factory) return fail("cannot get the factory"), 1;
    Fixture f;
    f.factory = static_cast<Object*>(factory);
    f.plain.resize(60000);
    for (std::size_t i = 0; i < f.plain.size(); ++i) f.plain[i] = static_cast<unsigned char>((i % 251) ^ 0x5a);
    f.stream = stored_zlib(f.plain);

    if (!worker_cannot_start(f)) return 1;
    if (!worker_starts_at_submit(f)) return 1;
    if (!construction_throws(f, false)) return 1;
    if (!construction_throws(f, true)) return 1;
    std::puts("a queue that cannot start its worker completes status and fences at Submit, and recovers");
    return 0;
}
