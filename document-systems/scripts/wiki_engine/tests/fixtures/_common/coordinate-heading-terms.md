---
common_type: glossary
level: repo
owns: coordinate-heading-terms
---

# 航向角、ego 坐标系与 UTM 口径说明

## 1. 范围与级别

仓库级公共文档，被 port-telecontrol、port-ingest 引用其坐标 / 航向口径术语。

## 2. 术语表

| 术语 | 含义 | 来源 / 出处 |
|---|---|---|
| `headingAngle` | PRD 上报航向角，正北为 0、顺时针为正，单位度 | `../spec/external-kafka-upload-20260521/external-kafka-upload-project-implementation.md` |
| `EPSG:32651` | UTM Zone 51 投影坐标系 | 同上 |

## 待确认 / 疑问

- [§2 术语表] `acc_x` / `acc_y` 是否始终为 UTM 全局东 / 北分量，待车端联调确认。已检查：上报实现文档。建议核实方向：车端原始数据口径。
