#!/usr/bin/env node
/* 模拟试测执行器 —— 票 #24（模拟版）
 *
 * 关键约束：**不在 Python 里重写一遍计分**。这个脚本直接吃成品 dist 里的
 * `window.__DATA__`，直接跑 src/modules/report.js 的 `window.REP`，也就是
 * 施测人拿到结果 JSON 后真正用的那段计分与切档代码。Python 侧 analyze.py
 * 会独立复算一遍，两边逐格比对 —— 两套独立实现给出同一个数，才说明计分口径
 * 没有隐含分歧。
 *
 * 用法：node pilot/run_pilot.mjs
 * 产物：pilot/out/scored.json、pilot/out/模拟试测_结果JSON_样例.json、
 *       pilot/out/模拟试测_报告样例.html
 */
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.dirname(HERE);
const OUT = path.join(HERE, "out");
const DIST = path.join(ROOT, "dist", "云上文旅集团核心人才系列测试_20261024.html");

function fail(msg) {
  console.error("FAIL: " + msg);
  process.exit(1);
}

/* ---------- 1. 从成品里取数据 ---------- */
if (!fs.existsSync(DIST)) fail("找不到成品 " + DIST);
const html = fs.readFileSync(DIST, "utf8");

const dataMatch = html.match(/window\.__DATA__\s*=\s*(\{[\s\S]*?\});\s*<\/script>/);
if (!dataMatch) fail("成品里找不到 window.__DATA__");
let DATA;
try {
  DATA = JSON.parse(dataMatch[1]);
} catch (e) {
  fail("成品里的 __DATA__ 不是合法 JSON：" + e.message);
}

/* 成品内嵌的 report.js 必须与 src 里的同一份，否则「测的不是在跑的那段码」 */
const reportSrc = fs.readFileSync(path.join(ROOT, "src", "modules", "report.js"), "utf8");
const embedded = html.includes("bandComposite: bandComposite");
if (!embedded) fail("成品里找不到 report.js 的导出标记，dist 与 src 可能不同步");

const cssMatch = html.match(/<style>([\s\S]*?)<\/style>/);
const CSS = cssMatch ? cssMatch[1] : "";

const copySrc = fs.readFileSync(path.join(ROOT, "src", "data", "copy.js"), "utf8");

/* ---------- 2. 起一个最小 window，跑真实 report.js ---------- */
const sandbox = { console };
sandbox.window = sandbox;
vm.createContext(sandbox);
vm.runInContext(copySrc, sandbox, { filename: "copy.js" });
vm.runInContext("window.__DATA__ = " + JSON.stringify(DATA), sandbox, { filename: "__DATA__" });
vm.runInContext(reportSrc, sandbox, { filename: "report.js" });
const REP = sandbox.window.REP;
if (!REP || typeof REP.score !== "function") fail("report.js 没导出 REP.score");

/* ---------- 3. 读样本，逐份跑计分 ---------- */
/* 用法：node pilot/run_pilot.mjs [样本文件]
   默认读合成样本 pilot/out/samples.json；真人试测时传入真实作答文件（格式见
   真人试测作业包 §6）。真人数据没有 end_to_end 字段时自动跳过整卷那一段。 */
const samplesPath = process.argv[2] ? path.resolve(process.argv[2]) : path.join(OUT, "samples.json");
if (!fs.existsSync(samplesPath)) fail("找不到 " + samplesPath + "，先跑 python3 pilot/simulate.py");
/* 计分结果的落盘名跟着输入名走（real_samples.json → real_scored.json；
   samples.json → scored.json，与旧行为一致）。
   2026-10-25：以前这个脚本固定写 pilot/out/scored.json，于是票 #26 正文里那串命令
   （analyze.py --scored pilot/out/real_scored.json）直接报「文件不存在」——
   命令链在纸上是对的、跑起来是断的。现在输入名决定输出名，两处都写。 */
const scoredPath = (() => {
  if (!process.argv[2]) return path.join(OUT, "scored.json");
  const base = path.basename(samplesPath, ".json").replace(/_?samples$/, "_scored");
  return path.join(path.dirname(samplesPath), base + ".json");
})();
const samples = JSON.parse(fs.readFileSync(samplesPath, "utf8"));

const scored = samples.respondents.map((r) => {
  const S = { a: { m1: r.responses, m2: [], m3: [] } };
  const out = REP.score(S);
  return {
    id: r.id, group: r.group, profile: r.profile || null, behavior: r.behavior || null,
    theta: r.theta || null, fake: r.fake || null,
    m1: out.m1.out,
  };
});

/* ---------- 4. 整卷端到端：一份样本跑完三项 + 综合评估 + 报告渲染 ---------- */
const e2e = samples.end_to_end;
let e2eScore = null, resultJSON = null, reportHTML = null;
if (e2e) {
  const e2eS = { a: { m1: e2e.responses_m1, m2: e2e.responses_m2, m3: e2e.responses_m3 } };
  e2eScore = REP.score(e2eS);
  resultJSON = {
    tool: DATA.brand, version: "20261024",
    code: e2e.code, name: e2e.name, idLast4: e2e.idLast4,
    date: "2026-10-24T00:00:00.000Z",
    m1: e2eScore.m1.out, m2: e2eScore.m2.out, m3: e2eScore.m3.out,
  };
  const R = REP.build(resultJSON);
  const body = REP.reportHTML(R);
  reportHTML = `<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>模拟试测报告样例</title>
<style>${CSS}</style></head><body>
${body}
</body></html>`;

  /* 报告里的关键内容必须真的在（防止「渲染成功但内容是空的」） */
  const musts = ["总报告", "综合评估", "短板", "第一项", "第二项", "第三项",
    e2eScore.m1.out.short.grade, e2eScore.compose.grade];
  const missing = musts.filter((m) => !body.includes(m));
  if (missing.length) fail("报告里缺少这些内容：" + missing.join(" / "));
}

fs.mkdirSync(OUT, { recursive: true });
const scoredJSON = JSON.stringify({ scored }, null, 1);
fs.writeFileSync(path.join(OUT, "scored.json"), scoredJSON);
if (scoredPath !== path.join(OUT, "scored.json")) fs.writeFileSync(scoredPath, scoredJSON);
if (resultJSON) {
  fs.writeFileSync(path.join(OUT, "模拟试测_结果JSON_样例.json"), JSON.stringify(resultJSON, null, 2));
  fs.writeFileSync(path.join(OUT, "模拟试测_报告样例.html"), reportHTML);
}

/* ---------- 5. 自检门 ---------- */
const dimGrades = new Set();
scored.forEach((s) => s.m1.dims.forEach((d) => dimGrades.add(d.grade)));
/* 第一项不给总档（ADR-0010）：m1 里不该再有 grade；短板维仍必须等于四维最低档 */
const noOverall = scored.every((s) => s.m1.grade === undefined || s.m1.grade === null);
if (!noOverall) fail("第一项仍产出总档（m1.grade），与 ADR-0010 冲突");
const shortRule = scored.every((s) => {
  const min = s.m1.dims.map((d) => d.grade).sort((a, b) => REP.ORD[a] - REP.ORD[b])[0];
  return s.m1.short.grade === min;        // 短板维 = 四维最低维档
});
if (!shortRule) fail("短板维 != 四维最低维档，短板规则没生效");

console.log("== 试测执行完成 ==");
console.log(`  样本文件：${samplesPath}`);
console.log(`  数据源：成品 dist 内嵌的 __DATA__（题库 ${DATA.m1.items.length} 题）`);
console.log("  计分：src/modules/report.js 的 window.REP（成品同款）");
console.log(`  样本 ${scored.length} 份 → 第一项无总档（ADR-0010）；短板维档出现 ${[...new Set(scored.map((s) => s.m1.short.grade))].join("/")}；维度档出现 ${[...dimGrades].join("/")}`);
console.log(`  短板维 = 四维最低维档 规则：${shortRule ? "通过" : "不通过"}`);
if (e2eScore) {
  console.log(`  整卷端到端：短板维 ${e2eScore.m1.out.short.name}（${e2eScore.m1.out.short.grade}，无总档）/ 综合评估 ${e2eScore.compose.grade} / 短板 ${e2eScore.compose.short.name}`);
  console.log("  产物：pilot/out/{scored.json,模拟试测_结果JSON_样例.json,模拟试测_报告样例.html}");
} else {
  console.log("  产物：pilot/out/scored.json");
}
