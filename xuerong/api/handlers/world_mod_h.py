# -*- coding: utf-8 -*-
"""POST 路由 · 世界与 Mod（world / mod / navy / air / unit / template / adopt / repair）。

P4：从 routes_post.py 原样搬出（26 条）。

P6（2B）：门面依赖全部显式（`_router.install()` 已删除）。门面名字走 `LG.xxx`（`xuerong/core/facade_bridge.py`）。
"""
import os

from xuerong.api.router import post
from xuerong.core import facade_bridge as LG
from xuerong.model.world import (
    create_mod, mod_home, template_add, unit_add, world_create)


@post("/api/pick_mod")
def r_api_pick_mod(h, body):
    ds = LG.detect_mods()
    if not ds:
        h._send({"ok": False, "msg": "未选择目录"})
    else:
        # 只负责选目录并把路径交回去，实际加载由前端再调 /api/load_mod。
        # 原先这里一并 load_mod_root()，导致「选完文件夹」到「加载完」之间
        # 一个请求堵 20 秒，前端拿不到任何中间状态，看起来像卡死。
        h._send({"ok": True, "path": ds[0], "msg": "已选择：" + os.path.basename(ds[0])})


@post("/api/navy")
def r_api_navy(h, body):
    h._send(LG.navy_payload(body.get("root") or None))


@post("/api/air_wings")
def r_api_air_wings(h, body):
    h._send(LG.air_wings_payload(body.get("root") or None))


@post("/api/air_wing_add")
def r_api_air_wing_add(h, body):
    h._send(LG.air_wing_add(body.get("root") or None, body.get("province"),
                            body.get("name"), body.get("type"),
                            body.get("owner"), body.get("amount", 10)))


@post("/api/air_wing_delete")
def r_api_air_wing_delete(h, body):
    h._send(LG.air_wing_delete(body.get("root") or None, body.get("index")))


@post("/api/navy_add_ship")
def r_api_navy_add_ship(h, body):
    h._send(LG.navy_add_ship(body.get("root") or None, body.get("fi"),
                             body.get("ti"), body.get("name"),
                             body.get("definition"), body.get("exp"),
                             body.get("tag")))


@post("/api/navy_add_tf")
def r_api_navy_add_tf(h, body):
    h._send(LG.navy_add_tf(body.get("root") or None, body.get("fi"),
                           body.get("name"), body.get("location"),
                           body.get("tag")))


@post("/api/navy_set_ship")
def r_api_navy_set_ship(h, body):
    h._send(LG.navy_set_ship(body.get("root") or None, body.get("fi"),
                             body.get("ti"), body.get("si"),
                             body.get("fields") or {}))


@post("/api/navy_delete_fleet")
def r_api_navy_delete_fleet(h, body):
    h._send(LG.navy_delete_fleet(body.get("root") or None, body.get("fi")))


@post("/api/navy_delete_tf")
def r_api_navy_delete_tf(h, body):
    h._send(LG.navy_delete_taskforce(body.get("root") or None,
                                     body.get("fi"), body.get("ti")))


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


@post("/api/battalions")
def r_api_battalions(h, body):
    h._send(LG.battalions_payload(body.get("root") or None))


@post("/api/template_save")
def r_api_template_save(h, body):
    h._send(LG.template_save(body.get("name"), body.get("fields") or {},
                             body.get("root") or None))


@post("/api/template_delete")
def r_api_template_delete(h, body):
    h._send(LG.template_delete(body.get("name"), body.get("root") or None))


@post("/api/template_add")
def r_api_template_add(h, body):
    h._send(template_add(body.get("name"), body.get("unit"),
                            body.get("x", 0), body.get("y", 0),
                            body.get("root") or None, body.get("tag")))


@post("/api/units")
def r_api_units(h, body):
    h._send(LG.units_payload(body.get("root") or None))


@post("/api/unit_add")
def r_api_unit_add(h, body):
    h._send(unit_add(body.get("location"), body.get("template"),
                        body.get("name"), body.get("exp"), body.get("eq"),
                        body.get("root") or None, body.get("tag")))


@post("/api/unit_delete")
def r_api_unit_delete(h, body):
    h._send(LG.unit_delete(body.get("location"), body.get("index"),
                           body.get("root") or None))


@post("/api/unit_move")
def r_api_unit_move(h, body):
    h._send(LG.unit_move(body.get("location"), body.get("index"),
                         body.get("to"), body.get("root") or None))


@post("/api/verify_adopt")
def r_api_verify_adopt(h, body):
    _sub = body.get("sub")
    _root = body.get("root")
    h._send(LG.verify_adopt(_root, _sub) if _sub else LG.verify_all_adopted(_root))


@post("/api/adopt_dir")
def r_api_adopt_dir(h, body):
    h._send(LG.adopt_dir(body.get("root"), body.get("sub"),
                         bool(body.get("force"))))


@post("/api/load_mod")
def r_api_load_mod(h, body):
    ok, msg = LG.load_mod_root(body.get("path"))
    h._send({"ok": ok, "msg": msg})


@post("/api/new_mod")
def r_api_new_mod(h, body):
    base = body.get("base") or mod_home()
    ok, msg = create_mod(base, body.get("id"), body.get("name"),
                         body.get("version", "0.1.0"),
                         body.get("game_version") or "",
                         body.get("tree_id", ""), body.get("tag", ""),
                         bool(body.get("create_tree", True)),
                         body.get("dep", ""))
    root = os.path.join(os.path.abspath(base), body.get("id") or "")
    if ok:
        ok2, msg2 = LG.load_mod_root(root)
        msg = msg + ("；" + msg2 if ok2 else "（加载失败: %s）" % msg2)
    h._send({"ok": ok, "msg": msg, "root": root})


@post("/api/unload_mod")
def r_api_unload_mod(h, body):
    ok, msg = LG.unload_mod(body.get("root"))
    h._send({"ok": ok, "msg": msg})


@post("/api/repair_braces")
def r_api_repair_braces(h, body):
    ok, msg = LG.repair_file_braces(body.get("file") or "")
    h._send({"ok": ok, "msg": msg})


@post("/api/repair_all")
def r_api_repair_all(h, body):
    ok, msg = LG.repair_all_braces()
    h._send({"ok": ok, "msg": msg})
