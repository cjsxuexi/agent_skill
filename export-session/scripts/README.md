# session_export — 会话导出分析引擎(Stage 1 + Stage 2)

纯 stdlib、零 LLM(导出/筛选/触点层)、可复现:同一份 jsonl + 注入相同 `exported_at`/`generated_at` → 产物**逐字节一致**(设计 §14)。Stage 2 在导出之上补齐:自动筛选(`score`)、wiki 触点识别 + 取原文(`wiki_touch`)、D1/D2 分析渲染(`analyze`)、自评 log 追加(`evallog`,幂等 + 文件锁)、以及把它们连同 §12/§13 护栏串起来的 `launcher`(CLI `analyze` 子命令)。

## 布局

```
scripts/
├─ session_export/          # 引擎包(python -m session_export)
│  ├─ config.py             # §11 配置/探测 projects 根 + 无 BOM 的 UTF-8/JSON 写入 + slug(保留 CJK)
│  ├─ parse.py              # jsonl → 规范化 Session(容错尾部半行;各行/块类型分类)
│  ├─ summarize.py          # §10 summary.json:指标 + frictions[](tool_error/permission_denied/retry/user_correction)
│  ├─ render.py             # → transcript.md(簿记不入流水、注入折叠、超长截断留 raw/、子代理递归链接)
│  ├─ catalog.py            # 顶层会话编目 + .catalog-cache.json(size/mtime 失效)
│  ├─ index.py              # 跨会话 INDEX.md / index.json(全量重算,幂等)
│  ├─ score.py              # Stage 2:按能否完成 D1/D2 自动筛选;未选 + 理由带 recorded_at
│  ├─ wiki_touch.py         # Stage 2:确定性标 wiki 触点(Read/Grep/Glob/WebFetch/ones_wiki/skill)+ 取被引原文
│  ├─ analyze.py            # Stage 2:按模板渲染 D1+D2 analysis.md + 确定性基线分析器
│  ├─ evallog.py            # Stage 2:自评 log 追加(幂等 by key + O_CREAT|O_EXCL 文件锁)
│  ├─ launcher.py           # Stage 2:定位会话 + §12 三层过滤 + §13 护栏 + 串联导出/分析
│  ├─ export.py             # 编排 export;含 CLI(export / index / catalog / analyze)
│  └─ __main__.py           # python -m session_export 入口
└─ tests/                   # pytest(合成 fixtures;builders.py 复刻真实 jsonl schema)
```

## 跑测试

引擎只依赖标准库;测试需要 `pytest`。

```powershell
cd D:\jk_file\skills\export-session\scripts
uv venv .venv                       # externally-managed python:用 uv 建临时环境
uv pip install --python .venv pytest
.\.venv\Scripts\python.exe -m pytest -q   # 全绿(Stage 1 + Stage 2:116 项)
```

## 跑导出

```powershell
cd D:\jk_file\skills\export-session\scripts

# 按 jsonl 路径导出单个会话,并重算跨会话索引
python -m session_export export --jsonl <path\to\session.jsonl> --export-root D:\claude-sessions

# 或按 session_id 在 projects 根下定位后导出
python -m session_export export --session-id <uuid> --projects-root %USERPROFILE%\.claude\projects --export-root D:\claude-sessions

# 仅重算索引
python -m session_export index --export-root D:\claude-sessions
```

常用参数:`--no-raw`(不落 raw/ 截断原文)、`--truncate-at N`(超长阈值,默认 2000 字符)、
`--exported-at <ISO8601>`(注入固定时间戳以获得逐字节可复现的产物;缺省用当前 UTC)。

## 跑分析(Stage 2:export + score + wiki_touch + D1/D2 + eval-log)

```powershell
cd D:\jk_file\skills\export-session\scripts

# hook 路径:直接给会话(或 --session-id + --projects-root)
python -m session_export analyze --session-id <uuid> --projects-root %USERPROFILE%\.claude\projects `
  --export-root D:\claude-sessions --wiki-root D:\wiki --trigger session_end_hook

# 评论路径:从 `multica issue runs <id>` 解析 session_id(排除自身 run)
python -m session_export analyze --issue-id <issue-id> --trigger comment `
  --trigger-comment-id <人类评论 id> --self-agent-id <export-session agent id> `
  --export-root D:\claude-sessions --wiki-root D:\wiki
```

产物:`<会话目录>/analysis/<generated_at>_D1D2/analysis.md`(D1+D2)、`export-session-eval-log.md` 追加一条(默认写 skill 目录;`--eval-log <path>` 覆盖)。护栏不过则写 `<EXPORT_ROOT>/.auto.log` 并干净退出(exit 0)。可注入 `--generated-at <ISO8601>` 复现。

**受控分析(D1/D2 深判)**:`launcher.run(..., analyzer=...)` 的 `analyzer` 形参默认是零 LLM 的 `analyze.baseline_judgments`(取到原文的 D2 触点标"待判定 + 附原文",取不到标"低置信疑似");接一次真正的 LLM 受控分析时,替换该形参即可(参见设计 §4 step 5)。

触发接线(settings.json 片段 + Multica 评论路径)见 `../references/triggers.md`。
