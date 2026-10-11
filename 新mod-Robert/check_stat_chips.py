#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
RobertNPC —— 属性提示宏（彩色小标签）自检
===========================================================================

本 mod 的书写规范（需求方 2026-10 确定）
---------------------------------------------------------------------------
**提示的符号个数 = 数值幅度。**

    一个 +  → <<gdom "Robert">>   且 addStat('dom', +1)
    两个 +  → <<ggdom "Robert">>  且 addStat('dom', +2)
    两个 -  → <<lldom "Robert">>  且 addStat('dom', -2)
    三个 -  → <<llldom "Robert">> 且 addStat('dom', -3)

需求方以后只会说「这是一个 +／两个 +／两个 -」，提示与数值**一起**定下来，
两边永远一致。单次增减控制在 1–3 档（原版变体最多到 3）。

以前踩过的三类错（都不会报错，只有跑起来看界面才发现）
---------------------------------------------------------------------------
  1. **参数写成数量**：`<<glust 8>>` → 渲染成「+ 8的性欲」。
     这些宏的参数是 **NPC 名**（ModI18N 里是
     `statDisplay.statChange(`${setup.NPC_CN_NAME(npc)}的性欲`, 1, "lewd")`，
     非字符串参数原样返回）。
  2. **叠提示块凑幅度**：`<<lldom>><<lldom>><<ldom>>` 想表达 −5，
     实际是三个块、共 5 个减号（<<ldom>>=−1、<<lldom>>=−2 本身就是档位）。
  3. **标签硬编码英文**：`statDisplay.statChange("Rage", 1, "gold")` ——
     第一个参数是显示文本，中文界面里会单独冒出一个英文词。

本脚本的六条规则
---------------------------------------------------------------------------
  A. 需要 NPC 名的提示宏，参数不能是数量；
  B. 同一行里同一个提示宏不能出现两次以上；
  C. 自建提示宏的标签不能硬编码英文；
  D. 提示宏不能写进链标 `[[…]]`；
  E. **同一行**里 addStat(属性, N) 与提示宏的符号数必须一致（方向也要一致）；
  F. **同一段落**里，每个属性的「addStat 幅度集合」与「提示符号集合」必须相等；
     有 addStat 却整段没有提示 → 提醒（不失败）。

用法：
    <python> check_stat_chips.py
退出码 0 = 通过，1 = 发现问题。
"""

from __future__ import print_function

import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# 提示宏 → (属性, 带符号幅度)。全部列出来，避免正则猜错名字。
CHIP_TABLE = {
    "glust": ("lust", 1), "gglust": ("lust", 2), "ggglust": ("lust", 3),
    "llust": ("lust", -1), "lllust": ("lust", -2), "llllust": ("lust", -3),
    "glove": ("love", 1), "gglove": ("love", 2), "ggglove": ("love", 3),
    "llove": ("love", -1), "lllove": ("love", -2), "llllove": ("love", -3),
    "gdom": ("dom", 1), "ggdom": ("dom", 2), "gggdom": ("dom", 3),
    "ldom": ("dom", -1), "lldom": ("dom", -2), "llldom": ("dom", -3),
    "grage": ("rage", 1), "ggrage": ("rage", 2), "gggrage": ("rage", 3),
    "lrage": ("rage", -1), "llrage": ("rage", -2), "lllrage": ("rage", -3),
}

# 幅度由运行时决定的提示 widget：它们自己会挑正确的变体，
# 所以静态检查时视为「任意 1–3 档的正向爱意提示」。
DYNAMIC_CHIPS = {"robertLoveChip": ("love", +1)}

# 原版里需要 NPC 名的家族（用于规则 A：这些宏不能接数字）。
NPC_CHIP_RE = re.compile(
    r"<<((?:g|l)+(?:lust|love|dom)|(?:g|l)+rage)((?:\s+[^>]*?)?)>>")

CHIP_RE = re.compile(r"<<(\w+)((?:\s+[^>]*?)?)>>")
ADD_RE = re.compile(r"addStat\?\.\(\s*'(\w+)'\s*,\s*(-?\d+)\s*\)")

MAX_TIER = 3


def read(path):
    with io.open(path, encoding="utf-8") as fh:
        return fh.read()


def strip_comments(src):
    """把 /* … */ 换成等量空白（保留换行，行号不漂移）。"""
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
    """切成 [(段落名, 起始行号, 正文)]。"""
    marks = list(re.finditer(r"^::[ \t]*([^\[\n]+?)[ \t]*(?:\[[^\]]*\])?[ \t]*$", src, re.M))
    out = []
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(src)
        start_line = src[:m.start()].count("\n") + 1
        out.append((m.group(1).strip(), start_line, src[m.end():end]))
    return out


WIDGET_RE = re.compile(r'<<widget\s+"([^"]+)"\s*>>(.*?)<</widget>>', re.S)


def scopes(pname, start_line, body):
    """把段落切成若干**作用域**：顶层文本 + 每个 <<widget>> 的正文。

    规则 F 必须按作用域比对，不能按整个段落 —— 一个 [widget] 段落里
    可以塞十几个 widget，各自的数值与提示互不相干，
    混在一起比对会把「定义提示宏的 widget」也算进来（会误报）。
    """
    out = []
    pos = 0
    for m in WIDGET_RE.finditer(body):
        head = body[pos:m.start()]
        if head.strip():
            out.append((pname, start_line, head))
        wline = start_line + body[:m.start()].count("\n")
        out.append(('%s → widget "%s"' % (pname, m.group(1)), wline, m.group(2)))
        pos = m.end()
    tail = body[pos:]
    if tail.strip():
        out.append((pname, start_line, tail))
    return out


def chips_in(text):
    """返回 [(宏名, 属性, 带符号幅度)]，只含有数值含义的那些。"""
    found = []
    for m in CHIP_RE.finditer(text):
        name = m.group(1)
        if name in CHIP_TABLE:
            fam, amount = CHIP_TABLE[name]
            found.append((name, fam, amount))
        elif name in DYNAMIC_CHIPS:
            fam, _ = DYNAMIC_CHIPS[name]
            found.append((name, fam, None))       # None = 幅度由运行时决定
    return found


def main():
    problems = []
    warnings = []
    checked = 0

    for name, path in twee_files():
        src = strip_comments(read(path))
        lines = src.split("\n")

        # ---------- 行级规则 A / B / D / E ----------
        for lineno, line in enumerate(lines, 1):
            calls = list(CHIP_RE.finditer(line))
            checked += len(calls)

            # A. 参数不能是数量
            for m in NPC_CHIP_RE.finditer(line):
                macro, args = m.group(1), m.group(2).strip()
                if not args:
                    continue
                head = args.split()[0]
                if re.match(r"^[0-9]", head) or head[0] in "+-":
                    problems.append(
                        "%s:%d  <<%s %s>> —— 参数是**数量**，但该宏要的是 **NPC 名**；"
                        "会渲染成「+ %s的XX」。幅度请改用对应的宏变体（一个 + = +1…）。"
                        % (name, lineno, macro, args, head))

            # B. 同一行同一个提示宏叠用
            seen = {}
            for m in calls:
                seen.setdefault(m.group(1), []).append(m)
            for macro, items in seen.items():
                if macro in CHIP_TABLE and len(items) > 1:
                    problems.append(
                        "%s:%d  <<%s>> 在同一行出现 %d 次 —— 提示宏的前缀本身就是档位"
                        "（<<ldom>>=−1、<<lldom>>=−2），**一个属性只给一个提示块**，"
                        "幅度靠选对应变体，不靠叠块。"
                        % (name, lineno, macro, len(items)))

            # D. 提示宏不能写进链标
            for m in re.finditer(r"\[\[[^\]\n]*", line):
                if CHIP_RE.search(m.group(0)):
                    problems.append(
                        "%s:%d  提示宏被写进了链标 [[…]] —— DoL 的 link 宏对链标取 "
                        ".textContent，HTML 会被剥掉，颜色丢失且文字错位。"
                        "提示宏必须是 <<link>> 的**兄弟节点**。" % (name, lineno))

            # E. 同一行的「数值 vs 符号个数」
            adds = [(m.group(1), int(m.group(2))) for m in ADD_RE.finditer(line)]
            if adds:
                for key, val in adds:
                    if abs(val) > MAX_TIER:
                        problems.append(
                            "%s:%d  addStat('%s', %d) 超过 %d 档 —— 没有对应的提示变体，"
                            "请拆成多次或先跟需求方确认。"
                            % (name, lineno, key, val, MAX_TIER))
                    same = [c for c in chips_in(line) if c[1] == key]
                    if len(same) == 1 and same[0][2] is not None:
                        _, _, amount = same[0]
                        if amount != val:
                            problems.append(
                                "%s:%d  addStat('%s', %+d) 与提示 <<%s>>（%+d）不一致 —— "
                                "**符号个数必须等于数值幅度**。"
                                % (name, lineno, key, val, same[0][0], amount))

        # ---------- 段级规则 C / F ----------
        for pname, start_line, body in split_passages(src):
            # C. statChange 的标签不能是硬编码英文
            for m in re.finditer(r"statDisplay\.statChange\(\s*([^,]+),", body):
                label = m.group(1).strip()
                lineno = start_line + body[:m.start()].count("\n")
                if re.match(r"^[\"']", label):
                    inner = label[1:-1]
                    if re.search(r"[A-Za-z]", inner) and not re.search(r"[\u4e00-\u9fa5]", inner):
                        problems.append(
                            "%s:%d  statDisplay.statChange 的标签是硬编码英文 %s —— "
                            "中文界面里会单独冒出一个英文词；请走 "
                            "RobertNPC.chipLabel('rage') 或翻译表。"
                            % (name, lineno, label))

            # F. 作用域内「数值集合」vs「提示集合」
            for scope_name, scope_line, scope_body in scopes(pname, start_line, body):
                adds, chips = {}, {}
                for m in ADD_RE.finditer(scope_body):
                    key, val = m.group(1), int(m.group(2))
                    if key in ("rage", "lust", "love", "dom"):
                        adds.setdefault(key, []).append(val)
                for _, fam, amount in chips_in(scope_body):
                    if amount is not None:
                        chips.setdefault(fam, []).append(amount)
                for key, vals in adds.items():
                    got = chips.get(key, [])
                    if not got:
                        # 动态提示 widget（如 <<robertLoveChip>>）也算有提示
                        if any(c[1] == key for c in chips_in(scope_body)):
                            continue
                        warnings.append(
                            "%s 作用域「%s」：改了 %s（%s）但这里没有对应提示块。"
                            % (name, scope_name, key, ", ".join("%+d" % v for v in vals)))
                        continue
                    if sorted(vals) != sorted(got):
                        problems.append(
                            "%s 作用域「%s」：%s 的数值 %s 与提示 %s 不匹配"
                            "（每个数值都要有**同幅度同方向**的提示，符号个数 = 幅度）。"
                            % (name, scope_name, key,
                               ", ".join("%+d" % v for v in sorted(vals)),
                               ", ".join("%+d" % v for v in sorted(got))))

    print("检查了 %d 个提示宏调用（%d 个文件）" % (checked, len(twee_files())))
    print("=" * 74)
    for w in warnings:
        print("  [提醒] %s" % w)
    if problems:
        print("提示宏自检失败（%d 项）：" % len(problems))
        for p in problems:
            print("  [错误] %s" % p)
        print("=" * 74)
        return 1
    print("提示宏自检通过：")
    print("  · 符号个数 = 数值幅度（行级 + 段级双向核对）")
    print("  · 参数都是 NPC 名；没有叠提示块；没有硬编码英文标签；没有写进链标")
    print("  · 单次增减都在 1–3 档以内")
    print("=" * 74)
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    sys.exit(main())
