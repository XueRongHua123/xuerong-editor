# -*- coding: utf-8 -*-
"""POST 路由（P3 从 Handler.do_POST_impl 的 if-elif 链原样搬出）。

151 个精确路由。函数体与原来完全一致，只有两处机械改动：
`self.` → `h.`、整体少一级缩进。
"""
from xuerong.api.router import post, dispatch_post as dispatch


@post("/api/options")
def r_api_options(h, body):
    # v1.24.0：两个独立开关。改完要重新 load_mod 才生效——
    # 这里只把缓存清掉，不自动重载（会打断用户正在编辑的东西）。
    _changed = False
    for _k in ("follow_deps", "follow_launcher"):
        if _k in body:
            OPTIONS[_k] = bool(body[_k])
            _changed = True
    if _changed:
        _save_options()
        _LAYERS_CACHE.clear()
        _MOD_ORDER_CACHE.clear()
    h._send(dict(OPTIONS))
    return


@post("/api/entry_source")
def r_api_entry_source(h, body):
    # v1.24.2：打开编辑器那一刻问「这条会写到哪」，接管提示前移
    h._send(entry_source(body.get("root"), body.get("file") or body.get("rel"),
                            body.get("layer")))
    return


@post("/api/save")
def r_api_save(h, body):
    root = body.get("root")
    rel = body.get("file")
    fid = body.get("id")
    fields = body.get("fields", {})
    ok, msg = save_focus(root, rel, fid, fields)
    h._send({"ok": ok, "msg": msg})


@post("/api/export")
def r_api_export(h, body):
    path, msg = export_zip()
    h._send({"path": path, "msg": msg})


@post("/api/add_focus")
def r_api_add_focus(h, body):
    ok, msg = add_focus(body.get("root"), body.get("file"), body.get("tree"),
                        body.get("id"), body.get("x", 0), body.get("y", 0),
                        body.get("cost", 5),
                        body.get("icon", "GFX_goal_generic_national_unity"))
    h._send({"ok": ok, "msg": msg})


@post("/api/delete_focus")
def r_api_delete_focus(h, body):
    ok, msg = delete_focus(body.get("root"), body.get("file"), body.get("id"))
    h._send({"ok": ok, "msg": msg})


@post("/api/loc_save")
def r_api_loc_save(h, body):
    ok, msg = save_loc(body.get("root"), body.get("entries", {}))
    h._send({"ok": ok, "msg": msg})


@post("/api/add_tree")
def r_api_add_tree(h, body):
    ok, msg = add_tree(body.get("root"), body.get("id"))
    h._send({"ok": ok, "msg": msg})


@post("/api/delete_tree")
def r_api_delete_tree(h, body):
    ok, msg = delete_tree(body.get("root"), body.get("file"), body.get("id"))
    h._send({"ok": ok, "msg": msg})


@post("/api/tech_move")
def r_api_tech_move(h, body):
    h._send(tech_move(body.get("root", ""), body.get("rel", ""),
                         body.get("tid", ""), body.get("x", 0), body.get("y", 0)))


@post("/api/state_province")
def r_api_state_province(h, body):
    h._send(state_province_edit(body.get("pid"), body.get("target")))


@post("/api/update_apply")
def r_api_update_apply(h, body):
    act = body.get("act") or "prepare"
    if act == "download":
        h._send(update_download(body.get("url") or None, body.get("size") or 0))
    elif act == "launch":
        h._send(update_apply(launch=True))
    else:
        h._send(update_apply(launch=False))


@post("/api/map_paint")
def r_api_map_paint(h, body):
    act = body.get("act") or ""
    if act == "begin":
        _bp = body.get("bmp") or MAP_EDIT.get("file") or ""
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
            _rgb = PROV_RGB.get(int(body.get("pid")))
            if not _rgb:
                h._send({"ok": False, "msg": "省 %s 没有颜色定义" % body.get("pid")})
                return
        nx = map_edit_dab(MAP_EDIT.get("file") or body.get("bmp"), int(body.get("x", 0)),
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


@post("/api/state_create")
def r_api_state_create(h, body):
    h._send(state_create(body.get("provinces") or [], body.get("root") or None,
                            body.get("name"), body.get("category"),
                            body.get("manpower") or 100000, body.get("id")))


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


@post("/api/country_variant")
def r_api_country_variant(h, body):
    act = (body.get("action") or "add").lower()
    if act == "del":
        h._send(country_variant_del(body.get("tag", ""), body.get("name", "")))
    else:
        h._send(country_variant_add(body.get("tag", ""), body))


@post("/api/state_save")
def r_api_state_save(h, body):
    h._send(state_save(body.get("id", ""), body.get("fields") or {}))


@post("/api/state_buildings_batch")
def r_api_state_buildings_batch(h, body):
    h._send(state_apply_buildings(body.get("ids") or [],
                                     body.get("buildings") or {},
                                     body.get("resources") or {},
                                     bool(body.get("only_empty"))))


@post("/api/diplomacy_save")
def r_api_diplomacy_save(h, body):
    h._send(diplomacy_save(body.get("tag", ""),
                              body.get("puppets"),
                              body.get("overlord"),
                              body.get("autonomy"),
                              body.get("guarantees"),
                              body.get("access")))


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


@post("/api/country_save")
def r_api_country_save(h, body):
    h._send(country_history_save(body.get("tag", ""), body.get("fields") or {}))


@post("/api/idea_save")
def r_api_idea_save(h, body):
    root = body.get("root")
    ok, msg = save_idea(root, body.get("file"), body.get("id"),
                        body.get("raw") or "", body.get("props") or {},
                        body.get("picture") or "")
    if ok:
        ents = {}
        if body.get("name"):
            ents.setdefault("simp_chinese", {})[body.get("id")] = body.get("name")
        if body.get("desc"):
            ents.setdefault("simp_chinese", {})[body.get("id") + "_desc"] = body.get("desc")
        if body.get("name_ja"):
            ents.setdefault("japanese", {})[body.get("id")] = body.get("name_ja")
        if body.get("desc_ja"):
            ents.setdefault("japanese", {})[body.get("id") + "_desc"] = body.get("desc_ja")
        if body.get("name_en"):
            ents.setdefault("english", {})[body.get("id")] = body.get("name_en")
        if body.get("desc_en"):
            ents.setdefault("english", {})[body.get("id") + "_desc"] = body.get("desc_en")
        if ents:
            save_loc(root, ents)
    h._send({"ok": ok, "msg": msg})


@post("/api/add_idea")
def r_api_add_idea(h, body):
    ok, msg = add_idea(body.get("root"), body.get("id"))
    h._send({"ok": ok, "msg": msg})


@post("/api/delete_idea")
def r_api_delete_idea(h, body):
    ok, msg = delete_idea(body.get("root"), body.get("file"), body.get("id"))
    h._send({"ok": ok, "msg": msg})


@post("/api/load_progress")
def r_api_load_progress(h, body):
    d = dict(LOAD_PROGRESS)
    # 保护：超过 10 秒没更新，认定这轮加载已经结束（防止某处忘了 _lp_done）
    if d.get("active") and time.time() - (d.get("t") or 0) > 10:
        d["active"] = False
    h._send(d)


@post("/api/pick_mod")
def r_api_pick_mod(h, body):
    ds = detect_mods()
    if not ds:
        h._send({"ok": False, "msg": "未选择目录"})
    else:
        # 只负责选目录并把路径交回去，实际加载由前端再调 /api/load_mod。
        # 原先这里一并 load_mod_root()，导致「选完文件夹」到「加载完」之间
        # 一个请求堵 20 秒，前端拿不到任何中间状态，看起来像卡死。
        h._send({"ok": True, "path": ds[0], "msg": "已选择：" + os.path.basename(ds[0])})


@post("/api/state_refine")
def r_api_state_refine(h, body):
    h._send(state_refine_apply(body.get("sid"), body.get("k"),
                                  body.get("root")))


@post("/api/equipment_edit")
def r_api_equipment_edit(h, body):
    h._send(equipment_edit(body.get("id"), body.get("props"),
                              body.get("root")))


@post("/api/equipment_delete")
def r_api_equipment_delete(h, body):
    h._send(equipment_delete(body.get("id"), body.get("root")))


@post("/api/tech_graph")
def r_api_tech_graph(h, body):
    h._send(tech_tree_graph(body.get("folder") or "",
                               body.get("tag") or None,
                               body.get("root") or None))


@post("/api/navy")
def r_api_navy(h, body):
    h._send(navy_payload(body.get("root") or None))


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


@post("/api/decisions")
def r_api_decisions(h, body):
    h._send(decisions_payload(body.get("root") or None))


@post("/api/decision_add")
def r_api_decision_add(h, body):
    h._send(decision_add(body.get("root") or None, body.get("id"),
                            body.get("category"), body.get("icon"),
                            body.get("cost", 50), body.get("fire_only_once", True),
                            body.get("effect"), body.get("category_new")))


@post("/api/decision_set")
def r_api_decision_set(h, body):
    h._send(decision_set(body.get("root") or None, body.get("id"),
                            body.get("fields") or {}))


@post("/api/decision_delete")
def r_api_decision_delete(h, body):
    h._send(decision_delete(body.get("root") or None, body.get("id")))


@post("/api/characters")
def r_api_characters(h, body):
    h._send(characters_payload(body.get("root") or None))


@post("/api/character_add")
def r_api_character_add(h, body):
    h._send(character_add(body.get("root") or None, body.get("id"),
                             body.get("name"), body.get("type"),
                             body.get("skill", 3), body.get("attack", 3),
                             body.get("defense", 3), body.get("planning", 3),
                             body.get("logistics", 3),
                             body.get("portrait_large"),
                             body.get("portrait_small"),
                             body.get("country"),
                             body.get("portrait_src"),
                             body.get("portrait_overwrite", False)))


@post("/api/character_set")
def r_api_character_set(h, body):
    h._send(character_set(body.get("root") or None, body.get("id"),
                             body.get("fields") or {}))


@post("/api/character_delete")
def r_api_character_delete(h, body):
    h._send(character_delete(body.get("root") or None, body.get("id")))


@post("/api/bookmarks")
def r_api_bookmarks(h, body):
    h._send(bookmarks_payload(body.get("root") or None))


@post("/api/bookmark_add")
def r_api_bookmark_add(h, body):
    h._send(bookmark_add(body.get("root") or None, body.get("name"),
                            body.get("date"), body.get("desc"),
                            body.get("picture"), body.get("default_country"),
                            body.get("countries")))


@post("/api/bookmark_set")
def r_api_bookmark_set(h, body):
    h._send(bookmark_set(body.get("root") or None, body.get("index"),
                            body.get("fields") or {}))


@post("/api/bookmark_delete")
def r_api_bookmark_delete(h, body):
    h._send(bookmark_delete(body.get("root") or None, body.get("index")))


@post("/api/completed_focuses")
def r_api_completed_focuses(h, body):
    h._send(completed_focuses_payload(body.get("root") or None,
                                         body.get("tag") or ""))


@post("/api/focus_complete_add")
def r_api_focus_complete_add(h, body):
    h._send(focus_complete_add(body.get("root") or None,
                                  body.get("tag"), body.get("focus")))


@post("/api/focus_complete_delete")
def r_api_focus_complete_delete(h, body):
    h._send(focus_complete_delete(body.get("root") or None,
                                     body.get("tag"), body.get("index")))


@post("/api/politics")
def r_api_politics(h, body):
    h._send(politics_payload(body.get("root") or None, body.get("tag") or ""))


@post("/api/politics_save")
def r_api_politics_save(h, body):
    h._send(politics_save(body.get("root") or None, body.get("tag"),
                             body.get("fields") or {}))


@post("/api/popularities_save")
def r_api_popularities_save(h, body):
    h._send(popularities_save(body.get("root") or None, body.get("tag"),
                                 body.get("pops") or {}))


@post("/api/war_add")
def r_api_war_add(h, body):
    h._send(war_add(body.get("root") or None, body.get("tag"),
                       body.get("target"), body.get("type")))


@post("/api/war_delete")
def r_api_war_delete(h, body):
    h._send(war_delete(body.get("root") or None, body.get("tag"),
                          body.get("index")))


@post("/api/air_wings")
def r_api_air_wings(h, body):
    h._send(air_wings_payload(body.get("root") or None))


@post("/api/air_wing_add")
def r_api_air_wing_add(h, body):
    h._send(air_wing_add(body.get("root") or None, body.get("province"),
                            body.get("name"), body.get("type"),
                            body.get("owner"), body.get("amount", 10)))


@post("/api/air_wing_delete")
def r_api_air_wing_delete(h, body):
    h._send(air_wing_delete(body.get("root") or None, body.get("index")))


@post("/api/navy_add_ship")
def r_api_navy_add_ship(h, body):
    h._send(navy_add_ship(body.get("root") or None, body.get("fi"),
                             body.get("ti"), body.get("name"),
                             body.get("definition"), body.get("exp"),
                             body.get("tag")))


@post("/api/navy_add_tf")
def r_api_navy_add_tf(h, body):
    h._send(navy_add_tf(body.get("root") or None, body.get("fi"),
                           body.get("name"), body.get("location"),
                           body.get("tag")))


@post("/api/navy_set_ship")
def r_api_navy_set_ship(h, body):
    h._send(navy_set_ship(body.get("root") or None, body.get("fi"),
                             body.get("ti"), body.get("si"),
                             body.get("fields") or {}))


@post("/api/navy_delete_fleet")
def r_api_navy_delete_fleet(h, body):
    h._send(navy_delete_fleet(body.get("root") or None, body.get("fi")))


@post("/api/navy_delete_tf")
def r_api_navy_delete_tf(h, body):
    h._send(navy_delete_taskforce(body.get("root") or None,
                                     body.get("fi"), body.get("ti")))


@post("/api/gfx_list")
def r_api_gfx_list(h, body):
    h._send(gfx_list(body.get("root") or None, body.get("kind") or "goal"))


@post("/api/portrait_import")
def r_api_portrait_import(h, body):
    h._send(portrait_import(body.get("root") or None,
                               body.get("src_path"), body.get("tag"),
                               body.get("id"), body.get("overwrite", False),
                               body.get("small", False)))


@post("/api/diagnose")
def r_api_diagnose(h, body):
    h._send(diagnose(body.get("root") or None))


@post("/api/gfx_import")
def r_api_gfx_import(h, body):
    h._send(gfx_import(body.get("root") or None, body.get("src"),
                          body.get("kind") or "goal", body.get("name"),
                          body.get("sprite"), body.get("size"),
                          bool(body.get("overwrite"))))


@post("/api/gfx_sprites")
def r_api_gfx_sprites(h, body):
    h._send(gfx_registered(body.get("root") or None,
                              body.get("pattern") or ""))


@post("/api/country_tags")
def r_api_country_tags(h, body):
    h._send(country_tags_payload(body.get("root") or None))


@post("/api/country_tag_add")
def r_api_country_tag_add(h, body):
    h._send(country_tag_add(body.get("root") or None, body.get("tag"),
                               body.get("color"), body.get("culture")))


@post("/api/country_tag_delete")
def r_api_country_tag_delete(h, body):
    h._send(country_tag_delete(body.get("root") or None, body.get("tag")))


@post("/api/country_history_create")
def r_api_country_history_create(h, body):
    h._send(country_history_create(
        body.get("root") or None, body.get("tag"),
        capital=body.get("capital") or 1,
        ruling_party=body.get("ruling_party") or "neutrality",
        name=body.get("name"), oob=body.get("oob") or None,
        research_slots=body.get("research_slots") or 3))


@post("/api/world_create")
def r_api_world_create(h, body):
    h._send(world_create(
        body.get("out_dir") or "",
        source=body.get("source") or "procedural",
        width=body.get("width") or 1024,
        height=body.get("height") or 512,
        n_provinces=body.get("n_provinces") or 40,
        min_size=body.get("min_size") or 300,
        seed=body.get("seed") or 11,
        src_path=body.get("src_path") or None,
        sea_level=body.get("sea_level") or 0.42,
        balance=body.get("balance", True),
        min_province_px=body.get("min_province_px") or 800,
        n_regions=body.get("n_regions") or None,
        n_supply=body.get("n_supply") or None,
        tag=body.get("tag") or "ZZV",
        country_name=body.get("country_name") or "新世界",
        color=body.get("color") or None,
        per_state=body.get("per_state") or 8,
        mod_name=body.get("mod_name") or None,
        army=body.get("army", True),
        n_focus=body.get("n_focus") or 24,
        focus_shape=body.get("focus_shape") or "tree",
        gen_focus=body.get("gen_focus", True),
        gen_event=body.get("gen_event", True),
        unit_name=body.get("unit_name") or None))


@post("/api/country_tag_refs")
def r_api_country_tag_refs(h, body):
    h._send(country_tag_refs(body.get("root") or None, body.get("tag")))


@post("/api/country_starter")
def r_api_country_starter(h, body):
    h._send(country_starter_payload(body.get("root") or None,
                                       body.get("tag") or ""))


@post("/api/country_offsite_add")
def r_api_country_offsite_add(h, body):
    h._send(country_offsite_add(body.get("root") or None,
                                   body.get("tag"), body.get("type"),
                                   body.get("level", 1)))


@post("/api/country_offsite_delete")
def r_api_country_offsite_delete(h, body):
    h._send(country_offsite_delete(body.get("root") or None,
                                      body.get("tag"), body.get("index")))


@post("/api/country_offsite_set")
def r_api_country_offsite_set(h, body):
    h._send(country_offsite_set(body.get("root") or None,
                                   body.get("tag"), body.get("index"),
                                   body.get("type"), body.get("level")))


@post("/api/country_ideas")
def r_api_country_ideas(h, body):
    h._send(country_ideas_payload(body.get("root") or None,
                                     body.get("tag") or ""))


@post("/api/country_idea_toggle")
def r_api_country_idea_toggle(h, body):
    h._send(country_idea_toggle(body.get("root") or None,
                                   body.get("tag"), body.get("idea"),
                                   body.get("on", True)))


@post("/api/country_ideas_raw")
def r_api_country_ideas_raw(h, body):
    h._send(load_country_ideas(body.get("root") or None,
                                  body.get("tag") or ""))


@post("/api/country_techs")
def r_api_country_techs(h, body):
    h._send(country_techs_payload(body.get("root") or None,
                                     body.get("tag") or ""))


@post("/api/country_tech_toggle")
def r_api_country_tech_toggle(h, body):
    h._send(country_tech_toggle(body.get("root") or None,
                                   body.get("tag"), body.get("tech"),
                                   body.get("on", True)))


@post("/api/country_techs_raw")
def r_api_country_techs_raw(h, body):
    h._send(load_country_techs(body.get("root") or None,
                                  body.get("tag") or ""))


@post("/api/battalions")
def r_api_battalions(h, body):
    h._send(battalions_payload(body.get("root") or None))


@post("/api/template_save")
def r_api_template_save(h, body):
    h._send(template_save(body.get("name"), body.get("fields") or {},
                             body.get("root") or None))


@post("/api/template_delete")
def r_api_template_delete(h, body):
    h._send(template_delete(body.get("name"), body.get("root") or None))


@post("/api/template_add")
def r_api_template_add(h, body):
    h._send(template_add(body.get("name"), body.get("unit"),
                            body.get("x", 0), body.get("y", 0),
                            body.get("root") or None, body.get("tag")))


@post("/api/units")
def r_api_units(h, body):
    h._send(units_payload(body.get("root") or None))


@post("/api/unit_add")
def r_api_unit_add(h, body):
    h._send(unit_add(body.get("location"), body.get("template"),
                        body.get("name"), body.get("exp"), body.get("eq"),
                        body.get("root") or None, body.get("tag")))


@post("/api/unit_delete")
def r_api_unit_delete(h, body):
    h._send(unit_delete(body.get("location"), body.get("index"),
                           body.get("root") or None))


@post("/api/unit_move")
def r_api_unit_move(h, body):
    h._send(unit_move(body.get("location"), body.get("index"),
                         body.get("to"), body.get("root") or None))


@post("/api/verify_adopt")
def r_api_verify_adopt(h, body):
    _sub = body.get("sub")
    _root = body.get("root")
    h._send(verify_adopt(_root, _sub) if _sub else verify_all_adopted(_root))


@post("/api/adopt_dir")
def r_api_adopt_dir(h, body):
    h._send(adopt_dir(body.get("root"), body.get("sub"),
                         bool(body.get("force"))))


@post("/api/replace_drop")
def r_api_replace_drop(h, body):
    h._send(replace_drop(body.get("root") or None, body.get("sub") or ""))


@post("/api/replace_fix_all")
def r_api_replace_fix_all(h, body):
    h._send(replace_fix_all(
        body.get("root") or None,
        kind=body.get("kind") or "drop_replace",
        subs=body.get("subs") or None,
        force=bool(body.get("force"))))


@post("/api/replace_ignore")
def r_api_replace_ignore(h, body):
    h._send(replace_ignore(
        body.get("root") or None,
        sub=body.get("sub") or "",
        ref_dir=body.get("ref_dir") or "",
        subs=body.get("subs") or None,
        group=body.get("group") or "",
        remove=bool(body.get("remove"))))


@post("/api/write_targets")
def r_api_write_targets(h, body):
    # POST 分支里 h.q 取不到参数，必须从 body 拿
    h._send(write_targets(body.get("root") or None))


@post("/api/supply_save")
def r_api_supply_save(h, body):
    h._send(supply_area_save(body.get("id"), body.get("value"),
                                body.get("states"), body.get("name"),
                                body.get("root")))


@post("/api/supply_delete")
def r_api_supply_delete(h, body):
    h._send(supply_area_delete(body.get("id"), body.get("root")))


@post("/api/adj_edit")
def r_api_adj_edit(h, body):
    h._send(adjacency_edit(body.get("line"), body.get("type"),
                              body.get("root")))


@post("/api/adj_delete")
def r_api_adj_delete(h, body):
    h._send(adjacency_delete(body.get("line"), body.get("root")))


@post("/api/adj_add")
def r_api_adj_add(h, body):
    h._send(adjacency_add(body.get("from"), body.get("to"),
                             body.get("type"), body.get("through"),
                             body.get("root")))


@post("/api/sr_create")
def r_api_sr_create(h, body):
    h._send(strategic_region_create(body.get("root"), body.get("id"),
                                       body.get("name"), body.get("provinces")))


@post("/api/sr_set_provinces")
def r_api_sr_set_provinces(h, body):
    h._send(strategic_region_set_provinces(body.get("id"),
                                              body.get("provinces"),
                                              body.get("root")))


@post("/api/sr_delete")
def r_api_sr_delete(h, body):
    h._send(strategic_region_delete(body.get("id"), body.get("root")))


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
    h._send(railway_edit(body.get("index"), body.get("level"),
                            body.get("provs"), body.get("root")))


@post("/api/railway_delete")
def r_api_railway_delete(h, body):
    h._send(railway_delete(body.get("index"), body.get("root")))


@post("/api/railway_level")
def r_api_railway_level(h, body):
    h._send(railway_set_level(body.get("index"), body.get("level"),
                                 body.get("root")))


@post("/api/loc_generate")
def r_api_loc_generate(h, body):
    h._send(loc_generate(body.get("root"), body.get("keys"),
                            body.get("lang") or "simp_chinese",
                            bool(body.get("dry"))))


@post("/api/event_edit")
def r_api_event_edit(h, body):
    h._send(event_edit(body.get("id"), body.get("title"), body.get("desc"),
                          body.get("options"), body.get("root"),
                          body.get("titleText"), body.get("descText")))


@post("/api/refine_apply")
def r_api_refine_apply(h, body):
    h._send(refine_apply(body.get("pid") or 0, body.get("k") or 2,
                            body.get("root"), body.get("base_pid")))


@post("/api/output_apply")
def r_api_output_apply(h, body):
    h._send(output_apply_back())


@post("/api/playset_save")
def r_api_playset_save(h, body):
    h._send(playset_save(body.get("paths") or []))


@post("/api/playset_pick")
def r_api_playset_pick(h, body):
    ds = detect_mods()
    h._send({"ok": bool(ds), "path": ds[0] if ds else "",
                "msg": "" if ds else "没有选择目录"})


@post("/api/load_mod")
def r_api_load_mod(h, body):
    ok, msg = load_mod_root(body.get("path"))
    h._send({"ok": ok, "msg": msg})


@post("/api/load_vanilla")
def r_api_load_vanilla(h, body):
    ok, msg = load_vanilla()
    h._send({"ok": ok, "msg": msg})


@post("/api/copy_tree")
def r_api_copy_tree(h, body):
    ok, msg = copy_tree(body.get("id"), body.get("new_id"))
    h._send({"ok": ok, "msg": msg})


@post("/api/copy_item")
def r_api_copy_item(h, body):
    ok, msg = copy_item(body.get("kind"), body.get("id"), body.get("new_id"))
    h._send({"ok": ok, "msg": msg})


@post("/api/design_save")
def r_api_design_save(h, body):
    ok, msg = save_design(body.get("archetype"), body.get("modules") or {},
                          body.get("org") or "", body.get("name") or "",
                          body.get("target") or "")
    h._send({"ok": ok, "msg": msg})


@post("/api/variant_save")
def r_api_variant_save(h, body):
    ok, msg = save_variant(body.get("archetype"), body.get("modules") or {},
                           body.get("name") or "", body.get("org") or "",
                           body.get("target") or "")
    h._send({"ok": ok, "msg": msg})


@post("/api/new_mod")
def r_api_new_mod(h, body):
    base = body.get("base") or mod_home()
    ok, msg = create_mod(base, body.get("id"), body.get("name"),
                         body.get("version", "0.1.0"),
                         body.get("game_version", "1.19.*"),
                         body.get("tree_id", ""), body.get("tag", ""),
                         bool(body.get("create_tree", True)),
                         body.get("dep", ""))
    root = os.path.join(os.path.abspath(base), body.get("id") or "")
    if ok:
        ok2, msg2 = load_mod_root(root)
        msg = msg + ("；" + msg2 if ok2 else "（加载失败: %s）" % msg2)
    h._send({"ok": ok, "msg": msg, "root": root})


@post("/api/undo")
def r_api_undo(h, body):
    ok, msg = undo_last()
    h._send({"ok": ok, "msg": msg})


@post("/api/redo")
def r_api_redo(h, body):
    ok, msg = redo_last()
    h._send({"ok": ok, "msg": msg})


@post("/api/save_tree")
def r_api_save_tree(h, body):
    ok, msg = save_tree(body.get("root"), body.get("file"), body.get("id"),
                        body.get("default"), body.get("country_raw"))
    h._send({"ok": ok, "msg": msg})


@post("/api/equip_save")
def r_api_equip_save(h, body):
    ok, msg = save_equipment(body.get("root"), body.get("file"), body.get("id"),
                             body.get("raw") or "", body.get("name") or "",
                             body.get("desc") or "", body.get("name_ja") or "",
                             body.get("desc_ja") or "", body.get("props") or {},
                             body.get("name_en") or "", body.get("desc_en") or "",
                             body.get("picture") or "")
    h._send({"ok": ok, "msg": msg})


@post("/api/tech_save")
def r_api_tech_save(h, body):
    ok, msg = save_tech(body.get("root"), body.get("file"), body.get("id"),
                        body.get("raw") or "", body.get("name") or "",
                        body.get("desc") or "", body.get("name_ja") or "",
                        body.get("desc_ja") or "", body.get("props") or {},
                        body.get("name_en") or "", body.get("desc_en") or "")
    h._send({"ok": ok, "msg": msg})


@post("/api/tech_link")
def r_api_tech_link(h, body):
    ok, msg = tech_link(body.get("root"), body.get("file"),
                        body.get("source"), body.get("target"))
    h._send({"ok": ok, "msg": msg})


@post("/api/tech_add")
def r_api_tech_add(h, body):
    ok, msg = add_tech(body.get("root"), body.get("id"),
                       body.get("folder") or "", body.get("year") or "1936")
    h._send({"ok": ok, "msg": msg})


@post("/api/tech_delete")
def r_api_tech_delete(h, body):
    ok, msg = delete_tech(body.get("root"), body.get("file"), body.get("id"))
    h._send({"ok": ok, "msg": msg})


@post("/api/event_save")
def r_api_event_save(h, body):
    ok, msg = save_event(body.get("root"), body.get("file"), body.get("id"),
                         body.get("raw") or "", body.get("title") or "",
                         body.get("desc") or "", body.get("title_ja") or "",
                         body.get("desc_ja") or "", body.get("title_en") or "",
                         body.get("desc_en") or "", body.get("options") or [],
                         body.get("trigger_raw") or "", body.get("immediate_raw") or "",
                         body.get("picture") or "")
    h._send({"ok": ok, "msg": msg})


@post("/api/equip_add")
def r_api_equip_add(h, body):
    ok, msg = add_equipment(body.get("root"), body.get("id"))
    h._send({"ok": ok, "msg": msg})


@post("/api/equip_delete")
def r_api_equip_delete(h, body):
    ok, msg = delete_equipment(body.get("root"), body.get("file"), body.get("id"))
    h._send({"ok": ok, "msg": msg})


@post("/api/ai_config")
def r_api_ai_config(h, body):
    ok, msg = save_ai(body)
    h._send({"ok": ok, "msg": msg})


@post("/api/ai_test")
def r_api_ai_test(h, body):
    # 连通性测试：配置不全时立刻返回，不发请求——否则会卡满 90 秒的 HTTP 超时，
    # 前端等不到响应只会看到「连接被断开」，看不出真实原因。
    cfg = load_ai()
    provider = (cfg.get("provider") or "").lower()
    base = (cfg.get("base_url") or "").strip()
    key = cfg.get("api_key") or ""
    model = (cfg.get("model") or "").strip()
    missing = []
    if not provider:
        missing.append("provider")
    if not base:
        missing.append("Base URL")
    if not model:
        missing.append("model")
    if provider and provider != "ollama" and not key:
        missing.append("API Key")
    if missing:
        h._send({"ok": False,
                    "msg": "配置不全：" + "、".join(missing) + "（在「AI」面板里填）",
                    "ms": 0})
    else:
        t0 = time.time()
        try:
            ok, msg = ai_chat(cfg, "ping，只回复 ok", "")
        except Exception as e:
            ok, msg = False, "请求异常：%s" % str(e)[:160]
        h._send({"ok": bool(ok), "msg": (msg or "")[:300],
                    "ms": int((time.time() - t0) * 1000),
                    "provider": provider, "base": base[:60]})


@post("/api/ai_chat")
def r_api_ai_chat(h, body):
    _cfg = load_ai()
    if body.get("stream"):
        h._ai_stream(_cfg, body.get("prompt") or "", body.get("context") or "",
                        body.get("history") or [])
    else:
        ok, msg = ai_chat(_cfg, body.get("prompt") or "", body.get("context") or "",
                          body.get("history") or [])
        h._send({"ok": ok, "msg": msg})


@post("/api/shared_add")
def r_api_shared_add(h, body):
    ok, msg = add_shared_focus(body.get("root"), body.get("id"))
    h._send({"ok": ok, "msg": msg})


@post("/api/shared_delete")
def r_api_shared_delete(h, body):
    ok, msg = delete_shared_focus(body.get("root"), body.get("file"), body.get("id"))
    h._send({"ok": ok, "msg": msg})


@post("/api/event_add")
def r_api_event_add(h, body):
    ok, msg = add_event(body.get("root"), body.get("id"))
    h._send({"ok": ok, "msg": msg})


@post("/api/event_delete")
def r_api_event_delete(h, body):
    ok, msg = delete_event(body.get("root"), body.get("file"), body.get("id"))
    h._send({"ok": ok, "msg": msg})


@post("/api/restore_backup")
def r_api_restore_backup(h, body):
    ok, msg = restore_backup(body.get("root"), body.get("file"), int(body.get("index", -1)))
    h._send({"ok": ok, "msg": msg})


@post("/api/unload_mod")
def r_api_unload_mod(h, body):
    ok, msg = unload_mod(body.get("root"))
    h._send({"ok": ok, "msg": msg})


@post("/api/repair_braces")
def r_api_repair_braces(h, body):
    ok, msg = repair_file_braces(body.get("file") or "")
    h._send({"ok": ok, "msg": msg})


@post("/api/repair_all")
def r_api_repair_all(h, body):
    ok, msg = repair_all_braces()
    h._send({"ok": ok, "msg": msg})
