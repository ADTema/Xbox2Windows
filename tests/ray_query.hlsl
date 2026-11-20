RaytracingAccelerationStructure scene : register(t0);
RWStructuredBuffer<uint4> results : register(u0);
struct Query { float4 originMin; float4 directionMax; uint mask; };
StructuredBuffer<Query> queries : register(t1);

[RootSignature("SRV(t0),UAV(u0),SRV(t1)")]
[numthreads(1, 1, 1)]
void CSMain(uint3 thread : SV_DispatchThreadID)
{
    uint i = thread.x;
    RayDesc ray;
    Query query = queries[i];
    ray.Origin = query.originMin.xyz;
    ray.Direction = query.directionMax.xyz;
    ray.TMin = query.originMin.w;
    ray.TMax = query.directionMax.w;
    RayQuery<RAY_FLAG_FORCE_OPAQUE> q;
    q.TraceRayInline(scene, RAY_FLAG_NONE, query.mask, ray);
    while (q.Proceed()) {}
    uint4 value = uint4(0, 0, 0, 0);
    if (q.CommittedStatus() == COMMITTED_TRIANGLE_HIT)
        value = uint4(1, q.CommittedInstanceID(), q.CommittedPrimitiveIndex(), asuint(q.CommittedRayT()));
    results[i] = value;
}
