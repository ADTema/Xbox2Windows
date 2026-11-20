float4 VSMain(uint vertex : SV_VertexID) : SV_Position
{
    // Pixel coordinates in a 64x64 viewport. The diagonal avoids pixel centers.
    const float2 corners[3] = { float2(8, 8), float2(56.25, 8), float2(8, 56.25) };
    return float4(corners[vertex] * float2(1.0 / 32, -1.0 / 32) + float2(-1, 1), 0, 1);
}

float4 PSMain() : SV_Target
{
    return float4(0, 1, 0, 1);
}
