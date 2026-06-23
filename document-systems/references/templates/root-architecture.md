<!--
Template for <DOC_ROOT>/architecture.md (root system overview).

Usage: the main agent reads this file, replaces every placeholder per the rules
below, REMOVES this leading comment block, and writes the result to
<DOC_ROOT>/architecture.md.

============================================================
Placeholder rules
============================================================

Inline values (single token):
  <REPO_NAME>         repo directory name (basename of repo root)
  <YYYY-MM-DD>        today's date, ISO form
  <SUBSYSTEM_COUNT>   total number of subsystems from Phase 2
  <DOC_ROOT>          absolute doc folder for this repo (<WIKI_BASE>/<DOMAIN>/<REPO_NAME>)
  <DOC_GIT_ROOT>      git work tree owning the docs (<WIKI_BASE>)
  <DOC_REL>           doc pathspec inside the wiki repo (<DOMAIN>/<REPO_NAME>)
  (the three above appear in the 文档维护说明 hints below — substitute the real
   resolved values when writing the file)

Block placeholders (multi-line, generated from Phase 2 data):

<SUBSYSTEM_TABLE_ROWS>
  One row per subsystem from Phase 2 discovery, format:
    | <name> | <类型> | <port> | <path> | <deps> | [→](./<name>/architecture.md) |
  Field rules:
    类型  : map subsystem_type → Chinese label
            java-service  → Java 服务
            java-lib      → Java 共享库
            frontend      → 前端
            node-service  → Node 服务
            python-service→ Python 服务
    port  : first entry in hints.ports; if absent, write "—"
    deps  : comma-joined subsystem.deps; if empty, write "—"

<DEPENDENCY_GRAPH_BODY>
  Body lines INSIDE the mermaid fence (do not emit the fence itself).
  Two kinds of lines:
    Node declaration (one per subsystem):
      <name>["<name><br/>:<port>"]   for services with a port
      <name>["<name><br/>共享库"]     for java-lib
      <name>["<name>"]                for services without a port
    Edge (one per (subsystem, dep) pair):
      <subsystem> --> <dep>

<TOPOLOGY_LAYERS>
  Bullet list, one bullet per layer from the topological sort:
    - **L<idx>**：<comma-joined subsystem names of that layer>
  Append "（基础层）" to the L0 bullet only.

<COMMUNICATION_PROTOCOL_ROWS>
  One row per protocol that ACTUALLY appears in any subsystem's hints.outbound.
  Detect protocols by prefix in hints.outbound entries:
    feign:  → HTTP (Feign / Axios)
    grpc:   → gRPC
    kafka:  → Kafka
    mqtt:   → MQTT
    ws:     → WebSocket
  Canonical row template:
    | <protocol display name> | <usage description> | <comma-joined subsystem names that use it> |
  Suggested usage descriptions (use only if the protocol is present):
    HTTP (Feign / Axios)  | 同步业务调用
    gRPC                  | 流式 / 高性能 RPC
    Kafka                 | 异步事件、状态广播
    MQTT                  | 设备消息双向通道
    WebSocket             | 实时推送
  Omit any row whose protocol is not present anywhere.

<REPO_COMMON_INDEX_ROWS>
  One row per repo-level common document under <DOC_ROOT>/_common/, format:
    | [<name>](./_common/<name>.md) | 仓库级 | <common_type> | <one-sentence purpose> |
  Detect them from <DOC_ROOT>/_common/*.md frontmatter (common_type / owns).
  If there are no repo-level common documents yet, write a single line containing only: 无
  Note: init scans <DOC_ROOT>/_common/ for REPO-level rows only. Domain-level common rows
  (linking ../_common/) and global common rows (linking ../../_common/) are added later by the
  engine's update_root common_index_entry op (which selects the correct relative prefix based on
  the common document's level field). Do not pre-populate domain/global rows during init.

<AUXILIARY_RESOURCES>
  Bullet list, one per item in discovery JSON `resources`:
    - `<name>/` — <purpose>
  If `resources` is empty, write a single line containing only: 无

============================================================
Output rules
============================================================

- Section headers (## …) and table column headers are FIXED — do not rename.
- The "文档维护说明" section is fixed text; do not modify.
- After substitution, delete this entire HTML comment block before writing
  the file.
-->

# 系统总览

> 由 `/document-systems` 自动生成
> 仓库：<REPO_NAME>
> 最近更新：<YYYY-MM-DD>
> 子系统数量：<SUBSYSTEM_COUNT>

## 子系统清单

| 子系统 | 类型 | 端口 | 路径 | 上游依赖 | 详细文档 |
|---|---|---|---|---|---|
<SUBSYSTEM_TABLE_ROWS>

## 依赖关系图

```mermaid
graph TD
<DEPENDENCY_GRAPH_BODY>
```

## 拓扑层级

层级用于决定文档生成顺序，下层依赖上层。

<TOPOLOGY_LAYERS>

## 跨系统通信方式

| 协议 | 使用场景 | 涉及子系统 |
|---|---|---|
<COMMUNICATION_PROTOCOL_ROWS>

## 数据资产索引指引

各子系统的具体数据资产（关系型表 / Redis key / Kafka topic / MongoDB collection / gRPC stub / 对外 HTTP）清单见各自文档的 §7 数据资产：

- `<子系统>/architecture.md#7-数据资产`

本根文档不重复枚举，避免双向维护成本。需要跨子系统反查某张表 / topic 的使用情况时，建议在 IDE 中全局搜索表名或 topic 名。

## 仓内公共文档

跨子系统共享、无单一属主的事实（术语 / 共享库契约 / 公共协议 / 基础设施约定）由仓库级公共文档 `./_common/` 持有；子系统文档以锚点引用、不复制其内部细节。本域内跨仓库共享事实见域级 `../_common/`；跨域或全公司级共享事实见全局 `../../_common/`。

| 公共文档 | 级别 | 类型 | 说明 |
|---|---|---|---|
<REPO_COMMON_INDEX_ROWS>

## 辅助资源

<AUXILIARY_RESOURCES>

## 文档维护说明

本文档由 `/document-systems` skill 生成。默认命令不会重新执行 Discovery/拓扑；当代码结构发生重大变化（新增/删除子系统、依赖关系变化）后，使用 `--force` 重建子系统清单与根文档。

日常更新全部子系统：`/document-systems`：更新全部子系统并审校。
单独更新某子系统：`/document-systems --only=<子系统名>`。
重新 Discovery/拓扑并全量重生成：`/document-systems --force`。
仅基于已保存清单重写系统总览：`/document-systems --step=root`。

查看待确认疑问：在 IDE 中全局搜索 `## 10. 待确认`，或运行 `grep -rnF "## 10. 待确认" <DOC_ROOT>`（PowerShell 用 `Select-String -Pattern '## 10\. 待确认' -Path <DOC_ROOT> -Recurse`）。
查看本次相对上次的差异：`git -C <DOC_GIT_ROOT> diff HEAD -- <DOC_REL>/`；还原某子系统的上一版：`git -C <DOC_GIT_ROOT> restore --source=HEAD -- <DOC_REL>/<子系统>/architecture.md`。
