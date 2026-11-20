# -*- coding: utf-8 -*-
"""GET 路由 · 一批一次性读取（首页 / 文件片段 / 图标 / 吉祥物图 / 静态前缀）。

P5：从 routes_get.py 原样搬出（23 条，含 4 条前缀）。

这 23 条彼此没有共同领域——多数是「取一段文本 / 取一张图」的一次性路由，
所以单独一个 misc_h，不混进 system_h。

P6（2B）：门面依赖全部显式（`_router.install()` 已删除）。门面名字走 `LG.xxx`（`xuerong/core/facade_bridge.py`）。
"""
import io
import os
from urllib.parse import parse_qs, urlparse

import editor_i18n as i18n

from xuerong.api.router import get, prefix
from xuerong.core import facade_bridge as LG
from xuerong import state
from xuerong.model.map import _map_pick


@get("/")
def r_index(h, path_only):
    lang = LG._lang(h.path)
    html = io.open(state.path_var("INDEX"), encoding="utf-8", errors="replace").read()
    html = i18n.inject(html, lang)
    h._send(html.encode("utf-8"), ctype="text/html; charset=utf-8")


@get("/api/fs")
def r_api_fs(h, path_only):
    qs = parse_qs(urlparse(h.path).query)
    h._send(LG.fs_list(qs.get("path", [""])[0]))


@get("/api/countries")
def r_api_countries(h, path_only):
    h._send(LG.countries_payload())


@get("/api/diplomacy")
def r_api_diplomacy(h, path_only):
    qs = parse_qs(urlparse(h.path).query)
    h._send(LG.diplomacy_get(qs.get("tag", [""])[0]))


@get("/api/log")
def r_api_log(h, path_only):
    _q = parse_qs(urlparse(h.path).query)
    h._send(LG.read_error_log((_q.get("path", [""])[0] or None)))


@get("/api/orphan_tags")
def r_api_orphan_tags(h, path_only):
    h._send(LG.orphan_tags(_map_pick(None)))


@get("/api/strategic_regions")
def r_api_strategic_regions(h, path_only):
    h._send(LG.strategic_regions_list(_map_pick(None)))


@get("/api/supply_areas")
def r_api_supply_areas(h, path_only):
    h._send(LG.supply_areas(_map_pick(None)))


@get("/api/railways")
def r_api_railways(h, path_only):
    _q = parse_qs(urlparse(h.path).query)
    h._send(LG.railways_list(_q.get("root", [None])[0]))


@get("/api/app_info")
def r_api_app_info(h, path_only):
    h._send({"ok": True, **LG.app_info()})


@get("/api/file_excerpt")
def r_api_file_excerpt(h, path_only):
    _q = parse_qs(urlparse(h.path).query)
    h._send(LG.file_excerpt(_q.get("file", [""])[0], _q.get("line", ["1"])[0],
                            _q.get("root", [None])[0]))


@get("/api/errorlog")
def r_api_errorlog(h, path_only):
    h._send(LG.error_log())


@get("/api/report")
def r_api_report(h, path_only):
    h._send({"items": LG.report_items()})


@get("/api/usages")
def r_api_usages(h, path_only):
    qs = parse_qs(urlparse(h.path).query)
    h._send({"items": LG.find_usages(qs.get("id", [""])[0])})


@get("/api/raw")
def r_api_raw(h, path_only):
    qs = parse_qs(urlparse(h.path).query)
    h._send(LG.item_raw(qs.get("kind", [""])[0], qs.get("id", [""])[0]))


@get("/api/icon")
def r_api_icon(h, path_only):
    qs = parse_qs(urlparse(h.path).query)
    p = LG.icon_png(qs.get("gfx", [""])[0])
    if p:
        h._send(io.open(p, "rb").read(), ctype="image/png")
    else:
        h._send({"err": "no icon"}, 404)


@get("/mascot_face.png")
def r_mascot_files(h, path_only):
    fn = os.path.basename(path_only)
    p = os.path.join(state.path_var("RES_DIR"), fn)
    if os.path.exists(p):
        ctype = "image/x-icon" if fn.endswith(".ico") else "image/png"
        h._send(io.open(p, "rb").read(), ctype=ctype)
    else:
        h._send({"err": "no mascot"}, 404)


@get("/mascot_card.png")
def r_mascot_files(h, path_only):
    fn = os.path.basename(path_only)
    p = os.path.join(state.path_var("RES_DIR"), fn)
    if os.path.exists(p):
        ctype = "image/x-icon" if fn.endswith(".ico") else "image/png"
        h._send(io.open(p, "rb").read(), ctype=ctype)
    else:
        h._send({"err": "no mascot"}, 404)


@get("/mascot.ico")
def r_mascot_files(h, path_only):
    fn = os.path.basename(path_only)
    p = os.path.join(state.path_var("RES_DIR"), fn)
    if os.path.exists(p):
        ctype = "image/x-icon" if fn.endswith(".ico") else "image/png"
        h._send(io.open(p, "rb").read(), ctype=ctype)
    else:
        h._send({"err": "no mascot"}, 404)


@prefix("/index")
def rp_index(h, path_only):
    lang = LG._lang(h.path)
    html = io.open(state.path_var("INDEX"), encoding="utf-8", errors="replace").read()
    html = i18n.inject(html, lang)
    h._send(html.encode("utf-8"), ctype="text/html; charset=utf-8")


@prefix("/help")
def rp_help(h, path_only):
    html = i18n.help_html(LG._lang(h.path))
    h._send(html.encode("utf-8"), ctype="text/html; charset=utf-8")


@prefix("/web/")
def rp_web(h, path_only):
    # v2.1 P4：前端资源（CSS 三拆 / JS 底层三拆后由 <link>、<script src> 加载）。
    # 这是本次唯一新增的路由：拆分前页面是单文件，没有任何静态资源请求；
    # 拆分后必须有个出口，否则 /web/css/*.css 全是 404、页面直接裸奔。
    # 只放行 web/ 下的 .css / .js，且 realpath 必须落在 web/ 里（防 ../ 穿越）。
    _rel = path_only[len("/web/"):].replace("\\", "/")
    _base = os.path.realpath(os.path.join(state.path_var("RES_DIR"), "web"))
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
    p = os.path.join(state.path_var("RES_DIR"), "mascot", fn)
    if fn and os.path.isfile(p):
        h._send(io.open(p, "rb").read(), ctype="image/png")
    else:
        h._send({"err": "no mascot"}, 404)
