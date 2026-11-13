# OpenKnowledge 在线知识库验收

验收日期：2026-11-09（Asia/Shanghai）

## 结论

专用知识仓、私有 Git、OpenViking 检索副本、后续定稿接收和每 300 秒定时同步已完成真实运行验收。原始工作区未改写，云端未执行自动删除。

## 安装与桌面

- OpenKnowledge：0.89.3，Developer ID 签名与公证检查通过；桌面已实际打开 `hr-knowledge`，不是仅检查进程。
- OpenSpec：1.16.1；`add-online-knowledge-sync` 严格校验通过。
- OpenViking CLI：0.5.1；`ov health` 与配置认证通过。
- OpenKnowledge `ok status --json`：server/ui 均 alive。`ok config validate` 通过。
- 最终 `ok lint docs --json` 与 `ok audit docs --json`：fileCount=132，errorCount=0，warningCount=0。

## 本地迁移与安全门

- 首批策选源文件 160 件：迁移 147 件、暂缓 13 件，生成 206 个仓内目标；独立回读原始目标 162 件、Markdown 语义副本 44 件，错误 0，敏感命中 0，暂缓件泄漏 0。
- 后续定稿接收是独立批次：递归候选 55 件，仓内已有/本次新增合计 36 件，拦截 19 件；最近一次新增 6 件、12 个目标，全部源文件 SHA-256 前后不一致 0 件。两个批次不相加冒充“全部文件”。
- 最终发布路径安全门：file_count=245，blocked_count=0。被拦截的人员敏感件、同名不同内容冲突件均未复制或上传。
- 单元测试 6 项全部通过，覆盖二进制源文件不变、语义目标、精确 URI、变化文件识别、删除拦截、原件/检索副本分流。

## 私有 Git 与原件哈希

- 私有远端：`https://github.com/nolifeking0916/hr-knowledge`。
- 定时服务真实运行后的本地 HEAD 与 origin/main 均为 `5cf01e3a4b12eaf97acb1d33a5aafbb1155bd5bb`，remote_verified=true。
- 原件 `outputs/旧件留档/职代会代表选举办法-2026-10-28.final.docx`：
  - 本地 SHA-256：`717d6ae6f3880d73a23b0a5ac2cfa6afc9730ad6c5fd0c64384e545e6768c62a`。
  - origin/main 中该文件 SHA-256：`717d6ae6f3880d73a23b0a5ac2cfa6afc9730ad6c5fd0c64384e545e6768c62a`。
- Office/PDF 原件只进入私有 Git；OpenViking 使用对应 Markdown 语义副本，不送二进制目录解析。

## OpenViking 云端

- 首次成功 docs 任务 `027f648d-1fdf-487b-a9f2-c7c140774447` 的 119 个 processed_files 与 Git 基线 `6afc8c243cc3491380591a3a14523b59443602f7` 的 119 个 docs 路径逐一相等，已建立内容 SHA-256 增量基线。
- 后续逐文件全链路任务对应 Git `e2e950fd04890270dbf9d91cb415a5277fb02323`：docs 15 件、openspec 2 件、migration 1 件，共 18 个任务全部 completed，failed_files 为空，最终 errors=[]。
- `docs/README` 云端已回读到“递归扫描 55 件候选、仓内 36 件、拦截 19 件”；该精确 URI 下只有一个正文入口，未制造新的重复入口。
- 新增嵌套历史件 `docs/evidence/nested/旧件留档/职代会代表选举办法-2026-10-28.final` 云端分 3 段，正文及上述 source_sha256 均可回读。
- 新定稿来源说明 `docs/evidence/final/认知上行-2026-11-09.provenance` 可回读；Markdown 表格由云端规范化为 KBTable，文字内容可读，不把格式转换误称为原件字节相同。
- 旧的目录级增量曾因 duplicate record id 失败，已改为逐文件精确 URI；失败任务不写成成功，已取消的 Office/PDF 目录任务不计入在线验收。

## 定时服务

- LaunchAgent：`com.uu1.hr-knowledge-sync`，StartInterval=300，RunAtLoad=true。
- 真实运行记录：2026-11-09T09:44:55Z 开始，2026-11-09T09:45:00Z 完成；status=pass，Git 远端核验通过，uploaded=[]，所有知识根目录 unchanged，errors=[]。
- launchctl 最后退出码 0。互斥锁会跳过并发实例；本地删除只报告，不自动删除云端。

## 保留事项

- 首批 13 件与后续定稿 19 件仍需脱敏或冲突复核；未宣称 3,195 个文档候选全部上线。
- 早期试验多余入口 `viking://resources/hr-knowledge/README.md/` 保留待维护者明确确认后清理；现行入口为 `viking://resources/hr-knowledge/README/`。
- OpenViking 生成内容仍须先进入仓外待审区，人工评审后才可回 Git；禁止自动双向覆盖。
