<div align="center">

<img src="assets/og.png" alt="数学小白导览" width="760">

# 数学小白导览

**把 OpenAI 公开的数学前沿问题，讲给“数学小白”听。**

一句话版本 · 大白话提问 · 生活类比 · 先备积木 · 学习阶梯 · 互动实验<br>
全中文，免费开源，不用注册，下载离线版后不联网也能读。

[**🌐 在线阅读**](https://gezip.github.io/openai-math-study/) ·
[📦 离线版](https://github.com/GeziP/openai-math-study/releases/latest) ·
[🐞 报告问题](https://github.com/GeziP/openai-math-study/issues/new?template=correction.yml) ·
[English](#english)

[![构建并发布网站](https://github.com/GeziP/openai-math-study/actions/workflows/pages.yml/badge.svg)](https://github.com/GeziP/openai-math-study/actions/workflows/pages.yml)
![code: MIT](https://img.shields.io/badge/code-MIT-3b82f6)
![text: CC BY 4.0](https://img.shields.io/badge/text-CC%20BY%204.0-8b5cf6)
![unofficial](https://img.shields.io/badge/OpenAI-unofficial-lightgrey)

</div>

---

## 这是什么

OpenAI 在 GitHub 上公开了一个数学仓库 [openai/math](https://github.com/openai/math)：里面是内部模型产出的研究论文，整理成 **372 个“结果家族”**（共 719 篇）。它们的摘要是写给专业数学家的，普通人很难读下去。

这个项目为**每一个家族**补上面向零基础读者的学习指导，做成可以直接访问的网站：

- 先用一句不含术语的话讲清楚“这个问题在折腾什么”；
- 再用大白话和日常类比讲它到底在问什么、结果是什么、为什么重要；
- 列出看懂陈述所需的“先备积木”，常用词汇收在词汇表里；
- 给出一条从初中到前沿的学习阶梯，附关键词，一键搜索维基和 B 站；
- 能动手的地方做成互动实验：拖一拖滑块，现象就在眼前。

**论文本身仍在上游仓库，不在本站。** 页面上的论文链接都指向上游 GitHub。

<table>
<tr>
<td width="50%"><img src="docs/img/home.png" alt="首页：非官方、免费、全中文"><br><sub>首页：一眼看清是什么、有多少、怎么开始</sub></td>
<td width="50%"><img src="docs/img/problem.png" alt="问题页：一句话看懂、这个问题到底在问什么"><br><sub>问题页：先“一句话看懂”，再慢慢展开</sub></td>
</tr>
<tr>
<td><img src="docs/img/subjects.png" alt="17 个学科地图"><br><sub>17 个学科，每幅配图都是用数学本身画出来的</sub></td>
<td><img src="docs/img/lab.png" alt="互动实验：混沌游戏"><br><sub>互动实验：随机跳点，长出谢尔宾斯基三角形</sub></td>
</tr>
</table>

## 内容一览

> 以下数字对应上游提交 [`fd4aeeb`](https://github.com/openai/math/commit/fd4aeeb2ee4fc729c18d98444fed42fd0529eeeb)，网站页脚始终标明当前对应的上游版本。

| | |
|---|---|
| 问题页 | 372 个，每页都有门槛 ★1～5（读懂**问题陈述**需要的数学水平，不是证明的难度） |
| 学科 | 17 个，每个先讲“它在研究什么”，再按从易到难列出问题 |
| 词汇表 | 271 个词条，问题页里的“先备积木”点开就能查 |
| 互动实验 | 39 个，单个网页，素数、分形、渗流、伊辛模型、混沌……，不用联网 |
| 学习路线 | 按基础挑起点；还有“已学”进度，只存在你的浏览器里，可导出/导入 |

## 先说清楚（诚实说明）

- **非官方。** 与 OpenAI 无隶属关系，也未获其背书；本站不对论文证明的正确性做担保。上游 README 自己写明：这些结果处于不同的验证阶段，并非都有 Lean 形式化，没有形式化的部分可能有问题。
- **指导由 AI 辅助撰写**，经过自动化检查（链接、公式、结构），**没有人工逐篇审校**，难免有错——每页底部都有“报告问题”入口。
- 类比是为了建立直觉，必然丢失精确性；遇到分歧以原文摘要为准。互动实验只演示很小规模的情形，**不能代替证明**。
- 上游撤回或更正过的结果，页面会加醒目提醒；仓库里有个每天运行的脚本比对上游，有变化就自动开 Issue（见 [`upstream-watch`](.github/workflows/upstream-watch.yml)）。

## 本地使用

只需要 Python 3（标准库即可）：

```bash
git clone https://github.com/GeziP/openai-math-study.git
cd openai-math-study
python tools/build.py          # 生成 _site/
python tools/preview.py        # 浏览 http://127.0.0.1:8770/openai-math-study/
```

想离线读：到 [Releases](https://github.com/GeziP/openai-math-study/releases/latest) 下载 `math-study-guide-offline-*.zip`，解压后双击 `index.html`。

## 参与

发现讲错了、讲得不清楚、链接失效？在页面底部点“报告问题”，或直接[开个 Issue](https://github.com/GeziP/openai-math-study/issues/new?template=correction.yml)。想改写某个问题的讲法、补一个互动实验，欢迎提 PR，细则见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 许可与署名

| 内容 | 许可 |
|---|---|
| 指导文字与图片（`src/`、生成的页面文字、配图） | [CC BY 4.0](LICENSE-CONTENT)：转载、改编、商用都可以，署名并注明是否修改 |
| 代码（`tools/`、`assets/` 里的脚本与样式、`labs_src/`、`.github/`） | [MIT](LICENSE) |
| `data/` 里取自上游的标题与摘要 | 保留上游的 Apache-2.0，署名与修改说明见 [NOTICE](NOTICE) |
| [KaTeX](https://katex.org)（`assets/katex/`） | MIT，许可证随文件收录 |

署名示例：“数学小白导览”，GeziP/openai-math-study，https://github.com/GeziP/openai-math-study ，CC BY 4.0

如果它对你有帮助，欢迎点个 ⭐，也欢迎把它转给想入门数学的朋友。

---

## English

**Math for Beginners — a plain-language reading guide to OpenAI's open math problems** (site and text in Chinese).

[openai/math](https://github.com/openai/math) publishes research manuscripts produced by an internal OpenAI model, grouped into 372 result families. Their abstracts are written for specialists. This unofficial project adds a beginner-friendly guide for every family: a one-sentence version, an everyday analogy, the prerequisite concepts, a learning ladder from middle school to the research frontier, a glossary, and 39 interactive labs. Papers stay in the upstream repository; every link points there.

- Live site: <https://gezip.github.io/openai-math-study/> · offline zip on the [Releases](https://github.com/GeziP/openai-math-study/releases/latest) page
- Static site built with a stdlib-only Python generator (`python tools/build.py`); math rendered offline with KaTeX
- The guide text is AI-assisted and **not** reviewed line by line by a human; it makes no claim about the correctness of the manuscripts. Please [report errors](https://github.com/GeziP/openai-math-study/issues/new?template=correction.yml)
- Licenses: code MIT, text and images CC BY 4.0, upstream-derived data keeps Apache-2.0 (see [NOTICE](NOTICE)). Not affiliated with or endorsed by OpenAI
