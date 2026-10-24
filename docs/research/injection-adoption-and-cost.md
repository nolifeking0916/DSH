# 注入的采纳率与成本实测（DSH 上下文注入 · 地图 #10 / 票 #14）

> **一句话结论（现态＝三插件并跑）**：每轮真实注入 **1 966 字符 ≈ 1 000 净 token**、**4 次 MemOS HTTP 请求**、**串行 +1.3~1.4 s 墙钟**；三路之间**条目级重复 26.2 %（21/80）、字符级重复 7.9 %（1 543/19 639）**；其中 context-inject 的「记忆」段在并跑轮次里**只有 2/10 轮真正露出**（其余被 800 字预算挤掉）——即它一半的 MemOS 流量（记忆视图请求）在现态下**几乎白花**。采纳侧：离线 A/B（注入块 vs 裸问句，同模型端点、各跑一次）实测 **16.7 %（15/90 条目，人工复核后 13.3 %）**，分路 **经验 25.0 % > 技能 22.7 % > 记忆 9.1 %**；**采纳只能证明相关性，不等于答案正确率提升**。单源态线上对照臂**待跑**（等票 #13）。

> **本文件是 `docs/research/` 这个新目录下的第一篇**。仓库此前没有统一的 research 目录，只有任务级的 `work/<主题>/research/*.md`（例：`work/assessment-kit/research/无障碍与打印归档基线_20261024.md`）。本图（#10）的研究票统一落在 `docs/research/`，文件名 = 票号主题。**这是新约定，不是既有约定**；若后续票沿用，需在 `AGENTS.md` 里补一句才算固化。

---

## 0. 口径、证据等级与边界声明

### 0.1 口径（维护者已定，本笔记不改）

| 口径 | 定义 | 实现位置 |
|---|---|---|
| **采纳** | 注入条目被模型在**最终回答**中实际使用的比例：用注入条目里的关键短语／结论在回答中是否出现来判定 | §4.2 判分规则（机械可复跑） |
| **成本** | 每轮注入的**字符数与 token**、**额外 MemOS 请求次数与延迟**、**重复内容占比** | §3 |

### 0.2 边界声明（必须先读）

- **采纳只能证明相关性，不等于答案正确率提升。** 本笔记测的是「注入里的内容有没有出现在回答里」；回答**对不对**、是否更完整、是否更少返工，**不在本图验收范围内**（票 #14 原文：§要做的事 4）。票 #12《验收口径与阈值：什么样的数据算「有实质作用」》才是定阈值的地方。
- 本轮每臂**只跑一次**（票要求「各跑一次」）。n=1、且模型带 thinking，**单题结果有方差**；所以本笔记给的是**聚合口径**（全部题一起算），不是单题结论。
- A 臂的 prompt = **注入块 + 问句**拼成**一条** user 消息（Anthropic 协议要求 user/assistant 严格交替，DSH 真实链路是插一条独立 user 消息，此处合并，**对模型可见内容等价**）。
- A 臂**不带** system prompt（DSH 真实链路有完整 system prompt + runtime context）。这会让 A 臂的绝对表现低于线上，但**A/B 差值**仍然可比。
- **现态 ≠ 单源态**：本票此刻测的是**三插件并跑**；单源对照臂**待跑**，等票 #13 落地，§5 给出**一条命令**补跑。
- 任何**没有实测到的数字，一律写「未测到 + 原因」**，不做估算。

### 0.3 证据来源（一手）

| 来源 | 用途 |
|---|---|
| `/Users/leto/Documents/DSH/plugins/context-inject/index.js` | 注入块生成逻辑（`render()` 257-288、`loadPatterns()` 119-143、`matchPatterns()` 152-164、`recallOnce()` 168-253） |
| `/Users/leto/Documents/DSH/plugins/memos-autoinject/index.js`、`plugins/wikiskill-inject/index.js` | 另外两路的请求体与渲染逻辑 |
| `/Users/leto/Documents/DSH/plugins/*/cordis.patch.yml`、`~/.dsh/profiles/desktop/cordis.patch.yml` | 生效配置（含「三插件并跑」的成因） |
| `/tmp/context-inject.log`、`/tmp/memos-autoinject.log`、`/tmp/wikiskill-inject.log` | 现态每轮字符数、请求数、耗时 |
| `~/.dsh/sessions/--Users-leto-Documents-DSH--/<会话 id>/session.v4.jsonl.zstd` | **真实注入块全文**（三块同轮的原文，用于算重复率） |
| `~/.dsh/wiki/patterns/*.md` | 经验库（注入内容来源） |
| `workbuddy-archive/sessions/*.md` | 题集来源（真实用户问句） |
| MiniMax Anthropic 兼容端点 `https://api.minimax.cn/anthropic`（`~/.dsh/profiles/desktop/cordis.patch.yml:23-52` 定义） | A/B 实测 |

> **密钥处理**：`MINI_API_KEY` 不在本会话的进程环境里（实测 `env` 无此变量，见 §4.1），改从 `~/.dsh/.credentials.yaml` 的 `refs.MINI_API_KEY` 取出后**只在子进程环境变量里使用**；本文件、脚本与汇报里**都不含任何密钥明文**。

---

## 1. 现态是什么：三插件并跑是怎么发生的

仓库里的插件自带补丁**本来是要关掉另两个的**：

- `plugins/context-inject/cordis.patch.yml:28-31` → `- id: memos-autoinject / disabled: true`、`- id: wikiskill-inject / disabled: true`。

但**profile 层把它们又打开了**：

- `~/.dsh/profiles/desktop/cordis.patch.yml:113-116` →
  ```yaml
  - id: wikiskill-inject
    disabled: false
  - id: memos-autoinject
    disabled: false
  ```

profile 补丁是「顶层裸条目覆盖」，优先级高于插件自带补丁 → **每轮三个注入插件各注入一条**，实测同一轮里能同时看到 `<context_inject>` / `<skill_context>` / `<memos_context>` 三块（§3.2 有原文与出处）。

这条根因已在既有 wiki 经验条 `~/.dsh/wiki/patterns/injection-single-source-and-server-limit.md:24-26` 记过；本票补的是**它没记的另一半**：这套并跑**每轮到底花多少、产出多少、重复多少**。

---

## 2. 题集与判分规则

### 2.1 题集来源

题集全部来自本工作区**真实用户问句**：`workbuddy-archive/sessions/*.md` 里的 `<user_query>` 轮次（共 352 条用户轮次，抽 16 条），覆盖本工作区的真实业务面（HR 制度/花名册/职代会/在线表格/技能调用/记忆系统自检）与**元问题**（问注入、记忆、MCP 本身是否在跑）。

### 2.2 注入块怎么生成（不编造）

每条问句都走**插件自己的代码路径**复现：

1. 经验：`loadPatterns('~/.dsh/wiki/patterns')`（真实目录，只取 `status: active`）+ `matchPatterns()`，取前 `maxPatterns=3`（`index.js:119-164`）。
2. 记忆 + 技能：`recallOnce()`（`index.js:168-253`），**并行发 2 个 `POST /search/memory`**：`memory_limit_number=25`、`relativity=0.45`、记忆视图 `['detail_factual','preference']`、技能视图 `['skill']`、带 `kbId`。
3. 组装：`render()`（`index.js:257-288`），预算 `budgetChars=800`，优先级 经验 → 技能 → 记忆。

> 实现方式：测量脚本**从 `plugins/context-inject/index.js` 源码里原样抽出** `loadPatterns/bigrams/matchPatterns/render/recallOnce` 五个函数再调用（不重写、不改语义），脚本见 §7。注入内容因此是**插件真实会注入的内容**，不是人工编的。

### 2.3 判分规则（机械可复跑）

对每个被注入的条目：

1. 从条目文本里抽「**显著短语**」：ASCII 词（≥5 字符）+ CJK 连续片段（≥5 字）。
2. **剔除问句里已经出现的短语**（否则模型本来就会说，算不出注入的功劳）。
3. **采纳判定**：回答正文包含 ≥1 条显著短语 → 该条目判「被采纳」。
4. 同时在 B 臂（无注入）上跑同一套判定，得出 **净采纳 = A 命中且 B 未命中**（这才是「因为注入才被用上」的严格版）。

> **为什么不用「关键词出现」这么糙的口径**：注入条目里大量是通用词（「记忆」「技能」「任务」），回答里天然会出现。剔除问句内短语 + 要求 ≥5 字片段，把误判压到可人工复核的范围。§4.3 给出**逐条命中原文**供人工复核。

---

## 3. 成本基线（现态＝三插件并跑）

### 3.1 现态每轮要花什么

| 项 | 口径 | 实测值 | 出处 |
|---|---|---|---|
| 注入字符 | 三块合计 | **1 966 字符**（`<context_inject>` 795 + `<skill_context>` 517 + `<memos_context>` 654） | `/tmp/context-inject.log:307`（`chars=795`）、`/tmp/wikiskill-inject.log:103`（`chars=517`）、`/tmp/memos-autoinject.log:39`（`chars=654`）；块全文见 `~/.dsh/sessions/--Users-leto-Documents-DSH--/session-c0e130d4-…/session.v4.jsonl.zstd`（2026-10-24T11:28:58） |
| 注入 token | 三块合计 | **1 106 – 1 242 token**（`count_tokens` 实测，含 202 固定开销）／**净 904 – 1 040 token** | §3.4 |
| MemOS 请求次数 | 每轮 HTTP 次数 | **4 次**：context-inject 2 次（记忆视图 + 技能视图，并行）+ memos-autoinject 1 次 + wikiskill-inject 1 次（kb 路径） | `plugins/context-inject/index.js:219`（`Promise.all([post(memBody), post(skillBody)])`）、`plugins/memos-autoinject/index.js:145`、`plugins/wikiskill-inject/index.js:185` |
| 墙钟延迟 | 三插件**串行**相加 | **1 309 ms**（571 + 329 + 409） | `/tmp/memos-autoinject.log:38,40`、`/tmp/wikiskill-inject.log:104`、`/tmp/context-inject.log:308` |
| 墙钟实测跨度 | pre-step 开始 → 最后一块注入完成 | **1 316 ms**（03:28:56.734Z → 03:28:58.050Z） | 同上三行时间戳 |
| 重复内容占比 | 条目级 | **26.2 %**（21/80 条注入条目与另一路同名） | §3.3 |
| 重复内容占比 | 字符级 | **7.9 %**（1 543/19 639 字符） | §3.3 |

**串行而非并行**：三个插件都注册在 `agent/pre-step` 且都是 `const decision = await next(); …干活…` 的中间件形态（`context-inject/index.js:299-300`、`memos-autoinject/index.js`、`wikiskill-inject/index.js:353-354`）。按 cordis 的中间件链，**先注册的先干活、后注册的后干活**，三段耗时相加。时间戳可以证伪「并行」假设：`memos-autoinject` 结束于 `.304` → `wikiskill-inject` 结束于 `.638`（差 334 ms ≈ 它自己的 329 ms）→ `context-inject` 结束于 `.050`（差 412 ms ≈ 它自己的 409 ms）。三段首尾相接。

**2026-10-24T03:34Z 那一轮**同样成立：`pre-step 03:34:05.164` → `memos 05.596`（432 ms）→ `wikiskill 06.037`（433 ms）→ `context-inject 06.594`（552 ms），合计 **1 430 ms**（`/tmp/memos-autoinject.log:41-43`、`/tmp/wikiskill-inject.log:105-106`、`/tmp/context-inject.log:309-310`）。

### 3.2 三块同轮的原文（现态样本）

`2026-10-24T11:28:58`（= UTC 03:28）这一轮，三块同时注入（会话 `session-c0e130d4-4f1c-48fd-bd93-40da66c9956f`，`~/.dsh/sessions/--Users-leto-Documents-DSH--/session-c0e130d4-…/session.v4.jsonl.zstd`）：

- `<context_inject>`：3 条经验 + 4 条技能 + 1 条记忆（记忆段被 800 字预算**截断**，只露出 1 条，末尾带 `…`），795 字符。
- `<skill_context>`：6 条技能 + 1 条经验（来自 wiki 的「相关经验」），517 字符。
- `<memos_context>`：4 条记忆，654 字符。

`2026-10-24T11:34:06`（= UTC 03:34）那一轮（会话 `session-fd373cf7-2915-4abf-a2a3-8f278a80bc67`）：`795 + 517 + 654 = 1 966` 字符，`context_inject` 的记忆段**一条都没露出来**。

### 3.3 重复内容占比（现态 10 个并跑轮次全量）

口径：**同一轮内**，如果某条注入条目的「判定键」（经验＝标题、技能＝技能名、记忆＝前 20 字）出现在**另一个块**里，就算重复。

| 轮次（本地时间） | 会话 | ctx | skill | memos | 合计 | 重复条目 | 重复字符 | ctx 里【记忆】可见条数 |
|---|---|---|---|---|---|---|---|---|
| 10:49:22 | session-4c7b3533 | 795 | 517 | 616 | 1 928 | 4/8 | 264 | 2 |
| 11:21:39 | de83becf | 795 | 517 | 676 | 1 988 | 0/8 | 0 | 0 |
| 11:22:29 | session-eed4a016 | 795 | 517 | 648 | 1 960 | 5/8 | 353 | 0 |
| 11:27:55 | 31265c40 | 795 | 517 | 676 | 1 988 | 0/8 | 0 | 0 |
| **11:28:58** | **session-c0e130d4** | **795** | **517** | **654** | **1 966** | **1/8** | **77** | **1** |
| **11:34:06** | **session-fd373cf7** | **795** | **517** | **654** | **1 966** | **1/8** | **78** | **0** |
| 11:35:03 | 76be7d84 | 795 | 517 | 676 | 1 988 | 2/8 | 174 | 0 |
| 11:35:05 | 1f19c4e4 | 795 | 517 | 676 | 1 988 | 1/8 | 65 | 0 |
| 11:40:04 | session-001c2e62 | 795 | 517 | 567 | 1 879 | 6/8 | 460 | 0 |
| 11:45:06 | 35d7cc8c | 795 | 517 | 676 | 1 988 | 1/8 | 72 | 0 |
| **合计/均值** | 10 轮 | 795 | 517 | 634 | **min 1 879 / p50 1 977 / mean 1 964** | **21/80 = 26.2 %** | **1 543/19 639 = 7.9 %** | **2/10 轮可见** |

三个可以立刻拿来决策的事实：

1. **每轮固定 ~1 966 字符**，因为三块各自有硬上限（`budgetChars=800` / `maxChars=500` / `maxChars=600`），跟问句内容几乎无关（10 轮里 9 轮是 795+517）。
2. **并跑时 context-inject 的记忆段基本露不出来**：10 轮里只有 **2 轮**能看到【记忆】条目。因为 `render()`（`index.js:257-288`）按 经验 → 技能 → 记忆 顺序拼块，800 字预算被前两段吃掉后，记忆段被整段截断（`body += \n${block.slice(0, room)}…`，`index.js:281`）。**即 context-inject 的记忆视图请求（它 2 次 MemOS 请求里的 1 次）在现态下基本是白花的**。
3. **重复主要发生在技能路**：21 条重复条目里绝大多数是「同一个技能在 `【技能】` 和 `<skill_context>` 各出现一次」（例：11:40:04 那轮 6/8 全是技能重复，重复字符 460）。经验路重复少，因为 `<skill_context>` 只带 **1 条** wiki 经验（`wikiskill-inject/index.js:285-291`）。

### 3.4 token 折算与全量日志分布

**每轮注入 token（实测 `POST /anthropic/v1/messages/count_tokens`，基线 `count_tokens("")=202`）**

| 轮次（本地） | ctx 字符/token | skill 字符/token | memos 字符/token | 合计字符 | 合计 token | **净注入 token** |
|---|---|---|---|---|---|---|
| 10:49:22 | 795 / 599 | 517 / 438 | 616 / 505 | 1 928 | 1 138 | **936** |
| 11:21:39 | 795 / 605 | 517 / 422 | 676 / 526 | 1 988 | 1 149 | **947** |
| 11:22:29 | 795 / 612 | 517 / 458 | 648 / 576 | 1 960 | 1 242 | **1 040** |
| 11:27:55 | 795 / 590 | 517 / 422 | 676 / 526 | 1 988 | 1 134 | **932** |
| **11:28:58** | **795 / 651** | **517 / 444** | **654 / 542** | **1 966** | **1 233** | **1 031** |
| **11:34:06** | **795 / 590** | **517 / 444** | **654 / 542** | **1 966** | **1 172** | **970** |
| 11:35:03 | 795 / 585 | 517 / 418 | 676 / 547 | 1 988 | 1 146 | **944** |
| 11:35:05 | 795 / 563 | 517 / 416 | 676 / 547 | 1 988 | 1 122 | **920** |
| 11:40:04 | 795 / 596 | 517 / 455 | 567 / 494 | 1 879 | 1 141 | **939** |
| 11:45:06 | 795 / 562 | 517 / 422 | 676 / 526 | 1 988 | 1 106 | **904** |

合计 token：**1 106 – 1 242**，**净注入 904 – 1 040**（均值 ~956）；字符/token 比约 **1.26**（中英混排 + markdown 噪声）。
（合计 token = 三块拼成**一条** user 消息后计数，所以固定开销 202 只付一次；分块 token 列各自都含一次 202 开销。）

**全量日志分布（2026-10-21 → 2026-10-24，三路各自）**

| 插件 | 注入字符 min/p50/max | 自身耗时 ms min/p50/max | 样本 |
|---|---|---|---|
| context-inject | 159 / 675 / 801 | 324 / 515 / 1 148 | n=156 注入行、n=155 api 行 |
| memos-autoinject | 181 / 648 / 676 | 343 / 574 / 1 070 | n=19 |
| wikiskill-inject | 214 / 517 / 517 | 294 / 395 / 714 | n=49 注入行、n=56 kb 行 |

（`/tmp/context-inject.log`、`/tmp/memos-autoinject.log`、`/tmp/wikiskill-inject.log` 逐行解析；「自身耗时」= 该插件从发起到写日志的毫秒数。）

### 3.5 现态 vs 单源态：待跑臂

本票此刻测的是**三插件并跑**。**单源态（只留 context-inject）的对照臂待跑**，等票 #13《把注入收敛到单源：停用两个旧插件并保留回滚路径》落地（票 #14 的 `blockedBy` 就是 #13）。补跑方式见 §5。

---

## 4. A/B 实测：注入到底有没有被用上

### 4.1 端点与样本

| 项 | 值 | 出处 |
|---|---|---|
| 端点 | `https://api.minimax.cn/anthropic/v1/messages` | `~/.dsh/profiles/desktop/cordis.patch.yml:33`（`baseURL`）+ `:31`（`apiKeyEnv: MINI_API_KEY`）+ `:32`（`api: anthropic-messages`） |
| 模型 | `MiniMax-M3.1-Flash`（与 `agent-default-model` 路由一致） | `~/.dsh/profiles/desktop/cordis.patch.yml:43,89-92` |
| 密钥 | `MINI_API_KEY` **不在本会话进程环境里**（实测 `env` 无此变量）；从 `~/.dsh/.credentials.yaml` 的 `refs.MINI_API_KEY` 取出后仅在子进程环境变量中使用，**未落盘、未出现在本文件任何地方** | `~/.dsh/.credentials.yaml`（`refs:` 段） |
| 端点连通性 | 有效密钥 POST → **200**；占位密钥 POST → **401**（真实 ALB 回 `trace-id`/`alb_request_id`） | 探测命令输出（密钥未打印） |
| 题量 | 16 条真实用户问句 | §2.1、§7.3 |
| 每臂调用次数 | **1 次**（票要求「各跑一次」） | §7 脚本 |
| `max_tokens` | 8 000（thinking 与正文共用额度；见下方踩坑） | — |

**踩坑（已修，记录在此避免复跑者重踩）**：首轮用 `max_tokens=1200` 跑，MiniMax 的 adaptive thinking 把额度吃掉，**4/7 题的回答正文为空**（`output_tokens=1200` 而 `content` 里没有 `text` 块），无法判分。改成 `max_tokens=8000` 后正文正常。**thinking 是 MiniMax 服务端默认开启的**（不传 `thinking` 参数也会产生 `output_tokens_details.thinking_tokens`），且 `thinking:{type:'disabled'}` 会被该端点 400 拒（与 `cordis.patch.yml:34-41` 的注释一致）。

### 4.2 判分

按 §2.3 的机械规则：注入条目 → 显著短语（剔除问句内已有短语）→ 回答正文命中即「采纳」；**净采纳** = A 命中且 B 未命中。

### 4.3 对照表

| 题 | 问句（节选） | 出处 | 注入条目（经/技/记） | 注入字符 | 注入 token(净) | A 耗时 | B 耗时 | A 采纳/条目 | 净采纳 | 人工复核后 | 判分资格 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Q01 | 我的定时任务也丢失了啊 | `202610021622_定时任务丢失问题排查.md:12` | 2/4/4 | 795 | 402 | 30619 ms | 1987 ms | 1/10 | 0 | 0 | 不可判(标题JSON) |
| Q02 | 帮我测试下本地的memos数据库和wiki相关MCP… | `202610021623_测试memos与wiki的MCP hooks流程.md:12` | 3/4/4 | 771 | 375 | 81571 ms | 33658 ms | 3/11 | 3 | 1 | 可判 |
| Q03 | 查下云端数据库是不是健康，同时建立或启用相关MCP服… | `202610021646_检查云端数据库并启用MCP服务.md:12` | 3/5/4 | 795 | 382 | 74653 ms | 2355 ms | 7/12 | 7 | 6 | 不可判(标题JSON) |
| Q04 | 我现在的对话，有在使用我的本地记忆和学习 MCP吗？ | `202610031410_吉华丹 补上预约.md:1893` | 3/2/4 | 795 | 418 | 8985 ms | 3850 ms | 3/9 | 3 | 2 | 可判 |
| Q05 | 本地那个 enterprise.db 确认是 0 字… | `202610031410_吉华丹 补上预约.md:1298` | 3/4/4 | 785 | 361 | 7486 ms | 2068 ms | 2/11 | 2 | 2 | 不可判(标题JSON) |
| Q06 | 现在测试并验证下我的本地记忆系统 | `202610031635_切换到 DeepSeek 并删除本地模型组件.md:12` | 3/1/4 | 797 | 400 | 38090 ms | 15456 ms | 2/8 | 2 | 2 | 可判 |
| Q07 | 你能测试下，我现在的记忆系统，到底有没有帮助到wor… | `202610061032_全面修改并落实建议.md:1427` | 3/2/4 | 795 | 404 | 57131 ms | 26926 ms | 5/9 | 5 | 5 | 可判 |
| Q08 | 量比 和 委比 什么意思 | `202610131206_解释量比和委比含义.md:12` | 0/0/4 | 368 | 200 | 8077 ms | 10986 ms | 0/4 | 0 | 0 | 可判 |
| Q09 | 猎聘的背调基本流程 | `202610131249_猎聘背调流程梳理.md:12` | 0/0/4 | 383 | 206 | 9852 ms | 18223 ms | 0/4 | 0 | 0 | 可判 |
| Q10 | 推荐 国产替代的半导体设备和英伟达产业链的PCB | `202610131414_推荐半导体设备与英伟达产业链PCB.md:12` | 0/0/4 | 294 | 145 | 41102 ms | 79225 ms | 0/4 | 0 | 0 | 可判 |
| Q11 | 朱晁均 查一下他所有的数据 上个月的薪资 | `202610141407_查询朱晁均上月薪资数据.md:12` | 3/1/4 | 801 | 466 | 15265 ms | 12347 ms | 1/8 | 1 | 1 | 可判 |
| Q12 | 南京林业大学 甘肃农业大学 国内相关的排名或者专业排… | `202610121204_查询两所高校国内排名和专业排名.md:12` | 0/0/3 | 310 | 179 | 73331 ms | 66239 ms | 0/3 | 0 | 0 | 不可判(截断、无正文) |
| Q13 | 帮我生成一个智能表格，用日历的形式去选择自己的休息时… | `202609261833_确认图片文字修改情况.md:12` | 3/3/4 | 795 | 406 | 50438 ms | 37519 ms | 0/10 | 0 | 0 | 可判 |
| Q14 | 你能查到我会议的云录音和见面谈记录吗？ | `202610071301_按时间顺序填写表格.md:12` | 3/5/4 | 782 | 422 | 7436 ms | 4852 ms | 1/12 | 1 | 1 | 可判 |
| Q15 | 花名册指的是 企业微信的通讯录接口啊，你能不能抓到最… | `202610031410_吉华丹 补上预约.md:2241` | 3/4/4 | 795 | 432 | 23534 ms | 2169 ms | 3/11 | 3 | 3 | 不可判(标题JSON) |
| Q16 | 帮我优化排版，美化布局和颜色，同时确保在一页上 | `202610071301_按时间顺序填写表格.md:1733` | 3/4/4 | 795 | 419 | 6539 ms | 3315 ms | 0/11 | 0 | 0 | 可判 |

> 「注入 token(净)」= `/v1/messages/count_tokens` 实测值减去空消息基线 202 token（实测 `count_tokens("")=202`）。
> 「A 采纳/条目」= 该题注入条目中，判定短语出现在 A 臂回答里的条数；「净采纳」= A 命中且 B 未命中；「人工复核后」= 剔除 5 条明显误判（见 §4.4）后的条数。
> 「不可判」= 该题至少一臂没产出正文（MiniMax 回的是 `{"isNewTopic":…,"title":…}` 标题 JSON，或 8 000 token 截断后正文为空），这一题不进入分母。
>
> 复核说明：`ready`（Q04）、`limit`（Q07）、`launchd`（Q02）是通用英文词，但回答里的用法能对上注入条目原文（如 Q07 回答写了「服务端 limit 是 25，客户端要求最多返回 10 条」），故仍判有效；`title`/`macos`/`tools`/`prepare`/`profile` 五条判为误判。

| 口径 | 题数 | 注入条目 | A 采纳 | B 采纳 | 净采纳 | 人工复核后 A 采纳 | 人工复核后净采纳 |
|---|---|---|---|---|---|---|---|
| 全部（16 题） | 16 | 137 | 28（20.4%） | 1（0.7%） | 27（19.7%） | 23（16.8%） | 23（16.8%） |
| **可判分（11 题）** | 11 | 90 | 15（16.7%） | 0（0.0%） | 15（16.7%） | 12（13.3%） | 12（13.3%） |

可判分 11 题按供给类型拆开（条目级）：

| 供给类型 | 注入条目数 | A 采纳 | 净采纳 | 人工复核后 A 采纳 |
|---|---|---|---|---|
| 经验 | 24 | 6（25.0%） | 6（25.0%） | 5（20.8%） |
| 技能 | 22 | 5（22.7%） | 5（22.7%） | 3（13.6%） |
| 记忆 | 44 | 4（9.1%） | 4（9.1%） | 4（9.1%） |

### 4.4 逐条命中明细（供人工复核）

| 题 | 供给 | 命中短语 | 条目原文（节选） | 判定 |
|---|---|---|---|---|
| Q01 | 经验 | `title` | - 名单 / 盘点类任务：先查潜规则表，再动数：第 0 步先查云库 `public.tacit_rules` 的 act | 误判（通用词/非本条目来源） |
| Q02 | 经验 | `launchd` | - launchd 定时任务读不到 ~/Documents（macOS TCC 拦截），且失败会被静默吞掉：- **la | 有效采纳 |
| Q02 | 技能 | `macos` | - mac-agent-uninstall-residue-cleanup：macOS 上彻底清除已卸载 AI agen | 误判（通用词/非本条目来源） |
| Q02 | 技能 | `tools` | - qwenwork-guidance：Routing guide for the built-in QwenWork  | 误判（通用词/非本条目来源） |
| Q03 | 经验 | `企微原生数据` | - 企微三条通道的能力边界 + 「企业后台」与「企业微信」是两套数据源：- 先判定数据源：企业后台数据（无 IP 限制） | 有效采纳 |
| Q03 | 技能 | `cloudbase` | - cloud-hr-db：云上文旅集团「云上HR数据库」（CloudBase PostgreSQL）取数口径与访问路径 | 有效采纳 |
| Q03 | 技能 | `cloudbase` | - yunshang-cloud-ops：云上文旅集团「云端与企微通道运维」——CloudBase 环境接入、云函数固定 | 有效采纳 |
| Q03 | 技能 | `runtime-env-contract` | - runtime-env-contract：WorkBuddy 工作区「运行时契约自检与修复」——venv 建仓/切解 | 有效采纳 |
| Q03 | 技能 | `prepare` | - qw-pages-supabase：Prepare Supabase-compatible persistent s | 误判（通用词/非本条目来源） |
| Q03 | 记忆 | `cloudbase` | - 用户获悉CloudBase环境即将于2026年10月26日到期。助手建议优先续费以防定时任务与数据同步中断，或待续费 | 有效采纳 |
| Q03 | 记忆 | `cloudbase` | - 用户描述了线上数据库（CloudBase）和本地工作环境的结构，指出已落地‘加速三件套’包括云函数只读通道和本地脚本 | 有效采纳 |
| Q04 | 经验 | `profile` | - 注入类插件：服务端 limit 与客户端截断要分开，插件禁用要在 profile 层确认：- **服务端 limit | 误判（通用词/非本条目来源） |
| Q04 | 记忆 | `memos-api-mcp` | - memos-api-mcp(user=ETF)与memos-hr(user=HR)共用同一MEMOS_API_KEY | 有效采纳 |
| Q04 | 记忆 | `ready` | - 2026年9月11日晚上6:53，用户通过MCP成功检索并获取了事实与偏好记忆。此次实操验证了MCP在会话建立前必须 | 有效采纳 |
| Q05 | 技能 | `cloud-hr-db` | - cloud-hr-db：云上文旅集团「云上HR数据库」（CloudBase PostgreSQL）取数口径与访问路径 | 有效采纳 |
| Q05 | 技能 | `hrq-pg` | - runtime-env-contract：WorkBuddy 工作区「运行时契约自检与修复」——venv 建仓/切解 | 有效采纳 |
| Q06 | 记忆 | `memos_sync.py` | - 2026年10月3日下午4:36，用户对本地记忆系统进行了测试，重点验证了 memos_sync.py 的全链路流程 | 有效采纳 |
| Q06 | 记忆 | `memos_sync.py` | - 2026年9月23日17:24，用户执行了一次本地迁移验证写入操作。该操作基于memos_sync.py脚本的本地模 | 有效采纳 |
| Q07 | 经验 | `会被代码签名拒绝` | - DSH 桌面端加载本地编译 .node 会被代码签名拒绝：需要原生模块的插件在桌面端**不可用**，改用纯 JS/H | 有效采纳 |
| Q07 | 经验 | `hrq-pg` | - hrq-pg / hrdata 取数报「JSON 解析失败：'data'」＝ SQL 里驼峰列名没加双引号：- PG | 有效采纳 |
| Q07 | 经验 | `limit` | - 注入类插件：服务端 limit 与客户端截断要分开，插件禁用要在 profile 层确认：- **服务端 limit | 有效采纳 |
| Q07 | 技能 | `runtime-env-contract` | - runtime-env-contract：WorkBuddy 工作区「运行时契约自检与修复」——venv 建仓/切解 | 有效采纳 |
| Q07 | 技能 | `dingtalk-minutes` | - dingtalk-minutes：钉钉 AI 听记。Use when 查询或修改听记摘要、完整逐字稿、关键词、标签、 | 有效采纳 |
| Q11 | 经验 | `hrq-pg` | - hrq-pg / hrdata 取数报「JSON 解析失败：'data'」＝ SQL 里驼峰列名没加双引号：- PG | 有效采纳 |
| Q14 | 技能 | `完整逐字稿` | - dingtalk-minutes：钉钉 AI 听记。Use when 查询或修改听记摘要、完整逐字稿、关键词、标签、 | 有效采纳 |
| Q15 | 经验 | `企业后台数据` | - 企微三条通道的能力边界 + 「企业后台」与「企业微信」是两套数据源：- 先判定数据源：企业后台数据（无 IP 限制） | 有效采纳 |
| Q15 | 经验 | `hr_persons_all` | - 名单与后台对不上时：姓名+机构双字段匹配，待核项单列：1. 每次出名单前现拉后台（`hr_persons_all`， | 有效采纳 |
| Q15 | 技能 | `userid` | - dingtalk-contact：钉钉通讯录精确查询。Use when 已有 userId 后查详情、部门、职位或邮 | 有效采纳 |

---

## 5. 单源态对照臂：**待跑**，一条命令补跑

票 #14 的 `blockedBy` 是票 #13《把注入收敛到单源：停用两个旧插件并保留回滚路径》。**#13 落地前，本票无法给出单源态的线上对照臂。**

### 5.1 现在就能确定的事（不需要等 #13）

§4 的 A/B 用的是 **context-inject 自己的 `render()` 输出**，也就是**单源注入块**。所以：

- §4 的采纳率数字**已经是「单源注入块」的采纳率**，不用重跑；
- #13 会改变的是**线上每轮的成本**与**模型在完整 system prompt 下**的采纳表现。
  - 单路成本可参考 context-inject 自身实测：注入字符 p50 675 / p90 795，api 耗时 p50 515 ms / p90 752 ms（§3.4）；**但「并跑 → 单源」之后的线上净墙钟收益，本票未测到**（#13 落地后用 §5.2 命令实测）。

### 5.2 一条命令补跑（#13 落地后）

```bash
export MINI_API_KEY="$(python3 -c "import re,pathlib;print(re.search(r'^\s*MINI_API_KEY:\s*(.+)$',pathlib.Path.home().joinpath('.dsh/.credentials.yaml').read_text(),re.M).group(1).strip())")" \
 && node /tmp/measure_injection_adoption.mjs --questions /tmp/question_set.json --out /tmp/ab_single_source.json --max_tokens 8000 \
 && python3 /tmp/measure_live_cost.py --since 2026-10-25 --out /tmp/live_cost_single_source.json
```

- 前半段：同一批题、同一端点、同一判分规则重跑一遍（`measure_injection_adoption.mjs`，§7.1），产出单源态的采纳对照表；
- 后半段：解析 #13 落地后的新日志，产出单源态的**线上**每轮字符/token/请求数/耗时（`measure_live_cost.py`，§7.2）；
- 两个脚本的完整源码都**内嵌在 §7**，即使 `/tmp` 被清空也能从本文件复原（只需把代码块存成同名文件）。

> `--since` 的日期在真正补跑时改成 #13 落地那天；写死 `2026-10-25` 只是本票交付时的占位。

---

## 6. 结论与限制

### 6.1 可以拿去做决策的五条

1. **现态每轮固定烧掉 ~1 966 字符 / ~1 000 净 token / 4 次 MemOS 请求 / +1.3 s 墙钟**，而且**与问句内容几乎无关**（10 个并跑轮次里 9 轮都是 795+517）。预算被三块各自的硬上限锁死（`budgetChars=800` / `maxChars=500` / `maxChars=600`）。
2. **并跑时 context-inject 的记忆段基本白花**：10 轮里只有 2 轮露出【记忆】条目，因为 `render()` 的 800 字预算被「经验+技能」先吃掉（`context-inject/index.js:277-285`）。也就是它 2 次 MemOS 请求里的**记忆视图那一次**在现态下基本没有产出。
3. **重复集中在技能路**：条目级重复 26.2 %（21/80）、字符级 7.9 %（1 543/19 639）；重复几乎全是「同一个技能在 `【技能】` 和 `<skill_context>` 各出现一次」。两条路都在供同一批 skill（`context-inject` 的 skill 视图 + `wikiskill-inject` 的 kb skill 视图），但**客户端筛选口径不同**——`context-inject` 阈值 `skillThreshold=0.5`（短问句 0.6）取 top5（`context-inject/index.js:33-35,234-243`），`wikiskill-inject` 阈值 `0.4`（短问句取 `max(0.4,0.6)`）取 top6（`wikiskill-inject/index.js:24,208-209`）。长问句上后者阈值更低，取到的集合因此**既重叠又不相同**（11:40:04 那轮 6/8 条重复、11:21:39 与 11:27:55 那轮 0/8）。
4. **采纳是可测的，但不是「全有全无」**：可判分 11 题 90 条注入条目里，A 臂命中 **15 条（16.7 %）**，B 臂 **0 条**，**净采纳 15 条（16.7 %）**；人工复核剔除 5 条通用词误判后是 **12 条（13.3 %）**。分路看：**经验 25.0 % > 技能 22.7 % > 记忆 9.1 %**。
5. **记忆路采纳最低、且现态里最贵**：记忆条目占注入条目的 49 %（44/90），采纳率只有 9.1 %；同时它在现态下还要被另两个插件各供一次（`memos-autoinject` 的 fact+preference 视图、`context-inject` 的 fact+preference 视图）。

### 6.2 限制（必须一起读）

- **采纳 ≠ 正确率**。本笔记只证明「注入里的内容出现在回答里」。回答是否更对、返工是否更少，**没测**（票 #12 才是定阈值的地方）。
- **每臂只跑一次**，n=1；单题方差很大（同一题的 A 臂耗时就从 7.4 s 到 81.6 s 不等）。
- **A 臂没有 system prompt**，与线上真实链路不等价；绝对值会低于线上，差值（A−B）才可比。
- **6 个臂退化（占 5 题）**：MiniMax M3.1-Flash 对部分问句会回 `{"isNewTopic":…,"title":…}` 这种**标题 JSON**（Q01 两臂、Q03/Q05/Q15 的 B 臂），Q12 的 A 臂在 8 000 token 上限处截断且正文为空。这 5 题**不可判**，已从分母剔除；这也意味着**任何在这个端点上的 A/B 都必须加「正文长度」资格检查**。
- **判分是短语命中，不是语义判定**：会漏判「用了意思但没用词」的采纳，也会误判通用词（已人工剔除 5 条，但仍有残余风险）。
- **注入块是离线复现的**：`recallOnce()` 用的是**合成 conversation_id**（`ab-Q01`…），与线上真实 session id 不同，召回结果可能与线上有差异；线上真实块见 §3.2 的会话转录原文。
- **成本数字只覆盖现态**：单源态线上成本**未测到**（等 #13）。

### 6.3 既有 wiki 经验条为什么答不了本票

`~/.dsh/wiki/patterns/injection-single-source-and-server-limit.md` 记的是**根因与做法**：`memory_limit_number` 是候选池不是返回条数（:16-21）、多视图必须拆并行多请求（:30-31）、profile 顶层条目覆盖插件自带补丁导致三插件并跑（:24-26）。这些**本票全部复核成立**。

但它**没有**：① 任何**采纳率**数据；② 每轮**字符/token/请求数/延迟**的实测值；③ **重复内容占比**；④ A/B 对照。全文 44 行里唯一的数字是候选池 `25` 与两组 skill 命中条数（6 条 / 0 条），**与「注入有没有被用上」「值不值」无关**。所以它**不足以回答本票**，只能作为「为什么是现在这个现态」的根因引用。

---

## 7. 附录：可复跑的测量脚本

> 两个脚本本次运行时的副本在 `/tmp/measure_injection_adoption.mjs` 与 `/tmp/measure_live_cost.py`；`/tmp` 会被清理，所以**完整源码内嵌在此**，按代码块存回同名路径即可复跑。

### 7.1 `measure_injection_adoption.mjs`（A/B 采纳）

```js
#!/usr/bin/env node
/**
 * measure_injection_adoption.mjs —— 票 #14「注入的采纳率与成本实测」的可复跑测量脚本
 *
 * 做的事情：
 *  1) 从 context-inject 插件源码里【原样抽出】loadPatterns / bigrams / matchPatterns / render / recallOnce，
 *     不重写、不编造；注入块 = 插件真实 render() 的输出。
 *  2) 记忆/技能来自 MemOS /search/memory，body 与插件 recallOnce 完全一致（插件内联 apiKey 从环境变量取）。
 *  3) A 版 prompt = 注入块 + 问句；B 版 = 裸问句。同一端点（anthropic-messages）、同一模型，各跑一次。
 *  4) 判分：注入条目里「问句中不存在」的显著短语，出现在回答里即判为该条目被采纳。
 *
 * 用法：
 *   export MEMOS_API_KEY=...        # MemOS 令牌（也可留空，脚本会回退读插件配置里的内联值，仅进程内使用）
 *   export MINI_API_KEY=...         # MiniMax 令牌
 *   node /tmp/measure_injection_adoption.mjs --questions /tmp/question_set.json --out /tmp/ab_results.json
 *
 * 依赖：node >= 18（原生 fetch）；密钥一律走环境变量，不落盘。
 */
import fs from 'node:fs';
import path from 'node:path';

const PLUGIN = '/Users/leto/Documents/DSH/plugins/context-inject/index.js';
const args = Object.fromEntries(
  process.argv.slice(2).join(' ').split('--').filter(Boolean)
    .map((s) => s.trim().split(/\s+/)).map(([k, ...v]) => [k, v.join(' ') || true]),
);
const QUESTIONS_FILE = args.questions || '/tmp/question_set.json';
const OUT_FILE = args.out || '/tmp/ab_results.json';
const MINI_BASE = 'https://api.minimax.cn/anthropic';
const MINI_MODEL = 'MiniMax-M3.1-Flash';

/* ---------- 1. 从插件源码原样抽函数 ---------- */
function extractFn(src, name) {
  const re = new RegExp(`(?:async\\s+)?function\\s+${name}\\s*\\(`);
  const m = re.exec(src);
  if (!m) throw new Error(`cannot find function ${name}`);
  let i = src.indexOf('{', m.index);
  let depth = 0;
  for (; i < src.length; i += 1) {
    if (src[i] === '{') depth += 1;
    else if (src[i] === '}') { depth -= 1; if (depth === 0) { i += 1; break; } }
  }
  return src.slice(m.index, i);
}
const pluginSrc = fs.readFileSync(PLUGIN, 'utf8');
const libSrc = [
  "import { readdir, readFile } from 'node:fs/promises';",
  "import path from 'node:path';",
  'let patternsCache = { at: 0, items: [] };',
  extractFn(pluginSrc, 'loadPatterns'),
  extractFn(pluginSrc, 'bigrams'),
  extractFn(pluginSrc, 'matchPatterns'),
  extractFn(pluginSrc, 'render'),
  extractFn(pluginSrc, 'recallOnce'),
  'export { loadPatterns, matchPatterns, render, recallOnce };',
].join('\n');
const LIB = '/tmp/ctx_plugin_lib.mjs';
fs.writeFileSync(LIB, libSrc, 'utf8');
const { loadPatterns, matchPatterns, render, recallOnce } = await import(LIB);

/* ---------- 2. 配置 ---------- */
const cfg = JSON.parse(fs.readFileSync('/tmp/ctx_config.json', 'utf8'));
if (!process.env.MEMOS_API_KEY) {
  // 回退：插件配置文件里内联的令牌（只在进程内用，不写盘、不打印）
  const y = fs.readFileSync('/Users/leto/Documents/DSH/plugins/context-inject/cordis.patch.yml', 'utf8');
  const m = /apiKey:\s*(\S+)/.exec(y);
  if (m) cfg.apiKey = m[1];
}
if (!cfg.apiKey) throw new Error('no MemOS api key available');
const MINI_KEY = process.env.MINI_API_KEY;
if (!MINI_KEY) throw new Error('MINI_API_KEY not in env');

/* ---------- 3. 判分：显著短语 ---------- */
const STOP = new Set(['the', 'and', 'with', 'when', 'user', 'must', 'should', 'from', 'this', 'that',
  'have', 'been', 'will', 'make', 'your', 'into', 'more', 'than', 'then', 'they', 'them', '什么', '怎么',
  '可以', '需要', '这个', '那个', '一个', '我们', '他们', '因为', '所以', '如果', '但是', '已经']);
function normalize(s) {
  return String(s).toLowerCase()
    .replace(/[\*`#>\[\]()（）「」【】·・]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}
/** 从注入条目里抽「显著短语」：显著 = 长度够 + 问句里没有（否则模型本来就会说） */
function salientPhrases(entry, question) {
  const q = normalize(question);
  const out = new Set();
  const cleaned = String(entry).replace(/[\*`#]/g, '').replace(/\s+/g, ' ');
  // ASCII 词（>=5）
  for (const w of cleaned.toLowerCase().match(/[a-z0-9_][a-z0-9_.\-]{4,}/g) ?? []) {
    const t = w.replace(/[.\-]+$/, '');
    if (STOP.has(t) || t.length < 5) continue;
    if (q.includes(t)) continue;
    out.add(t);
  }
  // CJK 片段（按标点切，>=5 字）
  for (const chunk of cleaned.split(/[^一-鿿A-Za-z0-9]+/).filter(Boolean)) {
    const han = chunk.match(/[一-鿿]{5,}/g) ?? [];
    for (const h of han) {
      if (STOP.has(h)) continue;
      if (q.includes(h.toLowerCase())) continue;
      out.add(h);
    }
  }
  // 含数字的标识符（>=5）
  for (const m of cleaned.match(/[A-Za-z_][A-Za-z0-9_\-]{3,}[0-9][A-Za-z0-9_\-]*/g) ?? []) {
    if (q.includes(m.toLowerCase())) continue;
    out.add(m);
  }
  return [...out].slice(0, 8);
}
function adopted(entry, question, answer) {
  const a = normalize(answer);
  const phrases = salientPhrases(entry, question);
  const hit = phrases.find((p) => a.includes(normalize(p)));
  return { adopted: Boolean(hit), hit: hit ?? null, phrases };
}

/* ---------- 4. 模型调用 ---------- */
async function callModel(content, label) {
  const body = {
    model: MINI_MODEL,
    max_tokens: Number(args.max_tokens || 8000),
    messages: [{ role: 'user', content }],
  };
  const t0 = Date.now();
  const res = await fetch(`${MINI_BASE}/v1/messages`, {
    method: 'POST',
    headers: {
      'content-type': 'application/json',
      'anthropic-version': '2023-06-01',
      'x-api-key': MINI_KEY,
    },
    body: JSON.stringify(body),
  });
  const ms = Date.now() - t0;
  const payload = await res.json().catch(() => ({}));
  if (!res.ok) {
    return { ok: false, status: res.status, ms, error: JSON.stringify(payload).slice(0, 300) };
  }
  const text = (payload.content ?? []).filter((b) => b?.type === 'text').map((b) => b.text).join('\n');
  return {
    ok: true, status: res.status, ms, text, stop_reason: payload.stop_reason ?? null,
    usage: payload.usage ?? null,
    inputTokens: payload.usage?.input_tokens ?? null,
    outputTokens: payload.usage?.output_tokens ?? null,
  };
}

/* ---------- 5. 主流程 ---------- */
const questions = JSON.parse(fs.readFileSync(QUESTIONS_FILE, 'utf8'));
const results = [];
for (const q of questions) {
  const query = q.text;
  const t0 = Date.now();
  // 经验：本地匹配（插件真实逻辑）
  const patterns = matchPatterns(await loadPatterns(cfg.patternsDir), query, cfg.maxPatterns);
  // 记忆 + 技能：一次 recallOnce（内部并行发 2 个请求）
  const apiLog = [];
  const recall = await recallOnce(cfg, query, `ab-${q.id}`, undefined, (m) => apiLog.push(m));
  const skills = recall?.skills ?? [];
  const memories = recall?.memories ?? [];
  const injection = render(patterns, skills, memories, cfg.budgetChars);
  const buildMs = Date.now() - t0;

  if (args.dry) {
    console.log('='.repeat(90));
    console.log(`[${q.id}] ${q.source}`);
    console.log(injection || '(无注入)');
    console.log('patterns:', patterns.map((p) => p.title));
    console.log('skills:', skills.map((s) => `${s.name}(${s.score.toFixed(2)})`));
    console.log('memories:', memories.map((m) => `${m.score.toFixed(2)} ${m.text.slice(0, 40)}`));
    console.log('api_log:', apiLog, 'build_ms:', buildMs);
    continue;
  }
  const A = await callModel(injection ? `${injection}\n\n${query}` : query, 'A');
  const B = await callModel(query, 'B');

  const entries = [];
  const push = (route, item) => {
    const r = adopted(item, query, A.text ?? '');
    const rb = adopted(item, query, B.text ?? '');
    entries.push({
      route, item: item.slice(0, 120),
      a_adopted: r.adopted, a_hit: r.hit,
      b_adopted: rb.adopted, b_hit: rb.hit,
      net_adopted: r.adopted && !rb.adopted,
      phrases: r.phrases,
    });
  };
  for (const p of patterns) push('经验', `- ${p.title}：${p.body.slice(0, 70)}`);
  for (const s of skills) push('技能', `- ${s.name}：${s.description.slice(0, 60)}`);
  for (const m of memories) push('记忆', `- ${m.text.slice(0, 70)}`);

  results.push({
    id: q.id, supply: q.supply, source: q.source, text: query,
    injection_chars: injection.length,
    injection_text: injection,
    patterns: patterns.map((p) => p.title),
    skills: skills.map((s) => s.name),
    memories: memories.map((m) => m.text.slice(0, 70)),
    api_log: apiLog,
    build_ms: buildMs,
    A: { ok: A.ok, status: A.status, ms: A.ms, text: A.text, input_tokens: A.inputTokens, output_tokens: A.outputTokens, usage: A.usage, error: A.error },
    B: { ok: B.ok, status: B.status, ms: B.ms, text: B.text, input_tokens: B.inputTokens, output_tokens: B.outputTokens, usage: B.usage, error: B.error },
    entries,
  });
  const na = entries.filter((e) => e.a_adopted).length;
  const nb = entries.filter((e) => e.net_adopted).length;
  console.log(`[${q.id}] ${q.supply} inj=${injection.length}ch A=${A.ms}ms(${A.inputTokens}in) B=${B.ms}ms(${B.inputTokens}in) 条目=${entries.length} 采纳=${na} 净采纳=${nb}`);
  fs.writeFileSync(OUT_FILE, JSON.stringify(results, null, 1), 'utf8');
}
fs.writeFileSync(OUT_FILE, JSON.stringify(results, null, 1), 'utf8');
console.log(`\nwritten ${OUT_FILE} (${results.length} questions)`);
```

### 7.2 `measure_live_cost.py`（线上每轮成本）

```python
#!/usr/bin/env python3
"""measure_live_cost.py —— 现态/单源态每轮注入成本的一键复算（票 #14）

只读：解析三个注入插件的调试日志 + 会话转录里真实注入块的原文，输出每轮
字符数 / token 数 / MemOS 请求次数 / 各段耗时 / 重复条目占比。

用法：
    python3 /tmp/measure_live_cost.py [--since 2026-10-25] [--out /tmp/live_cost.json]

--since 之后的日志行参与统计；单源态（只留 context-inject）落地后，
把 --since 设成 #13 落地的时间点即可得到单源态对照臂。
"""
import argparse, json, pathlib, re, collections, datetime, statistics

LOGS = {
    "context-inject": "/tmp/context-inject.log",
    "memos-autoinject": "/tmp/memos-autoinject.log",
    "wikiskill-inject": "/tmp/wikiskill-inject.log",
}
SESSIONS = pathlib.Path.home() / ".dsh/sessions"


def parse_log(path):
    rows = []
    p = pathlib.Path(path)
    if not p.exists():
        return rows
    for line in p.read_text(errors="replace").splitlines():
        m = re.match(r"^(\S+Z)\s+(.*)$", line)
        if m:
            rows.append((m.group(1), m.group(2)))
    return rows


def round_key(ts):
    """把 ISO 时间戳截到分钟，作为轮次桶。"""
    return ts[:16]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default=None, help="只看该时间点之后的日志行，如 2026-10-25")
    ap.add_argument("--out", default="/tmp/live_cost.json")
    args = ap.parse_args()

    logs = {k: parse_log(v) for k, v in LOGS.items()}
    for k, rows in logs.items():
        if args.since:
            rows = [(t, l) for t, l in rows if t[:10] >= args.since]
        logs[k] = rows

    per_route = {}
    for route, rows in logs.items():
        chars = [(t, int(m.group(1))) for t, l in rows for m in [re.search(r"chars=(\d+)", l)] if m]
        ms = []
        for t, l in rows:
            m = re.search(r"api: ok ms=(\d+)", l) or re.search(r"recall: .* ms=(\d+)", l) \
                or re.search(r"kb: rows=.* ms=(\d+)", l) or re.search(r"rerank: .* ms=(\d+)", l)
            if m:
                ms.append((t, int(m.group(1))))
        per_route[route] = {
            "注入行数": len(chars),
            "字符 min/p50/max": [min(c for _, c in chars), int(statistics.median([c for _, c in chars])), max(c for _, c in chars)] if chars else None,
            "耗时ms min/p50/max": [min(m for _, m in ms), int(statistics.median([m for _, m in ms])), max(m for _, m in ms)] if ms else None,
            "本段是否仍在注入": bool(chars),
        }

    # 同分钟桶 = 同一轮
    buckets = collections.defaultdict(dict)
    for route, rows in logs.items():
        for t, l in rows:
            m = re.search(r"chars=(\d+)", l)
            if m:
                buckets[round_key(t)].setdefault(route, int(m.group(1)))
    rounds = []
    for k in sorted(buckets):
        v = buckets[k]
        rounds.append({"轮次(分钟)": k, "各路字符": v, "合计字符": sum(v.values()), "并发路数": len(v)})
    multi = [r for r in rounds if r["并发路数"] >= 2]

    out = {
        "since": args.since,
        "各路汇总": per_route,
        "轮次数": len(rounds),
        "多路并发轮次数": len(multi),
        "多路并发轮次_每轮合计字符": {
            "min": min((r["合计字符"] for r in multi), default=None),
            "p50": int(statistics.median([r["合计字符"] for r in multi])) if multi else None,
            "max": max((r["合计字符"] for r in multi), default=None),
            "mean": round(statistics.mean([r["合计字符"] for r in multi]), 1) if multi else None,
        },
        "轮次明细": rounds[-40:],
    }
    print(json.dumps(out, ensure_ascii=False, indent=1))
    pathlib.Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(f"\nwritten {args.out}", flush=True)


if __name__ == "__main__":
    main()
```

### 7.3 题集（16 条，含出处）

| 题 | 问句 | 出处（仓库内） |
|---|---|---|
| Q01 | 我的定时任务也丢失了啊 | `workbuddy-archive/sessions/202610021622_定时任务丢失问题排查.md:12` |
| Q02 | 帮我测试下本地的memos数据库和wiki相关MCP或者技能是不是全流程hooks，有没有正常运作 | `workbuddy-archive/sessions/202610021623_测试memos与wiki的MCP hooks流程.md:12` |
| Q03 | 查下云端数据库是不是健康，同时建立或启用相关MCP服务，增加稳定和速度 | `workbuddy-archive/sessions/202610021646_检查云端数据库并启用MCP服务.md:12` |
| Q04 | 我现在的对话，有在使用我的本地记忆和学习 MCP吗？ | `workbuddy-archive/sessions/202610031410_吉华丹 补上预约.md:1893` |
| Q05 | 本地那个 enterprise.db 确认是 0 字节空壳（9 月 26 日被清空了，9-29 排查时也是这个结论） 本地不用了啊，你怎么没有相关的记忆呢？ | `workbuddy-archive/sessions/202610031410_吉华丹 补上预约.md:1298` |
| Q06 | 现在测试并验证下我的本地记忆系统 | `workbuddy-archive/sessions/202610031635_切换到 DeepSeek 并删除本地模型组件.md:12` |
| Q07 | 你能测试下，我现在的记忆系统，到底有没有帮助到workbuddy | `workbuddy-archive/sessions/202610061032_全面修改并落实建议.md:1427` |
| Q08 | 量比 和 委比 什么意思 | `workbuddy-archive/sessions/202610131206_解释量比和委比含义.md:12` |
| Q09 | 猎聘的背调基本流程 | `workbuddy-archive/sessions/202610131249_猎聘背调流程梳理.md:12` |
| Q10 | 推荐 国产替代的半导体设备和英伟达产业链的PCB | `workbuddy-archive/sessions/202610131414_推荐半导体设备与英伟达产业链PCB.md:12` |
| Q11 | 朱晁均 查一下他所有的数据 上个月的薪资 | `workbuddy-archive/sessions/202610141407_查询朱晁均上月薪资数据.md:12` |
| Q12 | 南京林业大学 ⏎ 甘肃农业大学 国内相关的排名或者专业排名 | `workbuddy-archive/sessions/202610121204_查询两所高校国内排名和专业排名.md:12` |
| Q13 | 帮我生成一个智能表格，用日历的形式去选择自己的休息时间，有5个人可以选择 | `workbuddy-archive/sessions/202609261833_确认图片文字修改情况.md:12` |
| Q14 | 你能查到我会议的云录音和见面谈记录吗？ | `workbuddy-archive/sessions/202610071301_按时间顺序填写表格.md:12` |
| Q15 | 花名册指的是 企业微信的通讯录接口啊，你能不能抓到最新的 | `workbuddy-archive/sessions/202610031410_吉华丹 补上预约.md:2241` |
| Q16 | 帮我优化排版，美化布局和颜色，同时确保在一页上 | `workbuddy-archive/sessions/202610071301_按时间顺序填写表格.md:1733` |
