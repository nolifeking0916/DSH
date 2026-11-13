---
id: injection-single-source-and-server-limit
title: 注入类插件：服务端 limit 与客户端截断要分开，插件禁用要在 profile 层确认
tags: [DSH, 插件, 注入, MemOS, 可观测性, 配置覆盖]
status: active
created: 2026-10-23
---

## 症状
合并后的注入插件 `@local/context-inject` 正常注入「经验(patterns)=3」和「记忆(mem)=4」，
但日志里 **skills 长期为 0**——技能那一路根本没供货。
与此同时还能收到旧的 `<skill_context>` 块，一轮同时注入 `<memos_context>`／`<skill_context>`／`<context_inject>` 三份。
插件在 UI 上显示 `active`，看起来一切正常。

## 根因
1. **服务端候选池被掐小**：插件把请求体里的 `memory_limit_number` 直接设成 `maxMem`（=4），
   这是**返回条数**的参数，不是**候选池**参数。服务端在候选池内先做视图排序再截断，
   池子只有 4 时 `include_memory_view` 里的 `skill` 那一路被完全挤掉。
   实测同一查询「按机构统计在职人数」：`memory_limit_number=4 → skill_detail_list=[]`；
   `=25 → skill_detail_list=[cloud-hr-db 0.62]`。
   **返回多少条是客户端截断的事，候选池给多大才是服务端检索的事——两者不能共用一个数。**
   而且**给足候选池仍不够**：合并视图（detail_factual+preference+skill 一次请求）里 skill 那一路照样被挤空，
   必须把 skill 单独发一次请求才能稳定拿到。
2. **profile 顶层条目覆盖插件自带补丁**：插件的 `cordis.patch.yml` 里写了
   `- id: wikiskill-inject / disabled: true`，但 profile 的 `cordis.patch.yml` 里同名 id 写着 `disabled: false`，
   **顶层裸条目优先级更高**，插件自带补丁被覆盖 → 三个注入插件同时在跑。

## 可复用做法
- **服务端 limit 与客户端截断分开**：`memory_limit_number` 给足（25 量级），返回后再按 `maxMem/maxSkills` 自己 slice；
- **但光给足 limit 还不够：多视图必须拆成并行多请求**。服务端在合并视图里会让某一视图被挤空，且**给大 limit 也救不回来**（实测 limit=25 时三视图 `skill=[]`、单 skill 视图 6 条）。正确做法：记忆请求（detail_factual+preference，带 conversation_id）与技能请求（只 skill，带 KB）**并行**发，耗时取慢的那条；技能请求不要带 conversation_id。
  代价是响应体从 ~3KB 涨到 ~20KB、耗时从 ~270ms 到 ~500-800ms，超时要相应放宽（实测 1.8s 够用）。
- **多路检索要做「分视图验证」**：分别用「合并视图」和「单视图」各打一次请求，看哪一路被挤空；
  只看合并请求的结果会误判成「没有匹配项」。
- **禁用插件要查最终生效的那一层**：插件自带 bundle 补丁 ≠ profile 补丁，profile 顶层条目会覆盖；
  验收看 `/tmp/<plugin>.log` 是否还在新增 `inject` 行，而不是看 UI 上插件是不是 active。
- **注入链路要有可观测字段**：每轮日志打 `patterns= / skills= / mem= / chars=`，哪一路为 0 一眼可见；
  再加一条「队列/命中/空手」统计进体检命令。
- **元问题会命中关键词噪声**：问「技能注入是否运作」这类问题时，语义检索会因 skill/技能 字样命中一批无关技能
  （实测推来 5 个钉钉技能）。这是正常题的正常表现，判断检索质量要用真实业务问句测。

## 适用边界
适用于 DSH 上任何「在 agent/pre-step 注入上下文」的插件（记忆/经验/技能/知识库索引），
以及任何「一次请求里带多视图 + 多上限参数」的检索型 API。
服务端行为差异需按各自 API 复核，不能照搬本条的 25 这个数。
