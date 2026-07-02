<!--
export-session 触发接线(设计 §6 分层触发)。这是"样例配置 + 接线说明",不是自动应用。
两条主路径:① 本地 SessionEnd hook(真·全自动);② Multica 评论/@mention(主机制)。
-->
# export-session 触发接线(设计 §6)

会话**结束后自动触发**分析。平台实测(设计 §0)决定分层:评论/@mention 是 Multica 上唯一"自带已认证人类发起者"的可靠信号,本地 cc 则用 `SessionEnd` hook。两条路径都汇入同一 launcher(`session_export.launcher.run` / CLI `analyze`)。

---

## ① 本地 SessionEnd hook(真·全自动,设计 §6 中段)

会话一结束就自动跑,零人工动作。hook 向 stdin 注入 JSON(含 `session_id`、`transcript_path`),`analyze --from-hook-stdin` 直接读取,免去 `issue runs` 定位。

**`~/.claude/settings.json` 片段**(指向随 skill 附带的接线脚本 `references/hooks/session_end_hook.py`):

```json
{
  "hooks": {
    "SessionEnd": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python \"D:\\jk_file\\skills\\export-session\\references\\hooks\\session_end_hook.py\""
          }
        ]
      }
    ]
  }
}
```

- 导出根 / wiki 根可用环境变量覆盖:`EXPORT_SESSION_ROOT`、`EXPORT_SESSION_WIKI_ROOT`(默认 `D:\claude-sessions` / `D:\wiki`)。
- **防自噬(§12/§13)**:launcher 的 `session_guard` 会跳过 cwd 命中 `export-session` 的会话;且接线脚本是普通 Python 进程(不是 cc 会话),不会再触发新的 `SessionEnd`,故无递归。
- 前提(§13.6):执行 hook 的机器与产生会话的机器共享 `~/.claude/projects`(同机即可)。

等价手动命令(调试用):

```powershell
cd D:\jk_file\skills\export-session\scripts
echo '{"session_id":"<uuid>","transcript_path":"C:\\Users\\me\\.claude\\projects\\<enc>\\<uuid>.jsonl"}' | ^
  python -m session_export analyze --from-hook-stdin --export-root D:\claude-sessions --wiki-root D:\wiki --trigger session_end_hook
```

---

## ② Multica 评论 / @mention(主机制,设计 §6 首段 / §12 第 1 层)

用户对**已结束的 issue** 发一条评论或 `@mention export-session`。该 run 为 `kind:comment`,平台注入**已认证人类发起者** + `trigger_comment_id` —— 既是"任务已结束"信号,也是"用户主动发起"的硬证明。

被分析会话经 `multica issue runs <issue-id>` 的 `result.session_id` 定位(实测该字段存在),并**排除 export-session 自己的 run**。CLI 直接支持:

```powershell
cd D:\jk_file\skills\export-session\scripts
python -m session_export analyze `
  --issue-id <issue-id> `
  --trigger comment --trigger-comment-id <人类评论 id> `
  --self-agent-id <export-session 的 agent id> `
  --export-root D:\claude-sessions --wiki-root D:\wiki
```

- `analyze` 会 shell 调 `multica issue runs <issue-id> --output json`,用 `launcher.resolve_session_id` 取工作 run 的 `session_id`(§12 第 2 层:按 `--self-agent-id` / `--self-session-id` 排除自身 run;跳过未完成 run;取最近完成者)。
- **回贴摘要不 @mention**(§12 第 2 层防循环):`launcher.build_reply_summary` 产出的文本不含任何 `mention://` / `@`。回贴时用 `multica issue comment add`,沿用触发评论的 `--parent`,**不要**再 `@` 触发者或任何 agent。
- 判"是否用户发起":`launcher.is_user_initiated({"kind","trigger_comment_id","author_type"})` —— 仅人类评论(`kind:comment` + 有 `trigger_comment_id` + 作者非 agent)为真。

---

## ③ 兜底 · scheduled autopilot 轮询(最弱,设计 §6 末段)

一个 cron autopilot 定时跑 `analyze --trigger schedule_poll` 扫近段"已完成"的 issue。平台无"状态操作者"查询,无法证明"已完成"是人点的,"只评估用户发起"在此模式只能尽力而为(可加"该 issue 最近有人类评论"等弱信号)。默认不启用;仅在 ①② 都不可用时退此。

---

> 三条路径都收敛到 `launcher.run`:定位会话 → §12/§13 护栏(不过则写 `<EXPORT_ROOT>/.auto.log` 并干净退出)→ 确定性导出 → score(§1 实时落盘)→ wiki_touch → 一次受控分析(默认确定性基线,可注入 LLM)→ 渲染 `analysis.md` → 追加自评 log(幂等 + 文件锁)→ 重算索引。
