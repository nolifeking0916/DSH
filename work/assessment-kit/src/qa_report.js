/* 打印验收用：把报告页渲染成"有数据的样子"，供 verify_print.py 出 A4 PDF。
   用法：把本文件内容拼在成品 HTML 的 </body> 之前，Chrome --print-to-pdf 即可打印出报告。 */
<script>
window.addEventListener('load', function () {
  setTimeout(function () {
    try {
      var S = APP.S(), D = window.__DATA__;
      S.name = '演示候选人';
      S.idLast4 = '4821';
      S.code = 'EQ-20261024-95DX6F-FD1E';
      S.consented = true;
      /* 第一项：锚定端全选（每题 anchor 那一端） */
      D.m1.items.forEach(function (it, ix) { S.a.m1[ix] = it.anchor === 'a' ? 0 : 1; });
      /* 第二项：自评取 4/7，情境取正确项 */
      D.eq.self_items.forEach(function (x, ix) { S.a.m2[ix] = ix % 3 === 0 ? 5 : 4; });
      var off = D.eq.self_items.length;
      D.eq.sjt.forEach(function (q, ix) {
        var L = 'ABCD', k = L.indexOf(q.answer);
        S.a.m2[off + ix] = k < 0 ? 0 : (k === 0 ? 1 : k);
      });
      /* 第三项：留 8 题故意答错，好让错题回顾有内容可查 */
      D.m3.questions.forEach(function (q, ix) { S.a.m3[ix] = q.answer === 0 ? 1 : q.answer; });
      APP.openReport();
    } catch (e) {
      document.title = 'QAERR: ' + e.message;
    }
  }, 200);
});
</script>
