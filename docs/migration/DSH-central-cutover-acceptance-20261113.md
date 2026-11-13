# DSH 中央仓集中与统一同步验收回执（2026-11-13）

## 结论

六个第一方仓已集中到唯一私有权威仓 `nolifeking0916/DSH` 的 `main`；三个第三方 fork 未合并。中央 60 秒轮询与 300 秒兜底已启用，旧 DSH-output-hub 两个任务已停用并禁止随登录恢复，旧 hr-knowledge 任务只保留 OpenViking 语义副本，不再执行 Git 写入。

## 远端与独立克隆验收

- 集中化独立验收基线：`565ed7c97677e9ab9ab66a1b15eb37665cbf3d77`。
- 该时点独立克隆：863 个跟踪文件、53,971,681 字节；缺失文件 0、SHA-256 不一致 0。
- 19 项敏感新产出与 hr-progress-table 四项真实姓名文件均不在克隆中。
- 最终持续同步提交会随真实新增产出继续前进；最终远端回读以本机 `~/.dsh/state/dsh-central-sync/main-acceptance.json` 为准。

## 真实运行验证

- 中央全量同步：知识投影 434 件，产出投影 275 件；排除 19 项敏感新产出后通过。
- 新增验证：源知识仓新增无敏感信息的验证文档后，中央自动提交并推送。
- 失败恢复：将 origin 临时指向不存在的本地路径，产生本地提交 `659d0560221441ee652479ca951945c9115c98db`，推送按预期失败且工作区干净；恢复 origin 后，该提交已进入远端历史，后续恢复提交为 `db869b619269ce9f968ea1ac0a07ec5c5724fba8`。
- 同内容改名：`f7de6629dfa62b832a70098507580eff03008495` 通过；为避免语义副本把测试改名判为删除，再以 `794e10777e2665d69f49f1e0cba0b0def814f45e` 改回验证文件名。
- launchd 首轮：`22af6a08d9048db137be599f337eb4367342ba1c`，中央同步任务 exit 0，watch 持续运行。
- 语义-only：2026-11-13T04:43:23Z 回读 `status=pass`、`git.status=skipped`、`git.reason=openviking_only`、错误 0。

## 自动化测试

- 产出投影 7 案、知识投影 7 案、Git 执行 4 案、端到端 4 案、语义-only 1 案，共 23 案通过。
- 提取的 assessment 源码验证 10 项通过、0 失败。
- 最终集成安全扫描：阻断 0，超过 50/100MiB 均为 0；件数与字节以 STATE 的 final-integration-safety.json 当次回读为准。

## 旧仓处置

2026-11-13T04:39:07Z 已将以下五个旧第一方仓归档，均仍为 private：DSH-output-hub、dsh-context-injection、hr-data-center、hr-knowledge、hr-progress-table。MemOS、newsnow、TrendRadar 三个 fork 未动。

## 未纳入与待决项

- hr-progress-table 四个真实姓名文件仍未获私有到私有迁移批准，继续阻断。
- 19 项含真实姓名或人员路径的新产出已列入本机排除清单，源文件保留，中央不复制、不上传。
- 本地 hr-data-hub 不是六个远端第一方仓之一，且 README 有已提交明文凭据；未纳入，须另案脱敏与裁定。
- 两份既有 DSH 工作树的未审查未跟踪文件、个人/聚合报告、评分键与生成载荷未自动纳入。
- 源删除不会自动删除中央副本；删除、身份冲突、远端 ahead 与敏感命中均停止待审，不强推。
