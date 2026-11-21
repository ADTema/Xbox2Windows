// Map an x64 PE image without LoadLibrary and bind its imports through a host resolver.
// Scope: DIR64 relocations, ordinary imports by name or ordinal, section protections and
// .pdata registration. Images with TLS, delay imports or an entry point are rejected.
// Header fields are checked against the file or SizeOfImage before they are used.
#include <windows.h>

#include <cstdint>
#include <cstdio>
#include <cstring>
#include <new>
#include <string>
#include <vector>

// Keep in step with STATUS in tests/cpu/native_map_check.py.
enum MapStatus : std::uint32_t {
    MAP_OK = 0,
    MAP_IO = 1,
    MAP_FORMAT = 2,
    MAP_MEMORY = 3,
    MAP_RELOCATION = 4,
    MAP_UNRESOLVED_IMPORT = 5,
    MAP_UNSUPPORTED = 6,
    MAP_PROTECT = 7,
    MAP_FUNCTION_TABLE = 8,
};

// Returns the address bound to one import, or null to reject it. name is null for an ordinal.
using Resolver = void*(__cdecl*)(const char* dll, const char* name, std::uint32_t ordinal);

namespace {

constexpr std::uint64_t MAX_FILE = 1ull << 30;

struct Failure {
    std::uint32_t* status;
    char* detail;
    std::size_t capacity;

    template <typename... Args>
    void* operator()(MapStatus code, const char* format, Args... args) const {
        if (status) *status = code;
        if (detail && capacity) std::snprintf(detail, capacity, format, args...);
        return nullptr;
    }
};

bool inside(std::uint64_t offset, std::uint64_t size, std::uint64_t limit) {
    return offset <= limit && size <= limit - offset;
}

const IMAGE_DATA_DIRECTORY& directory(const IMAGE_NT_HEADERS64* nt, int index) {
    static const IMAGE_DATA_DIRECTORY empty{};
    return nt->OptionalHeader.NumberOfRvaAndSizes > static_cast<DWORD>(index)
        ? nt->OptionalHeader.DataDirectory[index] : empty;
}

// A view of the mapped image that rejects any range outside SizeOfImage.
struct Image {
    std::uint8_t* base;
    std::uint64_t size;

    template <typename T>
    T* at(std::uint64_t rva, std::uint64_t count = 1) const {
        return inside(rva, sizeof(T) * count, size) ? reinterpret_cast<T*>(base + rva) : nullptr;
    }

    const char* string(std::uint64_t rva) const {
        if (rva >= size) return nullptr;
        const auto* start = base + rva;
        const bool terminated = std::memchr(start, 0, static_cast<std::size_t>(size - rva)) != nullptr;
        return terminated ? reinterpret_cast<const char*>(start) : nullptr;
    }

    const IMAGE_NT_HEADERS64* headers() const {
        const auto* dos = reinterpret_cast<const IMAGE_DOS_HEADER*>(base);
        return reinterpret_cast<const IMAGE_NT_HEADERS64*>(base + dos->e_lfanew);
    }
};

DWORD protection(DWORD flags) {
    const bool exec = flags & IMAGE_SCN_MEM_EXECUTE, write = flags & IMAGE_SCN_MEM_WRITE;
    const bool read = flags & IMAGE_SCN_MEM_READ;
    if (exec) return write ? PAGE_EXECUTE_READWRITE : read ? PAGE_EXECUTE_READ : PAGE_EXECUTE;
    return write ? PAGE_READWRITE : read ? PAGE_READONLY : PAGE_NOACCESS;
}

bool read_file(const wchar_t* path, std::vector<std::uint8_t>& raw) {
    HANDLE file = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ, nullptr, OPEN_EXISTING, 0, nullptr);
    if (file == INVALID_HANDLE_VALUE) return false;
    LARGE_INTEGER length{};
    DWORD read = 0;
    bool ok = GetFileSizeEx(file, &length) && length.QuadPart > 0
        && static_cast<std::uint64_t>(length.QuadPart) <= MAX_FILE;
    if (ok) {
        try {
            raw.resize(static_cast<std::size_t>(length.QuadPart));
        } catch (const std::bad_alloc&) {
            ok = false;
        }
    }
    ok = ok && ReadFile(file, raw.data(), static_cast<DWORD>(raw.size()), &read, nullptr) && read == raw.size();
    CloseHandle(file);
    return ok;
}

}  // namespace

extern "C" __declspec(dllexport) void* pe_map_image(const wchar_t* path, Resolver resolve,
                                                    std::uint32_t* status, char* detail,
                                                    std::size_t capacity) {
    const Failure fail{status, detail, capacity};
    if (status) *status = MAP_OK;
    if (detail && capacity) detail[0] = '\0';

    std::vector<std::uint8_t> raw;
    if (!read_file(path, raw)) return fail(MAP_IO, "cannot read image");
    if (raw.size() < sizeof(IMAGE_DOS_HEADER)) return fail(MAP_FORMAT, "truncated DOS header");
    const auto* dos = reinterpret_cast<const IMAGE_DOS_HEADER*>(raw.data());
    if (dos->e_magic != IMAGE_DOS_SIGNATURE || dos->e_lfanew < 0
        || !inside(dos->e_lfanew, sizeof(IMAGE_NT_HEADERS64), raw.size()))
        return fail(MAP_FORMAT, "bad DOS header");
    const auto* nt = reinterpret_cast<const IMAGE_NT_HEADERS64*>(raw.data() + dos->e_lfanew);
    const auto& opt = nt->OptionalHeader;
    if (nt->Signature != IMAGE_NT_SIGNATURE || nt->FileHeader.Machine != IMAGE_FILE_MACHINE_AMD64
        || opt.Magic != IMAGE_NT_OPTIONAL_HDR64_MAGIC)
        return fail(MAP_FORMAT, "not an x64 PE32+ image");
    const auto* sections = IMAGE_FIRST_SECTION(nt);
    const std::uint64_t table_end =
        reinterpret_cast<const std::uint8_t*>(sections + nt->FileHeader.NumberOfSections) - raw.data();
    if (nt->FileHeader.SizeOfOptionalHeader < sizeof(IMAGE_OPTIONAL_HEADER64)
        || dos->e_lfanew + sizeof(IMAGE_NT_HEADERS64) > opt.SizeOfHeaders || table_end > opt.SizeOfHeaders
        || opt.SizeOfHeaders > opt.SizeOfImage || opt.SizeOfHeaders > raw.size())
        return fail(MAP_FORMAT, "section table outside headers");

    if (directory(nt, IMAGE_DIRECTORY_ENTRY_TLS).Size) return fail(MAP_UNSUPPORTED, "TLS directory");
    if (directory(nt, IMAGE_DIRECTORY_ENTRY_DELAY_IMPORT).Size) return fail(MAP_UNSUPPORTED, "delay imports");
    if (opt.AddressOfEntryPoint) return fail(MAP_UNSUPPORTED, "entry point");

    // Map away from the preferred base so the relocation path always runs.
    auto allocate = [&] {
        return static_cast<std::uint8_t*>(
            VirtualAlloc(nullptr, opt.SizeOfImage, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE));
    };
    auto* base = allocate();
    if (base == reinterpret_cast<std::uint8_t*>(opt.ImageBase)) {
        auto* other = allocate();
        VirtualFree(base, 0, MEM_RELEASE);
        base = other;
    }
    if (!base) return fail(MAP_MEMORY, "cannot reserve image");
    const Image image{base, opt.SizeOfImage};
    auto release = [&](void* result) {
        VirtualFree(base, 0, MEM_RELEASE);
        return result;
    };

    std::memcpy(base, raw.data(), opt.SizeOfHeaders);
    for (WORD i = 0; i < nt->FileHeader.NumberOfSections; ++i) {
        const auto& s = sections[i];
        const DWORD span = s.Misc.VirtualSize ? s.Misc.VirtualSize : s.SizeOfRawData;
        const DWORD copy = s.SizeOfRawData < span ? s.SizeOfRawData : span;
        if (s.VirtualAddress < opt.SizeOfHeaders || !inside(s.VirtualAddress, span, opt.SizeOfImage)
            || !inside(s.PointerToRawData, copy, raw.size()))
            return release(fail(MAP_FORMAT, "section %.8s outside image", reinterpret_cast<const char*>(s.Name)));
        std::memcpy(base + s.VirtualAddress, raw.data() + s.PointerToRawData, copy);
    }

    // Writes below (relocations, IAT) must land in sections, never in the headers or in the
    // directory that drives them, so validated structures cannot change while they are walked.
    auto writable = [&](std::uint64_t rva, const IMAGE_DATA_DIRECTORY& driver) {
        const std::uint64_t start = driver.VirtualAddress, end = start + driver.Size;
        const bool overlaps = rva + 8 > start && rva < end;
        return rva >= opt.SizeOfHeaders && image.at<std::uint64_t>(rva) && !overlaps;
    };

    const auto delta = reinterpret_cast<std::uint64_t>(base) - opt.ImageBase;
    const auto& relocs = directory(nt, IMAGE_DIRECTORY_ENTRY_BASERELOC);
    if (nt->FileHeader.Characteristics & IMAGE_FILE_RELOCS_STRIPPED)
        return release(fail(MAP_RELOCATION, "relocations stripped"));
    if (!inside(relocs.VirtualAddress, relocs.Size, opt.SizeOfImage))
        return release(fail(MAP_RELOCATION, "relocation directory outside image"));
    for (std::uint64_t offset = 0; offset + sizeof(IMAGE_BASE_RELOCATION) <= relocs.Size;) {
        const auto* block = image.at<IMAGE_BASE_RELOCATION>(relocs.VirtualAddress + offset);
        const DWORD page = block->VirtualAddress, length = block->SizeOfBlock;
        if (length < sizeof(IMAGE_BASE_RELOCATION) || length > relocs.Size - offset)
            return release(fail(MAP_RELOCATION, "bad relocation block"));
        const auto* entry = reinterpret_cast<const WORD*>(block + 1);
        const DWORD count = (length - sizeof(IMAGE_BASE_RELOCATION)) / sizeof(WORD);
        for (DWORD k = 0; k < count; ++k) {
            const WORD type = entry[k] >> 12;
            const std::uint64_t target = page + std::uint64_t{entry[k] & 0xfffu};
            if (type == IMAGE_REL_BASED_ABSOLUTE) continue;
            if (type != IMAGE_REL_BASED_DIR64 || !writable(target, relocs))
                return release(fail(MAP_RELOCATION, "unsupported relocation at RVA %#llx",
                                    static_cast<unsigned long long>(target)));
            *image.at<std::uint64_t>(target) += delta;
        }
        offset += length;
    }

    const auto& imports = directory(nt, IMAGE_DIRECTORY_ENTRY_IMPORT);
    if (imports.Size) {
        const auto descriptors = imports.Size / sizeof(IMAGE_IMPORT_DESCRIPTOR);
        if (!descriptors) return release(fail(MAP_FORMAT, "import directory smaller than one descriptor"));
        if (!resolve) return release(fail(MAP_UNRESOLVED_IMPORT, "imports present without a resolver"));
        const auto* desc = image.at<IMAGE_IMPORT_DESCRIPTOR>(imports.VirtualAddress, descriptors);
        if (!desc) return release(fail(MAP_FORMAT, "import directory outside image"));
        for (std::uint64_t d = 0; d < descriptors && desc[d].Name; ++d) {
            const char* name_in_image = image.string(desc[d].Name);
            if (!name_in_image) return release(fail(MAP_FORMAT, "import DLL name outside image"));
            // Keep a copy: an IAT write below may legally overlap the string in the image.
            const std::string dll_name(name_in_image);
            const char* dll = dll_name.c_str();
            const DWORD lookup = desc[d].OriginalFirstThunk ? desc[d].OriginalFirstThunk : desc[d].FirstThunk;
            for (std::uint64_t i = 0;; ++i) {
                const auto* word = image.at<std::uint64_t>(lookup + 8 * i);
                if (!word || !writable(desc[d].FirstThunk + 8 * i, imports))
                    return release(fail(MAP_FORMAT, "import thunk for %s outside image", dll));
                if (!*word) break;
                const bool by_ordinal = IMAGE_SNAP_BY_ORDINAL64(*word);
                const auto ordinal = by_ordinal ? static_cast<std::uint32_t>(IMAGE_ORDINAL64(*word)) : 0u;
                const auto* hint = by_ordinal ? nullptr : image.at<WORD>(*word & 0x7fffffff);
                const char* name = hint ? image.string((*word & 0x7fffffff) + sizeof(WORD)) : nullptr;
                if (!by_ordinal && !name) return release(fail(MAP_FORMAT, "import name for %s outside image", dll));
                void* bound = resolve(dll, name, ordinal);
                if (!bound && name) return release(fail(MAP_UNRESOLVED_IMPORT, "unresolved import %s!%s", dll, name));
                if (!bound)
                    return release(fail(MAP_UNRESOLVED_IMPORT, "unresolved import %s!#%u", dll,
                                        static_cast<unsigned>(ordinal)));
                *image.at<std::uint64_t>(desc[d].FirstThunk + 8 * i) = reinterpret_cast<std::uint64_t>(bound);
            }
        }
    }

    // Record the actual base in the mapped headers, as the Windows loader does.
    reinterpret_cast<IMAGE_NT_HEADERS64*>(base + dos->e_lfanew)->OptionalHeader.ImageBase =
        reinterpret_cast<std::uint64_t>(base);
    DWORD old = 0;
    if (!VirtualProtect(base, opt.SizeOfHeaders, PAGE_READONLY, &old))
        return release(fail(MAP_PROTECT, "cannot protect headers"));
    for (WORD i = 0; i < nt->FileHeader.NumberOfSections; ++i) {
        const auto& s = sections[i];
        const DWORD span = s.Misc.VirtualSize ? s.Misc.VirtualSize : s.SizeOfRawData;
        if (span && !VirtualProtect(base + s.VirtualAddress, span, protection(s.Characteristics), &old))
            return release(fail(MAP_PROTECT, "cannot protect section %.8s", reinterpret_cast<const char*>(s.Name)));
    }
    FlushInstructionCache(GetCurrentProcess(), base, opt.SizeOfImage);

    const auto& pdata = directory(nt, IMAGE_DIRECTORY_ENTRY_EXCEPTION);
    if (pdata.Size) {
        auto* table = image.at<RUNTIME_FUNCTION>(pdata.VirtualAddress, pdata.Size / sizeof(RUNTIME_FUNCTION));
        if (!table || !RtlAddFunctionTable(table, pdata.Size / sizeof(RUNTIME_FUNCTION),
                                           reinterpret_cast<DWORD64>(base)))
            return release(fail(MAP_FUNCTION_TABLE, "cannot register .pdata"));
    }
    return base;
}

// Only valid for a base returned by pe_map_image, whose headers were validated and are read-only.
extern "C" __declspec(dllexport) void* pe_map_export(void* mapped, const char* name) {
    const auto* nt = Image{static_cast<std::uint8_t*>(mapped), 0}.headers();
    const Image image{static_cast<std::uint8_t*>(mapped), nt->OptionalHeader.SizeOfImage};
    const auto& exports = directory(nt, IMAGE_DIRECTORY_ENTRY_EXPORT);
    const auto* dir = exports.Size ? image.at<IMAGE_EXPORT_DIRECTORY>(exports.VirtualAddress) : nullptr;
    if (!dir) return nullptr;
    const auto* names = image.at<DWORD>(dir->AddressOfNames, dir->NumberOfNames);
    const auto* ordinals = image.at<WORD>(dir->AddressOfNameOrdinals, dir->NumberOfNames);
    const auto* functions = image.at<DWORD>(dir->AddressOfFunctions, dir->NumberOfFunctions);
    if (!names || !ordinals || !functions) return nullptr;
    for (DWORD i = 0; i < dir->NumberOfNames; ++i) {
        const char* exported = image.string(names[i]);
        if (!exported || std::strcmp(exported, name) != 0) continue;
        if (ordinals[i] >= dir->NumberOfFunctions) return nullptr;
        const DWORD rva = functions[ordinals[i]];
        // Forwarded exports point back into the export directory; they are not code here.
        if (rva >= exports.VirtualAddress && rva - exports.VirtualAddress < exports.Size) return nullptr;
        // An empty slot (RVA 0) names no code; returning the image base would be wrong.
        return rva && rva < image.size ? image.base + rva : nullptr;
    }
    return nullptr;
}

extern "C" __declspec(dllexport) void pe_map_release(void* mapped) {
    auto* base = static_cast<std::uint8_t*>(mapped);
    const auto& pdata = directory(Image{base, 0}.headers(), IMAGE_DIRECTORY_ENTRY_EXCEPTION);
    if (pdata.Size) RtlDeleteFunctionTable(reinterpret_cast<PRUNTIME_FUNCTION>(base + pdata.VirtualAddress));
    VirtualFree(base, 0, MEM_RELEASE);
}
