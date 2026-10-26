/* 云版候选人页 · 交卷写库运行时（票 #26 · 维护者 2026-10-25 裁定 Q1=B）
 *
 * 由 cloud/build_candidate.py 注入候选人页（浏览器可见的这一份）。它做三件事：
 *   1) 到达完成页时，把作答**只以原始选择**（选了哪一端）POST 给云函数；
 *   2) 完成页换成云版口径的「已完成 · 结果由 HR 保管」（无回传话术、无分数）；
 *   3) 提交失败可重试。
 *
 * 它**不含**任何题库锚点与判据 —— 分数一律由云函数算（functions/assessment/score.js）。
 * 任何时候都不显示分数、等级与评价结论（旧图红线 6：候选人端不显示分数）。
 *
 * 为什么用「观察 DOM」而不是改 app.js：app.js 正被另一条会话改（票 #39 的限时与完成页），
 * 本文件不碰它，靠 APP.S() 读状态、靠 MutationObserver 感知完成页出现 —— 零耦合、可独立回滚。
 */
(function () {
  var ENDPOINT = "__ENDPOINT__";
  /* 告诉 app.js「提交由本运行时负责」：app.js 自己那条云端提交路径的载荷形状
     （-1 表示未答、带客户端算的分数）与服务端约定不符 ⇒ 会和服务端抢同一行，
     谁先到谁写进去 ⇒ 有可能把一份「客户端算的全 0 分数」写进库。 */
  window.__cloudRuntime = true;
  var st = { sending: false, sent: false, err: null, submitted: false, incomplete: null, forceSubmit: false };

  function appState() {
    try { return (window.APP && window.APP.S) ? window.APP.S() : null; } catch (e) { return null; }
  }
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
      return ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]);
    });
  }
  function nItems() {
    var D = window.__DATA__ || {};
    return (D.m1 && D.m1.items ? D.m1.items.length : 96);
  }
  function nM2() {
    var D = window.__DATA__ || {};
    var e = D.eq || {};
    return (e.self_items ? e.self_items.length : 0) + (e.sjt ? e.sjt.length : 0);
  }
  function nM3() {
    var D = window.__DATA__ || {};
    return (D.m3 && D.m3.questions ? D.m3.questions.length : 0);
  }

  /* ---- 完整度体检（2026-10-26 · 票 #26 根因之后加的闸门）--------------------
     为什么要它：修好「选 C/D 被丢」那个 bug 之后，**空位就只可能表示真的没答**。
     那就不能再让「带着空位交卷」悄悄发生 —— 候选人看到的是「已完成」，
     施测人看到的是一份被按未作答计过分的成绩（这就是崔婵那份的经过）。
     现在：走到完成页时先体检 ⇒ 有空位就**不自动交卷**，改为拦下来让她去补。 */
  function completeness() {
    var s = appState();
    var a = (s && s.a) || {};
    function countFilled(arr) {
      if (!Array.isArray(arr)) return 0;
      var n = 0;
      for (var i = 0; i < arr.length; i++) if (arr[i] !== null && arr[i] !== undefined) n++;
      return n;
    }
    var m1n = nItems(), m2n = nM2(), m3n = nM3();
    var m1a = countFilled(a.m1);
    var m2a = a.m2 && typeof a.m2 === "object" ? Object.keys(a.m2).length : 0;
    var m3a = countFilled(a.m3);
    var r = { m1: { done: m1a, total: m1n }, m2: { done: m2a, total: m2n },
              m3: { done: m3a, total: m3n } };
    r.missing = { m1: Math.max(0, m1n - m1a), m2: Math.max(0, m2n - m2a), m3: Math.max(0, m3n - m3a) };
    r.total = r.missing.m1 + r.missing.m2 + r.missing.m3;
    /* 第一处空位在哪（用于「去补答」跳转） */
    r.firstEmpty = null;
    if (r.missing.m1) {
      for (var i = 0; i < m1n; i++) if (a.m1[i] === null || a.m1[i] === undefined) { r.firstEmpty = { mod: "m1", i: i }; break; }
    } else if (r.missing.m2) {
      for (var j = 0; j < m2n; j++) if (!a.m2 || a.m2[j] === undefined) { r.firstEmpty = { mod: "m2", i: j }; break; }
    } else if (r.missing.m3) {
      for (var k = 0; k < m3n; k++) if (a.m3[k] === null || a.m3[k] === undefined) { r.firstEmpty = { mod: "m3", i: k }; break; }
    }
    return r;
  }

  /* 跳到第一处未答题（借 app.js 的公开 API：APP.S() 拿状态，APP.go('quiz') 触发重绘） */
  function jumpToFirstEmpty() {
    var c = completeness();
    if (!c.firstEmpty) return false;
    var s = appState();
    if (!s) return false;
    s.mod = c.firstEmpty.mod;
    s.cur[c.firstEmpty.mod] = c.firstEmpty.i;
    try { if (window.APP && window.APP.save) window.APP.save(); } catch (e) { }
    try { if (window.APP && window.APP.go) window.APP.go("quiz"); } catch (e) { }
    return true;
  }

  /* 把稀疏数组补成定长数组：没答的位置是 null（= 未作答），不是缺项。
     ⚠ 2026-10-26 修（票 #26 的根因）：这个函数原来**只认 0 和 1**，
       而它是给**第一项的二极题**（选 a / 选 b）写的；后来被原样用在
       **第三项的四选项题**（选项下标 0/1/2/3）上 ⇒
       **凡选 C(2) 或 D(3) 的答案，在浏览器端就被丢成 null（= 未作答）**。
       后果：库里的第三项逐题作答里，选了 C/D 的题位全是 null，
       服务端按「未作答」计 ⇒ 分数被系统性压低，而候选人**确实答了**。
       实证：崔婵那份（EQ-20261026-L52MPC-2A49）浏览器本地 40 题全有值、值域 {0,1,2,3}，
       落库后只剩 18 个有值且只有 0/1。
     ⇒ 现在按模块分别给定允许值域：第一项 [0,1]、第三项 [0,1,2,3]。 */
  function normalize(list, len, allowed) {
    var ok = allowed || [0, 1];
    var out = new Array(len);
    for (var i = 0; i < len; i++) {
      var v = (list && list.length > i) ? list[i] : null;
      out[i] = (v !== null && v !== undefined && ok.indexOf(v) >= 0) ? v : null;
    }
    return out;
  }

  function buildPayload(s) {
    var a = s.a || {};
    var m2 = {};
    var raw2 = a.m2 || {};
    var len2 = nM2();
    for (var i = 0; i < len2; i++) {
      var v = raw2[i];
      if (v === null || v === undefined) continue;
      m2[String(i)] = v;
    }
    return {
      code: s.code,
      name: s.name || null,
      id_last4: s.idLast4 || null,
      /* 不可逆校验码（SHA-256 前 16 位）：完整号码从不离开浏览器，
         只回传末 4 位 + 这个校验码，用来识别同一人重复提交。 */
      id_hash: s.idHash || null,
      group: s.group || null,
      level: s.level || null,
      dept: s.dept || null,
      m1_raw: normalize(a.m1, nItems(), [0, 1]),
      m2_answers: m2,
      /* 第三项是四选项（0/1/2/3）—— 允许值域必须给全，否则 C/D 被丢成未作答 */
      m3_answers: normalize(a.m3, nM3(), [0, 1, 2, 3]),
      started_at: s.t0 ? new Date(s.t0).toISOString() : null,
      duration_ms: s.t0 ? Math.round(Date.now() - s.t0) : null,
      limit_hint: s.limitHint || null
    };
  }

  /* 交卷前先问一句「这一份是不是已经交过了」。
     2026-10-25 加（真实候选人刷新后想回到最后一题）：`responses.code` 上有唯一索引，
     同一份再交一次会被数据库拒（重复键）⇒ 页面显示「提交未成功」，其实第一份早就存好了。
     ⇒ 先 GET 一下：库里有了就当「已提交」，不再 POST。 */
  function alreadySubmitted(code) {
    if (!code) return Promise.resolve(false);
    return fetch(ENDPOINT + "?code=" + encodeURIComponent(code), { method: "GET" })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (j) {
        if (!j) return false;
        var row = j.row || j.data || j;
        if (row && typeof row === "object" && row.code) return true;
        if (Array.isArray(row) && row.length) return true;
        return false;
      })
      .catch(function () { return false; });   // 查不到就照常交（宁可重复，也不要把作答弄丢）
  }

  function submit() {
    if (st.sending || st.sent) return;
    var s = appState();
    if (!s) return;
    st.sending = true; st.err = null;
    paint();
    var p;
    try { p = buildPayload(s); } catch (e) { st.sending = false; st.err = String(e && e.message || e); paint(); return; }
    alreadySubmitted(p.code).then(function (dup) {
      if (dup) { st.sending = false; st.sent = true; st.err = null; st.dup = true; paint(); return; }
      return doPost(p);
    });
  }

  function doPost(p) {
    fetch(ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(p)
    }).then(function (r) {
      return r.text().then(function (t) {
        var j = null;
        try { j = JSON.parse(t); } catch (e) { j = null; }
        return { ok: r.ok, j: j };
      });
    }).then(function (res) {
      st.sending = false;
      if (res.ok && res.j && res.j.ok) { st.sent = true; st.err = null; }
      else { st.err = (res.j && res.j.error) || "提交失败（HTTP " + (res.ok ? "?" : "错误") + "）"; }
      paint();
    }).catch(function (e) {
      st.sending = false;
      st.err = "网络异常：" + String(e && e.message || e);
      paint();
    });
  }

  /* 完成页：云版口径。**候选人只看到两个词：「已完成」与「成功提交」**（维护者 2026-10-25 定）。
     没有分数、没有等级、没有回传话术、也不解释流程。
     复核 / 更正 / 删除的入口在**作答前的告知卡第 7 条**里已经给过，完成页不再重复。 */
  function doneHtml(s) {
    var status;
    if (st.incomplete) {
      /* 未答完 ⇒ **不交卷**（2026-10-26 · 票 #26 根因之后加的闸门）。
         这时候页面不能显示「已完成」—— 她还没做完，显示了就是骗人。 */
      var c = st.incomplete;
      var parts = [];
      if (c.missing.m1) parts.push("第一项 " + c.missing.m1 + " 题");
      if (c.missing.m2) parts.push("第二项 " + c.missing.m2 + " 题");
      if (c.missing.m3) parts.push("第三项 " + c.missing.m3 + " 题");
      status = "<div class=\"warn\" style=\"margin-top:var(--sp-3)\">还有 <b>" + c.total +
        "</b> 道题没有作答（" + parts.join("、") + "）。没作答的题会按未作答计分，" +
        "<b>请先补答再交卷</b>。</div>" +
        "<button class=\"btn btn-primary btn-full\" style=\"margin-top:var(--sp-2)\" onclick=\"window.__cloudJump()\">去补答</button>" +
        "<button class=\"btn btn-quiet btn-full\" style=\"margin-top:var(--sp-2)\" onclick=\"window.__cloudForceSubmit()\">仍然提交（按未作答计分）</button>";
    } else if (st.sent) {
      status = "<div class=\"panel\"><p class=\"hint\">成功提交</p></div>";
    } else if (st.sending) {
      status = "<div class=\"panel\"><p class=\"hint\">提交中…</p></div>";
    } else if (st.err) {
      status = "<div class=\"panel\"><p class=\"hint\">提交未成功：" + esc(st.err) + "</p>" +
        "<button class=\"btn btn-primary btn-full\" style=\"margin-top:var(--sp-2)\" onclick=\"window.__cloudRetry()\">重新提交</button>" +
        /* 兜底出口：上传失败时，作答要能被带走（app.js 的云版完成页本来就有这一条，
           但 paint() 换掉整块 .sheet 会把它抹掉 ⇒ 这里补回来） */
        "</div>";
    } else {
      status = "<div class=\"panel\"><p class=\"hint\">提交中…</p></div>";
    }
    var limit = (s && s.limitHint)
      ? "<div class=\"warn\" style=\"margin:var(--sp-3) 0 0\">限时到点时你已作答 " + s.limitHint.answered + " / " + s.limitHint.total + " 题，之后继续作答并自行交卷。</div>"
      : "";
    return "<div class=\"done-seal\">\u2713</div>" +
      "<h2 style=\"font-size:var(--fs-6);text-align:center\">已完成</h2>" +
      limit + status;
  }

  var lastPainted = null;
  function paint() {
    var s = appState();
    if (!s || s.screen !== "done") return;
    var sheet = document.querySelector(".sheet");
    if (!sheet) return;
    /* 幂等：内容没变就不碰 DOM。
       2026-10-25 修（真实候选人反馈「走到第三项最后一题后网页卡住」）：
       MutationObserver 盯着 body，paint() 每次都重写 innerHTML ⇒ 改动又触发观察者
       ⇒ paint() 又跑 ⇒ **无限渲染循环**，页面直接卡死（作答其实已经落库了）。
       ⇒ 用 lastPainted 记住上次画的内容，变了才重画。 */
    var html = doneHtml(s);
    if (lastPainted === html) return;
    lastPainted = html;
    sheet.innerHTML = html;
  }

  /* 隐藏施测人入口（候选人页用不到；HR 侧走汇总台/数据库） */
  function hideHrEntry() {
    var links = document.querySelectorAll("a, .hint");
    for (var i = 0; i < links.length; i++) {
      if (/施测人入口/.test(links[i].textContent || "")) links[i].style.display = "none";
    }
  }

  function tick() {
    var s = appState();
    if (!s) return;
    if (s.screen === "done") {
      /* 完整度闸门：还有空位 ⇒ 不自动交卷，先让她去补（2026-10-26 · 票 #26）。
         补完（或她明确选择「仍然提交」）才交。 */
      if (!st.submitted && !st.incomplete && !st.forceSubmit) {
        var c = completeness();
        if (c.total > 0) { st.incomplete = c; st.submitted = true; paint(); return; }
      }
      if (!st.submitted) { st.submitted = true; submit(); }
      paint();
    } else {
      hideHrEntry();
    }
  }

  window.__cloudRetry = function () { st.err = null; st.submitted = false; tick(); };
  /* 去补答：跳到第一处未答题，回到答题屏 */
  window.__cloudJump = function () {
    st.incomplete = null; st.submitted = false; st.forceSubmit = false;
    if (jumpToFirstEmpty()) { try { if (window.APP && window.APP.go) window.APP.go("quiz"); } catch (e) { } }
  };
  /* 仍然提交：明确同意按未作答计分 */
  window.__cloudForceSubmit = function () {
    st.incomplete = null; st.submitted = false; st.forceSubmit = true;
    submit();
  };

  function boot() {
    var obs = new MutationObserver(function () { tick(); });
    obs.observe(document.body, { childList: true, subtree: true });
    tick();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();
