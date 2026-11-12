# 服务端调优：JVM、server.properties、预生成

mod 只解决“代码怎么算”，JVM 和参数解决“内存怎么给、GC 怎么停、区块什么时候生成”。两者缺一不可。

## 1. JVM 参数

### 1.1 推荐配置（8 GB 内存机器，服务端独占）

```bat
java -Xms4G -Xmx4G ^
  -XX:+UseG1GC -XX:+ParallelRefProcEnabled -XX:MaxGCPauseMillis=200 ^
  -XX:+UnlockExperimentalVMOptions -XX:+DisableExplicitGC -XX:+AlwaysPreTouch ^
  -XX:G1NewSizePercent=30 -XX:G1MaxNewSizePercent=40 -XX:G1HeapRegionSize=8M ^
  -XX:G1ReservePercent=20 -XX:G1HeapWastePercent=5 -XX:G1MixedGCCountTarget=4 ^
  -XX:InitiatingHeapOccupancyPercent=15 -XX:G1MixedGCLiveThresholdPercent=90 ^
  -XX:G1RSetUpdatingPauseTimePercent=5 -XX:SurvivorRatio=32 ^
  -XX:+PerfDisableSharedMem -XX:MaxTenuringThreshold=1 ^
  -XX:ReservedCodeCacheSize=512M -XX:AutoBoxCacheMax=20000 ^
  -XX:+ExitOnOutOfMemoryError -Djava.awt.headless=true ^
  -Xlog:gc*:file=logs/gc.log:time,uptime,level,tags:filecount=5,filesize=10M ^
  -jar server.jar nogui
```

### 1.2 每组参数在做什么

| 组 | 作用 | 什么时候改 |
|---|---|---|
| `-Xms4G -Xmx4G` | 固定堆，避免运行中扩堆造成卡顿 | 内存 8 GB → 4 GB；16 GB → 6–8 GB；不要超过物理内存的 60% |
| `-XX:+UseG1GC` + `MaxGCPauseMillis` | 低延迟 GC，适合 tick 敏感场景 | 见 1.3 的 ZGC 对比 |
| `G1NewSizePercent=30 / G1MaxNewSizePercent=40` | 给年轻代足够空间，减少晋升与混合 GC | 堆 ≤ 4 GB 时有效；堆很大时可回调 |
| `G1HeapRegionSize=8M` | 区域大小与堆匹配，减少 humongous 分配 | 堆 4–8 GB 用 8M；2 GB 用 4M |
| `AlwaysPreTouch` | 启动时把堆页全部摸一遍，避免运行中缺页 | 启动会慢几秒，换来更稳的 tick |
| `DisableExplicitGC` | 忽略 `System.gc()`，防止 mod 触发全量 GC | 一般保持开启 |
| `ReservedCodeCacheSize=512M` | 大 mod 包需要更多 JIT 代码缓存 | 出现 “CodeCache is full” 时加大 |
| `AutoBoxCacheMax=20000` | 扩大 Integer 缓存，减少装箱分配 | 对区块/实体 ID 密集场景有小收益 |
| `ExitOnOutOfMemoryError` | OOM 时直接退出，交给守护脚本重启 | 生产必开，避免半死状态 |
| `PerfDisableSharedMem` | 不写 hsperfdata，减少磁盘 IO 抖动 | Linux/Windows 都可开 |
| `Xlog:gc*` | GC 日志，排障与验证调优效果 | 保留，滚动 5×10 MB 足够 |

### 1.3 G1 还是 ZGC

| | G1 | ZGC（分代） |
|---|---|---|
| 暂停 | 几 ms 到几十 ms | 通常 <1 ms |
| CPU 开销 | 低 | 高，4 核机器更明显 |
| 内存开销 | 低 | 高（需要额外堆外/染色指针空间） |
| 适用 | 4–8 核、4–8 GB、单服 | 核心多、堆大、暂停极敏感 |

```bat
java -Xms6G -Xmx6G -XX:+UseZGC -XX:+AlwaysPreTouch -XX:+ExitOnOutOfMemoryError -jar server.jar nogui
```

4 核 8 GB 的笔记本优先 G1。ZGC 在核心不足时会把 CPU 从 tick 线程抢走，TPS 反而更差。切换前用同一负载跑两轮对比 tick p95 和 GC 日志。

### 1.4 不要做的事

- 不要设 `-Xmn`：与 G1 的自适应策略冲突
- 不要把 `-Xmx` 开到物理内存 80% 以上：系统缓存和客户端会抢内存
- 不要用 `-XX:+UseParallelGC` 追求“吞吐”：停顿会直接体现为 tick 尖峰
- 不要频繁 full GC 排查内存泄漏：先看 spark 的堆直方图与 chunk 数

## 2. server.properties

```properties
# 区块写入不强制同步，崩溃时最多丢最后几秒；有备份再开
sync-chunk-writes=false

# 每 tick 最多保存 8 个区块，避免自动保存尖峰
max-auto-save-chunks-per-tick=8

# 压缩阈值提高，减少小包压缩的 CPU 开销（带宽换 CPU）
network-compression-threshold=512

# 视距/模拟距离是最大的性能杠杆，按玩家数与机器调整
view-distance=10
simulation-distance=8

# 实体广播范围，90% 可减少带宽；不影响实际实体逻辑
entity-broadcast-range-percentage=100
```

说明：

- `view-distance` 影响客户端能看到多远；`simulation-distance` 影响实体/红石/随机刻。**降模拟距离会直接改变机器行为**，生电服不要低于机器所需范围。
- `network-compression-threshold=512` 对高带宽低 CPU 的场景有利；如果是云服务器按流量计费，保持默认 256 或更低。
- `sync-chunk-writes=false` 是性能项也是风险项：断电/崩溃可能丢最后一段存档。务必保留自动备份。

## 3. 预生成

首次探索时边跑边生成是 TPS 杀手。用 Chunky 预生成：

```text
/chunky world overworld
/chunky center 0 0
/chunky radius 3000
/chunky start
```

- 半径 3000 方块 ≈ 14 万区块，4C8T 大约 20–40 分钟，磁盘 +1–2 GB
- 预生成期间不要开玩家登录；生成完 `stop` 一次再开服
- 需要下界/末地时分别执行 `world the_nether` / `world the_end`
- C2ME 会加速生成，但预生成仍然是 IO 密集，磁盘慢的机器收益有限

## 4. 系统层

| 项 | 建议 |
|---|---|
| 电源计划 | Windows 设为“高性能”，避免 CPU 降频 |
| 杀毒软件 | 把服务端目录加入排除项，避免实时扫描 jar/区块文件 |
| 页面文件 | 保持系统管理；不要禁用，OOM 前还有缓冲 |
| 磁盘 | 机械盘会影响区块读写；SSD 优先 |
| 后台程序 | 浏览器、启动器、录屏会抢 CPU/内存，压测时全部关闭 |

## 5. 如何验证调优有效

1. 固定假人、固定坐标、固定视距，跑 3 分钟
2. 记录 tick 中位数、p95、最大值（spark 或服务端自带统计）
3. 至少两轮，取稳定值；单次尖峰不算回归
4. 看 GC 日志：`logs/gc.log` 里找 Full GC、长暂停、晋升失败
5. 机制验证：红石时钟、刷怪塔、村民交易、流体、传送门各一个

> spark 在 Windows 上 attach 会暂停服务端 10–15 秒，这段窗口要从稳态数据里剔除。

## 6. 客户端侧

- 内存：`-Xmx4G` 足够大多数 26.2 整合包；不要和 32 个光影包一起开到 8G
- Sodium 的渲染距离与模拟距离分开调；先降模拟距离再降渲染距离
- 关闭垂直同步、限制帧率到显示器刷新率，降低 GPU 占用与发热
- 笔记本插电再测，电池模式会触发功耗墙
