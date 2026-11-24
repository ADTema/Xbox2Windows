// Experimental (docs/startup-runtime.md): on-disk store behind the local game-save stand-in.
// One directory per container, one file per blob, all below one root folder. Plain standard C++
// with no Windows types, so the logic can be compiled and tested on its own.
#pragma once

#include <atomic>
#include <cctype>
#include <chrono>
#include <cstddef>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <mutex>
#include <string>
#include <string_view>
#include <system_error>
#include <thread>
#include <vector>

namespace x2w_save {

namespace fs = std::filesystem;

enum class Status { ok, bad_name, too_large, not_found, io_error };

constexpr std::size_t max_name_bytes = 128;
constexpr std::size_t max_blob_bytes = std::size_t{64} << 20;
constexpr std::string_view part_suffix = ".x2w-part";

// A name becomes one path component. Anything that could address another place is refused: empty,
// too long, separators, drive letters and streams (':'), control characters, characters Windows
// does not allow in file names, "..", a trailing dot or space, device names, and the suffix the
// store uses for files it is still writing.
inline bool valid_name(std::string_view name) noexcept
{
    if (name.empty() || name.size() > max_name_bytes) return false;
    for (const unsigned char c : name) {
        if (c < 0x20 || c == 0x7f) return false;
        if (std::string_view("/\\:*?\"<>|").find(static_cast<char>(c)) != std::string_view::npos) return false;
    }
    if (name.find("..") != std::string_view::npos) return false;
    if (name.back() == '.' || name.back() == ' ' || name.front() == ' ') return false;
    // Case-insensitive: on Windows "X.X2W-PART" and "X.x2w-part" are the same file.
    if (name.size() >= part_suffix.size()) {
        const std::string_view tail = name.substr(name.size() - part_suffix.size());
        bool same = true;
        for (std::size_t i = 0; i < tail.size() && same; ++i)
            same = std::tolower(static_cast<unsigned char>(tail[i])) == part_suffix[i];
        if (same) return false;
    }
    std::string stem(name.substr(0, name.find('.')));
    for (char& c : stem) c = static_cast<char>(c >= 'a' && c <= 'z' ? c - 'a' + 'A' : c);
    while (!stem.empty() && stem.back() == ' ') stem.pop_back();
    for (const char* device : {"CON", "PRN", "AUX", "NUL"})
        if (stem == device) return false;
    if (stem.size() == 4 && (stem.compare(0, 3, "COM") == 0 || stem.compare(0, 3, "LPT") == 0) && stem[3] >= '0' && stem[3] <= '9') return false;
    return true;
}

// A staging file name nobody can predict or share: process-wide counter plus a clock reading.
inline std::string unique_part_name()
{
    static std::atomic<unsigned long long> counter{0};
    const auto ticks = std::chrono::steady_clock::now().time_since_epoch().count();
    return "." + std::to_string(counter.fetch_add(1) + 1) + "-" + std::to_string(static_cast<long long>(ticks)) + std::string(part_suffix);
}

// Container handles of the game-save stand-in: a fixed table indexed by the low bits of the handle,
// with a reference count per entry so closed containers give their slot back. The caller holds the
// lock; no Windows types here so it can be tested on its own.
class ContainerTable {
public:
    static constexpr std::size_t capacity = 64;
    // Index of the container with this name (opened again or new), or -1 when the table is full.
    long open(const std::string& name)
    {
        for (std::size_t i = 0; i < capacity; ++i)
            if (names_[i] == name && !name.empty()) {
                ++refs_[i];
                return static_cast<long>(i);
            }
        for (std::size_t i = 0; i < capacity; ++i)
            if (names_[i].empty()) {
                names_[i] = name;
                refs_[i] = 1;
                return static_cast<long>(i);
            }
        return -1;
    }
    void close(std::size_t index)
    {
        if (index >= capacity) return;
        if (refs_[index] > 0) --refs_[index];
        reclaim(index);
    }
    // Index of the update slot, or -1 (container not open, or no free update slot).
    long begin_update(std::size_t container)
    {
        if (container >= capacity || names_[container].empty()) return -1;
        for (std::size_t i = 0; i < capacity; ++i)
            if (!updates_[i]) {
                updates_[i] = static_cast<int>(container) + 1;
                return static_cast<long>(i);
            }
        return -1;
    }
    void end_update(std::size_t update)
    {
        if (update >= capacity || !updates_[update]) return;
        const std::size_t container = static_cast<std::size_t>(updates_[update] - 1);
        updates_[update] = 0;
        reclaim(container);
    }
    // Name of the container behind an open update, or empty.
    std::string update_container(std::size_t update) const
    {
        return update < capacity && updates_[update] ? names_[updates_[update] - 1] : std::string();
    }
    std::size_t in_use() const
    {
        std::size_t used = 0;
        for (const std::string& name : names_) used += !name.empty();
        return used;
    }

private:
    void reclaim(std::size_t index)
    {
        if (refs_[index] > 0) return;
        for (const int update : updates_)
            if (update == static_cast<int>(index) + 1) return;
        names_[index].clear();
    }
    std::string names_[capacity];
    int refs_[capacity]{};
    int updates_[capacity]{};  // container index + 1 of an open update, 0 = free
};

class Store {
public:
    explicit Store(fs::path root) : root_(std::move(root)) {}

    // An existing container directory counts as success.
    Status create_container(std::string_view container) const
    {
        const fs::path dir = container_dir(container);
        if (dir.empty()) return Status::bad_name;
        std::error_code ec;
        if (fs::is_symlink(fs::symlink_status(dir, ec))) return Status::bad_name;
        if (fs::is_directory(dir, ec)) return Status::ok;
        fs::create_directories(dir, ec);
        return !ec && fs::is_directory(dir, ec) ? Status::ok : Status::io_error;
    }

    Status delete_container(std::string_view container) const
    {
        const fs::path dir = container_dir(container);
        if (dir.empty()) return Status::bad_name;
        std::error_code ec;
        const fs::file_status state = fs::symlink_status(dir, ec);
        if (!fs::exists(state)) return Status::not_found;
        if (!fs::is_directory(state) || fs::is_symlink(state)) return Status::bad_name;
        fs::remove_all(dir, ec);
        return ec ? Status::io_error : Status::ok;
    }

    // Writes to a side file and renames it over the blob, so a reader sees the old or the new bytes.
    Status write_blob(std::string_view container, std::string_view blob, const void* data, std::size_t size) const
    {
        if (size > max_blob_bytes) return Status::too_large;
        if (size && !data) return Status::io_error;
        const fs::path file = blob_file(container, blob);
        if (file.empty()) return Status::bad_name;
        if (const Status made = create_container(container); made != Status::ok) return made;
        std::error_code ec;
        if (fs::is_symlink(fs::symlink_status(file, ec))) return Status::bad_name;
        // A staging file of its own for every write: two writers never share one, and an old link
        // left at a guessable name is never opened. An existing entry at the name is refused.
        fs::path part = file;
        part += unique_part_name();
        if (fs::symlink_status(part, ec).type() != fs::file_type::not_found) return Status::io_error;
        {
            std::ofstream out(part, std::ios::binary | std::ios::trunc);
            if (!out) return Status::io_error;
            if (size) out.write(static_cast<const char*>(data), static_cast<std::streamsize>(size));
            if (!out.flush()) {
                out.close();
                fs::remove(part, ec);
                return Status::io_error;
            }
        }
        // Replacing a file another writer is replacing at the same moment can fail on Windows
        // (access denied or a sharing violation instead of last-writer-wins), so the rename is
        // serialised in this process and, for another process, retried a few times.
        static std::mutex commit;
        const std::lock_guard<std::mutex> guard(commit);
        for (int attempt = 0;; ++attempt) {
            fs::rename(part, file, ec);
            if (!ec) return Status::ok;
            if (attempt == 8) break;
            std::this_thread::sleep_for(std::chrono::milliseconds(5 << (attempt < 4 ? attempt : 4)));
        }
        fs::remove(part, ec);
        return Status::io_error;
    }

    // not_found only when the blob is truly absent; any other failure is io_error.
    Status read_blob(std::string_view container, std::string_view blob, std::vector<unsigned char>& bytes) const
    {
        const fs::path file = blob_file(container, blob);
        if (file.empty()) return Status::bad_name;
        std::error_code ec;
        const fs::file_status state = fs::symlink_status(file, ec);
        if (!fs::exists(state)) return Status::not_found;
        if (!fs::is_regular_file(state)) return Status::io_error;
        const std::uintmax_t size = fs::file_size(file, ec);
        if (ec || size > max_blob_bytes) return ec ? Status::io_error : Status::too_large;
        std::ifstream in(file, std::ios::binary);
        if (!in) return Status::io_error;
        bytes.assign(static_cast<std::size_t>(size), 0);
        if (size && !in.read(reinterpret_cast<char*>(bytes.data()), static_cast<std::streamsize>(size))) return Status::io_error;
        return Status::ok;
    }

    Status delete_blob(std::string_view container, std::string_view blob) const
    {
        const fs::path file = blob_file(container, blob);
        if (file.empty()) return Status::bad_name;
        std::error_code ec;
        const fs::file_status state = fs::symlink_status(file, ec);
        if (!fs::exists(state)) return Status::not_found;
        if (!fs::is_regular_file(state)) return Status::bad_name;
        return fs::remove(file, ec) && !ec ? Status::ok : Status::io_error;
    }

private:
    // Empty path when the name is not acceptable. The result is always root/<container>.
    fs::path container_dir(std::string_view container) const
    {
        if (!valid_name(container)) return {};
        return root_ / std::string(container);
    }
    fs::path blob_file(std::string_view container, std::string_view blob) const
    {
        if (!valid_name(blob)) return {};
        const fs::path dir = container_dir(container);
        return dir.empty() ? fs::path{} : dir / std::string(blob);
    }

    fs::path root_;
};

}  // namespace x2w_save
