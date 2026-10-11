# -*- coding: utf-8 -*-
"""
检查成就「恋人罗伯特」的定义是否完整、且 VrelCoin 数量符合要求。

需求：该成就应当获得 **2 枚 VrelCoin**。

⚠️ 为什么需要这个检查器：
    VrelCoin 的数量**不是单独配置的字段**，而是直接取自成就的 `difficulty`
    （feats.js:2078 与 :2476 都是 `coins += setup.feats[feat].difficulty`）。
    也就是说「难度」与「硬币数」是同一个数字 —— 有人想调难度时很可能
    没意识到自己在改硬币数，反之亦然。用断言把它钉住。

跑法：python check_feat.py
"""

import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FRAMEWORK = os.path.join(HERE, "framework.js")
FEAT_TWEE = os.path.join(HERE, "robert-feat.twee")
BOOT = os.path.join(HERE, "boot.json")

FEAT_NAME = "恋人罗伯特"
FEAT_DESC = "把你的第一次交给对方。"
# 需求：2 枚 VrelCoin。因为硬币数 == difficulty，所以 difficulty 必须是 2。
REQUIRED_DIFFICULTY = 2

checks = []
problems = []


def ok(label):
    checks.append(label)
    print("  [OK] %s" % label)


def bad(label, why):
    problems.append("%s —— %s" % (label, why))
    print("  [!!] %s" % label)


def read(path):
    return io.open(path, encoding="utf-8").read()


def main():
    if not os.path.isfile(FRAMEWORK):
        print("找不到 %s" % FRAMEWORK)
        return 1

    fw = read(FRAMEWORK)

    print("成就注册（framework.js 的 RB.registerFeats）")

    # 1. 键名
    m = re.search(r"RB\.FEAT_LOVER\s*=\s*'([^']+)'", fw)
    if not m:
        bad("定义 RB.FEAT_LOVER", "找不到键名常量")
    elif m.group(1) != FEAT_NAME:
        bad("成就键名", "是 %r，应为 %r" % (m.group(1), FEAT_NAME))
    else:
        ok("成就键名 = %s" % FEAT_NAME)

    # 2. 描述
    if FEAT_DESC in fw:
        ok("描述 = %s" % FEAT_DESC)
    else:
        bad("描述", "找不到 %r" % FEAT_DESC)

    # 3. difficulty（== VrelCoin 数量）—— 本次需求的核心
    dm = re.search(r"difficulty:\s*(\d+)", fw)
    if not dm:
        bad("difficulty 已设置", "找不到 difficulty 字段")
    elif int(dm.group(1)) != REQUIRED_DIFFICULTY:
        bad("difficulty = %s（决定 VrelCoin 数量）" % dm.group(1),
            "应为 %d，否则硬币数不是 %d 枚" % (REQUIRED_DIFFICULTY, REQUIRED_DIFFICULTY))
    else:
        ok("difficulty = %d（= %d 枚 VrelCoin）" % (REQUIRED_DIFFICULTY, REQUIRED_DIFFICULTY))

    # 4. 分类（与原版同类成就一致）
    if re.search(r"filter:\s*\[\s*'All'\s*,\s*'Social'\s*\]", fw):
        ok("分类 filter = ['All', 'Social']（与原版 Robin the Lover 一致）")
    else:
        bad("分类 filter", "应为 ['All', 'Social']，与原版同类成就保持一致")

    # 5. 必须先注册再授予：earnFeat 读 setup.feats[键] 时没有存在性判断
    if re.search(r"if\s*\(setup\.feats\[RB\.FEAT_LOVER\]\)\s*return\s+true", fw):
        ok("注册函数幂等（已存在则跳过）")
    else:
        bad("注册函数幂等", "重复注册会覆盖已有条目")

    if re.search(r"if\s*\(typeof setup === 'undefined'[^)]*\)\s*return\s+false", fw):
        ok("注册前检查 setup.feats 是否存在（避免加载顺序问题）")
    else:
        bad("注册前检查 setup.feats",
            "若本 mod 早于 feats.js 加载，注册会静默失败，之后 <<earnFeat>> 会抛异常")

    print()
    print("授予条件（RB.earnLoverFeat）")

    em = re.search(r"RB\.earnLoverFeat = function \(\) \{(.*?)\n\t\};", fw, re.S)
    if not em:
        bad("定义 RB.earnLoverFeat", "找不到该函数")
    else:
        body = em.group(1)
        if "robertRomance" in body:
            ok("要求已建立恋爱关系（$robertRomance）")
        else:
            bad("要求已建立恋爱关系",
                "需求指定要先成为恋人；不要改用「爱意 ≥ 某值」，那样刷爱意就能拿成就")
        if re.search(r"earnFeat\(\s*RB\.FEAT_LOVER\s*\)", body):
            ok("用常量调用 earnFeat（键名不会两边写错）")
        else:
            bad("用常量调用 earnFeat", "直接写字符串容易与键名定义不一致")

    print()
    print("Twee 侧接线")

    if not os.path.isfile(FEAT_TWEE):
        bad("存在 robert-feat.twee", "找不到文件")
    else:
        tw = read(FEAT_TWEE)
        if re.search(r'<<widget "robertTheLoverCheck">>', tw):
            ok("定义 widget robertTheLoverCheck")
        else:
            bad("定义 widget robertTheLoverCheck", "补丁 5 会调用它")
        if "earnLoverFeat" in tw:
            ok("widget 委托给 RB.earnLoverFeat（逻辑只有一处）")
        else:
            bad("widget 委托给 RB.earnLoverFeat", "不要在两处各写一份判定")

    if not os.path.isfile(BOOT):
        bad("存在 boot.json", "找不到文件")
    else:
        boot = read(BOOT)
        # 该文件应该被登记（widget 需要被加载）
        if "robert-feat.twee" in boot:
            ok("robert-feat.twee 已登记进 tweeFileList")
        else:
            bad("robert-feat.twee 已登记", "widget 不会被加载")
        # 补丁 5 必须把 widget 接进原版 awardVirginityFeat
        if re.search(r'<<case \\"Robert\\">><<robertTheLoverCheck>>', boot):
            ok("补丁 5 把 Robert 分支接进 awardVirginityFeat")
        else:
            bad("补丁 5 接线", "找不到 <<case \"Robert\">><<robertTheLoverCheck>>")

    print()
    print("=" * 74)
    if problems:
        print("成就自检失败（%d 项）：" % len(problems))
        for p in problems:
            print("  [违反] %s" % p)
        print("=" * 74)
        return 1
    print("成就自检通过（%d 项断言）" % len(checks))
    print("=" * 74)
    return 0


if __name__ == "__main__":
    sys.exit(main())
