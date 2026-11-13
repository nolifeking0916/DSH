---
title: 目录属性与文件标签
description: 说明知识仓目录属性、文档元数据和原件保护边界。
tags: [ 主题-系统运维, 类型-运行手册, 状态-使用指引, 检索-OpenViking, 格式-MD ]
category: 系统运维
document_type: 运行手册
lifecycle: 使用指引
search_scope: OpenViking
type: note
---
# 目录属性与文件标签

更新时间：2026-11-10（Asia/Shanghai）

## 补全方式

- 目录使用 OpenKnowledge 原生的 `.ok/frontmatter.yml`，记录标题、说明、主题、状态、检索边界和文件数。
- 本仓自行维护的导航、运行手册和阅读入口使用 Markdown frontmatter，正文不变。
- 迁移原件、证据留痕、语录副本、Office/PDF 和规格文件不为贴标签而改写；它们的标签统一保存在 `scripts/metadata-catalog.json`，随私有 Git 版本化。
- 标签只依据路径、格式和可读取文本，不推断讲话人身份，不把“当前阅读”误写成“制度现行有效”，不替代业务裁定。

## 标签口径

- `主题-*`：如干部管理、职代会、招聘配置、薪酬绩效。
- `类型-*`：如制度通知、表单模板、报告清单、校验留痕。
- `状态-*`：如当前阅读、定稿产出、工作草稿、历史留档、语义副本。
- `检索-*`：OpenViking 或私有 Git；这不是对外公开级别。
- `格式-*` 与 `日期标记-*`：来自扩展名和文件名日期，不伪造文件真实成文日期。

## 维护与验收

```bash
python3 scripts/enrich_metadata.py --apply
python3 scripts/enrich_metadata.py --check
```

执行前需在 OpenKnowledge 打开本仓。脚本先读目录再合并缺失属性，保留已有字段；对原生 Markdown 只补丁缺失的 frontmatter。首次完整哈希和正文哈希保存在仓外 `review-inbox/metadata-enrichment-20261110/`，用于复核“原件未改、正文未改”。
