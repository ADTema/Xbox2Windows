# Experiment notes and reproduction commands

Run commands from the repository root. Start with the [project overview](../README.md) and [contribution guide](../CONTRIBUTING.md). Package-specific observations below used local inputs. Community regression tests use fixtures built from this repository.

## Local tools

For optional static dependency inspection, build Microsoft's pinned version of xbdepends from PowerShell with x64 Visual Studio Build Tools, CMake and the Windows SDK.

```powershell
.\tools\setup-xbdepends.ps1
```

Load the toolchain in each new development shell, then configure, build and test.

```powershell
.\tools\dev.ps1
cmake --preset dev
cmake --build --preset dev
ctest --preset dev
```

The tests exercise desktop D3D12 root signature serialization and deserialization. Use the resulting test binary to try the static inspection tools.

```powershell
xbdepends -v .\out\build\dev\d3d12_sdk_check.exe
dumpbin /imports .\out\build\dev\d3d12_sdk_check.exe
```

Build outputs and downloaded tool sources live under `out/`. [Microsoft xbdepends documentation](https://learn.microsoft.com/en-us/samples/microsoft/xbox-gdk-samples/xbdepends/)

## Package integrity

For a local build with a multi-file v1 torrent and `layout*.xml`, run the offline verification with Python 3.9 or newer. Substitute your local directory name.

```powershell
python tools/verify_build.py "game-files/<build-directory>"
```

The script verifies SHA-1 pieces across file boundaries in torrent order and compares layout destinations separately with disk and torrent entries. The report is `out/integrity/<build-directory>.json`. Exit code 0 means the payload passed piece verification. `layout.absent_from_disk` lists missing layout entries separately.

## PE dependency baseline

The scanner uses x64 Windows, Python 3.11 or newer and pefile. Set up an isolated environment once.

```powershell
python -m venv out/pe-env
.\out\pe-env\Scripts\python.exe -m pip install pefile==2024.8.26
```

Capture a DLL-only baseline. When an EXE becomes available, write a separate report and compare it with the saved baseline.

```powershell
$pePython = '.\out\pe-env\Scripts\python.exe'
$buildDir = 'game-files/<build-directory>'
& $pePython tools/pe_inventory.py $buildDir --output out/dependencies/pre-exe.json
# Run the next command after adding the main executable.
& $pePython tools/pe_inventory.py $buildDir --baseline out/dependencies/pre-exe.json --output out/dependencies/with-exe.json
```

`summary` gives counts. `unresolved_edges` lists requested exports missing from both the package and the host. Each `imports` entry identifies the caller, import mechanism, provider and symbol. `#N` denotes an ordinal. `images` includes architecture, SHA-256, export names, ordinals and forwarders. `diff` distinguishes new caller relationships from dependencies seen for the first time in the build.

The desktop comparison reads System32 export tables and resolves providers using the host API-set v6 map. Name and ordinal matches include forwarded exports. Final forwarding destinations, parameters, runtime lookups and object methods need separate checks. [Wine API-set lookup](https://github.com/wine-mirror/wine/blob/master/dlls/ntdll/loader.c)

## Heap and process memory

`src/era_heap.cpp` implements ordinary desktop heap requests for source-built callers. The alignment exponent uses attribute bits 24–28 following SlimEra's Xbox One ERA definition. The fixture accepts ordinary heap requests with all other attribute bits clear. Scarlett attribute encodings, error conventions and graphics memory semantics remain open questions. [SlimEra attributes](https://github.com/XWine1/SlimEra/blob/main/era.h#L105-L137) · [SlimEra default heap](https://github.com/XWine1/SlimEra/blob/main/kernelx.cpp#L600-L657)

| CTest case | Inputs and checks |
|---|---|
| `era_heap_allocation` | Allocate 257 bytes using six alignment exponents. Check alignment of at least 16 bytes and the requested alignment, initial zeroing, writes and release. Debug builds also compare CRT heap snapshots. |
| `era_heap_failure` | Zero size, excessive size, graphics memory, nondefault pages and reserved bits return a null pointer under the fixture's error policy. |
| `era_heap_concurrency` | Four threads run 100 rounds each. They hold simultaneous allocations, write distinct values, compare every byte and release the memory. |

`desktop_memory_query` supplies Windows observations for `XMemVirtualQuery` and `XMemGetWorkingSetStatistics`. The test reserves memory, commits and writes 1,024 pages, checks the read-only/writable boundary, then decommits. It verifies residency of a locked page and records working set, peak working set and private commit at three points. Values vary between runs. Scarlett structure layout, units and accounting scope remain unconfirmed. [Windows working sets](https://learn.microsoft.com/en-us/windows/win32/memory/working-set)

## Offscreen rendering and readback

`offscreen_hardware` selects a high-performance adapter. `offscreen_warp` selects Microsoft's software rasterizer. Both draw the same DXC-compiled triangle to a 64×64 RGBA8 texture. After GPU completion the test reads the texture using its row pitch and compares colors and coverage pixel by pixel. Outputs are `triangle_hardware.bmp` and `triangle_warp.bmp` in the build directory. `ctest --preset dev -V` reports the adapter, driver, debug layer and pixel differences. Error or corruption messages from an available debug layer fail the test.

The original test machine had Windows Graphics Tools installed. A second build in `out/build/agility` used Microsoft Agility SDK 1.620.2. Set `-DOFFSCREEN_AGILITY_620_DIR=<directory containing the x64 SDK DLLs>` to reproduce it. This configuration verifies debug interface activation. [Agility SDK package](https://www.nuget.org/packages/Microsoft.Direct3D.D3D12/1.620.2)

## Static executable intake

By default, the intake tool locates the Scarlett entry in the sole build's `MicrosoftGame.Config`. It accepts the layout path or a separate candidate file and opens the game files for reading only.

```powershell
.\out\pe-env\Scripts\python.exe -B tools/intake_exe.py
# Inspect a separately supplied candidate.
.\out\pe-env\Scripts\python.exe -B tools/intake_exe.py "E:\incoming\game_scarlett_master.exe"
```

Each run writes a new JSON report in `out/intake/`. Exit codes are 3 for a missing layout executable, 2 for an input or inspection failure and 0 for completed inspection. The report links the previous verification time, torrent SHA-256, install chunks and baseline summary. The inspected torrent omitted the EXE. The 13,345 matching pieces and 223,880,932,870 bytes verified in the historical report cover that original payload. A later EXE needs separate provenance. Intake rescans the package PEs and lists changed DLLs.

For each candidate the tool records SHA-256, architecture, entry RVA and section, TLS directory and callback order, then compares imports, modules and unresolved items with the baseline. Source-built PE fixtures and a miniature torrent cover named, ordinal and delayed imports, missing providers, TLS callbacks, invalid callback addresses, truncation, an absent entry and path conflicts. These checks establish static properties. Authenticity and startup remain unverified.

## Six API call sites

After loading the toolchain, inspect three local DLLs. `out/calls/six-apis.json` records image SHA-256, import slots, callers of thunks, embedded container sections and code references. Addresses below are RVAs in the relevant DLL. Indirect calls need execution evidence to identify the selected path.

```powershell
.\tools\dev.ps1
.\out\pe-env\Scripts\python.exe -B tools/call_evidence.py "game-files/<build-directory>"
```

| Import | Observed inputs, return handling and desktop check |
|---|---|
| `XMemAlloc` | At `0x25c35`, Bink passes the requested length plus 64 and attributes `0x05e50000` through a thunk. A null return enters diagnostics. Success wraps the pointer. At `0x565d`, AMD rounds the length up to a multiple of 256, reads the attributes at `0x6eee0` (on-disk initial value `0xa8004000`) and checks for null. Regression assertions cover both attribute sets, which exceed the ordinary-heap fixture's supported range. |
| `XMemFree` | At `0x25be4`, Bink recovers the base pointer from an offset preceding the wrapper, passes the same attributes, and uses a matching callback for custom allocation. At `0x5712` and `0x5921`, AMD reads the same global slot and clears the stored pointer after release. No observed caller consumes the return value. |
| `XMemVirtualQuery` | The BVH callers at `0x19c69`, `0x19ccb`, `0x19d9d` and `0x19df9` pass the current process, a target address and a zeroed 64-byte buffer. Zero enters diagnostics. On success the code reads `+0x20` and `+0x30`, and the first caller also reads `+0x24`. Desktop `VirtualQueryEx` wrote 48 of 64 bytes and left the last 16 sentinel bytes intact. The read at `+0x30` remains unexplained. |
| `XMemGetWorkingSetStatistics` | Seven AMD calls pass selector `0x20000001` and a local output address. At `0x26b3` and elsewhere a zero return contributes zero to a calculation. Success uses the 64-bit value at `+8`. Code near `0x74d2/75b1` uses a before/after difference to update a counter. The units, scope and selector meaning remain open. |
| `D3D12SerializeVersionedRootSignature` | At `0xc2d0` the BVH code copies a caller's 48-byte descriptor and adds flags `0x03000000` at `+0x28`. At `0xc32f` it passes the descriptor, a blob output pointer and a null error output. Negative HRESULT enters diagnostics. Success uses the blob length and data pointer. A synthetic v1.1 descriptor returned `S_OK` with baseline flags and `E_INVALIDARG` with the two added bits. |
| `D3D12CreateRootSignatureDeserializer` | At `0x4f88`, AMD reads a byte pointer and a 32-bit length from record offsets `+0/+8`, then supplies an interface IID and object output address. A negative HRESULT or null object triggers partial cleanup. Success retrieves the descriptor via the object. Desktop code read the root signature from a complete Microsoft sample shader and returned `E_INVALIDARG` for a synthetic shader without one. |

### Graphics input paths

- The BVH serializer helper has 16 direct calls. At `0xd967–0xd998` the caller builds a version, six parameters and the parameter-array address on the stack. At `0x2151d` another path references container `0x25700` and passes it downstream with length `0x1134`. The DLL contains 52 code-referenced DXBC containers with structurally valid DXIL programs and `RTS0` sections. All 52 root signature headers carry `0x03000000`. The desktop failure case reproduces these flag bits. Their meaning remains unconfirmed.
- AMD registers the deserialization function in a callback table at `0xcea3–0xceaa`. A producer at `0xe9b8/0xe9c3` selects container `0x714f0` of length `0x1910`, copies its descriptor record and calls through the table at `0xebad`. The DLL has 29 structurally complete containers, each with a matching pointer-table entry and `RTS0` and `ACCC` sections. None contains DXIL. These observations support an embedded source. Runtime initialization determines the indirect path.
- Counts cover the inspected DLLs. Scene shaders, archive read order and the graphics path used at startup have no execution record here. An entry executable would allow its imports and initialization calls to be examined.

### Microsoft sample on desktop

The test uses Microsoft's SimpleTriangle at `Xbox-GDK-Samples` commit `b1e77b6ac10f95b07296025fda171ca2ddc42dbe`. The project includes a `Gaming.Xbox.Scarlett.x64` configuration and a published reference image. Desktop builds compile the two HLSL files using the sample's three vertices, colors, sRGB render target and clear color. The test checks SHA-256 for both shaders and the image. Set `SIMPLE_TRIANGLE_DIR` to that revision's sample directory and run `ctest --preset dev -R reference_triangle -V`. [Microsoft sample overview](https://learn.microsoft.com/en-us/samples/microsoft/xbox-gdk-samples/simpletriangle/) · [Pinned source and reference image](https://github.com/microsoft/Xbox-GDK-Samples/tree/b1e77b6ac10f95b07296025fda171ca2ddc42dbe/Samples/IntroGraphics/SimpleTriangle)

RTX 2060 and WARP rendered at 64×64. Excluding triangle edges by normalized coordinates left 10,812 color channels per adapter. Differences from the source-derived colors were at most 2 on an 8-bit scale. Against the published image the mean absolute difference was 6.88 and the maximum was 17. The two desktop images differed at 94 pixels, by at most 1 per channel. The published image came without a device model, build hash or lossless GPU readback. Source-derived colors supply the acceptance values. Microsoft distributes console GDKX separately. [Microsoft developer resources](https://developer.microsoft.com/en-us/games/resources/)

## Compute and ray tracing before executable intake

The inspection reads bytes from two local DLLs. Desktop parsers inspect serialized descriptors and DXIL. GPU tests execute HLSL built from this repository. After building, run:

```powershell
$pkg = (Get-ChildItem game-files -Directory)[0].FullName
.\out\pe-env\Scripts\python.exe -B tools/probe_roots.py $pkg --controls out/build/dev
ctest --preset dev -R 'compute_|dxr_query|shader_metadata|bvh_buffer_ops' -V
```

`out/calls/desktop-roots.json` records per-container return codes, root signature summaries, matching desktop fixtures, static call counts and validator diagnostics. It also hashes the input inventory and probe executable. Each container was checked independently.

| Windows check | XboxBvhBuilder | AMD upscaler |
|---|---|---|
| Both D3D12 deserializers read the embedded signature from the full container | 52/52 accepted, 16 distinct signatures | 29/29 accepted, 3 distinct signatures |
| Reserialize unmodified v1.1 descriptor | 52/52 returned `E_INVALIDARG` | 29/29 accepted |
| Clear only `0x03000000` in a memory copy and reserialize | 52/52 accepted. Console flag semantics are unknown. | Original flags were zero. |
| Validate the entire container and the internal bitcode separately using the Windows SDK | Both checks rejected all 52 Shader Model 6.5 compute programs. | `ACCC` present, no DXIL input. |

Both source-built control shaders passed container and module validation. For the BVH modules the validator reported an unrecognized `dxil-ms-xb2` target and `xbox.compiler.options` metadata. DXC disassembly showed 43 modules directly calling 33 distinct `xbox.` functions, including cache-controlled reads, cross-lane operations and floating-point atomics. The other nine had no such direct calls. Diagnostics retain up to 2 KiB per message. Counts use the complete disassembly. [DXC validator interface](https://github.com/microsoft/DirectXShaderCompiler/blob/main/include/dxc/dxcapi.h)

The first synthetic compute layout uses an SRV, a UAV and 16 root constants. Its `RTS0` payload matches 11 BVH containers byte for byte after clearing the two flags. The second uses 13 UAVs, 21 SRVs, four root CBVs and a static sampler. It matches 27 unmodified AMD containers. Both tests access the last registers in the descriptor tables. RTX 2060 and WARP wrote 257 correct integer words per layout and preserved 63 sentinel words.

The native DXR fixture builds a bottom-level structure (BLAS) from one triangle and a top-level structure (TLAS) from two instances. Five inline Shader Model 6.5 queries cover hits, a geometric miss, distance clipping, translation and instance masks. Both backends hit instances 7 and 11 at distance 1 and missed the other three rays. Integration of the game's acceleration structure layout and consumers with desktop DXR remains unverified. [Microsoft DXR specification](https://microsoft.github.io/DirectX-Specs/d3d/Raytracing.html)

Four priority BVH containers use the first layout, are referenced by the function starting at `0x20270` and use 32×1×1 thread groups. Source-built HLSL reproduces the data operations inferred from static instructions. Independent CPU results supply the expected values.

| Container RVA | Observed input and write behavior |
|---|---|
| `0xb3ae0` | Copy the specified count of 16-byte input blocks to matching output offsets. |
| `0xb82e0` | Write the same constant to all four 32-bit words of each valid block. |
| `0xb4bd0` | Write consecutive unsigned 32-bit integers starting at a seed. |
| `0xb5be0` | Read the length parameter from the second input word and copy `64 × (parameter + 1)` bytes in steps. When reset is enabled, write the positive and negative maximum finite float bit patterns to six words at output offsets 16–39. |

Tests use disjoint buffers and cover zero length, thread-group boundaries, integer wraparound and untouched memory. Each desktop backend runs 26 cases and checks 384 words per case. The fourth operation schedules its optional reset in a second dispatch with a UAV barrier. Source cross-group synchronization, aliasing and actual game call parameters remain open.

### BVH reads and cross-lane operations

In `out/calls/desktop-roots.json`, `static_operands` from `tools/probe_roots.py` groups functions by module count, call site and operand form. The counts below describe static instructions across the 52 BVH programs. Runtime frequency is unknown.

| Read form | Modules | Static calls |
|---|---:|---:|
| Global, one word | 17 | 227 |
| Global, two words | 3 | 129 |
| Global, three words | 12 | 184 |
| Global, four words | 10 | 44 |
| Scalar, one word | 16 | 32 |

Across 27 distinct modules, all 616 reads use 64-bit addresses and end with two LLVM `undef` arguments. They provide no definite cache policy. At RVA `0xa4780` a count read from base plus 12 limits active threads. A loop in `0xc6260` reads a word at base plus four times the index and writes it to the destination. The fixture exercises both data behaviors and the scalar offset `(index << 8) | 44`.

Two successive writes to the same GPU buffer are each ordered by a UAV-to-SRV transition before reads of all four widths. Each round submits 128 synthetic requests covering low-word carry, shared and scattered addresses, a final valid vector, overrun, misalignment and different high words. The CPU uses independent 64-bit range arithmetic and compares each returned word. Out-of-range sentinels are a fixture rule. Console cache hit rate, address ownership, invalid access behavior and visibility without explicit ordering remain unknown.

Eight modules contain 75 calls to `LaneSwizzle.i32`, with immediates 30, 60, 120, 240 and 480 occurring 15 times each. The `0x95e20` sequence conditionally accumulates exchanged values and reads lane 31. This motivated a candidate five-stage prefix sum within each 32-lane subgroup. Tests exercise native waves and group-shared memory separately. The logical 64-lane path also checks both halves of the ballot mask, prefix counts, dynamic indices and lane 31. The native path checks the active minimum, broadcast, divergent votes and dynamic reads. The CPU reconstructs expectations from GPU-reported native lane IDs.

Each backend runs 38 groups with empty, full and sparse ballots and 32 single-point inputs covering every position in each half. RTX 2060 reported native width 32–32 and WARP 4–4. Both passed the group-shared 64-logical-lane test and skipped forced native wave64 on capability grounds. A capable adapter will run that case. Single-point inputs, CPU prefix sums and final ray hits provide the PC acceptance checks. [WaveReadLaneAt semantics](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/wavereadlaneat)

```powershell
ctest --preset dev -R 'bvh_reads|bvh_waves|bvh_wave64|bvh_hits' -V
```

### From buffer reads to ray hits

`bvh_hits_hardware` and `bvh_hits_warp` connect bounded address reads and half-group prefix sums to ray intersections. Box and triangle tests follow AMD GPURT's software approach. A synthetic root holds 64 child bounds with logical 64-bit triangle addresses. The 64 logical lanes test bounds and compact candidates using both half-group sums. Receiving lanes fetch vertices and reduce nearest hits within and across native waves. The fixture breaks distance ties by the smallest primitive ID. [AMD GPURT intersections](https://github.com/GPUOpen-Drivers/gpurt/blob/dev/src/shaders/IntersectCommon.hlsl)

Three successive scenes occupy the same GPU buffer. Each is written as a UAV and then read as an SRV. A CPU brute-force, double-precision plane intersection independently checks each ray's box count, triangle hit count, closest distance and primitive ID. Each round uses the same 130 rays, covering each leaf in isolation, forward, reverse and oblique rays, edges, vertices, zero distance and box-only intersections.

| Scene | Hits | Misses |
|---|---:|---:|
| Sparse layout, isolate all 64 leaves | 112 | 18 |
| Permuted addresses, overlapping geometry and equal-distance hits | 14 | 116 |
| Permuted again, with invalid address high bits, an out-of-range tail and a degenerate triangle | 108 | 22 |

RTX 2060 and WARP agreed with the CPU on every field. Closed intervals, tie breaking and invalid-leaf handling are fixture rules. The tests establish synchronized desktop reads and hit results. Scarlett node layouts and cache hints remain hypotheses to check against producer writes and consumer reads.

### Independent BVH checks on PC

Each scene sends the same 136 rays through a double-precision brute-force CPU test, a custom shader reading packed nodes, and standard DXR. DXR builds its own BLAS and TLAS from the original accessible vertices and runs inline queries. All paths check hit status and closest distance. The CPU also checks that the specific DXR-selected primitive intersects at that distance, allowing valid ties. Comparisons use triangle interiors and distance margins. Edge and endpoint cases use the preceding fixture's fixed conventions. [DXR ray extents](https://microsoft.github.io/DirectX-Specs/d3d/Raytracing.html#ray-extents)

RTX 2060 and WARP each completed 408 comparisons. In fault controls only the custom shader's input changes. Swapping child 0 and 32 addresses changed four results, replaying the previous scene changed 102 and aliasing invalid address high bits changed one. Each fault must alter its designated witness ray. Run `ctest --preset dev -R bvh_differential -V` for hit counts, changed results and witness indices.

Project acceptance uses reproducible PC behavior. The next game-specific check is to identify the builder selected by the main executable, its node-buffer inputs and outputs, and the downstream queries, then add the observed constraints to PC tests.

### Dynamic dependencies at startup

Five `GetProcAddress` calls were inspected in the local AMD loader. The `0x10000` descriptor selects the packaged upscaler, whose five exports match. `0x20000` and `0x30000` select `amd_fidelityfx_framegeneration_xbox.dll`, absent from the inspected directory and torrent manifest. The loader checks for an already-loaded module before calling `LoadLibraryA`. Whether the main executable requests frame generation remains unknown. [AMD FidelityFX API](https://github.com/GPUOpen-LibrariesAndSDKs/FidelityFX-SDK/blob/main/Kits/FidelityFX/api/include/ffx_api.h)

The executable intake report's `dependency_paths` gives an explanatory path from the entry to each reachable dependency, preferring ordinary imports and marking delay imports and confirmed AMD branches. The AMD branch data applies only to a SHA-256-matched loader. Dynamic lookups, host forwarders and execution order require separate evidence. With DLLs alone, trace from each one:

```powershell
.\out\pe-env\Scripts\python.exe -B tools/dependency_paths.py out/dependencies/pre-exe.json |
    Set-Content out/dependencies/pre-exe-paths.json -Encoding utf8
```

## Resource chunks and shader formats

After building, use the source-built pixel shader as a known DXIL control.

```powershell
python -B tools/resource_inventory.py "game-files/<build-directory>" --shader-control out/build/dev/triangle_ps.cso
```

`out/resources/<build-directory>.json` records install chunks, flags, byte counts and missing layout destinations. It records file-header signatures for the build and scans all raw bytes in `appdata0.rpf`, `common.rpf` and `shaders.rpf` for format markers. Candidate DXBC containers are checked for length, section boundaries and DXIL program headers. `sample_streams` covers at most eight qualifying zlib streams per file within the first 4 MiB. Plaintext stays in memory. The sample cannot characterize the rest of the archive. Installation order and runtime I/O need independent checks. [DXIL container format](https://github.com/microsoft/DirectXShaderCompiler/blob/main/docs/DXIL.rst) · [RPF9 observation source](https://gtamodx.com/columns/eXk_fiBUaYta)
