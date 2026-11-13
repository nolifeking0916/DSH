/* report_blocks.js —— report_blocks.py 的 JS 同构实现（票 #78 / 口径 22）。
 *
 * 同一份结果 JSON，Python（生成器）与 JS（/hr/ 汇总台、离线单文件）产出同序、同字段的内容块，
 * 由 src/verify_block_parity.py 逐块比对。改任一侧必须两边同改。
 *
 * 依赖：window.__DATA__（题库）、window.__REPORT_PROFILES__（画像文案）、
 * window.__NARRATIVE_RULES__（离线判读快照，可选）；Node 下经 create(data, profiles, rules) 注入。
 */
(function (root, factory) {
  if (typeof module !== "undefined" && module.exports) module.exports = factory;
  root.RBLOCKS = factory();  // 浏览器：题库/文案取 window 注入
})(typeof self !== "undefined" ? self : this, function (bankArg, profilesArg, rulesArg) {
  const NAME_M1 = "人格特质";
  const NAME_M2 = "情景处理";
  const NAME_M3 = "逻辑分析能力";
  const ORDER = ["待提升", "合格", "良好", "优秀", "顶尖"];
  const ORG = "行政管理中心 · 行政人事部 · 干部管理组";
  // Node 调用 factory(bank, profiles, rules) 时显式注入；浏览器取 window 全局
  const D = bankArg || (typeof window !== "undefined" ? window.__DATA__ : null);
  const P = profilesArg || (typeof window !== "undefined" ? window.__REPORT_PROFILES__ : null);
  const RULES = rulesArg || (typeof window !== "undefined" ? window.__NARRATIVE_RULES__ : null) || [];
  const RPROFILE = (typeof window !== "undefined" && window.RPROFILE) ||
    (typeof require === "function" ? require("./report_profile.js")(P) : null);


    const ord = (g) => { const i = ORDER.indexOf(g); return i < 0 ? 0 : i; };
    const r1 = (v) => Math.round(v * 10) / 10;
    const f1 = (v) => (Math.round(v * 10) / 10).toFixed(1);

    /* ---------- 判读匹配（report_narrative.match_local 的同构） ---------- */
    function pick(list, module, dimension, band, pole, kind) {
      const cands = list.filter((r) => r.module === module && r.dimension === dimension &&
        (kind == null || r.kind === kind));
      const tries = [];
      if (band && band !== "__all__") {
        tries.push([band, pole || "__any__"]);
        tries.push([band, "__any__"]);
      }
      tries.push(["__all__", "__any__"]);
      for (const [b, pp] of tries) {
        for (const r of cands) {
          if (r.band === b && (r.pole || "__any__") === pp) return r;
        }
      }
      return null;
    }

    function matchLocal(profile) {
      const out = { personality: {}, situation: {}, reasoning: {}, overall: [] };
      const pp = profile.personality || {};
      Object.keys(pp).forEach((key) => {
        const d = pp[key];
        const r = pick(RULES, "personality", d.dimension || key, d.band, d.pole);
        if (r) out.personality[key] = { text: r.text, title: r.title, pole_label: r.pole_label, band: d.band, pole: d.pole };
      });
      const sp = profile.situation || {};
      Object.keys(sp).forEach((key) => {
        const d = sp[key];
        const r = pick(RULES, "situation", d.dimension || key, d.band, null);
        if (r) out.situation[key] = { text: r.text, title: r.title, band: d.band };
      });
      const rp = profile.reasoning || {};
      Object.keys(rp).forEach((key) => {
        const d = rp[key];
        const r = pick(RULES, "reasoning", d.dimension || key, d.band, null);
        if (r) out.reasoning[key] = { text: r.text, title: r.title, band: d.band };
      });
      const ov = profile.overall || {};
      (ov.kinds || []).forEach((kind) => {
        const r = pick(RULES, "overall", "__overall__", ov.grade, "__any__", kind);
        if (r) out.overall.push({ kind: kind, title: r.title, text: r.text });
      });
      return out;
    }

    /* ---------- 可信度（report_narrative.credibility 同构，含 #51 判缺分支） ---------- */
    function asList(v) {
      if (v == null) return [];
      if (!Array.isArray(v)) {
        const out = [];
        Object.keys(v).sort((a, b) => (Number.isFinite(+a) && Number.isFinite(+b) ? +a - +b : 0)).forEach((k) => out.push(v[k]));
        return out;
      }
      return v.slice();
    }
    function maxRun(seq) {
      let best = 0, cur = 0, prev = null;
      seq.forEach((v) => {
        if (v == null) { cur = 0; prev = null; return; }
        if (v === prev) cur++; else { cur = 1; prev = v; }
        if (cur > best) best = cur;
      });
      return best;
    }
    function credibility(data, m1, m2, m3, raw) {
      const m1Raw = raw || data.m1_raw;
      const m2Answers = data.m2_answers;
      const m3Answers = data.m3_answers;
      const out = {};
      let flags = [], level = "高";
      if (m1Raw) {
        const seq = m1Raw.slice();
        const run = maxRun(seq);
        const ones = seq.filter((v) => v === 1).length;
        const zeros = seq.filter((v) => v === 0).length;
        const answered = ones + zeros;
        const dom = answered ? Math.max(ones, zeros) / answered : 0;
        if (run >= 25 || dom >= 0.85) {
          level = "低";
          flags.push("96 题里同侧连答最长 " + run + " 题、某一侧占比 " + Math.round(dom * 100) + "%，接近连续作答同一端的形态");
        } else if (run >= 15 || dom >= 0.70) {
          if (level === "高") level = "中";
          flags.push("同侧连答最长 " + run + " 题、某一侧占比 " + Math.round(dom * 100) + "%，作答偏好偏集中");
        }
      }
      if (!m1Raw) {
        flags.push("本次未留存逐题作答，同侧作答与缺失只能看汇总口径");
        if (level === "高") level = "中";
      }
      const miss1 = data.unanswered_m1;
      if (Number.isInteger(miss1) && miss1 > 0) {
        flags.push("第一项有 " + miss1 + " 题未作答");
        if (miss1 >= 24) level = "低";
        else if (miss1 >= 10 && level === "高") level = "中";
      }
      out.m1 = { level: level, flags: flags };

      let flags2 = [], level2 = "高";
      if (m2Answers) {
        const seq2 = asList(m2Answers);
        const answered = seq2.filter((v) => v != null);
        const miss = seq2.length - answered.length;
        if (miss) {
          flags2.push("有 " + miss + " 题未作答");
          if (miss >= 20) level2 = "低";
          else if (miss >= 8 && level2 === "高") level2 = "中";
        }
      }
      const pairs = (m2 && m2.consistency) || [];
      if (pairs.length) {
        const bad = pairs.filter((p) => (p.status || "").indexOf("需复核") >= 0).length;
        const tot = pairs.length, same = tot - bad;
        if (same / tot < 0.6 && level2 === "高") level2 = "低";
        if (same / tot < 0.6) flags2.push(tot + " 对一致性题里只有 " + same + " 对同向，两可情境下的倾向偏不稳");
      }
      if (!m2Answers) {
        flags2.push("本次未留存逐题作答，缺失只能看汇总口径");
        if (level2 === "高") level2 = "中";
      }
      out.m2 = { level: level2, flags: flags2 };

      let flags3 = [], level3 = "高";
      if (m3Answers) {
        const miss = m3Answers.length - m3Answers.filter((v) => v != null).length;
        if (miss) {
          flags3.push("有 " + miss + " 题未作答");
          if (miss >= 10) level3 = "低";
          else if (miss >= 4 && level3 === "高") level3 = "中";
        }
      } else {
        flags3.push("本次未留存逐题作答，缺失与作答模式只能看汇总口径");
        if (level3 === "高") level3 = "中";
      }
      out.m3 = { level: level3, flags: flags3 };

      let speedNote = null;
      const dur = data.duration_ms;
      if (Number.isFinite(dur) && dur > 0) {
        const per = dur / 212000.0;
        if (per < 4) speedNote = "整卷平均 " + per.toFixed(1) + " 秒/题，节奏偏快";
        else if (per > 120) speedNote = "整卷平均 " + Math.round(per) + " 秒/题，节奏偏慢";
        else speedNote = "整卷平均 " + per.toFixed(1) + " 秒/题";
      }
      const order = { "高": 3, "中": 2, "低": 1 };
      const levels = [out.m1.level, out.m2.level, out.m3.level];
      const overall = levels.reduce((a, b) => (order[a] < order[b] ? a : b));
      out.overall = { level: overall, speed: speedNote, flags: out.m1.flags.concat(out.m2.flags, out.m3.flags) };
      return out;
    }

    /* ---------- 结果 JSON → 报告上下文（build_report_docx.build_context 同构） ---------- */
    function prepareContext(data) {
      const m1meta = {};
      ((((D.m1 && D.m1.meta && D.m1.meta.dimensions)) || [])).forEach((d) => { m1meta[d.key] = d; });
      const dims1 = (data.m1.dims || []).map((d) => {
        const meta = m1meta[d.key] || {};
        let brief = meta.definition || "";
        if (brief) brief = brief.split("——")[0].split("是")[0].slice(0, 38);
        if (!brief && meta.behavior) brief = meta.behavior.slice(0, 38);
        return { key: d.key, name: d.name, score: d.score, max: d.max, grade: d.grade,
          brief: brief, behavior: meta.behavior || "", _meta: meta };
      });
      const o = data.m1;
      const m1 = {
        dims: dims1,
        short: { name: (o.short || {}).name || "", grade: (o.short || {}).grade },
        short_text: (o.short || {}).name + "（" + (o.short || {}).grade + "）",
        score_text: "四维 " + dims1.map((d) => String(d.score)).join("、") + " 分",
      };

      const wmap = {};
      (D.eq.dimensions || []).forEach((d) => { wmap[d.key] = d; });
      const dims2 = (data.m2.dims || []).map((d) => {
        const w = wmap[d.key] || {};
        let read = !d.flag ? "在该维度上的情境反应与自我参照基本一致。" : "自我参照与情境作答差异偏大，此维结论待人工确认。";
        if (d.selfAvg != null) {
          read += "自我参照折算 " + d.selfAvg.toFixed(2) + " / 5.00，与情境折算 " + (d.avg != null ? d.avg : 0).toFixed(2) +
            " / 5.00 " + (!d.flag ? "差异 < 1.0" : "差异 ≥ 1.0") + "。";
        }
        return { key: d.key, name: d.name, outer_name: w.outer_name || "", weight: w.weight || 0,
          score: d.score, max: d.max, grade: d.grade, flag: d.flag, read: read };
      });
      const m2 = {
        dims: dims2, total: data.m2.total, grade: data.m2.grade,
        short_text: ((data.m2.short || {}).name || "") + "（" + ((data.m2.short || {}).grade || "") + "）",
        need_review: data.m2.needReview || [], consistency: data.m2.consistency || [],
      };

      const m3bank = (D.m3 && D.m3.dims) || {};
      const dims3 = (data.m3.dims || []).map((d) => {
        const dm = m3bank[d.key] || {};
        return { key: d.key, name: d.name, short: dm.short || d.name,
          correct: d.correct, total: d.total, rate: d.rate, pct: d.pct, t: d.t, grade: d.grade,
          what: dm.what || "", high: dm.high || "", low: dm.low || "", job: dm.job || "", risk: dm.risk || "" };
      });
      const short3 = dims3.slice().sort((a, b) => ord(a.grade) - ord(b.grade))[0];
      const m3 = { dims: dims3, total: data.m3.total, pct: data.m3.pct, t: data.m3.t, grade: data.m3.grade,
        short_text: short3 ? short3.name + "（" + short3.grade + "）" : "" };
      return { m1: m1, m2: m2, m3: m3, m1meta: m1meta };
    }

    /* ---------- 综合评估与追问（build_context 尾部 compose + compose_text 同构） ---------- */
    function bandComposite(v) {
      return v >= 4.5 ? "顶尖" : v >= 3.75 ? "优秀" : v >= 3.0 ? "良好" : v >= 2.25 ? "合格" : "待提升";
    }
    function baseCompose(m1, m2, m3) {
      const items = [
        { name: NAME_M1, grade: (m1.short || {}).grade },
        { name: NAME_M2, grade: m2.grade },
        { name: NAME_M3, grade: m3.grade },
      ];
      const avg = items.reduce((x, it) => x + ord(it.grade), 0) / 3;
      const cgrade = bandComposite(avg);
      const cshort = items.slice().sort((a, b) => ord(a.grade) - ord(b.grade))[0];
      const skew = items.filter((it) => ord(cgrade) - ord(it.grade) >= 2);
      return { grade: cgrade, score: Math.round(avg * 100) / 100,
        short: { name: cshort.name, grade: cshort.grade }, skew: skew,
        headline: "", paragraphs: [], questions: [] };
    }

    function composeText(ctx) {
      const m1 = ctx.m1, m2 = ctx.m2, m3 = ctx.m3, m1meta = ctx.m1meta || {};
      const compose = ctx.compose || baseCompose(m1, m2, m3);
      const grade = compose.grade, short = compose.short;
      const shortDim = m1.dims.slice().sort((a, b) => ord(a.grade) - ord(b.grade))[0];
      const sk = m1meta[shortDim.key] || {};
      const paras = [];
      paras.push("这位候选人三项的综合评估为" + grade + "。综合评估是三项等级（顶尖 5 / 优秀 4 / 良好 3 / 合格 2 / 待提升 1）等权平均后切的档，不产生总分，也不是任何形式的淘汰线。");
      paras.push("三类测试里最弱的是" + (short.name || "—") + "（" + (short.grade || "—") + "）；人格特质（工作方式倾向）不合成总档，最弱的一维在「" +
        shortDim.name + "」（" + shortDim.grade + "）——这一维更值得在面试里展开：" + (sk.behavior || "结合具体工作场景核实其真实工作顺序。"));
      paras.push("情景处理加权 " + m2.total.toFixed(2) + " / 5.00，等级" + m2.grade + "；" +
        ((m2.need_review || []).length ? "其中 " + m2.need_review.join("、") + " 需人工确认。" : "") +
        "逻辑分析能力落在参考分布第 " + m3.pct + " 百分位（T 分 " + m3.t + "），等级" + m3.grade + "。" +
        "逻辑分析能力与前两类预期弱相关，同涨同跌时应复核题目是否重叠，而不是直接加分。");
      paras.push("结论口径：以上只说明这位候选人在常规工作方式、具体管理情境、陌生问题推理三个切面上的表现倾向，不说明能力高低，不诊断性格，也不作录用评分项。录用决策应由简历、专业技能、面谈与工作样本等多源证据支撑；测评与面试冲突时以面试与工作样本为主，并记录冲突原因。");

      const qs = [];
      const basis = ((sk.behavior || "该维度判据").split("；")[0]).slice(0, 46);
      qs.push("围绕人格特质的短板「" + shortDim.name + "」：请他复盘一个最近三个月里，" + basis + "的具体场景——当时怎么做的、为什么这么排、代价是什么。");
      if ((m2.need_review || []).length) {
        qs.push("情景处理里 " + m2.need_review.join("、") + " 这几维，他的自我描述和现场选择不一致：请他给一个真实案例，看两种答案各自对应什么处境。");
      }
      const need = (m2.consistency || []).filter((c) => (c.status || "").indexOf("需复核") >= 0);
      if (need.length) {
        qs.push("情景处理的一致性检查里 " + need.map((c) => c.pair).join("、") + " 这几对同一情境选了不同方向：说明倾向在两可情境下不稳定，请他说明两种情境各自发生了什么。");
      }
      compose.skew.forEach((it) => {
        qs.push(it.name + " 这一项与综合评估相差 2 级以上（结构性偏科）：请他描述一次该维度明显拖后腿的经历，以及后来怎么调整。");
      });
      const m3low = m3.dims.slice().sort((a, b) => a.rate - b.rate).slice(0, 1)[0];
      if (m3low) {
        qs.push("逻辑分析能力里「" + m3low.name + "」正确率 " + m3low.rate + "%（八维中最低）：请他讲一道当时判断错的题，看他复盘时会不会改结论、还是为原答案找理由。");
      }
      qs.push("对照他简历上的最近一段经历，请他讲一个「本来可以更早发现、但没有」的问题，看他是先复盘事实还是先归因（对应人格特质的「关注重点」）。");
      compose.paragraphs = paras;
      compose.questions = qs;
      compose.headline = grade + "；最短板：" + (short.name || "—") + "（" + (short.grade || "—") + "）";
      return compose;
    }

    /* ---------- 内容块（report_blocks.build_blocks 同构） ---------- */
    function buildBlocks(data, ctx, narrative, cred, compose, profile) {
      const m1 = ctx.m1, m2 = ctx.m2, m3 = ctx.m3;
      const PN = narrative || {};
      const Pmap = PN.personality || {}, Smap = PN.situation || {}, Rmap = PN.reasoning || {};
      const O = {};
      (PN.overall || []).forEach((it) => { O[it.kind] = it; });
      const ov = (kind, fb) => { const it = O[kind]; return (it && it.text) ? it.text : fb; };

      const TP = RPROFILE.typeProfile(m1);
      const AN = RPROFILE.animalProfile(m1, m2, m3);
      const TB = RPROFILE.threeBand(m1, m2, m3);
      const TBSummary = TB.parts.map((x) => x.name + " " + x.band).join(" · ");
      const blocks = [];

      const prof = data.profile || {};
      const pf = (label, v) => [label, (v == null || v === "") ? "—" : v];
      blocks.push({ t: "cover", brand: "云上文旅集团 · 核心人才系列测试",
        title: (data.name || "候选人") + "的核心人才三联测试",
        sub: "性格特质 · 情绪特质 · 逻辑评价　|　施测人报告",
        fields: [
          pf("姓名", data.name), pf("年龄", prof.age), pf("性别", prof.sex),
          pf("毕业信息", [prof.school || "—", prof.major || "—"].join(" · ")),
          pf("职级", prof.level),
          pf("职位及岗位", [prof.position || "—", prof.unit || "—"].join(" · ")),
          pf("测评编号", data.code),
          ["身份标识", data.idLast4 ? "末 4 位 " + data.idLast4 : "—"],
          pf("报告日期", (data.date || "").slice(0, 10)),
          ["报告性质", "内部判读材料：只产出追问清单，不作录用评分项"],
          ["施测与归档", ORG],
        ],
        grade: TBSummary, score: null, band_note: TB.note, org: ORG,
        notice: "本报告由测评结果生成，只用于招聘环节的面谈追问；不作录用评分项，不设淘汰线，不构成心理或医学诊断。候选人如对结果有疑问，可在 5 个工作日内向集团人力资源部提出复核。" });

      blocks.push({ t: "h1", num: "1", text: "整体画像" });
      blocks.push({ t: "p", text: "这位候选人的整体画像是：" + RPROFILE.overallSentence(m1, m2, m3, TP, AN, TB) });
      blocks.push({ t: "h2", text: "1.1　形象类比" });
      blocks.push({ t: "callout", text: "如果要给这三种能力找一个形象参照，最接近的是「" + AN.name + "」：" + AN.why + "。本次三项的情况是" + AN.strength + "。" });
      blocks.push({ t: "note", text: "类比只用来帮施测人快速形成印象（取自行为倾向的三个关键轴：主动推动 / 等待配合、事实先行 / 趋势先导、定时收口 / 随机应对），不构成任何结论，也不是对候选人的评价性标签。" });
      blocks.push({ t: "h2", text: "1.2　本次作答的可信度" });
      const cred1 = cred.m1 || {};
      if (cred1.level === "低") {
        blocks.push({ t: "callout", text: "本次人格特质的作答可信度为「低」（" + (cred1.flags || []).join("；") + "）——下面这段画像只作参考，不能当成结论；建议先让候选人重测一遍再判读。" });
      }
      const rows = [];
      const prof1 = ((profile || {}).personality) || {};
      m1.dims.forEach((d) => {
        const nar = Pmap[d.key] || {};
        const pf1 = prof1[d.key] || {};
        let side;
        if (pf1.a_cnt == null || pf1.b_cnt == null) side = nar.pole_label || "—";
        else if (Math.abs(pf1.a_cnt - pf1.b_cnt) <= 3) side = "两极相当（" + pf1.a_cnt + " : " + pf1.b_cnt + "）";
        else side = (nar.pole_label || "—") + "（" + pf1.a_cnt + " : " + pf1.b_cnt + "）";
        rows.push([d.name, d.score + " / " + d.max, RPROFILE.dimBand3(d.score, d.max), side, nar.text || d.brief || ""]);
      });
      const crows = [["m1", NAME_M1], ["m2", NAME_M2], ["m3", NAME_M3]].map(([key, label]) => {
        const c = cred[key] || {};
        return [label, c.level || "—", (c.flags || []).join("；") || "无异常信号"];
      });
      blocks.push({ t: "table", header: ["部分", "可信度", "依据"], rows: crows, align: ["l", "c", "l"] });
      blocks.push({ t: "note", text: "可信度回答的是「这份结果能不能信」，不是「这个人行不行」。判据：同侧作答（连续选同一端的长度与偏向比例）、未作答比例、成对题的一致性、以及整卷节奏" +
        (((cred.overall || {}).speed) ? "（" + cred.overall.speed + "）" : "") + "。可信度偏低时，下面的分数只作参考，面试取证优先。" });

      blocks.push({ t: "h1", num: "2", text: "分项" });
      blocks.push({ t: "h2", text: "2.1　" + NAME_M1 + " · 类型归类" });
      blocks.push({ t: "callout", text: (TP.type_name || "未定型") + "（" + TP.code + "）· " + TP.type_desc });
      blocks.push({ t: "p", text: "按四个行为轴归类：" + TP.summary + "。" });
      TP.axes.forEach((ax) => {
        blocks.push({ t: "p", text: ax.name + "（" + ax.axis + " 轴）：" + ax.side_label + "（" + ax.score + " / " + ax.max + "，" + RPROFILE.dimBand3(ax.score, ax.max) + "）——" + ax.desc + "。" });
      });
      blocks.push({ t: "note", text: "归类口径：每个行为轴按「更有效的一端」在 24 题中的命中数归边，严格过半（13 题及以上）算偏这一侧，否则算偏另一侧，四轴拼成四字母。这是基于本测评四维行为倾向的类型化归类，与通行的心理类型量表不同：轴的含义是工作方式上的行为倾向，不是心理类型，结果不可对外当作心理类型判定使用。" });
      blocks.push({ t: "h2", text: "2.1.1　对应详情" });
      blocks.push({ t: "table", header: ["维度", "得分", "等级", "两极倾向（极a : 极b）", "工作方式上的表现"], rows: rows, align: ["l", "r", "c", "l", "l"] });
      blocks.push({ t: "note", text: "「两极倾向」由 96 道两极题的逐题选择统计得出（极a : 极b，两极相当时直接标出比值），描述的是工作方式上的倾向，不是性格类型，也不是诊断结论。极的归口用逐题映射表 data/m1_pole_map.json（题库里 a/b 两列正反混排，不能直接按 a/b 列的占比算）。" });
      const weak1 = m1.dims.slice().sort((a, b) => a.score / (a.max || 1) - b.score / (b.max || 1))[0];
      blocks.push({ t: "p", text: "口径：每一题是一道两极对比，两端都是行为频率陈述；每题锚定「更有效的一端」计 1 分，每维 24 题、0–24 分，各维独立、没有总档。本部分采用绝对锚点切档，内部样本到量后再校准参照分布。最弱的一维是 " + weak1.name + "（" + RPROFILE.dimBand3(weak1.score, weak1.max) + "）。" });
      blocks.push({ t: "cred", level: (cred.m1 || {}).level || "—", text: ((cred.m1 || {}).flags || []).join("；") || "无异常信号" });

      /* 票 #81：删掉未进词汇表的「情绪特质」括注，口径 23 对外只留类目名（与 Python 侧逐字同源） */
      blocks.push({ t: "h2", text: "2.2　" + NAME_M2 + "分析" });
      blocks.push({ t: "p", text: "这一部分看候选人在具体管理情境中的反应方式：压力下稳不稳、冲突怎么处理、关系经营与同理沟通如何，共八个情境维度。" });
      let strong = m2.dims.filter((d) => ["顶尖", "优秀"].indexOf(d.grade) >= 0).sort((a, b) => ord(b.grade) - ord(a.grade)).slice(0, 3);
      let weak = m2.dims.filter((d) => ["合格", "待提升"].indexOf(d.grade) >= 0).sort((a, b) => ord(a.grade) - ord(b.grade)).slice(0, 3);
      if (!strong.length) strong = m2.dims.slice().sort((a, b) => ord(b.grade) - ord(a.grade)).slice(0, 2);
      if (!weak.length) weak = m2.dims.slice().sort((a, b) => ord(a.grade) - ord(b.grade)).slice(0, 2);
      const TR = (P.m2_traits || (profiles && profiles.m2_traits) || {});
      const traitLine = (dim, field) => { const tt = (TR[dim.key] || {})[field] || dim.read || ""; return dim.name + "——" + tt; };
      blocks.push({ t: "kv", rows: [
        ["善于什么", strong.map((d) => traitLine(d, "strong")).join("；")],
        ["不善于什么", weak.map((d) => traitLine(d, "weak")).join("；")],
      ] });
      const m2part = TB.parts.filter((x) => x.name === "情绪特质")[0];
      blocks.push({ t: "p", text: "总结：" + m2part.text + "（占满分 " + f1(m2part.pct) + "%，" + m2part.band + "）。" });
      blocks.push({ t: "h2", text: "2.2.1　对应详情" });
      const rows2 = m2.dims.map((d) => {
        const nar = Smap[d.key] || {};
        return [d.name, d.outer_name, d.weight + "%", d.score + " / " + d.max, RPROFILE.dimBand3(d.score, d.max), nar.text || d.read || ""];
      });
      blocks.push({ t: "table", header: ["维度", "归属", "权重", "得分", "等级", "判读"], rows: rows2, align: ["l", "l", "r", "r", "c", "l"] });
      blocks.push({ t: "p", text: "口径：八个管理情境维度上的行为反应，每维 6 道计分题（每题满分 2 分）、折算成 0–12 分；模块总分按权重加权到 0–5.00。自评折算与情境折算差异 ≥ 1.0 的维度标为「需复核」。" });
      if ((m2.consistency || []).length) {
        blocks.push({ t: "table", header: ["题对", "判定", "作答"],
          rows: m2.consistency.map((c) => [c.pair, c.status, c.detail]), align: ["l", "l", "l"],
          caption: "一致性检查（同一致情境的两种问法是否指向同一倾向；不计入任何维度分）" });
      }
      if ((m2.need_review || []).length) {
        blocks.push({ t: "callout", text: "需复核：" + m2.need_review.join("、") + " —— 自我参照与情境作答差异较大，按「需结合真实经历再确认」处理，不直接采信任一方。" });
      }
      blocks.push({ t: "cred", level: (cred.m2 || {}).level || "—", text: ((cred.m2 || {}).flags || []).join("；") || "无异常信号" });

      /* 票 #81：删掉未进词汇表的「逻辑评价」括注（与 Python 侧逐字同源） */
      blocks.push({ t: "h2", text: "2.3　" + NAME_M3 + "总结" });
      blocks.push({ t: "p", text: "这一部分看候选人面对陌生问题时的推理与判断：从给定条件推结论、从现象找规律、读懂数字口径，到风险与决策偏差识别，共八个推理维度；它不是标准化智力测验，也不与另两部分互相替代。" });
      let strong3 = m3.dims.filter((d) => ["顶尖", "优秀"].indexOf(d.grade) >= 0).sort((a, b) => ord(b.grade) - ord(a.grade)).slice(0, 3);
      let weak3 = m3.dims.filter((d) => ["合格", "待提升"].indexOf(d.grade) >= 0).sort((a, b) => ord(a.grade) - ord(b.grade)).slice(0, 3);
      if (!strong3.length) strong3 = m3.dims.slice().sort((a, b) => ord(b.grade) - ord(a.grade)).slice(0, 2);
      if (!weak3.length) weak3 = m3.dims.slice().sort((a, b) => ord(a.grade) - ord(b.grade)).slice(0, 2);
      const logLine = (d, field) => d.name + "——" + (d[field] || "");
      blocks.push({ t: "kv", rows: [
        ["善于", strong3.map((d) => logLine(d, "high")).join("；")],
        ["不善于", weak3.map((d) => logLine(d, "low")).join("；")],
      ] });
      blocks.push({ t: "h2", text: "2.3.1　对应详情" });
      const rows3 = m3.dims.map((d) => {
        const nar = Rmap[d.key] || {};
        let txt = nar.text || "";
        if (!txt) txt = d.high || "";
        return [d.name, d.correct + " / " + d.total, d.rate + "%", "P" + d.pct, RPROFILE.band3(d.rate), txt];
      });
      blocks.push({ t: "table", header: ["维度", "正确 / 总题", "正确率", "百分位", "等级", "判读"], rows: rows3, align: ["l", "r", "r", "r", "c", "l"] });
      blocks.push({ t: "img", path: null,
        radar_dims: m3.dims.map((d) => ({ key: d.key, short: d.short || d.name, name: d.name, pct: d.pct })),
        caption: NAME_M3 + " 八维参考分布百分位（雷达几何刻度 = 百分位，与上表同口径；金色虚线 = 中位 P50，灰色虚线 = P25）" });
      blocks.push({ t: "p", text: "口径：难度加权答对 " + m3.total + " 分，落在内置参考分布的第 " + m3.pct + " 百分位、T 分 " + m3.t + "。百分位基于按题目难度加权的理论模型换算，不是商业常模，也不等同任何标准化智力测验；档位以百分位为准。" });
      blocks.push({ t: "cred", level: (cred.m3 || {}).level || "—", text: ((cred.m3 || {}).flags || []).join("；") || "无异常信号" });

      blocks.push({ t: "h1", num: "3.0", text: "人才综合素质与潜力" });
      blocks.push({ t: "h2", text: "3.0.1　三项总览" });
      blocks.push({ t: "table", header: ["测试", "核心特征", "得分（占满分 · 档位）"],
        rows: TB.parts.map((x) => [x.name, x.text, x.score_text + " · " + f1(x.pct) + "% · " + x.band]), align: ["l", "l", "r"] });
      blocks.push({ t: "h2", text: "3.0.2　提升方向" });
      if (TB.gapToTop <= 0) {
        blocks.push({ t: "callout", text: "三项都在突出水平，没有明显短板；接下来的成长更多来自经验与场景复杂度，而不是补哪一项。" });
      } else {
        blocks.push({ t: "callout", text: "最值得补的是" + TB.weakest.name + "（当前 " + f1(TB.weakest.pct) + "%，" + TB.weakest.band + "）；补到 85% 还差 " + f1(TB.gapToTop) + " 个百分点。" });
      }
      blocks.push({ t: "p", text: "提升方向只看最弱的那一项，不做跨项合成：这一项补上来，最明显的短板就消失了，其余两项维持现状即可。" });
      blocks.push({ t: "h2", text: "3.0.3　适合的方向" });
      blocks.push({ t: "p", text: ov("fit", "综合三类测试的表现，下面给出方向性建议；具体岗位还需结合专业技能与工作样本。") });
      blocks.push({ t: "p", text: ov("potential", "潜力判断以现有分数与短板分布为依据，成长空间主要取决于短板维度。") });
      blocks.push({ t: "h2", text: "3.0.4　面谈追问清单" });
      blocks.push({ t: "note", text: "测评只产出追问清单，不作录用评分项。下列问题按短板与复核项生成，供面谈现场取证：" });
      blocks.push({ t: "ol", items: compose.questions || [] });
      blocks.push({ t: "h2", text: "3.0.5　使用边界" });
      blocks.push({ t: "kv", rows: [
        ["结果性质", "只产出追问清单，不作录用评分项；同一岗位对所有候选人使用同一套题、同一权重、同一阈值。"],
        ["与面试冲突时", "以面试与工作样本为主，并记录冲突原因。"],
        ["不是淘汰线", "本产品不设淘汰线；三档档位与单项等级同样不产生淘汰动作。"],
        ["不做什么", "不测量性格，不测量智力，不属于临床心理评估，不对心理健康状况作判断。"],
        ["谁能看到", "集团人力资源部 2–3 名工作人员（含用人部门负责人）在施测工作台查看并讨论，用于招聘环节的评估；自测期工作台入口暂未设访问鉴权，该暴露面已按票 #36 记录在案。"],
        ["留存与复核", "交卷记录（含逐题作答与三项分数）留存集团人力资源部系统，测试数据保留不超过 1 年，到期删除或匿名化；查询、更正、删除由集团人力资源部受理，候选人可在提交后 5 个工作日内提出复核。"],
        ["施测与归档单位", ORG],
      ] });

      blocks.push({ t: "h1", num: "附录", text: "结论口径与使用边界" });
      blocks.push({ t: "p", text: ov("conclusion", "以上只说明这位候选人在常规工作方式、具体管理情境、陌生问题推理三个切面上的表现倾向，不说明能力高低，不诊断性格，也不作录用评分项。") });
      blocks.push({ t: "p", text: ov("boundary", "录用决策应由简历、专业技能、面谈与工作样本等多源证据支撑；测评与面试冲突时以面试与工作样本为主。") });
      blocks.push({ t: "p", text: ov("method", "本报告的三类测试互不替代：" + NAME_M1 + "看工作方式上的倾向，" + NAME_M2 + "看在具体管理情境里的反应，" + NAME_M3 + "看陌生问题上的推理与判断。三者同涨同跌时需要复核题目是否重叠，而不是直接加分。") });
      blocks.push({ t: "kv", rows: [
        ["报告名称", (data.name || "候选人") + "的核心人才三联测试"],
        ["施测与归档单位", ORG],
        ["报告日期", (data.date || "").slice(0, 10) || "—"],
        ["测评编号", data.code || "—"],
      ] });
      return blocks;
    }

    /* 报告页画像（report_narrative.build_profile 同构）。
     * 无 m1_raw（产品 resultObj 的 9 字段路径）时极向计数为 0、pole 默认 a，
     * build_blocks 因此显示「两极相当（0 : 0）」——与 Python 同路径一致。 */
    function bandOfRatio(v, lo, hi) {
      const r = hi > lo ? (v - lo) / (hi - lo) * 100 : 0;
      return r >= 85 ? "突出" : r >= 70 ? "常规" : "偏弱";
    }
    function buildProfile(data, ctx, m1Raw) {
      const m1 = ctx.m1, m2 = ctx.m2, m3 = ctx.m3;
      const prof = {
        personality: {}, situation: {}, reasoning: {},
        overall: {
          grade: (ctx.compose && ctx.compose.grade) || null,
          kinds: ["profile", "fit", "potential", "strength", "caution", "conclusion", "boundary", "method"],
        },
      };
      // 极向：有 m1_raw + m1_pole_map 时按映射算；否则 a_cnt=b_cnt=0（pole=a）。
      let poleMap = {};
      try {
        poleMap = ((D.m1 && D.m1.poleMap) || {});
      } catch (e) { poleMap = {}; }
      const order = ((D.m1 && D.m1.items) || []).map((it) => it.id);
      const idxOf = {};
      order.forEach((id, i) => { idxOf[id] = i; });
      const dimItems = {};
      ((D.m1 && D.m1.items) || []).forEach((it) => {
        (dimItems[it.dim] = dimItems[it.dim] || []).push(it);
      });
      m1.dims.forEach((d) => {
        let aCnt = 0, bCnt = 0;
        if (m1Raw) {
          (dimItems[d.key] || []).forEach((it) => {
            const i = idxOf[it.id];
            if (i == null || i >= m1Raw.length) return;
            const v = m1Raw[i];
            if (v == null) return;
            const pmv = poleMap[it.id];
            if (pmv != null) {
              if (v === Number(pmv)) aCnt++; else bCnt++;
            } else {
              const ansA = (v === 0);
              const anchorA = String(it.anchor || "a").toLowerCase() !== "b";
              if (ansA === anchorA) aCnt++; else bCnt++;
            }
          });
        }
        const total = aCnt + bCnt;
        const pole = (total === 0 || aCnt >= bCnt) ? "a" : "b";
        prof.personality[d.key] = { dimension: d.key, score: d.score, max: d.max || 24,
          band: d.grade, pole: pole, a_cnt: aCnt, b_cnt: bCnt, pole_src: m1Raw ? "map" : "map",
          aligned: total ? Math.round(aCnt / total * 1000) / 1000 : null };
      });
      const keyOfName = {};
      (D.eq.dimensions || []).forEach((x) => { if (x.name) keyOfName[x.name] = x.key; });
      m2.dims.forEach((d) => {
        const k = d.key || keyOfName[d.name] || d.name;
        prof.situation[k] = { dimension: k, name: d.name, score: d.score, max: d.max || 12,
          band: d.grade, flag: !!d.flag };
      });
      m3.dims.forEach((d) => {
        const rate = d.rate || 0;
        prof.reasoning[d.key] = { dimension: d.key, rate: rate, correct: d.correct, total: d.total,
          band: d.grade || bandOfRatio(rate, 0, 100) };
      });
      return prof;
    }

    return {
      prepareContext: prepareContext, composeText: composeText,
      credibility: credibility, matchLocal: matchLocal,
      buildBlocks: buildBlocks, buildProfile: buildProfile,
      constants: { NAME_M1: NAME_M1, NAME_M2: NAME_M2, NAME_M3: NAME_M3, ORG: ORG, ORDER: ORDER },
    };
});
