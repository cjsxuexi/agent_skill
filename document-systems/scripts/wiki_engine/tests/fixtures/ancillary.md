# port-device 告警业务架构文档

> 由 `/document-systems` 自动生成，最近更新：2026-05-20

## 1. 概述

设备告警专题文档，自成一套章节方案（light，不受 §1–§10 子系统契约约束）。

## 2. 功能需求

- 实时告警推送
- 告警历史归档

## 3. 业务流程

告警从设备上报到通知的链路。

## 10. 待确认与优化建议

无

## 11. 附录：代码锚点索引

- `AlarmService#handle (src/main/java/ai/fabu/device/alarm/AlarmService.java)`
- `AlarmController#list (src/main/java/ai/fabu/device/alarm/AlarmController.java)`
