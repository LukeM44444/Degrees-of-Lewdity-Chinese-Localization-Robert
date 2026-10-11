#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RobertNPC —— 事件链路导出（只读工具，不参与打包）
===========================================================================
为什么要它
---------------------------------------------------------------------------
skill 要求「每次新增/修改页面后都要给出事件链路图，而且图必须**从源码
核对**，不能凭记忆写」。段落一多，手写链路图必然出错：漏掉一个 <<if>>
就会把「有条件的选项」写成「始终显示」，漏掉一个 <<set>> 就会把数值
写错。所以链路图必须由脚本 dump 出来再整理。

本文件名以 `_` 开头 —— build_mod.py 会跳过所有 `_` 开头的文件，
所以它**不会**进入 .mod 包，对游戏零影响。

用法
---------------------------------------------------------------------------
    python _dump_chain.py                # 全部段落
    python _dump_chain.py Taxi           # 只看段落名含 "Taxi" 的
    python _dump_chain.py --widgets      # 只列 widget 定义
    python _dump_chain.py --vars         # 只列所有 $ 变量的读写点

输出结构（每个段落一节）：
    :: 段落名 [标签]
      <条件栈>                       ← 该位置所处的 <<if>> 嵌套
      → 链接：标签 => 目标段落
        点击时：<<set>> / 数值宏      ← 链接体内的全部变化
      · 数值宏（正文里的）            ← 段落正文直接改的数值
      · widget 调用
===========================================================================
"""

import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# 会改玩家/NPC 数值的宏 —— 用于「数值变化清单」
STAT_MACROS = (
    "arousal", "stress", "def", "trauma", "money", "pass", "lust", "love",
    "dom", "rage", "orgasm", "exposure", "brat", "defiance", "promiscuity",
    "gstress", "ggstress", "gggstress", "lstress", "llstress",
    "garousal", "ggarousal", "glust", "gglust", "llust", "lllust",
    "glove", "gglove", "llove", "lllove",
    "gdom", "ggdom", "ldom", "lldom", "llldom",
    "grage", "lrage", "trauma", "handskill", "oralskill", "vaginalskill",
    "penileskill", "analskill", "endcombat", "endevent", "npcMakeNaked",
    "loveInterestAdd", "earnFeat", "consensual", "maninit", "npc", "person1",
)

LINK_RE = re.compile(r"\[\[([^\[\]|]*)\|([^\[\]]*)\]\]")
SET_RE = re.compile(r"<<set\s+(\$[\w.\[\]]+)\s+(to|\+=|-=|\*=)\s*([^>]*)>>")
UNSET_RE = re.compile(r"<<unset\s+(\$[\w.\[\]]+)>>")
RUN_RE = re.compile(r"<<run\s+(.+?)>>", re.S)
MACRO_RE = re.compile(r"<<(/?)([A-Za-z_][\w-]*)((?:\s+(?:\"(?:[^\"\\]|\\.)*\"|'(?:[^'\\]|\\.)*'|`[^`]*`|[^>\s]+))*)\s*(/?)>>", re.S)
WIDGET_DEF_RE = re.compile(r"<<widget\s+\"([^\"]+)\"", re.S)
PASSAGE_RE = re.compile(r"^::\s*([^\[\n]+?)\s*(?:\[([^\]]*)\])?\s*$", re.M)

# 块级宏：用来重建「选项出现在什么条件里」
BLOCK_OPEN = {"if", "for", "switch", "widget", "capture"}
BLOCK_MID = {"elseif", "else", "case", "default"}


def load_twee_files():
    """按 boot.json 的 tweeFileList 顺序读，保证输出顺序与游戏加载一致。"""
    files = []
    boot = os.path.join(HERE, "boot.json")
    if os.path.isfile(boot):
        import json
        with open(boot, "r", encoding="utf-8") as fh:
            files = json.load(fh).get("tweeFileList", [])
    if not files:
        files = sorted(f for f in os.listdir(HERE) if f.endswith(".twee"))
    out = []
    for name in files:
        path = os.path.join(HERE, name.replace("/", os.sep))
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as fh:
                out.append((name, fh.read()))
    return out


def split_passages(text):
    """把一份 twee 文本切成 [(名字, 标签, 正文)]。"""
    marks = list(PASSAGE_RE.finditer(text))
    out = []
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        body_start = text.find("\n", m.end())
        body = text[body_start + 1:end] if body_start != -1 else ""
        out.append((m.group(1).strip(), (m.group(2) or "").strip(), body))
    return out


def strip_comments(body):
    """去掉 /* … */ 块注释，避免把注释里的示例当成真实代码。"""
    return re.sub(r"/\*.*?\*/", "", body, flags=re.S)


def strip_html_comments(body):
    return re.sub(r"<!--.*?-->", "", body, flags=re.S)


def cond_stack(body, upto):
    """重建 offset 处的条件栈（只看块级宏）。"""
    stack = []
    for m in MACRO_RE.finditer(body, 0, upto):
        closing, name, args = m.group(1), m.group(2), m.group(3).strip()
        if name in BLOCK_OPEN and not closing:
            stack.append(name + (" " + args if args else ""))
        elif name == "if" and closing:
            if stack:
                stack.pop()
        elif name in BLOCK_MID and not closing:
            if stack:
                head = stack[-1].split(" ", 1)[0]
                stack[-1] = {"elseif": "elseif", "else": "else",
                             "case": "case", "default": "default"}[name] + (" " + args if args else "")
    return " / ".join(s for s in stack if s)


def effects_in(text):
    """抽出一段文本里的数值变化。"""
    out = []
    for m in SET_RE.finditer(text):
        var, op, val = m.group(1), m.group(2), m.group(3).strip()
        val = re.sub(r"\s+", " ", val)
        out.append(f"set {var} {op} {val}" if op != "to" else f"set {var} = {val}")
    for m in UNSET_RE.finditer(text):
        out.append(f"unset {m.group(1)}")
    for m in RUN_RE.finditer(text):
        code = re.sub(r"\s+", " ", m.group(1).strip())
        out.append(f"run {code}")
    for m in MACRO_RE.finditer(text):
        closing, name = m.group(1), m.group(2)
        if closing or name in ("set", "unset", "run", "link", "if", "elseif",
                               "else", "for", "switch", "case", "default",
                               "widget", "print", "="):
            continue
        if name in STAT_MACROS:
            args = re.sub(r"\s+", " ", m.group(3).strip())
            out.append(f"<<{name}{(' ' + args) if args else ''}>>")
    return out


def dump_passage(name, tags, body, want_vars=False):
    clean = strip_html_comments(strip_comments(body))
    print(f"\n:: {name}" + (f"  [{tags}]" if tags else ""))

    # ---- 链接与它们的效果 ----
    for m in LINK_RE.finditer(clean):
        label = m.group(1).strip()
        target = m.group(2).strip()
        # 链接体 = <</link>> 之前的内容
        close = clean.find("<</link>>", m.end())
        linkbody = clean[m.end():close] if close != -1 else ""
        cond = cond_stack(clean, m.start())
        eff = effects_in(linkbody)
        print(f"  → [[{label}|{target}]]" + (f"   条件: {cond}" if cond else "   条件: 始终"))
        for e in eff:
            print(f"        · {e}")

    # ---- 正文里（链接之外）的数值宏 ----
    outside = re.sub(r"<<link\b.*?<</link>>", "", clean, flags=re.S)
    # ⚠️ 不要过滤 `run RobertNPC?...` —— 那些正是本 mod 改属性的唯一途径
    #    （addStat / npcMakeNaked / snapshotNpcClothes …），过滤掉链路图就会漏数值。
    bodyeff = effects_in(outside)
    if bodyeff:
        print("  [正文效果]")
        for e in bodyeff:
            print(f"      · {e}")


def dump_vars(all_passages):
    """列出每个 $ 变量的赋值点与读取点。"""
    write, read = {}, {}
    for name, tags, body in all_passages:
        clean = strip_html_comments(strip_comments(body))
        for m in re.finditer(r"\$([\w.\[\]]+)", clean):
            var = m.group(1)
            # 粗略判断：出现在 <<set>> 左边就是写
            line_start = clean.rfind("<<", 0, m.start())
            chunk = clean[line_start:line_start + 120] if line_start != -1 else ""
            if re.match(r"<<set\s+\$", chunk) and chunk.find(">>", m.end() - line_start) != -1:
                write.setdefault(var, set()).add(name)
            else:
                read.setdefault(var, set()).add(name)
    print("\n" + "=" * 74)
    print("$ 存档变量（写 = 被 <<set>> 赋值）")
    print("=" * 74)
    for var in sorted(set(write) | set(read)):
        w = ", ".join(sorted(write.get(var, []))) or "—"
        r = ", ".join(sorted(read.get(var, []))) or "—"
        print(f"  ${var}")
        print(f"        写: {w}")
        print(f"        读: {r}")


def main():
    ap = argparse.ArgumentParser(description="RobertNPC 事件链路导出（只读）")
    ap.add_argument("filter", nargs="?", default="", help="只看段落名包含该子串的段落")
    ap.add_argument("--widgets", action="store_true", help="只列 widget 定义")
    ap.add_argument("--vars", action="store_true", help="只列 $ 变量读写点")
    args = ap.parse_args()

    all_passages = []
    for fname, text in load_twee_files():
        for name, tags, body in split_passages(text):
            all_passages.append((name, tags, body, fname))

    if args.widgets:
        print("widget 定义（已剔除注释里的示例）：")
        for name, tags, body, fname in all_passages:
            # ⚠️ 必须先剥掉 /* … */ 注释：注释里常引用原版 widget 名
            #    （例如「原版 <<widget "relation-box">>」），
            #    不剥就会把它们误报成「本 mod 定义了这个 widget」。
            for m in WIDGET_DEF_RE.finditer(strip_comments(body)):
                print(f"  <<widget \"{m.group(1)}\">>  ({fname} → {name})")
        return 0

    if args.vars:
        dump_vars([(n, t, b) for n, t, b, _ in all_passages])
        return 0

    for name, tags, body, fname in all_passages:
        if args.filter and args.filter.lower() not in name.lower():
            continue
        print(f"\n{'=' * 74}\n[{fname}]")
        dump_passage(name, tags, body)
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    sys.exit(main())
