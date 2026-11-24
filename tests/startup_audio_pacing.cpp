// Playback-timing control: the same endpoint and the same sink as #1250, fed two ways.
//
// The stutter reported from the title is a pacing symptom, and an audible report cannot say whether
// the producer fed the endpoint in steady blocks or in bursts with gaps. This fixture feeds the sink
// the same number of blocks, and therefore the same total audio, twice:
//
//   steady  - one block every block_period, paced in real time
//   bursty  - a run of blocks back to back, then a withholding gap with no submission
//
// and prints, for each phase, the first submission, the block and frame counts, the endpoint clock,
// the drained interval (how long the queue sat empty while the producer withheld data) and the
// recovery time (from the producer resuming to consumption advancing again). The sink and the endpoint
// are not modified: this measures them.
//
// The sink's report is cumulative for the life of the sink, so every number below is a phase delta
// taken against a snapshot before the phase started; a raw report() would otherwise include the
// earlier phase and mislabel it as this one's.
//
// The check is the difference between the phases, not an absolute number: bursty input must show a
// drained interval the steady phase does not, otherwise the measurement cannot see a producer-side
// stutter at all and this fixture is not evidence either way.
#include "startup_stubs/audio_sink.h"

#define NOMINMAX
#include <windows.h>
#include <objbase.h>

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>

using namespace x2w_audio;

namespace {
constexpr int skip_no_endpoint = 77;

// What one phase did, with every sink counter expressed as a delta over the phase.
struct Phase {
    const char* name = "";
    double first_submit_ms = -1;
    double largest_gap_ms = 0;
    unsigned long long blocks = 0;
    unsigned long long frames = 0;
    unsigned long long consumed = 0;
    unsigned long long clock = 0;
    double drained_ms = 0;
    double recovery_ms = -1;
    unsigned rejected_full = 0;
    unsigned unsupported = 0;
};

void print_phase(const Phase& p)
{
    std::printf("%s: first_submission_at=%.1fms blocks=%llu frames=%llu consumed=%llu clock=%llu "
                "largest_submit_gap=%.1fms drained_ms=%.1f recovery_ms=%.1f rejected_full=%u unsupported=%u\n",
                p.name, p.first_submit_ms, p.blocks, p.frames, p.consumed, p.clock, p.largest_gap_ms, p.drained_ms,
                p.recovery_ms, p.rejected_full, p.unsupported);
}

// Frames of a quiet tone so blocks are valid audio rather than an empty submission.
std::vector<int16_t> tone(uint32_t rate, uint32_t frames, double hz)
{
    std::vector<int16_t> pcm(frames);
    for (uint32_t i = 0; i < frames; ++i)
        pcm[i] = static_cast<int16_t>(1200.0 * std::sin(2.0 * 3.14159265358979 * hz * i / rate));
    return pcm;
}

Submit submit_with_wait(AudioSink& sink, const BlockFormat& format, const std::vector<int16_t>& pcm)
{
    const double end = now_ms() + 500;
    for (;;) {
        const Submit r = sink.submit(format, static_cast<uint32_t>(pcm.size()), pcm.data());
        if (r != Submit::Full || now_ms() > end) return r;
        Sleep(2);
        sink.observe(false);
    }
}

Phase delta(const Report& before, const Report& after, const char* name)
{
    Phase p;
    p.name = name;
    p.blocks = after.frames.size() - before.frames.size();
    p.frames = after.submitted_frames - before.submitted_frames;
    p.consumed = after.consumed_frames - before.consumed_frames;
    p.clock = after.clock_frames - before.clock_frames;
    p.drained_ms = after.drained_ms - before.drained_ms;
    p.recovery_ms = after.recovery_ms;
    p.rejected_full = after.rejected_full - before.rejected_full;
    p.unsupported = after.unsupported - before.unsupported;
    return p;
}

// Records when a submission happened and the largest gap between consecutive submissions in a phase.
struct Cadence {
    double begin = 0;
    double first = -1;
    double previous = -1;
    double largest = 0;
    void mark()
    {
        const double at = now_ms() - begin;
        if (first < 0) first = at;
        if (previous >= 0) largest = (std::max)(largest, at - previous);
        previous = at;
    }
};

bool run_steady(AudioSink& sink, const BlockFormat& source, uint32_t block_frames, int blocks, Phase& phase)
{
    const auto pcm = tone(source.rate, block_frames, 220.0);
    const Report before = sink.report();
    Cadence cadence;
    cadence.begin = now_ms();
    for (int i = 0; i < blocks; ++i) {
        const double want = cadence.begin + i * (1000.0 * block_frames / source.rate);
        while (now_ms() < want) Sleep(1);
        if (submit_with_wait(sink, source, pcm) != Submit::Accepted) return false;
        cadence.mark();
        sink.observe(false);
    }
    sink.observe(false);
    const Report after = sink.report();
    phase = delta(before, after, "steady");
    phase.first_submit_ms = cadence.first;
    phase.largest_gap_ms = cadence.largest;
    return true;
}

bool run_bursty(AudioSink& sink, const BlockFormat& source, uint32_t block_frames, int bursts, int per_burst, int gap_ms,
                Phase& phase)
{
    const auto pcm = tone(source.rate, block_frames, 220.0);
    const Report before = sink.report();
    Cadence cadence;
    cadence.begin = now_ms();
    for (int b = 0; b < bursts; ++b) {
        for (int i = 0; i < per_burst; ++i) {
            if (submit_with_wait(sink, source, pcm) != Submit::Accepted) return false;
            cadence.mark();
            sink.observe(false);
        }
        const double until = now_ms() + gap_ms;
        while (now_ms() < until) {
            sink.observe(true);
            Sleep(5);
        }
    }
    sink.observe(false);
    const Report after = sink.report();
    phase = delta(before, after, "bursty");
    phase.first_submit_ms = cadence.first;
    phase.largest_gap_ms = cadence.largest;
    return true;
}
}  // namespace

int main()
{
    if (FAILED(CoInitializeEx(nullptr, COINIT_MULTITHREADED))) {
        std::printf("skip: COM initialisation failed\n");
        return skip_no_endpoint;
    }
    AudioSink sink;
    const std::string error = sink.open();
    if (!error.empty()) {
        std::printf("skip: no usable endpoint: %s\n", error.c_str());
        return skip_no_endpoint;
    }
    const BlockFormat mix = sink.mix_format();
    std::printf("endpoint: %s, %s %u ch %u Hz, buffer %u frames\n", sink.endpoint().c_str(),
                mix.kind == SampleKind::Float32 ? "float32" : "pcm16", mix.channels, mix.rate, sink.buffer_frames());

    const BlockFormat source{SampleKind::Pcm16, 1, mix.rate};
    const uint32_t block_frames = mix.rate / 100;  // 10 ms
    if (block_frames == 0) return 2;

    // The same block count in both phases, so the only difference is pacing.
    constexpr int total_blocks = 120;
    constexpr int bursts = 20, per_burst = total_blocks / bursts;  // 6 x 20 = 120

    Phase steady{}, bursty{};
    if (!run_steady(sink, source, block_frames, total_blocks, steady)) return 3;
    if (!run_bursty(sink, source, block_frames, bursts, per_burst, 150, bursty)) return 4;

    print_phase(steady);
    print_phase(bursty);
    std::printf("comparison: blocks %llu/%llu frames %llu/%llu drained steady=%.1f ms bursty=%.1f ms\n", steady.blocks,
                bursty.blocks, steady.frames, bursty.frames, steady.drained_ms, bursty.drained_ms);

    if (!steady.blocks || !bursty.blocks) {
        std::printf("FAIL: no accepted blocks in a phase\n");
        return 1;
    }
    if (steady.frames != bursty.frames) {
        std::printf("FAIL: phases did not submit the same total audio (%llu vs %llu frames)\n", steady.frames, bursty.frames);
        return 1;
    }
    if (bursty.drained_ms <= steady.drained_ms + 20.0) {
        std::printf("FAIL: bursty input did not register a longer drained interval than steady input "
                    "(%.1f vs %.1f ms); the measurement cannot see producer stutter\n", bursty.drained_ms,
                    steady.drained_ms);
        return 1;
    }
    if (bursty.recovery_ms < 0) {
        std::printf("FAIL: bursty phase never recovered (recovery not measured)\n");
        return 1;
    }
    std::printf("PASS: same total audio, bursty feed shows a drained interval steady feed does not, recovery %.1f ms\n",
                bursty.recovery_ms);
    return 0;
}