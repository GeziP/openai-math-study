#!/usr/bin/env python3
"""检查构建出的站点（不联网，只看本地文件）：内部链接与锚点、CSS 里引用的字体、页面结构与元信息、sitemap。

用法
    python tools/check_site.py [站点目录]        默认 _site
退出码：0 全部通过；1 发现问题。

与 tools/check_math.js（公式渲染检查）搭配使用，CI 里两个都会跑。
"""
import html.parser
import json
import os
import posixpath
import re
import struct
import sys
from urllib.parse import unquote, urlsplit

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, ".."))

SKIP_SCHEMES = ("mailto:", "tel:", "javascript:", "data:", "blob:")
PROBLEM_H2 = ["这个问题到底在问什么", "打个比方", "积木", "结果是什么", "学习路径", "关键词", "原始论文"]


class Page(html.parser.HTMLParser):
    """只收集检查用得到的信息。"""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.lang = ""
        self.base = ""
        self.title = ""
        self.canonical = ""
        self.meta = {}
        self.ids = set()
        self.links = []          # (标签, 属性值)
        self.h1 = 0
        self.h2 = []
        self.no_alt = 0
        self.text = []
        self._in_title = False
        self._in_h2 = False
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        a = {k: (v if v is not None else "") for k, v in attrs}
        if a.get("id"):
            self.ids.add(a["id"])
        if tag == "a" and a.get("name"):
            self.ids.add(a["name"])
        if tag == "html":
            self.lang = a.get("lang", "")
        elif tag == "base":
            self.base = a.get("href", "")
        elif tag == "title":
            self._in_title = True
        elif tag == "meta":
            key = a.get("name") or a.get("property")
            if key:
                self.meta[key] = a.get("content", "")
        elif tag == "link":
            if "canonical" in a.get("rel", "").split():
                self.canonical = a.get("href", "")
            elif a.get("href"):
                self.links.append(("link", a["href"]))
        elif tag == "a":
            if a.get("href"):
                self.links.append(("a", a["href"]))
        elif tag in ("script", "img", "source", "iframe"):
            if a.get("src"):
                self.links.append((tag, a["src"]))
            if tag == "img" and "alt" not in a:
                self.no_alt += 1
        elif tag == "h1":
            self.h1 += 1
        elif tag == "h2":
            self._in_h2 = True
            self.h2.append("")
        if tag in ("script", "style"):
            self._skip += 1

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        elif tag == "h2":
            self._in_h2 = False
        if tag in ("script", "style") and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        if self._in_h2 and self.h2:
            self.h2[-1] += data
        if not self._skip:
            self.text.append(data)


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def png_size(path):
    with open(path, "rb") as f:
        head = f.read(24)
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    return struct.unpack(">II", head[16:24])


def main():
    root = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(REPO, "_site"))
    if not os.path.isdir(root):
        print("找不到站点目录：%s（请先运行 python tools/build.py）" % root)
        return 1

    errors = []

    def err(where, msg):
        errors.append("[%s] %s" % (where, msg))

    # ---- 收集所有页面 ----
    pages = {}
    for dp, _dn, fn in os.walk(root):
        for name in fn:
            if name.endswith(".html"):
                rel = os.path.relpath(os.path.join(dp, name), root).replace(os.sep, "/")
                p = Page()
                p.feed(read(os.path.join(dp, name)))
                p.close()
                pages[rel] = p

    # ---- 磁盘上的真实文件清单 ----
    # Windows / macOS 默认不区分大小写，而 GitHub Pages（Linux）区分：href="Assets/a.css" 在本机能打开、上线就 404。
    # 所以存在性一律拿“逐字符一致”的清单来比，而不是 os.path.isfile。
    disk_files, disk_dirs = set(), {""}
    for dp, dn, fn in os.walk(root):
        rp = os.path.relpath(dp, root).replace(os.sep, "/")
        rp = "" if rp == "." else rp
        disk_dirs.update(posixpath.join(rp, d) for d in dn)
        disk_files.update(posixpath.join(rp, f) for f in fn)
    lower_files = {p.lower(): p for p in disk_files}

    def case_hint(target):
        real = lower_files.get(target.lower())
        return "（大小写不一致：磁盘上是 %s，GitHub Pages 区分大小写，线上会 404）" % real if real else ""

    # ---- 站点根地址（带 --site-url 构建时才有 sitemap）----
    site_url = ""
    sitemap = os.path.join(root, "sitemap.xml")
    sitemap_locs = []
    if os.path.exists(sitemap):
        sitemap_locs = re.findall(r"<loc>([^<]+)</loc>", read(sitemap))
        robots = os.path.join(root, "robots.txt")
        m = re.search(r"^Sitemap:\s*(\S+)", read(robots), re.M) if os.path.exists(robots) else None
        if not m:
            err("robots.txt", "缺少 Sitemap: 行")
        else:
            site_url = m.group(1)[: -len("sitemap.xml")]

    # ---- 1. 内部链接与锚点 ----
    checked_links = 0

    def resolve(rel, page, raw):
        """返回 (目标相对路径, 片段) ；外链/特殊协议返回 None。"""
        u = raw.strip()
        if not u or u.startswith(SKIP_SCHEMES) or u.startswith("//"):
            return None
        sp = urlsplit(u)
        if sp.scheme in ("http", "https"):
            if site_url and u.startswith(site_url):
                u = u[len(site_url):]
                sp = urlsplit(u)
            else:
                return None
        elif sp.scheme:
            return None
        path = unquote(sp.path)
        if path.startswith("/"):
            err(rel, "根相对链接 %r 在子路径部署（/仓库名/）下会失效，请改成相对路径" % raw)
            return None
        if not path:
            return rel, sp.fragment
        base_dir = "" if page.base else posixpath.dirname(rel)
        target = posixpath.normpath(posixpath.join(base_dir, path))
        if target.startswith(".."):
            err(rel, "链接 %r 指到站点根目录之外" % raw)
            return None
        if path.endswith("/") or target in disk_dirs:
            target = posixpath.join(target, "index.html")
        return target, sp.fragment

    for rel, page in sorted(pages.items()):
        for kind, raw in page.links:
            r = resolve(rel, page, raw)
            if r is None:
                continue
            checked_links += 1
            target, frag = r
            if target not in disk_files:
                err(rel, "<%s> 指向不存在的文件：%s%s" % (kind, raw, case_hint(target)))
                continue
            if kind == "a" and frag and target.endswith(".html"):
                tp = pages.get(target)
                if tp is not None and frag not in tp.ids:
                    err(rel, "锚点不存在：%s" % raw)

    # ---- 2. CSS 里引用的本地资源（字体等）----
    for dp, _dn, fn in os.walk(root):
        for name in fn:
            if not name.endswith(".css"):
                continue
            cpath = os.path.join(dp, name)
            for u in re.findall(r"url\(\s*['\"]?([^)'\"]+?)['\"]?\s*\)", read(cpath)):
                if u.startswith(("data:", "http:", "https:", "#")):
                    continue
                target = os.path.normpath(os.path.join(dp, unquote(urlsplit(u).path)))
                trel = os.path.relpath(target, root).replace(os.sep, "/")
                if trel in disk_files:
                    continue
                # KaTeX 的 CSS 给每个字体列了 woff2 / woff / ttf 三种格式；浏览器只取第一个支持的（woff2），
                # 本站只收录 woff2，缺少后两种备用格式是有意的。
                stem, ext = posixpath.splitext(trel)
                if ext in (".woff", ".ttf") and (stem + ".woff2") in disk_files:
                    continue
                err(os.path.relpath(cpath, root).replace(os.sep, "/"), "CSS 引用的文件不存在：%s%s" % (u, case_hint(trel)))

    # ---- 3. 每个页面的通用结构 ----
    for rel, page in sorted(pages.items()):
        if page.lang != "zh-CN":
            err(rel, "<html lang> 应为 zh-CN，实际是 %r" % page.lang)
        if not page.title.strip():
            err(rel, "缺少 <title>")
        if not page.meta.get("description", "").strip():
            err(rel, "缺少 meta description")
        if "viewport" not in page.meta:
            err(rel, "缺少 viewport")
        if page.h1 != 1:
            err(rel, "应该恰好有 1 个 <h1>，实际 %d 个" % page.h1)
        if page.no_alt:
            err(rel, "%d 张图片没有 alt 属性" % page.no_alt)
        text = "".join(page.text)
        if "\ufffd" in text or "???" in text:
            err(rel, "可见文字里有乱码（U+FFFD 或连续的 ???）")
        if re.search(r"%\([a-z_]+\)[sd]", text):
            err(rel, "有没替换掉的模板占位符 %(…)s")

    # ---- 4. 与数据对应：问题页 / 学科页 / 实验页 ----
    fam_path = os.path.join(REPO, "data", "families.json")
    if os.path.exists(fam_path):
        data = json.loads(read(fam_path))
        want = {f["id"] for f in data["families"]}
        have = {m.group(1) for r in pages for m in [re.fullmatch(r"p/(\d{3})\.html", r)] if m}
        for i in sorted(want - have):
            err("p/%s.html" % i, "上游有这个家族，但站点没有对应页面")
        for i in sorted(have - want):
            err("p/%s.html" % i, "页面存在，但 data/families.json 里没有这个家族")
        want_s = {str(s["id"]) for s in data["subjects"]}
        have_s = {m.group(1) for r in pages for m in [re.fullmatch(r"s/(\d+)\.html", r)] if m}
        if want_s != have_s:
            err("s/", "学科页与数据不一致：缺 %s，多 %s" % (sorted(want_s - have_s), sorted(have_s - want_s)))
    else:
        want = set()
    for rel, page in sorted(pages.items()):
        if re.fullmatch(r"p/\d{3}\.html", rel):
            heads = " ".join(page.h2)
            for h in PROBLEM_H2:
                if h not in heads:
                    err(rel, "缺少小节“%s”" % h)
    labs_src = os.path.join(REPO, "labs_src")
    if os.path.isdir(labs_src):
        want_l = {re.sub(r"^lab-|\.html$", "", n) for n in os.listdir(labs_src) if n.startswith("lab-") and n.endswith(".html")}
        have_l = {m.group(1) for r in pages for m in [re.fullmatch(r"labs/(?!index)([^/]+)\.html", r)] if m}
        if want_l != have_l:
            err("labs/", "实验页与 labs_src 不一致：缺 %s，多 %s" % (sorted(want_l - have_l), sorted(have_l - want_l)))
    data_js = os.path.join(root, "assets", "data.js")
    if os.path.exists(data_js):
        src = read(data_js)
        try:
            gd = json.loads(src[src.index("{"): src.rindex("}") + 1])
            ids = {it["id"] for it in gd["items"]}
            if want and ids != want:
                err("assets/data.js", "卡片数据与家族不一致：缺 %s，多 %s" % (sorted(want - ids)[:5], sorted(ids - want)[:5]))
        except (ValueError, KeyError) as e:
            err("assets/data.js", "解析失败：%s" % e)
    else:
        err("assets/data.js", "缺少文件")

    # ---- 5. 带站点地址时：canonical / sitemap / 分享图 ----
    if sitemap_locs:
        loc_paths = set()
        for loc in sitemap_locs:
            if not loc.startswith(site_url):
                err("sitemap.xml", "地址不以站点根开头：%s" % loc)
                continue
            rel = unquote(loc[len(site_url):])
            if rel == "":
                rel = "index.html"
            elif rel.endswith("/"):
                rel += "index.html"
            loc_paths.add(rel)
            if rel not in pages:
                err("sitemap.xml", "收录了不存在的页面：%s" % loc)
        for rel, page in sorted(pages.items()):
            if rel == "404.html":
                continue
            if rel not in loc_paths:
                err(rel, "没有被 sitemap.xml 收录")
            exp = site_url + ("" if rel == "index.html" else "labs/" if rel == "labs/index.html" else rel)
            if page.canonical != exp:
                err(rel, "canonical 应为 %s，实际是 %r" % (exp, page.canonical))
            if page.meta.get("og:image") != site_url + "assets/og.png":
                err(rel, "og:image 不对：%r" % page.meta.get("og:image"))
        if "404.html" in pages and not pages["404.html"].base:
            err("404.html", "带站点地址的构建里，404 页需要 <base href>（它会在任意深度的路径下被返回）")
        og = os.path.join(root, "assets", "og.png")
        if "assets/og.png" not in disk_files:
            err("assets/og.png", "缺少分享图")
        elif png_size(og) != (1200, 630):
            err("assets/og.png", "分享图应为 1200×630，实际 %s" % (png_size(og),))

    # ---- 报告 ----
    n_p = sum(1 for r in pages if re.fullmatch(r"p/\d{3}\.html", r))
    print("站点检查：%d 个页面（其中问题页 %d）、%d 条内部链接，发现 %d 个问题。" % (len(pages), n_p, checked_links, len(errors)))
    for e in errors[:60]:
        print("  ✗ " + e)
    if len(errors) > 60:
        print("  …… 还有 %d 个" % (len(errors) - 60))
    return 1 if errors else 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa
        pass
    sys.exit(main())
