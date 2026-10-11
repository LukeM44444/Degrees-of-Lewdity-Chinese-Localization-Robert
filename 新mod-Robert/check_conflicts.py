#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RobertNPC —— 命名冲突自检工具
===========================================================================
在打包前跑一次，检查本 mod 的段落名 / widget 名 / 存档变量 / 全局名
是否和下列来源撞车：

  1. 原版游戏源码      游戏源代码-degrees-of-lewdity-master/game/**/*.twee|js
  2. 汉化 mod          (只查 passage 名是否被汉化 mod 覆盖)
  3. 图包 mod          (只查图片路径)
  4. 框架 mod          maplebirch 的全局名与内部名字
  5. 象牙怨灵 mod      Wraith.sReflection.mod
  6. 哈珀 mod          ClaimableHarperbyMonMondayy_DOLP

用法：
    python check_conflicts.py                 # 用默认路径
    python check_conflicts.py --mine <目录>   # 指定本 mod 源目录
    python check_conflicts.py --quiet         # 只输出问题

退出码：0 = 无冲突；1 = 发现冲突或高危警告；2 = 路径/参数错误。
===========================================================================
"""

import argparse
import json
import os
import re
import sys

# ---------------------------------------------------------------------------
# 默认路径（相对工作区根目录）
# ---------------------------------------------------------------------------
DEFAULT_WORKSPACE = r"D:\mod  c\xin mod"
DEFAULT_MINE = "新mod-Robert"

SOURCES = {
    "原版游戏源码": "游戏源代码-degrees-of-lewdity-master/game",
    "象牙怨灵mod": "象牙怨灵mod-Wraith.sReflection.mod",
    "哈珀mod": "哈珀mod-ClaimableHarperbyMonMondayy_DOLP",
    "汉化mod": "汉化文件源代码-ModI18N-0.5.11.9-chs-1.0.0a.mod",
    "图包mod": "图包mod-GameOriginalImagePack-0.5.11.9.mod",
    "框架mod": "框架mod-maplebirch-0.5.10.12-v4.1.14.mod",
}

# ---------------------------------------------------------------------------
# 提取正则
# ---------------------------------------------------------------------------
RE_PASSAGE = re.compile(r"^::\s*([^\[\{\n]+?)\s*(?:\[[^\]]*\])?\s*$", re.M)
# ⚠️ widget 定义必须**行首锚定**。
#    不带 ^ 的版本会把「注释里引用的 widget 名」也算成定义 ——
#    真实踩过：robert-cheat.twee 的说明注释里写了
#        * <<widget "cheats-npcs">>（base-system/overlays/cheats.twee:1209）里，
#    于是检查器报「widget 名与原版重名，会覆盖原版 widget！」，
#    而实际并没有覆盖。锚定行首（允许前置空白）即可排除正文/注释里的引用：
#    真正的定义总是从行首（或缩进后）开始的。
RE_WIDGET = re.compile(r'^[ \t]*<<widget\s+"([^"]+)"', re.M)
RE_WIDGET_BARE = re.compile(r"^[ \t]*<<widget\s+'([^']+)'", re.M)
RE_MACRO_ADD = re.compile(r'Macro\.add\s*\(\s*[\["\']([^"\'\]\[]+)')
RE_DEFINE_MACRO = re.compile(r'DefineMacro\w*\s*\(\s*["\']([^"\']+)["\']')
RE_WINDOW = re.compile(r'window\.([A-Za-z_$][\w$]*)\s*=')
RE_STORY_VAR = re.compile(r"\$([A-Za-z_][\w]*)")
RE_SETUP = re.compile(r"setup\.([A-Za-z_$][\w$]*)")

SKIP_DIRS = {"node_modules", ".git", "__pycache__", "dist-BeforeSC2", "out"}

# ---------------------------------------------------------------------------
# 有意覆盖的原版 widget：覆盖本身就是功能实现方式。
# 每条都要写清楚「为什么必须覆盖」——不要往里塞偷懒的例外。
# ---------------------------------------------------------------------------
ALLOWED_WIDGET_OVERRIDES = {
    "buswait":
        "在【等公交】与【消磨时间】之间插入【等待出租车】。原版 <<buswait>> 只往 "
        "$link_table 推一行公交链接，没有可插入的中间锚点，所以只能整体覆盖；"
        "robert-taxi.twee 里照抄了原版那一行，保证公交车不受影响。",
}

# 这些是「原版或框架拥有、本 mod 只读写」的存档变量，
# 功能上必须沿用原名（例如 $bus 是原版目的地系统的载体），不参与前缀检查。
FOREIGN_VARS = {
    "NPCName", "NPCNameList", "maplebirch", "objectVersion", "worn", "player",
    "bus", "forest", "foresthunt", "money", "outside", "options", "town_projects",
}

# 同理，这些 setup 键由框架 / 原版拥有，本 mod 只读取。
FOREIGN_SETUP_KEYS = {
    "setup.NPCNameList",
    "setup.loveInterestNpc",
    "setup.loveAlias",
    "setup.NPC_CN_NAME",
    "setup.NPC_CN_TITLE",
    "setup.clothingTraits",
    "setup.specialClothes",
    "setup.pills",
    "setup.shopDetails",
    "setup.baseNNPC",     # 原版命名 NPC 模板（四个属性的字段名就来自这里）
    "setup.baseNPC",      # 原版遭遇 NPC 模板
}


def walk_files(root, exts):
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            if os.path.splitext(name)[1].lower() in exts:
                yield os.path.join(base, name)


def read_text(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


class Inventory:
    """收集某一来源里占用的所有名字。"""

    def __init__(self, label):
        self.label = label
        self.passages = {}
        self.widgets = {}
        self.windows = {}
        self.macros = {}
        self.story_vars = set()
        self.setup_keys = set()
        self.images = set()

    def add(self, table, name, path):
        table.setdefault(name, path)

    def merge(self, other):
        for attr in ("passages", "widgets", "windows", "macros"):
            getattr(self, attr).update(getattr(other, attr))
        self.story_vars |= other.story_vars
        self.setup_keys |= other.setup_keys
        self.images |= other.images


def scan_twee_folder(label, root):
    inv = Inventory(label)
    if not os.path.isdir(root):
        return inv, False
    for path in walk_files(root, {".twee", ".js", ".css"}):
        text = read_text(path)
        ext = os.path.splitext(path)[1].lower()
        if ext == ".twee":
            for name in RE_PASSAGE.findall(text):
                inv.add(inv.passages, name.strip(), path)
            for rx in (RE_WIDGET, RE_WIDGET_BARE):
                for name in rx.findall(text):
                    inv.add(inv.widgets, name, path)
        for name in RE_MACRO_ADD.findall(text):
            inv.add(inv.macros, name, path)
        for name in RE_DEFINE_MACRO.findall(text):
            inv.add(inv.macros, name, path)
        for name in RE_WINDOW.findall(text):
            inv.add(inv.windows, name, path)
        for name in RE_STORY_VAR.findall(text):
            inv.story_vars.add(name)
        for name in RE_SETUP.findall(text):
            inv.setup_keys.add(name)
    return inv, True


def scan_boot_json_images(label, mod_dir):
    """从 mod 的 boot.json 里取 imgFileList。"""
    boot = os.path.join(mod_dir, "boot.json")
    inv = Inventory(label)
    if not os.path.isfile(boot):
        return inv, False
    try:
        with open(boot, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return inv, False
    for img in data.get("imgFileList", []) or []:
        if isinstance(img, str):
            inv.images.add(img)
    return inv, True


# 只对这些 mod 做 TweeReplacer 锚点交叉检查（都是会给原版打补丁的内容型 mod）
OTHER_TWEE_MODS = ["象牙怨灵mod", "哈珀mod"]


def extract_twee_patches(boot_path):
    """
    从 boot.json 里抽出所有 TweeReplacer 补丁（含 params 与 paramsFiles）。

    返回 [{"passage": ..., "find": ..., "src": 来源描述}, ...]
    """
    if not os.path.isfile(boot_path):
        return []
    try:
        with open(boot_path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return []

    patches = []
    root = os.path.dirname(boot_path)

    for plugin in data.get("addonPlugin", []) or []:
        if plugin.get("modName") != "TweeReplacer":
            continue

        # 内联 params
        for patch in plugin.get("params", []) or []:
            if isinstance(patch, dict) and "findString" in patch and "passage" in patch:
                patches.append({
                    "passage": patch["passage"],
                    "find": patch["findString"],
                    "replace": patch.get("replace", "") or "",
                    "hasReplaceFile": bool(patch.get("replaceFile")),
                    "src": os.path.basename(root),
                })

        # 外置 paramsFiles（JSON5，这里按 JSON 宽松解析）
        for rel in plugin.get("paramsFiles", []) or []:
            full = os.path.join(root, rel.replace("/", os.sep))
            if not os.path.isfile(full):
                continue
            try:
                with open(full, encoding="utf-8") as fh:
                    raw = fh.read()
            except OSError:
                continue
            items = load_json5_loose(raw)
            if not isinstance(items, list):
                continue
            for patch in items:
                if isinstance(patch, dict) and "findString" in patch and "passage" in patch:
                    patches.append({
                        "passage": patch["passage"],
                        "find": patch["findString"],
                        "replace": patch.get("replace", "") or "",
                        "hasReplaceFile": bool(patch.get("replaceFile")),
                        "src": rel,
                    })

    return patches


def load_json5_loose(raw):
    """
    极简 JSON5 容错解析：去掉 // 与 /* */ 注释、去掉尾随逗号，再交给 json.loads。
    只为读别人的 paramsFiles，解析失败就返回 None（不当作冲突）。
    """
    text = re.sub(r"/\*.*?\*/", "", raw, flags=re.S)
    text = re.sub(r"(^|[^:])//[^\n]*", r"\1", text)
    text = re.sub(r",(\s*[}\]])", r"\1", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def load_exported_passages(export_dir):
    """
    读取 ModLoader 错误日志导出的 passage 目录。
    这些是**打完所有 mod 补丁之后**的真实游戏文本，也就是 TweeReplacer
    实际看到的输入。用它校验 findString 才是准确的 ——
    拿原版源码校验会漏掉「汉化 mod 已经改过原文」这一类致命问题。
    """
    passage_dir = os.path.join(export_dir, "passage")
    if not os.path.isdir(passage_dir):
        return None
    out = {}
    for name in os.listdir(passage_dir):
        if not name.endswith(".twee"):
            continue
        path = os.path.join(passage_dir, name)
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        except OSError:
            continue
        if not text.startswith("::"):
            continue
        head, _, body = text.partition("\n")
        title = re.sub(r"^::[ \t]*", "", head)
        title = re.sub(r"\[[^\]]*\]\s*$", "", title).strip()
        if title and title not in out:
            out[title] = body
    return out


def find_export_dirs(workspace):
    """找出工作区里所有 ModLoader 错误日志导出目录，按名字排序（新的在后）。"""
    if not os.path.isdir(workspace):
        return []
    found = []
    for name in os.listdir(workspace):
        full = os.path.join(workspace, name)
        if os.path.isdir(full) and name.startswith("错误日志") and os.path.isdir(os.path.join(full, "passage")):
            found.append(full)
    return sorted(found)


def load_vanilla(workspace):
    """原版只统计 passage / widget / window / macro（story var 太多，单独按前缀判）。"""
    return scan_twee_folder("原版游戏源码", os.path.join(workspace, SOURCES["原版游戏源码"]))[0]


def main():
    parser = argparse.ArgumentParser(description="RobertNPC 命名冲突自检")
    parser.add_argument("--workspace", default=DEFAULT_WORKSPACE)
    parser.add_argument("--mine", default=None, help=f"本 mod 源目录（默认 {DEFAULT_MINE}）")
    parser.add_argument("--quiet", action="store_true", help="只输出问题")
    parser.add_argument("--patched-dir", default=None,
                        help="ModLoader 错误日志导出目录（含 passage/ 子目录）。"
                             "默认自动搜索工作区里的「错误日志*」目录。"
                             "用它校验 findString 能否匹配汉化后的真实文本。")
    args = parser.parse_args()

    workspace = args.workspace
    mine_dir = args.mine or os.path.join(workspace, DEFAULT_MINE)
    if not os.path.isdir(mine_dir):
        print(f"[错误] 找不到本 mod 目录: {mine_dir}", file=sys.stderr)
        return 2

    problems = []
    warnings = []

    def say(*a):
        if not args.quiet:
            print(*a)

    # ---- 收集本 mod 的占用 ------------------------------------------------
    mine, _ = scan_twee_folder("本mod", mine_dir)
    # boot.json 里没有 passage，但 framework.js 与 modules/ 里的名字也要查
    for extra in ("framework.js",):
        p = os.path.join(mine_dir, extra)
        if os.path.isfile(p):
            text = read_text(p)
            for name in RE_MACRO_ADD.findall(text):
                mine.add(mine.macros, name, p)
            for name in RE_WINDOW.findall(text):
                mine.add(mine.windows, name, p)

    img_inv, _ = scan_boot_json_images("本mod", mine_dir)
    mine.images |= img_inv.images

    # 本 mod 自己声明的 widget：从 twee 里已经拿到
    say("=" * 74)
    say(f"本 mod 目录 : {mine_dir}")
    say(f"  段落   {len(mine.passages):>5} 个")
    say(f"  widget {len(mine.widgets):>5} 个 : {', '.join(sorted(mine.widgets)) or '(无)'}")
    say(f"  宏     {len(mine.macros):>5} 个")
    say(f"  全局名 {len(mine.windows):>5} 个")
    say(f"  图片   {len(mine.images):>5} 个")
    say(f"  存档变量 {len(mine.story_vars):>5} 个 : "
        f"{', '.join('$' + v for v in sorted(mine.story_vars)) or '(无)'}")
    say(f"  setup 键 {len(mine.setup_keys):>5} 个 : "
        f"{', '.join('setup.' + v for v in sorted(mine.setup_keys)) or '(无)'}")
    say("=" * 74)
    say()

    # ---- 1. 原版 ----------------------------------------------------------
    vanilla = load_vanilla(workspace)
    say(f"[1/6] 原版游戏源码：{len(vanilla.passages)} 段落 / {len(vanilla.widgets)} widget / "
        f"{len(vanilla.windows)} 全局名 / {len(vanilla.macros)} 宏")

    for name in mine.passages:
        if name in vanilla.passages:
            problems.append(f"段落名与原版重名（会覆盖原版段落！）: :: {name}\n"
                            f"        原版位置: {os.path.relpath(vanilla.passages[name], workspace)}")
    for name in mine.widgets:
        if name in vanilla.widgets and name not in ALLOWED_WIDGET_OVERRIDES:
            problems.append(f"widget 名与原版重名（会覆盖原版 widget！）: <<widget \"{name}\">>\n"
                            f"        原版位置: {os.path.relpath(vanilla.widgets[name], workspace)}\n"
                            f"        若是刻意覆盖，请在 ALLOWED_WIDGET_OVERRIDES 里登记原因")
    for name in mine.windows:
        if name in vanilla.windows:
            problems.append(f"全局名与原版重名: window.{name}\n"
                            f"        原版位置: {os.path.relpath(vanilla.windows[name], workspace)}")
    for name in mine.macros:
        if name in vanilla.macros:
            warnings.append(f"宏名与原版重名（可能是有意覆盖原版宏，请确认）: <<{name}>>")
    say("      → 检查完毕")
    say()

    # ---- 2~6. 其他 mod ----------------------------------------------------
    mods = ["象牙怨灵mod", "哈珀mod", "汉化mod", "图包mod"]
    for idx, key in enumerate(mods, start=2):
        root = os.path.join(workspace, SOURCES[key])
        inv, ok = scan_twee_folder(key, root)
        if not ok:
            warnings.append(f"[{key}] 目录不存在，已跳过: {root}")
            say(f"[{idx}/6] {key}：目录不存在，跳过")
            say()
            continue

        say(f"[{idx}/6] {key}：{len(inv.passages)} 段落 / {len(inv.widgets)} widget")

        for name in mine.passages:
            if name in inv.passages:
                problems.append(f"段落名与{key}重名: :: {name}\n"
                                f"        对方位置: {os.path.relpath(inv.passages[name], workspace)}")
        for name in mine.widgets:
            if name in inv.widgets:
                problems.append(f"widget 名与{key}重名: <<widget \"{name}\">>\n"
                                f"        对方位置: {os.path.relpath(inv.widgets[name], workspace)}")
        for name in mine.windows:
            if name in inv.windows:
                problems.append(f"全局名与{key}重名: window.{name}")
        for name in sorted(mine.story_vars):
            if name in inv.story_vars:
                warnings.append(f"存档变量 ${name} 也出现在{key}中（确认是否同一含义）")
        say("      → 检查完毕")
        say()

    # ---- 图片路径 ---------------------------------------------------------
    imgpack_root = os.path.join(workspace, SOURCES["图包mod"])
    imgpack, ok = scan_boot_json_images("图包mod", imgpack_root)
    if ok:
        say(f"[图片] 图包 mod 共 {len(imgpack.images)} 张图")
        for img in sorted(mine.images):
            if img in imgpack.images:
                problems.append(f"图片路径与图包 mod 重名（会被图包覆盖）: {img}")
        say("      → 检查完毕")
        say()

    # ---- TweeReplacer 补丁锚点冲突（最重要的一项） -------------------------
    say("[补丁] TweeReplacer 锚点交叉检查")
    mine_patches = extract_twee_patches(os.path.join(mine_dir, "boot.json"))
    if not mine_patches:
        say("      本 mod 没有 TweeReplacer 补丁，跳过")
        say()
    else:
        say(f"      本 mod 有 {len(mine_patches)} 条补丁，锁定段落："
            f"{', '.join(sorted({p['passage'] for p in mine_patches}))}")
        for label in OTHER_TWEE_MODS:
            root = os.path.join(workspace, SOURCES[label])
            boot_path = os.path.join(root, "boot.json")
            if not os.path.isfile(boot_path):
                continue
            theirs = extract_twee_patches(boot_path)
            if not theirs:
                continue
            their_passages = {p["passage"]: p for p in theirs}
            their_anchors = {}
            for p in theirs:
                their_anchors.setdefault(p["passage"], []).append(p["find"])

            touched = 0
            for p in mine_patches:
                psg = p["passage"]
                if psg not in their_passages:
                    continue
                touched += 1
                exact = [f for f in their_anchors[psg] if f == p["find"]]
                # 只有「一方锚点是另一方的前缀」才可能互相影响。
                # 注意：startswith 判定本身**不足以**断定有危险 ——
                # 如果较长的锚点把较短的那个完整包住，且较短方的 replace 保留了
                # 这个前缀，那么两种加载顺序都能命中（用真实文本模拟即可证明）。
                prefix = [f for f in their_anchors[psg]
                          if f != p["find"]
                          and (f.startswith(p["find"]) or p["find"].startswith(f))]
                if exact:
                    problems.append(
                        f"TweeReplacer 锚点与{label}完全相同（必然互相脱锚）:\n"
                        f"        段落: {psg}\n"
                        f"        findString: {p['find'][:80]!r}")
                elif prefix:
                    # 进一步判断：较长的一方是否把较短一方的前缀完整包含？
                    # 是的话只是「嵌套」，不是冲突 —— 两种加载顺序都能命中。
                    # 若对方用 replaceFile 外置文本，这里读不到内容，保守起见报警告。
                    nested = False
                    if any(f.startswith(p["find"]) for f in prefix):
                        # 对方锚点更长：它的 replace 必须保留我方锚点
                        nested = p["find"] in p["replace"]
                    else:
                        # 我方锚点更长：我的 replace 必须保留对方锚点作为开头
                        nested = any(p["replace"].startswith(f) for f in prefix)

                    if nested:
                        say(f"      · 段落 {psg!r} 锚点与{label}构成嵌套，"
                            f"较长锚点完整包含较短锚点 → 两种加载顺序均可命中")
                    else:
                        warnings.append(
                            f"锚点与{label}存在前缀包含关系（可能互相脱锚，请人工确认）:\n"
                            f"        段落: {psg}\n"
                            f"        本 mod: {p['find'][:60]!r}\n"
                            f"        对方  : {prefix[0][:60]!r}\n"
                            f"        自动判定未能确认安全（对方可能用 replaceFile 外置文本，"
                            f"或较长方的 replace 破坏了这个前缀）。")
                else:
                    say(f"      ✓ 段落 {psg!r} 双方都改，但锚点文本不重叠"
                        f"（对方 {len(their_anchors[psg])} 条）")
            if touched == 0:
                say(f"      ✓ 与本 mod 的补丁段落无交集（{label} 共 {len(their_passages)} 个段落）")
    say("      → 检查完毕")
    say()

    # ---- 用「打完补丁的真实游戏文本」校验锚点 ------------------------------
    # 这是最关键的一步：TweeReplacer 看到的是所有 mod 补丁之后的文本。
    # 汉化 mod（ModI18N）会先一步把原版英文换成中文，如果 findString 还写英文，
    # 补丁会直接匹配失败 —— 本 mod 第一版就栽在这里。
    say("[补丁] 锚点 vs 实际打补丁后的游戏文本")
    exports = [args.patched_dir] if args.patched_dir else find_export_dirs(workspace)
    exports = [e for e in exports if e]
    if not mine_patches:
        say("      没有补丁，跳过")
        say()
    elif not exports:
        warnings.append(
            "没有找到 ModLoader 错误日志导出目录（错误日志*/passage），"
            "无法校验 findString 是否匹配「汉化之后」的真实文本。\n"
            "        强烈建议至少做一次实机测试并把导出目录放到工作区，再跑一次本脚本。")
        say("      ！未找到导出目录，跳过（这是最关键的检查项，建议补上）")
        say()
    else:
        for export_dir in exports:
            patched = load_exported_passages(export_dir)
            if not patched:
                continue
            say(f"      数据来源: {os.path.basename(export_dir)}"
                f"（{len(patched)} 个段落）")
            for p in mine_patches:
                psg = p["passage"]
                if psg not in patched:
                    warnings.append(
                        f"补丁目标段落 {psg!r} 不在导出数据里，无法校验锚点")
                    say(f"      ？ {psg!r} 不在导出里")
                    continue
                n = patched[psg].count(p["find"])
                if n == 1:
                    say(f"      ✓ [{psg}] findString 唯一匹配")
                elif n == 0:
                    problems.append(
                        f"findString 在实际打补丁后的文本里匹配失败 —— 补丁不会生效！\n"
                        f"        段落: {psg}\n"
                        f"        findString: {p['find'][:100]!r}\n"
                        f"        常见原因: 汉化 mod 已经把原文改成中文了（或被其它 mod 改过）。\n"
                        f"        请从导出目录的 passage/{psg}.twee 里取真实文本重新填写。")
                    say(f"      ✗ [{psg}] 匹配失败")
                else:
                    warnings.append(
                        f"findString 在 [{psg}] 里命中 {n} 次（TweeReplacer 默认只替换第一处）")
                    say(f"      ！ [{psg}] 命中 {n} 次")
    say("      → 检查完毕")
    say()

    # ---- buswait 覆盖的一致性检查 -----------------------------------------
    # 本 mod 覆盖了原版 <<buswait>>，所以必须在自己的 widget 里把原版那行公交链接
    # 照抄回来。这里要求「boot.json 的 findString」与「本 mod widget 里那行公交链接」
    # 中的中文字符串逐字一致 —— 两者一旦分叉，补丁就会匹配失败或输出错误文本。
    say("[补丁] buswait 覆盖一致性")
    bus_patches = [p for p in mine_patches
                   if p["passage"] == "Widgets Bus" and "busicon" in p["find"]]
    if not bus_patches:
        say("      本 mod 没有覆盖 buswait，跳过")
        say()
    else:
        # 从 findString 里取出 [[...]] 中的链接文本
        def bus_label(text):
            m = re.search(r"\[\[([^\]|]+?)\s*\(0:0?2\)", text)
            return m.group(1).strip() if m else None

        anchor_label = bus_label(bus_patches[0]["find"])
        widget_label = None
        taxi_path = os.path.join(mine_dir, "robert-taxi.twee")
        if os.path.isfile(taxi_path):
            tw = read_text(taxi_path)
            m = re.search(r"<<widget \"buswait\">>(.*?)<</widget>>", tw, re.S)
            if m and "busicon" in m.group(1):
                widget_label = bus_label(m.group(1))

        if not anchor_label:
            warnings.append("无法从补丁 1 的 findString 里解析出公交链接文本，跳过一致性检查")
            say("      ！ 解析失败")
        elif not widget_label:
            problems.append(
                "本 mod 覆盖了 buswait，但 robert-taxi.twee 的 <<widget \"buswait\">> 里"
                "找不到公交链接 —— 公交车会消失！")
            say("      ✗ widget 里没有公交链接")
        elif anchor_label != widget_label:
            problems.append(
                f"buswait 覆盖不一致（会同时导致补丁失效与文本错误）:\n"
                f"        boot.json findString 里的公交链接: {anchor_label!r}\n"
                f"        robert-taxi.twee widget 里的公交链接: {widget_label!r}\n"
                f"        两者必须逐字一致。")
            say(f"      ✗ 不一致: {anchor_label!r} vs {widget_label!r}")
        else:
            say(f"      ✓ 两处公交链接文本一致: {anchor_label!r}")
    say("      → 检查完毕")
    say()

    # ---- 前缀规范检查 -----------------------------------------------------
    say("[规范] 前缀检查（框架 / 原版拥有的键已排除）")
    for name in mine.passages:
        if not name.startswith("Robert"):
            warnings.append(f"段落名未使用 Robert 前缀: :: {name}")
    for name in mine.widgets:
        if name in ALLOWED_WIDGET_OVERRIDES:
            say(f"      · 有意覆盖原版 widget <<{name}>>：{ALLOWED_WIDGET_OVERRIDES[name]}")
            continue
        if not name.lower().startswith("robert"):
            warnings.append(f"widget 名未使用 robert 前缀: {name}")
    for name in sorted(mine.story_vars):
        if name in FOREIGN_VARS:
            continue
        if not name.lower().startswith(("robert", "rb", "_rb")):
            warnings.append(f"存档变量未使用 robert 前缀: ${name}")
    for name in sorted(mine.setup_keys):
        if f"setup.{name}" in FOREIGN_SETUP_KEYS:
            continue
        if not name.lower().startswith(("robert", "rb")):
            warnings.append(f"setup 键未使用 robert 前缀: setup.{name}")
    say("      → 检查完毕")
    say()

    # ---- 汇总 -------------------------------------------------------------
    say("=" * 74)
    if problems:
        print(f"发现 {len(problems)} 处冲突：")
        for item in problems:
            print(f"  [冲突] {item}")
    if warnings:
        print()
        print(f"{len(warnings)} 条提醒：")
        for item in warnings:
            print(f"  [提醒] {item}")
    if not problems and not warnings:
        print("未发现命名冲突，规范检查全部通过。")
    elif not problems:
        print()
        print("未发现硬冲突（冲突 = 段落/widget/全局名/图片重名）。提醒项请人工确认。")
    print("=" * 74)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
