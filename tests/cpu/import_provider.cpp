#include <cstdint>

using Word = std::uint64_t;

extern "C" Word mix_args(Word first, Word second, Word* output) {
    output[0] = first;
    output[1] = second;
    output[2] = first - second + 11;
#ifdef ALTER_RETURN
    return output[2] + 1;
#else
    return output[2];
#endif
}
