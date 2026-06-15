# charge-manage-platform 架构文档

> 由 `/document-systems` 自动生成，最近更新：2026-05-18

## 1. 概述

充电管理平台，作为单系统（single mode）文档化。

## 2. 入口与启动

主类 `ChargeApplication (src/main/java/com/charge/ChargeApplication.java)`。

## 3. 目录结构

- `controller/`

## 4. 对外接口

| 接口 | 方法 | 锚点 |
|---|---|---|
| `/api/charge/list` | GET | `ChargeController#list (src/main/java/com/charge/ChargeController.java)` |

## 5. 上下游依赖

无

## 6. 业务流

### 6.1 充电列表查询

#### 处理流程

1. `ChargeController#list` 查询充电记录。

#### 数据交互

- 关系型数据库表（R/W）：`t_charge_record` R

## 7. 数据资产

### 7.1 关系型数据库表
| 表名 | 主键 / 关键索引 | 读取的入口 | 写入的入口 |
|---|---|---|---|
| `t_charge_record` | id | 充电列表查询 | 无 |

## 8. 关键配置项

无

## 9. 已知问题 / 历史决定

无

## 10. 待确认 / 疑问

无
