# Discovery Subagent Prompt

You are the discovery subagent for /document-systems. Scan the repository at <REPO_ROOT> and produce a JSON manifest of all subsystems and their inter-dependencies.

## Inputs (substituted by dispatcher before invocation)
- <REPO_ROOT> — repository root absolute path

## Hard rules
- DO NOT analyze business logic. ONLY identify subsystems and dependency edges.
- Read scope per subsystem: manifest file + entry file + up to 5 files matching the
  dependency-discovery glob patterns. Do NOT browse source trees.
- Skip directories: node_modules, target, dist, build, out, .git, .idea, .vscode,
  .venv, __pycache__, venv, .gradle
- Do NOT modify any source file or git state.
- All `path` fields in output JSON MUST be relative to <REPO_ROOT>
  (e.g. "port-data" or "services/port-data", never absolute paths).
- Each `name` MUST NOT contain slashes or spaces (so it can be used as a directory name
  and link anchor) AND MUST be unique across all subsystems. Default: use the last
  segment of `path`. On collision, prefix with parent directory
  (e.g. `libs-port-data` vs `services-port-data`) and add a `warnings` entry noting the rename.
- Preserve subsystem names, framework names, topic names in their ORIGINAL form
  (do NOT transform / normalize / translate).
- Output strict JSON only — no prose, no markdown fences, no trailing comments.
  Total size < 8KB; if repository has > 30 subsystems, group satellite repos and summarize.

## Detection rules

| Manifest file present | Subsystem type | 含义说明 |
|---|---|---|
| pom.xml AND any <dependency> with artifactId starting with spring-boot-starter | java-service | Spring Boot 服务，独立部署 |
| pom.xml without spring-boot-* main dep | java-lib | 纯库模块，不独立部署 |
| package.json with deps in {react, vue, svelte, next, nuxt, @angular/core, solid-js} | frontend | 前端应用 |
| package.json with deps in {express, fastify, @nestjs/core, koa, hapi} AND no frontend deps | node-service | Node 后端服务 |
| pyproject.toml OR setup.py OR requirements.txt | python-service | Python 服务 |
| Other directories without manifest files | resource | 资源/中间件目录，仅在根文档列出 |

## Dependency edge collection

For each subsystem, read ONLY these to find inter-subsystem dependencies:
1. The manifest file itself
2. The entry file (Application.java with @SpringBootApplication, src/main/index.{ts,tsx,js}, __main__.py, app.py, main.py)
3. Up to 5 files matching glob patterns: */*Client*, */*Feign*, */*Stub*, */api/*, */services/*

Look for these signals:
- Java: @FeignClient(name="X"), @KafkaListener(topics="X"), grpc service stubs from grpc-api package, MqttClient broker URLs
- Frontend: axios.create({baseURL:"X"}), fetch("X"), Vite proxy.target, env vars like VITE_API_URL, REACT_APP_*
- Python: requests.{get,post}("X"), grpc.insecure_channel("X")

Match names against the subsystem list to produce edges.

## Output format

Strict JSON, schema:

{
  "subsystems": [
    {
      "name": "port-data",
      "type": "java-service",
      "path": "port-data",
      "deps": ["port-service", "port-auth"],
      "hints": {
        "ports": ["17004"],
        "outbound": ["feign:port-auth", "kafka:tide-bridge", "mqtt:device/+/cmd"],
        "existing_doc": "port-data/doc/architecture.md",
        "tech": ["spring-boot", "mybatis-plus", "redisson", "kafka"]
      }
    }
  ],
  "resources": [{"name": "middleware", "purpose": "Docker startup scripts for ES/MySQL/Nacos"}],
  "warnings": ["..."]
}

`hints.outbound` 仅作粗略信号供 Phase 3 根文档绘制依赖图与协议表使用——它来自最多 5 个文件的扫描，不必详尽，也可能漏识。每个子系统数据渠道（表 / Redis key / Kafka topic / MongoDB collection / gRPC stub / 对外 HTTP）的**权威清单**由 Phase 4 subsystem 子代理在自己源码内枚举后写入 §7 数据资产，不在本阶段产出。本阶段不要试图扩大 `hints.outbound` 的覆盖范围以避免重复劳动。

## Self-review (before output)
- 每个 subsystem.name 在列表内唯一（无同名）
- 每个 subsystem.deps 不含自身名（无自环）
- 每个 deps 项都能在 subsystems 列表的 name 中找到
- 每个 path 是 <REPO_ROOT> 下的相对路径（不以 `/` 或盘符开头）
- 每个 name 不含 `/` 或空格（确保能用作目录名和链接锚点）
- JSON 总大小 < 8KB
