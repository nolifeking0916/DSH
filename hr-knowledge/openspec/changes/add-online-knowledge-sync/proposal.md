# Proposal: 私有在线知识同步

## Why
既有 HR 文档散落在工作仓，人类缺少统一编辑、版本评审和云端检索入口；直接全量上传会混入人员明细、密钥和原始导出。

## What Changes
- 使用 OpenKnowledge 桌面版维护专用仓中的 Markdown。
- 使用 OpenSpec 管理规格和变更，私有 Git 保存正本。
- 使用带敏感信息门的本机同步器，每五分钟同步白名单目录到 OpenViking 共享 Resources。
- 云端报告只进仓外待审区，禁止自动回写；本地删除不触发云端删除。

## Impact
仅影响专用知识仓、其私有 Git 远端和 viking://resources/hr-knowledge/；不改业务数据库、企微后台或既有工作仓。
