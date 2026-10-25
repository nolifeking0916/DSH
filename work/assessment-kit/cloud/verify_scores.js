/* 服务端计分 vs 客户端计分 · 逐格交叉验算（票 #26 · 裁定 Q1=B 的验收门）
 *
 * 为什么要这道门：判据与计分移到服务端之后，「施测人报告页看到的分」与「云端存的分」
 * 必须永远是同一个数。两边若漂移，票 #26 的信效度统计就全建立在错的口径上。
 *
 * 验法：客户端用 report.js + 客户端数据算一遍；服务端用 score.js + keys.json 算一遍；
 * 同一份作答，两边输出必须**逐字节相同**（JSON.stringify 后完全相等）。
 *
 * 覆盖：
 *   1) 120 份合成样本的 96 题逐题作答（第一项全覆盖，含全 0/全 1 的极端）
 *   2) 随机作答 200 份（第一项 + 第二项 + 第三项，含未答的空位）
 *   3) 空作答、单题作答等退化输入
 *
 * 用法：node cloud/verify_scores.js
 */
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.dirname(HERE);
const CLIENT_DATA = path.join(HERE, "out", "client_data.json");
const REPORT_SRC = path.join(ROOT, "src", "modules", "report.js");

function fail(msg) { console.error("FAIL: " + msg); process.exit(1); }

if (!fs.existsSync(CLIENT_DATA)) fail("找不到 " + CLIENT_DATA + "，先跑 python3 cloud/build_keys.py");

/* ---------- 客户端：report.js + 客户端数据 ---------- */
const DATA = JSON.parse(fs.readFileSync(CLIENT_DATA, "utf8"));
const reportSrc = fs.readFileSync(REPORT_SRC, "utf8");
const copySrc = fs.readFileSync(path.join(ROOT, "src", "data", "copy.js"), "utf8");
const sandbox = { console };
sandbox.window = sandbox;
vm.createContext(sandbox);
vm.runInContext(copySrc, sandbox, { filename: "copy.js" });
vm.runInContext("window.__DATA__ = " + JSON.stringify(DATA), sandbox, { filename: "__DATA__" });
vm.runInContext(reportSrc, sandbox, { filename: "report.js" });
const REP = sandbox.window.REP;
if (!REP || typeof REP.score !== "function") fail("report.js 没导出 REP.score");

/* ---------- 服务端：score.js + keys.json ---------- */
const { scoreAll } = require(path.join(HERE, "functions", "assessment", "score.js"));

/* ---------- 造样本 ---------- */
const rnd = (n) => Math.floor(Math.random() * n);
function randomPayload(seed) {
  const m1_raw = [];
  for (let i = 0; i < 96; i++) m1_raw.push(Math.random() < 0.08 ? null : rnd(2));
  const m2_answers = {};
  const n2 = DATA.eq.self_items.length + DATA.eq.sjt.length;
  for (let i = 0; i < n2; i++) {
    if (Math.random() < 0.08) continue;
    m2_answers[String(i)] = rnd(4);
  }
  const m3_answers = [];
  for (let i = 0; i < DATA.m3.questions.length; i++) {
    m3_answers.push(Math.random() < 0.08 ? null : rnd(DATA.m3.questions[i].options.length));
  }
  return { code: "EQ-TEST-" + seed, m1_raw: m1_raw, m2_answers: m2_answers, m3_answers: m3_answers };
}

function clientScore(payload) {
  const S = { a: { m1: payload.m1_raw.slice(), m2: Object.assign({}, payload.m2_answers), m3: payload.m3_answers.slice() } };
  return REP.score(S).out;
}

function compare(label, payload) {
  const a = JSON.stringify(clientScore(payload));
  const b = JSON.stringify(scoreAll(payload));
  if (a === b) return true;
  console.error("分歧：" + label);
  console.error("  客户端：" + a.slice(0, 400));
  console.error("  服务端：" + b.slice(0, 400));
  return false;
}

let checked = 0, bad = 0;

/* 1) 合成样本（第一项 96 题全覆盖） */
const synthPath = path.join(ROOT, "pilot", "out", "samples.json");
if (fs.existsSync(synthPath)) {
  const samples = JSON.parse(fs.readFileSync(synthPath, "utf8"));
  for (const r of samples.respondents) {
    const payload = { code: r.id, m1_raw: r.responses, m2_answers: {}, m3_answers: [] };
    checked++;
    if (!compare("合成样本 " + r.id, payload)) bad++;
  }
} else {
  console.log("（没有 pilot/out/samples.json，跳过第一组：先跑 python3 pilot/simulate.py）");
}

/* 2) 随机作答（含未答空位） */
for (let i = 0; i < 200; i++) {
  const payload = randomPayload(i);
  checked++;
  if (!compare("随机样本 #" + i, payload)) bad++;
}

/* 3) 退化输入 */
const edge = [
  { code: "EDGE-EMPTY", m1_raw: new Array(96).fill(null), m2_answers: {}, m3_answers: [] },
  { code: "EDGE-ONE", m1_raw: [0].concat(new Array(95).fill(null)), m2_answers: {}, m3_answers: [] },
  { code: "EDGE-ALL0", m1_raw: new Array(96).fill(0), m2_answers: {}, m3_answers: [] },
  { code: "EDGE-ALL1", m1_raw: new Array(96).fill(1), m2_answers: {}, m3_answers: [] }
];
for (const p of edge) { checked++; if (!compare(p.code, p)) bad++; }

console.log(`交叉验算：${checked} 份作答，客户端 vs 服务端逐字节比对 → ${bad === 0 ? "全部一致（0 处分歧）" : bad + " 份有分歧"}`);
process.exit(bad === 0 ? 0 : 1);
