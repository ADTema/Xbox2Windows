// Shader-side lookup of title GPU addresses (host side: src/era_title_va.h).
// On the console a shader can load through a 64-bit address read from memory, because a
// graphics allocation's CPU pointer is also its GPU address. On desktop each aliased
// allocation is a separate buffer, so the shader finds the range holding the address and
// loads through that range's buffer at the byte offset. Ranges come from
// era_title_va::shader_ranges: sorted by title address, non-overlapping, each shorter than
// 4 GiB, with `slot` naming the descriptor of the buffer that aliases the range.
// Addresses are uint2 values: x is the low 32 bits, y the high 32 bits.
#ifndef TITLE_VA_LOOKUP_HLSLI
#define TITLE_VA_LOOKUP_HLSLI

struct TitleRange {
    uint2 begin;
    uint2 end;  // exclusive
    uint slot;
    uint reserved;
};

bool TitleAddressLess(uint2 a, uint2 b)
{
    return a.y < b.y || (a.y == b.y && a.x < b.x);
}

// Returns false when no range holds `address`. Otherwise sets the range's slot and the byte
// offset of `address` inside it.
bool TitleLookup(StructuredBuffer<TitleRange> ranges, uint count, uint2 address,
                 out uint slot, out uint offset)
{
    slot = 0;
    offset = 0;
    uint low = 0;
    uint high = count;
    // First range whose begin is above the address.
    while (low < high) {
        const uint middle = (low + high) / 2;
        if (TitleAddressLess(address, ranges[middle].begin)) {
            high = middle;
        } else {
            low = middle + 1;
        }
    }
    if (low == 0) {
        return false;
    }
    const TitleRange range = ranges[low - 1];
    if (!TitleAddressLess(address, range.end)) {
        return false;
    }
    // address - begin is below 4 GiB, so the low words' difference modulo 2^32 is exact.
    offset = address.x - range.begin.x;
    slot = range.slot;
    return true;
}

#endif
