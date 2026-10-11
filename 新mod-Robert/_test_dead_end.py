#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_dead_end.py 的合成用例回归测试（不依赖 mod 文件）。

用例 ① 就是 Robert Taxi 那个真实 bug 的形状；
用例 ③ 是遭遇战页的形状（曾经被误报）。
"""
import check_dead_end as C

CASES = [
    ("① Robert Taxi 原始 bug 形状（钱不够分支无链接）", True, """:: Robert Taxi
<<unset $bus>>
你上了出租车。价£5。
<br>
<<if $money gte 500>>
<<link [[乘车前往多姆斯街（家）(0:05)|Robert Taxi Seat]]>><<set $bus to "domus">><<money -500 "taxi">><</link>>
<br>
<<if $town_projects.road gte 4>>
<<link [[乘车前往湖边 (0:05)|Robert Taxi Seat]]>><<set $bus to "lakebus">><</link>>
<br>
<</if>>
<<else>>
你的钱不够付车费。
<br><br>
<</if>>
<<destination>>
"""),
    ("② 给钱不够分支补上【继续】链接后", False, """:: Robert Taxi
<<unset $bus>>
你上了出租车。价£5。
<br>
<<if $money gte 500>>
<<link [[乘车前往多姆斯街（家）(0:05)|Robert Taxi Seat]]>><<money -500 "taxi">><</link>>
<br>
<<else>>
你的钱不够付车费。
<br><br>
<<set _rtFareBack to ($passagePrev and $passagePrev isnot "none") ? $passagePrev : "Domus Street">>
<<link [[继续|_rtFareBack]]>><</link>>
<br>
<</if>>
<<destination>>
"""),
    ("③ 遭遇战页形状（守卫支有文字，后面 if/else 两支都有链接）", False, """:: Robert Taxi Caress Back
<<if $robertTaxiFightInit is 1>>
	<<set $robertTaxiFightInit to 0>>
	你把左手覆在他的手背上，指尖顺着他的指缝慢慢嵌进去。
	<br><br>
<</if>>
<<effects>>
<<actionsman>>
<<if _combatend>>
<span id="next"><<link [[继续|A]]>><<endcombat>><</link>></span>
<<else>>
<span id="next"><<link [[继续|B]]>><</link>></span>
<</if>>
"""),
    ("④ 整页有文字但完全没有链接", True, """:: Robert Dead End
你站在那里，什么也做不了。
<br><br>
"""),
    ("⑤ 没有 else 的 if 里有链接 —— 不算覆盖，后面裸文字仍该报", True, """:: Robert Half
<<if $money gte 500>>
<<link [[继续|A]]>><</link>>
<</if>>
你的钱不够付车费。
<br><br>
"""),
    ("⑥ 顺序区有链接（末尾给到达按钮）—— 分支不必各自带", False, """:: Robert Taxi Destination
<<if $robertTaxiDriver is "robert">>
	罗伯特收回手，重新握在方向盘上。
	<br>
<<else>>
	出租车稳稳地停在路边。
<</if>>
<<set $robertTaxiSeat to "">>
<br>
<<robertTaxiArriveText>>
<<robertTaxiArriveLink>>
"""),
    ("⑦ [widget] 段落不参与判定", False, """:: Robert Some Widget [widget]
<<widget "x">>
	<<if $a is 1>>有文字的分支<</if>>
	<</widget>>
"""),
]


def main():
    ok = True
    for label, should_flag, src in CASES:
        found = []
        for pname, tags, line, body in C.split_passages(C.strip_comments(src)):
            f, _ = C.check_passage("probe.twee", pname, tags, line, body)
            found += f
        got = bool(found)
        mark = "✔" if got == should_flag else "✘"
        if got != should_flag:
            ok = False
        print("%s %s  （期望%s，实际%s）" % (
            mark, label, "报错" if should_flag else "通过", "报错" if got else "通过"))
        for x in found:
            print("      " + x.replace("\n", " ")[:120])
    print("=" * 70)
    print("合成用例回归：" + ("全部符合预期" if ok else "有用例不符"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
