# -*- coding: utf-8 -*-
"""按「放开某些 replace_path」快速生成一个实验变体 mod。

为什么要这个工具
----------------
50 条 replace_path 里哪一条导致进游戏崩溃，只能一条条试。
手工复制目录 + 改 descriptor 很容易出错（重名、重复 path、残留占位文件），
前几轮就栽在这上面两次。这里把三件事固定下来：

1. 复制源 mod（默认 xuerong_world）
2. 从 descriptor 里删掉指定的 replace_path
3. 删掉对应目录里的空占位文件（否则「放开了原版」但还是读我们的空目录）
4. 显示名加唯一后缀写 .mod —— 重名会让两个 mod 都不加载

用法：
    python qa/_mkvariant.py --name zz_bs1 --release common/ideas,common/bop
"""
import argparse
import io
import os
import shutil
import sys

MODDIR = r"C:\Users\33206\Documents\Paradox Interactive\Hearts of Iron IV\mod"


def build(src_name, name, release, title=None):
    src = os.path.join(MODDIR, src_name)
    dst = os.path.join(MODDIR, name)
    if not os.path.isdir(src):
        raise SystemExit("源 mod 不存在：%s" % src)
    if os.path.isdir(dst):
        shutil.rmtree(dst)
    shutil.copytree(src, dst)

    p = os.path.join(dst, "descriptor.mod")
    lines = io.open(p, encoding="utf-8").read().splitlines()
    kept, dropped = [], []
    for ln in lines:
        if ln.startswith("replace_path="):
            v = ln.split('"')[1]
            if v in release:
                dropped.append(v)
                continue
        if ln.startswith("path="):
            continue                      # 目录内 descriptor 不写 path
        kept.append(ln)

    disp = title or ("实验_" + name)
    kept = [ln.replace('name="雪绒新世界"', 'name="%s"' % disp) for ln in kept]
    # 名字行没匹配到就补一行，保证显示名唯一
    if not any(ln.startswith("name=") for ln in kept):
        kept.insert(0, 'name="%s"' % disp)
    else:
        kept = ['name="%s"' % disp if ln.startswith("name=") else ln for ln in kept]
    text = "\n".join(kept) + "\n"
    io.open(p, "w", encoding="utf-8", newline="").write(text)
    io.open(os.path.join(MODDIR, name + ".mod"), "w",
            encoding="utf-8", newline="").write(text + 'path="mod/%s"\n' % name)

    for sub in dropped:
        d = os.path.join(dst, sub.replace("/", os.sep))
        if not os.path.isdir(d):
            continue
        for fn in os.listdir(d):
            fp = os.path.join(d, fn)
            if os.path.isfile(fp):
                os.remove(fp)
        try:
            os.rmdir(d)                   # 只删空目录；有子目录就留着
        except OSError:
            pass
    return {"dir": dst, "dropped": dropped,
            "replace_left": sum(1 for x in kept if x.startswith("replace_path="))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="xuerong_world")
    ap.add_argument("--name", required=True)
    ap.add_argument("--release", default="", help="逗号分隔的目录名")
    ap.add_argument("--title", default=None)
    a = ap.parse_args()
    rel = [x.strip() for x in a.release.split(",") if x.strip()]
    r = build(a.src, a.name, rel, a.title)
    print("生成 %s：放开 %d 条，剩 %d 条 replace"
          % (r["dir"], len(r["dropped"]), r["replace_left"]))
    if len(r["dropped"]) != len(rel):
        miss = [x for x in rel if x not in r["dropped"]]
        print("注意：这些没在 descriptor 里找到：%s" % ", ".join(miss))
    return 0


if __name__ == "__main__":
    sys.exit(main())
