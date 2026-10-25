#!/usr/bin/env node
/* 生成一份完整的模拟作答（96 题逐题 + 76 + 40），并用**服务端的计分代码**算出三项。
   为什么不用 pilot/simulate.py：那份样例只出分数、不出逐题作答，
   报告里的「可信度」与「两极倾向」就都算不出来（只能写"未留存"）。
   用法：node pilot/simulate_full.mjs --out pilot/out/结果JSON_模拟演示.json --seed 7 */
const fs = require("node:fs");
const path = require("node:path");
const ROOT = path.join(__dirname, "..");

function arg(name, def) {
  const i = process.argv.indexOf("--" + name);
  return i > 0 ? process.argv[i + 1] : def;
}

/* 可复现的伪随机（LCG） */
let seed = parseInt(arg("seed", "7"), 10) || 7;
/* mulberry32：用 Math.imul，避开 JS 浮点精度把低位算坏（踩过：
   朴素 LCG 的 seed*1103515245 超出 2^53，低位乱掉 ⇒ 每次都抽到同一个选项）。 */
function rnd() {
  seed = (seed + 0x6D2B79F5) | 0;
  let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
  t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
  return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
}
function pickIdx(weights) {
  /* 权重是「各选项的相对份额」⇒ 先把随机数放大到总权重再累计。
     （踩过：拿 r 直接跟累计和比，永远落在第 0 项 ⇒ 每题都选同一个。） */
  let total = 0;
  for (const w of weights) total += w;
  let r = rnd() * total, acc = 0;
  for (let i = 0; i < weights.length; i++) { acc += weights[i]; if (r <= acc) return i; }
  return weights.length - 1;
}

const items = JSON.parse(fs.readFileSync(path.join(ROOT, "items", "m1_items.json"), "utf8")).items;
const eq = JSON.parse(fs.readFileSync(path.join(ROOT, "data", "eq_bank_encoded.json"), "utf8"));
const keys = require(path.join(ROOT, "cloud", "functions", "assessment", "keys.json"));
const { scoreAll } = require(path.join(ROOT, "cloud", "functions", "assessment", "score.js"));

/* 人格特质：每维按不同的「答在有效端」概率作答，避免出现整段同侧 */
const P = { INT: 0.72, SNT: 0.66, TFS: 0.70, JPS: 0.64 };
const m1_raw = items.map((it) => {
  const p = P[it.dim] !== undefined ? P[it.dim] : 0.68;
  const anchorA = String(it.anchor || "a").toLowerCase() !== "b";
  const onAnchor = rnd() < p;
  if (onAnchor) return anchorA ? 0 : 1;
  return anchorA ? 1 : 0;
});

/* 情景处理：16 道自评（1–7）+ 60 道情境（0–3） */
const m2 = {};
const nSelf = (eq.self_items || []).length;
for (let i = 0; i < nSelf; i++) {
  /* 自评：偏中间 4–5，偶尔 6 或 3 */
  m2[i] = pickIdx([0.5, 0.8, 1.2, 2.5, 3.5, 1.5, 0.5]) + 1;   /* 1–7 级，偏向中间偏上 */
}
const sjt = eq.sjt || [];
/* 一致性题对：同一情境的两种问法 ⇒ 真实被试会选**同一个倾向**（同字母）。
   所以按题对（c 字段）成对作答，而不是逐题乱选 ——
   否则模拟出来的「一致性」全是低可信度，演示效果失真。 */
const pairLetter = {};
for (let j = 0; j < sjt.length; j++) {
  const ck = sjt[j].c || ("S" + j);
  if (pairLetter[ck] === undefined) {
    const best = "ABCD".indexOf(String(sjt[j].answer || "A").toUpperCase());
    const w = [0, 0, 0, 0];
    w[best >= 0 ? best : 0] = 6;         /* 六成选最优 */
    for (let k = 0; k < 4; k++) if (k !== (best >= 0 ? best : 0)) w[k] = 1.2;
    pairLetter[ck] = pickIdx(w);
  }
}
for (let j = 0; j < sjt.length; j++) {
  const ck = sjt[j].c || ("S" + j);
  m2[nSelf + j] = pairLetter[ck];       /* 同一题对选同一个倾向 */
}

/* 逻辑分析：40 题，六成答对 */
const m3 = [];
for (let i = 0; i < 40; i++) {
  const q = (keys.m3 && keys.m3.questions && keys.m3.questions[i]) || {};
  const ans = typeof q.answer === "number" ? q.answer : null;
  const w = [1, 1, 1, 1];
  if (ans !== null && ans >= 0 && ans < 4) w[ans] = 6;
  m3.push(pickIdx(w));
}

const payload = {
  code: "SIM-20261025-DEMO01",
  respondent_name: "模拟候选人（演示数据 · 非真人作答）",
  id_last4: "0000",
  m1_raw: m1_raw,
  m2_answers: m2,
  m3_answers: m3,
  started_at: new Date(Date.now() - 26 * 60 * 1000).toISOString(),
  duration_ms: 26 * 60 * 1000
};
const out = scoreAll(payload);

const data = {
  tool: "云上文旅集团核心人才系列测试",
  version: "20261025",
  code: payload.code,
  name: payload.respondent_name,
  idLast4: payload.id_last4,
  date: new Date().toISOString(),
  m1: out.m1, m2: out.m2, m3: out.m3,
  m1_raw: m1_raw, m2_answers: m2, m3_answers: m3,
  unanswered_m1: 0, duration_ms: payload.duration_ms
};
const outPath = arg("out", path.join(ROOT, "pilot", "out", "结果JSON_模拟演示.json"));
fs.writeFileSync(outPath, JSON.stringify(data, null, 1), "utf8");
console.log("已生成：" + outPath);
console.log("第一项四维：" + (out.m1.dims || []).map((d) => d.name + " " + d.score + "/" + d.max + " " + d.grade).join("；"));
console.log("第二项：" + out.m2.total + "/5.00 " + out.m2.grade + "；第三项：" + out.m3.pct + " P " + out.m3.pct + " " + out.m3.grade);
