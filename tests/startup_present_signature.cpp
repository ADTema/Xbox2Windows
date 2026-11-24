// Verifies the presented-picture signature (src/startup_stubs/present_signature_sampler.h) on WARP:
// the sampler copies only the sampled rows of a presented surface, publishes a grid equal to the CPU
// reduction of those rows, and the published signal changes once for two different pictures and
// never for repeated identical pictures (negative control). Also checks the sampling interval.
//
// usage: startup_present_signature   (exit 77 when no WARP adapter can be created)
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>

#include "startup_stubs/input_script.h"
#include "startup_stubs/present_signature_sampler.h"

#include <d3d12.h>
#include <dxgi1_4.h>

#include <cstdint>
#include <cstdio>
#include <cstring>
#include <vector>

namespace {

int failures = 0;
void check(bool ok, const char* what)
{
    if (!ok) {
        ++failures;
        std::printf("FAIL: %s\n", what);
    }
}

constexpr UINT width = 200, height = 120;

// Picture contents, 4 bytes a texel in the surface's byte order.
using Picture = std::vector<unsigned char>;
Picture gradient(bool inverted)
{
    Picture p(std::size_t{width} * height * 4);
    for (UINT y = 0; y < height; ++y)
        for (UINT x = 0; x < width; ++x) {
            unsigned char* t = &p[(std::size_t{y} * width + x) * 4];
            const auto v = static_cast<unsigned char>((x * 255) / (width - 1));
            t[0] = inverted ? 255 - v : v;
            t[1] = static_cast<unsigned char>((y * 255) / (height - 1));
            t[2] = inverted ? v : static_cast<unsigned char>(255 - v);
            t[3] = 255;
        }
    return p;
}

struct Gpu {
    ID3D12Device* device = nullptr;
    ID3D12CommandQueue* queue = nullptr;
    ID3D12Fence* fence = nullptr;
    UINT64 value = 0;
    HANDLE event = CreateEventW(nullptr, FALSE, FALSE, nullptr);

    void idle()
    {
        queue->Signal(fence, ++value);
        if (fence->GetCompletedValue() < value) {
            fence->SetEventOnCompletion(value, event);
            WaitForSingleObject(event, 10000);
        }
    }
};

// A texture in COMMON holding `picture`.
ID3D12Resource* surface(Gpu& gpu, DXGI_FORMAT format, const Picture& picture)
{
    D3D12_RESOURCE_DESC desc{};
    desc.Dimension = D3D12_RESOURCE_DIMENSION_TEXTURE2D;
    desc.Width = width;
    desc.Height = height;
    desc.DepthOrArraySize = 1;
    desc.MipLevels = 1;
    desc.Format = format;
    desc.SampleDesc.Count = 1;
    D3D12_HEAP_PROPERTIES heap{};
    heap.Type = D3D12_HEAP_TYPE_DEFAULT;
    ID3D12Resource* texture = nullptr;
    if (FAILED(gpu.device->CreateCommittedResource(&heap, D3D12_HEAP_FLAG_NONE, &desc, D3D12_RESOURCE_STATE_COMMON, nullptr,
                                                   IID_PPV_ARGS(&texture))))
        return nullptr;
    D3D12_PLACED_SUBRESOURCE_FOOTPRINT footprint{};
    UINT64 total = 0;
    gpu.device->GetCopyableFootprints(&desc, 0, 1, 0, &footprint, nullptr, nullptr, &total);
    heap.Type = D3D12_HEAP_TYPE_UPLOAD;
    D3D12_RESOURCE_DESC buffer{};
    buffer.Dimension = D3D12_RESOURCE_DIMENSION_BUFFER;
    buffer.Width = total;
    buffer.Height = 1;
    buffer.DepthOrArraySize = 1;
    buffer.MipLevels = 1;
    buffer.SampleDesc.Count = 1;
    buffer.Layout = D3D12_TEXTURE_LAYOUT_ROW_MAJOR;
    ID3D12Resource* upload = nullptr;
    gpu.device->CreateCommittedResource(&heap, D3D12_HEAP_FLAG_NONE, &buffer, D3D12_RESOURCE_STATE_GENERIC_READ, nullptr, IID_PPV_ARGS(&upload));
    void* mapped = nullptr;
    upload->Map(0, nullptr, &mapped);
    for (UINT y = 0; y < height; ++y)
        std::memcpy(static_cast<unsigned char*>(mapped) + footprint.Offset + std::size_t{y} * footprint.Footprint.RowPitch,
                    &picture[std::size_t{y} * width * 4], std::size_t{width} * 4);
    upload->Unmap(0, nullptr);
    ID3D12CommandAllocator* allocator = nullptr;
    ID3D12GraphicsCommandList* list = nullptr;
    gpu.device->CreateCommandAllocator(D3D12_COMMAND_LIST_TYPE_DIRECT, IID_PPV_ARGS(&allocator));
    gpu.device->CreateCommandList(0, D3D12_COMMAND_LIST_TYPE_DIRECT, allocator, nullptr, IID_PPV_ARGS(&list));
    D3D12_RESOURCE_BARRIER barrier{};
    barrier.Type = D3D12_RESOURCE_BARRIER_TYPE_TRANSITION;
    barrier.Transition.pResource = texture;
    barrier.Transition.Subresource = D3D12_RESOURCE_BARRIER_ALL_SUBRESOURCES;
    barrier.Transition.StateBefore = D3D12_RESOURCE_STATE_COMMON;
    barrier.Transition.StateAfter = D3D12_RESOURCE_STATE_COPY_DEST;
    list->ResourceBarrier(1, &barrier);
    D3D12_TEXTURE_COPY_LOCATION to{}, from{};
    to.pResource = texture;
    to.Type = D3D12_TEXTURE_COPY_TYPE_SUBRESOURCE_INDEX;
    from.pResource = upload;
    from.Type = D3D12_TEXTURE_COPY_TYPE_PLACED_FOOTPRINT;
    from.PlacedFootprint = footprint;
    list->CopyTextureRegion(&to, 0, 0, 0, &from, nullptr);
    std::swap(barrier.Transition.StateBefore, barrier.Transition.StateAfter);
    list->ResourceBarrier(1, &barrier);
    list->Close();
    ID3D12CommandList* lists[] = {list};
    gpu.queue->ExecuteCommandLists(1, lists);
    gpu.idle();
    list->Release();
    allocator->Release();
    upload->Release();
    return texture;
}

// The grid the sampler must publish for `picture`, reduced on the CPU from the same rows.
void expected_grid(const Picture& picture, x2w_present_signature::Layout layout, std::uint8_t (&grid)[x2w_present_signature::cells])
{
    for (int band = 0; band < x2w_present_signature::cells_y; ++band)
        x2w_present_signature::reduce_row(&picture[std::size_t{x2w_present_signature::sampled_row(band, height)} * width * 4], width, layout,
                                          grid + band * x2w_present_signature::cells_x);
}

// Presents `surfaces` in order through a sampler with interval 1, letting the GPU finish between
// presents, then one empty present to publish the last copy. Returns the published grids.
std::vector<x2w_present_signature::Snapshot> present_all(Gpu& gpu, x2w_present_signature::Block* block, const std::vector<ID3D12Resource*>& surfaces)
{
    std::vector<x2w_present_signature::Snapshot> published;
    x2w_present_signature::Sampler sampler(1);
    LONG64 present = 0;
    const std::uint64_t start = static_cast<std::uint64_t>(block->sequence / 2);
    const auto record = [&] {
        x2w_present_signature::Snapshot s{};
        if (x2w_present_signature::read(block, s) && s.sequence > start && (published.empty() || s.sequence != published.back().sequence))
            published.push_back(s);
    };
    for (ID3D12Resource* s : surfaces) {
        sampler.present(gpu.device, gpu.queue, s, ++present, block);
        record();
        gpu.idle();
    }
    sampler.present(gpu.device, gpu.queue, nullptr, ++present, block);
    record();
    check(!sampler.failed(), "sampler setup");
    return published;
}

int changes(const std::vector<x2w_present_signature::Snapshot>& grids)
{
    int n = 0;
    for (std::size_t i = 1; i < grids.size(); ++i)
        n += x2w_input_script::signal_distance(grids[i - 1].luma, grids[i].luma) >= x2w_input_script::changed_cells;
    return n;
}

}  // namespace

int main()
{
    IDXGIFactory4* factory = nullptr;
    IDXGIAdapter* warp = nullptr;
    Gpu gpu;
    if (FAILED(CreateDXGIFactory1(IID_PPV_ARGS(&factory))) || FAILED(factory->EnumWarpAdapter(IID_PPV_ARGS(&warp))) ||
        FAILED(D3D12CreateDevice(warp, D3D_FEATURE_LEVEL_11_0, IID_PPV_ARGS(&gpu.device)))) {
        std::printf("SKIP: no WARP device\n");
        return 77;
    }
    D3D12_COMMAND_QUEUE_DESC queue_desc{};
    queue_desc.Type = D3D12_COMMAND_LIST_TYPE_DIRECT;
    gpu.device->CreateCommandQueue(&queue_desc, IID_PPV_ARGS(&gpu.queue));
    gpu.device->CreateFence(0, D3D12_FENCE_FLAG_NONE, IID_PPV_ARGS(&gpu.fence));

    // A block of its own: this test's process id plus a high bit, so it never meets a run's block.
    x2w_present_signature::Block* block = x2w_present_signature::create_block(GetCurrentProcessId() | 0x80000000u, 1);
    check(block != nullptr, "create the signature block");
    if (!block) return 1;

    const Picture a = gradient(false), b = gradient(true);
    for (DXGI_FORMAT format : {DXGI_FORMAT_R8G8B8A8_UNORM, DXGI_FORMAT_B8G8R8A8_TYPELESS}) {
        const auto layout = format == DXGI_FORMAT_R8G8B8A8_UNORM ? x2w_present_signature::Layout::rgba8 : x2w_present_signature::Layout::bgra8;
        ID3D12Resource* a1 = surface(gpu, format, a);
        ID3D12Resource* a2 = surface(gpu, format, a);
        ID3D12Resource* b1 = surface(gpu, format, b);
        ID3D12Resource* b2 = surface(gpu, format, b);
        check(a1 && a2 && b1 && b2, "create the surfaces");
        if (!(a1 && a2 && b1 && b2)) return 1;

        // Two different pictures (A, A, B, B): the signal changes exactly once.
        const auto changing = present_all(gpu, block, {a1, a2, b1, b2});
        std::uint8_t grid_a[x2w_present_signature::cells], grid_b[x2w_present_signature::cells];
        expected_grid(a, layout, grid_a);
        expected_grid(b, layout, grid_b);
        check(changing.size() == 4, "four samples published for four presents");
        if (changing.size() == 4) {
            check(std::memcmp(changing[0].luma, grid_a, sizeof(grid_a)) == 0 && std::memcmp(changing[3].luma, grid_b, sizeof(grid_b)) == 0,
                  "published grids equal the CPU reduction of the sampled rows");
            check(changing[0].sample_present == 1 && changing[3].sample_present == 4, "samples carry their present numbers");
        }
        check(changes(changing) == 1, "two different pictures: the signal changes once");
        // Negative control: the same picture presented four times never changes the signal.
        const auto steady = present_all(gpu, block, {a1, a2, a1, a2});
        check(steady.size() == 4 && changes(steady) == 0, "identical pictures: the signal never changes");
        for (ID3D12Resource* r : {a1, a2, b1, b2}) r->Release();
    }

    // Interval: with every = 4, eight presents publish two samples (presents 1 and 5).
    {
        ID3D12Resource* s = surface(gpu, DXGI_FORMAT_R8G8B8A8_UNORM, a);
        x2w_present_signature::Sampler sampler(4);
        const LONG64 before = block->sequence / 2;
        for (LONG64 present = 1; present <= 8; ++present) {
            sampler.present(gpu.device, gpu.queue, s, present, block);
            gpu.idle();
        }
        sampler.present(gpu.device, gpu.queue, nullptr, 9, block);
        x2w_present_signature::Snapshot last{};
        check(block->sequence / 2 - before == 2 && x2w_present_signature::read(block, last) && last.sample_present == 5 && last.presents == 9,
              "every 4 presents: two samples from presents 1 and 5, latest present 9");
        s->Release();
    }
    // A format the signature does not read is refused, not guessed.
    {
        D3D12_RESOURCE_DESC desc{};
        desc.Dimension = D3D12_RESOURCE_DIMENSION_TEXTURE2D;
        desc.Width = 16;
        desc.Height = 16;
        desc.DepthOrArraySize = 1;
        desc.MipLevels = 1;
        desc.Format = DXGI_FORMAT_R16G16B16A16_FLOAT;
        desc.SampleDesc.Count = 1;
        D3D12_HEAP_PROPERTIES heap{};
        heap.Type = D3D12_HEAP_TYPE_DEFAULT;
        ID3D12Resource* half = nullptr;
        gpu.device->CreateCommittedResource(&heap, D3D12_HEAP_FLAG_NONE, &desc, D3D12_RESOURCE_STATE_COMMON, nullptr, IID_PPV_ARGS(&half));
        x2w_present_signature::Sampler sampler(1);
        sampler.present(gpu.device, gpu.queue, half, 1, block);
        check(half && sampler.unsupported_format() == DXGI_FORMAT_R16G16B16A16_FLOAT && !sampler.in_flight(),
              "16-bit float surface refused without a copy");
        if (half) half->Release();
    }
    std::printf("%s\n", failures ? "FAIL" : "pass");
    return failures ? 1 : 0;
}
