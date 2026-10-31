# -*- coding: utf-8 -*-
"""打包发布用的 ZIP。

自动剔除：
  - 调试桥脚本 dbgConfig.py
  - .pyc / __pycache__
  - .mcs/editorSave.json（编辑器状态）
  - dist/、tools/、docs/、README.md、.gitignore

用法：
    python tools/pack.py
输出：
    dist/ChestTransporter.zip
"""
import os
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "dist")
OUT = os.path.join(OUT_DIR, "ChestTransporter.zip")

EXCLUDE_DIRS = {".git", "__pycache__", "dist", "tools", "docs"}
EXCLUDE_FILES = {"dbgConfig.py", "README.md", ".gitignore", "editorSave.json"}
EXCLUDE_EXT = (".pyc", ".pyo", ".zip")


def main():
    if os.path.isfile(OUT):
        os.remove(OUT)
    if not os.path.isdir(OUT_DIR):
        os.makedirs(OUT_DIR)

    count = 0
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        for dirpath, dirnames, filenames in os.walk(ROOT):
            dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
            rel_dir = os.path.relpath(dirpath, ROOT)
            for name in filenames:
                if name in EXCLUDE_FILES or name.endswith(EXCLUDE_EXT):
                    continue
                full = os.path.join(dirpath, name)
                rel = name if rel_dir == "." else os.path.join(rel_dir, name)
                z.write(full, rel.replace(os.sep, "/"))
                count += 1

    print("输出: %s" % OUT)
    print("文件: %d" % count)
    print("大小: %d 字节" % os.path.getsize(OUT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
