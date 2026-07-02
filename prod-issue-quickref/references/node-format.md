# 诊断树节点规则（记录时严格照此）

这是一棵**诊断决策树**：根 = 主诉现象，中间 = 判别信号（把候选根因区分开的观测），叶 = 根因。随事故一条条增量长出来。

## 三种节点

1. **`## <共有现象>`（根）** — 主诉现象，**自然语言、可归纳整合多种表现，不必逐字**（现象是给人快速匹配的）。**仅当没有已存在的现象根能匹配时才新建**；能挂到已有根就别新起。
2. **`- **判别**：<信号>`（枝）** — 把候选根因区分开、或指导用户去确认的观测（CPU/日志/前端表现/告警关键字…）。**含代码 / 日志标识时一律原样**（反引号包住）。可再缩进一层表达「细分现象」。
3. **`  - **根因**：<一句话> **确认** → [文字](相对链接#锚点)`（叶）** — 一句话根因链，标识原样；**必须**链到一篇**已存在**的 wiki 文档（架构 `§` / troubleshooting / `_common`）。

## 硬规则（校验器会查）

- 每个 `根因` 叶子**必须**含至少一个 `](....md)` 相对确认链接。
- 标识符（接口路径 / 类 / Mapper / 表 / 错误类 / 日志关键字）**原样**、反引号包。
- **禁**在树里写：恢复 / 缓解步骤、待确认清单、证据摘录、事故时间线——这些进被链接的 wiki 文档。
- 全程 UTF-8，无 `???`。
- 现象节点不受「原样」约束——可归纳。

## 真实范例（抄自 fabusurfer 仓的速查）

```markdown
## 云控卡顿 / 监控地图车辆刷不出来（卡顿或完全不显示；常伴 port-device CPU 飙升）

- **判别**：车辆**完全显示不出来**（列表总计 0 / 暂无数据）；前端 Chrome Network 看 `VEHICLE_STATUS_PUSH` 那条 WS **只有上传（↑ outgoing）帧、无回执（无 incoming 帧）**；且 mysql CPU 也飙升（~1200%）+「云控生产日志告警」群有 `BadSqlGrammarException`
  - **根因**：**生产库 schema 漏更**（`versionConfigMapper.selectPage()` 查的表加了字段、生产 MySQL 没同步 `ALTER`）→ `/ota/vehicleConfig` 每次先跑 `vehicleService.list()` 慢 SQL、再 `versionConfigMapper.selectPage()` 因缺列抛 `BadSqlGrammarException` → **报错即重试**把前面的慢 SQL 反复放大 → mysql ~1200% / port-device 700–800% → port-device 被打满、`VEHICLE_STATUS_PUSH` 推送发不出回执 → 前端拿不到车辆 → 地图空。**确认** → [port-device §6.6 OTA 流](./port-device/architecture.md#66-ota--版本--文件日志流)、[port-service §对外接口](./port-service/architecture.md#4-对外接口)
- **判别**：车辆**卡顿 / 坐标几分钟不更新**（有数据但不动，不是全空）；仅 port-device CPU 飙升、mysql 正常，日志有 `RedisCommandTimeoutException`
  - **根因**：`list-vehicle-info` 刷新循环里 Redis 调用高延迟，本地车辆缓存从 0.5s/次退化到数秒/次。**确认** → [vehicle-status-push-troubleshooting.md](./port-device/vehicle-status-push-troubleshooting.md)
```

## 追加时的落点判断

- 现象能匹配某个 `##` 根 → 在其下加一条 `- 判别 / 根因` 分支；已有等价分支就**合并/跳过**，不造重复。
- 没有能匹配的根 → 新起 `## <共有现象>` 根。
- 同一根因可有多个「现象入口」（判别分支），这是索引的价值，允许。
