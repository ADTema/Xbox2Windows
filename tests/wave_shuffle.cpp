#include "bvh_fixture.h"
#include "WaveShuffle.h"
#include "WaveShuffle16.h"
#include "WaveShuffle32.h"
#include "WaveShuffle64.h"
#include <map>
#include <utility>

using namespace bvh_fixture;

namespace {
constexpr Word threads = 64, fields = 8;

// Runs one shader variant and classifies every thread's WaveReadLaneAt((lane*7+3) % width) result.
// Returns the number of threads whose shuffle or controls read the wrong lane.
unsigned run_variant(ID3D12Device* device, const char* label, D3D12_SHADER_BYTECODE code, Word forced)
{
    constexpr UINT bytes = threads * fields * sizeof(Word);
    Kernel shader(device, code);
    auto out = make_buffer(device, bytes, D3D12_HEAP_TYPE_DEFAULT, D3D12_RESOURCE_STATE_COMMON,
                           D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS);
    auto back = make_buffer(device, bytes, D3D12_HEAP_TYPE_READBACK, D3D12_RESOURCE_STATE_COPY_DEST);
    ComputeCommands cmd(device, shader.pipeline.Get());
    auto* list = cmd.list.Get();
    transition(list, out.Get(), D3D12_RESOURCE_STATE_COMMON, D3D12_RESOURCE_STATE_UNORDERED_ACCESS);
    list->SetComputeRootSignature(shader.root.Get());
    list->SetComputeRootUnorderedAccessView(0, out->GetGPUVirtualAddress());
    list->Dispatch(1, 1, 1);
    transition(list, out.Get(), D3D12_RESOURCE_STATE_UNORDERED_ACCESS, D3D12_RESOURCE_STATE_COPY_SOURCE);
    list->CopyBufferRegion(back.Get(), 0, out.Get(), 0, bytes);
    cmd.submit_and_wait(device);
    const auto r = read(back.Get(), threads * fields);

    const Word width = r[1];
    if (!width || width > threads || threads % width) throw std::runtime_error("Unexpected wave width");
    if (forced && width != forced) throw std::runtime_error("Forced wave width was not applied");
    std::map<std::pair<Word, Word>, Word> thread_at;  // (wave, lane) -> group thread
    for (Word t = 0; t < threads; ++t) {
        const Word* rec = r.data() + t * fields;
        if (rec[1] != width || rec[6] != width) throw std::runtime_error("Wave not full or width varies");
        if (!thread_at.emplace(std::make_pair(rec[2], rec[0]), t).second)
            throw std::runtime_error("Duplicate native lane");
    }
    auto source = [&](Word wave, Word lane) {
        auto it = thread_at.find({wave, lane});
        return it == thread_at.end() ? UINT32_MAX : it->second;
    };
    auto inverse_lane = [&](Word n) {  // the lane m with (7m+3) % width == n
        for (Word m = 0; m < width; ++m)
            if ((m * 7 + 3) % width == n) return m;
        throw std::runtime_error("Shuffle permutation is not invertible at this width");
    };
    bool distinct = false;  // whether the inverse permutation differs from the requested one
    for (Word n = 0; n < width; ++n)
        if (inverse_lane(n) != (n * 7 + 3) % width) distinct = true;
    unsigned correct = 0, inverse = 0, other = 0, controls = 0;
    for (Word t = 0; t < threads; ++t) {
        const Word* rec = r.data() + t * fields;
        const Word lane = rec[0], wave = rec[2];
        if (rec[3] == source(wave, (lane * 7 + 3) % width)) {
            ++correct;
        } else {
            ++(rec[3] == source(wave, inverse_lane(lane)) ? inverse : other);
        }
        if (rec[4] != source(wave, width - 1 - lane) || rec[5] != source(wave, 3 % width)) ++controls;
    }
    std::printf("wave_shuffle %s width=%u correct=%u inverse=%u other=%u control_errors=%u inverse_distinct=%s\n",
                label, width, correct, inverse, other, controls, distinct ? "yes" : "no");
    return threads - correct + controls;
}
}

bool check_wave_shuffle(ID3D12Device* device)
{
    D3D12_FEATURE_DATA_D3D12_OPTIONS1 caps{};
    D3D12_FEATURE_DATA_SHADER_MODEL model{D3D_SHADER_MODEL_6_6};
    check(device->CheckFeatureSupport(D3D12_FEATURE_D3D12_OPTIONS1, &caps, sizeof(caps)), "Query wave range");
    check(device->CheckFeatureSupport(D3D12_FEATURE_SHADER_MODEL, &model, sizeof(model)), "Query wave shader model");
    std::printf("native_lane_range=%u..%u shader_model_capped_at_6_6=0x%x\n",
                caps.WaveLaneCountMin, caps.WaveLaneCountMax, model.HighestShaderModel);
    // The native variant is cs_6_5 like the other dynamic-shuffle fixtures. The Windows 10 in-box WARP
    // (10.0.19041, SM 6.2) removes the device for any WaveReadLaneAt whose lane index is not a literal.
    if (!caps.WaveOps || model.HighestShaderModel < D3D_SHADER_MODEL_6_5) return false;
    unsigned errors = run_variant(device, "native", {WaveShuffle, sizeof(WaveShuffle)}, 0);
    const struct { Word width; D3D12_SHADER_BYTECODE code; } forced[] = {
        {16, {WaveShuffle16, sizeof(WaveShuffle16)}},
        {32, {WaveShuffle32, sizeof(WaveShuffle32)}},
        {64, {WaveShuffle64, sizeof(WaveShuffle64)}},
    };
    bool ran_forced = false;
    for (const auto& f : forced) {
        if (model.HighestShaderModel < D3D_SHADER_MODEL_6_6 || caps.WaveLaneCountMin > f.width ||
            caps.WaveLaneCountMax < f.width) {
            std::printf("wave_shuffle forced width=%u skipped\n", f.width);
            continue;
        }
        errors += run_variant(device, "forced", f.code, f.width);
        ran_forced = true;
    }
    if (errors) throw std::runtime_error("WaveReadLaneAt returned a value from a lane other than the requested one");
    return ran_forced;
}
