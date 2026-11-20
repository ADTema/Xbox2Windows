#include "era_heap.h"

#include <algorithm>
#include <array>
#include <atomic>
#include <barrier>
#include <cstdio>
#include <limits>
#include <memory>
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

bool caller_layout_checks()
{
    using Byte = unsigned char;
    using Block = std::unique_ptr<void, decltype(&era_heap::release)>;
    constexpr Byte guard = 0xec, marker = 0x51, tag = 0x34;
    // Supply owned storage with a known origin for each possible base address residue.
    for (std::size_t length : {1u, 31u, 32u, 33u, 255u, 256u, 257u, 4097u}) {
        const auto total = length + 64 + 96;
        Block block(era_heap::allocate(total, 5ull << 24), era_heap::release);
        if (!block) return false;
        auto* storage = static_cast<Byte*>(block.get());
        for (unsigned residue = 0; residue < 32; ++residue) {
            std::fill_n(storage, total, guard);
            auto* base = storage + 32 + residue;
            const auto address = reinterpret_cast<std::uintptr_t>(base);
            const auto offset = static_cast<Byte>(64 - (address & 31));
            auto* user = base + offset;
            if ((address & 31) != residue || reinterpret_cast<std::uintptr_t>(user) % 32 ||
                offset < 33 || user + length > base + length + 64) return false;
            user[-2] = tag;
            user[-1] = offset;
            std::fill_n(user, length, marker);
            if (user - user[-1] != base || user[-2] != tag ||
                !std::all_of(storage, user - 2, [](Byte b) { return b == guard; }) ||
                !std::all_of(user + length, storage + total, [](Byte b) { return b == guard; }))
                return false;
        }
    }
    // AMD rounds the size. This experiment imposes no 256-byte pointer alignment.
    struct SizeCase { std::size_t requested, allocated; };
    constexpr SizeCase sizes[]{{1,256}, {255,256}, {256,256}, {257,512}, {511,512},
                               {512,512}, {513,768}, {4095,4096}, {4096,4096}, {4097,4352}};
    for (const auto& size : sizes) {
        const auto rounded = (size.requested + 255) & ~std::size_t{255};
        if (rounded != size.allocated) return false;
        Block block(era_heap::allocate(rounded, 0), era_heap::release);
        if (!block) return false;
        auto* data = static_cast<Byte*>(block.get());
        std::fill_n(data, size.requested, marker);
        if (!std::all_of(data, data + size.requested, [](Byte b) { return b == marker; }) ||
            !std::all_of(data + size.requested, data + rounded, [](Byte b) { return b == 0; })) return false;
    }
    std::puts("bink_base_layouts=256 amd_size_boundaries=10");
    return true;
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
    } else if (scenario == "caller_layout"sv) {
        passed = caller_layout_checks();
    } else if (scenario == "concurrency"sv) {
        passed = concurrency_checks();
    } else {
        return 2;
    }
    std::printf("Desktop ERA heap experiment %s: %s\n", argv[1], passed ? "PASS" : "FAIL");
    return passed ? 0 : 1;
}
