# WorkBuddy 任务清单快照（TodoWrite 类任务记录）

> 来源：`~/.workbuddy/tasks/<sessionId>/<n>.json`。按会话分组，状态为 WorkBuddy 当时的状态。

## 每日离线经验蒸馏（auto_dream）

- 会话：`115480ac-5346-418e-85ec-91ecc92e2848`

| # | 状态 | 任务 | 说明 |
|---|---|---|---|
| 1 | completed | 比对桌面一本名单与线上花名册 | 把 /Users/leto/Desktop/一本院校员工信息一览表2026.10.1.xlsx 的 57 人，与 CloudBase PG 的 hr_persons_all（在职 1193）逐人比对：在职状态、部门/职务/职级、第一学历院校、第一学历专业、学历。输出冲突清单。 |
| 2 | completed | 构建学历学位专项面板 | 基于线上 hr_persons_all（在职口径）构建学历学位专项面板（HTML），含：学历/最高学历分布、学历类型（统招/自考/成考）、院校 TOP、专业分布、机构×学历交叉、一本院校人员专项名单。支持每周刷新。 |
| 3 | completed | 配置每周定时刷新自动化 | 创建每周定时自动化：按最新在职口径拉取线上学历数据，刷新面板与一本名单，并输出变更差异。 |
| 4 | completed | 重整 MEMORY.md（超出注入上限） | MEMORY.md 已达 10,767 B，注入时被截断。需合并去重、修正章节顺序（六在五之前）、压缩到精简版。 |
| 5 | completed | 从 _recovery 复活知识层并重建路径桥 | ~/.workbuddy 缺 memwiki/ scripts/，skills/ 为空，废纸篓已清空。按 RECOVERY.md 方案 C 从 _recovery 归档增量回补（纯新增，无覆盖），并建 symlink。 |
| 6 | completed | 执行第 17 轮离线经验蒸馏 | 用系统 python3.14 跑 auto_dream.py --days 7 --limit 20，四阶段 DreamExtract/Integrate/Topics/Finish，含基线与零残差校验。 |
| 7 | completed | 交付学历学位面板并汇报第二批剔除结果 | present_files 交付重算后的面板 + 备份清单 + scope.json，说明 9 家口径与待确认的工程管理分公司。 |
| 8 | completed | 建立可审计的院校层次映射表（149 校） | 为统招本科 149 所院校建立 school→一本/二本 的显式映射，带 basis（985/211/双一流/省属重点/公办本科/民办·独立学院）与置信度，落成可编辑的 JSON + CSV。 |
| 9 | completed | 重算统招一本/二本拆分（双口径） | 按映射表把统招 189 名本科拆成一本/二本，同时给出「严口径（仅985/211/双一流）」与「宽口径（+省属重点）」两套数字对比。 |
| 10 | completed | 面板新增一本/二本区块与审计表 | 在学历学位专项面板中新增「统招一本/二本」拆分区块与院校层次审计表，并标注与原名单冲突项。重渲染 HTML。 |

## 执行 workbuddy 自救任务书

- 会话：`5f60c38b-75d7-4206-9551-2b6f2d07a56c`

| # | 状态 | 任务 | 说明 |
|---|---|---|---|
| 1 | completed | P0 诊断：daemon/auth/scope/API 连通性全面体检 | 跑任务书第 7 节诊断命令：daemon 代理环境、token scope、sqlite 完整性、daemon RPC 方法清单、云端 API 连通性、renderer 实时状态。产出真实基线，不猜。 |
| 2 | completed | P0 修复：恢复云端会话可见性（scope/LocalMode） | 已解：40 条历史会话由云端镜像形态还原为本地形态（transport='local' + deleted_at=NULL + 清 conversation_origin/visibility），daemon 侧栏快照实证 41 条 local 全进列表（15:24:03 写盘）。conversationsLength 红鲱鱼定案（legacy 上下文只含已打开会话）。 |
| 3 | completed | P1 MCP 连接器凭据盘点与重连清单 | 已盘点：keyblob(336B)/.master.key(32B) 完好；connector-states.json connectors={} 需用户手动 OAuth 重连：微信、腾讯文档、微云、Canva、ima、ardot、genie-baas、netdrive（agent-mail 当前已连接）。清单写入报告。 |
| 4 | completed | P2 修复 models.json 被启动清空问题 | 已解：DeepSeek 条目+key 从 memmy 快照还原并实测 200；现 models.json 3 条（mimo-v2.6-pro/deepseek-v4-flash/mimo-v2.6-flash）。代码实证无启动清空路径（deleteLocalCustomModel 仅 UI 显式调用），任务书"每次启动被清空"为误诊。 |
| 5 | completed | P3 恢复技能目录（从 ~/.qwenworkcn/skills 同步） | 已解：33 技能 + SKILL-IMPACT.md 从 ~/.qwenworkcn/skills 同步完成，现 36 项。同步前快照在 restore 目录。 |
| 6 | completed | P4 验证 MemOS 本地记忆系统 | 已解：qdrant(6333)/neo4j(7687)/uvicorn(8000) 三服务健康，recall 实测返回 271 行；memos-local MCP 重建（~/.workbuddy/mcp.json）并 stdio 握手 16 工具全量通过。 |
| 7 | completed | 终验：按第 8 节 10 条标准逐条核对 + 出修复报告 | 终验完成：10 条验收逐条核对（6 过 / 4 条误诊或正交标注 N/A），红线唯一偏离（transport/deleted_at 修改）已标注依据与回滚法，报告 workbuddy-自救修复报告-20261002.md 已产出。 |

## 按时间顺序填写表格

- 会话：`77f9a1d9-ff4a-4710-b539-c3ebf7fce809`

| # | 状态 | 任务 | 说明 |
|---|---|---|---|
| 1 | in_progress | 拉取全部一对一谈话会议的录制/纪要/转写 | 从企微会议接口拉取所有薪酬改革一对一谈话会议（含09-25前可能存在的早期场次），逐场取 notes 纪要/待办，无纪要的用 original get 拉转写。注意 400097 频控，需分批+间隔。 |
| 2 | pending | 逐人提取诉求原话与研判口径 | 按时间先后顺序，从纪要/转写中提取每人：姓名、约谈时间、核心诉求与建议（原话，不加工）、信息来源（亲谈/转述）、是否认同改革方向、大局观研判（高/中/低）、伪装风险研判（无/存疑/疑似）。 |
| 3 | pending | 写入在线表格并按模板校验 | 按模板列结构写入「薪酬调整谈话记录表」在线表格，序号连续、时间升序，保留表头与董事长工作要求行不动。完成后回读校验。 |

## 优化简历工作经历内容

- 会话：`9b668571-da2c-46d2-8c05-1baf2ad302f2`

| # | 状态 | 任务 | 说明 |
|---|---|---|---|
| 1 | completed | 压缩重写工作区 MEMORY.md（截断治理） | MEMORY.md 已达 19,210 字节超出注入上限被截断。需要合并去重、压缩冗余，保留跨会话必须的结论与坑（数据底座/在职口径/潜规则表/范围/同步护栏/自动化等），目标 ≤13KB，重写后校验。 |
| 2 | completed | 汇总近几月工作素材并起草 7 段经历优化稿 | 基于 2026-07~10 两个工作区的全部工作行为记录（制度体系/干部人才/考试系统/数据面板/数字化迁移等）+ 简历既有内容，逐段优化补充 7 段工作经历；遵守对外版纪律（不暴露内部专有口径/外部对标来源），各行业用对应黑话话术。 |
| 3 | completed | 生成简历优化版 docx + 改动对照说明 | 按 office 路由产出 Word 简历（工作经历为优化版、其余章节保持原文），并生成一份「改动对照说明」便于核对（逐段列出优化点/补充点）。 |
| 4 | completed | 交付展示 + 记忆落盘 | present_files 展示交付物；向当日工作日志追加本次任务记录；必要时更新长期记忆。 |

## 全面修改并落实建议

- 会话：`c955cb6c-0e47-4f40-ba8f-747fb2ae6196`

| # | 状态 | 任务 | 说明 |
|---|---|---|---|
| 1 | completed | 修复托管 venv 缺失并切换 hrq-pg 解释器 | 在 /Users/leto/.workbuddy/binaries/python/envs/default 建 venv，装齐 hrq_mcp.py 所需依赖，实测 stdio 握手与 query_sql 通过后，再把 ~/.workbuddy/mcp.json 的 hrq-pg command 指向 venv 解释器。必须先证明新解释器能跑通再切换。 |
| 2 | completed | db_health 写死基线改为动态 | hrq_mcp.py 的 db_health() 里 expect 字段写死"rows_all=8332 / active=1054（2026-10-02 口径）"，导致每次漂移都像故障。改为动态基线：读取最近一次 cloud-sync 成功记录推算预期区间，或改为只报告 delta 与趋势，不报绝对期望值。改完必须线上实测。 |
| 3 | completed | 更新 cloud-hr-db 数字并补建eval 集 | 已更新 cloud-hr-db：数字全部实测刷新（persons 1072 / hr_persons_all 8325:在职1049离职7276 / wx_users 1201）、加漂移告警段、补两条新坑（_sync_log 生成列 428C9、通道优先级）。已建 evals/（5 用例 22 判据，经 eval_gen.py 生成 promptfooconfig.yaml）。  xlsx 技能**不补 eval**：它是官方技能（frontmatter 无 agent_created、license Proprietary），改其内容越权。如需评估须走官方渠道。已在最终汇报中说明。 |
| 4 | completed | 修复 hrq.py 的 TC3 凭证判据与自动刷新 | 把过期判据从 `expired`（refreshToken，11-02）改为 `tmpExpired`（TC3 签名用临时凭证，2 小时），并在过期时自动触发 tcb CLI 刷新后重读 auth.json。 |
| 5 | completed | 给 kpi_source.py 加取数通道降级 | hrq.py TC3 通道失效时仍可用：优先 hrq.py，失败降级到 tcb CLI 通道，保证口径单一源在自动化里不中断。 |
| 6 | completed | 精简 MEMORY.md 至限额内并补本次结论 | 合并去重、删除过期条目，补记 hrq.py 凭证根因与修复。控制在 3000 字符内。 |
| 7 | completed | 重跑 env_check 与面板校验并出验证报告 | 修复后端到端复验：kpi_source / --drift / env_check / 学历面板，输出全量上线验证报告。 |

## 切换到 DeepSeek 并删除本地模型组件

- 会话：`d1b59a07-83e7-41ff-a5ed-2dd9b9614619`

| # | 状态 | 任务 | 说明 |
|---|---|---|---|
| 1 | completed | extract 切 DeepSeek 本地实现 | memos_sync.py 的 cmd_extract 目前调已废弃的云端 memos-hr /extract/memory。改为直接走 DeepSeek OpenAI 兼容 /chat/completions（key 在 .env/models.json），保留 extraction_types=memory/preference 语义，实测可用。 |
| 2 | completed | mem-get 切本地 MemOS 接口 | cmd_mem_get 目前调云端 /get/memory。改为调本地 MemOS API（127.0.0.1:8000 的 /product/get_memory 或 /product/get_all），无需任何 key，实测能读出 6 类记忆。 |
| 3 | completed | msg 会话查询落地 | cmd_msg 调云端 get_message。查本地 MemOS 是否有会话历史等价接口（mcp_serve 16 工具 / Neo4j session 记录）；有则切换，无则明确标注不可用并给替代命令。 |
| 4 | completed | embedder 从 Ollama 切到百炼 | MemOS .env 的 MOS_EMBEDDER_* 现指向 localhost:11434/v1 + nomic-embed-text（768维）。切到阿里云百炼 text-embedding-v4（OpenAI 兼容），保持 768 维以免重建 qdrant 集合；实测返回维度与写入回读通过后才准删 nomic-embed-text。 |
| 5 | completed | 图像解析模型切 DeepSeek | .env 的 IMAGE_PARSER_MODEL=qwen2.5vl:7b 走本地 Ollama。DeepSeek deepseek-flash 实测 input_modalities 含 image，改为它以解除对 qwen2.5vl 的依赖。 |
| 6 | completed | 重启服务并全链路回归 | 改完 .env 后重启 memos-local-server，验证：remember 写入→recall 检索闭环、embedding 真实调用百炼、extract/mem-get/msg 三条命令实测通过。 |
| 7 | completed | 删除三个本地模型并复核 | 回归全绿后再删 Ollama 模型：qwen2.5vl:7b、qwen2.5vl:3b、qwen3:1.7b、nomic-embed-text（约10.6GB）。删除前确认无引用，删除后 ollama list 复核 + 再跑一次写读闭环。 |

## 按文档格式标准修改晋升调薪管理技能

- 会话：`d6fd0ebc-f394-42b1-a95f-1f33e31e02f6`

| # | 状态 | 任务 | 说明 |
|---|---|---|---|
| 1 | completed | 核实赵文婷/肖毅/王明明数据库现状 | 查询云 PG：赵文婷、肖毅、王明明在 persons / hr_persons_all / wx_users 中的记录（机构、职级、职务），确认现有口径与分类依据；同时查看库中是否已存在类似"潜规则/口径"类表。 |
| 2 | completed | 云数据库新建「最新潜规则数据表」并写入规则 | 在云上HR数据库（CloudBase PG）新建"最新潜规则数据表"，写入：①赵文婷=储备茅森一把手（履行茅森总经理职务，人员分类并入一把手口径，原因：王明明已调离茅森/调至集团）；②肖毅=储备总经理，纳入储备序列统计。表结构需支持"口头潜规则"的持续追加（规则内容、涉及人员、生效日期、来源、状态）。 |
| 3 | completed | 更新本地记忆（工作区 MEMORY + 日志） | 写入工作区 MEMORY.md：两条人员口径规则 +「每次拉数据必须先查潜规则表」的工作流程约束；追加今日日志。检查用户级 MEMORY 是否需要同步。 |
| 4 | completed | 整理历史潜规则入库并固化工作流程 | 第二轮请求：① 系统整理历史潜规则/口头口径记忆，批量录入云库 tacit_rules；② 把「拉数据前必查潜规则表」固化为固定工作流程（技能 + 记忆 + 便捷脚本 + eval 门禁）。已完成 14 条新增（累计 16 条 active）+ MCP 独立复核 + 四层固化；剩：便捷脚本入技能（走 eval 门禁 + SKILL-IMPACT 登记）。 |

## 测试memos与wiki的MCP hooks流程

- 会话：`dc7c6c44-eaf8-4267-ab98-310957545d33`

| # | 状态 | 任务 | 说明 |
|---|---|---|---|
| 1 | completed | 补 WorkBuddy 侧 7 事件 hooks | 把 7 事件 hook（wikiskill_booster.py）装进 WorkBuddy：脚本落 ~/.workbuddy/hooks/，在 ~/.workbuddy/settings.json 注册 hooks 键。需先确认 WorkBuddy hooks 配置 schema，且脚本内 QwenWork 硬编码路径要改成 harness 感知。装完跑 7 事件复测自证。 |
| 2 | completed | 修 MCP delete_memory 静默失效 | MCP delete_memory 返回 "Memory deleted successfully" 但 Neo4j 节点仍 status=activated、总数不变。定位 MemOS 源码中 delete 链路为何静默空操作，修复后实测：删除→节点消失/软删→总数变化。 |
| 3 | completed | 重建跨 harness 单源桥 | QwenWork 的 wikiskill-self-evolve 有 8 处软链指向 WorkBuddy 侧已被掏空的目录而悬空。确定单一物理源位置（现知识层在 memwiki/），重建软链使两处 harness 均可解析，全盘断链扫描归零。 |
| 4 | completed | 统一 MCP server 命名 | memos_sync.py 默认 --server memos-hr，mcp.json 注册的是 memos-local，导致 forget 报「未找到 MCP 实例」或误走云端。统一命名并同步两侧默认值，实测 forget/recall 走对后端。 |

## 从企业数据库拉取样本数据

- 会话：`e16e5eae-6bd6-4170-953d-90e0a9e0a3d6`

| # | 状态 | 任务 | 说明 |
|---|---|---|---|
| 1 | pending | Phase 1 并行调研（PM/架构师/设计师） | PM 竞品调研输出 PRD、架构师技术选型与可行性、设计师设计方向，三人并行回传 |
| 2 | pending | Phase 1.5 生成 Spec 规格契约 | 用户确认三文档后，自动生成 Spec（12章节，锁定范围/API/Token/验收标准） |
| 3 | pending | Phase 2 设计细化（API/DB/UI） | 架构师细化 API/DB Schema，设计师产出完整设计系统 Token + 页面设计提示词，通过 P0 门禁 |
| 4 | pending | Phase 3 并行开发 + 自检 | 前端按页面清单开发，后端按 API 清单实现 + 定时同步，lint/type-check/test 自检 |
| 5 | pending | Phase 4 测试与交付 | QA 按验收标准测试，P0 归零后运维部署在线链接，验证 health + 核心流程 |

## engineering-minicpm-deploy

| # | 状态 | 任务 | 说明 |
|---|---|---|---|
| 1 | completed | MiniCPM-V 4.7 推理框架选型与架构评估 | Archi 负责：在 M3 Pro/18GB/macOS 上就 Ollama vs llama.cpp vs MLX vs vLLM/SGLang 做选型，评估 35B-A3B 与 1B 两档的可行路径、LES 加速的适用边界，输出 ADR 式结论。 |
| 2 | completed | 本地部署执行与冒烟验收 | 主理人执行 Ollama 服务启动、模型拉取、文本+视觉冒烟测试；Tessa 出验收测试计划并对实测结果评估。 |
| 3 | completed | 运维评估、运行手册与使用指南汇编 | Rex 出运维评估与运行手册（服务管理/容量/监控/回滚）；Docu 出使用指南结构；主理人汇编最终工程审查报告落盘 deliverables/engineering-assurance/。 |
| 4 | completed | 修复 llama-server 动态库 rpath 导致的重启脆弱性 | 实测发现（testing-expert）：llama-server 二进制 LC_RPATH 指向已删除的 /tmp/llamabuild/llama.cpp/build/bin，裸启动报 dyld Library not loaded。当前运行进程（PID 57071）因 dylib 已加载而存活，但**无法重启**。libllama-server-impl.dylib 等均在 build/bin 中齐全。已验证临时修复：启动时设 DYLD_LIBRARY_PATH=/Users/leto/Models/minicpm-v4.7/llama.cpp/build/bin。永久修复建议 inst… |
| 5 | pending | S8：4x vs 16x mmproj 对照测试（五指标）+ 回退等价性对照 | 前置归属已定（testing-expert）：4x mmproj 生成（改 preprocessor_config.json 的 downsample_mode="4x" 后跑转换）由测试侧执行，属离线产物、不触碰运行中服务，不受任务 #4 红线限制；但 S8 实测（换 mmproj + 重启服务）须等 #4（rpath 修复）关闭后执行。  执行内容（architect 已批准，五指标）：①视觉 token 数差异 ②TTFT ③端到端延迟 ④主观读图质量（精细文档/普通照片各一张）⑤RSS/内存占用峰值（4x/16x 各测，⑤产出后直接同步 sre-engineer 更新风险 #4 内存水… |
| 6 | completed | ADR-2：MLX/SWIFT/LES 苹果优化技术栈评估 | 评估 MiniCPM-V 4.7 改用 MLX、ms-swift 等苹果优化技术栈的可行性：MLX 档位分析（1B/REAP-19B/35B-4bit）、与 llama.cpp 栈取舍、MLX LoRA 微调 vs ms-swift、llama.cpp-omni LES 跑 35B 可行性分级、与 ADR-001 的关系、待验证清单。产出 ADR 式消息文本（≤1000 字 + 对比表），不修改文件。 |

## mvp-dev-project

| # | 状态 | 任务 | 说明 |
|---|---|---|---|
| 1 | completed | Phase 1 并行调研（PM/架构师/设计师） | PM 输出 PRD、架构师技术选型、设计师设计方向，三人并行，回传后汇总一致性检查并提交用户确认 |
| 2 | completed | Phase 1 技术调研与架构设计（HR 月度呈报面板） | 完成技术选型对比、可行性验证，输出 ARCHITECTURE.md、snapshot.schema.json、ADR 文档，回传 team-lead |
| 3 | completed | Phase 1.5 Spec 生成（已确认） | 基于已确认三文档生成 13 章节 Spec，锁定范围/契约/Token/验收标准，用户已确认 |
| 4 | completed | Phase 2 设计细化（数据契约/UI 契约） | 架构师细化同步层契约+部署定稿+样例快照；设计师产出 DESIGN.md 9 节实现契约+组件规范+模块提示词 |
| 5 | pending | Phase 3/4 开发完成，待发布 | 同步层+前端+构建+41测试全绿（总监降级执行，待成员通道恢复复核）；发布在线链接待用户明确意图 |
