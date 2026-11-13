/* 施测人汇总台 · 前端逻辑（票 #45 · 施测人侧落地）
 * ------------------------------------------------------------------
 * 这一页是**只读**的：不写库、不改任何一份作答。
 * 数据源有三个（都由云函数算，页面只渲染）：
 *   ① GET ?action=list&limit=N                 → 汇总列表（姓名 / 编号 / 组 / 岗位层级 / 等级 / 提交时间 / 时长 / 未答题数）
 *   ② GET ?action=export&code=…&src=hr         → 一份属于某人的报告（服务端算分 + 综合档）
 *   ③ GET ?action=export&scope=batch&limit=N   → 一批的汇总（分布统计）
 *      GET ?action=export&scope=batch&limit=N&format=pipeline → 离线分析管线吃的 JSON
 *
 * 两条硬约束（票 #45 / 票 #36）：
 *   · **页面不展示逐题作答**（第一项 96 题的逐题作答一次都不进 DOM，也不进任何下载文件）；
 *   · 页面不提供任何写入 / 删除入口。
 *
 * 端点地址由 build_hr.py 注入（__ENDPOINT__ 占位符只在这里替换一次）。
 */
(function () {
  "use strict";

  var ENDPOINT = "__ENDPOINT__";
  var $ = function (s) { return document.querySelector(s); };
  var state = { limit: 50, rows: [], one: null, batch: null };

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
      return ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c];
    });
  }
  function dash(v) { return (v === null || v === undefined || v === "") ? "—" : String(v); }
  function fmtTime(s) {
    if (!s) return "—";
    var d = new Date(s);
    if (isNaN(d.getTime())) return String(s);
    var p = function (n) { return String(n).padStart(2, "0"); };
    return d.getFullYear() + "-" + p(d.getMonth() + 1) + "-" + p(d.getDate()) + " " + p(d.getHours()) + ":" + p(d.getMinutes());
  }
  function fmtDur(ms) {
    if (ms === null || ms === undefined) return "—";
    var s = Math.round(ms / 1000);
    var m = Math.floor(s / 60);
    return m ? (m + " 分 " + (s % 60) + " 秒") : (s + " 秒");
  }
  function getJSON(q) {
    return fetch(ENDPOINT + "?" + q).then(function (r) { return r.json(); });
  }
  function note(msg, kind) {
    var el = $("#note");
    el.textContent = msg || "";
    el.className = "note " + (kind || "");
  }
  function download(name, text, mime, bom) {
    var blob = new Blob([(bom ? "\ufeff" : "") + text], { type: (mime || "text/plain") + ";charset=utf-8" });
    var url = URL.createObjectURL(blob);
    var a = document.createElement("a");
    a.href = url; a.download = name;
    document.body.appendChild(a); a.click();
    document.body.removeChild(a);
    setTimeout(function () { URL.revokeObjectURL(url); }, 1500);
  }
  function stamp() {
    var d = new Date();
    var p = function (n) { return String(n).padStart(2, "0"); };
    return d.getFullYear() + p(d.getMonth() + 1) + p(d.getDate()) + "-" + p(d.getHours()) + p(d.getMinutes());
  }

  /* ---------------- 汇总列表（票 #36 Q3 的默认列） ---------------- */
  var COLS = [
    { k: "respondent_name", t: "姓名" },
    { k: "code", t: "测评编号" },
    { k: "group_name", t: "组" },
    { k: "level", t: "岗位层级" },
    { k: "grade", t: "等级" },
    { k: "submitted_at", t: "提交时间", f: fmtTime },
    { k: "duration_ms", t: "时长", f: fmtDur },
    { k: "unanswered_m1", t: "未答题数" }
  ];

  function renderRows(rows) {
    state.rows = rows;
    var head = "<tr>" + COLS.map(function (c) { return "<th>" + c.t + "</th>"; }).join("") + "<th>操作</th></tr>";
    var body = rows.map(function (r) {
      return "<tr>" + COLS.map(function (c) {
        var v = c.f ? c.f(r[c.k]) : dash(r[c.k]);
        if (c.k === "grade" && r[c.k]) v = '<span class="grade-pill" data-level="' + levelKey(r[c.k]) + '">' + esc(r[c.k]) + "</span>";
        if (c.k === "code") v = '<code class="mono">' + esc(r[c.k]) + "</code>";
        return "<td>" + v + "</td>";
      }).join("") + '<td><button class="btn btn-quiet" data-code="' + esc(r.code) + '">看报告</button></td></tr>';
    }).join("");
    $("#rows").innerHTML = head + body;
    Array.prototype.forEach.call(document.querySelectorAll("#rows button[data-code]"), function (b) {
      b.addEventListener("click", function () { loadOne(b.getAttribute("data-code")); });
    });
    note(rows.length ? ("最近 " + rows.length + " 份（按提交时间倒序）") : "库里还没有作答记录。");
  }
  function levelKey(g) { return ({ "顶尖": "T", "优秀": "A", "良好": "B", "合格": "C", "待提升": "D" })[g] || "B"; }

  function loadList() {
    note("正在取…");
    getJSON("action=list&limit=" + state.limit).then(function (d) {
      if (!d || !d.ok) { note("取列表失败：" + (d && d.error ? d.error : "未知错误"), "bad"); return; }
      renderRows(d.rows || []);
    }).catch(function (e) { note("取列表失败：" + e, "bad"); });
  }

  /* ---------------- 按编号直达一份 ---------------- */
  function loadOne(code) {
    code = String(code || "").trim();
    if (!code) { note("先填测评编号。", "bad"); return; }
    note("正在取 " + code + " …");
    getJSON("action=export&code=" + encodeURIComponent(code) + "&src=hr").then(function (d) {
      if (!d || !d.ok) { note("取不到：" + (d && d.error ? d.error : "未知错误"), "bad"); return; }
      state.one = d;
      renderOne(d);
    }).catch(function (e) { note("取不到：" + e, "bad"); });
  }

  function renderOne(d) {
    var r = d.report || {};
    $("#one-meta").innerHTML =
      "<tr><th>测评编号</th><td><code class=\"mono\">" + esc(d.code) + "</code></td>" +
      "<th>姓名</th><td>" + esc(dash(d.respondent_name)) + "</td>" +
      "<th>身份证后 4 位</th><td>" + esc(dash(d.id_last4)) + "</td></tr>" +
      "<tr><th>组</th><td>" + esc(dash(d.group_name)) + "</td>" +
      "<th>岗位层级</th><td>" + esc(dash(d.level)) + "</td>" +
      "<th>提交时间</th><td>" + esc(fmtTime(d.submitted_at)) + "</td></tr>" +
      "<tr><th>时长</th><td>" + esc(fmtDur(d.duration_ms)) + "</td>" +
      "<th>未答题数</th><td>" + esc(dash(d.unanswered_m1)) + "</td>" +
      "<th>生成时间</th><td>" + esc(fmtTime(d.generated_at)) + "</td></tr>";
    var el = $("#report");
    if (window.REP && r.m1 && r.m2 && r.m3 && r.compose) {
      var R = { name: r.name, code: r.code, idLast4: r.idLast4, date: r.submitted_at,
                m1: r.m1, m2: r.m2, m3: r.m3, compose: r.compose,
                profile: d.respondent_profile || null };
      if (window.RBLOCKS && window.REP.buildBlocksReport) {
        el.innerHTML = window.REP.buildBlocksReport(R);
      } else {
        el.innerHTML = window.REP.reportHTML(R);
      }
    } else {
      el.innerHTML = '<p class="note bad">这一份的结果不完整（缺某一项的分数），渲染器不出报告。可先用「导出汇总」里的行看等级。</p>';
    }
    $("#one-panel").hidden = false;
    note("已取到 " + d.code + " 的报告。");
  }

  /* ---------------- 一键导出 ---------------- */
  function loadBatch() {
    note("正在算这一批的汇总…");
    getJSON("action=export&scope=batch&limit=" + state.limit + "&src=hr").then(function (d) {
      if (!d || !d.ok) { note("导出失败：" + (d && d.error ? d.error : "未知错误"), "bad"); return; }
      state.batch = d;
      renderDistribution(d);
      note("这一批 " + d.count + " 份的汇总已算好，可下载。");
    }).catch(function (e) { note("导出失败：" + e, "bad"); });
  }

  function distTable(obj, title) {
    var keys = Object.keys(obj || {});
    if (!keys.length) return "";
    return "<div class=\"dist\"><h4>" + esc(title) + "</h4><table>" +
      keys.map(function (k) { return "<tr><td>" + esc(k) + "</td><td>" + esc(obj[k]) + " 份</td></tr>"; }).join("") +
      "</table></div>";
  }
  function renderDistribution(d) {
    $("#dist").innerHTML =
      distTable(d.distribution && d.distribution.by_grade, "等级分布") +
      distTable(d.distribution && d.distribution.by_group, "组别分布") +
      distTable(d.distribution && d.distribution.by_level, "岗位层级分布");
    $("#batch-panel").hidden = false;
  }

  function csvCell(v) {
    var s = (v === null || v === undefined) ? "" : String(v);
    return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
  }
  function buildCSV(d) {
    var head = ["姓名", "测评编号", "组", "岗位层级", "等级", "提交时间", "时长（分）", "未答题数",
      "第一项四维", "第一项短板档", "第二项档", "第三项档"];
    var lines = [head.join(",")];
    (d.rows || []).forEach(function (r) {
      var dims = (r.m1_dims || []).map(function (x) { return x.name + " " + x.score + "/" + x.max + " " + x.grade; }).join("；");
      lines.push([
        csvCell(r.respondent_name), csvCell(r.code), csvCell(r.group_name), csvCell(r.level),
        csvCell(r.grade), csvCell(fmtTime(r.submitted_at)),
        csvCell(r.duration_ms === null ? "" : Math.round(r.duration_ms / 60000)),
        csvCell(r.unanswered_m1), csvCell(dims), csvCell(r.m1_grade),
        csvCell(r.m2_grade), csvCell(r.m3_grade)
      ].join(","));
    });
    return "\ufeff" + lines.join("\n");
  }

  function downloadCSV() {
    if (!state.batch) { note("先点「导出这一批的汇总」。", "bad"); return; }
    download("测评汇总_" + stamp() + ".csv", buildCSV(state.batch), "text/csv", false);
    note("已导出汇总 CSV。");
  }
  function downloadPipeline() {
    if (!state.batch) { note("先点「导出这一批的汇总」。", "bad"); return; }
    var q = state.batch.pipeline_query || ("action=export&scope=batch&limit=" + state.limit + "&format=pipeline&src=hr");
    getJSON(q).then(function (d) {
      var payload = { meta: d.meta, respondents: d.respondents, excluded: d.excluded };
      download("测评作答_分析用_" + stamp() + ".json", JSON.stringify(payload, null, 1), "application/json", false);
      note("已导出分析用 JSON（" + (d.respondents || []).length + " 份进管线" +
        ((d.excluded || []).length ? "，" + d.excluded.length + " 份未答完被单列" : "") + "）。");
    }).catch(function (e) { note("导出失败：" + e, "bad"); });
  }
  function downloadReport() {
    if (!state.one) { note("先按编号直达一份。", "bad"); return; }
    var css = document.getElementById("page-css").textContent;
    var html = '<!DOCTYPE html>\n<html lang="zh-CN">\n<head>\n<meta charset="UTF-8">\n' +
      '<title>施测人报告 ' + esc(state.one.code) + '</title>\n<style>\n' + css + "\n</style>\n</head>\n<body>\n" +
      $("#report").innerHTML + "\n</body>\n</html>";
    download("施测人报告_" + (state.one.respondent_name || "") + "_" + state.one.code + ".html", html, "text/html", false);
    note("已导出这一份的报告 HTML（可直接打开或打印成 PDF）。");
  }

  /* ---------------- 启动 ---------------- */
  document.addEventListener("DOMContentLoaded", function () {
    $("#limit").addEventListener("change", function (e) {
      state.limit = parseInt(e.target.value, 10) || 50;
      loadList();
    });
    $("#refresh").addEventListener("click", loadList);
    $("#go").addEventListener("click", function () { loadOne($("#code").value); });
    $("#code").addEventListener("keydown", function (e) { if (e.key === "Enter") loadOne($("#code").value); });
    $("#export-batch").addEventListener("click", loadBatch);
    $("#dl-csv").addEventListener("click", downloadCSV);
    $("#dl-json").addEventListener("click", downloadPipeline);
    $("#dl-report").addEventListener("click", downloadReport);
    loadList();
  });
})();
