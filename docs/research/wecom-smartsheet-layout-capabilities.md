# 企业微信智能表格（WeCom Smartsheet）版式能力实测：面向「集团人力近期重点工作进度表」重设计

> 调查日期：2026-10-24
> 性质：**只读调查**。调查期间未创建/修改/删除任何智能表格、文档、文件或云端资源；未执行任何 `create` / `import` / `records add|update|delete` / `fields add|update|delete` / `views add|update|delete` 写命令。唯一写操作是本文件与 `docs/research/` 目录。
> 目标：为「人力资源六大模块 → 人/流程/成本 → 具体事项 → 分项 → 分项简介 → 最新进展(日期+进展内容) + 开始/完成时间 + 周计划块（按天逐行、与当天进展行 1:1）+ 责任人/负责人类型/协调事项」这一版式，找出 WeCom 智能表格数据模型**能做**与**不能做**的硬约束。
> 关键前提（用户明确要求）：**避免单元格合并**。

---

## 0. 结论速览

**智能表格里根本不存在「合并单元格」这个概念——不是不支持，而是整个模型里没有这个原语。** 一手证据：`wecom-cli smartsheet --doc` 全文对 `merge` / `合并` **零命中**（`grep -ci merge` = 0，`grep -c 合并` = 0），而同一次安装的姊妹服务「在线表格」`wecom-cli sheet --doc` 却有完整的 `merge` 资源（`Sheet_merged_set` / `_get` / `_clear`，支持 `all`/`rows`/`columns` 三种合并方式）——这说明 merge 是 WeCom 文档产品线的**在线表格专属**能力，智能表格从未拥有它。因此「避免合并」不是设计妥协，而是**唯一可行路径**，不需要在「合并」和「扁平」之间取舍。

**每条记录是一个扁平的「字段 → 标量值」映射，没有嵌套子结构、没有子记录集合、没有一对多内联表**（`OaRecord.values: map<string, string>`，key 为字段标题/ID，value 为 JSON 序列化的单值）。因此「一天一条进展」**必须**是一行记录，不能塞进某个单元格里。可替代的跨行关系只有三种扁平引用字段：`reference`（关联，跨子表指向记录）、`two_way_link_records`（双向关联，甚至可跨文档）、`lookup`（查找引用，按条件做 original/unique/sum/count/count_unique/average/max/min 汇总）。

**「按天逐行」在容量上完全可行**：单个子表上限 **20000 条记录、150 个字段**；`records add/update` 单次最多 **2000 条**。39 个事项 × 30 天 ≈ 1170 行、十余个字段，远在限额之内。**真正的约束在读取侧**：`records list` 要求 `limit × 返回列数 < 10000`（15 列时单次 ≤ 666 行），需用 `cursor` 翻页。

**视图侧能力足够支撑目标版式**：视图类型共 6 种（`grid` / `kanban` / `gallery` / `gantt` / `calendar` / `form`，**没有 pivot**）；表格视图可配置分组（多字段列表）、排序、筛选、隐藏字段、冻结列（`frozen_field_count`）、条件填色（可按行/列/单元格）、列宽（`col_infos`，1–1000px）。甘特视图绑定**两个日期字段**（起点/终点，只允许日期类型），可直接复用「开始时间/完成时间」两列。同一子表可并存多个不同类型的视图。

**唯一的未决点**：xlsx 导入时**源文件里的合并单元格会变成什么，一手资料完全没写**（`SmartSheetImportReq` 只有 `name` / `media_id` / `passwd` / `append_doc_id`；`--doc` 与技能文档均未描述合并单元格的处理策略）。但可以确定的是：合并**不可能被保留为合并**（目标模型无合并原语），所以导入只能把它拍平成若干个普通单元格的值。

---

## 1. 证据基座与引用约定

### 1.1 一手来源清单

| 代号 | 来源 | 获取方式 | 备注 |
|---|---|---|---|
| `[CLI-DOC]` | `wecom-cli smartsheet --doc` | 本机 `wecom-cli 1.3.4 (wecom 2026-09-23T11:50:48Z f9b2815)` | 服务文档全文 1678 行，含全部 TypeScript 声明（接口/请求/响应体） |
| `[CLI-SCHEMA]` | `wecom-cli smartsheet --schema` | 同上 | 方法级 JSON Schema（方法清单 + 请求/响应 `$ref`） |
| `[CLI-METHOD-SCHEMA]` | `wecom-cli smartsheet <method> --schema` | 同上 | 单方法 schema（与 `[CLI-DOC]` 同源，用于交叉校验） |
| `[SHEET-DOC]` | `wecom-cli sheet --doc` | 同上 | **姊妹服务「在线表格」**文档，用于对照 merge 能力 |
| `[SKILL:文件:行]` | `~/.dsh/skills/wecom-unified/references/wecomcli-smartsheet-*.md` | 本地安装的企微技能包 | 行号为该文件内行号 |

技能包位置说明（本次实际定位过程）：任务提示的 `~/.dsh/skills/wecomcli-smartsheet/` 与 `~/.dsh/profiles/desktop/node_modules/` 下**并不存在**独立的 `wecomcli-smartsheet` 技能目录；`find ~/.dsh -type d -name "wecomcli-*"` 零命中。实际结构是**单一技能目录 `~/.dsh/skills/wecom-unified/`**，`SKILL.md` 内以「🧮 智能表格 (smartsheet)」一节路由到 `references/wecomcli-smartsheet.md`，其余 34 个 `wecomcli-smartsheet-*.md` 是该技能的参考文件（字段类型、视图类型、记录值、公式、模板等）。本次引用统一使用 `~/.dsh/skills/wecom-unified/references/<文件名>` 绝对路径。

### 1.2 读到的关键接口全景

`[CLI-SCHEMA]` 列出 smartsheet 的全部 26 个方法：`create` / `get` / `import`，以及 `charts`、`fields`、`files`、`images`、`records`、`sheets`、`views` 六个资源组（各含 add/update/delete/list，records 另有 query）。`[CLI-DOC]`「Resource Tree」一致。

---

## 2. 逐题发现

### 2.1 Q1 — 合并单元格：模型里没有这个概念

**结论：不可表达。「合并单元格」在智能表格的 sheets / records / fields / views / charts 任意一个 schema 中都不存在。**

**证据 A（决定性对照）**：同一 CLI 内，姊妹服务「在线表格」**有**完整的 merge 资源：

```
[SHEET-DOC]
- merge
  - `clear(req: Sheet_merged_clearReq)`: 取消指定 A1 区域内的单元格合并；需显式确认后执行。
  - `get(req: Sheet_merged_getReq)`: 获取指定 A1 区域内的合并单元格范围。
  - `set(req: Sheet_merged_setReq)`: 按全部、按行或按列方式合并指定 A1 区域的单元格。
…
interface Sheet_merged_setReq {
  /** 合并方式：all（默认，全合并）/ rows（按行合并）/ columns（按列合并） */
  merge_type?: "all" | "rows" | "columns";
}
```

而智能表格侧同样方法 `grep -ci merge` 与 `grep -c 合并` 均为 **0** 命中。两条产品线共用同一套 sheet-api 类型体系（`OaCellData` / `OaCellFormat` / `OaCellBorder` 等在 `[CLI-DOC]` 中出现），说明智能表格是被**刻意**建模为无合并原语的，而非文档遗漏。

**证据 B（记录结构的扁平性）**：`[CLI-DOC]`

```
/** 行完整记录（SmartSheetGetData Response 中 type=records 时返回，含元数据）
 * 原始 proto3 类型: map<string, google.protobuf.Value> */
interface OaRecord {
  /** 记录 ID */
  record_id?: string;
  /** 记录内容（key: 字段标题/ID, value: JSON 序列化的值） */
  values?: Record<string, string>;
}
```

一条记录 = 一个 `map<string,string>`，每个字段一个值。没有任何「子记录数组」「子表内嵌表」「明细行」字段。

**证据 C（创建时的初始网格也无合并语义）**：`[CLI-DOC]`

```
interface OaGridData {
  /** 各行的数据 */ rows?: OaRowData[];
  start_column?: number;   // 起始列编号（从 0 开始计算）
  start_row?: number;      // 起始行编号（从 0 开始计算）
}
interface OaRowData { /** 单元格数据列表 */ values?: OaCellData[]; }
interface OaCellData {
  cell_format?: OaCellFormat;   // 单元格格式
  cell_value?: OaCellValue;     // 单元格值
  data_type?: string;            // SELECT/CHECKBOX/EMAIL/PHONE/TIME/IMAGE/TEXT/NUMBER/LINK/LOCATION/STAR/ATTACHMENT_VIDEO/FORMULA
}
```

`smartsheet create --grid-data` 只能写「行 × 单元格」的矩形数据，`OaCellData` 里没有 merge/span 字段；`OaCellFormat` 提供的是**边框、对齐、内边距、文本格式**（`borders` / `horizontal_alignment` / `vertical_alignment` / `padding` / `text_format`）——视觉样式可控，但**依然不是合并**。

**证据 D（分组是视图层概念，不是单元格几何）**：`[CLI-DOC]` `OaGroupSpec { groups?: OaGroupInfo[] }`，`OaGroupInfo { field_id, field_title, desc }`。分组是「按字段分组展示行」，与「把 N 列并成 1 个大单元格」无关。

**给设计的替代杠杆**：合并既然不可得，视觉上的「事项块」只能靠**视图层条件填色**实现——`[SKILL:wecomcli-smartsheet-view-types.md:307-313]` 定义 `ViewColorConditionType` 为 `row` / `column` / `cell` 三种粒度，`[SKILL:wecomcli-smartsheet.md:12]` 明确「给单元格/行/列填色、着色、染色、标红、标黄、标绿、高亮、加底色、做条件格式」是本技能的适用能力。即：**用「按行填色 + 分组」制造视觉分段，而非用合并制造视觉分段**。

> 明确说明：**「智能表格 UI 上是否存在某种手工合并」不在这份一手资料覆盖范围内**——`[CLI-DOC]` 只描述 API 能力。CLI/API 层面确定为零。

### 2.2 Q2 — 字段类型全集

**结论：共 27 种 `field_type`。**

`[CLI-DOC]` **不枚举** `field_type` 的取值——`OaField.field_type` 的注释原文是「字段类型, 不要校验了，要不很容易和下游对不齐。」（CLI 的 schema 因此是开放字符串）。完整枚举来自本地技能参考文件：

`[SKILL:wecomcli-smartsheet-field-types.md:5-33]`

| 参数值 | 说明 | 对应属性 | 能装什么（据本表 + 值格式表推断） |
|---|---|---|---|
| `text` | 文本 | 无 | **长自由文本**（唯一文本型；写入为普通 string） |
| `number` | 数字 | `property_number` | 数值 |
| `checkbox` | 复选框 | `property_checkbox` | 布尔 |
| `date_time` | 日期 | `property_date_time` | **日期**（格式串 + `auto_fill`） |
| `image` | 图片 | 无 | 图片数组 |
| `attachment` | 文件 | `property_attachment` | 附件数组 |
| `user` | 成员 | `property_user` | 人员数组（`is_multiple` / `is_notified`） |
| `url` | 超链接 | `property_url` | 链接 |
| `select` | 多选 | `property_select` | 多选数组 |
| `single_select` | 单选 | `property_single_select` | 单选数组（**「负责人类型」这类枚举列用它**） |
| `created_user` | 创建人 | 系统字段 | 只读 |
| `modified_user` | 最后编辑人 | 系统字段 | 只读 |
| `created_time` | 创建时间 | `property_created_time` | 系统时间戳 |
| `modified_time` | 最后编辑时间 | `property_modified_time` | 系统时间戳 |
| `progress` | 进度 | `property_progress` | 0–100 数值 |
| `phone_number` | 电话 | 无 | 字符串 |
| `email` | 邮箱 | 无 | 字符串 |
| `reference` | **关联** | `property_reference` | **跨子表指向记录** |
| `location` | 地理位置 | `property_location` | 坐标 |
| `formula` | **公式** | `property_formula` | **计算值** |
| `lookup` | **查找引用** | `property_lookup` | **跨子表汇总值** |
| `two_way_link_records` | **双向关联** | `property_two_way_link_records` | **跨子表（可跨文档）关联记录** |
| `currency` | 货币 | `property_currency` | 数值 + 币种 |
| `wwgroup` | 群 | `property_ww_group` | 群聊 |
| `autonumber` | 自动编号 | `property_auto_number` | 系统生成（只读） |
| `percentage` | 百分数 | `property_percentage` | 0–1 小数 |
| `barcode` | 条码 | `property_barcode` | 字符串 |

**与目标版式的对应关系（依据上一表 + `[SKILL:wecomcli-smartsheet-record-values.md:7-28]` 的值格式表）**：

| 目标列 | 应选 field_type | 依据 |
|---|---|---|
| 人 / 流程 / 成本（六大模块下的三层） | `text` 或 `single_select` | `[SKILL:…-field-types.md:7,23]`；模块层级用 `single_select` 做枚举更利于分组 |
| 具体事项 / 分项 / 分项简介 | `text` | `[SKILL:…-record-values.md:9]` value 为普通 string |
| 最新进展 · 日期 | `date_time` | 写入格式**必须**为 `"YYYY-MM-DD HH:mm:ss"`（`[SKILL:…-record-values.md:12]`；`[SKILL:…-edit.md:557]`） |
| 最新进展 · 内容 | `text` | 同上 |
| 开始时间 / 完成时间 | `date_time` | 甘特视图要求日期类型（见 §2.3） |
| 责任人 | `user` | `[SKILL:…-record-values.md:15]`，值 `[{"userId":"…","userName":"…"}]`，写入优先传 `userName` |
| 负责人类型 | `single_select` | `[SKILL:…-field-types.md:23]` |
| 协调事项 | `text` | `[SKILL:…-record-values.md:9]` |

**硬性写法约束**：`[SKILL:wecomcli-smartsheet-field-types.md:438]`「添加/更新字段时必须带属性：日期、超链接、人员、单选、多选、数字等字段类型，**必须带上对应的 `property_xxx` 属性**，否则会报 `调用失败, ret=-1`。只有纯文本(`text`)等简单类型不需要额外属性。」

**类型化单元格值里唯一与「一行内多值」有关的是扁平数组**（`select` / `user` / `image` / `attachment` / `url` / `location` / `reference`），但它们都是**同构标量数组**，不是「子记录集合」。

### 2.3 Q3 — 视图

#### 2.3.1 `view_type` 全集（6 种，**无 pivot**）

`[SKILL:wecomcli-smartsheet-view-types.md:34-43]`

| 参数值 | 说明 |
|---|---|
| `grid` | 表格视图 |
| `kanban` | 看板视图 |
| `gallery` | 画册视图 |
| `gantt` | 甘特视图 |
| `calendar` | 日历视图 |
| `form` | 表单视图 |

> 用户设想的「pivot / 数据透视」**不在枚举中**——**一手资料未提供任何透视视图**。若需要透视，只能用「仪表盘图表」替代（见 §2.7 与 `[SKILL:wecomcli-smartsheet-chart-types.md]`）。

#### 2.3.2 表格视图（grid）可配置项

`[CLI-DOC] interface OaViewProperty`

| 配置项 | 类型 | 语义 | 一手依据 |
|---|---|---|---|
| `group_spec` | `OaGroupSpec` | 分组：`groups: OaGroupInfo[]`（字段列表，含 `desc` 降序标记） | `[CLI-DOC]`；`[SKILL:…-view-types.md:184-195]` |
| `sort_spec` | `OaSortSpec` | 排序：`sort_infos: OaSortInfo[]`（多字段，带 `desc`） | `[CLI-DOC]`；`[SKILL:…-view-types.md:171-182]` |
| `filter_spec` | `OaFilterSpec` | 筛选：`conjunction`(`and`/`or`) + `conditions[]`；每条含 `field_title`/`field_type`/`operator` + 值 | `[CLI-DOC]`；`[SKILL:…-view-types.md:199-219]` |
| `field_visibility` | `Record<string,boolean>` | **隐藏字段**（key 支持 field_id / field_title 双形态） | `[CLI-DOC]`；`[SKILL:…-view-types.md:167]` |
| `frozen_field_count` | int32 | **冻结列数量，从首列开始** | `[CLI-DOC]`；`[SKILL:…-view-types.md:168]` |
| `color_config` | `OaViewColorConfig` | **条件填色**，粒度 `row`/`column`/`cell` | `[CLI-DOC]`；`[SKILL:…-view-types.md:292-313]` |
| `auto_sort` | bool | 记录变更后自动重排 | `[CLI-DOC]`；`[SKILL:…-view-types.md:162]` |
| `is_field_stat_enabled` | bool | 是否使用数据统计 | `[CLI-DOC]`；`[SKILL:…-view-types.md:166]` |

**关于「分组是否支持嵌套」**：`groups` 是一个**字段列表**（有序），可以一次指定多个分组字段（六大模块 → 人/流程/成本 这类层级正是靠它实现）；但「该列表是否渲染为多级嵌套分组、嵌套深度上限是多少」**在所有一手资料中均未明述**——`[SKILL:…-view-types.md:188]` 只说「参与分组的字段列表」。**此处标注为「未在一手资料中说明」**，不臆断。

**关于「字段排序（列顺序）」**：`[CLI-DOC] interface OaViewParam` 中 `col_infos?: OAViewColInfos[]` 的注释是「**新增**」；而 `[SKILL:…-view-types.md:63-92]` 明确 `col_infos` 的用途是**列宽**（`field_title` + `width`，1～1000），示例通过 `smartsheet views update` 调用：

```json
{"views": [{"view_id": "<view_id>",
  "col_infos": [{"field_title": "任务名称", "width": 280}, ...]}]}
```

`OAViewColInfos` 另有 `field_id` / `field_title` / `width` 三个字段，**没有 `order` / `index` 之类字段**。结论：**列宽可编程设置；列顺序不可编程设置**（列顺序取决于字段添加顺序，见 §2.7）。**「列重排 API」在所有一手资料中未出现**。

#### 2.3.3 甘特视图 / 日历视图

`[CLI-DOC]`

```
interface OaGanttViewProperty {
  end_date_field_id?: string;    end_date_field_title?: string;
  start_date_field_id?: string;  start_date_field_title?: string;
}
interface OaCalendarViewProperty { /* 结构相同 */ }
```

`[SKILL:…-view-types.md:49-61]`：

| 参数 | 必须 | 说明 |
|---|---|---|
| `start_date_field_title` | 是 | 时间条起点字段名称，**只允许日期类型** |
| `end_date_field_title` | 是 | 时间条终点字段名称，**只允许日期类型** |

且 `[SKILL:…-view-types.md:18]`：`smartsheet views add` 时传 `view_title` + `view_type`，**甘特视图传 `property_gantt`，日历视图传 `property_calendar`**——即这两个属性是**新增时必填**的独立参数（不挂在 `property` 下）。除起止日期字段外，**甘特视图没有其它专属可配置项**（无进度条比例、无依赖关系、无里程碑声明）。

**与目标版式的对接**：用户版式里的「开始时间 / 完成时间」两列**正好就是甘特视图所需的起止日期字段**——甘特视图可零成本复用。技能包内已有同构先例：`[SKILL:wecomcli-smartsheet-template-rd_process_project.md:89-100]`「人力甘特图 / 人力表」字段为 `研发人员(USER) / 开始日期(DATE_TIME) / 结束日期(DATE_TIME) / 优先级(SELECT) / 状态(SELECT) / 需求(TEXT)`。

### 2.4 Q4 — 记录粒度：一条记录能否容纳「重复的子结构」

**结论：不能。必须一天一条记录（或一天一列，见下方权衡）。**

**证据 A**：`[CLI-DOC] interface OaRecord { record_id?, create_time?, creator_name?, update_time?, updater_name?, values?: Record<string,string> }` —— 值类型是 `string`（JSON 序列化的**单值**），键是字段标题/ID。没有 `children` / `sub_records` / `rows` 之类字段。

**证据 B**：写入接口 `[CLI-DOC] interface OaSmartSheetBatchUpdateRecordsReq`：

```
records: OaRecordParam[];   // @minItems 1 @maxItems 2000
interface OaRecordParam { record_id?: string; values?: Record<string, string>; }
```

`[SKILL:…-record-values.md:3]` 同义：「记录的 `fields` / `values` 是一个 key-value 映射，key 为字段名，value 的格式取决于字段类型」。

**证据 C（跨行关系只有「引用」，没有「内联子表」）**：字段类型里能跨表建立关系的是 `reference` / `two_way_link_records` / `lookup` 三种（§2.4 表），它们都是**指向别处**的引用字段，不是**内联容器**。对全部 `wecomcli-smartsheet-*.md` 检索「子记录 / 嵌套记录 / 明细行 / 一对多 / 多对一 / child」**零命中**。

**证据 D（`text` 字段可以「手工塞多天内容」，但那是文本不是结构）**：`text` 写入格式是裸 string（`[SKILL:…-record-values.md:9]`），理论上可以拼成「10-21：完成A；10-22：完成B」这样的**手工编码**。但一手资料**没有给出 `text` 的最大长度限制**（**未在一手资料中说明**），且这种做法会失去可排序、可筛选、可甘特绑定、可按日聚合的能力。**属设计上的下策，不建议**。

**因此「周计划块按天逐行、与当天进展行 1:1」在模型层是自然表达**：每天 = 一条记录 = 一组字段值。`[SKILL:…-template-work_report.md:11-20]` 已有同构先例（日报表：`负责人(USER) / 汇报时间(DATE_TIME) / 相关资料(ATTACHMENT) / 下一步计划(TEXT) / 所属项目(SELECT) / 今日工作总结(TEXT)`）——**「一条记录 = 一天的汇报 + 下一步计划」正是官方模板的形状**。

**唯一真正需要在两种方案间二选一的设计岔路**（这是本调查最重要的推论）：

| 方案 | 形状 | 优点 | 代价 |
|---|---|---|---|
| **A. 长表（每天一行）** | 39 事项 × N 天 = N×39 行 | 一天一列无法容纳「周计划」；每天一行天然 1:1；可按日筛选/排序/甘特 | 行数膨胀；「六大模块/事项」等维度字段在每行重复 |
| **B. 宽表（每天一列）** | 39 行 × (周计划列组) | 行数不变 | **每天需要「计划列 + 进展列」成对**，周数一多字段数暴涨；且**周计划块无法与进展行天然 1:1**（列对列，不是行对行） |

方案 A 与「周计划块按天逐行、1:1 对齐」的硬要求一致；方案 B 的「1:1」只能靠列序约定模拟。**容量上 A 完全可行**（见 §2.7 限额）。

### 2.5 Q5 — 跨子表关系

**结论：有三种，且都能跨子表；其中 `two_way_link_records` 还能跨文档。**

**`reference`（关联）** `[CLI-DOC]`

```
/** 双向关联字段属性，field_type=twowaylinkrecords 时有效 */
interface OaReferenceFieldProperty {
  field_title?: string;    // 字段标题
  filed_id?: string;       // 关联的字段 ID
  is_multiple?: boolean;   // 是否允许多选
  sub_id?: string;         // 关联的子表 ID
  sub_title?: string;      // 子表标题
  view_id?: string;        // 视图 ID
}
```

`[SKILL:…-field-types.md:118-125]`：`property_reference` 参数为 `sub_title`（**关联的子表名称，不传=关联本子表**）、`field_title`（关联的字段名称）、`is_multiple`、`view_id`。

**值格式** `[SKILL:…-record-values.md:148-156]`：

```
### CellReferenceValue（关联）
[{ "record_id": "rec_001" }]
```

→ **B 子表的一条记录可以在 `reference` 字段里写入 A 子表某条记录的 `record_id`，指向关系成立**。

**`two_way_link_records`（双向关联）** `[CLI-DOC]`

```
interface OaTwoWayLinkRecordsFieldProperty {
  back_field_id?: string;   // 双向关联的对应列 ID
  back_field_title?: string;
  field_id?: string;        // 关联的字段 ID
  field_title?: string;
  is_multiple?: boolean;
  pad_id?: string;          // 关联的文档 ID，为空时表示关联当前文档
  sub_id?: string;          // 关联的子表 ID，为空时表示关联本子表
  sub_title?: string;
  view_id?: string;
}
```

`pad_id` 明确支持**跨文档**关联。`[SKILL:…-template-work_report.md:65]` 的「团队日报汇总」模板就用了 `关联 = FIELD_TYPE_TWOWAYLINKRECORDS`。

**`lookup`（查找引用）** `[CLI-DOC] interface OaLookupFieldProperty`：`link_records_field_id`（关联列）+ `lookup_field_id`（引用列）+ `lookup_sub_id`（被引用的子表）+ `filter` + `rollup_type`（`original`/`unique`/`sum`/`count`/`count_unique`/`average`/`max`/`min`，`[CLI-DOC]` 与 `[SKILL:…-field-types.md:394-405]` 一致）。`[SKILL:…-field-types.md:170]`：「当前仅支持按条件查找模式，`lookup_field_title`、`lookup_sub_title`、`filter`（至少一条 condition）均为必填」。

**读取形态**（`[SKILL:…-read.md:180-181]`）：`lookup` / `two_way_link_records` 在 SQL 结果中**展开为被引用值的数组**，例如 `["这是一个纯文本"]`，无引用值返回 `null`。

**对本设计的意义**：若最终采用「长表」方案，`事项` 与 `每日进展` 分两张子表，用 `reference` 或 `two_way_link_records` 挂接，**完全可行**；`lookup` 可用于「每个事项的进展条数」「每个事项的最后进展日期」等派生列。

### 2.6 Q6 — 公式字段

**结论：存在 `formula` 类型，支持跨表、跨记录引用；函数集是白名单制，且不支持取模与三元表达式。**

**结构** `[CLI-DOC]`

```
interface OaFormulaFieldProperty {
  formatter?: OaFormatter;          // 展示格式
  formulaModel?: OaFormulaItem[];   // 公式项列表
}
interface OaFormulaItem {
  attribute?: number;
  fieldId?: string;  field_title?: string;  field_type?: string;
  tableId?: string;  table_title?: string;
  text?: string;
  type?: string;  // FORMULA_TYPE_TEXT / FIELD / ATTRIBUTES / TABLE_REF / FIELD_REF /
                  // TABLE_FIELD_REF / CURRENT_VALUE / VIEW_REF / LINK_FIELD_REF /
                  // PAGE_REF / BLOCK_REF
}
```

技能包给出的**实际可用**子集（`[SKILL:…-formula.md:41-51]`）：`text` / `field`（当前记录字段）/ `table_ref`（引用整个表）/ `field_ref`（列引用）/ `table_field_ref`（表.列引用，返回该列所有值）/ `current_value`（FILTER 遍历中的当前记录）。

**能否引用其它记录？——能，三条路径：**

1. **聚合引用**（跨表）：`{type:"table_field_ref", sheet_title:"订单表", field_title:"金额"}` + `.SUM()` / `.AVERAGE()` / `.MIN()` / `.MAX()` / `.COUNTA()` / `.COUNTIF(条件)` / `.SUMIF(条件)`（`[SKILL:…-formula.md:161-173, 329-343]`）。
2. **FILTER 过滤后聚合**（跨表 + 逐记录条件）：`{type:"table_ref", sheet_title:"任务表"}` + `.FILTER(` + `{type:"current_value"}` + `.` + `{type:"field_ref",...}` + `条件` + `)` + `.列.聚合函数()`（`[SKILL:…-formula.md:179, 380-402]`）。这是**唯一能在公式里逐条遍历别的表记录**的机制。
3. **LOOKUP 跨子表查找**：`LOOKUP(查找值, 匹配列, 返回列, 模式)`，模式 `0`=整体匹配、`1`=拆分多选（`[SKILL:…-formula.md:183, 623-665]`）。
4. **经关联字段穿透**（示例 16）：`{type:"field", field_title:"项目", field_type:"reference"}` + `.` + `{type:"field_ref", field_title:"预算", sheet_title:"项目表"}`（`[SKILL:…-formula.md:579-595]`）。

**函数全集**（`[SKILL:…-formula.md:159-266]`）：聚合 7 个、列表 7 个（`FILTER`/`CONTAINS`/`CONTAINSALL`/`CONTAINSONLY`/`LOOKUP`/`LIST`/`LISTCOMBINE`/`LISTJOIN`/`UNIQUE`）、逻辑 11 个（`IF`/`IFS`/`AND`/`OR`/`TRUE()`/`FALSE()`/`IFBLANK`/`IFERROR`/`ISBLANK`/`ISERROR`/`ISNULL`/`SWITCH`）、日期 17 个（`TODAY`/`NOW`/`DATE`/`DATEVALUE`/`TODATE`/`YEAR`/`MONTH`/`DAY`/`HOUR`/`MINUTE`/`SECOND`/`WEEKDAY`/`WEEKNUM`/`DATEDIF`/`NETWORKDAYS`/`WORKDAY` 等）、数学 11 个、文本 18 个（`TEXTJOIN`/`CONCAT`/`LEFT`/`RIGHT`/`MID`/`LEN`/`FIND`/`SEARCH`/`SPLIT`/`SUBSTITUTE`/`TEXT`/`TRIM`/`VALUE`/`CHAR` 等）。

**明确不支持**：`[SKILL:…-formula.md:12, 841-845]`「仅支持四则运算 + 本文档列出的函数，**不支持取模 `%`、三元表达式 `?:`**」、「本文档未列出的任何函数」也不支持。

**对本设计的意义**：可以用公式字段做「**距今天数**」（`DATEDIF(开始时间, TODAY(), "D")`）、「**是否超期**」（`IF(AND(完成时间 < TODAY(), 状态 <> "已完成"), "超期", "正常")`）、「**各事项进展条数**」（`[进展表].FILTER(cur.事项 = 当前记录.事项).事项.COUNTA()`）、「**该事项最新进展日期**」（对进展表日期列取 `MAX()`）。

### 2.7 Q8 — 字段与记录的变更面、限额

#### 2.7.1 字段

| 操作 | 支持？ | 依据 |
|---|---|---|
| 新增 | ✅ `fields add`（传 `field_title` + `field_type` + `property_xxx`） | `[SKILL:…-edit.md:213-219]` |
| **重命名** | ✅ `fields update` 传 `field_title` + `field_type`（必传）+ `new_field_title`（可选） | `[SKILL:…-edit.md:218]`；`[CLI-DOC] OaField.new_field_title` |
| **删除** | ✅ `fields delete`（只需 `field_title`） | `[SKILL:…-edit.md:219]`；`[SKILL:…-edit.md:202]` |
| **重排（列顺序）** | ❌ **无重排 API**；列顺序 = 添加顺序 | `[SKILL:…-edit.md:554]`「字段添加顺序：系统按添加顺序排列，建议按业务逻辑顺序依次添加」；`col_infos` 只有宽度（§2.3.2） |
| 修改属性 | ✅ `fields update` 可传 `property_xxx` | `[SKILL:…-edit.md:218]` |
| 与子表一起建 | ✅ `create` / `sheets add` 时传 `fields` 初始化 | `[SKILL:…-common.md:55-62]`；`[SKILL:…-edit.md:130]` |

约束：**字段名在同一子表内不可重复**（`[SKILL:…-smartsheet.md:63]`）；**删除时至少保留一个文本类型字段**（`[SKILL:…-edit.md:551]`）；**新增字段后必须立刻调列宽**（`[SKILL:…-edit.md:41, 223-225]`）。

#### 2.7.2 记录

| 操作 | 支持？ | 依据 |
|---|---|---|
| 批量新增 | ✅ `records add`，单次 1–2000 条 | `[CLI-DOC] OaSmartSheetBatchUpdateRecordsReq.records`（`@minItems 1 @maxItems 2000`）；`[SKILL:…-edit.md:251, 258]` |
| 批量更新 | ✅ `records update`，传 `record_id` + `values` | `[SKILL:…-edit.md:256]` |
| 批量删除 | ✅ `records delete`，只需 `record_id` | `[SKILL:…-edit.md:257]` |
| 增删改混批 | ✅ 单次请求的 `type` 取 `add`/`update`/`delete` | `[CLI-DOC] OaSmartSheetBatchUpdateRecordsReq.type` |

> ⚠️ **文档内部不一致（需注意）**：`[SKILL:…-edit.md:44]` 写「`records update` 对单次更新的记录**无数量限制**，任何记录更新操作必须一次完成，**严禁**拆分请求」，而同一文件 `:251` 与 `[CLI-DOC]` 的 schema 都写 `@maxItems 2000`。**以 schema 的 2000 为硬上限**；`edit.md:44` 那句更像是「不要人为拆小批次」的纪律性表述。

#### 2.7.3 与本次改版直接相关的限额

| 限额 | 值 | 依据 | 对本次设计的含义 |
|---|---|---|---|
| **单子表记录数** | **最多 20000 条** | `[SKILL:…-edit.md:558]`「单表限制：单个子表最多 20000 条记录、150 个字段」 | 39 事项 × 30 天 ≈ 1170 行，**余量充足** |
| **单子表字段数** | **最多 150 个** | 同上 | 目标版式十余列，**余量充足** |
| 一次 `records add/update` | 1–2000 条 | `[CLI-DOC]` / `[SKILL:…-edit.md:251]` | 1170 行一次即可写完；超出按 2000 拆分 |
| `create` 初始字段 | 0–100 个 | `[CLI-DOC] SmartSheetCreateReq.fields`（`@maxItems 100`） | — |
| `sheets/fields` 单次字段批 | 0–150 个 | `[CLI-DOC] OaSmartSheetBatchUpdateSchemaReq.fields`（`@maxItems 150`） | — |
| `records list` 读取 | `limit` ≤ 1000，且 **`limit × 返回列数 < 10000`** | `[SKILL:…-read.md:285]` | 15 列时单次 ≤ 666 行，需 `cursor` 翻页（`next_cursor`） |
| `fields/records/views/charts list` | `limit` ≤ 1000 + `cursor` | `[SKILL:…-read.md:345, 367, 388]` | — |
| `records query` SQL 数组 | 1–20 条 | `[CLI-DOC] OaSmartSheetQueryDataBySQLReq.sql` | — |
| `views add/update/delete` 单次 | 1–20 个视图 | `[CLI-DOC] OaSmartSheetModifyViewReq.views`（`@minItems 1 @maxItems 20`） | — |
| 公式跨表聚合读取 | **超 1000 行的数值汇总不支持**（须落到公式字段） | `[SKILL:…-read.md:64]` | 大数据量统计走公式字段 |

### 2.8 Q9 — 一个子表能否同时存在多种类型的视图

**结论：能。**

**证据 A（API 形态）**：`[CLI-DOC] interface OaSmartSheetModifyViewReq { docid; sheet_id?; sheet_title?; type?; views: OaViewParam[] }`，其中 `views` 为数组（`@minItems 1 @maxItems 20`），且 `OaViewParam` 同时包含 `view_type`（新增时必传）、`view_id`（更新/删除时必传）、`view_title`、`property`、`property_gantt`、`property_calendar`、`col_infos`。同一 `views` 数组里可以混放不同 `view_type` 的项（结构上是同一种类型，语义上无冲突限制）。

**证据 B（读取）**：`[CLI-DOC] OaSmartSheetGetDataTypedRsp { views?: OaView[]; views_count?: number }`，`[SKILL:…-read.md:353-368]` 的 `views list` 返回指定子表的**视图列表**（带 `limit`/`cursor` 分页）。

**证据 C（隐含约束反证）**：`[SKILL:…-edit.md:13]`「由于智能表格**至少需要保留一个子表、一个字段、一个视图**，所以执行删除操作前必须先……确认对应资源的数量」——「至少一个视图」这一下限只有在「一个子表可容纳多个视图」时才有意义。

**证据 D（视图类型不可变）**：`[SKILL:…-view-types.md:19]`「`smartsheet views update` 时……**不支持修改视图类型**，只能修改同一视图下的标题和属性（如筛选、排序、分组等），不能将一种视图类型改为另一种（例如不能把表格视图改为看板视图）。如需更换视图类型，只能先删除旧视图再新增新视图」。

**对本设计的意义**：可以在同一子表上并存「表格视图（按六大模块分组，按日筛选）」+「甘特视图（绑定开始/完成时间）」+「看板视图（按状态分泳道）」+「日历视图（绑定某一天字段，看每日进展）」，这恰好覆盖「同一份数据、多种切面」的诉求。

### 2.9 Q7 — 导入路径（xlsx → 智能表格）

**结论：能导入 xlsx；但「源文件里的合并单元格会怎样」在一手资料中完全没有说明。**

**接口** `[CLI-DOC]`

```
interface SmartSheetImportReq {
  /** 支持文档的 docid 和 url ，有传则代表导入追加到对应智能表上，跟原有子表名称重复要做重命名；
      仅 doc_type=sheet/smartsheet 生效，其它类型忽略 */
  append_doc_id?: string;
  content_path?: string;   // 隐藏别名，与 media_id 二选一
  media_id?: string;       // 与 content_path 二选一
  /** 智能表格名称，映射到 doc/import 的 file_name（broker 自动追加 .xlsx 后缀） */
  name: string;            // @minLength 1 @maxLength 251
  passwd?: string;         // 文件密码
}
```

返回 `[CLI-DOC] OaDocImportTaskCreateTypedRsp { docid, task_id, task_status: "succ"|"fail"|"processing", url }` —— **导入是异步任务**。

**流程约束**：`[SKILL:…-common.md:31, 111]`「导入只接受 `media_id`」——若只有本地文件路径，**必须先**用 `wecomcli-media.md` 的上传接口换 `media_id`，再调 `smartsheet import`；`content_path` 在 CLI schema 里标注为 `@hidden true`（兼容模型传 `content_path` 字段名）。`[SKILL:…-common.md:78]` 写明支持 `.csv` / `.xls` / `.xlsx`。

**合并单元格的处理**：`[CLI-DOC]` 的 `SmartSheetImportReq` 与 `OaDocImportTaskCreateTypedRsp` **没有任何关于合并/样式/公式的字段**；`[SKILL:…-common.md:76-104]` 与 `[SKILL:…-edit.md:24]` 对 import 的描述只有「导入 xlsx 创建智能表格」与参数表；`[CLI-SCHEMA]` 的方法描述同为一句「导入 xlsx 创建智能表格」。**全库检索 `wecomcli-smartsheet-*.md` 中的「合并 / merge」零命中**（唯一命中的「合并」是 `LISTCOMBINE` 公式函数与「合并作答」等无关措辞）。

> **明确标注：xlsx 导入对合并单元格的处置策略（拍平 / 保留 / 报错）——未在一手资料中说明。**
> 但可以**确定**（而非推测）：**合并不可能被保留为合并**，因为目标模型没有合并原语（§2.1）。导入后合并区域只会表现为「若干个普通单元格，各自持有一个值」。

**导入路径对本设计的评价**：若源 xlsx 是「带合并单元格的人力进度表」，`import` 会把它拍平成一张**列名取自首行、每行独立**的表——**这正好是本设计想要的扁平结构**（合并区域会被重复读成同一批值）。但由于处置策略未文档化，**不应把 import 当作保真转换手段**；更稳妥的是「`create` 建结构 + `records add` 批量灌数据」（§2.7）。

### 2.10 Q5 补充：SQL 侧的跨表能力

`records query` 支持跨子表 JOIN（只读）：`[SKILL:…-read.md:256-262]` 给出 `FROM <表1> AS 任务表 JOIN <表2> AS 项目表 ON 任务表.项目编号 = 项目表.项目编号` 的跨表统计示例，条件与数据源均用字段名 / 子表名。**但** `[SKILL:…-read.md:266-272]`：`records query` **要求当前用户拥有智能表的全部权限**，否则返回 `errcode=538005`，须降级用 `records list`（仅支持基础筛选/排序/分页，不支持 JOIN/聚合/TopN）。

---

## 3. 对目标版式的能力判定汇总

| # | 目标诉求 | 判定 | 依据 | 落地约束 |
|---|---|---|---|---|
| 1 | 避免单元格合并 | ✅ **天然满足**（无需任何规避手段） | §2.1 | 智能表格零 merge 原语；用「分组 + 条件填色」制造视觉分段 |
| 2 | 六大模块 → 人/流程/成本 → 具体事项 → 分项 → 分项简介 | ✅ | §2.2 | `text` / `single_select`；层级用视图 `group_spec.groups`（多字段列表）呈现；**嵌套深度未文档化** |
| 3 | 最新进展（日期 + 进展内容） | ✅ | §2.2 | `date_time`（值必须 `YYYY-MM-DD HH:mm:ss`）+ `text` |
| 4 | 开始时间 / 完成时间 | ✅ | §2.3.3 | `date_time`；**甘特视图直接绑定这两列** |
| 5 | 周计划块按天逐行、与当天进展行 1:1 | ✅ **必须用长表** | §2.4 | 每天 = 一条记录；39×N 行 ≪ 20000 行上限 |
| 6 | 责任人 | ✅ | §2.2 | `user`，值 `[{"userName":"张三"}]`（失败再换 `userId`） |
| 7 | 负责人类型 | ✅ | §2.2 | `single_select` + `property_single_select.options` |
| 8 | 协调事项 | ✅ | §2.2 | `text`（长度上限未文档化） |
| 9 | 多视图并存（表格 + 甘特 + 看板 + 日历） | ✅ | §2.8 | 同子表可并存；**视图类型创建后不可改** |
| 10 | 透视（pivot）视图 | ❌ **不存在** | §2.3.1 | ViewType 枚举无 pivot；用仪表盘图表替代 |
| 11 | 一个单元格里放多天的进展数组 | ❌ | §2.4 | 无嵌套结构；`text` 手工拼接是下策且长度上限未知 |
| 12 | 事项与进展分表并关联 | ✅ | §2.5 | `reference` / `two_way_link_records` / `lookup` |
| 13 | 自动算「距今天数 / 是否超期 / 各事项进展条数」 | ✅ | §2.6 | `formula`；函数白名单，不支持 `%` 与 `?:` |

---

## 4. 一手资料**未能**回答的问题（不猜测，如实列出）

1. **xlsx 导入时合并单元格的处置策略**（拍平 / 保留 / 报错）——`[CLI-DOC]` `SmartSheetImportReq`、`[SKILL:…-common.md]`、`[SKILL:…-edit.md]` 均无相关描述。
2. **`group_spec.groups` 多字段是否渲染为多级嵌套分组、嵌套深度上限**——只说明是「参与分组的字段列表」（`[SKILL:…-view-types.md:188]`）。
3. **字段列顺序能否被 API 改写**——`col_infos` 只暴露 `field_id`/`field_title`/`width`（`[CLI-DOC] OAViewColInfos`），无 order/index；列序只由添加顺序决定（`[SKILL:…-edit.md:554]`）。
4. **`text` 字段的最大长度 / 是否自动换行**——`[SKILL:…-record-values.md:9]` 只给格式，未给长度上限。
5. **单个子表可容纳的视图总数上限**——只有单次请求 1–20 的批量约束（`[CLI-DOC]`），无总量上限。
6. **智能表格 UI 层面是否存在手工合并/跨列操作**——CLI 文档只描述 API 能力，UI 行为未覆盖；本文件的所有结论限于 API/模型层。
7. **导入后子表名冲突的具体重命名规则**——`[CLI-DOC]` 仅说明「跟原有子表名称重复要做重命名」，未给规则细节。
8. **甘特视图是否支持依赖关系 / 里程碑 / 进度百分比条**——`[CLI-DOC] OaGanttViewProperty` 只有起止日期四字段，无其它属性。

---

## 5. 复现命令（只读，可直接重跑核验）

```bash
wecom-cli --version
wecom-cli smartsheet --doc > /tmp/doc.txt        # 1678 行服务文档
wecom-cli smartsheet --schema                     # 26 个方法的 JSON Schema
wecom-cli smartsheet <create|get|import|charts|fields|files|images|records|sheets|views> --help
wecom-cli smartsheet <method> --schema            # 单方法 schema
wecom-cli sheet --doc | grep -n -i "merge\|合并"   # 对照：在线表格有 merge 资源，智能表格没有
grep -ci merge /tmp/doc.txt                      # → 0
grep -rn "合并\|merge" ~/.dsh/skills/wecom-unified/references/wecomcli-smartsheet-*.md
```

> 本次调查**未**调用任何写命令；上述命令全部为 `--doc` / `--schema` / `--help` 与文本检索。
