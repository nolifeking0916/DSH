/* report_profile.js —— report_v2_profile.py 的 JS 同构实现（票 #78 / 口径 22）。
 *
 * 类型归类 / 形象类比 / 三档与潜力给分，与 Python 侧逐函数对应；
 * verify_block_parity.py 会对同一份结果 JSON 逐块比对，改任一侧必须两边同改。
 *
 * 浏览器：画像文案取 window.__REPORT_PROFILES__（build.py 内联 data/report_profiles.json）。
 * Node：create(profiles) 显式传入。
 */
(function (root, factory) {
  if (typeof module !== "undefined" && module.exports) module.exports = factory;
  root.RPROFILE = factory();  // 浏览器：画像文案取 window.__REPORT_PROFILES__
})(typeof self !== "undefined" ? self : this, function (profilesArg) {
  const ORDER = ["待提升", "合格", "良好", "优秀", "顶尖"];
  const TILT_MIN = 13;

  function profiles() {
    return profilesArg || (typeof window !== "undefined" ? window.__REPORT_PROFILES__ : null);
  }

  // ≥85% 突出 / 70-85% 常规 / <70% 偏弱（维护者 2026-10-26 裁定）
  function band3(pct) {
    if (pct >= 85) return "突出";
    if (pct >= 70) return "常规";
    return "偏弱";
  }

  // round(x,1) 用「四舍五入 .5 进位」（与 Python round(p*100,1) 的展示口径一致；
  // 这里 p 已是一位小数，直接判档）
  function dimBand3(score, mx) {
    const p = mx ? Math.round((score / mx) * 1000) / 10 : 0;
    return band3(p);
  }

  function typeProfile(m1) {
    const P = profiles();
    const axes = [];
    const letters = "";
    const m1dims = (m1 && m1.dims) || [];
    m1dims.forEach(function (d) {
      const a = P.axes[d.key] || {};
      const side = d.score >= TILT_MIN ? "a" : "b";
      const info = (side === "a" ? a.a : a.b) || {};
      const letter = info.letter;
      axes.push({
        key: d.key, name: d.name, axis: a.axis,
        side_label: info.label, letter: letter,
        score: d.score, max: d.max, grade: d.grade, desc: info.desc,
      });
    });
    let code = "";
    axes.forEach(function (ax) { code += ax.letter || ""; });
    const t = (P.types && P.types[code]) || {};
    const sent = axes.map(function (x) {
      return x.name + "偏" + (x.side_label || "");
    }).join("、");
    return {
      code: code,
      type_name: t.name || "",
      type_desc: t.desc || "",
      summary: sent,
      axes: axes,
    };
  }

  function animalProfile(m1, m2, m3) {
    const P = profiles();
    function g(grade) { return ORDER.indexOf(grade); }
    const tp = typeProfile(m1);
    const by = tp.code[0] === "E" ? "%s_%s_%s" : "%s_%s_%s";
    const k = tp.code[0] + "_" + tp.code[1] + "_" + tp.code[3];
    const a = (P.animals && P.animals[k]) || {};
    const s1 = g((m1.short || {}).grade);
    const s2 = g(m2.grade);
    const s3 = g(m3.grade);
    const strength = (s1 >= 3 && s3 >= 3) ? "性格面与逻辑面都靠前"
      : (s2 >= 3 && s2 >= s1 && s2 >= s3) ? "情绪面最稳"
      : (s2 <= Math.min(s1, s3)) ? "情绪面相对吃紧"
      : "三类表现比较均衡";
    return { key: k, name: a.name || "", why: a.why || "", strength: strength };
  }

  function threeBand(m1, m2, m3) {
    const P = profiles();
    const p1 = (m1.dims.reduce(function (s, d) { return s + d.score / (d.max || 24); }, 0) / m1.dims.length) * 100;
    const p2 = (m2.total || 0) / 5.0 * 100;
    const p3 = (m3.total || 0) / 40.0 * 100;
    function r1(v) { return Math.round(v * 10) / 10; }
    const parts = [
      { name: "性格特质", score_text: m1.score_text, pct: r1(p1), basis: "四维 0–24（各维独立，无总档）", max_text: "性格特质 0–24" },
      { name: "情绪特质", score_text: (m2.total || 0).toFixed(2) + " / 5.00", pct: r1(p2), basis: "0–5.00", max_text: "情绪特质 0–5.00" },
      { name: "逻辑评价", score_text: (m3.total || 0).toFixed(1) + " / 40", pct: r1(p3), basis: "难度加权 0–40", max_text: "逻辑评价 0–40" },
    ];
    parts.forEach(function (x) {
      x.band = band3(x.pct);
      x.text = (P.bands[x.name] || {})[x.band] || "";
    });
    const weak = parts.slice().sort(function (a, b) { return a.pct - b.pct; })[0];
    return {
      parts: parts,
      weakest: weak,
      gapToTop: Math.max(0, Math.round((85.0 - weak.pct) * 10) / 10),
      note: P.band_note || "",
    };
  }

  function overallSentence(m1, m2, m3, tp, an, tb) {
    const p = {};
    tb.parts.forEach(function (x) { p[x.name] = x; });
    const em = (p["情绪特质"] || {}).text || "";
    const lg = (p["逻辑评价"] || {}).text || "";
    return "性格上属于" + (tp.type_name || "未定型") + "（" + tp.code + "），" +
      (tp.type_desc || "") + "；情绪上" + em + "；逻辑上" + lg;
  }

  return {
    ORDER: ORDER, TILT_MIN: TILT_MIN,
    band3: band3, dimBand3: dimBand3,
    typeProfile: typeProfile, animalProfile: animalProfile,
    threeBand: threeBand, overallSentence: overallSentence,
  };
});
