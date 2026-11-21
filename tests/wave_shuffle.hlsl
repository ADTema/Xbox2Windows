// Minimal source-built WaveReadLaneAt check: one 64-thread group. Every thread stores its native lane,
// the wave width, a wave identifier and the group thread whose value each read returned, so the CPU
// can tell a correct read from the inverse permutation. WAVE_SIZE forces the width (SM 6.6).
RWByteAddressBuffer output : register(u0);

#ifdef WAVE_SIZE
[WaveSize(WAVE_SIZE)]
#endif
[RootSignature("UAV(u0)")] [numthreads(64,1,1)]
void Shuffle(uint t : SV_GroupIndex)
{
    uint lane = WaveGetLaneIndex();
    uint width = WaveGetLaneCount();
    uint wave = WaveReadLaneFirst(t);
    // A different source lane for every lane. Not self-inverse at widths 16, 32 and 64.
    uint gathered = WaveReadLaneAt(t, (lane * 7 + 3) % width);
    // Controls: a self-inverse shuffle and a uniform broadcast.
    uint mirrored = WaveReadLaneAt(t, width - 1 - lane);
    uint broadcast = WaveReadLaneAt(t, 3 % width);
    output.Store4(t * 32, uint4(lane, width, wave, gathered));
    output.Store4(t * 32 + 16, uint4(mirrored, broadcast, WaveActiveCountBits(true), 0));
}
