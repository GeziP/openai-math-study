#!/usr/bin/env node
/*
 * 公式检查：用站点自带的 KaTeX，把所有页面里的 $...$ / $$...$$ 渲染一遍，渲染不出来就报错。
 *
 * 用法：node tools/check_math.js [站点目录]        默认 _site
 * 退出码：0 全部通过；1 有公式渲染失败；2 参数/环境问题。
 *
 * 切分规则与浏览器里 auto-render 的配置完全一致（见 assets/app.js 的 renderMath）：
 *   分隔符 $$...$$（行间）和 $...$（行内）；忽略 script/style/noscript/textarea/pre/code/option 里的文字；
 *   每段连续文字单独切分，公式不能跨标签。
 * 另外检查 assets/data.js 里卡片用到的标题/摘要（它们由脚本渲染到首页和“全部问题”页）。
 */
'use strict';
const fs = require('fs');
const path = require('path');

const root = path.resolve(process.argv[2] || path.join(__dirname, '..', '_site'));
const katexPath = path.join(root, 'assets', 'katex', 'katex.min.js');
if (!fs.existsSync(katexPath)) {
  console.error('找不到 ' + katexPath + '，请先构建站点，或把站点目录作为参数传入。');
  process.exit(2);
}
const katex = require(katexPath);

const IGNORED = new Set(['script', 'noscript', 'style', 'textarea', 'pre', 'code', 'option']);
const VOID = new Set(['area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'source', 'track', 'wbr']);

/* ---- 与 KaTeX auto-render 一致的公式切分 ---- */
function findEndOfMath(delim, text, start) {
  let i = start, depth = 0;
  while (i < text.length) {
    const c = text[i];
    if (depth <= 0 && text.startsWith(delim, i)) return i;
    if (c === '\\') i++;
    else if (c === '{') depth++;
    else if (c === '}') depth--;
    i++;
  }
  return -1;
}

// 返回 { found: [{math, display}], rest: 公式以外的文字 }
function extractMath(text) {
  const found = [];
  let rest = '';
  const lefts = [{ l: '$$', r: '$$', display: true }, { l: '$', r: '$', display: false }];
  while (true) {
    let at = -1;
    let d = null;
    for (const cand of lefts) {            // 同一位置 $$ 先于 $，与 auto-render 的正则交替顺序一致
      const i = text.indexOf(cand.l);
      if (i !== -1 && (at === -1 || i < at)) { at = i; d = cand; }
    }
    if (at === -1) break;
    rest += text.slice(0, at);
    text = text.slice(at);
    const end = findEndOfMath(d.r, text, d.l.length);
    if (end === -1) break;                  // 没有闭合：auto-render 也是就此停手，剩下的当普通文字
    found.push({ math: text.slice(d.l.length, end), display: d.display });
    text = text.slice(end + d.r.length);
  }
  return { found, rest: rest + text };
}

/* ---- HTML → 文字段（跳过忽略的标签与脚本） ---- */
const ENT = { amp: '&', lt: '<', gt: '>', quot: '"', apos: "'", nbsp: '\u00a0' };
function decode(s) {
  return s.replace(/&(#x[0-9a-fA-F]+|#\d+|[a-zA-Z]+);/g, (m, g) => {
    if (g[0] === '#') {
      const code = g[1] === 'x' || g[1] === 'X' ? parseInt(g.slice(2), 16) : parseInt(g.slice(1), 10);
      return Number.isFinite(code) ? String.fromCodePoint(code) : m;
    }
    return Object.prototype.hasOwnProperty.call(ENT, g) ? ENT[g] : m;
  });
}

function textSegments(html) {
  const segs = [];
  const lower = html.toLowerCase();
  const re = /<!--[\s\S]*?-->|<(\/?)([a-zA-Z][\w:-]*)((?:"[^"]*"|'[^']*'|[^'">])*)>|([^<]+|<)/g;
  const stack = [];                         // 当前处于哪些“忽略标签”里
  let m;
  let prevText = false;                     // 上一个记号是不是文字（相邻的文字属于同一个文本节点）
  while ((m = re.exec(html)) !== null) {
    if (m[4] !== undefined) {               // 文字；孤立的 "<"（如 "|x|<1"）浏览器也当作文字，要并进同一节点
      if (!stack.length) {
        if (prevText) segs[segs.length - 1] += decode(m[4]);
        else segs.push(decode(m[4]));
      }
      prevText = true;
      continue;
    }
    prevText = false;
    if (m[2] === undefined) continue;       // 注释
    const closing = m[1] === '/';
    const tag = m[2].toLowerCase();
    if ((tag === 'script' || tag === 'style') && !closing) {
      const close = lower.indexOf('</' + tag, re.lastIndex);
      re.lastIndex = close === -1 ? html.length : close;   // 脚本/样式内容整体跳过
      continue;
    }
    if (!IGNORED.has(tag) || VOID.has(tag)) continue;
    if (closing) { const k = stack.lastIndexOf(tag); if (k !== -1) stack.length = k; }
    else if (!/\/\s*$/.test(m[3])) stack.push(tag);
  }
  return segs;
}

/* ---- 检查 ---- */
const cache = new Map();
let total = 0;
const bad = [];

function check(where, math, display) {
  const key = (display ? 'D' : 'I') + math;
  total++;
  if (!cache.has(key)) {
    let err = '';
    try {
      katex.renderToString(math, { displayMode: display, throwOnError: true, strict: 'ignore' });
    } catch (e) {
      err = String(e && e.message ? e.message : e).replace(/\s+/g, ' ').slice(0, 200);
    }
    cache.set(key, err);
  }
  const err = cache.get(key);
  if (err) bad.push({ where, math: math.length > 90 ? math.slice(0, 90) + '…' : math, err });
}

// 处理一段文字：渲染其中的公式；若公式以外的文字里还残留 $，说明有没闭合的公式，会以原样显示在页面上
function checkText(where, text) {
  const { found, rest } = extractMath(text);
  for (const x of found) check(where, x.math, x.display);
  if (rest.includes('$')) {
    const i = rest.indexOf('$');
    total++;
    bad.push({ where, math: rest.slice(Math.max(0, i - 20), i + 40), err: '残留的 $：公式没有闭合（或花括号不配对），页面上会显示成原始文字' });
  }
}

function walk(dir, out) {
  for (const name of fs.readdirSync(dir)) {
    if (name === 'katex') continue;         // 跳过 KaTeX 自己的文件
    const full = path.join(dir, name);
    const st = fs.statSync(full);
    if (st.isDirectory()) walk(full, out);
    else if (name.endsWith('.html')) out.push(full);
  }
  return out;
}

const files = walk(root, []);
for (const f of files) {
  const rel = path.relative(root, f).split(path.sep).join('/');
  for (const seg of textSegments(fs.readFileSync(f, 'utf8'))) checkText(rel, seg);
}

const dataJs = path.join(root, 'assets', 'data.js');
let cardTexts = 0;
if (fs.existsSync(dataJs)) {
  const src = fs.readFileSync(dataJs, 'utf8');
  const j = src.slice(src.indexOf('{'), src.lastIndexOf('}') + 1);
  const data = JSON.parse(j);
  for (const it of data.items || []) {
    for (const k of ['zh', 'en', 'tl']) {
      if (typeof it[k] !== 'string') continue;
      cardTexts++;
      checkText('data.js 卡片 ' + it.id + '.' + k, it[k]);
    }
  }
}

console.log('公式检查：%d 个页面、%d 段卡片文字，共 %d 处公式（去重后 %d 种），失败 %d 处。',
  files.length, cardTexts, total, cache.size, bad.length);
if (bad.length) {
  for (const b of bad.slice(0, 40)) console.log('  ✗ [%s] %s\n      %s', b.where, b.math, b.err);
  if (bad.length > 40) console.log('  …… 还有 %d 处', bad.length - 40);
  process.exit(1);
}
