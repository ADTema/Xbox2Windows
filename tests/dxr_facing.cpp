#include "dxr_fixture.h"
#include "dxr_facing_reference.h"
#include <cmath>
#include <cstdio>
#include <cstring>
#include <stdexcept>

static_assert(dxr_facing::cullBack == D3D12_RAY_FLAG_CULL_BACK_FACING_TRIANGLES);
static_assert(dxr_facing::cullFront == D3D12_RAY_FLAG_CULL_FRONT_FACING_TRIANGLES);

bool check_dxr_facing(ID3D12Device* device) {
    // The geometric reference must reproduce the hand-derived table on every
    // machine, including those that skip the GPU comparison.
    const auto scene = dxr_facing::instances();
    const auto probes = dxr_facing::rays();
    const auto mesh = dxr_facing::vertices();
    if (dxr_facing::first_reference_mismatch() != probes.size())
        throw std::runtime_error("Facing reference disagrees with its hand-derived table");
    if (!dxr_fixture::supported(device)) return false;
    std::vector<dxr_fixture::Vertex> vertices(mesh.begin(), mesh.end());
    std::vector<D3D12_RAYTRACING_INSTANCE_DESC> instances;
    for (const auto& source : scene) {
        D3D12_RAYTRACING_INSTANCE_DESC desc{};
        for (UINT axis = 0; axis < 3; ++axis) desc.Transform[axis][axis] = source.scale[axis];
        desc.Transform[0][3] = source.translateX;
        desc.InstanceID = source.id;
        desc.InstanceMask = 255;
        desc.Flags = (source.counterclockwise ? D3D12_RAYTRACING_INSTANCE_FLAG_TRIANGLE_FRONT_COUNTERCLOCKWISE : 0u) |
                     (source.cullDisable ? D3D12_RAYTRACING_INSTANCE_FLAG_TRIANGLE_CULL_DISABLE : 0u);
        instances.push_back(desc);
    }
    std::vector<dxr_fixture::Ray> rays;
    for (const auto& probe : probes)
        rays.push_back({probe.origin[0], probe.origin[1], probe.origin[2], probe.nearT,
                        probe.direction[0], probe.direction[1], probe.direction[2], probe.farT,
                        255, probe.flags | dxr_fixture::report_facing});
    const auto words = dxr_fixture::trace(device, vertices, instances, rays);
    UINT hits = 0, frontHits = 0, mismatches = 0;
    for (UINT i = 0; i < rays.size(); ++i) {
        const auto expected = dxr_facing::closest(mesh, scene, probes[i]);
        const UINT* value = words.data() + 4 * i;
        float distance;
        std::memcpy(&distance, value + 3, sizeof(distance));
        // Status, instance and primitive are exact. A hit distance may differ
        // from the reference by 1e-5 relative; a miss leaves all four words zero.
        const UINT status = expected.hit ? (expected.front ? 3u : 1u) : 0u;
        const bool distanceMatches = expected.hit
            ? std::abs(distance - expected.distance) <= 1e-5 * expected.distance : value[3] == 0;
        if (value[0] != status || value[1] != expected.instance || value[2] != expected.primitive || !distanceMatches) {
            if (!mismatches)
                std::fprintf(stderr, "ray=%u flags=0x%x expected status=%u instance=%u primitive=%u distance=%g "
                             "actual status=%u instance=%u primitive=%u distance=%g\n", i, probes[i].flags, status,
                             expected.instance, expected.primitive, expected.distance, value[0], value[1], value[2], distance);
            ++mismatches;
        }
        hits += expected.hit;
        frontHits += expected.hit && expected.front;
    }
    std::printf("dxr_facing rays=%zu hits=%u front_hits=%u culled=%zu mismatches=%u\n",
                rays.size(), hits, frontHits, rays.size() - hits, mismatches);
    if (mismatches) throw std::runtime_error("DXR facing or culling disagrees with the CPU reference");
    if (hits != 64 || frontHits != 32) throw std::runtime_error("Facing fixture lost its expected coverage");
    return true;
}
