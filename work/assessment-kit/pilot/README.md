# pilot —— 试测工具链（票 #24 · 模拟版）

这里放的是**试测流水线**，不是一次试测的结果。

- 一次「模拟试测」的完整结论在 [`试测报告_模拟版_20261024.md`](试测报告_模拟版_20261024.md)。
- 真人试测怎么做，在 [`真人试测作业包_20261024.md`](真人试测作业包_20261024.md)。

## 跑一遍（合成数据）

```bash
cd work/assessment-kit
python3 pilot/simulate.py --selftest   # 1. 生成合成样本 + α 自检对照数据集
node    pilot/run_pilot.mjs             # 2. 跑成品真实计分 + 整卷端到端出报告
python3 pilot/analyze.py                # 3. 统计与判定
python3 pilot/verify_report_pdf.py     # 4. 报告打印验收（Chrome → PDF → 文本层断言）
```

产物落在 `pilot/out/`（样本、计分结果、分析结果、报告 HTML 与 PDF、结果 JSON 样例）。

## 跑一遍（真人数据）

三步：**回收表录入 → 真实计分 → 统计判定**。录入这一步以前要手工拼 JSON，
现在有工具（票 #26 前置）：

```bash
# 0. 拿模板（表头 + 两行假数据，工具会拒绝 DEMO-FAKE- 前缀的行）
python3 pilot/ingest_real.py --template > pilot/out/回收登记表.csv

# 1. 施测人填完回收表 → 转成流水线要的 JSON（硬错误整批阻断，不写任何输出）
python3 pilot/ingest_real.py --csv pilot/out/回收登记表.csv --out-dir pilot/out/
#    产出：real_samples.json / excluded_ids.json / 回收登记表_回收后.csv / ingest_report.json

# 2. 真实计分（同一段 report.js）+ 统计判定
node    pilot/run_pilot.mjs pilot/out/real_samples.json
cp pilot/out/scored.json pilot/out/real_scored.json
python3 pilot/analyze.py --real pilot/out/real_samples.json \
        --scored pilot/out/real_scored.json \
        --exclude pilot/out/excluded_ids.json

# 3. 双人标注 / 仲裁 / 锚定审计 → 分歧率与命中率（机器判定，人只仲裁）
python3 pilot/analyze_annotations.py \
        --annotations pilot/out/annotations.csv \
        --arbitration pilot/out/arbitration.csv \
        --audit pilot/out/audit.csv --out-dir pilot/out/
```

输入格式见作业包 §六；录入工具的字段表与校验规则见
[`ingest_real_说明.md`](ingest_real_说明.md)，标注工具见
[`analyze_annotations_说明.md`](analyze_annotations_说明.md)。

> 录入的**硬错误是全量阻断**：一行写错整批不写。建议每收一份就转一次，
> 别攒到最后。`ingest_report.json` 里的**提醒项**不阻断（缺层级、缺部门、
> `actual_min` 与起止时刻矛盾等），归档前扫一眼。

## 发卷前预检（一条命令）

```bash
python3 pilot/preflight.py
```

依次查：成品在不在（+ sha256）· 成品是否比产品源旧 · 当前限时口径是 B 还是 A/C ·
四个自检门 · 两个工具自检 · 生成回收登记表模板。任一项不过 → 退出码 1，别发卷。

## 文件

| 文件 | 干什么 |
|---|---|
| `preflight.py` | **发卷前预检**（成品/新鲜度/口径/四个门/两个工具自检/模板生成）|
| `施测动作清单_一份被试_20261025.md` | **施测人现场照着做的一页纸**（发卷/批次计时/收卷/登记/交接/异常）|
| `录入链路演练_20261025.md` | 用手抄风格的假表撞录入工具的演练记录（非真人数据）|
| `simulate.py` | 合成样本生成器：HR 画像注入真值、装分与社会赞许项、异常作答注入、α 自检对照数据集 |
| `run_pilot.mjs` | **驱动成品真实计分**：从 `dist/` 里抽 `window.__DATA__`，跑 `src/modules/report.js` 的 `window.REP`；整卷端到端出报告 HTML |
| `analyze.py` | α / 分半信度 / 分布 / 极端题 / 锚定审计演练 / 真值回收 / 异常盲检 / 校准演示 / 相关性检查 / 与 Node 的交叉验算 |
| `verify_report_pdf.py` | 报告打印验收：Chrome headless 出 A4 → `pdftotext` 抽文本层 → 8 项断言 |

## 三条纪律

1. **计分不在 Python 里重写。** `analyze.py` 里那份复算是为了**交叉验算**，不是替代；
   真正的计分永远跑 `src/modules/report.js`（成品同款）。
2. **合成数据的数字不是信效度证据。** α / 分布 / 极端题全是生成模型的性质。
   `analyze.py` 对合成数据一律标 `(模拟)`，真人模式才输出无后缀的 α。
3. **阈值、题库、裁定表在真人证据到手前不动。** 校准演示只演示算法，不落盘阈值。
