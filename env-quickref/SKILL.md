---
name: env-quickref
description: 维护 wiki 体系「港口环境实例信息」文档（<WIKI_BASE>/<域>/_env/<港口码>.md，引擎 IGNORED 区、排查时按需加载）——按 环境（test/Pre-release/prod）→ 实例（MySQL/Redis/服务/中间件）记录位置、日志、配置文件、脚本与取证入口；密码/token 永不入文档，「凭据获取」只写指针。触发：(1) 用户要求记录/更新环境事实（实例位置、日志路径、环境变更、实例迁移、新增港口环境）；(2) 显式 /env-quickref init|add。只做维护侧：查询/消费环境信息走 /wiki-search，不要因为「要查环境信息」触发本 skill。规划与 prod-issue-quickref 合并为一个排查资料 skill。
---

# env-quickref

维护**港口环境实例信息**文档：每个港口一个 md（`<WIKI_BASE>/<域>/_env/<港口码>.md`），记录该港口 test / Pre-release / prod 各环境的实例（MySQL、Redis、服务、中间件）位置与日志、配置文件、脚本等取证信息。它是 prod-issue-quickref 速查树根因叶「确认 →」的落点（去哪确认），也是子系统文档 §8 的实例位置权威源。

文件结构见 `references/port-file-template.md`（动手前先读）。校验器 `scripts/validate_env.py`。
`_env/` 是 wiki 引擎的 IGNORED 命名空间（common-conventions §1）：不 lint、不进 `/wiki-refine` 的常驻上下文，**只在排查（及分析设计查配置）时按需加载**——这是设计意图，不是欠治理；治理由本 skill 的模板 + 校验器承担。

## 1. 定位文档（每种操作先做）

1. 读 `%USERPROFILE%\.document-systems.json` 取 `wiki_base`（缺失 / 空则按 document-systems 的默认逻辑回退，不要写死盘符）。
2. 按港口码定位（港口码 = 文件名 = fms-log / fms-diagnose 的 `--port` 前缀，一港一文件；生产/uat 参数变体如 `np_prod` / `nb_uat` 记在同一文件的对应环境节里）：

| 域 | 港口码 → 文件 | 港口 |
|---|---|---|
| old_project | `yz.md` / `nb.md` / `mb.md` | 甬舟 / 梅山 / 梅北 |
| NP_FMS | `np.md` / `dg.md` | Napier / 青岛 |
| PSA_FMS | `psa.md` | PSA（新加坡 Tuas） |

3. `ENV_DOC = <WIKI_BASE>/<域>/_env/<港口码>.md`。用户口述新港口时先确认其所属域，再建文件。

## 2. init（脚手架）

以 `references/port-file-template.md` 生成 `ENV_DOC`：frontmatter 填 port/domain/title/updated；三个环境节齐备（没有的环境正文写「无」）；`## 待确认 / 疑问` 收未知项。生成后必跑校验（§4）。

## 3. add / update（口述 → 落盘）

1. **定落点**：港口文件（§1）→ 环境节（test / Pre-release / prod）→ 实例节 `### <环境> · <实例名>`。已有同实例 → 原地更新并改 `> 来源：…（日期）`；新实例 → 新增三级节。MySQL / Redis / 服务 / 中间件都是实例；JumpServer、Grafana 等取证入口写进相关实例正文，不另立节。
2. **信息行**（自由行文，推荐：位置 / 日志 / 配置文件 / 脚本·工具 / 凭据获取）：标识符（host、路径、实例名、datasource 名）**原样保留**；不确定的进 `## 待确认 / 疑问`，不写进环境节正文。
3. **凭据硬规则**：只写「凭据获取：<指针>」（哪个脚本 / 哪台机器哪个文件 / 哪个 Mcp 配置叶子）。密码/token 明文会被校验器拒绝；agent 需要连接时调对应工具 skill 拿**数据**，不拿凭据。
4. **跨港口共享设施**：物理归属港口的文件持有事实，其它港口文件锚点引用、不复写。引用一律写成含 `_env/` 的相对路径（同域也写 `../_env/<港口>.md#<锚点>`）——`--check-refs` 的断锚反查按 `_env/<文件>#` 匹配，别的写法扫不到。
5. **改/删实例标题前**：标题即入站锚点（速查根因叶、子系统 §8 都在链），先跑 `--check-refs`（§4）看有哪些引用，改完再跑一次确认无断锚。
6. frontmatter `updated` 改为今天。

## 4. 必跑校验

```
python -X utf8 <本skill>/scripts/validate_env.py <ENV_DOC>              # 结构 + 凭据黑名单
python -X utf8 <本skill>/scripts/validate_env.py <ENV_DOC> --check-refs # 涉及标题增删改时加跑：全 wiki 断锚反查
```

- 手动场景：不过则据报错修好再落定，并 `git -C <WIKI_BASE> diff` 让用户看改动。
- 自动化场景（无人当场复核）：不过则**回滚本次编辑**、如实告知「校验没过，未落盘」，不要硬写。

## 5. 与相邻文档/skill 的分工

- **prod-issue-quickref（速查树）**：现象 → 根因分诊；其根因叶「确认 →」链到本文档锚点（根因 → 去哪确认）。两 skill 规划合并，故共用 wiki 根解析方式与校验器调用约定。
- **fms-log / fms-diagnose**：可执行事实源（连接配置、查询命令）；本文档是可读索引，两边互指防漂移。
- **cmdcap 及各 runbook**：「怎么取证」的操作规范；本文档只管「哪里有什么」。

## 不做

不做查询/消费指引（/wiki-search 的事）；不碰 `_common/` 与 wiki 引擎管辖的文档；不存任何凭据明文；不写取证操作教程（cmdcap / fms-log 等 skill 的事）；不跨港口汇总（一港一档，域内共享靠锚点引用）。
