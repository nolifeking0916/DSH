# -*- coding: utf-8 -*-
"""生成**临时补答页**：只出某人第三项里没作答的题位，提交后由服务端合并并重算第三项成绩。

为什么要有它（2026-10-26 · 票 #26 / #52）：
  某份作答的第三项有题位未作答（页面 bug 或候选人跳答），第一、二项完整。
  整份重做要 70 分钟；本页只把那批空题补上，服务端**只填空位**、**不动其它任何字段**。

用法：
  python3 cloud/build_patch_page.py --dump <云端导出的 dump.json> --code <测评编号> \
      --out cloud/publish/patch/index.html

依赖：云端 dump（public.responses 一行，m3_answers 必���） + data/logic_m3.json（第三项题库）。
产出：单文件 HTML（零外链）—— 题面内联、样式内联、提交直接打云函数。
⚠ 临时页用完即删（它没有鉴权，页面地址 + 编号即门槛）。
"""
import argparse
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BANK = os.path.join(ROOT, "data", "logic_m3.json")
API = "https://uu-one-d4gc4ot78a702cb70-1257197409.ap-shanghai.app.tcloudbase.com/api/assessment"
DIMS = {"DED": "演绎推理", "IND": "归纳推理与模式识别", "NUM": "数量推理与数据素养",
        "CON": "约束分析与约束求解", "SPA": "图形与空间推理", "CRI": "组合与逻辑组合",
        "PLN": "计划与执行推理", "RSK": "风险与不确定性判断"}


def read_dump(path):
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    rows = raw.get("rows") or (raw.get("data") or {}).get("rows") or raw
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", required=True)
    ap.add_argument("--code", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--title", default="第三项补答")
    ap.add_argument("--api", default=API, help="交卷接口（测试时指向本地假服务器）")
    a = ap.parse_args()

    rows = read_dump(a.dump)
    row = next((r for r in rows if r.get("code") == a.code), None)
    if not row:
        raise SystemExit("dump 里没有 %s" % a.code)
    m3 = row.get("m3_answers")
    if isinstance(m3, str):
        m3 = json.loads(m3)
    if not isinstance(m3, list):
        raise SystemExit("m3_answers 不是数组")
    bank = json.load(open(BANK, encoding="utf-8"))["questions"]
    n = min(len(m3), len(bank))
    empty = [i for i in range(n) if m3[i] is None]
    if not empty:
        raise SystemExit("这一份第三项没有空位，不用补")

    qs = []
    for i in empty:
        q = bank[i]
        qs.append({"slot": i, "id": q["id"], "dim": DIMS.get(q.get("dim"), q.get("dim")),
                   "stem": q.get("stem", ""), "grid": q.get("grid"),
                   "opts": q.get("options") or []})

    data = json.dumps({"code": a.code, "name": row.get("respondent_name") or "",
                       "api": a.api + ("&" if "?" in a.api else "?") + "action=patch_m3", "qs": qs}, ensure_ascii=False)
    html = TEMPLATE.replace("/*__DATA__*/", data).replace("__TITLE__", a.title)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(html)
    print("补答页：%s（%d 题 · 题位 %s）" % (a.out, len(qs), ",".join(str(i) for i in empty)))
    print("交卷接口：%s（只填空位）" % (a.api + "?action=patch_m3"))


TEMPLATE = r"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>__TITLE__</title>
<style>
:root{
  --green:#1E4634; --green-2:#2A5C46; --gold:#6E5B36; --gold-2:#B08D57;
  --cream:#F5F0E4; --paper:#FBF8F1; --ink:#22322B; --muted:#5C6A60;
  --line:#D9D2C2; --sp-1:6px; --sp-2:12px; --sp-3:18px; --sp-4:26px;
  --fs-1:13px; --fs-2:15px; --fs-3:17px; --fs-4:20px; --fs-5:24px; --fs-6:28px;
  --r:12px;
}
*{box-sizing:border-box}
body{margin:0;background:var(--cream);color:var(--ink);
  font:400 var(--fs-2)/1.65 -apple-system,BlinkMacSystemFont,"PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;
  -webkit-text-size-adjust:100%}
.topbar{background:var(--green);color:var(--cream);padding:var(--sp-3) 0}
.wrap{max-width:720px;margin:0 auto;padding:0 var(--sp-3)}
.brand{font-size:var(--fs-1);letter-spacing:.12em;opacity:.75}
.title{font-size:var(--fs-5);font-weight:700;margin:var(--sp-1) 0 0}
.meta{font-size:var(--fs-1);opacity:.85;margin-top:var(--sp-1)}
.pbar{height:5px;background:rgba(245,240,228,.22);border-radius:99px;margin-top:var(--sp-2);overflow:hidden}
.pbar i{display:block;height:100%;width:0;background:var(--gold-2);transition:width .2s}
.sheet{background:var(--paper);border-radius:var(--r);padding:var(--sp-4) var(--sp-3);
  box-shadow:0 1px 0 rgba(0,0,0,.05);margin:var(--sp-3) 0 var(--sp-4)}
.note{background:#EEF3EE;border-left:3px solid var(--green-2);border-radius:6px;
  padding:var(--sp-2) var(--sp-3);font-size:var(--fs-1);color:var(--muted);margin-bottom:var(--sp-3)}
.note b{color:var(--ink)}
.q{padding:var(--sp-3) 0;border-top:1px solid var(--line)}
.q:first-of-type{border-top:0}
.qh{display:flex;gap:var(--sp-2);align-items:baseline;margin-bottom:var(--sp-2)}
.qn{font-size:var(--fs-1);color:var(--muted);letter-spacing:.04em}
.qstem{font-size:var(--fs-3);font-weight:600;line-height:1.6;margin:0 0 var(--sp-2);overflow-wrap:anywhere}
.grid{font-family:ui-monospace,Menlo,monospace;font-size:var(--fs-2);line-height:1.5;
  background:#F1EEE5;border-radius:8px;padding:var(--sp-2);margin:0 0 var(--sp-2);
  white-space:pre;overflow-x:auto}
.opts{display:flex;flex-direction:column;gap:var(--sp-1)}
.opt{display:flex;gap:var(--sp-2);align-items:flex-start;width:100%;text-align:left;min-width:0;
  background:#fff;border:1px solid var(--line);border-radius:10px;padding:10px 12px;
  font:inherit;color:var(--ink);cursor:pointer}
.opt:hover{border-color:var(--green-2)}
.opt[aria-pressed="true"]{border-color:var(--green);background:#EFF4F0;box-shadow:inset 0 0 0 1px var(--green)}
.opt .k{flex:0 0 22px;height:22px;flex-shrink:0;background:#EDE8DB;color:var(--muted);
  font-size:12px;display:flex;align-items:center;justify-content:center;font-weight:700}
.opt[aria-pressed="true"] .k{background:var(--green);color:var(--cream)}
.sticky{position:sticky;bottom:0;background:linear-gradient(180deg,rgba(245,240,228,0),var(--cream) 28%);
  padding:var(--sp-3) 0 calc(var(--sp-3) + env(safe-area-inset-bottom))}
.btn{display:block;width:100%;border:0;border-radius:10px;padding:14px 16px;font:600 var(--fs-3)/1.4 inherit;
  background:var(--green);color:var(--cream);cursor:pointer}
.btn[disabled]{background:#C9C4B6;cursor:not-allowed}
.btn.ghost{background:transparent;color:var(--muted);border:1px solid var(--line);margin-top:var(--sp-2)}
.status{margin-top:var(--sp-2);font-size:var(--fs-1);color:var(--muted);text-align:center}
.status.err{color:#8C2F1E}
.status.ok{color:var(--green-2);font-weight:600}
.foot{font-size:var(--fs-1);color:var(--muted);line-height:1.6}
.foot hr{border:0;border-top:1px solid var(--line);margin:var(--sp-3) 0}
</style></head><body>
<div class="topbar"><div class="wrap">
  <div class="brand">云上文旅集团 · 核心人才系列测试</div>
  <div class="title" id="ttl">__TITLE__</div>
  <div class="meta" id="meta"></div>
  <div class="pbar"><i id="bar"></i></div>
</div></div>
<div class="wrap">
  <div class="sheet">
    <div class="note">
      <b>这是第三项的补答页。</b>你上次作答时，第三项有 <b id="nq"></b> 道题没有作答记录（第一项、第二项**不用重做**，那两项的成绩不受影响）。
      请把下面这 <b id="nq2"></b> 道题答完并提交；提交后系统会把这批题**合并**进你原来那份作答，并重算第三项成绩。
      <br>本页面是临时页面，**用完即删**；如需更正或删除本次作答，请联系集团人力资源部。
    </div>
    <div id="restore" style="display:none;background:#EFF4F0;border:1px solid #C9D8CE;border-radius:10px;padding:var(--sp-2) var(--sp-3);margin-bottom:var(--sp-3)">
      <div style="font-weight:600;margin-bottom:4px">检测到这台设备上还留着这次作答的完整记录</div>
      <div style="font-size:var(--fs-1);color:var(--muted);margin-bottom:8px">第三项的 40 道题你当时**都答了**（服务器收到的只是其中 22 道被产品丢弃的答案）。
        点下面的按钮，系统会**直接把这台设备上保存的答案**补进去，你不用再答一遍。</div>
      <button class="btn" id="restoreBtn">从本机恢复第三项答案</button>
    </div>
    <div id="qs"></div>
    <div class="sticky">
      <button class="btn" id="submit" disabled>提交补答</button>
      <button class="btn ghost" id="again" style="display:none">返回修改</button>
      <div class="status" id="st"></div>
    </div>
    <div class="foot"><hr>
      本次补答只写入第三项的空白题位，**已作答的题目不会被改动**。第三项共 40 道题，本次需补答的题位见每题标题。
    </div>
  </div>
</div>
<script>
const D = /*__DATA__*/;
const ans = {};
document.getElementById('ttl').textContent = D.name ? ('第三项补答 · ' + D.name) : '第三项补答';
document.getElementById('meta').textContent = '测评编号 ' + D.code + ' · 需补答 ' + D.qs.length + ' 道题';
document.getElementById('nq').textContent = D.qs.length;
document.getElementById('nq2').textContent = D.qs.length;
const box = document.getElementById('qs');
D.qs.forEach((q, n) => {
  const wrap = document.createElement('div');
  wrap.className = 'q';
  let h = '<div class="qh"><span class="qn">第 ' + (n+1) + ' / ' + D.qs.length + ' 道 · 原第 ' + (q.slot+1) + ' 题位 · ' + q.id + '（' + q.dim + '）</span></div>';
  h += '<p class="qstem">' + q.stem.replace(/[<>&]/g, c => ({'<':'&lt;','>':'&gt;','&':'&amp;'}[c])) + '</p>';
  if (q.grid) h += '<pre class="grid">' + (Array.isArray(q.grid)? q.grid.join('\n') : q.grid) + '</pre>';
  h += '<div class="opts" id="o' + n + '">';
  q.opts.forEach((o, k) => {
    h += '<button type="button" class="opt" data-q="' + n + '" data-v="' + k + '" aria-pressed="false">' +
         '<span class="k">' + 'ABCD'[k] + '</span><span>' + o + '</span></button>';
  });
  h += '</div>';
  wrap.innerHTML = h;
  box.appendChild(wrap);
});
box.addEventListener('click', e => {
  const b = e.target.closest('.opt'); if (!b) return;
  const q = +b.dataset.q, v = +b.dataset.v;
  ans[D.qs[q].slot] = v;
  document.querySelectorAll('#o' + q + ' .opt').forEach(x => x.setAttribute('aria-pressed', String(x === b)));
  const n = Object.keys(ans).length;
  document.getElementById('bar').style.width = (n / D.qs.length * 100) + '%';
  document.getElementById('submit').disabled = n < D.qs.length;
  document.getElementById('st').textContent = n < D.qs.length ? ('已答 ' + n + ' / ' + D.qs.length) : '已答完，可以提交';
});
/* ---- 从本机恢复（2026-10-26）：她这台设备上其实存着完整的 40 题 ----
   根因：客户端 normalize 只认 0/1，把第三项选 C/D 的答案丢成了 null（已修）。
   ⇒ 库里那份的 22 个 null，在**她本机**其实是完整答案。 */
const LS = 'assessment_core_v1';
let localM3 = null;
try {
  const raw = localStorage.getItem(LS);
  if (raw) {
    const s2 = JSON.parse(raw);
    if (s2 && s2.code === D.code && s2.a && Array.isArray(s2.a.m3)) {
      const filled = s2.a.m3.filter(v => v !== null && v !== undefined).length;
      const hasCD = s2.a.m3.some(v => v === 2 || v === 3);
      if (filled >= D.qs.length && hasCD) localM3 = s2.a.m3;
    }
  }
} catch (e) { localM3 = null; }
if (localM3) {
  document.getElementById('restore').style.display = 'block';
  document.getElementById('restoreBtn').addEventListener('click', () => {
    const st = document.getElementById('st');
    const btn = document.getElementById('restoreBtn');
    btn.disabled = true; st.className = 'status'; st.textContent = '正在从本机恢复…';
    const payload = {};
    localM3.forEach((v, i) => { if (v !== null && v !== undefined) payload[String(i)] = v; });
    fetch(D.api, { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code: D.code, m3_answers: payload }) })
     .then(r => r.text().then(t => ({ ok: r.ok, j: (function(){try{return JSON.parse(t)}catch(e){return {raw:t}}})() })))
     .then(res => {
       const j = res.j || {};
       if (res.ok && j.ok) {
         st.className = 'status ok';
         st.textContent = '已从本机恢复：服务器合并 ' + (j.filled||[]).length + ' 道题，第三项成绩已重算' +
           (j.remaining_empty ? ('（仍有 ' + j.remaining_empty + ' 道空题）') : '（第三项已答完）') +
           (j.m3_grade ? ('，第三项等级：' + j.m3_grade) : '') + '。本临时页面现在可以关闭。';
         document.getElementById('restore').style.display = 'none';
         document.getElementById('bar').style.width = '100%';
       } else {
         st.className = 'status err';
         st.textContent = '恢复未成功：' + (j.error || '未知错误') + '（请改用下方逐题作答）';
         btn.disabled = false;
       }
     })
     .catch(e => { st.className = 'status err'; st.textContent = '网络异常：' + e + '（请改用下方逐题作答）'; btn.disabled = false; });
  });
}
document.getElementById('submit').addEventListener('click', () => {
  const st = document.getElementById('st');
  if (Object.keys(ans).length < D.qs.length) { st.className='status err'; st.textContent='还有题没答'; return; }
  const btn = document.getElementById('submit'); btn.disabled = true; st.className='status'; st.textContent='提交中…';
  fetch(D.api, { method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({ code: D.code, m3_answers: ans }) })
   .then(r => r.text().then(t => ({ ok: r.ok, j: (function(){try{return JSON.parse(t)}catch(e){return {raw:t}}})() })))
   .then(res => {
     const j = res.j || {};
     if (res.ok && j.ok) {
       st.className='status ok';
       st.textContent = '已提交：合并 ' + (j.filled||[]).length + ' 道题，第三项成绩已重算' +
         (j.remaining_empty ? ('（仍有 ' + j.remaining_empty + ' 道空题）') : '（第三项已答完）') +
         (j.m3_grade ? ('，第三项等级：' + j.m3_grade) : '') + '。本临时页面现在可以关闭。';
       document.getElementById('again').style.display = 'none';
       document.getElementById('bar').style.width = '100%';
     } else {
       st.className='status err';
       st.textContent = '提交未成功：' + (j.error || ('HTTP ' + (res.j && res.j.raw ? res.j.raw.slice(0,80) : '未知')));
       btn.disabled = false;
     }
   })
   .catch(e => { st.className='status err'; st.textContent = '网络异常：' + e; btn.disabled = false; });
});
document.getElementById('again').addEventListener('click', () => location.reload());
</script>
</body></html>
"""

if __name__ == "__main__":
    main()
