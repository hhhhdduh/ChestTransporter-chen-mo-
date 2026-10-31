# -*- coding: utf-8 -*-
"""发布前自检：JSON 结构 / 物品与贴图互引 / 配方结果 / Python 2.7 语法。

用法：
    python tools/selfcheck.py        py3 下会自动用 py -2.7 重跑语法检查
    py -2.7 tools/selfcheck.py
"""
from __future__ import print_function

import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BP = os.path.join(ROOT, "behavior_pack_chesttransporter")
RP = os.path.join(ROOT, "resource_pack_chesttransporter")

IS_PY2 = sys.version_info[0] < 3
CHILD = os.environ.get("CT_CHECK_CHILD") == "1"

# 模组脚本是 Python 2.7 语法（print 语句、except X, e），py3 编译必然误报，
# 所以 py3 下换 py -2.7 重跑一遍。
if not IS_PY2 and not CHILD:
    try:
        env = dict(os.environ)
        env["CT_CHECK_CHILD"] = "1"
        sys.exit(subprocess.call(["py", "-2.7", os.path.abspath(__file__)], env=env))
    except OSError:
        pass

SKIP_SYNTAX = (not IS_PY2) and (not CHILD)
errors = []


def read_json(path):
    with open(path, "rb") as f:
        return json.loads(f.read().decode("utf-8"))


def walk(root, ext):
    hits = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames
                       if d not in (".git", "__pycache__", "dist", "docs", "tools")]
        for name in filenames:
            if name.endswith(ext):
                hits.append(os.path.join(dirpath, name))
    return hits


def main():
    print("--- JSON ---")
    data = {}
    paths = walk(BP, ".json") + walk(RP, ".json")
    for p in paths:
        try:
            data[p] = read_json(p)
        except Exception as exc:
            errors.append("JSON 解析失败 %s : %s" % (os.path.basename(p), exc))
    print("  解析 %d / %d 个文件" % (len(data), len(paths)))

    print("--- Python 2.7 语法 ---")
    py_paths = walk(BP, ".py")
    if SKIP_SYNTAX:
        print("  跳过（当前 py3 且找不到 py -2.7）")
    else:
        ok = 0
        for p in py_paths:
            try:
                with open(p, "rb") as f:
                    src = f.read()
                compile(src, "selfcheck.py", "exec", 0, True)
                ok += 1
            except SyntaxError as exc:
                errors.append("语法错误 %s 第 %s 行: %s"
                              % (os.path.basename(p), exc.lineno, exc.msg))
        print("  通过 %d / %d 个脚本" % (ok, len(py_paths)))

    print("--- 物品 / 外观 / 贴图 ---")
    beh, res, tex = {}, {}, {}
    for p, d in data.items():
        if os.path.basename(p) == "item_texture.json":
            tex = d.get("texture_data") or {}
            continue
        folder = os.path.basename(os.path.dirname(p))
        body = d.get("minecraft:item") or {}
        ident = (body.get("description") or {}).get("identifier")
        if not ident:
            continue
        if folder == "netease_items_beh":
            beh[ident] = body
        elif folder == "netease_items_res":
            res[ident] = body

    for ident, body in beh.items():
        comps = body.get("components") or {}
        desc = body.get("description") or {}
        icon = comps.get("minecraft:icon")
        if not icon:
            errors.append("物品缺少 icon: %s" % ident)
        elif icon not in tex:
            errors.append("icon 未在 item_texture.json 中定义: %s" % ident)
        if "minecraft:max_damage" not in comps:
            errors.append("物品缺少 max_damage: %s" % ident)
        if not ident.endswith("_full"):
            if desc.get("register_to_create_menu") is not True:
                errors.append("物品缺少 register_to_create_menu: %s" % ident)
        if ident not in res:
            errors.append("资源包缺少外观定义: %s" % ident)
    for ident in res:
        if ident not in beh:
            errors.append("资源包有多余外观: %s" % ident)

    for key, entry in tex.items():
        path = entry.get("textures")
        if not path:
            errors.append("贴图键为空: %s" % key)
        elif not os.path.isfile(os.path.join(RP, path + ".png")):
            errors.append("缺少贴图文件: %s -> %s" % (key, path))
    print("  %d 物品 / %d 外观 / %d 贴图键" % (len(beh), len(res), len(tex)))

    print("--- 配方 ---")
    count = 0
    for p, d in data.items():
        if os.path.basename(os.path.dirname(p)) != "netease_recipes":
            continue
        count += 1
        body = (d.get("minecraft:recipe_shaped")
                or d.get("minecraft:recipe_shapeless") or {})
        result = (body.get("result") or {}).get("item")
        if result and result not in beh:
            errors.append("配方产物不是本模组物品: %s" % result)
    print("  %d 个配方" % count)

    print("")
    if errors:
        print("--- 发现 %d 个问题 ---" % len(errors))
        for e in errors:
            print("  " + e)
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
