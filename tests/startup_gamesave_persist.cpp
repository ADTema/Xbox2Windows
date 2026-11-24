// Experimental (docs/startup-runtime.md): the on-disk store behind the game-save stand-in
// (src/startup_stubs/save_store.h, called by the XGameSave slots of runtime_proxy.cpp) keeps
// containers and blobs between processes. The test writes in one process and starts itself again
// (argument "read") to read the bytes back in a second process. Synthetic data only.
#include "../src/startup_stubs/save_store.h"

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <ctime>
#include <string>

namespace fs = std::filesystem;
using x2w_save::Status;

namespace {
constexpr int exit_missing = 10, exit_mismatch = 11;

std::vector<unsigned char> payload(unsigned seed, std::size_t size)
{
    std::vector<unsigned char> bytes(size);
    for (std::size_t i = 0; i < size; ++i) bytes[i] = static_cast<unsigned char>(seed * 31 + i * 7 + 3);
    return bytes;
}

// Second process: exit 0 when the blob holds payload(seed, size), else a code that says why.
int reader(const char* root, const char* seed_text)
{
    const unsigned seed = static_cast<unsigned>(std::strtoul(seed_text, nullptr, 10));
    std::vector<unsigned char> bytes;
    const Status status = x2w_save::Store(root).read_blob("slot-a", "profile.dat", bytes);
    if (status == Status::not_found) return exit_missing;
    return status == Status::ok && bytes == payload(seed, 300) ? 0 : exit_mismatch;
}

int run_reader(const std::string& self, const fs::path& root, unsigned seed)
{
    std::string command = "\"" + self + "\" read \"" + root.string() + "\" " + std::to_string(seed);
#ifdef _WIN32
    command = "\"" + command + "\"";  // cmd.exe drops the outer quotes
#endif
    const int code = std::system(command.c_str());
#ifdef _WIN32
    return code;
#else
    return code == -1 ? -1 : (code >> 8) & 0xff;
#endif
}

int failures;
void expect(bool ok, const char* what)
{
    if (!ok) {
        std::fprintf(stderr, "FAIL: %s\n", what);
        ++failures;
    }
}
}  // namespace

int main(int argc, char** argv)
{
    if (argc == 4 && std::strcmp(argv[1], "read") == 0) return reader(argv[2], argv[3]);
    if (argc != 1) return 2;

    std::error_code ec;
    const fs::path root = fs::temp_directory_path(ec) / ("x2w-gamesave-persist-" + std::to_string(std::rand()) + "-" + std::to_string(std::time(nullptr)));
    fs::remove_all(root, ec);
    const x2w_save::Store store(root / "store");
    const std::string self = argv[0];
    const std::vector<unsigned char> first = payload(1, 300), second = payload(2, 300);

    // Negative control: before anything is written, the second process must see nothing. If this
    // returned 0 the reader would be passing for the wrong reason.
    expect(run_reader(self, root / "store", 1) == exit_missing, "reader finds a blob before any write");

    // Write in this process, read in another.
    expect(store.create_container("slot-a") == Status::ok, "create container");
    expect(store.create_container("slot-a") == Status::ok, "an existing container directory counts as success");
    expect(fs::is_directory(root / "store" / "slot-a"), "one directory per container");
    expect(store.write_blob("slot-a", "profile.dat", first.data(), first.size()) == Status::ok, "write blob");
    expect(fs::is_regular_file(root / "store" / "slot-a" / "profile.dat"), "one file per blob");
    expect(run_reader(self, root / "store", 1) == 0, "second process reads the bytes back");
    // Negative control: the reader's comparison can fail.
    expect(run_reader(self, root / "store", 2) == exit_mismatch, "reader rejects different bytes");

    // Overwrite replaces the bytes and leaves no side file.
    expect(store.write_blob("slot-a", "profile.dat", second.data(), second.size()) == Status::ok, "overwrite blob");
    expect(run_reader(self, root / "store", 2) == 0, "second process reads the overwritten bytes");
    expect(run_reader(self, root / "store", 1) == exit_mismatch, "old bytes are gone");
    std::size_t entries = 0;
    for (const auto& item : fs::directory_iterator(root / "store" / "slot-a", ec)) { (void)item; ++entries; }
    expect(entries == 1, "no side file is left behind");

    // Empty blob, missing blob, missing container.
    std::vector<unsigned char> bytes;
    expect(store.write_blob("slot-a", "empty", nullptr, 0) == Status::ok && store.read_blob("slot-a", "empty", bytes) == Status::ok && bytes.empty(), "empty blob round trip");
    expect(store.read_blob("slot-a", "absent", bytes) == Status::not_found, "missing blob is not_found");
    expect(store.read_blob("slot-none", "profile.dat", bytes) == Status::not_found, "missing container is not_found");

    // Names that could leave the store are refused and nothing is created outside it.
    const char* bad[] = {"", "..", ".", "../x", "a/b", "a\\b", "/abs", "\\abs", "C:x", "C:\\x", "a..b", "x.", "NUL", "com1.txt", "a\nb", "n*", "a.x2w-part"};
    for (const char* name : bad) {
        expect(!x2w_save::valid_name(name), name);
        expect(store.create_container(name) == Status::bad_name, "bad container name refused");
        expect(store.write_blob("slot-a", name, first.data(), first.size()) == Status::bad_name, "bad blob name refused");
        expect(store.write_blob(name, "profile.dat", first.data(), first.size()) == Status::bad_name, "write below bad container refused");
        expect(store.read_blob("slot-a", name, bytes) == Status::bad_name, "bad blob read refused");
        expect(store.delete_blob("slot-a", name) == Status::bad_name, "bad blob delete refused");
        expect(store.delete_container(name) == Status::bad_name, "bad container delete refused");
    }
    expect(!x2w_save::valid_name(std::string(x2w_save::max_name_bytes + 1, 'a')), "name length is capped");
    expect(store.write_blob("slot-a", "big", first.data(), x2w_save::max_blob_bytes + 1) == Status::too_large, "size is capped");
    expect(!fs::exists(root / "x") && !fs::exists(root / "abs"), "nothing outside the store root");

    // Delete a blob, then the container.
    expect(store.delete_blob("slot-a", "profile.dat") == Status::ok, "delete blob");
    expect(store.delete_blob("slot-a", "profile.dat") == Status::not_found, "second delete finds nothing");
    expect(run_reader(self, root / "store", 2) == exit_missing, "second process no longer finds the deleted blob");
    expect(store.delete_container("slot-a") == Status::ok && !fs::exists(root / "store" / "slot-a"), "delete container removes its directory");
    expect(fs::exists(root / "store"), "the store root itself stays");

    fs::remove_all(root, ec);
    if (failures) return 1;
    std::puts("startup_gamesave_persist: ok");
    return 0;
}
