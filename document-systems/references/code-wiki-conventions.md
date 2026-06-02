# Code Wiki Conventions

Conventions specific to wikis that document source code. Apply when the wiki target is a code repository.

---

## 1. Source-code read boundary: only the explicitly assigned `<ABSOLUTE_PATH>`

**Rule**: a subagent may only read source under the `<ABSOLUTE_PATH>` assigned to it by the dispatcher (i.e. "the current object's source"). Do not read other subsystems' source. Do not read source of jar / SDK / third-party libraries, even if locally available.

**Why**: prevents leaking the caller's internals into the callee's doc; keeps main agent / subagent context bounded.

**Counter-example**: while writing the `port-data` subsystem doc, the subagent reads `port-auth/src/...` source and copies its methods into §6 — violates both ownership and this boundary.

---

## 2. External-dependency boundary: track to the call site, not the library internals

**Rule**: data-flow tracking ends at the call site in the current object's source. Call sites include:

- `kafkaTemplate.send("topic-name", payload)`
- `feignClient.someMethod(req)`
- `restTemplate.exchange(url, ...)` / `webClient.post().uri(url)...`
- `mqttClient.publish(topic, ...)`
- gRPC stubs: `xxxBlockingStub.method(req)`
- `redisTemplate.opsForXxx().xxx(key, ...)`
- ORM mapper / repository invocations

Do not read jar / SDK source. Do not speculate about library internals (interceptors, AOP, serialization protocols, retry behavior). Document only:

- The call site's code anchor `Class#method (path)`
- The call's produced artifact: topic name, endpoint URL, table name, key pattern, gRPC service.method
- The wire contract of inputs / outputs (not how the library processes them)

For uncertain library-internal behavior, record in §10 per wiki-principles §5.

**Why**: jars typically exist as bytecode; source isn't always available. Even when readable, library internals are unstable (a dependency upgrade changes them), so deep tracking produces docs that quickly drift.

**Example**:

```
本系统在 OrderService#refund 调用 kafkaTemplate.send("order.refund.event", payload)。
后续由 Kafka broker 路由至订阅方（订阅链路非本系统职责，不在此追踪）。
```

**Counter-example**: unpack `spring-kafka-3.x.jar` and write `KafkaTemplate.doSend`'s internal partition logic into the current system's §6.

---

## 3. User-supplied knowledge as a legitimate source — with attribution

**Rule**: in conversational skills, if the user provides knowledge that source scanning can't see (jar / SDK internals, runtime config, private conventions, business rules), the subagent may write it into the doc, but must attach an attribution annotation adjacent to that content:

```
> 来源：用户口述（<YYYY-MM-DD>）
```

**Why**:

- User-supplied knowledge is often the only source for blind spots the code can't verify.
- Attribution lets later readers distinguish "code-verifiable" from "user-supplied" content, preventing the latter from being read as code-confirmed fact.
- Provides an audit trail for review.

**Example**:

```
本系统调用 `payment-sdk` 的 `PaymentClient.charge(...)`（OrderService#refund, ...）。

> 来源：用户口述（2026-05-13）
> SDK 内部对失败重试 3 次后将事件投递到 DLQ topic `payment.failed.dlq`，
> 该 topic 由风控团队消费做人工对账。

代码可验证范围仅到 charge 调用点；SDK 内部行为未读源码。
```

**Counter-example**: mixing user-supplied content into the body without attribution — later readers cannot tell what is code-evidenced.

---

## 4. §6 业务流 sub-section structure: 处理流程 + 数据交互

**Rule**: in §6 业务流, every entry (HTTP endpoint / Kafka consumer / gRPC method / scheduled job / other externally triggered handler) MUST contain two sub-sections:

### 6.x.1 处理流程

The current object's internal `Class#method` sequence (semantic-node granularity; no need to list every method). Each step includes a current-object code anchor `Class#method (path)`. For multi-step flows that span calls, use a mermaid `sequenceDiagram`; otherwise use a numbered list. Cross-object steps describe the other party's action in natural language only ("调用 port-auth 鉴权"), with a section-anchored cross-doc link per wiki-principles §4.

### 6.x.2 数据交互

Every concrete cross-module / data-store interaction in this entry, classified by channel (see §5 below). If the entry has no external interactions, write `无外部数据交互`.

**Why**: separating "what the entry does internally" from "what external data it touches" lets readers query independently; §7 reverse-lookup is built from §6.x.2.

**Counter-examples**:

- Mixing data interactions into the processing-flow steps — §7 reverse lookup can't align
- Writing the called object's internal `Class#method` into 处理流程 — ownership violation

---

## 5. §6 数据交互 channel categories

**Rule**: §6.x.2 数据交互 classifies items into the following six channels. Omit channels that don't apply (do NOT write `无` for unused channels here):

- **调用的外部系统**: `[外部对象 § 章节](...)` + brief purpose statement (channel kind: HTTP / Feign / gRPC / Kafka pub-sub / MQTT / WebSocket / etc.)
- **关系型数据库表（R/W）**: table name + operation (R read / W write / RW read-write)
- **Redis（R/W）**: key or key pattern + operation
- **Kafka topic（P/C）**: topic + P produce / C consume
- **MongoDB collection（R/W）**: collection + operation
- **gRPC stub 调用**: service.method
- **对外 HTTP 端点** (direct URL not mapped through a known system name): target + path

**Why**: these six channels cover the typical code-wiki data taxonomy. Uniform classification lets §7 build the matching six reverse-lookup sub-tables.

---

## 6. §7 数据资产 inverted-index six-table structure

**Rule**: §7 is organized into six reverse-lookup sub-tables (one per data channel). If a channel isn't used, write `无` under that sub-table:

### 7.1 关系型数据库表
| 表名 | 主键 / 关键索引 | 读取的入口 | 写入的入口 |
|---|---|---|---|

### 7.2 Redis
| key 或 key 模式 | 作用 | 读取的入口 | 写入的入口 |
|---|---|---|---|

### 7.3 Kafka topic
| topic | P/C | 涉及入口 |
|---|---|---|

### 7.4 MongoDB collection
| collection | R/W | 涉及入口 |
|---|---|---|

### 7.5 gRPC stub
| service.method | 调用的入口 |
|---|---|

### 7.6 对外 HTTP（Feign / 自管 client / 直调 URL）
| 目标 + 路径 | 调用的入口 |
|---|---|

The "入口" column uses §4 entry identifiers or method names (no need to repeat §6's code anchors).

**Why**: fixed table headers let automated review check mechanically; uniform headers let §6 ↔ §7 cross-validation scripts run.

---

## 7. §7 must exhaustively enumerate

**Rule**: §7 must list every data channel the current object's source can be observed to use. Even when §6 entries' internal flows can't be fully traced, the channels themselves must still appear in §7.

If an asset is listed in §7 but no §6 entry references it, it may be: dead code; used only externally; used by an internal task missing from §4. Such cases must produce a §10 entry; do not silently delete the asset.

**Why**:

- Missing a table in impact analysis is an incident. The §7 contract prefers "over-list with a §10 question" to "miss-list silently".
- Reverse-lookup completeness is §7's core value — under-listing destroys it.

**Counter-example**: remove `device.event.raw` from §7 because §6 couldn't find its consumer — it should remain in §7 with a §10 question note.

---

## 8. Data-name grep validation

**Rule**: every concrete data name in §6.x.2 数据交互 and §7 数据资产 (table name / Redis key / Kafka topic / MongoDB collection / gRPC service.method / external HTTP path) MUST be greppable as a literal match in the current object's source (including `.java / .kt / .ts / .py / .yml / .yaml / .xml / .sql / mapper.xml` etc.).

Data names do not require `Class#method (path)` anchors (they often live in config or SQL rather than method bodies), but a literal grep miss → flag.

**Exception**: data names that come from `<USER_SUPPLEMENT>` (see §3) are not subject to source grep, but must carry the「来源：用户口述」 attribution.

**Why**:

- A name written from imagination misleads later readers into a fruitless search.
- Grep validation is a mechanically executable review step.

**Counter-examples**:

- Doc says "writes to `t_order_refund_log`" but no code / SQL / mapper contains the table name — should correct or §10-flag
- Doc writes `order:refund:{orderId}` but code actually uses `order_refund_${orderId}` — also fail (name mismatch)
