# -*- coding: utf-8 -*-
"""路由 · 内容数据（event / tech / idea / equip / decision / character / loc / variant / design / portrait）。

P4：从 routes_post.py 原样搬出（31 条）。

P5：又从 routes_get.py 原样搬出 10 条 GET（含前缀）。

P6（2B）：门面依赖全部显式（`_router.install()` 已删除）。门面名字走 `LG.xxx`（`xuerong/core/facade_bridge.py`）。
"""
from urllib.parse import parse_qs, urlparse

from xuerong.api.router import get, post
from xuerong.core import facade_bridge as LG
from xuerong.model.character import (
    character_add, character_delete, character_set, characters_payload,
    portrait_import)
from xuerong.model.decision import (
    decision_add, decision_delete, decision_set, decisions_payload)
from xuerong.model.equipment import (
    add_equipment, delete_equipment, equipment_delete, equipment_detail,
    equipment_edit, equipment_list, save_equipment)
from xuerong.model.event import (
    add_event, delete_event, event_detail, event_edit, event_graph,
    event_space_create, event_space_delete, save_event)
from xuerong.model.idea import add_idea, delete_idea, save_idea
from xuerong.model.loc import save_loc
from xuerong.model.map import _map_pick
from xuerong.model.tech import (
    add_tech, delete_tech, save_tech, tech_link, tech_move, tech_tree_graph)
from xuerong.model.world import loc_generate, loc_missing


@post("/api/loc_save")
def r_api_loc_save(h, body):
    ok, msg = save_loc(body.get("root"), body.get("entries", {}))
    h._send({"ok": ok, "msg": msg})


@post("/api/tech_move")
def r_api_tech_move(h, body):
    h._send(tech_move(body.get("root", ""), body.get("rel", ""),
                         body.get("tid", ""), body.get("x", 0), body.get("y", 0)))


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


@post("/api/portrait_import")
def r_api_portrait_import(h, body):
    h._send(portrait_import(body.get("root") or None,
                               body.get("src_path"), body.get("tag"),
                               body.get("id"), body.get("overwrite", False),
                               body.get("small", False)))


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


@post("/api/design_save")
def r_api_design_save(h, body):
    ok, msg = LG.save_design(body.get("archetype"), body.get("modules") or {},
                          body.get("org") or "", body.get("name") or "",
                          body.get("target") or "")
    h._send({"ok": ok, "msg": msg})


@post("/api/variant_save")
def r_api_variant_save(h, body):
    ok, msg = LG.save_variant(body.get("archetype"), body.get("modules") or {},
                           body.get("name") or "", body.get("org") or "",
                           body.get("target") or "")
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


@post("/api/event_add")
def r_api_event_add(h, body):
    ok, msg = add_event(body.get("root"), body.get("id"))
    h._send({"ok": ok, "msg": msg})


@post("/api/event_delete")
def r_api_event_delete(h, body):
    ok, msg = delete_event(body.get("root"), body.get("file"), body.get("id"))
    h._send({"ok": ok, "msg": msg})


# --------------------------------------------------------------- GET（P5 从 routes_get.py 原样搬出，10 条）

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


@get("/api/equipment_list")
def r_api_equipment_list(h, path_only):
    _q = parse_qs(urlparse(h.path).query)
    h._send(equipment_list(_map_pick(None), _q.get("q", [""])[0]))


@get("/api/equipment_detail")
def r_api_equipment_detail(h, path_only):
    _q = parse_qs(urlparse(h.path).query)
    h._send(equipment_detail(_q.get("id", [""])[0], _q.get("root", [None])[0]))


@get("/api/gfx_missing")
def r_api_gfx_missing(h, path_only):
    _q = parse_qs(urlparse(h.path).query)
    h._send(LG.gfx_missing(_q.get("root", [None])[0],
                           int(_q.get("limit", ["600"])[0])))


@get("/api/loc_missing")
def r_api_loc_missing(h, path_only):
    _q = parse_qs(urlparse(h.path).query)
    h._send(loc_missing(_q.get("root", [None])[0],
                           int(_q.get("limit", ["800"])[0])))


@get("/api/missing_loc")
def r_api_missing_loc(h, path_only):
    h._send({"items": LG.missing_loc()})
