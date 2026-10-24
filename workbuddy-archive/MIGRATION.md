# WorkBuddy → DeepSeek Harness 迁移报告

迁移时间：2026-10-14　｜　执行者：DeepSeek Harness agent（本文件由它生成）

> 一句话结论：**技能、长期记忆/身份、MCP、hooks、脚本、wiki、密钥、会话与自动化存档**全部迁完。
> 配置已通过 `dsh --dump-config` 校验，并在**真实运行态**复核：MCP 两条已注册为 active、
> hooks 已在本会话触发、独立 headless 会话成功用 `skill` 工具加载了迁移过来的技能。
> WorkBuddy 原目录一律**只读保留**，未删除、未改动。
> 唯一要做的：**当前这个会话**的技能目录是会话启动时的快照 —— **开个新会话**就能看到 55 个技能。

---

## 1. 已迁移清单

| # | 类别 | 来源（WorkBuddy） | 去向（DSH） | 状态 |
|---|---|---|---|---|
| 1 | 技能（38 个） | `~/.workbuddy/skills/` | `~/.dsh/skills/` | ✅ 全部通过 DSH frontmatter 校验（name kebab-case + description） |
| 2 | 技能审计台账 | `~/.workbuddy/skills/SKILL-IMPACT.md` | `~/.dsh/skills/SKILL-IMPACT.md` | ✅ hook 的 Stop 校验继续可用 |
| 3 | 长期记忆 v178 | `~/.workbuddy/memory/*_memory.md` | `~/.dsh/AGENTS.md`（现行）+ `~/.dsh/memory/`（归档） | ✅ 已被系统作为 workspace instructions 注入本会话 |
| 4 | 身份/用户档案 | `~/.workbuddy/{SOUL,USER,IDENTITY,BOOTSTRAP}.md` | 并入 `~/.dsh/AGENTS.md`；原件 `workbuddy-archive/identity/WorkBuddy/` | ✅ |
| 5 | MCP servers | `~/.workbuddy/mcp.json` | `~/.dsh/cordis.patch.yml`（DSH 原生注册）+ `~/.dsh/mcp.json`（hook 侧镜像） | ✅ 运行态复核：`mcp-memos-local` / `mcp-hrq-pg` 均 `enabled + active`，工具已在本会话可调 |
| 6 | hooks（wikiskill 自迭代） | `~/.workbuddy/hooks/` | `~/.dsh/hooks/` + `~/.dsh/cordis.patch.yml` 挂 `dsh-hooks-claude-code` | ✅ 运行态复核：`workbuddy-hooks` active，本会话已触发 SessionStart / UserPromptSubmit |
| 7 | 脚本工具链 | `~/.workbuddy/scripts/`（3.1MB） | `~/.dsh/scripts/` | ✅ 路径已改写 |
| 8 | 经验知识库 wiki | `~/.workbuddy/memwiki/`（3.2MB） | `~/.dsh/memwiki/` | ✅ digest / pitfalls-ledger / evals 原样 |
| 9 | 密钥 | `~/.workbuddy/secrets/` | `~/.dsh/secrets/`（0600） | ✅ deepseek_api_key、mimo_api_key |
| 10 | 会话转写 | `~/.workbuddy/projects/**/*.jsonl` + `workbuddy.db` | `workbuddy-archive/sessions/*.md` | ✅ 51 条导出，索引见 `SESSIONS_INDEX.md` |
| 11 | 定时自动化 | `workbuddy.db → automations` | `workbuddy-archive/automations.md` | ✅ 4 条（DSH 无调度器，按需手动执行） |
| 12 | 任务清单 | `~/.workbuddy/tasks/` | `workbuddy-archive/tasks.md` | ✅ 11 组 |
| 13 | PATH：dingtalk CLI | `~/.qwenworkcn/bin/dws` | 包装脚本 `~/.local/bin/dws` | ✅ 可执行（运行时限制见 §3） |

### 迁移时做的适配（不是原样复制的部分）

1. **路径改写**：所有 `~/.workbuddy/{skills,scripts,hooks,memwiki,memory,secrets,mcp.json}` 引用
   改写为 `~/.dsh/...`（含绝对路径写法），覆盖 skills / scripts / hooks / memwiki 共 850+ 个文本文件，
   其中 90+ 个实际命中改写。`mac-agent-uninstall-residue-cleanup` 技能**故意不改写**（它的用途就是清理 WorkBuddy 残留）。
2. **解释器解耦**：`wikiskill_booster.py` 与 `hooks.json` 的解释器从 WorkBuddy 托管 python 换成 `/usr/bin/python3`
   （脚本纯标准库，实测可跑），hook 子进程 `PY_BIN` 同步替换 —— hooks 链路不再依赖 WorkBuddy。
3. **代理补丁**：DSH 的 shell 环境带 `http_proxy=127.0.0.1:7897` 与 `NO_PROXY=[::1]`，
   会让 httpx 抛 `Invalid port: ':1]'`，导致 memos 本地检索失败（在 WorkBuddy 原路径上同样复现，非迁移引入）。
   已在 `~/.dsh/scripts/{memos_sync,memos_local_ops}.py` 子进程剥离代理变量，并在 MCP env 里显式清空。
4. **技能补缺**：
   - `wikiskill-self-evolve` 在 WorkBuddy 侧缺 SKILL.md → 从 `~/.qwenworkcn/skills/` 镜像补齐，
     `references` 软链重指向 `~/.dsh/memwiki/references`；
   - `qoder-hook-port-install` 源侧 SKILL.md 是指向自身的坏软链（源数据已损坏）→ **未迁移**；
   - 根目录的 `_bm_skillid_migration.json` 等迁移标记文件未带过来。
5. **MCP 注册形式**：DSH 的 patch 层里新增条目必须写成 `- insert:`（顶层裸条目是"按 id 覆盖"，会报 not found），
   已按此写入 `~/.dsh/cordis.patch.yml`。

---

## 2. 校验结果

| 校验项 | 方法 | 结果 |
|---|---|---|
| DSH 配置语法与插件解析 | `dsh --profile web --dump-config`（临时 profile，用完已删） | ✅ 无告警；三条新条目均进入组合树 |
| 运行态插件状态 | `plugin_manager list_plugins` | ✅ `mcp-memos-local`、`mcp-hrq-pg`、`workbuddy-hooks` 全部 `enabled:true / fiberPhase:active` |
| MCP 进程真的能起 | headless 会话启动时的 stderr | ✅ MemOS FastMCP server 完成 stdio 启动；`mcp__hrq-pg__*`、`mcp__memos-local__*` 工具已出现在本会话工具表 |
| hooks 真的在跑 | `~/.dsh/hooks/hook-runs.log` + `/tmp/wikiskill-hook-state/dsh/` | ✅ 本会话 SessionStart(inject:885)、UserPromptSubmit(inject:5414)，`dsh` 命名空间状态已建 |
| 技能目录 | 逐个解析 frontmatter（`name` 必须 kebab-case、`description` 必填） | ✅ 55 个可收录（~/.dsh 38 + ~/.agents 17），0 个不合格 |
| 技能端到端可用 | 独立 headless 会话里调 `skill` 工具加载 `cloud-hr-db` | ✅ 加载成功，正确返回正文第一个二级标题「访问路径（两条，按优先级）」 |
| 技能重名 | 全量比对 | 仅 `wecom-unified` 同名（`~/.dsh` rank 400 优先于 `~/.agents` rank 500），符合预期 |
| 坏软链 | `find -L ~/.dsh/skills` | ✅ 无 |
| hooks 冒烟 | `SessionStart` / `UserPromptSubmit` 喂真实 stdin JSON | ✅ 返回 `additionalContext`，且本地记忆检索（含 rerank）成功 |
| 记忆注入 | 写入 `~/.dsh/AGENTS.md` 后 | ✅ 系统已把该文件作为 workspace instructions 注入本会话（含变更热更新提示） |
| 存档完整性 | 导出计数 | ✅ 51 会话 / 4 自动化 / 11 任务组 / 4 身份文件 |
| 校验残留清理 | 删除校验用 profile / session | ✅ `profiles/{web,headless}`、`sessions/--private-tmp--`、对应 projcache 已删，只留 desktop |

**关于生效时机**：本次实测 `~/.dsh/cordis.patch.yml` 是**热生效**的（HMR 已把 MCP 与 hooks 挂上，无需重启）。
例外是**技能目录**：它在会话首次请求时生成快照，因此当前这个会话看不到新技能，**新开会话即可**。

---

## 3. 未迁移 / 不可迁移（含原因）

| 项 | 规模 | 原因 |
|---|---|---|
| WorkBuddy 插件 | `~/.workbuddy/plugins` 256MB | WorkBuddy/CodeBuddy 插件体系，与 DSH cordis 插件不兼容 |
| Python 托管运行时 | `~/.workbuddy/binaries` 3.8GB | 体积大且 `auto_dream`、`hrq-pg` 等脚本仍显式指向它；**卸载 WorkBuddy 前需先切换解释器** |
| 会话原文（DSH 格式） | `~/.workbuddy/projects` 166MB、traces 628MB、blobs 76MB | DSH 会话是自有压缩日志格式，无导入通道 → 已导出 Markdown 存档替代 |
| 模型/账号配置 | `settings.json`、`models.json`、`workbuddy.db`、keyblob、`tcb/auth.json` | WorkBuddy 私有格式或加密存储；DSH 已有自己的模型配置（mimo-v2.6-flash）与凭据 |
| 商店/账号态 | `plugin-account-state`、`connectors`、`edge-sync` | 绑定 WorkBuddy 账号与端云同步，无对应概念 |
| 工作区（15 个 `~/WorkBuddy/...`） | — | DSH 工作区由 GUI 管理，运行中改 `storages/workspace.json` 会被覆盖 → **请在 DSH 界面「工作区」里手动添加**，路径都是现成的 |
| dingtalk 14 个技能的运行时 | `dws` | `dws` 需要 `QODERWORK_SOURCE_CHAT_ID`（QwenWork 会话环境），本机无处可取；包装脚本已就位，拿到该环境变量即可用 |
| MemOS 运行时 | `/Users/leto/WorkBuddy/MemOS` | MCP 与本地检索直接引用其 venv 与源码，原地保留最稳 |
| DeepSeek 官方 key | `~/.dsh/secrets/deepseek_api_key` | 实测 **QUOTA: Insufficient Balance**，无法作为 DSH 的模型路由；DSH 现用 mimo 路由正常 |

---

## 4. 迁移后的使用说明

1. **开个新会话** → 55 个技能就会出现在技能目录里（当前会话的目录是启动时的旧快照）。
   MCP 与 hooks 已经热生效，不用重启。
2. 可用工具：`mcp__memos-local__*`（本地记忆检索/落盘）、`mcp__hrq-pg__*`（CloudBase PG 只读快查）。
3. **记忆维护**：以后长期记忆直接改 `~/.dsh/AGENTS.md`（64KB 预算，当前 19KB）；
   `~/.dsh/memory/` 是 WorkBuddy 归档原件，不要再往里写。
4. **新增 MCP server**：要在两处登记 —— `~/.dsh/cordis.patch.yml`（DSH 侧，`- insert:` 形式）
   和 `~/.dsh/mcp.json`（hook 侧读取的镜像）。
5. **改技能**：编辑 `~/.dsh/skills/<name>/SKILL.md`（有 watcher，不必重启），
   按老规矩在 `~/.dsh/skills/SKILL-IMPACT.md` 登记 Before/After/Evidence。
6. **定时任务**：WorkBuddy 的 4 条 rrule 调度 DSH 不会自动跑，见 `automations.md`，需要时把 prompt 丢给我执行。
7. **WorkBuddy 清理**：确认迁移无误后，可用已迁移的 `mac-agent-uninstall-residue-cleanup` 技能做残留清理；
   但请先处理 §3 里的 3.8GB 解释器与 MemOS 依赖。

---

## 5. 存档结构

```
~/Documents/DSH/workbuddy-archive/
├── MIGRATION.md          ← 本文件
├── SESSIONS_INDEX.md     ← 51 个会话导出索引（+51 条 DB 有记录但无本地转写）
├── sessions/*.md         ← 会话正文（用户/助手，去 system-reminder，单条 8000 字截断）
├── automations.md        ← 4 条定时自动化完整 prompt + rrule
├── tasks.md              ← 11 组任务清单快照
└── identity/WorkBuddy/   ← SOUL / USER / IDENTITY / BOOTSTRAP 原件

~/.dsh/                   ← DSH 侧已迁移资产
├── AGENTS.md             ← 现行记忆与守则（19KB）
├── cordis.patch.yml      ← MCP + hooks 注册（本机层，所有 profile 生效）
├── mcp.json              ← hook 读取的 MCP 镜像
├── skills/  scripts/  memwiki/  hooks/  memory/  secrets/
```
