#!/usr/bin/env python3
"""把上游 openai/math 的 overview.tex 解析成结构化数据（学科 → 结果家族 → 论文）。

被 sync_upstream.py 当作库使用；也可以单独运行，快速看一眼解析结果：
    python tools/parse_overview.py path/to/overview.tex
"""
import re
import sys
from urllib.parse import unquote

GITHUB_PREFIX = "https://github.com/openai/math/blob/main/"

ACCENTS = {
    ("H", "o"): "ő", ("H", "O"): "Ő", ("H", "u"): "ű",
    ('"', "u"): "ü", ('"', "o"): "ö", ('"', "a"): "ä", ('"', "U"): "Ü", ('"', "O"): "Ö", ('"', "A"): "Ä",
    ("'", "e"): "é", ("'", "a"): "á", ("'", "o"): "ó", ("'", "i"): "í", ("'", "u"): "ú", ("'", "E"): "É",
    ("`", "e"): "è", ("`", "a"): "à", ("`", "o"): "ò",
    ("^", "o"): "ô", ("^", "e"): "ê", ("^", "a"): "â", ("^", "i"): "î",
    ("v", "c"): "č", ("v", "s"): "š", ("v", "z"): "ž", ("v", "C"): "Č", ("v", "S"): "Š",
    ("c", "c"): "ç", ("c", "s"): "ş",
    ("~", "n"): "ñ", ("~", "a"): "ã", ("~", "o"): "õ",
    ("=", "o"): "ō", ("=", "a"): "ā",
    ("u", "a"): "ă", ("u", "g"): "ğ",
}


def read_group(s, i):
    """s[i] == '{'; 返回 (内容, 下一个位置)。支持转义与嵌套。"""
    assert s[i] == "{", (i, s[i - 20:i + 20])
    depth = 0
    j = i
    while j < len(s):
        c = s[j]
        if c == "\\":
            j += 2
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return s[i + 1:j], j + 1
        j += 1
    raise ValueError("unbalanced braces at %d" % i)


def split_math(text):
    """把文本切成 [(is_math, chunk)]，只识别 $...$（概述里没有 $$ ）。"""
    parts = []
    buf = []
    in_math = False
    i = 0
    while i < len(text):
        c = text[i]
        if c == "\\" and i + 1 < len(text):
            buf.append(text[i:i + 2])
            i += 2
            continue
        if c == "$":
            parts.append((in_math, "".join(buf)))
            buf = []
            in_math = not in_math
            i += 1
            continue
        buf.append(c)
        i += 1
    parts.append((in_math, "".join(buf)))
    return [(m, t) for (m, t) in parts if t != "" or m]


def detex_text(t):
    """文本模式（非数学）LaTeX → Unicode。"""
    # 重音：\H{o} \"{u} \"u \'e \v{c} ...
    def acc_braced(m):
        return ACCENTS.get((m.group(1), m.group(2)), m.group(2))
    t = re.sub(r"\\([Hvcu~=^`'\"])\s*\{(\w)\}", acc_braced, t)
    t = re.sub(r"\\(['\"`^~=])(\w)", acc_braced, t)
    for cmd, ch in (("ss", "ß"), ("o", "ø"), ("O", "Ø"), ("l", "ł"), ("L", "Ł"), ("i", "ı"), ("aa", "å"), ("ae", "æ")):
        # \o{} / \o␣ / {\o} / \o 后紧跟字母时 LaTeX 会吞掉一个空格
        t = re.sub(r"\\" + cmd + r"(?:\{\}|\s+|(?![A-Za-z]))", ch, t)
    t = t.replace("\\textquotesingle", "'")
    t = re.sub(r"\\(?:textnormal|textrm|mbox|text)\{([^{}]*)\}", r"\1", t)
    t = t.replace("\\&", "&").replace("\\%", "%").replace("\\_", "_").replace("\\#", "#")
    t = t.replace("---", "—").replace("--", "–")
    t = t.replace("\\enspace", " ").replace("\\textperiodcentered", "·").replace("\\,", " ").replace("\\ ", " ")
    t = re.sub(r"\\(?:emph|textit|textsl)\{([^{}]*)\}", r"\1", t)
    t = re.sub(r"\\textbf\{([^{}]*)\}", r"\1", t)
    t = re.sub(r"\\texorpdfstring\{([^{}]*)\}\{[^{}]*\}", r"\1", t)
    t = t.replace("~", "\u00a0")
    t = t.replace("``", "“").replace("''", "”").replace("`", "‘")
    t = re.sub(r"\\(?:ldots|dots)", "…", t)
    t = t.replace("{}", "")
    t = re.sub(r"\{([^{}]*)\}", r"\1", t)  # 剩余的纯分组
    return t


def replace_href(text):
    """\\href{url}{label} -> [label](url)（摘要里偶尔内嵌外部链接）。"""
    out = []
    i = 0
    while True:
        j = text.find("\\href", i)
        if j < 0:
            out.append(text[i:])
            break
        out.append(text[i:j])
        k = j + len("\\href")
        url, k = read_group(text, k)
        label, k = read_group(text, k)
        out.append("[%s](%s)" % (label, url.replace("\\_", "_").replace("\\%", "%").replace("\\#", "#")))
        i = k
    return "".join(out)


def detex(text):
    text = replace_href(text)
    out = []
    for is_math, chunk in split_math(text):
        out.append("$" + chunk + "$" if is_math else detex_text(chunk))
    return "".join(out)


def parse_papers(arg4):
    papers = []
    i = 0
    while True:
        j = arg4.find("\\href", i)
        if j < 0:
            break
        k = j + len("\\href")
        url, k = read_group(arg4, k)
        label, k = read_group(arg4, k)
        i = k
        rel = url[len(GITHUB_PREFIX):] if url.startswith(GITHUB_PREFIX) else None
        papers.append({"title": detex(label).strip(), "url": url, "path": unquote(rel) if rel else None})
    return papers


def parse(src):
    """src 是 overview.tex 的全文；返回 (subjects, entries)。

    entries[i] = {id, subject, subject_id, title, desc, papers: [{title, url, path}]}。
    论文是否真实存在（exists）、该家族有没有 Lean 说明（lean）要对照上游文件列表才知道，由 sync_upstream.py 补上。
    """
    entries, subjects, subject = [], [], None
    pos = src.index("\\begin{document}")  # 跳过导言区里的 \newcommand 定义
    pat = re.compile(r"\\cataloguesection(?=\{)|\\resultentry(?=\{)")
    while True:
        m = pat.search(src, pos)
        if not m:
            break
        if m.group(0) == "\\cataloguesection":
            k = m.end()
            name, k = read_group(src, k)
            sid, k = read_group(src, k)
            subject = {"id": int(sid), "name": name.strip()}
            subjects.append(subject)
            pos = k
        else:
            k = m.end()
            num, k = read_group(src, k)
            title, k = read_group(src, k)
            desc, k = read_group(src, k)
            papers, k = read_group(src, k)
            pos = k
            entries.append({
                "id": num.strip(),
                "subject": subject["name"],
                "subject_id": subject["id"],
                "title": detex(title).strip(),
                "desc": detex(re.sub(r"\s+", " ", desc)).strip(),
                "papers": parse_papers(papers),
            })
    return subjects, entries


def leftover_commands(entries):
    """标题/摘要里残留的（非数学模式的）LaTeX 命令及次数；有残留说明 detex 没覆盖到某种写法。"""
    left = {}
    for e in entries:
        for is_math, chunk in split_math(e["title"] + " " + e["desc"]):
            if not is_math:
                for c in re.findall(r"\\[A-Za-z]+", chunk):
                    left[c] = left.get(c, 0) + 1
    return left


def main(argv):
    path = argv[1] if len(argv) > 1 else "overview.tex"
    with open(path, encoding="utf-8") as f:
        subjects, entries = parse(f.read())
    ids = [e["id"] for e in entries]
    print("学科 %d 个，家族 %d 个（编号不重复 %d 个），论文 %d 篇" % (len(subjects), len(entries), len(set(ids)), sum(len(e["papers"]) for e in entries)))
    print("编号范围 %s ~ %s" % (ids[0], ids[-1]))
    print("残留的非数学 LaTeX 命令：", leftover_commands(entries) or "无")


if __name__ == "__main__":
    sys.exit(main(sys.argv))
