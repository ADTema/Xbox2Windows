# 实验记录与复测命令

以下命令均在仓库根目录运行。首次参与请先阅读[项目首页](../README.md)和[贡献指南](../CONTRIBUTING.md)。本记录包含使用本地输入的专项研究，社区回归使用仓库中的自建样例。

## 本地开发

在仓库根目录打开 PowerShell。需要 Visual Studio Build Tools 的 x64 C++、CMake 工具和 Windows SDK。首次配置时运行以下命令，从微软固定版本的源码构建静态依赖分析工具。

```powershell
.\tools\setup-xbdepends.ps1
```

在每个新的开发终端中加载工具链，然后配置、构建并测试。

```powershell
.\tools\dev.ps1
cmake --preset dev
cmake --build --preset dev
ctest --preset dev
```

测试使用自建根签名验证桌面 D3D12 的序列化与反序列化。可以用测试产物练习静态检查。

```powershell
xbdepends -v .\out\build\dev\d3d12_sdk_check.exe
dumpbin /imports .\out\build\dev\d3d12_sdk_check.exe
```

构建产物和工具源码缓存在 `out/`。工具用法见[微软 xbdepends 文档](https://learn.microsoft.com/en-us/samples/microsoft/xbox-gdk-samples/xbdepends/)。

## 构建完整性

对同时包含多文件 v1 种子和 `layout*.xml` 的构建目录，可以用 Python 3.9+ 离线校验。将下方路径替换为本机构建目录。

```powershell
python tools/verify_build.py "game-files/<构建目录名>"
```

脚本按种子顺序读取文件，校验跨文件的 SHA-1 分块，再将安装布局的目标路径与磁盘、种子分别核对。报告位于 `out/integrity/<构建目录名>.json`。退出码 0 表示种子内容通过，布局缺项单独记录在 `layout.absent_from_disk`。

## PE 依赖基线

扫描器使用 x64 Windows、Python 3.11+ 和 pefile。首次配置隔离环境可以运行以下命令。

```powershell
python -m venv out/pe-env
.\out\pe-env\Scripts\python.exe -m pip install pefile==2024.8.26
```

在只有 DLL 时保存基线。后续加入 EXE 后另存新报告，并将旧报告作为比较输入。

```powershell
$pePython = '.\out\pe-env\Scripts\python.exe'
$buildDir = 'game-files/<构建目录名>'
& $pePython tools/pe_inventory.py $buildDir --output out/dependencies/pre-exe.json
# 加入主程序后执行下一行
& $pePython tools/pe_inventory.py $buildDir --baseline out/dependencies/pre-exe.json --output out/dependencies/with-exe.json
```

`summary` 给出计数，`unresolved_edges` 列出包内和本机均未找到指定导出的条目。每条 `imports` 记录对应一个调用模块、导入方式、提供方和符号的组合，`#N` 表示按序号导入。`images` 记录架构、SHA-256、导出名、序号和转发目标。`diff` 区分新增调用关系和整个构建首次出现的依赖。

桌面对照读取本机 System32 的导出表，并按主机的 API-set v6 映射查找提供方。同名或同序号匹配包含转发导出，最终转发目标、函数参数、运行时动态加载和对象方法仍需验证。[API-set v6 结构与查找实现](https://github.com/wine-mirror/wine/blob/master/dlls/ntdll/loader.c)

## 普通堆内存实验

`src/era_heap.cpp` 是供自有程序调用的桌面实验。对齐指数按 SlimEra 的 Xbox One ERA 定义取属性的第 24–28 位；当前仅处理其他属性位为零的普通堆请求。Scarlett 的属性编码、错误约定和图形内存语义仍待验证。[SlimEra 属性定义](https://github.com/XWine1/SlimEra/blob/main/era.h#L105-L137) · [SlimEra 默认堆实现](https://github.com/XWine1/SlimEra/blob/main/kernelx.cpp#L600-L657)

| CTest 用例 | 输入及验收条件 |
|---|---|
| `era_heap_allocation` | 257 字节、6 种对齐指数；检查至少 16 字节及指定对齐、初始清零、写入和释放。Debug 构建额外核对 CRT 堆快照。 |
| `era_heap_failure` | 对零长度、超大长度、图形内存、非默认页和保留位请求，实验返回空指针。这是本实验定义的失败策略。 |
| `era_heap_concurrency` | 4 个线程各 100 轮，同时持有分配并写入不同值，逐字节检查数据独立性后释放。 |

`desktop_memory_query` 为 `XMemVirtualQuery` 和 `XMemGetWorkingSetStatistics` 提供 Windows 侧对照。用例预留一段内存，提交并逐页写入其中 1,024 页，验证只读页和可写页的分界，再撤销提交。它检查锁定页的驻留状态，并记录三个时点的进程工作集、峰值工作集和私有提交字节数。不同次运行的统计值会浮动。Scarlett 返回结构、单位和统计范围仍待核对。[Windows 工作集说明](https://learn.microsoft.com/en-us/windows/win32/memory/working-set)

## 离屏绘制与读回

`offscreen_hardware` 使用高性能硬件适配器，`offscreen_warp` 使用微软软件光栅器。两个用例使用 DXC 编译的同一组自建着色器，在 64×64 RGBA8 纹理绘制三角形，等 GPU 完成后按行距读回，逐像素核对颜色和覆盖范围。输出在构建目录的 `triangle_hardware.bmp` 和 `triangle_warp.bmp`。运行 `ctest --preset dev -V` 可查看适配器、驱动、调试层状态和像素差异。具备调试层时，队列中的错误或损坏级别消息会使测试失败。

本机已安装 Windows Graphics Tools。另一个构建目录 `out/build/agility` 使用微软 Agility SDK 1.620.2 验证同一用例。复建时给 CMake 指定 `-DOFFSCREEN_AGILITY_620_DIR=<SDK 的 x64 DLL 目录>`。此配置会检查调试接口是否真正启用。[微软 Agility SDK 包](https://www.nuget.org/packages/Microsoft.Direct3D.D3D12/1.620.2)

## 主程序静态接收

在仓库根目录运行下列命令。默认从唯一构建的 `MicrosoftGame.Config` 读取 Scarlett 入口。文件可以在安装布局指定的位置，也可以作为单独的路径参数传入。整个流程只读取游戏文件。

```powershell
.\out\pe-env\Scripts\python.exe -B tools/intake_exe.py
# 独立收到的文件可以直接检查
.\out\pe-env\Scripts\python.exe -B tools/intake_exe.py "E:\incoming\game_scarlett_master.exe"
```

每次检查在 `out/intake/` 新建 JSON。退出码 3 表示仍在等待布局中的文件，2 表示输入或检查失败，0 表示静态检查完成。报告关联上次完整性校验的时间、种子 SHA-256、安装分块和基线摘要。当前种子未收录这个 EXE，历史上的 13,345 个匹配分块无法证明后来文件的来源。工具重新扫描包内 PE 并另列发生变化的 DLL，历史上的 223,880,932,870 字节资源校验结果保留在原报告中。

对候选文件记录 SHA-256、架构、入口 RVA 和节、TLS 目录及回调顺序，随后列出相对基线新增的导入、模块和未解析项。测试用自建 PE 和单独的小种子覆盖按名、按序号、延迟导入、缺少提供方、TLS 回调、非法回调地址、截断、入口文件尚缺和路径冲突。接收结果不代表来源鉴定或可启动性。

## 六个接口的调用点

在加载开发工具链后可复查三个 DLL。输出的 `out/calls/six-apis.json` 包含镜像 SHA-256、导入槽、跳板上游、内嵌容器的分段以及代码引用。下表中的地址均为该 DLL 的 RVA，间接回调的运行时选择仍需执行证据。

```powershell
.\tools\dev.ps1
.\out\pe-env\Scripts\python.exe -B tools/call_evidence.py "game-files/<构建目录名>"
```

| 导入 | 已观察到的输入、返回处理与桌面验证 |
|---|---|
| `XMemAlloc` | Bink 在 `0x25c35` 经跳板传入请求长度加 64 和属性 `0x05e50000`。返回空指针进入失败分支，成功时包装返回指针。AMD 在 `0x565d` 将长度向上取整到 256 的倍数，属性取自 `0x6eee0`，磁盘初值为 `0xa8004000`，也检查空指针。两组属性都超出现有普通堆实验的支持范围，已添加回归断言。 |
| `XMemFree` | Bink 在 `0x25be4` 用包装指针前的偏移还原分配基址，并传回相同属性；空指针直接返回，自定义分配走配对回调。AMD 在 `0x5712` 和 `0x5921` 从同一全局槽读取属性，后者释放后清空持有者指针。没有观察到调用者使用返回值。 |
| `XMemVirtualQuery` | BVH 的四个调用点是 `0x19c69/19ccb/19d9d/19df9`。传入当前进程、待查地址和清零的 64 字节输出区。返回零走诊断分支，成功后读取偏移 `+0x20` 和 `+0x30`，第一处还读取 `+0x24`。桌面对照向 `VirtualQueryEx` 提供 64 字节空间，实测写回 48 字节，最后 16 字节的标记保持原值。游戏读取的 `+0x30` 需要独立解释。 |
| `XMemGetWorkingSetStatistics` | AMD 的七处调用使用选择值 `0x20000001` 和本地输出地址。在 `0x26b3` 及多处调用中，返回零时将参与计算的数置零，成功使用输出 `+8` 的 64 位值。`0x74d2/75b1` 附近用前后差值更新计数。单位、统计范围及选择值语义待核实。 |
| `D3D12SerializeVersionedRootSignature` | BVH 在 `0xc2d0` 复制调用者传来的 48 字节描述符，在 `+0x28` 的标志位并入 `0x03000000`，`0xc32f` 传入描述符、blob 输出指针及空错误输出。负 HRESULT 进入诊断路径，成功后使用 blob 的长度与数据指针。桌面测试使用同一份自建 v1.1 描述符，无附加标志返回 `S_OK`，加入这两位后返回 `E_INVALIDARG`。 |
| `D3D12CreateRootSignatureDeserializer` | AMD 在 `0x4f88` 从传入记录的 `+0/+8` 取字节指针和 32 位长度，传入接口 IID 及对象输出地址。负 HRESULT 或空对象进入清理部分状态的路径，成功后通过对象取描述符。桌面对照可从微软样例的完整着色器读取内嵌根签名，对自建的无根签名着色器返回 `E_INVALIDARG`。 |

### 两条图形输入路径

- BVH 的序列化辅助函数有 16 处直接调用。例如 `0xd967–0xd998` 在栈上组装版本、六个参数及参数数组地址，再调用该函数。另一路径在 `0x2151d` 引用内嵌容器 `0x25700`，把它和长度 `0x1134` 交给后续函数。这个 DLL 内有 52 个带代码引用的完整 DXBC 容器，均含结构验证通过的 DXIL 程序及 `RTS0`，52 个根签名头都记录了 `0x03000000`。这将桌面的失败用例与文件中的实际数据联系起来，两个标志的语义仍待确认。
- AMD 在 `0xcea3–0xceaa` 将反序列化所在函数登记到回调表。一个内部生产路径在 `0xe9b8/0xe9c3` 取出容器 `0x714f0` 及长度 `0x1910`，复制描述记录，然后在 `0xebad` 通过表间接调用。DLL 内有 29 个结构完整的容器，每个都有匹配长度的指针表项、`RTS0` 和 `ACCC` 分段，均未检出 DXIL 程序。这个样本支持内嵌来源，间接调用最终选中哪条路径取决于实际初始化。
- 这些计数只覆盖上述 DLL。游戏场景着色器、资源归档读取顺序和启动时使用的图形路径还没有运行记录。后续从主 EXE 新增的导入及初始化调用开始追踪。

### 微软样例的桌面对照

使用微软 `Xbox-GDK-Samples` 提交 `b1e77b6ac10f95b07296025fda171ca2ddc42dbe` 的 SimpleTriangle。工程含 `Gaming.Xbox.Scarlett.x64` 配置，说明文档提供参考图。本机将该提交的两份 HLSL 编译为桌面着色器，在离屏用例中使用源程序指定的三个顶点、颜色、sRGB 渲染目标和清屏色。测试核对两份 HLSL 和参考图的 SHA-256。要在其他工作副本复现，可将 CMake 变量 `SIMPLE_TRIANGLE_DIR` 指向该提交中的样例目录，再运行 `ctest --preset dev -R reference_triangle -V`。[微软样例说明](https://learn.microsoft.com/en-us/samples/microsoft/xbox-gdk-samples/simpletriangle/) · [固定版本源码和参考图](https://github.com/microsoft/Xbox-GDK-Samples/tree/b1e77b6ac10f95b07296025fda171ca2ddc42dbe/Samples/IntroGraphics/SimpleTriangle)

RTX 2060 和 WARP 都完成了 64×64 渲染。按归一化坐标排除三角形边缘后，每个后端各比较 10,812 个颜色通道，所有通道与源码推算的颜色相差至多 2，与微软发布图相比平均绝对差为 6.88、最大为 17（8 位通道）。两个桌面后端的整幅图有 94 个像素不同，最大通道差为 1。发布图未附设备型号、构建哈希或无损 GPU 读回记录。桌面像素验收采用样例源码推算值，发布图作为辅助参考。微软将主机构建所需的 GDKX 列在单独的受限下载中。[微软开发资源](https://developer.microsoft.com/en-us/games/resources/)

## 主程序到达前的计算与光追验证

本轮检查只从两个游戏 DLL 读取字节。桌面原生解析器检查序列化描述和 DXIL，GPU 测试使用本仓库编译的 HLSL。开发构建完成后可以复测。

```powershell
$pkg = (Get-ChildItem game-files -Directory)[0].FullName
.\out\pe-env\Scripts\python.exe -B tools/probe_roots.py $pkg --controls out/build/dev
ctest --preset dev -R 'compute_|dxr_query|shader_metadata|bvh_buffer_ops' -V
```

`out/calls/desktop-roots.json` 逐个记录返回码、根签名摘要、对应的桌面用例、静态调用点计数和校验器诊断。它也记录输入清单和探针程序的 SHA-256。下表统计的是各容器独立接受检查的结果。

| Windows 检查 | XboxBvhBuilder | AMD upscaler |
|---|---|---|
| 两种 D3D12 反序列化接口读取完整容器内的根签名 | 52/52 成功，16 种根签名内容 | 29/29 成功，3 种根签名内容 |
| 原样重新序列化 v1.1 描述符 | 52/52 返回 `E_INVALIDARG` | 29/29 成功 |
| 在内存副本中仅清除 `0x03000000` 后重新序列化 | 52/52 成功，两个标志的主机语义仍待核实 | 原始标志均为零 |
| Windows SDK DXIL 校验器单独检查完整容器和内部 bitcode | 两种检查都拒绝 52/52 个计算程序，均为 Shader Model 6.5 | 容器含 `ACCC`，没有 DXIL 输入 |

已编译的两份自建着色器都通过了同一套容器和模块校验。对 BVH，校验器均报告不识别 `dxil-ms-xb2` 目标及 `xbox.compiler.options` 元数据。DXC 的静态反汇编显示，43 个模块中有直接调用，以 `xbox.` 开头的函数共 33 种，包括带缓存控制的读取、跨通道取值及浮点原子操作。另 9 个模块未检出这种直接调用。诊断文本每次最多保存前 2 KiB，调用数从完整反汇编计算。[微软 DXC 校验接口](https://github.com/microsoft/DirectXShaderCompiler/blob/main/include/dxc/dxcapi.h)

两套自建计算用例的 `RTS0` 载荷做了逐字节比对。第一套的 SRV、UAV 和 16 个根常量与清除上述标志后的 11 个 BVH 容器吻合。第二套的 13 个 UAV、21 个 SRV、4 个根 CBV 和静态采样器与 27 个 AMD 容器原样吻合。测试实际读取和写入描述符表的末端寄存器。RTX 2060 与 WARP 在两套布局下均正确写回 257 个整数字，另外 63 个哨兵字保持原值。

原生 DXR 用例由一个三角形构建底层加速结构（BLAS），再用同一 BLAS 的两个实例构建顶层加速结构（TLAS）。它以 Shader Model 6.5 的内联射线查询核对五组结果，涵盖命中、几何未命中、距离裁剪、实例平移和实例掩码。两个后端都命中了预期的实例 7 和 11，命中距离均为 1，其余三条射线均未命中。Xbox 构建使用的加速结构布局和下游消费者能否接入桌面 DXR，仍需单独验证。[微软 DXR 规范](https://microsoft.github.io/DirectX-Specs/d3d/Raytracing.html)

四个优先验证的 BVH 容器均匹配第一套布局，都由从 `0x20270` 开始的同一个函数引用，线程组大小均为 32×1×1。根据静态指令整理出的数据行为已在自建 HLSL 中复现。桌面实验以独立的 CPU 计算结果为对照。

| 容器 RVA | 静态输入和写入行为 |
|---|---|
| `0xb3ae0` | 按计数将输入中的 16 字节块复制到输出的同一偏移。 |
| `0xb82e0` | 向每个有效块的四个 32 位字写入同一个常量。 |
| `0xb4bd0` | 从给定种子开始，依次写入连续的 32 位无符号整数。 |
| `0xb5be0` | 从输入第二个字读取长度参数，分步复制 `64 × (参数 + 1)` 字节。设置重置标志时，还向输出偏移 16–39 的六个 32 位字写入正、负最大有限浮点数的位模式。 |

测试在互不重叠的缓冲区上检查零长度、线程组边界、编号回绕和未写入区域。每个桌面后端运行 26 组，每组逐字核对 384 个字。第四个操作的桌面实验将可选重置放到独立的第二次 dispatch，以 UAV 屏障保证顺序。源程序的跨工作组同步、输入与输出别名和实际游戏调用参数仍待核对。

### BVH 缓存读取与跨通道试验

`tools/probe_roots.py` 在 `out/calls/desktop-roots.json` 的 `static_operands` 中按函数、模块数、调用点和操作数形式汇总。计数来自本构建 52 个 BVH 程序的静态指令，不能用于推算每帧执行频率。

| 读取形式 | 模块数 | 静态调用点 |
|---|---:|---:|
| Global，单字 | 17 | 227 |
| Global，双字 | 3 | 129 |
| Global，三字 | 12 | 184 |
| Global，四字 | 10 | 44 |
| Scalar，单字 | 16 | 32 |

合计 27 个不同模块、616 处读取。每处均使用 64 位地址，最后两个参数均为 LLVM `undef`。这些操作数没有给出可采用的确定缓存策略。RVA `0xa4780` 从常量缓冲区中的基址加 12 读取计数，用来限制参与工作的线程；`0xc6260` 中的一段循环从基址加四倍索引读取一个字并写到目标。桌面测试抽取了这两种数据行为，也覆盖标量偏移 `(index << 8) | 44`。

桌面读取用例在同一个 GPU 缓冲区先后写入两组数据，通过 UAV 到 SRV 的资源状态转换排序，再执行四种读取宽度。每轮有 128 个合成请求。输入覆盖跨越地址低 32 位的进位、共享和分散地址、末端合法向量、向量越界、未按字对齐和不同高位的地址。CPU 独立按 64 位范围计算预期结果，逐字核对两轮读回。越界返回标记是测试规则。主机的缓存命中率、地址归属、非法读取行为和缺少显式同步时的可见性仍未知。

八个模块中的 75 处 `LaneSwizzle.i32` 只出现五个立即数：30、60、120、240、480，各 15 次。在 RVA `0x95e20` 的调用序列中，交换结果经条件选择后累加，随后读取第 31 通道。据此测试一个候选解释：每个 32 通道分组内按五级路由求前缀和。用例在原生 wave 和组共享内存两条路径上分别验证。逻辑 64 通道路径还核对高低两段投票掩码、前缀计数、动态索引及第 31 通道读取；原生路径额外核对活动通道最小值、广播、分支内投票和动态取值。CPU 按 GPU 回报的原生通道编号重建参考值。

每个后端运行 38 个工作组，包括空、满、稀疏投票和 32 个单点输入，逐一检验每半组中的所有输入位置。RTX 2060 报告原生范围 32–32，WARP 报告 4–4。两者通过 64 个逻辑通道的组共享对照。强制原生 64 通道用例按能力跳过，具备相应能力的设备将实际运行该用例。通道路由的 PC 验收采用单点输入和 CPU 前缀和，再用下文的射线查询检验路由差错对命中的影响。[微软 WaveReadLaneAt 语义](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/wavereadlaneat)

```powershell
ctest --preset dev -R 'bvh_reads|bvh_waves|bvh_wave64|bvh_hits' -V
```

### 从缓存读取到射线命中

`bvh_hits_hardware` 和 `bvh_hits_warp` 将上述有界地址读取、半组前缀和与射线求交接在一起。包围盒筛选和三角形求交参考 AMD GPURT 的软件路径。测试自定义一个含 64 个子包围盒的根节点，每个子项通过 64 位逻辑地址引用一个三角形。64 个逻辑通道分别读取包围盒，按两个半组的前缀和紧凑排列候选地址，再由接收通道读取顶点，按原生 wave 归约最近命中。最后跨 wave 合并距离，同距时取最小图元编号。[AMD GPURT 求交源码](https://github.com/GPUOpen-Drivers/gpurt/blob/dev/src/shaders/IntersectCommon.hlsl)

同一 GPU 缓冲区依次接收三份场景，每次先通过 UAV 写入，再转为 SRV 读取。CPU 直接遍历几何体，用双精度计算射线与三角形所在平面的交点，逐条核对候选包围盒数、命中三角形数、最近距离和图元编号。每轮使用相同的 130 条射线，包括隔离每个叶节点的距离区间、正反向射线、斜射、边、顶点、零距离和仅穿过包围盒的情形。

| 同一批射线的结果 | 命中 | 未命中 |
|---|---:|---:|
| 分散布局，逐个覆盖 64 个叶节点 | 112 | 18 |
| 重排叶地址，重叠几何并制造等距命中 | 14 | 116 |
| 再次重排，加入地址高位错误、末端越界和退化三角形 | 108 | 22 |

RTX 2060 和 WARP 均与 CPU 逐项一致。闭区间裁剪、同距选择和非法叶地址的处理均由本用例定义。此测试验证桌面同步后的读值和命中结果。Scarlett 节点格式与缓存提示的解释保留为假设，后续根据文件中生产端的写入和消费端的读取约束逐项核对。

### PC 上的独立 BVH 验收

每个场景把同一批 136 条射线交给三条路径。CPU 用双精度逐个求交，自建计算着色器读取打包的节点，标准 DXR 从原始顶点独立构建 BLAS 和 TLAS，再执行内联射线查询。DXR 只接收有效地址对应的几何体。三条路径核对命中状态和最近距离。CPU 还检查 DXR 选中的图元确实在该距离相交，因此重合三角形可以有多个正确编号。跨实现比较使用三角形内部的交点和有余量的距离区间，边缘及端点由前一节的固定规则单独测试。[微软 DXR 射线区间规范](https://microsoft.github.io/DirectX-Specs/d3d/Raytracing.html#ray-extents)

RTX 2060 与 WARP 各完成 408 次比较。为验证比较器确实能发现错误，只改变自建着色器的输入，CPU 和 DXR 始终接收原场景。调换第 0 与第 32 个子项的地址使 4 条射线的命中结果改变，重放上一轮场景影响 102 条，把错误高位映入有效地址影响 1 条。每个故障都必须在指定射线上被检出。运行 `ctest --preset dev -R bvh_differential -V` 可以看到各场景的命中数、差异数和指定射线编号。

工程以 PC 上可复现的行为作为验收条件。真实游戏路径的下一项验收是从主 EXE 确认所用构建器、节点缓冲的输入输出和下游查询，再把这些约束加入 PC 回归。

### 动态依赖对启动评估的影响

已核对本构建 AMD 加载器的五个 `GetProcAddress` 调用点。按描述符中的功能值，`0x10000` 路径选择包内的 upscaler，其五个导出均可匹配。`0x20000` 和 `0x30000` 路径选择 `amd_fidelityfx_framegeneration_xbox.dll`，当前目录和种子清单均未列出该文件。加载函数先查已加载模块，必要时再调用 `LoadLibraryA`。静态分析尚不能判断主程序是否请求帧生成。[AMD FidelityFX 公开接口和功能编号](https://github.com/GPUOpen-LibrariesAndSDKs/FidelityFX-SDK/blob/main/Kits/FidelityFX/api/include/ffx_api.h)

主 EXE 接收报告新增 `dependency_paths`。从入口出发，它列出包内依赖的一条解释路径，优先显示普通导入链，同时标记延迟导入及已确认的 AMD 条件分支。AMD 分支记录仅适用于 SHA-256 匹配的加载器。未解析的运行时查找、系统转发链路和真实执行顺序仍需独立证据。在没有主 EXE 时可以分别以各 DLL 为起点：

```powershell
.\out\pe-env\Scripts\python.exe -B tools/dependency_paths.py out/dependencies/pre-exe.json |
    Set-Content out/dependencies/pre-exe-paths.json -Encoding utf8
```

## 资源分块与着色器格式检查

在开发构建完成后运行以下命令。自建像素着色器提供已知的 DXIL 阳性对照。

```powershell
python -B tools/resource_inventory.py "game-files/<构建目录名>" --shader-control out/build/dev/triangle_ps.cso
```

`out/resources/<构建目录名>.json` 按布局的目标路径记录安装分块、标记、字节数和缺项。报告记录全部构建文件的文件头特征，对 `appdata0.rpf`、`common.rpf` 和 `shaders.rpf` 的原始字节做全文件标记检查。检测到候选 DXBC 容器时核对长度、分段边界和 DXIL 程序头。报告的 `sample_streams` 仅覆盖各文件前 4 MiB 内符合筛选条件的最多八个 zlib 流，明文留在内存中。该样本不足以推断归档内其他条目的表示。安装顺序和运行时 I/O 需分别验证。[微软 DXIL 容器说明](https://github.com/microsoft/DirectXShaderCompiler/blob/main/docs/DXIL.rst) · [RPF9 压缩流观察来源](https://gtamodx.com/columns/eXk_fiBUaYta)
