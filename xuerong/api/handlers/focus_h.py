# -*- coding: utf-8 -*-
"""路由 · 国策与共享国策（focus / tree / completed / shared）。

P4：从 routes_post.py 原样搬出（11 条）。

P5：又从 routes_get.py 原样搬出 3 条 GET（含前缀）。

P6（2B）：门面依赖全部显式（`_router.install()` 已删除）。门面名字走 `LG.xxx`（`xuerong/core/facade_bridge.py`）。
"""
from urllib.parse import parse_qs, urlparse

from xuerong.api.router import get, post
from xuerong.core import facade_bridge as LG
from xuerong import state
from xuerong.model.focus import (
    add_focus, delete_focus, focus_complete_add, focus_complete_delete,
    focus_tree_graph, focus_tree_list)


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


@post("/api/add_tree")
def r_api_add_tree(h, body):
    ok, msg = LG.add_tree(body.get("root"), body.get("id"))
    h._send({"ok": ok, "msg": msg})


@post("/api/delete_tree")
def r_api_delete_tree(h, body):
    ok, msg = LG.delete_tree(body.get("root"), body.get("file"), body.get("id"))
    h._send({"ok": ok, "msg": msg})


@post("/api/completed_focuses")
def r_api_completed_focuses(h, body):
    h._send(LG.completed_focuses_payload(body.get("root") or None,
                                         body.get("tag") or ""))


@post("/api/focus_complete_add")
def r_api_focus_complete_add(h, body):
    h._send(focus_complete_add(body.get("root") or None,
                                  body.get("tag"), body.get("focus")))


@post("/api/focus_complete_delete")
def r_api_focus_complete_delete(h, body):
    h._send(focus_complete_delete(body.get("root") or None,
                                     body.get("tag"), body.get("index")))


@post("/api/copy_tree")
def r_api_copy_tree(h, body):
    ok, msg = LG.copy_tree(body.get("id"), body.get("new_id"))
    h._send({"ok": ok, "msg": msg})


@post("/api/save_tree")
def r_api_save_tree(h, body):
    ok, msg = LG.save_tree(body.get("root"), body.get("file"), body.get("id"),
                        body.get("default"), body.get("country_raw"))
    h._send({"ok": ok, "msg": msg})


@post("/api/shared_add")
def r_api_shared_add(h, body):
    ok, msg = LG.add_shared_focus(body.get("root"), body.get("id"))
    h._send({"ok": ok, "msg": msg})


@post("/api/shared_delete")
def r_api_shared_delete(h, body):
    ok, msg = LG.delete_shared_focus(body.get("root"), body.get("file"), body.get("id"))
    h._send({"ok": ok, "msg": msg})


# --------------------------------------------------------------- GET（P5 从 routes_get.py 原样搬出，3 条）

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
    t = state.trees().get(tid)
    node = None
    if t:
        for f in t.get("focuses", []):
            if f.get("id") == fid:
                node = f
                break
    if node:
        h._send({"desc": state.loc().get(fid + "_desc", ""),
                    "effect": node.get("effect", ""),
                    "select_effect": node.get("select_effect", "")})
    else:
        h._send({"err": "not found"}, 404)
