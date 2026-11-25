// Experimental (docs/startup-runtime.md): the synchronous save read (provider slot 20) against a
// writer in a second process. Built twice, like startup_gamesave_publish, from the generated copies
// of save_store.h and file_lock.h (see CMakeLists.txt): the writer stops at each step of a two-blob
// publication. A reader must then get one whole generation, or a failure with its destination
// untouched; the copy whose lock is a no-op must be caught. The test starts itself again for the
// writer and the readers; handshakes are files, every wait has a deadline. Synthetic data only.
#include "../src/startup_stubs/runtime_proxy.cpp"

#include <chrono>
#include <fstream>
#include <thread>

namespace {
namespace fs = std::filesystem;
const GUID provider{0x704c3f58,0xe629,0x4cc2,{0xb1,0x97,0x30,0x51,0x1b,0x99,0x6f,0xe2}};
const GUID interface_id{0x1bfff3af,0xf14a,0x40a3,{0x8e,0x35,0x9a,0xda,0x90,0x65,0x93,0xf9}};
constexpr int exit_old = 20, exit_new = 21, exit_mixed = 22, exit_busy = 23, exit_other = 24, exit_touched = 25;
constexpr auto handshake_deadline = std::chrono::seconds(30);
constexpr std::size_t blob_bytes = 4096;

HRESULT WINAPI fixture_query(const GUID*, const GUID*, void** out)
{
    static void* token;
    *out = &token;
    return S_OK;
}
template<class T> u64 address(T* p) { return reinterpret_cast<u64>(p); }
u64 call(void* object, int slot, u64 a = 0, u64 b = 0, u64 c = 0, u64 d = 0, u64 e = 0)
{
    return reinterpret_cast<Method>((*reinterpret_cast<void***>(object))[slot])(object, a, b, c, d, e, 0, 0, 0, 0, 0, 0);
}

bool wait_for(const fs::path& file)
{
    const auto deadline = std::chrono::steady_clock::now() + handshake_deadline;
    std::error_code ec;
    while (!fs::exists(file, ec)) {
        if (std::chrono::steady_clock::now() > deadline) return false;
        std::this_thread::sleep_for(std::chrono::milliseconds(1));
    }
    return true;
}
void touch(const fs::path& file) { std::ofstream(file, std::ios::binary) << "x"; }

// Two blobs per generation; the bytes tell which generation a blob belongs to.
std::vector<unsigned char> bytes_of(unsigned generation, unsigned blob)
{
    std::vector<unsigned char> bytes(blob_bytes);
    for (std::size_t i = 0; i < bytes.size(); ++i) bytes[i] = static_cast<unsigned char>(generation * 53 + blob * 17 + i * 7 + 1);
    return bytes;
}
std::vector<x2w_save::Action> generation(unsigned number)
{
    return {x2w_save::Action{false, "a.dat", bytes_of(number, 0)}, x2w_save::Action{false, "b.dat", bytes_of(number, 1)}};
}

// Reader process: one slot 20 call through the provider vtable, by name or (mode "all") for every
// blob. The exit code says what it saw.
int reader(const char* sync, const char* mode)
{
    const bool all = std::strcmp(mode, "all") == 0;
    touch(fs::path(sync) / (std::string("started-") + mode));
    fill_slots(std::make_index_sequence<max_slots>{});
    real_query = fixture_query;
    void* object = nullptr;
    u64 handle = 0, container = 0;
    if (FAILED(proxy_query(&provider, &interface_id, &object)) || call(object, 3, local_user_handle, address("fixture"), 0, address(&handle)) ||
        call(object, 16, handle, address("slot-p"), address(&container))) return exit_other;
    const char* names[]{"a.dat", "b.dat"};
    std::uint32_t count = all ? 0 : 2;
    std::vector<u64> words(2048, 0xcdcdcdcdcdcdcdcdull);
    const auto unchanged = words;
    const u64 result = call(object, 20, container, all ? 0 : address(names), address(&count), words.size() * sizeof(u64), address(words.data()));
    std::fprintf(stderr, "reader (%s): slot 20 -> 0x%llx, count %u\n", mode, static_cast<unsigned long long>(result), count);
    if (result == save_read::missing_blob) return exit_mixed;  // a blob of the generation was missing
    if (result) return words == unchanged && result == e_fail ? exit_busy : (words == unchanged ? exit_other : exit_touched);
    if (count != 2) return exit_mixed;
    const auto* records = reinterpret_cast<const save_read::Blob*>(words.data());
    std::vector<unsigned char> seen[2];
    for (std::uint32_t i = 0; i < count; ++i) {
        const int blob = std::strcmp(records[i].info.name, "a.dat") == 0 ? 0 : std::strcmp(records[i].info.name, "b.dat") == 0 ? 1 : -1;
        if (blob < 0) return exit_other;
        seen[blob].assign(records[i].data, records[i].data + records[i].info.size);
    }
    if (seen[0] == bytes_of(1, 0) && seen[1] == bytes_of(1, 1)) return exit_old;
    if (seen[0] == bytes_of(2, 0) && seen[1] == bytes_of(2, 1)) return exit_new;
    return exit_mixed;
}

fs::path pause_dir;  // set in the writer process only
unsigned pause_point = ~0u;

// Writer process: commits generation 2 and stops at the chosen point until the parent creates "go".
int writer(const char* root, const char* sync, const char* point)
{
    pause_dir = sync;
    pause_point = static_cast<unsigned>(std::atoi(point));
    return x2w_save::Store(root).commit("slot-p", generation(2)) == x2w_save::Status::ok ? 0 : 1;
}

int run_child(const std::string& self, const std::string& arguments)
{
    const std::string command = "\"\"" + self + "\" " + arguments + "\"";  // cmd.exe drops the outer quotes
    return std::system(command.c_str());
}
std::string quoted(const fs::path& path) { return "\"" + path.string() + "\""; }

int failures;
void expect(bool ok, const std::string& what)
{
    if (!ok) {
        std::fprintf(stderr, "FAIL: %s\n", what.c_str());
        ++failures;
    }
}

// The writer stops at `point` of the publication (0: first old blob moved aside, 1: first new blob
// in, 2: second old blob moved aside, 3: second new blob in). A reader during the pause waits for the
// store's lock timeout and fails with its buffer untouched; a reader that is still waiting when the
// writer goes on sees the whole new generation.
void paused_publication(const std::string& self, const fs::path& base, unsigned point, const char* mode)
{
    const std::string label = std::string("pause point ") + std::to_string(point) + " (" + mode + ")";
    const fs::path dir = base / ("point-" + std::to_string(point) + "-" + mode);
    const fs::path sync = dir / "sync", root = dir / "store" / "x2w-gamesave";
    fs::create_directories(sync);
    SetEnvironmentVariableW(L"X2W_STORAGE_PATH", (dir / "store").wstring().c_str());
    const x2w_save::Store store(root);
    expect(store.create_container("slot-p") == x2w_save::Status::ok && store.commit("slot-p", generation(1)) == x2w_save::Status::ok, label + ": fixture generation 1");
    const std::string read_args = std::string("read ") + quoted(sync) + " " + mode;
    expect(run_child(self, read_args) == exit_old, label + ": a second process reads generation 1");

    int writer_code = -1, waiting = -1;
    std::thread write_thread([&] { writer_code = run_child(self, "write " + quoted(root) + " " + quoted(sync) + " " + std::to_string(point)); });
    const bool paused = wait_for(sync / "paused");
    expect(paused, label + ": the writer reached its pause point");
    if (paused) {
        const int during = run_child(self, read_args);
        if (during == exit_mixed) std::fprintf(stderr, "FAIL: reader saw a mixed generation at %s\n", label.c_str());
        expect(during == exit_busy, label + ": a reader during the publication fails with its destination untouched (exit " +
            std::to_string(during) + ", expected 23: 20 old, 21 new, 22 mixed, 23 busy, 24 other, 25 destination changed)");
        std::error_code ec;
        fs::remove(sync / (std::string("started-") + mode), ec);
        std::thread read_thread([&] { waiting = run_child(self, read_args); });
        expect(wait_for(sync / (std::string("started-") + mode)), label + ": the waiting reader started");
        std::this_thread::sleep_for(std::chrono::milliseconds(200));
        touch(sync / "go");
        read_thread.join();
    } else {
        touch(sync / "go");
    }
    write_thread.join();
    expect(writer_code == 0, label + ": the writer commits");
    expect(waiting == exit_new, label + ": a reader that waited sees the whole new generation (exit " + std::to_string(waiting) + ")");
    expect(run_child(self, read_args) == exit_new, label + ": after the publication a reader sees generation 2");
}
}  // namespace

// Called by the generated copy of save_store.h at each step of a publication (see CMakeLists.txt).
void x2w_save_test_point(unsigned point)
{
    if (pause_dir.empty() || point != pause_point) return;
    touch(pause_dir / "paused");
    if (!wait_for(pause_dir / "go")) std::_Exit(3);
}

int main(int argc, char** argv)
{
    SetEnvironmentVariableA("X2W_FAKE_USER", "1");
    if (argc == 4 && std::strcmp(argv[1], "read") == 0) return reader(argv[2], argv[3]);
    if (argc == 5 && std::strcmp(argv[1], "write") == 0) return writer(argv[2], argv[3], argv[4]);
    if (argc != 1) return 2;
    std::error_code ec;
    const fs::path base = fs::temp_directory_path(ec) / ("x2w-gamesave-read-publish-" + std::to_string(GetCurrentProcessId()) + "-" +
        std::to_string(std::chrono::steady_clock::now().time_since_epoch().count()));
    const std::string self = argv[0];
    for (unsigned point = 0; point < 4; ++point) paused_publication(self, base, point, "named");
    for (unsigned point : {1u, 2u}) paused_publication(self, base, point, "all");
    fs::remove_all(base, ec);
    if (failures) return 1;
    std::puts("startup_gamesave_read_publish: ok");
    return 0;
}
