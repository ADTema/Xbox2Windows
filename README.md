# Xbox2Windows

Xbox2Windows 研究 Xbox Series X|S（Scarlett）程序在 x64 Windows 上的兼容性。目前可以复现的是内存接口、PE 依赖分析、D3D12 绘制和 BVH 射线命中实验。运行社区测试只需 Windows PC。完整商业游戏启动仍待验证。

**For contributors:** Xbox2Windows studies Xbox Series X|S compatibility on Windows. All community tests use source-built fixtures and run on a PC. Contributions and test reports in English or Chinese are welcome. [Contribution guide](CONTRIBUTING.md)

## 第一次构建

在 Windows x64 上安装 Visual Studio 的“使用 C++ 的桌面开发”工作负载，包含 MSVC x64、C++ CMake 工具以及 Windows SDK 10.0.26100（含 DXC）。从仓库根目录打开 PowerShell。

```powershell
.\tools\dev.ps1
cmake --preset dev
cmake --build --preset dev
ctest --preset dev -R 'desktop_root_signature|era_heap_allocation|offscreen_warp'
```

最后一条命令验证根签名、内存分配和软件渲染。安装 x64 Python 3.11 或更高版本后可启用 PE 和着色器元数据测试。创建虚拟环境后重新配置，CMake 会注册这些用例。

```powershell
python -m venv out/pe-env
.\out\pe-env\Scripts\python.exe -m pip install -r requirements-dev.txt
cmake --preset dev
cmake --build --preset dev
ctest --preset dev
```

## 从哪里参与

| 方向 | 可以独立完成的第一项工作 | 本地验证 |
|---|---|---|
| D3D12 / GPU | 在另一种适配器上复测 BVH，报告驱动、通道宽度、命中差异和能力跳过项 | `ctest --preset dev -R 'bvh_differential\|bvh_wave64' -V` |
| Windows 运行时 | 用自建分配请求复现一个内存行为，给出 Windows 端的期望值 | `ctest --preset dev -R 'era_heap\|desktop_memory_query'` |
| PE 与工具 | 用自行编译的 DLL 或 EXE 补一个导入解析边界用例 | `ctest --preset dev -R 'static_exe_intake\|conditional_import_paths'` |
| 文档和复现 | 从全新工作副本运行上面的命令，记录第一个需要补充说明的步骤 | 附系统、工具版本、命令和输出 |

在 [Issues](https://github.com/R0Y00/Xbox2Windows/issues) 查看或提出任务。提交范围、复现信息和评审流程见[贡献指南](CONTRIBUTING.md)。已有实验的输入、结果和局限见[实验记录](docs/experiments.md)。

## 许可

本项目的原创代码和文档采用 [MIT 许可证](LICENSE)。第三方游戏、素材、SDK 和商标的权利归各自权利人。项目独立维护，与 Rockstar Games、Take-Two、Microsoft 和 AMD 均无隶属关系。
