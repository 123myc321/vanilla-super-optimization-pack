# 原版超级优化整合包

> Vanilla Super Optimization Pack — 面向 Minecraft **26.2** / Fabric **0.19.3** / Java **25** 的全面性能整合包。
> 客户端与服务端双侧优化，提供 **full**（极限性能）与 **strict**（机制安全）两套配置。

[![Minecraft](https://img.shields.io/badge/Minecraft-26.2-3C8527)](#)
[![Fabric](https://img.shields.io/badge/Fabric-0.19.3-DBB69C)](#)
[![Java](https://img.shields.io/badge/Java-25-E76F00)](#)
[![License](https://img.shields.io/badge/License-MIT-blue)](LICENSE)

---

## 这是什么

这不是“再装一个优化 mod”的清单，而是一套**经过取舍的完整方案**：

- **21 个 mod**，覆盖渲染、内存、网络、区块、世界生成、服务端调度
- **两套配置**：`full` 追求极限性能，允许改变原版机制；`strict` 只保留不触碰红石/流体/刷怪/tick 顺序的优化
- **服务端与客户端分开安装**：同一个 `.mrpack`，启动器会按 `env` 标记自动选择对应文件
- **不打包 jar**：安装时从 Modrinth 官方 CDN 下载，按 SHA-512 校验，分发干净
- **可验证**：自带静态校验脚本、服务端冒烟测试记录、JVM/服务端参数模板

## 快速开始

### 方式一：Modrinth App / Prism Launcher（推荐）

下载 [vanilla-super-optimization-1.0.0-fabric26.2.mrpack](vanilla-super-optimization-1.0.0-fabric26.2.mrpack)，拖进启动器安装。

- 启动器会安装 `full` 配置
- 客户端只装 client 侧 mod，服务端只装 server 侧 mod

### 方式二：脚本安装（已有客户端/服务端目录）

```powershell
# 客户端
python install.py --side client --dir "C:\Users\<你>\AppData\Roaming\.minecraft"

# 服务端（极限性能）
python install.py --side server --dir "D:\servers\mc" --profile full

# 服务端（机制安全）
python install.py --side server --dir "D:\servers\mc" --profile strict
```

Windows 也可以直接用包装脚本：

```powershell
.\install.ps1 -Side server -Profile full -Dir "D:\servers\mc"
```

先看会装什么、不动文件：

```powershell
python install.py --side server --profile full --dir "D:\servers\mc" --dry-run
```

安装器行为：

- 只下载当前侧需要的 mod
- 每个文件按 `pack.json` 里的 SHA-512 校验
- 已存在且校验通过的文件直接复用，断网重跑可续
- 已存在的配置**不会静默覆盖**：内容不同会写成 `xxx.pack-new`

### 方式三：手动

`pack.json` 里每个条目都有 Modrinth 下载地址、文件名、SHA-1 / SHA-512。按 `env` 和 `profiles` 字段自行挑选即可。

## 两套配置怎么选

| | `full` | `strict` |
|---|---|---|
| 定位 | 极限性能，允许改变原版机制 | 机制安全，生电/技术服可用 |
| Lithium | 全部默认优化开启（含红石线、流体、tick 调度、刷怪、爆炸） | 关闭 12 项会改变行为的 mixin |
| C2ME | 异步序列化、POI 卸载、含水层优化、流体后处理改期全开 | 全部回退原版行为 |
| zfastnoise | `end` / `fixed` / `trivial` 开启 | 关闭 |
| VMP | 异步传送门开启 | 关闭 |
| ServerCore | 激活范围、动态调节、刷怪上限、村民惰化、繁殖上限 | 不安装 |
| TT20 | 全部加速项开启 | 不安装 |
| Ksyxis | 不加载出生点常加载区块 | 不安装 |
| LeavesBeGone | 树叶 5–20 tick 快速衰减 | 不安装 |

**如果你在生电 / 技术生存服玩，用 `strict`。** `full` 的收益真实存在，但代价同样真实：见 [docs/mod-selection.md](docs/mod-selection.md) 的“机制改变清单”。

## 装了什么

完整版本与许可证见 [docs/mod-versions.md](docs/mod-versions.md)。

| 层 | 服务端 | 客户端 |
|---|---|---|
| 游戏逻辑 | Lithium | Lithium |
| 区块/线程 | C2ME、VMP | C2ME |
| 世界生成 | zfastnoise | — |
| 内存 | FerriteCore、ModernFix | FerriteCore、ModernFix |
| 网络 | Krypton、PacketFixer | Krypton、PacketFixer |
| 渲染 | — | Sodium、EntityCulling、MoreCulling、ImmediatelyFast、Dynamic FPS |
| 调度/杂项 | ServerCore、TT20、Ksyxis、LeavesBeGone（仅 full） | — |

前置自动解析：Fabric API、Cloth Config、Puzzles Lib、Forge Config API Port。

## 服务端调优

装完 mod 只完成一半，另一半在 JVM 和服务端参数：

- JVM：G1 固定堆、代码缓存 512M、`ExitOnOutOfMemoryError`、GC 日志
- `server.properties`：`sync-chunk-writes=false`、`max-auto-save-chunks-per-tick=8`、`network-compression-threshold=512`
- 预生成：Chunky 半径 3000 起

完整参数、逐项解释和替代方案（ZGC）见 [docs/tuning.md](docs/tuning.md)。

## 延伸阅读

选型方法论、审计清单、基准脚本与自制 mod 示例单独整理在：
[123myc321/mc-tech-server-optimization](https://github.com/123myc321/mc-tech-server-optimization)

## 验证与实测

静态校验（需要先 `python tools/build_pack.py --download`）：

```powershell
python tools/verify_pack.py
```

检查内容：jar 完整性、`fabric.mod.json`、mod id 重复、Minecraft 版本范围、必需前置是否齐全、client/server 标记是否与 jar 声明一致。

服务端冒烟测试（本机 4C8T / 8 GB / Java 25，全新世界）：

| 配置 | 加载 mod 数 | 结果 |
|---|---|---|
| full | 15 | `Done (29.8s)`，RCON `stop` 干净退出，无 WARN/ERROR |
| strict | 9 | 正常启动、保存、退出，无 WARN/ERROR |

复现：

```powershell
python tools/smoke_test.py --server-src "D:\你的Fabric服务端目录" --profile full
```

脚本会把 `server.jar` + `libraries` 复制到临时目录、安装本包、用全新世界启动、通过 RCON 发送 `stop`，并检查是否有 `Mod resolution failed` 等致命错误；源目录不会被修改。

客户端未做真机启动测试（环境无图形界面），但所有客户端 jar 的 `environment` 与 mod 依赖已通过静态校验。

## 已排除的方案

以下内容**没有**进包，原因写在 [docs/mod-selection.md](docs/mod-selection.md)：

- `dimparallel`：主世界仍是单线程，跨维度动作延迟 1 tick，未加载区块读成空气
- Moonrise / Paper 系补丁：与 Fabric 不兼容
- `FastItemFrames`：会把展示框写成自定义方块，移除后世界缺方块
- `letmedespawn`：刷怪笼生物会自然消失
- `Noisium` / `FastSuite` / `Indium` / `Cull Less Leaves`：26.2 无 Fabric 构建
- `Nvidium`：仅 NVIDIA 且仍为 beta，作为可选项在文档中说明
- `Alternate Current`、`Structure Layout Optimizer` 等：与 26.2 生态或本包目标不匹配

## 目录

```text
.
├── pack.json                     # 唯一事实来源：21 个 mod 的版本/哈希/侧/配置
├── install.py / install.ps1      # 安装器
├── vanilla-super-optimization-1.0.0-fabric26.2.mrpack
├── configs/
│   ├── full/{common,server}/     # full 配置
│   └── strict/common/            # strict 配置
├── docs/
│   ├── mod-selection.md          # 选型经验、机制改变清单、被拒方案
│   ├── mod-versions.md           # 自动生成的版本表
│   ├── tuning.md                 # JVM / server.properties / 预生成
│   └── faq.md                    # 常见问题
├── examples/                     # server.properties、启动脚本模板
└── tools/
    ├── build_pack.py             # 重新解析 Modrinth、生成 pack.json 与 mrpack
    ├── verify_pack.py            # 静态校验
    └── smoke_test.py             # 服务端起停冒烟测试
```

## 更新

```powershell
python tools/build_pack.py --all      # 重新取最新版本、下载校验、生成 mrpack
python tools/verify_pack.py           # 静态校验
```

升级前请备份世界与 `config/`。`tools/mod-sources.json` 是选型清单，版本策略为“release > beta > alpha，同通道取最新”；需要锁版本时在条目里写 `"version": "x.y.z"`。

## 许可与分发

- 本仓库的脚本、配置、文档：MIT
- 各 mod 保留自己的许可证，仓库**不包含**任何 mod jar
- 安装时从 Modrinth 官方 CDN 下载，哈希与 `pack.json` 一致

## 隐私

仓库不包含服务器地址、世界种子、玩家名、UUID、路径或备份信息。示例路径统一用占位符。
