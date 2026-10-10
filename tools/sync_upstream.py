#!/usr/bin/env python3
"""与上游 openai/math 同步：取最新快照 → 重新解析 → 写 data/ → 打印"变更报告"。

用法
    python tools/sync_upstream.py                    # 拉取上游 main 的最新快照，更新 data/，打印变更报告
    python tools/sync_upstream.py --src DIR          # 使用已有的上游检出目录（需是 git 仓库，含 overview.tex / history.md）
    python tools/sync_upstream.py --check            # 只检查，不写文件；上游有变化就以退出码 1 结束
    python tools/sync_upstream.py --report out.md    # 同时把报告写成 Markdown 文件（upstream-watch 工作流用它开 Issue）

做了什么
    1. 只取 overview.tex / history.md / README.md 三个小文件，以及 preprints/、lean/docs/ 的"文件清单"
       （用 blobless + sparse 克隆，不下载 780 MB 的论文）。
    2. 用 parse_overview.parse() 解析 overview.tex，按文件清单补上每篇论文是否存在（exists）、
       每个家族是否有 Lean 说明（lean）。
    3. 写 data/families.json 和 data/upstream.json（对应的上游提交、同步日期等，页脚会显示）。
    4. 与旧数据比对，输出报告：家族/论文/Lean 的增减、标题与摘要变化、论文目录改名（修订版）。
       收到报告后，要人工判断哪些指导需要改写（例如被撤回的结果），再在对应的 src/*.txt 里加 warn: 字段。
"""
import argparse
import datetime
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
import parse_overview  # noqa: E402

UPSTREAM_REPO = "openai/math"
UPSTREAM_URL = "https://github.com/%s.git" % UPSTREAM_REPO
UPSTREAM_REF = "main"
CACHE_DIR = os.path.join(REPO_DIR, ".cache", "upstream")
FAMILIES = os.path.join(REPO_DIR, "data", "families.json")
UPSTREAM_JSON = os.path.join(REPO_DIR, "data", "upstream.json")


def git(*args, cwd=None, check=True):
    r = subprocess.run(["git", "-c", "core.quotepath=false", *args], cwd=cwd, capture_output=True, encoding="utf-8")
    if check and r.returncode != 0:
        raise RuntimeError("git %s 失败：%s" % (" ".join(args), (r.stderr or r.stdout).strip()[:400]))
    return r.stdout


def remote_head():
    out = git("ls-remote", UPSTREAM_URL, "refs/heads/" + UPSTREAM_REF)
    return out.split()[0] if out.strip() else ""


def ensure_snapshot(src_dir):
    """返回一个含 overview.tex / history.md 的 git 检出目录。"""
    if src_dir:
        return os.path.abspath(src_dir)
    if not os.path.isdir(os.path.join(CACHE_DIR, ".git")):
        os.makedirs(os.path.dirname(CACHE_DIR), exist_ok=True)
        print("首次同步：克隆上游的目录结构（不含论文，约几十 MB）……", flush=True)
        git("clone", "--depth", "1", "--filter=blob:none", "--no-checkout", UPSTREAM_URL, CACHE_DIR)
        git("sparse-checkout", "init", "--no-cone", cwd=CACHE_DIR)
        git("sparse-checkout", "set", "/overview.tex", "/history.md", "/README.md", cwd=CACHE_DIR)
        git("checkout", UPSTREAM_REF, cwd=CACHE_DIR)
    else:
        git("fetch", "--depth", "1", "origin", UPSTREAM_REF, cwd=CACHE_DIR)
        git("checkout", "--force", "FETCH_HEAD", cwd=CACHE_DIR)
    return CACHE_DIR


def listing(snap):
    """上游 preprints/ 与 lean/docs/ 的全部文件路径。"""
    out = git("ls-tree", "-r", "-z", "--name-only", "HEAD", "--", "preprints", "lean/docs", cwd=snap)
    return {p for p in out.split("\0") if p}


def load_json(path):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return None


def history_latest(snap):
    p = os.path.join(snap, "history.md")
    if not os.path.exists(p):
        return "", ""
    txt = open(p, encoding="utf-8").read()
    m = re.search(r"^## (.+)$", txt, re.M)
    if not m:
        return "", ""
    nxt = re.search(r"^## ", txt[m.end():], re.M)
    body = txt[m.end(): m.end() + nxt.start()] if nxt else txt[m.end():]
    return m.group(1).strip(), body.strip()


def build_data(snap):
    with open(os.path.join(snap, "overview.tex"), encoding="utf-8") as f:
        subjects, entries = parse_overview.parse(f.read())
    paths = listing(snap)
    lean_ids = {m.group(1) for p in paths for m in [re.fullmatch(r"lean/docs/(\d{3})\.md", p)] if m}
    for e in entries:
        e["lean"] = e["id"] in lean_ids
        for p in e["papers"]:
            p["exists"] = bool(p["path"]) and p["path"] in paths
    problems = []
    ids = [e["id"] for e in entries]
    if len(set(ids)) != len(ids):
        problems.append("overview.tex 里有重复的家族编号")
    miss = [(e["id"], p["path"]) for e in entries for p in e["papers"] if not p["exists"]]
    if miss:
        problems.append("%d 篇论文在上游找不到对应文件，例如 %s" % (len(miss), miss[:3]))
    left = parse_overview.leftover_commands(entries)
    if left:
        problems.append("标题/摘要里残留 LaTeX 命令：%s" % left)
    h_title, _ = history_latest(snap)
    meta = {
        "repo": UPSTREAM_REPO,
        "ref": UPSTREAM_REF,
        "commit": git("rev-parse", "HEAD", cwd=snap).strip(),
        "commit_date": git("show", "-s", "--format=%cI", "HEAD", cwd=snap).strip(),
        "commit_subject": git("show", "-s", "--format=%s", "HEAD", cwd=snap).strip(),
        "families": len(entries),
        "papers": sum(len(e["papers"]) for e in entries),
        "lean_families": sum(1 for e in entries if e["lean"]),
        "history_latest": h_title,
    }
    return {"subjects": subjects, "families": entries}, meta, problems


def short(sha):
    return (sha or "")[:7] or "（无）"


def make_report(old, old_meta, new, new_meta, snap):
    O = {f["id"]: f for f in (old or {}).get("families", [])}
    N = {f["id"]: f for f in new["families"]}
    L = ["# 上游同步报告", ""]
    L.append("- 上游：`%s@%s`（%s）" % (UPSTREAM_REPO, short(new_meta["commit"]), new_meta["commit_date"]))
    if old_meta:
        L.append("- 之前对应：`%s`（%s）" % (short(old_meta.get("commit")), old_meta.get("commit_date", "")))
    L.append("- 家族 %d → %d；论文 %d → %d；有 Lean 说明的家族 %d → %d" % (
        len(O), len(N), sum(len(f["papers"]) for f in O.values()), new_meta["papers"],
        sum(1 for f in O.values() if f.get("lean")), new_meta["lean_families"]))
    L.append("")
    changes = 0

    add, rem = sorted(set(N) - set(O)), sorted(set(O) - set(N))
    if add or rem:
        changes += 1
        L.append("## 家族增删")
        for i in add:
            L.append("- 新增 `%s` %s" % (i, N[i]["title"]))
        for i in rem:
            L.append("- 删除 `%s` %s" % (i, O[i]["title"]))
        L.append("")

    tchg = [i for i in N if i in O and N[i]["title"] != O[i]["title"]]
    dchg = [i for i in N if i in O and N[i]["desc"] != O[i]["desc"]]
    schg = [i for i in N if i in O and N[i]["subject_id"] != O[i]["subject_id"]]
    if tchg or dchg or schg:
        changes += 1
        L.append("## 标题/摘要/学科变化（这些家族的指导需要重新核对）")
        for i in sorted(set(tchg) | set(dchg) | set(schg)):
            L.append("- `%s`" % i)
            if i in tchg:
                L.append("  - 标题：%s → %s" % (O[i]["title"], N[i]["title"]))
            if i in dchg:
                L.append("  - 摘要有改动（旧 %d 字 → 新 %d 字）" % (len(O[i]["desc"]), len(N[i]["desc"])))
            if i in schg:
                L.append("  - 学科：%s → %s" % (O[i]["subject"], N[i]["subject"]))
        L.append("")

    pchg = []
    for i in N:
        if i not in O:
            continue
        a = {p["title"]: p["path"] for p in O[i]["papers"]}
        b = {p["title"]: p["path"] for p in N[i]["papers"]}
        gone = [t for t in a if t not in b]
        new_ = [t for t in b if t not in a]
        moved = [t for t in b if t in a and a[t] != b[t]]
        if gone or new_ or moved:
            pchg.append((i, gone, new_, moved))
    if pchg:
        changes += 1
        L.append("## 论文变化（撤回/新增/修订版换了目录）")
        for i, gone, new_, moved in pchg:
            parts = []
            if gone:
                parts.append("移除 %d 篇：%s" % (len(gone), "；".join(t[:60] for t in gone)))
            if new_:
                parts.append("新增 %d 篇：%s" % (len(new_), "；".join(t[:60] for t in new_)))
            if moved:
                parts.append("目录改名 %d 篇（多为修订版）" % len(moved))
            L.append("- `%s` %s：%s" % (i, N[i]["title"][:50], "；".join(parts)))
        L.append("")

    lo = {i for i, f in O.items() if f.get("lean")}
    ln = {i for i, f in N.items() if f.get("lean")}
    if lo != ln:
        changes += 1
        L.append("## Lean 说明变化")
        if ln - lo:
            L.append("- 新增：" + " ".join("`%s`" % i for i in sorted(ln - lo)))
        if lo - ln:
            L.append("- 去掉：" + " ".join("`%s`" % i for i in sorted(lo - ln)))
        L.append("")

    if not changes:
        L.append("解析出的数据与上次完全一致。")
        L.append("")
    h_title, h_body = history_latest(snap)
    if h_title:
        L.append("## 上游 history.md 最新条目：%s" % h_title)
        L.append("")
        L.extend(h_body.splitlines()[:40])
        L.append("")
    L.append("> 下一步：人工判断受影响的指导是否要改写（被撤回/改动的结果尤其要处理），"
             "必要时在对应的 `src/*.txt` 块里加 `warn:` 字段；然后运行 `python tools/build.py --strict`。")
    return "\n".join(L) + "\n", changes


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", help="已有的上游 git 检出目录")
    ap.add_argument("--check", action="store_true", help="只检查，上游有变化时退出码为 1，不写文件")
    ap.add_argument("--report", help="把变更报告另存为 Markdown 文件")
    args = ap.parse_args()

    old, old_meta = load_json(FAMILIES), load_json(UPSTREAM_JSON)
    if args.check and old_meta and not args.src:
        head = remote_head()
        if head and head == old_meta.get("commit"):
            print("上游没有新提交（%s），无需同步。" % short(head))
            return 0

    snap = ensure_snapshot(args.src)
    new, meta, problems = build_data(snap)
    report, changes = make_report(old, old_meta, new, meta, snap)
    meta["synced_at"] = datetime.datetime.now().astimezone().strftime("%Y-%m-%d")   # 取自系统时钟

    sys.stdout.reconfigure(encoding="utf-8")
    print(report)
    for p in problems:
        print("[问题] " + p)
    if args.report:
        with open(args.report, "w", encoding="utf-8", newline="\n") as f:
            f.write(report)
            for p in problems:
                f.write("\n- ⚠️ " + p)

    drift = bool(changes) or not old_meta or old_meta.get("commit") != meta["commit"]
    if args.check:
        return 1 if drift else 0
    if problems:
        print("存在上述问题，未写入 data/。请先处理。")
        return 2
    os.makedirs(os.path.dirname(FAMILIES), exist_ok=True)
    with open(FAMILIES, "w", encoding="utf-8", newline="\n") as f:
        json.dump(new, f, ensure_ascii=False, indent=1)
        f.write("\n")
    with open(UPSTREAM_JSON, "w", encoding="utf-8", newline="\n") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("已写入 data/families.json 与 data/upstream.json（对应上游 %s）。" % short(meta["commit"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
