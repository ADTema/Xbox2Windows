// Verifies X2W_INPUT_SCRIPT playback of the GameInput.dll stand-in: holds, overlapping masks, stick
// and trigger values, both time bases, the 256-entry and 4,095-character limits, rejected items
// (tests/startup_gameinput_script.cpp keeps its own long and entries cases), and waits on the presented
// picture, marks and relative times (the timeline with a controllable clock and picture signal). The parser is checked directly
// (src/startup_stubs/input_script.h); playback is checked through IGameInput::GetCurrentReading in one
// child process per case, because the stand-in reads the script once per process. The children set
// X2W_INPUT_CLOCK_MS (milliseconds since process start) before every poll.
//
// usage: startup_gameinput_script_syntax <GameInput.dll>   (exit 77 when XInput pad 0 is connected: its
// values would merge into every reading; the parser checks still run first)
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>

#include "startup_stubs/input_script.h"
#include "startup_stubs/present_signature.h"

#include <cstdint>
#include <cstdio>
#include <cstring>
#include <iterator>
#include <string>
#include <utility>
#include <vector>

namespace {

constexpr std::uint32_t kind_gamepad = 0x00040000;

struct GamepadState {
    std::uint32_t buttons;
    float leftTrigger, rightTrigger;
    float leftThumbstickX, leftThumbstickY, rightThumbstickX, rightThumbstickY;
};
static_assert(sizeof(GamepadState) == 28, "GamepadState layout");

struct PadShared {
    std::uint32_t magic, buttons, title_read, reads;
};

struct IGameInputReading {
    const void* const* vtbl;
    std::uint32_t Release()
    {
        using Fn = std::uint64_t(__stdcall*)(IGameInputReading*);
        return static_cast<std::uint32_t>(reinterpret_cast<Fn>(vtbl[2])(this));
    }
    bool GetGamepadState(GamepadState* state)
    {
        using Fn = bool(__stdcall*)(IGameInputReading*, GamepadState*);
        return reinterpret_cast<Fn>(vtbl[22])(this, state);
    }
};
struct IGameInput {
    const void* const* vtbl;
    HRESULT GetCurrentReading(std::uint32_t kind, void* device, IGameInputReading** reading)
    {
        using Fn = HRESULT(__stdcall*)(IGameInput*, std::uint32_t, void*, IGameInputReading**);
        return reinterpret_cast<Fn>(vtbl[4])(this, kind, device, reading);
    }
};

int failures = 0;
void check(bool ok, const char* what, double at = -1)
{
    if (ok) return;
    ++failures;
    if (at >= 0)
        std::printf("FAIL: %s (at %.3f s)\n", what, at);
    else
        std::printf("FAIL: %s\n", what);
}

// ---- legacy reference: the parser and playback this stand-in shipped before holds and axes ----------
struct LegacyScript {
    std::uint32_t mask[32];
    double at[32];
    int count;
};
LegacyScript legacy_parse(const char* script)
{
    LegacyScript sc{{}, {}, 0};
    char text[512]{};
    std::strncpy(text, script, sizeof(text) - 1);
    char* context = nullptr;
    for (char* item = strtok_s(text, ",", &context); item && sc.count < 32; item = strtok_s(nullptr, ",", &context)) {
        unsigned mask = 0;
        double at = 0;
        if (std::sscanf(item, "%x@%lf", &mask, &at) == 2) {
            sc.mask[sc.count] = mask;
            sc.at[sc.count++] = at;
        }
    }
    return sc;
}
std::uint32_t legacy_buttons(const LegacyScript& sc, std::uint64_t ms_since_zero)
{
    const double t = ms_since_zero / 1000.0;
    std::uint32_t buttons = 0;
    for (int i = 0; i < sc.count; ++i)
        if (t >= sc.at[i] && t < sc.at[i] + 0.3) buttons |= sc.mask[i];
    return buttons;
}

const char* const legacy_scripts[] = {
    "4@60,1@70,20@80",
    "4@70",
    "4@1,,1@2.5,20@3,0x10@3.1, 8@4 ,2@4.2,",
    "4@1,4@1.1,4@1.25,8@1.2",
    "200@0,400@0.3,800@0.6,1000@0.9,2000@1.2",
};

std::uint32_t lcg(std::uint32_t& state) { return state = state * 1664525u + 1013904223u; }
std::string random_legacy_script(std::uint32_t& state)
{
    std::string text;
    const int count = 1 + static_cast<int>(lcg(state) % 32);
    for (int i = 0; i < count; ++i) {
        char item[48];
        const unsigned mask = 1 + lcg(state) % 0x3FFF;
        const unsigned ms = lcg(state) % 20000;
        switch (lcg(state) % 4) {
        case 0: std::snprintf(item, sizeof(item), "%x@%u", mask, ms / 1000); break;
        case 1: std::snprintf(item, sizeof(item), "0x%X@%.1f", mask, ms / 1000.0); break;
        case 2: std::snprintf(item, sizeof(item), " %x@%.3f", mask, ms / 1000.0); break;
        default: std::snprintf(item, sizeof(item), "%x@%.2f ", mask, ms / 1000.0); break;
        }
        text += (i ? "," : "") + std::string(item);
    }
    return text;
}

// Old-form against new-form parsing: identical buttons at every millisecond.
void check_legacy_equivalence()
{
    std::vector<std::string> scripts(std::begin(legacy_scripts), std::end(legacy_scripts));
    std::uint32_t state = 0x5EED;
    for (int i = 0; i < 60; ++i) scripts.push_back(random_legacy_script(state));
    for (const std::string& text : scripts) {
        const LegacyScript old_form = legacy_parse(text.c_str());
        const x2w_input_script::Script new_form = x2w_input_script::parse(text.c_str());
        if (new_form.entries.size() != static_cast<std::size_t>(old_form.count) || !new_form.rejections.empty() ||
            new_form.from_process_start) {
            std::printf("FAIL: legacy script \"%s\": %d old entries, %zu new entries, %zu rejected\n", text.c_str(),
                        old_form.count, new_form.entries.size(), new_form.rejections.size());
            ++failures;
            continue;
        }
        double last = 0;
        for (int i = 0; i < old_form.count; ++i) last = old_form.at[i] > last ? old_form.at[i] : last;
        const auto limit = static_cast<std::uint64_t>(last * 1000) + 1000;
        for (std::uint64_t ms = 0; ms <= limit; ++ms) {
            const x2w_input_script::Output out = x2w_input_script::play(new_form, ms / 1000.0);
            bool axes = false;
            for (bool active : out.active) axes |= active;
            if (out.buttons != legacy_buttons(old_form, ms) || axes) {
                std::printf("FAIL: legacy script \"%s\" at %llu ms: old 0x%x, new 0x%x\n", text.c_str(),
                            static_cast<unsigned long long>(ms), legacy_buttons(old_form, ms), out.buttons);
                ++failures;
                break;
            }
        }
    }
}

void check_rejections()
{
    struct Case {
        const char* script;
        std::size_t accepted, index;
        const char* reason;
    };
    const Case cases[] = {
        {"4", 0, 1, "missing @<seconds>"},
        {"4 @1", 0, 1, "missing @<seconds>"},
        {"4@", 0, 1, "bad time"},
        {"4@x", 0, 1, "bad time"},
        {"4@1+0", 0, 1, "bad duration"},
        {"4@1+-1", 0, 1, "bad duration"},
        {"4@1+", 0, 1, "bad duration"},
        {"4@1junk", 0, 1, "trailing text"},
        {"4@1,zz@2,8@3", 2, 2, "bad mask"},
        {"1FFFFFFFF@1", 0, 1, "bad mask"},
        {"lx=2@1", 0, 1, "value out of range [-1, 1]"},
        {"lt=-0.5@1", 0, 1, "value out of range [0, 1]"},
        {"qq=1@1", 0, 1, "unknown token"},
        {"lx=@1", 0, 1, "bad value"},
        {"ly=0.5", 0, 1, "missing @<seconds>"},
        {"4@1,base=start", 1, 2, "base= must be the first item"},
        {"base=later,4@1", 1, 1, "unknown base (use poll or start)"},
    };
    for (const Case& c : cases) {
        const x2w_input_script::Script s = x2w_input_script::parse(c.script);
        const bool ok = s.entries.size() == c.accepted && s.rejections.size() == 1 && s.rejections[0].index == c.index &&
                        s.rejections[0].reason == c.reason;
        if (!ok) {
            std::printf("FAIL: \"%s\": %zu accepted, %zu rejected, first %zu \"%s\" (want %zu accepted, item %zu \"%s\")\n",
                        c.script, s.entries.size(), s.rejections.size(), s.rejections.empty() ? 0 : s.rejections[0].index,
                        s.rejections.empty() ? "" : s.rejections[0].reason.c_str(), c.accepted, c.index, c.reason);
            ++failures;
        }
    }
    // The base directive is an item (it counts for indices) but not an entry.
    const x2w_input_script::Script based = x2w_input_script::parse(" base = start ,4@1,lx=-1@2+0.5,rt=1@3");
    check(based.from_process_start && based.entries.size() == 3 && based.rejections.empty(), "base=start with two axis entries");
    // Limit: 256 entries accepted, the 257th reported with its index.
    std::string text;
    for (int i = 0; i < 257; ++i) text += (i ? ",1@" : "1@") + std::to_string(i);
    const x2w_input_script::Script full = x2w_input_script::parse(text.c_str());
    check(full.entries.size() == 256 && full.rejections.size() == 1 && full.rejections[0].index == 257 &&
              full.rejections[0].reason == "over 256 entries" && full.items == 257,
          "257-entry script: 256 accepted, item 257 rejected over the limit");
}

// ---- waits, marks and relative times: the timeline with a controllable clock and picture signal ----
namespace tl = x2w_input_script;

// A picture whose every cell has `level`; `odd` cells (the first n) get `odd_level` instead.
tl::Signal picture(std::uint64_t sequence, std::uint8_t level, int odd = 0, std::uint8_t odd_level = 0, std::uint64_t present = 0)
{
    tl::Signal s;
    s.available = true;
    s.sequence = sequence;
    s.present = present;
    for (int i = 0; i < tl::signal_cells; ++i) s.cells[i] = i < odd ? odd_level : level;
    return s;
}

struct Run {
    tl::Script script;
    std::vector<tl::Event> events;
    std::vector<std::pair<int, std::uint32_t>> buttons;  // (ms, buttons) whenever they change
};

// Polls every `step` ms from 0 to `until` ms; `signal_at(ms)` gives the latest published picture.
template <class SignalAt>
Run run_timeline(const char* text, int until, SignalAt signal_at, int step = 10)
{
    Run run;
    run.script = tl::parse(text);
    if (!run.script.rejections.empty()) {
        std::printf("FAIL: timeline script \"%s\": item %zu rejected (%s)\n", text, run.script.rejections[0].index,
                    run.script.rejections[0].reason.c_str());
        ++failures;
    }
    tl::Timeline timeline(run.script);
    std::uint32_t last = ~0u;
    for (int ms = 0; ms <= until; ms += step) {
        const double t = ms / 1000.0;
        timeline.advance(t, signal_at(ms), run.events);
        const std::uint32_t b = timeline.play(t).buttons;
        if (b != last) run.buttons.push_back({ms, b});
        last = b;
    }
    return run;
}

// The buttons at `ms` from the change list.
std::uint32_t buttons_at(const Run& run, int ms)
{
    std::uint32_t b = 0;
    for (const auto& change : run.buttons)
        if (change.first <= ms) b = change.second;
    return b;
}
// First ms at which any of `mask` is down, or -1.
int first_press(const Run& run, std::uint32_t mask)
{
    for (const auto& change : run.buttons)
        if (change.second & mask) return change.first;
    return -1;
}
const tl::Event* find_event(const Run& run, tl::Event::Type type, std::size_t nth = 0)
{
    for (const tl::Event& e : run.events)
        if (e.type == type && nth-- == 0) return &e;
    return nullptr;
}
std::size_t count_events(const Run& run, tl::Event::Type type)
{
    std::size_t n = 0;
    for (const tl::Event& e : run.events) n += e.type == type;
    return n;
}
bool close_to(double a, double b) { return a > b - 1e-9 && a < b + 1e-9; }

void check_timeline()
{
    // Change then settle: picture A until 3.0 s, B afterwards; wait (settle 1 s) completes at 4.0 s.
    // "+2 then press down, +0.5 then press A": down at 6.0 s, A at 6.5 s.
    {
        const Run run = run_timeline("wait,80@+2,4@+0.5", 9000, [](int ms) {
            return ms < 3000 ? picture(1 + ms / 100, 40) : picture(1 + ms / 100, 200);
        });
        const tl::Event* begun = find_event(run, tl::Event::wait_begun);
        const tl::Event* changed = find_event(run, tl::Event::wait_changed);
        const tl::Event* done = find_event(run, tl::Event::wait_done);
        check(begun && close_to(begun->at, 0) && begun->signal, "settle: wait begins at 0 with a signal");
        check(changed && close_to(changed->at, 3.0), "settle: change seen at 3.0 s");
        check(done && close_to(done->at, 4.0) && close_to(done->elapsed, 4.0), "settle: wait done at 4.0 s after 4.0 s");
        check(count_events(run, tl::Event::wait_begun) == 1 && count_events(run, tl::Event::wait_done) == 1 &&
                  count_events(run, tl::Event::wait_timeout) == 0,
              "settle: each wait event once");
        check(first_press(run, 0x80) == 6000 && buttons_at(run, 6290) == 0x80 && buttons_at(run, 6300) == 0,
              "settle: down from 6.0 s for 0.3 s");
        check(first_press(run, 0x4) == 6500 && buttons_at(run, 6790) == 0x4 && buttons_at(run, 6800) == 0,
              "settle: accept from 6.5 s for 0.3 s");
    }
    // A picture that keeps changing past the settle time: A/B alternate every 0.5 s from 1.0 s to 5.0 s,
    // then B stays, with a small 5-cell flicker that must not count. Done at 6.0 s, changed logged once.
    {
        const Run run = run_timeline("wait,4@+0", 9000, [](int ms) {
            if (ms < 1000) return picture(1 + ms / 100, 40);
            if (ms < 5000) return picture(1 + ms / 100, ((ms - 1000) / 500) % 2 ? 40 : 200);
            return picture(1 + ms / 100, 200, ((ms / 250) % 2) ? 5 : 0, 0);
        });
        const tl::Event* done = find_event(run, tl::Event::wait_done);
        check(count_events(run, tl::Event::wait_changed) == 1, "keeps changing: one change event");
        check(done && close_to(done->at, 6.0), "keeps changing: done 1 s after the last large change (6.0 s)");
        check(first_press(run, 0x4) == 6000, "keeps changing: entry after the wait at 6.0 s");
    }
    // Timeout, go on: the picture never changes. Negative control: nothing after the wait before 10 s.
    {
        const Run run = run_timeline("wait=1/10,4@+1,8@+0", 15000, [](int ms) { return picture(1 + ms / 100, 90); });
        const tl::Event* timeout = find_event(run, tl::Event::wait_timeout);
        check(timeout && close_to(timeout->elapsed, 10.0) && !timeout->stopped && timeout->signal, "timeout go: logged at 10 s, goes on");
        check(count_events(run, tl::Event::wait_done) == 0 && count_events(run, tl::Event::wait_changed) == 0, "timeout go: never done");
        bool early = false;
        for (const auto& change : run.buttons) early |= change.first < 10000 && change.second != 0;
        check(!early, "negative control: no entry after an unchanged wait fires before the timeout");
        check(first_press(run, 0xC) == 11000 && buttons_at(run, 11100) == 0xC, "timeout go: entries 1 s after the timeout");
    }
    // Timeout, stop: nothing after the wait ever plays and later marks are not logged.
    {
        const Run run = run_timeline("2@0.5,wait=1/10/stop,4@+1,mark=after@+0", 30000, [](int ms) { return picture(1 + ms / 100, 90); });
        const tl::Event* timeout = find_event(run, tl::Event::wait_timeout);
        check(timeout && close_to(timeout->elapsed, 10.0) && timeout->stopped, "timeout stop: logged 10 s after the wait began, stops");
        check(first_press(run, 0x2) == 500 && first_press(run, 0x4) == -1, "timeout stop: earlier entry played, later one never");
        check(count_events(run, tl::Event::mark) == 0, "timeout stop: later mark never logged");
    }
    // No presenter: the wait begins without a signal and times out, saying so.
    {
        const Run run = run_timeline("wait=1/5,4@+0.5", 8000, [](int) { return tl::Signal{}; });
        const tl::Event* begun = find_event(run, tl::Event::wait_begun);
        const tl::Event* timeout = find_event(run, tl::Event::wait_timeout);
        check(begun && !begun->signal, "no presenter: wait begun without a signal");
        check(timeout && !timeout->signal && close_to(timeout->elapsed, 5.0), "no presenter: timeout after 5 s without a signal");
        check(first_press(run, 0x4) == 5500, "no presenter: entry 0.5 s after the timeout");
    }
    // Two waits in a row: A -> B at 2 s, B -> C at 4 s, settle 0.5 s each.
    {
        const Run run = run_timeline("wait=0.5,wait=0.5,4@+0", 8000, [](int ms) {
            return picture(1 + ms / 100, ms < 2000 ? 40 : ms < 4000 ? 120 : 220);
        });
        const tl::Event* first = find_event(run, tl::Event::wait_done, 0);
        const tl::Event* second = find_event(run, tl::Event::wait_done, 1);
        check(first && close_to(first->at, 2.5) && second && close_to(second->at, 4.5), "two waits: done at 2.5 s and 4.5 s");
        check(first_press(run, 0x4) == 4500, "two waits: entry at 4.5 s");
    }
    // Marks: label, time and present number; the default label names the item.
    {
        const Run run = run_timeline("mark=start@1,wait=0.5/30,mark=screen,mark@+2", 9000, [](int ms) {
            return picture(1 + ms / 100, ms < 3000 ? 40 : 200, 0, 0, 100 + ms / 16);
        });
        const tl::Event* a = find_event(run, tl::Event::mark, 0);
        const tl::Event* b = find_event(run, tl::Event::mark, 1);
        const tl::Event* c = find_event(run, tl::Event::mark, 2);
        check(a && a->label == "start" && close_to(a->at, 1.0) && a->present == 100 + 1000 / 16 && a->item == 1, "mark start at 1.0 s with its present");
        check(b && b->label == "screen" && close_to(b->at, 3.5) && b->item == 3, "mark screen when the wait completes (3.5 s)");
        check(c && c->label == "mark4" && close_to(c->at, 5.5), "default label and relative time (5.5 s)");
        check(count_events(run, tl::Event::mark) == 3, "each mark once");
    }
    // Relative times without waits; the cursor is the previous item's start.
    {
        const tl::Script s = tl::parse("4@1,8@+0.5,lx=1@+0.5+1,10@3,20@+0");
        check(s.entries.size() == 5 && close_to(s.entries[1].at, 1.5) && close_to(s.entries[2].at, 2.0) && close_to(s.entries[3].at, 3.0) &&
                  close_to(s.entries[4].at, 3.0),
              "relative times follow the previous item's start");
    }
    // Rejections of the new items.
    {
        struct Case {
            const char* script;
            std::size_t index;
            const char* reason;
        };
        const Case cases[] = {
            {"4@10,wait,8@5", 3, "time before the preceding wait"},
            {"wait=1/2/maybe", 1, "bad wait option"},
            {"wait=1/0", 1, "bad wait option"},
            {"wait=x", 1, "bad wait option"},
            {"wait=1/2/go/x", 1, "bad wait option"},
            {"wait@+1+2", 1, "duration not allowed on wait or mark"},
            {"mark=a b", 1, "bad label"},
            {"4@+-1", 1, "bad time"},
            {"wait@5,mark@4", 2, "time before the preceding wait"},
        };
        for (const Case& c : cases) {
            const tl::Script s = tl::parse(c.script);
            const bool ok = s.rejections.size() == 1 && s.rejections[0].index == c.index && s.rejections[0].reason == c.reason;
            if (!ok) {
                std::printf("FAIL: \"%s\": %zu rejected, first item %zu \"%s\" (want item %zu \"%s\")\n", c.script, s.rejections.size(),
                            s.rejections.empty() ? 0 : s.rejections[0].index, s.rejections.empty() ? "" : s.rejections[0].reason.c_str(),
                            c.index, c.reason);
                ++failures;
            }
        }
        const tl::Script options = tl::parse("wait=2.5/30/stop,wait=/45,wait=0");
        check(options.waits.size() == 3 && close_to(options.waits[0].settle, 2.5) && close_to(options.waits[0].timeout, 30) && options.waits[0].stop &&
                  close_to(options.waits[1].settle, 1.0) && close_to(options.waits[1].timeout, 45) && !options.waits[1].stop &&
                  close_to(options.waits[2].settle, 0) && close_to(options.waits[2].timeout, 120),
              "wait options and defaults");
    }
    // Scripts without waits or marks: the timeline plays exactly what play() plays.
    {
        const char* scripts[] = {"4@60,1@70,20@80", "4@1+2,8@2+2,10@2.5", "lx=-1@1+1,ly=0.5@1.5+1,rt=0.75@2,4@1.2+0.5"};
        for (const char* text : scripts) {
            const tl::Script s = tl::parse(text);
            tl::Timeline timeline(s);
            std::vector<tl::Event> events;
            bool same = s.waits.empty() && s.marks.empty();
            for (int ms = 0; ms <= 90000 && same; ++ms) {
                timeline.advance(ms / 1000.0, tl::Signal{}, events);
                const tl::Output a = timeline.play(ms / 1000.0), b = tl::play(s, ms / 1000.0);
                same = a.buttons == b.buttons && std::memcmp(a.axes, b.axes, sizeof(a.axes)) == 0 &&
                       std::memcmp(a.active, b.active, sizeof(a.active)) == 0;
            }
            check(same && events.empty(), "timeline equals play() for a script without waits");
        }
    }
}

// ---- playback through the stand-in, one child process per case --------------------------------------
struct Child {
    IGameInput* input = nullptr;
    std::string log_path;
    ~Child()
    {
        if (!log_path.empty()) DeleteFileA(log_path.c_str());
    }

    GamepadState at(std::uint64_t ms)
    {
        char text[24];
        std::snprintf(text, sizeof(text), "%llu", static_cast<unsigned long long>(ms));
        SetEnvironmentVariableA("X2W_INPUT_CLOCK_MS", text);
        GamepadState state{};
        IGameInputReading* reading = nullptr;
        if (FAILED(input->GetCurrentReading(kind_gamepad, nullptr, &reading)) || !reading) {
            check(false, "GetCurrentReading", ms / 1000.0);
            return state;
        }
        check(reading->GetGamepadState(&state), "GetGamepadState", ms / 1000.0);
        reading->Release();
        return state;
    }
    std::string log() const
    {
        std::string text;
        if (FILE* f = std::fopen(log_path.c_str(), "rb")) {
            char buffer[4096];
            for (std::size_t n; (n = std::fread(buffer, 1, sizeof(buffer), f)) > 0;) text.append(buffer, n);
            std::fclose(f);
        }
        return text;
    }
    std::size_t count(const char* needle) const
    {
        const std::string text = log();
        std::size_t n = 0;
        for (std::size_t at = text.find(needle); at != std::string::npos; at = text.find(needle, at + 1)) ++n;
        return n;
    }
};

bool open_child(const char* dll, const std::string& script, Child& child)
{
    char temp[MAX_PATH];
    GetTempPathA(MAX_PATH, temp);
    child.log_path = std::string(temp) + "x2w_gameinput_script_" + std::to_string(GetCurrentProcessId()) + ".log";
    DeleteFileA(child.log_path.c_str());
    SetEnvironmentVariableA("X2W_TRAP_LOG", child.log_path.c_str());
    SetEnvironmentVariableA("X2W_INPUT_PRESS", nullptr);
    SetEnvironmentVariableA("X2W_INPUT_KEYS", nullptr);
    SetEnvironmentVariableA("X2W_INPUT_SCRIPT", script.c_str());
    // The external-input block is OR-ed into every reading; this check needs it clear.
    HANDLE mapping = CreateFileMappingW(INVALID_HANDLE_VALUE, nullptr, PAGE_READWRITE, 0, sizeof(PadShared), L"Local\\x2w_input_pad");
    if (auto* shared = mapping ? static_cast<PadShared*>(MapViewOfFile(mapping, FILE_MAP_ALL_ACCESS, 0, 0, sizeof(PadShared))) : nullptr)
        shared->buttons = 0;
    HMODULE module = LoadLibraryA(dll);
    if (!module) {
        std::printf("LoadLibraryA(%s) failed: %lu\n", dll, GetLastError());
        return false;
    }
    using CreateFn = HRESULT(__stdcall*)(IGameInput**);
    const auto create = reinterpret_cast<CreateFn>(GetProcAddress(module, "GameInputCreate"));
    if (!create || FAILED(create(&child.input)) || !child.input) {
        std::printf("GameInputCreate failed\n");
        return false;
    }
    return true;
}

void expect_buttons(Child& child, std::uint64_t ms, std::uint32_t want, const char* what)
{
    const GamepadState s = child.at(ms);
    if (s.buttons != want) {
        std::printf("FAIL: %s at %llu ms: buttons 0x%x, want 0x%x\n", what, static_cast<unsigned long long>(ms), s.buttons, want);
        ++failures;
    }
}

int case_long(const char* dll)
{
    // 200 entries, one every 0.5 s, about 2.5 KB of text (the former limits were 32 entries and 512 bytes).
    std::string script;
    std::vector<std::uint32_t> masks;
    for (int i = 0; i < 200; ++i) {
        masks.push_back((1u << (i % 14)) | (static_cast<std::uint32_t>(i) << 16));
        char item[32];
        std::snprintf(item, sizeof(item), "%s%x@%.3f", i ? "," : "", masks.back(), i * 0.5);
        script += item;
    }
    Child child;
    if (!open_child(dll, script, child)) return 2;
    const std::uint64_t first_poll = 1000;
    expect_buttons(child, first_poll, masks[0], "first poll");
    int delivered = 0;
    for (int i = 0; i < 200; ++i) {
        const std::uint64_t start = first_poll + static_cast<std::uint64_t>(i) * 500;
        const GamepadState on = child.at(start + 100), off = child.at(start + 400);
        if (on.buttons == masks[i] && off.buttons == 0) ++delivered;
    }
    if (delivered != 200) {
        std::printf("FAIL: %d of 200 entries delivered\n", delivered);
        ++failures;
    }
    check(child.count("x2w-input script: 200 entries accepted, 0 rejected, time base first-poll") == 1, "200-entry summary line");
    check(child.count("x2w-input script time passed its last entry (200 entries, ended at 99.800 s") == 1, "last-entry line");
    return 0;
}

int case_legacy(const char* dll)
{
    const char* script = "4@1,,1@2.5,20@3,0x10@3.1, 8@4 ,2@4.2,";
    const LegacyScript old_form = legacy_parse(script);
    Child child;
    if (!open_child(dll, script, child)) return 2;
    const std::uint64_t first_poll = 2345;
    for (std::uint64_t ms = 0; ms <= 6000; ms += 5) {
        const std::uint32_t want = legacy_buttons(old_form, ms);
        const GamepadState s = child.at(first_poll + ms);
        if (s.buttons != want) {
            std::printf("FAIL: legacy script at %llu ms after the first poll: 0x%x, want 0x%x\n",
                        static_cast<unsigned long long>(ms), s.buttons, want);
            ++failures;
            break;
        }
    }
    check(child.count("x2w-input script: 6 entries accepted, 0 rejected, time base first-poll") == 1, "legacy summary line");
    return 0;
}

int case_hold(const char* dll)
{
    Child child;
    if (!open_child(dll, "4@1+2,8@5", child)) return 2;
    const std::uint64_t z = 2000;
    expect_buttons(child, z, 0, "hold before start");
    expect_buttons(child, z + 990, 0, "hold before start");
    expect_buttons(child, z + 1000, 4, "hold starts");
    expect_buttons(child, z + 2990, 4, "hold still held");
    expect_buttons(child, z + 3000, 0, "hold ends after 2 s");
    expect_buttons(child, z + 5000, 8, "default press starts");
    expect_buttons(child, z + 5290, 8, "default press held");
    expect_buttons(child, z + 5310, 0, "default press ends after 0.3 s");
    return 0;
}

int case_overlap(const char* dll)
{
    Child child;
    if (!open_child(dll, "4@1+2,8@2+2,10@2.5", child)) return 2;
    const std::uint64_t z = 500;
    expect_buttons(child, z, 0, "overlap start");
    expect_buttons(child, z + 1500, 0x4, "first hold alone");
    expect_buttons(child, z + 2200, 0xC, "two holds combined");
    expect_buttons(child, z + 2600, 0x1C, "three entries combined");
    expect_buttons(child, z + 2900, 0xC, "press ended, holds remain");
    expect_buttons(child, z + 3500, 0x8, "second hold alone");
    expect_buttons(child, z + 4500, 0, "all released");
    return 0;
}

int case_sticks(const char* dll)
{
    Child child;
    if (!open_child(dll, "lx=-1@1+1,ly=0.5@1.5+1,rt=0.75@2,4@1.2+0.5,rx=1@3+1,rx=-0.25@3.5+0.2,lt=1@3,ry=-0.5@3", child)) return 2;
    struct Want {
        std::uint64_t ms;
        std::uint32_t buttons;
        float lt, rt, lx, ly, rx, ry;
    };
    const Want wants[] = {
        {500, 0, 0, 0, 0, 0, 0, 0},       {1300, 4, 0, 0, -1, 0, 0, 0},    {1600, 4, 0, 0, -1, 0.5f, 0, 0},
        {2100, 0, 0, 0.75f, 0, 0.5f, 0, 0}, {2600, 0, 0, 0, 0, 0, 0, 0},     {3100, 0, 1, 0, 0, 0, 1, -0.5f},
        {3600, 0, 0, 0, 0, 0, -0.25f, 0}, {3800, 0, 0, 0, 0, 0, 1, 0},       {4500, 0, 0, 0, 0, 0, 0, 0},
    };
    const std::uint64_t z = 1000;
    child.at(z);
    for (const Want& w : wants) {
        const GamepadState s = child.at(z + w.ms);
        const bool ok = s.buttons == w.buttons && s.leftTrigger == w.lt && s.rightTrigger == w.rt && s.leftThumbstickX == w.lx &&
                        s.leftThumbstickY == w.ly && s.rightThumbstickX == w.rx && s.rightThumbstickY == w.ry;
        if (!ok) {
            std::printf("FAIL: sticks at %.3f s: buttons 0x%x lt %g rt %g lx %g ly %g rx %g ry %g\n", w.ms / 1000.0, s.buttons,
                        s.leftTrigger, s.rightTrigger, s.leftThumbstickX, s.leftThumbstickY, s.rightThumbstickX, s.rightThumbstickY);
            ++failures;
        }
    }
    return 0;
}

int case_base_start(const char* dll)
{
    Child child;
    if (!open_child(dll, "base=start,4@5", child)) return 2;
    expect_buttons(child, 3000, 0, "process-start base, first poll");
    expect_buttons(child, 4900, 0, "process-start base, before");
    expect_buttons(child, 5100, 4, "process-start base, 5 s after process start");
    expect_buttons(child, 5400, 0, "process-start base, after");
    expect_buttons(child, 8100, 0, "process-start base, not first-poll relative");
    check(child.count("x2w-input script: 1 entries accepted, 0 rejected, time base process-start") == 1, "process-start summary");
    check(child.count("x2w-input script time base process-start: first poll at 3.000 s, first entry at 5.000 s since process start") == 1,
          "process-start resolved time line");
    return 0;
}

int case_base_poll(const char* dll)
{
    Child child;
    if (!open_child(dll, "4@5", child)) return 2;
    expect_buttons(child, 3000, 0, "first-poll base, first poll");
    expect_buttons(child, 5100, 0, "first-poll base, not process-start relative");
    expect_buttons(child, 8100, 4, "first-poll base, 5 s after the first poll");
    expect_buttons(child, 8400, 0, "first-poll base, after");
    check(child.count("x2w-input script time base first-poll: first poll at 3.000 s, first entry at 8.000 s since process start") == 1,
          "first-poll resolved time line");
    return 0;
}

int case_malformed(const char* dll)
{
    Child child;
    if (!open_child(dll, "4@1,zz@2,8@3", child)) return 2;
    const std::uint64_t z = 100;
    expect_buttons(child, z, 0, "malformed script, first poll");
    expect_buttons(child, z + 1100, 4, "valid item before the malformed one");
    expect_buttons(child, z + 2100, 0, "malformed item delivers nothing");
    expect_buttons(child, z + 3100, 8, "valid item after the malformed one");
    check(child.count("x2w-input script: 2 entries accepted, 1 rejected, time base first-poll") == 1, "malformed summary counts");
    check(child.count(" rejected (") == 1, "exactly one rejection line");
    check(child.count("x2w-input X2W_INPUT_SCRIPT: 2 of 3 entries used (1 malformed, at most 256)") == 1, "entries-used line");
    check(child.count("x2w-input script item 2 rejected (bad mask): \"zz@2\"") == 1, "rejection names item 2 and the reason");
    return 0;
}

// A wait through the stand-in, with this process standing in for the presenter: it creates the
// picture-signature block of its own process id and publishes pictures A and then B.
int case_wait(const char* dll)
{
    x2w_present_signature::Block* block = x2w_present_signature::create_block(GetCurrentProcessId(), 4);
    if (!block) {
        std::printf("FAIL: create_block\n");
        return 2;
    }
    std::uint8_t a[x2w_present_signature::cells], b[x2w_present_signature::cells];
    std::memset(a, 40, sizeof(a));
    std::memset(b, 200, sizeof(b));
    x2w_present_signature::publish(block, a, 8);
    x2w_present_signature::note_present(block, 10);
    Child child;
    if (!open_child(dll, "wait=1/20,80@+2,mark=menu@+0,4@+0.5", child)) return 2;
    const std::uint64_t z = 1000;  // first poll: the wait begins at 0 s on the first-poll base
    for (std::uint64_t ms = z; ms <= z + 8000; ms += 100) {
        if (ms == z + 2000) x2w_present_signature::publish(block, b, 40);
        x2w_present_signature::note_present(block, static_cast<LONG64>(10 + (ms - z) / 16));
        const GamepadState s = child.at(ms);
        const std::uint64_t t = ms - z;
        const std::uint32_t want = t >= 5000 && t < 5300 ? 0x80 : t >= 5500 && t < 5800 ? 0x4 : 0;
        if (s.buttons != want) {
            std::printf("FAIL: wait script at %.3f s: buttons 0x%x, want 0x%x\n", t / 1000.0, s.buttons, want);
            ++failures;
            break;
        }
    }
    check(child.count("x2w-input script: 3 entries accepted, 0 rejected, time base first-poll") == 0, "summary counts entries only");
    check(child.count("x2w-input script: 2 entries accepted, 0 rejected, time base first-poll") == 1, "wait summary line");
    check(child.count("x2w-input script: 1 waits, 1 marks; picture signal from Local\\x2w_present_signature_") == 1, "wait and mark count line");
    check(child.count("x2w-input script wait item 1 begun at 0.000 s\r\n") == 1, "wait begun line");
    check(child.count("x2w-input script wait item 1: picture changed at 2.000 s, 2.000 s after the wait began") == 1, "picture changed line");
    check(child.count("x2w-input script wait item 1 done at 3.000 s after 3.000 s") == 1, "wait done line");
    check(child.count("timed out") == 0, "no timeout line");
    check(child.count("x2w-input script mark menu at 5.000 s (item 3, present 322)") == 1, "mark line with the present number");
    check(child.count("x2w-input script time passed its last entry (2 entries, ended at 5.800 s") == 1, "last-entry line after the wait");
    return 0;
}

// The same kind of script without a presenter: the wait times out and says so; the script goes on.
int case_wait_without_presenter(const char* dll)
{
    Child child;
    if (!open_child(dll, "wait=1/2,4@+0.5,mark@+0", child)) return 2;
    const std::uint64_t z = 500;
    for (std::uint64_t ms = z; ms <= z + 4000; ms += 50) {
        const GamepadState s = child.at(ms);
        const std::uint64_t t = ms - z;
        const std::uint32_t want = t >= 2500 && t < 2800 ? 0x4 : 0;
        if (s.buttons != want) {
            std::printf("FAIL: presenter-less wait at %.3f s: buttons 0x%x, want 0x%x\n", t / 1000.0, s.buttons, want);
            ++failures;
            break;
        }
    }
    check(child.count("x2w-input script wait item 1 begun at 0.000 s (no presenter signal yet)") == 1, "begun without a presenter");
    check(child.count("x2w-input script wait item 1 timed out at 2.000 s after 2.000 s (no presenter signal); the script goes on") == 1,
          "timeout without a presenter");
    check(child.count("x2w-input script mark mark3 at 2.500 s (item 3, no presenter signal)") == 1, "mark without a presenter");
    return 0;
}

// Over 4,095 characters the value is ignored as a whole and logged; nothing is pressed.
int case_too_long(const char* dll)
{
    std::string script = "4@0";
    while (script.size() < 4096) script += ",1@9000";
    Child child;
    if (!open_child(dll, script, child)) return 2;
    expect_buttons(child, 1000, 0, "too-long script, first poll");
    expect_buttons(child, 1100, 0, "too-long script presses nothing");
    char line[96];
    std::snprintf(line, sizeof(line), "x2w-input X2W_INPUT_SCRIPT ignored: %zu characters, at most 4095", script.size());
    check(child.count(line) == 1, "ignored line with the length");
    check(child.count("x2w-input script: ") == 0, "no summary for an ignored script");
    return 0;
}

// 257 entries: the 257th is reported over the limit and counted; the 256 others play.
int case_over_limit(const char* dll)
{
    std::string script;
    for (int i = 0; i < 257; ++i) script += (i ? ",4@" : "4@") + std::to_string(i);
    Child child;
    if (!open_child(dll, script, child)) return 2;
    expect_buttons(child, 0, 4, "over limit: entry 1");
    expect_buttons(child, 255100, 4, "over limit: entry 256");
    expect_buttons(child, 256100, 0, "over limit: entry 257 not played");
    check(child.count("x2w-input X2W_INPUT_SCRIPT: 256 of 257 entries used (0 malformed, at most 256)") == 1, "entries-used line");
    check(child.count("x2w-input script item 257 rejected (over 256 entries): \"4@256\"") == 1, "item 257 named");
    return 0;
}

struct NamedCase {
    const char* name;
    int (*run)(const char*);
};
const NamedCase cases[] = {
    {"long", case_long},         {"legacy", case_legacy},         {"hold", case_hold},
    {"overlap", case_overlap},   {"sticks", case_sticks},         {"base_start", case_base_start},
    {"base_poll", case_base_poll}, {"malformed", case_malformed},
    {"too_long", case_too_long}, {"over_limit", case_over_limit},
    {"wait", case_wait},         {"wait_without_presenter", case_wait_without_presenter},
};

bool xinput_pad_connected()
{
    struct State {
        DWORD packet;
        BYTE pad[12];
    };
    HMODULE module = LoadLibraryW(L"xinput1_4.dll");
    if (!module) return false;
    using Fn = DWORD(WINAPI*)(DWORD, State*);
    const auto get = reinterpret_cast<Fn>(GetProcAddress(module, "XInputGetState"));
    State state{};
    return get && get(0, &state) == 0;
}

int run_child_case(const char* self, const char* dll, const char* name)
{
    std::string command = std::string("\"") + self + "\" \"" + dll + "\" " + name;
    STARTUPINFOA si{sizeof(si)};
    PROCESS_INFORMATION pi{};
    if (!CreateProcessA(nullptr, command.data(), nullptr, nullptr, FALSE, 0, nullptr, nullptr, &si, &pi)) {
        std::printf("CreateProcess(%s) failed: %lu\n", name, GetLastError());
        return 2;
    }
    DWORD code = 1;
    if (WaitForSingleObject(pi.hProcess, 120000) != WAIT_OBJECT_0) {
        TerminateProcess(pi.hProcess, 1);
        std::printf("case %s timed out\n", name);
    }
    GetExitCodeProcess(pi.hProcess, &code);
    CloseHandle(pi.hThread);
    CloseHandle(pi.hProcess);
    return static_cast<int>(code);
}

}  // namespace

int main(int argc, char** argv)
{
    if (argc < 2) {
        std::printf("usage: %s <GameInput.dll> [case]\n", argv[0]);
        return 2;
    }
    if (argc >= 3) {
        for (const NamedCase& c : cases)
            if (std::strcmp(c.name, argv[2]) == 0) {
                const int status = c.run(argv[1]);
                return status ? status : (failures ? 1 : 0);
            }
        std::printf("unknown case %s\n", argv[2]);
        return 2;
    }

    check_legacy_equivalence();
    check_rejections();
    check_timeline();
    std::printf("parser checks: %s\n", failures ? "FAIL" : "pass");
    if (xinput_pad_connected()) {
        std::printf("SKIP: XInput pad 0 is connected; its values merge into every reading, playback cases not run\n");
        return failures ? 1 : 77;
    }
    char self[MAX_PATH];
    GetModuleFileNameA(nullptr, self, MAX_PATH);
    for (const NamedCase& c : cases) {
        const int code = run_child_case(self, argv[1], c.name);
        std::printf("case %s: %s (exit %d)\n", c.name, code == 0 ? "pass" : "FAIL", code);
        if (code != 0) ++failures;
    }
    return failures ? 1 : 0;
}
