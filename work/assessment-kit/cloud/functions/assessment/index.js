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
const { scoreAll } = require("./score.js");

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
      if (!payload.code) return reply(400, { ok: false, error: "缺少 code（测评编号）" });
      const m1 = payload.m1_raw;
      const n = Array.isArray(m1) ? m1.length : 0;
      if (n !== 96) return reply(400, { ok: false, error: "m1_raw 应为 96 题的 0/1 序列，实得 " + n });
      for (let i = 0; i < m1.length; i++) {
        const v = m1[i];
        if (v === null) continue;                       /* null = 未作答（合法） */
        if (v !== 0 && v !== 1) return reply(400, { ok: false, error: "m1_raw 第 " + (i + 1) + " 题不是 0/1" });
      }
      /* 服务端算分：浏览器自报的任何分数一律不采信 */
      let out;
      try {
        out = scoreAll(payload);
      } catch (err) {
        return reply(500, { ok: false, error: "服务端计分失败：" + String(err && err.message || err) });
      }
      const unanswered = m1.filter((v) => v === null).length;
      const row = {
        code: payload.code,
        respondent_name: payload.respondent_name || payload.name || null,
        id_last4: payload.id_last4 || payload.idLast4 || null,
        group_name: payload.group_name || payload.group || null,
        level: payload.level || null,
        dept: payload.dept || null,
        started_at: payload.started_at || null,
        duration_ms: Number.isFinite(payload.duration_ms) ? payload.duration_ms : null,
        m1_raw: m1,
        m1_scores: out.m1,
        m2_result: out.m2,
        m3_result: out.m3,
        /* 第二、三项的逐题作答也存：报告里的「可信度」三项都要算，
           一致性检查复核与错题回顾也要用到（票 #34 的表结构补齐）。 */
        m2_answers: payload.m2_answers || payload.m2_answers_raw || null,
        m3_answers: payload.m3_answers || payload.m3_answers_raw || null,
        limit_hint: payload.limit_hint || payload.limitHint || null,
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
        const rows = await pg("GET", "/" + table + "?select=code,respondent_name,id_last4,group_name,level,submitted_at,duration_ms,unanswered_m1&order=submitted_at.desc&limit=" + limit);
        return reply(200, { ok: true, count: (rows || []).length, rows: rows || [] });
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
