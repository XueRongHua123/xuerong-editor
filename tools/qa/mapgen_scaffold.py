# -*- coding: utf-8 -*-
"""从省图生成一个能启动的最小 mod 骨架。

地图片能生成 map/ 24 个文件，但游戏要启动还缺：
  descriptor.mod
  history/states/*.txt      每个省必须归属到某个州
  common/country_tags/
  common/countries/
  history/countries/
  localisation/
"""
import io
import os
import numpy as np

import mapgen_extra as mgx


def _w(path, text):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    io.open(path, "w", encoding="utf-8", newline="").write(text)


# 换掉地图就等于换掉了省的数量和编号，所有「按省 id / 州 id 引用」的原版数据都会指错。
# 这 50 条目录必须一起 replace 掉，否则游戏在加载期就会崩。
# 清单与占位内容统一放在 qa/world_stubs.py（那边有逐条理由与真机验证记录）。
try:
    import world_stubs
except Exception:                                    # 被当包导入时包路径不同
    import sys as _sys
    _sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import world_stubs

REPLACE_DIRS = world_stubs.REPLACE_DIRS





def _desc_body(name, version, with_path=False, mod_dir_name=""):
    lines = ['version="%s"' % version,
             'tags={ "Alternative History" }',
             'name="%s"' % name,
             'supported_version="1.19.*"']
    if with_path and mod_dir_name:
        lines.append('path="mod/%s"' % mod_dir_name)
    for d in REPLACE_DIRS:
        lines.append('replace_path="%s"' % d)
    return "\n".join(lines) + "\n"


def write_descriptor(mod_dir, name, version="1.0.0"):
    d = os.path.join(mod_dir, "descriptor.mod")
    _w(d, _desc_body(name, version))
    # 同时写一份到 mod 目录外（HOI4 的 mod/ 下需要 <name>.mod 指路）
    outer = os.path.join(os.path.dirname(mod_dir), os.path.basename(mod_dir) + ".mod")
    _w(outer, _desc_body(name, version, True, os.path.basename(mod_dir)))
    return d


def write_country_tags(mod_dir, tag="ZZZ"):
    """写自己的 tag。

    不 replace 原版 common/country_tags，这里只是新增一个文件，
    条目会和原版 00_countries.txt 的 383 个 tag 合并。
    原版是裸键值列表（`GER = "countries/Germany.txt"`，没有 countries = { } 包裹），
    本文件照同一格式写，避免两层不同结构的解析差异。
    """
    _w(os.path.join(mod_dir, "common", "country_tags", "zz_editor_tags.txt"),
       '%s = "countries/%s.txt"\n' % (tag, tag))


def write_country_def(mod_dir, tag="ZZZ", color=(70, 120, 180)):
    _w(os.path.join(mod_dir, "common", "countries", "%s.txt" % tag),
       'graphical_culture = western_european_gfx\n'
       'graphical_culture_2d = western_european_2d\n'
       'color = { %d %d %d }\n' % color)


def write_country_history(mod_dir, tag="ZZZ"):
    """国家历史。

    两处必须照原版写全，少一个进游戏时就崩在初始化阶段
    （game.log 停在 Launching SINGLEPLAYER-game，异常地址 0x00007FF6BEED4300）：

    1. set_popularities 必须四项意识形态齐全。只写 neutrality 是不够的，
       引擎初始化派系时时会读到空指针。
    2. set_research_slots 要写，否则科研槽为 0 时同样会在初始化里出问题。

    oob 指向真实 OOB 文件名（不含 .txt），写成空串会指向不存在的 OOB。
    """
    _w(os.path.join(mod_dir, "history", "countries", "%s - Test.txt" % tag),
       'capital = 1\n'
       'set_research_slots = 3\n'
       'oob = "%s_1936"\n' % tag +
       'set_technology = {\n\tinfantry_weapons = 1\n}\n'
       'set_politics = {\n'
       '\truling_party = neutrality\n'
       '\tlast_election = "1936.1.1"\n'
       '\telection_frequency = 48\n'
       '\telections_allowed = no\n'
       '}\n'
       'set_popularities = {\n'
       '\tdemocratic = 10\n'
       '\tfascism = 10\n'
       '\tcommunism = 10\n'
       '\tneutrality = 70\n'
       '}\n')


def write_states(mod_dir, labels, tag="ZZZ", per_state=8, capital_province=1,
                 sea_ids=None, with_map=False):
    """按省 id 顺序每 per_state 个切一个州。

    每个州必须有：id / name / manpower / state_category / provinces / local_supplies /
    history 里的 owner。缺一个游戏都起不来。

    with_map=True 时返回 (州数, [(州号, [省号...])])，给补给图用。
    """
    n = int(labels.max())
    if n == 0:
        return (0, []) if with_map else 0
    seas = set(int(x) for x in (sea_ids or ()))
    # 海省绝不能进 state：州里出现 sea 省，游戏会在地图加载期报错退出
    land_ids = [i for i in range(1, n + 1) if i not in seas]
    n_states = 0
    sid = 1
    mapping = []
    for start in range(0, len(land_ids), per_state):
        pids = land_ids[start:start + per_state]
        if not pids:
            continue
        # 州名用省 id 范围
        name = "STATE_%d" % sid
        body = [
            "state = {",
            "\tid = %d" % sid,
            '\tname = "%s"' % name,
            "\tmanpower = 100000",
            "\tstate_category = rural",
            "\tprovinces = {",
        ]
        for pid in pids:
            body.append("\t\t%d" % pid)
        body.append("\t}")
        body.append("\tlocal_supplies = 1.0")
        # 第一个州归玩家 tag，其余不归属（无主地）
        if sid == 1:
            body.append("\thistory = {")
            body.append("\t\towner = %s" % tag)
            body.append("\t\t1936.1.1 = {")
            body.append("\t\t\towner = %s" % tag)
            body.append("\t\t}")
            body.append("\t}")
        body.append("}")
        _w(os.path.join(mod_dir, "history", "states", "%d-%s.txt" % (sid, name)),
           "\n".join(body) + "\n")
        mapping.append((sid, list(pids)))
        n_states += 1
        sid += 1
    return (n_states, mapping) if with_map else n_states


def write_units(mod_dir, tag="ZZZ", provinces=()):
    """写 history/units。OOB 可以很空，但这个目录被 replace 掉之后
    至少要有文件，否则某些版本会在加载期报找不到 OOB。"""
    d = os.path.join(mod_dir, "history", "units")
    os.makedirs(d, exist_ok=True)
    # 一个最小的师团模板 + 一支开局部队，保证国家有东西
    body = ['division_template = {',
            '\tname = "%s_Infantry"' % tag,
            '\tregiments = {',
            '\t\tinfantry = { x = 0 y = 0 }',
            '\t}',
            '}',
            '']
    pl = [p for p in provinces][:1]
    if pl:
        body += ['units = {',
                 '\tdivision = {',
                 '\t\tdivision_name = {',
                 '\t\t\tis_name_ordered = yes',
                 '\t\t\tname_order = 1',
                 '\t\t}',
                 '\t\tlocation = %d' % pl[0],
                 '\t\tdivision_template = "%s_Infantry"' % tag,
                 '\t\tstart_experience_factor = 0.3',
                 '\t}',
                 '}',
                 '']
    _w(os.path.join(d, "%s_1936.txt" % tag), "\n".join(body))
    return os.path.join("history", "units", "%s_1936.txt" % tag)


def write_bookmarks(mod_dir, name="雪绒战役", tag="ZZZ", date="1936.1.1.12"):
    """写 common/bookmarks。没有剧本的话游戏会跳过剧本选择，
    直接拿默认局面开局，玩家看不出这是个新世界。"""
    d = os.path.join(mod_dir, "common", "bookmarks")
    os.makedirs(d, exist_ok=True)
    body = ['bookmarks = {',
            '\tbookmark = {',
            '\t\tname = "ZZ_EDITOR_BOOKMARK"',
            '\t\tdesc = "ZZ_EDITOR_BOOKMARK_DESC"',
            '\t\tdate = %s' % date,
            '\t\tpicture = "GFX_select_date_1936"',
            '\t\tdefault_country = "%s"' % tag,
            '\t\tfilters = { new_content continent }',
            '\t\tdefault = yes',
            '',
            '\t\t"%s" = {' % tag,
            '\t\t\thistory = "ZZ_EDITOR_BOOKMARK_COUNTRY"',
            '\t\t\tideology = neutrality',
            '\t\t}',
            '\t}',
            '}',
            '']
    _w(os.path.join(d, "zz_editor_bookmarks.txt"), "\n".join(body))
    return "common/bookmarks/zz_editor_bookmarks.txt"


def write_ai_stubs(mod_dir, tag="ZZZ"):
    """被 replace 掉的 AI 目录里塞一个占位文件。

    **已被 qa/world_stubs.py 取代**，保留只为兼容老脚本调用。
    新代码请用 world_stubs.write_all（清单更全，且带 national_focus 的默认树）。

    目录整个被卸载后如果连文件都没有，不同版本表现不一样。

    ai_strategy 不能写 `ai_strategy = { }`：那样引擎会把块名当成策略名，
    报 "AI strategy ai_strategy with missing or empty enable trigger"。
    原版结构是「顶层 = 策略名，ai_strategy = { type id value } 嵌在里面」，
    这里写一条永不启用的合法策略（enable 恒假、abort 恒真）。
    """
    made = []
    stub = (
        "zz_editor_stub = {\n"
        "\tallowed = {\n\t\talways = no\n\t}\n"
        "\tenable = {\n\t\talways = no\n\t}\n"
        "\tabort = {\n\t\talways = yes\n\t}\n"
        "\tai_strategy = {\n\t\ttype = alliance\n\t\tid = \"%s\"\n\t\tvalue = 0\n\t}\n"
        "}\n" % tag)
    for sub, head in (
            ("common/ai_strategy", stub),
            ("common/ai_strategy_plans", ""),
            ("common/ai_areas", ""),
            ("common/ai_war_goals", ""),
            ("common/ai_templates", ""),
            ("common/ai_equipment", ""),
            ("common/ai_focuses", ""),
    ):
        d = os.path.join(mod_dir, sub.replace("/", os.sep))
        os.makedirs(d, exist_ok=True)
        _w(os.path.join(d, "zz_editor_placeholder.txt"), head)
        made.append(sub + "/zz_editor_placeholder.txt")
    return made


def write_localisation(mod_dir, name):
    d = os.path.join(mod_dir, "localisation")
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, "zz_editor_l_english.yml")
    io.open(p, "w", encoding="utf-8-sig", newline="").write(
        "l_english:\n"
        ' STATE_1:0 "起始州"\n'
    )


def build(mod_dir, labels, mod_name="雪绒地图测试", tag="ZZZ", per_state=8,
          sea_ids=None, n_focus=24, gen_focus=True, gen_event=True):
    """在 mod_dir 下补齐所有能让游戏启动的文件。

    `gen_focus` / `n_focus`：A2 起默认生成一棵真国策树（带 default = yes），
    关掉就退回 A1 的单节点占位。`gen_event` 同理（开局弹一个事件）。
    """
    made = []
    if not mod_dir:
        return {"ok": False, "msg": "没给目录", "made": made}
    os.makedirs(mod_dir, exist_ok=True)
    write_descriptor(mod_dir, mod_name)
    made.append("descriptor.mod")
    write_country_tags(mod_dir, tag)
    made.append("common/country_tags/zz_editor_tags.txt")
    write_country_def(mod_dir, tag)
    made.append("common/countries/%s.txt" % tag)
    write_country_history(mod_dir, tag)
    made.append("history/countries/%s - Test.txt" % tag)
    ns, smap = write_states(mod_dir, labels, tag, per_state, sea_ids=sea_ids,
                            with_map=True)
    made.append("history/states/ × %d" % ns)
    write_localisation(mod_dir, mod_name)
    made.append("localisation/")

    # 按 East Showdown 的路子补齐：OOB / 剧本 / 各目录占位
    try:
        # 开局部队放在第一个州的第一块地上（不能写死 1：省 1 可能是海）
        first_prov = smap[0][1][0] if smap and smap[0][1] else 1
        made.append(write_units(mod_dir, tag, [first_prov]))
    except Exception:
        pass
    try:
        made.append(write_bookmarks(mod_dir, mod_name, tag))
    except Exception:
        pass
    # 国家领袖：common/characters 被整目录屏蔽，不写就没有领袖，
    # 选国家界面的「选择国家」会点了没反应
    leader_loc = []
    try:
        import world_leader
        lr = world_leader.write(mod_dir, tag,
                               leader_name=(mod_name or "新世界") + "领袖")
        leader_loc = lr["loc"]
        made.append(lr["path"])
    except Exception:
        pass

    # A2：真国策树 + 真开局事件（先算好，下面当占位内容写进去）
    focus_text, focus_loc, ev_text, oa_text, ev_loc = None, [], None, None, []
    if gen_focus:
        try:
            import focus_gen
            fr = focus_gen.build(tag=tag, n_focus=n_focus)
            focus_text, focus_loc = fr["text"], fr["loc"]
            made.append("国策树 × %d 节点" % len(fr["nodes"]))
        except Exception:
            pass
    if gen_event:
        try:
            import world_events
            er = world_events.build(tag=tag)
            ev_text, oa_text, ev_loc = er["events"], er["on_actions"], er["loc"]
            made.append("开局事件 " + er["event_id"])
        except Exception:
            pass

    # 被 replace 的每个目录都必须有东西，尤其 national_focus 要带 default = yes
    try:
        ov = {}
        if focus_text:
            ov["common/national_focus"] = focus_text
        if ev_text:
            ov["events"] = ev_text
        if oa_text:
            ov["common/on_actions"] = oa_text
        made.extend(world_stubs.write_all(mod_dir, tag, overrides=ov))
    except Exception as e:
        return {"ok": False, "states": ns, "made": made,
                "msg": "写占位失败：%s" % e}
    # 补给区/补给节点要按真实州号写，必须等地建完
    try:
        import mapgen_write as _mgw
        _mgw.write_supply_graph(os.path.join(mod_dir, "map"), smap)
        made.append("map/supplyareas + supply_nodes.txt")
    except Exception:
        pass

    # buildings.txt 要按州摆落点，同样得等州建完
    try:
        import mapgen_write as _mgw
        cen = mgx.centroids(labels)
        cen = {int(k): (float(v[0]), float(v[1])) for k, v in cen.items()
               if int(k) > 0}
        nb = _mgw.write_buildings(os.path.join(mod_dir, "map"), cen, smap)
        made.append("map/buildings.txt × %d 行" % nb)
    except Exception:
        pass

    # 世界本地化：国名 / 州名 / 国策名 / 事件文本
    try:
        import world_loc
        entries = (world_loc.country_entries(tag, mod_name)
                   + world_loc.state_entries([s for s, _p in smap])
                   + focus_loc + ev_loc + leader_loc)
        n_loc = world_loc.write(mod_dir, entries)
        made.append("本地化 × %d 条" % n_loc)
    except Exception:
        pass

    problems = world_stubs.check(mod_dir, dirs=REPLACE_DIRS)
    fatal = [p for p in problems if p["level"] == "error"]
    return {"ok": not fatal, "states": ns, "made": made,
            "problems": problems,
            "msg": ("骨架完成：%d 个州（占位 %d 个目录）" % (ns, len(REPLACE_DIRS)))
                   if not fatal else
                   ("骨架有 %d 处硬伤：%s" % (len(fatal), fatal[0]["dir"]))}
