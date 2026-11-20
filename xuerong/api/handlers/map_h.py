# -*- coding: utf-8 -*-
"""路由 · 地图（map / prov / terrain / river / rail / supply / 战略区 / 邻接）。

P4：从 routes_post.py 原样搬出（25 条）。

P5：又从 routes_get.py 原样搬出 12 条 GET（含前缀）。

P6（2B）：门面依赖全部显式（`_router.install()` 已删除）。门面名字走 `LG.xxx`（`xuerong/core/facade_bridge.py`）。
"""
import io
import os
from urllib.parse import parse_qs, urlparse

from xuerong.api.router import get, post, prefix
from xuerong.core import facade_bridge as LG
from xuerong import state
from xuerong.core.paths import is_under_game, mod_layers
from xuerong.model.map import (
    _ensure_prov_rgb, _map_pick, height_paint, height_sample, map_analysis,
    map_asset, map_build, map_cache_clear, map_edit_begin, map_edit_commit,
    map_edit_dab, map_edit_redo, map_edit_state, map_edit_undo, map_generate,
    map_integrity, map_merge_apply, map_merge_preview, map_meta,
    map_prov_neighbors, map_repair_cross, map_repair_ghost, map_repair_preview,
    prov_terrain_batch, prov_terrain_by_type, prov_terrain_set, river_paint,
    river_preview, river_stats, river_undo, terrain_paint, terrain_types)


@post("/api/map_paint")
def r_api_map_paint(h, body):
    act = body.get("act") or ""
    if act == "begin":
        _bp = body.get("bmp") or state.map_var("MAP_EDIT").get("file") or ""
        if not _bp:
            _root = _map_pick(body.get("root") or None)
            _layers = mod_layers(_root)
            _top = _layers[-1] if _layers else ""
            _bp = os.path.join(_top, "map", "provinces.bmp")
            # 写操作只落链顶；链顶没 bmp 就不能涂（避免写到父 mod）
            if not os.path.exists(_bp):
                h._send({"ok": False,
                            "msg": "链顶 mod 没有自己的 provinces.bmp（地图来自父 mod），"
                                   "不能直接涂色；请对提供地图的那个 mod 操作"})
                return
        if is_under_game(_bp):
            h._send({"ok": False, "msg": "原版目录只读，不能涂色"})
            return
        r = {"ok": map_edit_begin(_bp), "bmp": _bp}
    elif act == "dab":
        _rgb = body.get("rgb")
        if not _rgb and body.get("pid") is not None:
            _ensure_prov_rgb(body.get("root") or None)
            _rgb = state.map_var("PROV_RGB").get(int(body.get("pid")))
            if not _rgb:
                h._send({"ok": False, "msg": "省 %s 没有颜色定义" % body.get("pid")})
                return
        nx = map_edit_dab(state.map_var("MAP_EDIT").get("file") or body.get("bmp"), int(body.get("x", 0)),
                          int(body.get("y", 0)), int(body.get("r", 2)),
                          tuple(_rgb or (255, 0, 255)))
        r = {"ok": True, "pixels": nx}
    elif act == "commit":
        r = map_edit_commit()
    elif act == "undo":
        r = map_edit_undo()
    elif act == "redo":
        r = map_edit_redo()
    else:
        r = map_edit_state()
    h._send(r)


@post("/api/map_merge")
def r_api_map_merge(h, body):
    act = (body.get("act") or "preview")
    _src = int(body.get("src", 0))
    _dst = int(body.get("dst", 0))
    _rt = body.get("root") or None
    if act == "preview":
        h._send(map_merge_preview(_src, _dst, _rt))
    elif act == "neighbors":
        h._send(map_prov_neighbors(_src, _rt))
    else:
        h._send(map_merge_apply(_src, _dst, _rt))


@post("/api/map_integrity")
def r_api_map_integrity(h, body):
    h._send(map_integrity(body.get("root") or None))


@post("/api/map_cache_clear")
def r_api_map_cache_clear(h, body):
    h._send(map_cache_clear())


@post("/api/map_build")
def r_api_map_build(h, body):
    h._send(map_build(bool(body.get("force")), (body.get("root") or None)))


@post("/api/river_paint")
def r_api_river_paint(h, body):
    h._send(river_paint(body.get("points") or [],
                           body.get("kind") or "main",
                           body.get("brush") or 1,
                           bool(body.get("erase")),
                           bool(body.get("new_stroke")),
                           body.get("root") or None))


@post("/api/river_undo")
def r_api_river_undo(h, body):
    h._send(river_undo(body.get("root") or None))


@post("/api/map_generate")
def r_api_map_generate(h, body):
    h._send(map_generate(body.get("source") or "procedural",
                            body.get("out"), body.get("width", 1200),
                            body.get("height", 440),
                            body.get("n_provinces", 180),
                            body.get("min_size", 300),
                            body.get("seed", 11),
                            body.get("src_path"),
                            body.get("sea_level", 0.42),
                            body.get("balance", True),
                            body.get("min_province_px", 800),
                            body.get("n_regions"),
                            body.get("n_supply"),
                            body.get("bbox"),
                            body.get("rivers_path"),
                            body.get("cities_path"),
                            body.get("city_radius", 4)))


@post("/api/supply_save")
def r_api_supply_save(h, body):
    h._send(LG.supply_area_save(body.get("id"), body.get("value"),
                                body.get("states"), body.get("name"),
                                body.get("root")))


@post("/api/supply_delete")
def r_api_supply_delete(h, body):
    h._send(LG.supply_area_delete(body.get("id"), body.get("root")))


@post("/api/adj_edit")
def r_api_adj_edit(h, body):
    h._send(LG.adjacency_edit(body.get("line"), body.get("type"),
                              body.get("root")))


@post("/api/adj_delete")
def r_api_adj_delete(h, body):
    h._send(LG.adjacency_delete(body.get("line"), body.get("root")))


@post("/api/adj_add")
def r_api_adj_add(h, body):
    h._send(LG.adjacency_add(body.get("from"), body.get("to"),
                             body.get("type"), body.get("through"),
                             body.get("root")))


@post("/api/sr_create")
def r_api_sr_create(h, body):
    h._send(LG.strategic_region_create(body.get("root"), body.get("id"),
                                       body.get("name"), body.get("provinces")))


@post("/api/sr_set_provinces")
def r_api_sr_set_provinces(h, body):
    h._send(LG.strategic_region_set_provinces(body.get("id"),
                                              body.get("provinces"),
                                              body.get("root")))


@post("/api/sr_delete")
def r_api_sr_delete(h, body):
    h._send(LG.strategic_region_delete(body.get("id"), body.get("root")))


@post("/api/terrain_batch")
def r_api_terrain_batch(h, body):
    h._send(prov_terrain_batch(body.get("pids"), body.get("terrain"),
                                  body.get("root")))


@post("/api/terrain_by_type")
def r_api_terrain_by_type(h, body):
    h._send(prov_terrain_by_type(body.get("from"), body.get("to"),
                                    body.get("root")))


@post("/api/height_paint")
def r_api_height_paint(h, body):
    h._send(height_paint(body.get("points") or [], body.get("height"),
                            body.get("brush", 8), body.get("feather", True),
                            body.get("root") or None))


@post("/api/height_sample")
def r_api_height_sample(h, body):
    h._send(height_sample(body.get("points") or [], body.get("radius", 1),
                             body.get("root") or None))


@post("/api/terrain_paint")
def r_api_terrain_paint(h, body):
    h._send(terrain_paint(body.get("points"), body.get("terrain"),
                             body.get("brush"), body.get("root")))


@post("/api/terrain_set")
def r_api_terrain_set(h, body):
    h._send(prov_terrain_set(body.get("pid"), body.get("terrain"),
                                body.get("root")))


@post("/api/railway_edit")
def r_api_railway_edit(h, body):
    h._send(LG.railway_edit(body.get("index"), body.get("level"),
                            body.get("provs"), body.get("root")))


@post("/api/railway_delete")
def r_api_railway_delete(h, body):
    h._send(LG.railway_delete(body.get("index"), body.get("root")))


@post("/api/railway_level")
def r_api_railway_level(h, body):
    h._send(LG.railway_set_level(body.get("index"), body.get("level"),
                                 body.get("root")))


# --------------------------------------------------------------- GET（P5 从 routes_get.py 原样搬出，12 条）

@get("/api/river_stats")
def r_api_river_stats(h, path_only):
    qs = parse_qs(urlparse(h.path).query)
    h._send(river_stats(qs.get("root", [""])[0] or None))


@get("/api/river_preview.png")
def r_api_river_preview_png(h, path_only):
    qs = parse_qs(urlparse(h.path).query)
    _rp = river_preview(qs.get("root", [""])[0] or None)
    if not _rp:
        h._send({"ok": False, "msg": "生成河流预览失败"}, 404)
    else:
        h._send(io.open(_rp, "rb").read(), 200, "image/png")


@get("/api/map_meta")
def r_api_map_meta(h, path_only):
    qs3 = parse_qs(urlparse(h.path).query)
    h._send(map_meta((qs3.get("root", [""])[0] or None)))


@get("/api/map_asset")
def r_api_map_asset(h, path_only):
    qs2 = parse_qs(urlparse(h.path).query)
    name = (qs2.get("name", [""])[0] or "")
    p = map_asset(name, (qs2.get("root", [""])[0] or None))
    if not p:
        h._send({"ok": False, "msg": "没有这个图块"}, 404)
    else:
        data = io.open(p, "rb").read()
        h._send(data, 200, "image/png" if p.endswith(".png") else
                   ("application/json; charset=utf-8" if p.endswith(".json") else "application/octet-stream"))


@get("/api/adjacencies")
def r_api_adjacencies(h, path_only):
    h._send(LG.adjacencies_list(_map_pick(None)))


@get("/api/terrain_by_type")
def r_api_terrain_by_type(h, path_only):
    _q = parse_qs(urlparse(h.path).query)
    h._send(prov_terrain_by_type(_q.get("from", [""])[0],
                                    _q.get("to", [""])[0],
                                    _q.get("root", [None])[0]))


@get("/api/terrain_types")
def r_api_terrain_types(h, path_only):
    h._send(terrain_types(_map_pick(None)))


@get("/api/map_repair_cross")
def r_api_map_repair_cross(h, path_only):
    _q = parse_qs(urlparse(h.path).query)
    _ap = _q.get("apply", ["0"])[0] in ("1", "true", "yes")
    h._send(map_repair_cross(_q.get("root", [None])[0], _ap))


@get("/api/map_repair")
def r_api_map_repair(h, path_only):
    _q = parse_qs(urlparse(h.path).query)
    _act = _q.get("act", ["preview"])[0]
    if _act == "ghost":
        h._send(map_repair_ghost(_q.get("root", [None])[0]))
    else:
        h._send(map_repair_preview(_q.get("root", [None])[0]))


@get("/api/map_analysis")
def r_api_map_analysis(h, path_only):
    _q = parse_qs(urlparse(h.path).query)
    try:
        _lim = int(_q.get("limit", ["60"])[0])
        _minpx = int(_q.get("min_px", ["800"])[0])
    except Exception:
        _lim, _minpx = 60, 800
    _ol = _q.get("only_land", ["1"])[0] not in ("0", "false", "")
    h._send(map_analysis(_q.get("root", [None])[0], _lim, _minpx, _ol))


@get("/api/icons")
def r_api_icons(h, path_only):
    qs = parse_qs(urlparse(h.path).query)
    kind = qs.get("kind", ["focus"])[0]
    if kind == "tech":
        h._send({"list": sorted(state.tech_icons().keys()), "map": state.tech_icons()})
    elif kind == "equip":
        h._send({"list": sorted(state.equip_icons().keys()), "map": state.equip_icons()})
    else:
        h._send({"list": LG.all_goal_icons() or sorted(state.icons().keys()),
                    "map": {g: "/api/icon?gfx=" + g for g in (LG.all_goal_icons() or sorted(state.icons().keys()))}})


@prefix("/icons/")
def rp_icons(h, path_only):
    # 用 isfile 而不是 exists：请求 /icons/ 本身时 basename 是空串，join 出来是目录，
    # exists 会为真然后拿目录去 open，抛 IsADirectoryError 变成 500 + 泄露绝对路径。
    fn = os.path.basename(path_only)
    p = os.path.join(state.path_var("ICON_DIR"), fn)
    if fn and os.path.isfile(p):
        h._send(io.open(p, "rb").read(), ctype="image/png")
    else:
        h._send({"err": "no icon"}, 404)
