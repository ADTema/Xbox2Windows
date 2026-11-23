// Controlled recording provider for XMemTransferMemory.
// Validates proposed call contracts and records trace of calls:
// - Partition selector validation (partition 1 = tools memory to title).
// - 2 MiB boundary alignment and non-zero byte count <= 16 MiB.
// - Rejection and tracking of invalid partition, zero bytes, unaligned bytes, and oversized requests.
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#include <cstdint>

namespace {
constexpr std::uint32_t FIXTURE_PARTITION_TOOLS_TO_TITLE = 1;
constexpr std::uint64_t TRANSFER_ALIGNMENT_MASK = 0x1FFFFF; // 2 MiB alignment requirement
constexpr std::uint64_t MAX_TRANSFER_BYTES = 0x1000000;    // 16 MiB maximum boundary

volatile LONG transfer_calls = 0;
volatile LONG rejection_calls = 0;

volatile std::uint32_t recorded_partition = 0;
volatile std::uint64_t recorded_bytes = 0;
}

extern "C" __declspec(dllexport) BOOL WINAPI XMemTransferMemory(
    UINT32 partition,
    UINT64 byte_count)
{
    if (partition != FIXTURE_PARTITION_TOOLS_TO_TITLE ||
        byte_count == 0 ||
        (byte_count & TRANSFER_ALIGNMENT_MASK) != 0 ||
        byte_count > MAX_TRANSFER_BYTES)
    {
        InterlockedIncrement(&rejection_calls);
        SetLastError(ERROR_INVALID_PARAMETER);
        return FALSE;
    }

    recorded_partition = partition;
    recorded_bytes = byte_count;
    InterlockedIncrement(&transfer_calls);
    SetLastError(ERROR_SUCCESS);
    return TRUE;
}

extern "C" __declspec(dllexport) uint32_t WINAPI get_transfer_call_count(void)
{
    return static_cast<uint32_t>(transfer_calls);
}

extern "C" __declspec(dllexport) uint32_t WINAPI get_argument_rejection_count(void)
{
    return static_cast<uint32_t>(rejection_calls);
}

extern "C" __declspec(dllexport) uint32_t WINAPI get_recorded_partition(void)
{
    return static_cast<uint32_t>(recorded_partition);
}

extern "C" __declspec(dllexport) uint64_t WINAPI get_recorded_bytes(void)
{
    return static_cast<uint64_t>(recorded_bytes);
}

extern "C" __declspec(dllexport) void WINAPI reset_transfer_mem_records(void)
{
    InterlockedExchange(&transfer_calls, 0);
    InterlockedExchange(&rejection_calls, 0);
    recorded_partition = 0;
    recorded_bytes = 0;
}
