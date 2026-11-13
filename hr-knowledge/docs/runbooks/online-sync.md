---
title: 在线同步运行手册
description: LaunchAgent com.uu1.hr-knowledge-sync 每 300 秒运行一次 scripts/synconline.py。每次运行顺序为：
tags:
  - 主题-系统运维
  - 类型-运行手册
  - 状态-使用指引
  - 检索-OpenViking
  - 格式-MD
category: 系统运维
document_type: 运行手册
lifecycle: 使用指引
search_scope: OpenViking
type: note
---

# 在线同步运行手册

更新时间：2026-11-09（Asia/Shanghai）

## 两条在线链路

1. OpenKnowledge 桌面版编辑本仓 Markdown，OpenSpec 管理规格变更。
2. 同步器先执行安全门，再把本仓提交并推送到私有 Git：`https://github.com/nolifeking0916/hr-knowledge`。
3. 私有 Git 保存全部已接收原件，包括 Office/PDF；OpenViking 只导入可检索的 Markdown/文本/JSON/YAML 语义副本，目录为 `viking://resources/hr-knowledge/`。
4. OpenViking 生成的内容只能先进入仓外待审区，人工评审后才可进入 Git；禁止自动双向覆盖。

## 后续产出怎么进入

- 直接在本仓编辑：在 OpenKnowledge 中打开本仓，检查 diff 后由同步器自动提交。
- 旧工作区定稿：`scripts/intake_outputs.py` 递归接收 `/Users/leto/.dsh/bot/workspace/work/hr-data-center/outputs` 内含 `.final.`、`.receipt.`、`.provenance.` 标记的文件；嵌套历史件保留相对路径，语义副本放入 `docs/evidence/nested/`，不冒充现行定稿。
- 二进制定稿复制到 `outputs/`，其正文语义副本进入 `docs/current/final/`；回执和来源说明同时进入 `docs/evidence/final/`。
- 同名但内容不同的定稿进入人工复核，不覆盖旧定稿；人员个案、名单、薪酬明细、密钥和原始导出拦截，不上传。
- 其他输出目录中的指定材料：`scripts/reviewed_sources.json` 逐项登记源相对路径、目标路径和 SHA-256，`scripts/intake_reviewed_sources.py` 只复制哈希完全一致的已复核件。源文件变化或目标冲突会停止同步，要求重新复核；不整目录接收。此类目标只能放在 `outputs/`，因此只进入私有 Git，不进入 OpenViking 通用检索。
- 2026-11-10 管理原话任务的入口是 `outputs/管理原话-20261110/00-阅读入口.md`。首批只登记四份汇编/校验文档，不包含录音、转写原件和处理脚本；原件仍留在原工作区。

## 定时与安全门

LaunchAgent `com.uu1.hr-knowledge-sync` 每 300 秒运行一次 `scripts/sync_online.py`。每次运行顺序为：

1. DSH 全盘 AI 产出总账只读发现：按根目录、排除规则、文件身份、SHA-256 和来源证据登记；本机 SQLite 保存完整路径，知识仓只显示脱敏摘要。随后接收旧工作区的新定稿；
2. 为新增或变化的 DOCX 生成/更新同名 PDF 阅读预览，核对原件哈希不变；详见 `docs/runbooks/word-reading.md`；
3. 对全部发布路径执行敏感信息扫描，任一命中即整批停止；
4. 自动暂存白名单路径，提交并推送私有 Git，回读远端提交号；
5. 按内容哈希逐文件精确重导入变化的 Markdown/文本；Office/PDF 原件仅进私有 Git，不送入 OpenViking 解析；
6. 云端任务必须返回 completed 且失败列表为空，才记录同步状态；删除、冲突和超时均需人工处理。

当前 OpenViking CLI 的 `--watch-interval` 不接受本地路径，所以使用本机定时重导入，不能称为“本地目录 watch”。同步器不会自动删除云端资源。

### DSH 主账与全盘发现边界

- DSH 是主账，OpenKnowledge 跟从展示；Git 与 OpenViking 各自保留正本或语义副本，不反向覆盖原件。
- 来源不明文件只登记，不自动接收或上传；`confirmed/probable/unknown` 是来源证据分级，不是业务放行结论。
- 图片等二进制文件只登记，需人工看图/脱敏复核；源文件不移动、不删除、不改名。
- `Photos Library.photoslibrary` 内部派生图片不是 AI 产出候选，已排除；主动导出的图片仍需人工复核。
- 2026-11-10 修正前扩展名候选为 213,485 件，其中 Pictures 189,225 件，主要是照片图库派生内容；这不是 AI 产出数量，不能作为正式总账结论。

## 常用检查

```bash
python3 scripts/sync_online.py --check-only
python3 scripts/intake_outputs.py --check-only
python3 -m unittest discover -s scripts -p 'test_*.py' -v
ov health
ov task list
ok status
```

状态与原始回执保存在仓外 `~/Library/Application Support/hr-knowledge-sync/`，日志保存在 `~/Library/Logs/hr-knowledge-sync/`，密钥不写入仓库或命令参数。

## 已知处置

早期 URI 映射试验留下一个多余入口 `viking://resources/hr-knowledge/README.md/`。现行入口是 `viking://resources/hr-knowledge/README/`。未经维护者明确确认，不自动删除旧入口。

## 回退

停用 `com.uu1.hr-knowledge-sync` 即可停止新增同步；Git 正本和原始工作区不受影响。云端删除、覆盖恢复和共享范围变更必须单独审批。
