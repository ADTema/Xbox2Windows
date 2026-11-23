// Test-only recording provider for d3d12_xs.dll frame-event exports (#874):
//   d3d12_xs.dll!SetFrameIntervalX
//   d3d12_xs.dll!ScheduleFrameEventX
//   d3d12_xs.dll!WaitFrameEventX
//
// Established by public Microsoft sample (InGameStore/DeviceResources.cpp):
// - Registers ORIGIN scheduling once, then waits each frame.
// - Uses INFINITE wait and a NULL event handle.
// - Follow-up: the returned token is subsequently passed into PresentX (not called here).
//
// Labeled as fixture behavior / policy (requiring separate evidence):
// - PE imports: exposing these APIs as d3d12_xs.dll exports is a fixture choice (sample calls device methods).
// - Null output: passing NULL to SetFrameIntervalX is a fixture choice (sample passes an actual IDXGIOutput*).
// - Numeric values: intervals, timeouts, and seeded token representation (monotonic integer increment).
// - Unused HANDLE signaling: dropped per review feedback.
// - Controlled tick driver: one registration injects two scheduled ticks from a worker thread,
//   exercising real blocked waiters with an explicit witness without relying on wall-clock timer resolution.
// - FAULT_CLOBBER / FAULT_EARLY_RELEASE: two distinct fault controls for refusal sentinel overwrite
//   and premature wait release.
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>

#include <atomic>
#include <cstdint>

namespace {
std::atomic<std::uint32_t> g_mode{0};
std::atomic<std::uint64_t> g_token_counter{0};
std::atomic<std::uint64_t> g_origin_waits{0};
std::atomic<std::uint64_t> g_blocked_waits{0};
std::atomic<std::uint64_t> g_timeouts{0};
std::atomic<std::uint64_t> g_rejections{0};
std::atomic<std::uint64_t> g_schedule_calls{0};

HANDLE g_tick_event = NULL;
HANDLE g_worker_thread = NULL;
SRWLOCK g_lock = SRWLOCK_INIT;

DWORD WINAPI tick_injector(LPVOID)
{
    // Delay to guarantee caller is blocked inside first WaitFrameEventX
    Sleep(15);
    SetEvent(g_tick_event);

    // Delay to guarantee caller is blocked inside second WaitFrameEventX
    Sleep(15);
    SetEvent(g_tick_event);

    return 0;
}

void ensure_event()
{
    if (!g_tick_event) {
        AcquireSRWLockExclusive(&g_lock);
        if (!g_tick_event) {
            // Auto-reset event: each SetEvent releases exactly one waiting thread
            g_tick_event = CreateEventW(nullptr, FALSE, FALSE, nullptr);
        }
        ReleaseSRWLockExclusive(&g_lock);
    }
}
} // namespace

extern "C" HRESULT WINAPI SetFrameIntervalX(
    void* output,
    UINT interval,
    UINT period,
    UINT flags)
{
    (void)interval;
    (void)period;
    (void)flags;
    ensure_event();
    ResetEvent(g_tick_event);
    g_mode.store(output != nullptr ? 1 : 0);
    return S_OK;
}

extern "C" HRESULT WINAPI ScheduleFrameEventX(
    UINT event_type,
    UINT offset_us,
    HANDLE event_handle,
    UINT flags)
{
    (void)offset_us;
    (void)event_handle;
    (void)flags;
    ensure_event();

    // Only D3D12XBOX_FRAME_EVENT_ORIGIN (0) has an established contract.
    if (event_type != 0) {
        g_rejections.fetch_add(1);
        return static_cast<HRESULT>(0x80070057); // E_INVALIDARG (fixture policy)
    }

    g_schedule_calls.fetch_add(1);

    // Register ORIGIN once: spawn the controlled injector thread delivering two ticks
    AcquireSRWLockExclusive(&g_lock);
    if (!g_worker_thread) {
        g_worker_thread = CreateThread(nullptr, 0, tick_injector, nullptr, 0, nullptr);
    }
    ReleaseSRWLockExclusive(&g_lock);

    return S_OK;
}

extern "C" HRESULT WINAPI WaitFrameEventX(
    UINT event_type,
    UINT timeout_ms,
    HANDLE event_handle,
    UINT flags,
    UINT64* out_token)
{
    (void)event_handle;
    (void)flags;
    if (!out_token) {
        return static_cast<HRESULT>(0x80004003); // E_POINTER
    }

    // Only D3D12XBOX_FRAME_EVENT_ORIGIN (0) has an established contract.
    if (event_type != 0) {
        g_rejections.fetch_add(1);
#ifdef FAULT_CLOBBER
        // Mutation 1: overwrite caller's sentinel on refusal
        *out_token = 0xBADF00DDEADBEEFull;
#endif
        return static_cast<HRESULT>(0x80070057); // E_INVALIDARG (fixture policy)
    }

#ifdef FAULT_EARLY_RELEASE
    // Mutation 2: release wait early without blocking on tick
    *out_token = g_token_counter.fetch_add(1) + 1;
    return S_OK;
#else
    ensure_event();

    // Bounded wait on the scheduled tick
    const DWORD wait_result = WaitForSingleObject(g_tick_event, timeout_ms);
    if (wait_result == WAIT_TIMEOUT) {
        // Timeout before a tick leaves sentinel unchanged
        g_timeouts.fetch_add(1);
        return static_cast<HRESULT>(0x00000102); // WAIT_TIMEOUT (fixture policy)
    }

    if (wait_result != WAIT_OBJECT_0) {
        return E_FAIL;
    }

    // The waiter actually blocked and was released by an injected tick
    g_blocked_waits.fetch_add(1);
    g_origin_waits.fetch_add(1);
    const std::uint64_t token = g_token_counter.fetch_add(1) + 1;
    *out_token = token;

    // Clean up worker thread when all scheduled ticks are delivered
    if (token >= 2 && g_worker_thread) {
        WaitForSingleObject(g_worker_thread, 2000);
        CloseHandle(g_worker_thread);
        g_worker_thread = NULL;
    }

    return S_OK;
#endif
}

// ---- Instrumentation exports for test verification ----
extern "C" std::uint64_t WINAPI get_frame_events_origin_waits()
{
    return g_origin_waits.load();
}

extern "C" std::uint64_t WINAPI get_frame_events_last_token()
{
    return g_token_counter.load();
}

extern "C" std::uint64_t WINAPI get_frame_events_blocked_waits()
{
    return g_blocked_waits.load();
}

extern "C" std::uint64_t WINAPI get_frame_events_timeouts()
{
    return g_timeouts.load();
}

extern "C" std::uint64_t WINAPI get_frame_events_rejections()
{
    return g_rejections.load();
}

extern "C" std::uint64_t WINAPI get_frame_events_schedule_calls()
{
    return g_schedule_calls.load();
}

extern "C" std::uint32_t WINAPI get_frame_events_mode()
{
    return g_mode.load();
}
