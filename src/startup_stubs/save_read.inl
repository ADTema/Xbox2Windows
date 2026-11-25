// Synchronous operations on the public GDK save provider identity. Every answer comes from the
// store's shared publication lock (save_store.h), so a commit from any process is seen whole or
// not at all within one call.
namespace save_read {
struct BlobInfo { const char* name; std::uint32_t size; };
struct Blob { BlobInfo info; unsigned char* data; };
struct ContainerInfo {
    const char* name;
    const char* display_name;
    std::uint32_t blob_count;
    u64 bytes;
    std::time_t modified;
    bool needs_sync;
};
static_assert(sizeof(Blob) == 24 && offsetof(Blob, data) == 16);
static_assert(sizeof(ContainerInfo) == 48 && offsetof(ContainerInfo, bytes) == 24);
// 0x80830010 for a name with no committed container is not verified against the platform.
constexpr u64 small_buffer = 0x80830007, missing_blob = 0x80830008, missing_container = 0x80830010;

// Name of an open container handle; a closed handle is empty, as for the asynchronous read.
std::string container_name(u64 handle)
{
    if (handle < save_container_handle || handle - save_container_handle >= max_save_handles) return {};
    AcquireSRWLockShared(&save_lock);
    struct Unlock { ~Unlock() { ReleaseSRWLockShared(&save_lock); } } unlock;
    return save_table.container_name(static_cast<std::size_t>(handle - save_container_handle));
}

std::time_t modified_time(const std::string& container)
{
    std::error_code ec;
    const auto file_time = std::filesystem::last_write_time(std::filesystem::path(storage_path()) / "x2w-gamesave" / container, ec);
    if (ec) return std::time(nullptr);
    const auto elapsed = file_time - std::filesystem::file_time_type::clock::now();
    return std::chrono::system_clock::to_time_t(std::chrono::system_clock::now() +
        std::chrono::duration_cast<std::chrono::system_clock::duration>(elapsed));
}

// 13: GetContainerInfo(provider, name, context, callback); 14: EnumerateContainerInfo(provider,
// context, callback). Each container's blob count and bytes come from one list_blobs call.
// Names match case-insensitively, as the store's Windows directories do.
u64 containers(bool exact, u64* args)
{
    const auto callback = reinterpret_cast<bool(WINAPI*)(const ContainerInfo*, void*)>(args[exact ? 3 : 2]);
    auto* context = reinterpret_cast<void*>(args[exact ? 2 : 1]);
    std::string wanted;
    if (args[0] != save_provider_handle || !callback ||
        (exact && (!read_save_name(args[1], wanted) || !x2w_save::valid_name(wanted)))) return e_invalidarg;
    struct Snapshot { std::string name; std::uint32_t count; u64 size; std::time_t modified; };
    std::vector<Snapshot> snapshots;
    const auto store = save_store();
    std::vector<x2w_save::ContainerEntry> entries;
    if (auto s = store.list_containers(entries); s != x2w_save::Status::ok) return save_status(s);
    for (const auto& entry : entries) {
        if (exact && _stricmp(entry.name.c_str(), wanted.c_str()) != 0) continue;
        std::vector<x2w_save::BlobEntry> blobs;
        const auto s = store.list_blobs(entry.name, blobs);
        if (s == x2w_save::Status::not_found) continue;  // deleted since the container list was taken
        if (s != x2w_save::Status::ok) return save_status(s);
        if (blobs.size() > UINT32_MAX) return e_fail;
        u64 bytes = 0;
        for (const auto& blob : blobs) bytes += blob.bytes;
        snapshots.push_back({entry.name, static_cast<std::uint32_t>(blobs.size()), bytes, modified_time(entry.name)});
    }
    if (exact && snapshots.empty()) return missing_container;
    for (const auto& item : snapshots) {
        const char* name = item.name.c_str();
        const ContainerInfo info{name, name, item.count, item.size, item.modified, false};
        if (!callback(&info, context)) break;
    }
    return 0;
}

// 18: EnumerateBlobInfo(container, context, callback), from one list_blobs call.
u64 blobs(u64* args)
{
    const auto name = container_name(args[0]);
    const auto callback = reinterpret_cast<bool(WINAPI*)(const BlobInfo*, void*)>(args[2]);
    auto* context = reinterpret_cast<void*>(args[1]);
    if (name.empty() || !callback) return e_invalidarg;
    std::vector<x2w_save::BlobEntry> entries;
    if (auto s = save_store().list_blobs(name, entries); s != x2w_save::Status::ok) return save_status(s);
    for (const auto& entry : entries) {
        const BlobInfo info{entry.name.c_str(), static_cast<std::uint32_t>(entry.bytes)};
        if (!callback(&info, context)) break;
    }
    return 0;
}

// 20: ReadBlobData(container, names, &count, capacity, records). The requested set (or, with a
// count of 0, every blob) is read under one shared lock with read_blobs (list_blobs for all), and
// the capacity is checked against that snapshot. The destination is written only on success.
u64 read(u64* args)
{
    const auto name = container_name(args[0]);
    const auto* names = reinterpret_cast<const u64*>(args[1]);
    auto* count = reinterpret_cast<std::uint32_t*>(args[2]);
    const auto capacity = static_cast<std::size_t>(args[3]);
    auto* output = reinterpret_cast<Blob*>(args[4]);
    if (name.empty() || !x2w_local::writable(count, sizeof(*count))) return e_invalidarg;
    const auto requested = *count;
    if (requested > capacity / sizeof(Blob)) return small_buffer;
    if (requested && !x2w_local::readable(names, sizeof(*names) * u64{requested})) return e_invalidarg;
    std::vector<std::string> selected;
    for (std::uint32_t i = 0; i < requested; ++i) {
        std::string wanted;
        if (!read_save_name(names[i], wanted) || !x2w_save::valid_name(wanted)) return e_invalidarg;
        selected.push_back(std::move(wanted));
    }
    const auto store = save_store();
    std::vector<std::vector<unsigned char>> data;
    x2w_save::Status status;
    if (requested) {
        status = store.read_blobs(name, selected, data);
    } else {
        std::vector<x2w_save::BlobEntry> all;
        status = store.list_blobs(name, all, &data);
        for (auto& entry : all) selected.push_back(std::move(entry.name));
    }
    if (status != x2w_save::Status::ok) return save_status(status);
    if (data.size() != selected.size() || selected.size() > UINT32_MAX) return e_fail;
    std::size_t bytes = selected.size() * sizeof(Blob);
    for (std::size_t i = 0; i < selected.size(); ++i) {
        const auto extra = selected[i].size() + 1 + data[i].size();
        if (extra > SIZE_MAX - bytes) return small_buffer;
        bytes += extra;
    }
    if (bytes > capacity) return small_buffer;
    if (bytes && (!x2w_local::writable(output, bytes) || args[4] % alignof(Blob))) return e_invalidarg;
    if (!selected.empty()) {
        auto* cursor = reinterpret_cast<unsigned char*>(output + selected.size());
        for (std::size_t i = 0; i < selected.size(); ++i) {
            auto* saved_name = reinterpret_cast<char*>(cursor);
            std::memcpy(cursor, selected[i].c_str(), selected[i].size() + 1);
            cursor += selected[i].size() + 1;
            output[i] = {{saved_name, static_cast<std::uint32_t>(data[i].size())}, cursor};
            if (!data[i].empty()) std::memcpy(cursor, data[i].data(), data[i].size());
            cursor += data[i].size();
        }
    }
    *count = static_cast<std::uint32_t>(selected.size());
    return 0;
}
}

bool save_read_call(int slot, u64* args, u64* result)
{
    try {
        switch (slot) {
        case 13: case 14: *result = save_read::containers(slot == 13, args); break;
        case 18: *result = save_read::blobs(args); break;
        case 20: *result = save_read::read(args); break;
        default: return false;
        }
    } catch (const std::bad_alloc&) {
        *result = e_outofmemory;
    } catch (const std::length_error&) {
        *result = e_outofmemory;
    } catch (const std::filesystem::filesystem_error&) {
        *result = e_fail;
    }
    return true;
}
