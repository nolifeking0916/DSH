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
  var st = { sending: false, sent: false, err: null, submitted: false };

  function appState() {
    try { return (window.APP && window.APP.S) ? window.APP.S() : null; } catch (e) { return null; }
  }
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
      return ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", """: "&quot;" }[c]);
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

  /* 把稀疏数组补成定长数组：没答的位置是 null（= 未作答），不是缺项 */
  function normalize(list, len) {
    var out = new Array(len);
    for (var i = 0; i < len; i++) {
      var v = (list && list.length > i) ? list[i] : null;
      out[i] = (v === 0 || v === 1) ? v : null;
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
      group: s.group || null,
      level: s.level || null,
      dept: s.dept || null,
      m1_raw: normalize(a.m1, nItems()),
      m2_answers: m2,
      m3_answers: normalize(a.m3, nM3()),
      started_at: s.t0 ? new Date(s.t0).toISOString() : null,
      duration_ms: s.t0 ? Math.round(Date.now() - s.t0) : null,
      limit_hint: s.limitHint || null
    };
  }

  function submit() {
    if (st.sending || st.sent) return;
    var s = appState();
    if (!s) return;
    st.sending = true; st.err = null;
    paint();
    var p;
    try { p = buildPayload(s); } catch (e) { st.sending = false; st.err = String(e && e.message || e); paint(); return; }
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
      st.err = "网络异常：\u" + String(e && e.message || e);
      paint();
    });
  }

  /* 完成页：云版口径。没有分数、没有等级、没有回传话术。 */
  function doneHtml(s) {
    var status;
    if (st.sent) {
      status = "<div class=\"panel\"><p class=\"hint\">本次作答已提交，结果由集团人力资源部保管。</p></div>";
    } else if (st.sending) {
      status = "<div class=\"panel\"><p class=\"hint\">正在提交…</p></div>";
    } else if (st.err) {
      status = "<div class=\"panel\"><p class=\"hint\">提交未成功：" + esc(st.err) + "</p>" +
        "<button class=\"btn btn-primary btn-full\" style=\"margin-top:var(--sp-2)\" onclick=\"window.__cloudRetry()\">重新提交</button></div>";
    } else {
      status = "<div class=\"panel\"><p class=\"hint\">准备提交…</p></div>";
    }
    var limit = (s && s.limitHint)
      ? "<div class=\"warn\" style=\"margin:var(--sp-3) 0 0\">限时到点时你已作答 " + s.limitHint.answered + " / " + s.limitHint.total + " 题，之后继续作答并自行交卷。</div>"
      : "";
    return "<div class=\"done-seal\">\u2713</div>" +
      "<h2 style=\"font-size:var(--fs-6);text-align:center\">已完成</h2>" +
      "<p class=\"hint\" style=\"max-width:330px;margin:var(--sp-2) auto 0;text-align:center\">本次结果已由集团人力资源部保管；本页面不显示你的结果。如需查询、更正或要求删除，请联系集团人力资源部。</p>" +
      limit + status;
  }

  function paint() {
    var s = appState();
    if (!s || s.screen !== "done") return;
    var sheet = document.querySelector(".sheet");
    if (!sheet) return;
    sheet.innerHTML = doneHtml(s);
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
      paint();
      if (!st.submitted) { st.submitted = true; submit(); }
    } else {
      hideHrEntry();
    }
  }

  window.__cloudRetry = function () { st.err = null; st.submitted = false; tick(); };

  function boot() {
    var obs = new MutationObserver(function () { tick(); });
    obs.observe(document.body, { childList: true, subtree: true });
    tick();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();
