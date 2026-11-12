#!/usr/bin/env sh
# 示例启动脚本：Minecraft 26.2 / Fabric 0.19.3 / Java 25
# 8 GB 内存机器用 4G；服务端与客户端同机时把 -Xmx 降到 3G。
# 参数解释见 docs/tuning.md。

cd "$(dirname "$0")" || exit 1
mkdir -p logs

exec java -Xms4G -Xmx4G \
  -XX:+UseG1GC -XX:+ParallelRefProcEnabled -XX:MaxGCPauseMillis=200 \
  -XX:+UnlockExperimentalVMOptions -XX:+DisableExplicitGC -XX:+AlwaysPreTouch \
  -XX:G1NewSizePercent=30 -XX:G1MaxNewSizePercent=40 -XX:G1HeapRegionSize=8M \
  -XX:G1ReservePercent=20 -XX:G1HeapWastePercent=5 -XX:G1MixedGCCountTarget=4 \
  -XX:InitiatingHeapOccupancyPercent=15 -XX:G1MixedGCLiveThresholdPercent=90 \
  -XX:G1RSetUpdatingPauseTimePercent=5 -XX:SurvivorRatio=32 \
  -XX:+PerfDisableSharedMem -XX:MaxTenuringThreshold=1 \
  -XX:ReservedCodeCacheSize=512M -XX:AutoBoxCacheMax=20000 \
  -XX:+ExitOnOutOfMemoryError -Djava.awt.headless=true \
  -Xlog:gc*:file=logs/gc.log:time,uptime,level,tags:filecount=5,filesize=10M \
  -jar server.jar nogui
