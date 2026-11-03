# -*- coding: utf-8 -*-
"""成对二分 history/：每轮从干净产物重建 mod、删掉指定的几类、走一遍真实点击。

为什么必须「成对」
------------------
`map/` 与 `history/` 强耦合：只换 map 会崩（原版 history 引用 1..13413 号省），
只删 map 会卡在 `4489 defines loaded`（我们的 state 引用的省号在原版里对不上）。
所以变量只能放在 history/ 内部，且每轮都要把 map/ 一起带上。

用法
----
    python qa/_bisect_history.py --drop history/units
    python qa/_bisect_history.py --drop history/units,history/countries

判定沿用 `_game_run.py`：GAME_OK / DIED / STUCK，DIED 会打印崩溃目录与异常首行。
"""
import argparse
import io
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _hoi4_probe as P          # noqa: E402
import _game_run as G            # noqa: E402

SRC = r"D:\大肥鱼工作区\HOI4 MUVLUVsub mod 制作\work\tmp\_a3"
NAME = "xuerong_world"
# 真实点击链：单人游戏 → 开始游戏 → 选择剧本。坐标是 1536x960 窗口下的物理像素。
CLICKS = "950,345;950,480;1109,889"


def deploy(drop=()):
    """从 src 重新生成 mod，删掉 drop 里的目录并同步删 replace_path。"""
    tgt = os.path.join(P.MODDIR, NAME)
    if os.path.isdir(tgt):
        shutil.rmtree(tgt)
    tgt, n, nr, _out, _other = P.build(SRC, [], [], NAME, mod_name="雪绒新世界")
    removed = []
    for sub in drop:
        d = os.path.join(tgt, sub.replace("/", os.sep))
        if os.path.isdir(d):
            shutil.rmtree(d)
            removed.append(sub)
    # 同步删掉 .mod / descriptor 里的 replace_path（否则变成「replace 一个不存在的目录」）
    for fn in (NAME + ".mod", os.path.join(NAME, "descriptor.mod")):
        p = os.path.join(P.MODDIR, fn)
        if not os.path.exists(p):
            continue
        lines = io.open(p, encoding="utf-8-sig").read().splitlines()
        keep = [ln for ln in lines
                if not any(ln.strip() == 'replace_path="%s"' % sub for sub in drop)]
        io.open(p, "w", encoding="utf-8", newline="").write("\n".join(keep) + "\n")
    P.enable(NAME)
    return tgt, n, nr, removed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--drop", default="", help="逗号分隔，如 history/units,history/countries")
    ap.add_argument("--tag", default="bisect")
    ap.add_argument("--settle", type=float, default=20)
    a = ap.parse_args()
    drop = [x.strip() for x in a.drop.split(",") if x.strip()]

    tgt, n, nr, removed = deploy(drop)
    print("部署：%d 文件 / %d 条 replace；已删 %s" % (n, nr, removed or "无"))
    os.environ["GAME_RUN_CLICKS"] = CLICKS

    sys.argv = ["_game_run.py", "--tag", a.tag, "--clicks", CLICKS,
                "--click-gap", "6", "--settle", str(a.settle)]
    G.main()


if __name__ == "__main__":
    main()
