# DSH 上下文注入（单一注入源收敛）

DSH 每轮对话的上下文供给，收敛为**一条注入通道**：`@local/context-inject` 独占供给「经验 + 技能 + 记忆」，每轮只发一条消息、每类内容各设一份配额。

> 本仓库是这个主题的**独立归属地**：插件源码、规格、决策记录、研究笔记与经验条目都在这里；issue 历史（地图与决策票）也从主工作区仓库迁了过来。

## 为什么会有这个项目

原先三个本地插件同时注入同一轮上下文，带来两类问题：

1. **重复与成本**：每轮 1,519–1,988 字符、4 次 MemOS 请求、串行多耗 0.6–0.8 秒，条目级重复 26.2%。
2. **更隐蔽的两个缺陷**（比「同时在跑」更致命）：
   - `agent/pre-step` 的 `step` 是**会话内累计**的（实测涨到 113），而三个插件都写死 `injectStep: 1` ⇒ 注入条件退化成「会话的第一次 agent step」，**第一轮之后静默失效**（插件显示 active、日志一行都没有）；
   - context-inject 的【记忆】段因「经验 → 技能 → 记忆」顺序瓜分 800 字，room 实测 −53 ⇒ **整段不渲染**，而日志仍打 `mem=4`。

## 现在的形态

| 指标 | 三插件并跑 | 单源（现在） |
|---|---|---|
| 每轮注入字符 | 1,519–1,988 | **782–788** |
| MemOS 请求 | 4 次/轮（串行） | **2 次/轮**（并行） |
| 额外延迟 | +1,309–1,430 ms | +676～1,124 ms |
| 条目级重复 | 26.2% | **0** |
| 注入连续性 | 只有会话第一轮 | **每轮都有** |
| 采纳率（16 题 A/B） | 16.7%（人工复核 13.3%） | 经验 25.0% ＞ 技能 22.7% ＞ 记忆 9.1% |

## 装法（本机 profile 挂载）

插件以 `link:` 方式挂进桌面 profile：

```jsonc
// ~/.dsh/profiles/desktop/package.json
"dependencies": {
  "@local/context-inject": "link:/Users/leto/Documents/dsh-context-injection",
  "@local/memos-autoinject": "link:/Users/leto/Documents/dsh-context-injection/legacy/memos-autoinject",
  "@local/wikiskill-inject": "link:/Users/leto/Documents/dsh-context-injection/legacy/wikiskill-inject"
}
```

对应的软链在 `~/.dsh/profiles/desktop/node_modules/@local/context-inject`。

- 插件自带 bundle 补丁（`cordis.patch.yml`）负责把自己插进 profile，并**停用**历史的 `memos-autoinject` / `wikiskill-inject`（两者的源码仍留在主工作区仓库，可随时回滚：把 profile 层的 `disabled` 改回 `false` 即可，热生效、不用重启）。
- **改插件代码需要触发一次 profile 重算**才生效（linked package 的模块在重算时被替换）——最省事的做法是改一次 `~/.dsh/profiles/desktop/cordis.patch.yml`。
- 调试日志：`/tmp/context-inject.log`（`api:` / `pre-step:` / `inject:` 三类行）。

## 仓库结构

```
index.js / package.json / cordis.patch.yml   插件本体（@local/context-inject）
docs/spec.md                                  收敛方案规格（现状诊断 → 架构 → 迁移与回滚 → 验收）
docs/adr/0001-上下文注入以本地插件为单一来源.md        架构决策：为什么这样定、代价是什么
docs/research/                                两份研究笔记（通道全谱 / 采纳率与成本）
docs/patterns/                                经验条目（从 wiki 复制；正本在 ~/.dsh/wiki/patterns/）
legacy/memos-autoinject                       已停用的旧插件（保留回滚路径，未卸载）
legacy/wikiskill-inject                       同上
```

## 术语

「注入源」「单一注入源」「注入预算」「经验」「采纳率」的定义见本仓库根目录 `GLOSSARY.md`（沿用工作区的单上下文约定：术语只在根 `GLOSSARY.md` 一处维护）。

**单一注入源** = 每轮只由一条注入源发出一条注入消息，且每类内容（经验 / 技能 / 记忆）只有一个供给路径。

## 已知缺口（见 docs/spec.md §6）

- 原生技能目录的描述上限（默认 500 → 160）写进配置但**未生效**：app.asar 内未改动模块的配置改动，热重算不会让它重新 apply，需重启桌面端复核；若仍不生效，回落为「不动内核目录」，20K 固定开销保留。
- 定时提醒触发的轮次拿不到注入（判据只认普通用户消息）。
- `~/.dsh/AGENTS.md` 每轮被整份丢弃（超 65,536 B 指令预算）。
- 装上 DSH hooks 桥接插件后，`wikiskill_booster` 会成为第二条注入通道。

## 相关 issue

本主题的地图与决策票在本仓库的 issue 区（从主工作区仓库 `nolifeking0916/DSH` 迁入，票号随之变化：地图 #10 → **#2**）；里程碑在本仓库 #1；GitHub Project 看板「DSH 上下文注入（单一注入源收敛）」的条目随票自动跟随。

| 本仓库票号 | 主题 |
|---|---|
| #2 | 地图（wayfinder:map） |
| #3 / #4 | 目标架构 / 验收阈值 |
| #5 / #9 / #10 | 收敛到单源 / 补两处缺口 / 运行时复核 |
| #6 / #7 | 采纳率与成本 / 通道全谱 |
| #8 | 规格成文 |
| #1 / #11 / #12 | 提醒轮次缺口 / AGENTS.md 被丢弃 / hooks 第二通道 |
