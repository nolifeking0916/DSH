# DSH

这是唯一的第一方私有集中仓，也是所有第一方 Git 同步的唯一目的地。

- 远端：https://github.com/nolifeking0916/DSH
- 原则：一个权威仓、每个中央路径只有一个写入方、远端回读通过才算同步完成。
- OpenViking 语义副本是独立知识检索层，不是第二个 Git 目的地。

## 集中布局

| 中央路径 | 内容 |
|---|---|
| hr-knowledge/ | 原 hr-knowledge 的完整跟踪树；旧同步器的语义同步模式也保留在此 |
| packages/dsh-context-injection/ | 原 dsh-context-injection 仓 |
| apps/hr-progress-table/ | 原 hr-progress-table 独立仓的已批准内容 |
| docs/migration/sources/hr-data-center/ | 原远端占位仓的留痕 |
| docs/migration/sources/DSH-output-hub/ | 原产出台说明与配置留痕 |
| dsh-workspace/、manifests/ | 已通过总账、来源和敏感门的 DSH 产出 |
| work/assessment-kit/ | 已按白名单提取并验证的本地测评代码与构建件 |
| scripts/central-sync/ | 中央同步、投影、检查和测试代码 |

DSH 原有根目录与其余主题继续保留，不因集中化而改名或重写历史。

## 同步边界

- 所有启用的 Git 同步只写 nolifeking0916/DSH。
- 原 hr-knowledge 与 DSH-output-hub 的 Git 写入已停止；旧仓只归档，不继续承载新同步。
- 源文件消失不会自动删除中央副本；改名须同 SHA-256 且一对一映射，否则阻断。
- 远端出现非本机新提交、敏感信息、身份冲突或大文件阻断时，不自动强推。
- 三个第三方 fork 不并入；本地 hr-data-hub 因归属与明文凭据问题另案处理。

详见[中央同步运行手册](docs/runbooks/dsh-central-sync.md)和[集中化 OpenSpec 变更](openspec/changes/consolidate-dsh-monorepo-20261113/proposal.md)。
