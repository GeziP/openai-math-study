/* 互动实验室 · 公共库（无依赖、可离线）。每个实验页的脚本直接使用全局对象 Lab。
 * 约定：canvas 用"逻辑像素"作画（Lab.canvas(host, w, h) 里的 w、h），自动适配高分屏与页面宽度。 */
(function () {
  'use strict';
  var Lab = (window.Lab = {});
  var TAU = Math.PI * 2;
  Lab.TAU = TAU;

  /* ============================== DOM 与控件 ============================== */
  Lab.$ = function (sel, root) { return (root || document).querySelector(sel); };
  Lab.$$ = function (sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); };

  Lab.el = function (tag, props, kids) {
    var e = document.createElement(tag), k, s, ev;
    props = props || {};
    for (k in props) {
      if (!Object.prototype.hasOwnProperty.call(props, k)) continue;
      var v = props[k];
      if (k === 'class') e.className = v;
      else if (k === 'text') e.textContent = v;
      else if (k === 'html') e.innerHTML = v;
      else if (k === 'style') { for (s in v) e.style[s] = v[s]; }
      else if (k === 'on') { for (ev in v) e.addEventListener(ev, v[ev]); }
      else e.setAttribute(k, v);
    }
    (kids || []).forEach(function (c) { e.appendChild(typeof c === 'string' ? document.createTextNode(c) : c); });
    return e;
  };

  function wrap(host, label, cls) {
    var w = Lab.el('div', { 'class': 'ctrl' + (cls ? ' ' + cls : '') });
    if (label != null && label !== '') w.appendChild(Lab.el('span', { 'class': 'nm', html: label }));
    host.appendChild(w);
    return w;
  }

  /* 滑块：o = {label, min, max, step, value, fmt, onInput} */
  Lab.slider = function (host, o) {
    var w = wrap(host, o.label);
    var val = Lab.el('output', { 'class': 'val' });
    var inp = Lab.el('input', { type: 'range', min: o.min, max: o.max, step: o.step || 1 });
    inp.value = o.value != null ? o.value : o.min;
    w.appendChild(val);
    w.appendChild(inp);
    var fmt = o.fmt || function (v) { return String(v); };
    function paint() { val.textContent = fmt(+inp.value); }
    inp.addEventListener('input', function () { paint(); if (o.onInput) o.onInput(+inp.value); });
    paint();
    return {
      el: inp,
      get: function () { return +inp.value; },
      set: function (v, silent) { inp.value = v; paint(); if (!silent && o.onInput) o.onInput(+inp.value); }
    };
  };

  /* 按钮：返回 <button>；cls 可为 'pri'（主按钮） */
  Lab.button = function (host, text, fn, cls) {
    var b = Lab.el('button', { 'class': 'lb' + (cls ? ' ' + cls : ''), type: 'button', html: text });
    if (fn) b.addEventListener('click', fn);
    host.appendChild(b);
    return b;
  };
  Lab.row = function (host) { var r = Lab.el('div', { 'class': 'btn-row' }); host.appendChild(r); return r; };

  /* 下拉框：o = {label, options:[[value,text],...], value, onChange} */
  Lab.select = function (host, o) {
    var w = wrap(host, o.label);
    var sel = Lab.el('select');
    o.options.forEach(function (p) { sel.appendChild(Lab.el('option', { value: p[0], text: p[1] })); });
    sel.value = o.value != null ? o.value : o.options[0][0];
    sel.addEventListener('change', function () { if (o.onChange) o.onChange(sel.value); });
    w.appendChild(sel);
    return { el: sel, get: function () { return sel.value; }, set: function (v) { sel.value = v; } };
  };

  /* 文本框：o = {label, value, placeholder, onInput} */
  Lab.text = function (host, o) {
    var w = wrap(host, o.label);
    var inp = Lab.el('input', { type: 'text', placeholder: o.placeholder || '', spellcheck: 'false', autocomplete: 'off' });
    inp.value = o.value != null ? o.value : '';
    inp.addEventListener('input', function () { if (o.onInput) o.onInput(inp.value); });
    w.appendChild(inp);
    return { el: inp, get: function () { return inp.value; }, set: function (v, silent) { inp.value = v; if (!silent && o.onInput) o.onInput(v); } };
  };

  /* 数字框：o = {label, min, max, step, value, onInput} */
  Lab.number = function (host, o) {
    var w = wrap(host, o.label);
    var inp = Lab.el('input', { type: 'number', min: o.min, max: o.max, step: o.step || 1 });
    inp.value = o.value != null ? o.value : o.min;
    inp.addEventListener('input', function () { if (o.onInput) o.onInput(+inp.value); });
    w.appendChild(inp);
    return { el: inp, get: function () { return +inp.value; }, set: function (v, silent) { inp.value = v; if (!silent && o.onInput) o.onInput(+inp.value); } };
  };

  /* 复选框：o = {label, checked, onChange} */
  Lab.check = function (host, o) {
    var w = Lab.el('label', { 'class': 'ctrl inline' });
    var inp = Lab.el('input', { type: 'checkbox' });
    inp.checked = !!o.checked;
    inp.addEventListener('change', function () { if (o.onChange) o.onChange(inp.checked); });
    w.appendChild(inp);
    w.appendChild(Lab.el('span', { 'class': 'nm', html: o.label }));
    host.appendChild(w);
    return { el: inp, get: function () { return inp.checked; }, set: function (v) { inp.checked = !!v; } };
  };

  /* 只读输出框（等宽字体），.html(s) 可含简单标签 */
  Lab.out = function (host, cls) {
    var d = Lab.el('div', { 'class': 'lab-out' + (cls ? ' ' + cls : '') });
    host.appendChild(d);
    return { el: d, html: function (s) { d.innerHTML = s; }, text: function (s) { d.textContent = s; } };
  };

  /* 小标题 / 提示文字 */
  Lab.h3 = function (host, s) { var e = Lab.el('h3', { html: s }); host.appendChild(e); return e; };
  Lab.hint = function (host, s) { var e = Lab.el('p', { 'class': 'hint', html: s }); host.appendChild(e); return e; };

  /* 图例：items = [[颜色, 文字], ...] */
  Lab.legend = function (host, items) {
    var d = Lab.el('div', { 'class': 'lab-legend' });
    items.forEach(function (it) {
      d.appendChild(Lab.el('span', { html: '<i style="background:' + it[0] + '"></i>' + it[1] }));
    });
    host.appendChild(d);
    return d;
  };

  /* ============================== 主题与颜色 ============================== */
  Lab.colors = function () {
    var cs = getComputedStyle(document.documentElement);
    function v(n) { return cs.getPropertyValue(n).trim(); }
    return {
      bg: v('--bg'), card: v('--card'), ink: v('--ink'), ink2: v('--ink2'), muted: v('--muted'), line: v('--line'),
      accent: v('--accent'), accentInk: v('--accent-ink'), soft: v('--accent-soft'), good: v('--good'), warn: v('--warn'), bad: v('--bad'), code: v('--code-bg')
    };
  };
  Lab.isDark = function () {
    var t = document.documentElement.getAttribute('data-theme');
    if (t) return t === 'dark';
    return !!(window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches);
  };
  /* 主题切换时回调（用来重绘 canvas） */
  Lab.onTheme = function (cb) {
    try { new MutationObserver(function () { cb(); }).observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] }); } catch (e) { /* ignore */ }
    if (window.matchMedia) {
      var mq = window.matchMedia('(prefers-color-scheme: dark)');
      if (mq.addEventListener) mq.addEventListener('change', function () { cb(); });
    }
  };
  Lab.hsl = function (h, s, l, a) { return 'hsla(' + (((h % 360) + 360) % 360).toFixed(1) + ',' + s + '%,' + l + '%,' + (a == null ? 1 : a) + ')'; };
  /* h∈[0,360)，s、l∈[0,100] → [r,g,b]（0~255），用于逐像素作画 */
  Lab.rgb = function (h, s, l) {
    h = (((h % 360) + 360) % 360) / 360; s /= 100; l /= 100;
    function f(p, q, t) { if (t < 0) t += 1; if (t > 1) t -= 1; if (t < 1 / 6) return p + (q - p) * 6 * t; if (t < 1 / 2) return q; if (t < 2 / 3) return p + (q - p) * (2 / 3 - t) * 6; return p; }
    if (s === 0) { var g = Math.round(l * 255); return [g, g, g]; }
    var q = l < 0.5 ? l * (1 + s) : l + s - l * s, p = 2 * l - q;
    return [Math.round(f(p, q, h + 1 / 3) * 255), Math.round(f(p, q, h) * 255), Math.round(f(p, q, h - 1 / 3) * 255)];
  };
  /* 'rgb(…)'/'#rrggbb' 之类的 CSS 颜色 → [r,g,b]（借助 canvas 解析） */
  var _cc = null;
  Lab.parseColor = function (css) {
    if (!_cc) { var c = document.createElement('canvas'); c.width = c.height = 1; _cc = c.getContext('2d'); }
    _cc.clearRect(0, 0, 1, 1);
    _cc.fillStyle = '#000';
    _cc.fillStyle = css;
    _cc.fillRect(0, 0, 1, 1);
    var d = _cc.getImageData(0, 0, 1, 1).data;
    return [d[0], d[1], d[2]];
  };

  /* ============================== Canvas ============================== */
  /* 在 host 里创建画布。返回 {cv, ctx, w, h, clear(bg), pos(event)}；pos 把鼠标位置换算成逻辑坐标 */
  Lab.canvas = function (host, w, h) {
    var dpr = Math.min(window.devicePixelRatio || 1, 2);
    var cv = Lab.el('canvas', { 'class': 'lab-canvas', width: Math.round(w * dpr), height: Math.round(h * dpr) });
    cv.style.aspectRatio = w + ' / ' + h;
    host.appendChild(cv);
    var ctx = cv.getContext('2d');
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    return {
      cv: cv, ctx: ctx, w: w, h: h, dpr: dpr,
      clear: function (bg) {
        ctx.save();
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        ctx.fillStyle = bg || Lab.colors().card;
        ctx.fillRect(0, 0, w, h);
        ctx.restore();
      },
      pos: function (e) {
        var r = cv.getBoundingClientRect();
        return { x: (e.clientX - r.left) * w / r.width, y: (e.clientY - r.top) * h / r.height };
      }
    };
  };

  /* 离屏位图：img.data 是 RGBA 数组，flush() 写回；blit 把它拉伸画到主画布（不做平滑） */
  Lab.bitmap = function (w, h) {
    var cv = document.createElement('canvas');
    cv.width = w; cv.height = h;
    var ctx = cv.getContext('2d');
    var img = ctx.createImageData(w, h);
    return {
      cv: cv, ctx: ctx, img: img, data: img.data, w: w, h: h,
      flush: function () { ctx.putImageData(img, 0, 0); },
      blit: function (dst, x, y, ww, hh) { dst.imageSmoothingEnabled = false; dst.drawImage(cv, x, y, ww, hh); }
    };
  };

  /* 简单绘图小工具 */
  Lab.line = function (ctx, x0, y0, x1, y1, color, lw) {
    ctx.beginPath(); ctx.moveTo(x0, y0); ctx.lineTo(x1, y1);
    if (color) ctx.strokeStyle = color;
    if (lw) ctx.lineWidth = lw;
    ctx.stroke();
  };
  Lab.dot = function (ctx, x, y, r, fill, stroke) {
    ctx.beginPath(); ctx.arc(x, y, r, 0, TAU);
    if (fill) { ctx.fillStyle = fill; ctx.fill(); }
    if (stroke) { ctx.strokeStyle = stroke; ctx.stroke(); }
  };
  Lab.path = function (ctx, pts, close) {
    if (!pts.length) return;
    ctx.beginPath(); ctx.moveTo(pts[0][0], pts[0][1]);
    for (var i = 1; i < pts.length; i++) ctx.lineTo(pts[i][0], pts[i][1]);
    if (close) ctx.closePath();
  };
  Lab.label = function (ctx, s, x, y, color, align, size, base) {
    ctx.fillStyle = color || Lab.colors().ink;
    ctx.textAlign = align || 'left';
    ctx.textBaseline = base || 'middle';
    ctx.font = (size || 13) + 'px "Microsoft YaHei UI","PingFang SC","Noto Sans SC",system-ui,sans-serif';
    ctx.fillText(s, x, y);
  };
  Lab.arrow = function (ctx, x0, y0, x1, y1, color, lw) {
    var a = Math.atan2(y1 - y0, x1 - x0), hl = 8 + (lw || 1) * 1.5;
    ctx.strokeStyle = color; ctx.fillStyle = color; ctx.lineWidth = lw || 1.5;
    ctx.beginPath(); ctx.moveTo(x0, y0); ctx.lineTo(x1, y1); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(x1, y1);
    ctx.lineTo(x1 - hl * Math.cos(a - 0.4), y1 - hl * Math.sin(a - 0.4));
    ctx.lineTo(x1 - hl * Math.cos(a + 0.4), y1 - hl * Math.sin(a + 0.4));
    ctx.closePath(); ctx.fill();
  };

  /* "好看"的刻度：返回 [lo,hi] 内约 n 个整齐的刻度值 */
  Lab.ticks = function (lo, hi, n) {
    var span = hi - lo;
    if (!(span > 0)) return [lo];
    var step0 = span / Math.max(1, n), mag = Math.pow(10, Math.floor(Math.log(step0) / Math.LN10)), r = step0 / mag;
    var step = (r < 1.5 ? 1 : r < 3.5 ? 2 : r < 7.5 ? 5 : 10) * mag;
    var out = [], t = Math.ceil(lo / step - 1e-9) * step;
    for (; t <= hi + step * 1e-9; t += step) out.push(Math.abs(t) < step * 1e-9 ? 0 : t);
    return out;
  };
  /* 画坐标轴与网格。box={x,y,w,h}（像素），xr/yr=[最小,最大]。
   * o: {nx, ny, xticks, yticks, fx, fy, xlabel, ylabel, grid(默认true)}；返回 {X(x), Y(y), iX(px), iY(py), box} */
  Lab.axes = function (ctx, box, xr, yr, o) {
    o = o || {};
    var C = Lab.colors();
    var X = function (x) { return box.x + (x - xr[0]) / (xr[1] - xr[0]) * box.w; };
    var Y = function (y) { return box.y + box.h - (y - yr[0]) / (yr[1] - yr[0]) * box.h; };
    var iX = function (px) { return xr[0] + (px - box.x) / box.w * (xr[1] - xr[0]); };
    var iY = function (py) { return yr[0] + (box.y + box.h - py) / box.h * (yr[1] - yr[0]); };
    var xt = o.xticks || Lab.ticks(xr[0], xr[1], o.nx || 6), yt = o.yticks || Lab.ticks(yr[0], yr[1], o.ny || 5);
    var fx = o.fx || function (v) { return Lab.fmt(v, 3); }, fy = o.fy || function (v) { return Lab.fmt(v, 3); };
    ctx.save();
    ctx.lineWidth = 1;
    ctx.strokeStyle = C.line;
    if (o.grid !== false) {
      ctx.beginPath();
      xt.forEach(function (t) { var px = Math.round(X(t)) + 0.5; ctx.moveTo(px, box.y); ctx.lineTo(px, box.y + box.h); });
      yt.forEach(function (t) { var py = Math.round(Y(t)) + 0.5; ctx.moveTo(box.x, py); ctx.lineTo(box.x + box.w, py); });
      ctx.stroke();
    }
    ctx.strokeStyle = C.muted;
    ctx.strokeRect(box.x + 0.5, box.y + 0.5, box.w, box.h);
    xt.forEach(function (t) { Lab.label(ctx, fx(t), X(t), box.y + box.h + 12, C.muted, 'center', 11.5); });
    yt.forEach(function (t) { Lab.label(ctx, fy(t), box.x - 6, Y(t), C.muted, 'right', 11.5); });
    if (o.xlabel) Lab.label(ctx, o.xlabel, box.x + box.w / 2, box.y + box.h + 28, C.ink2, 'center', 12.5);
    if (o.ylabel) {
      ctx.translate(box.x - 40, box.y + box.h / 2);
      ctx.rotate(-Math.PI / 2);
      Lab.label(ctx, o.ylabel, 0, 0, C.ink2, 'center', 12.5);
    }
    ctx.restore();
    return { X: X, Y: Y, iX: iX, iY: iY, box: box };
  };

  /* ============================== 动画、拖动 ============================== */
  /* 循环：fn(t) 每帧调用；fps 可限速。返回 {start, stop, toggle, running()} */
  Lab.loop = function (fn, fps) {
    var id = 0, last = 0, on = false;
    function tick(t) {
      if (!on) return;
      if (!fps || t - last >= 1000 / fps) { last = t; fn(t); }
      id = requestAnimationFrame(tick);
    }
    var api = {
      start: function () { if (!on) { on = true; id = requestAnimationFrame(tick); } },
      stop: function () { on = false; cancelAnimationFrame(id); },
      toggle: function () { if (on) api.stop(); else api.start(); return on; },
      running: function () { return on; }
    };
    return api;
  };

  /* 拖动：c 是 Lab.canvas 的返回值；o = {down(p,e)→状态或falsy, move(p,状态,e), up(p,状态,e), hover(p,e)} */
  Lab.drag = function (c, o) {
    var st = null;
    c.cv.addEventListener('pointerdown', function (e) {
      var s = o.down(c.pos(e), e);
      if (s) { st = s; try { c.cv.setPointerCapture(e.pointerId); } catch (err) { /* ignore */ } e.preventDefault(); }
    });
    c.cv.addEventListener('pointermove', function (e) {
      var p = c.pos(e);
      if (st) o.move(p, st, e); else if (o.hover) o.hover(p, e);
    });
    function end(e) { if (st) { var s = st; st = null; if (o.up) o.up(c.pos(e), s, e); } }
    c.cv.addEventListener('pointerup', end);
    c.cv.addEventListener('pointercancel', end);
  };

  /* ============================== 随机数 ============================== */
  /* 可复现的随机数（mulberry32）：r() 返回 [0,1)；r.int(n)、r.normal()、r.pick(arr)、r.shuffle(arr) */
  Lab.rng = function (seed) {
    var a = (seed == null ? (Math.random() * 4294967296) : seed) >>> 0;
    function r() {
      a = (a + 0x6D2B79F5) | 0;
      var t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    }
    r.int = function (n) { return Math.floor(r() * n); };
    r.normal = function () { var u = 1 - r(), v = r(); return Math.sqrt(-2 * Math.log(u)) * Math.cos(TAU * v); };
    r.pick = function (arr) { return arr[Math.floor(r() * arr.length)]; };
    r.shuffle = function (arr) { for (var i = arr.length - 1; i > 0; i--) { var j = Math.floor(r() * (i + 1)), t = arr[i]; arr[i] = arr[j]; arr[j] = t; } return arr; };
    return r;
  };

  /* ============================== 数学小工具 ============================== */
  Lab.fmt = function (x, d) {
    if (!isFinite(x)) return String(x);
    if (d == null) d = 3;
    var s = x.toFixed(d);
    if (s.indexOf('.') >= 0) s = s.replace(/0+$/, '').replace(/\.$/, '');
    return s === '-0' ? '0' : s;
  };
  Lab.big = function (n) { return String(Math.round(n)).replace(/\B(?=(\d{3})+(?!\d))/g, ','); };
  Lab.gcd = function (a, b) { a = Math.abs(a); b = Math.abs(b); while (b) { var t = a % b; a = b; b = t; } return a; };
  /* 埃氏筛：返回 Uint8Array，s[i]=1 表示 i 是素数 */
  Lab.sieve = function (n) {
    var s = new Uint8Array(n + 1);
    s.fill(1); s[0] = 0; if (n >= 1) s[1] = 0;
    for (var i = 2; i * i <= n; i++) if (s[i]) for (var j = i * i; j <= n; j += i) s[j] = 0;
    return s;
  };
  Lab.isPrime = function (n) {
    if (n < 2) return false;
    if (n < 4) return true;
    if (n % 2 === 0 || n % 3 === 0) return false;
    for (var i = 5; i * i <= n; i += 6) if (n % i === 0 || n % (i + 2) === 0) return false;
    return true;
  };
  /* 模乘、模幂（超出安全整数范围时自动用 BigInt） */
  Lab.mulmod = function (a, b, m) {
    if (m < 94906265) return (a * b) % m;
    return Number((BigInt(a) * BigInt(b)) % BigInt(m));
  };
  Lab.modpow = function (a, e, m) {
    var r = 1 % m; a %= m;
    while (e > 0) { if (e & 1) r = Lab.mulmod(r, a, m); a = Lab.mulmod(a, a, m); e = Math.floor(e / 2); }
    return r;
  };
  /* 统计直方图：把 values 分到 [lo,hi) 的 nb 个格子里，返回计数数组 */
  Lab.hist = function (values, lo, hi, nb) {
    var c = new Array(nb).fill(0);
    for (var i = 0; i < values.length; i++) {
      var b = Math.floor((values[i] - lo) / (hi - lo) * nb);
      if (b >= 0 && b < nb) c[b]++;
    }
    return c;
  };
  /* 把 HTML 里的 &、<、> 转义 */
  Lab.esc = function (s) { return String(s).replace(/[&<>]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]; }); };

  /* ============================== 中文引号 ============================== */
  /* 脚本里写的直引号 "…"，在汉字语境下显示成 “…”。规则和构建脚本（tools/build.py 的 _curly_pairs）一致：
   * 只改成对的引号；引号里有汉字、或紧挨着汉字/中文标点才改；个数是奇数就不动。
   * 页面里本来就有的文字，构建时已经换好；这里管的是脚本运行时才生成、更新的文字（控件标签、读数、提示）。 */
  (function () {
    var CJK = /[\u4e00-\u9fff]/, CJKISH = /[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]/;
    var SKIP = 'code,pre,script,style,textarea,.katex';
    function zq(s) {
      var parts = s.split('"');
      if (parts.length < 3 || parts.length % 2 === 0) return s;
      var out = [parts[0]], i, inner, before, after, zh;
      for (i = 1; i < parts.length; i += 2) {
        inner = parts[i]; before = parts[i - 1]; after = parts[i + 1];
        zh = CJK.test(inner) || (before && CJKISH.test(before.slice(-1))) || (after && CJKISH.test(after.charAt(0)));
        out.push(zh ? '\u201c' + inner + '\u201d' : '"' + inner + '"');
        out.push(after);
      }
      return out.join('');
    }
    function skipped(node) { var p = node.parentNode; return !p || (p.closest && p.closest(SKIP)); }
    function fix(t) {
      var v = t.nodeValue;
      if (v.indexOf('"') < 0 || skipped(t)) return;
      var w = zq(v);
      if (w !== v) t.nodeValue = w;
    }
    function walk(root) {
      if (root.nodeType === 3) { fix(root); return; }
      if (root.nodeType !== 1 || (root.closest && root.closest(SKIP))) return;
      var tw = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null), n, list = [];
      while ((n = tw.nextNode())) if (n.nodeValue.indexOf('"') >= 0) list.push(n);
      list.forEach(fix);
    }
    function start() {
      walk(document.body);
      new MutationObserver(function (recs) {
        recs.forEach(function (r) {
          if (r.type === 'characterData') fix(r.target);
          else Array.prototype.forEach.call(r.addedNodes, walk);
        });
      }).observe(document.body, { childList: true, subtree: true, characterData: true });
    }
    if (document.body) start(); else document.addEventListener('DOMContentLoaded', start);
  })();
})();
