#!/usr/bin/env node
/* 云函数接口自测（票 #45 · 施测人侧落地）
 * ------------------------------------------------------------------
 * 用一个**本地假 PG 网关**跑 cloud/functions/assessment/index.js 的 exports.main，
 * 验证本轮改的三件事（不连生产库、不写生产数据）：
 *   ① 交卷按**白名单**落库：多传的字段一律不落库；分数由服务端算，客户端自报的不采信；
 *      m1_raw 的 -1（未作答）归一为 null，unanswered_m1 照实计数；
 *   ② code 形态校验（EQ-YYYYMMDD-6 位随机码-4 位校验码），不符 400；
 *   ③ 汇总台要的三件事：list 带姓名与等级；export 三档（单份报告 / 批次汇总 /
 *      离线管线 JSON）返回各自的形状，且每次导出在 CLS 留一行结构化日志。
 *
 * 用法：node cloud/verify_export_api.js
 */
"use strict";

const http = require("node:http");
const path = require("node:path");
const assert = require("node:assert");

const HERE = __dirname;
const MOD = path.join(HERE, "functions", "assessment");

/* ---------- 假 PG 网关：模仿 PostgREST 的 select / order / limit / code=eq. ---------- */
const M1 = { dims: [
    { key: "INT", name: "互动方式", score: 12, max: 24, grade: "合格" },
    { key: "SNT", name: "关注重点", score: 11, max: 24, grade: "合格" },
    { key: "TFS", name: "行事依据", score: 12, max: 24, grade: "合格" },
    { key: "JPS", name: "行事节奏", score: 12, max: 24, grade: "合格" }
  ], short: { key: "INT", name: "互动方式", grade: "合格" } };
const M2 = { dims: [], total: 1.85, grade: "待提升", short: { key: "regu", name: "情绪稳定", grade: "待提升" }, needReview: [], consistency: [] };
const M3 = { total: 26, pct: 0, t: -14.8, grade: "待提升", dims: [], wrong: [] };

let ROWS = [
  { id: 1, code: "EQ-20261025-ZXN7TL-B454", respondent_name: "汪洋", id_last4: "5615",
    group_name: null, level: null, dept: null, started_at: "2026-10-25T13:23:00+08:00",
    submitted_at: "2026-10-25T13:44:22+08:00", duration_ms: 1236174,
    m1_raw: new Array(96).fill(1), m1_scores: M1, m2_result: M2, m3_result: M3,
    m2_answers: null, m3_answers: null, limit_hint: null, unanswered_m1: 0 },
  { id: 2, code: "EQ-20261025-ABCDEF-1234", respondent_name: "李四", id_last4: "7890",
    group_name: "餐饮二部", level: "主管", dept: "餐饮部", started_at: "2026-10-25T14:00:00+08:00",
    submitted_at: "2026-10-25T14:20:00+08:00", duration_ms: 1200000,
    m1_raw: new Array(96).fill(0).map((v, i) => (i < 90 ? v : null)), m1_scores: M1, m2_result: M2, m3_result: M3,
    m2_answers: null, m3_answers: null, limit_hint: null, unanswered_m1: 6 }
];
let POSTED = [];

function server() {
  return http.createServer((req, res) => {
    const u = new URL(req.url, "http://127.0.0.1");
    if (req.method === "POST") {
      let body = "";
      req.on("data", (c) => { body += c; });
      req.on("end", () => {
        const row = JSON.parse(body || "{}");
        POSTED.push(row);
        row.id = 900 + POSTED.length;
        res.writeHead(201, { "Content-Type": "application/json" });
        res.end(JSON.stringify([row]));
      });
      return;
    }
    const q = u.searchParams;
    let rows = ROWS.slice();
    const codeEq = q.get("code");
    if (codeEq) rows = rows.filter((r) => r.code === codeEq.replace(/^eq\./, ""));
    const sel = q.get("select");
    if (sel) {
      const keys = sel.split(",").map((s) => s.trim());
      rows = rows.map((r) => { const o = {}; for (const k of keys) o[k] = r[k] === undefined ? null : r[k]; return o; });
    }
    const lim = parseInt(q.get("limit") || "50", 10);
    rows = rows.slice(0, lim);
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify(rows));
  });
}

function ev(method, queryString, body) {
  return { httpMethod: method, queryStringParameters: queryString || {}, body: body === undefined ? undefined : JSON.stringify(body) };
}

async function main() {
  const srv = server();
  await new Promise((r) => srv.listen(0, "127.0.0.1", r));
  const port = srv.address().port;
  process.env.PG_BASE = "http://127.0.0.1:" + port + "/v1/rdb/rest";
  process.env.PG_KEY = "test-key";
  process.env.PG_TABLE = "responses";
  const { main: fn } = require(path.join(MOD, "index.js"));

  const logs = [];
  const realLog = console.log;
  console.log = (...a) => { logs.push(a.join(" ")); };

  let failed = 0;
  const check = (name, cond, extra) => {
    if (cond) { realLog("  ✓ " + name); }
    else { failed++; realLog("  ✗ " + name + (extra ? "  ← " + extra : "")); }
  };

  try {
    /* ---------- ① 白名单 ---------- */
    realLog("① 交卷按白名单落库");
    const m1 = new Array(96).fill(0).map((v, i) => (i < 90 ? 0 : -1));   /* 6 题未作答（-1） */
    const r1 = await fn(ev("POST", {}, {
      code: "EQ-20261025-ZXN7TL-B454",
      respondent_name: "汪洋", id_last4: "5615",
      started_at: "2026-10-25T13:23:00Z", duration_ms: 1234,
      m1_raw: m1,
      m1_scores: { cheat: true },          /* 客户端自报分数 —— 必须不采信 */
      m2_result: { cheat: true },
      m3_result: { cheat: true },
      answered_at: "2020-01-01",           /* 多传的字段 —— 必须不落库 */
      evil_column: "x",
      __proto__hack: 1
    }));
    check("201 落库", r1.statusCode === 201, JSON.stringify(r1.body).slice(0, 200));
    const row = POSTED[0] || {};
    /* 白名单 17 列（12 项客户端填 + 5 项服务端算）；另有 id 是数据库自己给的
       （id BIGINT GENERATED ALWAYS AS IDENTITY），不属客户端可控的列。 */
    const EXPECT = ["code", "respondent_name", "id_last4", "group_name", "level", "dept",
      "started_at", "duration_ms", "m1_raw", "m2_answers", "m3_answers", "limit_hint",
      "submitted_at", "m1_scores", "m2_result", "m3_result", "unanswered_m1", "id"];
    const got = Object.keys(row).sort();
    check("落库列集合 = 白名单（17 列）+ 数据库自带的 id", JSON.stringify(got) === JSON.stringify(EXPECT.slice().sort()),
      "实得 " + JSON.stringify(got));
    check("多传字段没落库（answered_at / evil_column）", !("answered_at" in row) && !("evil_column" in row));
    check("客户端自报分数不采信（m1_scores 是服务端算的）",
      !!row.m1_scores && row.m1_scores.cheat === undefined && Array.isArray(row.m1_scores.dims));
    check("m1_raw 的 -1 归一为 null", Array.isArray(row.m1_raw) && row.m1_raw[95] === null && row.m1_raw[0] === 0);
    check("unanswered_m1 照实计数（6）", row.unanswered_m1 === 6, String(row.unanswered_m1));
    check("submitted_at 用服务器时间", typeof row.submitted_at === "string" && row.submitted_at !== "2020-01-01");

    /* ---------- ② code 形态校验 ---------- */
    realLog("② code 形态校验");
    const r2 = await fn(ev("POST", {}, { code: "随便写一个", m1_raw: new Array(96).fill(0) }));
    check("形态不对 → 400", r2.statusCode === 400, String(r2.statusCode));
    const r3 = await fn(ev("POST", {}, { code: "EQ-20261025-ZXN7TL-B454", m1_raw: new Array(95).fill(0) }));
    check("不是 96 题 → 400", r3.statusCode === 400, String(r3.statusCode));
    process.env.CODE_CHECK = "off";
    const r4 = await fn(ev("POST", {}, { code: "随便写一个", m1_raw: new Array(96).fill(0) }));
    check("CODE_CHECK=off 时放行", r4.statusCode === 201, String(r4.statusCode));
    delete process.env.CODE_CHECK;

    /* ---------- ③ 汇总台三件事 ---------- */
    realLog("③ list / export");
    const rl = await fn(ev("GET", { action: "list", limit: "50" }));
    const lrows = JSON.parse(rl.body).rows;
    check("list 带姓名", lrows.length === 2 && lrows[0].respondent_name === "汪洋");
    check("list 带等级（综合档）", lrows[0].grade === "待提升", JSON.stringify(lrows[0].grade));
    check("list 不回传逐题 / 分数", !("m1_raw" in lrows[0]) && !("m1_scores" in lrows[0]));
    check("list 的默认列齐（8 列 + 等级）",
      ["code", "respondent_name", "id_last4", "group_name", "level", "submitted_at", "duration_ms", "unanswered_m1", "grade"]
        .every((k) => k in lrows[0]), JSON.stringify(Object.keys(lrows[0])));

    const re = await fn(ev("GET", { action: "export", code: "EQ-20261025-ZXN7TL-B454", src: "hr" }));
    const one = JSON.parse(re.body);
    check("单份导出：report 齐（m1/m2/m3/compose + 抬头）",
      !!one.report && !!one.report.m1 && !!one.report.m2 && !!one.report.m3 && !!one.report.compose &&
      one.report.name === "汪洋" && one.report.idLast4 === "5615");
    check("单份导出：compose 算得出综合档", one.report.compose.grade === "待提升" &&
      Array.isArray(one.report.compose.items) && one.report.compose.items.length === 3);
    check("单份导出：不含逐题作答", !JSON.stringify(one.report).includes('"m1_raw"'));

    const rb = await fn(ev("GET", { action: "export", scope: "batch", limit: "50", src: "hr" }));
    const batch = JSON.parse(rb.body);
    check("批次导出：rows + distribution", Array.isArray(batch.rows) && batch.rows.length === 2 &&
      !!batch.distribution.by_grade && !!batch.distribution.by_group);
    check("批次导出：m1 四维分带出来", Array.isArray(batch.rows[0].m1_dims) && batch.rows[0].m1_dims.length === 4);

    const rp = await fn(ev("GET", { action: "export", scope: "batch", limit: "50", format: "pipeline", src: "hr" }));
    const pipe = JSON.parse(rp.body);
    check("管线导出：{meta, respondents}", !!pipe.meta && Array.isArray(pipe.respondents));
    check("管线导出：未答完的份子被排除并单列",
      pipe.respondents.length === 1 && pipe.excluded.length === 1 && pipe.excluded[0].code === "EQ-20261025-ABCDEF-1234",
      JSON.stringify(pipe.excluded));
    check("管线导出：responses 是 96 个 0/1",
      pipe.respondents[0].responses.length === 96 && pipe.respondents[0].responses.every((v) => v === 0 || v === 1));
    check("管线导出：id 是测评编号", pipe.respondents[0].id === "EQ-20261025-ZXN7TL-B454");

    /* ---------- ④ 导出留一行结构化日志 ---------- */
    realLog("④ 导出日志（票 #36 R2-3 选 B：留痕本轮不做，位置先留出来）");
    const lines = logs.filter((l) => l.indexOf("assessment_export") >= 0);
    check("每次导出都有一行日志（单份 1 + 批次 1 + 管线 1）", lines.length === 3, "实得 " + lines.length);
    const j = JSON.parse(lines[0]);
    check("日志含 时间 + 件数 + 来源",
      typeof j.at === "string" && typeof j.count === "number" && typeof j.source === "string" && j.source === "hr",
      lines[0]);
  } finally {
    console.log = realLog;
    srv.close();
  }

  realLog(failed ? ("\n自测未通过：" + failed + " 项") : "\n自测全部通过 ✓");
  process.exit(failed ? 1 : 0);
}

main();
