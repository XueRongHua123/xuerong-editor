# -*- coding: utf-8 -*-
"""给自建国家写一个国家领袖。

为什么必须有
------------
`common/characters` 被 replace_path 整目录屏蔽，里面一个角色都没有 →
自建国家的「领袖」是空的（选国家页上写着「领袖 无」）。
缺领袖的后果实测是：**选国家页的「选择国家」按钮点了没反应**，
也就是玩家永远进不了游戏。地图、日期、剧本名、国名全都正常，
只有领袖那一行是「无」——这个坑不看那一行根本发现不了。

写法照原版 `common/characters/GER.txt`：
    characters = { <id> = { name = <loc key>
                            portraits = { civilian = { large = GFX_... } }
                            country_leader = { ideology = ... expire = ... id = -1 } } }

注意 `ideology` 要写**具体意识形态（type）**，不能写意识形态组：
中立主义组（neutrality）下面的 type 是 despotism / oligarchism 等。
写组名会报 `neutrality is not a valid ideology. file: common/characters/<TAG>.txt`
——不崩，但领袖等于没定义，还是进不了游戏。

肖像用原版就有的通用头像 `GFX_portrait_generic_europe_male_01`
（已在 interface/*.gfx 里核实存在），不新增任何美术资源。
"""
import io
import os

# 原版 interface 里确实存在的通用头像，换地图/换国家都不用带图片
GENERIC_PORTRAITS = (
    "GFX_portrait_generic_europe_male_01",
    "GFX_portrait_generic_europe_male_02",
    "GFX_portrait_generic_europe_male_03",
)


def build(tag="ZZV", leader_name="临时执政", ideology="despotism",
          portrait=0, expire="1965.1.1.1"):
    """返回 {"text": 角色文件内容, "loc": [(key, 中文), ...], "id": 角色 id}"""
    tag = (tag or "ZZV").upper().strip()
    cid = "%s_leader" % tag
    key = "%s_leader_name" % tag
    gfx = GENERIC_PORTRAITS[int(portrait) % len(GENERIC_PORTRAITS)]
    text = (
        "characters = {\n"
        "\t%s = {\n"
        "\t\tname = %s\n"
        "\t\tportraits = {\n"
        "\t\t\tcivilian = {\n"
        "\t\t\t\tlarge = %s\n"
        "\t\t\t}\n"
        "\t\t}\n"
        "\t\tcountry_leader = {\n"
        "\t\t\tideology = %s\n"
        "\t\t\ttraits = {\n"
        "\t\t\t}\n"
        "\t\t\texpire = \"%s\"\n"
        "\t\t\tid = -1\n"
        "\t\t}\n"
        "\t}\n"
        "}\n") % (cid, key, gfx, ideology, expire)
    return {"text": text, "id": cid,
            "loc": [(key, leader_name or "临时执政")],
            "portrait": gfx}


def write(mod_dir, tag="ZZV", **kw):
    """写到 common/characters/<TAG>.txt，返回相对路径。"""
    r = build(tag, **kw)
    d = os.path.join(mod_dir, "common", "characters")
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, "%s.txt" % (tag or "ZZV").upper())
    io.open(p, "w", encoding="utf-8", newline="").write(r["text"])
    return {"path": "common/characters/%s.txt" % (tag or "ZZV").upper(),
            "loc": r["loc"]}


def link_history(mod_dir, tag="ZZV", cid=None):
    """把国家领袖登记到 history/countries/<TAG> - <名>.txt。

    只写 common/characters 是不够的：HOI4 1.19 里 country_leader 类型的人物
    必须在国家历史里 recruit_character 一句，否则选国家页上「领袖」仍是空的。
    """
    tag = (tag or "ZZV").upper().strip()
    cid = cid or ("%s_leader" % tag)
    d = os.path.join(mod_dir, "history", "countries")
    if not os.path.isdir(d):
        return {"path": "", "added": False, "msg": "没有 history/countries"}
    for fn in sorted(os.listdir(d)):
        if not fn.lower().endswith(".txt"):
            continue
        stem = fn[:-4]
        if not (stem.upper() == tag or stem.upper().startswith(tag + " ")):
            continue
        p = os.path.join(d, fn)
        s = io.open(p, encoding="utf-8", errors="replace").read()
        if cid in s:
            return {"path": "history/countries/" + fn, "added": False,
                    "msg": "已经 recruit 过"}
        if not s.endswith("\n"):
            s += "\n"
        s += "recruit_character = %s\n" % cid
        io.open(p, "w", encoding="utf-8", newline="").write(s)
        return {"path": "history/countries/" + fn, "added": True, "msg": "已 recruit"}
    return {"path": "", "added": False, "msg": "找不到 %s 的国家历史" % tag}
