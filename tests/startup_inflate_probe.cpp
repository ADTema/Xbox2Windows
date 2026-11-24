// Input for tests/startup_inflate_check.py: runs the DirectStorage stand-in's zlib decoder
// (src/startup_stubs/inflate.h) on one stream file and writes the decoded bytes.
//
// usage: startup_inflate_probe <stream> <capacity> <output>
// Prints "inflated <size>" and writes the output file when inflate_zlib accepts the stream; prints
// "rejected" otherwise. 16 guard bytes of 0xA5 precede and follow the destination; a write to
// either guard is reported whether or not the decoder accepted the stream.
#include "startup_stubs/inflate.h"

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iterator>
#include <vector>

int main(int argc, char** argv)
{
    if (argc != 4) {
        std::fprintf(stderr, "usage: startup_inflate_probe <stream> <capacity> <output>\n");
        return 2;
    }
    std::ifstream file(argv[1], std::ios::binary);
    if (!file) {
        std::fprintf(stderr, "cannot read %s\n", argv[1]);
        return 2;
    }
    const std::vector<unsigned char> stream{std::istreambuf_iterator<char>(file), std::istreambuf_iterator<char>()};
    const std::size_t capacity = std::strtoull(argv[2], nullptr, 10);
    constexpr std::size_t guard = 16;
    std::vector<unsigned char> buffer(guard + capacity + guard, 0xA5);
    unsigned char* const destination = buffer.data() + guard;
    std::size_t produced = 0;
    const bool ok = x2w_inflate::inflate_zlib(stream.data(), stream.size(), destination, capacity, &produced);
    for (std::size_t i = 0; i < guard; ++i) {
        if (buffer[i] != 0xA5) {
            std::printf("wrote before the destination at -%zu\n", guard - i);
            return 3;
        }
        if (destination[capacity + i] != 0xA5) {
            std::printf("wrote past the destination at +%zu\n", i);
            return 3;
        }
    }
    if (!ok) {
        std::printf("rejected\n");
        return 1;
    }
    std::ofstream out(argv[3], std::ios::binary);
    out.write(reinterpret_cast<const char*>(destination), static_cast<std::streamsize>(produced));
    if (!out) {
        std::fprintf(stderr, "cannot write %s\n", argv[3]);
        return 2;
    }
    std::printf("inflated %zu\n", produced);
    return 0;
}
