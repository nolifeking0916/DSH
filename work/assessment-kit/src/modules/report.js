/* 报告层：三项计分、综合评估（档位层合成）、三模块报告页与总报告 */
window.REP = (function () {
  const D = window.__DATA__;
  const C = window.__COPY__;   /* 固定文案（口径说明的两套措辞在 copy.js，不在本文件写死） */
  const ORD = { "待提升": 1, "合格": 2, "良好": 3, "优秀": 4, "顶尖": 5 };
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const M3META = D.m3.meta || {};
  const W_DIFF = M3META.weights || { "1": 1.0, "2": 1.4, "3": 1.8 };
  const TOT_MU = M3META.tot_mu || 31.54, TOT_SD = M3META.tot_sd || 4.653;
  const DIM_MU = M3META.dim_mu || 3.942, DIM_SD = M3META.dim_sd || 1.6452;

  function erf(x) {
    const s = x < 0 ? -1 : 1; x = Math.abs(x);
    const t = 1 / (1 + 0.3275911 * x);
    const y = 1 - ((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t * t - 0; // A&S 近似
    const y2 = 1 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t * Math.exp(-x * x);
    return s * y2;
  }
  const phi = (z) => 0.5 * (1 + erf(z / Math.SQRT2));
  function bandM1(score, bands) {
    for (const k of ["顶尖", "优秀", "良好", "合格"]) if (score >= bands[k][0] && score <= bands[k][1]) return k;
    return "待提升";
  }
  function bandWeighted(v) { return v >= 4.4 ? "顶尖" : v >= 3.8 ? "优秀" : v >= 3.0 ? "良好" : v >= 2.4 ? "合格" : "待提升"; }
  // 档位按百分位切（与原第三项口径一致）：P90 顶尖 / P70 优秀 / P45 良好 / P25 合格 / 以下待提升
  function bandPct(p) { return p >= 90 ? "顶尖" : p >= 70 ? "优秀" : p >= 45 ? "良好" : p >= 25 ? "合格" : "待提升"; }
  function bandComposite(v) { return v >= 4.5 ? "顶尖" : v >= 3.75 ? "优秀" : v >= 3.0 ? "良好" : v >= 2.25 ? "合格" : "待提升"; }

  /* ---------- 计分 ---------- */
  function scoreM1(S) {
    const bands = D.m1.meta.bands;
    const dims = D.m1.meta.dimensions.map((d) => {
      const items = D.m1.items.filter((it) => it.dim === d.key);
      let sc = 0;
      items.forEach((it) => {
        const idx = D.m1.items.indexOf(it);
        const picked = S.a.m1[idx];
        if (picked === null || picked === undefined) return;
        if ((it.anchor === "a" && picked === 0) || (it.anchor === "b" && picked === 1)) sc++;
      });
      return { key: d.key, name: d.name, score: sc, max: items.length, grade: bandM1(sc, bands) };
    });
    const short = dims.slice().sort((a, b) => ORD[a.grade] - ORD[b.grade])[0];
    const grade = short.grade; // 整体档 = 最低维档（短板决定）
    return { out: { dims: dims, grade: grade, short: { key: short.key, name: short.name, grade: short.grade } }, dims: dims, grade: grade, short: short };
  }

  function scoreM2(S) {
    const dims = D.eq.dimensions;
    // 序号口径必须与 app.js 一致：自评在前、情境在后，答案存在 S.a.m2[序号]
    const M2 = D.eq.self_items.map((x) => ({ kind: "self", id: x.id, dim: x.dimension, rev: !!x.reverse }))
      .concat(D.eq.sjt.map((x) => ({ kind: "sjt", id: x.id, dim: x.dimension, ans: x.answer, sec: x.second, thd: x.third, scored: x.scored !== false, pair: x.pair || "" })));
    const res = dims.map((d) => {
      let sc = 0, n = 0;
      M2.forEach((q, idx) => {
        if (q.kind !== "sjt" || q.dim !== d.key || !q.scored) return;
        const p = S.a.m2[idx];
        if (p === null || p === undefined) return;
        n++;
        const L = "ABCD";
        if (L[p] === q.ans) sc += 2;
        else if (q.sec && L[p] === q.sec) sc += 1;
        else if (q.thd && L[p] === q.thd) sc += 1;
      });
      const selfVals = [];
      M2.forEach((q, idx) => {
        if (q.kind !== "self" || q.dim !== d.key) return;
        const v = S.a.m2[idx];
        if (v === null || v === undefined) return;
        selfVals.push(q.rev ? 8 - v : v); // 反向题要反过来算
      });
      let selfAvg = null, flag = false;
      if (selfVals.length) {
        const avg = selfVals.reduce((a, b) => a + b, 0) / selfVals.length;
        selfAvg = (avg - 1) / 6 * 5; // 1-7 → 0-5
      }
      const avg = n ? sc / 12 * 5 : 0;
      if (selfAvg !== null && Math.abs(selfAvg - avg) >= 1.0) flag = true;
      return { key: d.key, name: d.name, score: sc, max: 12, avg: Math.round(avg * 100) / 100, grade: bandWeighted(avg), flag: flag, selfAvg: selfAvg === null ? null : Math.round(selfAvg * 100) / 100 };
    });
    // 一致性检查：同对两题都选 A/B（积极）或都选 C/D（消极）判一致；一正一负判需复核
    const pairs = {};
    M2.forEach((q, idx) => {
      if (q.kind !== "sjt" || !q.pair) return;
      const v = S.a.m2[idx];
      if (v === null || v === undefined) return;
      (pairs[q.pair] = pairs[q.pair] || []).push("ABCD"[v]);
    });
    const consistency = Object.keys(pairs).sort().map((p) => {
      const a = pairs[p];
      if (a.length < 2) return { pair: p, status: "未答完", detail: "" };
      const pos = a.filter((x) => x === "A" || x === "B").length;
      if (pos === 2) return { pair: p, status: "一致（积极型）", detail: a.join(" / ") };
      if (pos === 0) return { pair: p, status: "一致（消极型）", detail: a.join(" / ") };
      return { pair: p, status: "需复核", detail: a.join(" / ") };
    });
    const wsum = dims.reduce((s, d) => s + (d.weight || 0), 0) || 100;
    const total = res.reduce((s, r) => {
      const dim = dims.find((x) => x.key === r.key);
      return s + r.avg * ((dim && dim.weight) || 0) / wsum;
    }, 0);
    const grade = bandWeighted(total);
    const short = res.slice().sort((a, b) => ORD[a.grade] - ORD[b.grade])[0];
    return { out: { dims: res, total: Math.round(total * 100) / 100, grade: grade, short: { key: short.key, name: short.name, grade: short.grade }, needReview: res.filter((r) => r.flag).map((r) => r.name), consistency: consistency }, dims: res, grade: grade, short: short };
  }

  function scoreM3(S) {
    const dims = Object.keys(D.m3.dims);
    let wsum = 0;
    const wrong = [];
    D.m3.questions.forEach((q, idx) => {
      const p = S.a.m3[idx];
      if (p === null || p === undefined) return;
      if (p !== q.answer) wrong.push({ id: q.id, stem: q.stem, explain: q.explain || "" });
    });
    const dimArr = dims.map((k) => {
      let w = 0, c = 0, n = 0;
      D.m3.questions.forEach((q, idx) => {
        if (q.dim !== k) return;
        n++;
        const p = S.a.m3[idx];
        if (p === null || p === undefined) return;
        if (p === q.answer) { w += (W_DIFF[String(q.difficulty)] || 1); c++; }
      });
      const z = (w - DIM_MU) / DIM_SD;
      const pct = Math.max(0, Math.min(100, Math.round(phi(z) * 100)));
      const t = Math.round((50 + 10 * z) * 10) / 10;
      return { key: k, name: D.m3.dims[k].name, short: D.m3.dims[k].short, score: Math.round(w * 100) / 100,
               correct: c, total: n, rate: n ? Math.round(c / n * 100) : 0, pct: pct, t: t, grade: bandPct(pct) };
    });
    let total = 0;
    D.m3.questions.forEach((q, idx) => {
      const p = S.a.m3[idx];
      if (p === null || p === undefined) return;
      if (p === q.answer) total += (W_DIFF[String(q.difficulty)] || 1);
    });
    const z = (total - TOT_MU) / TOT_SD;
    const pct = Math.max(0, Math.min(100, Math.round(phi(z) * 100)));
    const t = Math.round((50 + 10 * z) * 10) / 10;
    const grade = bandPct(pct);
    const short = dimArr.slice().sort((a, b) => ORD[a.grade] - ORD[b.grade])[0];
    return { out: { total: Math.round(total * 100) / 100, pct: pct, t: t, grade: grade, dims: dimArr, wrong: wrong }, dims: dimArr, grade: grade, short: short };
  }

  function compose(m1, m2, m3) {
    const items = [
      { name: "第一项 · " + D.m1.meta.title, grade: m1.grade },
      { name: "第二项 · 情境测试", grade: m2.grade },
      { name: "第三项 · 推理测试", grade: m3.grade }
    ];
    const ord = items.map((i) => ORD[i.grade]);
    const avg = ord.reduce((a, b) => a + b, 0) / ord.length;
    const grade = bandComposite(avg);
    const minOrd = Math.min.apply(null, ord);
    const short = items[ord.indexOf(minOrd)];
    const skew = items.filter((i, k) => ORD[grade] - ORD[i.grade] >= 2);
    return { grade: grade, score: Math.round(avg * 100) / 100, short: short, skew: skew, items: items };
  }

  function score(S) {
    const m1 = scoreM1(S), m2 = scoreM2(S), m3 = scoreM3(S);
    const cp = compose(m1, m2, m3);
    return {
      m1: m1, m2: m2, m3: m3, compose: cp,
      out: { m1: m1.out, m2: m2.out, m3: m3.out, compose: cp }
    };
  }

  /* ---------- 报告渲染 ---------- */
  const LVL = { "顶尖": "T", "优秀": "A", "良好": "B", "合格": "C", "待提升": "D" };
  function gradePill(g) { return '<span class="grade-pill" data-level="' + (LVL[g] || "B") + '">' + esc(g) + "</span>"; }
  function gradeBlock(g, scoreText) {
    const n = ORD[g] || 1;
    const meter = '<span class="grade-meter">' + [1, 2, 3, 4, 5].map((i) => '<i class="' + (i <= n ? "on" : "") + '"></i>').join("") + "</span>";
    return '<span class="grade" data-level="' + (LVL[g] || "B") + '"><span class="grade-name">' + esc(g) + "</span>" +
      (scoreText ? '<span class="grade-score">' + esc(scoreText) + "</span>" : "") + meter + "</span>";
  }
  /* ---------- 票 #39：口径说明块 + 五级梯 ---------- */
  /* D2 裁定（维护者 2026-10-25 12:34）：校准前一律用「绝对锚点口径 + 明写尚未校准」。
     口径出处：items/m1_design.md §九.2（档位是专家阈值，不是人群分布）+ 票 #26 §12。
     切换点：把 CALIBRATED 改成 true，四个报告块的口径说明自动换成参照人群口径的措辞 ——
     两套措辞都放在 copy.js（calibAbs / calibRef），本文件只做选择，不并排写死。 */
  const CALIBRATED = false;
  const CALIB_TEXT = CALIBRATED ? C.calibRef : C.calibAbs;
  /* 口径说明块：告诉施测人这套档位是怎么划出来的、目前还没校准 */
  function calibNote() {
    return '<p class="calib"><b>口径说明</b>：' + esc(CALIB_TEXT) + "</p>";
  }
  /* 五级梯：从高到低（顶尖 → 待提升）五格并排。
     深绿格 = **已达到的档**（从低到高直到当前档，含当前档），当前档再加一道金线，
     浅灰格 = 未达到。与 .grade-meter「前 n 段点亮」同口径（同一人的两处图形不打架）。
     档名是主编码（文字写在格子里），底色只是辅助。 */
  const LADDER = ["顶尖", "优秀", "良好", "合格", "待提升"];
  function ladderHTML(grade) {
    const n = ORD[grade] || 1;
    return '<div class="ladder">' + LADDER.map((g) =>
      '<span class="' + (ORD[g] <= n ? "on" : "") + (g === grade ? " cur" : "") + '">' + esc(g) + "</span>"
    ).join("") + "</div>";
  }
  function ladderBlock(cap, grade) {
    return '<div class="ladder-cap">' + esc(cap) + " · 五级档上的位置（深绿＝已达到的档）</div>" + ladderHTML(grade);
  }
  /* 维度条：一行一值（票 #27）。
     .metric-row 已经是「名 + 分 + 五级胶囊」（《测评设计规范》§五组件表），
     所以条形只负责**把分数画出来**，不再在右端重复同一个数 —— 原来的
     「18/24」在上下两行各出现一次，看着像出错。 */
  function bar(label, v, max, valueText) {
    const p = Math.max(0, Math.min(100, Math.round(v / max * 100)));
    const val = valueText ? '<span class="bar-value">' + esc(valueText) + "</span>" : "";
    return '<div class="bar"><span class="bar-label">' + esc(label) + '</span><span class="bar-track"><span class="bar-fill" style="width:' + p + '%"></span></span>' + val + "</div>";
  }
  function metricRow(d) {
    return '<div class="metric-row"><span class="mr-name">' + esc(d.name) + '</span><span class="mr-score">' +
      esc(d.scoreText || (d.score + (d.max ? " / " + d.max : ""))) + "</span>" + gradePill(d.grade) + "</div>" +
      (d.max ? bar("相对表现", d.score, d.max) : "");
  }
  const RADAR_SHORT = { DED: "演绎", IND: "归纳", NUM: "数量", CON: "约束", SPA: "图形", CRI: "批判", PLN: "规划", RSK: "风险" };
  function radarSVG(dims) {
    const R = 108, cx = 180, cy = 150, n = dims.length;
    const pt = (i, r) => {
      const a = -Math.PI / 2 + i * 2 * Math.PI / n;
      return [cx + Math.cos(a) * r, cy + Math.sin(a) * r];
    };
    const poly = (arr) => arr.map((p) => p[0].toFixed(1) + "," + p[1].toFixed(1)).join(" ");
    const grid = [0.25, 0.5, 0.75, 1].map((f) => poly(dims.map((_, i) => pt(i, R * f))));
    const self = dims.map((d, i) => pt(i, R * Math.max(0.04, Math.min(1, d.pct / 100))));
    const labels = dims.map((d, i) => {
      const p = pt(i, R + 24);
      const p2 = pt(i, R * Math.max(0.04, Math.min(1, d.pct / 100)));
      /* 数值标在**顶点外侧**（票 #27）：之前写的是 `p2[1] < cy ? -6 : 12` —— 漏了
         `p2[1] +`，于是上半圈所有数值标签都塌到 SVG 顶边（y=-6 / 12），互相叠、
         还跟顶部维度名叠在一起，读者根本对不上哪个数属于哪一维（这正是「蛛网图的
         分数和推理测试对不上」的一半原因）。现在按顶点位置偏移：
         上半圈放顶点上方、下半圈放下方、水平轴放点的正上方。 */
      const left = p2[0] < cx - 6, right = p2[0] > cx + 6;
      const vx = left ? p2[0] - 7 : right ? p2[0] + 7 : p2[0];
      const anchor = left ? "end" : right ? "start" : "middle";
      const onAxis = Math.abs(p2[1] - cy) < 10;   // 水平轴上的顶点：数值放到点的正上方，避开维度名
      const vy = onAxis ? p2[1] - 9 : (p2[1] < cy ? p2[1] - 7 : p2[1] + 15);
      /* 数值标签写「P75」而不是「75」：这张图画的是**参考分布百分位**，
         顶点标 P 前缀 = 口径自明（不用猜是百分位还是百分数）。
         与 Word/PDF 双胞胎（src/build_report_docx.py 的 radar_svg，标 P%d）
         和下方维度行的「P75」完全同口径 —— 票 #27 的「两个口径并置」就是这么消掉的。 */
      return '<text class="radar-label" x="' + p[0].toFixed(1) + '" y="' + p[1].toFixed(1) + '" text-anchor="middle">' + esc(RADAR_SHORT[d.key] || d.short || d.name) + "</text>" +
        '<text class="radar-value" x="' + vx.toFixed(1) + '" y="' + vy.toFixed(1) + '" text-anchor="' + anchor + '">P' + d.pct + "</text>";
    }).join("");
    const axes = dims.map((_, i) => { const p = pt(i, R); return '<line class="radar-axis" x1="' + cx + '" y1="' + cy + '" x2="' + p[0].toFixed(1) + '" y2="' + p[1].toFixed(1) + '"/>'; }).join("");
    const dots = dims.map((d, i) => '<circle class="radar-point" cx="' + self[i][0].toFixed(1) + '" cy="' + self[i][1].toFixed(1) + '" r="3"/>').join("");
    return '<div class="radar-wrap"><svg class="radar" viewBox="0 0 360 300" width="360" height="300" role="img" aria-label="八维度相对位置雷达图">' +
      '<g class="radar-grid">' + grid.map((g) => '<polygon points="' + g + '"/>').join("") + axes + "</g>" +
      '<polygon points="' + poly(dims.map((_, i) => pt(i, R * 0.25))) + '" fill="none" stroke="#B7BEB9" stroke-width="1" stroke-dasharray="3 3"/>' +
      '<polygon points="' + poly(dims.map((_, i) => pt(i, R * 0.5))) + '" fill="none" stroke="#C9A55C" stroke-width="1" stroke-dasharray="3 3"/>' +
      '<polygon class="radar-area" points="' + poly(self) + '"/>' + dots + labels + "</svg></div>" +
      '<p class="note">实线 = 本次作答在参考分布上的<b>百分位</b>位置；金色虚线 = 参考分布中位（P50）；灰色虚线 = 参考分布第 25 百分位。每个顶点旁同时标注维度名与百分位数值（黑白打印也能读）；下方维度行给出该维的「对 / 总题数」与百分位、T 分，可互相核对。</p>';
  }

  function composeBlock(cp) {
    const skew = cp.skew.length
      ? '<p class="compose-note compose-flag">结构性偏科：' + cp.skew.map((s) => esc(s.name)).join("、") + " 明显低于综合水平，面试优先追问这一项。</p>"
      : "";
    return '<section class="compose"><h3 class="compose-title">综合评估</h3>' +
      '<div class="compose-head">' + gradeBlock(cp.grade, "三项等级合成") + "</div>" +
      ladderBlock("综合档", cp.grade) +
      '<p class="compose-note">综合评估由三项的等级合成（顶尖 5 / 优秀 4 / 良好 3 / 合格 2 / 待提升 1，等权平均后切档），<b>不代表总分</b>，也不作一票否决的依据，只用来决定面试追问什么。</p>' +
      skew + "</section>" +
      '<div class="short-board">短板：<b>' + esc(cp.short.name) + "（" + esc(cp.short.grade) + "）</b>。整体档按最短板的一维确定。</div>";
  }
  function listMetrics(cp) {
    return '<div class="list-metrics">' + cp.items.map((i) =>
      '<div class="metric"><div class="metric-name">' + esc(i.name) + '</div><div class="metric-value">' + gradePill(i.grade) + "</div>" +
      '<div class="metric-note">短板提示见各模块报告页</div></div>').join("") + "</div>";
  }

  function build(data) {
    if (!data || !data.m1 || !data.m2 || !data.m3) throw new Error("结果数据不完整");
    const cp = data.compose || compose(
      { grade: data.m1.grade, dims: data.m1.dims },
      { grade: data.m2.grade, dims: data.m2.dims },
      { grade: data.m3.grade, dims: data.m3.dims }
    );
    /* limitHint = 限时到点的痕迹（票 #39 · D3）：到点**只提示、不自动交卷**，
       候选人继续作答、最后自己交卷。痕迹记着到点那一刻已答了多少题，
       供票 #26 第 13 条算「完成整卷比例 / 省略作答比例」。
       旧结果 JSON 没有这个字段 → null。 */
    return { code: data.code, name: data.name, idLast4: data.idLast4, date: data.date, m1: data.m1, m2: data.m2, m3: data.m3, compose: cp, limitHint: data.limitHint || null };
  }

  function secHTML(R, id) {
    const cp = R.compose;
    if (id === "total") {
      /* 到点痕迹必须一眼可见：分数会被未作答拉低，
         施测人若不知道这份结果是到点之后接着答的，就会把「超时」当成「能力差」（票 #25/#39）。 */
      const hint = R.limitHint;
      const hintBlock = hint
        ? '<div class="warn" style="margin:var(--sp-3) 0"><b>限时到点（未自动交卷）</b>：限时到点时已作答 ' +
          hint.answered + " / " + hint.total + " 题；到点后候选人可继续作答，最终由本人自行交卷。判读时请把这一点计入完成度。" +
          "</div>"
        : "";
      return hintBlock + calibNote() + composeBlock(cp) + '<div class="rep-block"><h3>三项成绩</h3>' + listMetrics(cp) + "</div>" +
        '<div class="rep-block"><h3>怎么用这份结果</h3><p class="note">测评只产出追问清单，不作录用评分项：同一岗位对所有候选人使用同一套题、同一权重、同一阈值；面试按各档位的追问方向取证，录用决策由简历、专业技能、面谈与工作样本多源证据支撑；测评与面试冲突时以面试与工作样本为主，并记录冲突原因。</p></div>';
    }
    if (id === "m1") {
      return '<div class="rep-block"><h3>第一项 · ' + esc(D.m1.meta.title) + "</h3>" +
        calibNote() +
        /* 四维每行仍是「名 + 分 + 五级胶囊」，**不加迷你梯**：五格并排放不下
           「待提升」（实测折行成两行，390 与 800 宽都难看）—— 按票 #39「别硬塞」，
           梯只给整体档（总报告给综合档、第二项给整体档）。 */
        '<div class="dims">' + R.m1.dims.map((d) => metricRow(d)).join("") + "</div>" +
        ladderBlock("整体档", R.m1.grade) +
        '<div class="short-board">短板：<b>' + esc(R.m1.short.name) + "（" + esc(R.m1.short.grade) + "）</b>。整体档按最短板的一维确定。</div>" +
        '<p class="note">每维 0–24 分，按绝对锚点切档（顶尖 22–24 / 优秀 18–21 / 良好 14–17 / 合格 9–13 / 待提升 0–8）；暂未建立参照分布，后续内部样本到量后校准。</p>' +
        "</div>";
    }
    if (id === "m2") {
      const need = (R.m2.needReview || []);
      return '<div class="rep-block"><h3>第二项 · 情境测试</h3>' +
        calibNote() +
        '<div class="dims">' + R.m2.dims.map((d) => metricRow(d)).join("") + "</div>" +
        ladderBlock("整体档", R.m2.grade) +
        '<p class="note">加权总分 ' + R.m2.total + " / 5.00。档位：顶尖 ≥4.4 / 优秀 3.8–4.39 / 良好 3.0–3.79 / 合格 2.4–2.99 / 待提升 &lt;2.4。</p>" +
        (need.length ? '<div class="short-board">需复核：<b>' + esc(need.join("、")) + "</b>（自我参照与情境作答差异较大，按『需结合真实经历再确认』处理，不直接采信任一方）。</div>" : "") +
        ((R.m2.consistency && R.m2.consistency.length) ? '<div class="rep-block keep" style="margin-top:var(--sp-4)"><h3>一致性检查</h3><ul class="must">' +
          R.m2.consistency.map((c) => "<li><b>" + esc(c.pair) + "</b>：" + esc(c.status) + "（作答 " + esc(c.detail) + "）</li>").join("") + "</ul>" +
          '<p class="note">一致性检查题不计入任何维度分，只用于观察同一致情境的两种问法是否指向同一倾向；一正一负的按需复核处理。</p></div>' : "") +
        "</div>";
    }
    return '<div class="rep-block"><h3>第三项 · 推理测试</h3>' +
      calibNote() +
      '<div class="radar-wrap">' + radarSVG(R.m3.dims) + "</div>" +
      /* 维度行同时给三个数：原始分（对 / 总）+ 模型换算（百分位 / T 分）——
         雷达图画的是百分位，这一行给出百分位与 T 分，两个口径就能互相推导（票 #27）。
         只写「对 / 总」时，读者对不上雷达上的数。 */
      '<div class="dims">' + R.m3.dims.map((d) => metricRow(Object.assign({}, d, {
        scoreText: d.correct + " / " + d.total + "　·　P" + d.pct + "　·　T " + d.t, max: 0
      }))).join("") + "</div>" +
      '<p class="note">难度加权答对 ' + R.m3.total + " 分 · 参考分布第 " + R.m3.pct + " 百分位 · T 分 " + R.m3.t +
      "。百分位基于内置参考分布（按题目难度加权的理论模型）换算，不是商业常模，也不等同任何标准化智力测验；T 分超出 100 表示超出模型分布上端（满分作答的正常结果），档位以百分位为准。</p>" +
      /* 「错题回顾」整块去掉（维护者 2026-10-24 裁定：施测人报告只要结果、解析与对候选人的判断；
         逐题解析是给考生自己复盘的，打印出来是 4000+ 字一堵墙 —— 票 #27）。 */
      ((D.m3.must_say && D.m3.must_say.length) ? '<div class="rep-block"><h3>对外反馈时必须说明</h3><ul class="must">' + D.m3.must_say.map((t) => "<li>" + esc(t) + "</li>").join("") + "</ul></div>" : "") +
      ((D.m3.must_not_say && D.m3.must_not_say.length) ? '<div class="rep-block"><h3>对外反馈时不得说</h3><ul class="must">' + D.m3.must_not_say.map((t) => "<li>" + esc(t) + "</li>").join("") + "</ul></div>" : "") +
      "</div>";
  }

  function reportHTML(R) {
    const cp = R.compose;
    const nav = [['总报告', 'total'], ['第一项', 'm1'], ['第二项', 'm2'], ['第三项', 'm3']];
    const sec = (id) => secHTML(R, id);
    LAST = R;
    const PAGES = [["total", "总报告"], ["m1", "第一项报告"], ["m2", "第二项报告"], ["m3", "第三项报告"]];
    const all = PAGES.map((pg, i) =>
      '<section class="rep-sec' + (pg[0] === "total" ? " on" : "") + '" data-sec="' + pg[0] + '">' +
      '<div class="print-only print-head">报告区块 ' + (i + 1) + " / " + PAGES.length + "： " + esc(pg[1]) +
      " ｜ " + esc(R.name || "") + " ｜ 编号 " + esc(R.code || "") + (R.idLast4 ? " ｜ 末 4 位 " + esc(R.idLast4) : "") + "</div>" +
      secHTML(R, pg[0]) +
      // 区块落款：跨浏览器都能定位到「这是谁的报告、报告第几块」；不依赖固定定位（固定元素会压住正文）
      '<div class="print-only print-end">本区块结束 ｜ 云上文旅集团核心人才系列测试 ｜ 编号 ' + esc(R.code || "") +
      (R.name ? " ｜ " + esc(R.name) : "") + (R.idLast4 ? " ｜ 末 4 位 " + esc(R.idLast4) : "") +
      " ｜ 报告共 " + PAGES.length + " 个区块（每块另起一页）</div></section>").join("");
    return '<div class="wrap" style="max-width:760px">' +
      '<div class="topbar"><div class="wrap" style="padding:0"><div class="toprow"><b>施测人报告</b><span' +
      /* 有到点痕迹时把整行透明度拉回 1，否则金色徽标被父组 opacity:.92 压到 4.5:1 以下 */
      (R.limitHint ? ' style="opacity:1"' : "") + ">" + esc(R.name || "") +
      " ｜ " + esc(String(R.code || "").slice(0, 12)) + "…" + (R.idLast4 ? " ｜ 末4位 " + esc(R.idLast4) : "") +
      (R.limitHint ? ' ｜ <span style="color:var(--gold);font-weight:700">限时到点（未自动交卷）</span>' : "") + "</span></div></div></div>" +
      '<div class="rep-nav noprint">' + nav.map((n) => '<button data-s="' + n[1] + '" onclick="REP.setSec(this.dataset.s)">' + esc(n[0]) + "</button>").join("") + "</div>" +
      '<div id="rep-body" style="padding-bottom:var(--sp-6)">' + all + "</div>" +
      '<div class="noprint" style="margin:var(--sp-3) 0"><button class="btn btn-primary btn-full" onclick="window.print()">打印 / 存为 PDF</button></div>' +
      '<div class="foot">' + C.foot.map((f) => "<b>" + esc(f) + "</b>").join("") + "</div></div>";
  }

  let LAST = null;
  function setSec(id) {
    if (!LAST) return;
    const btns = document.querySelectorAll(".rep-nav button");
    btns.forEach((b) => b.setAttribute("aria-current", b.dataset.s === id ? "true" : "false"));
    document.querySelectorAll(".rep-sec").forEach((s) => s.classList.toggle("on", s.dataset.sec === id));
    window.scrollTo(0, 0);
  }

  /* setSec 必须导出：报告页的切换按钮写的是 onclick="REP.setSec(...)"
     —— 2026-10-25 修（票 #39 顺带发现的老 bug）：原来没导出，点任何一个区块标签
     都抛 "REP.setSec is not a function"，四个报告块里只有「总报告」能看见。 */
  return { score: score, build: build, reportHTML: reportHTML, setSec: setSec, gradePill: gradePill, bandComposite: bandComposite, ORD: ORD };
})();
