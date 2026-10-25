# ingest_real.py 配套说明 —— 回收登记表 CSV → 真实作答 JSON

> 工具：[`ingest_real.py`](ingest_real.py) · 口径出处：[`真人试测作业包_20261024.md`](真人试测作业包_20261024.md) · 票：<https://github.com/nolifeking0916/DSH/issues/26>
>
> **这个工具不造数据、不给信效度证据。** 它只做一件事：把施测人填的回收登记表，变成
> 流水线（`run_pilot.mjs` / `analyze.py`）读得懂的几个文件，并在转换前把不该进统计的东西挡在门外。

---

## 一、用法

```bash
cd work/assessment-kit

# 1. 拿模板（表头 + 2 行**假数据**示例；示例行必须整行删掉）
python3 pilot/ingest_real.py --template > 回收登记表_模板.csv

# 2. 施测人填完表后转换（四个产物落在 --out-dir）
python3 pilot/ingest_real.py --csv 回收登记表.csv --out-dir pilot/out

# 3. 接着跑流水线（作业包 §六 的复跑命令）
node    pilot/run_pilot.mjs pilot/out/real_samples.json
cp      pilot/out/scored.json pilot/out/real_scored.json
python3 pilot/analyze.py --real pilot/out/real_samples.json \
        --scored pilot/out/real_scored.json --exclude pilot/out/excluded_ids.json

# 4. 改完工具后自检（只在系统临时目录里跑，不碰 pilot/out/）
python3 pilot/ingest_real.py --selftest
```

退出码：`0` 成功 · `1` 有硬错误（**一个输出文件都不写**）· `2` 命令行用法错误。

---

## 二、产物

| 文件 | 内容 | 给谁用 |
|---|---|---|
| `real_samples.json` | 作业包 §六 格式：`{meta, respondents:[{id, group, responses[96], times_ms[96]}]}` | `run_pilot.mjs` / `analyze.py --real` |
| `excluded_ids.json` | JSON 数组，人工判定要剔除的 id | `analyze.py --exclude` |
| `回收登记表_回收后.csv` | **原表逐字节回带**（一个字符都不改），供归档对账 | 归档 |
| `ingest_report.json` | 逐份样本的校验结论 + 全部提醒项 + 批次切分说明 + 题目顺序 | 施测人 / 试测负责人复核 |

**被剔除的样本仍留在 `real_samples.json` 里。** 剔除由 `analyze.py --exclude` 执行（作业包 §六：
剔除的样本不进信度统计，清单会写进 `analysis.json` 留痕）。工具只负责把 id 收进 `excluded_ids.json`
并在报告里标出来，**不替人做剔除决定**。

`meta` 里有什么：`note`（这文件是什么）、`generated_at`（生成时间）、`source_csv`（源 CSV 绝对路径）、
`csv_rows`（CSV 数据行数）、`n_respondents`、`items_source`（题目顺序来源 `items/m1_items.json`）、
`batch_split`（批次切分说明）、`excluded_ids`、`warning_count`。

---

## 三、CSV 字段说明

表头**固定**，列名与顺序必须一字不差（工具会校验并报出缺列/多列）。

```
id,group,level,dept,id4,start_at,end_at,actual_min,
b1,b2,b3,b4,b5,b6,b7,b8,b9,b10,
answers,midway_exit,exit_at,review_request,result_json,quality_note,exclude_reason
```

| 字段 | 填什么 | 硬错误？ | 提醒？ | 出处 |
|---|---|---|---|---|
| `id` | 测评编号或「后 4 位 + 编号」。**不许写完整身份证号** | 空 / 重复 / 疑似 18 位或 15 位身份证号 / 模板示例行 | — | 作业包 §四、§六 |
| `group` | `内部候选人` 或 `在职员工`，只有这两档 | 空 / 不在枚举内 | — | 作业包 §二、§四 |
| `level` | 岗位层级：`专员` / `经理` / `总监` / `其他` | — | 缺 / 不在枚举内 | 作业包 §四 |
| `dept` | 部门（**在职员工填**；内部候选人可空） | — | 在职员工缺 | 作业包 §四 |
| `id4` | 身份标识：身份证**后 4 位**（不记全号） | 疑似完整证件号 | 缺 / 超过 4 位 | 作业包 §四 |
| `start_at` | 开始时刻，如 `2026-10-25 09:00` | 不可解析 | 缺 | 作业包 §三、§四 |
| `end_at` | 收卷时刻，同上；必须 ≥ `start_at` | 不可解析 / 早于开始 | 缺 | 作业包 §三、§四 |
| `actual_min` | 实际用时（分钟） | — | 缺 / 非数字 / 与起止推算差 > 2 分钟 | 作业包 §二、§四 |
| `b1`–`b10` | 每批**本批用时**（毫秒），10 个都要、正整数 | 缺 / 非正整数 / 非数字 | 折算后平均每题 < 3 秒 | 票 #26 §3 |
| `answers` | 96 个 `0`/`1`（`0` = 选 a 侧，`1` = 选 b 侧），顺序与 `items/m1_items.json` 一致 | 空 / 长度 ≠ 96 / 含非 0/1 字符 | — | 作业包 §六 |
| `midway_exit` | `无` / `有` / 有则记退出时刻 | — | 有内容（§二 有效作答要求「无中途退出」） | 作业包 §二、§三 |
| `exit_at` | 中途退出时刻 | — | — | 作业包 §三 |
| `review_request` | `无` / `有`（受理日期、诉求） | — | 有内容（5 个工作日内受理） | 作业包 §三 |
| `result_json` | 结果 JSON 文件名（归档用） | — | 缺 | 作业包 §三、§四 |
| `quality_note` | 作答质量备注（是否中途接电话、是否明显敷衍） | — | 缺 | 作业包 §四 |
| `exclude_reason` | 人工判定剔除的理由。**留空或填 `-` = 不剔除** | — | 填了「无」按不剔除处理（会提醒） | 作业包 §四、§六 |

几点写法上的讲究：

- **未知的时间填 `-`**（填空也行）：缺失不算错，但那样就判不了时长异常（作业包 §二 的
  「时长 ≥ 名义时长 40%」判定要用起止时刻）。
- `answers` 两种写法都收：紧凑 96 字符（`0101…`），或用逗号 / 空格分隔的 96 个 `0`/`1`。
- CSV 里的 `#` 开头行与空行会被跳过（模板自带注释行，所以 `--template > xxx.csv` 出来的文件
  可以直接被工具读）。
- 编码：先按 UTF-8 读（带 BOM 也认，Excel 导出常见），失败再按 GB18030 读（Windows 另存为常见）。

---

## 四、批次切分与时间折算（票 #26 §3）

**批次切分是写死的：**

| 批次 | 题号 | 题数 |
|---|---|---|
| 1 | 第 1–10 题 | 10 |
| 2 | 第 11–20 题 | 10 |
| … | … | … |
| 9 | 第 81–90 题 | 10 |
| 10 | 第 91–96 题 | 6 |

**折算：每题均毫秒 = 该批累计用时 ÷ 该批题数**（四舍五入到整数毫秒）。
例：`b1 = 60000` → 前 10 题每题 6000 毫秒；`b10 = 36000` → 后 6 题每题 6000 毫秒。

这段切分会同时写进 `real_samples.json` 的 `meta.batch_split` 和 `ingest_report.json`，
跑完能对着看。

> ⚠️ **最大的坑**：`b_k` 填的是「**本批**用时」，不是「从开考到第 k 批的累计」。
> 填错的后果是全部时长判歪（`analyze.py` 的「平均每题 < 3 秒」「总时长不足名义 40%」
> 两个旗标会乱响）。工具查得出「批次合计比起止时刻跨度还长」这种自相矛盾，但查不出
> 单批填错 —— 所以现场就要说清楚是「这一批花了多久」。

---

## 五、校验规则

### 硬错误（**整批阻断：一个输出文件都不写，退出码 1，逐条列出哪行哪个字段**）

| 代码 | 含义 |
|---|---|
| `header_mismatch` | 表头与固定表头不一致（报出缺列 / 多列） |
| `id_empty` / `id_duplicate` | id 为空 / 与前面某行重复 |
| `id_pii` | id 疑似完整身份证号（18 位 / 15 位） |
| `id_demo_row` | id 带 `DEMO-FAKE-` 前缀：模板示例行没删干净 |
| `group_empty` / `group_invalid` | 组为空 / 不在「内部候选人、在职员工」内 |
| `answers_empty` | `answers` 为空（作业包 §六 要求 96 题全作答） |
| `answers_invalid` | `answers` 长度 ≠ 96 或含非 0/1 字符 |
| `batch_missing` / `batch_invalid` | `b1..b10` 缺列 / 不是正整数毫秒 |
| `time_unparsable` / `time_reversed` | 起止时刻不可解析 / 收卷早于开始 |
| `id4_pii` | `id4` 疑似完整证件号 |
| `too_many_fields` | 某行字段数多于表头 |
| `items_invalid` | 题库 `items/m1_items.json` 不是 96 题 / 四维不是各 24 题 |

报错示例（真实输出）：

```
校验未通过：发现 3 处硬错误，**没有写出任何输出文件**。
  - CSV 第 3 行（数据第 2 行）字段 answers：长度 94，应为 96（作业包 §六：96 个 0/1，0 = 选 a 侧，1 = 选 b 侧）
  - CSV 第 4 行（数据第 3 行）字段 answers：长度 95，应为 96（作业包 §六：96 个 0/1，0 = 选 a 侧，1 = 选 b 侧）
  - CSV 第 5 行（数据第 4 行）字段 id：与第 2 行的 id 重复（回收核对与防重复提交用）
请改 CSV 后重跑；「CSV 第 N 行」是物理行号，「数据第 M 行」是第几份样本（空行与 # 注释行不计入）。
```

（「CSV 第 N 行」是文件里的物理行号，**包括注释行**；如果登记表是从 `--template` 存下来的，
前面有 9 行注释，表头在第 10 行、样本从第 11 行起，报错里的物理行号会整体后移，
「数据第 M 行」才是第几份样本。）

### 提醒项（**不阻断**，全部进 `ingest_report.json`，命令行也会打印）

`missing_level`（缺岗位层级）· `level_unknown` · `missing_dept`（在职员工缺部门）·
`missing_id4` · `id4_too_long` · `missing_start` / `missing_end`（缺起止时刻，时长异常就判不了）·
`missing_actual_min` · `actual_min_unparsable` · `actual_min_mismatch`（与起止推算差 > 2 分钟）·
`session_over_nominal`（起止跨度超过 §二 的限时 90 分钟）· `fast_items`（折算后平均每题 < 3 秒）·
`batch_total_gt_actual_min` / `batch_total_gt_window`（批次合计比整场用时还长 → `b_k` 填法错了）·
`midway_exit`（有中途退出）· `review_request`（有复核申请）· `missing_result_json` ·
`missing_quality_note` · `exclude_reason_is_wu`（填了「无」→ 按不剔除处理）· `missing_actual_min`。

---

## 六、已知限制

1. **「姓名」不在本 CSV 表头里。** 作业包 §四 的登记表有「姓名」一栏，但本工具的表头是固定的
   25 列，姓名不在其中。名字只在结果 JSON 里（作业包 §四 也说「只在本表留姓名；结果 JSON 里已有」）。
   要归档带姓名的登记表，就在这份 CSV 之外另存一份带姓名的表（本工具回带的
   `回收登记表_回收后.csv` 与原表逐字节相同，不含姓名）。
2. **`answers` 的顺序没法验。** 工具只能验「96 个 0/1」；「施测人是不是按 `m1_items.json` 的题目
   顺序作答」只能靠现场纪律（题面顺序就是 `INT-01…24 → SNT-01…24 → TFS-01…24 → JPS-01…24`）。
3. **逐题时间是批均值的台阶。** 96 个 `times_ms` 里只有 10 个不同值（每批一个），
   批次内部的真实快慢分不出来。作业包 §九 风险 2 已经写明：异常判定阈值拿到真实时长分布后
   **必须重新标定**。折算本身有 ±0.5 毫秒/题的取整误差，可忽略。
4. **`b1..b10` 只覆盖第一项。** 96 题是第一项；第二项、第三项没有批次计时。作业包 §二 的
   90 分钟是三项合计，所以「批次合计 ≤ 整场用时」是正常的，工具只在**反过来**时提醒。
5. **硬错误是全量阻断。** 一行错整批不写。这是刻意的：宁可重跑，也不要半份数据进流水线。
   代价是一份 60 行的表只要有一行 id 写错就要重来，所以建议**每收一份就转一次**。
6. **`id` 写完整身份证号按硬错误处理**（比作业包 §六 的措辞更严）。理由：一旦写进
   `real_samples.json` 就等于把证件号带进了分析产物，而这个文件会跟着分析结论到处传。
   拦在门口比事后清理便宜。
7. **`exclude_reason` 填「无」按不剔除处理**（并给提醒）。字面「非空即剔除」会把「无」也当成剔除，
   那会**静默地把一份有效样本踢出信度统计** —— 比反过来危险。
8. **`analyze.py` 的剔除只作用于信度统计。** 分布、极端题、异常盲检那些段仍然统计全部样本
   （现有行为，本工具不改 `analyze.py`）。报告 §八 第 1 条要求「各组份数、分层、剔除情况」，
   分层数据请从 `ingest_report.json` 取。
9. **模板里的两行是假数据**，且 id 带 `DEMO-FAKE-` 前缀，工具会直接拒绝 —— 防止忘了删就进真跑。
10. **自检不碰 `pilot/out/`。** `--selftest` 的所有 fixture 都落在系统临时目录
    （`tempfile.mkdtemp(prefix="SELFTEST_ingest_real_")`），跑完删掉；自检里有一条断言专门比对
    `pilot/out/` 的文件清单前后是否一致。

---

## 七、自检覆盖了什么

`python3 pilot/ingest_real.py --selftest`（42 项断言，全在临时目录里）：

- 正例：能转出 4 个产物；`responses` / `times_ms` 长度 96；`times_ms` 的批折算对得上
  （`b1=60000→6000ms`、`b10=36000→6000ms`）；`real_samples.json` 顶层只有 `meta` / `respondents`，
  每份样本只有 `id` / `group` / `responses` / `times_ms` 四个键；`excluded_ids.json` 是 JSON 数组；
  被剔除的样本仍留在样本文件里；登记表回带与原表一样大。
- 反例：长度错、非法字符、重复 id 三种错被抓到，且**报错文案指到具体行与字段**；
  CLI 退出码 = 1 且**一个输出文件都不写**。
- 其他硬错误：组不在枚举内、批次不是正整数、收卷早于开始、id 写完整身份证号、模板示例行没删。
- 提醒项：缺 level、缺 dept、`actual_min` 与起止矛盾 → 只提醒不阻断，样本照样生成。
- `answers` 的逗号分隔写法被正确解析。
- 模板表头与固定表头一致、示例行都是假数据。
- `pilot/out/` 文件清单前后一致（自检没写进去）、产物全在临时目录内。
