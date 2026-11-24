#pragma once

#include <windows.h>
#include <cstddef>
#include <cstdint>

namespace x2w_startup {

// x64 layout from Microsoft's MIT-licensed Xbox-GDK-Samples dstorage_win32.h,
// revision 1f44bdabed6e340170e2c7d1007500e4dff897bb, SimpleDirectStorageCombo.
// The request's options and its address unions are represented by their raw storage.
struct StorageRequest {
    std::uint64_t options;
    void* destination;
    std::uint64_t destination_page_offset;
    std::uint32_t destination_size;
    void* source;
    std::uint64_t file_offset;
    std::uint32_t source_size;
    std::uint32_t intermediate_size;
    std::uint64_t cancellation_tag;
    const char* name;
};

struct StorageErrorRecord {
    std::uint32_t failure_count;
    struct Failure {
        HRESULT result;
        std::uint64_t options;
        void* destination;
        std::uint32_t destination_size;
        wchar_t filename[MAX_PATH];
        std::uint64_t file_offset;
        void* source;
        std::uint32_t source_size;
        std::uint64_t cancellation_tag;
        char name[64];
    } first_failure;
};

static_assert(sizeof(StorageRequest) == 0x48);
static_assert(offsetof(StorageRequest, options) == 0x00);
static_assert(offsetof(StorageRequest, destination) == 0x08);
static_assert(offsetof(StorageRequest, destination_page_offset) == 0x10);
static_assert(offsetof(StorageRequest, destination_size) == 0x18);
static_assert(offsetof(StorageRequest, source) == 0x20);
static_assert(offsetof(StorageRequest, file_offset) == 0x28);
static_assert(offsetof(StorageRequest, source_size) == 0x30);
static_assert(offsetof(StorageRequest, intermediate_size) == 0x34);
static_assert(offsetof(StorageRequest, cancellation_tag) == 0x38);
static_assert(offsetof(StorageRequest, name) == 0x40);

static_assert(sizeof(StorageErrorRecord) == 0x290);
static_assert(sizeof(StorageErrorRecord::Failure) == 0x288);
static_assert(offsetof(StorageErrorRecord, failure_count) == 0x000);
static_assert(offsetof(StorageErrorRecord, first_failure) == 0x008);
static_assert(offsetof(StorageErrorRecord, first_failure.result) == 0x008);
static_assert(offsetof(StorageErrorRecord, first_failure.options) == 0x010);
static_assert(offsetof(StorageErrorRecord, first_failure.destination) == 0x018);
static_assert(offsetof(StorageErrorRecord, first_failure.destination_size) == 0x020);
static_assert(offsetof(StorageErrorRecord, first_failure.filename) == 0x024);
static_assert(offsetof(StorageErrorRecord, first_failure.file_offset) == 0x230);
static_assert(offsetof(StorageErrorRecord, first_failure.source) == 0x238);
static_assert(offsetof(StorageErrorRecord, first_failure.source_size) == 0x240);
static_assert(offsetof(StorageErrorRecord, first_failure.cancellation_tag) == 0x248);
static_assert(offsetof(StorageErrorRecord, first_failure.name) == 0x250);

}  // namespace x2w_startup
