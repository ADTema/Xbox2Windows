# Contributing to Xbox2Windows

You can contribute a hardware result, a source-built failing case, a documentation fix or a patch from an x64 Windows PC. Our GTA VI / Xbox Series X case study supplies research questions. The shared regression suite runs with public tools and fixtures built from this repository.

## Find and claim a task

1. Search the [issue tracker](https://github.com/R0Y00/Xbox2Windows/issues) for the test name or observed behavior. Issues labeled **good first issue** have a small first step. **help wanted** marks work that can proceed independently.
2. For an existing task, comment with the part you plan to test and your environment. Multiple adapters can be tested in parallel. For a new investigation, open a research task with a question, reproducible inputs and a completion condition. Small fixes can start with a PR.
3. If another contributor takes over, leave the commit, last command, observed result and next unanswered question on the issue. A maintainer can use the assignee field to record ownership of a patch.

## Build and test

Hardware reporters can use the [standalone package](tools/gpu-check/README.md). Paste the generated Markdown into issue #1. For a first-build report, use a clean checkout and post the three smoke-test outcomes to issue #2. Maintainers verify each incoming result, link the source report in the README coverage table, and record repeated runs on the same adapter as follow-ups. Link a feedback-driven fix to its report and ask the reporter to verify the change.

Start with the [first build](README.md#first-build). Install the pinned Python dependency before configuring to include the PE tests. List the tests registered in your environment with `ctest --preset dev -N`, then run a focused test with `ctest --preset dev -R <name> -V`.

| Location | What to work on |
|---|---|
| `src/` | Windows runtime implementations and their observable behavior. |
| `tests/` | C++, HLSL and generated-input fixtures. Tests ending in `_warp` use the software adapter. Those ending in `_hardware` use a physical GPU. |
| `tools/` | Build setup and offline metadata tools. The PE fixtures live in `tests/intake/`. |
| `docs/experiments.md` | Measured results, assumptions and reproduction commands. |

Windows CI builds the C++ and HLSL, then runs the CPU, Python and WARP checks. Contributors supply physical GPU coverage. For a hardware report, record the commit, adapter and driver, Windows version, test names and debug-layer status. Include the reported feature tier or wave width when relevant. A capability skip is a useful observation. Record it separately from a pass or failure.

## Share a reproducible finding

Use original source, synthetic inputs or a public sample with its revision and license. Store local inputs in `game-files/` and generated output in `out/`. Keep game files, distribution links, SDK redistributables and dumps out of issues, PRs and Git. Remove personal paths and credentials from logs.

State what the test measured and which behavior remains a hypothesis. For example, a BVH report can identify the first differing ray and give the CPU, shader and DXR hit distances. If several primitives coincide, describe which IDs are valid. Claims about the GTA VI build should identify their source. A passing fixture supports the behavior under test; full-game startup requires its own execution evidence.

## Submit and review a patch

Create a topic branch from current `main` in your fork. Keep a PR focused on one reviewable behavior, include the exact test command and result, and link any related issue with `Refs #123`. Use `Fixes #123` when the patch meets that issue's completion condition. Submit original contributions under the [MIT License](LICENSE) and preserve applicable third-party notices.

Reviewers reproduce the smallest relevant case, check the origin of any new fixtures and compare behavior before and after the change. Maintainers merge through a PR after the Windows check passes and review conversations are resolved. Record remaining questions in a linked issue so the next contributor can pick them up.
