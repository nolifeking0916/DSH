#!/usr/bin/env node
/* 交卷形状门（票 #83 长度/题位 + 票 #85 第二项值域 · 2026-10-26）
 * ---------------------------------------------------------------------------
 * 守的是四件事：
 *   ① **第三项长度必须 = 40**：多一项（41）/ 少一项（39）/ 整个缺（0）都在**落库前**被拒（400）；
 *      错误信息里能一眼看出「是第几项、期望几项、实到几项」。
 *   ② **完整载荷仍能收**：96 / 76 / 40 的正常交卷照旧 201，落库体的长度就是 96 / 76 / 40。
 *   ③ **不误伤已落库的合法数据**：public.responses 那 7 行的**形状**（只读快照
 *      src/data/responses_shape_20261026.json）在新规则下逐行仍然合法 ——
 *      其中「第三项只答了 20 题」的两行（页面上「仍然提交（按未作答计分）」那条路径）
 *      照旧能交（长度是 40，答没答满不是长度问题）。
 *   ④ **第二项值域必须是 0-3 整数（票 #85）**：已作答题位的值若是 -1 / 4 / 7 /
 *      字符串 / 小数 / null ⇒ 落库前 400，错误信息点明「第二项 / 题位 / 应 0-3 / 实到值」；
 *      值域两端 0 与 3 都合法、稀疏作答照旧 201（不查键数，「仍然提交」路径不堵）。
 *
 * 全程**不连生产库**：跑的是 cloud/functions/assessment/index.js 的 exports.main，
 * PG 网关指向本机 127.0.0.1 的假网关（同一套路见 cloud/verify_export_api.js）。
 * ⇒ 库里的行数、内容一字不动（本脚本一个写请求都不往真库发）。
 *
 * 用法：node src/verify_submit_shape.js
 * 退出码 0 = 全绿；非 0 = 有项未通过（逐条打印）。
 */
"use strict";

const http = require("node:http");
const path = require("node:path");
const fs = require("node:fs");

const HERE = __dirname;
const ROOT = path.dirname(HERE);
const MOD = path.join(ROOT, "cloud", "functions", "assessment");
const SNAPSHOT = path.join(HERE, "data", "responses_shape_20261026.json");

const M1_N = 96;   /* 第一项题数 */
const M2_N = 76;   /* 第二项题数（自评 16 + 情境 60） */
const M3_N = 40;   /* 第三项题数 */
const CODE = "EQ-20261026-QA7Z3M-ABCD";   /* 形态合法（EQ-YYYYMMDD-6 位随机码-4 位校验码） */

const results = [];
function check(name, ok, detail) {
  results.push({ name: name, ok: !!ok, detail: detail || "" });
  console.log((ok ? "  [OK ] " : "  [FAIL] ") + name + (detail ? "：" + detail : ""));
}
function fail(msg) { console.error("FAIL: " + msg); process.exit(1); }

/* ---------------- 假 PG 网关（本机）：只认 POST /responses 与 GET ---------------- */
let INSERTS = [];    /* 收到的插入行 */
let CALLS = [];      /* 收到的全部请求（用来断言「没有 PATCH / DELETE / PUT」） */
function fakePg() {
  return http.createServer((req, res) => {
    let body = "";
    req.on("data", (c) => { body += c; });
    req.on("end", () => {
      CALLS.push({ method: req.method, url: req.url });
      if (req.method === "POST") {
        const row = JSON.parse(body || "{}");
        row.id = 900 + INSERTS.length;
        INSERTS.push(row);
        res.writeHead(201, { "Content-Type": "application/json" });
        res.end(JSON.stringify([row]));
        return;
      }
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end("[]");
    });
  });
}

/* ---------------- 载荷构件 ---------------- */
function m1Payload(n, holes) {
  const a = new Array(n).fill(1);
  for (let i = 0; i < (holes || 0); i++) a[i] = null;   /* null = 未作答 */
  return a;
}
function m2Payload(n) {
  const o = {};
  for (let i = 0; i < n; i++) o[String(i)] = i % 4;       /* 0-3 的选项下标 */
  return o;
}
function m3Payload(n, holes) {
  const a = new Array(n).fill(2);
  for (let i = 0; i < (holes || 0); i++) a[i] = null;     /* null = 未作答（占位） */
  return a;
}
function payload(over) {
  const p = {
    code: CODE,
    respondent_name: "门禁自检",
    id_last4: "0000",
    group_name: "门禁",
    level: "门禁",
    dept: "门禁",
    m1_raw: m1Payload(M1_N),
    m2_answers: m2Payload(M2_N),
    m3_answers: m3Payload(M3_N),
    started_at: "2026-10-26T20:00:00.000Z",
    duration_ms: 1000
  };
  return Object.assign(p, over || {});
}

/* 票 #87：前置形状自检把错误体统一成 reasons[]，错误文案期望改认结构化原因
   （方案 A：整份拒收不落库 + reasons + CLS 留痕；错误串不再逐条点名模块）。 */
function reasonOf(json, module) {
  const rs = (json && json.reasons) || [];
  return rs.find((x) => x && x.module === module) || null;
}

async function main() {
  if (!fs.existsSync(MOD + "/index.js")) fail("找不到云函数 " + MOD + "/index.js");
  const server = fakePg();
  await new Promise((r) => server.listen(0, "127.0.0.1", r));
  const port = server.address().port;
  process.env.PG_BASE = "http://127.0.0.1:" + port + "/rdb/rest";
  process.env.PG_KEY = "fake-key";
  process.env.PG_TABLE = "responses";
  const handler = require(path.join(MOD, "index.js")).main;

  const before = INSERTS.length;
  async function post(p) {
    const r = await handler({ httpMethod: "POST", body: JSON.stringify(p), headers: {} });
    let j = null;
    try { j = JSON.parse(r.body); } catch (e) { j = null; }
    return { status: r.statusCode, json: j, err: (j && j.error) || "" };
  }

  console.log("\n=== ① 第三项长度：多一项 / 少一项 / 整个缺 ⇒ 落库前被拒 ===");
  {
    const r = await post(payload({ m3_answers: m3Payload(M3_N + 1) }));
    check("第三项 41 项 → 400", r.status === 400, "实得状态 " + r.status);
    check("41 项的错误信息点明「第三项 / 期望 40 / 实得 41」",
      reasonOf(r.json, "m3") &&
      reasonOf(r.json, "m3").expected === 40 && reasonOf(r.json, "m3").actual === 41,
      JSON.stringify(r.json && r.json.reasons));
    check("41 项**没有**落库", INSERTS.length === before, "插入行数 " + (INSERTS.length - before));
  }
  {
    const r = await post(payload({ m3_answers: m3Payload(M3_N - 1) }));
    check("第三项 39 项（缺一项）→ 400", r.status === 400, "实得状态 " + r.status);
    check("39 项的错误信息点明「应为 40 / 实得 39」",
      reasonOf(r.json, "m3") &&
      reasonOf(r.json, "m3").expected === 40 && reasonOf(r.json, "m3").actual === 39,
      JSON.stringify(r.json && r.json.reasons));
    check("39 项**没有**落库", INSERTS.length === before, "插入行数 " + (INSERTS.length - before));
  }
  {
    const p = payload();
    delete p.m3_answers;
    const r = await post(p);
    check("第三项整个缺 → 400", r.status === 400, "实得状态 " + r.status);
    check("整个缺的错误信息写明「实得 0」",
      reasonOf(r.json, "m3") && reasonOf(r.json, "m3").actual === null,
      JSON.stringify(r.json && r.json.reasons));
    check("整个缺**没有**落库", INSERTS.length === before, "插入行数 " + (INSERTS.length - before));
  }
  {
    const bad = m3Payload(M3_N);
    bad[39] = 7;                                  /* 值域越界（既有校验不能被改坏） */
    const r = await post(payload({ m3_answers: bad }));
    check("第三项值域越界（值 7）仍 → 400", r.status === 400, "实得状态 " + r.status);
    check("值域越界的错误信息仍是既有的「不是 0-3」", r.err.indexOf("不是 0-3") >= 0, r.err);
    check("值域越界**没有**落库", INSERTS.length === before, "插入行数 " + (INSERTS.length - before));
  }

  console.log("\n=== ② 完整载荷仍能收（96 / 76 / 40）===");
  {
    const r = await post(payload());
    check("完整载荷 → 201", r.status === 201, "实得状态 " + r.status + " " + r.err);
    check("完整载荷落库了 1 行", INSERTS.length === before + 1, "插入行数 " + (INSERTS.length - before));
    const row = INSERTS[INSERTS.length - 1] || {};
    check("落库体第一项 96 题", Array.isArray(row.m1_raw) && row.m1_raw.length === M1_N,
      "实得 " + (row.m1_raw ? row.m1_raw.length : "无"));
    check("落库体第二项 76 个题位", row.m2_answers && Object.keys(row.m2_answers).length === M2_N,
      "实得 " + (row.m2_answers ? Object.keys(row.m2_answers).length : "无"));
    check("落库体第三项 40 题", Array.isArray(row.m3_answers) && row.m3_answers.length === M3_N,
      "实得 " + (row.m3_answers ? row.m3_answers.length : "无"));
    check("响应回显三项缺口都是 0", r.json && r.json.gaps &&
      r.json.gaps.m1 === 0 && r.json.gaps.m2 === 0 && r.json.gaps.m3 === 0,
      JSON.stringify(r.json && r.json.gaps));
  }

  console.log("\n=== ③ 不误伤：既有的合法交卷路径照旧能过 ===");
  {
    const r = await post(payload({ m3_answers: m3Payload(M3_N, 20) }));
    check("第三项 40 个题位但只答了 20 题（页面上「仍然提交」那条路径）→ 201",
      r.status === 201, "实得状态 " + r.status + " " + r.err);
    check("该份的第三项缺口被回显为 20 题", r.json && r.json.gaps && r.json.gaps.m3 === 20,
      JSON.stringify(r.json && r.json.gaps));
  }
  {
    const r = await post(payload({ m2_answers: m2Payload(20) }));
    check("第二项只答了 20 题（稀疏对象）→ 201（不该拦）", r.status === 201, "实得状态 " + r.status + " " + r.err);
  }
  {
    const m2 = m2Payload(M2_N);
    m2[String(M2_N)] = 1;                          /* 题位 76 越界 */
    const r = await post(payload({ m2_answers: m2 }));
    check("第二项题位越界（键 76）→ 400", r.status === 400, "实得状态 " + r.status);
    check("第二项越界的错误信息点明「第二项 / 0-75 / 共 76 题」",
      reasonOf(r.json, "m2") && reasonOf(r.json, "m2").kind === "shape" &&
      reasonOf(r.json, "m2").expected === "slot 0-75" &&
      String(reasonOf(r.json, "m2").actual) === String(M2_N),
      JSON.stringify(r.json && r.json.reasons));
  }
  {
    const r = await post(payload({ m1_raw: m1Payload(M1_N - 1) }));
    check("第一项 95 题（既有校验）仍 → 400", r.status === 400, "实得状态 " + r.status);
    check("第一项的错误信息仍是既有的「实得 95」",
      reasonOf(r.json, "m1") && reasonOf(r.json, "m1").expected === M1_N &&
      reasonOf(r.json, "m1").actual === M1_N - 1,
      JSON.stringify(r.json && r.json.reasons));
  }

  console.log("\n=== ③-补 第二项值域：已作答题位的值必须是 0-3 整数（票 #85）===");
  /* 每个拒绝样本都断言：400 + 错误串含「第二项 / 题位 / 0-3 / 实到值」+ 没落库。
     构造时只动一个题位，便于错误信息定位。 */
  const valueBad = [
    { val: -1, label: "-1", shown: "-1" },
    { val: 4, label: "4", shown: "4" },
    { val: 7, label: "7（票 #85 的超范围下标）", shown: "7" },
    { val: 1.5, label: "1.5（小数）", shown: "1.5" },
    { val: "2", label: "\"2\"（字符串）", shown: "\"2\"" },
    { val: null, label: "null（键在但值空 = 形状坏，不是未答）", shown: "null" },
  ];
  for (const bad of valueBad) {
    const m2 = m2Payload(M2_N);
    m2["37"] = bad.val;
    const before = INSERTS.length;
    const r = await post(payload({ m2_answers: m2 }));
    check("第二项题位 37 值为 " + bad.label + " → 400", r.status === 400, "实得状态 " + r.status);
    check("错误信息点明「第二项 / 题位 37 / 应 0-3 / 实得 " + bad.shown + "」",
      r.err.indexOf("第二项") >= 0 && r.err.indexOf("题位 37") >= 0 &&
      r.err.indexOf("0-3") >= 0 && r.err.indexOf("实得 " + bad.shown) >= 0, r.err);
    check("值为 " + bad.label + " 的载荷**没有**落库", INSERTS.length === before,
      "插入行数 " + (INSERTS.length - before));
  }
  {
    /* 值域两端 + 稀疏：只答 30 题，值只取 0 与 3（票 #85 验收点名的边界样本） */
    const m2 = {};
    for (let i = 0; i < 30; i++) m2[String(i)] = (i % 2 === 0) ? 0 : 3;
    const before = INSERTS.length;
    const r = await post(payload({ m2_answers: m2 }));
    check("第二项只答 30 题且值只有 0/3（边界样本）→ 201", r.status === 201,
      "实得状态 " + r.status + " " + r.err);
    check("该份落库 1 行，落库体题位 29 的值 3 原样保留（服务端不改写选项下标）",
      INSERTS.length === before + 1 && INSERTS[INSERTS.length - 1].m2_answers["29"] === 3,
      "插入行数 " + (INSERTS.length - before));
    check("缺口回显 m2 = 46（76-30，不查键数但缺口照算）",
      r.json && r.json.gaps && r.json.gaps.m2 === 46, JSON.stringify(r.json && r.json.gaps));
  }
  {
    /* 76 题答满且全取两端值 0/3 —— 完整载荷在 #85 下照样收 */
    const m2 = {};
    for (let i = 0; i < M2_N; i++) m2[String(i)] = (i % 2 === 0) ? 0 : 3;
    const r = await post(payload({ m2_answers: m2 }));
    check("第二项 76 题答满、值只有 0/3 → 201", r.status === 201,
      "实得状态 " + r.status + " " + r.err);
  }

  console.log("\n=== ④ 已落库的 7 行真实数据：形状在新规则下逐行仍合法 ===");
  {
    const snap = JSON.parse(fs.readFileSync(SNAPSHOT, "utf8"));
    check("快照行数 = 7（public.responses 的真实行数）",
      snap.rows.length === 7 && snap.row_count === 7, "快照 " + snap.rows.length + " 行");
    let allOk = true, detail = "";
    for (const row of snap.rows) {
      if (row.m1_len !== M1_N) { allOk = false; detail = row.code + " 第一项 " + row.m1_len; break; }
      if (row.m2_max_key !== null && (row.m2_max_key < 0 || row.m2_max_key >= M2_N)) {
        allOk = false; detail = row.code + " 第二项题位 " + row.m2_max_key; break;
      }
      if (row.m3_len !== null && row.m3_len !== M3_N) {
        allOk = false; detail = row.code + " 第三项长度 " + row.m3_len; break;
      }
    }
    check("7 行的形状全部合法（第一项 96 / 第二项题位 ≤75 / 第三项长度 40）", allOk, detail);
    const legacy = snap.rows.filter((r) => r.legacy);
    check("其中 1 行是加列前的遗留行（m3 为 null，不追溯）",
      legacy.length === 1 && legacy[0].m3_len === null, JSON.stringify(legacy.map((r) => r.code)));
    const partial = snap.rows.filter((r) => r.m3_len === M3_N && r.m3_answered < M3_N);
    check("其中 2 行第三项只答了一半（真实存在 ⇒ 长度校验不能查「答满」）",
      partial.length === 2, "实得 " + partial.length + " 行：" + partial.map((r) => r.code).join("、"));
    /* 用**同形状**的合成载荷回放（不含任何真实作答内容）：真实数据形状在新规则下必须照样能交 */
    let replayOk = true, replayDetail = "";
    for (const row of snap.rows) {
      const p = payload({
        code: "EQ-20261026-REPLAY-" + row.code.slice(-4),
        m3_answers: row.m3_len === null ? undefined : m3Payload(row.m3_len, row.m3_len - row.m3_answered),
        m2_answers: row.m2_keys === 0 ? {} : m2Payload(row.m2_keys)
      });
      if (p.m3_answers === undefined) delete p.m3_answers;
      const r = await post(p);
      const expect = row.m3_len === null ? 400 : 201;   /* 遗留行：m3 缺 ⇒ 新规则拒（只管新交卷） */
      if (r.status !== expect) { replayOk = false; replayDetail = row.code + " 实得 " + r.status + "（期望 " + expect + "）" + r.err; break; }
    }
    check("按真实形状回放：6 行照旧 201，遗留行按新规则 400（历史行不受影响）", replayOk, replayDetail);
  }

  console.log("\n=== ⑤ 全程没有碰生产库 ===");
  {
    const writes = CALLS.filter((c) => c.method !== "GET");
    check("假网关只收到交卷用的 POST（没有 PATCH / DELETE / PUT）",
      writes.every((c) => c.method === "POST" && /\/responses$/.test(c.url)),
      JSON.stringify(writes.map((c) => c.method + " " + c.url).slice(0, 5)));
    check("本脚本连的是本机假网关（不是生产库）",
      /^http:\/\/127\.0\.0\.1:\d+\//.test(process.env.PG_BASE), process.env.PG_BASE);
  }

  server.close();

  const bad = results.filter((r) => !r.ok);
  console.log("\n" + (results.length - bad.length) + "/" + results.length + " 项通过");
  if (bad.length) {
    console.log("未通过：");
    for (const b of bad) console.log("  · " + b.name + (b.detail ? "：" + b.detail : ""));
    process.exit(1);
  }
  console.log("全绿。");
  process.exit(0);
}

main().catch((e) => { console.error(e); process.exit(1); });
