---
title: Word 阅读与 PDF 预览
description: DOCX 本质上是 ZIP/XML 容器，不是 UTF-8 纯文本。OpenKnowledge 可以渲染 PDF，但没有原生 DOCX 排版预览；对 DOCX 选择“View as text”会把 ZIP 字节当文字，于是出现 PK、[ContentTypes].xml 和乱码。这不表示原 Word 已损坏。
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

# Word 阅读与 PDF 预览

更新时间：2026-11-09（Asia/Shanghai）

## 为什么之前会乱码

DOCX 本质上是 ZIP/XML 容器，不是 UTF-8 纯文本。OpenKnowledge 可以渲染 PDF，但没有原生 DOCX 排版预览；对 DOCX 选择“View as text”会把 ZIP 字节当文字，于是出现 `PK`、`[Content_Types].xml` 和乱码。这不表示原 Word 已损坏。

## 现在的阅读方式

- `assets/` 和 `outputs/` 下每份 DOCX 都配一个同名 PDF，点击 PDF 阅读。
- `.okignore` 只从 OpenKnowledge 文件树隐藏 DOCX 原始入口，避免再次误按“View as text”；没有删除或改写原 Word。
- DOCX 原件仍保留在本机和私有 Git，可用 Word/WPS 打开；正式版式、打印和签发仍以原 DOCX 为准。
- 已有同名 PDF 首次直接复用；缺少 PDF 的由 LibreOffice 生成阅读预览。PDF 是阅读副本，不反向覆盖 DOCX。
- `migration/word-preview-summary.json` 记录逐件 DOCX/PDF 哈希、页数和文本回读校验。

## 后续自动处理

同步器每次运行会检查 `assets/`、`outputs/`：新 Word 缺预览时自动生成，已有 Word 内容变化时重新生成 PDF；未变化的文件只核对哈希，不重复转换，也不因定时检查制造空提交。

手工执行（使用带 python-docx 的工作区运行时）：

```bash
/Users/leto/.dsh/dsh-runtimes/dsh-primary-runtime/dependencies/python/bin/python3 scripts/word_previews.py
/Users/leto/.dsh/dsh-runtimes/dsh-primary-runtime/dependencies/python/bin/python3 scripts/word_previews.py --check
```

生成器先验证 PDF 文件头、页数和可提取正文，再接受预览；文本比对允许分页页眉及表格换栏插入额外字符，避免把正常 PDF 误判为缺字。若转换或校验失败，同步整批停止，不隐藏失败事实，也不改写 Word 原件。

## 边界

LibreOffice 与 Word/WPS 的字体替换、分页和表格排版可能略有差异。PDF 用于解决阅读乱码，不替代秘书审校或正式版式验收。原 Word 的字节 SHA-256 在生成前后必须完全一致。
