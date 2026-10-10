#!/usr/bin/env python3
"""构建「数学小白导览」静态站点。

用法
    python tools/build.py                   # 构建到 _site/ 并校验
    python tools/build.py --strict          # 有任何警告也以非 0 退出（CI 用）
    python tools/build.py --out DIR         # 输出目录（默认 _site/）
    python tools/build.py --site-url URL    # 站点上线后的根地址（以 / 结尾）：写入 canonical / 分享图 / sitemap。
                                            #   填 auto：按环境变量 GITHUB_REPOSITORY 推出 https://<owner>.github.io/<repo>/
                                            #   不填：纯相对路径的离线版（可直接双击 index.html，也能放进任意子路径）

输入
    data/families.json      上游家族与论文（tools/sync_upstream.py 生成）
    data/upstream.json      对应的上游提交（同上）
    src/*.txt               指导 / 词汇表 / 学科导读（手写）
    src/*.html              路线图等整页片段
    labs_src/lab-*.html     互动实验的中间片段
    assets/                 样式、脚本、KaTeX（原样拷贝）
输出
    _site/index.html  problems.html  subjects.html  roadmap.html  glossary.html  about.html  404.html
    _site/p/NNN.html（每个结果家族一页）  s/N.html（每个学科一页）  labs/*.html  art/*.svg
    _site/sitemap.xml  robots.txt（仅在给了 --site-url 时）
"""
import argparse
import datetime
import filecmp
import glob
import html
import json
import os
import re
import shutil
import sys
from urllib.parse import quote

HERE = os.path.dirname(os.path.abspath(__file__))
SG = os.path.abspath(os.path.join(HERE, ".."))          # 仓库根目录（源文件所在）
sys.path.insert(0, HERE)
try:
    import art  # 学科配图（程序化生成的 SVG）
except Exception:  # 配图是锦上添花，缺失时退回 emoji
    art = None

STRICT = False
WARN = []
OUT = os.path.join(SG, "_site")        # 输出目录，main() 里按 --out 覆盖
SITE_URL = ""                          # 线上根地址（以 / 结尾）；空 = 离线版
REPO = os.environ.get("GITHUB_REPOSITORY", "GeziP/openai-math-study")
REPO_URL = "https://github.com/" + REPO
UPSTREAM = "openai/math"
UP_URL = "https://github.com/" + UPSTREAM
UP_BLOB = UP_URL + "/blob/main/"       # 上游文件的网页地址前缀
UP = {}                                # data/upstream.json 的内容，main() 里读入
BUILD_DATE = datetime.datetime.now().astimezone().strftime("%Y-%m-%d")   # 取自系统时钟，不写死
SITE_DESC = ""                         # 站点简介（main() 里按实际数量生成）


def warn(msg):
    WARN.append(msg)
    print("  [WARN] " + msg)


# ----------------------------------------------------------------------------
# 常量
# ----------------------------------------------------------------------------
SUBJECT_META = {  # id: (中文名, 图标)
    1: ("数论", "🔢"), 2: ("代数", "🧩"), 3: ("代数几何与复几何", "🍩"), 4: ("拓扑", "🌀"),
    5: ("群论", "🔄"), 6: ("数理逻辑", "🧠"), 7: ("微分几何", "🌐"), 8: ("凸几何与度量几何", "🔷"),
    9: ("偏微分方程", "🌊"), 10: ("实分析与复分析", "📈"), 11: ("泛函分析", "🎛️"), 12: ("动力系统与遍历论", "🔁"),
    13: ("组合学", "🧮"), 14: ("理论计算机科学", "💻"), 15: ("概率与统计力学", "🎲"), 16: ("算子代数", "🧱"),
    17: ("数学物理", "⚛️"),
}
LV_TEXT = {
    1: "初高中就能看懂问题本身",
    2: "高中 + 一点点大学数学",
    3: "大学数学专业本科水平",
    4: "研究生课程水平",
    5: "需要某个研究方向的专门训练",
}
LAB_META = {  # id: (标题, 图标, 一句话)
    "primes": ("素数与素数间隔", "🔍", "用筛法画出素数，观察素数计数 π(x) 与 x/ln x、相邻素数间隔的分布。"),
    "liouville": ("刘维尔函数：抛硬币般的符号", "🪙", "把每个整数标上 ±1，看它的累加和像不像随机游走，并检验相邻项的相关性。"),
    "convergents": ("连分数：最佳分数逼近", "📐", "把 π、e、√2 等一步步化成越来越好的分数，看误差随分母怎样变小。"),
    "egyptian": ("埃及分数分解器", "🏺", "输入任意分数，用贪心法拆成不同的单位分数之和。"),
    "gaussian": ("高斯素数护城河", "🏝️", "在复平面上画高斯素数，设定步长，看你能从原点走多远。"),
    "modpow": ("原根与模幂转圈", "🎡", "看 a 的各次幂模 p 如何绕圈；能走遍所有刻度的 a 就是原根。"),
    "elliptic": ("椭圆曲线上的弦切法加法", "🍩", "拖动两点，看连线与曲线的第三个交点如何给出点的加法。"),
    "ramsey": ("拉姆齐游戏：六个人里必有三人互相认识或互相不认识", "🎨", "给完全图的边涂两种颜色，看能不能避免同色三角形。"),
    "heilbronn": ("海尔布朗三角形", "📍", "在单位正方形里放点，让最小的三角形尽可能大。"),
    "randomwalk": ("随机游走", "🚶", "观察二维随机游走的轨迹，以及走了 n 步后离原点的典型距离。"),
    "ising": ("伊辛模型：磁铁与温度", "🧲", "拉动温度滑块，观察自旋如何从有序走向无序，并在临界点附近出现大尺度结构。"),
    "chaos": ("混沌游戏：自相似图形", "🔺", "随机地朝几个顶点跳，竟能画出谢尔宾斯基三角形等分形。"),
    "maxcut": ("最大割游戏", "✂️", "把图的顶点染成两种颜色，让两端异色的边越多越好。"),
    "totient": ("欧拉函数的散点图", "✳️", "画出 φ(n)，看哪些值取得到、哪些取不到。"),
    "ap3": ("没有三项等差数列的集合", "🔢", "在 1..N 里挑尽量多的数，使其中不含三项等差数列。"),
    "fourier": ("傅里叶合成器：用正弦波拼出方波", "🎼", "一项一项加上正弦波，看部分和怎样逼近方波；对比“一刀切”与“渐变截断”的差别。"),
    "littlewood": ("±1 序列的平坦度", "📡", "输入一串 +1/−1，画出它在单位圆上的大小曲线，并计算品质因数；试试 Barker 码。"),
    "mahler": ("正多边形与它的对偶：体积乘积", "🔷", "拖动边数，看正多边形 K 与极体 K° 的面积之积如何从三角形的 6.75 走向圆的 π²。"),
    "latticeenergy": ("格点能量地图：谁是最放松的队形？", "🐝", "在所有二维格点里扫描排斥能量，看谷底是否总落在蜂窝（三角）晶格上。"),
    "propeller": ("螺旋桨游戏：分割高斯云", "🌀", "把圆分成几块扇形，计算各块重心长度的平方和，看谁最大。"),
    "editdist": ("编辑距离计算器", "✏️", "输入两个词，看动态规划表怎样一格一格算出最少的插入、删除、替换次数。"),
    "matmul": ("矩阵乘法：Strassen 的 7 次乘法", "🧮", "验证 2×2 矩阵只需 7 次乘法，并比较 n³、n^2.807、n^2.371、n^2.25 的增长。"),
    "subsetsum": ("子集和：折半相遇", "💰", "给一组数和目标值，看暴力枚举与“折半相遇”各需要检查多少种组合。"),
    "courtade": ("噪声里的信息：谁保留得最多？", "📞", "枚举所有 3～4 位的布尔函数，计算它们经过噪声后的互信息，看谁是冠军。"),
    "wl": ("颜色细化：Weisfeiler–Leman", "🎨", "对一个图反复做“按邻居重新着色”，看哪些图一直无法被区分。"),
    "superstring": ("最短公共超串", "🧬", "输入几个短词，穷举所有排列，找出最短的、包含它们全部的字符串。"),
    "vdp": ("极限环：范德波尔振子", "💓", "从不同起点出发，看轨道如何都盘旋着靠近同一条闭曲线；调节非线性强度 μ。"),
    "catmap": ("猫映射：把图片搅匀", "🐱", "反复用 Arnold 猫映射拉伸并折叠一张图片，看它如何被“搅匀”，又在若干步后回到原样。"),
    "standardmap": ("标准映射：规则与混沌共存", "🎯", "拖动踢力强度 K，看相图从规则的“岛链”逐渐被混沌海淹没。"),
    "billiard": ("台球桌：圆、椭圆与三角形", "🎱", "选择桌面形状，射出一颗球，看路径是否出现整齐的焦散线。"),
    "bernoulli": ("伯努利卷积：±λⁿ 的随机和", "🎲", "调节 λ，画出随机和 Σ±λⁿ 的分布，对比光滑与“尘埃”两种形态。"),
    "vdw": ("范德瓦尔登游戏：给数字涂两种颜色", "🔴", "给 1…N 涂红蓝两色，看能否避免同色的三项等差数列。"),
    "crossing": ("交叉数游戏：把完全图画得交叉最少", "🕸️", "拖动顶点，让 K₅、K₆、K₃,₃ 等图的边交叉尽量少，并与公式对比。"),
    "trianglerem": ("随机删三角形", "🧹", "在完全图上反复随机删去一个三角形，看最后还剩多少条边。"),
    "percolation": ("渗流：咖啡粉里的水路", "☕", "拖动打通概率 p，看方格网里的连通团何时突然贯穿整个区域（临界值约 0.5）。"),
    "fpp": ("首次通过渗流：随机路费下的“球”", "🗺️", "给每条边随机的通行时间，用 Dijkstra 算法长出一个随机的“球”，并画出最快路线。"),
    "sat": ("随机 3-SAT：约束多了就无解", "🧩", "随机生成逻辑约束，看“有解”的比例如何随约束密度突然下跌（阈值约 4.27）。"),
    "shuffle": ("洗牌：几次才算洗匀？", "🃏", "观察 Thorp 洗牌与鸽尾式洗牌，看牌的位置分布如何一步步趋于均匀。"),
    "signmatrix": ("±1 矩阵什么时候奇异？", "🧱", "枚举或抽样随机的对称 ±1 矩阵，数出行列式为 0 的比例如何随 n 指数下降。"),
}
STAGE_CLS = [("小学", 0), ("初中", 0), ("高中", 0), ("大一", 1), ("大二", 1), ("本科", 2), ("大三", 2), ("大四", 2),
             ("研究生", 3), ("研究", 4), ("前沿", 4)]


def stage_cls(label):
    for k, c in STAGE_CLS:
        if label.startswith(k):
            return c
    return 2


# ----------------------------------------------------------------------------
# 文本工具
# ----------------------------------------------------------------------------
def esc(s):
    return html.escape(s, quote=True)


_MATH_RE = re.compile(r"\$\$[\s\S]+?\$\$|\$(?:\\.|[^$\\])+?\$")


def rich(s):
    """转义并支持 **粗体**、`代码`、[文字](链接)；$公式$ 原样保留给 KaTeX（公式里的 ** ` [ 等符号不会被当成标记，例如 $X^{**}$）。"""
    s = html.escape(s, quote=False)
    maths = []

    def stash(m):
        maths.append(m.group(0))
        return "\ue000%d\ue001" % (len(maths) - 1)

    s = _MATH_RE.sub(stash, s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2" target="_blank" rel="noopener">\1</a>', s)
    return re.sub("\ue000(\\d+)\ue001", lambda m: maths[int(m.group(1))], s)


def url_path(p):
    return "/".join(quote(seg) for seg in p.split("/"))


def has_cjk(s):
    return re.search(r"[\u4e00-\u9fff]", s) is not None


# --- 直引号 → 中文弯引号 ---------------------------------------------------------
# 作者在源文件里照常写 "…"，构建时统一换成 “…”（汉字文本里直引号很难看）。
# 规则：宁可少改，不可乱改——只处理成对的引号，且引号里至少有一个汉字；
# 引号个数是奇数（比如 5" 表示英寸）就整段原样返回，免得后面全部错位。
_CJKISH = re.compile(r"[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]")      # 汉字、中文标点、全角符号


def _curly_pairs(s):
    """成对的 "…" 换成 “…”，条件：引号里有汉字，或者紧挨着引号外面的字符是汉字/中文标点（即整句是中文，
    引号里只引了个 $公式$、英文词、符号也要用中文引号）。纯英文句子里的引号不动。"""
    parts = s.split('"')
    if len(parts) < 3 or len(parts) % 2 == 0:
        return s
    out = [parts[0]]
    for i in range(1, len(parts), 2):
        inner, before, after = parts[i], parts[i - 1], parts[i + 1]
        zh = has_cjk(inner) or bool(before and _CJKISH.match(before[-1])) or bool(after and _CJKISH.match(after[0]))
        out.append("\u201c%s\u201d" % inner if zh else '"%s"' % inner)
        out.append(after)
    return "".join(out)


def curly_quotes(s):
    """源文件里一个字段的值（纯文本 + $公式$）：公式先藏起来，公式里的引号不动；公式之外还有 < 的当作 HTML，原样返回。"""
    if '"' not in s:
        return s
    maths = []

    def stash(m):
        maths.append(m.group(0))
        return "\ue000%d\ue001" % (len(maths) - 1)

    t = _MATH_RE.sub(stash, s)
    if "<" in t:
        return s
    return re.sub("\ue000(\\d+)\ue001", lambda m: maths[int(m.group(1))], _curly_pairs(t))


# 整页 HTML：只改正文文本里的引号。标签（含属性）、script/style/pre/code/textarea、注释、公式都不动。
_PROTECT_RE = re.compile(r"<script\b[\s\S]*?</script>|<style\b[\s\S]*?</style>|<pre\b[\s\S]*?</pre>|<code\b[\s\S]*?</code>"
                         r"|<textarea\b[\s\S]*?</textarea>|<!--[\s\S]*?-->", re.I)
_TAG_RE = re.compile(r"<(/?)([A-Za-z][A-Za-z0-9-]*)\b(?:[^<>\"']|\"[^\"]*\"|'[^']*')*>")
_BLOCK_TAGS = frozenset(("html head body title meta link base main header footer nav aside section article div p ul ol li dl dt dd "
                         "h1 h2 h3 h4 h5 h6 br hr table thead tbody tfoot tr td th figure figcaption blockquote details summary "
                         "form label button select option input canvas svg fieldset legend").split())


def curly_html(h):
    if '"' not in h:
        return h
    keep = []

    def hide(m):
        keep.append(m.group(0))
        return "\ue002%d\ue003" % (len(keep) - 1)

    t = _MATH_RE.sub(hide, _PROTECT_RE.sub(hide, h))
    out, run, pos = [], [], 0

    def flush():
        if run:
            out.append(_curly_pairs("".join(run)))
            run.clear()

    for m in _TAG_RE.finditer(t):
        run.append(t[pos:m.start()])
        if m.group(2).lower() in _BLOCK_TAGS:
            flush()                     # 块级标签：这里断开，引号不跨段落配对
            out.append(m.group(0))
        else:
            run.append(hide(m))         # 行内标签：藏成占位符，引号可以隔着 <b>…</b> 配对
        pos = m.end()
    run.append(t[pos:])
    flush()
    res = "".join(out)
    for _ in range(4):                  # 占位符里可能还套着占位符（公式里夹着 code 之类），逐层还原
        if "\ue002" not in res:
            break
        res = re.sub("\ue002(\\d+)\ue003", lambda m: keep[int(m.group(1))], res)
    return res


# ----------------------------------------------------------------------------
# 读取源文件
# ----------------------------------------------------------------------------
KEEP_QUOTES = {"kw", "lv", "lab"}   # 搜索词、等级、实验 id：不是给人读的正文，引号保持原样


def parse_blocks(path):
    blocks, cur = [], None
    with open(path, encoding="utf-8") as f:
        for ln, line in enumerate(f, 1):
            line = line.rstrip("\n")
            if line.startswith("## "):
                cur = {"id": line[3:].strip(), "f": {}, "file": os.path.basename(path), "line": ln}
                blocks.append(cur)
            elif cur is not None and line.strip() and not line.startswith("#"):
                m = re.match(r"^([a-z_]+):\s?(.*)$", line)
                if not m:
                    warn("%s:%d 无法解析的行: %s" % (os.path.basename(path), ln, line[:40]))
                    continue
                if m.group(1) in cur["f"]:
                    warn("%s:%d 重复字段 %s（块 %s）" % (os.path.basename(path), ln, m.group(1), cur["id"]))
                val = m.group(2).strip()
                if m.group(1) not in KEEP_QUOTES:
                    val = curly_quotes(val)
                cur["f"][m.group(1)] = val
    return blocks


def load_sources():
    guides, gloss, prim = {}, {}, {}
    for path in sorted(glob.glob(os.path.join(SG, "src", "*.txt"))):
        for b in parse_blocks(path):
            i = b["id"]
            if re.fullmatch(r"\d{3}", i):
                if i in guides:
                    warn("重复的指导 %s（%s 与 %s）" % (i, guides[i]["file"], b["file"]))
                guides[i] = b
            elif i.startswith("subject:"):
                prim[int(i.split(":")[1])] = b
            elif re.fullmatch(r"[A-Za-z0-9_]+", i):
                if i in gloss:
                    warn("重复的词条 %s" % i)
                gloss[i] = b
            else:
                warn("无法识别的块标题 %r（%s:%d）" % (i, b["file"], b["line"]))
    return guides, gloss, prim


def split_items(s):
    return [x.strip() for x in s.split(";;") if x.strip()]


REQ = ["zh", "lv", "tl", "ask", "ana", "need", "why", "path", "kw"]


def validate(fams, guides, gloss):
    ids = [f["id"] for f in fams]
    missing = [i for i in ids if i not in guides]
    if missing:
        warn("缺少指导 %d 个：%s%s" % (len(missing), " ".join(missing[:12]), " …" if len(missing) > 12 else ""))
    for i in guides:
        if i not in ids:
            warn("指导 %s 对应的家族不存在" % i)
    used = {}
    for i, g in guides.items():
        f = g["f"]
        for k in REQ:
            if not f.get(k):
                warn("%s 缺少字段 %s" % (i, k))
        if f.get("lv") and not re.fullmatch(r"[1-5]", f["lv"]):
            warn("%s 的 lv 非法: %s" % (i, f["lv"]))
        for it in split_items(f.get("need", "")):
            if it.startswith("@"):
                k = it[1:].strip()
                used.setdefault(k, []).append(i)
                if k not in gloss:
                    warn("%s 引用了不存在的词条 @%s" % (i, k))
            elif "｜" not in it:
                warn("%s 的 need 项缺少 ｜ 说明：%s" % (i, it[:30]))
        for it in split_items(f.get("path", "")):
            if "｜" not in it:
                warn("%s 的 path 项缺少 ｜ ：%s" % (i, it[:30]))
        if len(split_items(f.get("path", ""))) < 3:
            warn("%s 的学习路径少于 3 步" % i)
        if len(split_items(f.get("need", ""))) < 2:
            warn("%s 的先备积木少于 2 项" % i)
        for fld in ("tl", "ask", "ana", "why", "how", "warn"):
            v = f.get(fld, "")
            if ";;" in v or "｜" in v:
                warn("%s 的字段 %s 含保留分隔符" % (i, fld))
        if f.get("lab") and f["lab"] not in LAB_META:
            warn("%s 引用了未登记的实验 %s" % (i, f["lab"]))
    for k, g in gloss.items():
        for fld in ("zh", "short", "long"):
            if not g["f"].get(fld):
                warn("词条 %s 缺少 %s" % (k, fld))
        if g["f"].get("lab") and g["f"]["lab"] not in LAB_META:
            warn("词条 %s 引用了未登记的实验 %s" % (k, g["f"]["lab"]))
    return used


# ----------------------------------------------------------------------------
# 页面骨架
# ----------------------------------------------------------------------------
NAV = [("index.html", "首页", "home"), ("problems.html", "全部问题", "problems"), ("roadmap.html", "学习路线", "roadmap"),
       ("subjects.html", "学科", "subjects"), ("glossary.html", "词汇表", "glossary"), ("labs/index.html", "实验室", "labs"),
       ("about.html", "关于", "about")]


_GREEK_NAMES = ("alpha beta gamma delta epsilon varepsilon zeta eta theta vartheta iota kappa lambda mu nu xi pi rho sigma tau "
                "upsilon phi varphi chi psi omega Gamma Delta Theta Lambda Xi Pi Sigma Phi Psi Omega").split()
_GREEK_CHARS = "αβγδεεζηθϑικλμνξπρστυφφχψω" "ΓΔΘΛΞΠΣΦΨΩ"
assert len(_GREEK_NAMES) == len(_GREEK_CHARS)
_TEX_GREEK = dict(zip(_GREEK_NAMES, _GREEK_CHARS))
_TEX_SYM = {
    "times": "×", "cdot": "·", "pm": "±", "mp": "∓", "le": "≤", "leq": "≤", "ge": "≥", "geq": "≥", "ne": "≠", "neq": "≠",
    "approx": "≈", "equiv": "≡", "cong": "≅", "sim": "∼", "simeq": "≃", "to": "→", "rightarrow": "→", "longrightarrow": "→",
    "leftarrow": "←", "Rightarrow": "⇒", "Leftrightarrow": "⇔", "iff": "⇔", "mapsto": "↦", "in": "∈", "notin": "∉",
    "subset": "⊂", "subseteq": "⊆", "supset": "⊃", "cup": "∪", "cap": "∩", "infty": "∞", "partial": "∂", "nabla": "∇",
    "sum": "∑", "prod": "∏", "int": "∫", "ldots": "…", "dots": "…", "cdots": "…", "forall": "∀", "exists": "∃",
    "emptyset": "∅", "varnothing": "∅", "mid": "|", "setminus": "∖", "ell": "ℓ", "hbar": "ℏ", "langle": "⟨", "rangle": "⟩",
    "lfloor": "⌊", "rfloor": "⌋", "lceil": "⌈", "rceil": "⌉", "oplus": "⊕", "otimes": "⊗", "circ": "∘", "wedge": "∧",
    "vee": "∨", "neg": "¬", "star": "⋆", "ast": "∗", "prime": "′", "ll": "≪", "gg": "≫", "propto": "∝", "perp": "⊥",
    "angle": "∠", "bullet": "•", "colon": ":", "lt": "<", "gt": ">", "quad": " ", "qquad": " ",
}
_TEX_DROP = {"left", "right", "big", "Big", "bigg", "Bigg", "limits", "displaystyle", "textstyle"}
_TEX_WRAP = {"mathcal", "mathrm", "mathbf", "mathit", "mathsf", "mathfrak", "mathscr", "mathtt", "text", "textbf", "textit",
             "operatorname", "boldsymbol", "bm", "mathop", "overline", "underline", "hat", "widehat", "tilde", "widetilde",
             "bar", "vec", "dot", "ddot"}
_TEX_OPS = set("log ln lg sin cos tan cot sec csc arcsin arccos arctan sinh cosh tanh exp lim liminf limsup sup inf max min "
               "gcd det dim ker deg arg Pr Re Im mod Hom End Aut rank tr".split())
_TEX_BB = dict(zip("NZQRCPFAHGEKSTDB", "ℕℤℚℝℂℙ𝔽𝔸ℍ𝔾𝔼𝕂𝕊𝕋𝔻𝔹"))
_SUP_FROM, _SUP_TO = "0123456789+-=()ni", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿⁱ"
_SUB_FROM, _SUB_TO = "0123456789+-=()aehijklmnoprstuvx", "₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎ₐₑₕᵢⱼₖₗₘₙₒₚᵣₛₜᵤᵥₓ"
assert len(_SUP_FROM) == len(_SUP_TO) and len(_SUB_FROM) == len(_SUB_TO) and len(_TEX_BB) == 16


def tex_plain(t):
    """把一小段 LaTeX 转成大致可读的纯文本（给 <title> / <meta> 用，不求严格）。读不懂的复杂结构返回 "…"。"""
    if "\\begin" in t or "\\array" in t:
        return "…"
    n = len(t)

    def arg(i):
        """读一个参数：{…} 或单个记号；返回 (文本, 下一个位置)。"""
        while i < n and t[i] == " ":
            i += 1
        if i >= n:
            return "", i
        if t[i] == "{":
            depth, j = 0, i
            while j < n:
                if t[j] == "\\":
                    j += 2
                    continue
                if t[j] == "{":
                    depth += 1
                elif t[j] == "}":
                    depth -= 1
                    if depth == 0:
                        return t[i + 1:j], j + 1
                j += 1
            return t[i + 1:], n
        if t[i] == "\\":
            m = re.match(r"\\(?:[A-Za-z]+|.)", t[i:])
            if not m:
                return "\\", i + 1
            return m.group(0), i + len(m.group(0))
        return t[i], i + 1

    def simple(x):
        return len(x) <= 1 or re.fullmatch(r"[A-Za-z0-9]+|\([^()]*\)", x) is not None

    def script(sub, i):
        a, j = arg(i)
        inner = conv(a)
        frm, to = (_SUB_FROM, _SUB_TO) if sub else (_SUP_FROM, _SUP_TO)
        if inner and all(c in frm for c in inner):
            return inner.translate(str.maketrans(frm, to)), j
        mark = "_" if sub else "^"
        return mark + (inner if len(inner) <= 1 else "(" + inner + ")"), j

    def conv(s):
        nonlocal t, n
        saved = (t, n)
        t, n = s, len(s)
        out, i = [], 0
        while i < n:
            c = t[i]
            if c == "\\":
                m = re.match(r"\\([A-Za-z]+)", t[i:])
                if not m:                                   # \, \; \! \{ \} \\ \% 等
                    d = t[i + 1] if i + 1 < n else ""
                    i += 2
                    out.append({",": " ", ";": " ", ":": " ", "!": "", " ": " ", "\\": " ", "|": "‖"}.get(d, d))
                    continue
                name = m.group(1)
                i += len(m.group(0))
                while i < n and t[i] == " ":                # 控制序列后面的空格被 TeX 吞掉
                    i += 1
                if name in ("frac", "dfrac", "tfrac"):
                    a, i = arg(i)
                    b, i = arg(i)
                    a, b = conv(a), conv(b)
                    out.append("%s/%s" % (a if simple(a) else "(" + a + ")", b if simple(b) else "(" + b + ")"))
                elif name == "binom":
                    a, i = arg(i)
                    b, i = arg(i)
                    out.append("C(%s,%s)" % (conv(a), conv(b)))
                elif name == "sqrt":
                    idx = ""
                    if i < n and t[i] == "[":
                        k = t.find("]", i)
                        idx = conv(t[i + 1:k]) if k != -1 else ""
                        i = k + 1 if k != -1 else n
                    a, i = arg(i)
                    a = conv(a)
                    out.append(idx.translate(str.maketrans(_SUP_FROM, _SUP_TO)) + "√" + (a if simple(a) else "(" + a + ")"))
                elif name == "mathbb":
                    a, i = arg(i)
                    out.append("".join(_TEX_BB.get(ch, ch) for ch in conv(a)))
                elif name == "operatorname" or name in _TEX_OPS:
                    if name == "operatorname":
                        a, i = arg(i)
                        name = conv(a)
                    if out and out[-1][-1:].isalnum():          # L\log L → "L log L"
                        out.append(" ")
                    out.append(name)
                    if i < n and (t[i].isalnum() or t[i] in "\\{"):
                        out.append(" ")
                elif name in _TEX_WRAP:
                    a, i = arg(i)
                    out.append(conv(a))
                elif name in _TEX_GREEK:
                    out.append(_TEX_GREEK[name])
                elif name in _TEX_SYM:
                    out.append(_TEX_SYM[name])
                elif name in _TEX_DROP:
                    pass
                else:
                    out.append(name)
                continue
            if c in "^_":
                s2, i = script(c == "_", i + 1)
                out.append(s2)
                continue
            if c in "{}$":
                i += 1
                continue
            out.append(" " if c == "~" else c)
            i += 1
        t, n = saved
        return "".join(out)

    return re.sub(r"\s+", " ", conv(t)).strip()


def plain(s, limit=0):
    """去掉公式标记和简单 Markdown，得到可放进 <title> / <meta description> 的纯文本（公式转成近似的 Unicode 写法）。"""
    def m(mo):
        out = tex_plain(mo.group(0).strip("$"))
        return out if len(out) <= 48 else "…"
    s = re.sub(r"\$\$[\s\S]+?\$\$|\$(?:\\.|[^$\\])+?\$", m, s)
    s = re.sub(r"\*\*(.+?)\*\*", r"\1", s)
    s = re.sub(r"`([^`]+)`", r"\1", s)
    s = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", s)
    s = re.sub(r"\s+", " ", s).strip()
    return (s[:limit - 1].rstrip() + "…") if limit and len(s) > limit else s


def up_date():
    """上游提交日期（UTC，YYYY-MM-DD）。"""
    d = UP.get("commit_date", "")
    try:
        return datetime.datetime.fromisoformat(d).astimezone(datetime.timezone.utc).strftime("%Y-%m-%d")
    except ValueError:
        return d[:10]


def up_stamp(link=True):
    """「对应上游 openai/math@fd4aeeb（上游提交于 …）· 同步于 …」；没有 upstream.json 时返回空串。"""
    c = UP.get("commit", "")
    if not c:
        return ""
    ver = "openai/math@" + c[:7]
    if link:
        ver = '<a href="%s/commit/%s" target="_blank" rel="noopener">%s</a>' % (UP_URL, c, ver)
    return "对应上游 %s（上游提交于 %s）· 同步于 %s" % (ver, up_date(), UP.get("synced_at", BUILD_DATE))


def issue_url(template="correction.yml", title="", page=""):
    q = "template=" + template
    if title:
        q += "&title=" + quote(title)
    if page:
        q += "&page=" + quote(page, safe="")
    return REPO_URL + "/issues/new?" + q


def footer_html(base):
    return """<footer><div class="wrap">
<p>本站是对上游 <a href="%(up)s" target="_blank" rel="noopener">openai/math</a> 中研究论文的<strong>阅读指导</strong>，<strong>非 OpenAI 官方</strong>，与 OpenAI 无关联。论文由 OpenAI 内部模型生成；上游说明这些结果处于不同的验证阶段，并非都有 Lean 形式化，没有形式化的部分可能有问题。本站不对论文证明的正确性做担保。</p>
<p>本站的指导由 AI 辅助撰写，经过自动化检查（链接、公式、结构），<strong>没有人工逐篇审校</strong>，难免有错：<a href="%(issues)s" target="_blank" rel="noopener">发现问题请告诉我们</a>。</p>
<p class="foot-meta">%(stamp)s · 页面构建于 %(date)s。文中“至今”“目前”“近年”这类说法，以这个日期前后为准，详见<a href="%(base)sabout.html">关于</a>。<br>
文字 CC BY 4.0 · 代码 MIT · <a href="%(repo)s" target="_blank" rel="noopener">源码</a> · <a href="%(repo)s/releases/latest" target="_blank" rel="noopener">离线版</a> · <a href="%(base)sabout.html#license">许可与署名</a></p>
</div></footer>""" % {"up": UP_URL, "issues": issue_url(), "stamp": up_stamp(), "date": BUILD_DATE, "base": base, "repo": REPO_URL}


def layout(title, body, base="", active="", extra_head="", subj_hue=None, desc="", path=None, base_href=""):
    """path：本页相对站点根的路径（如 p/001.html；首页传 ""），给 canonical / og:url 用；base_href 仅 404 页使用。"""
    nav = "".join('<a href="%s%s"%s>%s</a>' % (base, h, ' class="on"' if k == active else "", t) for h, t, k in NAV)
    style = ' style="--sc:hsl(%d 62%% 48%%)"' % subj_hue if subj_hue is not None else ""
    d = esc(plain(desc or SITE_DESC, 140))
    title = plain(title)            # 标签页标题 / 分享标题里不放 LaTeX 源码，转成近似的 Unicode 写法
    head = []
    if base_href:
        head.append('<base href="%s">' % esc(base_href))
    head.append('<meta name="description" content="%s">' % d)
    head.append('<meta name="theme-color" content="#4f5bd5">')
    head.append('<link rel="icon" href="%sassets/favicon.svg" type="image/svg+xml">' % base)
    head.append('<link rel="apple-touch-icon" href="%sassets/apple-touch-icon.png">' % base)
    head.append('<meta property="og:type" content="website"><meta property="og:site_name" content="数学小白导览"><meta property="og:locale" content="zh_CN">')
    head.append('<meta property="og:title" content="%s"><meta property="og:description" content="%s">' % (esc(title), d))
    head.append('<meta name="twitter:card" content="summary_large_image">')
    if SITE_URL:
        if path is not None and not base_href:
            head.append('<link rel="canonical" href="%s%s"><meta property="og:url" content="%s%s">' % (SITE_URL, path, SITE_URL, path))
        head.append('<meta property="og:image" content="%sassets/og.png"><meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">' % SITE_URL)
    return """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>%(title)s</title>
%(head)s
<link rel="stylesheet" href="%(base)sassets/katex/katex.min.css">
<link rel="stylesheet" href="%(base)sassets/style.css">
<script defer src="%(base)sassets/katex/katex.min.js"></script>
<script defer src="%(base)sassets/katex/auto-render.min.js"></script>
%(extra)s<script defer src="%(base)sassets/app.js"></script>
</head>
<body%(style)s>
<header class="topbar"><div class="wrap">
<a class="brand" href="%(base)sindex.html"><span class="logo">∑</span>数学小白导览</a>
<nav class="nav">%(nav)s</nav>
<a class="gh" href="%(repo)s" target="_blank" rel="noopener" title="在 GitHub 上看源码、提问题、点 Star">⭐<span> GitHub</span></a>
<button class="theme-btn" title="切换明暗主题" aria-label="切换明暗主题">◐</button>
</div></header>
%(body)s
%(footer)s
</body>
</html>
""" % {"title": esc(title), "head": "\n".join(head), "base": base, "nav": nav, "body": body, "extra": extra_head,
       "style": style, "repo": REPO_URL, "footer": footer_html(base)}


def stars(n):
    return '<span class="stars lv%d" title="门槛 %d/5：%s">%s<span style="opacity:.25">%s</span></span>' % (
        n, n, LV_TEXT[n], "★" * n, "★" * (5 - n))


def kw_chips(kws):
    out = []
    for k in [x.strip() for x in kws.split(",") if x.strip()]:
        q = quote(k)
        wiki = "https://zh.wikipedia.org/w/index.php?search=" if has_cjk(k) else "https://en.wikipedia.org/w/index.php?search="
        out.append('<span class="kw"><a href="%s%s" target="_blank" rel="noopener" title="在维基百科搜索">%s</a>'
                   '<a class="v" href="https://search.bilibili.com/all?keyword=%s" target="_blank" rel="noopener" title="在 B 站搜索相关视频">▶ 视频</a></span>'
                   % (wiki, q, rich(k), q))
    return '<div class="kws">%s</div>' % "".join(out)


def need_cards(need_str, gloss, base):
    out = []
    for it in split_items(need_str):
        if it.startswith("@"):
            k = it[1:].strip()
            g = gloss.get(k)
            if not g:
                continue
            f = g["f"]
            lab = ""
            if f.get("lab") and lab_exists(f["lab"]):
                lab = ' · <a href="%slabs/%s.html">🧪 试试互动实验</a>' % (base, f["lab"])
            out.append('<details class="need"><summary><b>%s</b><span class="s">%s</span></summary>'
                       '<div class="more">%s<br><a href="%sglossary.html#g-%s">在词汇表中查看 →</a>%s</div></details>'
                       % (rich(f["zh"]), rich(f["short"]), rich(f["long"]), base, k, lab))
        else:
            term, expl = it.split("｜", 1)
            out.append('<div class="need plain"><b>%s</b><span class="s">%s</span></div>'
                       % (rich(term.strip()), rich(expl.strip())))
    return '<div class="needs">%s</div>' % "".join(out)


def path_steps(path_str):
    lis = []
    for n, it in enumerate(split_items(path_str), 1):
        label, text = it.split("｜", 1)
        c = stage_cls(label.strip())
        lis.append('<li><span class="dot st%d">%d</span><span class="st st%d">%s</span>%s</li>' % (c, n, c, rich(label.strip()), rich(text.strip())))
    return '<ol class="steps">%s</ol>' % "".join(lis)


_lab_cache = {}


def lab_exists(lab):
    """互动实验的源文件是 labs_src/lab-<id>.html（只写页面中间的片段），构建时由 page_lab() 套上统一的页头页脚后写到 labs/<id>.html。"""
    if lab not in _lab_cache:
        _lab_cache[lab] = os.path.exists(os.path.join(SG, "labs_src", "lab-" + lab + ".html"))
    return _lab_cache[lab]


# ----------------------------------------------------------------------------
# 页面：单个问题
# ----------------------------------------------------------------------------
def page_problem(fam, g, subj, prev_f, next_f, gloss, same_subject, guides):
    f = g["f"]
    base = "../"
    hue = subj["hue"]
    lv = int(f["lv"])
    metas = ['<a class="tag" href="%ss/%d.html">%s %s</a>' % (base, subj["id"], subj["icon"], esc(subj["zh"])),
             '<span class="tag">门槛 %s</span>' % stars(lv),
             '<span class="tag">%d 篇论文</span>' % len(fam["papers"])]
    if f.get("warn"):
        metas.append('<span class="tag warn">⚠️ 有提醒</span>')
    if fam["lean"]:
        metas.append('<a class="tag lean" href="%slean/docs/%s.md" target="_blank" rel="noopener" title="Lean 形式化的范围说明（并非等于整篇论文都被形式化验证）">🧾 有 Lean 形式化（范围见说明）</a>' % (UP_BLOB, fam["id"]))
    if f.get("lab") and lab_exists(f["lab"]):
        metas.append('<a class="tag lab" href="%slabs/%s.html">🧪 有互动实验</a>' % (base, f["lab"]))

    parts = []
    parts.append('<div class="crumbs"><a href="%sindex.html">首页</a> › <a href="%ss/%d.html">%s</a> › %s</div>'
                 % (base, base, subj["id"], esc(subj["zh"]), fam["id"]))
    parts.append('<h1 class="title"><span class="no">%s</span>%s</h1>' % (fam["id"], rich(f["zh"])))
    parts.append('<div class="en-title">%s</div>' % rich(fam["title"]))
    parts.append('<div class="meta-row">%s</div>' % "".join(metas))
    if f.get("warn"):
        parts.append('<div class="warnbar"><b>⚠️ 先看这条提醒</b>%s</div>' % rich(f["warn"]))
    parts.append('<div class="tldr"><small>🎯 一句话看懂</small>%s</div>' % rich(f["tl"]))

    parts.append('<section class="blk"><h2><span class="ic">❓</span>这个问题到底在问什么</h2><p>%s</p></section>' % rich(f["ask"]))
    parts.append('<section class="blk"><h2><span class="ic">🍎</span>打个比方</h2><div class="analogy">%s</div></section>' % rich(f["ana"]))
    parts.append('<section class="blk"><h2><span class="ic">🧱</span>想看懂它，先备哪几块"积木"</h2>%s</section>' % need_cards(f["need"], gloss, base))
    parts.append('<section class="blk"><h2><span class="ic">🏁</span>结果是什么？为什么重要</h2><p>%s</p></section>' % rich(f["why"]))
    if f.get("how"):
        parts.append('<section class="blk"><h2><span class="ic">🧭</span>做法的大方向</h2><div class="how">%s<small>注：这是领域内的通行思路，不代表对论文证明的逐页解读。</small></div></section>' % rich(f["how"]))
    if f.get("lab") and lab_exists(f["lab"]):
        t, ic, d = LAB_META[f["lab"]]
        parts.append('<section class="blk"><div class="labcard"><span class="ic">%s</span><div><b>互动实验：%s</b><p>%s</p></div>'
                     '<a class="go" href="%slabs/%s.html">打开实验 →</a></div></section>' % (ic, esc(t), esc(d), base, f["lab"]))
    parts.append('<section class="blk"><h2><span class="ic">🪜</span>从零开始的学习路径</h2>%s</section>' % path_steps(f["path"]))
    parts.append('<section class="blk"><h2><span class="ic">🔎</span>继续探索：搜这些关键词</h2>%s</section>' % kw_chips(f["kw"]))

    rel = [x for x in same_subject if x["id"] != fam["id"]]
    rel.sort(key=lambda x: (abs(int(guides[x["id"]]["f"].get("lv", "3")) - lv), x["id"]))
    rel = rel[:6]
    if rel:
        parts.append('<section class="blk"><h2><span class="ic">🧭</span>同一学科里，难度相近的问题</h2><div class="related">%s</div></section>' % "".join(
            '<a href="%s.html"><span class="no">%s</span>%s</a>' % (x["id"], x["id"], rich(guides[x["id"]]["f"]["zh"])) for x in rel))

    parts.append('<section class="blk"><details class="abs"><summary>📄 原始摘要（英文，供对照）</summary><p>%s</p></details></section>' % rich(fam["desc"]))
    pl = []
    for p in fam["papers"]:
        if p["exists"]:
            pl.append('<li><a href="%s" target="_blank" rel="noopener">%s</a> <span class="pn">· PDF</span></li>' % (p["url"], rich(p["title"])))
        else:
            pl.append("<li>%s</li>" % rich(p["title"]))
    parts.append('<section class="blk"><h2><span class="ic">📚</span>原始论文（在上游仓库 openai/math，共 %d 篇）</h2><ul class="papers">%s</ul>'
                 '<p class="small-note">链接指向 GitHub 上的原文件，用 GitHub 自带的查看器即可阅读；论文版权与许可见上游仓库。</p></section>' % (len(fam["papers"]), "".join(pl)))
    parts.append('<section class="blk"><button id="done-btn" class="done-btn" data-id="%s"></button></section>' % fam["id"])
    parts.append('<p class="feedback">这页讲得不对、看不懂，或者有更好的类比？'
                 '<a href="%s" target="_blank" rel="noopener">报告问题</a> · <a href="%s/edit/main/src/%s" target="_blank" rel="noopener">在 GitHub 上直接改</a></p>'
                 % (issue_url("correction.yml", "[%s] " % fam["id"], "p/%s.html" % fam["id"]), REPO_URL, g["file"]))

    def nv(x, cls, lab):
        if not x:
            return "<span></span>"
        return '<a class="%s" href="%s.html"><small>%s</small>%s %s</a>' % (cls, x["id"], lab, x["id"], rich(guides[x["id"]]["f"]["zh"]))
    parts.append('<div class="prevnext">%s%s</div>' % (nv(prev_f, "pv", "← 上一个"), nv(next_f, "nx", "下一个 →")))

    notice = '<div class="notice"><b>读前提示：</b>本页讲的是论文“宣称证明了什么”，帮你看懂问题与意义，并不是对其证明正确性的背书。</div>'
    body = '<main class="page"><div class="narrow">%s%s</div></main>' % (notice, "".join(parts))
    return layout("%s %s · 数学小白导览" % (fam["id"], f["zh"]), body, base, "", subj_hue=hue,
                  desc=f["tl"], path="p/%s.html" % fam["id"])


# ----------------------------------------------------------------------------
# 页面：首页 / 学科 / 词汇表 / 实验室 / 关于
# ----------------------------------------------------------------------------
def lv_bar(counts, total):
    if not total:
        return ""
    return '<div class="bar" title="门槛分布（绿=易，红=难）">%s</div>' % "".join(
        '<i class="b%d" style="width:%.2f%%"></i>' % (k, 100.0 * counts.get(k, 0) / total) for k in range(1, 6))


# 首页的编辑性选择（id 不存在会在构建时报警告）
FEATURED = ["025", "158", "238", "143", "128", "100", "028", "109"]          # 「精选」轮播
HOME_LABS = ["chaos", "ising", "percolation", "catmap", "billiard", "fourier"]   # 「实验室」预览
EXAMPLE_ID = "158"                                                         # 「三步」里拿来举例的问题
HERO_GLYPHS = [("∑", 5, 16, 46, 0), ("∫", 40, 7, 40, 2), ("π", 88, 20, 54, 4), ("∞", 68, 72, 44, 1),
               ("∂", 10, 76, 40, 3), ("√", 50, 90, 36, 5), ("≈", 94, 84, 38, 2), ("ζ", 27, 42, 34, 6)]


def start_pick(items, lv, n=6):
    """「找到你的起点」：门槛落在 [lv-1, lv]（lv=1 时只取 1）里的问题；有互动的优先，同一学科尽量不重复。home.js 里有同样的规则。"""
    pool = [x for x in items if (x["lv"] == 1 if lv == 1 else lv - 1 <= x["lv"] <= lv)]
    pool.sort(key=lambda x: (0 if x["lab"] else 1, x["id"]))
    out, seen = [], set()
    for x in pool:
        if x["s"] not in seen and len(out) < n:
            out.append(x)
            seen.add(x["s"])
    for x in pool:
        if x not in out and len(out) < n:
            out.append(x)
    return out


def item_card(x, s, base=""):
    """一张问题卡片（静态版；app.js 的 sgBuildCard 生成同样的结构）。"""
    return ('<a class="item" style="--sc:hsl(%d 62%% 48%%)" href="%sp/%s.html"><div class="top"><span class="num">%s</span><span>%s</span></div>'
            '<h3>%s</h3><div class="tl">%s</div><div class="meta">%s%s%s</div></a>') % (
        s["hue"], base, x["id"], x["id"], esc(s["zh"]), rich(x["zh"]), rich(x["tl"]), stars(x["lv"]),
        '<span class="tag lab">🧪 有互动</span>' if x["lab"] else "", '<span class="tag warn">⚠️ 有提醒</span>' if x.get("warn") else "")


def page_index(items, subjects, stats, guides):
    sub = {s["id"]: s for s in subjects}
    by_id = {x["id"]: x for x in items}
    n = stats["n"]
    glyphs = "".join('<span style="--x:%d%%;--y:%d%%;--s:%dpx;--d:%ds">%s</span>' % (x, y, sz, d, g) for g, x, y, sz, d in HERO_GLYPHS)
    hero = """<section class="lp-hero">
<div class="lp-glyphs" aria-hidden="true">%(glyphs)s</div>
<div class="wrap lp-hero-grid">
<div class="lp-copy">
<div class="lp-badge"><span class="dot"></span>非官方 · 免费开源 · 全中文 · 不用注册</div>
<h1>把 OpenAI 公开的<br><em>%(n)d 个</em>数学前沿问题，<br>讲给“数学小白”听</h1>
<p class="lp-sub">每个问题都配了：一句话版本 · 大白话提问 · 生活类比 · 先备积木 · 从零开始的学习阶梯。能玩的地方还有互动实验——不用安装，不用联网。</p>
<div class="lp-cta"><a class="btn-primary" href="#start">开始阅读 →</a><a class="btn-ghost" href="%(repo)s" target="_blank" rel="noopener">⭐ 在 GitHub 上 Star</a><a class="btn-link" href="problems.html" data-random>🎲 随机来一个</a></div>
<div class="lp-resume" id="resume" hidden></div>
<div class="lp-stats">
<div class="lp-stat"><b>%(n)d</b><span>个问题</span></div><div class="lp-stat"><b>%(ns)d</b><span>个数学学科</span></div>
<div class="lp-stat"><b>%(nl)d</b><span>个互动实验</span></div><div class="lp-stat"><b>%(ng)d</b><span>条词汇表</span></div>
</div>
<div class="lp-stamp">%(stamp)s</div>
</div>
<figure class="lp-art"><canvas id="chaos" width="800" height="700" role="img" aria-label="一幅正在自己生长出来的分形图"></canvas>
<figcaption><span id="chaos-label">混沌游戏：随机朝顶点跳半步，点点之间长出谢尔宾斯基三角形。</span> <a href="labs/chaos.html">自己玩一玩 →</a></figcaption></figure>
</div></section>""" % {"glyphs": glyphs, "n": n, "ns": stats["ns"], "nl": stats["nl"], "ng": stats["ng"], "repo": REPO_URL, "stamp": up_stamp()}

    marq = "".join('<a href="s/%d.html">%s %s</a>' % (s["id"], s["icon"], esc(s["zh"])) for s in subjects)
    marquee = '<div class="lp-marquee" aria-label="全部学科"><div class="track"><span class="grp">%s</span><span class="grp" aria-hidden="true">%s</span></div></div>' % (
        marq, marq.replace("<a ", '<a tabindex="-1" '))

    feat = []
    for fid in FEATURED:
        x = by_id.get(fid)
        if not x:
            warn("FEATURED 里的 %s 不存在" % fid)
            continue
        s = sub[x["s"]]
        feat.append('<a class="fc" href="p/%s.html" style="--sc:hsl(%d 62%% 48%%)"><img src="art/s%d.svg" alt="" loading="lazy" width="480" height="320">'
                    '<div class="fc-b"><div class="top"><span class="num">%s</span><span>%s</span></div><h3>%s</h3><p>%s</p><div class="meta">%s%s</div></div></a>' % (
                        x["id"], s["hue"], s["id"], x["id"], esc(s["zh"]), rich(x["zh"]), rich(x["tl"]), stars(x["lv"]),
                        '<span class="tag lab">🧪 有互动</span>' if x["lab"] else ""))
    featured = """<section class="lp-sec" id="featured"><div class="wrap">
<div class="lp-head row"><div><small>精选</small><h2>先从这几个感受一下</h2><p>都是不用大学数学就能读懂“在问什么”的问题。</p></div>
<div class="car-nav"><button type="button" id="car-prev" aria-label="向左">←</button><button type="button" id="car-next" aria-label="向右">→</button></div></div>
<div class="car" id="car" tabindex="0" aria-label="精选问题，可左右滑动">%s</div></div></section>""" % "".join(feat)

    eg = guides.get(EXAMPLE_ID)
    if eg:
        ef = eg["f"]
        e1, e2 = rich(ef["tl"]), rich(ef["ana"])
        e3 = " → ".join("<b>%s</b>：%s" % (rich(a.strip()), rich(b.strip())) for a, b in (it.split("｜", 1) for it in split_items(ef["path"])[:3]))
        eg_link = '<a href="p/%s.html">%s %s</a>' % (EXAMPLE_ID, EXAMPLE_ID, rich(ef["zh"].split("：")[0]))
    else:
        warn("EXAMPLE_ID %s 不存在" % EXAMPLE_ID)
        e1 = e2 = e3 = eg_link = ""
    steps = """<section class="lp-sec alt" id="what"><div class="wrap">
<div class="lp-head"><small>怎么读</small><h2>三步，从“看不懂”到“知道在问什么”</h2><p>不用硬啃摘要。每个问题页都按同一个顺序讲，下面是真实的一页（%(eg)s）里摘出来的样子。</p></div>
<div class="lp-steps3">
<div class="lp-step"><span class="n">1</span><h3>🎯 先看“一句话”</h3><p>别急着懂细节。先用一句不含术语的话，知道这个问题在折腾什么。</p><div class="eg"><small>一句话看懂</small>%(e1)s</div></div>
<div class="lp-step"><span class="n">2</span><h3>🍎 再看“打个比方”</h3><p>把抽象概念对上日常经验；能动手的，就去玩互动实验。</p><div class="eg"><small>打个比方</small>%(e2)s</div></div>
<div class="lp-step"><span class="n">3</span><h3>🪜 沿“学习阶梯”补课</h3><p>每个问题都有一条从初中到前沿的路径，附关键词，一键搜索维基与 B 站。</p><div class="eg"><small>学习路径（节选）</small>%(e3)s</div></div>
</div></div></section>""" % {"eg": eg_link, "e1": e1, "e2": e2, "e3": e3}

    lvl_btn = [(1, "🌱 初高中", "只需要初高中数学"), (2, "📘 高中 + 一点点大学", "微积分、线代刚入门"), (3, "🎓 大学数学专业本科", "学过分析/代数/概率"),
               (4, "🔬 研究生课程", "学过一两门研究生课"), (5, "🚀 专家级", "想看最硬的")]
    chips = "".join('<button type="button" class="chip lg%s" data-lv="%d" title="%s">%s <small>%d</small></button>' % (
        " on" if lv == 2 else "", lv, esc(tip), lab, sum(1 for x in items if (x["lv"] == 1 if lv == 1 else lv - 1 <= x["lv"] <= lv)))
        for lv, lab, tip in lvl_btn)
    first = "".join(item_card(x, sub[x["s"]]) for x in start_pick(items, 2))
    finder = """<section class="lp-sec" id="start"><div class="wrap">
<div class="lp-head"><small>找到你的起点</small><h2>你现在的数学大概到哪儿？</h2><p>选一个最接近的，挑几个读得懂的问题给你。（“门槛”衡量的是读懂<b>问题陈述</b>要什么基础，不是证明的难度。）</p></div>
<div class="finder-bar" id="fd-bar">%(chips)s<span class="sp"></span><label class="chk"><input type="checkbox" id="fd-lab"> 只看有互动实验的</label><button type="button" class="btn" id="fd-shuffle">🔀 换一批</button></div>
<div class="grid" id="fd-grid">%(first)s</div>
<p class="more"><a id="fd-more" href="problems.html?lv=1,2">查看这一档的全部问题 →</a>　<a href="problems.html">浏览全部 %(n)d 个 →</a></p>
</div></section>""" % {"chips": chips, "first": first, "n": n}

    scards = []
    for s in subjects:
        cnt = {}
        for x in items:
            if x["s"] == s["id"]:
                cnt[x["lv"]] = cnt.get(x["lv"], 0) + 1
        scards.append('<a class="sj" style="--sc:hsl(%d 62%% 48%%)" href="s/%d.html"><img src="art/s%d.svg" alt="" loading="lazy" width="480" height="320">'
                      '<div class="sj-b"><b>%s %s</b><small>%s · %d 个问题</small>%s</div></a>' % (
                          s["hue"], s["id"], s["id"], s["icon"], esc(s["zh"]), esc(s["en"]), s["n"], lv_bar(cnt, s["n"])))
    # 17 个学科排 4 列会剩 1 张孤零零的卡片：用一张“学科导览”入口卡补满最后一行
    scards.append('<a class="sj sj-more" href="subjects.html"><div><b>想按学科慢慢逛？</b>'
                  '<p>每个学科页先用大白话讲“它在研究什么”，再列出该学科的全部问题。</p>'
                  '<span class="btn-primary">学科导览 →</span></div></a>')
    subj_sec = """<section class="lp-sec alt" id="subjects"><div class="wrap">
<div class="lp-head"><small>学科地图</small><h2>%(ns)d 个学科，每一个都先讲“它在研究什么”</h2><p>每幅图都是用数学本身画出来的：素数螺旋、椭圆曲线、纽结、双曲树、元胞自动机……卡片下方的彩色条是该学科的门槛分布（绿＝易，红＝难）。</p></div>
<div class="sj-grid">%(cards)s</div></div></section>""" % {"ns": len(subjects), "cards": "".join(scards)}

    lcards = []
    for lab in HOME_LABS:
        if lab not in LAB_META or not lab_exists(lab):
            warn("HOME_LABS 里的 %s 不存在" % lab)
            continue
        t, ic, d = LAB_META[lab]
        lcards.append('<a class="lab-card" href="labs/%s.html"><span class="ic">%s</span><div><b>%s</b><p>%s</p></div></a>' % (lab, ic, esc(t), esc(d)))
    labs_sec = """<section class="lp-sec" id="labs"><div class="wrap">
<div class="lp-head row"><div><small>互动实验室</small><h2>能动手的地方，不要只看</h2><p>每个实验都是单个网页，拖一拖滑块、点一点按钮就能看到现象。只演示很小规模的情形，帮你建立直觉，不能代替证明。</p></div>
<a class="btn" href="labs/index.html">全部 %(nl)d 个实验 →</a></div>
<div class="lab-grid">%(cards)s</div></div></section>""" % {"nl": stats["nl"], "cards": "".join(lcards)}

    cnt = {k: sum(1 for x in items if x["lv"] == k) for k in range(1, 6)}
    mx = max(cnt.values()) or 1
    rows = "".join('<div class="lad"><span class="stars lv%d">%s</span><div><b>%s</b><div class="meter"><i class="b%d" style="width:%.1f%%"></i></div></div><span class="c">%d 个</span></div>' % (
        k, "★" * k, LV_TEXT[k], k, 100.0 * cnt[k] / mx, cnt[k]) for k in range(1, 6))
    ladder = """<section class="lp-sec alt" id="ladder"><div class="wrap">
<div class="lp-head"><small>门槛 ★</small><h2>怎么读“门槛”</h2><p>它表示读懂<b>问题本身</b>需要的数学水平，不是证明的难度——论文里的证明几乎都在 ★★★★★ 之上。你完全可以只读“问题”和“为什么重要”，把证明留给专家。</p></div>
<div class="ladder">%s</div></div></section>""" % rows

    honest = """<section class="lp-sec" id="honest"><div class="wrap">
<div class="lp-head"><small>先把话说清楚</small><h2>它靠谱吗？</h2><p>数学最看重“说清楚边界”。所以先说我们是谁、做了什么、没做什么。</p></div>
<div class="cols3">
<div class="card"><h3>🧭 这是什么</h3><p>对上游仓库 <a href="%(up)s" target="_blank" rel="noopener">openai/math</a> 里研究论文的<b>阅读指导</b>：问题是什么、为什么重要、该先学什么。不复述证明。</p></div>
<div class="card"><h3>🚫 这不是什么</h3><p><b>不是 OpenAI 官方</b>，也不判断论文证明是否正确。上游论文由 OpenAI 内部模型生成；上游自己说明，这些结果处于不同的验证阶段，并非都有 Lean 形式化，没有形式化的部分可能有问题。有 Lean 标记也只表示“有形式化”，范围以上游说明为准。</p></div>
<div class="card"><h3>🔬 内容怎么来的</h3><p>指导文字由 <b>AI 辅助撰写</b>，经过自动化检查（链接、公式、结构），<b>没有人工逐篇审校</b>，难免有错。每页底部都有“报告问题”入口，欢迎纠错。</p></div>
</div>
<div class="notice" style="margin-top:18px"><b>我们会跟着上游更新。</b>脚本每天比对上游仓库，有变化就提 Issue、改页面。例如上游在 2026 年 10 月 7 日撤回了 3 篇稿件，相关页面（如 <a href="p/032.html">032</a>）已加上醒目的提醒。<a href="about.html">了解更多 →</a></div>
</div></section>""" % {"up": UP_URL}

    faq_items = [
        ("我完全没学过高等数学，能看吗？", "能。每页先给一句话和一个比喻；门槛 ★1–2 的问题只需要初高中数学。遇到不懂的词，点开“先备积木”就有解释。"),
        ("这些论文是真的吗？证明对不对？", "论文来自 OpenAI 公开的仓库 <a href=\"%s\" target=\"_blank\" rel=\"noopener\">openai/math</a>。该仓库自己说明：这些结果处于不同的验证阶段，并非都有 Lean 形式化，没有形式化的部分“可能有问题”。本站只讲“它宣称证明了什么”，不对正确性背书。" % UP_URL),
        ("这些指导是人写的吗？", "不是纯人工：由 AI 辅助撰写，经自动化检查，没有人工逐篇审校。所以请带着一点怀疑读，发现错误请<a href=\"%s\" target=\"_blank\" rel=\"noopener\">告诉我们</a>。" % issue_url()),
        ("学习进度存在哪里？", "只存在你这台设备的浏览器里（localStorage），不上传、不需要账号。换设备或清缓存会丢，可以在“全部问题”页导出/导入进度。"),
        ("能离线用吗？", "可以。<a href=\"%s/releases/latest\" target=\"_blank\" rel=\"noopener\">Releases</a> 里有离线包，解压后双击 <code>index.html</code>；公式和实验都不需要联网。" % REPO_URL),
        ("能转载或再创作吗？", "指导文字用 CC BY 4.0（署名即可，可商用可改编），代码用 MIT。上游论文与摘要的版权/许可见上游仓库。详见<a href=\"about.html#license\">许可与署名</a>。"),
        ("我想参与怎么办？", "最简单：在任何问题页底部点“报告问题”或“在 GitHub 上直接改”。想加互动实验、改讲法，欢迎提 PR，见 <a href=\"%s/blob/main/CONTRIBUTING.md\" target=\"_blank\" rel=\"noopener\">CONTRIBUTING</a>。" % REPO_URL),
    ]
    faq = """<section class="lp-sec alt" id="faq"><div class="wrap narrow0">
<div class="lp-head"><small>常见问题</small><h2>你可能想问</h2></div>
<div class="faq">%s</div></div></section>""" % "".join("<details><summary>%s</summary><p>%s</p></details>" % (q, a) for q, a in faq_items)

    band = """<section class="lp-cta-band"><div class="wrap">
<h2>从一个你最好奇的问题开始</h2><p>不用一次读完。挑一个，读完“一句话”和“打个比方”，就已经赢了一半。</p>
<div class="lp-cta" style="justify-content:center"><a class="btn-primary" href="#start">找一个起点 →</a><a class="btn-ghost" href="%s" target="_blank" rel="noopener">⭐ Star 支持一下</a></div>
</div></section>""" % REPO_URL

    body = hero + marquee + featured + steps + finder + subj_sec + labs_sec + ladder + honest + faq + band
    return layout("数学小白导览：%d 个数学前沿问题的学习指导" % n, body, "", "home", path="", desc=SITE_DESC,
                  extra_head='<link rel="stylesheet" href="assets/home.css">\n<script defer src="assets/data.js"></script>\n<script defer src="assets/home.js"></script>\n')


def page_problems(items, subjects, stats):
    body = """<main class="page"><div class="wrap">
<div class="crumbs"><a href="index.html">首页</a> › 全部问题</div>
<h1 class="title">全部问题</h1>
<p style="color:var(--ink2);margin:4px 0 0">%(n)d 个问题。用学科、门槛、是否有互动实验筛选，或直接搜索；点进去先看“一句话”。</p>
<div class="progress-row"><b id="progress">已学 0 / %(n)d</b><span class="sp"></span>
<button type="button" class="btn" id="exp" title="把“已学”记录下载成文件">⬇ 导出进度</button>
<label class="btn" title="导入之前导出的文件（与当前进度合并）">⬆ 导入进度<input type="file" id="imp" accept="application/json,.json" hidden></label></div>
<div class="small-note" style="margin:6px 0 0">进度只保存在你这台设备的浏览器里，不上传。</div>
<div class="filters">
<div class="search-row">
<input id="q" type="search" placeholder="搜索：编号、中文/英文标题、关键词，如 素数、椭圆曲线、Ramsey……" autocomplete="off">
<select id="sort" aria-label="排序"><option value="id">按编号</option><option value="lv">按门槛（易→难）</option><option value="lvd">按门槛（难→易）</option><option value="subj">按学科</option></select>
</div>
<div class="chips" id="f-subj"></div>
<div class="chips" id="f-lv"></div>
<div class="chips" id="f-flag"></div>
</div>
<div class="count" id="count"></div>
<div class="grid" id="grid"></div>
</div></main>
""" % {"n": stats["n"]}
    return layout("全部问题 · 数学小白导览", body, "", "problems", path="problems.html",
                  desc="按学科、门槛、是否有互动实验，筛选与搜索全部 %d 个数学前沿问题的学习指导。" % stats["n"],
                  extra_head='<script defer src="assets/data.js"></script>\n')


def page_404():
    body = """<main class="page"><div class="narrow" style="text-align:center;padding:40px 0 20px">
<div style="font-size:64px;line-height:1">🧭</div><h1 class="title">这一页不存在</h1>
<p style="color:var(--ink2)">可能是链接写错了，或者这个问题被合并/改名了。可以从下面几个入口重新出发：</p>
<p style="margin-top:22px"><a class="btn" href="index.html">回首页</a> <a class="btn" href="problems.html">浏览全部问题</a> <a class="btn" href="roadmap.html">看学习路线</a> <a class="btn" href="glossary.html">查词汇表</a></p>
</div></main>"""
    return layout("页面不存在 · 数学小白导览", body, "", "", base_href=SITE_URL)


def page_subjects(subjects, items, prim):
    cards = []
    for s in subjects:
        its = [x for x in items if x["s"] == s["id"]]
        cnt = {}
        for x in its:
            cnt[x["lv"]] = cnt.get(x["lv"], 0) + 1
        tl = prim.get(s["id"], {"f": {}})["f"].get("tl", "")
        cards.append('<a class="subj-card" style="--sc:hsl(%d 62%% 48%%)" href="s/%d.html"><div class="ic">%s</div><b>%s</b><small>%s · %d 个问题</small>%s<p>%s</p></a>'
                     % (s["hue"], s["id"], s["icon"], esc(s["zh"]), esc(s["en"]), len(its), lv_bar(cnt, len(its)), rich(tl)))
    body = '<main class="page"><div class="wrap"><h1 class="title">学科导览</h1><p style="color:var(--ink2)">%d 个学科。点进去先看"这门学问在研究什么"，再按从易到难的顺序读问题。卡片下方的彩色条是该学科的门槛分布（绿＝容易，红＝困难）。</p><div class="subj-grid">%s</div></div></main>' % (len(subjects), "".join(cards))
    return layout("学科导览 · 数学小白导览", body, "", "subjects", path="subjects.html",
                  desc="%d 个数学学科：先讲它在研究什么，再按从易到难的顺序读问题。" % len(subjects))


def page_subject(s, its, guides, prim, gloss):
    base = "../"
    p = prim.get(s["id"])
    pf = p["f"] if p else {}
    art_svg = ""
    if art and pf.get("viz"):
        try:
            art_svg = art.render(pf["viz"], s["hue"])
        except Exception as e:  # noqa
            warn("学科 %d 配图失败: %s" % (s["id"], e))
    hero_art = '<div class="art">%s</div>' % art_svg if art_svg else '<div class="art" style="font-size:96px;text-align:center;padding:30px">%s</div>' % s["icon"]
    cnt = {}
    for x in its:
        cnt[x["lv"]] = cnt.get(x["lv"], 0) + 1
    words = ""
    if pf.get("words"):
        wl = []
        for it in split_items(pf["words"]):
            if "｜" in it:
                t, e = it.split("｜", 1)
                wl.append('<div class="need plain"><b>%s</b><span class="s">%s</span></div>' % (rich(t.strip()), rich(e.strip())))
        words = '<section class="blk"><h2><span class="ic">🔑</span>这门学问里最常听到的词</h2><div class="words">%s</div></section>' % "".join(wl)
    intro = ""
    if pf:
        if pf.get("what"):
            intro += '<section class="blk"><h2><span class="ic">🔭</span>它在研究什么</h2><p>%s</p></section>' % rich(pf["what"])
        if pf.get("ana"):
            intro += '<section class="blk"><h2><span class="ic">🍎</span>打个比方</h2><div class="analogy">%s</div></section>' % rich(pf["ana"])
        intro += words
        if pf.get("kinds"):
            intro += '<section class="blk"><h2><span class="ic">🧩</span>这里的问题通常怎么问</h2><p>%s</p></section>' % rich(pf["kinds"])
        if pf.get("start"):
            intro += '<section class="blk"><h2><span class="ic">🚪</span>怎么入门</h2><p>%s</p></section>' % rich(pf["start"])
    groups = []
    for lv in range(1, 6):
        g = [x for x in its if x["lv"] == lv]
        if not g:
            continue
        groups.append('<h3 style="margin:22px 0 4px"><span class="stars lv%d">%s</span> %s <small style="color:var(--muted);font-weight:400">· %d 个</small></h3><div class="grid">%s</div>' % (
            lv, "★" * lv, LV_TEXT[lv], len(g), "".join(
                '<a class="item" style="--sc:hsl(%d 62%% 48%%)" href="../p/%s.html"><div class="top"><span class="num">%s</span></div><h3>%s</h3><div class="en">%s</div><div class="tl">%s</div><div class="meta">%s%s%s</div></a>' % (
                    s["hue"], x["id"], x["id"], rich(x["zh"]), rich(x["en"]), rich(x["tl"]), stars(x["lv"]),
                    '<span class="tag lab">🧪 有互动</span>' if x["lab"] else "", '<span class="tag lean">Lean</span>' if x["lean"] else "") for x in g)))
    body = ('<main class="page"><div class="wrap"><div class="crumbs"><a href="../index.html">首页</a> › <a href="../subjects.html">学科导览</a> › %s</div>'
            '<div class="subj-hero"><div><h1 class="title">%s %s</h1><div class="en-title">%s · %d 个问题</div><div class="tldr"><small>🎯 一句话看懂这个学科</small>%s</div>%s</div>%s</div>'
            '<div class="narrow" style="margin:0">%s</div><h2 style="margin-top:34px">📚 本学科的全部问题（由易到难）</h2>%s</div></main>') % (
        esc(s["zh"]), s["icon"], esc(s["zh"]), esc(s["en"]), len(its), rich(pf.get("tl", "")), lv_bar(cnt, len(its)), hero_art, intro, "".join(groups))
    return layout("%s · 学科导览" % s["zh"], body, base, "subjects", subj_hue=s["hue"],
                  desc=pf.get("tl", ""), path="s/%d.html" % s["id"])


def page_glossary(gloss, used, guides):
    items = []
    for k, g in gloss.items():
        f = g["f"]
        lab = ""
        if f.get("lab") and lab_exists(f["lab"]):
            lab = ' <a href="labs/%s.html">🧪 互动实验</a>' % f["lab"]
        us = " ".join('<a href="p/%s.html" title="%s">%s</a>' % (i, esc(re.sub(r"\$[^$]*\$", "", guides[i]["f"]["zh"])), i) for i in sorted(set(used.get(k, [])))[:40])
        more = " …" if len(set(used.get(k, []))) > 40 else ""
        items.append('<div class="gl-item" id="g-%s"><h3>%s</h3><div class="s">%s</div><p>%s%s</p>%s</div>' % (
            k, rich(f["zh"]), rich(f["short"]), rich(f["long"]), lab,
            ('<div class="used">用到它的问题：%s%s</div>' % (us, more)) if us else ""))
    body = ('<main class="page"><div class="narrow"><h1 class="title">词汇表</h1><p style="color:var(--ink2)">问题页里的"先备积木"点开后会链到这里。共 %d 个条目，下面可以搜索。</p>'
            '<div class="search-row" style="margin:12px 0 16px"><input id="gq" type="search" placeholder="搜索词条……" autocomplete="off"></div><div class="gl-list" id="gl-list">%s</div></div></main>') % (len(gloss), "".join(items))
    return layout("词汇表 · 数学小白导览", body, "", "glossary", path="glossary.html",
                  desc="%d 个数学词条：用大白话解释，点问题页里的“先备积木”会跳到这里。" % len(gloss))


def page_labs(used_by):
    cards = []
    for lab, (t, ic, d) in LAB_META.items():
        ok = lab_exists(lab)
        ids = sorted(set(used_by.get(lab, [])))
        links = " ".join('<a href="../p/%s.html">%s</a>' % (i, i) for i in ids[:16])
        cards.append('<%s class="subj-card" style="--sc:hsl(150 55%%45%%)" %s><div class="ic">%s</div><b>%s</b><p>%s</p><p style="font-size:13px;color:var(--muted)">相关问题：%s</p></%s>' % (
            "a" if ok else "div", ('href="%s.html"' % lab) if ok else 'style="opacity:.5"', ic, esc(t), esc(d), links or "—", "a" if ok else "div"))
    body = '<main class="page"><div class="wrap"><h1 class="title">互动实验室</h1><p style="color:var(--ink2)">能动手的地方不要只看。每个实验都是单个网页，不用联网，直接在浏览器里玩。</p><div class="subj-grid">%s</div></div></main>' % "".join(cards)
    return layout("互动实验室 · 数学小白导览", body, "../", "labs", path="labs/",
                  desc="%d 个能在浏览器里直接玩的数学小实验：素数、分形、渗流、伊辛模型、混沌……" % sum(1 for k in LAB_META if lab_exists(k)))


LAB_HEAD = '<link rel="stylesheet" href="../assets/lab.css">\n<script src="../assets/lab.js"></script>\n'


def page_lab(lab, frag, used_by, items_by_id):
    """单个互动实验页：统一的面包屑、标题、一句话、免责提示、相关问题；中间的交互部分来自 labs_src/lab-<id>.html。"""
    t, ic, d = LAB_META[lab]
    ids = sorted(set(used_by.get(lab, [])))
    rel = ""
    if ids:
        rel = ('<section class="blk"><h2><span class="ic">🔗</span>这个实验和哪些问题有关</h2><div class="related">%s</div></section>' % "".join(
            '<a href="../p/%s.html"><span class="no">%s</span>%s</a>' % (i, i, rich(items_by_id[i]["zh"])) for i in ids))
    note = '<div class="notice"><b>提醒：</b>这是一个教学演示，用来帮你建立直觉。它不能代替证明，也不是对稿件结论的验证。</div>'
    body = ('<main class="page"><div class="wrap lab-page">'
            '<div class="crumbs"><a href="../index.html">首页</a> › <a href="index.html">互动实验室</a> › %s</div>'
            '<h1 class="title">%s %s</h1><div class="tldr"><small>🧪 你可以在这里动手</small>%s</div>'
            '%s%s%s</div></main>') % (esc(t), ic, esc(t), rich(d), frag, rel, note)
    return layout("%s · 互动实验" % t, body, "../", "labs", extra_head=LAB_HEAD, desc=d, path="labs/%s.html" % lab)


def page_about(stats, built, warned):
    wl = "、".join('<a href="p/%s.html">%s</a>' % (i, i) for i in warned) or "（目前没有）"
    body = """<main class="page"><div class="narrow"><h1 class="title">关于这套指导</h1>
<div class="card"><h3 style="margin-top:0">它是什么</h3>
<p>OpenAI 在 GitHub 上公开了一个数学仓库 <a href="%(up_url)s" target="_blank" rel="noopener">openai/math</a>：里面是 OpenAI 内部模型产出的研究论文，整理成了 <b>%(n)d 个“结果家族”</b>（共 %(np)d 篇论文）。这些摘要面向专业数学家。本站为每个家族补上了面向零基础读者的学习指导。<b>论文本身仍在上游仓库，不在本站。</b></p>
<h3>每个问题页包含什么</h3>
<ul><li><b>一句话看懂</b>：不含术语的最短版本</li><li><b>这个问题到底在问什么</b>：大白话 + 小例子</li><li><b>打个比方</b>：类比（不严格，只为建立直觉）</li><li><b>先备积木</b>：看懂陈述所需的概念；点开有解释，常用的收在<a href="glossary.html">词汇表</a></li><li><b>结果是什么、为什么重要</b></li><li><b>从零开始的学习路径</b>：从初中到前沿的阶梯，附可搜索的关键词</li><li><b>原始摘要与论文链接</b>：随时对照原文（链接指向上游 GitHub）</li></ul>
<h3>怎么读“门槛 ★”</h3>
<p>%(lv)s</p>
<h3>需要知道的局限</h3>
<ul><li>这里的解释是<b>阅读指导，不是证明的复述</b>。本站没有逐篇审阅 %(np)d 篇论文的证明；类比和“做法的大方向”来自摘要与领域常识。</li>
<li>指导文字由 <b>AI 辅助撰写</b>，经过自动化检查（链接是否有效、公式能否渲染、页面结构是否完整），<b>没有人工逐篇审校</b>。难免有错或表述不准，欢迎<a href="%(issue)s" target="_blank" rel="noopener">纠错</a>。</li>
<li>论文由 AI 模型产出。上游 README 自己写明：这些结果处于不同的验证阶段，并非都有 Lean 形式化，<b>没有形式化的部分可能有问题</b>。有 Lean 标记也只表示“有形式化”，具体覆盖范围以上游的 <code>lean/docs/NNN.md</code> 为准。</li>
<li>“打个比方”是为了建立直觉，必然会丢失精确性；遇到分歧，以原文摘要为准。</li>
<li><b>时间说明</b>：文里“至今”“目前”“近年”“几十年来”这类说法，指的是撰写这套指导时（大致就是页面底部写的同步日期）的情况，而且大多带着“据我所知”。数学前沿变化很快，如果你读到的时候已经隔了很久，最新进展请自己再查证。</li></ul>
<h3 id="upstream">数据来源与更新</h3>
<ul><li>家族与论文列表取自上游的 <code>overview.tex</code>。当前对应：%(stamp)s。该版本共 %(uf)s 个家族、%(up)s 篇论文，其中 %(ul)s 个家族附有 Lean 说明。</li>
<li>每天有一个脚本比对上游；上游一有变化，仓库里会自动开一个 Issue（标签 <code>upstream-sync</code>），再据此更新页面。</li>
<li>上游撤回或更正了结论的页面，会加上醒目的提醒。目前有提醒的页面：%(warned)s。</li>
<li>论文链接指向上游 GitHub 的原文件；上游若改名或移动文件，链接可能暂时失效，请告诉我们。</li></ul>
<h3>怎么参与</h3>
<ul><li>最简单：在任何问题页底部点“报告问题”或“在 GitHub 上直接改”。</li>
<li>源文件在仓库的 <code>src/</code>（纯文本块）和 <code>labs_src/</code>（互动实验）。改完运行 <code>python tools/build.py --strict</code> 重新生成，<code>python tools/preview.py</code> 本地预览。细则见 <a href="%(repo)s/blob/main/CONTRIBUTING.md" target="_blank" rel="noopener">CONTRIBUTING</a>。</li>
<li>公式用 KaTeX 0.16.11（MIT 许可）渲染，已离线收录在 <code>assets/katex/</code>，不需要联网。</li></ul>
<h3>离线使用</h3>
<p>到 <a href="%(repo)s/releases/latest" target="_blank" rel="noopener">Releases</a> 下载离线包，解压后双击 <code>index.html</code> 即可，公式和互动实验都不联网。</p>
<h3 id="license">许可与署名</h3>
<ul><li><b>指导文字</b>（<code>src/</code> 及由它生成的页面）：<a href="https://creativecommons.org/licenses/by/4.0/deed.zh-hans" target="_blank" rel="noopener">CC BY 4.0</a>。转载、改编、商用都可以，需要署名并注明是否做了修改，例如：“数学小白导览，%(repo_name)s，%(repo)s”。</li>
<li><b>代码</b>（<code>tools/</code>、<code>assets/</code> 下的脚本与样式、<code>labs_src/</code>）：MIT。</li>
<li><b>上游数据</b>（<code>data/</code> 里取自 openai/math 的标题与摘要）：来自 OpenAI 发布的上游仓库，保留其 Apache-2.0 许可，署名与修改说明见仓库里的 <code>NOTICE</code>。</li>
<li><b>论文</b>不在本站，版权与许可见<a href="%(up_url)s" target="_blank" rel="noopener">上游仓库</a>。</li>
<li><b>KaTeX</b>：MIT，许可证随文件收录。</li></ul>
<p class="small-note">本站页面构建于 %(built)s。</p></div></div></main>""" % {
        "up_url": UP_URL, "repo": REPO_URL, "repo_name": REPO, "issue": issue_url(), "n": stats["n"], "np": stats["np"],
        "lv": "；".join("%s %d：%s" % ("★" * k, k, v) for k, v in LV_TEXT.items()), "stamp": up_stamp() or "（未记录上游版本）",
        "uf": UP.get("families", "?"), "up": UP.get("papers", "?"), "ul": UP.get("lean_families", "?"), "warned": wl, "built": built}
    return layout("关于 · 数学小白导览", body, "", "about", path="about.html",
                  desc="这套学习指导是什么、怎么来的、有哪些局限、怎么更新、怎么参与、许可与署名。")


# ----------------------------------------------------------------------------
# 主流程
# ----------------------------------------------------------------------------
MARK = ".sg-build"      # 输出目录里的标记文件：只有带这个标记的目录才允许被清理多余文件
WRITTEN = set()         # 本次构建写出的文件（相对 OUT 的路径）


def write(path, text):
    """写到 OUT/path；内容没变就不重写（保持修改时间不变）。"""
    rel = path.replace("\\", "/")
    if rel.endswith(".html"):
        text = curly_html(text)          # 正文里的直引号统一换成中文弯引号
    WRITTEN.add(rel)
    full = os.path.join(OUT, rel)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    try:
        with open(full, encoding="utf-8", newline="") as f:
            if f.read() == text:
                return
    except (OSError, UnicodeDecodeError):
        pass
    with open(full, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def prepare_out():
    if os.path.isdir(OUT) and os.listdir(OUT) and not os.path.exists(os.path.join(OUT, MARK)):
        sys.exit("拒绝写入：输出目录 %s 非空，而且不是本脚本创建的（缺少 %s 标记）。请换一个空目录，或先手动清空它。" % (OUT, MARK))
    os.makedirs(OUT, exist_ok=True)


def copy_assets():
    """assets/ 原样拷到 OUT/assets/（没变的文件不重复拷）。"""
    src = os.path.join(SG, "assets")
    n = 0
    for d, _dirs, files in os.walk(src):
        for fn in files:
            sp = os.path.join(d, fn)
            rel = os.path.relpath(sp, SG).replace("\\", "/")
            dp = os.path.join(OUT, rel)
            WRITTEN.add(rel)
            n += 1
            if os.path.exists(dp) and filecmp.cmp(sp, dp, shallow=True):
                continue
            os.makedirs(os.path.dirname(dp), exist_ok=True)
            shutil.copy2(sp, dp)
    return n


def prune():
    """删掉 OUT 里这次没写出的旧文件（比如已经不存在的页面），再删空目录。"""
    gone = 0
    for d, _dirs, files in os.walk(OUT, topdown=False):
        for fn in files:
            rel = os.path.relpath(os.path.join(d, fn), OUT).replace("\\", "/")
            if rel not in WRITTEN:
                os.remove(os.path.join(d, fn))
                gone += 1
        if d != OUT and not os.listdir(d):
            os.rmdir(d)
    return gone


def site_url_from(arg):
    if not arg:
        return ""
    if arg == "auto":
        owner, _, name = REPO.partition("/")
        arg = "https://%s.github.io/%s/" % (owner.lower(), name)
    return arg if arg.endswith("/") else arg + "/"


def write_art(subjects, prim):
    """每个学科一幅配图，写成独立的 art/s<id>.svg（首页用 <img> 引用，避免多幅内联 SVG 的 id 冲突）。"""
    n = 0
    for s in subjects:
        viz = prim.get(s["id"], {"f": {}})["f"].get("viz")
        if not (art and viz):
            warn("学科 %d 没有配图（src 里的 viz 字段缺失，或 art.py 不可用）" % s["id"])
            continue
        try:
            write("art/s%d.svg" % s["id"], art.render(viz, s["hue"]))
            n += 1
        except Exception as e:  # noqa
            warn("学科 %d 配图失败: %s" % (s["id"], e))
    return n


def write_seo():
    """sitemap.xml + robots.txt（只在给了 --site-url 时才有意义）。"""
    if not SITE_URL:
        return
    paths = []
    for rel in sorted(WRITTEN):
        if not rel.endswith(".html") or rel == "404.html":
            continue
        paths.append("" if rel == "index.html" else "labs/" if rel == "labs/index.html" else rel)
    urls = "".join("<url><loc>%s%s</loc><lastmod>%s</lastmod></url>\n" % (SITE_URL, quote(pth, safe="/"), BUILD_DATE) for pth in paths)
    write("sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n%s</urlset>\n' % urls)
    write("robots.txt", "User-agent: *\nAllow: /\n\nSitemap: %ssitemap.xml\n" % SITE_URL)


def main(argv=None):
    global STRICT, OUT, SITE_URL, SITE_DESC, UP
    for st in (sys.stdout, sys.stderr):
        try:
            st.reconfigure(errors="replace")   # 控制台不是 UTF-8 时也别因为一个字符崩掉
        except Exception:  # noqa
            pass
    ap = argparse.ArgumentParser(description="构建「数学小白导览」静态站点")
    ap.add_argument("--strict", action="store_true", help="有任何警告也以非 0 退出（CI 用）")
    ap.add_argument("--out", default=os.path.join(SG, "_site"), help="输出目录（默认 _site/）")
    ap.add_argument("--site-url", default="", help="站点根地址（以 / 结尾），写入 canonical / 分享图 / sitemap；auto = 按 GITHUB_REPOSITORY 推出；不填 = 纯相对路径的离线版")
    args = ap.parse_args(argv)
    STRICT, OUT, SITE_URL = args.strict, os.path.abspath(args.out), site_url_from(args.site_url)

    up_path = os.path.join(SG, "data", "upstream.json")
    if os.path.exists(up_path):
        with open(up_path, encoding="utf-8") as f:
            UP = json.load(f)
    else:
        warn("缺少 data/upstream.json（先运行 python tools/sync_upstream.py）")

    data = json.load(open(os.path.join(SG, "data", "families.json"), encoding="utf-8"))
    fams = data["families"]
    guides, gloss, prim = load_sources()
    used = validate(fams, guides, gloss)

    order = [s["id"] for s in data["subjects"]]  # 与 overview 相同的学科顺序
    subjects = []
    for i, sid in enumerate(order):
        zh, ic = SUBJECT_META[sid]
        en = next(s["name"] for s in data["subjects"] if s["id"] == sid)
        subjects.append({"id": sid, "zh": zh, "en": en, "icon": ic, "hue": int(i * 360 / len(order) + 215) % 360})
    sub_by_id = {s["id"]: s for s in subjects}

    items, warned = [], []
    for fam in fams:
        g = guides.get(fam["id"])
        if not g:
            continue
        f = g["f"]
        it = {"id": fam["id"], "zh": f.get("zh", fam["title"]), "en": fam["title"], "s": fam["subject_id"],
              "lv": int(f.get("lv", "3")) if f.get("lv", "3").isdigit() else 3, "tl": f.get("tl", ""),
              "kw": f.get("kw", ""), "lean": fam["lean"], "lab": f.get("lab") if f.get("lab") and lab_exists(f["lab"]) else ""}
        if f.get("warn"):
            it["warn"] = 1
            warned.append(fam["id"])
        items.append(it)
    for s in subjects:
        s["n"] = sum(1 for x in items if x["s"] == s["id"])

    used_by_lab = {}
    for it in items:
        if it["lab"]:
            used_by_lab.setdefault(it["lab"], []).append(it["id"])

    built = datetime.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")
    stats = {"n": len(items), "ns": len(subjects), "nl": sum(1 for k in LAB_META if lab_exists(k)), "ng": len(gloss), "np": sum(len(f["papers"]) for f in fams)}
    SITE_DESC = ("把 OpenAI 公开的 %d 个数学前沿问题，讲给数学零基础的读者听：一句话看懂、生活类比、先备积木、从零开始的学习路径，外加 %d 个互动实验。非官方，免费开源。"
                 % (stats["n"], stats["nl"]))

    prepare_out()
    n_assets = copy_assets()
    n_art = write_art(subjects, prim)

    # data.js：给首页/全部问题页的前端脚本用
    payload = {"subjects": [{k: s[k] for k in ("id", "zh", "en", "icon", "hue", "n")} for s in subjects], "items": items}
    write("assets/data.js", "window.GUIDE_DATA = " + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + ";\n")

    write("index.html", page_index(items, subjects, stats, guides))
    write("problems.html", page_problems(items, subjects, stats))
    write("subjects.html", page_subjects(subjects, items, prim))
    write("glossary.html", page_glossary(gloss, used, guides))
    write("about.html", page_about(stats, built, warned))
    write("404.html", page_404())
    write("labs/index.html", page_labs(used_by_lab))
    items_by_id = {x["id"]: x for x in items}
    for sp in sorted(glob.glob(os.path.join(SG, "labs_src", "lab-*.html"))):
        lab = os.path.basename(sp)[4:-5]
        if lab not in LAB_META:
            warn("labs_src/%s 对应的实验 id 不在 LAB_META 中" % os.path.basename(sp))
            continue
        with open(sp, encoding="utf-8") as f:
            write("labs/%s.html" % lab, page_lab(lab, f.read(), used_by_lab, items_by_id))
    rp = os.path.join(SG, "src", "roadmap.html")
    if os.path.exists(rp):
        write("roadmap.html", layout("学习路线 · 数学小白导览", open(rp, encoding="utf-8").read(), "", "roadmap", path="roadmap.html",
                                     desc="从初中到前沿的数学学习路线：每一站学什么、做什么、怎么判断自己到了哪一站。"))
    else:
        warn("缺少 src/roadmap.html")

    fam_by_id = {f["id"]: f for f in fams}
    sids = [f["id"] for f in fams if f["id"] in guides]
    for n, fid in enumerate(sids):
        fam = fam_by_id[fid]
        subj = sub_by_id[fam["subject_id"]]
        same = [{"id": x["id"]} for x in items if x["s"] == subj["id"]]
        prev_f = {"id": sids[n - 1]} if n > 0 else None
        next_f = {"id": sids[n + 1]} if n + 1 < len(sids) else None
        write("p/%s.html" % fid, page_problem(fam, guides[fid], subj, prev_f, next_f, gloss, same, guides))
    for s in subjects:
        its = sorted([x for x in items if x["s"] == s["id"]], key=lambda x: (x["lv"], x["id"]))
        write("s/%d.html" % s["id"], page_subject(s, its, guides, prim, gloss))

    write_seo()
    write(MARK, "built %s by tools/build.py\n" % built)
    gone = prune()

    print("构建完成 → %s" % OUT)
    print("  %d 个问题页 / %d 个学科页 / %d 个词条 / %d 个实验 / %d 幅学科配图 / %d 个静态资源 / 清理旧文件 %d 个 / 警告 %d 条" % (
        len(sids), len(subjects), len(gloss), stats["nl"], n_art, n_assets, gone, len(WARN)))
    print("  站点地址：%s" % (SITE_URL or "（未指定，生成纯相对路径的离线版）"))
    missing = [f["id"] for f in fams if f["id"] not in guides]
    print("  尚未撰写指导的问题：%d / %d" % (len(missing), len(fams)))
    if STRICT and WARN:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
