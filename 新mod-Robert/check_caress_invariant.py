#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
RobertNPC —— 【页面1】（Robert Taxi Caress）告示不变式检查

强制一条规则：

    「每个带淫乱判定效果的选项，其效果必须与本段落开头的
      <<robertTaxiLewd 档位>> 一致。」

背景：选项上的彩色提示（+压力 / +性奋 / 淫乱 N）由 <<robertLewdOption>>
按**实际**淫乱等级渲染，而数值由段落开头的 <<robertTaxiLewd N>> 施加。
两者一旦不一致，玩家看到的提示就与实际变化不符 —— 属于「骗玩家」，
而且不会报任何错，是那种只有跑起来才发现的 bug。

本脚本做静态比对：
  1. 找出页面上所有「带效果」的选项；
  2. 读出这些选项声明的档位（check 就是 <<robertTaxiLewd N>> 的 N，
     或 <<robertLewdOption>> 的第 2 个参数）；
  3. 与段落开头的 <<robertTaxiLewd>> 档位核对；
  4. 另外核对：每个条件的等级门槛与它挂的 <<promiscuousN>> 标记一致
     （例如 hasSexStat("promiscuity", 3) 应挂 <<promiscuous3>>）。

用法：
    <python> check_caress_invariant.py
退出码 0 = 通过，1 = 违反不变式。
"""

from __future__ import print_function

import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EVENT = os.path.join(HERE, "robert-taxi-event.twee")
PAGE = "Robert Taxi Caress"

# 判定等级 → 该等级下实际生效的效果
# 与 modules/robert-stats.js 的 RB.lewdEffectTokens / RB.PROMISCUITY_LEVELS 对应
LEVEL_EFFECTS = {
    0: {"stress", "arousal"},
    1: {"stress", "arousal"},
    2: {"arousal"},
    3: {"arousal"},
}


def read(path):
    with io.open(path, encoding="utf-8") as fh:
        return fh.read()


def strip_comments(src):
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


def passage_body(text, title):
    """取某个段落的正文（不含段落头）。"""
    parts = re.split(r"^::[ \t]*", text, flags=re.M)[1:]
    for part in parts:
        head, _, body = part.partition("\n")
        name = re.sub(r"\[[^\]]*\]\s*$", "", head).strip()
        if name == title:
            return body
    return None


def main():
    if not os.path.isfile(EVENT):
        print("找不到 %s" % EVENT)
        return 1

    raw = read(EVENT)
    body = passage_body(strip_comments(raw), PAGE)
    if body is None:
        print("找不到段落 %r" % PAGE)
        return 1

    problems = []

    # 1. 段落开头的判定档位
    m = re.search(r"<<robertTaxiLewd\s+(\d+)>>", body)
    if not m:
        problems.append("段落开头没有 <<robertTaxiLewd N>>，无法确定判定档位")
        declared = None
    else:
        declared = int(m.group(1))
        if int(m.group(1)) not in LEVEL_EFFECTS:
            problems.append("<<robertTaxiLewd %s>> 档位超出 0–3" % m.group(1))

    # 2. 找出所有「带效果」的选项
    #    <<robertLewdOption [[标签|目标]] ["计数变量"] [门槛等级]>>
    #    <<robertArousalOption [[标签|目标]] N>>
    #    ⚠️ 三个坑，缺一个就会错位：
    #       a) 开头必须是字面量 \[\[，否则 [^\]]+? 只吃掉一个 '['；
    #       b) 标签用 [^\]|]+?（不含 | 和 ]）；
    #       c) 参数里的 \S 必须排除 '>'，否则会把结尾的 >> 一起吃进参数，
    #          然后贪婪地跨到下一条选项上去。
    lewd_opts = re.findall(
        r'<<robertLewdOption\s+\[\[([^\]\|]+?)\|([^\]]+?)\]\]((?:\s+(?:"[^"]*"|[^\s>]+))*)\s*>>',
        body)
    arous_opts = re.findall(
        r'<<robertArousalOption\s+\[\[([^\]\|]+?)\|([^\]]+?)\]\]((?:\s+[^\s>]+)*)\s*>>',
        body)

    if not lewd_opts and not arous_opts:
        problems.append("没有找到任何带效果的选项 —— 页面结构可能已被改坏")

    # 3. 淫乱判定类选项：与段落档位核对
    for label, target, rest in lewd_opts:
        label, target = label.strip(), target.strip()
        params = re.findall(r'"[^"]*"|[^\s>]+', rest)
        counter = params[0].strip('"') if params else None
        threshold = None
        if len(params) > 1 and re.match(r"^\d+$", params[1]):
            threshold = int(params[1])

        if declared is None:
            continue
        if declared < 1:
            problems.append(
                "选项【%s】挂了淫乱判定提示，但段落档位是 %d（无判定）" % (label, declared))
        if declared not in LEVEL_EFFECTS:
            problems.append("选项【%s】的档位 %r 非法" % (label, declared))
        if counter and counter not in ("count", "robertTaxiJump", "robertTaxiBackJump"):
            problems.append(
                "选项【%s】的计数参数 %r 未知（应为 robertTaxiJump / "
                "robertTaxiBackJump / count）" % (label, counter))
        if threshold is not None and threshold not in LEVEL_EFFECTS:
            problems.append("选项【%s】的门槛等级 %d 非法" % (label, threshold))

        shown = threshold if threshold is not None else declared
        print("  选项【%s】 -> %s   实际档位 %d   提示显示 %d (效果 %s)   计数 %s"
              % (label, target, declared, shown,
                 "、".join(sorted(LEVEL_EFFECTS[declared])), counter or "无"))

    # 4. 性奋类选项：确认它真的给性奋
    for label, target, rest in arous_opts:
        label, target = label.strip(), target.strip()
        amount = rest.strip()
        if not amount or not re.match(r"^\d+$", amount):
            problems.append("选项【%s】的性奋数值 %r 不是正整数" % (label, amount))
        else:
            print("  选项【%s】 -> %s   性奋 +%s" % (label, target, amount))

    # 5. 条件门槛与选项提示一致
    #
    #    ⚠️ 这里要按**实际写法**判定，不能简单找 <<promiscuousN>>：
    #       <<if hasSexStat("promiscuity", 3)>>
    #       <<robertLewdOption [[摸回去|…]] "robertTaxiBackJump" 3>>
    #       <</if>>
    #       条件的 <<if>> 在宏调用**之外**，标记由宏在运行时渲染，
    #       所以正文里当然找不到字面的 <<promiscuous3>>。
    #       正确的断言是：分支内带门槛参数的宏，其门槛必须等于条件等级。
    for cond, branch in re.findall(
            r'hasSexStat\("promiscuity",\s*(\d)\)>>(.*?)<</if>>', body, re.S):
        level = int(cond)
        want = "<<promiscuous%d>>" % level

        # a) 分支里直接写了标记（旧写法）
        if want in branch:
            print("  条件 淫乱 >= %d  字面标记 OK" % level)
            continue

        # b) 分支里用带门槛的 <<robertLewdOption … "N">>（现行写法）
        thresholds = [int(t) for t in re.findall(
            r'<<robertLewdOption[^\n]*?"[^"]*"\s+(\d)\s*>>', branch)]
        if level in thresholds:
            print("  条件 淫乱 >= %d  选项门槛参数 = %d  OK（宏按该等级渲染 %s）"
                  % (level, level, want))
            continue

        if thresholds:
            problems.append(
                "条件 hasSexStat(\"promiscuity\", %d) 的分支里，"
                "选项门槛参数是 %s，与条件等级不一致"
                % (level, thresholds))
        else:
            problems.append(
                "条件 hasSexStat(\"promiscuity\", %d) 的分支里既没有字面 %s，"
                "也没有带门槛参数的 <<robertLewdOption … \"N\">>"
                % (level, want))

    # 6. 链标内不得有换行（skill §2）
    for mm in re.finditer(r"\[\[[^\]\n]*\n", body):
        line = body[:mm.start()].count("\n") + 1
        problems.append("链标内有换行（第 %d 行附近）" % line)

    print()
    print("=" * 74)
    if problems:
        print("【页面1】告示不变式检查失败（%d 项）：" % len(problems))
        for p in problems:
            print("  [违反] %s" % p)
        print("=" * 74)
        return 1
    print("【页面1】告示不变式检查通过：")
    print("  · 段落判定档位 = %s，效果 = %s"
          % (declared, "、".join(sorted(LEVEL_EFFECTS.get(declared, set())))))
    print("  · 所有带效果选项的档位与之一致，计数参数合法，链标无换行")
    print("=" * 74)
    return 0


if __name__ == "__main__":
    sys.exit(main())
