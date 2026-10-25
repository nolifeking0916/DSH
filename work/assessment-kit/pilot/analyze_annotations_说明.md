# `analyze_annotations.py` 说明 —— 真人试测标注 / 仲裁 / 锚定审计的机器判定

> 票 #26（真人试测）的前置工具。配套脚本：`pilot/analyze_annotations.py`。
> 口径来源：`pilot/真人试测作业包_20261024.md` §五（双人标注与锚定审计）、§七（判定阈值表）。
> 题库：`items/m1_items.json`（96 题，INT / SNT / TFS / JPS 各 24 题）。

## 一、它干什么 / 不干什么

**干什么**：吃**真实**的双人标注表、仲裁表、锚定审计表，产出机器能判、人能读的结论——
每维分歧率过没过线、锚定审计命中率达没达标、哪些题待仲裁、哪些题的 `rationale` 该写回什么。

**不干什么**（这几条是纪律，不是限制）：

1. **不裁决。** 「哪一端更有效」由人判断；分歧题的仲裁权在测评负责人，机器不代劳。
2. **不写题库。** `rationale_suggestions` 只是**建议清单**，一个字节都不写回 `items/m1_items.json`。
3. **不改阈值。** 15% / 80% 是作业包 §七 定死的值，脚本里是常量，不接受命令行改。
4. **不造数据。** 脚本不生成任何「真人数据」；`--selftest` 造的 fixture 文件名与标注员代号一律带
   `SELFTEST_` 前缀，报告里也会打上「自检（非真人数据）」的标记。
5. **不算是信度。** Cronbach's α / 分半信度是 `analyze.py` 的活，且要的是被试作答数据；
   本脚本吃的是标注员对题目的判断，两者不是一回事。

## 二、用法

```bash
cd work/assessment-kit

# 最小用法：只有双人标注表
python3 pilot/analyze_annotations.py \
    --annotations pilot/out/annotations.csv \
    --out-dir pilot/out

# 完整用法：三张表都上
python3 pilot/analyze_annotations.py \
    --annotations  pilot/out/annotations.csv \
    --arbitration pilot/out/arbitration.csv \
    --audit       pilot/out/audit.csv \
    --out-dir     pilot/out

# 自检（造 fixture 并断言判定；临时文件全在 tempfile 目录内）
python3 pilot/analyze_annotations.py --selftest
```

| 参数 | 必填 | 说明 |
|---|---|---|
| `--annotations CSV` | 是（`--selftest` 除外） | 双人标注表 |
| `--arbitration CSV` | 否 | 仲裁表；不提供就只报分歧、不报仲裁 |
| `--audit CSV` | 否 | 锚定审计表；不提供则四维都记「未审计」 |
| `--out-dir DIR` | 是 | 报告输出目录，不存在会建 |
| `--selftest` | 否 | 跑自检 |

**产物**（都在 `--out-dir` 里）：

- `annotations_report.json` —— 机器判定结果
- `annotations_report.md` —— 人读版，**可直接整段贴进试测报告**

只用 Python 标准库，无第三方依赖。Python 3.9+ 可跑。

## 三、输入表结构

### 3.1 标注表 `annotations.csv`

| 列 | 必填 | 说明 |
|---|---|---|
| `qid` | 是 | 题号，对应题库 `id`（如 `INT-01`） |
| `annotator` | 是 | 标注员代号（如 `A` / `B`） |
| `choice` | 是 | 选中的那一端：`a` / `b`（也接受 `A端` / `选a` 这类写法） |
| `comment` | 否 | 标注员自己的理由，仲裁时用得上 |

每题每名标注员一行；同一 `qid` 可以有多行（两名标注员各一行）。

```csv
qid,annotator,choice,comment
INT-01,A,a,主动约人对齐更省事
INT-01,B,b,等对方来找更稳妥
```

### 3.2 仲裁表 `arbitration.csv`（可空）

| 列 | 必填 | 说明 |
|---|---|---|
| `qid` | 是 | 分歧题号 |
| `final_choice` | 是 | 仲裁结论：`a` / `b` |
| `reason` | 否 | 仲裁理由，**这段话才是写回题库 `rationale` 的内容** |

```csv
qid,final_choice,reason
INT-01,a,两人都强调先连接再推进，判 a 端更有效
```

### 3.3 锚定审计表 `audit.csv`（可空）

| 列 | 必填 | 说明 |
|---|---|---|
| `qid` | 是 | 抽检题号 |
| `orig_anchor` | 是 | **原**有效端：`a` / `b`（应与题库 `anchor` 一致，不一致会告警） |
| `swapped_anchor` | 是 | **换位后**有效行为所在的一侧：`a` / `b`（= 原有效端的另一侧） |
| `annotator` | 是 | 标注员代号 |
| `choice` | 是 | 换位后该标注员选中的那一端（`a` / `b`）**或**行为原文 |

```csv
qid,orig_anchor,swapped_anchor,annotator,choice
INT-05,a,b,A,b
INT-05,a,b,B,b
```

> 作业包 §五 的锚定审计记录表是一题一行（标注员 A / B 两列 + 一列「命中」），
> CSV 是它的长表形态：每名标注员一行。工具按题聚合（见 §四.3）。

## 四、判定口径

### 4.1 分歧率（双人标注）

- **分歧** = 同一题两名标注员选的端不同。
- **分歧率** = 分歧题数 ÷ **该维题数**（分母是题库的 24，**不随实际标注数变**）。
- 阈值：**> 15%（24 题中 ≥ 4 题）→ 该维整维重标**；≤ 15% → 通过。
  - 处置是**整维重标**，不是只改那几道分歧题（作业包 §五.3）。
- 分母固定成 24 是规程的原话。**代价是：标注不齐时分歧率会偏低**，所以本工具另出
  `data_status`（完整 / 不全 / 缺失）与 `overall_provisional` 标记，见 §六.1。

### 4.2 锚定审计命中率

- 抽检：每维 6 题（作业包 §五）。
- **命中题数** ÷ **审计题数** = 命中率；阈值 **≥ 80%** 通过，**< 80% → 该维题目重写**。
- 6 题的粒度是 1/6 ≈ 16.7%：5/6 = 83.3% 过线，4/6 = 66.7% 不过线。

### 4.3 逐题命中怎么聚合

CSV 是逐标注员的，规程的命中率是**逐题**的。规则：**该题两名标注员都命中，才算该题命中**；
一人命中一人没命中 → 该题记**未命中**，并在该维的 `mixed_questions` 与报告里单列出来，
让人复核。（报告同时给出逐行的 `hit` / `hit_rule`，可以自己换口径重算。）

### 4.4 总判定

任一维的分歧率不过线、或锚定审计命中率不过线 → **`overall: "需返工"`**；否则 **`"通过"`**。
报告顶部（MD 第一屏）一定有一句总判定。

### 4.5 `hit_rule`：命中是怎么判出来的

换位之后，**原来有效的那一条行为**出现在 `swapped_anchor` 那一侧。工具据此判命中：

| `hit_rule` | 什么时候用 | 判定 |
|---|---|---|
| `anchor_side` | 标注员记的是**侧别字母**（`a` / `b`） | `choice == swapped_anchor` 即命中 |
| `behavior_text` | 标注员记的是**行为原文**，且能在题面里唯一对上 | 原文就是**原有效端那一条行为**即命中；是对面那条即未命中 |
| `fallback_swapped_anchor` | **题面判不出行为一致性** | 退回按「换位后选择与 `swapped_anchor` 相同」判定 |

- **不瞎猜**：题面两侧文本都能对上、或者都对不上时，工具不替人判断行为是不是同一个，
  退回 `fallback_swapped_anchor`，并在 `hit_rule` 与报告里写明用了哪种口径，让人能复核。
- 某一维用到的口径不唯一时，`hit_rule` 写成 `mixed(anchor_side,behavior_text)`。
- `fallback_swapped_anchor` 下认不出来的一律**不算命中**（宁可漏，不可凭空给命中）。

## 五、输出

### 5.1 `annotations_report.json`

| 顶层字段 | 说明 |
|---|---|
| `overall` | `"需返工"` / `"通过"` |
| `overall_provisional` | `true` = 数据不齐，这个结论是**暂定**的，不能当最终结论 |
| `overall_provisional_reasons` | 暂定的具体原因（哪维没标全 / 没审计 / 抽样不足） |
| `overall_note` | 总判定的一句话说明 |
| `rework_dimensions` | 需要返工的维与处置 |
| `thresholds` | 本次用的阈值与出处 |
| `hit_rule_desc` | 三种 `hit_rule` 的文字说明 |
| `input_summary` | 读了多少行 / 多少题 / 多少维 / 缺失标注的题号清单 … |
| `per_dimension` | 每维 `{total, disagree_count, disagree_rate, threshold, pass, action, ...}` |
| `disputes` | 全部分歧题 `{qid, dimension, annotator_a, annotator_b, choice_a, choice_b, comment_a, comment_b, final_choice, reason, need_arbitration}` |
| `audit` | 每维 `{sampled, hit_count, hit_rate, threshold, pass, action, hit_rule, ...}` |
| `audit_questions` | 逐题明细（含每名标注员的 `hit` / `hit_rule` / `note`），可自行换口径重算 |
| `rationale_suggestions` | 写回题库 `rationale` 的**建议**清单 `{qid, dimension, reason, source, need_arbitration}` |
| `warnings` | 数据告警（题号不在题库、取值非法、自相矛盾、三名标注员 …） |

`per_dimension[d].action`：`"pass"` / `"整维重标"`。
`audit[d].action`：`"pass"` / `"该维题目重写"` / `"未审计（无数据）"`。

`rationale_suggestions[].source` 三种：

- `arbitration` —— 分歧题的仲裁理由（`need_arbitration: true` 的表示**还没仲裁**，理由待补）
- `missing_rationale` —— 题库 `rationale` 为空
- `audit_miss` —— 锚定审计未命中，判据句需重写

### 5.2 `annotations_report.md`

人读版，结构：总判定 → 一、分歧率 → 二、锚定审计 → 三、分歧题清单 → 四、待仲裁题 →
五、`rationale` 写回建议 → 六、输入与数据完整性 → 七、数据告警。
每维一行（题数 / 分歧数 / 分歧率 / 是否过线 / 处置），可直接贴进试测报告。

## 六、已知限制

1. **数据不齐时的「通过」是假的通过。** 分歧率的分母固定是该维 24 题，
   一题没标也算「一致」。工具不会偷偷改判定口径（那是规程），但会：
   - 报 `data_status`（完整 / 不全 / 缺失）；
   - 置 `overall_provisional = true`，在 MD 第一屏打出「⚠ 结论暂定」的横幅；
   - 把判定列写成「**暂定过线**」而不是「过线」。
   **看到「暂定」就先去补数据，别把这种「通过」写进结论。**
2. **审计的逐题聚合是本工具定的口径**（两人都命中才算该题命中），规程只写了逐题记录表。
   原始逐行判定都在 `audit_questions` 里，要换口径自己重算。
3. **`hit_rule` 的行为原文比对用的是归一化后的精确 / 包含匹配**，不是语义理解。
   题面两侧文本高度相似时会退回 `fallback_swapped_anchor`（不瞎猜）。
4. **换位审计表里 `swapped_anchor` 必须是「换位后有效行为所在的一侧」**（原有效端的另一侧）。
   填反了工具按填的值判定（只对与题库 `anchor` 不一致的 `orig_anchor` 告警），
   所以**录入审计表时务必先确认这一列的口径**。
5. **数据异常一律不计入、不猜**：题号不在题库、`choice` 不是 `a`/`b`、仲裁取值非法、
   同一标注员同一题给了两个不同选择、同一题出现三名以上标注员 —— 这些题都不进分歧统计，
   全部进 `warnings`。**静默丢数据是这类工具最容易出的事故**，所以每一条都告警。
6. **本工具只判「标注员之间是否一致」和「换位后是否还选中同一个行为」**，
   不判「哪一端更有效」，也不判题目写得好不好——那是仲裁和改题环节的事。
7. **不做信度、不做分布、不做社会赞许偏差**。那些要的是被试作答数据，走 `analyze.py`。
8. **`overall_provisional` 不会让 `overall` 变成第三种值。** `overall` 只有
   `"需返工"` / `"通过"` 两个取值（照规程），暂定信息走单独字段——不在工具里另立口径。

## 七、容易踩的坑（给施测人与测评负责人）

1. **审计表的 `swapped_anchor` 填反** → 命中率会莫名其妙地变成 0 或 100%。
   填之前先确认「换位后有效行为在哪一侧」。
2. **审计时把换位版发给标注员时，没说清「现在问的是哪一端更有效」** → 标注员会以为还是原题，
   答案不是「换位后选的端」而是「原题选的端」。工具判不出来时会退回口径并告警，
   但**根源在施测环节**。
3. **两名标注员互相看过结果** → 规程要求互不可见。一旦串了，分歧率会假性下降。
4. **同一标注员给同一题填了两个不同选择** → 该题整题作废（不进分歧统计）。
   录完先跑一遍本工具，看 `warnings` 有没有这类问题，别等报告贴出去才发现。
5. **只标了一部分题就出报告** → 分歧率会偏低，工具会标「暂定」，但**人容易忽略这行**。
6. **仲裁只写结论不写理由** → `rationale` 无内容可写回。仲裁理由是题库更新的原料，
   规程 §五.4 明确要写回 `rationale`。
7. **把自检产物当成真人数据引用** —— 自检 fixture 的文件名与标注员代号都带 `SELFTEST_`，
   报告里也会打「自检（非真人数据）」标记。**报告贴出去前先看第一屏那行**。
8. **审计抽样超过 6 题** → 工具照算并在 `warnings` 里提示规程是每维 6 题。
9. **把本工具的结论当成「题目质量已过关」** —— 它只回答「标注员之间一致吗 / 换位后还认得出吗」。
   题面写得好不好，最后还是要靠仲裁理由和改题记录来判断。

## 八、自检

```bash
python3 pilot/analyze_annotations.py --selftest
```

自检在 `tempfile` 临时目录里造 fixture（**不会写进 `pilot/out/`**，跑完自动清理），
覆盖六组断言：

1. **两维分歧率超线** —— INT 4/24 = 16.7%、TFS 5/24 = 20.8% → 均为「整维重标」；
2. **审计命中率达线 / 不过线** —— SNT 6/6 = 100% → 通过；JPS 4/6 = 66.7% → 该维题目重写；
3. **缺仲裁** —— 无仲裁的 `final_choice` 为 `null`、`need_arbitration` 为 `true`；
   仲裁取值非 `a`/`b` 的按未仲裁处理；
4. **总判定与写回建议** —— `overall = "需返工"`；建议清单含已仲裁题、待仲裁题、审计未命中题；
5. **三种 `hit_rule`** —— 侧别字母、行为原文、退回口径各自的命中/未命中；
6. **目录纪律** —— 产物全部落在 `tempfile` 内，`pilot/out/` 前后快照一致。
