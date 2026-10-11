#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RobertNPC —— 打包脚本
===========================================================================
把 mod 源文件夹打包成 ModLoader 能直接读取的 .mod 文件（标准 zip）。

为什么需要它：ModLoader 用 JSZip 读 zip，对条目名和压缩方式有硬性要求，
手打包很容易踩坑（社区里最常见的就是「条目名用了反斜杠」导致图片全部读不到）。

本脚本做的事情：
  1. 读取并解析 boot.json；
  2. 校验 boot.json 里引用的每一个文件都真实存在（漏打包会直接报错）；
  3. 校验所有路径都是正斜杠、相对路径；
  4. 用 Store / Deflate、UTF-8 文件名打包成 zip；
  5. 打包后重新打开 zip 逐条校验，并打印清单。

用法：
    python build_mod.py
    python build_mod.py --check-only      # 只校验，不打包
    python build_mod.py --out 别的名字.mod
===========================================================================
"""

import argparse
import json
import os
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))

# 打包参数（按需求固定）：
#   格式     : .zip  —— ModLoader 的 .mod 就是标准 zip，只是扩展名不同
#   压缩方法 : Deflate
#   压缩等级 : 5（标准压缩）
# 说明：PNG 本身已是压缩格式，Deflate 对它的收益很小，但统一用 Deflate
#       可以保证任何解压实现都不会因为 Store 条目而出现兼容问题。
COMPRESS_LEVEL = 5

# boot.json 里所有「文件路径列表」类型的字段（元素是字符串）
LIST_OF_PATHS_FIELDS = [
    "styleFileList",
    "scriptFileList",
    "scriptFileList_inject_early",
    "scriptFileList_earlyload",
    "scriptFileList_preload",
    "tweeFileList",
    "imgFileList",
    "imgFileReplaceList",
    "additionFile",
    "additionBinaryFile",
    "additionDir",
    "paramsFiles",
]

# 这些字段里出现的路径不要求文件存在（例如框架的 translations 目录）
SKIP_EXISTENCE_CHECK = {"additionDir"}


def fail(msg):
    print(f"[错误] {msg}", file=sys.stderr)
    return False


def collect_paths(boot, where="boot.json"):
    """从 boot.json 里递归收集所有文件路径，返回 (field, path) 列表。"""
    found = []

    def walk(node, field):
        if isinstance(node, str):
            # 只把看起来像路径的字符串收进来
            if "/" in node or node.lower().endswith(
                (".js", ".twee", ".css", ".json", ".json5", ".png", ".jpg",
                 ".jpeg", ".gif", ".webp", ".md", ".txt", ".yml", ".yaml",
                 ".ttf", ".base64", ".py")
            ):
                found.append((field, node))
        elif isinstance(node, list):
            for item in node:
                walk(item, field)
        elif isinstance(node, dict):
            for key, value in node.items():
                if key in LIST_OF_PATHS_FIELDS:
                    walk(value, key)
                elif key == "modName" or key.startswith("_"):
                    continue
                else:
                    # paramsFiles / script / module / language 等
                    if key in ("paramsFiles", "script", "module"):
                        walk(value, key)
                    elif key == "language" and isinstance(value, dict):
                        walk(list(value.values()), "language")
                    else:
                        walk(value, field)

    for field in LIST_OF_PATHS_FIELDS:
        if field in boot:
            walk(boot[field], field)

    for plugin in boot.get("addonPlugin", []):
        params = plugin.get("params")
        if isinstance(params, dict):
            for key in ("paramsFiles", "script", "module"):
                if key in params:
                    walk(params[key], key)
            lang = params.get("language")
            if isinstance(lang, dict):
                walk(list(lang.values()), "language")

    return found


def normalize(path):
    return path.replace("\\", "/").lstrip("./")


def check(boot):
    ok = True
    print(f"模组名称 : {boot.get('name')}")
    print(f"模组版本 : {boot.get('version')}")
    print()

    paths = collect_paths(boot)
    seen = {}
    for field, raw in paths:
        path = normalize(raw)
        if path != raw:
            ok = fail(f"{field}: 路径必须用正斜杠相对路径，发现 {raw!r}") or ok
        if path in seen and seen[path] != field:
            print(f"[提示] {path} 被多个字段引用（{seen[path]} / {field}），这是允许的。")
        seen[path] = field
        if field in SKIP_EXISTENCE_CHECK:
            continue
        full = os.path.join(HERE, path.replace("/", os.sep))
        if not os.path.isfile(full):
            ok = fail(f"{field}: boot.json 引用了不存在的文件 -> {path}") or ok

    # 反向检查：源目录里有没有漏登记的文件
    print(f"boot.json 引用文件数: {len(seen)}")
    orphans = []
    for root, dirs, files in os.walk(HERE):
        dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git")]
        for name in files:
            rel = os.path.relpath(os.path.join(root, name), HERE).replace(os.sep, "/")
            if rel.startswith("_"):
                continue
            if rel in ("boot.json", "build_mod.py"):
                continue
            if rel.endswith((".mod", ".mod.zip", ".modpack", ".zip")):
                continue
            if rel not in seen and not any(rel.startswith(p.rstrip("/") + "/") for p in seen):
                orphans.append(rel)
    if orphans:
        print()
        print("[提示] 以下文件存在于源目录但未被 boot.json 引用，不会被打包：")
        for rel in sorted(orphans):
            print(f"       - {rel}")
    return ok

def build(boot, out_path):
    files = []
    out_abs = os.path.abspath(out_path)
    for root, dirs, names in os.walk(HERE):
        dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git")]
        for name in names:
            full = os.path.join(root, name)
            rel = os.path.relpath(full, HERE).replace(os.sep, "/")
            if rel.startswith("_") or rel == "build_mod.py":
                continue
            # 不把打包产物本身装进去（否则会变成"包中包"）
            if rel.endswith((".mod", ".mod.zip", ".modpack", ".zip")):
                continue
            if os.path.abspath(full) == out_abs:
                continue
            files.append((rel, full))

    files.sort(key=lambda item: (item[0] != "boot.json", item[0]))

    # 打包参数（按需求固定，不要随意改）：
    #   格式     : .zip（ModLoader 的 .mod 就是标准 zip，只是换了扩展名）
    #   压缩方法 : Deflate
    #   压缩等级 : 5（标准压缩）
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED, compresslevel=COMPRESS_LEVEL) as zf:
        for rel, full in files:
            # 不写目录条目，条目名一律正斜杠；中文名交给 zipfile 以 UTF-8 处理
            zf.write(full, arcname=rel)

    # 打包后自检
    with zipfile.ZipFile(out_path) as zf:
        bad = zf.testzip()
        if bad:
            return fail(f"打包后校验失败，第一个损坏条目: {bad}")
        names = zf.namelist()
        if "boot.json" not in names:
            return fail("打包后 zip 根目录缺少 boot.json")
        for info in zf.infolist():
            if "\\" in info.filename:
                return fail(f"条目名含反斜杠: {info.filename}")
            if info.compress_type != zipfile.ZIP_DEFLATED:
                return fail(f"条目压缩方式不是 Deflate: {info.filename}")
        print()
        print(f"打包完成: {out_path}")
        print(f"压缩方式: Deflate / 等级 {COMPRESS_LEVEL}（标准压缩）")
        print(f"条目数  : {len(names)}")
        raw = sum(i.file_size for i in zf.infolist())
        print(f"文件大小: {os.path.getsize(out_path):,} 字节（原始 {raw:,} 字节）")
        print()
        print("zip 内容清单：")
        for name in names:
            print(f"  - {name}")
    return True


def run_page_checks():
    """
    打包前跑一遍「页面级」检查脚本。

    为什么放在这里：这些检查抓的是**不会报错、只有跑起来才发现**的问题
    （告示与实际数值不符、跨段落临时变量被清空、宏没配平…）。
    放在打包流程里，就不会出现「检查写了但忘了跑」。

    约定：同目录下 check_*.py 里带 `if __name__ == "__main__"` 的脚本，
    退出码 0 = 通过，非 0 = 失败。check_conflicts.py / check_macros.py 依赖
    工作区里的原版源码，耗时较长，所以**不在**这里跑，仍由人工/CI 单独调用。
    """
    import subprocess

    scripts = ["check_comments.py", "check_expr_chars.py",
               "check_caress_invariant.py", "check_combat_page.py",
               "check_feat.py", "check_stat_chips.py"]
    failed = []
    for name in scripts:
        path = os.path.join(HERE, name)
        if not os.path.isfile(path):
            print(f"  [跳过] {name}（不存在）")
            continue
        print(f"  运行 {name} ...")
        proc = subprocess.run(
            [sys.executable, path],
            cwd=HERE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        out = proc.stdout.decode("utf-8", "replace").strip()
        if proc.returncode == 0:
            # 只打印最后一行结论，避免刷屏
            last = out.splitlines()[-2] if len(out.splitlines()) > 1 else out
            print(f"    ✓ 通过：{last.strip()}")
        else:
            print(out)
            failed.append(name)
    return failed


def main():
    parser = argparse.ArgumentParser(description="RobertNPC 打包脚本")
    parser.add_argument("--out", default=None, help="输出文件名（默认 <mod名>.mod）")
    parser.add_argument("--check-only", action="store_true", help="只校验 boot.json，不打包")
    parser.add_argument("--skip-page-checks", action="store_true",
                        help="跳过页面级检查（不建议；仅调试用）")
    args = parser.parse_args()

    boot_path = os.path.join(HERE, "boot.json")
    if not os.path.isfile(boot_path):
        fail(f"找不到 boot.json: {boot_path}")
        return 1
    with open(boot_path, "r", encoding="utf-8") as fh:
        boot = json.load(fh)

    if not check(boot):
        print()
        fail("校验未通过，已中止打包。")
        return 1

    if not args.skip_page_checks:
        print()
        print("=" * 74)
        print("页面级检查")
        print("=" * 74)
        failed = run_page_checks()
        if failed:
            print()
            fail(f"页面级检查未通过：{', '.join(failed)}")
            return 1

    if args.check_only:
        print()
        print("校验通过（--check-only，未打包）。")
        return 0

    out_name = args.out or f"{boot.get('name', 'mod')}.mod"
    out_path = out_name if os.path.isabs(out_name) else os.path.join(HERE, out_name)
    if not build(boot, out_path):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
