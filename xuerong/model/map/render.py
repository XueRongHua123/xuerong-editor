# -*- coding: utf-8 -*-
"""渲染与生成：主渲染（map_build）、地形底图、山体阴影贴图、新地图生成。"""
import io
import json
import os
import re
import time
import zlib

from xuerong import state
from xuerong.core import paths
from xuerong.core.paths import _layers_find, mod_layers, qa_dir as _qa_dir
from xuerong.core.text import _first, brace_match, strip_comments
from xuerong.model.map._inj import load_units
from xuerong.model.map.io import (_map_dir, _map_files_strict, _map_pick,
                                 _prov_type_map, map_sources)
from xuerong.model.map.river import _build_rivers_png
from xuerong.model.map.terrain import _terrain_tex_map


def map_generate(source="procedural", out_dir=None, width=1200, height=440,
                 n_provinces=180, min_size=300, seed=11, src_path=None,
                 sea_level=0.42, balance=True, min_province_px=800,
                 n_regions=None, n_supply=None, bbox=None, rivers_path=None,
                 cities_path=None, city_radius=4):
    """调用 qa/mapgen.py 生成完整 map/ 目录。"""
    try:
        import sys as _sys
        _qa = _qa_dir()
        if _qa not in _sys.path:
            _sys.path.insert(0, _qa)
        import mapgen
    except Exception as e:
        return {"ok": False, "msg": "地图生成器不可用：%s" % e}
    if not out_dir:
        out_dir = os.path.join(paths.app_dir(), "tmp",
                               "_gen_%d" % int(__import__("time").time()))
    try:
        r = mapgen.generate(source, out_dir, int(width), int(height),
                            int(n_provinces), int(min_size), int(seed),
                            src_path, float(sea_level),
                            template_map=os.path.join(state.game(), "map") if state.game() else None,
                            balance=bool(balance),
                            min_province_px=int(min_province_px),
                            n_regions=n_regions, n_supply=n_supply,
                            bbox=bbox, rivers_path=rivers_path,
                            cities_path=cities_path, city_radius=int(city_radius))
        return r
    except Exception as e:
        import traceback
        return {"ok": False, "msg": "生成失败：%s" % e,
                "trace": traceback.format_exc()[-800:]}

def _hsv_hex(i, sat=0.52, val=0.88):
    """6 色循环 + 按 id 的轻微明度扰动：相邻省不撞色，整体也不花"""
    i = int(i)
    base = state.map_var("MAP_PALETTE")[i % len(state.map_var("MAP_PALETTE"))]
    d = ((i * 37) % 44) - 22
    return bytes(max(10, min(246, c + d)) for c in base)


# ---------------- 跨层钩子：构建进度上报 ----------------
# model 层不 import 门面，由门面在启动期注入 _lp / _lp_begin / _lp_done / _lp_fail。
_PROGRESS = {"fn": None, "begin": None, "done": None, "fail": None}


def set_progress_hook(fn, begin=None, done=None, fail=None):
    """门面启动期注入地图构建进度钩子；model 层不 import 门面。"""
    _PROGRESS["fn"] = fn
    _PROGRESS["begin"] = begin
    _PROGRESS["done"] = done
    _PROGRESS["fail"] = fail


def _tick(stage, sub="", pct=0):
    fn = _PROGRESS.get("fn")
    if fn:
        try:
            fn(stage, sub, pct)
        except Exception:
            pass


def map_build(force=False, root=None):
    """生成地图图层（首次约 13 秒），返回 meta。可按 root 指定来源。"""
    root = _map_pick(root)
    if not root:
        return {"ok": False, "msg": "还没有加载任何 mod"}
    bmp, csv, base = _map_files_strict(root)
    if not bmp:
        return {"ok": False, "msg": "这个来源没有 map/provinces.bmp 或 definition.csv",
                "sources": map_sources(), "picked": root}
    dirp, key, base = _map_dir(root)
    if not dirp:
        return {"ok": False, "msg": "无法创建缓存目录"}
    os.makedirs(dirp, exist_ok=True)
    meta_path = os.path.join(dirp, "meta.json")
    try:
        os.makedirs(state.map_var("MAP_CACHE_DIR"), exist_ok=True)
        io.open(os.path.join(state.map_var("MAP_CACHE_DIR"), "_last.json"), "w", encoding="utf-8", newline="").write(
            json.dumps({"root": os.path.abspath(base or ""), "key": key,
                        "built": time.strftime("%Y-%m-%d %H:%M:%S")}, ensure_ascii=False))
    except Exception:
        pass
    if not force and os.path.exists(meta_path):
        try:
            return {"ok": True, "cached": True,
                    "meta": json.loads(io.open(meta_path, encoding="utf-8").read())}
        except Exception:
            pass

    _beg = _PROGRESS.get("begin")
    if _beg:
        try:
            _beg("map")
        except Exception:
            pass
    _ok = False
    try:
        res = _map_build_run(root, dirp, base, bmp, csv, meta_path)
        _ok = True
        return res
    except Exception as _err:
        _fail = _PROGRESS.get("fail")
        if _fail:
            try:
                _fail(_err)
            except Exception:
                pass
        raise
    finally:
        if _ok:
            _done = _PROGRESS.get("done")
            if _done:
                try:
                    _done()
                except Exception:
                    pass


def _map_build_run(root, dirp, base, bmp, csv, meta_path):
    """map_build 的实际执行体，按 14 个阶段上报进度。"""
    from PIL import Image, ImageDraw
    Image.MAX_IMAGE_PIXELS = None
    t_all = time.time()

    # 1) definition.csv：颜色 -> 省 id
    _tick("读取省份定义", "", 5)
    color2prov = {}
    prov2type = {}
    prov2terrain = {}
    prov2continent = {}
    with io.open(csv, encoding="utf-8", errors="replace") as f:
        for line in f:
            parts = line.strip().split(";")
            if len(parts) < 5:
                continue
            try:
                pid = int(parts[0])
                rgb = (int(parts[1]), int(parts[2]), int(parts[3]))
            except Exception:
                continue
            color2prov[rgb] = pid
            prov2type[pid] = parts[4] or "land"
            if len(parts) > 6:
                prov2terrain[pid] = (parts[6] or "").strip()
            if len(parts) > 7:
                try:
                    prov2continent[pid] = int(parts[7])
                except Exception:
                    pass

    # 2) 读图
    _tick("读取省份底图", "", 10)
    im = Image.open(bmp).convert("RGB")
    w, h = im.size
    raw = im.tobytes()

    # 3) 省 -> 州
    _tick("读取州与国家", "", 14)
    prov2state = {}
    for sid, st in state.states().items():
        try:
            sid_int = int(st.get("id") or sid)
        except Exception:
            continue
        for p in (st.get("provinces") or []):
            try:
                prov2state[int(p)] = sid_int
            except Exception:
                pass

    # 3.5) 政治视图：省 -> owner -> 国家颜色
    prov2owner = {}
    for sid, st in state.states().items():
        ow = (st.get("owner") or "").strip()
        if not ow:
            continue
        for p in (st.get("provinces") or []):
            try:
                prov2owner[int(p)] = ow
            except Exception:
                pass
    tag_color = {}
    tag_color_real = {}
    for tag, c in state.countries().items():
        col = c.get("color") or []
        if len(col) >= 3:
            _c = bytes((max(0, min(255, int(col[0] * 255))),
                        max(0, min(255, int(col[1] * 255))),
                        max(0, min(255, int(col[2] * 255)))))
            tag_color[tag] = _c
            tag_color_real[tag] = _c
        else:
            tag_color[tag] = bytes((132, 132, 132))
    neutral = bytes((46, 50, 46))
    oceanc = bytes((26, 42, 74))          # 海色：比无主陆地明显的蓝
    ptypes = _prov_type_map(root)

    # 3.6) 战略区
    _tick("读取战略区与地形", "", 18)
    prov2region, region_list = _strategic_regions(root)

    # 3.7) 地形：用游戏自己的配色，再叠 terrain.bmp 的明暗做出纹理感
    _tcols = {}
    try:
        _tcols = _terrain_colors(root)
    except Exception as _e:
        print("读地形配色失败:", _e)
    # 旧的「terrain.bmp 灰度明暗」已弃用：现在统一用 heightmap 的真实山体阴影
    # （_apply_hillshade）。两套叠一起会把颜色压暗一倍。
    _shade = None

    # 4) 一遍像素：ids、质心累加
    n = w * h
    _tick("准备像素缓冲", "%dx%d" % (w, h), 20)
    ids = [0] * n
    sumx = {}
    sumy = {}
    cnts = {}
    lookup = color2prov
    unset_px = 0          # 颜色在 definition.csv 里找不到的像素
    _step1 = max(1, n // 40)
    _next1 = _step1
    _dim = "%dx%d" % (w, h)
    for i in range(n):
        if i >= _next1:
            _tick("扫描省份像素", _dim, 22 + int(20 * i / n))
            _next1 += _step1
        o = i * 3
        pid = lookup.get((raw[o], raw[o + 1], raw[o + 2]))
        if pid is None:
            pid = 0
            unset_px += 1
        ids[i] = pid
        if pid:
            sumx[pid] = sumx.get(pid, 0) + (i % w)
            sumy[pid] = sumy.get(pid, 0) + (i // w)
            cnts[pid] = cnts.get(pid, 0) + 1

    # 4.5) 地图定义一致性（definition.csv ↔ provinces.bmp）
    try:
        state.map_var("PROV_RGB").clear()
        for _rgb, _pid in color2prov.items():
            state.map_var("PROV_RGB")[int(_pid)] = _rgb
    except Exception:
        pass
    csv_ids = set(color2prov.values())
    bmp_ids = set(cnts)
    ghost = sorted(csv_ids - bmp_ids)          # 定义了但地图上没有像素
    # 同色多个省（后写覆盖前写，前面的 id 永远不会出现）
    rgb_count = {}
    for _rgb, _pid in color2prov.items():
        rgb_count.setdefault(_rgb, []).append(_pid)
    dup_rgb = {k: v for k, v in rgb_count.items() if len(v) > 1}
    consistency = {
        "csv_ids": len(csv_ids),
        "bmp_ids": len(bmp_ids),
        "ghost": len(ghost),
        "ghost_sample": ghost[:20],
        "unset_pixels": unset_px,
        "unset_ratio": round(unset_px * 100.0 / max(1, n), 3),
        "dup_rgb": len(dup_rgb),
        "dup_rgb_sample": [{"rgb": list(k), "ids": v[:5]} for k, v in list(dup_rgb.items())[:10]],
    }

    # 5) 图层缓冲
    provbuf = bytearray(n * 3)
    statebuf = bytearray(n * 3)
    polbuf = bytearray(n * 3)
    regbuf = bytearray(n * 3)
    terrbuf = bytearray(n * 3)
    contbuf = bytearray(n * 3)
    edgebuf = bytearray(n * 3)
    idbuf = bytearray(n * 3)
    prov_color = {}
    state_color = {}
    reg_color = {}
    terr_color = {}
    cont_color = {}
    _step2 = max(1, n // 40)
    _next2 = _step2
    for i in range(n):
        if i >= _next2:
            _tick("生成图层像素", _dim, 42 + int(20 * i / n))
            _next2 += _step2
        pid = ids[i]
        c = prov_color.get(pid)
        if c is None:
            c = _hsv_hex(pid, 0.72, 0.96) if pid else bytes((24, 28, 26))
            prov_color[pid] = c
        sid = prov2state.get(pid, 0)
        sc = state_color.get(sid)
        if sc is None:
            sc = _hsv_hex(sid + 7, 0.62, 0.92) if sid else bytes((30, 34, 32))
            state_color[sid] = sc
        o = i * 3
        provbuf[o:o + 3] = c
        statebuf[o:o + 3] = sc
        ow = prov2owner.get(pid, "")
        if ow:
            pcb = tag_color.get(ow)
            if pcb is None:
                # 国家表里没有这个 tag（mod 改了国家但州还引用旧 tag），
                # 按 tag 生成稳定色，而不是画成无主灰
                pcb = _tag_fallback_color(ow)
                tag_color[ow] = pcb
        else:
            # 没有归属国的省分两种：海洋给海色，无主陆地给中性灰
            ptype = ptypes.get(pid, "")
            pcb = oceanc if ptype in ("sea", "ocean", "lake") else neutral
        polbuf[o:o + 3] = pcb
        # 地形：按 definition.csv 的 terrain 名字取稳定色
        tname = prov2terrain.get(pid, "")
        tc = terr_color.get(tname)
        if tc is None:
            _base = _tcols.get(tname)
            if _base:
                tc = bytes(_base)
            elif tname:
                tc = _hsv_hex(zlib.crc32(tname.encode("utf-8")) % 997, 0.35, 0.72)
            else:
                tc = bytes((26, 30, 28))
            terr_color[tname] = tc
        if _shade is not None:
            # 明暗系数 0.72~1.18，让同一种地形也有起伏感
            _f = 0.72 + (_shade[i] / 255.0) * 0.46
            terrbuf[o] = min(255, int(tc[0] * _f))
            terrbuf[o + 1] = min(255, int(tc[1] * _f))
            terrbuf[o + 2] = min(255, int(tc[2] * _f))
        else:
            terrbuf[o:o + 3] = tc
        # 大洲
        con = prov2continent.get(pid, 0)
        cc2 = cont_color.get(con)
        if cc2 is None:
            cc2 = _hsv_hex(con * 7 + 11, 0.40, 0.78) if con else bytes((30, 34, 32))
            cont_color[con] = cc2
        contbuf[o:o + 3] = cc2
        rid = prov2region.get(pid, 0)
        rc = reg_color.get(rid)
        if rc is None:
            rc = _hsv_hex(rid + 3, 0.38, 0.72) if rid else bytes((28, 32, 30))
            reg_color[rid] = rc
        regbuf[o:o + 3] = rc
        idbuf[o] = (pid >> 16) & 0xFF
        idbuf[o + 1] = (pid >> 8) & 0xFF
        idbuf[o + 2] = pid & 0xFF

    # 6) 省界（4 邻域不同即标白）
    _tick("绘制省界", "", 62)
    _ystep = max(1, h // 12)
    _ynext = _ystep
    for y in range(h):
        if y >= _ynext:
            _tick("绘制省界", "", 62 + int(6 * y / h))
            _ynext += _ystep
        row = y * w
        for x in range(w):
            i = row + x
            pid = ids[i]
            edge = False
            if x + 1 < w and ids[i + 1] != pid:
                edge = True
            elif y + 1 < h and ids[i + w] != pid:
                edge = True
            elif x > 0 and ids[i - 1] != pid:
                edge = True
            elif y > 0 and ids[i - w] != pid:
                edge = True
            if edge:
                o = i * 3
                # 淡灰而不是纯白：放大后边界线仍然可见但不会压过色块
                edgebuf[o] = 205
                edgebuf[o + 1] = 209
                edgebuf[o + 2] = 203

    # 6.5) 国家边界：相邻省属于不同 owner 的地方压深一档
    _tick("绘制国界", "", 68)
    _ynext2 = _ystep
    for y in range(h):
        if y >= _ynext2:
            _tick("绘制国界", "", 68 + int(6 * y / h))
            _ynext2 += _ystep
        row = y * w
        for x in range(w):
            i = row + x
            pid = ids[i]
            ow = prov2owner.get(pid, "")
            border = False
            if x + 1 < w:
                ow2 = prov2owner.get(ids[i + 1], "")
                if ow2 != ow:
                    border = True
            elif y + 1 < h:
                ow3 = prov2owner.get(ids[i + w], "")
                if ow3 != ow:
                    border = True
            if border:
                o = i * 3
                polbuf[o] = min(255, int(polbuf[o] * 0.45))
                polbuf[o + 1] = min(255, int(polbuf[o + 1] * 0.45))
                polbuf[o + 2] = min(255, int(polbuf[o + 2] * 0.45))

    # 7) 写资产
    _tick("写入省/州/政治图层", "", 76)
    Image.frombytes("RGB", (w, h), bytes(provbuf)).save(os.path.join(dirp, "province.png"))
    Image.frombytes("RGB", (w, h), bytes(statebuf)).save(os.path.join(dirp, "state.png"))
    # 省界存成 RGBA：白线不透明、其余全透明。
    # 之前存 RGB（黑底白线），前端按 opacity 叠上去时黑色背景会把地形压暗一大截。
    _edge_img = Image.frombytes("RGB", (w, h), bytes(edgebuf)).convert("RGBA")
    _edge_img.putalpha(_edge_img.convert("L"))
    _edge_img.save(os.path.join(dirp, "edges.png"))
    Image.frombytes("RGB", (w, h), bytes(polbuf)).save(os.path.join(dirp, "political.png"))
    # 严格版：国家表里查不到的 tag 不参与着色，落到无主色（还原游戏里的真实政治图）
    try:
        stbuf = bytearray(polbuf)
        for i in range(n):
            pid = ids[i]
            ow = prov2owner.get(pid, "")
            if not ow or ow in tag_color_real:
                continue
            o = i * 3
            ptype = ptypes.get(pid, "")
            stbuf[o:o + 3] = oceanc if ptype in ("sea", "ocean", "lake") else neutral
        Image.frombytes("RGB", (w, h), bytes(stbuf)).save(
            os.path.join(dirp, "political_strict.png"))
    except Exception as _e:
        print("  严格版政治图跳过:", _e)
    # 开局部队图层：每省按部队数画一个标记（透明底，叠在任意图层上）
    _tick("绘制部队图层", "", 82)
    try:
        _u = load_units(root)
        _by = _u.get("by_prov") or {}
        _img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        _dr = ImageDraw.Draw(_img)
        _cent = {}
        try:
            _cj = io.open(os.path.join(dirp, "centers.json"), encoding="utf-8").read()
            _cent = json.loads(_cj) or {}
        except Exception:
            _cent = {}
        for _pid_s, _lst in _by.items():
            _c = _cent.get(str(_pid_s))
            if not _c:
                continue
            try:
                _cx, _cy = int(_c[0]), int(_c[1])
            except Exception:
                continue
            _n = len(_lst)
            # 半径随数量增长，封顶
            _r = 6 if _n < 5 else (9 if _n < 20 else (12 if _n < 50 else 15))
            _dr.ellipse([_cx - _r, _cy - _r, _cx + _r, _cy + _r],
                        fill=(220, 60, 60, 200), outline=(255, 255, 255, 230), width=2)
            _txt = str(_n) if _n < 100 else "99+"
            try:
                _dr.text((_cx, _cy), _txt, fill=(255, 255, 255, 255), anchor="mm")
            except Exception:
                pass
        _img.save(os.path.join(dirp, "units.png"))
        print("  部队图层: %d 个有部队的省" % len(_by))
    except Exception as _e:
        print("  部队图层生成失败: %s" % _e)
    except Exception as _e:
        print("  严格版政治图跳过:", _e)
    _tick("写入区域与地形图层", "", 86)
    Image.frombytes("RGB", (w, h), bytes(regbuf)).save(os.path.join(dirp, "region.png"))
    _terr_img = _render_terrain(root, w, h, prov2terrain)
    if _terr_img is None:
        # 省级地形色（来自 definition.csv，永远可信）+ 高度阴影
        _terr_img = Image.frombytes("RGB", (w, h), bytes(terrbuf))
        try:
            _terr_img = _apply_hillshade(_terr_img, root, w, h, None)
        except Exception as _e:
            print("  高度阴影失败，保留纯色:", _e)
    _terr_img.save(os.path.join(dirp, "terrain.png"))
    Image.frombytes("RGB", (w, h), bytes(contbuf)).save(os.path.join(dirp, "continent.png"))
    try:
        _build_rivers_png(root, w, h, dirp)
    except Exception as _e:
        print("  河流图层跳过:", _e)
    Image.frombytes("RGB", (w, h), bytes(idbuf)).save(os.path.join(dirp, "prov_id.png"))
    # 底图用全分辨率：缩进一半的话放大后是糊的（游戏地图本来就只有这个尺寸，没得再高）
    _tick("写入全分辨率底图", "", 94)
    im.save(os.path.join(dirp, "base.png"))

    _tick("写入索引与元信息", "", 97)
    centers = {}
    counts = cnts
    for pid, cnt in counts.items():
        centers[str(pid)] = [round(sumx[pid] / cnt, 1), round(sumy[pid] / cnt, 1)]

    index = {}
    for pid, cnt in counts.items():
        _rgb = None
        try:
            _rgb = list(color2prov and next((k for k, v in color2prov.items() if v == pid), None) or ()) or None
        except Exception:
            _rgb = None
        index[str(pid)] = {"state": prov2state.get(pid, 0), "type": prov2type.get(pid, ""),
                           "region": prov2region.get(pid, 0), "terrain": prov2terrain.get(pid, ""),
                           "continent": prov2continent.get(pid, 0), "px": cnt,
                           "rgb": _rgb}

    io.open(os.path.join(dirp, "centers.json"), "w", encoding="utf-8", newline="").write(
        json.dumps(centers, ensure_ascii=False))
    io.open(os.path.join(dirp, "prov_index.json"), "w", encoding="utf-8", newline="").write(
        json.dumps(index, ensure_ascii=False))
    io.open(os.path.join(dirp, "regions.json"), "w", encoding="utf-8", newline="").write(
        json.dumps(region_list, ensure_ascii=False))

    meta = {"w": w, "h": h, "provinces": len(counts), "source": base,
            "ms": int((time.time() - t_all) * 1000), "built": time.strftime("%Y-%m-%d %H:%M:%S"),
            "consistency": consistency,
            "assets": {a: os.path.getsize(os.path.join(dirp, a)) for a in state.map_var("MAP_ASSETS")
                       if os.path.exists(os.path.join(dirp, a))}}
    io.open(meta_path, "w", encoding="utf-8", newline="").write(json.dumps(meta, ensure_ascii=False))
    return {"ok": True, "cached": False, "meta": meta}

def _strategic_regions(root):
    """读 map/strategicregions/*.txt，返回 {province: region_id} 与 region 列表。
    带 mtime 缓存：合并预览/涂色都要用，不缓存每次白花 1.5 秒。"""
    try:
        _sig = None
        for _b in (root, state.game()):
            _d = os.path.join(_b or "", "map", "strategicregions")
            if os.path.isdir(_d):
                _mt = 0
                try:
                    for _fn in os.listdir(_d):
                        _mt = max(_mt, int(os.path.getmtime(os.path.join(_d, _fn))))
                except Exception:
                    pass
                _sig = (os.path.abspath(_b or ""), _mt)
                break
        _hit = state.map_var("_REGION_CACHE").get(_sig)
        if _hit:
            return dict(_hit[0]), list(_hit[1])
    except Exception:
        _sig = None
    _orig_note = None
    prov2region = {}
    regions = []
    for base in (root, state.game()):
        d = os.path.join(base or "", "map", "strategicregions")
        if not os.path.isdir(d):
            continue
        for fn in sorted(f for f in os.listdir(d) if f.endswith(".txt")):
            try:
                text = strip_comments(io.open(os.path.join(d, fn), encoding="utf-8", errors="replace").read())
            except Exception:
                continue
            for m in re.finditer(r'strategic_region\s*=\s*\{', text):
                b = text.find('{', m.end() - 1)
                e = brace_match(text, b)
                if e <= b:
                    continue
                body = text[b + 1:e - 1]
                rid = _first(body, r'(?m)^[ \t]*id\s*=\s*(\d+)')
                if not rid:
                    continue
                rid = int(rid)
                nm = _first(body, r'(?m)^[ \t]*name\s*=\s*"?([^"\r\n]+)"?') or ("地区 %d" % rid)
                pm = re.search(r'(?m)^[ \t]*provinces\s*=\s*\{', body)
                pids = []
                if pm:
                    pb = body.find('{', pm.end() - 1)
                    pe = brace_match(body, pb)
                    if pe > pb:
                        pids = [int(x) for x in re.findall(r'\d+', body[pb + 1:pe - 1])]
                for p in pids:
                    prov2region[p] = rid
                regions.append({"id": rid, "name": nm, "count": len(pids)})
        if regions:
            break
    try:
        if _sig:
            state.map_var("_REGION_CACHE")[_sig] = (dict(prov2region), list(regions))
    except Exception:
        pass
    return prov2region, regions

def _terrain_index_map(root):
    """解析 common/terrain/*.txt：地形索引 → 类别名"""
    idx2type = {}
    for base in reversed(mod_layers(root)):
        d = os.path.join(base or "", "common", "terrain")
        if not os.path.isdir(d):
            continue
        for fn in sorted(f for f in os.listdir(d) if f.endswith(".txt")):
            try:
                text = strip_comments(io.open(os.path.join(d, fn), encoding="utf-8-sig",
                                              errors="replace").read())
            except Exception:
                continue
            for m in re.finditer(r'(?m)^\s*([A-Za-z_][\w]*)\s*=\s*\{', text):
                b = text.find("{", m.end() - 1)
                e = brace_match(text, b)
                if e <= b:
                    continue
                body = text[b + 1:e - 1]
                typ = re.search(r'type\s*=\s*(\w+)', body)
                col = re.search(r'color\s*=\s*\{\s*(\d+)\s*\}', body)
                if typ and col:
                    idx2type[int(col.group(1))] = typ.group(1)
    return idx2type

def _hillshade_mask(root, w, h):
    """高度图 → 明暗 mask（L 模式，255=全亮）。没有高度图或尺寸不符返回 None。"""
    try:
        from PIL import Image, ImageChops
        Image.MAX_IMAGE_PIXELS = None
        hbmp, _ = _layers_find("map/heightmap.bmp", mod_layers(root))
        if not hbmp:
            return None
        with Image.open(hbmp) as him:
            if him.size != (w, h):
                return None
            hh = him.convert("L")
        gx = ImageChops.subtract(ImageChops.offset(hh, 1, 0),
                                 ImageChops.offset(hh, -1, 0), 1.0, 128)
        gy = ImageChops.subtract(ImageChops.offset(hh, 0, 1),
                                 ImageChops.offset(hh, 0, -1), 1.0, 128)

        def lit(v):
            # 西北光：东侧高、南侧高的地形变暗。系数小一点，避免山地整片压黑
            return max(0, min(255, int(128 - (v - 128) * 0.70)))
        shade = ImageChops.add(gx.point(lit), gy.point(lit), 1.0, -128)
        # 下限 108：最暗处也保留约 42% 亮度，当作环境光，不让背光坡变成黑块
        return shade.point(lambda v: max(108, min(255, int(v * 1.28))))
    except Exception:
        return None

def _apply_hillshade(img, root, w, h, ocean_mask=None):
    """给地形色图叠高度阴影。ocean_mask 为 L 模式，255 = 海洋（用弱阴影）。

    用乘法光照而不是 composite（后者会把背光面压到接近黑）：
      先把底色提亮 1.35 倍，再乘一个 0.72~1.27 的系数，
      最终亮度 = 底色 × (0.97 ~ 1.71)，中间值约 1.32 倍，暗部仍有 0.97 倍。"""
    from PIL import Image, ImageChops
    Image.MAX_IMAGE_PIXELS = None
    shade = _hillshade_mask(root, w, h)
    if shade is None:
        return img
    bright = img.point(lambda v: min(255, int(v * 1.35)))
    # m/255 = (0.72 + 0.55*s) / 1.35
    factor = shade.point(lambda v: max(1, min(255, int(189 * (0.72 + 0.55 * (v / 255.0))))))
    out = ImageChops.multiply(bright, factor.convert("RGB"))
    if ocean_mask is not None:
        # 海洋/湖泊只用很弱的起伏
        soft = ImageChops.multiply(img.point(lambda v: min(255, int(v * 1.06))),
                                   shade.point(lambda v: max(150, min(255, int(v * 1.6)))).convert("RGB"))
        out = Image.composite(soft, out, ocean_mask)
    return out

def _apply_terrain_texture(img, root, w, h, tmap, ids):
    """用 map/terrain/atlas0.dds 的贴图亮度调制地形色明暗。

    只调亮度不混色：贴图本身是灰色调细节层，直接 alpha 混合会把地形色洗掉。
    海洋/湖泊跳过——atlas 里没有水面贴图（借用 desert 的），会把海面弄成斑块。
    纹理起点按省号哈希偏移，相邻省的花纹不会对齐。"""
    try:
        from PIL import Image
        Image.MAX_IMAGE_PIXELS = None
        atlas_path, _ = _layers_find("map/terrain/atlas0.dds", mod_layers(root))
        if not atlas_path:
            _g = os.path.join(state.game() or "", "map", "terrain", "atlas0.dds")
            atlas_path = _g if os.path.exists(_g) else None
        if not atlas_path or not tmap:
            return img
        with Image.open(atlas_path) as aim:
            atlas = aim.convert("RGBA")
        TILE = atlas.width // 8
        if TILE <= 0:
            return img
        idx2type, idx2tex = _terrain_tex_map(root)
        if not idx2tex:
            return img
        apx = atlas.load()
        traw = tmap.tobytes()
        src = img.tobytes()
        out = bytearray(src)
        cache = {}
        water = ("ocean", "lakes")
        n = w * h
        for i in range(n):
            ti = traw[i]
            typ = idx2type.get(ti)
            m = idx2tex.get(ti)
            if m is None or m > 63 or typ in water:
                continue
            pid = ids[i] if ids else 0
            ax = (i % w + (pid * 37)) % TILE
            ay = (i // w + (pid * 71)) % TILE
            key = (m, ax, ay)
            tc = cache.get(key)
            if tc is None:
                tc = apx[(m % 8) * TILE + ax, (m // 8) * TILE + ay]
                if len(cache) < 300000:
                    cache[key] = tc
            luma = tc[0] * 0.30 + tc[1] * 0.59 + tc[2] * 0.11
            f = 0.74 + (luma / 255.0) * 0.56
            a = tc[3] / 255.0
            f = 1.0 + (f - 1.0) * (0.50 + a * 0.50)
            o = i * 3
            r = src[o] * f
            g = src[o + 1] * f
            b = src[o + 2] * f
            out[o] = 255 if r > 255 else int(r)
            out[o + 1] = 255 if g > 255 else int(g)
            out[o + 2] = 255 if b > 255 else int(b)
        return Image.frombytes("RGB", (w, h), bytes(out))
    except Exception as e:
        print("地形贴图失败，保留纯色:", e)
        return img

def _terrain_index_trusted(root, layers):
    """terrain.bmp 是否与 provinces.bmp 同源。
    不同源说明 mod 换了地图却没换地形索引图，用它着色会得到与地图无关的分布。"""
    try:
        _t, tbase = _layers_find("map/terrain.bmp", layers)
        _p, pbase = _layers_find("map/provinces.bmp", layers)
        if not _t or not _p:
            return False
        return os.path.abspath(tbase or "") == os.path.abspath(pbase or "")
    except Exception:
        return False

def _render_terrain(root, w, h, prov2terrain):
    """像素级地形图（terrain.bmp 可信时用）。返回 RGB Image，不可信或失败返回 None。"""
    try:
        from PIL import Image, ImageChops
        Image.MAX_IMAGE_PIXELS = None
        layers = mod_layers(root)
        if not _terrain_index_trusted(root, layers):
            print("  terrain.bmp 与 provinces.bmp 不同源，改用省级地形着色")
            return None
        tbmp, _ = _layers_find("map/terrain.bmp", layers)
        if not tbmp:
            return None
        cats = _terrain_colors(root)
        idx2type = _terrain_index_map(root)
        if not idx2type:
            return None
        with Image.open(tbmp) as tim:
            if tim.size != (w, h):
                return None
            tmap = tim.convert("P") if tim.mode != "P" else tim.copy()
        pal = [0] * (256 * 3)
        default = (60, 70, 60)
        for i in range(256):
            typ = idx2type.get(i)
            col = cats.get(typ, default) if typ else default
            pal[i * 3] = col[0]
            pal[i * 3 + 1] = col[1]
            pal[i * 3 + 2] = col[2]
        tmap.putpalette(pal)
        base_rgb = tmap.convert("RGB")

        ocean_mask = tmap.convert("L").point(
            lambda v: 255 if idx2type.get(v) in ("ocean", "lakes") else 0)
        base_rgb = _apply_terrain_texture(base_rgb, root, w, h, tmap, None)
        return _apply_hillshade(base_rgb, root, w, h, ocean_mask)
    except Exception as e:
        print("地形渲染失败，回退纯色:", e)
        return None

def _tag_fallback_color(tag):
    """没有定义颜色的 tag（mod 里州引用了不存在的国家）按 tag 哈希生成稳定色。

    比直接落到中性灰好：至少能看出边界和政治区划，
    不会让整片大陆看起来像数据缺失。"""
    import hashlib
    # 预定义调色板：20 种区分度足够的颜色，按哈希取模。
    # 用 HSV 现算会在某些色相区间退化成相近的 RGB（红区都变成 R=191），
    # 调色板能保证任意两个 tag 落在视觉上不同的色块。
    palette = (
        (230, 90, 90), (90, 160, 230), (110, 200, 120), (240, 190, 90),
        (180, 120, 220), (90, 200, 200), (230, 140, 200), (150, 190, 90),
        (200, 110, 80), (120, 140, 220), (200, 200, 100), (140, 100, 180),
        (100, 180, 160), (220, 160, 120), (160, 200, 200), (200, 130, 130),
        (130, 170, 220), (180, 200, 120), (220, 170, 200), (140, 160, 120),
    )
    h = int(hashlib.md5(str(tag or '').encode('utf-8')).hexdigest()[:8], 16)
    return bytes(palette[h % len(palette)])

def _terrain_colors(root):
    """从 common/terrain/*.txt 读各地形类别的游戏内配色 {name: (r,g,b)}。
    mod 定义了同名类别就覆盖原版；读不到就返回空字典。"""
    out = {}
    for base in reversed(mod_layers(root)):      # 原版 → ... → mod（后覆盖前）
        d = os.path.join(base or "", "common", "terrain")
        if not os.path.isdir(d):
            continue
        for fn in sorted(f for f in os.listdir(d) if f.endswith(".txt")):
            try:
                text = strip_comments(io.open(os.path.join(d, fn), encoding="utf-8-sig",
                                              errors="replace").read())
            except Exception:
                continue
            m = re.search(r'(?m)^categories\s*=\s*\{', text)
            if not m:
                continue
            b = text.find("{", m.end() - 1)
            e = brace_match(text, b)
            if e <= b:
                continue
            body = text[b + 1:e - 1]
            # 只取一级子块：行首单个 tab 缩进的 name = {
            for cm in re.finditer(r'(?m)^\t([a-zA-Z_][\w]*)\s*=\s*\{', body):
                name = cm.group(1)
                cb = body.find("{", cm.end() - 1)
                ce = brace_match(body, cb)
                if ce <= cb:
                    continue
                sub = body[cb + 1:ce - 1]
                col = re.search(r'color\s*=\s*\{\s*(\d+)\s+(\d+)\s+(\d+)\s*\}', sub)
                if col:
                    out[name] = [int(col.group(1)), int(col.group(2)), int(col.group(3))]
    # 亮度归一化：游戏里地形色差异很大（marsh 76,96,35 与 plains 255,129,66 差 3 倍），
    # 直接铺到 2D 地图上会显得一半发黑。把陆地的最大分量抬到 210 左右，色相不变；
    # 海洋/湖泊保持原值（水本来就该深）。
    for name, c in list(out.items()):
        if name in ("ocean", "lakes", "unknown"):
            out[name] = tuple(c)
            continue
        mx = max(c) or 1
        target = 210
        if mx < target:
            f = target / float(mx)
            out[name] = tuple(min(255, int(v * f)) for v in c)
        else:
            out[name] = tuple(c)
    return out
