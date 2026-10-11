#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RobertNPC —— twee 宏完整性自检
===========================================================================
在打包前跑一次，检查本 mod 的 twee 里用到的每个 <<macro>> 是否真的存在。

这是 DoL 模组最常踩的运行时坑之一：调用了不存在的宏（或已被版本移除的宏），
只会在玩到那个段落时弹出 "macro does not exist" 红字报错。
哈珀 mod 的第五、六轮修复（<<harperinterestchange>>、<<healthMultiplier>>、
<<npcStealMoney>>）全是这类问题。

宏来源：
  1. SugarCube 2 内建宏             —— 硬编码清单（见下）
  2. DoL 用 <<widget "名">> 定义的   —— 从原版 game/**/*.twee 提取
  3. DoL 用 Macro.add / DefineMacro  —— 从原版 game/**/*.js 提取
  4. 本 mod 自己定义的 widget        —— 从本 mod 的 twee 提取
  5. 象牙怨灵 / 哈珀 mod 定义的      —— 一并纳入（它们会共存于同一局游戏）

用法：
    python check_macros.py
    python check_macros.py --module 游戏源代码-degrees-of-lewdity-master/modules

退出码：0 = 全部存在；1 = 发现未定义宏；2 = 路径错误。
===========================================================================
"""

import argparse
import os
import re
import sys

DEFAULT_WORKSPACE = r"D:\mod  c\xin mod"
DEFAULT_MINE = "新mod-Robert"
DEFAULT_VANILLA = "游戏源代码-degrees-of-lewdity-master/game"
DEFAULT_MODULES = "游戏源代码-degrees-of-lewdity-master/modules"
EXTRA_SOURCES = [
    "象牙怨灵mod-Wraith.sReflection.mod",
    "哈珀mod-ClaimableHarperbyMonMondayy_DOLP",
]

# ---------------------------------------------------------------------------
# SugarCube 2.36.1 内建宏（含 DoL 用到的全部；来源：SugarCube 版 format.js 的 Macro.add 清单）
# ---------------------------------------------------------------------------
SUGARCUBE_MACROS = {
    "a", "act", "append", "array", "audio", "back", "button", "caption", "checkbox",
    "checked", "childvideo", "choice", "click", "cycle", "debug", "display", "done",
    "else", "elseif", "ended", "for", "forget", "goto", "hidden", "if", "include",
    "input", "jump", "link", "linkappend", "linkprepend", "linkreplace", "listbox",
    "macro", "masteraudio", "metro", "nobr", "notify", "numberbox", "once", "option",
    "optionsfrom", "password", "playlist", "prepend", "print", "radiobutton", "random",
    "redeem", "remember", "remove", "repeat", "replace", "return", "revert", "run",
    "script", "set", "settings", "silently", "skip", "stop", "storycaption",
    "storydisplay", "storyinit", "style", "switch", "t8n", "textarea", "textbox",
    "textboxreset", "throw", "timed", "toggle", "twee", "type", "unchecked", "unset",
    "video", "widget", "while", "=", "-", "==", "!=", ">", ">=", "<", "<=",
}

# 这些是「标记/结构」宏，不需要单独校验
IGNORE = {"else", "elseif", "case", "default", "break", "continue", "done", "silently",
          "nobr", "widget", "script", "style", "=", "-"}

SKIP_DIRS = {"node_modules", ".git", "__pycache__", "out"}

RE_WIDGET = re.compile(r'<<widget\s+["\']([^"\']+)["\']')
RE_MACRO_ADD = re.compile(r'Macro\.add\s*\(\s*[\["\']([^"\'\]\[]+)')
RE_DEFINE = re.compile(r'DefineMacro\w*\s*\(\s*["\']([^"\']+)["\']')
# 原版大量宏是用 statDisplay.create("名", fn) 注册的（base-system/text.js 里 384 个），
# 例如 gstress / garousal / glove / glust。不认这种写法会误报一堆「未定义」。
RE_STATDISPLAY = re.compile(r'statDisplay\.create\s*\(\s*["\']([^"\']+)["\']')
# 匹配 <<name ...>> / <<name>>（name 后必须是空白或 >>，避免把 <<= 之类算进来）
RE_CALL = re.compile(r"<<\s*([A-Za-z_][\w-]*)\s*(?=[\s/>]|>>)")


def walk(root, exts):
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            if os.path.splitext(name)[1].lower() in exts:
                yield os.path.join(base, name)


def read(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


def gather_defined(*roots):
    """从若干目录里收集所有已定义的宏/widget 名。"""
    defined = set()
    for root in roots:
        if not root or not os.path.isdir(root):
            continue
        for path in walk(root, {".twee", ".js"}):
            text = read(path)
            defined |= set(RE_WIDGET.findall(text))
            defined |= set(RE_STATDISPLAY.findall(text))
            for name in RE_MACRO_ADD.findall(text):
                # Macro.add 可能一次注册多个名字，例如 Macro.add(["a","b"], ...)
                for part in re.findall(r'["\']([^"\']+)["\']', name):
                    defined.add(part)
                defined.add(name)
            defined |= set(RE_DEFINE.findall(text))
    return defined


def strip_comments(src):
    """
    把块注释、行注释的内容替换成空白，保持行号与结构不变；
    同时把字符串字面量的**内容**替换掉（保留引号），
    这样括号计数不会被字符串里的 ( ) { } [ ] 干扰。

    用于「脚本顶层是否引用了尚不存在的全局」这类检查 —— 必须忽略注释与字符串里的示例代码。
    """
    out = []
    i, n = 0, len(src)
    in_block = in_line = False
    in_str = None
    while i < n:
        c = src[i]
        nxt = src[i + 1] if i + 1 < n else ""
        if in_line:
            if c == "\n":
                in_line = False
                out.append(c)
            else:
                out.append(" ")
        elif in_block:
            if c == "*" and nxt == "/":
                in_block = False
                out.append("  ")
                i += 2
                continue
            out.append("\n" if c == "\n" else " ")
        elif in_str:
            if c == "\\":
                out.append("  ")
                i += 2
                continue
            if c == in_str:
                in_str = None
                out.append(c)
            else:
                out.append(" ")
        else:
            if c == "/" and nxt == "*":
                in_block = True
                out.append("  ")
                i += 2
                continue
            if c == "/" and nxt == "/":
                in_line = True
                out.append("  ")
                i += 2
                continue
            if c in "\"'`":
                in_str = c
            out.append(c)
        i += 1
    return "".join(out)


# maplebirchAddon 的 params.script 在 ModLoader 的 afterRegisterMod2Addon 阶段执行，
# 早于 SugarCube2 启动 —— 那时 setup / V / T / State 都还不存在。
# 在 IIFE 体内（顶层）引用它们会让整个脚本抛异常中止（"setup is not defined"），
# mod 的 JS 侧完全不工作。
#
# 只检查 setup 与 State：
#   - setup / State 是 SugarCube 启动时才创建的，必须在函数内部（运行时回调）里用；
#   - V / T 属于运行时数据，本 mod 只在函数内访问，但它们在 SugarCube 启动前
#     同样是 undefined，因此不纳入自动判定，改由人工 review 把关。
RE_SUGARCUBE_GLOBAL = re.compile(r"(?<![.\w$])(setup|State)\b")

# 只在**真正的顶层**（IIFE 体，深度 ≤ 1）才认定违规。
#
# ⚠️ 这个阈值原来是 2，太松：本 mod 的文件都是
#       (function () { ... })();
#    形式，深度 1 = IIFE 体（真正顶层），深度 2 = **第一个函数体内**。
#    把 2 也算顶层，就会把函数体里的 setup 引用误报成顶层引用
#    （真实误报：RB.registerFeats 函数体里的 setup.feats）。
#    深度 1 的正经用法是各 modules 开头的
#       if (typeof maplebirch === 'undefined' || !maplebirch) return;
#    那类守卫，它们不碰 setup / State，所以收紧到 1 不会误伤。
TOPLEVEL_BRACE_MAX = 1


def _brace_depth_map(src):
    """
    逐行算出「进入该行时的花括号深度」。

    ⚠️ 不能用 `line.count("{") - line.count("}")` 直接累加（原实现就是这么错的）：
       字符串、模板串、正则里的花括号会被当成代码花括号，导致深度漂移。
       真实误报：framework.js 的 RB.registerFeats 里
           setup.feats[RB.FEAT_LOVER] = { ... }
       明明在函数体内（深度远大于 2），却因为深度被算低而被报成「顶层引用」。

    这里做一个极简但够用的词法扫描：跳过
      · // 行注释、/* */ 块注释
      · '…' 与 "…" 字符串
      · `…` 模板串（模板串里的 ${} 也一并按嵌套处理）
    不处理正则字面量（本项目的 JS 里没有含花括号的正则）。
    """
    depths = []
    depth = 0
    i = 0
    n = len(src)
    in_block = False
    in_line = False
    quote = None
    line = 1

    while i < n:
        ch = src[i]
        nxt = src[i + 1] if i + 1 < n else ""

        if ch == "\n":
            depths.append(depth)
            line += 1
            in_line = False
            i += 1
            continue

        if in_line:
            i += 1
            continue

        if in_block:
            if ch == "*" and nxt == "/":
                in_block = False
                i += 2
                continue
            i += 1
            continue

        if quote:
            if ch == "\\":
                i += 2
                continue
            if ch == quote:
                quote = None
            i += 1
            continue

        if ch == "/" and nxt == "/":
            in_line = True
            i += 2
            continue
        if ch == "/" and nxt == "*":
            in_block = True
            i += 2
            continue
        if ch in ("'", '"', "`"):
            quote = ch
            i += 1
            continue

        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        i += 1

    depths.append(depth)
    while len(depths) < line:
        depths.append(depth)
    return depths


def check_script_toplevel(mine_dir):
    """检查模组 JS 在 IIFE 顶层是否引用了 SugarCube 全局。返回问题列表。"""
    problems = []
    for path in walk(mine_dir, {".js"}):
        src = strip_comments(read(path))
        # depths[ln-1] = 进入第 ln 行时的深度
        depths = _brace_depth_map(src)
        for ln, line in enumerate(src.split("\n"), 1):
            if ln - 1 < len(depths) and depths[ln - 1] <= TOPLEVEL_BRACE_MAX \
                    and RE_SUGARCUBE_GLOBAL.search(line):
                problems.append((os.path.basename(path), ln, line.strip()))
    return problems


def is_dynamic_target(name):
    """
    判断一个 [[...|目标]] 里的目标是不是「表达式 / 变量」而不是字面段落名。
    这类目标在静态检查阶段无法解析（SugarCube 会在运行时求值），
    所以不能报成「未定义段落」——否则 <<link [[<<= _x>>|_node.link]]>> 这种
    合法写法每次都会被误报。

    判定依据：出现 TwineScript 里不可能出现在段落名中的字符。
    （段落名可以有空格、中文、括号、连字符，所以只排除真正的语法字符。）
    """
    return any(ch in name for ch in "/+*<>=!&|?:[]{}\"'`") or name.startswith(("_", "$"))


def check_passages(mine_dir, extra_roots):
    """
    检查本 mod 的段落完整性：
      1. 本 mod 内部有没有重名段落（同名会被 ModLoader 合并覆盖，很难查）；
      2. 有没有和已存在的原版 / 其它 mod 段落重名（会覆盖对方！）；
      3. <<link [[...|目标]]>> 指向的段落是否真的存在。
    返回 (problems, info)。
    """
    problems = []

    def index(root):
        found = {}
        for path in walk(root, {".twee"}):
            text = read(path)
            for m in re.finditer(r"^::[ \t]*([^\n\[]+?)(?:\s*\[[^\]]*\])?\s*$", text, re.M):
                title = m.group(1).strip()
                if title:
                    found.setdefault(title, []).append(path)
        return found

    mine = index(mine_dir)
    foreign = {}
    for root in extra_roots:
        if root and os.path.isdir(root):
            for name, paths in index(root).items():
                foreign.setdefault(name, paths)

    for name, paths in mine.items():
        if len(paths) > 1:
            problems.append(
                f"本 mod 内部段落重名: {name!r}\n"
                f"        {', '.join(os.path.basename(p) for p in paths)}\n"
                f"        同名段落会被 ModLoader 合并，只有最后一个生效。")
        if name in foreign:
            problems.append(
                f"段落名与已有段落重名（会覆盖对方）: {name!r}\n"
                f"        对方位置: {foreign[name][0]}")

    # 引用目标检查（剔除注释，避免把说明文字里的示例段落名当成真实链接）
    src = ""
    for path in walk(mine_dir, {".twee"}):
        src += strip_comments(read(path))
    refs = {m.group(1).strip() for m in re.finditer(r"\|([^\]\|\n]+)\]\]", src)}
    dynamic = sorted(r for r in refs if r and is_dynamic_target(r))
    refs -= set(dynamic)
    undefined = sorted(r for r in refs if r and r not in mine and r not in foreign)

    return problems, {
        "passages": len(mine),
        "refs": len(refs),
        "undefined": undefined,
        "dynamic": dynamic,
    }


FORBIDDEN_IN_TAXI = {
    "<<destination5>>": (
        "会调 <<domus>>/<<oxford>> 这类 widget 往 $link_table 塞一条旅行链接"
        "（例如「牛津街 (0:05) (学校)」），玩家会同时看到目的地链接和【继续】"
        "两个效果完全相同的按钮。"
    ),
    "<<destinationeventend>>": "会额外生成一个 Next 按钮，同样与【继续】重复。",
}


def check_forbidden(mine_dir):
    """
    禁止在出租车的到达流程里使用原版 destination 系列宏。
    这是已经修过的 bug（玩家看到两个一模一样的选项），这里做成常驻守卫。
    注释里的说明文字不算 —— 用 strip_comments 剔除。
    """
    problems = []
    for path in walk(mine_dir, {".twee"}):
        text = strip_comments(read(path))
        # 只检查非 widget 说明段落：有 [widget] 标签的段落不会被渲染
        for part in re.split(r"^::[ \t]*", text, flags=re.M)[1:]:
            head, _, body = part.partition("\n")
            is_widget = "[" in head and "widget" in head
            title = re.sub(r"\[[^\]]*\]\s*$", "", head).strip()
            if is_widget:
                continue
            for token, why in FORBIDDEN_IN_TAXI.items():
                if token in body:
                    problems.append(
                        f"段落 {title!r} 使用了 {token}\n"
                        f"        原因: {why}\n"
                        f"        到达请改用 <<robertTaxiArriveLink>>（见 robert-taxi.twee）。")
    return problems


RE_TEMP_VAR_DECL = re.compile(r"<<set\s+(_[A-Za-z_][A-Za-z0-9_]*)\s+to\b")



def check_cross_passage_vars(mine_dir):
    """
    找出「在某个段落里 <<set _xxx to ...>>、但在**另一个**段落里又被读取」的临时变量。

    SugarCube 的 enginePlay() 每次进入新段落前都会 State.clearTemporary()，
    所以 `_` 临时变量**跨不了段落** —— 这类写法会静默失效。
    （实例：$robertTaxiJump 原本写成 _robertTaxiJump，每次点【继续】都被清零，
      循环上限永远不生效。）

    只在**同一个段落内部**使用的临时变量是正常写法，不报。
    """
    problems = []
    passages = {}
    for path in walk(mine_dir, {".twee"}):
        text = strip_comments(read(path))
        # ⚠️ 必须带 re.M：段落头在行首，不是字符串开头
        for part in re.split(r"^::[ \t]*", text, flags=re.M)[1:]:
            head, _, body = part.partition("\n")
            is_widget = "widget" in head.split("[")[-1]
            title = re.sub(r"\[[^\]]*\]\s*$", "", head).strip()
            if title and not is_widget:
                passages[title] = body

    # 每个临时变量的「赋值段落」与「读取段落」
    written, used = {}, {}
    for title, body in passages.items():
        for name in RE_TEMP_VAR_DECL.findall(body):
            written.setdefault(name, set()).add(title)
        for name in re.findall(r"\b(_[A-Za-z_][A-Za-z0-9_]*)\b", body):
            used.setdefault(name, set()).add(title)

    for name, w in written.items():
        # 只关心本 mod 自己的变量（_robertXxx / _rbXxx）
        low = name.lower()
        if not (low.startswith("_robert") or low.startswith("_rb")):
            continue
        other = used.get(name, set()) - w
        if other:
            problems.append(
                f"临时变量 {name!r} 跨段落使用（会静默失效）\n"
                f"        赋值于: {', '.join(sorted(w))}\n"
                f"        读取于: {', '.join(sorted(other))}\n"
                f"        enginePlay() 每次进新段落都会 State.clearTemporary()，"
                f"请改用存档变量 ${name[1:]}。")
    return problems


def main():
    ap = argparse.ArgumentParser(description="RobertNPC twee 宏完整性自检")
    ap.add_argument("--workspace", default=DEFAULT_WORKSPACE)
    ap.add_argument("--mine", default=None)
    ap.add_argument("--vanilla", default=None)
    ap.add_argument("--module", default=None)
    ap.add_argument("--quiet", action="store_true", help="只输出问题")
    args = ap.parse_args()

    ws = args.workspace
    mine = args.mine or os.path.join(ws, DEFAULT_MINE)
    vanilla = args.vanilla or os.path.join(ws, DEFAULT_VANILLA)
    modules = args.module or os.path.join(ws, DEFAULT_MODULES)
    if not os.path.isdir(mine):
        print(f"[错误] 找不到本 mod 目录: {mine}", file=sys.stderr)
        return 2

    extra = [os.path.join(ws, d) for d in EXTRA_SOURCES]
    defined = gather_defined(vanilla, modules, *extra)

    def say(*a):
        if not args.quiet:
            print(*a)

    say(f"已知宏/widget 定义数 : {len(defined)}")
    say(f"  - 原版 {os.path.relpath(vanilla, ws)}")
    if os.path.isdir(modules):
        say(f"  - 模块 {os.path.relpath(modules, ws)}")
    for d in EXTRA_SOURCES:
        say(f"  - {d}  {'(存在)' if os.path.isdir(os.path.join(ws, d)) else '(缺失)'}")

    # 收集本 mod 自己定义的 widget，然后把它自己也算作已知
    mine_defined = set()
    ours = []
    for path in walk(mine, {".twee"}):
        text = read(path)
        mine_defined |= set(RE_WIDGET.findall(text))
        # 检查宏调用时必须剔除块注释，否则说明文字里的占位名（如 <<promiscuousN>>）
        # 会被当成真实调用而误报。
        ours.append((path, strip_comments(text)))
    known = defined | mine_defined | SUGARCUBE_MACROS

    say(f"本 mod 自定义 widget : {len(mine_defined)} 个 "
        f"{sorted(mine_defined) if mine_defined else ''}")
    say()

    missing = []
    used = set()
    for path, text in ours:
        for m in RE_CALL.finditer(text):
            name = m.group(1)
            if name in IGNORE:
                continue
            used.add(name)
            if name not in known:
                line = text.count("\n", 0, m.start()) + 1
                missing.append((name, os.path.relpath(path, ws), line))

    say(f"本 mod 使用的宏名   : {len(used)} 个")
    say(f"  {', '.join(sorted(used))}")
    say()

    # ---- 脚本顶层全局检查 -------------------------------------------------
    # 专门防「setup is not defined」：params.script 在 SugarCube 启动前执行。
    toplevel = check_script_toplevel(mine)
    if toplevel:
        print("=" * 74)
        print(f"发现 {len(toplevel)} 处脚本顶层引用了 SugarCube 全局")
        print("（params.script 在 afterRegisterMod2Addon 执行，此时 setup / State 尚不存在，")
        print("  顶层引用会让整个脚本抛异常中止，mod 的 JS 侧完全不工作）：")
        for fname, ln, text in toplevel:
            print(f"  [顶层引用] {fname}:{ln}   {text}")
        print("=" * 74)
        return 1
    say("脚本顶层检查      : 未在 IIFE 顶层引用 setup / State（符合 params.script 的时机约束）")
    say()

    # ---- 段落完整性检查 ---------------------------------------------------
    psg_problems, psg_info = check_passages(mine, [vanilla, modules, *extra])
    if psg_info["undefined"]:
        print("=" * 74)
        print("发现指向不存在段落的链接（点进去会报「找不到段落」）：")
        for name in psg_info["undefined"]:
            print(f"  [未定义段落] {name}")
        print("=" * 74)
        return 1
    if psg_problems:
        print("=" * 74)
        print(f"发现 {len(psg_problems)} 处段落问题：")
        for item in psg_problems:
            print(f"  [段落] {item}")
        print("=" * 74)
        return 1
    say(f"段落完整性检查    : {psg_info['passages']} 个段落，无重名、"
        f"{psg_info['refs']} 个链接目标全部存在"
        + (f"（另有 {len(psg_info['dynamic'])} 个运行时求值目标，静态跳过）"
           if psg_info.get("dynamic") else ""))
    if psg_info.get("dynamic"):
        for name in psg_info["dynamic"]:
            say(f"      · 运行时目标: {name!r}")
    say()

    # ---- 出租车到达流程守卫 -------------------------------------------------
    forbidden = check_forbidden(mine)
    if forbidden:
        print("=" * 74)
        print(f"发现 {len(forbidden)} 处被禁用的到达写法（会导致重复选项）：")
        for item in forbidden:
            print(f"  [禁用] {item}")
        print("=" * 74)
        return 1
    say("出租车到达守卫    : 未使用 <<destination5>> / <<destinationeventend>>（不会出现重复选项）")
    say()

    cross_var = check_cross_passage_vars(mine)
    if cross_var:
        print("=" * 74)
        print(f"发现 {len(cross_var)} 处临时变量使用错误（会静默失效）：")
        for item in cross_var:
            print(f"  [临时变量] {item}")
        print("=" * 74)
        return 1
    say("跨段落变量检查    : 没有 `_` 临时变量被跨段落使用（都用 $ 存档变量）")
    say("      ⚠️ 局限：这条只能抓「一个段落赋值、另一个段落读取」的写法。")
    say("         抓不到「每页都用 <<set _x to 默认值>> 重置」这种 ——")
    say("         那在结构上和合法用法完全一样。跨段落状态一律用 $，别用 _。")
    say()

    if missing:
        print("=" * 74)
        print(f"发现 {len(missing)} 处未定义的宏调用（运行到对应段落时会报红字错误）：")
        for name, path, line in missing:
            print(f"  [未定义] <<{name}>>   {path}:{line}")
        print("=" * 74)
        return 1

    print("=" * 74)
    print("全部宏调用均已定义，未发现 macro does not exist 风险。")
    print("=" * 74)
    return 0

if __name__ == "__main__":
    sys.exit(main())
