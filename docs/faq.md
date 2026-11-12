# 常见问题

## 启动与依赖

### 启动报 `Mod resolution failed` / `Incompatible mods found`

看日志里的 `Fix:` 行，通常会直接写“把 X 换成 Y”。常见原因：

- Fabric Loader 低于 mod 要求。本包基线是 **0.19.3**；如果手动换了新版 zfastnoise（1.1.x 要求 ≥0.19.5），要么升级 Loader，要么回到 `pack.json` 里锁定的 1.0.40
- 少装前置。用 `install.py` 安装会自动补齐 Fabric API、Cloth Config、Puzzles Lib、Forge Config API Port
- 混入了旧版本 jar。`mods/` 里同一 mod 只能留一个文件

### 客户端需要 Fabric API 吗

需要。`pack.json` 已包含；手动安装时不要漏。

### 服务端需要装客户端 mod 吗

不需要。`install.py --side server` 会跳过 Sodium、EntityCulling、MoreCulling、ImmediatelyFast、Dynamic FPS。

### 支持 Java 25 以外的版本吗

包按 Java 25 构建与测试。Java 21 可能能跑，但 26.2 的 Fabric 生态默认面向 25，出问题不奇怪。

## 性能

### 服务器启动很慢

- 首次启动要生成出生点区域，30 秒到几分钟都正常
- 预生成过的世界会快很多（见 [tuning.md](tuning.md#3-预生成)）
- Ksyxis 只减少登录时的区块加载，不负责首次世界生成
- 磁盘慢、杀毒软件实时扫描会明显拖慢

### TPS 低，先查什么

1. `spark profiler start` → 跑 60 秒 → `spark profiler stop`，看热点
2. 实体/区块数量：`/spark tps`、`/spark health`
3. 视距/模拟距离是否过高（最大的单一杠杆）
4. 是否有玩家在跑图、刷怪塔堆积、大量掉落物
5. 内存是否长期接近上限、GC 日志是否有长暂停

不要一上来就加 mod。先定位是 CPU、内存、IO 还是网络。

### 客户端 FPS 低

- 确认 Sodium 已加载（视频设置里能看到 Sodium 的界面）
- 先降模拟距离，再降渲染距离
- 关闭光影再对比；光影不是本包内容
- 检查是否误装了 OptiFine（与 Sodium 冲突）
- 笔记本插电、关闭后台录屏

### `Can't keep up` 只在启动时出现

玩家同时登录/区块集中加载造成的尖峰，不等于稳态问题。看登录后 30 秒的 tick 分布。

## 机制异常

### 红石机器时序不对 / 刷怪塔效率变了

你在用 `full`。`full` 明确开启了 Lithium 的红石线、流体、tick 调度、刷怪集合、爆炸、游戏事件优化。

处理：

1. 换 `strict` 配置（保留世界，只换 `config/` 与 mod 集合）
2. 或只关掉相关项，例如 `config/lithium.properties`：

```properties
mixin.block.redstone_wire=false
mixin.block.fluid=false
mixin.block.fluid.flow=false
mixin.world.tick_scheduler=false
mixin.world.chunk_ticking=false
mixin.collections.mob_spawning=false
mixin.minimal_nonvanilla.spawning=false
mixin.world.explosions=false
mixin.world.game_events=false
mixin.block_pattern_matching=false
mixin.world.temperature_cache=false
mixin.util.inventory_comparator_tracking=false
```

### 村民不动 / 不繁殖

`full` 的 ServerCore 默认开启：

- `lobotomize-villagers`：卡在 1×1 的村民降低 tick 频率
- `breeding-cap`：同类型 32 只 / 64 格内禁止继续繁殖

改 `config/servercore/config.yml` 里对应的 `enabled: false`，重启生效。

### 出生点的机器停了

`full` 装了 Ksyxis，不加载出生点常加载区块。要么把机器移到有玩家的区域，要么移除 `mods/Ksyxis-*.jar`。`strict` 不装 Ksyxis。

### 树叶瞬间消失

`full` 的 LeavesBeGone 把所有树叶衰减固定为 5–20 tick。移除 jar 或改用 `strict`。

### 传送门有 1 tick 延迟 / 跨维度动作不同步

`full` 的 VMP 开了 `use_async_portals=true`。改 `config/vmp.properties`：

```properties
use_async_portals=false
```

`strict` 默认就是关闭的。

### 区块回档 / 崩溃后少了几秒建筑

`full` 的 C2ME 开了异步序列化，`server.properties` 也可能关了同步写入。风险是真实存在的：

- 保留自动备份
- 重要施工后手动 `/save-all flush`
- 不能接受就改 `config/c2me.toml`：

```toml
[chunkSystem]
asyncSerialization = false
```

### 服务器过载时视距自己变了

`full` 的 ServerCore 开了 `dynamic`，会按 MSPT 自动降 chunk tick distance / mobcap / 视距。不想要就关：

```yaml
dynamic:
  enabled: false
```

## 安装与切换

### 怎么从 full 换成 strict

1. 停服，备份世界和 `config/`
2. 删除 `mods/` 里 full 独有的 jar：ServerCore、TT20、Ksyxis、LeavesBeGone
3. 用 `python install.py --side server --profile strict --dir <目录> --force-config` 覆盖配置
4. 启动，确认日志没有缺依赖

或者直接在一个干净目录装 strict，把世界拷过去。

### 怎么只装其中几个 mod

`pack.json` 每个条目都有 `env`、`profiles`、`filename`、`url`、`sha512`。按需下载并校验即可；注意前置（Fabric API 等）。

### 更新整合包

```powershell
python tools/build_pack.py --all
python tools/verify_pack.py
```

然后重新安装。升级前备份世界与 `config/`。不要直接覆盖 `mods/` 里旧版本文件，先删旧 jar 再装新 jar。

### 怎么完全卸载

删除安装时放入的 mod jar，恢复备份的 `config/`。本包不写注册表、不改系统、不装服务。

## 其他

### 为什么仓库里没有 jar

- 许可证：很多 mod 不允许再分发
- 信任：从官方 CDN 下载 + 哈希校验，比仓库里放二进制更透明
- 体积：仓库只保留元数据

### 能用在代理端（Velocity/BungeeCord）后面吗

可以。注意 Krypton 与代理端的压缩设置不要重复；`online-mode` 与转发配置按代理端要求设置。

### 支持 Forge / NeoForge 吗

不支持。本包是 Fabric 专用；C2ME、Lithium、VMP 等都有各自加载器的分支，但配置和版本需要重新验证。

### 遇到本包没覆盖的问题

保留 `logs/latest.log`、`crash-reports/`、`spark` 报告，先确认是不是某个开关导致的：用 `strict` 复现一次，能复现就不是 `full` 独有的机制改动。
