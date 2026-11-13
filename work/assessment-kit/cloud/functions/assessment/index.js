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

/* 【票 #54 第 2 层 · 2026-10-26 · 维护者拍板】Origin 白名单，落**函数层**：
   · Origin ∈ 白名单（候选页 / HR 台）→ 回显**该单个 origin**；
   · 无 Origin（curl、服务端直调）→ 回 `*`（服务端本就不受 CORS 约束，保持可读）；
   · 其余来源 → **不回 ACAO** ⇒ 浏览器读不到响应。
   ⚠ 网关 `EnableSafeDomain` 保持 **false 不动** —— 不把 10:31 那个「请求 origin,*」逗号多值 bug 放回来。
   ⚠ 这不是访问控制（research/网关与函数鉴权手段 §4：安全域名/CORS 只挡浏览器跨源、不挡 curl）；
     按人鉴权在第 3 层（票 #44）。 */
const ALLOWED_ORIGINS = [
  "https://assessment-test-uu-one-d4gc4ot78a702cb70.webapps.tcloudbase.com",
  "https://hr-panel-uu-one-d4gc4ot78a702cb70.webapps.tcloudbase.com"
];

function corsHeaders(origin) {
  const h = {
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type,Authorization,Prefer",
    "Access-Control-Max-Age": "600"
  };
  if (!origin) h["Access-Control-Allow-Origin"] = "*";
  else if (ALLOWED_ORIGINS.indexOf(origin) !== -1) h["Access-Control-Allow-Origin"] = origin;
  return h;
}

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

/* 【票 #54 第 2 层】origin 由 handler 入口取一次、按参数传进来 —— **不用模块级变量**，
   避免同实例并发请求串号；origin 缺省时（curl / 服务端直调）由 corsHeaders 回 `*`。 */
function _reply(status, body, origin) {
  return {
    statusCode: status,
    headers: Object.assign({ "Content-Type": "application/json; charset=utf-8" }, corsHeaders(origin)),
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

/* ============================================================ 题数（票 #83/#85）
   三个模块的题数都从**服务端题库**取，只在题库读不到时兜底，避免写死魔数。 */
function m3Slots() {
  try { return KEYS.m3.questions.length; } catch (e) { return 40; }
}
/* 第二项题数（自评 + 情境）：与第三项同一口径，从**服务端题库**取，兜底 76 */
function m2Slots() {
  try { return KEYS.eq.self_items.length + KEYS.eq.sjt.length; } catch (e) { return 76; }
}
/* 第一项题数：服务端题库，兜底 96（与 m2Slots/m3Slots 同纪律，票 #87） */
function m1Slots() {
  try { return KEYS.m1.questions.length; } catch (e) { return 96; }
}
/* ============================================================ 计分前形状自检（票 #87 · 方案 A 草案 2026-11-03，待维护者拍板）
   #83/#85 已在 POST 入口按字段 400；这是 scoreAll 前的**唯一口径兜底**，也给读侧
   （历史行）提供同一判定。只看**形状**，不看完成度：
   · m1/m3 是定长数组 ⇒ 长度必须分别 96/40（m3 整列 null = 加列前历史行）；
   · m2 是稀疏对象 ⇒ 键必须在 0-(n-1)（少键＝「仍然提交」合法路径，不报）。
   返回 [{module,kind,expected,actual}]，空数组 = 形状合法。 */
function shapeSelfCheck(m1, m2raw, m3) {
  const probs = [];
  const n1 = m1Slots();
  if (!Array.isArray(m1) || m1.length !== n1) {
    probs.push({ module: "m1", kind: "shape", expected: n1, actual: Array.isArray(m1) ? m1.length : null });
  }
  const n3 = m3Slots();
  if (!Array.isArray(m3) || m3.length !== n3) {
    probs.push({ module: "m3", kind: "shape", expected: n3, actual: Array.isArray(m3) ? m3.length : null });
  }
  if (m2raw !== undefined && m2raw !== null) {
    const n2 = m2Slots();
    if (typeof m2raw !== "object" || Array.isArray(m2raw)) {
      probs.push({ module: "m2", kind: "shape", expected: "sparse-object",
        actual: Array.isArray(m2raw) ? "array" : typeof m2raw });
    } else {
      for (const k of Object.keys(m2raw)) {
        const i = Number(k);
        if (!Number.isInteger(i) || i < 0 || i >= n2) {
          probs.push({ module: "m2", kind: "shape", expected: "slot 0-" + (n2 - 1), actual: k });
          break;
        }
      }
    }
  }
  return probs;
}
/* 读侧判定（方案 A 不新增列）：每次读取按现状现算，坏形状只在报告/统计侧隔离、不回写。
   m2_answers 为 null 合法（第二项可空交）；m3_answers 为 null = 加列前历史行。 */
function rowShapeProblems(row) {
  if (!row) return [{ module: "row", kind: "shape", expected: "object", actual: null }];
  return shapeSelfCheck(
    Array.isArray(row.m1_raw) ? row.m1_raw : null,
    row.m2_answers !== undefined ? row.m2_answers : null,
    Array.isArray(row.m3_answers) ? row.m3_answers : null
  );
}
/* 拒收留痕（票 #87 要做的事 3）：与 exportLog/patchLog 同一纪律 —— 一行结构化
   JSON 到 stdout（随云函数日志进 CLS），可查谁/何时/哪个模块/差多少；不另造表。 */
function rejectLog(meta, reasons) {
  const line = Object.assign({ ev: "assessment_submit_reject", at: new Date().toISOString() },
    meta, { reasons: reasons });
  try { console.log(JSON.stringify(line)); } catch (e) { /* 日志失败不改变拒收结论 */ }
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
// 票 #78 第 4 步：服务端算可信度，只下发 level+flags（#45：不下发逐题）
function credibilitySrv(row) {
  function maxRun(seq) {
    let best = 0, cur = 0, prev = null;
    (seq || []).forEach((v) => {
      if (v == null) { cur = 0; prev = null; return; }
      if (v === prev) cur++; else { cur = 1; prev = v; }
      if (cur > best) best = cur;
    });
    return best;
  }
  const out = {};
  const raw = Array.isArray(row.m1_raw) ? row.m1_raw : null;
  let f1 = [], l1 = "高";
  if (raw) {
    const run = maxRun(raw), ones = raw.filter(v => v === 1).length, zeros = raw.filter(v => v === 0).length;
    const ans = ones + zeros, dom = ans ? Math.max(ones, zeros) / ans : 0;
    if (run >= 25 || dom >= 0.85) { l1 = "低"; f1.push("96 题里同侧连答最长 " + run + " 题、某一侧占比 " + Math.round(dom*100) + "%，接近连续作答同一端的形态"); }
    else if (run >= 15 || dom >= 0.70) { l1 = "中"; f1.push("同侧连答最长 " + run + " 题、某一侧占比 " + Math.round(dom*100) + "%，作答偏好偏集中"); }
  } else { l1 = "中"; f1.push("本次未留存逐题作答，同侧作答与缺失只能看汇总口径"); }
  const miss1 = Number(row.unanswered_m1 || 0);
  if (miss1 > 0) f1.push("第一项有 " + miss1 + " 题未作答");
  out.m1 = { level: l1, flags: f1 };
  out.m2 = { level: "中", flags: ["汇总台导出不含 m2 原始作答，缺失与一致信号以 m2_result 为准"] };
  out.m3 = { level: "中", flags: ["汇总台导出不含 m3 原始作答，缺失与作答模式只能看汇总口径"] };
  out.overall = { level: "中", speed: null, flags: out.m1.flags.concat(out.m2.flags, out.m3.flags) };
  return out;
}
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
  /* 【票 #54 第 2 层】本次请求的 Origin 在入口取一次，绑进**本请求**的 reply 闭包：
     后续所有 reply(...) 都只看这一次的 origin（不用模块级变量，避免并发串号）。
     白名单判定在 corsHeaders()：白名单 → 回显该 origin；无 Origin → `*`；其余 → 不回 ACAO。 */
  const _h = event.headers || {};
  const origin = String(_h.origin || _h.Origin || "");
  const reply = (s, b) => _reply(s, b, origin);
  if (method === "OPTIONS") return reply(204, {});

  const q = event.queryStringParameters || {};
  const table = process.env.PG_TABLE || "responses";
  try {
    /* ---- 票 #86（2026-11-03）：补交第三项通道 action=patch_m3 已停用 --------------
       旧实现（票 #26 的临时补答）门槛只有测评编号、**无鉴权**，谁拿到 code 就能
       PATCH 服务端成绩。两位当事人的第三项已在库补完（40/40、0 空、值域 0-3），
       /patch 三份一次性补答页随票 #86 静态清理删除 ⇒ 服务端分支整段下掉：
         · 这里显式回 **410 Gone**：不解析 body、不查库、不写库（无凭据也无通道）；
         · 必须在普通交卷 POST 分支**之前**拦住，否则它会带着 action 参数落进
           普通交卷逻辑，被当成一份新交卷处理；
         · 不做「加凭据保留」：按人鉴权归票 #44 的施测人路径，将来若重开补答，
           另立带鉴权的正式接口，不复活这个一次性动作名。 */
    if (method === "POST" && q.action === "patch_m3") {
      return reply(410, { ok: false, retired: "patch_m3",
        error: "补答通道已停用（票 #86）；第三项补答已结束，如需补答请走施测人路径" });
    }

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
      /* 票 #87 方案 A：统一前置形状自检（对**原始载荷**，在任何逐字段解析之前）。
         m1/m3 定长 96/40、m2 稀疏对象键在 0-75。任一不符 ⇒ 整份拒收、不落库，
         400 带 reasons，并写 CLS 结构化留痕（谁/编号/模块/期望/实得）。
         值域（m1 0/1、m2 与 m3 0-3）仍归后面的逐字段校验，这里只管形状。
         这样 41 项 / 39 项 / 整缺 / m1 题数不符都走同一个带留痕的入口，
         不会先被 #83 那条只回错误串、不留痕的旧 400 拦走。 */
      {
        const earlyProbs = shapeSelfCheck(
          Array.isArray(raw.m1_raw) ? raw.m1_raw : null,
          raw.m2_answers,
          Array.isArray(raw.m3_answers) ? raw.m3_answers : null
        );
        if (earlyProbs.length) {
          rejectLog({ disposition: "rejected", code: code,
            respondent_name: str(raw.respondent_name) || str(payload.name) || null,
            id_last4: str(raw.id_last4), id_hash: str(raw.id_hash), group_name: str(raw.group_name) },
            earlyProbs);
          return reply(400, { ok: false, error: "作答形状自检未过，整份拒收、不落库",
            "void": true, reasons: earlyProbs });
        }
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
      /* ---- m2_answers：题位范围（票 #83）＋ 值域（票 #85 · 2026-10-26）----
         第二项是**自评 + 情境**共 76 题，作答以 {题位: 选项下标} 的对象上报
         （publish/candidate/index.html 的 buildPayload：**答了的题位才有键**）。
         ⇒ 这里查两件事，都不是查键的个数：
           · 题位范围（#83）：键必须是 0-75 的整数题位。
             键数少于 76 = 有题没答（页面上「仍然提交（按未作答计分）」那条路径，
             服务端照旧按未作答计分）—— **不该拦**；
             题位超出 0-75 = 形状坏了（多余项 / 越界）—— 400。
           · 值域（#85）：**已作答题位**的值必须是 0-3 的整数（四选项下标）。
             超范围（-1/4/7…）、字符串、小数、null 占位一律 400 —— 票 #85 实测前
             这类值会被静默算成别的分。键不存在才表示未答；键在但值不合法 = 形状坏。
         （第一项、第三项是定长数组 ⇒ 查长度；第二项是稀疏对象 ⇒ 查题位范围 + 值域。） */
      const m2n = m2Slots();
      if (raw.m2_answers !== undefined && raw.m2_answers !== null) {
        const m2in = raw.m2_answers;
        if (typeof m2in !== "object" || Array.isArray(m2in)) {
          return reply(400, { ok: false, error: "第二项 m2_answers 应为 {题位: 选项下标} 的对象，实得 " + (Array.isArray(m2in) ? "数组" : typeof m2in) });
        }
        for (const k of Object.keys(m2in)) {
          const i = Number(k);
          if (!Number.isInteger(i) || i < 0 || i >= m2n) {
            return reply(400, { ok: false, error: "第二项 m2_answers 题位 " + k + " 超出 0-" + (m2n - 1) + "（第二项共 " + m2n + " 题）" });
          }
          const mv = m2in[k];
          if (!Number.isInteger(mv) || mv < 0 || mv > 3) {
            return reply(400, { ok: false, error: "第二项 m2_answers 题位 " + k + "（第 " + (i + 1) + " 题）的选项下标应为 0-3 的整数，实得 " + JSON.stringify(mv) });
          }
        }
      }
      /* ---- m3_answers：值域校验（2026-10-26 · 票 #26 根因的服务器侧兜底）----
         第三项是**四选项**（选项下标 0/1/2/3）。客户端曾把 2/3 丢成 null
         （normalize 只认 0/1）⇒ 那一批数据整批被按「未作答」计分。
         ⇒ 服务端现在**明确拒绝**不在 0-3 的值（宁可报错也不要静默算错），
         并把「第三项有 N 题未作答」**回显在响应里**，让提交方立刻看得见。 */
      const m3in = raw.m3_answers;
      const m3 = Array.isArray(m3in) ? m3in : null;
      if (m3) {
        for (let i = 0; i < m3.length; i++) {
          const v = m3[i];
          if (v === null || v === undefined) continue;
          if (v !== 0 && v !== 1 && v !== 2 && v !== 3) {
            return reply(400, { ok: false, error: "m3_answers 第 " + (i + 1) + " 题不是 0-3 的选项下标", got: v });
          }
        }
      }
      /* ---- m3_answers：长度校验（票 #83 · 2026-10-26）----
         形状校验只做了**一半**：值域（0-3）查了，**长度没查** ⇒ 一份 41 项的
         载荷被接受并落库（票 #83 的实测）。第一项的 96 题是查长度的（上面那段），
         这里按同一写法、同一错误码风格补齐：第三项必须是 40 题的数组。
         ⚠ 客户端（publish/candidate/index.html 的 buildPayload）第三项恒是
           nM3()=40 的定长数组（没答的题位 = null 占位）⇒ 正常交卷长度恒为 40，
           本校验**不拦**「按未作答计分」那条路径（库里已有只答了 20 题的真实份子）。 */
      const m3n = m3Slots();
      const m3len = Array.isArray(m3) ? m3.length : 0;
      if (m3len !== m3n) {
        return reply(400, { ok: false, error: "第三项 m3_answers 应为 " + m3n + " 题的 0-3 选项下标序列，实得 " + m3len });
      }
      /* 票 #87 方案 A：计分前形状自检。#83/#85 入口已拦同类问题；这一步保证任何写
         路径（含以后新增的）都不可能让坏形状走到 scoreAll。裁定 A：整份拒收、不落库，
         CLS 结构化留痕（票 #87：不是只回一个 400 就完事）。 */
      const shapeProbs = shapeSelfCheck(m1, raw.m2_answers, m3);
      if (shapeProbs.length) {
        rejectLog({ disposition: "rejected", code: code,
          respondent_name: str(raw.respondent_name) || str(payload.name) || null,
          id_last4: str(raw.id_last4), id_hash: str(raw.id_hash), group_name: str(raw.group_name) },
          shapeProbs);
        return reply(400, { ok: false, error: "作答形状自检未过，整份拒收、不落库",
          "void": true, reasons: shapeProbs });
      }
      /* 服务端算分：浏览器自报的任何分数一律不采信 */
      let out;
      try {
        out = scoreAll({ m1_raw: m1, m2_answers: raw.m2_answers || null, m3_answers: m3 });
      } catch (err) {
        return reply(500, { ok: false, error: "服务端计分失败：" + String(err && err.message || err) });
      }
      const unanswered = m1.filter((v) => v === null).length;
      /* 完整度回显：三项各缺几题（第二项按键数、第三项按 40 位数组） */
      const m2done = (raw.m2_answers && typeof raw.m2_answers === "object") ? Object.keys(raw.m2_answers).length : null;
      const m3done = m3 ? m3.filter((v) => v !== null && v !== undefined).length : null;
      const gaps = {
        m1: unanswered,
        m2: m2done === null ? null : Math.max(0, 76 - m2done),
        m3: m3done === null ? null : Math.max(0, 40 - m3done),
      };
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
      /* 但**回显完整度**：哪一项缺了几题（2026-10-26）——
         之前「她漏答 22 题」是静默发生的（客户端丢答 + 页面显示已答 40/40），
         现在交卷方与服务端都能立刻看见缺口。 */
      return reply(201, { ok: true, code: first && first.code, id: first && first.id, stored: n, unanswered: unanswered, gaps: gaps });
    }

    if (method === "GET") {
      if (q.action === "list") {
        const limit = Math.min(parseInt(q.limit || "50", 10) || 50, 200);
        /* 【票 #54 第 1 层】action=list 去掉 id_hash（id_last4 保留供核对）——
           HR 台只渲染 code/姓名/后4位/组/层级/时间/时长/未答题/等级，未用 id_hash。 */
        const rows = await pg("GET", "/" + table + "?select=code,respondent_name,id_last4,group_name,level,submitted_at,duration_ms,unanswered_m1,m1_raw,m2_answers,m3_answers,m1_scores,m2_result,m3_result&order=submitted_at.desc&limit=" + limit);
        /* 「等级」= 综合档（compose）：m1 短板档 + m2 总档 + m3 总档重算，
           **不需要重新计分**（三样都在已落库的 out 里）⇒ 只取用、不回传。 */
        const out = (rows || []).map((r) => {
          /* 票 #87 方案 A：坏形状（历史遗留行）不综合、不给「待提升」，显式作废标记 */
          const probs = rowShapeProblems(r);
          const cp = probs.length ? null : composeStored(r.m1_scores, r.m2_result, r.m3_result);
          return {
            code: r.code,
            respondent_name: r.respondent_name || null,
            id_last4: r.id_last4 || null,
            group_name: r.group_name || null,
            level: r.level || null,
            submitted_at: r.submitted_at || null,
            duration_ms: r.duration_ms === null ? null : Number(r.duration_ms),
            unanswered_m1: r.unanswered_m1 === null ? null : Number(r.unanswered_m1),
            grade: cp ? cp.grade : null,
            voided: probs.length ? { kind: "shape", reasons: probs } : null
          };
        });
        return reply(200, { ok: true, count: out.length,
          count_voided: out.filter((r) => r.voided).length, rows: out });
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
          /* 票 #87 方案 A：历史坏形状行不出报告，不许再以「待提升」面貌进判读 */
          const probs = rowShapeProblems(row);
          if (probs.length) {
            exportLog("single-void", { code: row.code, count: 0, source: src });
            return reply(200, {
              ok: true, kind: "single-void",
              code: row.code,
              respondent_name: row.respondent_name || null,
              id_last4: row.id_last4 || null,
              submitted_at: row.submitted_at || null,
              generated_at: new Date().toISOString(),
              report: null,
              "void": { kind: "shape", reasons: probs,
                note: "该份作答形状不完整（历史遗留行），不计成绩、不出报告" }
            });
          }
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
            /* 票 #78 第 4 步：可信度由服务端算好后随 export 下发（只 level+flags，#45 不下发逐题） */
            credibility: credibilitySrv(row),
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
          const rows = await pg("GET", "/" + table + "?select=code,respondent_name,id_last4,group_name,m1_raw,m2_answers,m3_answers,unanswered_m1&order=submitted_at.desc&limit=" + limit);
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
            const shapeProbs = shapeSelfCheck(raw, r.m2_answers,
              Array.isArray(r.m3_answers) ? r.m3_answers : null);
            if (shapeProbs.length) {
              excluded.push({
                code: r.code, respondent_name: r.respondent_name || null, unanswered_m1: unanswered,
                reason: "形状不完整（历史遗留，票 #87）：" +
                  shapeProbs.map((x) => x.module + " 期望 " + JSON.stringify(x.expected) +
                    " 实得 " + JSON.stringify(x.actual)).join("；")
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
        const rows = await pg("GET", "/" + table + "?select=code,respondent_name,id_last4,id_hash,group_name,level,submitted_at,duration_ms,unanswered_m1,m1_raw,m2_answers,m3_answers,m1_scores,m2_result,m3_result&order=submitted_at.desc&limit=" + limit);
        const out = [];
        const voided = [];
        const byGrade = {}, byGroup = {}, byLevel = {};
        for (const r of rows || []) {
          /* 票 #87 方案 A：坏形状不进批次汇总与分布统计 */
          const probs = rowShapeProblems(r);
          if (probs.length) {
            voided.push({ code: r.code, respondent_name: r.respondent_name || null,
              submitted_at: r.submitted_at || null, voided: { kind: "shape", reasons: probs } });
            continue;
          }
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
          ok: true, kind: "batch", count: out.length, count_voided: voided.length,
          generated_at: new Date().toISOString(),
          rows: out,
          voided: voided,
          distribution: { by_grade: byGrade, by_group: byGroup, by_level: byLevel },
          pipeline_query: "?action=export&scope=batch&limit=" + limit + "&format=pipeline&src=" + encodeURIComponent(src)
        });
      }
      if (!q.code) return reply(400, { ok: false, error: "缺 code" });
      /* 【票 #54 第 1 层 · 读侧收窄 · 2026-10-26 维护者拍板】by-code 只回「存在与否」：
         **不回** m1_raw / m2_answers / m3_answers（逐题作答）、各分、id_hash。
         唯一调用方＝候选页 alreadySubmitted()（publish/candidate/index.html:1771），
         它只读 row.code 判真假 ⇒ 收窄后「已交卷」判定行为不变。
         逐题/整行读取归施测人路径（?action=export，第 3 层加鉴权，票 #44）。 */
      const rows = await pg("GET", "/" + table + "?code=eq." + encodeURIComponent(q.code) + "&select=code,submitted_at&limit=1");
      if (!rows || !rows.length) return reply(404, { ok: false, error: "没有这一份", code: q.code });
      return reply(200, { ok: true, row: { code: rows[0].code, submitted_at: rows[0].submitted_at || null, exists: true } });
    }

    return reply(405, { ok: false, error: "只支持 GET / POST / OPTIONS" });
  } catch (e) {
    return reply(e.status && e.status >= 400 && e.status < 600 ? e.status : 500, {
      ok: false, error: String(e && e.message || e),
      detail: e && e.detail || null
    });
  }
};

/* 本地单测用的导出（不参与线上逻辑）。
   票 #86 起补答通道下线，_mergeM3Patch 随之删除。 */
exports._shapeSelfCheck = shapeSelfCheck;
exports._rowShapeProblems = rowShapeProblems;
