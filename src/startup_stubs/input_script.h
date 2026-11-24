// Experimental (docs/startup-runtime.md#input-script): parser and playback of X2W_INPUT_SCRIPT for the
// GameInput stand-in (src/startup_stubs/gameinput.cpp). Pure C++, no Windows calls, so the
// checks in tests/startup_gameinput_script.cpp can drive it directly.
//
// A script is a comma-separated list. Each non-empty item is one of:
//   <mask hex>@<s>[+<d>]          press these GameInput button bits at <s> for <d> s (default 0.3)
//   <axis>=<value>@<s>[+<d>]      hold one axis at <value>: lx ly rx ry in [-1, 1], lt rt in [0, 1]
//   base=poll | base=start        time base of every entry (first item only; default poll)
//   wait[=<settle>[/<timeout>[/stop|/go]]][@<s>]
//                                 block the timeline until the presented picture changes and then
//                                 stays unchanged for <settle> s (default 1); after <timeout> s
//                                 (default 120) log a timeout and go on (go, default) or stop
//   mark[=<label>][@<s>]          log the script time and the present number at <s>
// <s> is absolute seconds on the time base, or +<seconds> after the previous timed item (its
// start; for a wait, its completion). wait and mark without @ mean @+0. Items after a wait are
// shifted by the time the wait blocked and never start before it completes.
// Active button entries OR their masks; among active entries on one axis the later item wins.
// Items that cannot be accepted are kept as rejections (1-based item index and reason).
#pragma once

#include <algorithm>
#include <cerrno>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <initializer_list>
#include <string>
#include <vector>

namespace x2w_input_script {

constexpr std::size_t max_entries = 256;  // as the stand-in kept before holds and axes (#1859)
constexpr double default_duration = 0.3;
// Same order as the floats of the stand-in's GamepadState after its buttons.
enum Axis : int { axis_left_trigger, axis_right_trigger, axis_left_x, axis_left_y, axis_right_x, axis_right_y, axis_count };
inline const char* const axis_names[axis_count] = {"lt", "rt", "lx", "ly", "rx", "ry"};

constexpr double default_settle = 1.0, default_timeout = 120.0;

struct Entry {
    int axis;  // -1 for a button entry
    std::uint32_t mask;
    float value;
    double at, duration;
    std::size_t segment;  // number of waits before this item
};
struct Wait {
    std::size_t index;  // item index
    double at, settle, timeout;
    bool stop;
};
struct Mark {
    std::size_t index;
    double at;
    std::size_t segment;
    std::string label;
};
struct Rejection {
    std::size_t index;  // 1-based position among the non-empty items
    std::string reason, text;
};
struct Script {
    bool from_process_start = false;
    std::size_t items = 0;  // non-empty items, accepted or not
    std::vector<Entry> entries;
    std::vector<Wait> waits;
    std::vector<Mark> marks;
    std::vector<Rejection> rejections;
};
struct Output {
    std::uint32_t buttons = 0;
    float axes[axis_count] = {};
    bool active[axis_count] = {};
};

namespace detail {
inline bool blank(char c) { return c == ' ' || c == '\t' || c == '\r' || c == '\n'; }

// "@<seconds>[+<duration>]" or "@+<seconds>[+<duration>]" (after `cursor`) up to the end of the item.
inline const char* parse_when(const char* p, double cursor, Entry& entry, bool* had_duration = nullptr)
{
    if (*p != '@') return "missing @<seconds>";
    char* stop = nullptr;
    const bool relative = p[1] == '+';
    p += relative ? 2 : 1;
    entry.at = std::strtod(p, &stop);
    if (stop == p || !std::isfinite(entry.at) || (relative && !(entry.at >= 0))) return "bad time";
    if (relative) entry.at += cursor;
    p = stop;
    entry.duration = default_duration;
    if (had_duration) *had_duration = *p == '+';
    if (*p == '+') {
        entry.duration = std::strtod(++p, &stop);
        if (stop == p || !std::isfinite(entry.duration) || !(entry.duration > 0)) return "bad duration";
        p = stop;
    }
    return *p ? "trailing text" : nullptr;
}

inline bool label_char(char c)
{
    return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') || c == '_' || c == '-' || c == '.';
}

// The option text after "wait=": <settle>[/<timeout>[/stop|/go]], empty fields keep their default.
inline const char* parse_wait_options(const std::string& text, Wait& wait)
{
    std::string parts[3];
    std::size_t count = 0, from = 0;
    for (;;) {
        if (count == 3) return "bad wait option";
        const std::size_t slash = text.find('/', from);
        parts[count++] = text.substr(from, slash == std::string::npos ? std::string::npos : slash - from);
        if (slash == std::string::npos) break;
        from = slash + 1;
    }
    for (std::size_t i = 0; i < count && i < 2; ++i) {
        if (parts[i].empty()) continue;
        char* stop = nullptr;
        const double value = std::strtod(parts[i].c_str(), &stop);
        if (*stop || !std::isfinite(value) || value < 0 || (i == 1 && value == 0)) return "bad wait option";
        (i == 0 ? wait.settle : wait.timeout) = value;
    }
    if (count == 3) {
        if (parts[2] != "stop" && parts[2] != "go") return "bad wait option";
        wait.stop = parts[2] == "stop";
    }
    return nullptr;
}

// wait and mark items: `value` is the text after '=' (may be empty), `when` the text from '@'
// (empty means @+0). Adds the item to `script` and sets `at`.
inline const char* parse_event(const std::string& name, const std::string& value, const std::string& when, std::size_t index,
                               double cursor, Script& script, double& at)
{
    Entry timing{};
    bool had_duration = false;
    if (when.empty()) {
        timing.at = cursor;
    } else if (const char* reason = parse_when(when.c_str(), cursor, timing, &had_duration)) {
        return reason;
    }
    if (had_duration) return "duration not allowed on wait or mark";
    if (!script.waits.empty() && timing.at < script.waits.back().at) return "time before the preceding wait";
    if (name == "wait") {
        Wait wait{index, timing.at, default_settle, default_timeout, false};
        if (const char* reason = parse_wait_options(value, wait)) return reason;
        script.waits.push_back(wait);
    } else {
        const std::string label = value.empty() ? "mark" + std::to_string(index) : value;
        if (label.size() > 32) return "bad label";
        for (char c : label)
            if (!label_char(c)) return "bad label";
        script.marks.push_back({index, timing.at, script.waits.size(), label});
    }
    at = timing.at;
    return nullptr;
}

// One trimmed, non-empty item. Returns the rejection reason, or nullptr with `entry` filled, or
// `directive` set for base=, wait and mark (which add themselves to `script`; `event_at` is then
// the time of the wait or mark).
inline const char* parse_item(const std::string& item, std::size_t index, double cursor, Script& script, Entry& entry,
                              bool& directive, double& event_at)
{
    directive = false;
    event_at = -1;
    const bool first = index == 1;
    const std::size_t equals = item.find('='), at = item.find('@');
    for (const char* event : {"wait", "mark"}) {
        const std::size_t length = std::strlen(event);
        if (item.compare(0, length, event) != 0 || (item.size() > length && item[length] != '=' && item[length] != '@'))
            continue;
        const std::size_t value_end = at == std::string::npos ? item.size() : at;
        const std::string value = item.size() > length && item[length] == '=' ? item.substr(length + 1, value_end - length - 1) : "";
        directive = true;
        return parse_event(event, value, at == std::string::npos ? "" : item.substr(at), index, cursor, script, event_at);
    }
    if (equals != std::string::npos && (at == std::string::npos || equals < at)) {
        std::string name = item.substr(0, equals);
        while (!name.empty() && blank(name.back())) name.pop_back();
        const char* rest = item.c_str() + equals + 1;
        if (name == "base") {
            std::string value = rest;
            while (!value.empty() && blank(value.front())) value.erase(0, 1);
            if (!first) return "base= must be the first item";
            if (value != "poll" && value != "start") return "unknown base (use poll or start)";
            script.from_process_start = value == "start";
            directive = true;
            return nullptr;
        }
        int axis = -1;
        for (int i = 0; i < axis_count; ++i)
            if (name == axis_names[i]) axis = i;
        if (axis < 0) return "unknown token";
        char* stop = nullptr;
        const double value = std::strtod(rest, &stop);
        if (stop == rest || !std::isfinite(value)) return "bad value";
        const bool trigger = axis == axis_left_trigger || axis == axis_right_trigger;
        if (value > 1 || value < (trigger ? 0 : -1)) return trigger ? "value out of range [0, 1]" : "value out of range [-1, 1]";
        entry.axis = axis;
        entry.mask = 0;
        entry.value = static_cast<float>(value);
        return parse_when(stop, cursor, entry);
    }
    // Button entry: strtoul and strtod accept what the earlier sscanf("%x@%lf") form accepted.
    const char* p = item.c_str();
    char* stop = nullptr;
    errno = 0;
    const unsigned long long mask = std::strtoull(p, &stop, 16);
    if (stop == p || errno == ERANGE || (mask > 0xFFFFFFFFull && mask < 0xFFFFFFFF00000000ull)) return "bad mask";
    entry.axis = -1;
    entry.mask = static_cast<std::uint32_t>(mask);
    entry.value = 0;
    return parse_when(stop, cursor, entry);
}
}  // namespace detail

inline Script parse(const char* text)
{
    Script script;
    if (!text) return script;
    std::size_t index = 0;
    double cursor = 0;
    for (const char* p = text;;) {
        const char* end = p;
        while (*end && *end != ',') ++end;
        const char* begin = p;
        const char* last = end;
        while (begin < last && detail::blank(*begin)) ++begin;
        while (last > begin && detail::blank(last[-1])) --last;
        if (begin < last) {
            const std::string item(begin, last);
            ++index;
            script.items = index;
            Entry entry{};
            bool directive = false;
            double event_at = -1;
            const std::size_t waits = script.waits.size(), marks = script.marks.size();
            const std::size_t timed = script.entries.size() + waits + marks;
            const char* reason = detail::parse_item(item, index, cursor, script, entry, directive, event_at);
            if (!reason && !directive && waits && entry.at < script.waits.back().at) reason = "time before the preceding wait";
            const bool event = script.waits.size() != waits || script.marks.size() != marks;
            if (!reason && (!directive || event) && timed >= max_entries) {
                reason = "over 256 entries";
                script.waits.resize(waits);
                script.marks.resize(marks);
            }
            if (reason) {
                script.rejections.push_back({index, reason, item});
            } else if (!directive) {
                entry.segment = script.waits.size();
                script.entries.push_back(entry);
                cursor = entry.at;
            } else if (event) {
                cursor = event_at;
            }
        }
        if (!*end) break;
        p = end + 1;
    }
    return script;
}

// State at `t` seconds on the script's time base.
inline Output play(const Script& script, double t)
{
    Output out;
    for (const Entry& entry : script.entries) {
        if (!(t >= entry.at && t < entry.at + entry.duration)) continue;
        if (entry.axis < 0) {
            out.buttons |= entry.mask;
        } else {
            out.axes[entry.axis] = entry.value;
            out.active[entry.axis] = true;
        }
    }
    return out;
}

inline double first_start(const Script& script)
{
    double first = script.entries.empty() ? 0 : script.entries.front().at;
    for (const Entry& entry : script.entries) first = entry.at < first ? entry.at : first;
    return first;
}
inline double last_end(const Script& script)
{
    double last = 0;
    for (const Entry& entry : script.entries) last = entry.at + entry.duration > last ? entry.at + entry.duration : last;
    return last;
}

// ---- waits and marks ------------------------------------------------------------------------------
// The picture signal: a coarse grid of mean luma (src/startup_stubs/present_signature.h), with a
// sequence number that grows with every published sample. Two grids differ when at least
// `changed_cells` cells differ by more than `cell_tolerance` levels, so a blinking cursor or a
// small counter does not count as a new screen.
constexpr int signal_cells = 32 * 18;
constexpr int cell_tolerance = 12, changed_cells = 16;
struct Signal {
    bool available = false;  // a presenter has published at least one sample
    std::uint64_t sequence = 0, present = 0;
    std::uint8_t cells[signal_cells] = {};
};
inline int signal_distance(const std::uint8_t* a, const std::uint8_t* b)
{
    int differing = 0;
    for (int i = 0; i < signal_cells; ++i) differing += (a[i] > b[i] ? a[i] - b[i] : b[i] - a[i]) > cell_tolerance;
    return differing;
}

struct Event {
    enum Type { wait_begun, wait_changed, wait_done, wait_timeout, mark } type;
    std::size_t item;      // item index
    double at;             // seconds on the time base
    double elapsed;        // waits: seconds since the wait began
    bool signal;           // a presenter signal was available
    bool stopped;          // wait_timeout: the script stops
    std::uint64_t present; // mark: present number, 0 without a presenter
    std::string label;     // mark
};

// Scripts with waits or marks. Real time `now` is seconds on the script's time base; a wait that
// began at its scheduled time b and completed at c shifts every later item by c - b.
class Timeline {
public:
    explicit Timeline(const Script& script) : script_(script), shift_(script.waits.size() + 1, 0.0), marked_(script.marks.size(), false) {}

    void advance(double now, const Signal& signal, std::vector<Event>& events)
    {
        while (!stopped_ && done_ < script_.waits.size()) {
            const Wait& wait = script_.waits[done_];
            const double begin = wait.at + shift_[done_];
            if (!waiting_) {
                if (now < begin) break;
                waiting_ = true;
                changed_ = false;
                have_reference_ = signal.available;
                if (have_reference_) take(signal);
                events.push_back({Event::wait_begun, wait.index, begin, 0, signal.available, false, 0, {}});
            }
            if (!have_reference_ && signal.available) {
                have_reference_ = true;
                take(signal);
            } else if (have_reference_ && signal.available && signal.sequence != sequence_) {
                sequence_ = signal.sequence;
                if (!changed_ && signal_distance(reference_, signal.cells) >= changed_cells) {
                    changed_ = true;
                    stable_since_ = now;
                    std::copy(signal.cells, signal.cells + signal_cells, last_);
                    events.push_back({Event::wait_changed, wait.index, now, now - begin, true, false, 0, {}});
                } else if (changed_ && signal_distance(last_, signal.cells) >= changed_cells) {
                    stable_since_ = now;
                    std::copy(signal.cells, signal.cells + signal_cells, last_);
                }
            }
            double completed = 0;
            if (changed_ && now - stable_since_ >= wait.settle) {
                completed = now;
                events.push_back({Event::wait_done, wait.index, now, now - begin, true, false, 0, {}});
            } else if (now - begin >= wait.timeout) {
                completed = begin + wait.timeout;
                events.push_back({Event::wait_timeout, wait.index, now, now - begin, have_reference_, wait.stop, 0, {}});
                if (wait.stop) {
                    stopped_ = true;
                    waiting_ = false;
                    break;
                }
            } else {
                break;
            }
            shift_[done_ + 1] = shift_[done_] + (completed - begin);
            ++done_;
            waiting_ = false;
        }
        for (std::size_t i = 0; i < script_.marks.size(); ++i) {
            const Mark& mark = script_.marks[i];
            if (marked_[i] || mark.segment > done_) continue;
            const double at = mark.at + shift_[mark.segment];
            if (now < at) continue;
            marked_[i] = true;
            events.push_back({Event::mark, mark.index, at, 0, signal.available, false, signal.available ? signal.present : 0, mark.label});
        }
    }

    // Same rule as play(), with each item moved by the waits before it; items behind an
    // unfinished or stopping wait are not active.
    Output play(double now) const
    {
        Output out;
        for (const Entry& entry : script_.entries) {
            if (entry.segment > done_) continue;
            const double at = entry.at + shift_[entry.segment];
            if (!(now >= at && now < at + entry.duration)) continue;
            if (entry.axis < 0) {
                out.buttons |= entry.mask;
            } else {
                out.axes[entry.axis] = entry.value;
                out.active[entry.axis] = true;
            }
        }
        return out;
    }

    bool stopped() const { return stopped_; }
    bool waiting() const { return waiting_; }
    std::size_t completed_waits() const { return done_; }
    // End of the last entry once every wait has resolved; negative before that.
    double end() const
    {
        if (!stopped_ && done_ < script_.waits.size()) return -1;
        double last = 0;
        for (const Entry& entry : script_.entries)
            if (entry.segment <= done_) last = std::fmax(last, entry.at + shift_[entry.segment] + entry.duration);
        return last;
    }

private:
    void take(const Signal& signal)
    {
        std::copy(signal.cells, signal.cells + signal_cells, reference_);
        sequence_ = signal.sequence;
    }

    const Script& script_;
    std::vector<double> shift_;
    std::vector<bool> marked_;
    std::size_t done_ = 0;
    bool stopped_ = false, waiting_ = false, changed_ = false, have_reference_ = false;
    double stable_since_ = 0;
    std::uint64_t sequence_ = 0;
    std::uint8_t reference_[signal_cells] = {}, last_[signal_cells] = {};
};

}  // namespace x2w_input_script
