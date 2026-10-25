# 候选人页产物 · 修复说明（2026-10-25 13:2x）

这一份 `index.html` 是从 `build_candidate.py` 的产物**手工修过**的三处构建缺陷。
修的是**产物**，不是构建脚本 ⇒ **下一次跑 `build_candidate.py` 仍会产出坏页面（整页空白）**，脚本本身要按下面三条修。

| # | 症状 | 根因 | 修法 |
|---|---|---|---|
| 1 | `Uncaught ReferenceError: __CLOUD_ON__ is not defined`（app.js 加载即抛错 ⇒ 全页空白） | 构建脚本只替换了 `__ENDPOINT__`，没替换 app.js 里的 `__CLOUD_ON__` / `__CLOUD_ENDPOINT__` 两个占位符 | 构建时一并替换：`__CLOUD_ON__` → `true`，`__CLOUD_ENDPOINT__` → 网关路由地址 |
| 2 | `Uncaught SyntaxError: Unexpected string`（`esc()` 里的单引号键被写成三个双引号 ⇒ 整个 app.js 块语法错误） | 构建脚本 `kb.SHELL.replace(old, new)` 的整段替换把 `esc()` 的引号键弄坏了 | 构建后断言产物里存在单引号键、且不存在三个连续双引号；或改成「先切脚本块、再逐块替换」 |
| 3 | `Uncaught SyntaxError: Invalid Unicode escape sequence`（`"网络异常：\u" +` ⇒ 交卷上报脚本整块不解析 ⇒ **交卷不写库**） | `cloud/candidate_runtime.js` 里的孤立 `\u` 转义 | **已修源码**（`cloud/candidate_runtime.js`：改成 `"网络异常：" +`） |

修完后的验证：Chrome headless 渲染**控制台 0 报错**、页面正常出内容。

**另外建议**：把「去答案键」这一步并进 `src/build.py`（加 `--candidate` 开关），让**只有一条构建路径**，
避免两个脚本各自拼装同一个单文件。
