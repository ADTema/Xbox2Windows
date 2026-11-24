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
}  // namespace

int main()
{
    using x2w_startup::packed_target_stand_in;
    using x2w_startup::packed_view_format;
    constexpr UINT RT = D3D12_RESOURCE_FLAG_ALLOW_RENDER_TARGET, UA = D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS;
    constexpr DXGI_FORMAT b5 = DXGI_FORMAT_B5G5R5A1_UNORM, b4 = DXGI_FORMAT_B4G4R4A4_UNORM, rgba = DXGI_FORMAT_R8G8B8A8_UNORM;
    const Adapter full{rt | uav, rt | uav, rt | uav};   // supports the packed formats: nothing changes
    const Adapter none{0, 0, rt | uav};                 // the measured case
    const Adapter render_only{rt, rt, rt | uav};        // packed formats render but have no typed UAV
    const Adapter bare{0, 0, 0};                        // no stand-in available either

    // The two descriptions the measured run was refused: render target with unordered access, and render target.
    expect("b5g5r5a1 RT|UAV, unsupported", packed_target_stand_in(texture(b5, RT | UA), none), rgba);
    expect("b4g4r4a4 RT, unsupported", packed_target_stand_in(texture(b4, RT), none), rgba);
    expect("b5g5r5a1 UAV, unsupported", packed_target_stand_in(texture(b5, UA), none), rgba);
    expect("b5g5r5a1 RT|UAV, render only", packed_target_stand_in(texture(b5, RT | UA), render_only), rgba);
    expect("b4g4r4a4 3D RT, unsupported", packed_target_stand_in(texture(b4, RT, D3D12_RESOURCE_DIMENSION_TEXTURE3D), none), rgba);

    // Controls: the format stays when the adapter supports the use, when no such use is asked,
    // when the stand-in would not help, and for other formats and buffers.
    expect("b5g5r5a1 RT|UAV, supported", packed_target_stand_in(texture(b5, RT | UA), full), b5);
    expect("b4g4r4a4 RT, supported", packed_target_stand_in(texture(b4, RT), full), b4);
    expect("b4g4r4a4 RT, render only", packed_target_stand_in(texture(b4, RT), render_only), b4);
    expect("b5g5r5a1 sampled only", packed_target_stand_in(texture(b5, 0), none), b5);
    expect("b5g5r5a1 RT, no stand-in", packed_target_stand_in(texture(b5, RT), bare), b5);
    expect("b5g6r5 RT", packed_target_stand_in(texture(DXGI_FORMAT_B5G6R5_UNORM, RT), none), DXGI_FORMAT_B5G6R5_UNORM);
    expect("rgba8 RT", packed_target_stand_in(texture(rgba, RT), none), rgba);
    expect("buffer", packed_target_stand_in(texture(b5, UA, D3D12_RESOURCE_DIMENSION_BUFFER), none), b5);

    // Views follow a stand-in texture and nothing else.
    expect("b5g5r5a1 view of a stand-in", packed_view_format(b5, rgba), rgba);
    expect("b4g4r4a4 view of a stand-in", packed_view_format(b4, rgba), rgba);
    expect("b5g5r5a1 view of a b5g5r5a1 texture", packed_view_format(b5, b5), b5);
    expect("srgb view of an rgba8 texture", packed_view_format(DXGI_FORMAT_R8G8B8A8_UNORM_SRGB, rgba), DXGI_FORMAT_R8G8B8A8_UNORM_SRGB);
    expect("b5g5r5a1 view of an unrelated texture", packed_view_format(b5, DXGI_FORMAT_B8G8R8A8_UNORM), b5);

    if (failures) {
        std::printf("startup_packed_target: %d FAILED\n", failures);
        return 1;
    }
    std::printf("startup_packed_target: PASS (5 stand-ins, 8 unchanged, 5 view formats)\n");
    return 0;
}
