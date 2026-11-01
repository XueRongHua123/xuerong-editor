# -*- coding: utf-8 -*-
"""map/ 目录格式体检。

把「游戏只肯在 error.log 里说的话」提前在本地说完（HOI4 wiki /Map_modding 的硬约束）。
每一项都对应一条真实崩点，不是风格建议。

用法：
    python work/qa/map_diag.py <map目录>
    from map_diag import diagnose; r = diagnose(map_dir)   # r["items"] 逐项结果

结果结构：
    {"ok": bool, "items": [{"id","level","title","detail"}...], "summary": {...}}
level: PASS / WARN / FAIL
"""
import io
import os
import csv
import struct

try:
    import numpy as np
    from PIL import Image
except Exception:                                    # pragma: no cover
    np = None
    Image = None

MAX_PIXELS = 13238272          # wiki: 总像素上限，超过引擎直接拒
LAND_CONTINENT_MIN = 1


# ---------------------------------------------------------------- BMP 读取

def _bmp_info(path):
    """只读头，不解像素。返回 dict 或 None。"""
    try:
        with io.open(path, "rb") as f:
            head = f.read(54)
    except Exception:
        return None
    if len(head) < 54 or head[:2] != b"BM":
        return None
    size, _r1, _r2, off = struct.unpack("<IHHI", head[2:14])
    dib = struct.unpack("<IiiHHIIiiII", head[14:54])
    bmp_bytes = struct.unpack("<I", head[34:38])[0]
    return {"size": size, "offset": off, "dib_size": dib[0],
            "w": dib[1], "h": dib[2], "bpp": dib[4],
            "compression": dib[5], "data_bytes": bmp_bytes,
            "clr_used": dib[9], "file": path}


def _bmp_pixels(path):
    """读像素。24 位返回 (h, w, 3) RGB；8 位返回 (h, w) 索引值。"""
    info = _bmp_info(path)
    if info is None:
        return None
    if Image is not None:
        im = Image.open(path)
        a = np.array(im)
        if info["bpp"] == 8:
            return a.astype(np.uint8)
        if a.ndim == 2:
            return np.stack([a, a, a], axis=2).astype(np.uint8)
        return a[:, :, :3].astype(np.uint8)
    # 兜底：无 Pillow 时手解 24 位
    if info["bpp"] != 24:
        return None
    with io.open(path, "rb") as f:
        f.seek(info["offset"])
        raw = f.read()
    w, h = info["w"], abs(info["h"])
    row = (w * 3 + 3) // 4 * 4
    buf = np.frombuffer(raw[:row * h], dtype=np.uint8).reshape(h, row)[:, :w * 3]
    rgb = buf.reshape(h, w, 3)
    return rgb[::-1] if info["h"] > 0 else rgb


# ---------------------------------------------------------------- 文本解析

def _read_text(path):
    try:
        return io.open(path, "r", encoding="utf-8", errors="replace", newline="").read()
    except Exception:
        return None


def _parse_definition(path):
    """返回 (rows, errors)。rows = [(id, r, g, b, type, coastal, terrain, continent)]"""
    errs = []
    rows = []
    txt = _read_text(path)
    if txt is None:
        return None, ["读不到 definition.csv"]
    if "\r\n" not in txt:
        errs.append("整份文件没有 CRLF 行尾（HOI4 只认 Windows 换行，"
                    "LF 会让每行的 continent 列失效，报 prov N has no continent）")
    for i, line in enumerate(txt.splitlines(), 1):
        s = line.strip().lstrip("\ufeff")
        if not s or s.startswith("#"):
            continue
        cols = s.split(";")
        if len(cols) < 8:
            errs.append("第 %d 行只有 %d 列（要 8 列：id;r;g;b;type;coastal;terrain;continent）"
                        % (i, len(cols)))
            continue
        try:
            rows.append((int(cols[0]), int(cols[1]), int(cols[2]), int(cols[3]),
                         cols[4].strip().lower(), cols[5].strip().lower(),
                         cols[6].strip().lower(), int(cols[7])))
        except Exception:
            errs.append("第 %d 行有非数字字段：%s" % (i, s[:60]))
    return rows, errs


def _parse_continents(path):
    """解析 continent.txt，返回 (names, errors)。只认 `continents = { a b c }`。

    也会认出欧洲那种 `europe = { 1 }` 的错写法并单独报。
    """
    errs = []
    names = []
    txt = _read_text(path)
    if txt is None:
        return None, ["读不到 continent.txt"]
    body = None
    depth = 0
    cur = []
    for ch in txt:
        if ch == "{":
            depth += 1
            if depth == 1:
                cur = []
            continue
        if ch == "}":
            depth -= 1
            if depth == 0:
                body = "".join(cur)
                break
            continue
        if depth >= 1:
            cur.append(ch)
    if body is None:
        return None, ["continent.txt 里找不到最外层 { }"]
    if "=" in body:
        errs.append("continents 块里出现了 `名字 = { ... }` 写法；"
                    "HOI4 要的是纯列表 `continents = { europe asia ... }`，"
                    "ID 按出现顺序从 1 开始")
    for tok in body.replace("\t", " ").replace("\n", " ").split():
        if tok in ("=", "{", "}"):
            continue
        names.append(tok)
    return names, errs


def _parse_regions(map_dir):
    """扫 strategicregions / supplyareas，返回 (prov_in_sr, prov_in_supply)。"""
    sr = set()
    sup = set()
    d = os.path.join(map_dir, "strategicregions")
    if os.path.isdir(d):
        for fn in os.listdir(d):
            if not fn.lower().endswith(".txt"):
                continue
            txt = _read_text(os.path.join(d, fn)) or ""
            i = txt.find("provinces")
            if i < 0:
                continue
            seg = txt[i:]
            b = seg.find("{")
            e = seg.find("}", b)
            for tok in seg[b + 1:e].replace("\n", " ").split():
                if tok.isdigit():
                    sr.add(int(tok))
    d = os.path.join(map_dir, "supplyareas")
    if os.path.isdir(d):
        for fn in os.listdir(d):
            if not fn.lower().endswith(".txt"):
                continue
            txt = _read_text(os.path.join(d, fn)) or ""
            i = txt.find("states")
            if i < 0:
                continue
            seg = txt[i:]
            b = seg.find("{")
            e = seg.find("}", b)
            for tok in seg[b + 1:e].replace("\n", " ").split():
                if tok.isdigit():
                    sup.add(int(tok))
    return sr, sup


# ---------------------------------------------------------------- 主检查

TEXTS = ("positions.txt", "continent.txt", "default.map")


def diagnose(map_dir):
    items = []
    add = lambda i, lv, t, d="": items.append(
        {"id": i, "level": lv, "title": t, "detail": d})

    if not os.path.isdir(map_dir):
        add(0, "FAIL", "map 目录不存在", map_dir)
        return {"ok": False, "items": items, "summary": {"fail": 1, "warn": 0, "pass": 0}}

    # 1 default.map
    dm = os.path.join(map_dir, "default.map")
    txt = _read_text(dm) or ""
    need = ("definitions", "provinces", "positions", "terrain", "rivers",
            "heightmap", "tree_definition", "continent", "adjacencies")
    missing = [k for k in need if (k + " =") not in txt]
    if not txt:
        add(1, "FAIL", "缺 default.map", "文件映射表不存在，游戏会退回原版路径")
    elif missing:
        add(1, "FAIL", "default.map 缺键", "缺：" + ", ".join(missing))
    else:
        add(1, "PASS", "default.map 键齐全")

    # 2 provinces.bmp 尺寸/位深
    pb = os.path.join(map_dir, "provinces.bmp")
    pinfo = _bmp_info(pb) if os.path.isfile(pb) else None
    if pinfo is None:
        add(2, "FAIL", "provinces.bmp 缺失或不是 BMP", pb)
        return {"ok": False, "items": items,
                "summary": {"fail": 1, "warn": 0, "pass": len(items) - 1}}
    w, h = pinfo["w"], abs(pinfo["h"])
    problems = []
    if pinfo["bpp"] != 24:
        problems.append("位深 %d（必须 24，32 位会报 We do not support bitdepth at 32）"
                        % pinfo["bpp"])
    if pinfo["compression"] != 0:
        problems.append("带压缩（compression=%d）" % pinfo["compression"])
    if w % 256 or h % 256:
        problems.append("尺寸 %dx%d 不是 256 的倍数" % (w, h))
    if w * h > MAX_PIXELS:
        problems.append("总像素 %d 超过上限 %d" % (w * h, MAX_PIXELS))
    if problems:
        add(2, "FAIL", "provinces.bmp 头不合规", "；".join(problems))
    else:
        add(2, "PASS", "provinces.bmp 头合规", "%dx%d / 24 位" % (w, h))

    # 3 其它位图位深
    # trees.bmp 原版是 1650x600，本来就不跟地图同尺寸，只查位深
    others = {"heightmap.bmp": (8, 1.0), "terrain.bmp": (8, 1.0),
              "rivers.bmp": (8, 1.0), "cities.bmp": (8, 1.0),
              "trees.bmp": (8, None), "world_normal.bmp": (24, 0.5)}
    bad = []
    missing_bmp = []
    for name, (bpp, scale) in others.items():
        p = os.path.join(map_dir, name)
        if not os.path.isfile(p):
            missing_bmp.append(name)
            continue
        inf = _bmp_info(p)
        if inf is None:
            bad.append("%s 不是 BMP" % name)
            continue
        if inf["bpp"] != bpp:
            bad.append("%s 位深 %d（要 %d）" % (name, inf["bpp"], bpp))
        if scale is None:
            continue
        ew, eh = int(w * scale), int(h * scale)
        if (inf["w"], abs(inf["h"])) != (ew, eh):
            bad.append("%s 尺寸 %dx%d（应与 provinces 同源 %dx%d）"
                       % (name, inf["w"], abs(inf["h"]), ew, eh))
    if missing_bmp:
        add(3, "FAIL", "缺位图", "缺：" + ", ".join(missing_bmp))
    elif bad:
        add(3, "FAIL", "位图位深/尺寸不合规", "；".join(bad))
    else:
        add(3, "PASS", "其余位图位深与尺寸正确")

    # 4 definition.csv
    rows, derr = _parse_definition(os.path.join(map_dir, "definition.csv"))
    if rows is None:
        add(4, "FAIL", "definition.csv 不可读", "；".join(derr))
        rows = []
        derr = []
    else:
        if derr:
            add(4, "FAIL", "definition.csv 格式问题", "；".join(derr[:4]))
        else:
            add(4, "PASS", "definition.csv 列数与行尾正确", "%d 行" % len(rows))

    # 5 省 id 连续
    ids = [r[0] for r in rows]
    if ids:
        gaps = [i for i in range(0, max(ids) + 1) if i not in set(ids)]
        if gaps:
            add(5, "FAIL", "省 id 有缺口",
                "缺口 %d 个，前几个：%s（缺口会让后面所有省属性错位到下一个省）"
                % (len(gaps), gaps[:8]))
        else:
            add(5, "PASS", "省 id 从 0 连续", "0..%d 共 %d 个" % (max(ids), len(ids)))

    # 6 颜色唯一
    cols = {}
    dup = []
    for r in rows:
        if r[0] == 0:
            continue
        key = (r[1], r[2], r[3])
        if key in cols:
            dup.append("%s = 省 %d 与省 %d" % (";".join(map(str, key)), cols[key], r[0]))
        else:
            cols[key] = r[0]
    if dup:
        add(6, "FAIL", "definition 颜色重复", "；".join(dup[:4]))
    else:
        add(6, "PASS", "definition 颜色唯一", "%d 个省" % len(cols))

    # 7 provinces.bmp 逐像素：孤儿色 / 空省
    pix = _bmp_pixels(pb)
    if pix is not None:
        flat = pix.reshape(-1, 3) if pix.ndim == 3 else None
        if flat is not None:
            uniq, counts = np.unique(flat, axis=0, return_counts=True)
            seen = {(int(c[0]), int(c[1]), int(c[2])): int(n)
                    for c, n in zip(uniq, counts)}
            orphan = [c for c in seen if c not in cols and c != (0, 0, 0)]
            if orphan:
                add(7, "FAIL", "provinces.bmp 有 definition 里没有的颜色",
                    "%d 种，前几个 %s（游戏会自动补成 land 省并报 prov N has no continent）"
                    % (len(orphan), orphan[:4]))
            else:
                add(7, "PASS", "provinces.bmp 每个颜色都有 definition 条目")
            empty = [pid for key, pid in cols.items() if seen.get(key, 0) == 0]
            if empty:
                add(8, "FAIL", "definition 里有的省在图上没有像素",
                    "%d 个，前几个 %s（报 Province X has no pixels）"
                    % (len(empty), empty[:6]))
            else:
                add(8, "PASS", "definition 每个省都有像素")
            # 海省存在性
            sea_n = sum(1 for r in rows if r[4] == "sea")
            black = seen.get((0, 0, 0), 0)
            if sea_n == 0 and black:
                add(9, "FAIL", "没有 sea 省，但图上有 %d 个黑色像素" % black,
                    "provinces.bmp 的 (0,0,0) 不是省 0，而是一个没定义的颜色；"
                    "游戏会把它补成 land 省，海变成陆地")
            elif sea_n == 0:
                add(9, "FAIL", "没有任何 sea 省", "海必须先成省，否则海军/港口无法工作")
            else:
                add(9, "PASS", "海省存在", "%d 个 sea 省" % sea_n)

    # 10 大洲
    cnames, cerr = _parse_continents(os.path.join(map_dir, "continent.txt"))
    n_cont = len(cnames or [])
    if cnames is None:
        add(10, "FAIL", "continent.txt 不可读", "；".join(cerr))
        cnames, n_cont = [], 0
    elif cerr:
        add(10, "FAIL", "continent.txt 写法不合规", "；".join(cerr))
    else:
        add(10, "PASS", "continent.txt 格式正确", "%d 个洲：%s" % (n_cont, ", ".join(cnames[:8])))

    zero = [r[0] for r in rows
            if r[0] != 0 and r[4] != "sea" and r[7] < LAND_CONTINENT_MIN]
    over = [r[0] for r in rows if r[7] > n_cont]
    if zero:
        add(11, "FAIL", "陆省大洲为 0",
            "%d 个，前几个 %s（error.log 报 prov N has no continent，MAP_ERROR 会直接拦加载）"
            % (len(zero), zero[:6]))
    elif over:
        add(11, "FAIL", "陆省大洲超出 continent.txt 的洲数",
            "%d 个，前几个 %s（只有 %d 个洲）" % (len(over), over[:6], n_cont))
    else:
        add(11, "PASS", "陆省大洲都在 1..%d" % n_cont)

    # 12 战略区覆盖
    sr, _sup = _parse_regions(map_dir)
    land_ids = [r[0] for r in rows if r[4] != "sea" and r[0] != 0]
    uncovered = [i for i in land_ids if i not in sr]
    if uncovered:
        add(12, "FAIL", "有省不在任何战略区",
            "%d 个，前几个 %s（province 没有战略区会让游戏崩）"
            % (len(uncovered), uncovered[:6]))
    else:
        add(12, "PASS", "所有陆省都归属了战略区", "%d 个省" % len(land_ids))

    fails = [i for i in items if i["level"] == "FAIL"]
    warns = [i for i in items if i["level"] == "WARN"]
    return {"ok": not fails, "items": items,
            "summary": {"fail": len(fails), "warn": len(warns),
                        "pass": len(items) - len(fails) - len(warns)}}


def format_report(r):
    lines = []
    for it in r["items"]:
        mark = {"PASS": "PASS", "WARN": "WARN", "FAIL": "FAIL"}[it["level"]]
        lines.append("[%s] %s%s" % (mark, it["title"],
                                    ("  — " + it["detail"]) if it.get("detail") else ""))
    s = r["summary"]
    lines.append("")
    lines.append("合计：FAIL %d / WARN %d / PASS %d" % (s["fail"], s["warn"], s["pass"]))
    lines.append("结论：%s" % ("可以进游戏" if r["ok"] else "会被 MAP_ERROR 拦住"))
    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    d = sys.argv[1] if len(sys.argv) > 1 else "map"
    rep = diagnose(d)
    print(format_report(rep))
    sys.exit(0 if rep["ok"] else 1)
