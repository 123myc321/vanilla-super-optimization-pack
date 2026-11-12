# 选型经验：21 个 mod 是怎么挑出来的

这份文档记录**取舍过程**，不是 mod 广告。目标是让下一个人能复现判断，而不是只照抄列表。

## 1. 先定原则，再看 mod

| 原则 | 含义 | 反面做法 |
|---|---|---|
| 先审计，再加装 | 已有配置决定了大半性能，空配置往往是“全部默认开启” | 看到 TPS 低就再装一个优化 mod |
| 一个功能只留一个实现 | 两个区块引擎、两个红石重写、两个渲染批处理必然打架 | “多多益善”式堆 mod |
| 分清“算得更快”和“算得更少” | 前者通常安全，后者一定改变机制 | 把降低 tick 频率当成纯优化 |
| 可回退 | 每个开关都能单独关掉，配置有备份 | 直接改 jar、写死逻辑 |
| 数据不可逆的 mod 单独评估 | 自定义方块/物品一旦写入存档，移除就缺方块 | 把展示框、存储类 mod 当普通优化 |
| 版本下限要写清 | mod 声明的 loader/MC 下限可能高于你的服务端 | 只看“支持 26.2”就装 |

## 2. 分层选型

优化 mod 不是同一类东西。按层挑，才能判断是否重复、是否冲突。

| 层 | 作用 | 本包选择 | 备注 |
|---|---|---|---|
| 游戏逻辑 | 减少方块/实体/流体/红石的重复计算 | Lithium | 改变机制最多的一类 |
| 区块与线程 | 异步加载/序列化、区块任务调度 | C2ME、VMP | 两者职责不同，可共存 |
| 世界生成 | 噪声、表层、群系、结构 | zfastnoise | 与 C2ME 的密度函数编译互补 |
| 内存 | 方块状态、模型、资源去重 | FerriteCore、ModernFix | 低内存机器收益最大 |
| 网络 | Netty 事件循环、包合并、包上限 | Krypton、PacketFixer | 玩家越多越明显 |
| 渲染 | 区块网格、可见性剔除、UI 批处理 | Sodium、EntityCulling、MoreCulling、ImmediatelyFast | 纯客户端 |
| 客户端功耗 | 失焦降帧 | Dynamic FPS | 不影响服务端 |
| 服务端调度 | 激活范围、低 TPS 补偿、出生点、树叶 | ServerCore、TT20、Ksyxis、LeavesBeGone | 全部会改变行为，只进 full |

## 3. 逐个选择理由

### 3.1 双侧（客户端 + 服务端）

| Mod | 为什么选 | 风险/注意 |
|---|---|---|
| **Lithium** | 覆盖最广的逻辑优化，单一 mod 顶十几个小优化 | 默认开启的项里包含红石线、流体、tick 调度、刷怪、爆炸；`strict` 关掉 12 项 |
| **C2ME** | 区块加载/生成/序列化的并发引擎，26.2 生态事实标准 | `asyncSerialization`、`allowPOIUnloading`、流体后处理改期都会改变时序；`strict` 全回原版 |
| **ModernFix (mVUS 分支)** | 启动速度、动态资源、模型/注册表去重；上游 26.2 分支由 mVUS 维护 | 部分 mixin 是 BETA，默认不开；不要和同类“动态资源”mod 叠加 |
| **FerriteCore** | 方块状态内存压缩，8 GB 机器收益明显 | 极少数情况下 `useSmallThreadingDetector` 会引发难复现崩溃，保持默认关闭 |
| **Krypton** | 网络栈优化，正版/离线服都有效 | 与代理端（Velocity/Bungee）叠加时注意重复压缩 |
| **PacketFixer** | 放宽包/NBT 上限，避免大区块、大容器被踢 | `allSizesUnlimited` 会削弱包大小防护，公网服可改回默认上限 |

### 3.2 仅服务端

| Mod | 为什么选 | 风险/注意 |
|---|---|---|
| **VMP** | 高玩家数下的区块发送、实体追踪、登录异步加载 | `use_async_portals` 改变传送门时序，`strict` 关闭 |
| **zfastnoise** | 表层/噪声/群系生成加速，与 C2ME 互补 | 1.1.x 要求 Fabric Loader ≥ 0.19.5；本包锁 1.0.40 以兼容 0.19.3 |
| **ServerCore** | 激活范围、动态调节、刷怪上限、村民惰化、繁殖上限，一个 mod 覆盖服务端大头 | 几乎每一项都改变行为；`full` 才装，且要逐项确认 |
| **TT20** | 低 TPS 时按 `ticks*tps/20` 补偿破坏/吃/拾取/传送等耗时 | 只修症状不修根因；会改变动作时长，`full` 才装 |
| **Ksyxis** | 启动时不加载出生点常加载区块 | 26.2 上效果已经很小（官方说明：登录时 7×7 不加载 + 取消单人 500ms 延迟）；依赖出生点的机器会停 |
| **LeavesBeGone** | 树叶 5–20 tick 衰减，减少随机刻与更新 | 固定衰减时间，改变原版随机性；`full` 才装 |

### 3.3 仅客户端

| Mod | 为什么选 | 风险/注意 |
|---|---|---|
| **Sodium** | 渲染管线重写，FPS 提升的核心 | 与 OptiFine 不兼容；部分 Fabric 渲染 API mod 需要 Indium，但 26.2 暂无 Indium 构建 |
| **EntityCulling** | 异步可见性剔除，实体/方块实体多时收益大 | 与光影/特殊渲染 mod 可能有视觉瑕疵 |
| **MoreCulling** | 方块面、模型、告示牌等剔除 | 依赖 Cloth Config；与同类剔除 mod 叠加要先测 |
| **ImmediatelyFast** | 即时渲染、UI、地图批处理 | 少数 GUI mod 可能闪烁，可单独关 |
| **Dynamic FPS** | 失焦/空闲降帧，笔记本省电降温 | 后台挂机时画面会明显降帧，属预期 |

### 3.4 自动解析的前置

`tools/build_pack.py` 会沿 Modrinth 的 `required` 依赖递归补齐：

- Fabric API（几乎所有 mod）
- Cloth Config（MoreCulling）
- Puzzles Lib、Forge Config API Port（LeavesBeGone）
- zconfig（旧版 zfastnoise；1.0.40 不再需要，脚本会自动去掉）

前置只装到**需要它的一侧**：客户端 mod 的前置不会进服务端，反之亦然。

## 4. full 到底改了什么

把“性能”与“机制”分开看。以下全部只在 `full` 生效：

| 开关 | 行为变化 |
|---|---|
| Lithium 默认全开 | 红石线充能顺序、流体流动、tick 调度、随机刻遍历、刷怪集合、爆炸、游戏事件、方块模式匹配、温度缓存、比较器追踪 |
| C2ME `asyncSerialization` | 区块读写异步化，崩溃时最后写入窗口与顺序不同 |
| C2ME `allowPOIUnloading` | 区块卸载时卸载 POI，按需重载 |
| C2ME `optimizeAquifer` | 含水层生成走优化路径，可能与改世界生成的 mod 冲突 |
| C2ME 流体后处理改期 / 过滤 | 流体更新从生成阶段挪到调度 tick，落地时序变化 |
| C2ME `autoSave.mode=ENHANCED` | 自动保存在 tick 后的空闲时间做 |
| VMP `use_async_portals` | 传送门搜索/创建异步，跨维度动作可能晚 1 tick |
| zfastnoise `end` / `fixed` / `trivial` | 末地群系、单群系、简单表层走快速路径 |
| ServerCore 激活范围 | 远离玩家的实体按间隔 tick，掉落物/水中的实体跳过 1/4 tick |
| ServerCore `lobotomize-villagers` | 卡在 1×1 的村民降低 tick 频率 |
| ServerCore 繁殖上限 | 同类型 32 只 / 64 格内禁止继续繁殖 |
| ServerCore 刷怪上限 | 僵尸增援、传送门随机刻、刷怪笼、蠹虫强制走 mobcap |
| ServerCore 动态调节 | 过载时自动降 chunk tick distance / mobcap / 视距 |
| ServerCore `cancel-duplicate-fluid-ticks` | 取消每 tick 第二次流体随机刻 |
| TT20 全部加速 | 破坏、吃、拾取、传送、睡眠、药水、流体、昼夜、弓箭、随机刻、生长/繁殖计时、TNT 全部按 TPS 补偿 |
| Ksyxis | 不加载出生点常加载区块 |
| LeavesBeGone | 树叶固定 5–20 tick 衰减 |

如果这些里有任何一项是玩法核心，请用 `strict`，或按文件逐项关掉。

## 5. 被拒绝 / 未采用的方案

| 方案 | 结论 | 原因 |
|---|---|---|
| **dimparallel（维度并行）** | 不采用 | 只并行下界/末地 tick，主世界仍单线程；worker 读未加载区块得到空气；跨维度动作延迟 1 tick；与 C2ME 的 `ServerChunkCache` mixin 冲突 |
| **Moonrise** | 不采用 | Paper 系区块系统，Fabric 不可用 |
| **FastItemFrames** | 不采用 | 已把展示框写成自定义方块；移除会导致存档缺方块，数据不可逆 |
| **letmedespawn** | 不采用 | 刷怪笼生成的生物会自然消失，直接改变刷怪塔产出 |
| **Noisium** | 不采用 | 26.2 无 Fabric 构建（仅有第三方 fork，未验证） |
| **FastSuite** | 不采用 | 26.2 无构建；配方查找优化收益也有限 |
| **Indium** | 不采用 | 26.2 无构建；缺少它时部分 Fabric 渲染 API mod 不可用 |
| **Cull Less Leaves** | 不采用 | 26.2 无构建 |
| **Nvidium** | 可选，不进默认包 | 仅 NVIDIA、仍为 beta；与 Sodium 版本强绑定 |
| **Alternate Current** | 不采用 | 与 Lithium 的红石线优化重叠，两者叠加的更新顺序未验证 |
| **Structure Layout Optimizer** | 不采用 | 改结构布局计算，26.2 构建与兼容性未验证 |
| **Adaptive Performance Tweaks (APT)** | 不采用 | 大量 gamerule/视距/刷怪动态修改，边界不可控 |
| **obe（方块实体优化）** | 不采用 | 改变方块实体 tick 行为，且与 26.2 兼容性存疑 |
| **RailOptimization** | 不采用 | 26.2 构建/维护状态不明，收益集中在矿车场景 |
| **ResourcefulConfig** | 不采用 | 只是前置库 |
| **FastAsyncWorldSave / 异步存档类** | 不采用 | 未在 Modrinth 找到 26.2 可信构建；异步存档必须有 drain 与失败回退，否则崩溃丢数据 |
| **spark** | 不进包 | 诊断工具，不是优化；建议单独放 `mods/` 用完即删 |
| **Chunky** | 不进包 | 预生成工具，不是运行时优化；服务端建议装 |
| **OptiFine** | 不采用 | 与 Sodium 生态冲突 |

## 6. 配置审计：最容易踩的坑

1. **空配置文件 = 全部默认开启**，不是“关闭”。
   Lithium 的空 `lithium.properties` 就是全默认优化。要关某项必须写 `mixin.xxx=false`。
2. **看启动日志确认生效**。
   Lithium 会打印 `N override(s) found`；C2ME/VMP/ModernFix 会打印配置变更。只看文件存在不算数。
3. **不要用“我装的是优化 mod”代替审计**。
   同一个 mod 的不同版本默认值会变；分支（如 ModernFix-mVUS）也可能改默认。
4. **版本下限要读 `fabric.mod.json`**。
   本包在冒烟测试时就抓到：zfastnoise 1.1.1 声明 `fabricloader >=0.19.5`，而基线是 0.19.3。最终锁 1.0.40。
5. **区分“加载成功”和“行为正确”**。
   服务端能 `Done` 只说明依赖齐全；机制是否正确要靠固定负载与对照测试。

## 7. 冲突判断速查

| 组合 | 判断 |
|---|---|
| Lithium + C2ME | 可以，职责不同；但同时开红石/流体优化要接受行为变化 |
| C2ME + dimthread | 不可以，C2ME 明确说明 mid-tick chunk tasks 与 Dimensional Threading 不兼容 |
| Sodium + OptiFine | 不可以 |
| Sodium + Indium | 需要 Indium，但 26.2 暂无构建 |
| EntityCulling + MoreCulling | 可以，前者实体、后者方块面 |
| 两个“动态资源/模型去重”mod | 不要，ModernFix 已覆盖 |
| 两个红石重写（Lithium + Alternate Current） | 不要，更新顺序不可预测 |
| 两个区块引擎（C2ME + Moonrise/FastAsyncWorldSave） | 不要 |
| Ksyxis + 出生点机器 | 不要，机器会停 |
| ServerCore 动态调节 + 手动改视距 | 会互相覆盖，二选一 |

## 8. 测试方法

- **固定负载**：固定假人数量、固定坐标、固定视距，至少跑两轮
- **看分布不看单点**：tick 中位数、p95、最大值；单次尖峰不算回归
- **排除干扰**：spark 在 Windows 上 attach 会暂停 10–15 秒，这段窗口不计入稳态
- **先测基线再改**：同一世界、同一启动参数
- **机制验证**：红石时钟、刷怪塔、村民交易、流体复制、传送门，各留一个可重复的小装置

参考数据（另一台 26.2 Fabric 服务端，固定假人 1 分钟窗口）：

| 配置 | tick 中位数 | p95 | 最大值 |
|---|---|---|---|
| 未优化基线 | 16.3 ms | 20.4 ms | 65.4 ms |
| 纯计算优化（机制优化全开） | 9.2–9.5 ms | 12.0 ms | 43.5 ms |
| 机制安全配置 | 16.7 ms | 24.9 ms | 52.4 ms |

结论：**机制相关的优化一关，性能基本回到原版**。这不是配置没生效，而是完整性真实的价格。追求极限就用 `full`，别期待两全。

## 9. 上线检查表

```text
[ ] Java 版本 = 25，Fabric Loader = 0.19.3
[ ] 只装了当前侧需要的 mod（客户端不要装 ServerCore/TT20/Ksyxis）
[ ] 启动日志无 Missing/Incompatible/Mod resolution failed
[ ] Lithium 打印了预期的 override 数量
[ ] 世界与 config/ 已备份
[ ] 固定负载跑过两轮，记录 tick 中位数/p95
[ ] 红石、刷怪、村民、流体、传送门各验证一个装置
[ ] 确认出生点机器不依赖常加载区块（否则移除 Ksyxis）
[ ] 确认繁殖上限/村民惰化可接受（否则关 ServerCore 对应项）
```

## 10. 发布与隐私

- 仓库只存**元数据与哈希**，不存 jar：避免许可证问题，也避免“整合包带毒”的信任成本
- 下载地址全部指向 Modrinth 官方 CDN
- 文档与示例不含服务器地址、种子、玩家名、UUID、本机路径
- 版本锁定到具体构建，升级必须显式重新生成 `pack.json`
