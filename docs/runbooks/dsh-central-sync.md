# DSH 中央同步运行手册

## 1. 唯一目的地与运行目录

- 权威远端：私有 nolifeking0916/DSH，main。
- 中央工作树：/Users/leto/.dsh/DSH-central。
- 中央状态：/Users/leto/.dsh/state/dsh-central-sync。
- 同步代码：仓内 scripts/central-sync/。
- 旧 hr-knowledge 仓只保留 OpenViking 语义副本，不再执行 Git add/commit/push。

所有第一方 Git 同步只写 DSH；不同路径可以有不同投影器，但同一路径只能有一个写入方。

## 2. 每轮顺序

run_once.py 严格按以下顺序执行：

1. output_ledger.py --scan：刷新现有 DSH 产出总账；只有 status=pass 才能继续，锁竞争返回 skipped 也按本轮暂停处理。
2. project_knowledge.py --apply：读取 hr-knowledge 的 Git 跟踪文件及未被忽略的未跟踪文件，投影到中央 hr-knowledge/；尊重 .gitignore 与 .git/info/exclude，不读取本地缓存，不把删除当同步指令。
3. project_outputs.py --apply：从最新总账选择 eligible_reviewed_intake 与 already_in_knowledge，按 artifact 与 SHA-256 去重后投影到 dsh-workspace/、hr-knowledge/ 或 manifests/。
4. sync_online.py --git-only：再次执行中央安全扫描、删除/改名预审、remote-ahead 检查，然后只暂存中央脚本和 PUBLISH_ROOTS，commit/push 并回读 origin/main。

中央 Git 执行器不调用 OpenViking。语义同步由旧知识脚本以 --openviking-only --skip-scan --skip-intake 独立运行，不形成第二个 Git 目的地。

## 3. 调度

- com.uu1.dsh-central-sync：launchd 每300秒运行一次 run_once.py。
- com.uu1.dsh-central-watch：60秒轮询两个源根，内容或源HEAD变化时触发同一 run_once.py；无 fswatch 依赖。
- com.uu1.hr-knowledge-sync：中央验收后以语义-only参数重载；不得恢复旧Git推送。
- com.uu1.dsh-output-hub-sync 与 com.uu1.dsh-output-hub-watch：保持停止。

同一 run_once.py 由 fcntl 锁保证非重叠；60秒快路径与300秒兜底不能形成双写。

## 4. 安全与冲突门

- 密钥、受限路径、人员字段和真实姓名规则在复制前及Git前各检查一次。
- 精确豁免必须同时绑定中央目标路径和当前SHA-256；文件变化后豁免自动失效。
- 超过100MiB阻断；50MiB以上列入人工复核报告。
- 云端dataless、symlink、来源不明、同目标不同内容均默认阻断。
- 源删除不删除中央副本；只有同SHA一对一改名可自动允许。
- staged deletion必须为零；remote ahead必须为零，否则停止待审，不自动rebase、不强推。
- hr-progress-table四个真实姓名文件未获批准，保持阻断，不得用“目标也是私有仓”自行放行。
- STATE/excluded-targets.json 是逐件人工排除清单；排除只阻止新投影，不删除中央既有副本，也不伪装成源删除。
- 本轮已将19项含真实姓名或人员路径的新产出列入该排除清单；原始文件只留在本机，未进入中央仓。

## 5. 本地检查

在仓根执行：

- DSH_CENTRAL_STATE=/Users/leto/.dsh/state/dsh-central-sync/test python3 scripts/central-sync/test_projection.py
- DSH_CENTRAL_STATE=/Users/leto/.dsh/state/dsh-central-sync/test python3 scripts/central-sync/test_knowledge_projection.py
- DSH_CENTRAL_STATE=/Users/leto/.dsh/state/dsh-central-sync/test python3 scripts/central-sync/test_sync_online.py
- DSH_CENTRAL_STATE=/Users/leto/.dsh/state/dsh-central-sync/test python3 scripts/central-sync/test_run_once.py
- python3 scripts/central-sync/test_semantic_only.py

测试只使用临时目录、合成样例和本地bare仓，不触GitHub生产仓。

## 6. 状态与排障

- 每轮汇总：/Users/leto/.dsh/state/dsh-central-sync/run-once-last.json。
-  watcher日志：/Users/leto/.dsh/state/dsh-central-sync/watcher.jsonl。
- 知识投影报告：STATE下各profile的 knowledge-projection-report.json。
- 产出投影报告：STATE下 projection-report.json 与 output-allowed-renames.json。
- Git安全报告：STATE下 safety-report.json。

若状态为held/blocked/fail，先读报告；不得通过删报告、跳扫描或强推制造“成功”。断网造成的本地commit可在下一轮继续push，因为无新文件变化时也会执行远端核对。

## 7. 验收与回滚

验收必须同时满足：

- origin/main等于本地HEAD。
- 独立clone中的预期文件与中央工作树逐文件SHA-256一致。
- 旧Git写入任务停止，旧知识任务只运行语义-only。
- 新增、修改、改名、删除阻断、断网恢复、remote-ahead和敏感样例测试通过。

回滚时先停中央两个任务，保留旧仓归档与审计报告；不得以重新启用旧Git双写作为默认回滚。历史修正用新提交完成，不force-push。
