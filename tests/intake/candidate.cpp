#include <windows.h>

extern "C" __declspec(dllimport) int named_value();
extern "C" __declspec(dllimport) int ordinal_value();
extern "C" __declspec(dllimport) int delayed_value();
// Static intake observes this import by name. The fixture never calls it.
extern "C" __declspec(dllimport) void ffxQuery();

static __declspec(thread) int initialized;
static void NTAPI initialize(PVOID, DWORD reason, PVOID)
{
    if (reason == DLL_PROCESS_ATTACH) initialized = 1;
}

#pragma section(".CRT$XLB", long, read)
extern "C" __declspec(allocate(".CRT$XLB")) const PIMAGE_TLS_CALLBACK fixture_tls = initialize;
#pragma comment(linker, "/include:fixture_tls")
#pragma comment(linker, "/include:_tls_used")

int main() {
    auto* volatile graphicsImport = &ffxQuery;
    return initialized + named_value() + ordinal_value() + delayed_value() + (graphicsImport != nullptr);
}
