#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
RobertNPC —— <<=>> / <<print>> 表达式卫生检查

抓一类**只在运行时才报错**的问题：JS 表达式里混进全角字符。

真实踩过的坑：诊断行里写了

    <<= (… ? 3 : …)>>

但全角空格 U+3000 落在了表达式内部。JS 不把 U+3000 当空白符，
于是运行时抛：

    <<=>>: bad evaluation: SyntaxError: Unexpected token ')'

排查代价很高（错误只指向 <<=>>，不指向具体字符）。

本脚本扫描 twee 里所有 <<= … >> 与 <<print … >> 的内容，
若含全角字符就报出**文件、行号、字符、码位**。

被判为"全角"的范围（JS 语法里不合法的常见中文标点）：
    U+3000 全角空格、U+FF01–U+FF5E 全角 ASCII、
    U+2018/2019/201C/201D 弯引号、U+3001/3002 顿号句号、
    U+FF0C 全角逗号、U+FF1A 全角冒号、U+FF08/FF09 全角括号、
    U+2265 ≥ 、U+2264 ≤ 、U+00D7 × 等常见全角符号。

用法：
    <python> check_expr_chars.py
退出码 0 = 通过，1 = 发现问题。
"""

from __future__ import print_function

import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# JS 表达式里不该出现的字符
BAD_RANGES = [
    (0x3000, 0x3000, "全角空格"),
    (0x3001, 0x3002, "顿号/句号"),
    (0xFF01, 0xFF5E, "全角ASCII"),
    (0x2018, 0x201D, "弯引号"),
    (0x2264, 0x2265, "≤/≥"),
    (0x00D7, 0x00D7, "乘号×"),
    (0x2026, 0x2026, "省略号…"),
    (0x2014, 0x2014, "破折号—"),
]


def classify(ch):
    cp = ord(ch)
    for lo, hi, name in BAD_RANGES:
        if lo <= cp <= hi:
            return name
    return None


# <<= expr >>  和  <<print expr >>
# ⚠️ 不能用正则的 `.*?>>` —— 非贪婪匹配会在**字符串字面量里的 `>>`** 处
#    提前收口。真实踩过的坑：
#        <<= cond ? a.join(' ｜ ') : '（本场还没有脱衣行动）'>>
#    `'>>'` 之类的内容会让匹配在第 126 行中途断掉，于是
#      · 真正的语法错误被漏掉
#      · 扫描到的"表达式"是被截断的半截，检查形同虚设
#    所以这里改成**手动扫描 + 括号/引号配平**来找真正的结尾。
RE_EXPR_START = re.compile(r"<<=\s*|<<print\s+")


def find_exprs(src):
    """
    逐个找出 <<= … >> / <<print … >> 的 (表达式, 起始下标)。
    结尾按 JS 的括号配平 + 引号状态判定，忽略字符串里的 >>。
    """
    results = []
    for m in RE_EXPR_START.finditer(src):
        i = m.end()
        n = len(src)
        depth = 0
        quote = None
        while i < n:
            c = src[i]
            if quote:
                if c == "\\" and i + 1 < n:
                    i += 2
                    continue
                if c == quote:
                    quote = None
                i += 1
                continue
            if c in "'\"`":
                quote = c
                i += 1
                continue
            if c in "([{":
                depth += 1
                i += 1
                continue
            if c in ")]}":
                depth -= 1
                i += 1
                continue
            if depth <= 0 and src.startswith(">>", i):
                results.append((src[m.end():i], m.start()))
                break
            i += 1
    return results


def blank_strings(expr):
    """
    把 JS 字符串/模板字面量的**内容**换成等长空白。

    为什么必须这么做：全角字符出现在**字符串字面量里**是完全合法的，例如
        <<= cond ? t('中文，带标点。') : '你决定不多管闲事，转身走开了。'>>
    「，」「。」在引号内，JS 不会报错。第一版检查器没区分，
    把这类正常写法全报成错误（假阳性），会淹掉真正的问题。

    只保留引号本身，内容抹白，这样"不在引号里的全角字符"仍会被抓到。
    """
    out = []
    i, n = 0, len(expr)
    quote = None          # 当前所处的引号：' " `
    while i < n:
        c = expr[i]
        if quote is None:
            if c in "'\"`":
                quote = c
                out.append(c)
            else:
                out.append(c)
        else:
            if c == "\\" and i + 1 < n:
                # 转义序列整体保留为空白（不含真实字符）
                out.append("  ")
                i += 2
                continue
            if c == quote:
                quote = None
                out.append(c)
            else:
                out.append("\n" if c == "\n" else " ")
        i += 1
    return "".join(out)


def strip_comments(src):
    """把 /* … */ 换成等长空白，避免注释里的示例被误报。"""
    out, i, n = [], 0, len(src)
    blk = False
    while i < n:
        c = src[i]
        nxt = src[i + 1] if i + 1 < n else ""
        if blk:
            if c == "*" and nxt == "/":
                blk = False
                out.append("  ")
                i += 2
                continue
            out.append("\n" if c == "\n" else " ")
        else:
            if c == "/" and nxt == "*":
                blk = True
                out.append("  ")
                i += 2
                continue
            out.append(c)
        i += 1
    return "".join(out)


def main():
    problems = []
    checked = 0

    for name in sorted(os.listdir(HERE)):
        if not name.endswith(".twee"):
            continue
        path = os.path.join(HERE, name)
        src = strip_comments(io.open(path, encoding="utf-8").read())

        for expr, start in find_exprs(src):
            if expr is None:
                continue
            checked += 1
            start_line = src[:start].count("\n") + 1

            # 只看"不在字符串字面量里"的部分，避免把合法的中文文案误报
            scanned = blank_strings(expr)

            # 括号配平自检 —— 这是最实用的一条：
            # 多一个 ')' 或少一个 '(' 都会让 JS 抛 SyntaxError，
            # 而报错只指向 <<=>>，不指向具体位置。真实案例见文件头注释。
            for open_ch, close_ch, label in (("(", ")", "圆括号"),
                                             ("[", "]", "方括号"),
                                             ("{", "}", "花括号")):
                diff = scanned.count(open_ch) - scanned.count(close_ch)
                if diff != 0:
                    problems.append(
                        "%s:%d  表达式%s不配平（%s 比 %s 多 %d 个）—— 会报 SyntaxError\n"
                        "        表达式: %s"
                        % (name, start_line, label, open_ch, close_ch, abs(diff),
                           expr.strip().replace("\n", " ")[:120])
                    )

            for offset, ch in enumerate(scanned):
                kind = classify(ch)
                if kind is None:
                    continue
                # 计算该字符所在行
                line = start_line + expr[:offset].count("\n")
                problems.append(
                    "%s:%d  表达式里有%s %r (U+%04X) —— JS 语法不认它，"
                    "运行时会报 bad evaluation/SyntaxError"
                    % (name, line, kind, ch, ord(ch))
                )

    print("检查了 %d 个 <<=>> / <<print>> 表达式" % checked)
    print("=" * 74)
    if problems:
        # 同一行可能重复报，去重
        seen, uniq = set(), []
        for p in problems:
            if p not in seen:
                seen.add(p)
                uniq.append(p)
        print("发现 %d 处问题：" % len(uniq))
        for p in uniq:
            print("  [全角] %s" % p)
        print("=" * 74)
        return 1
    print("通过：所有 JS 表达式里没有全角字符")
    print("=" * 74)
    return 0


if __name__ == "__main__":
    sys.exit(main())
