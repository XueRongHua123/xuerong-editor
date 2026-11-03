# -*- coding: utf-8 -*-
"""把 crashes/ 下的崩溃目录整理成一张表：时间、异常首行、当时启了哪些 mod。

用法：
    python qa/_crash_history.py            # 全部
    python qa/_crash_history.py --first 10 # 最早 10 个
"""
import argparse
import io
import os
import re

DOCS = r"C:\Users\33206\Documents\Paradox Interactive\Hearts of Iron IV"
CRASH = os.path.join(DOCS, "crashes")


def read_first(path, needle):
    if not os.path.exists(path):
        return ""
    try:
        for ln in io.open(path, encoding="utf-8", errors="replace"):
            if needle in ln:
                return ln.strip()
    except Exception:
        pass
    return ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--first", type=int, default=0, help="只看最早 N 个")
    ap.add_argument("--out", default="", help="把表格写到文件")
    a = ap.parse_args()
    if not os.path.isdir(CRASH):
        print("没有 crashes 目录")
        return
    dirs = sorted(d for d in os.listdir(CRASH)
                  if os.path.isdir(os.path.join(CRASH, d)))
    print("崩溃目录共 %d 个" % len(dirs))
    if a.first:
        dirs = dirs[:a.first]
    rows = []
    for d in dirs:
        p = os.path.join(CRASH, d)
        exc = read_first(os.path.join(p, "exception.txt"), "Unhandled Exception")
        mods = read_first(os.path.join(p, "meta.yml"), "Mods:")
        ver = read_first(os.path.join(p, "exception.txt"), "Version:")
        rows.append((d, ver, exc[:80], mods[:60]))
    for r in rows:
        print("%-22s %-46s %-46s %s" % r)
    if a.out:
        io.open(a.out, "w", encoding="utf-8", newline="").write(
            "| 崩溃目录 | 版本 | 异常 | 当时 mod |\n|---|---|---|---|\n"
            + "".join("| %s | %s | %s | %s |\n" % r for r in rows))
        print("已写入 " + a.out)


if __name__ == "__main__":
    main()
