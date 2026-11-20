# Xbox2Windows

Xbox2Windows investigates what it takes to run Xbox Series X|S (Scarlett) software on x64 Windows. **Grand Theft Auto VI (GTA 6) on Xbox Series X (XSX)** is the motivating case study. The part you can run today is a set of source-built Windows experiments covering executable dependencies, memory allocation, D3D12 shaders and ray tracing. Full-game startup and frame rate remain unverified.

## Where a contributor can help

Our RTX 2060 runs 32-lane waves and Microsoft's WARP software renderer runs 4-lane waves. Both passed the same 408 BVH ray comparisons and skipped the native 64-lane test. Two tasks are ready to pick up:

- **Have a wave64-capable GPU?** Run three BVH tests and report the adapter, lane range and first mismatch, if any. [Native wave64 coverage (#1)](https://github.com/R0Y00/Xbox2Windows/issues/1) · [Measured results](docs/experiments.md#independent-bvh-checks-on-pc)
- **New to graphics programming?** Try the first build on a clean Windows checkout and tell us where the instructions work or break down. This task uses software rendering. [First-build check (#2)](https://github.com/R0Y00/Xbox2Windows/issues/2)

## First build

On x64 Windows, install Visual Studio's **Desktop development with C++** workload, including x64 MSVC, the C++ CMake tools with Ninja, and Windows SDK 10.0.26100 with DXC. From the repository root in PowerShell, run:

```powershell
.\tools\dev.ps1
cmake --preset dev
cmake --build --preset dev
ctest --preset dev -R 'desktop_root_signature|era_heap_allocation|offscreen_warp'
```

These three tests exercise a D3D12 root signature, heap allocation and software rendering. To enable the PE and shader metadata tests, install x64 Python 3.11 or newer, then configure again:

```powershell
python -m venv out/pe-env
.\out\pe-env\Scripts\python.exe -m pip install -r requirements-dev.txt
cmake --preset dev
cmake --build --preset dev
ctest --preset dev
```

## Choose an experiment

| Area | A contribution you can verify | Focused CTest command |
|---|---|---|
| D3D12 and ray tracing | Compare the CPU reference, custom BVH shader and DXR on another adapter. Record the driver and native wave width. | `ctest --preset dev -R '^bvh_(differential\|wave64)_hardware$' -V` |
| Windows runtime | Add a source-built allocation case with a measurable Windows result. | `ctest --preset dev -R 'era_heap\|desktop_memory_query'` |
| PE tooling | Reproduce an import-resolution edge case with a DLL or EXE built from source. | `ctest --preset dev -R 'static_exe_intake\|conditional_import_paths'` |
| Build and documentation | Try the first build from a clean clone. Identify the first missing prerequisite or unclear instruction. | Use the three-test command above. |

The contribution guide explains how to claim a task, report a skip, or submit a patch. [Contributing](CONTRIBUTING.md) · [Open an issue](https://github.com/R0Y00/Xbox2Windows/issues/new/choose)

## GTA VI case study and provenance

In a statement dated November 20, 2026 and supplied to the project maintainer, CYBERLEEK claimed to have a November Xbox build of GTA VI and said the main executable had been withheld. The project's local intake recorded a Scarlett entry in the installation metadata and the absence of that executable from the inspected file set. Build authorship, date and completeness remain unverified. The public regression suite uses synthetic fixtures and independently built shaders. [Intake methods and evidence](docs/experiments.md#static-executable-intake)

## License

Original project code and documentation use the [MIT License](LICENSE). Third-party games, assets, SDKs and trademarks belong to their respective owners. Xbox2Windows is an independent community project, unaffiliated with Rockstar Games, Take-Two, Microsoft or AMD.
