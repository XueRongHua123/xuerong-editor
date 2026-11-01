# -*- coding: utf-8 -*-
"""world_stubs 的自检（不需要开游戏，2 秒出结果）。

跑法：
    python qa/_check_world_stubs.py

覆盖 4 组：
  1. REPLACE_DIRS 里没有「不该 replace」的资源目录
  2. write_all 写完之后 check() 零问题
  3. 删掉 default = yes 之后 check() 能报出来（回归 2026-11-02 的崩溃）
  4. 空目录能被报出来；资源类目录里有非 .txt 文件不算空

真机验收见 qa/_hoi4_probe.py（需要启动游戏）。
"""
import io
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import world_stubs  # noqa: E402

FORBIDDEN = ("music", "gfx/flags", "portraits", "gfx/loadingscreens",
             "common/units/equipment", "common/technologies",
             "common/country_tags")

ok = fail = 0


def check(name, cond, detail=""):
    global ok, fail
    if cond:
        ok += 1
        print("  PASS %s" % name)
    else:
        fail += 1
        print("  FAIL %s %s" % (name, detail))


def main():
    d = tempfile.mkdtemp(prefix="stubtest_")
    try:
        print("[1] 清单里没有不该 replace 的目录")
        bad = []
        for sub in world_stubs.REPLACE_DIRS:
            for f in FORBIDDEN:
                if sub == f or sub.startswith(f + "/"):
                    bad.append(sub)
        check("无禁区目录", not bad, str(bad))
        check("目录数 50", len(world_stubs.REPLACE_DIRS) == 50,
              str(len(world_stubs.REPLACE_DIRS)))

        print("[2] 写完占位后自检为零问题")
        world_stubs.write_all(d, "ZZV")
        probs = world_stubs.check(d)
        check("check() 空", not probs, str(probs[:2]))
        nf = os.path.join(d, "common", "national_focus", world_stubs.STUB_NAME)
        raw = io.open(nf, encoding="utf-8").read()
        check("国策树带 default = yes", "default = yes" in raw)
        check("国策树 id 用 tag 参数", "zz_editor_tree" in raw and "ZZV" in raw)

        print("[3] 去掉 default = yes 必须报错（这是崩溃的根因）")
        io.open(nf, "w", encoding="utf-8", newline="").write(
            raw.replace("\tdefault = yes\n", ""))
        probs = world_stubs.check(d)
        hit = [p for p in probs if p["dir"] == "common/national_focus"
               and p["level"] == "error"]
        check("报出 focus_no_default 等价问题", bool(hit), str(probs[:2]))

        print("[4] 目录被删掉要报 error")
        shutil.rmtree(os.path.join(d, "common", "ideas"))
        probs = world_stubs.check(d)
        hit = [p for p in probs if p["dir"] == "common/ideas"
               and p["level"] == "error"]
        check("报出空目录", bool(hit), str(probs[:2]))
    finally:
        shutil.rmtree(d, ignore_errors=True)

    print("\n结果：%d 过 / %d 挂" % (ok, fail))
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
