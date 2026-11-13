# dsh-output-ledger Specification Delta

## ADDED Requirements

### Requirement: DSH 唯一产出总账

系统 SHALL 以 DSH 维护的本机 SQLite 总账作为 AI 产出发现、身份、位置和接收状态的唯一调度依据；OpenKnowledge SHALL 只展示总账派生视图，不另行裁定来源。

#### Scenario: 同一成果出现在不同目录

- **WHEN** 扫描发现相同设备/inode 或相同内容哈希的候选
- **THEN** 总账关联到既有 artifact，并登记位置关系，不无条件创建新成果。

### Requirement: 只读发现与来源分级

系统 SHALL 只读扫描配置的本地范围，不跟随符号链接，不扫描系统、依赖、缓存、密钥配置和知识仓自身；每个候选 SHALL 标记 confirmed、probable 或 unknown 的 AI 来源级别及理由。

#### Scenario: 无法证明是 AI 产出

- **WHEN** 文件只具备内容或路径信号，不能确认由 AI 生成
- **THEN** 状态为待确认，不标记为已确认 AI 成果，不自动上传。

### Requirement: 移动、版本和缺失跟踪

系统 SHALL 使用设备/inode、路径、SHA-256、mtime 和大小识别移动、改名、同内容副本和内容变化；旧位置消失 SHALL 只登记 missing，不执行删除。

#### Scenario: 文件移动后重新扫描

- **WHEN** 旧路径消失且相同 inode 或唯一哈希出现在一个新路径
- **THEN** 更新当前位置并保留历史位置与推断依据。

#### Scenario: 同路径内容变化

- **WHEN** 已登记文件的 SHA-256 改变
- **THEN** 追加内容版本；已有接收副本不被静默覆盖，进入待复核。

### Requirement: 敏感边界与展示

完整源路径和原始回执 SHALL 保存在仓外本机状态区；OpenKnowledge 中的总账摘要 SHALL 脱敏。图片、未知来源、受限人员材料、密钥候选和不支持格式 SHALL 默认待确认。

#### Scenario: 来源明确且安全的新定稿

- **WHEN** 候选来自确认的 DSH 定稿/回执位置，且文本提取与敏感门通过
- **THEN** 可复制到带 artifact 标识的私有 Git 目标，并生成可检索语义副本；源文件保持不变。

### Requirement: 可复算验收

每次扫描 SHALL 输出候选数、状态计数、重复/移动数、错误和哈希缓存统计；验收 SHALL 包含移动识别、重复去重、来源不明拦截、敏感内容拦截和源文件未改动测试。

#### Scenario: 扫描或接收失败

- **WHEN** 文件在读取期间变化、哈希不一致或目标冲突
- **THEN** 该候选进入 held，不更新其成功接收状态。
