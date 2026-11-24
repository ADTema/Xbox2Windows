// Verifies that GameInput.dll plays the final entry of a long input script.
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>

#include <cstdint>
#include <cstdio>
#include <string>

namespace {

constexpr std::uint32_t kind_gamepad = 0x00040000;
constexpr std::uint32_t dpad_right = 0x200;

struct GamepadState {
    std::uint32_t buttons;
    float leftTrigger, rightTrigger;
    float leftThumbstickX, leftThumbstickY, rightThumbstickX, rightThumbstickY;
};
static_assert(sizeof(GamepadState) == 28, "GamepadState layout");

struct IGameInputDevice;

struct IGameInputReading {
    const void* const* vtbl;

    std::uint32_t Release()
    {
        using Fn = std::uint64_t(__stdcall*)(IGameInputReading*);
        return static_cast<std::uint32_t>(reinterpret_cast<Fn>(vtbl[2])(this));
    }
    bool GetGamepadState(GamepadState* state)
    {
        using Fn = bool(__stdcall*)(IGameInputReading*, GamepadState*);
        return reinterpret_cast<Fn>(vtbl[22])(this, state);
    }
};

struct IGameInput {
    const void* const* vtbl;

    std::uint32_t Release()
    {
        using Fn = std::uint64_t(__stdcall*)(IGameInput*);
        return static_cast<std::uint32_t>(reinterpret_cast<Fn>(vtbl[2])(this));
    }
    HRESULT GetCurrentReading(std::uint32_t kind, IGameInputDevice* device, IGameInputReading** reading)
    {
        using Fn = HRESULT(__stdcall*)(IGameInput*, std::uint32_t, IGameInputDevice*, IGameInputReading**);
        return reinterpret_cast<Fn>(vtbl[4])(this, kind, device, reading);
    }
};

int fail(const char* reason)
{
    std::printf("FAIL: %s\n", reason);
    return 1;
}

bool read_gamepad(IGameInput* input, GamepadState* state)
{
    IGameInputReading* reading = nullptr;
    const HRESULT hr = input->GetCurrentReading(kind_gamepad, nullptr, &reading);
    const bool ok = SUCCEEDED(hr) && reading && reading->GetGamepadState(state);
    if (reading) reading->Release();
    return ok;
}

const char* check_script(IGameInput* input)
{
    // The first GetCurrentReading calls capture_current(), which calls sample()
    // and starts the script clock. GetGamepadState copies the captured state.
    const ULONGLONG start = GetTickCount64();
    GamepadState state{};
    do {
        if (!read_gamepad(input, &state)) return "could not read initial gamepad state";
        if (state.buttons & dpad_right) break;
        Sleep(25);
    } while (GetTickCount64() - start < 200);
    if (!(state.buttons & dpad_right)) return "script did not press D-pad right";

    const ULONGLONG elapsed = GetTickCount64() - start;
    if (elapsed < 600) Sleep(static_cast<DWORD>(600 - elapsed));
    if (!read_gamepad(input, &state)) return "could not read gamepad state after the press";
    if (state.buttons & dpad_right) return "script did not release D-pad right";
    return nullptr;
}

}  // namespace

int main(int argc, char** argv)
{
    if (argc < 2) return fail("expected the path to GameInput.dll");

    // The 40 future entries put the immediate press beyond both old limits.
    // src_startup_stubs_gameinput_MAIN.cpp ignores the entire value because it
    // exceeds its 512-byte buffer, so the script never sets bit 0x200.
    std::string script;
    for (int i = 0; i < 40; ++i) script += "00000001@9000.000,";
    script += "200@0";
    if (!SetEnvironmentVariableA("X2W_INPUT_SCRIPT", script.c_str()))
        return fail("could not set X2W_INPUT_SCRIPT");
    if (!SetEnvironmentVariableA("X2W_INPUT_PRESS", nullptr) && GetLastError() != ERROR_ENVVAR_NOT_FOUND)
        return fail("could not clear X2W_INPUT_PRESS");

    HMODULE dll = LoadLibraryA(argv[1]);
    if (!dll) return fail("LoadLibraryA failed");

    using CreateFn = HRESULT(__stdcall*)(IGameInput**);
    auto create = reinterpret_cast<CreateFn>(GetProcAddress(dll, "GameInputCreate"));
    if (!create) {
        FreeLibrary(dll);
        return fail("GetProcAddress(GameInputCreate) failed");
    }

    IGameInput* input = nullptr;
    if (FAILED(create(&input)) || !input) {
        FreeLibrary(dll);
        return fail("GameInputCreate failed");
    }

    const char* error = check_script(input);
    input->Release();
    FreeLibrary(dll);
    if (error) return fail(error);
    std::printf("PASS\n");
    return 0;
}
