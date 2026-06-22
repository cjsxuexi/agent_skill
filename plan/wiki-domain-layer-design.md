# wiki 域分层改造设计（document-systems / wiki-refine / wiki_engine）

> 状态：**设计稿 v1 — 待用户评审**（创建 2026-06-22）
> 范围：在 `D:\wiki` 现有扁平结构之上**插入一层 domain**（`old-project` / `fms`），把两套独立架构拆成两个"相对独立、各自可当 wiki 读"的子 wiki；把现有**两级 common 扩成三级**（全局 / 域 / 仓）。
> 关联：本设计是 [`wiki-engine-refactor-plan.md`](./wiki-engine-refactor-plan.md) 的后续扩展——它的「决策 #1 两级 common」在此扩为三级，「决策 #7 `_` 命名空间」在此新增 domain 维度；与该方案的 Phase E（document-systems 接入）/ F（存量治理执行）相交。
> 出处：基于对 `D:\jk_file\skills\{document-systems,wiki-refine}` 与 `D:\wiki` 真实文件的通读，brainstorming 对话收敛而来。

---

## 1. 背景与目标

`D:\code` 已重排为两套独立产品：`D:\code\old_project\`（云控老产品：fabusurfer、charge-manage-platform、antenna-server-rpc、cloud-platform-web、common-lib 等）与 `D:\code\fms\`（FMS：fms-server、fms-display、fms-protocol）。二者是**两套不相迁移的独立架构**。

但 `D:\wiki` 当前是**扁平**的：所有仓的文档目录平铺在顶层（`fabusurfer/`、`fms-server/`、`charge-manage-platform/`、`common-lib/`、`antenna-server-rpc/`、空的 `common/`、`_meta/`）。`/document-systems` 与 `/wiki-refine` 没有"领域"维度，无法把这两套架构拆开。

**目标**：把 `D:\wiki` 拆成两个相对独立的子 wiki——每个域能当自己的 wiki 读——同时保留一个跨域共享区。落到目录上：

- `D:\wiki\old-project\<repo>\…`、`D:\wiki\fms\<repo>\…`（各仓文档下沉一层）
- 每个域一个**域级内部 common**：`D:\wiki\<domain>\_common\`
- 一个**跨域全局 common**：`D:\wiki\_common\`（默认近空，沿用现有 M5 哲学）

**非目标**：不重写各仓内部文档内容；不做代码侧改动；不引入新的重型"域架构"文档类型。

---

## 2. 现状关键事实（通读所得）

| # | 事实 | 出处 | 对设计的含义 |
|---|---|---|---|
| F1 | 扁平来自**一条路径规则**：两个 skill 都算 `DOC_ROOT = <WIKI_BASE>/<REPO_NAME>`、`DOC_GIT_ROOT = <WIKI_BASE>`、`DOC_REL = <REPO_NAME>` | document-systems SKILL §1.0；wiki-refine SKILL §1.0；MAINTAINER §7 | 域层 = 在这条规则里插入 `<DOMAIN>`，是主改动点 |
| F2 | 已有**两级 common**（拼写为 `_common`，下划线＝非业务命名空间）：全局 `D:\wiki\_common\` + 仓级 `<DOC_ROOT>\_common\` | common-conventions §1/§2；wiki-engine-refactor-plan 决策 #1/#7 | 扩为三级（加 domain），沿用 `_common` 约定（用户已确认） |
| F3 | 引擎 `doc_kind.classify` 对路径的归类是**相对 `doc_root`（即每仓根）**的；域层在 `doc_root` 之上 | `scripts/wiki_engine/doc_kind.py` | 每仓内的归类**不受域层影响**——改面比预想小得多 |
| F4 | 文档间链接全是**相对**的（`../architecture.md`、`<子系统>/architecture.md`、`./_common/`），"wherever DOC_ROOT resolves 都有效" | MAINTAINER §7；wiki-principles §3/§4 | 整目录搬动时**仓内链接全不破**；只有跨 `doc_root`（指向全局 `_common`）的引用对深度敏感 |
| F5 | 所有结构变更走确定性引擎 `wiki_engine`（原子事务 + lint 否决），有完整测试套件 | wiki-refine SKILL Hard Constraints；MAINTAINER §14 | 迁移与改造应骑引擎轨道；改动须保证 `python -X utf8 -m unittest discover scripts/wiki_engine/tests` 全绿 |
| F6 | 配置只有 `%USERPROFILE%\.document-systems.json = {"wiki_base":"D:\\wiki"}` | 实测 | domain 名单需要一个新的、随 wiki 走的注册表 |
| F7 | 引擎只允许**一个派生索引**：全局 `_common/index.md`（薄：file/level/一句话/owns，不复述内容） | common-conventions §6；wiki-principles §7 | 域落地页复用这一"薄索引"模式，把允许范围从"仅全局"扩到"也含域级" |
| F8 | 存量实测：全 wiki **0 个 `](../../)` 链接**；真正的 `_common` 文档引用仅 2 处（`antenna-server-rpc/`、`common-lib/` 的根文档样板里 `./_common/` + `../_common/`，是反引号内的描述性路径、非可点链接） | grep `D:\wiki` | **迁移 ≈ 纯 `git mv`，今天 0 链接需改**；唯一深度敏感的是那 2 处根文档样板的"全局"路径措辞 + 根模板 |

---

## 3. 已锁定决策（对话中用户已确认）

| # | 决策 | 内容 |
|---|---|---|
| D1 | 域分层 | 在 `<WIKI_BASE>` 与 `<REPO_NAME>` 之间插入 `<DOMAIN>`：`DOC_ROOT = <WIKI_BASE>/<DOMAIN>/<REPO_NAME>`。当前两域：`old-project`、`fms` |
| D2 | 域判定 | **混合**：父文件夹名自动推断（`basename(dirname(REPO_ROOT))`）作默认提案 + 一份随 wiki 走的 **domain 白名单**当事实源/护栏 + 未知父目录则一次性询问、落 `.progress.json`。父文件夹**不**单独够用——理由见 §5.2 |
| D3 | common 命名 | 三层全用 `_common`，保持引擎约定（不改成裸 `common`） |
| D4 | common 层数 | 三级：①仓内 `_common` → ②**域内 `_common`（新）** → ③全局 `_common`；放置阶梯从 3 档变 4 档 |
| D5 | 域落地页 | 每域 = 一张**薄 `index.md`**（不是 `architecture.md`、不走 §1–§10 强契约）：只列本域已生成文档的仓（仓名/一句话/链接）+ 链到域 `_common`。机械扫描生成、随仓增量增长 |
| D6 | 顶层 | 选 **B**：不做顶层聚合页；`D:\wiki\` 顶层就是 `<domain>/` 目录 + `_meta/` + 全局 `_common/`。每域当自己的 wiki 读即可 |
| D7 | 输出位置 | 本设计文档放 `D:\jk_file\skills\plan\`（跟着被改的 skill，不进产品仓） |

---

## 4. 目标模型

### 4.1 目标目录树

```
D:\wiki\
  .wiki.json                    # 新增：域注册表（committed，随 wiki 的 git 走）
  _common\                      # 全局：跨域共享（默认近空）
    index.md
  _meta\                        # 引擎忽略的自由区（不变）
  old-project\
    index.md                    # 新增：域落地页（薄索引）
    _common\                    # 新增：域级 common（old-project 各仓共享）
    fabusurfer\
      _common\                  # 仓级 common（不变）
      architecture.md           # 仓系统总览（§1–§10 strict，内容不变）
      port-data\architecture.md
      …
    charge-manage-platform\ …
    antenna-server-rpc\ …
    common-lib\ …
  fms\
    index.md
    _common\
    fms-server\
      architecture.md
      …
```

### 4.2 三级 common 放置阶梯（common-conventions §3 扩 4 档）

事实出现时自顶向下走，停在第一个匹配，**优先最低层**：

1. 单子系统属主 → 留在该子系统文档（不公共化）
2. 本仓 ≥2 子系统共享、无单一属主 → **仓级** `<DOC_ROOT>\_common\`
3. **本域 ≥2 仓共享、无单一属主 → 域级 `<WIKI_BASE>\<domain>\_common\`（新）**
4. ≥2 个域共享 / 全公司标准 → **全局** `<WIKI_BASE>\_common\`

`level` 默认仍是 `repo`；`domain` 与 `global` 都要在公共化门禁（wiki-refine 2.5.b）显式声明并经用户确认。

### 4.3 链接深度数学（域层使引用多一级 ../）

`_common` 三处实际位置：全局 `…/_common/`、域 `…/<domain>/_common/`、仓 `…/<domain>/<repo>/_common/`。

| 源文档 | → 仓 `_common` | → 域 `_common`（新） | → 全局 `_common` |
|---|---|---|---|
| `…/<domain>/<repo>/<子系统>/architecture.md` | `../_common/`（不变） | `../../_common/` | `../../../_common/`（原扁平为 `../../_common/`） |
| `…/<domain>/<repo>/architecture.md`（仓根/single） | `./_common/`（不变） | `../_common/` | `../../_common/`（原扁平为 `../_common/`） |
| `…/<domain>/index.md`（域索引） | —（仓 common 不直引） | `./_common/` | `../_common/` |

**要点**：仓级引用全程不变（域层在其之上）；变的只是"指向全局 `_common`"要多一个 `../`，并新增"指向域 `_common`"这一档。这是引擎链接写入逻辑（`ops`）+ common-conventions §2 表 + 根模板样板要改的全部。

---

## 5. 改动点（逐文件、精确）

### 5.1 路径派生：两个 SKILL.md 的 Phase 1.0

`document-systems` §1.0.3 与 `wiki-refine` §1.0.2 的派生集改为：

```
REPO_ROOT  = git rev-parse --show-toplevel（同前）
REPO_NAME  = basename(REPO_ROOT)（同前）
DOMAIN     = 见 §5.2 解析
DOC_ROOT   = <WIKI_BASE>/<DOMAIN>/<REPO_NAME>      ← 插入 <DOMAIN>
DOC_GIT_ROOT = <WIKI_BASE>（不变）
DOC_REL    = <DOMAIN>/<REPO_NAME>                  ← 插入 <DOMAIN>
```

两处必须**镜像同改**（MAINTAINER §8：解析规则一处改、另一处必须跟）。所有 `git -C <DOC_GIT_ROOT> … -- <DOC_REL>/` 因 `DOC_REL` 已含域而自动正确。`.gitignore` 行 `<DOC_REL>/.review.md`、tracked `<DOC_REL>/.progress.json` 同理随 `DOC_REL` 走。

**向后兼容**：`.wiki.json` 缺失或域解析为空 → 退回旧规则 `DOC_ROOT = <WIKI_BASE>/<REPO_NAME>`（扁平/legacy），保证未迁移仓与单域用户照常工作。

### 5.2 域解析 + 注册表（新增）

**注册表**：`<WIKI_BASE>\.wiki.json`，committed（随 wiki git）。顶层点文件被 classifier 的 `.`-前缀规则天然忽略（`doc_kind.classify` parts[0] 以 `.` 开头 → IGNORED），不会被误判为业务仓。

```json
{
  "domains": ["old-project", "fms"],
  "aliases": { "old_project": "old-project" }
}
```

`%USERPROFILE%\.document-systems.json` 维持只管 `wiki_base`（机器级），不放域信息——"有哪些域"是 wiki 的属性、该随 wiki 走（这是把它放进注册表而非用户配置的根本理由）。

**解析算法**（Phase 1.0，两 skill 共用，建议抽进引擎 `cli.py resolve-domain --repo <ROOT> --wiki <BASE>` 一个子命令，避免两 skill prose 漂移——见 §10 Q5）：

1. 读 `<WIKI_BASE>\.wiki.json`。缺失 → 域 = 空 → 走 5.1 的 legacy 扁平退化（并提示可 `--init-domains` 初始化）。
2. **该仓 `.progress.json` 已记 `"domain"` → 直接用它**（持久优先于推断：源码目录将来再重排，wiki 域也不静默漂移——正是这次记忆迁移踩过的坑）。
3. 否则 candidate = `aliases[ basename(dirname(REPO_ROOT)) ]`（无别名则原值）。
4. candidate ∈ `domains` → `DOMAIN = candidate`，写入该仓 `.progress.json` 的 `"domain"`。
5. candidate ∉ `domains` → **不静默造域**，`AskUserQuestion` 让用户：选一个已有域 / 把 candidate 注册为新域（追加进 `.wiki.json`）/ 退回扁平。选择落 `.progress.json`（之后免问）。

**新增 flag**：`/document-systems --init-domains`（写/改 `.wiki.json`）、`--reconfigure` 顺带可改域归属。

### 5.3 三级 common：契约 + 引擎

- **common-conventions.md**：§1 目录命名空间表加"域目录"一类（顶层非 `_`/`.` 且在 `.wiki.json domains` 中 = domain，其下才是业务仓）；§2 引用路径表换成 §4.3 三行版；§3 放置阶梯换成 4 档；§7 frontmatter `level` 枚举 `repo | global` → `repo | domain | global`。
- **引擎 `ops/__init__.py`**：`promote_to_common` 增加 `level=domain` 目标，解析到 `<WIKI_BASE>/<domain>/_common/`（domain 由 `doc_root` 的父目录得出）；改为引用时按 §4.3 算 `../` 深度（现仅 repo/global 两档，插入 domain 档）。
- **引擎 `doc_kind.py`**：每仓内归类**不动**（F3）。仅当引擎跨整 wiki 扫描时需识别 domain 顶层——由注册表喂入，不靠 classify 猜。
- **`level: domain` 的 lint**：`scripts/wiki_engine/lint/rules.py` 中校验 `level` 取值、域 `_common` 引用深度的规则相应加 `domain` 分支（MAINTAINER §10 双向完整性：契约加了 `domain` 档，引擎必须有对应校验或显式标 LLM-only）。

### 5.4 域 `index.md` 生成（新增，薄索引）

- **形态**：`<WIKI_BASE>\<domain>\index.md`，薄——每行 `仓名 / 一句话 / 链接 ./<repo>/architecture.md`，外加一段链到 `./_common/`。**不复述内容、不读源码、不做跨仓分析**。是 common-conventions §6"唯一派生索引"carve-out 从"仅全局"到"也含域级"的显式扩展（仍受同样薄约束，故不违反 wiki-principles §7）。
- **一句话来源**：扫 `<domain>\*\architecture.md`，取其 H1 标题 + 首个非空摘要行（机械、可重生、无漂移）。
- **触发**：① `/document-systems`（multi 模式、DOMAIN 已解析）跑完某仓后，作为廉价收尾**自动重刷**该域 index；② 新 flag `/document-systems --domain-index[=<domain>]` 按需独立重建。
- **引擎算子**：新增 `update_domain_index`（类比全局 `_common/index.md` 维护），由引擎原子写、lint 校验薄约束。
- **写边界放宽（须显式）**：两 SKILL 的硬约束现为"只写 `<DOC_ROOT>` 与 wiki `.gitignore`"。域 index 在 `<DOC_ROOT>` 的**父层** `<WIKI_BASE>\<domain>\`，故约束措辞要扩成"只写 `<DOC_ROOT>` + 引擎维护的 `<WIKI_BASE>\<domain>\index.md` + （`--init-domains` 时）`<WIKI_BASE>\.wiki.json`"。这与现有全局 `_common\index.md` 本就坐在任何仓 `DOC_ROOT` 之外是同一性质，只是首次让 `/document-systems` 触达 `DOC_ROOT` 之外——必须在两 SKILL 与 MAINTAINER §7 同步写明，不能默许。

### 5.5 模板与根文档样板

- **`references/templates/root-architecture.md`**：`## 仓内公共文档` 段里"全局 `../_common/`"措辞改为三级版（仓 `./_common/`、域 `../_common/`、全局 `../../_common/`）。因 skill 每次都用**当前模板重写** `architecture.md`（SKILL "Rewrite … using the CURRENT prompts/templates"），存量 2 处样板在下次生成/迁移时自动刷新。
- **MAINTAINER.md**：§7（路径解析）补 `<DOMAIN>` 层与 `.wiki.json`；§11 章节名常量集补 `index.md` 域索引列；§15 算子名补 `update_domain_index`；新增一条检查"域注册表存在性与 legacy 退化"。

---

## 6. 存量迁移方案（D:\wiki 扁平 → 两域）

实测（F8）：**0 个 `](../../)` 链接、仓内链接全相对**，故迁移近乎纯 `git mv`。建议在一次受控会话里、逐步带用户确认、尽量走引擎：

1. **建注册表**：写 `<WIKI_BASE>\.wiki.json`（domains + aliases）。
2. **建域目录**：`old-project\`、`fms\`。
3. **整目录搬动（保历史）**：`git -C D:\wiki mv fabusurfer old-project/fabusurfer`、`charge-manage-platform`、`antenna-server-rpc`、`common-lib` → `old-project/`；`fms-server` → `fms/`。仓内相对链接全不破。
4. **清理空目录**：删空的 `D:\wiki\common`（裸名、被 classifier 误当业务仓）。
5. **修唯一深度敏感处**：`antenna-server-rpc/architecture.md`、`common-lib/architecture.md` 的根样板"全局 `../_common/`" → `../../_common/`（+ 新增域级 `../_common/` 一句）。本质等价于对这两仓跑一次 `/document-systems --step=root` 用新模板重生成。
6. **各仓 `.progress.json` 记 `"domain"`**：固化归属（避免再推断漂移）。
7. **生成域索引**：对 `old-project`、`fms` 各跑 `--domain-index`。
8. **回归**：`/wiki-refine --lint` 全 wiki 跑通；`git -C D:\wiki diff` 人工过一遍再 commit。

> 注：本步骤对应 wiki-engine-refactor-plan 的 **Phase F（存量治理执行）**，性质是"未来会话、逐步、带确认"。域迁移可与 F 的 M1–M5 合并到同一治理窗口。

---

## 7. 向后兼容与边界

- **single 模式**：`DOC_ROOT/architecture.md` 仍是那一份；只是 `DOC_ROOT` 多了域前缀。域解析、域 index 同样适用（域 index 把单系统仓也列一行）。两 skill 的 `## Single mode overrides` 块按 MAINTAINER §9 同步。
- **legacy 扁平仓 / 无域仓**：`.wiki.json` 缺失或 candidate 不入白名单且用户选"退回扁平" → 走旧 `DOC_ROOT = <WIKI_BASE>/<REPO_NAME>`。新旧可共存于同一 `D:\wiki`（顶层既可有域目录，也可有未迁移的裸仓目录）。
- **不在域文件夹下的仓**（如临时 clone 到 `D:\experiments\foo`）：父文件夹推断会得 `experiments`，不在白名单 → 触发一次性询问，**杜绝静默造垃圾域**（§5.2 步骤 5）。
- **引擎测试**：任何依赖引擎的 skill 改动，未过 `unittest discover scripts/wiki_engine/tests` 不算完成（MAINTAINER §14）；`render(parse(x))==x` 字节级 round-trip 必须保持。

---

## 8. 风险与权衡

| 风险 | 说明 | 缓解 |
|---|---|---|
| 契约↔引擎漂移 | 加 `domain` 档要同时改 prose 契约与引擎 lint，二者分开维护易脱节（plan 最大风险） | MAINTAINER §10 双向审计：每条契约改动走回引擎一次；加 `level: domain` 的 lint 或显式标 LLM-only |
| 两 skill 路径规则不同步 | §5.1 改动若只改一个 skill，`/wiki-refine` 会找不到 `/document-systems` 写的 `DOC_ROOT` | MAINTAINER §8 镜像检查；建议把域解析下沉为引擎 `resolve-domain` 子命令，两 skill 共用 |
| 域 index 退化成派生漂移文件 | 若写厚了（复述内容）就违反 wiki-principles §7 | 硬约束薄结构（仓名/一句话/链接）+ 引擎 lint 卡死；只机械抽取、可重生 |
| 域边界一开始划不准 | 用户已点明：域内容多、起初难准确划分 | D5 的薄索引设计：从不声称完整划分，只反映"已文档化的仓"、随之增长；跨仓深度走 `_common`/refine 增量沉淀 |
| 别名/归一歧义 | 代码目录 `old_project`（下划线）vs 域名 `old-project`（连字符） | `.wiki.json aliases` 显式归一；`.progress.json` 固化最终域名 |

---

## 9. 实现清单（供 writing-plans 拆解）

1. 引擎：`cli.py` 加 `resolve-domain`、`update-domain-index` 子命令；`ops/__init__.py` 加 `level=domain` 与三档深度；`doc_kind.py` 域识别（注册表驱动）；`lint/rules.py` 加 `level: domain` 与域索引薄约束校验；补测试（`tests/`：域路径解析、域 common 深度、域 index 生成、legacy 退化）。
2. 契约：`common-conventions.md` §1/§2/§3/§7 四处；`templates/root-architecture.md` 样板措辞。
3. `document-systems/SKILL.md`：Phase 1.0 域解析 + 路径派生；`--init-domains` / `--domain-index` flag；Phase 6 收尾自动刷域 index；`## Single mode overrides` 同步。
4. `wiki-refine/SKILL.md`：Phase 1.0 镜像域解析；2.5.b 公共化门禁支持 `level=domain`；`<COMMON_CONTEXT>` 纳入域 `_common`。
5. `MAINTAINER.md`：§7/§11/§15 + 新检查；`MIGRATION.md`：把"域迁移"并入 Phase F（M0：建注册表 + git mv + 域 index）。
6. 存量迁移（§6，独立受控会话执行）。
7. 全程 `unittest` 绿 + `--lint` 全 wiki 通过。

---

## 10. 待确认（评审问题）

1. **域名拼写**：注册表/目录用连字符 `old-project` / `fms`，源码目录用 `old_project`（靠 `aliases` 归一），可否？还是 wiki 侧也想用 `old_project`？
2. **`cloud-platform-web` / `antenna-server` / `charge-manage-platform-scripts`**：这几个仓也归 `old-project` 域吧？（其中 scripts 的实际位置上次还没确认。）
3. **迁移时机**：§6 存量迁移是这次就执行，还是只先落"skill+引擎改造"、迁移留到单独的治理会话（对齐 plan 的 Phase F）？
4. **`common-lib` 归属**：确认它是 `old-project` 域内的一个普通业务仓（不是跨域共享）——你之前已把它列进 old_project，这里据此处理。
5. **是否现在就把域解析下沉成引擎 `resolve-domain` 子命令**（强烈建议，消两 skill 漂移），还是两 skill 各写 prose？
