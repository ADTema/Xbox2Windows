// Playback-timing control: the same endpoint and the same sink as #1250, fed two ways.
//
// The stutter reported from the title is a pacing symptom, and an audible report cannot say whether
// the producer fed the endpoint in steady blocks or in bursts with gaps. This fixture feeds the sink
// the same total amount of audio twice:
//
//   steady  - one block every block_period, paced in real time
//   bursty  - a run of blocks back to back, then a withholding gap with no submission
//
// and prints, for each phase, the first submission, the frame counts, the endpoint clock, the drained
// interval (how long the queue sat empty while the producer withheld data) and the recovery time (from
// the producer resuming to consumption advancing again). The sink and the endpoint are not modified:
// this measures them.
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

void print_report(const char* name, const Report& r, const std::vector<double>& starts, double first_ms)
{
    double largest_gap = 0;
    for (size_t i = 1; i < starts.size(); ++i) largest_gap = std::max(largest_gap, starts[i] - starts[i - 1]);
    std::printf("%s: first_submission_at=%.1fms blocks=%zu first_block=%lld frames=%llu consumed=%llu clock=%llu "
                "largest_submit_gap=%.1fms drained_ms=%.1f recovery_ms=%.1f rejected_full=%u unsupported=%u\n",
                name, first_ms, r.frames.size(), static_cast<long long>(r.first_block),
                static_cast<unsigned long long>(r.submitted_frames), static_cast<unsigned long long>(r.consumed_frames),
                static_cast<unsigned long long>(r.clock_frames), largest_gap, r.drained_ms, r.recovery_ms, r.rejected_full,
                r.unsupported);
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

int run_steady(AudioSink& sink, const BlockFormat& format, uint32_t block_frames, int blocks, Report& report,
               std::vector<double>& starts, double& first_ms)
{
    const auto pcm = tone(format.rate, block_frames, 220.0);
    const double begin = now_ms();
    first_ms = -1;
    for (int i = 0; i < blocks; ++i) {
        const double want = begin + i * (1000.0 * block_frames / format.rate);
        while (now_ms() < want) Sleep(1);
        const double at = now_ms();
        if (submit_with_wait(sink, format, pcm) != Submit::Accepted) return 1;
        if (first_ms < 0) first_ms = at - begin;
        starts.push_back(at - begin);
        sink.observe(false);
    }
    report = sink.report();
    return 0;
}

int run_bursty(AudioSink& sink, const BlockFormat& format, uint32_t block_frames, int bursts, int per_burst, int gap_ms,
               Report& report, std::vector<double>& starts, double& first_ms)
{
    const auto pcm = tone(format.rate, block_frames, 220.0);
    const double begin = now_ms();
    first_ms = -1;
    for (int b = 0; b < bursts; ++b) {
        for (int i = 0; i < per_burst; ++i) {
            const double at = now_ms();
            if (submit_with_wait(sink, format, pcm) != Submit::Accepted) return 1;
            if (first_ms < 0) first_ms = at - begin;
            starts.push_back(at - begin);
            sink.observe(false);
        }
        // Withhold: keep sampling so the sink can see the queue drain, but submit nothing.
        const double until = now_ms() + gap_ms;
        while (now_ms() < until) {
            sink.observe(true);
            Sleep(5);
        }
    }
    report = sink.report();
    return 0;
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

    Report steady{}, bursty{};
    std::vector<double> steady_starts, bursty_starts;
    double steady_first = -1, bursty_first = -1;
    if (run_steady(sink, source, block_frames, 120, steady, steady_starts, steady_first)) return 3;
    if (run_bursty(sink, source, block_frames, 8, 6, 150, bursty, bursty_starts, bursty_first)) return 4;

    print_report("steady", steady, steady_starts, steady_first);
    print_report("bursty", bursty, bursty_starts, bursty_first);

    // The comparison the fixture exists for.
    const double steady_drained = steady.drained_ms, bursty_drained = bursty.drained_ms;
    const double steady_gap = steady_starts.size() > 1 ? steady_starts.back() - steady_starts.front() : 0;
    const double bursty_gap = bursty_starts.size() > 1 ? bursty_starts.back() - bursty_starts.front() : 0;
    std::printf("comparison: drained steady=%.1f ms bursty=%.1f ms; span steady=%.1f ms bursty=%.1f ms\n",
                steady_drained, bursty_drained, steady_gap, bursty_gap);

    if (bursty.frames.empty() || steady.frames.empty()) {
        std::printf("FAIL: no accepted blocks\n");
        return 1;
    }
    if (bursty_drained <= steady_drained + 20.0) {
        std::printf("FAIL: bursty input did not register a longer drained interval than steady input "
                    "(%.1f vs %.1f ms); the measurement cannot see producer stutter\n", bursty_drained, steady_drained);
        return 1;
    }
    if (bursty.recovery_ms < 0) {
        std::printf("FAIL: bursty phase never recovered (recovery not measured)\n");
        return 1;
    }
    std::printf("PASS: bursty input shows a drained interval steady input does not, and recovers in %.1f ms\n",
                bursty.recovery_ms);
    return 0;
}