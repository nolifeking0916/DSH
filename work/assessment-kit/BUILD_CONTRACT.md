# 测评成品集成契约（并行施工用）

> 目的：三路并行（编码修复 / 新第一项题库 / 设计系统）+ 集成方（lead）**互不等待**，按本文件的口径拼装。
> 权威口径来源：`统一五级裁定表_20261024.md` · `告知卡要素与数据留存规则清单_20261024.md` · `research/无障碍与打印归档基线_20261024.md` · `合并版现状盘点_20261024.md`
> 原型基准（视觉与交互的唯一参照）：分支 `prototype/candidate-flow-20261024` 的 `work/assessment-kit/prototypes/candidate-flow-prototype.html`（A 纸感编辑式为基准 + 吸收 B 的任务清单式模块总览与顶部细眉题）。

## 0. 目录与写权限（互斥）

```
work/assessment-kit/
├── BUILD_CONTRACT.md              ← 本文件
├── items/                         ← B 写
│   ├── m1_items.json
│   └── m1_design.md
├── data/                          ← A 写（eq_bank_encoded.json）、C 写（logic_m3.json）
│   ├── eq_bank_encoded.json
│   └── logic_m3.json
├── src/                           ← C 写（tokens.css / components.css）、lead 写（其余）
│   ├── tokens.css                 C
│   ├── components.css             C
│   ├── layout.css                 lead
│   ├── modules/m1.js              lead
│   ├── modules/m2.js              lead
│   ├── modules/m3.js              lead
│   ├── modules/shared.js          lead
│   ├── modules/report.js          lead
│   └── build.py                   lead
├── dist/                          ← lead 写（构建产物）
│   └── 云上文旅集团核心人才系列测试_20261024.html
├── prototypes/                    ← 已有（原型，不动）
└── research/                      ← 已有

work/eq-test/                      ← A 写（build_eq_web_v2.py / web/eq_test_template_v2.html / test_eq_encoding.py）
```

**写作用域互斥**：A 只碰 `work/eq-test/**` 与 `work/assessment-kit/data/eq_bank_encoded.json`；B 只碰 `work/assessment-kit/items/**`；C 只碰 `work/assessment-kit/src/tokens.css`、`src/components.css`、`src/data/logic_m3.json`。lead 写其余全部。**任何人不得 git commit / checkout / 改其它文件。**

## 1. 数据文件 schema（字段名不许改）

### 1.1 `data/eq_bank_encoded.json`（A 产出）
与 `work/eq-test/bank/eq_bank.json` **同结构**，但：
- `meta` 增加 `"encoding":"fixed-20261024"`；
- `sjt[i].c` 换成**修好后**的编码串（解码必须与 `answer/second/third` 完全一致）；
- 保留 `answer/second/third` 原文字段（供回归比对）；`options/stem/dimension/id/consistency/pair` 原样；
- 一致性题 `c="0"`。

### 1.2 `items/m1_items.json`（B 产出）
```json
{
  "meta": {
    "version": "1.0",
    "title": "管理行为成熟度测评",
    "scoring": "每题给「更有效的一端」记 1 分；每维 0-24 分；整体档 = 最低维档",
    "bands": {"顶尖":[22,24],"优秀":[18,21],"良好":[14,17],"合格":[9,13],"待提升":[0,8]},
    "dimensions": [
      {"key":"INT","name":"互动方式","definition":"……（该维测什么）","theory":"……（核心理论出处）","items":24},
      {"key":"SNT","name":"关注重点","definition":"…","theory":"…","items":24},
      {"key":"TFS","name":"行事依据","definition":"…","theory":"…","items":24},
      {"key":"JPS","name":"行事节奏","definition":"…","theory":"…","items":24}
    ]
  },
  "items": [
    {"id":"INT-01","dim":"INT","a":"……","b":"……","anchor":"a","rationale":"为什么这一端更有效（一句话）","theory":"依据的行为科学/管理学要点（一句话）"}
  ]
}
```
硬约束：四维 key 固定 `INT/SNT/TFS/JPS`；`anchor` ∈ {`a`,`b`}；每维 24 题共 96 题；每维 anchor=a 与 anchor=b 的条数差 ≤ 2（防默认 acquiescence 偏差）；题干为**行为频率陈述**，两侧均 ≤ 20 字；不得出现双重否定、不得出现智力/性格/临床词汇、不得出现 MBTI 字母标签；每题必须能说清"哪端更有效"。

### 1.3 `data/logic_m3.json`（C 产出）
第三项的**逻辑与文案**（从现版第三项独立版搬过来，去掉淘汰语义）：
```json
{
  "meta": {"version":"1.0","title":"思维逻辑与推理能力测评","minutes":45,"items":40,"dims":8},
  "dims": {"DED":{"name":"演绎推理","short":"…","what":"…","high":"…","low":"…","job":"…","risk":"…","action":"…","probe":["…","…"]}, …8 个},
  "levels": [{"key":"T","name":"顶尖","range":"P90 以上（T≥63）","desc":"……（已去掉淘汰语义）"}, …5 个],
  "questions": [{"id":"DED-1","dim":"DED","difficulty":1,"stem":"…","grid":null,"options":["…"],"answer":0,"explain":"…"}],
  "norm_note":"…","report_note":"…","must_say":["…"],"must_not_say":["…"]
}
```
硬约束：40 题 / 8 维 / 5 档齐全；**任何一档的 desc 不得含「不宜独立承担」「低于岗位基本要求」等淘汰语义**（改成"这一项需要更多支持/复核"）；保留 `must_say` / `must_not_say` 供报告页使用。

## 2. CSS 分工（C 写 tokens.css + components.css）

`tokens.css`：只放**变量**，不许出现选择器：
```
--green #1E4634  --green2 #2A5C42  --gold #C9A55C  --cream #F5F0E4  --paper #FAF9F4
--ink #1D2A23  --ink2 #42544B  --muted #5C6A60  --line #E6EAE7  --sand #6E5B36
--red #8E2F26  --red-bg #FBEDEA  --good #1B7A56  --good-bg #E5F1EB
--sheet #FFFDF8  --page #EDE8DD  --paper-b #EFF1EF
--fs-1 12px  --fs-2 13px  --fs-3 14px  --fs-4 15px  --fs-5 16px  --fs-6 19px  --fs-7 22px
--sp-1 4px --sp-2 8px --sp-3 12px --sp-4 16px --sp-5 24px --sp-6 32px
--r-s 8px --r-m 12px --r-l 18px  --tap 44px
--font: -apple-system,BlinkMacSystemFont,"PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif
--serif: "Songti SC","Source Han Serif SC",Georgia,"Times New Roman",serif
```
> **两个对比度坑必须避开**：金色 `#C9A55C` 在浅底上只有 2.2:1 → **不能做小字**，只用于装饰线、大字（≥24px）或深绿底上的字；浅底上的小字用 `--sand #6E5B36`（5.35:1）。`--muted` 必须是 `#5C6A60`（不是 `#77867D`，后者只有 3.6:1）。正文/次级文字 ≥4.5:1，图形与控件边界 ≥3:1。

`components.css`：以下组件类，语义与原型一致（原型里已有可运行的样式，**以原型为准**）：
`wrap / sheet / brand / rule / sub / sect-title / kv / modlist / tasklist / qbar / qmeta / qstem / opts / opt / k / scale / seg / qnav / qtabs(仅原型，成品不用) / gridbtn / warn / btn btn-primary btn-ghost btn-quiet btn-full / field / hint / tag / terms / check / foot / card / panel / gridpanel / mask / list-metrics / metric / bar / bars / radar / grade / grade-pill / short-board / compose / compose-note`

`components.css` 额外必须提供成品专用组件（原型里没有，由 C 按同一视觉语言设计）：
- `.metric-row`：一行"维度名 + 分数 + 五级胶囊"（施测人报告用）
- `.bar-track / .bar-fill`：维度相对表现条（无背景色也能靠长度读懂，兼作打印可读）
- `.radar-wrap`：SVG 雷达图容器（宽 100%，max-width 420px，打印不丢色 → 形状与文字标注冗余）
- `.grade` / `.grade-pill`：五级色标（顶尖/优秀/良好/合格/待提升 五个，**颜色 + 文字双编码**，黑白打印也能读）
- `.short-board`：短板提示块（左侧金色竖条）
- `.compose`：总报告顶部的综合评估块（综合五级 + 短板 + 结构性偏科提示）
- `.list-metrics`：总报告的三项并列成绩表

## 3. 页面与阶段（lead 写 layout.css + modules + build.py）

六个阶段：`start` → `consent` → `quiz` → `done` → `hr`（施测人入口）→ `report`（施测人报告，含三模块报告 + 总报告）。

- **start**：品牌区一行标题（**不加副标题**，按第 7 轮口径）→ 测评人信息（姓名、18 位身份证，校验后只留后 4 位）→ 三模块任务清单式总览（题量 + 预计用时）→ 限时开关 → 「阅读说明并开始」→ 「从施测人入口进入」→ 两行合规页脚。
- **consent**：8 条告知卡（原文见 `告知卡要素与数据留存规则清单_20261024.md` §2.1，**照抄不允许改写**，第一条按新第一项改写）→ 勾选框（默认不勾）→ 同意并开始 / 暂不参加 → 两行页脚。
- **quiz**：顶部细眉题（模块名 + 进度 + 计时）→ 题面 → 选项（二极 / 四选一 / 7 点量表三种题型）→ 上一题 / 下一题（未答时 disabled + **文本提示**「这一题还没作答」）→ 题号抽屉 → 两行页脚。答题页**不出现维度名、不出现任何等级词**。
- **done**：完成页 → 下载结果 JSON（字段固定 `tool/version/code/name/idLast4/date/m1/m2/m3`）→ 回传引导 → 清除本机数据 → 两行页脚。**不显示任何分数与等级**。
- **hr**：施测人入口 → 输入测评编号 / 导入结果 JSON → 进入报告。
- **report**：顶部「综合评估块」（综合五级 + 短板 + 结构性偏科提示）→ 三项并列成绩 → 三个模块报告页（第一项四维五档 + 短板；第二项八维 + 档位 + 一致性标记；第三项 8 维 + 雷达图 + 错题回顾 + 使用边界）→ 打印 / 存 PDF → 两行页脚。

## 4. 计分与综合评估（lead 实现，规则来自裁定表）

- 第一项：每维 24 题，按 `anchor` 给分（选中的那一端是 anchor → +1）→ 0–24 → 按 `meta.bands` 切档 → **整体档 = 最低维档**。
- 第二项：沿用 `eq_bank_encoded.json` 的 `answer/second/third`（0/1/2 分）→ 8 维分 → 按题库权重加权 0–5 → 切档（顶尖 ≥4.4 / 优秀 3.8–4.39 / 良好 3.0–3.79 / 合格 2.4–2.99 / 待提升 <2.4）。
- 第三项：40 题难度加权 → 百分位/T 分 → 既有五档。
- **综合评估**：三项五级 → 序数分（顶尖 5 / 优秀 4 / 良好 3 / 合格 2 / 待提升 1）→ 等权平均 → 切档（≥4.5 顶尖 / 3.75–4.5 优秀 / 3.0–3.75 良好 / 2.25–3.0 合格 / <2.25 待提升）→ 综合档与某单项档差 ≥2 级 → 标「结构性偏科」，该项优先追问。**任何地方都不出现总分。**

## 5. 构建产物（lead）

`work/assessment-kit/dist/云上文旅集团核心人才系列测试_20261024.html`：**单文件、零外链**（无 link/script src/@import/url()/@font-face），内联顺序 `tokens.css → components.css → layout.css → data(JSON) → modules/*.js`。构建脚本 `src/build.py` 负责内联并做外链自检。

## 6. 机械自检（lead，脚本可复跑）

1. 零外链；2. 17+ 组对比度达标（阈值见 §2）；3. 告知卡 10 条清单逐条满足；4. 红线词 0（淘汰 / 及格线 / 决定录用 / 有条件行 / 不行 / MBTI / E-I 标签 / 智商 / 诊断）；5. 题面零漂移（成品里的题面与 `items/m1_items.json`、`data/eq_bank_encoded.json`、`data/logic_m3.json` 逐字一致）；6. 报告页含综合评估块且**不含任何总分字段**；7. 身份证只存后 4 位（成品代码里不得出现未脱敏 idNo）；8. 每屏两行合规页脚；9. 六个阶段无 JS 报错；10. 390 CSS px 视口无横向溢出。

## 7. 真人才能做的部分（明确不代做）

- 新第一项的**信效度**（α、分半信度、试测样本、锚定一致性、岗位胜任力映射）必须由真人试测得出 → #18 保留该条为未完成，另开「内部试测与信效度验证」票；本次交付只做到**题目与计分口径可复跑、机械校验全过**。
