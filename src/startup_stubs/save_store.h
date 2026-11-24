// Experimental (docs/startup-runtime.md): on-disk store behind the local game-save stand-in.
// One directory per container, one file per blob, all below one root folder. Plain standard C++
// with no Windows types, so the logic can be compiled and tested on its own.
#pragma once

#include <cstddef>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <string>
#include <string_view>
#include <system_error>
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
    if (name.size() >= part_suffix.size() && name.substr(name.size() - part_suffix.size()) == part_suffix) return false;
    std::string stem(name.substr(0, name.find('.')));
    for (char& c : stem) c = static_cast<char>(c >= 'a' && c <= 'z' ? c - 'a' + 'A' : c);
    while (!stem.empty() && stem.back() == ' ') stem.pop_back();
    for (const char* device : {"CON", "PRN", "AUX", "NUL"})
        if (stem == device) return false;
    if (stem.size() == 4 && (stem.compare(0, 3, "COM") == 0 || stem.compare(0, 3, "LPT") == 0) && stem[3] >= '0' && stem[3] <= '9') return false;
    return true;
}

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
        fs::path part = file;
        part += std::string(part_suffix);
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
        fs::rename(part, file, ec);
        if (ec) {
            fs::remove(part, ec);
            return Status::io_error;
        }
        return Status::ok;
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
