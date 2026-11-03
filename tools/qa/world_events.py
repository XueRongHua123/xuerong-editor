# -*- coding: utf-8 -*-
"""开局事件生成器：进游戏立刻弹一个框，让玩家知道「这个世界通了」。

为什么需要它
------------
A2 的验收里有一条「开局弹一个事件，点确定能关掉」。它顺便验证了两条管线：
`events/` 目录被 replace 之后能读到我们的文件、`common/on_actions` 里写的
`on_startup` 能真的触发。

三个必须写对的地方
------------------
1. `add_namespace = zz_editor` 不能少，否则报 `unknown namespace`
2. 事件 id 是 `<namespace>.<数字>`，本地化键是 `<namespace>.<数字>.t/.d/.a`
   （带点，yml 里照原样写）
3. `on_startup` 是全局 on_action，作用域里没有国家，必须自己指明：
   `ZZV = { country_event = { id = zz_editor.1 days = 0 } }`
"""
import io
import os

NAMESPACE = "zz_editor"
EVENT_ID = "zz_editor.1"

TITLE = "新世界的第一天"
DESC = ("地图、州界、国界、军队，都是刚刚才被造出来的。\\n"
        "从今天起，这里有一个国家，它需要一个方向。")
OPTION = "那就从这里开始。"


def build(tag="ZZV", namespace=NAMESPACE, event_id=EVENT_ID,
          title=TITLE, desc=DESC, option=OPTION):
    """返回事件文本、on_actions 文本、本地化条目。"""
    tag = (tag or "ZZV").strip().upper()
    events = (
        "add_namespace = %s\n"
        "\n"
        "country_event = {\n"
        "\tid = %s\n"
        "\ttitle = %s.t\n"
        "\tdesc = %s.d\n"
        "\tis_triggered_only = yes\n"
        "\tfire_only_once = yes\n"
        "\n"
        "\toption = {\n"
        "\t\tname = %s.a\n"
        "\t\tadd_political_power = 25\n"
        "\t\tset_country_flag = zz_editor_world_started\n"
        "\t}\n"
        "}\n") % (namespace, event_id, event_id, event_id, event_id)

    on_actions = (
        "# 开局把事件塞给玩家国家。on_startup 没有国家作用域，必须写明 tag。\n"
        "on_actions = {\n"
        "\ton_startup = {\n"
        "\t\teffect = {\n"
        "\t\t\t%s = {\n"
        "\t\t\t\tcountry_event = {\n"
        "\t\t\t\t\tid = %s\n"
        "\t\t\t\t\tdays = 0\n"
        "\t\t\t\t}\n"
        "\t\t\t}\n"
        "\t\t}\n"
        "\t}\n"
        "}\n") % (tag, event_id)

    loc = [(event_id + ".t", title),
           (event_id + ".d", desc),
           (event_id + ".a", option)]
    return {"ok": True, "events": events, "on_actions": on_actions,
            "loc": loc, "event_id": event_id}


def write(mod_dir, tag="ZZV", **kw):
    """写 events/ 与 common/on_actions/ 两个文件，返回 (事件文本, loc)。"""
    r = build(tag=tag, **kw)
    de = os.path.join(mod_dir, "events")
    os.makedirs(de, exist_ok=True)
    pe = os.path.join(de, "zz_editor_events.txt")
    io.open(pe, "w", encoding="utf-8", newline="").write(r["events"])
    da = os.path.join(mod_dir, "common", "on_actions")
    os.makedirs(da, exist_ok=True)
    try:
        import world_stubs
        fn = world_stubs.stub_name("common/on_actions")
    except Exception:
        fn = "zz_editor_on_actions.txt"
    pa = os.path.join(da, fn)                       # 覆盖 world_stubs 的空占位
    io.open(pa, "w", encoding="utf-8", newline="").write(r["on_actions"])
    r["paths"] = [pe, pa]
    return r
