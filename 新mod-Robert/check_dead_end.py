#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
RobertNPC —— 死路页面自检（「has no usable links」防护）
===========================================================================

为什么需要它
---------------------------------------------------------------------------
SugarCube 在**段落一个可用链接都没有**时抛红字：

    The passage Robert Taxi has no usable links.

这类错误静态看代码很难发现，因为它取决于**分支与运行时状态**。
本项目踩过一次（真实案例）：

    :: Robert Taxi
    <<unset $bus>>                       ← 清掉上一次残留的目的地
    <<if $money gte 500>>
        …目的地链接（<<link>>）…          ← 有钱时：一堆链接
    <<else>>
        你的钱不够付车费。                ← 没钱时：只有一句话，没有链接
    <</if>>
    <<destination>>                      ← 按 $bus 分派 <<Xquick>> 链接；
                                            $bus 被 unset 后它什么都不渲染

    结果：钱 < £5 时整页没有任何链接 ⇒ 红字。
    原版 <<Bus>> 段落有同样的结构却没暴露问题，只是因为它**不** unset $bus，
    残留值恰好提供了几条可用链接 —— 属于「靠巧合活着」，不能照抄。

本脚本做什么
---------------------------------------------------------------------------
把每个段落拆成「分支」（<<if>> / <<elseif>> / <<else>> 的每一支 + 顶层），
逐支检查：**这一支输出了正文文字，就必须在这一支里给出至少一个链接来源**。

链接来源包括：
  · <<link>> / <<goto>> / <<add_link>>
  · 本 mod 的链接型 widget：<<robertOption>> / <<robertLewdOption>> /
    <<robertArousalOption>> / <<robertTaxiArriveLink>> / <<robertRideEvent>>

**不算**链接来源的（重要）：
  · <<destination>> —— 它按 $bus 分派，$bus 为空时一个链接都不出；
  · <<nexttext>> 之类的纯文本宏。

用法：
    <python> check_dead_end.py
退出码 0 = 通过，1 = 发现死路分支。
"""

from __future__ import print_function

import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# 会被当作「提供了链接」的宏 / widget
LINK_MACROS = [
    "link", "goto", "add_link", "button",
    "robertOption", "robertLewdOption", "robertArousalOption",
    "robertTaxiArriveLink", "robertRideEvent",
]

LINK_RE = re.compile(r"<<(/?)(?:" + "|".join(LINK_MACROS) + r")\b")

# 「正文文字」的判据：出现中日韩字符（本 mod 的正文全是中文）。
# 用 CJK 而不是「任意非空白字符」，避免把宏、HTML、英文变量名误判成正文。
TEXT_RE = re.compile(r"[\u4e00-\u9fa5\u3000-\u303f\uff00-\uffef]")

BLOCK_OPEN = {"if", "for", "switch", "widget", "silently", "capture"}
BLOCK_MID = {"elseif", "else", "case", "default"}
MACRO_RE = re.compile(r"<<(/?)([A-Za-z_][\w-]*)((?:\s+(?:\"(?:[^\"\\]|\\.)*\"|'(?:[^'\\]|\\.)*'|`[^`]*`|[^>\s]+))*)\s*(/?)>>", re.S)


def read(path):
    with io.open(path, encoding="utf-8") as fh:
        return fh.read()


def strip_comments(src):
    return re.sub(r"/\*.*?\*/", lambda m: re.sub(r"[^\n]", " ", m.group(0)), src, flags=re.S)


def twee_files():
    boot = os.path.join(HERE, "boot.json")
    names = []
    if os.path.isfile(boot):
        with io.open(boot, encoding="utf-8") as fh:
            names = json.load(fh).get("tweeFileList", [])
    if not names:
        names = sorted(f for f in os.listdir(HERE) if f.endswith(".twee"))
    return [(n, os.path.join(HERE, n.replace("/", os.sep))) for n in names
            if os.path.isfile(os.path.join(HERE, n.replace("/", os.sep)))]


def split_passages(src):
    marks = list(re.finditer(r"^::[ \t]*([^\[\n]+?)[ \t]*(?:\[([^\]]*)\])?[ \t]*$", src, re.M))
    out = []
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(src)
        out.append((m.group(1).strip(), (m.group(2) or "").strip(),
                    src[:m.start()].count("\n") + 1, src[m.end():end]))
    return out


WIDGET_BODY_RE = re.compile(r'<<widget\s+"[^"]+"\s*>>.*?<</widget>>', re.S)


def branch_spans(body):
    """把正文切成：
         always  —— 顺序执行、一定会渲染的片段列表
         groups  —— 每个顶层 <<if>> 构造的「各分支片段」列表，元素是 (种类, 文本)，
                   种类 ∈ {"if", "elseif", "else"}

    ⚠️ 只有**互斥分支**才需要各自带链接。判定「这一页是否总能给出链接」用两条：
         1. 顺序执行区里有链接（顺序区一定会跑）；
         2. 某个顶层 `if/elseif/**else**` 的**每一支**都有链接 ——
            而且**必须带 <<else>>**：没有 else 的 if 有可能一整支都不执行，
            不能算作链接来源（第一版就是漏了这条，导致反例回归测不出来）。
    """
    always, groups = [], []
    depth = 0
    cur = 0            # 顺序区起点
    span = 0           # 当前分支起点
    current = None     # 当前顶层 if 的分支列表 [(种类, 文本)]
    kind = None
    for m in MACRO_RE.finditer(body):
        closing, name = m.group(1), m.group(2)
        if name == "if":
            if not closing:
                if depth == 0:
                    if m.start() > cur:
                        always.append(body[cur:m.start()])
                    current = []
                    kind = "if"
                    span = m.end()
                depth += 1
            else:
                if depth == 0:
                    # 结构不配对（缺 <<if>>）—— 跳过而不是崩，让后面的检查继续跑
                    continue
                depth -= 1
                if depth == 0 and current is not None:
                    current.append((kind, body[span:m.start()]))
                    groups.append(current)
                    current = None
                    kind = None
                    cur = m.end()
        elif name in ("elseif", "else") and not closing and depth == 1:
            if current is None:
                continue                     # 结构不正常（缺 <<if>>），跳过而不是崩
            current.append((kind, body[span:m.start()]))
            kind = name
            span = m.end()
    if cur < len(body):
        always.append(body[cur:])
    return always, groups


def check_passage(name, pname, tags, start_line, raw_body):
    """检查单个段落，返回问题列表（供 main 与单测复用）。"""
    problems = []
    branch_count = 0

    # [widget] 段落永远不会被渲染，不参与判定
    if "widget" in tags.split():
        return problems, branch_count
    # widget 定义体不在这里渲染（由调用它的页面负责给链接）
    body = WIDGET_BODY_RE.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), raw_body)

    always, groups = branch_spans(body)
    page_has_link = bool(LINK_RE.search(body))
    always_link = any(LINK_RE.search(t) for t in always)
    # ⚠️ 必须带 <<else>> 才「一定选中一支」；没有 else 的 if 可能整支跳过。
    complete_if = any(
        any(k == "else" for k, _ in group) and all(LINK_RE.search(t) for _, t in group)
        for group in groups)
    covered = always_link or complete_if

    if not page_has_link and TEXT_RE.search(body):
        problems.append(
            "%s:%d  段落「%s」整页没有任何链接来源 —— 打开它就会报 "
            "「The passage %s has no usable links.」"
            % (name, start_line, pname, pname))
        return problems, branch_count

    # 分支优先：分支里的死路最具体、最好改
    for group in groups:
        for _, text in group:
            branch_count += 1
            if not TEXT_RE.search(text):
                continue                     # 没有正文文字的分支不用管
            if covered or LINK_RE.search(text):
                continue
            pos = body.find(text)
            lineno = start_line + (body[:pos].count("\n") if pos >= 0 else 0)
            snippet = re.sub(r"\s+", " ", text).strip()[:48]
            problems.append(
                "%s:%d  段落「%s」的这一支有正文却没有链接来源（页面别处也没有"
                "「顺序执行的链接」或「每支都有链接且带 else 的 if」可以覆盖它）—— "
                "运行时走到这一支就会报 「The passage %s has no usable links.」\n"
                "           该支内容：「%s…」"
                % (name, lineno, pname, pname, snippet))

    # 分支都干净时才看顺序区：页面若不能保证给出链接，顺序区里的裸文字同样是死路。
    # 形状长这样（踩过）：
    #     <<if $money gte 500>><<link …>><</if>>      ← 只有这一支有链接，可能整支跳过
    #     你的钱不够付车费。                            ← 顺序区裸文字
    if not covered and not problems:
        for text in always:
            if not TEXT_RE.search(text) or LINK_RE.search(text):
                continue
            pos = body.find(text)
            lineno = start_line + (body[:pos].count("\n") if pos >= 0 else 0)
            snippet = re.sub(r"\s+", " ", text).strip()[:48]
            problems.append(
                "%s:%d  段落「%s」的顺序正文没有链接，而页面里的链接都藏在可能整支跳过的 "
                "<<if>> 里 —— 那些条件不成立时这一页就是死路（会报 "
                "「The passage %s has no usable links.」）\n"
                "           该处内容：「%s…」"
                % (name, lineno, pname, pname, snippet))
            break
    return problems, branch_count


def main():
    problems = []
    total = 0

    for name, path in twee_files():
        src = strip_comments(read(path))
        for pname, tags, start_line, body in split_passages(src):
            found, n = check_passage(name, pname, tags, start_line, body)
            problems.extend(found)
            total += n

    print("检查了 %d 个互斥分支（只统计会渲染的段落）" % total)
    print("=" * 74)
    if problems:
        print("死路分支自检失败（%d 处）：" % len(problems))
        for p in problems:
            print("  [错误] %s" % p)
        print()
        print("  提示：给该分支补一个 <<link>> / <<goto>>，")
        print("        或用本 mod 的链接型 widget（<<robertOption>> 等）。")
        print("        ⚠️ <<destination>> 不算链接来源 —— 它按 $bus 分派，")
        print("           $bus 为空时一个链接都不出（这就是 Robert Taxi 那次的成因）。")
        print("=" * 74)
        return 1
    print("死路分支自检通过：每个输出正文的互斥分支都有链接来源。")
    print("=" * 74)
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    sys.exit(main())
