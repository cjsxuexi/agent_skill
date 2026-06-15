# port-data 架构文档

> 由 `/document-systems` 自动生成，最近更新：2026-05-14
> 上一级：[系统总览](../architecture.md)

## 1. 概览

本系统是港口数据报表服务，基于 spring-boot + mybatis-plus。端口 17004。

## 2. 入口与启动

主类 `DataApplication (src/main/java/ai/fabu/data/DataApplication.java)`。

## 3. 目录结构

- `controller/` — 对外接口
- `service/` — 业务逻辑

## 4. 对外接口

| 接口 | 方法 | 锚点 |
|---|---|---|
| `/api/report/shift` | GET | `ShiftController#shift (src/main/java/ai/fabu/data/common/controller/ShiftController.java)` |

## 5. 上下游依赖

上游：调用 [port-service § 对外接口](../port-service/architecture.md#4-对外接口) 获取作业数据。
下游：无。

## 6. 业务流

### 6.1 工班报表查询

#### 处理流程

1. `ShiftController#shift` 接收请求。

#### 数据交互

- 关系型数据库表（R/W）：`dws_vessel_job` R

## 7. 数据资产

### 7.1 关系型数据库表
| 表名 | 主键 / 关键索引 | 读取的入口 | 写入的入口 |
|---|---|---|---|
| `dws_vessel_job` | — | 工班报表查询 | 无 |

### 7.2 Redis
无

## 8. 关键配置项

`bootstrap.yml` 中的 Nacos 配置。

## 9. 已知问题 / 历史决定

无

## 10. 待确认 / 疑问

- [§7.1 关系型数据库表] 多个 `@TableName` 未显式写 `value`，运行期表名依赖 MyBatis-Plus 默认命名策略和 Nacos 数据源配置；本文保留源码可 grep 的类名或显式表名。已检查：`src/main/java/ai/fabu/data/common/model/entity/`。建议核实方向：运行环境 MyBatis-Plus 表名转换规则与真实数据库 DDL。
- [§5.2 下游] 本服务源码只能确认自身暴露的入口，不能穷尽所有调用方。已检查：`src/main/java/ai/fabu/data/common/controller/`。建议核实方向：从网关路由反查。

## 11. 用户操作维度报表数据链路核对（2026-05-14）

本轮新增 [报表数据链路待补充问题清单](./lineage-open-questions.md)，按数据生成链路核对工班报表。
