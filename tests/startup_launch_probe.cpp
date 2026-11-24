// Input for the launch tool's containment check (docs/startup-runtime.md). The launcher runs one
// executable in a kill-on-close job with a timeout, a commit cap and captured stdout/stderr, and
// this fixture is the only executable the check needs: it writes known bytes to both streams and
// the trap log, reports a known exit code, or holds memory, spawns a child or stays alive so the
// job limits have to stop it.
#include <windows.h>

#include <cstdio>
#include <cstdlib>
#include <cstring>

namespace {
void stream(FILE* out, const char* text)
{
    std::fputs(text, out);
    std::fflush(out);
}

void write_trap_log(const char* text)
{
    char path[MAX_PATH]{};
    if (!GetEnvironmentVariableA("X2W_TRAP_LOG", path, MAX_PATH)) return;
    if (FILE* file = std::fopen(path, "w")) {
        std::fputs(text, file);
        std::fclose(file);
    }
}

void spawn_second_process(const char* self)
{
    char command[MAX_PATH + 16]{};
    std::snprintf(command, sizeof(command), "\"%s\" noop", self);
    STARTUPINFOA startup{};
    startup.cb = sizeof(startup);
    PROCESS_INFORMATION child{};
    if (!CreateProcessA(nullptr, command, nullptr, nullptr, FALSE, 0, nullptr, nullptr, &startup, &child)) {
        std::printf("spawn failed error=%lu\n", GetLastError());
        return;
    }
    WaitForSingleObject(child.hProcess, 5000);
    CloseHandle(child.hThread);
    CloseHandle(child.hProcess);
    std::printf("spawn ok\n");
}
}  // namespace

int main(int argc, char** argv)
{
    const char* mode = argc > 1 ? argv[1] : "report";
    if (std::strcmp(mode, "report") == 0) {
        stream(stdout, "launch-probe stdout\n");
        stream(stderr, "launch-probe stderr\n");
        write_trap_log("x2w-trap launch-probe\n");
        return argc > 2 ? std::atoi(argv[2]) : 0;
    }
    if (std::strcmp(mode, "sleep") == 0) {
        stream(stdout, "launch-probe sleeping\n");
        Sleep(static_cast<DWORD>(argc > 2 ? std::atoi(argv[2]) : 30000));
        return 0;
    }
    if (std::strcmp(mode, "allocate") == 0) {
        const SIZE_T mib = static_cast<SIZE_T>(argc > 2 ? std::atoi(argv[2]) : 64);
        void* memory = VirtualAlloc(nullptr, mib << 20, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
        if (!memory) {
            std::printf("allocate failed error=%lu\n", GetLastError());
            return 0;
        }
        std::memset(memory, 0x5a, mib << 20);
        std::printf("allocate ok %zu MiB\n", mib);
        VirtualFree(memory, 0, MEM_RELEASE);
        return 0;
    }
    if (std::strcmp(mode, "spawn") == 0) {
        char self[MAX_PATH]{};
        if (!GetModuleFileNameA(nullptr, self, MAX_PATH)) return 65;
        spawn_second_process(self);
        return 0;
    }
    if (std::strcmp(mode, "noop") == 0) return 0;
    return 64;
}