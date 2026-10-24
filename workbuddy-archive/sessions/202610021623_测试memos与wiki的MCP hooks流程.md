# 测试memos与wiki的MCP hooks流程

- 会话 ID：`dc7c6c44-eaf8-4267-ab98-310957545d33`
- 标题：测试memos与wiki的MCP hooks流程
- 工作目录：/Users/leto/WorkBuddy/HR技术中台
- 创建：2026-10-02 16:23　最后活动：2026-10-02 17:15　状态：completed

---

**用户**（2026-10-02 16:23）

<user_query>帮我测试下本地的memos数据库和wiki相关MCP或者技能是不是全流程hooks，有没有正常运作</user_query>

**助手**（2026-10-02 16:23）

我先摸清楚本地环境里 memos/MemOS 数据库、wiki 技能、hooks 各自在哪，再逐段实测。

**助手**（2026-10-02 16:23）

环境已定位到关键组件。继续挖 memos 数据库、MemOS 源码、hooks 配置三块。

**助手**（2026-10-02 16:23）

发现两个疑点：`qoder-hook-port-install` 的软链疑似自指（会断链），`wikiskill-self-evolve` 目录下没有 SKILL.md。继续核实 hooks 与数据库。

**助手**（2026-10-02 16:24）

memos 出现两份注册表（分裂风险）。继续查 MCP 加载清单、MemOS 配置寻址方式与今日日志。

**助手**（2026-10-02 16:24）

MemOS 数据面今日确有活动（Neo4j 检索返回了 HR 记录）。现在确认 MCP 实际加载了哪些 server，以及 hooks 到底有没有落地。

**用户**（2026-10-02 16:25）

<user_query>我已经让memoslocal和wiki 合并了 我记得</user_query>

**助手**（2026-10-02 16:25）

收到——你之前做过 memos-local 与 wiki 的合并。那我把测试重点放在「合并后的链路是否真的通」，直接做端到端实测。先看服务存活 + 合并链路文档。

**助手**（2026-10-02 16:25）

设计文档说全流程靠 `~/.workbuddy/hooks/wikiskill_booster.py` 7 事件 hook 驱动——但我刚才全盘搜没搜到 hooks 目录。这是关键点，直接验。

**助手**（2026-10-02 16:26）

核心矛盾出现了：hook 脚本在 **QwenWork** 的 `~/.qwenworkcn/hooks/`，而 **WorkBuddy 的 `~/.workbuddy/hooks/` 不存在**。但 `/tmp` 状态文件今天仍在写。必须查清是谁在写。

**助手**（2026-10-02 16:27）

架构已经查清。现在做真正的端到端读写实测（MCP 往返 + 清理），并全盘扫技能断链。

**助手**（2026-10-02 16:28）

MCP 工具签名与预期不符（需要真实 schema）。同时发现跨 harness 断链成片。取真实 schema 并查可恢复性。

**助手**（2026-10-02 16:28）

单源桥的设计意图清楚了：QwenWork 软链指向 WorkBuddy 侧单一源，而 10-01 重置把单一源掏空了。现在补齐 MCP 往返实测 + 契约链路实测。

**助手**（2026-10-02 16:29）

端到端实测已完成。最后清理测试写入的记忆，并核实 WorkBuddy 侧 hooks 的可行性。

**助手**（2026-10-02 16:31）

找到安装权威文档了。读一下它确认「本应有什么」，然后出报告。

**助手**（2026-10-02 16:32）

写后读没搜到，这要么是索引延迟要么是写入丢失——必须查实。直接进 Neo4j 取证。

**助手**（2026-10-02 16:32）

HITS: 0，但我用的属性名可能不对——先取真实 schema 再下结论。

**助手**（2026-10-02 16:33）

关键澄清：**写入确实落库了**（Neo4j 最新一条就是测试记忆，id `9378eacb`）。搜不到是因为 mem_reader 把原文改写成了叙述体。现在清理测试数据。

**助手**（2026-10-02 16:33）

`delete_memory` 报成功但节点仍在——查是软删还是删除失效。

**助手**（2026-10-02 16:34）

`delete_memory` 确认是静默空操作（两次返回成功、节点仍 activated）。看看工具链里有没有真正生效的删除子命令。

**助手**（2026-10-02 16:35）

有 `forget` 子命令（带 --yes 保护）。用它走正规路径清理测试数据。

**助手**（2026-10-02 16:35）

命名不匹配：脚本默认 `memos-hr`，但 mcp.json 注册的是 `memos-local`。这本身就是一处集成缺陷。用正确名字重试。

**助手**（2026-10-02 16:37）

实测全部完成，证据链完整。现在出报告。

**助手**（2026-10-02 16:38）

体检做完，全程命令取证。**结论：你记得没错，合并确实做了而且是通的；但「全流程 hooks」只在 QwenWork 成立，WorkBuddy 这边是裸奔的。**

## 状态总览

| 环节 | 状态 |
|---|---|
| memos 数据库（Neo4j+Qdrant） | 正常 · 4003 条，四端口全通 |
| memos-local MCP 主通道 | 正常 · 握手 OK，16 工具 |
| memos_sync 契约链路（recall） | 正常 · 双检索 + rerank 精排 |
| wiki 知识层 memwiki | 正常 · 223 文件，账本 112KB |
| memos↔wiki 合并 | 成立 · 2026-09-25，README 与记忆双向印证 |
| **7 事件 hooks** | **缺失 · 仅 QwenWork 有** |
| 跨 harness 单源桥 | 断裂 · 8 处软链悬空 |

## hooks 归属实锤

7 事件 hook 脚本在 `~/.qwenworkcn/hooks/wikiskill_booster.py`，注册于 **QwenWork 的** settings.json（今日 hook-runs.log 0 错误，Stop inject:2435 正常触发）。而 **`~/.workbuddy/settings.json` 里根本没有 hooks 键，`~/.workbuddy/hooks/` 目录不存在**。所以你在 WorkBuddy 里的每一轮，都没有 W1–W5 收尾、没有轮首双检索校验、没有 prefetch 兜底。

## 三个高危

1. **WorkBuddy 侧 7 事件 hook 完全缺失** —— 如上
2. **MCP `delete_memory` 静默失效** —— 两次返回 "Memory deleted successfully"，但 Neo4j 节点仍是 `status=activated`、`delete_time` 空、总数 4003 纪纹不动。记忆库只能进不能出，这个最伤可信度
3. **跨 harness 单源桥断裂** —— QwenWork 的 `wikiskill-self-evolve` 有 8 处软链指向 WorkBuddy 侧那个已被 10-01 重置掏空的目录

中危还有三处：`memos_sync.py` 默认找 `memos-hr`、mcp.json 注册的是 `memos-local`（名字对不上）；`forget` 反而误打到云端报 40000；`qoder-hook-port-install`（本该是装 hook 的工具）自己软链自指、两处 harness 都是坏的。

## 需要你定夺一件事

测试写入的记忆 1 条没能清掉，三条删除路径全失效（MCP 静默空操作 → 实例名不匹配 → 误走云端）：

- id `9378eacb-a312-4c9b-a13a-8e2c94e5e712`
- 内容「2026年10月2日下午4:28，用户发起了一项链路测试，标记为可删除…」

要么我直接在 Neo4j 删节点（绕过 Qdrant 索引，可能留孤儿向量），要么就留着当本次体检的留痕。你说一声。

修的优先级我建议：先补 WorkBuddy 的 hooks，再修 delete_memory，然后重建单源桥、统一 MCP 命名。要我直接开工的话说一下从哪条起。

**用户**（2026-10-02 16:39）

<user_query>先补 WorkBuddy 的 hooks，再修 delete_memory，然后重建单源桥、统一 MCP 命名</user_query>

**助手**（2026-10-02 16:41）

开工。四件事按顺序来，先建任务清单再逐项实测验证。

**助手**（2026-10-02 16:42）

`memos_sync` 的 `load_credentials` 是云端凭据通道，本地删除根本没有路径——这解释了 forget 的行为。先确认 WorkBuddy hooks schema（Task1 的前置门），同时读 MemOS 删除源码。

**助手**（2026-10-02 16:42）

WorkBuddy 文档站 Hooks 页是 404（之前 200 是 SPA 兜底）。直接到 WorkBuddy 应用本体里找 hooks schema，同时追 `mos_core.delete` 的实现。

**助手**（2026-10-02 16:43）

WorkBuddy 确实支持 hooks（`sheetagent/hooks/hooks.json` + CLI bundle 有 UserPromptSubmit）。取 schema 证据 + 读 delete 实现。

**助手**（2026-10-02 16:44）

hooks schema 已确认（`hooks` → 事件名 → `[{hooks:[{type:"command",command,timeout}]}]`）。继续定位 hooks 配置来源，同时追 text_mem.delete。

**助手**（2026-10-02 16:46）

**delete_memory 根因锁定了**：`TreeTextMemory.delete(memory_ids: list[str])` 收列表，但 `MOS.delete` 传的是**单个字符串** → `for mid in memory_ids` 变成逐字符迭代 → 每个字符都匹配不到节点 → 异常被吞 → 返回成功。精确、可复现。

先按你的顺序做 hooks。读 hook 脚本要改造的部位。

**助手**（2026-10-02 16:47）

根因与改造点都清楚了。先把 WorkBuddy 侧 hooks 装上——脚本要改成 harness 感知（现在混用了两个 harness 的路径，且 STATE_DIR 两侧行会互踩）。

**助手**（2026-10-02 16:47）

改造点共 6 处硬编码 + STATE_DIR 两侧行互踩。写补丁脚本，一次改好两侧。

**助手**（2026-10-02 16:47）

两侧脚本已改好。现在验证 harness 检测正确 + 7 事件功能自测。

**助手**（2026-10-02 16:48）

两侧脚本跑通。现在注册到 WorkBuddy settings.json（保留全部既有配置）。

**助手**（2026-10-02 16:48）

注册完成。跑 7 事件全量复测，逐个验证输出契约。

**助手**（2026-10-02 16:48）

hook 实际是好的——`hook-runs.log` 显示 7 事件全部触发（Stop inject:30009、SessionStart inject:707）。是我测试脚本断言写错了：silent 类事件本就不带 `hookSpecificOutput`。另外 STATE_DIR 名带了前导点，一并修掉。

**助手**（2026-10-02 16:49）

命名空间已修好。测试脚本的 shell 引号在大注入场景下吞了结果——改成纯 Python 测，排除干扰。

**助手**（2026-10-02 16:49）

两侧 **7/7 全通过**。Task 1 完成（活体触发需重启会话才能证实，这点我最后单独标）。

现在修 delete_memory。

**助手**（2026-10-02 16:50）

完整链路清楚了：`delete_node` 的 DETACH DELETE 是对的，问题就在传参。做修复——同时在被调方做 str/list 归一，杜绝这类 bug 复发。

**助手**（2026-10-02 16:51）

写入落库了（总数 4005），但又被 mem_reader 归一化改写、按原文搜不到。按时间戳取最新节点。

**助手**（2026-10-02 16:51）

三个测试记忆都在。现在用修复后的 delete_memory 逐个删除——既验证修复，也清干净我留下的测试数据。

**助手**（2026-10-02 16:52）

三条都报成功。**现在做回读校验**——这是之前假成功的关键分水岭。

**助手**（2026-10-02 16:52）

**delete_memory 修复验证通过**：三条全部真实删除（残留 0），总数 4005→4002，真实数据完好。顺手把上一轮遗留的测试记忆也清掉了。

再验一下反面用例（删除不存在的 id 应当报错而非假成功）。

**助手**（2026-10-02 16:52）

反面用例没过——Cypher 的 `DETACH DELETE` 对不存在的节点也返回成功，我的计数器因此虚高。要么真校验，要么别放假护栏。查 graph store 有没有可用的存在性接口。

**助手**（2026-10-02 16:53）

`delete_node_by_prams` 本身就返回删除条数——比 `delete_node` 更准。运行时确认实际生效的 graph_store 类型和可用方法。

**助手**（2026-10-02 16:53）

过滤条件误伤了自己的输出（stdio-guard 前缀）。重跑。

**助手**（2026-10-02 16:53）

生效的是 `Neo4jGraphDB`，它有 `delete_node_by_prams(...)->int` 返回真实删除数。改用它，正反两面就都准了。

**助手**（2026-10-02 16:54）

**delete_memory 正反两面都通过**：不存在的 id 现在报错 `not found ... nothing was deleted`，真实删除残留 0、计数准确。测试数据已全部清干净（回到 4002）。

Task 2 完成。开始重建单源桥。

**助手**（2026-10-02 16:54）

13 处断链。`qoder-hook-port-install` 的实体已彻底丢失。逐个映射断链目标的现存真实位置。

**助手**（2026-10-02 16:55）

内容全在 `memwiki/`，只是 digest 重组后 wiki↔procedure 子目录对调了。先确认每个目标唯一，再重指软链。

**助手**（2026-10-02 16:56）

映射确认（README.md 走同名相对路径，无歧义）。重指软链，同时再扩范围找那两个缺失实体。

**助手**（2026-10-02 16:56）

7 处已通。剩下 `.skill-metadata.yaml` 可以按同款格式重建，`.zip` 是打包件、真丢了。看下格式。

**助手**（2026-10-02 16:57）

`.skill-metadata.yaml` 是「推荐查询」契约文件，可按技能真实能力重建。取 SKILL.md 的能力描述对齐。

**助手**（2026-10-02 16:57）

YAML 里有个笔误（`en: ||` 应为 `|-`），修正并校验可解析。

**助手**（2026-10-02 16:58）

`wikiskill-self-evolve` 桥**已全部打通（0 断链）**。只剩 `qoder-hook-port-install`（内容彻底丢失）。验证桥的读穿透与单一源真实性。

**用户**（2026-10-02 17:00）

<conversation_history_summary>
## Summary:

1. **Primary Request and Intent:**

   用户共三次发话，意图层层递进：

   - **第 1 次**：「帮我测试下本地的 memos 数据库和 wiki 相关 MCP 或者技能是不是全流程 hooks，有没有正常运作」——要求对本地 memos 数据库、wiki 相关 MCP/技能做全链路 hooks 实测体检，确认是否正常运作。隐含工作纪律：结论要有据可查（查官方文档/实测），不凭记忆下结论。
   - **第 2 次**：「我已经让 memoslocal 和 wiki 合并了 我记得」——补充背景：用户此前已把 memos-local 与 wiki 做过合并，让我围绕「合并后链路是否真的通」做端到端验证。
   - **第 3 次**：「先补 WorkBuddy 的 hooks，再修 delete_memory，然后重建单源桥、统一 MCP 命名」——要求按此顺序执行四项修复。这是当前仍在执行中的指令。

2. **Key Technical Concepts:**

   - **WikiSkill 论文三层架构**（arXiv:2608.27454）：Raw Layer / Wiki Layer / Skills Layer；四组件×7 事件 hook 映射；消融铁律「提议者读 wiki、执行者不读」= 63.7% 最优
   - **7 事件 hooks**：SessionStart / UserPromptSubmit / PreToolUse / PostToolUse / PreCompact / Stop / SessionEnd，驱动 W1–W5 收尾流水线与合同校验
   - **跨 harness 单一源**：`~/.workbuddy`（WorkBuddy）与 `~/.qwenworkcn`（QwenWork）共用技能与 wiki，软链分发
   - **MemOS 记忆栈**：Neo4j Community（bolt:7687，label `Memory`，4003 节点）+ Qdrant(6333) + Ollama(11434) + mem_reader LLM 归一化改写
   - **MCP stdio 协议**：JSON-RPC over stdio，`mcp_serve.py` 有 stdout 的 `_JsonOnlyStream` guard
   - **memos_sync.py 工具链**：15 子命令，`load_credentials()` 走云端凭据通道（与本地 MCP 是两条路）
   - **WorkBuddy hooks schema**：`hooks` 键 → 事件名 → `[{hooks:[{type:"command",command,timeout}],matcher?}]`，配置文件名 `hooks.json`
   - **Cypher DETACH DELETE 语义**：对不存在节点同样返回成功 → 计数虚高

3. **Files and Code Sections:**

   - **`~/.workbuddy/mcp.json`**
     - 注册 `memos-local` server（`/Users/leto/WorkBuddy/MemOS/.venv/bin/python3` + `src/memos/api/mcp_serve.py --transport stdio`，env `HF_HUB_OFFLINE=1`）
     - 命名与 `memos_sync.py` 默认的 `memos-hr` 不一致（Task 4 要修）

   - **`/Users/leto/.qwenworkcn/hooks/wikiskill_booster.py`** 与新建的 **`/Users/leto/.workbuddy/hooks/wikiskill_booster.py`**
     - 7 事件 hook 脚本单一源，原只有 QwenWork 侧有注册
     - 改造点（两侧同步 patch）：
       ```python
       HOOK_DIR = os.path.dirname(os.path.abspath(__file__))
       HARNESS_ROOT = os.path.dirname(HOOK_DIR)                 # ~/.workbuddy 或 ~/.qwenworkcn
       HARNESS_NAME = os.path.basename(HARNESS_ROOT).lstrip('.')   # workbuddy / qwenworkcn
       OTHER_ROOT = (os.path.expanduser('~/.qwenworkcn') if HARNESS_NAME == 'workbuddy'
                     else os.path.expanduser('~/.workbuddy'))
       LOG = os.path.join(HOOK_DIR, 'hook-runs.log')
       STATE_DIR = f'/tmp/wikiskill-hook-state/{HARNESS_NAME}'
       ```
     - 另替换 6 处硬编码：`SKILLS_DIR`、`impact`（本侧 SKILL-IMPACT）、`CROSS_SKILL_IMPACT`（对侧）、技能改动扫描 glob、evals 路径
     - 保留共享单源路径不动：`~/.workbuddy/mcp.json`、`MEMOS_TOOL`、`PY_BIN`、`HEALTH_SCRIPT`

   - **`/Users/leto/.workbuddy/hooks/hooks.json`**（新建）
     - 7 事件注册，命令为 `/Users/leto/.workbuddy/binaries/python/versions/3.13.12/bin/python3 /Users/leto/.workbuddy/hooks/wikiskill_booster.py`，timeout 5–30s

   - **`/Users/leto/.workbuddy/settings.json`**（备份 `settings.json.bak-before-hooks-20261002`）
     - 新增顶层 `hooks` 键，保留原有 `enabledPlugins/sandbox/claw/http.proxy` 等全部配置

   - **`/Users/leto/WorkBuddy/MemOS/src/memos/mem_os/core.py`**（备份 `core.py.bak-before-delete-fix-20261002`）
     - line ~1134 `MOS.delete` 调用点修复：
       ```python
       # 2026-10-02 修复：text_mem.delete 收 list[str]，此前传单个 str 导致逐字符迭代、
       # 删除静默失效（MCP 返回成功但节点仍在）。现传 [memory_id] 并回读校验删除条数。
       deleted = self.mem_cubes[mem_cube_id].text_mem.delete([memory_id])
       if not deleted:
           raise ValueError(
               f"Memory {memory_id} not found in cube {mem_cube_id} — nothing was deleted"
           )
       logger.info(f"MemCube {mem_cube_id} deleted memory {memory_id} (deleted={deleted})")
       ```

   - **`/Users/leto/WorkBuddy/MemOS/src/memos/memories/textual/tree.py`**（备份 `tree.py.bak-before-delete-fix-20261002`）
     - `TreeTextMemory.delete` 重写（原签名 `delete(self, memory_ids: list[str], user_name=None) -> None`）：
       ```python
       def delete(self, memory_ids: list[str] | str, user_name: str | None = None) -> int:
           if not memory_ids:
               return 0
           if isinstance(memory_ids, str):
               memory_ids = [memory_ids]
           ids = [m for m in memory_ids if m]
           if not ids:
               return 0
           deleted = 0
           try:
               deleted = self.graph_store.delete_node_by_prams(memory_ids=ids) or 0
           except Exception as e:
               logger.warning(f"TreeTextMemory.delete_hard: failed to delete {ids}: {e}")
           logger.info(f"TreeTextMemory.delete_hard: requested={len(ids)} deleted={deleted}")
           return int(deleted)
       ```
     - 关键改用 `delete_node_by_prams(memory_ids=...) -> int`（返回真实删除数），而非 `delete_node`（DETACH DELETE 对不存在节点也"成功"）

   - **`/Users/leto/.workbuddy/skills/wikiskill-self-evolve/.skill-metadata.yaml`**（重建）
     - 「推荐查询」契约文件，6 条 examples（round-recall-remember / pitfalls-ledger-scan / stop-distill / skill-impact-audit / profile-memory-edit / tool-memory-capture），YAML 可解析校验通过

   - **`/Users/leto/WorkBuddy/HR技术中台/outputs/memos与wiki全链路hook体检_20261002.md`**（体检报告，已交付）

   - **`/Users/leto/WorkBuddy/HR技术中台/.workbuddy/memory/2026-10-02.md`**（追加 16:30 体检记录）

   - **`/Users/leto/.workbuddy/scripts/memos_sync.py`**
     - `load_credentials(server_name="memos-hr")` 从 `~/.workbuddy/mcp.json` 读云端 api_key；`forget` 走云端 API，本地无删除路径

4. **Errors and fixes:**

   - **MCP 工具入参猜错**：`add_memory(content)`、`search_memories(top_k)` 报 `Unexpected keyword argument`
     - 修复：拉取 `tools/list` 的真实 inputSchema → `add_memory(memory_content, doc_path, messages, cube_id, user_id)`、`search_memories(query, user_id, cube_ids, filter)`
   - **写后按原文搜不到**：`add_memory` 落库成功但 `search_memories` 命中不了标记文本
     - 查实：mem_reader LLM 把原文改写成中文叙述体（Neo4j 直查才找到节点）；非丢数据，是归一化机制
   - **`delete_memory` 静默失效**（两次返回 "Memory deleted successfully" 但节点仍 `status: activated`）
     - 根因：`MOS.delete` 传 str 给收 list 的 `TreeTextMemory.delete` → 逐字符迭代 → 异常被吞
     - 修复见上；二轮发现反面用例仍假成功 → 改用 `delete_node_by_prams` 取真实计数
   - **`memos_sync forget` 两条路都失败**：`--server memos-hr` 报「未找到 MCP 实例」；`--server memos-local` 报 40000 Invalid API Key format（误走云端）
     - 暂未修（Task 4 范围）
   - **7 事件测试 0/7 误判**：我的 shell 断言要求 `hookSpecificOutput.hookEventName` 存在，但 silent 类事件（PreToolUse/PostToolUse/SessionEnd）本就不带该字段
     - 修复：改纯 Python 测试 + 断言 `continue is True`，注入类才校验 hookSpecificOutput → 两侧 7/7
   - **STATE_DIR 命名带前导点**：`os.path.basename('/Users/leto/.workbuddy')` 得 `.workbuddy`
     - 修复：`HARNESS_NAME = os.path.basename(HARNESS_ROOT).lstrip('.')`
   - **Python 过滤误伤自身输出**：`grep -vE "...stdio-guard"` 把自己的 print 也滤掉了（MemOS 的 stdio-guard 会给 stderr 加前缀）
     - 修复：改用 `grep -E "graph_store class|has |sig:"` 正向匹配
   - **Cypher 查询类型错误**：`toString(n[k])` 遇 `StringArray` 报 CypherTypeError；`toString(n.created_at)` 遇 DateTime 报 `not subscriptable`
     - 修复：分别用 `apoc.meta.type` 过滤 / `toString(n.created_at) AS ca`
   - **`.skill-metadata.yaml` YAML 笔误**：`en: ||` 应为 `en: |-`
     - 修复：Edit 修正后 `yaml.safe_load` 校验通过

5. **Problem Solving:**

   **已解决**：
   - 体检结论成立：合并是真的（memwiki README 明载 2026-09-25，记忆库双向印证），数据面全通（四端口 UP、Neo4j 4002 条、MCP 16 工具握手/增/查/读通过、memos_sync recall 带 rerank）
   - hooks 归属实锤：7 事件脚本原只注册在 `~/.qwenworkcn/settings.json`，`~/.workbuddy` 零配置 → 已补齐
   - Task 1 完成：hooks 装进 WorkBuddy，两侧 7/7 事件通过
   - Task 2 完成：delete_memory 正反两面验证通过（不存在 id 报错、真实删除残留 0、计数准确），并顺手清掉上轮遗留测试数据（总数回到 4002）
   - Task 3 完成：`wikiskill-self-evolve` 桥 0 断链（7 处重指 + `.skill-metadata.yaml` 重建 + `.zip` 死指针移除），读穿透验证通过

   **未解决/待办**：
   - Task 4（统一 MCP 命名）**尚未开始**
   - `qoder-hook-port-install` 技能内容彻底丢失（双侧 4 处断链，实体在 `_recovery`/全盘均无），需用户决定是否删除
   - WorkBuddy 侧 hooks **活体触发**需重启会话才能最终证实（已确认 CLI bundle 支持 hooks schema + 7 事件枚举 + 脚本功能正确）
   - 低危遗留：两份 `.memos/memos_users.db` 分裂（1用户1cube vs 2用户2cube）；`created_at` 时区标注错位（本地时间被标 +00:00）

6. **All user messages:**

   - 「帮我测试下本地的memos数据库和wiki相关MCP或者技能是不是全流程hooks，有没有正常运作」
   - 「我已经让memoslocal和wiki 合并了 我记得」
   - 「先补 WorkBuddy 的 hooks，再修 delete_memory，然后重建单源桥、统一 MCP 命名」

7. **Pending Tasks:**

   - **Task #4：统一 MCP server 命名**（`in_progress` 状态待置）——`memos_sync.py` 默认 `--server memos-hr`，mcp.json 注册的是 `memos-local`，导致 `forget` 报「未找到 MCP 实例」或误走云端。需统一命名并同步两侧默认值，实测 for
…（截断，原文 9753 字符）

**用户**（2026-10-02 17:00）

Please continue with the conversation based on the summarized context above. Maintain the same level of detail and helpfulness as before the summarization.

**助手**（2026-10-02 17:03）

命名分裂的波及面比想象大——hooks 里 `refresh_tool_cache` 也按 `memos-hr` 从 mcp.json 取云端 key，取不到就静默 return，工具记忆缓存其实一直没在刷新。先把 MOS.delete 的真实签名摸清，再动手统一。

**助手**（2026-10-02 17:04）

先实测一把 search 返回的原始字段（id 字段名不能猜）：

**助手**（2026-10-02 17:06）

字段摸清了：`id` 就是删除用的 memory_id（uuid），metadata 的键是 `key` 不是 `memory_key`。现在动手统一。先看 forget 的参数定义：

**助手**（2026-10-02 17:06）

云端凭据备份 `mcp-removed-backup.json` 已经不存在了（大概率是 10-01 profile 重置时没的）——这就是 forget 报「未找到 MCP 实例」的直接原因。先找找 key 是否还有存世副本：

**助手**（2026-10-02 17:08）

SessionStart 的 hook 预算只有 15 秒，本地 MemOS 冷启动（含 ML 栈 import）可能超——工具记忆缓存刷新要做成后台落盘。开始改代码。

**① memos_sync.py：命名统一 + load_credentials 硬化**

**助手**（2026-10-02 17:08）

**② forget 打通本地路径（默认本地，--cloud 才走云端）**

**助手**（2026-10-02 17:08）

**③ memos_local_ops.py：补 delete 子命令（真实计数）+ search 输出 id**

**助手**（2026-10-02 17:09）

search 命中字段也要修——实测 `memories` 里是 `TextualMemoryItem` 对象而非 dict，`metadata.key` 也不是 `memory_key`：

**助手**（2026-10-02 17:10）

**④ 工具记忆缓存：云端 key 缺失时回退本地（别让缓存静默空转）**。抽一个两侧共享的刷新脚本：

**助手**（2026-10-02 17:10）

四处改动齐了。开始实测验证——先语法检查，再跑本地 forget 全链路（add → search 拿 id → forget → 回读）：

**助手**（2026-10-02 17:11）

`id` 字段透出成功，标记记忆命中第一。走 memos_sync forget 本地路径删它：

**助手**（2026-10-02 17:11）

正面 1/1 真实删除。反面用例 + 回读校验（T6）一起来：

**助手**（2026-10-02 17:11）

回读 ✅ 残留 0。反面用例刚才没跑到（路径写相对了），补上：

**助手**（2026-10-02 17:12）

反面 ✅ 零假成功。命名纠错三连测（三种历史误用都该给出明确报错，而不是 40000 或「未找到实例」）：

**助手**（2026-10-02 17:12）

三连全过。回归 recall + 工具记忆缓存本地回退实测：

**助手**（2026-10-02 17:12）

缓存 ✅ 5 条落盘。最后验 hook 活体路径（SessionStart → 无 key → 后台刷缓存）。先看 hook 怎么收事件：

**助手**（2026-10-02 17:13）

WorkBuddy 侧 hook 活体 ✅（8 秒缓存落盘）。QwenWork 侧同套代码，补齐验证：

**助手**（2026-10-02 17:13）

两侧全通。清理探针残留，收尾归档：

**助手**（2026-10-02 17:15）

四项修复全部闭环。最后一项「统一 MCP 命名」完成，修复记录已交付。

**命名口径（现行唯一标准）**
- `memos-local` = 本地 stdio MCP，**默认后端**（recall/remember/forget 不带 `--cloud` 都走它）
- `memos-hr` = 云端 API，仅 `--cloud` 时用；历史别名 `memos-local-mcp`/`memos-api-mcp` 一律归一

**修了什么**
1. `load_credentials` 按正式名解析，两类历史误用改为明确报错——误传本地名给云端（原先静默返回 None key → 40000）直接拦下；云端 key 缺失报「凭据缺失」而非误导性的「未找到 MCP 实例」
2. **forget 打通本地路径**：`memos_local_ops.py` 新增 `delete` 子命令（走修复后的真实计数路径），forget 默认本地、`--cloud` 才走云端——原先两条路全断的问题消除
3. search 命中补 `id` 字段（即 forget 用的 memory_id），并纠正字段名（实测关键词在 `metadata.key`，原代码找的 `memory_key` 恒空）

**顺带揪出一个隐藏故障**：hooks 的工具记忆缓存只认云端 key，自 10-01 事故后一直**静默空转**没刷过。现在无 key 时自动后台回退本地 Neo4j 刷新（后台跑是因 SessionStart 预算仅 15 秒）。

**实测全过**：本地 forget 正面 1/1 真删 + 回读残留 0 + 反面零假成功；三种命名误用均给出正确报错；recall 回归正常；两侧 hook 活体验证 8 秒内缓存落盘。

**待你定夺的两件事**
1. 云端 `memos-hr` 的 API key 已随 10-01 事故丢失（全盘无副本），`--cloud` 暂不可用——需要的话得从 MemOS 平台重新取 key
2. `qoder-hook-port-install` 技能实体彻底丢失（双侧断链），是否删除？

---

> 来源：`/Users/leto/.workbuddy/projects/Users-leto-WorkBuddy-HR技术中台/dc7c6c44-eaf8-4267-ab98-310957545d33.jsonl`　含 384 条工具调用（已省略）