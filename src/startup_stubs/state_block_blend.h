// Experimental (docs/startup-runtime.md): the blend state of a pipeline created through device
// slot 57, read from its state block A (#1216).
//
// State block A holds the eight CB_BLENDn_CONTROL words at +0xD0, one per render target (measured
// on #1216). They are decoded with cb_blend.h. CB_TARGET_MASK has not been located, so every
// target keeps all four channels.
#pragma once

#include "cb_blend.h"

#include <cstddef>
#include <cstdint>
#include <cstring>

namespace x2w_startup {
constexpr std::size_t state_block_blend_offset = 0xD0;

// Fills out from state block A. Returns false, leaving out alone, when the block is too short or
// the decoder refuses render target 0; reason then names the cause. A refused word of another
// target leaves that target unblended, and refused_targets has its bit set.
inline bool state_block_blend(const unsigned char* block, std::size_t bytes, bool alpha_factor_supported, D3D12_BLEND_DESC* out,
                              const char** reason = nullptr, unsigned* refused_targets = nullptr)
{
    const char* ignored = nullptr;
    const char*& why = reason ? *reason : ignored;
    why = nullptr;
    if (refused_targets) *refused_targets = 0;
    if (!block || bytes < state_block_blend_offset + 8 * sizeof(std::uint32_t)) {
        why = "state block A shorter than the blend words";
        return false;
    }
    D3D12_BLEND_DESC blend{};
    blend.IndependentBlendEnable = TRUE;
    for (unsigned target = 0; target < 8; ++target) {
        std::uint32_t word;
        std::memcpy(&word, block + state_block_blend_offset + 4 * target, sizeof(word));
        const x2w_cb_blend::Decoded decoded = x2w_cb_blend::decode(word, 0xF, alpha_factor_supported);
        if (decoded.ok) {
            blend.RenderTarget[target] = decoded.desc;
            continue;
        }
        if (target == 0) {
            why = decoded.reason;
            return false;
        }
        if (refused_targets) *refused_targets |= 1u << target;
        blend.RenderTarget[target] = x2w_cb_blend::decode(0, 0xF, alpha_factor_supported).desc;  // unblended, all channels
    }
    *out = blend;
    return true;
}
}  // namespace x2w_startup
