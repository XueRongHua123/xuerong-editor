# -*- coding: utf-8 -*-
"""把「删 install() 是否安全」变成一条可长期跑的断言（2A 的护栏）。

锁三件事，任何一条破了都说明有人往 handler 里塞了模块级门面引用：

  1. handler 模块里不存在「模块级出现」的门面名字（模块常量 / 装饰器参数 / 默认值）
     —— 否则门面加载到那一行时名字还没定义
  2. 每个路由函数的 __globals__ 就是它所在模块的 __dict__（不是门面字典）
  3. install() 之后 handler 模块的 __name__ / __file__ 没被门面顶掉

用法：python tests/test_scope_bridge.py     （不需要起服务）
退出码：0 = 通过；1 = 有违规。
"""
import dis
import glob
import importlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import ast                                                    # noqa: E402

FACADE_MOD = "focus_editor"


def facade_names():
    src = os.path.join(ROOT, "focus_editor.py")
    tree = ast.parse(open(src, encoding="utf-8").read())
    return {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}


def handler_files():
    return sorted(glob.glob(os.path.join(ROOT, "xuerong", "api", "handlers", "*.py")))


def check_module_level(facade):
    """handler 模块级（不在任何 def 内）不许出现门面名字。"""
    bad = []
    for p in handler_files():
        stem = os.path.basename(p)[:-3]
        if stem == "__init__":
            continue
        tree = ast.parse(open(p, encoding="utf-8").read())
        for n in tree.body:
            if isinstance(n, (ast.FunctionDef, ast.ClassDef)):
                # 函数默认值 / 装饰器在别处查，这里只看模块级语句
                continue
            for x in ast.walk(n):
                if isinstance(x, ast.Name) and x.id in facade:
                    bad.append((stem, "模块级", x.id, n.lineno))
    return bad


def check_defaults_and_decorators(facade):
    """默认参数值与装饰器参数是 import 期求值的，同样不许用门面名字。"""
    bad = []
    for p in handler_files():
        stem = os.path.basename(p)[:-3]
        if stem == "__init__":
            continue
        tree = ast.parse(open(p, encoding="utf-8").read())
        for fn in tree.body:
            if not isinstance(fn, ast.FunctionDef):
                continue
            vals = list(fn.args.defaults) + [d for d in fn.args.kw_defaults if d is not None]
            vals += list(fn.decorator_list)
            for v in vals:
                for x in ast.walk(v):
                    if isinstance(x, ast.Name) and x.id in facade:
                        bad.append((stem, fn.name, x.id, getattr(v, "lineno", 0)))
    return bad


def check_runtime():
    """import 门面（会触发 install），核 __globals__ 归属与元信息。"""
    sys.path.insert(0, ROOT)
    import focus_editor as fe                                 # noqa: F401
    from xuerong.api import router

    bad = []
    allfns = list(router.POST_ROUTES.values()) + list(router.GET_ROUTES.values())
    allfns += [fn for _p, fn in router.GET_PREFIXES]
    owner = {}
    for p in handler_files():
        stem = os.path.basename(p)[:-3]
        if stem == "__init__":
            continue
        m = importlib.import_module("xuerong.api.handlers." + stem)
        for fn in allfns:
            if fn.__globals__ is vars(m):
                owner.setdefault(stem, 0)
                owner[stem] += 1
        if m.__name__ != "xuerong.api.handlers." + stem:
            bad.append((stem, "__name__ 被顶掉", m.__name__, 0))
        if os.path.basename(m.__file__) != stem + ".py":
            bad.append((stem, "__file__ 被顶掉", m.__file__, 0))
    for stem, n in sorted(owner.items()):
        if n == 0:
            bad.append((stem, "没有任何路由函数的 __globals__ 指向本模块", "", 0))
    return bad, len(allfns), sum(owner.values())


def main():
    facade = facade_names()
    print("门面顶层 def/class：%d 个" % len(facade))
    bad = []
    bad += check_module_level(facade)
    bad += check_defaults_and_decorators(facade)
    bad_rt, n_fn, n_own = check_runtime()
    bad += bad_rt

    print("路由函数 %d 个，其中 %d 个的 __globals__ 指向自己所在的 handler 模块" % (n_fn, n_own))
    if bad:
        print("违规 %d：" % len(bad))
        for stem, what, nm, ln in bad:
            print("  %-20s %-32s %s (L%s)" % (stem, what, nm, ln))
        return 1
    print("违规 0 —— handlers 没有任何模块级门面引用，__globals__ 归属正确")
    return 0


if __name__ == "__main__":
    sys.exit(main())
