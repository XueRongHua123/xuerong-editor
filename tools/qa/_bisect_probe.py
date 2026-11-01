# -*- coding: utf-8 -*-
"""真机二分的跑批器：给一组目录下标，装 mod、启动、报 ALIVE/DIED。

下标基于「源 mod 的 replace_path 顺序」，加上前 6 个固定项：
  0 history/countries  1 history/states  2 history/units  3 history/general
  4 map/strategicregions  5 map/supplyareas   6+ 源 descriptor 里的 common/* 顺序

用法：
  python qa/_bisect_probe.py 6-16 17-27      # 两组，各跑一次
  python qa/_bisect_probe.py 6 --drop map,history

默认 --only-common：始终丢掉 map 与 history，把变量收敛到 common 占位。
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _hoi4_probe as P  # noqa: E402

SRC = r"D:\大肥鱼工作区\HOI4 MUVLUVsub mod 制作\work\tmp\_world5"
FIXED = ["history/countries", "history/states", "history/units", "history/general",
         "map/strategicregions", "map/supplyareas"]


def all_dirs():
    body = io.open(os.path.join(SRC, "descriptor.mod"), encoding="utf-8").read()
    return [l.split('"')[1] for l in body.splitlines()
                    if l.startswith("replace_path")]


def run(idx, tag, drops=("map", "history"), timeout=45):
    dirs = all_dirs()
    keeps = [dirs[i] for i in idx]
    tgt, n, nr, _out, _other = P.build(SRC, keeps, list(drops), "zz_probe",
                                       mod_name="探针_" + tag)
    P.enable("zz_probe")
    r = P.launch(timeout, tag)
    print("%-20s %-5s %.0fs  keep=%d repl=%d  %s" % (
        tag, "ALIVE" if r["alive"] else "DIED", r["secs"], len(keeps), nr,
        ",".join(keeps)[:100]))
    for ln in r["tail"]:
        print("    log| " + ln)
    return r["alive"]


def main():
    specs = [a for a in sys.argv[1:] if not a.startswith("--")]
    drops = ("map", "history")
    if "--with-map" in sys.argv:
        drops = ("history",)
    for spec in specs:
        lo, hi = (spec.split("-") + [spec])[:2]
        idx = list(range(int(lo), int(hi) + 1))
        run(idx, "i%d_%d" % (int(lo), int(hi)), drops)


if __name__ == "__main__":
    main()
