---
id: injection-per-turn-and-quota
title: 注入类插件：pre-step 的 step 是会话累计的，「每轮注入」要按用户消息判定；预算要按类配额
tags: [DSH, 插件, 注入, MemOS, 可观测性, 预算, 会话]
status: active
created: 2026-10-24
---

## 症状

三个注入插件（`@local/context-inject` / `memos-autoinject` / `wikiskill-inject`）在**会话的第一轮之后再也不注入**：
长会话里越聊越「没有记忆、没有经验、没有技能」，但插件在 UI 上仍是 active，日志里也没有任何报错——
只有「本轮没有新的 inject 行」。

同时期还观察到两个伴生症状：
- 三个插件在同一轮同时注入（约 1,966 字符/轮、条目级重复 26.2%）；
- `@local/context-inject` 的【记忆】段几乎永远渲染不出来（日志里 `mem=4`，实际块里 0 条）。

## 根因

1. **`agent/pre-step` 的 `step` 是会话内累计的，不是每轮从 1 重置**。实测同一个会话里它一路涨到 113。
   三个插件都写死 `injectStep: 1`，于是「注入条件」实际变成「**会话的第一次 agent step**」，
   第一轮之后 step 永远 > 1 → 直接 return，连一行日志都不打（静默失效）。
   ⚠️ 用「有没有新的用户消息」当判据才是「每轮一次」：一轮里 agent 跑多个 step 时，
   已认领的 claimed 消息里**不再有**那条用户消息，所以天然只注入一次。
2. **profile 层的同名条目会覆盖插件自带 bundle 补丁**：`~/.dsh/profiles/desktop/cordis.patch.yml`
   里的 `- id: wikiskill-inject / disabled: false` 覆盖了插件自带的 `disabled: true` → 三插件并跑。
3. **单一预算 + 固定优先级 = 某类被挤成 0 条**：`render()` 按「经验→技能→记忆」顺序瓜分 800 字，
   经验 372 字 + 技能 333 字后，记忆只剩 2 字符（阈值 40 不渲染）→ 整段消失，而日志仍打 `mem=4`。
4. **`link:` 挂载的本地插件，改代码不会立刻生效**：要等一次 profile 重算（改 profile patch / 触发 recomposition）
   才会替换 linked package 的模块。HMR 的模块监听默认关闭（`root: []`）。

## 可复用做法

- **「每轮注入一次」= 用户消息变了才注入**：记 `会话 id → 已注入的用户消息 id`，同一条不重复注入；
  不要用 `step === 1` 当判据。判据要能同时覆盖「新的一轮」与「同一轮的第 N 个 agent step」。
- **注入链路要有可观测字段**：`pre-step: step=… claimed=… queryLen=…` + `inject: patterns=… skills=…(来源) mem=… chars=…`。
  静默 return 的分支也要打一行 `skip:`——否则「插件没干活」和「插件不存在」分不开。
- **技能要有本地兜底**：MemOS 技能视图命中为 0（阈值不达标）或请求失败时，退回读本地 `SKILL.md` 做关键词匹配，
  否则单源化之后会出现「技能段空掉」的裸奔状态。日志里标注来源（`(memos)` / `(local)`）。
- **预算按类配额，不要顺序瓜分**：给「经验 / 技能 / 记忆」各设配额（如 340 / 220 / 240），
  再按总预算等比缩放，保证每一类都有出场机会；条目超配额就截断该条并停。
- **禁用插件要查最终生效的那一层**：看 `/tmp/<plugin>.log` 是否还在新增 `inject` 行，而不是看 UI 上是不是 active；
  profile 层同名条目优先级高于插件自带 bundle 补丁，后写覆盖。
- **改本地插件代码后**：touch 一次 profile patch 触发重算，linked package 才会被替换；
  验收看日志里的新 `apply:` 行（新代码会打印新配置项）。
- **验「是不是真注入了」**：查会话 transcript 里每条消息的 `source.kind`（`context-inject` / `memos-recall` / `wikiskill-context`），
  这是唯一能区分「谁产出的注入块」的可靠字段；拼措辞去猜来源会猜错。

## 残留缺口（2026-10-24 实测）

- **定时提醒触发的轮次不注入**：`schedule_create` 送达的 `[SCHEDULE REMINDER]` 消息在 `agent/pre-step`
  的 claimed 消息里取不到（预检日志 `skip: no user message (step=1..4)`），所以这一轮没有 `<context_inject>`。
  正常用户消息轮次照常注入（实测 step=81 与 step=1 都有）。
  若要覆盖这类轮次，判据要从「claimed 里有未注入的用户消息」放宽到「会话里有未注入的用户消息」
  （需要改用 session transcript 或 message id 全量集合，而不是 claimed 切片）。

## 适用边界

适用于任何挂在 `agent/pre-step` 上做上下文注入的插件（记忆 / 经验 / 技能 / 知识库索引），
以及任何「按预算顺序拼接多类内容」的渲染器。
`step` 是否累计、以及 claimed 消息是否保留历史，各 harness 版本需实测复核，不能照搬本条的结论。
