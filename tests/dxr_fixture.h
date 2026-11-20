#pragma once
#include "bvh_fixture.h"

namespace dxr_fixture {
struct Ray {
    float x, y, z, nearT, dx, dy, dz, farT;
    UINT mask = 255;
};
static_assert(sizeof(Ray) == 36);
using Vertex = std::array<float, 3>;
bool supported(ID3D12Device* device);
D3D12_RAYTRACING_INSTANCE_DESC instance(UINT id, UINT mask, float translateX = 0);
std::vector<bvh_fixture::Word> trace(ID3D12Device* device, const std::vector<Vertex>& vertices,
    std::vector<D3D12_RAYTRACING_INSTANCE_DESC> instances, const std::vector<Ray>& rays);
}
