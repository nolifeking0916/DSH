// 云上版测评系统 · 交卷与取报告接口（票 #26 / 新图 #33）
//
// 为什么必须有这个函数（而不是浏览器直连 PG）：
//   CloudBase 的 PG HTTP 网关（PostgREST）连接带 `row_security = off`，
//   因此**凡是开启了 RLS 的表，非 BYPASSRLS 角色一律写不进去**（报 42501
//   "violates row-level security policy"）；只有 `service_role`（rolbypassrls=true）
//   能写。所以：候选人浏览器 → 网关路由 → 本函数（持 API Key，service_role）→ PG。
//   API Key 只存在于函数的环境变量里，**绝不出现在浏览器代码里**。
//
// 环境变量（部署时注入，不落仓）：
//   PG_BASE   例如 https://<envId>.api.tcloudbasegateway.com/v1/rdb/rest
//   PG_KEY    service_role 级别的 API Key
//   PG_TABLE  默认 responses
//
// 接口：
//   POST  /                       交卷：body = 一份作答记录（字段见 public.responses）
//                                 → 201 落库并回显 code；失败 4xx/5xx 带原因
//   GET   /?code=EQ-xxxx         施测人取一份结果（施测人入口用；service_role 可读全部）
//   GET   /?action=list&limit=50  施测人列出最近 N 份（只要 code 与提交时间）
//   OPTIONS *                     CORS 预检
//
// 【2026-10-25 变更 · 维护者裁定 Q1=B】判据与计分放服务端
//   交卷接口现在**自己算分**：body 只带「选了哪一端」，分数由本函数用服务端专属的
//   keys.json（题库锚点）算出来再落库。
//   原因：自助云版里候选人能打开开发者工具；若分数由浏览器算，锚点就跟着答案一起发出去，
//   真人数据整批作废（见 issue #26 / #38）。
//   附带堵掉一个洞：**浏览器自报分数一律不采信**（以前 body 里的 m1_scores 是直接落库的，
//   任何人手工构造请求都能写进假分数）。
//   计分码不在本文件重写：score.js 在沙箱里跑与客户端逐字节相同的 report.js。

const { Buffer } = require("node:buffer");
const { scoreAll, rep, KEYS } = require("./score.js");

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type,Authorization,Prefer",
  "Access-Control-Max-Age": "600"
};

function env(name) {
  const v = process.env[name];
  if (!v) throw new Error("缺少环境变量 " + name);
  return v;
}

async function pg(method, path, body, prefer) {
  const base = env("PG_BASE").replace(/\/$/, "");
  const headers = {
    Authorization: "Bearer " + env("PG_KEY"),
    "Content-Type": "application/json"
  };
  if (prefer) headers.Prefer = prefer;
  const res = await fetch(base + path, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body)
  });
  const text = await res.text();
  let data = null;
  try { data = text ? JSON.parse(text) : null; } catch (e) { data = { raw: text }; }
  if (!res.ok) {
    const err = new Error("PG " + method + " " + path + " → HTTP " + res.status + " " + (data && (data.message || data.code) || text.slice(0, 200)));
    err.status = res.status;
    err.detail = data;
    throw err;
  }
  return data;
}

function reply(status, body) {
  return {
    statusCode: status,
    headers: Object.assign({ "Content-Type": "application/json; charset=utf-8" }, CORS),
    body: JSON.stringify(body)
  };
}

/* ============================================================ 字段白名单（票 #45 · 票 #36 Q4）
   交卷只认白名单里的列；请求体里多传的字段**一律忽略**。
   理由：判据与计分已在服务端（票 #38），客户端输入不再可信。
   · 客户端字段 = 票 #45 票面那 15 项里「由候选人填」的那些；
   · 服务端字段 = 分数与统计（m1_scores / m2_result / m3_result / unanswered_m1）
     —— 客户端就算传了也不采信，一律由服务端算。
   白名单比票面多两项：**m2_answers / m3_answers**（第二、三项的逐题作答）。
   今天 14:30 的迁移刚给表加了这两列（报告的「可信度」三项、错题回顾与
   一致性复核都要用），而**线上候选人页本来就在上报这两项** ——
   不收等于白加列，所以收。 */
const CLIENT_FIELDS = [
  "code", "respondent_name", "id_last4", "id_hash", "group_name", "level", "dept",
  "started_at", "duration_ms", "m1_raw", "m2_answers", "m3_answers", "limit_hint"
];
const SERVER_FIELDS = ["submitted_at", "m1_scores", "m2_result", "m3_result", "unanswered_m1"];

/* 测评编号形态：EQ-{YYYYMMDD}-{6 位随机码}-{4 位校验码}
   6 位随机码取自 32 字符表（无 I/O/0/1），4 位校验码是大写十六进制
   （客户端 publish/index.html 的 newCode() 就是这个格式）。
   **只查形态，不查随机性** —— 裁定二 ③ 排除的是「随机性加强」，不是形态校验。
   要临时关掉：环境变量 CODE_CHECK=off（不用改代码）。 */
const CODE_RE = /^EQ-\d{8}-[A-HJ-NP-Z2-9]{6}-[0-9A-F]{4}$/;
function codeCheckOn() {
  const v = String(process.env.CODE_CHECK || "").toLowerCase();
  return !(v === "off" || v === "0" || v === "false");
}

function str(v) {
  if (v === null || v === undefined) return null;
  const s = String(v).trim();
  return s === "" ? null : s;
}

function bump(obj, k) { obj[k] = (obj[k] || 0) + 1; }

/* 导出动作的结构化日志（票 #45 · 票 #36 R2-3 选 B：留痕本轮不做，**但位置先留出来**）
   —— 一行 JSON：时间 + 件数 + 来源。日后补审计表时不必改导出路径。 */
function exportLog(scope, extra) {
  const line = Object.assign({
    ev: "assessment_export", scope: scope, at: new Date().toISOString(), count: 1, source: "unknown"
  }, extra || {});
  try { console.log(JSON.stringify(line)); } catch (e) { /* 日志失败不能影响导出 */ }
}

/* 从落库的 out 结构重算「综合档」（票 #45 汇总台的「等级」列）。
   **不需要重新计分**：compose() 只吃 m1 短板档 + m2 总档 + m3 总档
   （src/modules/report.js 的 compose()），这三样都在已落库的 out 里。
   函数里的 report.js 与页面里的是同一份（逐字节相同）⇒ 两边算出来一致。 */
function composeStored(m1o, m2o, m3o) {
  if (!m1o || !m2o || !m3o) return null;
  const g1 = m1o.short && m1o.short.grade;
  const g2 = m2o.grade;
  const g3 = m3o.grade;
  if (!g1 || !g2 || !g3) return null;
  const R = rep();
  const items = [
    { name: "第一项 · " + KEYS.m1.meta.title, grade: g1 },
    { name: "第二项 · 情境测试", grade: g2 },
    { name: "第三项 · 推理测试", grade: g3 }
  ];
  const ord = items.map((i) => R.ORD[i.grade]);
  if (ord.some((x) => !x)) return null;
  const avg = ord.reduce((a, b) => a + b, 0) / ord.length;
  const grade = R.bandComposite(avg);
  const minOrd = Math.min.apply(null, ord);
  return {
    grade: grade,
    score: Math.round(avg * 100) / 100,
    short: items[ord.indexOf(minOrd)],
    skew: items.filter((i, k) => R.ORD[grade] - R.ORD[i.grade] >= 2),
    items: items
  };
}

/* ============================================================ 判读话术库匹配
   规则表 report_narrative：(module, dimension, band, pole, kind) ⇒ text
   profile = {
     personality: { INT: {band, pole, pole_label, score}, ... },
     situation:   { regu: {band, score}, ... },
     reasoning:   { DED: {band, rate}, ... },
     overall:     { grade, kinds: ["profile","fit","potential","strength","caution"] }
   }
   匹配顺序：精确（档位 + 极）→ 同档不区分极 → __all__ 通用条。
   **不按候选人编号取**：调用方只传分数画像，不碰 responses 表 ⇒ 不泄露任何人的数据。 */
function pickRule(rules, module, dimension, band, pole, kind) {
  const cands = rules.filter((r) => r.module === module && r.dimension === dimension
    && (kind === null || kind === undefined || r.kind === kind));
  const tries = [];
  if (band && band !== "__all__") {
    tries.push({ band: band, pole: pole || "__any__" });
    tries.push({ band: band, pole: "__any__" });
  }
  tries.push({ band: "__all__", pole: "__any__" });
  for (const t of tries) {
    const hit = cands.find((r) => r.band === t.band && r.pole === t.pole);
    if (hit) return hit;
  }
  return null;
}

function matchNarrative(rules, profile) {
  const out = { personality: {}, situation: {}, reasoning: {}, overall: [] };
  for (const key of Object.keys(profile.personality || {})) {
    const d = profile.personality[key] || {};
    const r = pickRule(rules, "personality", d.dimension || key, d.band, d.pole, null);
    if (r) out.personality[key] = { text: r.text, title: r.title, pole_label: r.pole_label || d.pole_label || null, band: d.band, pole: d.pole };
  }
  for (const key of Object.keys(profile.situation || {})) {
    const d = profile.situation[key] || {};
    const r = pickRule(rules, "situation", d.dimension || key, d.band, null, null);
    if (r) out.situation[key] = { text: r.text, title: r.title, band: d.band };
  }
  for (const key of Object.keys(profile.reasoning || {})) {
    const d = profile.reasoning[key] || {};
    const r = pickRule(rules, "reasoning", d.dimension || key, d.band, null, null);
    if (r) out.reasoning[key] = { text: r.text, title: r.title, band: d.band };
  }
  const ov = profile.overall || {};
  for (const kind of (ov.kinds || [])) {
    const r = pickRule(rules, "overall", "__overall__", ov.grade, "__any__", kind);
    if (r) out.overall.push({ kind: kind, title: r.title, text: r.text });
  }
  return out;
}

exports.main = async (event) => {
  const method = (event.httpMethod || event.requestContext && event.requestContext.httpMethod || "GET").toUpperCase();
  if (method === "OPTIONS") return reply(204, {});

  const q = event.queryStringParameters || {};
  const table = process.env.PG_TABLE || "responses";
  try {
    if (method === "POST") {
      let payload = event.body;
      if (payload && typeof payload === "string") {
        try { payload = JSON.parse(payload); } catch (e) { return reply(400, { ok: false, error: "请求体不是合法 JSON" }); }
      }
      if (!payload || typeof payload !== "object") return reply(400, { ok: false, error: "缺少作答记录" });

      /* ---- 只取白名单字段：多传的字段一律忽略（票 #45 · 票 #36 Q4）---- */
      const raw = {};
      for (const k of CLIENT_FIELDS) if (payload[k] !== undefined) raw[k] = payload[k];

      const code = str(raw.code);
      if (!code) return reply(400, { ok: false, error: "缺少 code（测评编号）" });
      if (codeCheckOn() && !CODE_RE.test(code)) {
        return reply(400, { ok: false, error: "测评编号格式不对（应为 EQ-YYYYMMDD-6 位随机码-4 位校验码）", code: code });
      }

      /* ---- m1_raw：96 题；-1 / null = 未作答 → 落 null ----
         线上候选人页把「未作答」编码成 **-1**（publish/index.html 的 cloudPayload），
         而服务端计分认的是 **null**（未作答不计入该维得分，report.js 的 scoreM1）。
         ⇒ 这里做一次归一：**-1 → null**。不归一的话，有未答题的交卷会被
         当成「答了但全错」（-1 既不是 null 也不等于 0/1）。 */
      const m1in = raw.m1_raw;
      const n = Array.isArray(m1in) ? m1in.length : 0;
      if (n !== 96) return reply(400, { ok: false, error: "m1_raw 应为 96 题的 0/1 序列，实得 " + n });
      const m1 = new Array(96);
      for (let i = 0; i < 96; i++) {
        const v = m1in[i];
        if (v === null || v === undefined || v === -1) { m1[i] = null; continue; }
        if (v !== 0 && v !== 1) return reply(400, { ok: false, error: "m1_raw 第 " + (i + 1) + " 题不是 0/1" });
        m1[i] = v;
      }
      /* 服务端算分：浏览器自报的任何分数一律不采信 */
      let out;
      try {
        out = scoreAll({ m1_raw: m1, m2_answers: raw.m2_answers || null, m3_answers: raw.m3_answers || null });
      } catch (err) {
        return reply(500, { ok: false, error: "服务端计分失败：" + String(err && err.message || err) });
      }
      const unanswered = m1.filter((v) => v === null).length;
      const row = {
        /* —— 白名单里的客户端字段 —— */
        code: code,
        respondent_name: str(raw.respondent_name) || str(payload.name) || null,
        id_last4: str(raw.id_last4),
        id_hash: str(raw.id_hash),        /* 不可逆校验码：识别同一人重复提交，不含原号信息 */
        group_name: str(raw.group_name),
        level: str(raw.level),
        dept: str(raw.dept),
        started_at: raw.started_at || null,
        duration_ms: Number.isFinite(raw.duration_ms) ? raw.duration_ms : null,
        m1_raw: m1,
        m2_answers: raw.m2_answers || null,
        m3_answers: raw.m3_answers || null,
        limit_hint: raw.limit_hint || null,
        /* —— 白名单里的服务端字段（客户端传了也不采信）—— */
        submitted_at: new Date().toISOString(),   /* 服务器时间：客户端时钟不可信 */
        m1_scores: out.m1,
        m2_result: out.m2,
        m3_result: out.m3,
        unanswered_m1: unanswered
      };
      const inserted = await pg("POST", "/" + table, row, "return=representation");
      const first = Array.isArray(inserted) ? inserted[0] : inserted;
      /* 响应里**不含分数**：候选人端不显示分数（红线 6） */
      return reply(201, { ok: true, code: first && first.code, id: first && first.id, stored: n, unanswered: unanswered });
    }

    if (method === "GET") {
      if (q.action === "list") {
        const limit = Math.min(parseInt(q.limit || "50", 10) || 50, 200);
        const rows = await pg("GET", "/" + table + "?select=code,respondent_name,id_last4,id_hash,group_name,level,submitted_at,duration_ms,unanswered_m1,m1_scores,m2_result,m3_result&order=submitted_at.desc&limit=" + limit);
        /* 「等级」= 综合档（compose）：m1 短板档 + m2 总档 + m3 总档重算，
           **不需要重新计分**（三样都在已落库的 out 里）⇒ 只取用、不回传。 */
        const out = (rows || []).map((r) => {
          const cp = composeStored(r.m1_scores, r.m2_result, r.m3_result);
          return {
            code: r.code,
            respondent_name: r.respondent_name || null,
            id_last4: r.id_last4 || null,
            id_hash: r.id_hash || null,
            group_name: r.group_name || null,
            level: r.level || null,
            submitted_at: r.submitted_at || null,
            duration_ms: r.duration_ms === null ? null : Number(r.duration_ms),
            unanswered_m1: r.unanswered_m1 === null ? null : Number(r.unanswered_m1),
            grade: cp ? cp.grade : null
          };
        });
        return reply(200, { ok: true, count: out.length, rows: out });
      }
      if (q.action === "narrative") {
        /* 判读话术：调用方只传**分数画像**，不传候选人编号 ⇒ 不碰 responses 表，
           也就不会泄露任何人的作答。规则从 report_narrative 读，按分数档 + 特征极匹配。 */
        let profile;
        try {
          profile = JSON.parse(decodeURIComponent(q.profile || ""));
        } catch (e) {
          return reply(400, { ok: false, error: "profile 不是合法 JSON" });
        }
        if (!profile || typeof profile !== "object") return reply(400, { ok: false, error: "缺 profile" });
        const rules = await pg("GET", "/report_narrative?select=module,dimension,band,pole,pole_label,kind,title,text&active=eq.true&order=sort.asc");
        return reply(200, { ok: true, narrative: matchNarrative(rules || [], profile) });
      }
      if (q.action === "rules") {
        /* 列出判读话术库（只有文案，没有任何候选人数据）——
           给「编辑后台」用：维护者改完话术后把这段 UPSERT SQL 在控制台执行即可。 */
        const rules = await pg("GET", "/report_narrative?select=id,module,dimension,band,pole,pole_label,kind,title,text,active&order=module,dimension,band,pole,kind");
        return reply(200, { ok: true, count: (rules || []).length, rules: rules || [] });
      }
      if (q.action === "export") {
        /* ---- 一键导出（票 #45 · 维护者原话：「我后台再做一个网页，让你可以一键导出对应的分析报告」）----
           两档：一份属于某人的报告 / 一批的汇总。
           报告由**云函数算**（判据与计分在服务端，票 #38），页面只渲染。
           导出动作在 CLS 留一行结构化日志（票 #36 R2-3 选 B：留痕本轮不做，位置先留出来）。 */
        const src = String(q.src || "unknown").slice(0, 40);
        if (q.code) {
          const rows = await pg("GET", "/" + table + "?code=eq." + encodeURIComponent(q.code) + "&limit=1");
          if (!rows || !rows.length) return reply(404, { ok: false, error: "没有这一份", code: q.code });
          const row = rows[0];
          const compose = composeStored(row.m1_scores, row.m2_result, row.m3_result);
          exportLog("single", { code: row.code, count: 1, source: src });
          return reply(200, {
            ok: true, kind: "single",
            code: row.code,
            respondent_name: row.respondent_name || null,
            id_last4: row.id_last4 || null,
            id_hash: row.id_hash || null,
            group_name: row.group_name || null,
            level: row.level || null,
            dept: row.dept || null,
            submitted_at: row.submitted_at || null,
            duration_ms: row.duration_ms === null ? null : Number(row.duration_ms),
            unanswered_m1: row.unanswered_m1 === null ? null : Number(row.unanswered_m1),
            generated_at: new Date().toISOString(),
            /* report 的形状 = 渲染器要的形状（src/modules/report.js 的 reportHTML(R)）：
               R.m1.dims / R.m1.short / R.m2.* / R.m3.* / R.compose。 */
            report: {
              name: row.respondent_name || null,
              code: row.code,
              idLast4: row.id_last4 || null,
              m1: row.m1_scores || null,
              m2: row.m2_result || null,
              m3: row.m3_result || null,
              compose: compose
            },
            /* 位置先留出来：判读话术库那半由另一条会话负责（report_narrative），
               那边就绪后在这里挂上即可，页面已有渲染位。 */
            narrative: null
          });
        }
        /* ---- 一批的汇总 ---- */
        const limit = Math.min(parseInt(q.limit || "50", 10) || 50, 200);
        if (q.format === "pipeline") {
          /* 离线分析管线吃的形状（pilot/analyze.py --real，作业包 §六）：
             { meta, respondents: [{ id, group, responses: [96 个 0/1], times_ms: [] }] }
             **未答完的份子不进管线**：管线的 0/1 形状放不下「未作答」，
             硬塞会被当成「选了 a 侧」把分压低 ⇒ 单独列出来，由施测人决定要不要人工看。 */
          const rows = await pg("GET", "/" + table + "?select=code,respondent_name,id_last4,group_name,m1_raw,unanswered_m1&order=submitted_at.desc&limit=" + limit);
          const respondents = [];
          const excluded = [];
          for (const r of rows || []) {
            const raw = Array.isArray(r.m1_raw) ? r.m1_raw : [];
            const unanswered = Number(r.unanswered_m1 || 0);
            if (raw.length !== 96 || unanswered > 0) {
              excluded.push({
                code: r.code, respondent_name: r.respondent_name || null, unanswered_m1: unanswered,
                reason: raw.length !== 96 ? "m1_raw 不是 96 题" : "有未答题"
              });
              continue;
            }
            respondents.push({
              id: r.code,
              group: r.group_name || "",
              responses: raw.map((v) => (v === 0 || v === 1 ? v : 0)),
              times_ms: [],
              name: r.respondent_name || null,
              id4: r.id_last4 || null
            });
          }
          exportLog("batch-pipeline", { count: respondents.length, source: src });
          return reply(200, {
            meta: {
              tool: "云上版测评系统",
              source: "cloudbase://public.responses",
              generated_at: new Date().toISOString(),
              n_respondents: respondents.length,
              n_excluded: excluded.length,
              note: "responses = 第一项 96 题的 0/1（0=选 a 侧，1=选 b 侧）；times_ms 线上未采逐题耗时，故为空数组；有未答题的份子不进管线（见 excluded）"
            },
            respondents: respondents,
            excluded: excluded
          });
        }
        const rows = await pg("GET", "/" + table + "?select=code,respondent_name,id_last4,id_hash,group_name,level,submitted_at,duration_ms,unanswered_m1,m1_scores,m2_result,m3_result&order=submitted_at.desc&limit=" + limit);
        const out = [];
        const byGrade = {}, byGroup = {}, byLevel = {};
        for (const r of rows || []) {
          const cp = composeStored(r.m1_scores, r.m2_result, r.m3_result);
          const m1o = r.m1_scores || {};
          out.push({
            code: r.code,
            respondent_name: r.respondent_name || null,
            id_last4: r.id_last4 || null,
            id_hash: r.id_hash || null,
            group_name: r.group_name || null,
            level: r.level || null,
            submitted_at: r.submitted_at || null,
            duration_ms: r.duration_ms === null ? null : Number(r.duration_ms),
            unanswered_m1: r.unanswered_m1 === null ? null : Number(r.unanswered_m1),
            grade: cp ? cp.grade : null,
            m1_dims: (m1o.dims || []).map((d) => ({ key: d.key, name: d.name, score: d.score, max: d.max, grade: d.grade })),
            m1_grade: (m1o.short && m1o.short.grade) || null,
            m2_grade: (r.m2_result && r.m2_result.grade) || null,
            m3_grade: (r.m3_result && r.m3_result.grade) || null
          });
          bump(byGrade, cp ? cp.grade : "（缺）");
          bump(byGroup, r.group_name || "（空）");
          bump(byLevel, r.level || "（空）");
        }
        exportLog("batch", { count: out.length, source: src });
        return reply(200, {
          ok: true, kind: "batch", count: out.length, generated_at: new Date().toISOString(),
          rows: out,
          distribution: { by_grade: byGrade, by_group: byGroup, by_level: byLevel },
          pipeline_query: "?action=export&scope=batch&limit=" + limit + "&format=pipeline&src=" + encodeURIComponent(src)
        });
      }
      if (!q.code) return reply(400, { ok: false, error: "缺 code" });
      const rows = await pg("GET", "/" + table + "?code=eq." + encodeURIComponent(q.code) + "&limit=1");
      if (!rows || !rows.length) return reply(404, { ok: false, error: "没有这一份", code: q.code });
      return reply(200, { ok: true, row: rows[0] });
    }

    return reply(405, { ok: false, error: "只支持 GET / POST / OPTIONS" });
  } catch (e) {
    return reply(e.status && e.status >= 400 && e.status < 600 ? e.status : 500, {
      ok: false, error: String(e && e.message || e),
      detail: e && e.detail || null
    });
  }
};
