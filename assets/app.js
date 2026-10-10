/* 数学小白导览 · 交互脚本（纯前端，可直接 file:// 打开） */
(function () {
  'use strict';
  var KEY_DONE = 'sg.done.v1';
  var KEY_THEME = 'sg.theme.v1';

  function getDone() { try { return JSON.parse(localStorage.getItem(KEY_DONE) || '[]'); } catch (e) { return []; } }
  function setDone(a) { try { localStorage.setItem(KEY_DONE, JSON.stringify(a)); } catch (e) { /* 隐私模式下忽略 */ } }
  window.sgGetDone = getDone;

  function renderMath(root) {
    if (typeof window.renderMathInElement !== 'function') return;
    window.renderMathInElement(root || document.body, {
      delimiters: [{ left: '$$', right: '$$', display: true }, { left: '$', right: '$', display: false }],
      throwOnError: false
    });
    fitMath(root || document.body);
  }

  /* 过宽的行内公式（手机上常见）：放进可以左右滑动的小盒子里，免得把整页撑宽 */
  function fitMath(root) {
    var list = Array.prototype.slice.call(root.querySelectorAll('.katex')).filter(function (el) { return !el.closest('.katex-display'); });
    if (!list.length) return;
    list.forEach(function (el) { el.classList.remove('katex-wide'); });
    var vw = document.documentElement.clientWidth;
    var wide = list.map(function (el) {
      var host = el.parentElement;
      while (host && window.getComputedStyle(host).display.indexOf('inline') === 0) host = host.parentElement;
      if (!host || !host.clientWidth) return false;   // 被隐藏的元素：先不管
      var cs = window.getComputedStyle(host);
      var room = host.clientWidth - (parseFloat(cs.paddingLeft) || 0) - (parseFloat(cs.paddingRight) || 0);
      return el.getBoundingClientRect().width > Math.min(room, vw - 24) + 1;
    });
    list.forEach(function (el, i) { if (wide[i]) el.classList.add('katex-wide'); });
  }
  window.sgRenderMath = renderMath;

  /* ---------- 主题 ---------- */
  function applyTheme(t) {
    if (t === 'dark' || t === 'light') document.documentElement.setAttribute('data-theme', t);
    else document.documentElement.removeAttribute('data-theme');
  }
  try { applyTheme(localStorage.getItem(KEY_THEME)); } catch (e) { /* ignore */ }
  document.addEventListener('click', function (e) {
    var b = e.target.closest && e.target.closest('.theme-btn');
    if (!b) return;
    var cur = document.documentElement.getAttribute('data-theme');
    var sysDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
    var next = (cur || (sysDark ? 'dark' : 'light')) === 'dark' ? 'light' : 'dark';
    applyTheme(next);
    try { localStorage.setItem(KEY_THEME, next); } catch (err) { /* ignore */ }
  });

  /* ---------- 学习进度（本机浏览器 localStorage） ---------- */
  function initDoneButton() {
    var btn = document.getElementById('done-btn');
    if (!btn) return;
    var id = btn.getAttribute('data-id');
    function paint() {
      var on = getDone().indexOf(id) >= 0;
      btn.classList.toggle('on', on);
      btn.textContent = on ? '✓ 我已经看懂啦' : '○ 标记为“已学”';
    }
    btn.addEventListener('click', function () {
      var d = getDone(), i = d.indexOf(id);
      if (i >= 0) d.splice(i, 1); else d.push(id);
      setDone(d); paint();
    });
    paint();
  }

  /* 导出 / 导入进度：换设备或清缓存前备份一下 */
  function initProgressIO() {
    var exp = document.getElementById('exp'), imp = document.getElementById('imp');
    if (!exp || !imp) return;
    var row = exp.parentNode, msg = document.createElement('span');
    msg.className = 'small-note'; msg.setAttribute('role', 'status'); msg.style.margin = '0'; row.appendChild(msg);
    function say(t) { msg.textContent = t; }
    exp.addEventListener('click', function () {
      var data = { app: 'math-study-guide', version: 1, done: getDone(), exported: new Date().toISOString() };
      var blob = new Blob([JSON.stringify(data, null, 1)], { type: 'application/json' });
      var a = document.createElement('a');
      a.href = URL.createObjectURL(blob); a.download = 'math-guide-progress.json';
      document.body.appendChild(a); a.click();
      setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 800);
      say('已导出 ' + data.done.length + ' 条。');
    });
    imp.addEventListener('change', function () {
      var f = imp.files && imp.files[0];
      if (!f) return;
      var r = new FileReader();
      r.onload = function () {
        try {
          var d = JSON.parse(r.result), arr = Array.isArray(d) ? d : d.done;
          if (!Array.isArray(arr)) throw new Error('not a progress file');
          var set = {};
          getDone().concat(arr).forEach(function (x) { x = String(x); if (/^\d{3}$/.test(x)) set[x] = 1; });
          var merged = Object.keys(set).sort();
          setDone(merged);
          say('已导入，现在共 ' + merged.length + ' 条已学。');
          setTimeout(function () { location.reload(); }, 600);
        } catch (e) { say('这个文件看起来不是之前导出的进度文件。'); }
      };
      r.readAsText(f);
      imp.value = '';
    });
  }

  /* ---------- 问题卡片（首页「找起点」与全部问题页共用） ---------- */
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function stars(n) { return '★★★★★'.slice(0, n) + '<span style="opacity:.25">' + '★★★★★'.slice(n) + '</span>'; }

  function buildCard(it, s) {
    var a = document.createElement('a');
    a.className = 'item'; a.href = 'p/' + it.id + '.html';
    a.style.setProperty('--sc', 'hsl(' + s.hue + ' 62% 48%)');
    a.innerHTML =
      '<div class="top"><span class="num">' + it.id + '</span><span>' + esc(s.zh) + '</span></div>' +
      '<h3>' + esc(it.zh) + '</h3>' +
      '<div class="en">' + esc(it.en) + '</div>' +
      '<div class="tl">' + esc(it.tl) + '</div>' +
      '<div class="meta"><span class="stars lv' + it.lv + '" title="门槛 ' + it.lv + '/5">' + stars(it.lv) + '</span>' +
      (it.lab ? '<span class="tag lab">🧪 有互动</span>' : '') +
      (it.lean ? '<span class="tag lean">Lean</span>' : '') +
      (it.warn ? '<span class="tag warn">⚠️ 有提醒</span>' : '') + '</div>' +
      '<span class="done" hidden>✓</span>';
    return a;
  }
  window.sgBuildCard = buildCard;

  function readParams() {
    var p = {}, qs = (location.search || '').replace(/^\?/, '');
    qs.split('&').forEach(function (kv) {
      if (!kv) return;
      var i = kv.indexOf('=');
      try {
        p[decodeURIComponent(i < 0 ? kv : kv.slice(0, i))] = i < 0 ? '' : decodeURIComponent(kv.slice(i + 1).replace(/\+/g, ' '));
      } catch (e) { /* 坏掉的参数忽略 */ }
    });
    return p;
  }
  function nums(s) { return String(s || '').split(',').map(function (x) { return parseInt(x, 10); }).filter(function (x) { return !isNaN(x); }); }

  /* ---------- 全部问题页：搜索 / 筛选 / 排序（支持 ?q=&s=&lv=&lab=1&lean=1&todo=1&sort= 预设） ---------- */
  function initIndex() {
    var D = window.GUIDE_DATA, grid = document.getElementById('grid');
    if (!D || !grid) return;
    var subj = {}; D.subjects.forEach(function (s) { subj[s.id] = s; });
    var done = getDone();

    var cards = D.items.map(function (it) {
      var a = buildCard(it, subj[it.s]), s = subj[it.s];
      a._it = it;
      a._hay = (it.id + ' ' + it.zh + ' ' + it.en + ' ' + it.tl + ' ' + it.kw + ' ' + s.zh + ' ' + s.en).toLowerCase();
      return a;
    });
    cards.forEach(function (c) { grid.appendChild(c); });
    if (window.sgRenderMath) window.sgRenderMath(grid);

    var q = document.getElementById('q'), sort = document.getElementById('sort'), count = document.getElementById('count');
    var state = { subjects: {}, lv: {}, lab: false, lean: false, todo: false };

    var P = readParams();
    if (P.q) q.value = P.q;
    if (/^(id|lv|lvd|subj)$/.test(P.sort || '')) sort.value = P.sort;
    nums(P.s).forEach(function (n) { state.subjects[n] = true; });
    nums(P.lv).forEach(function (n) { state.lv[n] = true; });
    state.lab = P.lab === '1'; state.lean = P.lean === '1'; state.todo = P.todo === '1';

    function mkChip(host, label, get, set) {
      var c = document.createElement('button');
      c.type = 'button'; c.className = 'chip'; c.innerHTML = label;
      function paint() { c.classList.toggle('on', !!get()); c.setAttribute('aria-pressed', get() ? 'true' : 'false'); }
      c.addEventListener('click', function () { set(!get()); paint(); apply(); });
      paint(); host.appendChild(c); return c;
    }
    var sh = document.getElementById('f-subj');
    D.subjects.forEach(function (s) {
      mkChip(sh, s.icon + ' ' + esc(s.zh) + ' <small>' + s.n + '</small>', function () { return state.subjects[s.id]; }, function (v) { state.subjects[s.id] = v; });
    });
    var lh = document.getElementById('f-lv');
    var lvName = ['', '初高中', '+一点大学', '本科', '研究生', '专家'];
    for (var i = 1; i <= 5; i++) (function (n) {
      mkChip(lh, '<span class="lv' + n + '">' + '★'.repeat(n) + '</span> ' + lvName[n], function () { return state.lv[n]; }, function (v) { state.lv[n] = v; });
    })(i);
    var fh = document.getElementById('f-flag');
    mkChip(fh, '🧪 有互动实验', function () { return state.lab; }, function (v) { state.lab = v; });
    mkChip(fh, '🧾 有 Lean 形式化', function () { return state.lean; }, function (v) { state.lean = v; });
    mkChip(fh, '📘 我还没学过', function () { return state.todo; }, function (v) { state.todo = v; });

    function anyOf(map) { return Object.keys(map).some(function (k) { return map[k]; }); }
    function onKeys(map) { return Object.keys(map).filter(function (k) { return map[k]; }); }
    function syncUrl() {
      var p = [];
      if (q.value.trim()) p.push('q=' + encodeURIComponent(q.value.trim()));
      if (anyOf(state.subjects)) p.push('s=' + onKeys(state.subjects).join(','));
      if (anyOf(state.lv)) p.push('lv=' + onKeys(state.lv).join(','));
      if (state.lab) p.push('lab=1');
      if (state.lean) p.push('lean=1');
      if (state.todo) p.push('todo=1');
      if (sort.value !== 'id') p.push('sort=' + sort.value);
      try { history.replaceState(null, '', location.pathname + (p.length ? '?' + p.join('&') : '')); } catch (e) { /* file:// 等场景不允许，忽略 */ }
    }
    function apply() {
      done = getDone();
      var terms = q.value.trim().toLowerCase().split(/\s+/).filter(Boolean);
      var useS = anyOf(state.subjects), useL = anyOf(state.lv), n = 0;
      cards.forEach(function (c) {
        var it = c._it, ok = true;
        if (useS && !state.subjects[it.s]) ok = false;
        if (ok && useL && !state.lv[it.lv]) ok = false;
        if (ok && state.lab && !it.lab) ok = false;
        if (ok && state.lean && !it.lean) ok = false;
        if (ok && state.todo && done.indexOf(it.id) >= 0) ok = false;
        if (ok) for (var t = 0; t < terms.length; t++) if (c._hay.indexOf(terms[t]) < 0) { ok = false; break; }
        c.hidden = !ok; if (ok) n++;
        c.querySelector('.done').hidden = done.indexOf(it.id) < 0;
      });
      count.textContent = '共 ' + n + ' 个问题' + (n === cards.length ? '' : '（已筛选，总数 ' + cards.length + '）');
      var pr = document.getElementById('progress');
      if (pr) pr.textContent = '已学 ' + done.filter(function (d) { return cards.some(function (c) { return c._it.id === d; }); }).length + ' / ' + cards.length;
      syncUrl();
    }
    function order() {
      var m = sort.value;
      var arr = cards.slice();
      if (m === 'lv') arr.sort(function (a, b) { return a._it.lv - b._it.lv || (a._it.id < b._it.id ? -1 : 1); });
      else if (m === 'subj') arr.sort(function (a, b) { return a._it.s - b._it.s || (a._it.id < b._it.id ? -1 : 1); });
      else if (m === 'lvd') arr.sort(function (a, b) { return b._it.lv - a._it.lv || (a._it.id < b._it.id ? -1 : 1); });
      else arr.sort(function (a, b) { return a._it.id < b._it.id ? -1 : 1; });
      arr.forEach(function (c) { grid.appendChild(c); });
    }
    q.addEventListener('input', apply);
    sort.addEventListener('change', function () { order(); syncUrl(); });
    order();
    apply();
  }

  /* ---------- 词汇表搜索 ---------- */
  function initGlossary() {
    var box = document.getElementById('gq'), list = document.getElementById('gl-list');
    if (!box || !list) return;
    var items = Array.prototype.slice.call(list.children);
    box.addEventListener('input', function () {
      var t = box.value.trim().toLowerCase();
      items.forEach(function (el) { el.hidden = t && el.textContent.toLowerCase().indexOf(t) < 0; });
    });
  }

  function boot() {
    renderMath(document.body);
    initDoneButton();
    initProgressIO();
    initIndex();
    initGlossary();
    // 卡片里的公式在 initIndex 内渲染；其余页面此处统一渲染
    var rz;
    window.addEventListener('resize', function () { clearTimeout(rz); rz = setTimeout(function () { fitMath(document.body); }, 150); });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else boot();
})();
