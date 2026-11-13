---
title: DSH 全盘 AI 产出总账
description: DSH 负责发现、追踪和登记，OpenKnowledge 跟从展示；原件只读，来源不明和敏感材料不自动上传。
tags:
  - 主题-系统运维
  - 类型-使用指引
  - 状态-现行
category: 系统运维
document_type: 使用指引
lifecycle: 现行
search_scope: OpenViking
type: note
---

# DSH 全盘 AI 产出总账

## 谁做主

- **DSH 做主**：维护本机 SQLite 唯一总账，记录 artifact、位置、版本、哈希和来源证据。
- **OpenKnowledge 跟从**：显示知识仓里的脱敏摘要和已确认内容，不自行建立另一套接收结论。
- **Git**：保存私有正本和版本历史。
- **OpenViking**：只保存允许在线检索的语义副本。

## 全盘是什么意思

扫描桌面、文稿、下载、图片、公共目录、WorkBuddy、当前 DSH 工作区、iCloud Drive 和临时目录中的指定文档/图片扩展名。排除知识仓自身、依赖缓存、安装包、审阅暂存区及 macOS 照片图库内部派生内容。

“全盘发现”不是把整台电脑上传，也不是把所有候选认定为 AI 产出。外部磁盘、其他用户目录、尚未导出的应用内部数据不在默认范围。iCloud `dataless` 占位文件只登记路径，不读取正文、不触发下载；2026-11-10 正式首扫中有 12,970 件此类占位文件。

## 如何追踪文件下落

1. 同 device/inode：识别移动或改名，旧位置标为历史，不制造新成果。
2. 同 SHA-256：识别完全相同的副本；相同内容不重复接收。
3. 内容变化：记录新版本；已接收内容的变更不能静默覆盖。
4. 文件暂时不可见：记为 `missing_observed_not_deleted`，不据此删除原件或云端。
5. 硬链接：保留各实际位置，不误报移动或缺失。

## AI 来源与接收是两道门

- `confirmed`：路径和成果标记能证明来自 DSH 定稿/回执区。
- `probable`：来自 DSH 输出区但缺少定稿标记。
- `unknown`：路径不足以证明来源，等待人工判断。

来源分级不等于业务放行。图片、敏感路径、来源不明文件均只登记，不自动复制或上传。`auto_intake` 首轮保持关闭。

## 首轮实际结果（2026-11-10）

- 截至 2026-11-10 16:42（Asia/Shanghai）：24,261 个候选位置，归并为 18,950 个 artifact；候选位置不是 AI 成果数量。
- 12,970 个 iCloud dataless 占位文件只登记，不读取、不下载。
- 2,728 个位置与知识仓现有内容哈希一致，不重复接收；19 个位置可进入安全接收复核。
- 其余项目按来源、图片、敏感路径等状态留在本机待确认，不自动上传。

## 在哪里查看

- OpenKnowledge：`outputs/产出总账/README.md` 与 `待确认清单.md`，只显示汇总数量，不公开源路径。
- 本机完整总账：`~/Library/Application Support/hr-knowledge-sync/output-ledger.sqlite3`。
- 本机原始回执：同目录 `output-ledger-report.json`。二者不进入私有 Git 或 OpenViking。

## 检查与回退

```bash
python3 scripts/output_ledger.py --scan
python3 -m unittest discover -s scripts -p 'test_*.py' -v
```

停用 `com.uu1.hr-knowledge-sync` 可停止复扫；不改动任何原始文件。总账数据库、知识仓和原始工作区各自保留，不做自动删除。
