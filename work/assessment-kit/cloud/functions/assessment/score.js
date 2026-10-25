/* 云函数侧计分（票 #26 · 维护者 2026-10-25 裁定 Q1=B：判据与计分放服务端）
 *
 * 设计要点：**服务端不重写一遍计分**。
 * 本文件在 vm 沙箱里跑与客户端**逐字节相同**的 report.js（随包复制的 report.js），
 * 只是喂给它的 window.__DATA__ 换成服务端那份 keys.json。
 * ⇒ 客户端与服务端的计分逻辑不可能漂移；唯一可能分歧的是数据，
 *   而数据由 cloud/verify_scores.js 逐格交叉验算（客户端数据 vs 服务端键）。
 *
 * 代价：服务端包里有题库锚点（keys.json）—— 这是**应该**的，判据只在服务端。
 * 浏览器侧那份（候选人页）不含锚点，见 cloud/build_candidate.py 与 cloud/verify_candidate_page.py。
 */
"use strict";

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const KEYS = require("./keys.json");

let REP = null;
function rep() {
  if (REP) return REP;
  const src = fs.readFileSync(path.join(__dirname, "report.js"), "utf8");
  const copySrc = fs.readFileSync(path.join(__dirname, "copy.js"), "utf8");
  const sandbox = { console };
  sandbox.window = sandbox;
  vm.createContext(sandbox);
  vm.runInContext(copySrc, sandbox, { filename: "copy.js" });
  vm.runInContext("window.__DATA__ = " + JSON.stringify(KEYS), sandbox, { filename: "__DATA__" });
  vm.runInContext(src, sandbox, { filename: "report.js" });
  REP = sandbox.window.REP;
  if (!REP || typeof REP.score !== "function") throw new Error("report.js 没导出 REP.score");
  return REP;
}

/** 把线上载荷规整成计分要的 S 形状（与 app.js 的 S.a 同构）。 */
function toS(payload) {
  const a = { m1: [], m2: {}, m3: [] };
  if (Array.isArray(payload.m1_raw)) a.m1 = payload.m1_raw.slice();
  const m2 = payload.m2_answers || {};
  Object.keys(m2).forEach((k) => { a.m2[k] = m2[k]; });
  const m3 = payload.m3_answers || [];
  if (Array.isArray(m3)) {
    a.m3 = m3.slice();
  } else {
    Object.keys(m3).forEach((k) => { a.m3[k] = m3[k]; });
  }
  return { a: a };
}

/** 算三项 + 综合评估。返回 report.js 的 out 结构（客户端同款）。 */
function scoreAll(payload) {
  return rep().score(toS(payload)).out;
}

module.exports = { scoreAll: scoreAll, toS: toS, rep: rep, KEYS: KEYS };
