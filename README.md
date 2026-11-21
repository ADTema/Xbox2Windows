# Xbox2Windows

Xbox2Windows investigates **static recompilation of Xbox Series X|S (Scarlett) software for x64 Windows**, using Grand Theft Auto VI as its case study. The CPU experiments translate source-built x64 functions from PE machine code through C++ to new Windows DLLs, including a direct call and a named import from another DLL. The shader experiment translates selected gfx1013 pixel shaders through HLSL to desktop DXIL. Other experiments test the Windows runtime, render recovered texture levels and read script state data. Title CPU code execution, full-game startup and frame rate remain unverified.

## Current results and open work

| Area | Result on Windows | Open question or contribution |
|---|---|---|
| Chained x64 functions | A source-built split function passes native comparisons. Two recompiled early exits from a local loader each return 6. [Chained ranges](docs/experiments.md#chained-function-ranges-and-early-returns) | Identify the non-null callback ABI. [Issue #29](https://github.com/R0Y00/Xbox2Windows/issues/29) |
| CPU translation | A [leaf function](docs/experiments.md#offline-cpu-leaf-recompilation), a [direct call](docs/experiments.md#recompiling-a-direct-x64-call) and a [named PE import](docs/experiments.md#calling-another-dll-through-a-named-pe-import) match the original on Windows. The import test also checks missing providers and exports. | Verify a call to an ordinal-only export. [Issue #26](https://github.com/R0Y00/Xbox2Windows/issues/26) |
| Shader translation | Supported pixel programs sample a texture, read constants and export color. D3D12 readback is checked against a CPU reference. [Translation and bindings](docs/experiments.md#offline-pixel-shader-recompilation) | Supply a source-built instruction case with known register inputs and an expected color. |
| BC7 textures | A translated shader samples recovered mip levels on hardware and WARP. Requests for missing high-resolution levels use the first resident level. [Mip fallback tests](docs/experiments.md#drawing-bc7-textures-with-a-recompiled-pixel-shader) | Match a variable BCPack lane against independently known BC7 blocks. [Issue #15](https://github.com/R0Y00/Xbox2Windows/issues/15) |
| Script states | A native x64 probe follows state-tree links and reproduces distinct camera limits for front and rear selections. The replay supplies the selection requests. [State replay](docs/experiments.md#state-linked-settings-in-a-script-archive) | Identify an event or caller that supplies a context and state ID, with a control input that takes a different branch. [Issue #19](https://github.com/R0Y00/Xbox2Windows/issues/19) |
| Windows runtime and GPU | Source-built checks cover PE imports, heap operations, root signatures, compute and ray tracing. [Experiment notes](docs/experiments.md) | Run the wave64 fixture on a physical adapter or reproduce the first build on a clean checkout. [Hardware reports](https://github.com/R0Y00/Xbox2Windows/issues/1) · [First builds](https://github.com/R0Y00/Xbox2Windows/issues/2) |

The public suite builds its own fixtures. A contributor can reproduce the checks below on a PC without a game installation. The standalone release packages the GPU check. To run the script, shader and texture development suite, build from source.

## Run the GPU check

Download the [Windows x64 GPU check and SHA-256](https://github.com/R0Y00/Xbox2Windows/releases/tag/gpu-check-v0.1.0), verify and extract the ZIP, then run this in PowerShell from the extracted folder. The package contains its own shaders and needs no compiler, console or game files.

```powershell
.\Run-GpuCheck.ps1
```

Review `gpu-report-hardware.md` and paste it in the [hardware coverage thread (#1)](https://github.com/R0Y00/Xbox2Windows/issues/1). Reports with a failure or capability skip are welcome. [Package instructions](tools/gpu-check/README.md)

### Hardware coverage

| Adapter or backend | Reported native lanes | Forced wave64 | BVH differential | Evidence |
|---|---:|---|---|---|
| NVIDIA GeForce RTX 2060 | 32 | Skipped | 408 queries passed | [Maintainer baseline](docs/experiments.md#independent-bvh-checks-on-pc) |
| NVIDIA GeForce RTX 4060 Laptop GPU | 32 | Skipped | 408 queries passed | [Second maintainer workstation](https://github.com/R0Y00/Xbox2Windows/issues/1#issuecomment-7058907095) |
| Microsoft WARP (software) | 4 | Skipped | 408 queries passed | [Maintainer baseline](docs/experiments.md#independent-bvh-checks-on-pc) |
| Wave64-capable Windows GPU | Awaiting report | Awaiting execution | Awaiting report | [Contribute a run](https://github.com/R0Y00/Xbox2Windows/issues/1) |

Maintainers link independent results to the original report and record the adapter, driver, commit and outcome. Names or handles are added on request. Our first community milestones are three independent hardware reports, one independent clean build and one verified fix driven by contributor feedback. New to graphics programming? Try the [first-build task (#2)](https://github.com/R0Y00/Xbox2Windows/issues/2).

## First build

On x64 Windows, install Visual Studio's **Desktop development with C++** workload, including x64 MSVC, the C++ CMake tools with Ninja, and Windows SDK 10.0.26100 with DXC. From the repository root in PowerShell, run:

```powershell
.\tools\dev.ps1
cmake --preset dev
cmake --build --preset dev
ctest --preset dev --no-tests=error -R 'desktop_root_signature|era_heap_allocation|offscreen_warp'
```

These three tests exercise a D3D12 root signature, heap allocation and software rendering. To enable the script, shader, texture and PE fixture tests, install x64 Python 3.11 or newer and configure again. Windows CI uses Python 3.12.

```powershell
python -m venv out/pe-env
.\out\pe-env\Scripts\python.exe -m pip install -r requirements-dev.txt
cmake --preset dev
cmake --build --preset dev
ctest --preset dev --no-tests=error
```

## Choose an experiment

| Area | A contribution you can verify | Focused CTest command |
|---|---|---|
| Static CPU recompilation | Compare a leaf, a direct call and a cross-DLL import with their originals and negative controls. | `ctest --preset dev --no-tests=error -R '^cpu_' -V` |
| Script states | Reproduce a parent/child lookup, an ambiguous selection or a damaged sibling link with a synthetic tree. | `ctest --preset dev --no-tests=error -R '^script_(state_literals\|path_links)$' -V` |
| Texture recovery | Check a packed mip tail, a first refill byte, or a resident mip drawn on the software adapter. | `ctest --preset dev --no-tests=error -R '^(bcpack_prefix_and_mip_tail\|bc7_draw_warp)$' -V` |
| Static shader recompilation | Translate the single-texture pixel shader fixtures to desktop DXIL and check every output channel. [Supported instructions and bindings](docs/experiments.md#offline-pixel-shader-recompilation) | `ctest --preset dev -R '^pixel_aot_' -V` |
| D3D12 and ray tracing | Compare the CPU reference, custom BVH shader and DXR on another adapter. Record the driver and native wave width. | `ctest --preset dev -R '^bvh_(differential\|wave64)_hardware$' -V` |
| Windows runtime | Add a source-built allocation case with a measurable Windows result. | `ctest --preset dev -R 'era_heap\|desktop_memory_query'` |
| PE tooling | Reproduce an import-resolution edge case with a DLL or EXE built from source. | `ctest --preset dev -R 'static_exe_intake\|conditional_import_paths'` |
| Build and documentation | Try the first build from a clean clone. Identify the first missing prerequisite or unclear instruction. | Use the three-test command above. |

For task ownership, evidence requirements and PR review, see the [contribution guide](CONTRIBUTING.md). [Open an issue](https://github.com/R0Y00/Xbox2Windows/issues/new/choose) · [Community conduct](CODE_OF_CONDUCT.md) · [Private security reports](SECURITY.md)

## GTA VI case study and provenance

In a statement dated November 20, 2026 and supplied to the project maintainer, CYBERLEEK claimed to have a November Xbox build of GTA VI and said the main executable had been withheld. The project's local intake recorded a Scarlett entry in the installation metadata and the absence of that executable from the inspected file set. Build authorship, date and completeness remain unverified. The public regression suite uses synthetic fixtures and independently built shaders. [Intake methods and evidence](docs/experiments.md#static-executable-intake)

## License

Original project code and documentation use the [MIT License](LICENSE). Third-party games, assets, SDKs and trademarks belong to their respective owners. Xbox2Windows is an independent community project, unaffiliated with Rockstar Games, Take-Two, Microsoft or AMD.
