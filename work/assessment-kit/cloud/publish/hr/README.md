# 施测人汇总台（票 #45 · 施测人侧落地）

线上地址：<https://uu-one-d4gc4ot78a702cb70-1257197409.tcloudbaseapp.com/hr/>
（静态托管的 `/hr/` 路径，**不绑自定义域** —— 票 #36 Q5；平台会给默认测试域名加一层「页面访问提示」，点一次「确定访问」即可。）

## 这是什么

一张**只读**的汇总台：列出最近 N 份作答、按测评编号直达某一份、一键导出。

- 默认列（票 #36 Q3 原样）：姓名 / 测评编号 / 组 / 岗位层级 / 等级 / 提交时间 / 时长 / 未答题数。
  **身份证后 4 位不在默认列里**，只在接口返回与导出文件里（供这一轮人工核对）。
- **页面不展示逐题作答**（96 题一次都不进 DOM，也不进任何下载文件）。
- 本轮**没有鉴权**：任何拿到这个地址的人都能看全部结果并导出（维护者已知的取舍，票 #36 决议）；
  等被测对象变成外部候选人 / 公开链接分发时再开（票 #44）。
- 页面自己写明口径：不显示分数给候选人、报告只给施测人、不得作为唯一录用依据。

## 数据从哪来

三个接口，都由云函数算，页面只渲染（判据与计分在服务端，票 #38）：

| 用途 | 接口 |
|---|---|
| 列表 | `GET ?action=list&limit=N` |
| 一份的报告 | `GET ?action=export&code=…&src=hr` |
| 一批的汇总 | `GET ?action=export&scope=batch&limit=N&src=hr` |
| 离线分析管线用的 JSON | `GET ?action=export&scope=batch&limit=N&format=pipeline&src=hr` |

基址：`https://uu-one-d4gc4ot78a702cb70-1257197409.ap-shanghai.app.tcloudbase.com/api/assessment`

## 怎么改 / 怎么重新发布

```bash
python3 cloud/build_hr.py     # 构建 + 跑发布门（verify_hr_page.py）
```

发布门查六样：内嵌数据无答案键字段、136 条金丝雀（判据原文 + 推理题解析）一个字不出现、
零外链资源、**页面里没有逐题作答字段**、占位符已替换、headless Chrome 实跑无 JS 报错。

发布（静态托管）：

```bash
# 上传到 /hr/index.html（manageHosting action=upload，localPath + cloudPath）
```

## 已知限制

- **组 / 岗位层级是空的**：候选人页只收姓名与身份证，链接也没带组参数 ⇒ 这两列恒为「—」。
  要真分组，得先决定「链接带组参数」还是「候选人页加字段」。
- **深度统计不在这一页**：α / 分半 / 极端题走既有离线管线 ——
  下载「分析用 JSON」后跑 `python3 pilot/analyze.py --real <文件>`。
  有未答完的份子不进管线（0/1 形状放不下「未作答」，硬塞会把分压低），会单列在 JSON 的 `excluded` 里。
- **导出留痕与水印本轮不做**（票 #36 R2-3 选 B）：但导出动作已经在 CLS 留一行结构化日志
  （`{"ev":"assessment_export","scope":…,"at":…,"count":…,"source":…}`），日后补审计表不必改导出路径。
- **判读话术**（report_narrative）还没接进这一页的导出：话术库由另一条会话在建，
  导出响应里已留好 `narrative` 位置。
