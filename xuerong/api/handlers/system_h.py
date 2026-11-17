# -*- coding: utf-8 -*-
"""路由 · 系统与工程（options / save / export / update / gfx / replace / playset / undo）。

P4：从 routes_post.py 原样搬出（23 条）。

P5：又从 routes_get.py 原样搬出 8 条 GET（含前缀）。

P6（2B）：门面依赖全部显式（`_router.install()` 已删除）。门面名字走 `LG.xxx`（`xuerong/core/facade_bridge.py`）。
"""
import time
from urllib.parse import parse_qs, unquote, urlparse

from xuerong.api.router import get, post, prefix
from xuerong.core import facade_bridge as LG
from xuerong.core.paths import (
    _LAYERS_CACHE, _MOD_ORDER_CACHE, _save_options)
from xuerong.model.diagnose import diagnose
from xuerong.model.focus import save_focus
from xuerong.model.history import redo_last, undo_last
from xuerong.model.replace import replace_drop, replace_fix_all, replace_ignore


@post("/api/options")
def r_api_options(h, body):
    # v1.24.0：两个独立开关。改完要重新 load_mod 才生效——
    # 这里只把缓存清掉，不自动重载（会打断用户正在编辑的东西）。
    _changed = False
    for _k in ("follow_deps", "follow_launcher"):
        if _k in body:
            LG.OPTIONS[_k] = bool(body[_k])
            _changed = True
    if _changed:
        _save_options()
        _LAYERS_CACHE.clear()
        _MOD_ORDER_CACHE.clear()
    h._send(dict(LG.OPTIONS))
    return


@post("/api/entry_source")
def r_api_entry_source(h, body):
    # v1.24.2：打开编辑器那一刻问「这条会写到哪」，接管提示前移
    h._send(LG.entry_source(body.get("root"), body.get("file") or body.get("rel"),
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
    path, msg = LG.export_zip()
    h._send({"path": path, "msg": msg})


@post("/api/update_apply")
def r_api_update_apply(h, body):
    act = body.get("act") or "prepare"
    if act == "download":
        h._send(LG.update_download(body.get("url") or None, body.get("size") or 0))
    elif act == "launch":
        h._send(LG.update_apply(launch=True))
    else:
        h._send(LG.update_apply(launch=False))


@post("/api/load_progress")
def r_api_load_progress(h, body):
    d = dict(LG.LOAD_PROGRESS)
    # 保护：超过 10 秒没更新，认定这轮加载已经结束（防止某处忘了 _lp_done）
    if d.get("active") and time.time() - (d.get("t") or 0) > 10:
        d["active"] = False
    h._send(d)


@post("/api/gfx_list")
def r_api_gfx_list(h, body):
    h._send(LG.gfx_list(body.get("root") or None, body.get("kind") or "goal"))


@post("/api/diagnose")
def r_api_diagnose(h, body):
    h._send(diagnose(body.get("root") or None))


@post("/api/gfx_import")
def r_api_gfx_import(h, body):
    h._send(LG.gfx_import(body.get("root") or None, body.get("src"),
                          body.get("kind") or "goal", body.get("name"),
                          body.get("sprite"), body.get("size"),
                          bool(body.get("overwrite"))))


@post("/api/gfx_sprites")
def r_api_gfx_sprites(h, body):
    h._send(LG.gfx_registered(body.get("root") or None,
                              body.get("pattern") or ""))


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
    h._send(LG.write_targets(body.get("root") or None))


@post("/api/refine_apply")
def r_api_refine_apply(h, body):
    h._send(LG.refine_apply(body.get("pid") or 0, body.get("k") or 2,
                            body.get("root"), body.get("base_pid")))


@post("/api/output_apply")
def r_api_output_apply(h, body):
    h._send(LG.output_apply_back())


@post("/api/playset_save")
def r_api_playset_save(h, body):
    h._send(LG.playset_save(body.get("paths") or []))


@post("/api/playset_pick")
def r_api_playset_pick(h, body):
    ds = LG.detect_mods()
    h._send({"ok": bool(ds), "path": ds[0] if ds else "",
                "msg": "" if ds else "没有选择目录"})


@post("/api/load_vanilla")
def r_api_load_vanilla(h, body):
    ok, msg = LG.load_vanilla()
    h._send({"ok": ok, "msg": msg})


@post("/api/copy_item")
def r_api_copy_item(h, body):
    ok, msg = LG.copy_item(body.get("kind"), body.get("id"), body.get("new_id"))
    h._send({"ok": ok, "msg": msg})


@post("/api/undo")
def r_api_undo(h, body):
    ok, msg = undo_last()
    h._send({"ok": ok, "msg": msg})


@post("/api/redo")
def r_api_redo(h, body):
    ok, msg = redo_last()
    h._send({"ok": ok, "msg": msg})


@post("/api/restore_backup")
def r_api_restore_backup(h, body):
    ok, msg = LG.restore_backup(body.get("root"), body.get("file"), int(body.get("index", -1)))
    h._send({"ok": ok, "msg": msg})


# --------------------------------------------------------------- GET（P5 从 routes_get.py 原样搬出，8 条）

@get("/api/scripted")
def r_api_scripted(h, path_only):
    h._send(LG.scripted_payload())


@get("/api/refine_preview")
def r_api_refine_preview(h, path_only):
    _q = parse_qs(urlparse(h.path).query)
    h._send(LG.refine_preview(_q.get("pid", ["0"])[0], _q.get("k", ["2"])[0],
                              _q.get("root", [None])[0]))


@get("/api/output")
def r_api_output(h, path_only):
    _q = parse_qs(urlparse(h.path).query)
    _act = _q.get("act", [""])[0]
    if _act == "toggle":
        _on = _q.get("on", [""])[0]
        h._send(LG.output_toggle(None if _on == "" else (_on in ("1", "true", "yes"))))
    elif _act == "clear":
        h._send(LG.output_clear())
    else:
        h._send(LG.output_state())


@get("/api/playset")
def r_api_playset(h, path_only):
    h._send(LG.playset_get())


@get("/api/update")
def r_api_update(h, path_only):
    _f = parse_qs(urlparse(h.path).query).get("force", [""])[0]
    h._send(LG.check_update(force=bool(_f)))


@get("/api/lint")
def r_api_lint(h, path_only):
    h._send(LG.lint_project())


@get("/api/backups")
def r_api_backups(h, path_only):
    qs = parse_qs(urlparse(h.path).query)
    root = unquote(qs.get("root", [""])[0])
    rel = unquote(qs.get("file", [""])[0])
    h._send({"items": LG.list_backups(root, rel)})


@prefix("/api/data")
def rp_api_data(h, path_only):
    h._send(LG.data_payload())
