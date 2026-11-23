// Source-built comparison of XG-style swizzle selection against AMD addrlib (#870).
//
// What is public:
//   - The XG caller sequence (microsoft/DirectXTex Auxiliary/DirectXTexXboxTile.cpp at
//     a8e5dbf42909aeeb9fcf9c2ae399ae3c06737379, MIT): a caller that has no specific mode asks XG for one
//     (XGComputeOptimalSwizzleMode(dimension, format, width, height, arraySize, sampleCount, bindFlags)) and
//     puts it in XG_TEXTURE2D_DESC::SwizzleMode. DirectXTex does not implement selection itself.
//   - AMD addrlib (Mesa src/amd/addrlib at tag mesa-25.1.0, 5c142e46f3f6e752ed745fd48912ebb8fad67145, MIT) is
//     the supported swizzle selector for gfx10.3: Addr2GetPreferredSurfaceSetting and Addr2ComputeSurfaceInfo.
//     The create inputs follow Mesa's ac_addrlib_create, and the selection inputs follow
//     gfx9_get_preferred_swizzle_mode (Mesa 25.1.0, src/amd/common/ac_surface.c, MIT). The 256 B and
//     variable-size blocks are forbidden and the resource lives in the CPU-invisible local heap.
//   - The configuration is Mesa's "navi21" surface-test configuration (src/amd/common/ac_fake_hw_db.h at
//     mesa-25.1.0): family NV (0x8F), external revision 0x28, GB_ADDR_CONFIG 0x40 with NUM_PIPES = 4 and
//     NUM_PKRS = 4, giving 0x444.
//
// These are "AddrLib observations": a match establishes the chosen PC reference behavior only. The
// Xbox-specific XG selection and its inputs still need separate evidence.
//
// Not public: the console's GB_ADDR_CONFIG, XG's own selection rules, the signature of the imported
// XGSuggestSwizzleMode, and XG enum values. The table below records what addrlib selects on the desktop
// Navi 21 configuration. It is a reference to compare an XG provider against, not the console's answer.
//
// Proposed desktop policy (test-only provider, suggest_swizzle_mode): XG-style bind flags map to addrlib
// surface flags. Every resource is a texture. A render target sets color, a depth target sets depth, an
// unordered-access target sets unordered, and a display target sets color and display. A forced-linear
// request forbids every non-linear block.
//
// Returns 0 on pass, 1 on failure, and 77 (skip) when built without addrlib (XBOX2WINDOWS_ADDRLIB_DIR unset).
// With --mutate-linear-fallback the provider under test falls back to linear and the run must fail.
#include <cstdint>
#include <cstdio>

#ifndef XBOX2WINDOWS_HAVE_ADDRLIB
int main()
{
    std::puts("xg_swizzle_select: SKIP (built without addrlib; run tools/fetch_addrlib.py and configure with "
              "-DXBOX2WINDOWS_ADDRLIB_DIR=<mesa>/src/amd/addrlib)");
    return 77;
}
#else
#include <cstdlib>
#include <cstring>
#include <vector>

#include "addrinterface.h"

namespace {
// Mesa ac_fake_hw_db.h "navi21": family_id AMDGPU_FAMILY_NV, chip_external_rev 0x28, gb_addr_config 0x40 with
// NUM_PIPES (bits 0-2) = 4 and NUM_PKRS (bits 8-10) = 4.
constexpr UINT_32 family_nv = 0x8F;
constexpr UINT_32 navi21_rev = 0x28;
constexpr UINT_32 navi21_gb_addr_config = 0x40 | 4u | (4u << 8);
constexpr UINT_32 arctic_island_engine = 0x0000000D;  // CIASICIDGFXENGINE_ARCTICISLAND (addrlib core/addrlib.h)
constexpr const char* addrlib_source = "Mesa 5c142e46f3f6e752ed745fd48912ebb8fad67145 (mesa-25.1.0) src/amd/addrlib (MIT)";

// ---- repo-local mirror of the XG-style request (field names from DirectXTex; values are repo-local) -------
enum Bind : std::uint32_t { srv = 1, rtv = 2, dsv = 4, uav = 8, display = 16 };
enum class Format { rgba8, r8, r16, r32, rgba32f };
struct XgRequest {
    const char* name;
    std::uint32_t width, height, mips;
    Format format;
    std::uint32_t bind;
    bool force_linear;
};

struct FormatInfo { AddrFormat addr; UINT_32 bpp; };
FormatInfo format_info(Format f)
{
    switch (f) {
    case Format::rgba8: return {ADDR_FMT_8_8_8_8, 32};
    case Format::r8: return {ADDR_FMT_8, 8};
    case Format::r16: return {ADDR_FMT_16, 16};
    case Format::r32: return {ADDR_FMT_32, 32};
    case Format::rgba32f: return {ADDR_FMT_32_32_32_32, 128};
    }
    return {ADDR_FMT_INVALID, 0};
}

const char* mode_name(AddrSwizzleMode m)
{
    switch (m) {
    case ADDR_SW_LINEAR: return "LINEAR";
    case ADDR_SW_4KB_S: return "4KB_S";
    case ADDR_SW_4KB_D: return "4KB_D";
    case ADDR_SW_4KB_S_X: return "4KB_S_X";
    case ADDR_SW_4KB_D_X: return "4KB_D_X";
    case ADDR_SW_4KB_R_X: return "4KB_R_X";
    case ADDR_SW_4KB_Z_X: return "4KB_Z_X";
    case ADDR_SW_64KB_S: return "64KB_S";
    case ADDR_SW_64KB_D: return "64KB_D";
    case ADDR_SW_64KB_S_T: return "64KB_S_T";
    case ADDR_SW_64KB_D_T: return "64KB_D_T";
    case ADDR_SW_64KB_S_X: return "64KB_S_X";
    case ADDR_SW_64KB_D_X: return "64KB_D_X";
    case ADDR_SW_64KB_R_X: return "64KB_R_X";
    case ADDR_SW_64KB_Z_X: return "64KB_Z_X";
    default: return "other";
    }
}

VOID* ADDR_API alloc_sys_mem(const ADDR_ALLOCSYSMEM_INPUT* in) { return std::malloc(in->sizeInBytes); }
ADDR_E_RETURNCODE ADDR_API free_sys_mem(const ADDR_FREESYSMEM_INPUT* in)
{
    std::free(in->pVirtAddr);
    return ADDR_OK;
}

ADDR_HANDLE create_navi21()
{
    ADDR_CREATE_INPUT in{};
    ADDR_CREATE_OUTPUT out{};
    in.size = sizeof in;
    out.size = sizeof out;
    in.chipEngine = arctic_island_engine;
    in.chipFamily = family_nv;
    in.chipRevision = navi21_rev;
    in.callbacks.allocSysMem = alloc_sys_mem;
    in.callbacks.freeSysMem = free_sys_mem;
    in.regValue.gbAddrConfig = navi21_gb_addr_config;
    return AddrCreate(&in, &out) == ADDR_OK ? out.hLib : nullptr;
}

ADDR2_SURFACE_FLAGS surface_flags(std::uint32_t bind)
{
    ADDR2_SURFACE_FLAGS f{};
    f.texture = 1;
    if (bind & (rtv | display)) f.color = 1;
    if (bind & display) f.display = 1;
    if (bind & dsv) f.depth = 1;
    if (bind & uav) f.unordered = 1;
    return f;
}

struct Selection {
    ADDR_E_RETURNCODE rc = ADDR_ERROR;
    AddrSwizzleMode mode = ADDR_SW_MAX_TYPE;
    UINT_32 base_align = 0;
    UINT_64 surf_size = 0;
};

// Test-only XG-style provider: the proposed desktop mapping of an XG request onto addrlib's selector, followed
// by Addr2ComputeSurfaceInfo for the chosen mode (base alignment and size show the block the mode implies).
Selection suggest_swizzle_mode(ADDR_HANDLE lib, const XgRequest& r, bool forbid_linear = false)
{
    const FormatInfo fi = format_info(r.format);
    ADDR2_GET_PREFERRED_SURF_SETTING_INPUT in{};
    ADDR2_GET_PREFERRED_SURF_SETTING_OUTPUT out{};
    in.size = sizeof in;
    out.size = sizeof out;
    in.flags = surface_flags(r.bind);
    in.resourceType = ADDR_RSRC_TEX_2D;
    in.format = fi.addr;
    in.resourceLoction = ADDR_RSRC_LOC_INVIS;
    in.forbiddenBlock.micro = 1;
    in.forbiddenBlock.var = 1;
    if (r.force_linear) {
        in.forbiddenBlock.macroThin4KB = in.forbiddenBlock.macroThick4KB = 1;
        in.forbiddenBlock.macroThin64KB = in.forbiddenBlock.macroThick64KB = 1;
    }
    if (forbid_linear) in.forbiddenBlock.linear = 1;
    in.bpp = fi.bpp;
    in.width = r.width;
    in.height = r.height;
    in.numSlices = 1;
    in.numMipLevels = r.mips;
    in.numSamples = 1;
    in.numFrags = 1;
    Selection s;
    s.rc = Addr2GetPreferredSurfaceSetting(lib, &in, &out);
    if (s.rc != ADDR_OK) return s;
    s.mode = out.swizzleMode;

    ADDR2_COMPUTE_SURFACE_INFO_INPUT si{};
    ADDR2_COMPUTE_SURFACE_INFO_OUTPUT so{};
    si.size = sizeof si;
    so.size = sizeof so;
    si.flags = in.flags;
    si.swizzleMode = s.mode;
    si.resourceType = ADDR_RSRC_TEX_2D;
    si.format = fi.addr;
    si.bpp = fi.bpp;
    si.width = r.width;
    si.height = r.height;
    si.numSlices = 1;
    si.numMipLevels = r.mips;
    si.numSamples = 1;
    si.numFrags = 1;
    s.rc = Addr2ComputeSurfaceInfo(lib, &si, &so);
    s.base_align = so.baseAlign;
    s.surf_size = so.surfSize;
    return s;
}

unsigned failures = 0;
void expect(bool ok, const char* what)
{
    std::printf("%s %s\n", ok ? "ok" : "FAIL", what);
    failures += !ok;
}

using Provider = Selection (*)(ADDR_HANDLE, const XgRequest&);
Selection reference_provider(ADDR_HANDLE lib, const XgRequest& r) { return suggest_swizzle_mode(lib, r); }
// A provider that silently falls back to linear: it asks addrlib with every non-linear block forbidden.
Selection linear_fallback_provider(ADDR_HANDLE lib, const XgRequest& r)
{
    XgRequest linear = r;
    linear.force_linear = true;
    return suggest_swizzle_mode(lib, linear);
}

// The reference table: addrlib's selection for each request on the Navi 21 configuration above, recorded
// from this build (AddrLib observations, not console values).
struct Row {
    XgRequest request;
    AddrSwizzleMode mode;
    UINT_32 base_align;
};
// clang-format off
const Row rows[] = {
    {{"128x128 RGBA8 8 mips, shader resource",            128,  128,  8, Format::rgba8,   srv,           false}, ADDR_SW_64KB_R_X, 65536},
    {{"1024x1024 RGBA8 11 mips, shader resource",         1024, 1024, 11, Format::rgba8,  srv,           false}, ADDR_SW_64KB_R_X, 65536},
    {{"64x64 R8 1 mip, shader resource",                  64,   64,   1, Format::r8,      srv,           false}, ADDR_SW_4KB_D_X, 4096},
    {{"16x16 RGBA8 1 mip, shader resource",               16,   16,   1, Format::rgba8,   srv,           false}, ADDR_SW_4KB_D_X, 4096},
    {{"4096x1 R32 1 mip, shader resource",                4096, 1,    1, Format::r32,     srv,           false}, ADDR_SW_LINEAR, 256},
    {{"1920x1080 RGBA8 1 mip, render target",             1920, 1080, 1, Format::rgba8,   srv | rtv,     false}, ADDR_SW_64KB_R_X, 65536},
    {{"1920x1080 RGBA8 1 mip, display render target",     1920, 1080, 1, Format::rgba8,   rtv | display, false}, ADDR_SW_64KB_R_X, 65536},
    {{"1920x1080 R32 1 mip, depth target",                1920, 1080, 1, Format::r32,     srv | dsv,     false}, ADDR_SW_64KB_Z_X, 65536},
    {{"512x512 RGBA32F 10 mips, unordered access",        512,  512,  10, Format::rgba32f, srv | uav,    false}, ADDR_SW_64KB_R_X, 65536},
    {{"2048x2048 R16 1 mip, unordered access",            2048, 2048, 1, Format::r16,     srv | uav,     false}, ADDR_SW_64KB_R_X, 65536},
};
// clang-format on

bool matches(const Selection& s, const Row& row)
{
    return s.rc == ADDR_OK && s.mode == row.mode && s.base_align == row.base_align;
}

// The one comparison every provider goes through: the number of reference rows it does not reproduce.
unsigned table_mismatches(ADDR_HANDLE lib, Provider provider)
{
    unsigned n = 0;
    for (const Row& row : rows) n += !matches(provider(lib, row.request), row);
    return n;
}

int run(bool mutate_linear_fallback)
{
    std::printf("AddrLib observations from %s\n", addrlib_source);
    std::printf("  AddrCreate: chipEngine 0x%X chipFamily 0x%X chipRevision 0x%X gbAddrConfig 0x%X createFlags 0\n",
                arctic_island_engine, family_nv, navi21_rev, navi21_gb_addr_config);
    std::puts("  selection inputs: ADDR_RSRC_TEX_2D, ADDR_RSRC_LOC_INVIS, forbiddenBlock micro+var, 1 slice, 1 sample");
    ADDR_HANDLE lib = create_navi21();
    expect(lib != nullptr, "AddrCreate for family NV rev 0x28, GB_ADDR_CONFIG 0x444 (Mesa navi21 test config)");
    if (!lib) return 1;

    // 1. The provider under test against the reference table, through the shared comparison.
    const Provider under_test = mutate_linear_fallback ? linear_fallback_provider : reference_provider;
    if (mutate_linear_fallback) std::puts("  mutation: the provider under test is the linear-fallback provider");
    unsigned tiled_rows = 0;
    std::vector<AddrSwizzleMode> chosen;
    for (const Row& row : rows) {
        const Selection s = under_test(lib, row.request);
        chosen.push_back(s.mode);
        const FormatInfo fi = format_info(row.request.format);
        std::printf("  %-50s fmt 0x%X bpp %u flags 0x%X mips %u -> status %d %s (%u) baseAlign %u surfSize %llu\n",
                    row.request.name, unsigned(fi.addr), fi.bpp, surface_flags(row.request.bind).value, row.request.mips,
                    int(s.rc), mode_name(s.mode), unsigned(s.mode), s.base_align, (unsigned long long)s.surf_size);
        char line[200];
        std::snprintf(line, sizeof line, "%s selects %s with %u-byte base alignment", row.request.name,
                      mode_name(row.mode), row.base_align);
        expect(matches(s, row), line);
        tiled_rows += row.mode != ADDR_SW_LINEAR;
    }
    expect(table_mismatches(lib, under_test) == 0, "the provider under test matches every reference row");

    // 2. Linear-fallback control: a provider that sends each request to addrlib with only the linear block allowed
    //    goes through the same comparison and must be caught. It agrees only on the reference's own LINEAR row;
    //    the 8 tiled colour rows get LINEAR and the depth target is refused.
    const unsigned fallback_mismatches = table_mismatches(lib, linear_fallback_provider);
    std::printf("  tiled reference rows %u, linear-fallback provider mismatches %u of %zu\n", tiled_rows,
                fallback_mismatches, sizeof rows / sizeof rows[0]);
    expect(tiled_rows == 9 && fallback_mismatches == tiled_rows,
           "linear-fallback control: the comparison rejects the addrlib-backed linear-fallback provider on all 9 tiled rows");

    // 3. Forced-linear control: with only the linear block allowed, every colour request selects LINEAR and the
    //    depth target, which has no linear mode, is refused rather than given a tiled mode.
    bool all_linear = true;
    for (const Row& row : rows) {
        XgRequest r = row.request;
        r.force_linear = true;
        const Selection s = suggest_swizzle_mode(lib, r);
        std::printf("  forced linear: %-50s -> status %d %s\n", row.request.name, int(s.rc), mode_name(s.mode));
        if (r.bind & dsv)
            all_linear &= s.rc == ADDR_INVALIDPARAMS;
        else
            all_linear &= s.rc == ADDR_OK && s.mode == ADDR_SW_LINEAR;
    }
    expect(all_linear,
           "forced-linear control: 9 colour requests select LINEAR, the depth target is refused (ADDR_INVALIDPARAMS)");

    // 4. Tiled-request control: forbidding the linear block never yields LINEAR, including for the
    //    one-row texture.
    bool none_linear = true;
    for (const Row& row : rows) {
        const Selection s = suggest_swizzle_mode(lib, row.request, true);
        none_linear &= s.rc == ADDR_OK && s.mode != ADDR_SW_LINEAR;
        if (s.mode == ADDR_SW_LINEAR) std::printf("  %s still LINEAR with linear forbidden\n", row.request.name);
    }
    expect(none_linear, "tiled-request control: no request selects LINEAR once the linear block is forbidden");

    // 5. Tight-pitch control: an explicit linear pitch below the required pitch is refused.
    {
        auto linear_pitch = [&](UINT_32 pitch, UINT_32* out_pitch) {
            ADDR2_COMPUTE_SURFACE_INFO_INPUT si{};
            ADDR2_COMPUTE_SURFACE_INFO_OUTPUT so{};
            si.size = sizeof si;
            so.size = sizeof so;
            si.flags.texture = 1;
            si.swizzleMode = ADDR_SW_LINEAR;
            si.resourceType = ADDR_RSRC_TEX_2D;
            si.format = ADDR_FMT_8_8_8_8;
            si.bpp = 32;
            si.width = 100;
            si.height = 64;
            si.numSlices = 1;
            si.numMipLevels = 1;
            si.numSamples = 1;
            si.numFrags = 1;
            si.pitchInElement = pitch;
            const ADDR_E_RETURNCODE rc = Addr2ComputeSurfaceInfo(lib, &si, &so);
            if (out_pitch) *out_pitch = so.pitch;
            return rc;
        };
        UINT_32 required = 0, accepted = 0;
        const ADDR_E_RETURNCODE base = linear_pitch(0, &required);
        std::printf("  100x64 RGBA8 linear: required pitch %u elements\n", required);
        expect(base == ADDR_OK && required >= 100, "linear 100x64 RGBA8 reports a pitch of at least 100 elements");
        expect(linear_pitch(required, &accepted) == ADDR_OK && accepted == required,
               "an explicit pitch equal to the required pitch is accepted");
        expect(linear_pitch(required + 1, nullptr) == ADDR_INVALIDPARAMS, "a misaligned explicit pitch is refused");
        expect(linear_pitch(64, nullptr) == ADDR_INVALIDPARAMS,
               "tight-pitch control: an explicit pitch of 64 elements for a 100-wide texture is refused");
    }

    // 6. Mismatched-input control: the reference does not give one answer for every request.
    bool varied = false;
    for (std::size_t i = 1; i < chosen.size(); ++i) varied |= chosen[i] != chosen[0];
    expect(varied, "mismatched-input control: the table's requests do not all select the same mode");

    AddrDestroy(lib);
    return failures ? 1 : 0;
}
}  // namespace

// --mutate-linear-fallback swaps the provider under test for the linear-fallback provider. CTest registers that run
// as xg_swizzle_select_mutation with WILL_FAIL, so the comparison must reject it.
int main(int argc, char** argv)
{
    const bool mutate = argc == 2 && std::strcmp(argv[1], "--mutate-linear-fallback") == 0;
    if (argc > 2 || (argc == 2 && !mutate)) {
        std::puts("usage: xg_swizzle_select_check [--mutate-linear-fallback]");
        return 2;
    }
    const int result = run(mutate);
    std::printf("xg_swizzle_select: %s\n", result == 0 ? "PASS" : "FAIL");
    return result;
}
#endif
