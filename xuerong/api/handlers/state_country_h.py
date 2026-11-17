# -*- coding: utf-8 -*-
"""路由 · 州与国家（state / country / war / diplomacy / politics / bookmark）。

P4：从 routes_post.py 原样搬出（32 条）。

P5：又从 routes_get.py 原样搬出 5 条 GET（含前缀）。

P6（2B）：门面依赖全部显式（`_router.install()` 已删除）。门面名字走 `LG.xxx`（`xuerong/core/facade_bridge.py`）。
"""
from urllib.parse import parse_qs, urlparse

from xuerong.api.router import get, post
from xuerong.core import facade_bridge as LG
from xuerong.model.idea import (
    country_idea_toggle, country_ideas_payload, load_country_ideas)
from xuerong.model.state import (
    state_apply_buildings, state_create, state_detail, state_province_edit,
    state_refine_apply, state_refine_preview, state_save, states_payload)
from xuerong.model.tech import (
    country_tech_toggle, country_techs_payload, load_country_techs)
from xuerong.model.world import (
    bookmark_add, country_history_create, country_tag_add,
    country_tag_delete, country_tag_refs)


@post("/api/state_province")
def r_api_state_province(h, body):
    h._send(state_province_edit(body.get("pid"), body.get("target")))


@post("/api/state_create")
def r_api_state_create(h, body):
    h._send(state_create(body.get("provinces") or [], body.get("root") or None,
                            body.get("name"), body.get("category"),
                            body.get("manpower") or 100000, body.get("id")))


@post("/api/country_variant")
def r_api_country_variant(h, body):
    act = (body.get("action") or "add").lower()
    if act == "del":
        h._send(LG.country_variant_del(body.get("tag", ""), body.get("name", "")))
    else:
        h._send(LG.country_variant_add(body.get("tag", ""), body))


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
    h._send(LG.diplomacy_save(body.get("tag", ""),
                              body.get("puppets"),
                              body.get("overlord"),
                              body.get("autonomy"),
                              body.get("guarantees"),
                              body.get("access")))


@post("/api/country_save")
def r_api_country_save(h, body):
    h._send(LG.country_history_save(body.get("tag", ""), body.get("fields") or {}))


@post("/api/state_refine")
def r_api_state_refine(h, body):
    h._send(state_refine_apply(body.get("sid"), body.get("k"),
                                  body.get("root")))


@post("/api/bookmarks")
def r_api_bookmarks(h, body):
    h._send(LG.bookmarks_payload(body.get("root") or None))


@post("/api/bookmark_add")
def r_api_bookmark_add(h, body):
    h._send(bookmark_add(body.get("root") or None, body.get("name"),
                            body.get("date"), body.get("desc"),
                            body.get("picture"), body.get("default_country"),
                            body.get("countries")))


@post("/api/bookmark_set")
def r_api_bookmark_set(h, body):
    h._send(LG.bookmark_set(body.get("root") or None, body.get("index"),
                            body.get("fields") or {}))


@post("/api/bookmark_delete")
def r_api_bookmark_delete(h, body):
    h._send(LG.bookmark_delete(body.get("root") or None, body.get("index")))


@post("/api/politics")
def r_api_politics(h, body):
    h._send(LG.politics_payload(body.get("root") or None, body.get("tag") or ""))


@post("/api/politics_save")
def r_api_politics_save(h, body):
    h._send(LG.politics_save(body.get("root") or None, body.get("tag"),
                             body.get("fields") or {}))


@post("/api/popularities_save")
def r_api_popularities_save(h, body):
    h._send(LG.popularities_save(body.get("root") or None, body.get("tag"),
                                 body.get("pops") or {}))


@post("/api/war_add")
def r_api_war_add(h, body):
    h._send(LG.war_add(body.get("root") or None, body.get("tag"),
                       body.get("target"), body.get("type")))


@post("/api/war_delete")
def r_api_war_delete(h, body):
    h._send(LG.war_delete(body.get("root") or None, body.get("tag"),
                          body.get("index")))


@post("/api/country_tags")
def r_api_country_tags(h, body):
    h._send(LG.country_tags_payload(body.get("root") or None))


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


@post("/api/country_tag_refs")
def r_api_country_tag_refs(h, body):
    h._send(country_tag_refs(body.get("root") or None, body.get("tag")))


@post("/api/country_starter")
def r_api_country_starter(h, body):
    h._send(LG.country_starter_payload(body.get("root") or None,
                                       body.get("tag") or ""))


@post("/api/country_offsite_add")
def r_api_country_offsite_add(h, body):
    h._send(LG.country_offsite_add(body.get("root") or None,
                                   body.get("tag"), body.get("type"),
                                   body.get("level", 1)))


@post("/api/country_offsite_delete")
def r_api_country_offsite_delete(h, body):
    h._send(LG.country_offsite_delete(body.get("root") or None,
                                      body.get("tag"), body.get("index")))


@post("/api/country_offsite_set")
def r_api_country_offsite_set(h, body):
    h._send(LG.country_offsite_set(body.get("root") or None,
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


# --------------------------------------------------------------- GET（P5 从 routes_get.py 原样搬出，5 条）

@get("/api/states")
def r_api_states(h, path_only):
    h._send(states_payload())


@get("/api/state")
def r_api_state(h, path_only):
    qs = parse_qs(urlparse(h.path).query)
    h._send(state_detail(qs.get("id", [""])[0], bool(qs.get("full", [""])[0])))


@get("/api/country")
def r_api_country(h, path_only):
    qs = parse_qs(urlparse(h.path).query)
    h._send(LG.country_detail(qs.get("tag", [""])[0]))


@get("/api/country_history")
def r_api_country_history(h, path_only):
    qs = parse_qs(urlparse(h.path).query)
    h._send(LG.country_history_raw(qs.get("tag", [""])[0]))


@get("/api/state_refine_preview")
def r_api_state_refine_preview(h, path_only):
    _q = parse_qs(urlparse(h.path).query)
    h._send(state_refine_preview(_q.get("sid", ["0"])[0],
                                    _q.get("k", ["2"])[0],
                                    _q.get("root", [None])[0]))
