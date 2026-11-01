# -*- coding: utf-8 -*-
"""为一个「新世界」mod 生成每个被 replace 目录的最小合法占位。

为什么需要这个模块
------------------
`replace_path` 是整体屏蔽：声明 `common/ideas` 之后，这个目录**只**从本 mod 读。
所以每声明一条，就必须在本 mod 里真的放点东西，否则引擎读到一个空目录。

2026-11-02 真机二分（46 轮）把崩溃收敛到唯一一处：

    空着 `common/national_focus` 会崩，且 error.log 一个字都不写。

机理：replace 掉国策树后，没有任何 `default = yes` 的树；开局时引擎要给
「history/countries 里没写 load_focus_tree 的国家」分配默认树，拿到空指针，
在 `Loaded N provinces` 之后 1–2 秒访问违例（异常地址每次不同，堆栈全是
PHYSFS_swapULE64，符号解析失败，没有可读信息）。

对照实验（同一套 map/history，只改 national_focus）：

| national_focus 里的东西            | 结果 |
|---|---|
| 一句话注释                         | 崩   |
| 一棵只匹配本 tag 的树              | 崩   |
| 一棵带 `default = yes` 的树        | 过   |
| 原版 generic.txt（含 default=yes） | 过   |
| 原版整套 81 个文件                 | 过   |

所以占位不是「随便写点合法语法」就够：**有的目录有硬性语义要求**。
本模块把每条要求的写法固定下来，并在 `check()` 里做静态复查。

用法
----
    import world_stubs
    world_stubs.write_all(mod_dir, tag="ZZV")
    problems = world_stubs.check(mod_dir)      # [] 表示齐了
"""
import io
import os

# 需要 replace 的目录。
#
# 清单来源：East Showdown（工坊 2948642461）的 65 条，去掉 14 条「不该 replace」的
# 一类（纯资源、以及被引用的一端），加上它漏写的 common/operation_tokens。
#
# 不 replace 的 14 条及原因：
#   music / music/hoi2 / music/hoi3       纯资源，换空 = 没有音乐
#   gfx/flags / gfx/flags/medium / small  纯资源，换空 = 全国旗空白
#   portraits / gfx/loadingscreens        纯资源
#   gfx/interface/equipmentdesigner/graphic_db  装备外观，换空 = 装备图标全没
#   interface/countrytechtreeview.gui     界面定义，换空 = 科技树界面崩
#   common/units / common/units/equipment 被引用的一端：师团模板、set_technology 全靠它
#   common/technologies                   同上，换空让 set_technology 全线失效
#   common/combat_tactics.txt             不按 id 引用，换空只可能把战斗搞坏，没有收益
REPLACE_DIRS = (
    # history：按省号/州号引用，必须整套换
    "history/countries",
    "history/states",
    "history/units",
    "history/general",
    # map 的两套按州号引用的子目录
    "map/strategicregions",
    "map/supplyareas",
    # 国策树（见模块开头：空着必崩）
    "common/national_focus",
    # 精神：遍布 add_timed_idea / has_idea，原版精神对应原版 tag
    "common/ideas",
    # 人物：原版人物挂在原版国家上
    "common/characters",
    "common/country_leader",
    "common/country_tag_aliases",
    # 决议 / 事件脚本
    "common/decisions",
    "common/decisions/categories",
    "common/on_actions",
    "common/scripted_triggers",
    "common/scripted_effects",
    "common/scripted_guis",
    "common/scripted_localisation",
    # 战术 / 情报 / 行动
    "common/abilities",
    "common/autonomous_states",
    "common/opinion_modifiers",
    "common/intelligence_agencies",
    "common/intelligence_agency_upgrades",
    "common/operations",
    "common/operation_phases",
    "common/operation_tokens",
    "common/raids",
    "common/raids/categories",
    "common/bop",
    "common/difficulty_settings",
    "common/dynamic_modifiers",
    # 军种命名（按 tag 建表，原版表里没有新 tag）
    "common/units/names",
    "common/units/names_divisions",
    "common/units/names_railway_guns",
    "common/units/names_ships",
    "common/units/codenames_operatives",
    # 军工组织 / 和平会议
    "common/military_industrial_organization/organizations",
    "common/peace_conference/ai_peace",
    "common/peace_conference/cost_modifiers",
    # AI：原版到处是 state = 1234 这种硬引用
    "common/ai_areas",
    "common/ai_equipment",
    "common/ai_focuses",
    "common/ai_navy",
    "common/ai_navy/goals",
    "common/ai_peace",
    "common/ai_strategy",
    "common/ai_strategy_plans",
    "common/ai_templates",
    # 剧本入口由我们自己写
    "common/bookmarks",
    # 事件
    "events",
)

# 需要写「块名 = { }」的目录。写成裸注释也行，但块名能让解析器明确读到空集合，
# 语义上更接近「这一类数据存在且为空」。
BLOCK_STUBS = {
    "common/abilities": "abilities",
    "common/autonomous_states": "autonomous_states",
    "common/opinion_modifiers": "opinion_modifiers",
    "common/ideas": "ideas",
    "common/on_actions": "on_actions",
    "common/operations": "operations",
    "common/raids": "raids",
    "common/bop": "bop",
    "common/dynamic_modifiers": "dynamic_modifiers",
    "common/decisions": "decisions",
    "common/decisions/categories": "decision_categories",
}

STUB_NAME = "zz_editor_stub.txt"


def focus_tree_stub(tag="ZZV", tree_id="zz_editor_tree"):
    """默认国策树。

    `default = yes` 是硬要求：没有它，引擎给无树国家分配默认树时拿到空指针，
    直接崩，而且什么都不写进 error.log。树里只有一根节点，保证结构合法。
    """
    return (
        'focus_tree = {\n'
        '\tid = %s\n'
        '\tcountry = {\n'
        '\t\tfactor = 0\n'
        '\t\tmodifier = {\n'
        '\t\t\tadd = 10\n'
        '\t\t\ttag = %s\n'
        '\t\t}\n'
        '\t}\n'
        '\tdefault = yes\n'
        '\tfocus = {\n'
        '\t\tid = %s_root\n'
        '\t\ticon = GFX_goal_generic_political_pressure\n'
        '\t\tx = 0\n'
        '\t\ty = 0\n'
        '\t\tcost = 10\n'
        '\t\tai_will_do = {\n'
        '\t\t\tfactor = 1\n'
        '\t\t}\n'
        '\t\tcompletion_reward = {\n'
        '\t\t\tadd_political_power = 5\n'
        '\t\t}\n'
        '\t}\n'
        '}\n') % (tree_id, tag, tree_id)


def _text_for(sub, tag):
    """一个目录该写什么内容。"""
    if sub == "common/national_focus":
        return focus_tree_stub(tag)
    if sub == "events":
        return "# 本项目暂时没有事件\n"
    blk = BLOCK_STUBS.get(sub)
    if blk:
        return "%s = {\n}\n" % blk
    return "# 占位：本目录被 replace_path 整体屏蔽，这里只有一个空文件\n"


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    io.open(path, "w", encoding="utf-8", newline="").write(text)


def write_all(mod_dir, tag="ZZV", dirs=None):
    """给每个目录写占位文件，返回相对路径列表。"""
    made = []
    for sub in (dirs or REPLACE_DIRS):
        p = os.path.join(mod_dir, sub.replace("/", os.sep), STUB_NAME)
        _write(p, _text_for(sub, tag))
        made.append(sub + "/" + STUB_NAME)
    return made


def check(mod_dir, dirs=None, tag=None):
    """静态复查：返回 [{"dir", "level", "msg"}]，空列表表示齐了。

    level: error（必崩或必失效）/ warning（可能不对，但不崩）
    """
    out = []
    for sub in (dirs or REPLACE_DIRS):
        d = os.path.join(mod_dir, sub.replace("/", os.sep))
        if not os.path.isdir(d):
            out.append({"dir": sub, "level": "error",
                        "msg": "声明了 replace_path 但目录不存在 —— 游戏会读到空目录"})
            continue
        files = [f for f in os.listdir(d) if f.endswith(".txt")]
        if not files:
            out.append({"dir": sub, "level": "error",
                        "msg": "目录里没有 .txt —— replace 之后这里是空的"})
            continue
        if sub == "common/national_focus":
            blob = ""
            for f in files:
                blob += io.open(os.path.join(d, f), encoding="utf-8-sig",
                                errors="replace").read()
            if "default = yes" not in blob:
                out.append({"dir": sub, "level": "error",
                            "msg": "没有 default = yes 的国策树 —— 实测进游戏必崩，"
                                   "且 error.log 无任何记录"})
            if "focus_tree" not in blob:
                out.append({"dir": sub, "level": "warning",
                            "msg": "没有任何 focus_tree，只有样式文件"})
        if sub == "common/ai_strategy":
            for f in files:
                raw = io.open(os.path.join(d, f), encoding="utf-8-sig",
                              errors="replace").read()
                if raw.strip().startswith("ai_strategy") and "zz" not in raw:
                    out.append({"dir": sub, "level": "warning",
                                "msg": "`ai_strategy = { }` 会被引擎当成策略名，"
                                       "报 missing enable trigger"})
    return out
