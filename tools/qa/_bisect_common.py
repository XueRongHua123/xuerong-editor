# -*- coding: utf-8 -*-
"""在「map + history 都不崩」的干净基准上，逐个加 common 目录，找出谁把游戏弄崩。

基准（已实测 ALIVE）：
  replace_path = history/* + map/strategicregions + map/supplyareas
  文件         = map/ 全量 + history/ 全量
本脚本在基准上加若干 common 目录（下标同 _bisect_probe.all_dirs()，6 起是 common）。

用法：
  python qa/_bisect_common.py 6            # 只加 national_focus
  python qa/_bisect_common.py 6-49         # 全加
  python qa/_bisect_common.py 6-49 --drop 6   # 全加但去掉 6
"""
import sys

sys.path.insert(0, r"D:\大肥鱼工作区\HOI4 MUVLUVsub mod 制作\work\qa")
import _bisect_probe as B  # noqa: E402
import _hoi4_probe as P  # noqa: E402

BASE_IDX = [0, 1, 2, 3, 4, 5]
BASE_DIRS = ["map", "history"]


def run(idx, tag, minus=()):
    dirs = B.all_dirs()
    idx = [i for i in idx if i not in minus]
    keeps = [dirs[i] for i in BASE_IDX + idx]
    common = [dirs[i] for i in idx]
    tgt, n, nr, _o, _x = P.build(B.SRC, keeps, [], "zz_probe",
                                 mod_name="探针_" + tag,
                                 file_keep=BASE_DIRS + common)
    P.enable("zz_probe")
    r = P.launch(45, tag)
    print("%-18s %-5s %.0fs files=%d repl=%d" % (
        tag, "ALIVE" if r["alive"] else "DIED", r["secs"], n, nr))
    for ln in r["tail"]:
        print("    log| " + ln)
    return r["alive"]


def parse(specs):
    out = []
    for s in specs:
        if s.startswith("--"):
            continue
        lo, hi = (s.split("-") + [s])[:2]
        out += list(range(int(lo), int(hi) + 1))
    return out


if __name__ == "__main__":
    args = sys.argv[1:]
    minus = []
    if "--drop" in args:
        i = args.index("--drop")
        minus = [int(x) for x in args[i + 1].split(",")]
        args = args[:i] + args[i + 2:]
    idx = parse(args)
    run(idx, "c_%d_%d" % (idx[0], idx[-1]) if idx else "c_none", minus)
