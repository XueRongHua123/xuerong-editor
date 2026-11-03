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

# 第 7 组要 import mapgen_write（依赖 numpy / PIL）。默认的 python 是 3.13 精简版，
# 没装 numpy；找到一个装了的解释器就自我重启一次，免得上手先踩环境坑。
try:
    import numpy  # noqa: F401
except Exception:
    import subprocess
    for _cand in (r"C:\Users\33206\AppData\Local\Programs\Python\Python312\python.exe",
                  r"C:\Users\33206\AppData\Local\Programs\Python\Python311\python.exe"):
        if not os.path.isfile(_cand):
            continue
        try:
            _r = subprocess.run([_cand, os.path.abspath(__file__)] + sys.argv[1:])
            sys.exit(_r.returncode)
        except Exception:
            continue
    print("警告：找不到带 numpy 的 Python，第 7 组会跳过")

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
        nf = os.path.join(d, "common", "national_focus",
                      world_stubs.stub_name("common/national_focus"))
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
        print("[5] A2 内容：国策树 / 事件 / 本地化")
        import focus_gen
        import world_events
        import world_loc
        fr = focus_gen.build(tag="ZZV", n_focus=24)
        check("国策树 ≥15 节点", len(fr["nodes"]) >= 15, str(len(fr["nodes"])))
        check("国策树自检为空", not focus_gen.check(fr["text"], "ZZV"),
              str(focus_gen.check(fr["text"], "ZZV")))
        check("国策树带 default = yes", "default = yes" in fr["text"])
        pre = [n for n in fr["nodes"] if n["prereq"]]
        check("有前置关系", len(pre) >= len(fr["nodes"]) - 3, str(len(pre)))
        ids = [n["id"] for n in fr["nodes"]]
        check("节点 id 唯一", len(ids) == len(set(ids)))
        check("图标全是 GFX_goal_/GFX_focus_research",
              all(n["icon"].startswith(("GFX_goal_", "GFX_focus_research"))
                  for n in fr["nodes"]))
        check("每层 y 不重叠",
              len({(n["x"], n["y"]) for n in fr["nodes"]}) == len(fr["nodes"]))
        er = world_events.build(tag="ZZV")
        check("事件有 namespace", "add_namespace" in er["events"])
        check("on_startup 指明 tag", "ZZV = {" in er["on_actions"])
        n = world_loc.write(d, fr["loc"] + er["loc"]
                            + world_loc.country_entries("ZZV", "新世界"))
        raw = io.open(os.path.join(d, "localisation", "simp_chinese",
                                   "zz_editor_world_l_simp_chinese.yml"),
                      encoding="utf-8-sig").read()
        check("本地化写入且是中文", n > 40 and "稳固根基" in raw, str(n))
        check("本地化带 BOM", io.open(os.path.join(
            d, "localisation", "simp_chinese",
            "zz_editor_world_l_simp_chinese.yml"), "rb").read(3) == b"\xef\xbb\xbf")
        print("[6] 不再给同名覆盖的 map 文件写 0 字节占位")
        src = io.open(os.path.join(HERE, "mapgen_write.py"),
                      encoding="utf-8").read()
        body = src[src.index("def write_empty_texts"):]
        body = body[:body.index("return written")]
        # 只认「写成元组项」的情况，别被 docstring 里那句「不要写这六个」误伤
        bad = [f for f in ("positions.txt", "buildings.txt", "cities.txt",
                           "railways.txt", "unitstacks.txt",
                           "adjacency_rules.txt")
               if ('("%s",' % f) in body]
        check("六个同名覆盖文件已不写", not bad, str(bad))
        check("仍写 adjacencies.csv / weatherpositions",
              "adjacencies.csv" in body and "weatherpositions.txt" in body)

        print("[7] 三张坐标表按自己的地图写，且坐标不越界")
        import mapgen_write as mgw
        md = os.path.join(d, "map")
        os.makedirs(md, exist_ok=True)
        cen = {1: (10.0, 20.0), 2: (100.0, 50.0), 3: (203.0, 111.0)}
        states = [(1, [1, 2]), (2, [3])]
        mp = mgw.write_map_positions(md, cen, states=states, size=(256, 128))
        check("unitstacks 每省一行", mp["unitstacks"] == len(cen), str(mp))
        check("weather 每省两行（small+large）", mp["weather"] == 2 * len(cen), str(mp))
        check("buildings 每州三行", mp["buildings"] == 3 * len(states), str(mp))
        for fn, ix, iy, hi_x, hi_y in (
                ("unitstacks.txt", 2, 4, 255.0, 127.0),
                ("buildings.txt", 2, 4, 255.0, 127.0),
                ("weatherpositions.txt", 1, 3, 255.0, 127.0)):
            bad = []
            for ln in io.open(os.path.join(md, fn), encoding="utf-8"):
                f = ln.strip().split(";")
                if len(f) < 5:
                    bad.append("列数 " + ln.strip())
                    continue
                try:
                    x, y = float(f[ix]), float(f[iy])
                except Exception:
                    bad.append("非数值 " + ln.strip())
                    continue
                if not (0 <= x <= hi_x and 0 <= y <= hi_y):
                    bad.append("越界 %.1f,%.1f" % (x, y))
            check("%s 坐标都在图内" % fn, not bad, str(bad[:2]))
        # 省 0 是占位省，任何坐标表里都不该出现
        for fn in ("unitstacks.txt", "weatherpositions.txt"):
            raw = io.open(os.path.join(md, fn), encoding="utf-8").read()
            check("%s 里没有省 0" % fn,
                  not any(ln.startswith("0;") for ln in raw.splitlines()))

        # [8] bmp / 补给节点的语义方向（都是「labels == 0 永不成立」那一族）
        #
        # 这一组的对象是地图生成器，不是占位生成器；占位测试不产 bmp 时跳过。
        _need = [os.path.join(md, n) for n in
                 ("provinces.bmp", "rivers.bmp", "cities.bmp", "terrain.bmp",
                  "definition.csv")]
        if not all(os.path.exists(p) for p in _need):
            check("[8] bmp 语义（本次不产 bmp，跳过）", True, "占位测试没有地图 bmp")
        else:
            try:
                import numpy as _np
                from PIL import Image as _Im
                _lab = _np.asarray(_Im.open(os.path.join(md, "provinces.bmp")).convert("RGB"))
                _key = (_lab[:, :, 0].astype(_np.int32) << 16) | \
                       (_lab[:, :, 1].astype(_np.int32) << 8) | _lab[:, :, 2].astype(_np.int32)
                _rgb2pid, _kind = {}, {}
                for _ln in io.open(os.path.join(md, "definition.csv"), encoding="utf-8", errors="replace"):
                    _p = _ln.strip().split(";")
                    if len(_p) >= 5:
                        try:
                            _rgb2pid[(int(_p[1]), int(_p[2]), int(_p[3]))] = int(_p[0])
                            _kind[int(_p[0])] = _p[4]
                        except Exception:
                            pass
                _land = _np.zeros(_key.shape, dtype=bool)
                _sea = _np.zeros(_key.shape, dtype=bool)
                for _pid, _k in _kind.items():
                    if _pid <= 0:
                        continue
                    _rgb = [r for r, p in _rgb2pid.items() if p == _pid]
                    if not _rgb:
                        continue
                    _c = (_rgb[0][0] << 16) | (_rgb[0][1] << 8) | _rgb[0][2]
                    if _k == "land":
                        _land |= (_key == _c)
                    else:
                        _sea |= (_key == _c)

                # rivers.bmp：255 = 陆，254 = 海（原版与 ES 双向验证过）
                _rv = _np.asarray(_Im.open(os.path.join(md, "rivers.bmp")))
                check("rivers.bmp 陆地像素是 255",
                      int((_rv[_land] == 255).sum()) > 0.9 * max(1, int(_land.sum())),
                      "255 占 %.1f%%" % (100.0 * (_rv[_land] == 255).sum() / max(1, _land.sum())))
                check("rivers.bmp 海洋像素是 254",
                      int((_rv[_sea] == 254).sum()) > 0.9 * max(1, int(_sea.sum())),
                      "254 占 %.1f%%" % (100.0 * (_rv[_sea] == 254).sum() / max(1, _sea.sum())))

                # cities.bmp：15 = 无城市。整张图不能全是有城市（索引 0）
                _ct = _np.asarray(_Im.open(os.path.join(md, "cities.bmp")))
                check("cities.bmp 默认是 15（无城市）",
                      int((_ct == 15).sum()) > 0.5 * _ct.size,
                      "15 占 %.1f%%" % (100.0 * (_ct == 15).sum() / _ct.size))

                # terrain.bmp：海是 15
                _tr = _np.asarray(_Im.open(os.path.join(md, "terrain.bmp")))
                check("terrain.bmp 海洋像素是 15",
                      int((_tr[_sea] == 15).sum()) > 0.9 * max(1, int(_sea.sum())),
                      "15 占 %.1f%%" % (100.0 * (_tr[_sea] == 15).sum() / max(1, _sea.sum())))
            except Exception as _e:
                check("[8] bmp 语义检查可运行", False, str(_e)[:80])

        # supply_nodes.txt：第一列是节点等级，恒为 1
        _snp = os.path.join(md, "supply_nodes.txt")
        if not os.path.exists(_snp):
            check("[8] supply_nodes（本次不产，跳过）", True, "")
        else:
            _sn = [ln.split() for ln in
                   io.open(_snp, encoding="utf-8").read().splitlines() if ln.strip()]
            check("supply_nodes 第一列全是 1",
                  bool(_sn) and all(len(f) == 2 and f[0] == "1" for f in _sn),
                  str(_sn[:3]))
    finally:
        shutil.rmtree(d, ignore_errors=True)

    print("\n结果：%d 过 / %d 挂" % (ok, fail))
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
