/* 成品主体：状态、存储、六个屏、三模块作答与计分。结果 JSON 与报告在 report.js。 */
(function () {
  const D = window.__DATA__;
  const C = window.__COPY__;
  const KEY = "assessment_core_v1";
  const OLD_KEYS = ["mbti_draft_v1", "yunshang_test3_draft_v1", "eq_test_draft_v2", "eq_test_done_v2"];
  const app = document.getElementById("app");

  /* ---------------- 工具 ---------------- */
  const $ = (s) => document.querySelector(s);
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  function validId(v) {
    if (!/^\d{17}[\dXx]$/.test(v)) return false;
    const w = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2], c = "10X98765432";
    let s = 0; for (let i = 0; i < 17; i++) s += Number(v[i]) * w[i];
    return c[s % 11] === v[17].toUpperCase();
  }
  /* ---------------- 不可逆校验码（SHA-256，纯 JS）----------------
     用途：把 18 位号码压成一个**不可逆**的短码，用来识别「同一个人重复提交」。
     为什么不用 crypto.subtle：它只在安全上下文可用、而且是异步的；
     离线单文件版是从本地文件打开的（非安全上下文），那里拿不到。
     为什么不用随机串：随机串没法跨会话认人。
     为什么不用 FNV（文件里已有 fnv）：32 位太短，18 位号码空间小，
     穷举几秒就能反推回去 —— 那不叫不可逆。 */
  const SHA_K = [
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2
  ];
  function sha256hex(s) {
    const rr = (v, n) => (v >>> n) | (v << (32 - n));
    const bytes = [];
    for (let i = 0; i < s.length; i++) {
      const c = s.charCodeAt(i);
      if (c < 0x80) bytes.push(c);
      else if (c < 0x800) bytes.push(0xc0 | (c >> 6), 0x80 | (c & 63));
      else bytes.push(0xe0 | (c >> 12), 0x80 | ((c >> 6) & 63), 0x80 | (c & 63));
    }
    const bitLen = bytes.length * 8;
    bytes.push(0x80);
    while (bytes.length % 64 !== 56) bytes.push(0);
    for (let i = 7; i >= 0; i--) bytes.push(Math.floor(bitLen / Math.pow(2, 8 * i)) & 0xff);
    let H = [0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19];
    const w = new Array(64);
    for (let off = 0; off < bytes.length; off += 64) {
      for (let i = 0; i < 16; i++) {
        w[i] = (bytes[off + i * 4] << 24) | (bytes[off + i * 4 + 1] << 16)
             | (bytes[off + i * 4 + 2] << 8) | bytes[off + i * 4 + 3];
      }
      for (let i = 16; i < 64; i++) {
        const s0 = rr(w[i - 15], 7) ^ rr(w[i - 15], 18) ^ (w[i - 15] >>> 3);
        const s1 = rr(w[i - 2], 17) ^ rr(w[i - 2], 19) ^ (w[i - 2] >>> 10);
        w[i] = (w[i - 16] + s0 + w[i - 7] + s1) | 0;
      }
      let a = H[0], b = H[1], c = H[2], d = H[3], e = H[4], f = H[5], g = H[6], h = H[7];
      for (let i = 0; i < 64; i++) {
        const S1 = rr(e, 6) ^ rr(e, 11) ^ rr(e, 25);
        const ch = (e & f) ^ (~e & g);
        const t1 = (h + S1 + ch + SHA_K[i] + w[i]) | 0;
        const S0 = rr(a, 2) ^ rr(a, 13) ^ rr(a, 22);
        const maj = (a & b) ^ (a & c) ^ (b & c);
        const t2 = (S0 + maj) | 0;
        h = g; g = f; f = e; e = (d + t1) | 0; d = c; c = b; b = a; a = (t1 + t2) | 0;
      }
      H[0] = (H[0] + a) | 0; H[1] = (H[1] + b) | 0; H[2] = (H[2] + c) | 0; H[3] = (H[3] + d) | 0;
      H[4] = (H[4] + e) | 0; H[5] = (H[5] + f) | 0; H[6] = (H[6] + g) | 0; H[7] = (H[7] + h) | 0;
    }
    return H.map((x) => ("00000000" + (x >>> 0).toString(16)).slice(-8)).join("").toUpperCase();
  }
  function newCode() {
    const d = new Date();
    const p = (n) => String(n).padStart(2, "0");
    const ds = d.getFullYear() + p(d.getMonth() + 1) + p(d.getDate());
    const cs = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
    let r = ""; const arr = new Uint32Array(6);
    if (window.crypto && window.crypto.getRandomValues) window.crypto.getRandomValues(arr);
    else for (let i = 0; i < 6; i++) arr[i] = Math.floor(Math.random() * 4294967296);
    for (let i = 0; i < 6; i++) r += cs[arr[i] % cs.length];
    return "EQ-" + ds + "-" + r + "-" + fnv(r + ds).toString(16).slice(0, 4).toUpperCase().padStart(4, "0");
  }
  function fnv(s) {
    let h = 0x811c9dc5;
    for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = (h + ((h << 1) + (h << 4) + (h << 7) + (h << 8) + (h << 24))) >>> 0; }
    return h >>> 0;
  }
  const GRADES = ["待提升", "合格", "良好", "优秀", "顶尖"];
  const ORD = { "待提升": 1, "合格": 2, "良好": 3, "优秀": 4, "顶尖": 5 };

  /* ---------------- 状态与存储（只存后 4 位 + 编号，不存全量身份证） ---------------- */
  let S = load();
  function load() {
    try {
      const raw = JSON.parse(localStorage.getItem(KEY) || "null");
      if (raw && raw.a) {
        /* 兼容旧状态：限时截止时刻（票 #25）是新增字段 */
        if (!raw.deadline) raw.deadline = 0;
        /* 2026-10-25：旧的 idEcho 存着「前 6 位 + **** + 后 4 位」⇒ 那是本机残留的个人信息，
           现在只保留末 4 位 + 不可逆校验码 ⇒ 顺手把旧的回显删掉。 */
        if (raw.idEcho) { try { delete raw.idEcho; } catch (e) { raw.idEcho = ""; } }
        return raw;
      }
    } catch (e) { /* 忽略损坏的本地状态 */ }
    return {
      name: "", idLast4: "", idHash: "", code: newCode(), consented: false, limit: false,
      a: { m1: [], m2: {}, m3: [] }, cur: { m1: 0, m2: 0, m3: 0 }, mod: "m1", phase: "self", t0: Date.now(),
      deadline: 0
    };
  }
  function save() { try { localStorage.setItem(KEY, JSON.stringify(S)); } catch (e) { /* 隐私模式等 */ } }
  function clearOldKeys() { OLD_KEYS.forEach((k) => { try { localStorage.removeItem(k); } catch (e) { } }); }
  function wipe() { try { localStorage.removeItem(KEY); } catch (e) { } clearOldKeys(); S = load(); }

  /* ---------------- 限时：全局一个 90 分钟钟（票 #25 裁定 + 票 #39 修订）----------------
     · 起算点 = 候选人点「同意并开始测试」的那一刻；
     · 截止时刻 deadline 存在本机，断点续答按存的时刻继续走（续答不重新给 90 分钟）；
     · **到点 → 只提示一次，不自动交卷**（票 #39 · D3 · 维护者 2026-10-25 12:34 裁定）：
       候选人可以继续作答，什么时候交卷由他自己决定（走完最后一题即交卷）；
     · **不留任何到点痕迹**（票 #39 · D3 复审定稿）：结果 JSON 与云端提交体里
       既没有用时字段，也没有 limitCut / limitHint —— 到点只是一个提示，不进结果。
     · deadline 只存在本机状态里，不进结果 JSON（不落用时字段）。 */
  const LIMIT_MIN = 90;                    /* 三项合计一个钟（分钟） */
  const LIMIT_WARN_MS = 10 * 60 * 1000;    /* 剩余 10 分钟开始变色 */
  let timerId = null;
  let limitTipped = false;   /* 到点提示只弹一次（票 #39 · D3 复审定稿） */

  function startTimer() {
    stopTimer();
    if (!S.limit) return;
    if (!S.deadline) { S.deadline = Date.now() + LIMIT_MIN * 60000; save(); }
    tickTimer();
    timerId = setInterval(tickTimer, 1000);
  }
  function stopTimer() { if (timerId) { clearInterval(timerId); timerId = null; } }
  function tickTimer() {
    const el = document.getElementById("t-left");
    if (!el) return;
    const left = S.deadline - Date.now();
    if (left <= 0) {
      /* 到点：停钟 + 顶栏改成「限时已到」（不再倒计时）+ 提示一次。**不跳完成页。** */
      stopTimer();
      el.textContent = C.limitHitLeftLabel;
      el.style.opacity = "1";
      el.style.color = "var(--gold)";
      el.style.fontWeight = "700";
      onLimitHit();
      return;
    }
    const m = Math.floor(left / 60000), s = Math.floor(left % 60000 / 1000);
    el.textContent = C.limitLeftLabel + " " + m + ":" + String(s).padStart(2, "0");
    /* 剩余 10 分钟内转金色提醒：金在深绿底 4.55:1 ✓（tokens.css 坑 1 (b)）。
       .toprow span 默认 opacity:.92（分组透明度），故提醒态须同时把 opacity 拉回 1，
       否则对比度会被压到 4.5:1 以下。#t-left 是 .toprow 的直接子元素，改它自身即可。 */
    const warn = left < LIMIT_WARN_MS;
    el.style.opacity = warn ? "1" : "";
    el.style.color = warn ? "var(--gold)" : "";
    el.style.fontWeight = warn ? "700" : "";
  }
  function onLimitHit() {
    /* 票 #39 · D3（维护者 2026-10-25 复审定稿）：到点**只提示一次、不自动交卷、不留痕**。
       这里不再有任何跳完成页的逻辑 —— 交卷只由候选人自己走完最后一题触发（APP.next → done）。
       也不写任何到点痕迹：结果里既没有用时字段，也没有 limitCut / limitHint。 */
    if (limitTipped) return;                 /* 只提示一次 */
    limitTipped = true;
    showLimitTip();
  }
  function showLimitTip() {
    const w = document.getElementById("warn");
    if (w) { w.hidden = false; w.textContent = C.limitHitTip; }
  }

  /* ---------------- 五级切档 ---------------- */
  function bandM1(score, dim) {
    const b = D.m1.meta.bands;
    for (const k of ["顶尖", "优秀", "良好", "合格"]) if (score >= b[k][0] && score <= b[k][1]) return k;
    return "待提升";
  }
  function bandWeighted(v) { return v >= 4.4 ? "顶尖" : v >= 3.8 ? "优秀" : v >= 3.0 ? "良好" : v >= 2.4 ? "合格" : "待提升"; }
  function bandT(t) { return t >= 63 ? "顶尖" : t >= 55 ? "优秀" : t >= 48 ? "良好" : t >= 42 ? "合格" : "待提升"; }
  function bandComposite(v) { return v >= 4.5 ? "顶尖" : v >= 3.75 ? "优秀" : v >= 3.0 ? "良好" : v >= 2.25 ? "合格" : "待提升"; }

  /* ---------------- 三模块的题目序列 ---------------- */
  const MODULES = [
    { key: "m1", no: "第一项", name: D.m1.meta.title, count: D.m1.meta.dimensions.reduce((n, d) => n + d.items, 0) + " 题", min: "约 12 分钟" },
    { key: "m2", no: "第二项", name: "情境测试", count: "16 自评 + 60 情境", min: "约 30 分钟" },
    { key: "m3", no: "第三项", name: "推理测试", count: "40 题 · 8 维度", min: "建议 45 分钟" }
  ];
  function m2List() {
    const self = D.eq.self_items.map((x) => ({ kind: "self", id: x.id, text: x.text, dim: x.dimension, rev: !!x.reverse }));
    /* 选项字段两个名字都认：build.py 把第二项的 options 由 {A,B,C,D} 转成了数组 opts，
       而第三项的题库里字段就叫 options。2026-10-25 修（真实候选人反馈「第二项第 17 题没有选项」）：
       这里原来只读 x.options ⇒ 取到 undefined ⇒ 渲染时 q.opts || q.options 两边都是空
       ⇒ **60 道情境题一题选项都不渲染**（自评 16 题走七级量表分支，所以卡在第 17 题才暴露）。 */
    const sjt = D.eq.sjt.map((x) => ({ kind: "sjt", id: x.id, stem: x.stem, opts: x.opts || x.options || [], dim: x.dimension, ans: x.answer, sec: x.second, thd: x.third }));
    return self.concat(sjt);
  }
  const M2ALL = m2List();
  const M3ALL = D.m3.questions;

  function totalOf(mk) {
    if (mk === "m1") return D.m1.items.length;
    if (mk === "m2") return M2ALL.length;
    return M3ALL.length;
  }
  function answeredOf(mk) {
    if (mk === "m1") return S.a.m1.filter((x) => x !== null && x !== undefined).length;
    if (mk === "m2") return Object.keys(S.a.m2).length;
    /* 第三项：**数真正有值的题位**，不能用 Object.keys(S.a.m3).length ——
       那是数组长度（localStorage 恢复后的 null 空洞也占位）⇒ 会虚报「已答 40/40」。
       2026-10-26 修（票 #26 根因）：崔婵那份浏览器本地 40 题全有值，
       但落库只剩 18 题有值（选 C/D 的被客户端丢成 null）；
       顶栏当时显示「已答 40 / 40」⇒ 她以为做完了。计数必须诚实。 */
    return S.a.m3.filter((x) => x !== null && x !== undefined).length;
  }
  function curItem(mk) {
    if (mk === "m1") return { kind: "ab", i: S.cur.m1 };
    if (mk === "m2") { const it = M2ALL[S.cur.m2]; return it ? { kind: it.kind, i: S.cur.m2 } : null; }
    return { kind: "mc", i: S.cur.m3 };
  }
  function pickOf(mk, i) {
    if (mk === "m1") return S.a.m1[i];
    if (mk === "m2") return S.a.m2[i];
    return S.a.m3[i];
  }
  function setPick(mk, i, v) {
    if (mk === "m1") S.a.m1[i] = v;
    else if (mk === "m2") S.a.m2[i] = v;
    else S.a.m3[i] = v;
    save();
  }

  /* ---------------- 渲染：开始页 ---------------- */
  function startHTML() {
    const idLine = S.idLast4
      ? '<span class="hint">已记录末 4 位 <b>' + esc(S.idLast4) + '</b> · 校验码 <b>' + esc(S.idHash || "—") +
        '</b>（不可逆，无法反推回号码）</span>'
      : "";
    const fields =
      '<label class="field"><span>姓名</span><input id="f-name" autocomplete="off" placeholder="请输入真实姓名" value="' + esc(S.name) + '"></label>' +
      '<label class="field"><span>身份核对码（18 位）</span><input id="f-id" autocomplete="off" inputmode="numeric" maxlength="18" placeholder="填写 18 位号码，只用来生成一个不可逆校验码" value="">' +
      idLine + '<span class="hint">只在本机校验（格式与校验位），随即丢弃原号；页面只保留末 4 位与一个不可逆校验码，' +
      '用来识别同一人重复提交，不作其他用途。</span></label>';
    const tasks = '<ul class="tasklist">' + MODULES.map((m) =>
      '<li><span class="mk">' + m.no.replace("第", "") + '</span><span class="tt">' + esc(m.name) + '<em>' + esc(m.count) + '</em></span><span class="pc">' + esc(m.min) + '</span></li>'
    ).join("") + '</ul>';
    const limit = '<label class="check"><input type="checkbox" id="f-limit" ' + (S.limit ? "checked" : "") + '><span>' + esc(C.limitLabel) + '</span></label>';
    const resume = (answeredOf("m1") || answeredOf("m2") || answeredOf("m3"))
      ? '<div class="panel" style="margin-top:var(--sp-3)"><h3>检测到未完成的作答</h3>' +
        '<p class="hint" style="margin:0">「' + esc(D.brand || "云上文旅集团核心人才系列测试") + '」上次做到 <b>' + esc(curLabel()) + '</b>。</p>' +
        '<button class="btn btn-ghost" style="margin-top:var(--sp-2)" onclick="APP.go(\'quiz\')">继续上次答题</button></div>'
      : "";
    return '<div class="wrap"><div class="sheet" style="margin-top:var(--sp-4)">' +
      '<div class="brand"><h1>' + esc(D.brand) + '</h1><div class="rule"></div></div>' +
      '<div class="sect-title">测评人信息</div>' + fields +
      '<div class="sect-title">本次包含</div>' + tasks +
      '<div class="sect-title">作答方式</div>' + limit +
      '<button class="btn btn-primary btn-full" style="margin-top:var(--sp-4)" onclick="APP.toConsent()">' + esc(C.startBtn) + '</button>' +
      resume +
      '<p class="hint" style="text-align:center;margin-top:var(--sp-3)">已有施测人？<a href="javascript:APP.go(\'hr\')">从施测人入口进入</a></p>' +
      '</div>' + footHTML() + '</div>';
  }
  function curLabel() {
    const it = curItem(S.mod);
    if (!it) return "完成页";
    if (S.mod === "m1") return "第一项 第 " + (it.i + 1) + " 题";
    if (S.mod === "m2") return "第二项 第 " + (it.i + 1) + " 题";
    return "第三项 第 " + (it.i + 1) + " 题";
  }

  /* ---------------- 渲染：告知卡 ---------------- */
  function consentHTML() {
    const first = MODULES[0].name + "（" + MODULES[0].count + "）";
    const terms = C.terms.map((t) => "<p><b>" + esc(t[0]) + "</b>" + esc(t[1].replace("{FIRST}", first)) + "</p>").join("");
    /* 勾了限时才给这段说明（告知卡要素清单把「限时模式开关说明」列为可选要素）；
       里面写的每一条都必须与实现对得上 —— 禁止本页做不到的表述。 */
    const limitBlock = S.limit
      ? '<div class="panel" style="margin:var(--sp-3) 0"><h3>' + esc(C.limitTermsTitle) + '</h3><div class="terms">' +
        C.limitTerms.map((t) => "<p>" + esc(t) + "</p>").join("") + "</div></div>"
      : "";
    return '<div class="wrap"><div class="sheet consent" style="margin-top:var(--sp-4);padding:var(--sp-5) var(--sp-4)">' +
      "<h2>本次测试的知情同意</h2>" +
      '<p class="hint" style="margin:var(--sp-1) 0 var(--sp-3)">下面这段说明这次测评是什么、结果谁会看到、怎么使用。请逐条阅读，勾选下方确认框后再开始。</p>' +
      '<div class="terms">' + terms + "</div>" +
      limitBlock +
      '<div style="border-top:1px solid var(--line);padding-top:var(--sp-3)">' +
      '<label class="check"><input type="checkbox" id="c-box" onchange="document.getElementById(\'c-ok\').disabled=!this.checked"><span>我已阅读并理解以上八条说明，<b>自愿参加</b>本次测试。</span></label>' +
      '<div style="display:flex;gap:var(--sp-2);margin-top:var(--sp-3)">' +
      '<button class="btn btn-primary" id="c-ok" style="flex:2" disabled onclick="APP.toQuiz()">' + esc(C.agreeBtn) + "</button>" +
      '<button class="btn btn-quiet" style="flex:1" onclick="APP.go(\'start\')">' + esc(C.quitBtn) + "</button>" +
      "</div></div></div>" + footHTML() + "</div>";
  }

  /* ---------------- 渲染：答题页 ---------------- */
  function quizHTML() {
    const mk = S.mod, it = curItem(mk);
    if (!it) return doneHTML();
    const total = totalOf(mk), done = answeredOf(mk);
    const pct = Math.round(done / total * 100);
    const mod = MODULES.find((m) => m.key === mk);
    const bar = '<div class="pbar"><i style="width:' + pct + '%"></i></div>';
    /* 限时中：题头显示**真实剩余时间**（票 #25）。原来这里只有「· 限时中」三个字，
       全文件没有任何计时行为 —— 那是一句做不到的承诺。 */
    /* 限时模式下顶栏分两行：第一行「模块名 + 剩余时间」，第二行「第 x / N 题 · 已答 y」。
       倒计时与模块名挤在一行会在 390 CSS px 下换行（顶栏涨到三行），已实测。 */
    const prog = '<span id="tmeta">第 ' + (it.i + 1) + " / " + total + " 题 · 已答 " + done + "</span>";
    const meta = S.limit
      ? '<div class="toprow"><b>' + esc(mod.no + " · " + mod.name) + '</b><span id="t-left">' + esc(C.limitLeftLabel) + " --:--</span></div>" +
        '<div class="toprow">' + prog + "</div>"
      : '<div class="toprow"><b>' + esc(mod.no + " · " + mod.name) + "</b>" + prog + "</div>";
    let body = "";
    if (it.kind === "ab") {
      const q = D.m1.items[it.i];
      body = '<div class="qstem">' + esc("以下哪种描述更符合你？") + "</div>" +
        '<div class="opts">' + [q.a, q.b].map((o, k) =>
          '<button class="opt" type="button" aria-pressed="' + (pickOf(mk, it.i) === k ? "true" : "false") + '" data-i="' + k + '" onclick="APP.pick(this)">' +
          '<span class="k">' + "AB"[k] + "</span><span>" + esc(o) + "</span></button>").join("") + "</div>";
    } else if (it.kind === "self") {
      const q = M2ALL[it.i];
      body = '<div class="qstem">' + esc(q.text) + "</div>" +
        '<div class="scale" role="group" aria-label="七级量表">' +
        ["非常不符合", "", "", "不确定", "", "", "非常符合"].map((lab, k) =>
          '<button class="seg" type="button" aria-pressed="' + (pickOf(mk, it.i) === k + 1 ? "true" : "false") + '" data-i="' + k + '" aria-label="第 ' + (k + 1) + ' 级 ' + (lab || "中间等级") + '" onclick="APP.pick(this)">' +
          '<span class="dot"></span><span class="sl">' + (lab || "") + "</span></button>").join("") + "</div>";
    } else {
      const q = mk === "m2" ? M2ALL[it.i] : M3ALL[it.i];
      /* 选项字段两个名字都认：第二项的题在 build.py 里转成了 opts，
         第三项的题库里字段就叫 options。2026-10-25 修（票 #39 顺带发现的老 bug）：
         这里原来只读 q.opts，第三项一渲染就抛 TypeError —— 候选人卡在第二项末尾，
         整卷交不出去（连带「手动交卷」流程根本走不到）。 */
      const opts = q.opts || q.options || [];
      const grid = q.grid ? '<pre class="grid" style="font-family:ui-monospace,Menlo,monospace;font-size:var(--fs-3);line-height:1.5;margin-bottom:var(--sp-3)">' +
        esc(Array.isArray(q.grid) ? q.grid.join("\n") : q.grid) + "</pre>" : "";
      body = '<div class="qstem">' + esc(q.stem) + "</div>" + grid +
        '<div class="opts" role="group" aria-label="选项">' + opts.map((o, k) =>
          '<button class="opt" type="button" aria-pressed="' + (pickOf(mk, it.i) === k ? "true" : "false") + '" data-i="' + k + '" onclick="APP.pick(this)">' +
          '<span class="k">' + "ABCD"[k] + "</span><span>" + esc(o) + "</span></button>").join("") + "</div>";
    }
    const warn = '<div class="warn" id="warn" role="status" aria-live="polite" hidden>' + esc(C.warnUnanswered) + "</div>";
    const nav = '<div class="qnav">' +
      '<button class="btn btn-quiet" onclick="APP.prev()">上一题</button>' +
      '<button class="btn btn-primary" id="next" ' + (pickOf(mk, it.i) === null || pickOf(mk, it.i) === undefined ? "disabled" : "") + " onclick=\"APP.next()\">下一题</button></div>" +
      '<button class="btn btn-quiet btn-full" style="margin-top:var(--sp-2)" onclick="APP.openGrid()">题号 · 已答 ' + done + " / " + total + "</button>" +
      '<p class="hint" style="margin-top:var(--sp-2)">进度自动保存在本机，中途关闭可继续。</p>';
    return '<div class="topbar"><div class="wrap"><div class="in">' + meta + "</div>" + bar + "</div></div>" +
      '<div class="wrap"><div class="qbody">' + body + warn + nav + "</div></div>" + footHTML();
  }

  /* ---------------- 渲染：完成页 ----------------
     票 #39：候选人在自助云版里**看不到自己的结果** ⇒ 这一页只说
     「已完成 · 结果由 HR 保管」，不出现分数、等级与任何评价结论（旧图红线 6 仍然有效）。
     撤回通道做成可选：提一句「如需删除本次记录，请联系 HR」。 */
  function doneHTML() {
    /* 完成页（票 #39 · D6 · 维护者 2026-10-25 裁定与复审定稿）：
       只显示「已完成 · 结果由 HR 保管」，**不出现分数、等级与任何评价结论**（旧图红线 6 仍然有效）。
       离线版的「下载结果文件 + 回传给施测人」整套话术与入口一并撤掉（云版直接落库，没有回传动作）；
       候选人侧的「清除本机」入口也一并撤掉（本机残留由候选人自行清浏览器数据）。
       撤回通道做成可选：这里只留一句「如需删除本次记录，请联系集团人力资源部」。
       **云上测试版**：上传状态行只在云上版出现（build.py --cloud）；
       「下载结果文件」兜底按钮**已移除**（票 #53 · 2026-10-26 · 维护者定方案 A）——
       云版交卷即落库，失败有「重试」这一条路；再加一个「带走原始作答」的出口
       等于给候选人一条绕过交卷的旁路（票 #39 已把下载/回传入口删过一轮）。
       且云版候选页已剥 answer 键，客户端 REP.score() 算不出分（全 0），按钮留着只会产出错误文件。
       离线版（CLOUD.enabled=false）仍保留 download() 入口（施测人本地用）。 */
    return '<div class="wrap"><div class="sheet" style="margin-top:var(--sp-4);padding:var(--sp-6) var(--sp-4)">' +
      '<div class="done-seal">✓</div>' +
      '<h2 style="font-size:var(--fs-6);text-align:center">' + esc(C.doneTitle) + "</h2>" +
      '<p class="hint" style="max-width:330px;margin:var(--sp-2) auto 0;text-align:center">' + esc(C.doneLead) + "</p>" +
      (CLOUD.enabled ? '<p class="hint" id="cloud-state" style="max-width:330px;margin:var(--sp-1) auto 0;text-align:center">正在提交本次作答…</p>' : "") +
      '<p class="hint" style="max-width:330px;margin:var(--sp-1) auto 0;text-align:center">' + esc(C.doneWithdraw) + "</p>" +
      '<button class="btn btn-quiet btn-full" style="margin-top:var(--sp-2)" onclick="APP.reset()">再测一次</button>' +
      "</div>" + footHTML() + "</div>";
  }

  /* ---------------- 渲染：施测人入口 ---------------- */
  function hrHTML() {
    return '<div class="wrap"><div class="sheet" style="margin-top:var(--sp-4);padding:var(--sp-5) var(--sp-4)">' +
      '<div class="sect-title">施测人入口</div>' +
      '<p class="hint">' + esc(C.hrLead) + "</p>" +
      '<label class="field" style="margin-top:var(--sp-3)"><span>测评编号</span><input id="hr-code" value="' + esc(S.code) + '"></label>' +
      '<label class="field"><span>或粘贴结果 JSON</span><textarea id="hr-json" style="width:100%;min-height:110px;border:1px solid var(--line);border-radius:var(--r-m);padding:var(--sp-2);font-family:ui-monospace,Menlo,monospace;font-size:var(--fs-2)" placeholder="{\\"tool\\": \\"…\\"}"></textarea></label>' +
      '<button class="btn btn-primary btn-full" onclick="APP.openReport()">导入结果并查看报告</button>' +
      '<p class="hint" style="margin-top:var(--sp-2)">（本页面纯前端处理，不上传任何数据。）</p>' +
      "</div>" + footHTML() + "</div>";
  }

  /* ---------------- 云端上报（云上版 · 票 #33 / #40）----------------
     离线版：__CLOUD_ON__ = false —— 不联网，页脚与完成页保持「只在本机」口径。
     云上版：src/build.py --cloud 会把 __CLOUD_ON__ 置为 true、__CLOUD_ENDPOINT__ 填成网关路由地址；
     交卷时把作答 POST 给云函数，由云函数落 CloudBase PG（候选人浏览器**不碰数据库**：
     网关的 PG 连接带 row_security=off，浏览器角色写不进开了 RLS 的表）。
     上报失败不阻断：候选人仍可下载结果文件回传（离线兜底）。 */
  const CLOUD = { enabled: __CLOUD_ON__, endpoint: "__CLOUD_ENDPOINT__" };

  function cloudPayload() {
    const r = window.REP.score(S);
    const m1 = (S.a.m1 || []).map(function (v) { return (v === null || v === undefined) ? -1 : v; });
    return {
      code: S.code,
      respondent_name: S.name,
      id_last4: S.idLast4,
      started_at: new Date(S.t0).toISOString(),
      submitted_at: new Date().toISOString(),
      duration_ms: Math.max(0, Date.now() - S.t0),
      m1_raw: m1,                 /* 96 题逐题作答：0=选 a 侧 / 1=选 b 侧（-1=未作答） */
      m1_scores: r.m1.out,        /* 四维分与档位快照（客户端算分的口径） */
      m2_result: r.m2.out,
      m3_result: r.m3.out,
      unanswered_m1: m1.filter(function (v) { return v === -1; }).length
    };
  }
  function cloudKick() {
    if (!CLOUD.enabled) return;
    /* 云版候选人页由 cloud/candidate_runtime.js 负责提交（载荷形状与服务端一致：
       未答 = null、只发原始选择、分数一律服务端算）。app.js 这条路径的载荷是
       -1 表示未答、且带客户端算的分数 ⇒ 服务端会拒收或写进错的一行 ⇒ 两边都在就跳过。
       2026-10-25 加。 */
    if (window.__cloudRuntime) return;
    const el = document.getElementById("cloud-state");
    fetch(CLOUD.endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(cloudPayload())
    }).then(function (r) { return r.json(); })
      .then(function (res) {
        if (!el) return;
        el.textContent = (res && res.ok)
          ? "已提交到集团人力资源部的系统（结果不在本页面显示）。"
          : "本次未能联网上传，请下载结果文件回传给施测人。";
      })
      .catch(function () {
        if (!el) return;
        el.textContent = "本次未能联网上传，请下载结果文件回传给施测人。";
      });
  }
  function footHTML() {
    const lines = (CLOUD.enabled && C.footCloud) ? C.footCloud : C.foot;
    return '<div class="foot">' + lines.map(function (f) { return "<b>" + esc(f) + "</b>"; }).join("") + "</div>";
  }

  /* ---------------- 屏幕切换 ---------------- */
  const SCREENS = { start: startHTML, consent: consentHTML, quiz: quizHTML, done: doneHTML, hr: hrHTML };
  let REPORT = null;
  function render() {
    app.innerHTML = SCREENS[S.screen] ? SCREENS[S.screen]() : (REPORT ? window.REP.reportHTML(REPORT) : startHTML());
    if (S.screen === "quiz") drawGrid();
    /* 计时器只在答题屏跑；离开答题屏立即停（施测人入口/报告页不该有钟） */
    if (S.screen === "quiz") startTimer(); else stopTimer();
    window.scrollTo(0, 0);
  }
  function go(s) { S.screen = s; render(); }

  /* ---------------- 交互 ---------------- */
  function toConsent() {
    const n = document.getElementById("f-name"), i = document.getElementById("f-id");
    const l = document.getElementById("f-limit");
    if (n) S.name = n.value.trim();
    if (l) {
      S.limit = l.checked;
      /* 取消勾选 = 取消限时：清掉截止时刻与到点痕迹，避免上一轮残留把这一轮也标上 */
      if (!S.limit) { S.deadline = 0; }
    }
    if (i && i.value.trim()) {
      if (!validId(i.value.trim())) { alert("号码格式或校验位不对，请核对后重填"); return; }
      const v = i.value.trim();
      /* 原号只在这里存在一瞬：算完校验码就丢。
         本机留下的是：末 4 位 + 不可逆校验码（SHA-256 前 16 位十六进制）。
         旧版本留下的「前 6 位 + **** + 后 4 位」回显已删除（见 load()）。 */
      S.idLast4 = v.slice(-4);
      S.idHash = sha256hex(v).slice(0, 16);
      i.value = "";
    }
    if (!S.name) { alert("请先填写姓名"); return; }
    save(); go("consent");
  }
  function toQuiz() {
    const b = document.getElementById("c-box");
    if (b) S.consented = b.checked;
    if (!S.consented) { alert("请先勾选同意"); return; }
    /* 限时起算点 = 候选人点「同意并开始测试」这一刻（票 #25 裁定） */
    if (S.limit && !S.deadline) S.deadline = Date.now() + LIMIT_MIN * 60000;
    S.mod = "m1"; S.phase = "self"; save(); go("quiz");
  }
  function pick(el) {
    const it = curItem(S.mod);
    let v = Number(el.dataset.i);
    if (it.kind === "self") v = v + 1;
    setPick(S.mod, it.i, v);
    document.querySelectorAll(".opt,.seg").forEach((o) => o.setAttribute("aria-pressed", "false"));
    el.setAttribute("aria-pressed", "true");
    const n = document.getElementById("next"); if (n) n.disabled = false;
    const w = document.getElementById("warn"); if (w) w.hidden = true;
  }
  function next() {
    const it = curItem(S.mod);
    const p = pickOf(S.mod, it.i);
    if (p === null || p === undefined) {
      const w = document.getElementById("warn");
      if (w) { w.hidden = false; w.textContent = C.warnUnanswered; }
      return;
    }
    const total = totalOf(S.mod);
    if (it.i + 1 >= total) {
      if (S.mod === "m1") { S.mod = "m2"; S.cur.m2 = 0; }
      else if (S.mod === "m2") { S.mod = "m3"; S.cur.m3 = 0; }
      else { S.screen = "done"; cloudKick(); }
      save(); render(); return;
    }
    S.cur[S.mod] = it.i + 1; save(); render();
  }
  function prev() {
    const it = curItem(S.mod);
    if (it.i <= 0) return;
    S.cur[S.mod] = it.i - 1; save(); render();
  }
  function openGrid() {
    const p = document.getElementById("gridpanel"), m = document.getElementById("mask");
    if (p) p.classList.add("on"); if (m) m.classList.add("on");
  }
  function closeGrid() {
    const p = document.getElementById("gridpanel"), m = document.getElementById("mask");
    if (p) p.classList.remove("on"); if (m) m.classList.remove("on");
  }
  function drawGrid() {
    const g = document.getElementById("grid"); if (!g) return;
    const total = totalOf(S.mod), it = curItem(S.mod);
    g.innerHTML = "";
    for (let i = 0; i < total; i++) {
      const b = document.createElement("b");
      b.textContent = i + 1;
      const p = pickOf(S.mod, i);
      if (p !== null && p !== undefined) b.className = "done";
      if (it && i === it.i) b.className = "cur";
      b.onclick = () => {
        if (p === null || p === undefined) { alert(C.warnJump.replace("N", i + 1)); return; }
        S.cur[S.mod] = i; save(); render();
      };
      g.appendChild(b);
    }
  }

  /* ---------------- 结果 JSON 与清除 ---------------- */
  function resultObj() {
    const r = window.REP.score(S);
    const out = {
      tool: D.brand, version: "20261024", code: S.code, name: S.name, idLast4: S.idLast4,
      date: new Date().toISOString(), m1: r.m1.out, m2: r.m2.out, m3: r.m3.out
    };
    /* 结果里不落任何用时字段，也不落到点痕迹（票 #39 · D3 复审定稿：到点只提示、不留痕）。
       字段恒为 9 个：tool / version / code / name / idLast4 / date / m1 / m2 / m3。 */
    return out;
  }
  function download() {
    const blob = new Blob([JSON.stringify(resultObj(), null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob); a.download = "核心人才系列测试_" + (S.name || "result") + ".json";
    a.click(); URL.revokeObjectURL(a.href);
  }
  function clearAll() {
    if (!confirm("确定清除本机缓存的作答与结果？清除后无法恢复。")) return;
    wipe(); closeGrid(); alert(C.clearDoneTip); go("start");
  }
  function reset() {
    if (!confirm("重新开始？本次记录会被清空。")) return;
    const code = S.code; wipe(); S.code = code; go("start");
  }

  /* ---------------- 施测人：导入结果 → 报告 ---------------- */
  function openReport() {
    const t = document.getElementById("hr-json");
    let data = null;
    if (t && t.value.trim()) {
      try { data = JSON.parse(t.value); } catch (e) { alert("结果 JSON 解析失败，请检查粘贴内容"); return; }
    } else {
      data = resultObj(); // 施测人本地直接生成（用于演示与自检）
    }
    try { REPORT = window.REP.build(data); } catch (e) { alert("报告生成失败：" + e.message); return; }
    S.screen = "report"; render();
  }

  /* ---------------- 启动 ---------------- */
  window.APP = { go, toConsent, toQuiz, pick, next, prev, openGrid, closeGrid, download, clearAll, reset, openReport, save, S: () => S };
  clearOldKeys();
  if (!S.a || !S.a.m1) S = load();
  render();
})();
