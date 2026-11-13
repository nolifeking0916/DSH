# online-knowledge-sync Specification Delta

## ADDED Requirements

### Requirement: 私有正本与人工评审
系统 SHALL 以专用本地 Git 仓为文档正本，并推送到私有远端；OpenViking 生成内容 SHALL NOT 自动回写正本。

#### Scenario: 云端报告返回
- **WHEN** OpenViking 生成摘要或报告
- **THEN** 报告仅进入仓外待审区，人工评审后才可进入 Git。

### Requirement: 上传前敏感信息门
系统 SHALL 在 Git 提交和云端导入前扫描白名单文档；发现密钥、人员敏感明细或不支持的格式时 SHALL 阻止本次同步并记录相对路径与原因。

#### Scenario: 检测到受限内容
- **WHEN** 任一候选文件命中敏感信息规则
- **THEN** 不执行 Git 推送或云端导入，状态为 blocked。

### Requirement: 原件与检索副本分流
私有 Git SHALL 保存通过安全门的 Office/PDF 原件；OpenViking SHALL 仅接收 docs、openspec、migration 及入口文件中的可检索文本，Office/PDF 的检索入口使用仓内 Markdown 语义副本。

#### Scenario: 二进制定稿进入后续产出
- **WHEN** 接收器取得通过安全门的 DOCX/PPTX/XLSX/PDF 定稿
- **THEN** 原件只进入私有 Git，已有或新增的 Markdown 语义副本进入 OpenViking，不把二进制目录提交给云端解析。

### Requirement: 增量更新且不自动删除
系统 SHALL 跳过内容未变化的根目录，并按相对路径去掉扩展名后的精确 URI 逐文件重导入新增或修改内容；目录级增量同步 SHALL 以已核对的云端/Git 共同基线为起点。检测到本地删除时 SHALL 报告并跳过该根目录，不自动删除云端资源。

#### Scenario: 目录已有内容需要更新
- **WHEN** 当前文件 SHA-256 与成功基线不同
- **THEN** 仅上传变化的文件到其精确 URI，不执行整目录重导入，不创建同内容的新入口。

#### Scenario: 文件未变化
- **WHEN** 根目录文件路径及 SHA-256 与上次成功状态一致
- **THEN** 跳过上传。

#### Scenario: 文件被删除
- **WHEN** 当前清单缺少上次成功同步的文件
- **THEN** 状态为 fail，原因是 deletion_requires_manual_review。

### Requirement: 可验证在线结果
每次同步 SHALL 保存 Git 远端 commit、OpenViking task id、root URI 和错误；验收 SHALL 包含云端检索、正文回读及至少一个原件的 SHA-256 对比。

#### Scenario: 命令提交成功但处理失败
- **WHEN** 异步任务失败或含 failed_files
- **THEN** 同步状态为 fail，不更新成功基线。
