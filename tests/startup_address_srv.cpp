#include <d3d12.h>
#include <array>
#include <cstddef>
#include <cstdint>
#include <vector>

using Word = std::uint64_t;
Word invoke(void*, unsigned, Word = 0, Word = 0, Word = 0, Word = 0, Word = 0, Word = 0, Word = 0, Word = 0);
namespace {
template<class T> Word ptr(T* value) { return reinterpret_cast<Word>(value); }
struct ViewAt {
    D3D12_SHADER_RESOURCE_VIEW_DESC view;
    Word address;
    Word tail[2];
};
static_assert(offsetof(ViewAt, address) == 0x28 && sizeof(ViewAt) == 0x40);
}

// Two separately placed R8 planes have the same descriptor and different row
// data. The producer and oracle both use the documented desktop footprint.
int draw_address_srvs(ID3D12Device* desktop, void* guest, void* list)
{
    const D3D12_RESOURCE_DESC desc{D3D12_RESOURCE_DIMENSION_TEXTURE2D, 0, 2, 2, 1, 1,
        DXGI_FORMAT_R8_UNORM, {1, 0}, D3D12_TEXTURE_LAYOUT_UNKNOWN, D3D12_RESOURCE_FLAG_NONE};
    D3D12_PLACED_SUBRESOURCE_FOOTPRINT footprint{};
    UINT rows = 0;
    UINT64 row_bytes = 0, bytes = 0;
    desktop->GetCopyableFootprints(&desc, 0, 1, 0, &footprint, &rows, &row_bytes, &bytes);
    if (rows != 2 || row_bytes != 2 || bytes < footprint.Footprint.RowPitch + 2) return 40;
    std::array<std::vector<unsigned char>, 2> planes;
    void* placed[2]{};
    for (unsigned i = 0; i < planes.size(); ++i) {
        planes[i].resize(static_cast<std::size_t>(bytes));
        for (unsigned y = 0; y < rows; ++y)
            for (unsigned x = 0; x < row_bytes; ++x)
                planes[i][y * footprint.Footprint.RowPitch + x] = static_cast<unsigned char>(16 + 128 * i + 32 * y + 7 * x);
        if (FAILED(static_cast<HRESULT>(invoke(guest, 133, ptr(planes[i].data()), ptr(&desc), D3D12_RESOURCE_STATE_COMMON,
                                               0, ptr(&__uuidof(ID3D12Resource)), ptr(&placed[i]))))) return 41;
    }
    struct Extended {
        D3D12_DESCRIPTOR_HEAP_DESC desc;
        Word address, bytes;
    } heap_desc{{D3D12_DESCRIPTOR_HEAP_TYPE_CBV_SRV_UAV, 1, D3D12_DESCRIPTOR_HEAP_FLAG_SHADER_VISIBLE}, 0, 0};
    void* heap = nullptr;
    if (FAILED(static_cast<HRESULT>(invoke(guest, 14, ptr(&heap_desc), ptr(&__uuidof(ID3D12DescriptorHeap)), ptr(&heap))))) return 42;
    const Word cpu = invoke(heap, 9);
    const Word gpu = invoke(heap, 10);
    invoke(list, 32, 1, ptr(&heap));
    invoke(list, 36, 0, gpu);
    ViewAt v{};
    v.view.Format = DXGI_FORMAT_R8_UNORM;
    v.view.ViewDimension = D3D12_SRV_DIMENSION_TEXTURE2D;
    v.view.Shader4ComponentMapping = D3D12_DEFAULT_SHADER_4_COMPONENT_MAPPING;
    v.view.Texture2D.MipLevels = 1;
    const auto draw = [&](LONG x) {
        const D3D12_RECT strip{x, 0, x + 1, 4};
        invoke(list, 22, 1, ptr(&strip));
        invoke(list, 12, 3, 1);
    };
    const auto publish = [&](const D3D12_RESOURCE_DESC& resource_desc, Word address) {
        v.address = address;
        invoke(guest, 70, ptr(&resource_desc), ptr(&v), cpu);
    };
    invoke(guest, 18, ptr(placed[0]), ptr(&v.view), cpu);
    draw(0); // Ordinary resource-object SRV is the independent control.
    publish(desc, ptr(planes[1].data())); draw(1);
    publish(desc, ptr(planes[0].data())); draw(2);
    publish(desc, 0); draw(3); // Rejection preserves the previous descriptor.
    publish(desc, ptr(planes[1].data())); draw(4);
    auto wrong_desc = desc;
    wrong_desc.Width = 1;
    publish(wrong_desc, ptr(planes[0].data())); draw(5);
    publish(desc, ptr(planes[0].data()) + 1); draw(6); // Interior address, not the registered base.
    publish(desc, ptr(planes[0].data())); draw(7);
    return 0;
}
