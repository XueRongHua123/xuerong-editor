# -*- coding: utf-8 -*-
"""门面桥：给 `xuerong/api/handlers/` 里的路由函数一个能读门面名字的入口。

**为什么需要它**。第一期把 213 条路由搬进 `handlers/` 时，函数体一个字都没改，靠的是
`xuerong/api/router.py` 的 `install()`：启动时把门面的名字补进每个路由函数所在模块的
`__globals__`，于是 `data_payload` / `TREES` / `_map_pick` 这些裸名字照旧能解析。这招能跑，
但它是隐式的——IDE 里跳不到定义，静态检查看不出引用，改名时也可能漏。

第二期要让这份依赖变成显式的：handlers 里写 `LG.data_payload`，一眼能看出它来自门面。
`install()` 在这个过程中逐步退场，最终 2C 换成 `ctx.xxx`。

**为什么是模块级 `__getattr__` 而不是 `from ... import`**。两个硬约束：

1. 门面 `focus_editor.py` 在 L114 就 `from xuerong.api import _router, routes_get, routes_post`，
   handlers 是被那条 import 链拉起来的。此时门面模块才执行到第 114 行，后面 200 多个 `def`
   还不存在——所以任何「从门面 import 名字」的写法都会 `ImportError`（import 期求值）。
2. `qa/_check_import_boundary.py:33` 有 `FORBIDDEN_TARGET = "focus_editor"`，`xuerong/` 包里
   反向 import 门面会被自己的检查器判违规。

模块级 `__getattr__`（PEP 562）把求值推迟到**调用期**，那时门面早就加载完了。

**边界要说准**：PEP 562 对 `from m import name` 也生效（import 语句内部就是 `getattr`），所以
「顶层 import 一定失败」是不对的。实测三种情形：

```
门面已加载完   → from facade_bridge import save_focus   成功
门面加载到一半 → from facade_bridge import 已定义的名字   成功
门面还没定义它 → from facade_bridge import late_name    ImportError: cannot import name 'late_name'
```

第三条才是真约束，也正是 handlers 的处境：它们是被门面 L114 的 `from xuerong.api import ...`
拉起来的，那一刻门面后面 200 多个 `def` 全不存在。所以 **handlers 里只能写 `LG.xxx` 属性访问
（在函数体内，调用期才求值），不能写顶层 `from ... import 名字`**。`tests/test_scope_bridge.py`
的第 1 条断言（handler 模块级不许出现门面名字）覆盖的就是这件事。

**怎么用**：

```python
from xuerong.core import facade_bridge as LG

@post("/api/xxx")
def r_api_xxx(h, body):
    LG.save_focus(h, body)          # 原来是裸 save_focus(h, body)
```

只做属性访问，不要写 `from xuerong.core.facade_bridge import save_focus`。

**什么时候它就该消失**。2C 完成后 handlers 拿的是 `ctx`，`LG.xxx` 全部换成 `ctx.xxx`，
这个模块只剩「门面自己还需要读的几个老名字」这一种用途，或者直接删掉。留着它当一个
永远不会被触发的中转层是负债。
"""
import sys

FACADE = "focus_editor"


def _facade():
    """取门面模块对象。没加载完就抛一个说清楚原因的错误。

    不缓存在模块级变量里：门面是 `__main__` 角色启动的（`python focus_editor.py` 或打包成
    exe），`sys.modules` 里的键可能是 `"__main__"` 而不是 `"focus_editor"`，而测试脚本里
    又可能是 `"focus_editor"`。每次现查一遍比缓存稳，代价是一次 dict 查找。
    """
    m = sys.modules.get(FACADE)
    if m is None:
        m = sys.modules.get("__main__")
        if m is not None and getattr(m, "__file__", "") and \
                m.__file__.replace("\\", "/").endswith("/focus_editor.py"):
            return m
        raise RuntimeError(
            "门面模块还没加载：既没有 sys.modules['%s']，__main__ 也不是 focus_editor.py。"
            "facade_bridge 只能被门面启动后的代码使用，独立脚本请直接 import 目标模块。"
            % FACADE)
    return m


def __getattr__(name):
    """把 `LG.xxx` 转成 `门面.xxx`。只有属性访问走到这里，`from ... import xxx` 不会。"""
    if name.startswith("__") and name.endswith("__"):
        raise AttributeError(name)
    try:
        m = _facade()
    except RuntimeError:
        raise AttributeError(name)
    try:
        return getattr(m, name)
    except AttributeError:
        raise AttributeError(
            "门面里没有 %r（facade_bridge 只转发已存在的名字，不做兜底）" % name)


def has(name):
    """这个门面名字现在存在吗。给需要在运行期判断可选依赖的地方用。"""
    try:
        getattr(_facade(), name)
    except (RuntimeError, AttributeError):
        return False
    return True


def names(prefix=""):
    """列出可转发的门面名字（调试用）。"""
    return sorted(n for n in dir(_facade()) if n.startswith(prefix))
