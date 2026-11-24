#include <windows.h>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <intrin.h>
#include <new>
#include <string>
#include <utility>
#include <vector>
// Everything runtime_proxy.cpp includes, before the logf/GetProcAddress macros below, so that the
// macros rename only the proxy's own calls and not declarations in the standard headers.
#include "startup_stubs/api_trace.h"
#include "startup_stubs/local_log.h"
#include "startup_stubs/save_blob_pack.h"
#include "startup_stubs/save_store.h"
#include "startup_stubs/storage_root.h"
#include "startup_stubs/storage_root_utf8.h"

namespace {
FARPROC WINAPI fixture_get_proc_address(HMODULE, LPCSTR name);
unsigned activation_logs{}, unanswered_logs{};
}

namespace x2w_local {
// Count the dedicated diagnostics separately from ordinary method tracing.
void fixture_logf(const char* format, ...)
{
    if (std::strstr(format, "-> S_OK (local runtime)")) ++activation_logs;
    if (std::strstr(format, "has no answer, E_NOTIMPL")) ++unanswered_logs;
}
}

#define GetProcAddress fixture_get_proc_address
#define logf fixture_logf
#include "../src/startup_stubs/runtime_proxy.cpp"
#undef logf
#undef GetProcAddress

namespace {
constexpr const char* exports[]{"InitializeApiImpl", "InitializeApiImplEx", "InitializeApiImplEx2"};
constexpr GUID providers[]{
    {0x01acd177}, {0x704c3f58}, {0xaf406016}, {0x973a344e}, {0x37e56907}, {0x0dd112ac},
};
constexpr GUID unknown_provider{0x12345678};
constexpr GUID async_provider{0x073b7dcb, 0x1fcf, 0x4030, {0x94,0xbe,0xe3,0xc9,0xeb,0x62,0x34,0x28}};
constexpr u64 init_failure = static_cast<unsigned>(E_ACCESSDENIED);
constexpr HRESULT query_failure = E_NOINTERFACE;
u64 init_result = init_failure;
unsigned init_calls[3]{}, provider_queries{}, async_queries{};
bool init_arguments_ok = true;

template<int Index>
u64 WINAPI fixture_init(u64 a, u64 b, u64 c, u64 d)
{
    ++init_calls[Index];
    init_arguments_ok = init_arguments_ok && a == 11 && b == 22 && c == 33 && d == 44;
    return init_result;
}

const InitApi original_init[]{fixture_init<0>, fixture_init<1>, fixture_init<2>};
const InitApi wrapped_init[]{proxy_init<0>, proxy_init<1>, proxy_init<2>};

struct Block {
    void* queue{};
    void* context{};
    void (WINAPI* callback)(Block*){};
    unsigned char internal[32]{};
};
void* async_methods[11]{};
struct AsyncService { void** vtable; } async_service{async_methods};
Block* expected_block{};
bool pending{}, async_arguments_ok = true;
unsigned begins{}, completions{}, releases{};
HRESULT completion_status = E_PENDING;
size_t completion_size = 1;

HRESULT WINAPI fixture_begin(void* self, void* block, void*, const void* identity,
                             const char* name, decltype(&submit_provider) provider)
{
    ++begins;
    if (self != &async_service || !expected_block || block != expected_block || pending ||
        !identity || !name || !provider) {
        async_arguments_ok = false;
        return E_INVALIDARG;
    }
    const auto result = provider(0, nullptr);
    pending = SUCCEEDED(result);
    return result;
}

void WINAPI fixture_complete(void* self, void* block, HRESULT status, size_t size)
{
    ++completions;
    if (self != &async_service || !pending || block != expected_block) {
        async_arguments_ok = false;
        return;
    }
    pending = false;
    completion_status = status;
    completion_size = size;
    auto* completed = static_cast<Block*>(block);
    if (completed->callback) completed->callback(completed);
}

ULONG WINAPI fixture_release(void* self)
{
    ++releases;
    async_arguments_ok = async_arguments_ok && self == &async_service && !pending;
    return 1;
}

HRESULT WINAPI fixture_query(const GUID* provider, const GUID* iid, void** out)
{
    *out = nullptr;
    if (provider && *provider == async_provider) {
        ++async_queries;
        if (!iid || *iid != async_provider) return query_failure;
        *out = &async_service;
        return S_OK;
    }
    ++provider_queries;
    return query_failure;
}

FARPROC WINAPI fixture_get_proc_address(HMODULE, LPCSTR name)
{
    for (int i = 0; i < 3; ++i)
        if (std::strcmp(name, exports[i]) == 0) return reinterpret_cast<FARPROC>(original_init[i]);
    if (std::strcmp(name, "QueryApiImpl") == 0) return reinterpret_cast<FARPROC>(&fixture_query);
    if (std::strcmp(name, "UnrelatedExport") == 0) return reinterpret_cast<FARPROC>(original_init[0]);
    return nullptr;
}

template<class T> u64 address(T* pointer) { return reinterpret_cast<u64>(pointer); }

u64 invoke(Proxy* proxy, int slot, u64 a = 0, u64 b = 0)
{
    return reinterpret_cast<Method>(proxy->vtable[slot])(proxy, a, b, 0, 0, 0, 0, 0, 0, 0, 0, 0);
}

struct Completion { Proxy* user; unsigned callbacks{}; u64 result{init_failure}, handle{}; };

void WINAPI on_complete(Block* block)
{
    auto& seen = *static_cast<Completion*>(block->context);
    ++seen.callbacks;
    seen.result = invoke(seen.user, 8, address(block), address(&seen.handle));
}

bool set_switch(const char* name, bool enabled)
{
    const char* value = enabled ? "1" : "0";
    return _putenv_s(name, value) == 0 && SetEnvironmentVariableA(name, value) &&
           x2w_local::env_on(name) == enabled;
}

bool query_fails(QueryApi query, const GUID& id)
{
    void* object = &async_service;
    const unsigned previous = provider_queries;
    return query(&id, &id, &object) == query_failure && !object && provider_queries == previous + 1;
}

const char* run()
{
    if (!set_switch("X2W_RUNTIME_PROXY", true) || !set_switch("X2W_TRACE_API", false) ||
        !set_switch("X2W_FAKE_USER", true) || !set_switch("X2W_RUNTIME_LOCAL", false))
        return "could not set the test environment";

    // Initialize the dispatch table as process attach does, without patching the test executable.
    fill_slots(std::make_index_sequence<max_slots>{});
    const auto query_addr = hooked_get_proc_address(nullptr, "QueryApiImpl");
    if (query_addr != reinterpret_cast<FARPROC>(&proxy_query)) return "switch off changed the QueryApiImpl hook";
    const auto query = reinterpret_cast<QueryApi>(query_addr);
    for (int i = 0; i < 3; ++i) {
        const auto entry = reinterpret_cast<InitApi>(hooked_get_proc_address(nullptr, exports[i]));
        if (entry != original_init[i] || entry(11, 22, 33, 44) != init_failure || init_calls[i] != 1)
            return "switch off changed an initialization export or its real failure";
    }
    if (local_active || activation_logs || !query_fails(query, providers[0]))
        return "switch off activated the fallback";

    if (!set_switch("X2W_RUNTIME_LOCAL", true)) return "could not enable local runtime";
    if (hooked_get_proc_address(nullptr, "QueryApiImpl") != query_addr ||
        hooked_get_proc_address(nullptr, "UnrelatedExport") != fixture_get_proc_address(nullptr, "UnrelatedExport") ||
        hooked_get_proc_address(nullptr, "MissingExport"))
        return "local runtime changed a non-initialization export";

    for (int i = 0; i < 3; ++i) {
        // Give every export its own attempt to trigger the process-wide latch.
        InterlockedExchange(&local_active, 0);
        const auto entry = reinterpret_cast<InitApi>(hooked_get_proc_address(nullptr, exports[i]));
        if (entry != wrapped_init[i]) {
            std::printf("Initialization export: %s\n", exports[i]);
            return "local runtime did not return the expected initialization wrapper";
        }
        const unsigned previous = init_calls[i];
        init_result = S_FALSE;
        if (entry(11, 22, 33, 44) != S_FALSE || init_calls[i] != previous + 1 || local_active ||
            activation_logs != static_cast<unsigned>(i) || !query_fails(query, providers[0]))
            return "successful initialization did not pass through or activated the fallback";
        init_result = init_failure;
        if (entry(11, 22, 33, 44) != S_OK || init_calls[i] != previous + 2 || !local_active ||
            activation_logs != static_cast<unsigned>(i + 1))
            return "failed initialization did not activate and log the fallback";
        if (entry(11, 22, 33, 44) != S_OK || init_calls[i] != previous + 2 ||
            activation_logs != static_cast<unsigned>(i + 1) || !init_arguments_ok)
            return "fallback retried the real export, logged again, or changed initialization arguments";
    }

    for (int i = 0; i < 3; ++i) {
        const auto entry = reinterpret_cast<InitApi>(hooked_get_proc_address(nullptr, exports[i]));
        if (entry != wrapped_init[i] || entry(11, 22, 33, 44) != S_OK || init_calls[i] != 3 || activation_logs != 3)
            return "active fallback did not short-circuit all initialization exports";
    }

    // Keep the latch set so this control independently verifies the fake-user gate in QueryApiImpl.
    if (!set_switch("X2W_FAKE_USER", false)) return "could not disable fake user";
    for (int i = 0; i < 3; ++i)
        if (reinterpret_cast<InitApi>(hooked_get_proc_address(nullptr, exports[i])) != original_init[i])
            return "fake user off still wrapped an initialization export";
    for (const auto& id : providers)
        if (!query_fails(query, id)) return "fake user off still returned a local object";
    if (!set_switch("X2W_FAKE_USER", true)) return "could not re-enable fake user";
    if (!query_fails(query, unknown_provider)) return "unlisted provider did not keep the real failure";

    Proxy* user = nullptr;
    for (const auto& id : providers) {
        void* object = nullptr;
        const unsigned previous = provider_queries;
        if (query(&id, &id, &object) != S_OK || !object || provider_queries != previous + 1)
            return "listed provider did not fall back after a real query failure";
        auto* proxy = static_cast<Proxy*>(object);
        if (proxy->real || proxy->vtable != slot_table) return "local provider did not return a null-real proxy";
        if (id == providers[0]) user = proxy;
        u64 queried{};
        if (invoke(proxy, 0, address(&id), address(&queried)) != S_OK || queried != address(proxy) ||
            invoke(proxy, 1) != 1 || invoke(proxy, 2) != 1)
            return "local QueryInterface, AddRef, or Release result was wrong";
    }
    constexpr int unanswered_slot = 95;
    if (invoke(user, unanswered_slot) != static_cast<unsigned>(E_NOTIMPL) || unanswered_logs != 1 ||
        invoke(user, unanswered_slot) != static_cast<unsigned>(E_NOTIMPL) || unanswered_logs != 1)
        return "unanswered local slot did not return E_NOTIMPL and log once";

    async_methods[2] = reinterpret_cast<void*>(&fixture_release);
    async_methods[7] = reinterpret_cast<void*>(&fixture_begin);
    async_methods[10] = reinterpret_cast<void*>(&fixture_complete);
    Completion seen{user};
    Block block{};
    block.context = &seen;
    block.callback = on_complete;
    expected_block = &block;
    if (invoke(user, 7, 0, address(&block)) != S_OK || async_queries != 1 ||
        begins != 1 || completions != 1 || releases != 1 || !async_arguments_ok || pending ||
        completion_status != S_OK || completion_size != 0 || seen.callbacks != 1)
        return "XUserAddAsync did not complete the caller's block through XAsync";
    if (seen.result != S_OK || seen.handle != local_user_handle)
        return "XUserAddResult did not return the local handle from the completion callback";
    return nullptr;
}
}

int main()
{
    if (const char* reason = run()) {
        std::printf("FAIL: %s\n", reason);
        return 1;
    }
    std::puts("PASS");
    return 0;
}
