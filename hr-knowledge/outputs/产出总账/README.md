---
title: DSH 全盘 AI 产出总账
description: DSH 主账的脱敏汇总；完整路径仅在本机，OpenKnowledge 跟从展示。
tags:
  - 主题-系统运维
  - 类型-产出总账
  - 状态-自动生成
category: 系统运维
document_type: 产出总账
lifecycle: 自动生成
search_scope: 私有Git
type: note
---

# DSH 全盘 AI 产出总账

> 本页由 DSH 总账生成；OpenKnowledge 跟从展示。完整源路径和原始回执只保存在本机状态区。

- 总账指纹：3c73754b271c54c6a1b62a20484dbb72ecb965284368470b986cc835c5d326e7
- 本轮候选：24138 件
- 唯一 artifact：18860 个
- 文件身份匹配：24135 件；其中移动/改名：0 件；唯一哈希关联：0 件
- 哈希缓存命中：11179 件；读取错误：0 件
- 原件策略：只读发现，不移动、不删除、不改名。

## 接收状态

| 状态 | 文件数 | 含义 |
|---|---:|---|
| already_in_knowledge | 2736 | 知识仓已有同内容，不重复收录 |
| eligible_reviewed_intake | 28 | 来源明确，可进入安全接收复核 |
| held_binary_review | 2064 | 图片等二进制内容需人工查看 |
| held_changed_version | 2 | 内容变化，不能静默覆盖旧接收版 |
| held_cloud_not_local | 12956 | iCloud 占位文件，只登记，不触发下载 |
| held_origin_review | 6351 | AI 来源未确认，等待人工判断 |
| held_sensitive_path | 1 | 路径显示可能敏感，默认留在本地 |

## AI 来源分级

| 级别 | 文件数 |
|---|---:|
| confirmed | 522 |
| probable | 150 |
| unknown | 23466 |

## 边界

- confirmed 仅表示路径和成果标记能证明来自 DSH 定稿/回执区，不证明业务内容已获维护者放行。
- unknown 不是非 AI，而是没有足够证据，不会擅自上传。
- 自动接收开关首扫保持关闭；清单确认后再按安全门接入。
- 详细文件身份与路径在本机 SQLite 总账，不在本页暴露。

[查看待确认清单](./待确认清单.md)
