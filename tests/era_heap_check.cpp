#include "era_heap.h"

#include <algorithm>
#include <array>
#include <atomic>
#include <barrier>
#include <cstdio>
#include <limits>
#include <string_view>
#include <thread>
#ifdef _DEBUG
#include <crtdbg.h>
#endif

using namespace std::literals;

bool allocation_checks()
{
    constexpr std::size_t bytes = 257;
#ifdef _DEBUG
    _CrtMemState before{}, after{}, change{};
    _CrtMemCheckpoint(&before);
#endif
    for (unsigned exponent : {0u, 3u, 4u, 6u, 12u, 16u}) {
        auto* p = static_cast<unsigned char*>(
            era_heap::allocate(bytes, static_cast<std::uint64_t>(exponent) << 24));
        if (!p) {
            return false;
        }
        const auto alignment = std::size_t{1} << std::max(4u, exponent);
        const bool aligned = reinterpret_cast<std::uintptr_t>(p) % alignment == 0;
        const bool zeroed = std::all_of(p, p + bytes, [](auto b) { return b == 0; });
        std::fill_n(p, bytes, 0xa5);
        era_heap::release(p);
        if (!aligned || !zeroed) {
            return false;
        }
    }
    era_heap::release(nullptr);
#ifdef _DEBUG
    _CrtMemCheckpoint(&after);
    return !_CrtMemDifference(&change, &before, &after);
#else
    return true;
#endif
}

bool failure_checks()
{
    return era_heap::allocate(0, 0) == nullptr &&
           era_heap::allocate(std::numeric_limits<std::size_t>::max(), 0) == nullptr &&
           era_heap::allocate(64, 1ull << 29) == nullptr &&  // graphics memory type
           era_heap::allocate(64, 1ull << 14) == nullptr &&  // non-default page size
           era_heap::allocate(64, 1ull << 63) == nullptr &&
           era_heap::allocate(257 + 64, 0x05e50000) == nullptr &&  // Bink fallback
           era_heap::allocate(512, 0xa8004000) == nullptr;        // AMD, 257 rounded up
}

bool concurrency_checks()
{
    constexpr std::size_t bytes = 511;
    std::array<std::thread, 4> workers;
    std::barrier rendezvous(static_cast<std::ptrdiff_t>(workers.size()));
    std::atomic<bool> ok{true};
    for (unsigned i = 0; i < workers.size(); ++i) {
        workers[i] = std::thread([&, i] {
            const auto marker = static_cast<unsigned char>(i + 1);
            for (int round = 0; round < 100; ++round) {
                auto* p = static_cast<unsigned char*>(era_heap::allocate(bytes, 6ull << 24));
                if (p) {
                    std::fill_n(p, bytes, marker);
                }
                rendezvous.arrive_and_wait();
                if (!p || !std::all_of(p, p + bytes, [marker](auto b) { return b == marker; })) {
                    ok = false;
                }
                rendezvous.arrive_and_wait();
                era_heap::release(p);
            }
        });
    }
    for (auto& worker : workers) {
        worker.join();
    }
    return ok.load();
}

int main(int argc, char** argv)
{
    if (argc != 2) {
        return 2;
    }
    const std::string_view scenario = argv[1];
    bool passed;
    if (scenario == "allocation"sv) {
        passed = allocation_checks();
    } else if (scenario == "failure"sv) {
        passed = failure_checks();
    } else if (scenario == "concurrency"sv) {
        passed = concurrency_checks();
    } else {
        return 2;
    }
    std::printf("Desktop ERA heap experiment %s: %s\n", argv[1], passed ? "PASS" : "FAIL");
    return passed ? 0 : 1;
}
