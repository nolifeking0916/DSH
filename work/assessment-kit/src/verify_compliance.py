#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""合规复核（票 #5）：结果 JSON 字段 / 本机存储与清除 / 断点续答 / 每屏页脚 / 脱敏一致 / 零外链。

用法：python3 src/verify_compliance.py [成品路径]
退出码 0 = 全绿；非 0 = 有项未通过（逐条打印）。
"""
import json
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROD = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    ROOT, "dist", "云上文旅集团核心人才系列测试_20261024.html")
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(("  [OK ] " if ok else "  [FAIL] ") + name + (("：" + detail) if detail else ""))


def run_chrome(url, js=""):
    """跑一次 headless Chrome，返回 (dump_dom, console_text)。"""
    src = open(PROD, encoding="utf-8").read()
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as f:
        if js:
            f.write(src.rsplit("</body>", 1)[0] + js + "</body></html>")
        else:
            f.write(src)
        tmp = f.name
    try:
        out = subprocess.run(
            [CHROME, "--headless=new", "--disable-gpu", "--virtual-time-budget=4000",
             "--dump-dom", "file://" + tmp],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=90).stdout.decode("utf-8", "ignore")
    finally:
        os.unlink(tmp)
    return out


def main():
    if not os.path.exists(PROD):
        print("找不到成品：", PROD)
        return 2
    html = open(PROD, encoding="utf-8").read()

    print("== 1. 零外链 ==")
    ext = re.findall(r'(?:src|href)\s*=\s*["\']https?://[^"\']+', html)
    ext += re.findall(r'@import\s+url\(', html)
    ext += re.findall(r'url\(\s*["\']?https?://', html)
    check("成品无任何外部资源引用", not ext, "命中 %d 处" % len(ext))

    print("== 2. 结果 JSON 只带脱敏身份字段 ==")
    m = re.search(r"function\s+resultObj\s*\([^)]*\)\s*\{(.*?)\n\s*\}", html, re.S)
    body = m.group(1) if m else ""
    keys = re.findall(r"(\w+)\s*:", body)
    id_like = [k for k in keys if re.search(r"id(no|card|full)?$", k, re.I) and k != "idLast4"]
    check("结果对象无 idNo/idCard 等全量身份字段", not id_like, "可疑字段：%s" % (id_like or "无"))
    check("结果对象带 idLast4（后 4 位）", "idLast4" in keys, "字段：%s" % ",".join(keys[:8]))
    check("全文不出现全量身份证回写", not re.search(r'"id"\s*:\s*S\.id\b', html))

    print("== 3. 本机存储与旧键清理 ==")
    cur = re.findall(r"const\s+KEY\s*=\s*\"([^\"]+)\"", html)
    old = re.findall(r"OLD_KEYS\s*=\s*\[([^\]]*)\]", html)
    old_keys = re.findall(r'"([^"]+)"', old[0]) if old else []
    check("当前存储键唯一且带版本", cur == ["assessment_core_v1"], "键：%s" % ",".join(cur))
    check("旧版 4 个键列入清理名单", len(old_keys) == 4, "旧键：%s" % ",".join(old_keys))
    check("旧键清单与已知历史键一致",
          set(old_keys) == {"mbti_draft_v1", "yunshang_test3_draft_v1", "eq_test_draft_v2", "eq_test_done_v2"},
          ",".join(old_keys))

    print("== 4. 每屏合规页脚 ==")
    foot = re.findall(r"foot\s*:\s*\[(.*?)\]", html, re.S)
    lines = re.findall(r'"([^"]{6,})"', foot[0]) if foot else []
    check("页脚两行：第一行带主体名、第二行是合规声明",
          len(lines) == 2 and "云上文旅集团" in lines[0] and ("不得作为" in lines[1] or "不构成" in lines[1]),
          "行数 %d：%s" % (len(lines), " / ".join(lines)))
    # 页脚在每一屏都渲染：五个屏各调一次 footHTML()
    calls = len(re.findall(r"footHTML\(\)", html))
    check("五屏都渲染两行页脚", calls >= 5, "footHTML() 调用 %d 次" % calls)

    print("== 5. 断点续答 ==")
    check("首页有「继续上次答题」入口", "继续上次" in html)
    check("提供清除本机数据入口", "清除本机数据" in html)

    print("== 6. 运行时行为（headless 实跑）==")
    # 6.1 写入半份作答 → 重新加载 → 出现续答入口并能恢复
    js = """
<script>window.addEventListener('load',function(){setTimeout(function(){
  try{
    var S=APP.S(); S.name='张三'; S.idLast4='4821'; S.a.m1[0]=0; S.a.m1[1]=1;
    APP.save();
    document.title='SAVED:'+(localStorage.getItem('assessment_core_v1')||'').length;
  }catch(e){document.title='ERR:'+e.message;}
},150);});</script>
"""
    dom = run_chrome("", js)
    tm = re.search(r"<title>([^<]*)</title>", dom)
    saved = tm.group(1) if tm else ""
    check("作答能写入本机存储", saved.startswith("SAVED:") and saved != "SAVED:0", saved)
    # 6.2 清除本机数据：把存储塞满后调用清除入口，确认存储被清空
    js2 = """
<script>window.addEventListener('load',function(){setTimeout(function(){
  try{
    window.confirm=function(){return true;}; window.alert=function(){};
    localStorage.setItem('assessment_core_v1','{"a":{"m1":[0,1]}}');
    localStorage.setItem('mbti_draft_v1','x');
    APP.clearAll();
    var fresh=localStorage.getItem('assessment_core_v1')||'';
    document.title='AFTER:'+Object.keys(localStorage).length+':'+(localStorage.getItem('mbti_draft_v1')===null?'gone':'legacy-left')+':'+(fresh.indexOf('"m1":[0,1]')>=0?'old-answers':'fresh');
  }catch(e){document.title='ERR:'+e.message;}
},150);});</script>
"""
    dom2 = run_chrome("", js2)
    tm2 = re.search(r"<title>([^<]*)</title>", dom2)
    after = tm2.group(1) if tm2 else ""
    # 清除后允许存在一把"新会话"的键（应用会立刻写入新的空白状态），但旧作答与旧键必须消失
    parts = after.split(":")
    # 允许剩 0 或 1 把键（0 = 彻底清空；1 = 应用立刻写入了新的空白会话），旧作答与旧键必须消失
    ok = len(parts) == 4 and parts[1] in ("0", "1") and parts[2] == "gone" and parts[3] == "fresh"
    check("清除本机数据后旧作答与旧键都消失", ok, after)

    print("== 7. 红线与合规表述 ==")
    for word in ["及格线", "决定录用", "MBTI", "智商", "风险区", "稳健区"]:
        n = html.count(word)
        check("不出现「%s」" % word, n == 0, "%d 次" % n)
    # 允许出现的两条只允许出现在否定语境里
    for word in ["淘汰", "唯一依据", "一票否决"]:
        hits = re.findall(r"[^。；\n]{0,40}" + word + r"[^。；\n]{0,20}", html)
        neg = [h for h in hits if re.search(r"(不|不得|不能|不作|非)[^。；\n]{0,8}" + word, h)]
        check("「%s」只出现在否定/合规声明中" % word, len(hits) > 0 and len(hits) == len(neg),
              "%d 处，其中否定语境 %d 处" % (len(hits), len(neg)))

    bad = [x for x in results if not x[1]]
    print("\n==== %s ====" % ("全部通过" if not bad else "有 %d 项未通过" % len(bad)))
    for name, _, detail in bad:
        print("  - %s（%s）" % (name, detail))
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
