// Four title allocations (three era_heap graphics allocations and one placed across a 4 GiB line)
// opened as D3D12 heaps (era_gpu_alias), packed for the shader
// lookup (era_title_va::shader_ranges), and read by a compute shader through 64-bit title
// addresses taken from an input buffer (src/title_va_lookup.hlsli). Expected values come from
// the CPU through the title pointers.
#include "bvh_fixture.h"
#include "era_gpu_alias.h"
#include "era_heap.h"
#include "era_title_va.h"
#include "LookupTitleAddresses.h"

#include <array>
#include <cstdint>
#include <cstdio>
#include <memory>
#include <stdexcept>
#include <vector>

using namespace bvh_fixture;

namespace {
// XALLOC_ATTRIBUTES: memoryType 1 (graphics), pageSize 1 (64 KB), alignment 16 (64 KB).
constexpr std::uint64_t graphics_64k = (1ull << 29) | (1ull << 14) | (16ull << 24);
constexpr std::array<std::size_t, 3> sizes{256 * 1024, 64 * 1024, 128 * 1024};
constexpr UINT descriptor_count = 8;  // matches Aliases[8] in tests/gpu_alias_lookup.hlsl
constexpr Word miss = 0xdeadbeef;

constexpr std::size_t straddle_bytes = 128 * 1024;

struct TitleAllocation {
    explicit TitleAllocation(std::size_t bytes) : base(era_heap::allocate(bytes, graphics_64k)), size(bytes) {}
    // An allocation placed across a 4 GiB line, so the lookup has to compare and subtract the
    // high 32-bit words correctly. Tries lines from 8 GiB up; base stays null if none is free.
    TitleAllocation() : base(nullptr), size(straddle_bytes), placed(true)
    {
        for (std::uint64_t line = 2; line < 128 && !base; ++line)
            base = VirtualAlloc(reinterpret_cast<void*>((line << 32) - straddle_bytes / 2), straddle_bytes,
                                MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE);
    }
    ~TitleAllocation()
    {
        if (placed) {
            if (base) VirtualFree(base, 0, MEM_RELEASE);
        } else {
            era_heap::release_with_attributes(base, graphics_64k);
        }
    }
    TitleAllocation(const TitleAllocation&) = delete;
    TitleAllocation& operator=(const TitleAllocation&) = delete;
    void* base;
    std::size_t size;
    bool placed = false;
};

Word pattern(std::size_t allocation, std::size_t offset)
{
    return static_cast<Word>((allocation + 1) * 0x01000193u ^ (offset * 2654435761u));
}
}

bool check_gpu_alias_lookup(ID3D12Device* device)
{
    std::vector<std::unique_ptr<TitleAllocation>> titles;
    for (const auto bytes : sizes) titles.push_back(std::make_unique<TitleAllocation>(bytes));
    titles.push_back(std::make_unique<TitleAllocation>());
    std::vector<era_gpu_alias::Alias> aliases(titles.size());
    era_title_va::Table table;
    for (std::size_t a = 0; a < titles.size(); ++a) {
        auto* base = static_cast<unsigned char*>(titles[a]->base);
        if (!base) throw std::runtime_error("title allocation failed");
        const HRESULT hr = era_gpu_alias::open(device, base, titles[a]->size, aliases[a]);
        if (hr == E_NOTIMPL) {
            std::puts("existing heaps are not supported by this adapter");
            return false;
        }
        check(hr, "Open a title allocation as a D3D12 heap");
        if (!table.add(reinterpret_cast<std::uint64_t>(base), titles[a]->size,
                       aliases[a].buffer->GetGPUVirtualAddress()))
            throw std::runtime_error("table rejected an alias");
        for (std::size_t offset = 0; offset < titles[a]->size; offset += sizeof(Word))
            *reinterpret_cast<Word*>(base + offset) = pattern(a, offset);
    }

    const auto ranges = table.ranges();
    std::vector<era_title_va::ShaderRange> packed;
    if (!era_title_va::shader_ranges(ranges, packed)) throw std::runtime_error("shader_ranges rejected the table");
    // Slot i of the descriptor table holds the alias of ranges[i].
    std::vector<std::size_t> slot_allocation(ranges.size());
    for (std::size_t slot = 0; slot < ranges.size(); ++slot)
        for (std::size_t a = 0; a < titles.size(); ++a)
            if (reinterpret_cast<std::uint64_t>(titles[a]->base) == ranges[slot].title_begin) slot_allocation[slot] = a;

    // Records: start, second word, middle words, last word and the words just outside each
    // allocation (outside words count as hits only if another allocation happens to be there),
    // plus the null page and an address with a high 32-bit word above any user address.
    std::vector<std::uint64_t> records;
    for (const auto& title : titles) {
        const auto begin = reinterpret_cast<std::uint64_t>(title->base);
        for (std::uint64_t offset : {std::uint64_t{0}, std::uint64_t{4}, title->size / 2, title->size / 2 + 0x124,
                                     title->size - 4})
            records.push_back(begin + offset);
        records.push_back(begin - 4);
        records.push_back(begin + title->size);
        for (std::uint64_t offset = 0; offset < title->size; offset += 0x1f04) records.push_back(begin + offset);
    }
    // Around the 4 GiB line inside the placed allocation, and the same low words one 4 GiB
    // above and below, which only a full 64-bit comparison rejects.
    const auto line = reinterpret_cast<std::uint64_t>(titles.back()->base) + straddle_bytes / 2;
    if ((line & 0xffffffffull) != 0) throw std::runtime_error("placed allocation does not straddle a 4 GiB line");
    for (std::uint64_t address : {line - 8, line - 4, line, line + 4, line + 0x1234}) {
        records.push_back(address);
        records.push_back(address + (1ull << 32));
        records.push_back(address - (1ull << 32));
    }
    records.push_back(0x10);
    records.push_back(0xfffffffffffffff0ull);
    const auto record_count = static_cast<Word>(records.size());

    // Expected results from the CPU through the title pointers.
    std::vector<Word> expected(records.size() * 2);
    Word hits = 0, misses = 0;
    for (std::size_t r = 0; r < records.size(); ++r) {
        expected[r * 2] = miss;
        expected[r * 2 + 1] = 0;
        if (!table.translate(records[r], sizeof(Word))) {
            ++misses;
            continue;
        }
        for (std::size_t slot = 0; slot < ranges.size(); ++slot) {
            if (records[r] >= ranges[slot].title_begin && records[r] < ranges[slot].title_end) {
                expected[r * 2] = *reinterpret_cast<const Word*>(records[r]);
                expected[r * 2 + 1] = static_cast<Word>(slot + 1);
            }
        }
        ++hits;
    }
    if (misses < 12) throw std::runtime_error("fixture needs the twelve guaranteed misses");

    ComPtr<ID3D12DescriptorHeap> heap;
    D3D12_DESCRIPTOR_HEAP_DESC heap_desc{D3D12_DESCRIPTOR_HEAP_TYPE_CBV_SRV_UAV, descriptor_count,
                                         D3D12_DESCRIPTOR_HEAP_FLAG_SHADER_VISIBLE, 0};
    check(device->CreateDescriptorHeap(&heap_desc, IID_PPV_ARGS(&heap)), "Create lookup descriptor heap");
    const UINT stride = device->GetDescriptorHandleIncrementSize(D3D12_DESCRIPTOR_HEAP_TYPE_CBV_SRV_UAV);
    for (UINT slot = 0; slot < descriptor_count; ++slot) {
        D3D12_UNORDERED_ACCESS_VIEW_DESC view{};
        view.Format = DXGI_FORMAT_R32_TYPELESS;
        view.ViewDimension = D3D12_UAV_DIMENSION_BUFFER;
        view.Buffer.Flags = D3D12_BUFFER_UAV_FLAG_RAW;
        ID3D12Resource* resource = nullptr;
        if (slot < ranges.size()) {
            const auto a = slot_allocation[slot];
            resource = aliases[a].buffer.Get();
            view.Buffer.NumElements = static_cast<UINT>(titles[a]->size / sizeof(Word));
        }
        D3D12_CPU_DESCRIPTOR_HANDLE cpu = heap->GetCPUDescriptorHandleForHeapStart();
        cpu.ptr += static_cast<SIZE_T>(slot) * stride;
        device->CreateUnorderedAccessView(resource, nullptr, &view, cpu);
    }

    Kernel kernel(device, {LookupTitleAddresses, sizeof(LookupTitleAddresses)});
    auto range_buffer = upload(device, packed);
    auto record_buffer = upload(device, records);
    const std::size_t result_bytes = expected.size() * sizeof(Word);
    auto results = make_buffer(device, result_bytes, D3D12_HEAP_TYPE_DEFAULT, D3D12_RESOURCE_STATE_COMMON,
                               D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS);
    auto back = make_buffer(device, result_bytes, D3D12_HEAP_TYPE_READBACK, D3D12_RESOURCE_STATE_COPY_DEST);
    ComputeCommands cmd(device, kernel.pipeline.Get());
    auto* list = cmd.list.Get();
    for (auto& alias : aliases)
        transition(list, alias.buffer.Get(), D3D12_RESOURCE_STATE_COMMON, D3D12_RESOURCE_STATE_UNORDERED_ACCESS);
    transition(list, results.Get(), D3D12_RESOURCE_STATE_COMMON, D3D12_RESOURCE_STATE_UNORDERED_ACCESS);
    ID3D12DescriptorHeap* heaps[] = {heap.Get()};
    list->SetDescriptorHeaps(1, heaps);
    list->SetComputeRootSignature(kernel.root.Get());
    list->SetComputeRootDescriptorTable(0, heap->GetGPUDescriptorHandleForHeapStart());
    list->SetComputeRootShaderResourceView(1, range_buffer->GetGPUVirtualAddress());
    list->SetComputeRootShaderResourceView(2, record_buffer->GetGPUVirtualAddress());
    list->SetComputeRootUnorderedAccessView(3, results->GetGPUVirtualAddress());
    list->SetComputeRoot32BitConstant(4, static_cast<UINT>(packed.size()), 0);
    list->SetComputeRoot32BitConstant(4, record_count, 1);
    list->Dispatch((record_count + 63) / 64, 1, 1);
    for (auto& alias : aliases)
        transition(list, alias.buffer.Get(), D3D12_RESOURCE_STATE_UNORDERED_ACCESS, D3D12_RESOURCE_STATE_COMMON);
    transition(list, results.Get(), D3D12_RESOURCE_STATE_UNORDERED_ACCESS, D3D12_RESOURCE_STATE_COPY_SOURCE);
    list->CopyBufferRegion(back.Get(), 0, results.Get(), 0, result_bytes);
    cmd.submit_and_wait(device);

    const auto actual = read(back.Get(), expected.size());
    for (std::size_t r = 0; r < records.size(); ++r) {
        equal(actual[r * 2], expected[r * 2], static_cast<unsigned>(r), 0);
        equal(actual[r * 2 + 1], expected[r * 2 + 1], static_cast<unsigned>(r), 1);
    }
    std::printf("gpu_alias_lookup ranges=%zu records=%u hits=%u misses=%u mismatches=0\n", packed.size(),
                record_count, hits, misses);
    return true;
}
