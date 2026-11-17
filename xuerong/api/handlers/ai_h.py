# -*- coding: utf-8 -*-
"""路由 · AI 辅助（ai_config / ai_test / ai_chat）。

P4：从 routes_post.py 原样搬出（3 条）。
P5：又从 routes_get.py 原样搬出 1 条 GET（含前缀）。

P6（2B）：门面依赖全部显式（`_router.install()` 已删除）。门面名字走 `LG.xxx`
（`xuerong/core/facade_bridge.py`），IDE 能跳转、改名能查引用。
"""
import time

from xuerong.api.router import get, post
from xuerong.core import facade_bridge as LG


@post("/api/ai_config")
def r_api_ai_config(h, body):
    ok, msg = LG.save_ai(body)
    h._send({"ok": ok, "msg": msg})


@post("/api/ai_test")
def r_api_ai_test(h, body):
    # 连通性测试：配置不全时立刻返回，不发请求——否则会卡满 90 秒的 HTTP 超时，
    # 前端等不到响应只会看到「连接被断开」，看不出真实原因。
    cfg = LG.load_ai()
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
            ok, msg = LG.ai_chat(cfg, "ping，只回复 ok", "")
        except Exception as e:
            ok, msg = False, "请求异常：%s" % str(e)[:160]
        h._send({"ok": bool(ok), "msg": (msg or "")[:300],
                    "ms": int((time.time() - t0) * 1000),
                    "provider": provider, "base": base[:60]})


@post("/api/ai_chat")
def r_api_ai_chat(h, body):
    _cfg = LG.load_ai()
    if body.get("stream"):
        h._ai_stream(_cfg, body.get("prompt") or "", body.get("context") or "",
                        body.get("history") or [])
    else:
        ok, msg = LG.ai_chat(_cfg, body.get("prompt") or "", body.get("context") or "",
                          body.get("history") or [])
        h._send({"ok": ok, "msg": msg})


# --------------------------------------------------------------- GET（P5 从 routes_get.py 原样搬出，1 条）

@get("/api/ai_config")
def r_api_ai_config(h, path_only):
    cfg = LG.load_ai()
    cfg["api_key"] = "" if cfg.get("api_key") else ""
    h._send({"config": cfg, "has_key": bool(LG.load_ai().get("api_key"))})
