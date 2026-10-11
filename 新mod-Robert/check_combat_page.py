#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
RobertNPC —— 【页面2】战斗页自检

这个页面踩坑最多，把每条已经确认过的结论都固化成断言，避免回归：
改坏了会直接报出来，而不是等玩家进战斗才发现。

⚠️ 最重要的一条（踩了十几轮才找到）：
   **<<npc X>><<person1>> 必须放在一次性守卫内！**
   <<npc Robert>> 会跑 <<initNNPCClothes>>/<<getNNPCClothes>> → <<npcClothes>>
   → <<npcEquipSet>> → 重新穿好整套衣服，把 penis 打回 "clothed"。
   放在循环段落顶层 = 每回合把他的裤子穿回去一次，
   表现为「脱衣显示成功但选项还在」，且手交类行动永远出不来。
   参考实现（哈珀 mod）所有战斗循环段落里的 <<npc …>> 都在守卫内。

断言清单：
  1. 存在一次性守卫，且 <<npc X>> 在守卫内（上面的头号陷阱）
  2. <<consensual>> + <<set $consensual to 1>> 在守卫内
  3. <<maninit>> 在守卫内，且在 <<npc X>> 之后
  4. 循环部分：<<effects>><<effectsman>><<man>><<stateman>><<actionsman>> 在守卫外
  5. <<actionsman>> 之后按 _combatend 分支给出路，未结束能回跳本页
  6. 不能对 $NPCList[0] 的 penis/vagina/chest 设 "none"
     （那些字段同时是玩家可针对的部位，设 "none" 会导致永远打不到对方）
  7. $lefttarget/$righttarget 不能是 "self"

注释会被剥离后再判断，避免注释里的示例代码造成误判。

用法：
    <python> check_combat_page.py
退出码 0 = 通过，1 = 违反。
"""

from __future__ import print_function

import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EVENT = os.path.join(HERE, "robert-taxi-event.twee")

FIGHTS = [
    ("Robert Taxi Caress Back", "robertTaxiFightInit", "robertHandsOnly"),
    ("Robert Taxi Oral Fight", "robertTaxiOralInit", "robertMouthOnly"),
]
LOOP = FIGHTS[0][0]          # 兼容下面的既有断言（衣着快照那一段用它）
REST = "Robert Taxi Caress Back Rest"

# 这些字段一旦设成 "none"，玩家就再也打不到对方
FORBIDDEN_NONE = ["penis", "vagina", "chest", "breasts"]


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


def passage(text, title):
    parts = re.split(r"^::[ \t]*", text, flags=re.M)[1:]
    for p in parts:
        head, _, body = p.partition("\n")
        name = re.sub(r"\[[^\]]*\]\s*$", "", head).strip()
        if name == title:
            return body
    return None


def guard_spans(body):
    """返回所有一次性守卫块 <<if $xxx is 1>> … <</if>> 的 (start, end)。"""
    spans = []
    for m in re.finditer(r"<<if \$(\w+) is 1>>", body):
        var = m.group(1)
        # 找到配对的 <</if>>（同层）
        depth = 1
        i = m.end()
        while i < len(body) and depth > 0:
            nxt_if = body.find("<<if ", i)
            nxt_end = body.find("<</if>>", i)
            if nxt_end < 0:
                break
            if 0 <= nxt_if < nxt_end:
                depth += 1
                i = nxt_if + 5
            else:
                depth -= 1
                i = nxt_end + 6
        spans.append((var, m.start(), i))
    return spans


def main():
    if not os.path.isfile(EVENT):
        print("找不到 %s" % EVENT)
        return 1

    src = strip_comments(io.open(EVENT, encoding="utf-8").read())
    problems = []
    checks = []

    def ok(label):
        checks.append(label)
        print("  [OK] %s" % label)

    def bad(label, why):
        problems.append("%s —— %s" % (label, why))
        print("  [!!] %s" % label)

    loop = passage(src, LOOP)
    if loop is None:
        bad("战斗页存在", "找不到段落 %r" % LOOP)
        return report(problems, checks)
    ok("战斗页存在: %s" % LOOP)

    spans = guard_spans(loop)

    # ---- 1. <<npc X>> 必须在守卫内（头号陷阱） ----
    print("\n最关键的断言：<<npc X>><<person1>> 是否在一次性守卫内")
    npc_hits = list(re.finditer(r"<<npc\s+[A-Z]\w*>>", loop))
    if not npc_hits:
        bad("存在 <<npc 具名NPC>>", "找不到；具名 NPC 必须用 <<npc X>> 而非 <<generate1>>")
    else:
        inside = [m for m in npc_hits
                  if any(s <= m.start() < e for _, s, e in spans)]
        outside = [m for m in npc_hits if m not in inside]
        if outside:
            for m in outside:
                line = loop[:m.start()].count("\n") + 1
                bad("<<npc X>> 在守卫内（第 %d 行）" % line,
                    "放在循环顶层 → 每回合重跑 <<npcClothes>> 把衣服穿回去，"
                    "脱衣状态永远丢失")
        else:
            ok("<<npc X>> 在守卫内（不会每回合重设衣着）")

    # ---- 2/3. 守卫内必须有 consensual / maninit ----
    print("\n守卫内的初始化内容")
    if not spans:
        bad("存在一次性守卫", "找不到 <<if $xxx is 1>> 结构")
    else:
        ok("存在一次性守卫: %s" % ", ".join("$" + v for v, _, _ in spans))
        gstart, gend = spans[0][1], spans[0][2]
        gtext = loop[gstart:gend]

        if re.search(r"<<consensual>>", gtext) and re.search(r"<<set \$consensual to 1>>", gtext):
            ok("守卫内有 <<consensual>> + $consensual = 1")
        else:
            bad("守卫内有 <<consensual>> + $consensual = 1",
                "缺 <<consensual>> 会导致 $trueconsensual/$consensualGuaranteed 没设，"
                "$consensual 被后续处理改回 0")

        m_npc = re.search(r"<<npc\s+[A-Z]\w*>>", gtext)
        m_init = re.search(r"<<maninit>>", gtext)
        if m_init and m_npc and m_npc.start() < m_init.start():
            ok("守卫内 <<npc X>> 在 <<maninit>> 之前")
        elif not m_init:
            bad("守卫内有 <<maninit>>", "缺失")
        else:
            bad("守卫内 <<npc X>> 在 <<maninit>> 之前", "顺序不对")

    # ---- 4. 循环内容在守卫外 ----
    print("\n循环内容（每回合都要跑）")
    gend = spans[0][2] if spans else 0
    after = loop[gend:]
    missing = [w for w in ("<<effects>>", "<<effectsman>>", "<<man>>",
                           "<<stateman>>", "<<actionsman>>")
               if w not in after]
    if missing:
        bad("循环内容在守卫外", "缺少: %s" % " ".join(missing))
    else:
        ok("<<effects>><<effectsman>><<man>><<stateman>><<actionsman>> 都在守卫外")

    # ---- 5. 出路 ----
    print("\n回合出口")
    m = re.search(r"<<actionsman>>", after)
    if not m:
        bad("调用 <<actionsman>>", "缺失")
    else:
        tail = after[m.end():]
        if "_combatend" in tail:
            ok("按 _combatend 分支给出路")
        else:
            bad("按 _combatend 分支给出路", "战斗结束不会自动跳转")
        if re.search(r"\[\[继续\|%s\]\]" % re.escape(LOOP), tail):
            ok("未结束时可回跳本页（多回合循环）")
        else:
            bad("未结束时可回跳本页", "打不了第二回合")
        if re.search(r"<<link \[\[[^\]]+\|%s Result\]\]>>" % re.escape(LOOP), tail):
            ok("结束时可去结算页")
        else:
            bad("结束时可去结算页", "缺少结算出口")

    # ---- 6. 不能摘除可针对部位 ----
    print("\n部位与目标")
    badnone = [p for p in FORBIDDEN_NONE
               if re.search(r'NPCList\[0\]\.%s\s+to\s+"none"' % p, src)]
    if badnone:
        bad('未对 .%s 设 "none"' % "/".join(badnone),
            '设 "none" 表示该部位不存在，玩家永远打不到它')
    else:
        ok("未摘除罗伯特的任何可针对部位")

    # ---- 7. 目标不能是 self ----
    if re.search(r'<<set \$(left|right)target to "self">>', src):
        bad('目标不是 "self"', "会导致所有行动变成针对自身")
    else:
        ok('目标未设成 "self"')

    # ---- 8. 生殖器隔离（只用手/只靠近某处的场景必须） ----
    print("\n生殖器隔离（防止对方生殖器占住玩家的阴部/阴茎）")
    if re.search(r"<<set \$enemyanger to 0>>", loop):
        ok("循环内每回合 $enemyanger 归零")
    else:
        bad("循环内每回合 $enemyanger 归零",
            "不归零时 `$enemyanger + $rng` 可能超过 171，"
            "<<penisinit>> 会把对方阴茎对到玩家阴道上（man-combat.twee:6268）")
    if re.search(r"<<set \$robertHandsOnly to 1>>", src):
        ok("已设只用手守卫标志 $robertHandsOnly")
    else:
        bad("已设只用手守卫标志 $robertHandsOnly", "缺少标志，兜底守卫不会生效")
    if re.search(r"<<robertGuardNpcPenis>>", loop):
        ok("循环内调用 <<robertGuardNpcPenis>> 兜底")
    else:
        bad("循环内调用 <<robertGuardNpcPenis>>", "缺少兜底，脏状态无法复原")

    # ---- 9. 衣着快照 / 恢复必须成对 ----
    print("\n衣着快照与恢复")
    restore = passage(src, REST)
    if re.search(r"<<set \$robertTaxiWornBackup to clone\(\$worn\)>>", loop):
        ok("手部路线入场时用 clone($worn) 记录衣着快照")
    else:
        bad("手部路线入场时用 clone($worn) 记录衣着快照",
            "遭遇战里玩家会脱衣；不记录快照就无法在收场页穿回去")

    # 口部路线：快照必须记在【页面1】的选项里，而不是遭遇战入场
    print("\n口部路线的快照时机（必须在衣服被改动之前）")
    caress = passage(src, "Robert Taxi Caress")
    oral_link = None
    if caress:
        for line in caress.split("\n"):
            if "Robert Taxi Oral 4" in line and "<<link" in line:
                oral_link = line
                break
    if oral_link is None:
        bad("【为其口交】选项存在", "找不到它的 <<link>>")
    else:
        ok("【为其口交】选项存在")
        if "snapshotNpcClothes" in oral_link:
            ok("选项里记了 NPC 衣着快照（早于【页面4】脱裤子）")
        else:
            bad("选项里记了 NPC 衣着快照",
                "【页面4】会脱掉他的裤子；快照若记在遭遇战入场就太晚了，"
                "恢复出来会是「裤子脱着」")
        if "robertTaxiWornBackup to clone($worn)" in oral_link:
            ok("选项里同时记了玩家衣着快照")
        else:
            bad("选项里同时记了玩家衣着快照", "玩家侧同样要在改动前记录")

    oral = passage(src, "Robert Taxi Oral Fight")
    if oral and "snapshotNpcClothes" in oral:
        bad("遭遇战入场不该再记一次快照",
            "那时裤子已经被【页面4】脱掉，会把「脱着」的状态存进去")
    elif oral:
        ok("遭遇战入场没有重复记快照")

    if restore is None:
        bad("收场页存在: %s" % REST, "找不到该段落")
    else:
        ok("收场页存在: %s" % REST)
        if re.search(r"<<set \$worn to clone\(\$robertTaxiWornBackup\)>>", restore):
            ok("收场页用 clone() 恢复衣着（不是赋引用）")
        else:
            bad("收场页用 clone() 恢复衣着",
                "直接 <<set $worn to $bak>> 会让快照被后续改动污染")
        if re.search(r"<<unset \$robertTaxiWornBackup>>", restore):
            ok("恢复后清除快照变量（不留到下一场）")
        else:
            bad("恢复后清除快照变量", "残留快照会影响下一场遭遇战")
        if re.search(r"<<exposure>>", restore):
            ok("恢复后重算 <<exposure>>")
        else:
            bad("恢复后重算 <<exposure>>",
                "$exposed 是推导值，衣服穿回去后必须重算")
        if re.search(r"<<set \$exposed to", restore):
            bad("不要直接写 $exposed",
                "它是推导值，直接赋值会与 $worn 不一致，应调 <<exposure>>")

    check_extra_fights(src, ok, bad)

    return report(problems, checks)


def check_extra_fights(src, ok, bad):
    """第二场之后的遭遇战（目前是「只靠近口部」那场）的针对性断言。

    没有把主流程改成循环 —— 第一场的断言已经调稳，不值得为对称去重构。
    这里只钉住第二场真正特有的几条。
    """
    for name, initvar, flag in FIGHTS[1:]:
        print("\n【%s】（%s）" % (name, flag))
        body = passage(src, name)
        if body is None:
            bad("段落存在: %s" % name, "找不到")
            continue
        ok("段落存在: %s" % name)

        spans = guard_spans(body)

        # 头号陷阱同样适用
        npc_hits = list(re.finditer(r"<<npc\s+[A-Z]\w*>>", body))
        inside = [m for m in npc_hits if any(s <= m.start() < e for _, s, e in spans)]
        if not npc_hits:
            bad("有 <<npc X>>", "缺失")
        elif len(inside) != len(npc_hits):
            bad("<<npc X>> 全在守卫内", "循环顶层重跑 <<npcClothes>> 会把裤子穿回去")
        else:
            ok("<<npc X>> 全在守卫内")

        if re.search(r"<<set \$%s to 1>>" % flag, src):
            ok("已设守卫标志 $%s" % flag)
        else:
            bad("已设守卫标志 $%s" % flag, "robert-guard.twee 的对应分支不会生效")

        gend = spans[0][2] if spans else 0
        after = body[gend:]
        missing = [w for w in ("<<effects>>", "<<effectsman>>", "<<man>>",
                               "<<stateman>>", "<<actionsman>>")
                   if w not in after]
        if missing:
            bad("循环内容在守卫外", "缺少: %s" % " ".join(missing))
        else:
            ok("循环五件套在守卫外")

        if re.search(r"<<set \$enemyanger to 0>>", after):
            ok("循环内 $enemyanger 归零")
        else:
            bad("循环内 $enemyanger 归零", "不归零会把生殖器掷到玩家身上")

        if re.search(r"<<robertGuardNpcPenis>>", after):
            ok("循环内调用守卫兜底")
        else:
            bad("循环内调用守卫兜底", "缺少兜底")

        m = re.search(r"<<actionsman>>", after)
        tail = after[m.end():] if m else ""
        if re.search(r"\[\[继续\|%s\]\]" % re.escape(name), tail):
            ok("未结束时可回跳本页")
        else:
            bad("未结束时可回跳本页", "打不了第二回合")
        if "_combatend" in tail:
            ok("按 _combatend 分支给出路")
        else:
            bad("按 _combatend 分支给出路", "战斗结束不会跳转")

        if re.search(r"<<set \$NPCList\[0\]\.(lefthand|righthand) to \"none\">>", body):
            ok("已屏蔽对方双手（只有嘴参与）")
        else:
            bad("已屏蔽对方双手", "本场景应只有嘴参与")

        if re.search(r"npcMakeNaked\(\$NPCList\[0\], \"lower\"\)", body):
            ok("用 npcMakeNaked 保持脱掉状态（寻欢洞做法）")
        else:
            bad("用 npcMakeNaked 保持脱掉状态", "本场景前提是裤子已脱，不该让玩家再点脱衣")

        # 开场就该就位：不能让引擎掷点决定贴哪里
        if re.search(r'<<set \$mouthuse to "penis">>', body):
            ok("开场即设 $mouthuse = \"penis\"（口部就位）")
        else:
            bad("开场即设 $mouthuse = \"penis\"",
                "不设的话 <<penisinit>> 会掷点，可能掷出「对准你的阴道」那种分支")
        if re.search(r'<<set \$NPCList\[0\]\.penis to "mouthentrance">>', body):
            ok("开场即设他的 penis = \"mouthentrance\"")
        else:
            bad("开场即设他的 penis = \"mouthentrance\"", "口部行动会等到引擎掷中才可用")
        if re.search(r"<<set \$NPCList\[0\]\.condom\.willUse to false>>", body):
            ok("关掉他的避孕套意图（避免「套上避孕套」那句）")
        else:
            bad("关掉他的避孕套意图",
                "阴道分支会印出「XX将粉色避孕套套在他的肉棒上。」，与本场景不符")

        # 守卫 C 段：把他放回嘴边，而不是清掉。
        # ⚠️ 判据不能用「有没有 <<set $mouthuse to "penis">>」——
        #    守卫现在是**按器官分支**的（有阴茎 → "penis"；只有阴道 → "othervagina"），
        #    所以正确形状是：引用 $mouthuse + 同时出现两种目标值。
        guard_path = os.path.join(HERE, "robert-guard.twee")
        guard = ""
        if os.path.isfile(guard_path):
            guard = strip_comments(io.open(guard_path, encoding="utf-8").read())
        has_mouthuse = bool(re.search(r"<<set \$mouthuse to _rgWantMouth>>", guard))
        has_both = bool(re.search(r'\? "penis" : "othervagina"', guard)) or (
            bool(re.search(r'<<set \$mouthuse to "penis">>', guard)) and
            bool(re.search(r'<<set \$mouthuse to "othervagina">>', guard)))
        if re.search(r'<<if \$robertMouthOnly is 1>>', guard) and has_mouthuse and has_both:
            ok("守卫在口部场景把他放回嘴边（按器官分支，不是清掉）")
        else:
            bad("守卫在口部场景把他放回嘴边",
                "只清掉的话 <<mouthActionInit>> 的核心行动会消失；"
                "且必须按器官选状态组：有阴茎 → \"penis\"/\"entrance\"，"
                "只有阴道 → \"othervagina\"/\"othervagina\"，"
                "否则 <<npcPenis>> 会退回 penisdesc 的 \"none\"")

        # 不能顺手把可针对部位摘掉
        badnone = [p for p in ("penis", "vagina", "chest")
                   if re.search(r'NPCList\[0\]\.%s\s+to\s+"none"' % p, body)]
        if badnone:
            bad("未摘除可针对部位", "被摘掉的是: %s" % ", ".join(badnone))
        else:
            ok("未摘除可针对部位")


def report(problems, checks):
    print()
    print("=" * 74)
    if problems:
        print("【页面2】自检失败（%d 项）：" % len(problems))
        for p in problems:
            print("  [违反] %s" % p)
        print("=" * 74)
        return 1
    print("【页面2】自检通过（%d 项断言）" % len(checks))
    print("=" * 74)
    return 0


if __name__ == "__main__":
    sys.exit(main())

