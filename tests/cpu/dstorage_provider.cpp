// Controlled DirectStorage factory and queue adapter provider for startup and staging tests.
// Implements XCRDAPI!DStorageGetFactory, IDStorageFactoryX, and IDStorageQueueX:
// - Verifies factory creation under console factory interface {62959d11-d45f-4884-a0a3-f7862ea243ae}.
// - Verifies SetStagingBufferSize (vtable slot 8) configuration (e.g. 32 MiB).
// - Verifies console queue creation (vtable slot 10) under queue interface {3c02cb0c-c050-4195-99a1-a1ce94ba33c5}.
// - Verifies delayed-submit negative control: staged requests remain pending until explicit Submit().
// - Verifies queue capacity threshold auto-submission behavior.
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#include <unknwn.h>
#include <cstddef>
#include <cstdint>
#include <cstring>

namespace {
// DirectStorage Xbox console interfaces
// IDStorageFactoryX: {62959d11-d45f-4884-a0a3-f7862ea243ae}
const GUID IID_IDStorageFactoryX = {
    0x62959d11, 0xd45f, 0x4884, {0xa0, 0xa3, 0xf7, 0x86, 0x2e, 0xa2, 0x43, 0xae}
};

// IDStorageQueueX: {3c02cb0c-c050-4195-99a1-a1ce94ba33c5}
const GUID IID_IDStorageQueueX = {
    0x3c02cb0c, 0xc050, 0x4195, {0x99, 0xa1, 0xa1, 0xce, 0x94, 0xba, 0x33, 0xc5}
};

// IDStorageQueueX legacy: {cd66d752-2786-44f7-9070-e2a6fdad3f1b}
const GUID IID_IDStorageQueueX_Legacy = {
    0xcd66d752, 0x2786, 0x44f7, {0x90, 0x70, 0xe2, 0xa6, 0xfd, 0xad, 0x3f, 0x1b}
};

// Test provider counters and records
volatile LONG cfg_factory_success = 1;
volatile LONG cfg_queue_success = 1;

volatile LONG factory_calls = 0;
volatile LONG queue_calls = 0;
volatile LONG staged_requests = 0;
volatile LONG submitted_batches = 0;
volatile uint32_t current_staging_buffer_size = 0;
volatile LONG active_queues = 0;

// Forward declarations
struct MockQueue;
struct MockFactory;

void* factory_vtable[16] = {};
void* queue_vtable[16] = {};

struct MockQueue {
    void** vtable;
    volatile LONG ref_count;
    uint16_t capacity;
    uint32_t pending_requests;
    volatile LONG is_completed;

    MockQueue(uint16_t cap)
        : vtable(queue_vtable), ref_count(1), capacity(cap), pending_requests(0), is_completed(0)
    {
        InterlockedIncrement(&active_queues);
        InterlockedIncrement(&queue_calls);
    }

    ~MockQueue()
    {
        InterlockedDecrement(&active_queues);
    }

    static HRESULT WINAPI QueryInterface(MockQueue* self, const GUID& riid, void** ppv)
    {
        if (!ppv) return E_POINTER;
        if (IsEqualGUID(riid, IID_IUnknown) ||
            IsEqualGUID(riid, IID_IDStorageQueueX) ||
            IsEqualGUID(riid, IID_IDStorageQueueX_Legacy))
        {
            AddRef(self);
            *ppv = self;
            return S_OK;
        }
        *ppv = nullptr;
        return E_NOINTERFACE;
    }

    static ULONG WINAPI AddRef(MockQueue* self)
    {
        return InterlockedIncrement(&self->ref_count);
    }

    static ULONG WINAPI Release(MockQueue* self)
    {
        ULONG r = InterlockedDecrement(&self->ref_count);
        if (r == 0) {
            delete self;
        }
        return r;
    }

    static void WINAPI EnqueueRequest(MockQueue* self, const void* request)
    {
        (void)request;
        InterlockedIncrement(&staged_requests);
        self->pending_requests++;
        // DirectStorage auto-submission triggers when reaching half capacity
        if (self->capacity > 0 && self->pending_requests >= (self->capacity / 2)) {
            Submit(self);
        }
    }

    static void WINAPI EnqueueStatus(MockQueue* self, void* statusArray, uint32_t index)
    {
        (void)self;
        (void)statusArray;
        (void)index;
    }

    static void WINAPI EnqueueSignal(MockQueue* self, void* fence, uint64_t value)
    {
        (void)self;
        (void)fence;
        (void)value;
    }

    static void WINAPI Submit(MockQueue* self)
    {
        InterlockedIncrement(&submitted_batches);
        self->pending_requests = 0;
        InterlockedExchange(&self->is_completed, 1);
    }

    static void WINAPI CancelRequestsWithTag(MockQueue* self, uint64_t mask, uint64_t tag)
    {
        (void)self;
        (void)mask;
        (void)tag;
    }
};

struct QueueDesc {
    uint32_t SourceType;
    uint16_t Capacity;
    int8_t Priority;
    const char* Name;
};

struct MockFactory {
    void** vtable;
    volatile LONG ref_count;

    MockFactory() : vtable(factory_vtable), ref_count(1) {}

    static HRESULT WINAPI DummyMethod()
    {
        return S_OK;
    }

    static HRESULT WINAPI QueryInterface(MockFactory* self, const GUID& riid, void** ppv)
    {
        if (!ppv) return E_POINTER;
        if (IsEqualGUID(riid, IID_IUnknown) || IsEqualGUID(riid, IID_IDStorageFactoryX)) {
            AddRef(self);
            *ppv = self;
            return S_OK;
        }
        *ppv = nullptr;
        return E_NOINTERFACE;
    }

    static ULONG WINAPI AddRef(MockFactory* self)
    {
        return InterlockedIncrement(&self->ref_count);
    }

    static ULONG WINAPI Release(MockFactory* self)
    {
        ULONG r = InterlockedDecrement(&self->ref_count);
        if (r == 0) {
            delete self;
        }
        return r;
    }

    static HRESULT WINAPI OpenFile(MockFactory* self, const wchar_t* path, const GUID& riid, void** ppv)
    {
        (void)self;
        (void)path;
        (void)riid;
        if (!ppv) return E_POINTER;
        *ppv = nullptr;
        return S_OK;
    }

    static HRESULT WINAPI SetStagingBufferSize(MockFactory* self, uint32_t size)
    {
        (void)self;
        // DirectStorage contract: staging buffer cannot be resized while queues or files are active
        if (active_queues > 0) {
            return E_FAIL;
        }
        current_staging_buffer_size = size;
        return S_OK;
    }

    static HRESULT WINAPI CreateQueue(MockFactory* self, const QueueDesc* desc, const GUID& riid, void** ppv)
    {
        (void)self;
        if (!ppv) return E_POINTER;
        if (!cfg_queue_success) {
            *ppv = nullptr;
            return E_FAIL;
        }
        if (!IsEqualGUID(riid, IID_IDStorageQueueX) && !IsEqualGUID(riid, IID_IDStorageQueueX_Legacy)) {
            *ppv = nullptr;
            return E_NOINTERFACE;
        }

        uint16_t cap = desc ? desc->Capacity : 128;
        *ppv = new MockQueue(cap);
        return S_OK;
    }
};

void init_vtables()
{
    static bool initialized = false;
    if (initialized) return;

    for (int i = 0; i < 16; ++i) {
        factory_vtable[i] = reinterpret_cast<void*>(&MockFactory::DummyMethod);
        queue_vtable[i] = reinterpret_cast<void*>(&MockFactory::DummyMethod);
    }

    factory_vtable[0] = reinterpret_cast<void*>(&MockFactory::QueryInterface);
    factory_vtable[1] = reinterpret_cast<void*>(&MockFactory::AddRef);
    factory_vtable[2] = reinterpret_cast<void*>(&MockFactory::Release);
    factory_vtable[4] = reinterpret_cast<void*>(&MockFactory::OpenFile);
    factory_vtable[8] = reinterpret_cast<void*>(&MockFactory::SetStagingBufferSize);
    factory_vtable[10] = reinterpret_cast<void*>(&MockFactory::CreateQueue);

    queue_vtable[0] = reinterpret_cast<void*>(&MockQueue::QueryInterface);
    queue_vtable[1] = reinterpret_cast<void*>(&MockQueue::AddRef);
    queue_vtable[2] = reinterpret_cast<void*>(&MockQueue::Release);
    queue_vtable[3] = reinterpret_cast<void*>(&MockQueue::EnqueueRequest);
    queue_vtable[4] = reinterpret_cast<void*>(&MockQueue::EnqueueStatus);
    queue_vtable[5] = reinterpret_cast<void*>(&MockQueue::EnqueueSignal);
    queue_vtable[6] = reinterpret_cast<void*>(&MockQueue::Submit);
    queue_vtable[7] = reinterpret_cast<void*>(&MockQueue::CancelRequestsWithTag);

    initialized = true;
}
} // namespace

extern "C" __declspec(dllexport) HRESULT WINAPI DStorageGetFactory(const GUID& riid, void** ppv)
{
    init_vtables();
    InterlockedIncrement(&factory_calls);
    if (!ppv) return E_POINTER;

    if (!cfg_factory_success || !IsEqualGUID(riid, IID_IDStorageFactoryX)) {
        *ppv = nullptr;
        return (!cfg_factory_success) ? E_FAIL : E_NOINTERFACE;
    }

    *ppv = new MockFactory();
    return S_OK;
}

// Verification and configuration exports
extern "C" __declspec(dllexport) uint32_t WINAPI get_dstorage_factory_calls(void)
{
    return static_cast<uint32_t>(factory_calls);
}

extern "C" __declspec(dllexport) uint32_t WINAPI get_dstorage_queue_calls(void)
{
    return static_cast<uint32_t>(queue_calls);
}

extern "C" __declspec(dllexport) uint32_t WINAPI get_dstorage_staging_buffer_size(void)
{
    return current_staging_buffer_size;
}

extern "C" __declspec(dllexport) uint32_t WINAPI get_dstorage_staged_requests_count(void)
{
    return static_cast<uint32_t>(staged_requests);
}

extern "C" __declspec(dllexport) uint32_t WINAPI get_dstorage_submitted_count(void)
{
    return static_cast<uint32_t>(submitted_batches);
}

extern "C" __declspec(dllexport) void WINAPI set_dstorage_factory_success(BOOL val)
{
    InterlockedExchange(&cfg_factory_success, val ? 1 : 0);
}

extern "C" __declspec(dllexport) void WINAPI set_dstorage_queue_success(BOOL val)
{
    InterlockedExchange(&cfg_queue_success, val ? 1 : 0);
}

extern "C" __declspec(dllexport) void WINAPI reset_dstorage_records(void)
{
    InterlockedExchange(&factory_calls, 0);
    InterlockedExchange(&queue_calls, 0);
    InterlockedExchange(&staged_requests, 0);
    InterlockedExchange(&submitted_batches, 0);
    InterlockedExchange(&active_queues, 0);
    current_staging_buffer_size = 0;
    cfg_factory_success = 1;
    cfg_queue_success = 1;
}
