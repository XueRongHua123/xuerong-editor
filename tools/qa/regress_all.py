# -*- coding: utf-8 -*-
"""通用性冒烟：在多个真实 mod 上跑核心接口，任一 500 / 关键字段缺失即失败。

用法：
    python work/qa/regress_all.py            # 自动发现 mod
    python work/qa/regress_all.py <mod1> ...  # 指定

规矩来源：AGENTS.md「通用性：不为单个 mod 写死」第 5 条。
"""
import io
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.dirname(HERE)
sys.path.insert(0, WORK)
import focus_editor as fe


def discover():
    """自动发现可测 mod：map_sources + Steam workshop 目录 + fixtures"""
    roots = []
    try:
        for s in fe.map_sources():
            p = s.get("root") or s.get("path")
            if p and os.path.isdir(p) and p not in roots:
                roots.append(p)
    except Exception:
        pass
    ws = r"E:\SteamLibrary\steamapps\workshop\content\394360"
    if os.path.isdir(ws):
        for name in sorted(os.listdir(ws))[:6]:
            p = os.path.join(ws, name)
            if os.path.isdir(p) and p not in roots:
                roots.append(p)
    fx = os.path.join(WORK, "qa", "fixtures", "country_mod")
    if os.path.isdir(fx):
        roots.append(fx)
    return roots


def is_content_mod(root):
    """有 map 或 common/countries 才算是完整 mod；纯资源包/子 mod 不适用本冒烟"""
    for sub in (os.path.join("map", "provinces.bmp"),):
        if os.path.exists(os.path.join(root, sub)):
            return True
    for sub in ("common/countries", "common/country_tags", "history/states"):
        if os.path.isdir(os.path.join(root, sub)):
            return True
    return False


def probe(root):
    """返回 (ok, 详情 dict, 错误)"""
    info = {}
    t0 = time.time()
    try:
        # 1) mod 元信息
        meta = fe.mod_meta(root) if hasattr(fe, "mod_meta") else {}
        info["name"] = (meta.get("name") or os.path.basename(root.rstrip("\\/"))) if isinstance(meta, dict) else os.path.basename(root.rstrip("\\/"))
        # 2) 国家
        fe.COUNTRIES.clear()
        fe.load_countries(root)
        info["countries"] = len(fe.COUNTRIES)
        # 3) 州
        fe.STATES.clear()
        fe.load_states(root)
        info["states"] = len(fe.STATES)
        # 4) 地图元信息
        mm = fe.map_meta(root)
        info["map_ok"] = bool(mm.get("ok"))
        info["map_built"] = bool(mm.get("built"))
        info["map_stale"] = bool(mm.get("stale"))
        info["map_src"] = os.path.basename((mm.get("source") or "").rstrip("\\/"))
        # 5) 图层缓存已建时，跑一次完整性检查（不重建）
        if mm.get("built"):
            t1 = time.time()
            integ = fe.map_integrity(root)
            info["integrity_ok"] = bool(integ.get("ok"))
            info["integrity_ms"] = int((time.time() - t1) * 1000)
            info["integrity_stats"] = integ.get("stats") or {}
        # 6) 开局日期
        try:
            info["start"] = fe._start_date_for(root)
        except Exception:
            info["start"] = "?"
    except Exception as e:
        return False, info, "%s: %s" % (type(e).__name__, e)
    info["ms"] = int((time.time() - t0) * 1000)
    if not is_content_mod(root):
        return True, info, "不适用（资源包/子 mod，无 map 与 common/countries）"
    problems = []
    if not info.get("countries"):
        problems.append("国家数为 0")
    if not info.get("states"):
        problems.append("州数为 0")
    if not info.get("map_ok"):
        problems.append("地图元信息失败")
    return not problems, info, "；".join(problems)


def main():
    roots = sys.argv[1:] or discover()
    if not roots:
        print("没有找到可测 mod")
        return 1
    print("待测 mod：%d 个\n" % len(roots))
    fails = 0
    rows = []
    for r in roots:
        ok, info, err = probe(r)
        rows.append((ok, r, info, err))
        if not ok:
            fails += 1
    width = max(len(os.path.basename(x[1].rstrip("\\/"))) for x in rows)
    print("%-*s %5s %5s %6s %4s %-12s %s" % (width, "mod", "国家", "州", "地图", "缓存", "开局面", "结果"))
    for ok, r, info, err in rows:
        name = os.path.basename(r.rstrip("\\/"))[:width]
        print("%-*s %5s %5s %6s %4s %-12s %s" % (
            width, name, info.get("countries", "-"), info.get("states", "-"),
            "ok" if info.get("map_ok") else "FAIL",
            "有" if info.get("map_built") else ("过期" if info.get("map_stale") else "无"),
            info.get("start", "-"),
            ("不适用" if err.startswith("不适用") else "通过") if ok else ("失败：" + err)))
    print("\n%d/%d 通过" % (len(rows) - fails, len(rows)))
    return 0 if fails == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
