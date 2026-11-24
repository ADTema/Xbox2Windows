// Source-built check of the AcpHal stand-in APU heap (src/startup_stubs/acphal.cpp): ApuFree returns blocks,
// neighbours coalesce, bad requests leave the heap alone and concurrent callers never get overlapping blocks.
// Usage: startup_acphal_apu_free <AcpHal.dll>
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <windows.h>

#include <atomic>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <iterator>
#include <map>
#include <mutex>
#include <thread>
#include <vector>

namespace {
using u64 = std::uint64_t;
using AllocFn = long(__cdecl*)(void**, std::uint32_t*, u64, u64, u64);
using FreeFn = long(__cdecl*)(void*);
using CreateFn = long(__cdecl*)(u64, u64);
using MapFn = std::uint32_t(__cdecl*)(void*);

constexpr long ok = 0, invalid = static_cast<long>(0x80070057), no_memory = static_cast<long>(0x8007000E),
               no_pointer = static_cast<long>(0x80004003);
constexpr u64 heap_size = 0x200000, first_offset = 0x10000, usable = heap_size - first_offset;

AllocFn alloc_fn;
FreeFn free_fn;
MapFn map_fn;
int failures;

void check(bool condition, const char* what)
{
    if (condition) return;
    std::printf("FAIL: %s\n", what);
    ++failures;
}

long take(void** out, u64 size, u64 alignment = 16, std::uint32_t* apu = nullptr) { return alloc_fn(out, apu, size, alignment, 0); }

void* take_ok(u64 size, u64 alignment = 16)
{
    void* p = nullptr;
    const long hr = take(&p, size, alignment);
    check(hr == ok && p, "allocation succeeds");
    return p;
}

// The whole heap is free again exactly when one block of the full usable size fits at the first offset.
void check_empty(const char* where)
{
    std::uint32_t apu = 0;
    void* p = nullptr;
    const long hr = take(&p, usable, 16, &apu);
    if (hr != ok || !p || apu != first_offset) {
        std::printf("FAIL: heap not whole after %s (hr=0x%08lx apu=0x%x)\n", where, static_cast<unsigned long>(hr), apu);
        ++failures;
        return;
    }
    check(free_fn(p) == ok, "whole-heap block frees");
}

void churn_beyond_capacity()
{
    void* a = take_ok(0x100000, 4096);
    void* b = nullptr;
    check(take(&b, 0x100000, 4096) == no_memory && !b, "two 1 MiB blocks do not fit while the first is live");
    check(free_fn(a) == ok, "free first");
    for (int round = 0; round < 64; ++round) {  // 64 MiB handed out in total, over 30 times the heap
        void* p = take_ok(0x100000, 4096);
        check(p == a, "same block comes back");
        if (!p) return;
        check(free_fn(p) == ok, "churn free");
    }
    check_empty("churn");
}

void reuse_and_alignment()
{
    for (u64 alignment : {16u, 256u, 4096u, 65536u}) {
        void* keep = take_ok(0x30, 16);
        void* a = take_ok(0x2000, alignment);
        void* after = take_ok(0x30, 16);
        check(reinterpret_cast<std::uintptr_t>(a) % alignment == 0, "alignment honoured");
        std::memset(a, 0xAA, 0x2000);
        check(free_fn(a) == ok, "free");
        void* again = take_ok(0x2000, alignment);
        check(again == a, "same size returns the freed block");
        bool zero = true;
        for (int i = 0; i < 0x2000; ++i) zero = zero && static_cast<unsigned char*>(again)[i] == 0;
        check(zero, "reused block is zeroed like fresh heap memory");
        check(free_fn(again) == ok, "free again");
        void* smaller = take_ok(0x1000, alignment);
        check(smaller >= a && static_cast<unsigned char*>(smaller) + 0x1000 <= static_cast<unsigned char*>(a) + 0x2000,
              "smaller request lands inside the freed block");
        std::uint32_t apu = 0;
        void* mapped = nullptr;
        check(take(&mapped, 0x40, 64, &apu) == ok && map_fn(mapped) == apu && apu, "APU address maps back to the block");
        for (void* p : {keep, after, smaller, mapped}) check(free_fn(p) == ok, "cleanup free");
        check_empty("reuse");
    }
}

void coalescing()
{
    constexpr u64 part = 0x10000;
    void* a = take_ok(part);
    void* b = take_ok(part);
    void* c = take_ok(part);
    void* rest = take_ok(usable - 3 * part);  // fills the heap: only A, B, C can ever be free
    auto* base = static_cast<unsigned char*>(a);
    check(b == base + part && c == base + 2 * part, "A, B and C are contiguous");
    check(free_fn(a) == ok && free_fn(c) == ok, "free A and C");
    void* big = nullptr;
    check(take(&big, 3 * part) == no_memory && !big, "A+B+C does not fit while B is live");
    check(free_fn(b) == ok, "free B");
    big = take_ok(3 * part);
    check(big == a, "A+B+C is one block at A");
    check(free_fn(big) == ok && free_fn(rest) == ok, "cleanup");
    check_empty("coalescing");
    void* x = take_ok(part);  // reverse order, middle first
    void* y = take_ok(part);
    void* z = take_ok(part);
    check(free_fn(y) == ok && free_fn(z) == ok && free_fn(x) == ok, "free middle, last, first");
    check_empty("coalescing reverse");
}

void bad_requests()
{
    const void* const sentinel = reinterpret_cast<void*>(0x1234);
    void* out = const_cast<void*>(sentinel);
    std::uint32_t apu = 0xDEADBEEF;
    check(free_fn(nullptr) == ok, "free(null) is a no-op");
    check(take(nullptr, 64) == no_pointer, "null output");
    check(take(&out, usable + 16, 16, &apu) == no_memory && !out && apu == 0xDEADBEEF, "larger than the heap");
    out = const_cast<void*>(sentinel);
    check(take(&out, 0xFFFFFFFFull, 16, &apu) == no_memory && !out, "size near 2^32");
    check(take(&out, ~u64{0}, 16, &apu) == no_memory && !out, "size 2^64-1 is cut to 32 bits");
    check(take(&out, 0, 16, &apu) == invalid && !out && apu == 0xDEADBEEF, "size 0");
    check(take(&out, 0x100000000ull, 16, &apu) == invalid && !out, "size 2^32 is size 0");
    check(take(&out, 64, 24, &apu) == invalid && !out && apu == 0xDEADBEEF, "alignment 24");
    check(take(&out, 64, 0xFFFFFFFFull, &apu) == invalid && !out, "alignment 2^32-1");
    void* probe = take_ok(16);
    const auto probe_addr = reinterpret_cast<std::uintptr_t>(probe);
    check(free_fn(probe) == ok, "free probe");
    const std::uint64_t big_align = 0x80000000ull;
    const std::uintptr_t aligned_addr = (probe_addr + big_align - 1) & ~(big_align - 1);
    const bool big_align_fits = aligned_addr >= probe_addr && (aligned_addr - probe_addr) + 64 <= usable;
    out = const_cast<void*>(sentinel);
    const long big_hr = take(&out, 64, big_align, &apu);
    if (big_align_fits) {
        check(big_hr == ok && out && reinterpret_cast<std::uintptr_t>(out) == aligned_addr,
              "alignment 2 GiB succeeds when heap straddles boundary");
        check(free_fn(out) == ok, "free 2 GiB aligned block");
    } else {
        check(big_hr == no_memory && !out && apu == 0xDEADBEEF, "alignment 2 GiB cannot be met");
    }
    check_empty("refused requests");

    void* p = take_ok(0x40, 0);  // 0 means the default of 16
    check(reinterpret_cast<std::uintptr_t>(p) % 16 == 0, "alignment 0");
    void* q = take_ok(0x40, 4);
    check(reinterpret_cast<std::uintptr_t>(q) % 16 == 0, "alignment 4 is raised to 16");
    check(free_fn(static_cast<unsigned char*>(p) + 8) == invalid, "free inside a live block");
    check(free_fn(&failures) == invalid, "free of a foreign address");
    check(free_fn(reinterpret_cast<void*>(0x10)) == invalid, "free of a tiny address");
    check(free_fn(p) == ok, "free");
    check(free_fn(p) == invalid, "double free");
    void* big = nullptr;
    check(take(&big, usable) == no_memory, "q is still live after the refused frees");
    check(free_fn(q) == ok && free_fn(q) == invalid, "free q, then a double free");
    check_empty("refused frees");
}

void table_full()
{
    std::vector<void*> blocks;
    void* p = nullptr;
    while (blocks.size() < 5000 && take(&p, 256) == ok) blocks.push_back(p);
    check(blocks.size() < 5000 && blocks.size() * 256 < usable, "extent table limit refuses before the heap is full");
    check(!blocks.empty() && take(&p, 256) == no_memory && !p, "refusal is E_OUTOFMEMORY and repeatable");
    for (size_t i = 0; i < blocks.size(); i += 2) check(free_fn(blocks[i]) == ok, "free every other block");
    for (size_t i = 1; i < blocks.size(); i += 2) check(free_fn(blocks[i]) == ok, "free the rest");
    check_empty("table full");
}

// Deterministic generator, so a failure is reproducible.
struct Rng {
    std::uint32_t state;
    std::uint32_t next() { return state = state * 1664525u + 1013904223u; }
};

struct Live {
    std::map<std::uintptr_t, std::uintptr_t> blocks;  // start -> end, shared by all threads
    std::mutex lock;
    bool add(std::uintptr_t start, std::uintptr_t end)
    {
        std::lock_guard<std::mutex> guard(lock);
        auto next = blocks.lower_bound(start);
        if (next != blocks.end() && next->first < end) return false;
        if (next != blocks.begin() && std::prev(next)->second > start) return false;
        blocks[start] = end;
        return true;
    }
    void remove(std::uintptr_t start)
    {
        std::lock_guard<std::mutex> guard(lock);
        blocks.erase(start);
    }
};

void worker(unsigned id, unsigned rounds, std::atomic<int>* ready, std::atomic<int>* errors, Live* live)
{
    struct Mine {
        unsigned char* p;
        u64 size;
        unsigned char tag;
    };
    std::vector<Mine> mine;
    Rng rng{0xC0FFEEu + id * 7919u};
    ready->fetch_add(1);
    while (ready->load() < 4) {}
    auto release = [&](std::size_t index) {
        const Mine m = mine[index];
        for (u64 i = 0; i < m.size; ++i)
            if (m.p[i] != m.tag) { errors->fetch_add(1); break; }
        live->remove(reinterpret_cast<std::uintptr_t>(m.p));
        if (free_fn(m.p) != ok) errors->fetch_add(1);
        mine.erase(mine.begin() + static_cast<std::ptrdiff_t>(index));
    };
    for (unsigned round = 0; round < rounds; ++round) {
        if (mine.size() >= 12 || (!mine.empty() && rng.next() % 3 == 0)) release(rng.next() % mine.size());
        const u64 size = 16 + (rng.next() % 256) * 16;
        const u64 alignment = u64{16} << (rng.next() % 5);
        void* p = nullptr;
        if (take(&p, size, alignment) != ok || !p || reinterpret_cast<std::uintptr_t>(p) % alignment) {
            errors->fetch_add(1);
            continue;
        }
        const auto start = reinterpret_cast<std::uintptr_t>(p);
        if (!live->add(start, start + size)) errors->fetch_add(1);
        const unsigned char tag = static_cast<unsigned char>(id * 64 + round % 61 + 1);
        std::memset(p, tag, size);
        mine.push_back({static_cast<unsigned char*>(p), size, tag});
    }
    while (!mine.empty()) release(mine.size() - 1);
}

void concurrent()
{
    Live live;
    std::atomic<int> ready{0}, errors{0};
    std::vector<std::thread> threads;
    for (unsigned id = 0; id < 4; ++id) threads.emplace_back(worker, id, 1000u, &ready, &errors, &live);
    for (auto& t : threads) t.join();
    check(errors.load() == 0, "no overlap, torn pattern or unexpected error across 4 threads x 1000 rounds");
    check(live.blocks.empty(), "every block was released");
    check_empty("concurrent run");
}
}  // namespace

int main(int argc, char** argv)
{
    if (argc != 2) return std::printf("usage: startup_acphal_apu_free <AcpHal.dll>\n"), 2;
    SetEnvironmentVariableA("X2W_AUDIO_PERMISSIVE", "1");
    HMODULE module = LoadLibraryA(argv[1]);
    if (!module) return std::printf("FAIL: cannot load %s\n", argv[1]), 2;
    alloc_fn = reinterpret_cast<AllocFn>(GetProcAddress(module, "ApuAlloc"));
    free_fn = reinterpret_cast<FreeFn>(GetProcAddress(module, "ApuFree"));
    map_fn = reinterpret_cast<MapFn>(GetProcAddress(module, "ApuMapVirtualAddress"));
    auto create = reinterpret_cast<CreateFn>(GetProcAddress(module, "ApuCreateHeap"));
    if (!alloc_fn || !free_fn || !map_fn || !create) return std::printf("FAIL: missing export\n"), 2;
    void* none = nullptr;
    check(take(&none, 64) == no_memory && !none, "no heap yet");
    check(create(heap_size, 0) == ok, "ApuCreateHeap");
    churn_beyond_capacity();
    reuse_and_alignment();
    coalescing();
    bad_requests();
    table_full();
    concurrent();
    std::printf(failures ? "startup_acphal_apu_free: %d failure(s)\n" : "startup_acphal_apu_free: ok\n", failures);
    return failures ? 1 : 0;
}
