# port-device 架构文档

> 由 `/document-systems` 自动生成，最近更新：2026-05-20
> 上一级：[系统总览](../architecture.md)

## 1. 概述

设备管理子系统，负责 OTA 命令下发与版本管理。

## 2. 入口与启动

主类 `DeviceApplication (src/main/java/ai/fabu/device/DeviceApplication.java)`。

## 3. 目录结构

- `controller/` — 对外接口
- `service/` — 业务逻辑

## 4. 对外接口

| 接口 | 方法 | 锚点 |
|---|---|---|
| OTA 命令发布 | Redis Pub/Sub | `OTAVehicleServiceImpl#sendOtaCommand (src/main/java/ai/fabu/device/service/impl/OTAVehicleServiceImpl.java)` |

## 5. 上下游依赖

下游：[port-vehicle § 上下游依赖](../port-vehicle/architecture.md#5-上下游依赖) 订阅 OTA 命令。

## 6. 业务流

### 6.6 OTA / 版本 / 文件日志流

#### 处理流程

1. `OTAVehicleServiceImpl#sendOtaCommand` 向每车独立 topic 发布命令。

#### 数据交互

- Kafka topic（P/C）：`ota_command_topic_{vehicleName}` P

## 7. 数据资产

### 7.1 关系型数据库表
无

### 7.3 Kafka topic
| topic | P/C | 涉及入口 |
|---|---|---|
| `ota_command_topic_{vehicleName}` | P | OTA / 版本 / 文件日志流 |

## 8. 关键配置项

无

## 9. 已知问题 / 历史决定

无

## 10. 待确认 / 疑问

无
