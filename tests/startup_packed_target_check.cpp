// Checks src/startup_stubs/packed_target_format.h without a device, against adapters described
// by their format-support bits.
#include "startup_stubs/packed_target_format.h"

#include <cstdio>

namespace {
int failures;
constexpr UINT rt = D3D12_FORMAT_SUPPORT1_RENDER_TARGET, uav = D3D12_FORMAT_SUPPORT1_TYPED_UNORDERED_ACCESS_VIEW;

struct Adapter {
    UINT b5g5r5a1, b4g4r4a4, rgba8;
    UINT operator()(DXGI_FORMAT format) const
    {
        return format == DXGI_FORMAT_B5G5R5A1_UNORM ? b5g5r5a1 : format == DXGI_FORMAT_B4G4R4A4_UNORM ? b4g4r4a4
             : format == DXGI_FORMAT_R8G8B8A8_UNORM ? rgba8 : rt | uav;
    }
};

D3D12_RESOURCE_DESC texture(DXGI_FORMAT format, UINT flags, D3D12_RESOURCE_DIMENSION dimension = D3D12_RESOURCE_DIMENSION_TEXTURE2D)
{
    D3D12_RESOURCE_DESC desc{};
    desc.Dimension = dimension;
    desc.Width = 2560;
    desc.Height = 1440;
    desc.DepthOrArraySize = 1;
    desc.MipLevels = 1;
    desc.Format = format;
    desc.SampleDesc.Count = 1;
    desc.Flags = static_cast<D3D12_RESOURCE_FLAGS>(flags);
    return desc;
}

void expect(const char* name, DXGI_FORMAT got, DXGI_FORMAT wanted)
{
    if (got != wanted) {
        std::printf("FAIL %s: format %d, expected %d\n", name, got, wanted);
        ++failures;
    }
}

void view(const char* name, x2w_startup::PackedView got, x2w_startup::PackedView wanted)
{
    if (got != wanted) {
        std::printf("FAIL %s: verdict %d, expected %d\n", name, static_cast<int>(got), static_cast<int>(wanted));
        ++failures;
    }
}
}  // namespace

int main()
{
    using x2w_startup::packed_target_stand_in;
    using x2w_startup::packed_view;
    constexpr UINT RT = D3D12_RESOURCE_FLAG_ALLOW_RENDER_TARGET, UA = D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS;
    constexpr DXGI_FORMAT b5 = DXGI_FORMAT_B5G5R5A1_UNORM, b4 = DXGI_FORMAT_B4G4R4A4_UNORM, rgba = DXGI_FORMAT_R8G8B8A8_UNORM;
    const Adapter full{rt | uav, rt | uav, rt | uav};   // supports the packed formats: nothing changes
    const Adapter none{0, 0, rt | uav};                 // the measured case
    const Adapter render_only{rt, rt, rt | uav};        // packed formats render but have no typed UAV
    const Adapter bare{0, 0, 0};                        // no stand-in available either

    // The two descriptions the measured run was refused: render target with unordered access, and render target.
    expect("b5g5r5a1 RT|UAV, unsupported", packed_target_stand_in(texture(b5, RT | UA), none), rgba);
    expect("b4g4r4a4 RT, unsupported", packed_target_stand_in(texture(b4, RT), none), rgba);
    expect("b5g5r5a1 RT|UAV, render only", packed_target_stand_in(texture(b5, RT | UA), render_only), rgba);

    // Controls: the format stays when the adapter supports the use, when the stand-in would not
    // help, for other formats, and for every role outside the measured ones.
    expect("b5g5r5a1 RT|UAV, supported", packed_target_stand_in(texture(b5, RT | UA), full), b5);
    expect("b4g4r4a4 RT, supported", packed_target_stand_in(texture(b4, RT), full), b4);
    expect("b4g4r4a4 RT, render only", packed_target_stand_in(texture(b4, RT), render_only), b4);
    expect("b5g5r5a1 RT, no stand-in", packed_target_stand_in(texture(b5, RT), bare), b5);
    expect("b5g6r5 RT", packed_target_stand_in(texture(DXGI_FORMAT_B5G6R5_UNORM, RT), none), DXGI_FORMAT_B5G6R5_UNORM);
    expect("rgba8 RT", packed_target_stand_in(texture(rgba, RT), none), rgba);
    expect("b5g5r5a1 sampled only", packed_target_stand_in(texture(b5, 0), none), b5);
    expect("b5g5r5a1 UAV without RT", packed_target_stand_in(texture(b5, UA), none), b5);
    expect("b4g4r4a4 3D RT", packed_target_stand_in(texture(b4, RT, D3D12_RESOURCE_DIMENSION_TEXTURE3D), none), b4);
    expect("b4g4r4a4 1D RT", packed_target_stand_in(texture(b4, RT, D3D12_RESOURCE_DIMENSION_TEXTURE1D), none), b4);
    expect("buffer", packed_target_stand_in(texture(b5, UA, D3D12_RESOURCE_DIMENSION_BUFFER), none), b5);
    D3D12_RESOURCE_DESC shaped = texture(b5, RT);
    shaped.DepthOrArraySize = 6;
    expect("b5g5r5a1 RT array", packed_target_stand_in(shaped, none), b5);
    shaped = texture(b5, RT);
    shaped.SampleDesc.Count = 4;
    expect("b5g5r5a1 RT multisampled", packed_target_stand_in(shaped, none), b5);

    // Views: a packed view becomes RGBA8 only on the stand-in for that very format.
    using x2w_startup::PackedView;
    constexpr DXGI_FORMAT plain = DXGI_FORMAT_UNKNOWN;
    view("b5g5r5a1 view of its stand-in", packed_view(b5, rgba, b5), PackedView::stand_in);
    view("b4g4r4a4 view of its stand-in", packed_view(b4, rgba, b4), PackedView::stand_in);
    view("b5g5r5a1 view of a b5g5r5a1 texture", packed_view(b5, b5, plain), PackedView::unchanged);
    view("srgb view of an rgba8 texture", packed_view(DXGI_FORMAT_R8G8B8A8_UNORM_SRGB, rgba, plain), PackedView::unchanged);
    view("rgba8 view of a stand-in", packed_view(rgba, rgba, b5), PackedView::unchanged);
    view("b5g5r5a1 view of a plain rgba8 texture", packed_view(b5, rgba, plain), PackedView::refused);
    view("b5g5r5a1 view of the b4g4r4a4 stand-in", packed_view(b5, rgba, b4), PackedView::refused);
    view("b5g5r5a1 view of a b4g4r4a4 texture", packed_view(b5, b4, plain), PackedView::refused);
    view("b5g5r5a1 view of a bgra8 texture", packed_view(b5, DXGI_FORMAT_B8G8R8A8_UNORM, plain), PackedView::refused);

    if (failures) {
        std::printf("startup_packed_target: %d FAILED\n", failures);
        return 1;
    }
    std::printf("startup_packed_target: PASS (3 stand-ins, 13 unchanged, 9 view verdicts)\n");
    return 0;
}
