# -*- coding: utf-8 -*-
"""GET 路由（P3 从 Handler.do_GET_impl 的 if-elif 链原样搬出）。

56 个精确路由 + 6 个前缀。注册顺序 = 原来 elif 链的顺序，前缀先注册先命中。
注意 `/api/data` 是**前缀**匹配，`/api/database` 也会进来——这是原有行为，别改成精确匹配。
"""
from xuerong.api.router import get, prefix, dispatch_get as dispatch


@get("/")
def r_index(h, path_only):
    lang = _lang(h.path)
    html = io.open(INDEX, encoding="utf-8", errors="replace").read()
    html = i18n.inject(html, lang)
    h._send(html.encode("utf-8"), ctype="text/html; charset=utf-8")


@get("/api/fs")
def r_api_fs(h, path_only):
    qs = parse_qs(urlparse(h.path).query)
    h._send(fs_list(qs.get("path", [""])[0]))


@get("/api/countries")
def r_api_countries(h, path_only):
    h._send(countries_payload())


@get("/api/states")
def r_api_states(h, path_only):
    h._send(states_payload())


@get("/api/state")
def r_api_state(h, path_only):
    qs = parse_qs(urlparse(h.path).query)
    h._send(state_detail(qs.get("id", [""])[0], bool(qs.get("full", [""])[0])))


@get("/api/diplomacy")
def r_api_diplomacy(h, path_only):
    qs = parse_qs(urlparse(h.path).query)
    h._send(diplomacy_get(qs.get("tag", [""])[0]))


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


@get("/api/country")
def r_api_country(h, path_only):
    qs = parse_qs(urlparse(h.path).query)
    h._send(country_detail(qs.get("tag", [""])[0]))


@get("/api/country_history")
def r_api_country_history(h, path_only):
    qs = parse_qs(urlparse(h.path).query)
    h._send(country_history_raw(qs.get("tag", [""])[0]))


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


@get("/api/scripted")
def r_api_scripted(h, path_only):
    h._send(scripted_payload())


@get("/api/log")
def r_api_log(h, path_only):
    _q = parse_qs(urlparse(h.path).query)
    h._send(read_error_log((_q.get("path", [""])[0] or None)))


@get("/api/orphan_tags")
def r_api_orphan_tags(h, path_only):
    h._send(orphan_tags(_map_pick(None)))


@get("/api/state_refine_preview")
def r_api_state_refine_preview(h, path_only):
    _q = parse_qs(urlparse(h.path).query)
    h._send(state_refine_preview(_q.get("sid", ["0"])[0],
                                    _q.get("k", ["2"])[0],
                                    _q.get("root", [None])[0]))


@get("/api/equipment_list")
def r_api_equipment_list(h, path_only):
    _q = parse_qs(urlparse(h.path).query)
    h._send(equipment_list(_map_pick(None), _q.get("q", [""])[0]))


@get("/api/equipment_detail")
def r_api_equipment_detail(h, path_only):
    _q = parse_qs(urlparse(h.path).query)
    h._send(equipment_detail(_q.get("id", [""])[0], _q.get("root", [None])[0]))


@get("/api/adjacencies")
def r_api_adjacencies(h, path_only):
    h._send(adjacencies_list(_map_pick(None)))


@get("/api/strategic_regions")
def r_api_strategic_regions(h, path_only):
    h._send(strategic_regions_list(_map_pick(None)))


@get("/api/terrain_by_type")
def r_api_terrain_by_type(h, path_only):
    _q = parse_qs(urlparse(h.path).query)
    h._send(prov_terrain_by_type(_q.get("from", [""])[0],
                                    _q.get("to", [""])[0],
                                    _q.get("root", [None])[0]))


@get("/api/terrain_types")
def r_api_terrain_types(h, path_only):
    h._send(terrain_types(_map_pick(None)))


@get("/api/supply_areas")
def r_api_supply_areas(h, path_only):
    h._send(supply_areas(_map_pick(None)))


@get("/api/railways")
def r_api_railways(h, path_only):
    _q = parse_qs(urlparse(h.path).query)
    h._send(railways_list(_q.get("root", [None])[0]))


@get("/api/gfx_missing")
def r_api_gfx_missing(h, path_only):
    _q = parse_qs(urlparse(h.path).query)
    h._send(gfx_missing(_q.get("root", [None])[0],
                           int(_q.get("limit", ["600"])[0])))


@get("/api/loc_missing")
def r_api_loc_missing(h, path_only):
    _q = parse_qs(urlparse(h.path).query)
    h._send(loc_missing(_q.get("root", [None])[0],
                           int(_q.get("limit", ["800"])[0])))


@get("/api/refine_preview")
def r_api_refine_preview(h, path_only):
    _q = parse_qs(urlparse(h.path).query)
    h._send(refine_preview(_q.get("pid", ["0"])[0], _q.get("k", ["2"])[0],
                              _q.get("root", [None])[0]))


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


@get("/api/output")
def r_api_output(h, path_only):
    _q = parse_qs(urlparse(h.path).query)
    _act = _q.get("act", [""])[0]
    if _act == "toggle":
        _on = _q.get("on", [""])[0]
        h._send(output_toggle(None if _on == "" else (_on in ("1", "true", "yes"))))
    elif _act == "clear":
        h._send(output_clear())
    else:
        h._send(output_state())


@get("/api/playset")
def r_api_playset(h, path_only):
    h._send(playset_get())


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


@get("/api/update")
def r_api_update(h, path_only):
    _f = parse_qs(urlparse(h.path).query).get("force", [""])[0]
    h._send(check_update(force=bool(_f)))


@get("/api/app_info")
def r_api_app_info(h, path_only):
    h._send({"ok": True, **app_info()})


@get("/api/lint")
def r_api_lint(h, path_only):
    h._send(lint_project())


@get("/api/missing_loc")
def r_api_missing_loc(h, path_only):
    h._send({"items": missing_loc()})


@get("/api/file_excerpt")
def r_api_file_excerpt(h, path_only):
    _q = parse_qs(urlparse(h.path).query)
    h._send(file_excerpt(_q.get("file", [""])[0], _q.get("line", ["1"])[0],
                            _q.get("root", [None])[0]))


@get("/api/errorlog")
def r_api_errorlog(h, path_only):
    h._send(error_log())


@get("/api/report")
def r_api_report(h, path_only):
    h._send({"items": report_items()})


@get("/api/usages")
def r_api_usages(h, path_only):
    qs = parse_qs(urlparse(h.path).query)
    h._send({"items": find_usages(qs.get("id", [""])[0])})


@get("/api/icons")
def r_api_icons(h, path_only):
    qs = parse_qs(urlparse(h.path).query)
    kind = qs.get("kind", ["focus"])[0]
    if kind == "tech":
        h._send({"list": sorted(TECH_ICONS.keys()), "map": TECH_ICONS})
    elif kind == "equip":
        h._send({"list": sorted(EQUIP_ICONS.keys()), "map": EQUIP_ICONS})
    else:
        h._send({"list": all_goal_icons() or sorted(ICONS.keys()),
                    "map": {g: "/api/icon?gfx=" + g for g in (all_goal_icons() or sorted(ICONS.keys()))}})


@get("/api/event_space_create")
def r_api_event_space_create(h, path_only):
    _q = parse_qs(urlparse(h.path).query)
    h._send(event_space_create(_q.get("ns", [""])[0], _q.get("root", [None])[0]))


@get("/api/event_space_delete")
def r_api_event_space_delete(h, path_only):
    _q = parse_qs(urlparse(h.path).query)
    h._send(event_space_delete(_q.get("ns", [""])[0], _q.get("root", [None])[0]))


@get("/api/event_detail")
def r_api_event_detail(h, path_only):
    _q = parse_qs(urlparse(h.path).query)
    h._send(event_detail(_q.get("id", [""])[0], _q.get("root", [None])[0]))


@get("/api/event_spaces")
def r_api_event_spaces(h, path_only):
    h._send(event_graph("", None))


@get("/api/event_graph")
def r_api_event_graph(h, path_only):
    _q = parse_qs(urlparse(h.path).query)
    h._send(event_graph(_q.get("ns", [""])[0], _q.get("root", [None])[0]))


@get("/api/focus_trees")
def r_api_focus_trees(h, path_only):
    h._send(focus_tree_list())


@get("/api/focus_graph")
def r_api_focus_graph(h, path_only):
    _q = parse_qs(urlparse(h.path).query)
    h._send(focus_tree_graph(_q.get("tree", [""])[0]))


@get("/api/focus")
def r_api_focus(h, path_only):
    qs = parse_qs(urlparse(h.path).query)
    tid = qs.get("tree", [""])[0]
    fid = qs.get("id", [""])[0]
    t = TREES.get(tid)
    node = None
    if t:
        for f in t.get("focuses", []):
            if f.get("id") == fid:
                node = f
                break
    if node:
        h._send({"desc": LOC.get(fid + "_desc", ""),
                    "effect": node.get("effect", ""),
                    "select_effect": node.get("select_effect", "")})
    else:
        h._send({"err": "not found"}, 404)


@get("/api/backups")
def r_api_backups(h, path_only):
    qs = parse_qs(urlparse(h.path).query)
    root = unquote(qs.get("root", [""])[0])
    rel = unquote(qs.get("file", [""])[0])
    h._send({"items": list_backups(root, rel)})


@get("/api/raw")
def r_api_raw(h, path_only):
    qs = parse_qs(urlparse(h.path).query)
    h._send(item_raw(qs.get("kind", [""])[0], qs.get("id", [""])[0]))


@get("/api/ai_config")
def r_api_ai_config(h, path_only):
    cfg = load_ai()
    cfg["api_key"] = "" if cfg.get("api_key") else ""
    h._send({"config": cfg, "has_key": bool(load_ai().get("api_key"))})


@get("/api/icon")
def r_api_icon(h, path_only):
    qs = parse_qs(urlparse(h.path).query)
    p = icon_png(qs.get("gfx", [""])[0])
    if p:
        h._send(io.open(p, "rb").read(), ctype="image/png")
    else:
        h._send({"err": "no icon"}, 404)


@get("/mascot_face.png")
def r_mascot_files(h, path_only):
    fn = os.path.basename(path_only)
    p = os.path.join(RES_DIR, fn)
    if os.path.exists(p):
        ctype = "image/x-icon" if fn.endswith(".ico") else "image/png"
        h._send(io.open(p, "rb").read(), ctype=ctype)
    else:
        h._send({"err": "no mascot"}, 404)


@get("/mascot_card.png")
def r_mascot_files(h, path_only):
    fn = os.path.basename(path_only)
    p = os.path.join(RES_DIR, fn)
    if os.path.exists(p):
        ctype = "image/x-icon" if fn.endswith(".ico") else "image/png"
        h._send(io.open(p, "rb").read(), ctype=ctype)
    else:
        h._send({"err": "no mascot"}, 404)


@get("/mascot.ico")
def r_mascot_files(h, path_only):
    fn = os.path.basename(path_only)
    p = os.path.join(RES_DIR, fn)
    if os.path.exists(p):
        ctype = "image/x-icon" if fn.endswith(".ico") else "image/png"
        h._send(io.open(p, "rb").read(), ctype=ctype)
    else:
        h._send({"err": "no mascot"}, 404)


@prefix("/index")
def rp_index(h, path_only):
    lang = _lang(h.path)
    html = io.open(INDEX, encoding="utf-8", errors="replace").read()
    html = i18n.inject(html, lang)
    h._send(html.encode("utf-8"), ctype="text/html; charset=utf-8")


@prefix("/help")
def rp_help(h, path_only):
    html = i18n.help_html(_lang(h.path))
    h._send(html.encode("utf-8"), ctype="text/html; charset=utf-8")


@prefix("/api/data")
def rp_api_data(h, path_only):
    h._send(data_payload())


@prefix("/icons/")
def rp_icons(h, path_only):
    fn = os.path.basename(path_only)
    p = os.path.join(ICON_DIR, fn)
    if os.path.exists(p):
        h._send(io.open(p, "rb").read(), ctype="image/png")
    else:
        h._send({"err": "no icon"}, 404)


@prefix("/web/")
def rp_web(h, path_only):
    # v2.1 P4：前端资源（CSS 三拆 / JS 底层三拆后由 <link>、<script src> 加载）。
    # 这是本次唯一新增的路由：拆分前页面是单文件，没有任何静态资源请求；
    # 拆分后必须有个出口，否则 /web/css/*.css 全是 404、页面直接裸奔。
    # 只放行 web/ 下的 .css / .js，且 realpath 必须落在 web/ 里（防 ../ 穿越）。
    _rel = path_only[len("/web/"):].replace("\\", "/")
    _base = os.path.realpath(os.path.join(RES_DIR, "web"))
    _p = os.path.realpath(os.path.join(_base, _rel))
    if (_p.startswith(_base + os.sep) and os.path.isfile(_p)
            and _p.lower().endswith((".css", ".js"))):
        _ct = ("text/css; charset=utf-8" if _p.lower().endswith(".css")
               else "application/javascript; charset=utf-8")
        h._send(io.open(_p, "rb").read(), ctype=_ct)
    else:
        h._send({"err": "no static file"}, 404)


@prefix("/mascot/")
def rp_mascot(h, path_only):
    fn = os.path.basename(path_only)
    p = os.path.join(RES_DIR, "mascot", fn)
    if os.path.exists(p):
        h._send(io.open(p, "rb").read(), ctype="image/png")
    else:
        h._send({"err": "no mascot"}, 404)
