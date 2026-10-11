#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
RobertNPC —— 块注释卫生检查

抓两类**不会报错、只会让注释文字漏到玩家眼前**的问题：

  1. 块注释（/* … */）外面出现孤立的 `*/`
     → 它会让后面的正文被当注释吃掉，或者让注释尾巴被当正文印出来。
       实例：曾经在注释块后面多打了一个 `*/`，玩家在页面上看到
       「* * ⚠️ 本页结束时**不要** ：那会让战斗按非自愿结算。 */」这种残留。

  2. 块注释里出现不配对的其它 `/*`
     → 嵌套会让注释提前/延后闭合，同样导致文字漏出。

用法：
    <python> check_comments.py
退出码 0 = 通过，1 = 发现问题。
"""

from __future__ import print_function

import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def scan(path):
    """返回 (孤立 */ 列表, 注释内嵌 /* 列表)。行号从 1 开始。"""
    text = io.open(path, encoding="utf-8").read()
    lone_close, nested_open = [], []

    i, n = 0, len(text)
    in_block = False
    block_start = 0
    while i < n:
        two = text[i:i + 2]
        if not in_block:
            if two == "/*":
                in_block = True
                block_start = i
                i += 2
                continue
            if two == "*/":
                lone_close.append(text[:i].count("\n") + 1)
                i += 2
                continue
        else:
            if two == "/*":
                nested_open.append(text[:i].count("\n") + 1)
                i += 2
                continue
            if two == "*/":
                in_block = False
                i += 2
                continue
        i += 1

    unclosed = None
    if in_block:
        unclosed = text[:block_start].count("\n") + 1
    return lone_close, nested_open, unclosed


def main():
    problems = []
    checked = 0
    for name in sorted(os.listdir(HERE)):
        if not name.endswith(".twee"):
            continue
        checked += 1
        path = os.path.join(HERE, name)
        lone, nested, unclosed = scan(path)
        for line in lone:
            problems.append("%s:%d  注释块外出现孤立的 */（会让正文漏字或印出注释尾巴）"
                            % (name, line))
        for line in nested:
            problems.append("%s:%d  注释块内又出现 /*（嵌套会让注释提前闭合）"
                            % (name, line))
        if unclosed is not None:
            problems.append("%s:%d  注释块没有闭合（缺 */）" % (name, unclosed))

    print("检查了 %d 个 twee 文件的块注释" % checked)
    print("=" * 74)
    if problems:
        print("发现 %d 处注释卫生问题：" % len(problems))
        for p in problems:
            print("  [注释] %s" % p)
        print("=" * 74)
        return 1
    print("通过：没有孤立 */、没有嵌套 /*、所有注释块都已闭合")
    print("=" * 74)
    return 0


if __name__ == "__main__":
    sys.exit(main())
