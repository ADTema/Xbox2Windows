// Records initialization calls from tls_route images. It is loaded before and unloaded after
// the images it observes, so detach calls remain visible after the image is gone.
#include <cstddef>
#include <cstdint>

struct Call {
    std::uint32_t caller;
    std::uint32_t reason;
    std::uint64_t module;
    std::uint64_t reserved;
};

static Call calls[64];
static std::size_t count;

extern "C" __declspec(dllexport) void sink_record(void* module, std::uint32_t reason, void* reserved,
                                                  std::uint32_t caller) {
    if (count < sizeof(calls) / sizeof(calls[0]))
        calls[count++] = {caller, reason, reinterpret_cast<std::uint64_t>(module),
                          reinterpret_cast<std::uint64_t>(reserved)};
}

extern "C" __declspec(dllexport) std::size_t sink_read(Call* out, std::size_t capacity) {
    for (std::size_t i = 0; i < count && i < capacity; ++i) out[i] = calls[i];
    return count;
}

extern "C" __declspec(dllexport) void sink_clear() { count = 0; }
