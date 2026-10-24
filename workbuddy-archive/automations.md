# WorkBuddy 定时自动化任务（DSH 无对应调度器，按需手动执行）

> 来源：`~/.workbuddy/workbuddy.db` → `automations` 表（4 条）。
> 用法：把 prompt 原样交给 DSH agent 执行即可；rrule 是 WorkBuddy 的调度规则，DSH 不会自动触发。

## 每日离线经验蒸馏（auto_dream）

- 状态：ACTIVE　类型：recurring　rrule：`FREQ=DAILY;BYHOUR=20;BYMINUTE=0`
- 上次运行：—　下次运行（WorkBuddy 侧）：2026-10-14 20:00
- ID：`7310bbec-376b-4386-b2c7-3b6599781400`

### Prompt
```text
把工作区日志升维成 digest/ 下的可复用知识节点。执行前先读技能 auto-dream-maintenance（细节全在技能内，含失败轮判定与伪检查点回滚）。

环境（2026-10-06 起 Memmy 已卸载，旧指令已作废）：
- export OPENAI_API_KEY="$(cat ~/.workbuddy/secrets/deepseek_api_key)"（实测有效；~/.zshrc 里的 DEEPSEEK_API_KEY/FXBAOGAO_API_KEY 均 401，不要用）
- export OPENAI_BASE_URL="https://api.deepseek.com/v1"（脚本不读，惯例 export）
- unset HTTP_PROXY HTTPS_PROXY http_proxy https_proxy ALL_PROXY all_proxy；export NO_PROXY='*' no_proxy='*'（不探测代理端口，直接 unset）
- 解释器：/Users/leto/.workbuddy/binaries/python/versions/3.13.12/bin/python3
- 命令：python3 ~/.workbuddy/scripts/auto_dream.py --days 7 --limit 20

验收：跑前 --stats 取基线，跑后 --stats 相减，ΣΔwrites 必须 == Σops − SKIP 数（H1 自 09-27 起恒为 1，不能当计数器）。异常先查并发双跑，不要直接判定写入语义坏了。经验续写旧 id 目录（稳定路径），勿新建目录。
```

## 技能健康度每周日回顾

- 状态：ACTIVE　类型：recurring　rrule：`FREQ=WEEKLY;BYDAY=SU;BYHOUR=8;BYMINUTE=0`
- 上次运行：—　下次运行（WorkBuddy 侧）：2026-10-18 08:00
- ID：`5ff240a1-8878-4817-8258-455e60899750`

### Prompt
```text
执行「技能健康度每周回顾」例行体检。工作目录 /Users/leto/WorkBuddy/HR技术中台。逐轮执行记录续写于稳定路径 /Users/leto/WorkBuddy/HR技术中台/.workbuddy/memory/automations/33b607f0-088b-4bb6-9b34-7d9b554370e5/memory.md（勿另起新文件）。

流程（六步）：
1. recall 双检索：本地记忆 + memos 记忆，检索近 7 天技能使用与改动情况（LOG_DIRS 双目录：~/WorkBuddy/HR/.workbuddy/memory 与 ~/WorkBuddy/HR技术中台/.workbuddy/memory 都扫，旧区历史仍有效）。
2. 体检：`/Users/leto/.workbuddy/binaries/python/versions/3.13.12/bin/python3 ~/.workbuddy/scripts/skill_health_scan.py`（不存在则退 /opt/homebrew/bin/python3）。输出各技能触发次数、SKILL.md 体积；红旗 = >15KB，另报距 15KB 门限 <1KB 的预警名单。
3. eval 回归（每技能抽样 3 条）：eval 样本在 ~/.workbuddy/memwiki/evals/ 与各技能 evals/。核对上一期「下一期执行注意」里的判据是否兑现（例如 WS-09 r2 审计留痕覆盖全部技能改动、高频无 eval 集名单清空），未兑现的写清原因。
4. 报告：TOP3 高频技能、红旗清单、eval 回归通过率与失效项、上期遗留项收口情况。
5. 落盘：报告全文追加到 /Users/leto/WorkBuddy/HR技术中台/.workbuddy/memory/$(date +%Y-%m-%d).md（中台区日志。不要写旧区 /Users/leto/WorkBuddy/HR/ —— 旧区已停止增长，写旧区会制造跨区副本）。
6. remember：本轮结论记入长期记忆。本地通道回执以「✅ 本地落盘成功」为准（无 task_id 字段）；云端只读不写（用户规则）。

纪律：不改任何 SKILL.md / 脚本本体；发现的修复项列入「下一期执行注意」由用户裁决；无人值守不调 AskUserQuestion；输出简洁不写「数据来源/口径说明」类尾巴。本轮记录（窗口、TOP3、红旗、eval 结果、remember 回执、下期注意）追加到上述稳定路径 memory.md。
```

## WikiSkill L3 周度记忆蒸馏

- 状态：ACTIVE　类型：recurring　rrule：`FREQ=WEEKLY;BYDAY=MO;BYHOUR=8;BYMINUTE=0`
- 上次运行：—　下次运行（WorkBuddy 侧）：2026-10-19 08:00
- ID：`010f9edd-f50a-4496-a425-2bdc86652534`

### Prompt
```text
把工作区日志蒸馏为 L3 wiki 层可复用知识节点。执行前先读技能 auto-dream-maintenance。

环境（2026-06 起 Memmy 已卸载，旧指令已作废）：
- export OPENAI_API_KEY="$(cat ~/.workbuddy/secrets/deepseek_api_key)"（实测有效；~/.zshrc 里的 DEEPSEEK_API_KEY/FXBAOGAO_API_KEY 均 401，不要用）
- export OPENAI_BASE_URL="https://api.deepseek.com/v1"
- unset HTTP_PROXY HTTPS_PROXY http_proxy https_proxy ALL_PROXY all_proxy；export NO_PROXY='*' no_proxy='*'
- 解释器：/Users/leto/.workbuddy/binaries/python/versions/3.13.12/bin/python3

账本=现行版 pitfalls-ledger（~/.workbuddy/memwiki/references/）。每轮：识别新增失败/踩坑 → 按稳定签名去重（剥路径行号版本号）→ 追加落账（禁整篇重写）→ 回读校验。产出落 memwiki/references/digest/。
```

## 学历学位专项面板 · 每周刷新

- 状态：ACTIVE　类型：recurring　rrule：`FREQ=WEEKLY;BYDAY=MO;BYHOUR=9;BYMINUTE=0`
- 上次运行：—　下次运行（WorkBuddy 侧）：2026-10-19 09:00
- ID：`1d87cc2a-d337-480f-8049-bf8f8529df73`

### Prompt
```text
刷新「学历学位专项面板」：线上取数 → 重算数据快照 → 重渲染单文件 HTML。工作目录 /Users/leto/WorkBuddy/HR技术中台。产物：data/edu_panel/edu_data_<今日YYYY-MM-DD>.json + data/edu_panel/学历学位专项面板.html（scripts/edu_panel_render.py 纯标准库渲染，品牌深绿 #1E5A44 / 米白 #F6F3EA）。

一、取数（只读）
- 数据底座 = CloudBase PostgreSQL（env uu-one-d4gc4ot78a702cb70，public schema），用 CloudBase 连接器 queryPgDatabase 只读 SQL（action=sql）。连接器不可用时如实报告并中止，不要造数。
- ⚠️ queryPgDatabase 单次返回上限 200 行、超限静默截断 → 一律用聚合或分页取全，被截断会得出错误结论且不报错。
- hr_persons_all 等表列名 camelCase，SQL 里必须加双引号（"degreeName"）；姓名键是 trueName（name 恒 null）；在职 = state=0。

二、业务范围（管辖口径，权威清单 config/scope.json）
- 9 家剔除：景尚建设、景尚科技、景尚控股、春秋航服、常州春秋国旅、杭州旅行社、淹城、云顶置业、规划设计院。唯一特意保留：工程管理分公司（待用户裁定，勿自行剔除）。
- 只按公司级列精确值匹配（companyName/companyShortName/addCompanyName/topUnitName/orgName），禁止对 unitName/addUserOrgPath 做包含匹配 —— 研创院下属「淹城设计组」是业务目标必须保留；近似主体（规划设计院 vs 研创院）先做反向断言再动。
- 数量基线（2026-10-02）：hr_persons_all 8332 / 在职 1054 / 在职机构 19 家 / companies 48。本期允许漂移，但要报出与基线的差。

三、★★★ 严格统一维度（最高优先级）
统招本科档只按 985 / 211 / 一本 / 二本 四档互斥统计。四前提缺一不可：在职 state=0 + 管辖口径内 + "educationTypeName"='统招' + 第一学历 "degreeName"='本科'。每期先自证四前提（含 189 人机构分布复核：应无任何被剔 9 家），再出数。
- 标签只允许七个值：985 / 211 / 一本 / 二本 / 待裁定 / 海外 / 异常。
- 校验式：四档 + 待裁定 + 海外 + 异常 = 本科档总数（基线 2+10+38+110+21+2+6 = 189）。四档基线：985=2、211=10、一本=38、二本=110；待裁定=21（省属重点·存疑，挂起不进四档）；海外=2；异常=6。
- 一本 = 双一流(非211) + 省属重点(稳妥)；二本 = 公办二本 + 独立学院 + 民办本科（基线 独立学院 40 / 民办 28 / 公办二本 42）；「双一流 / 省属重点 / 独立学院」只能进依据列，不得当维度。
- 硕士单独立档、不进四档（基线 3 人：崔婵/田丹/汪洋）；其他层次（大专/中专/高中/初中/其他）基线 801；校验式 189 + 3 + 801 = 统招总数（基线 993）。
- 特例孙晓东：第一学历大专（常州技术师范学院）、最高学历硕士（上海交大）→ 按第一学历归「其他层次」，不得擅自算进硕士档，单列「特例 · 第一学历非本科但有硕士学历」表待裁定。

四、★ 院校层次流水线（a 取数 → b 映射 → c 合并 → d 三口径）
- a：取统招+第一学历本科的院校与人数（基线 189 人 / 143 校，归并同校异名后 149→143）。
- b：映射用 scripts/build_school_tier_map.py 生成/刷新 data/edu_panel/school_tier_map.json + .csv（--check 只校对不写盘；改口径只改脚本顶部白名单集合后重跑）。
- 硬约束：只能用显式白名单映射表；新增未收录院校必须逐条列出供人工裁定，不得凭院校名臆造层次。新增未收录院校默认落「公办本科 conf=low」进 review，逐条列出、不得静默归类。
- 独立学院铁律：「XX 大学 XX 学院」= 独立学院 = 二本，绝不继承母体 985/211/一本身份；民办本科同理；非统招不进四档。母体为 985/211 的 11 所（东南大学成贤学院、同济大学浙江学院、浙江大学宁波理工学院、南京师范大学泰州学院、南京师范大学中北学院、苏州大学文正学院、苏州大学应用技术学院、云南大学旅游文化学院、南京理工大学紫金学院、南昌大学共青学院、南航金城学院）产出须标 parent + parent_tag，并写明「母体是 985/211 ≠ 本人是 985/211」。
- 同校异名按 NORMALIZE 归并（原校名进 aliases，勿拆两行）；OVERSEA 不得含中国院校（曾误收「国立华侨大学」，已修）。
- 脏值/异常 6 条单列不计层次：graduateSchool='1'、浙江龙井大学、国家开放大学、山西建筑职业技术学院、江苏农物科技职业学院、安徽科技工程大学。

五、名册对齐（参考件，只分析不写回）
- 源：~/Desktop/一本院校员工信息一览表2026.10.1.xlsx（57 人）。用户未授权改桌面文件，只提示不修改。
- 修正基线 10 行：朱正彦/张正猛 211→二本；刘宇航、卢国庆、罗蝴蝶、杨绍会、袁石磊、王珏、王艳、杨潇 一本→待裁定。修正行标 fix|<说明>（绿色「已修正」标签）。已知源侧待修：Sheet1 第 26 行朱正彦「苏州大学」应为「苏州大学文正学院」——只提示。
- 名册基线：985×2 / 211×10 / 一本×35 / 待裁定×8 / 二本×2 = 57。

六、渲染与校验
- 渲染：$PY scripts/edu_panel_render.py（PY=/Users/leto/.workbuddy/binaries/python/versions/3.13.12/bin/python3，不存在退 /opt/homebrew/bin/python3）。
- edu_data 必需键：school_tier、dim_split、degree_trio（base_label/base_total/buckets/remainder + master_n/other_n）、master_detail、master_special、conflicts、roster、kpi（含 dim_985/dim_211/dim_yiben/dim_erben/dim_pending/dim_single/dim_tier4/tongzhao_shuoshi/tongzhao_benke_shang 等）。缺 school_tier 键渲染器会降级成提示文案 —— 必须灌数，别留空壳。
- 渲染后把 KPI 与 SQL 重算对账，不一致以 SQL 为准修 JSON 后重渲染。

七、汇报
结论先行：本期 KPI（在职/统招占比/统招本科档/985/211/一本/二本/硕士/待裁定/待核实）+ 与上期基线差 + 新增待裁定院校逐条清单 + 遗留待裁定项（省属重点·存疑 21 人、孙晓东档归属、工程管理分公司是否剔除）。无人值守不调 AskUserQuestion，待裁定项只列出不擅断；输出简洁，不写「数据来源/口径说明/生成时间」类尾巴。
```
