#include <windows.h>
#include <d3d12.h>
#include <wrl/client.h>

#include <cstdint>
#include <cstdio>
#include <string_view>

#include "xmem_test_device.h"

using Microsoft::WRL::ComPtr;
using namespace std::literals;

namespace {
constexpr UINT64 tile_bytes = D3D12_TILED_RESOURCE_TILE_SIZE_IN_BYTES;
constexpr UINT words = static_cast<UINT>(tile_bytes / sizeof(std::uint32_t));

bool check(HRESULT result, const char* stage)
{
    if (SUCCEEDED(result)) return true;
    std::fprintf(stderr, "%s failed: 0x%08lx\n", stage, static_cast<unsigned long>(result));
    return false;
}

D3D12_RESOURCE_DESC buffer_desc()
{
    D3D12_RESOURCE_DESC desc{};
    desc.Dimension = D3D12_RESOURCE_DIMENSION_BUFFER;
    desc.Width = 2 * tile_bytes;
    desc.Height = 1;
    desc.DepthOrArraySize = 1;
    desc.MipLevels = 1;
    desc.SampleDesc.Count = 1;
    desc.Layout = D3D12_TEXTURE_LAYOUT_ROW_MAJOR;
    return desc;
}

std::uint32_t pattern(UINT tile, UINT word)
{
    return (tile ? 0x7a81fc39u : 0x42b167d3u) ^ (word * 0x9e3779b1u);
}

struct Queue {
    ComPtr<ID3D12CommandQueue> commands;
    ComPtr<ID3D12CommandAllocator> allocator;
    ComPtr<ID3D12Fence> fence;

    bool init(ID3D12Device* device, D3D12_COMMAND_LIST_TYPE type)
    {
        D3D12_COMMAND_QUEUE_DESC desc{};
        desc.Type = type;
        return check(device->CreateCommandQueue(&desc, IID_PPV_ARGS(&commands)), "CreateCommandQueue") &&
               check(device->CreateCommandAllocator(type, IID_PPV_ARGS(&allocator)), "CreateCommandAllocator") &&
               check(device->CreateFence(0, D3D12_FENCE_FLAG_NONE, IID_PPV_ARGS(&fence)), "CreateFence");
    }

    void execute(ID3D12GraphicsCommandList* list)
    {
        ID3D12CommandList* lists[]{list};
        commands->ExecuteCommandLists(1, lists);
    }
};

bool record_copy(ID3D12Device* device, const Queue& queue, ID3D12Resource* dst, UINT64 dst_offset,
                 ID3D12Resource* src, UINT64 size, ComPtr<ID3D12GraphicsCommandList>& list)
{
    if (!check(device->CreateCommandList(0, queue.commands->GetDesc().Type, queue.allocator.Get(), nullptr,
                                         IID_PPV_ARGS(&list)), "CreateCommandList")) {
        return false;
    }
    // Buffers decay to COMMON between ExecuteCommandLists calls. Both engines
    // may promote this reserved buffer to their own copy state.
    list->CopyBufferRegion(dst, dst_offset, src, 0, size);
    return check(list->Close(), "Close command list");
}

bool wait_for_read(ID3D12Fence* fence, UINT64 value)
{
    HANDLE event = CreateEventW(nullptr, FALSE, FALSE, nullptr);
    if (!event) return false;
    const bool done = check(fence->SetEventOnCompletion(value, event), "SetEventOnCompletion") &&
                      WaitForSingleObject(event, 10000) == WAIT_OBJECT_0;
    CloseHandle(event);
    return done;
}

int run(bool warp)
{
    bool unmatched = false;
    const auto device = create_device(warp, unmatched);
    if (unmatched) return 1;
    if (!device) return 77;
    D3D12_FEATURE_DATA_D3D12_OPTIONS options{};
    if (!check(device->CheckFeatureSupport(D3D12_FEATURE_D3D12_OPTIONS, &options, sizeof(options)),
               "Check tiled resource support")) return 1;
    if (options.TiledResourcesTier == D3D12_TILED_RESOURCES_TIER_NOT_SUPPORTED) {
        std::puts("Tiled resources are unavailable");
        return 77;
    }

    Queue copy, direct;
    ComPtr<ID3D12Resource> window, upload, readback;
    ComPtr<ID3D12Heap> pool;
    const auto desc = buffer_desc();
    D3D12_HEAP_PROPERTIES upload_heap{}, readback_heap{};
    upload_heap.Type = D3D12_HEAP_TYPE_UPLOAD;
    readback_heap.Type = D3D12_HEAP_TYPE_READBACK;
    upload_heap.CreationNodeMask = upload_heap.VisibleNodeMask = 1;
    readback_heap.CreationNodeMask = readback_heap.VisibleNodeMask = 1;
    D3D12_HEAP_DESC pool_desc{};
    pool_desc.SizeInBytes = 2 * tile_bytes;
    pool_desc.Properties = upload_heap;
    pool_desc.Properties.Type = D3D12_HEAP_TYPE_DEFAULT;
    pool_desc.Flags = D3D12_HEAP_FLAG_ALLOW_ONLY_BUFFERS;
    if (!copy.init(device.Get(), D3D12_COMMAND_LIST_TYPE_COPY) ||
        !direct.init(device.Get(), D3D12_COMMAND_LIST_TYPE_DIRECT) ||
        !check(device->CreateReservedResource(&desc, D3D12_RESOURCE_STATE_COMMON, nullptr,
                                               IID_PPV_ARGS(&window)), "CreateReservedResource") ||
        !check(device->CreateHeap(&pool_desc, IID_PPV_ARGS(&pool)), "CreateHeap") ||
        !check(device->CreateCommittedResource(&upload_heap, D3D12_HEAP_FLAG_NONE, &desc,
                                               D3D12_RESOURCE_STATE_GENERIC_READ, nullptr,
                                               IID_PPV_ARGS(&upload)), "Create upload buffer") ||
        !check(device->CreateCommittedResource(&readback_heap, D3D12_HEAP_FLAG_NONE, &desc,
                                               D3D12_RESOURCE_STATE_COPY_DEST, nullptr,
                                               IID_PPV_ARGS(&readback)), "Create readback buffer")) return 1;

    const D3D12_RANGE no_read{0, 0};
    void* mapped = nullptr;
    if (!check(upload->Map(0, &no_read, &mapped), "Map upload buffer")) return 1;
    auto* data = static_cast<std::uint32_t*>(mapped);
    for (UINT tile = 0; tile < 2; ++tile) {
        for (UINT word = 0; word < words; ++word) data[tile * words + word] = pattern(tile, word);
    }
    upload->Unmap(0, nullptr);

    ComPtr<ID3D12GraphicsCommandList> write, read_before, read_after;
    if (!record_copy(device.Get(), copy, window.Get(), 0, upload.Get(), 2 * tile_bytes, write) ||
        !record_copy(device.Get(), direct, readback.Get(), 0, window.Get(), tile_bytes, read_before) ||
        !record_copy(device.Get(), direct, readback.Get(), tile_bytes, window.Get(), tile_bytes, read_after)) return 1;

    const D3D12_TILED_RESOURCE_COORDINATE start{};
    const D3D12_TILE_REGION_SIZE full{2, FALSE, 0, 0, 0};
    const UINT initial_heap_offset = 0;
    copy.commands->UpdateTileMappings(window.Get(), 1, &start, &full, pool.Get(), 1, nullptr,
                                      &initial_heap_offset, nullptr, D3D12_TILE_MAPPING_FLAG_NONE);
    copy.execute(write.Get());
    if (!check(copy.commands->Signal(copy.fence.Get(), 1), "Signal initial upload") ||
        !check(direct.commands->Wait(copy.fence.Get(), 1), "Wait on DIRECT for initial upload")) return 1;
    direct.execute(read_before.Get());
    // The early reader must see tile 0. Ordering it before the remap makes this
    // a negative control without an unsynchronized read or a timing assumption.
    if (!check(direct.commands->Signal(direct.fence.Get(), 1), "Signal early read") ||
        !check(copy.commands->Wait(direct.fence.Get(), 1), "Wait on COPY for early read")) return 1;

    // Move the initialized physical tile 1 within the same reserved buffer.
    // The second range removes its old mapping, so there is no concurrent alias.
    const D3D12_TILE_RANGE_FLAGS ranges[]{D3D12_TILE_RANGE_FLAG_NONE, D3D12_TILE_RANGE_FLAG_NULL};
    const UINT offsets[]{1, 0}, counts[]{1, 1};
    copy.commands->UpdateTileMappings(window.Get(), 1, &start, &full, pool.Get(), 2, ranges, offsets, counts,
                                      D3D12_TILE_MAPPING_FLAG_NONE);
    if (!check(copy.commands->Signal(copy.fence.Get(), 2), "Signal remap") ||
        !check(direct.commands->Wait(copy.fence.Get(), 2), "Wait on DIRECT for remap")) return 1;
    direct.execute(read_after.Get());
    if (!check(direct.commands->Signal(direct.fence.Get(), 2), "Signal final read") ||
        !wait_for_read(direct.fence.Get(), 2)) {
        std::fputs("DIRECT did not complete the ordered read\n", stderr);
        return 1;
    }

    const D3D12_RANGE read_range{0, 2 * tile_bytes};
    if (!check(readback->Map(0, &read_range, &mapped), "Map readback buffer")) return 1;
    const auto* samples = static_cast<const std::uint32_t*>(mapped);
    UINT bad_before = 0, bad_after = 0, missed_new_before_remap = 0;
    for (UINT word = 0; word < words; ++word) {
        bad_before += samples[word] != pattern(0, word);
        bad_after += samples[words + word] != pattern(1, word);
        missed_new_before_remap += samples[word] != pattern(1, word);
    }
    readback->Unmap(0, &no_read);
    std::printf("copy queue early mismatches=%u ordered mismatches=%u early vs remapped=%u/%u\n",
                bad_before, bad_after, missed_new_before_remap, words);
    return bad_before == 0 && bad_after == 0 && missed_new_before_remap == words &&
           check(device->GetDeviceRemovedReason(), "Device removal status") ? 0 : 1;
}
} // namespace

int main(int argc, char** argv)
{
    if (argc != 2) return 1;
    const std::string_view mode(argv[1]);
    if (mode != "warp"sv && mode != "hardware"sv) return 1;
    return run(mode == "warp"sv);
}
