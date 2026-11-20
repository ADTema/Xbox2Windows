# Contributing to Xbox2Windows

欢迎用中文或英文提交改动、复现报告和不同显卡的测试结果。社区维护的回归用例全部来自仓库源码。参与者可以在 PC 上构建并运行它们。

## Pick up work / 认领任务

1. Search [open issues](https://github.com/R0Y00/Xbox2Windows/issues) for the behavior or test name. 对已有任务，留言说明你准备验证的部分，方便其他人并行处理其余部分。小修正可以直接提 PR。
2. For a new investigation, open a research proposal. 写清输入、能观察到的结果和完成条件。维护者可用 GitHub 的 assignee、关联 PR 和关闭原因记录进度。
3. Create a topic branch from the current `main`. External contributors can work on a fork when available. 每个 PR 聚焦一个可评审的问题，通过 `Fixes #123` 或 `Refs #123` 关联已有讨论。

## Build and test / 构建与验证

Use x64 Windows, Visual Studio C++ Build Tools with MSVC and CMake/Ninja, and Windows SDK 10.0.26100 with DXC. Start PowerShell at the repository root. Run the commands in the [README](README.md#第一次构建). Install the pinned Python dependency before configuring to include the PE tests. `ctest --preset dev -N` lists the tests registered on your machine.

| Where to work | What belongs there |
|---|---|
| `src/` | Windows runtime implementations; exercise public behavior through the matching test. |
| `tests/` | C++, HLSL and generated-input fixtures. The `_warp` suffix selects the software adapter. The `_hardware` suffix selects a physical GPU. |
| `tools/` | Build environment and offline metadata tools. Run PE checks on the locally built fixtures in `tests/intake/`. |
| `docs/experiments.md` | Measured results, input assumptions and commands for repeating an experiment. |

Use `ctest --preset dev -R <name> -V` for a focused run. For GPU work, record the adapter, driver, feature tier or wave width, and whether the debug layer was enabled. Include skipped test names and the reported capability. CI builds the C++ and HLSL, then runs the CPU, Python and WARP checks on a Windows runner. Physical GPU results come from contributor runs.

## Fixtures and evidence / 样例与证据

Submit original source, synthetic inputs, or a link to a public sample with its revision and license. Keep game files, distribution links, SDK redistributables and local dumps out of Git, issues and PR attachments. Store local inputs in `game-files/` and generated results in `out/`. For a bug report, share the smallest source fixture that reproduces the behavior. Remove personal paths and credentials from logs.

Submit original contributions under the project's [MIT license](LICENSE). Preserve any applicable third-party attribution and license notices.

Distinguish a measured result from a proposed interpretation. For a BVH change, for example, report the failing ray, the expected distance or primitive, and what the CPU, custom shader and DXR each returned. Where multiple primitives can satisfy a query, describe the accepted result set.

## Review / 合并

Describe the user-visible or testable change, include the command and result, and identify the behavior that still needs verification. Reviewers can reproduce the smallest failing case, check the source of new fixtures and compare the expected behavior before and after the patch. Maintainers merge reviewed changes after the relevant checks pass and link follow-up work to the original issue.
