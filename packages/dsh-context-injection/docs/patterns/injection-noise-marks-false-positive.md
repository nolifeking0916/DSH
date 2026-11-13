# 注入去重守卫的噪声标记会误伤「提到标记本身」的用户消息

**症状**：某一轮没有注入块，日志里是 `skip: no user message (step=1)`，而这一轮的会话确实是新会话。

**根因**：注入插件判定「这条消息是不是插件自己注入的块」时，看的是消息文本里有没有噪声标记串：

```js
const NOISE_MARKS = ['<memos_context>', '<skill_context>', '<context_inject>', 'Current runtime context'];
```

于是——**用户消息里只要出现这四个串中的任意一个，就会被判成「已注入块」而跳过**，该轮不注入。

**实测**：让子代理去「把上下文里的 `<context_inject>…</context_inject>` 块原样贴出来」，这个验证动作本身让那一轮**没有注入块**——提示词里写了 `<context_inject>`，被守卫误判。同批里提示词不含标记串的子代理，注入块照常存在。

**教训**：

1. **验证注入是否发生时，别在提示词里写注入块的标记串**，否则验证会自我否定。正确做法是让子代理「描述你看到的注入内容结构（几段、每段几条）」，或直接查插件日志的 `inject:` 行与会话存根里的 `source.kind=context-inject` 记录。
2. 这条守卫本身是对的（防止把插件自己的输出再当输入重复注入），代价是**关键词敏感**：用户真要讨论「context_inject 这个块」时，那一轮没有注入。

**查证路径**：插件日志 `/tmp/context-inject.log`（`pre-step: step=… claimed=…` 与 `inject:` 行）→ 会话存根 `~/.dsh/sessions/<工作区>/<sessionId>/session.v4.jsonl.zstd`（`zstd -dc` 后搜 `以下为经验库、技能索引与历史记忆` 与 `kind":"context-inject"`）。

**出处**：`nolifeking0916/dsh-context-injection`（独立仓库）迁移验证时踩到；见 `docs/spec.md` §6「已知缺口」。
