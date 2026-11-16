# -*- coding: utf-8 -*-
"""HTTP 路由表（P3）。

设计要点
--------
1. **按 HTTP 方法分两张表**。GET 和 POST 在门面里本来就是两个独立的 if-elif 链，
   语义也不一样（POST 带 body，GET 带 query），混成一张要额外判方法，没必要。

    POST_ROUTES   path     -> fn(h, body)        151 条
    GET_ROUTES    path     -> fn(h, path_only)    56 条
    GET_PREFIXES  prefix   -> fn(h, path_only)     6 条（按注册顺序，先到先得）

2. **路由函数自己调 `h._send(...)`**，签名统一 `(h, ...)`。
   门面里原有的分支就是这么写的，搬过来只把 `self` 改成 `h`，别的字不动。

3. **延迟绑定**：搬出来的函数体会用到门面里的几百个名字（`data_payload` /
   `TREES` / `_map_pick` …）。这些函数定义在 `xuerong/api/` 里，如果 import 门面就成环，
   所以改成运行时把函数的 `__globals__` 换成门面的模块字典——见 `install()`。
   这样 `fn.__code__` 一个字节没变，名字解析和搬家前完全一样，也不会把门面的 200 多个
   名字灌进本模块的命名空间。

4. **不合并重复分支**。有几个路由长得几乎一样（`*_payload` 那批），
   故意不抽公共函数：抽了就没法逐行 diff 核对「搬的是不是同一段」。
"""
import types

POST_ROUTES = {}      # path -> fn(h, body)
GET_ROUTES = {}       # path -> fn(h, path_only)
GET_PREFIXES = []     # [(prefix, fn(h, path_only))]，按注册顺序


def post(path):
    def deco(fn):
        POST_ROUTES[path] = fn
        return fn
    return deco


def get(path):
    def deco(fn):
        GET_ROUTES[path] = fn
        return fn
    return deco


def prefix(p):
    """前缀路由。注意顺序：dispatch_get 按注册顺序试，先注册的先命中。"""
    def deco(fn):
        GET_PREFIXES.append((p, fn))
        return fn
    return deco


def dispatch_post(h, path, body):
    """命中返回 True；没命中返回 False（调用方发 404）。"""
    fn = POST_ROUTES.get(path)
    if fn is None:
        return False
    fn(h, body)
    return True


def dispatch_get(h, path_only):
    fn = GET_ROUTES.get(path_only)
    if fn is not None:
        fn(h, path_only)
        return True
    for p, f in GET_PREFIXES:
        if path_only.startswith(p):
            f(h, path_only)
            return True
    return False


def _rebind(fn, ns):
    new = types.FunctionType(fn.__code__, ns, fn.__name__, fn.__defaults__, fn.__closure__)
    if fn.__kwdefaults__:
        new.__kwdefaults__ = fn.__kwdefaults__
    return new


def install(ns):
    """把三张表里的函数重新挂到 `ns`（门面的 globals）上，返回改了几个。

    只换 `__globals__`，`__code__` 不动——所以常量表、闭包、默认值全部原样。
    """
    n = 0
    for path, fn in list(POST_ROUTES.items()):
        POST_ROUTES[path] = _rebind(fn, ns)
        n += 1
    for path, fn in list(GET_ROUTES.items()):
        GET_ROUTES[path] = _rebind(fn, ns)
        n += 1
    for i, (p, fn) in enumerate(GET_PREFIXES):
        GET_PREFIXES[i] = (p, _rebind(fn, ns))
        n += 1
    return n


def stats():
    return {"post": len(POST_ROUTES), "get": len(GET_ROUTES), "prefix": len(GET_PREFIXES)}
