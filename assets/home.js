/* 数学小白导览 · 首页脚本：分形动画、精选轮播、找起点、随机一题、继续学习（纯前端，无依赖） */
(function () {
  'use strict';
  var D = window.GUIDE_DATA;
  var reduce = !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);

  function shuffle(a) {
    a = a.slice();
    for (var i = a.length - 1; i > 0; i--) { var j = Math.floor(Math.random() * (i + 1)), t = a[i]; a[i] = a[j]; a[j] = t; }
    return a;
  }

  /* ---------- 英雄区：混沌游戏（自己长出来的分形） ---------- */
  var PRESETS = [
    { n: 3, r: 0.5, rot: -90, text: '混沌游戏：随机朝顶点跳半步，点点之间长出谢尔宾斯基三角形。' },
    { n: 5, r: 0.618, rot: -90, text: '换成 5 个顶点，每次跳 0.618 的距离：长出五边形的分形。' },
    { n: 4, r: 0.5, rot: -135, noRepeat: true, text: '4 个顶点，但不许连着两次选同一个：正方形里也长出空洞。' },
    { n: 6, r: 0.667, rot: -90, text: '6 个顶点，每次跳 2/3：像雪花一样的自相似。' }
  ];

  function chaos() {
    var cv = document.getElementById('chaos');
    if (!cv || !cv.getContext) return;
    var ctx = cv.getContext('2d'), W = cv.width, H = cv.height, label = document.getElementById('chaos-label');
    var BG = '#080c26', TOTAL = 52000, PER = 260;
    var cur = 0, V, x, y, last, drawn, phase, wait, visible = true, raf = 0;

    function setup(k) {
      var P = PRESETS[k], R = Math.min(W, H) * 0.44, cx = W / 2, cy = H / 2 + 10;
      V = [];
      for (var i = 0; i < P.n; i++) {
        var a = (P.rot + 360 * i / P.n) * Math.PI / 180;
        V.push([cx + R * Math.cos(a), cy + R * Math.sin(a)]);
      }
      x = cx; y = cy; last = -1; drawn = 0; phase = 'draw'; wait = 0;
      ctx.globalAlpha = 1; ctx.fillStyle = BG; ctx.fillRect(0, 0, W, H);
      if (label) label.textContent = P.text;
    }
    function dots(count) {
      var P = PRESETS[cur], n = P.n;
      ctx.globalAlpha = 0.9;
      for (var i = 0; i < count; i++) {
        var j = Math.floor(Math.random() * n);
        if (P.noRepeat) while (j === last) j = Math.floor(Math.random() * n);
        last = j;
        x += (V[j][0] - x) * P.r; y += (V[j][1] - y) * P.r;
        if (drawn + i < 30) continue;   // 最开始几步还没“落进”图形里，不画
        ctx.fillStyle = 'hsl(' + Math.round(210 + 300 * j / n) % 360 + ',85%,68%)';
        ctx.fillRect(x - 0.8, y - 0.8, 1.7, 1.7);
      }
      drawn += count;
    }
    function frame() {
      raf = 0;
      if (visible && !document.hidden) {
        if (phase === 'draw') { dots(PER); if (drawn >= TOTAL) { phase = 'hold'; wait = 150; } }
        else if (phase === 'hold') { if (--wait <= 0) { phase = 'fade'; wait = 14; } }
        else {   // fade：逐帧盖一层半透明底色，再换下一个形状
          ctx.globalAlpha = 0.22; ctx.fillStyle = BG; ctx.fillRect(0, 0, W, H);
          if (--wait <= 0) { cur = (cur + 1) % PRESETS.length; setup(cur); }
        }
      }
      raf = requestAnimationFrame(frame);
    }

    setup(0);
    if (reduce) {   // 少动效偏好：一次画完第一幅，不再动
      while (drawn < TOTAL) dots(PER * 4);
      return;
    }
    if ('IntersectionObserver' in window) {
      new IntersectionObserver(function (es) { visible = es[0].isIntersecting; }, { threshold: 0.05 }).observe(cv);
    }
    raf = requestAnimationFrame(frame);
  }

  /* ---------- 精选轮播 ---------- */
  function carousel() {
    var car = document.getElementById('car'), prev = document.getElementById('car-prev'), next = document.getElementById('car-next');
    if (!car || !prev || !next) return;
    function step() { var c = car.querySelector('.fc'); return c ? c.getBoundingClientRect().width + 16 : 300; }
    function upd() {
      prev.disabled = car.scrollLeft < 4;
      next.disabled = car.scrollLeft + car.clientWidth >= car.scrollWidth - 4;
    }
    prev.addEventListener('click', function () { car.scrollBy({ left: -step(), behavior: reduce ? 'auto' : 'smooth' }); });
    next.addEventListener('click', function () { car.scrollBy({ left: step(), behavior: reduce ? 'auto' : 'smooth' }); });
    car.addEventListener('scroll', upd, { passive: true });
    car.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowRight') { e.preventDefault(); next.click(); }
      else if (e.key === 'ArrowLeft') { e.preventDefault(); prev.click(); }
    });
    window.addEventListener('resize', upd);
    upd();
  }

  /* ---------- 找到你的起点 ---------- */
  function finder() {
    var bar = document.getElementById('fd-bar'), grid = document.getElementById('fd-grid');
    if (!bar || !grid || !D || !window.sgBuildCard) return;
    var subj = {}; D.subjects.forEach(function (s) { subj[s.id] = s; });
    var chips = Array.prototype.slice.call(bar.querySelectorAll('.chip'));
    var labBox = document.getElementById('fd-lab'), more = document.getElementById('fd-more'), again = document.getElementById('fd-shuffle');
    var lv = 2, fresh = false;   // fresh：点了“换一批”之后才随机；刚切换档位时按固定规则排，和页面静态版一致

    function inBand(x) { return lv === 1 ? x.lv === 1 : (x.lv >= lv - 1 && x.lv <= lv); }
    function pick(n) {
      var p = D.items.filter(function (x) { return inBand(x) && (!labBox.checked || x.lab); });
      var withLab = p.filter(function (x) { return x.lab; }), rest = p.filter(function (x) { return !x.lab; });
      var by = function (a, b) { return a.id < b.id ? -1 : 1; };
      p = (fresh ? shuffle(withLab).concat(shuffle(rest)) : withLab.sort(by).concat(rest.sort(by)));
      var out = [], seen = {};
      p.forEach(function (x) { if (!seen[x.s] && out.length < n) { out.push(x); seen[x.s] = 1; } });   // 同一学科尽量不重复
      p.forEach(function (x) { if (out.indexOf(x) < 0 && out.length < n) out.push(x); });
      return out;
    }
    function render() {
      var list = pick(6), done = window.sgGetDone ? window.sgGetDone() : [];
      grid.textContent = '';
      if (!list.length) {
        var p = document.createElement('p');
        p.className = 'small-note'; p.textContent = '这一档里暂时没有符合条件的问题，试试取消“只看有互动实验的”。';
        grid.appendChild(p);
      }
      list.forEach(function (it) {
        var a = window.sgBuildCard(it, subj[it.s]);
        if (done.indexOf(it.id) >= 0) a.querySelector('.done').hidden = false;
        grid.appendChild(a);
      });
      if (window.sgRenderMath) window.sgRenderMath(grid);
      more.href = 'problems.html?lv=' + (lv === 1 ? '1' : (lv - 1) + ',' + lv) + (labBox.checked ? '&lab=1' : '');
    }
    chips.forEach(function (c) {
      c.addEventListener('click', function () {
        lv = parseInt(c.getAttribute('data-lv'), 10); fresh = false;
        chips.forEach(function (o) { var on = o === c; o.classList.toggle('on', on); o.setAttribute('aria-pressed', on ? 'true' : 'false'); });
        render();
      });
      c.setAttribute('aria-pressed', c.classList.contains('on') ? 'true' : 'false');
    });
    labBox.addEventListener('change', function () { fresh = false; render(); });
    again.addEventListener('click', function () { fresh = true; render(); });
  }

  /* ---------- 随机来一个 / 继续学习 ---------- */
  function extras() {
    if (!D) return;
    Array.prototype.forEach.call(document.querySelectorAll('[data-random]'), function (a) {
      a.addEventListener('click', function (e) {
        e.preventDefault();
        location.href = 'p/' + D.items[Math.floor(Math.random() * D.items.length)].id + '.html';
      });
    });
    var box = document.getElementById('resume');
    if (box && window.sgGetDone) {
      var ids = {}; D.items.forEach(function (x) { ids[x.id] = 1; });
      var n = window.sgGetDone().filter(function (id) { return ids[id]; }).length;
      if (n) {
        box.hidden = false;
        box.innerHTML = '👋 欢迎回来：你已学了 <b>' + n + ' / ' + D.items.length + '</b> 个问题。<a href="problems.html?todo=1">继续学下一个 →</a>';
      }
    }
  }

  function init() { chaos(); carousel(); finder(); extras(); }
  // 本脚本在 app.js 之前执行；等 DOMContentLoaded（所有 defer 脚本都跑完）再初始化，才能用到 app.js 暴露的 sgBuildCard 等函数
  if (document.readyState === 'complete') init(); else document.addEventListener('DOMContentLoaded', init);
})();
