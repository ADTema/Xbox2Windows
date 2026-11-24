// Checks the diagnostic line of src/startup_stubs/memory_srv_report.h without a device. The expected
// lines are written out by hand: they are what a tester pastes into an issue, field by field.
#include "startup_stubs/memory_srv_report.h"

#include <cstdio>
#include <cstring>

namespace {
int failures;

void expect(const char* name, const char* actual, const char* expected)
{
    if (std::strcmp(actual, expected) == 0) return;
    ++failures;
    std::printf("FAIL %s\n  actual   %s\n  expected %s\n", name, actual, expected);
}

D3D12_SHADER_RESOURCE_VIEW_DESC view(D3D12_SRV_DIMENSION dimension, DXGI_FORMAT format)
{
    D3D12_SHADER_RESOURCE_VIEW_DESC v{};
    v.Format = format;
    v.ViewDimension = dimension;
    v.Shader4ComponentMapping = D3D12_DEFAULT_SHADER_4_COMPONENT_MAPPING;
    return v;
}

int line(char (&out)[640], const char* reason, const D3D12_RESOURCE_DESC* r, const D3D12_SHADER_RESOURCE_VIEW_DESC* v,
         std::uint64_t address, bool readable, std::uint64_t destination, bool in_heap)
{
    return x2w_startup::report_refused_memory_srv(out, sizeof(out), "unsupported memory SRV arguments", reason, r, v,
                                                  address, readable, destination, in_heap);
}
}

int main()
{
    char out[640];
    D3D12_RESOURCE_DESC buffer{};
    buffer.Dimension = D3D12_RESOURCE_DIMENSION_BUFFER;
    buffer.Width = 4096;
    buffer.Height = buffer.DepthOrArraySize = buffer.MipLevels = buffer.SampleDesc.Count = 1;
    buffer.Layout = D3D12_TEXTURE_LAYOUT_ROW_MAJOR;

    // A view dimension that has no named fields here is printed as its six raw words.
    auto as = view(static_cast<D3D12_SRV_DIMENSION>(11), DXGI_FORMAT_UNKNOWN);
    as.Buffer.FirstElement = 0x1122334455667788ull;
    line(out, "unsupported_description", &buffer, &as, 0x2000, false, 0x1000, true);
    expect("acceleration structure view", out,
           "x2w-d3d12 Device::slot70 unsupported memory SRV arguments: reason=unsupported_description "
           "res{dim=1 fmt=0 size=4096x1x1 mips=1 layout=0x1 flags=0x0 align=0 samples=1/0} "
           "view{dim=11 fmt=0 map=0x1688 raw=55667788,11223344,00000000,00000000,00000000,00000000 "
           "(acceleration structure views are not supported)} dest=0x1000 dest_in_view_heap=1 address=0x2000 address_readable=0");

    auto b = view(D3D12_SRV_DIMENSION_BUFFER, DXGI_FORMAT_UNKNOWN);
    b.Buffer.FirstElement = 7;
    b.Buffer.NumElements = 64;
    b.Buffer.StructureByteStride = 16;
    b.Buffer.Flags = D3D12_BUFFER_SRV_FLAG_RAW;
    line(out, "unsupported_description", &buffer, &b, 0x2000, true, 0x1000, true);
    expect("buffer view", out,
           "x2w-d3d12 Device::slot70 unsupported memory SRV arguments: reason=unsupported_description "
           "res{dim=1 fmt=0 size=4096x1x1 mips=1 layout=0x1 flags=0x0 align=0 samples=1/0} "
           "view{dim=1 fmt=0 map=0x1688 first=7 count=64 stride=16 flags=0x1 (buffer views are not supported)} "
           "dest=0x1000 dest_in_view_heap=1 address=0x2000 address_readable=1");

    D3D12_RESOURCE_DESC bc7{D3D12_RESOURCE_DIMENSION_TEXTURE2D, 65536, 128, 128, 2, 6, DXGI_FORMAT_BC7_UNORM, {1, 0},
                            static_cast<D3D12_TEXTURE_LAYOUT>(0x105), static_cast<D3D12_RESOURCE_FLAGS>(0x300000)};
    auto array = view(D3D12_SRV_DIMENSION_TEXTURE2DARRAY, DXGI_FORMAT_BC7_UNORM);
    array.Texture2DArray.MostDetailedMip = 1;
    array.Texture2DArray.MipLevels = 5;
    array.Texture2DArray.FirstArraySlice = 1;
    array.Texture2DArray.ArraySize = 1;
    array.Texture2DArray.ResourceMinLODClamp = 0.5f;
    line(out, "destination_outside_view_heaps", &bc7, &array, 0x7000, true, 0x1001, false);
    expect("texture array view", out,
           "x2w-d3d12 Device::slot70 unsupported memory SRV arguments: reason=destination_outside_view_heaps "
           "res{dim=3 fmt=98 size=128x128x2 mips=6 layout=0x105 flags=0x300000 align=65536 samples=1/0} "
           "view{dim=5 fmt=98 map=0x1688 mostmip=1 mips=5 first=1 count=1 plane=0 clamp=0.5} "
           "dest=0x1001 dest_in_view_heap=0 address=0x7000 address_readable=1");

    // Memory the guest handed over but the runtime could not read.
    line(out, "null_destination", nullptr, nullptr, 0, false, 0, false);
    expect("unreadable arguments", out,
           "x2w-d3d12 Device::slot70 unsupported memory SRV arguments: reason=null_destination "
           "res{unreadable} view{unreadable} dest=0x0 dest_in_view_heap=0 address=0x0 address_readable=0");

    // A small buffer is cut, never overrun, and stays terminated.
    char small[40];
    std::memset(small, 'x', sizeof(small));
    x2w_startup::report_refused_memory_srv(small, sizeof(small), "unsupported memory SRV arguments", "null_address", &bc7,
                                           &array, 0, false, 0x1000, true);
    if (std::memchr(small, 0, sizeof(small)) == nullptr) {
        ++failures;
        std::printf("FAIL truncated line is not terminated\n");
    }
    if (failures) return 1;
    std::printf("slot 70 refusal lines: 4 formats and a truncation exact\n");
    return 0;
}
