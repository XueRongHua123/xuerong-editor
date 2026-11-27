# -*- coding: utf-8 -*-
"""全局状态的唯一声明处（P0-1 铺路版）。

为什么单独一个模块
------------------
`focus_editor.py` 有两万行、510 个顶层函数，所有 loader 都往同一批容器里写。
拆模块时最怕的不是「函数搬不过去」，而是「同一个东西存了两份」：
A 模块 import 了一份快照，B 模块改了原对象，A 永远看不到。

所以先规定三条规则，P0-2 起所有迁移的函数都按这个来：

1. **容器只改内容，不重新赋值。**
   用 `ROOTS.append(...)` / `ROOTS[:] = [...]` / `DICT.update(...)` / `DICT.clear()`，
   不要 `ROOTS = [...]`。重新赋值只改当前模块自己的名字，别的模块看到的还是旧对象。

2. **标量（GAME 之类）不要 `from ... import GAME`。**
   一律 `state.game()` 读、`state.set_game(v)` 写。

3. **迁移期以门面为准。**
   `focus_editor.py` 现在仍是这些变量的实际持有者，而且外部脚本会直接
   `fe.ROOTS = [root]`（`qa/regress_all.py` 就这么干）。所以 accessor 一律
   **先读门面模块的同名属性**，门面没加载（纯模块单测、打包后拆分）才回落到本模块。
   这样「外部重新赋值门面」不会让迁移中的模块读到过期数据。

`focus_editor.reload_data()` 目前用 `TREES = {}` 这种重新赋值写法（669-682 行）。
P0-2 里会改成 `TREES.clear()`，那之后本模块才真正成为唯一持有者；
在那之前 accessor 的门面优先策略保证两边一致。
"""
import os
import sys

# ---------------------------------------------------------------- 容器
ROOTS = []          # 已加载的 mod 根目录（按加载顺序，后面的覆盖前面的）
TREES = {}          # 国策树 id -> 树（根目录里的 focus_tree）
TREE_ORDER = []     # 展示顺序
LOC = {}            # 本地化 key -> 文本
CHANGED = {}        # 绝对路径 -> 相对路径（导出覆盖包用）
SHARED_FOCUSES = []
EQUIPMENTS = {}
TECHS = {}
EVENTS = {}
IDEAS = {}
MODULES = {}
ORGS = {}
COUNTRIES = {}
STATES = {}
HISTORY = {}        # 绝对路径 -> {"undo": [...], "redo": [...]}
PROV_RGB = {}       # 省份 id -> (r, g, b)，来自 definition.csv
SPRITE_MAP = {}
ICONS = {}
EQUIP_ICONS = {}
TECH_ICONS = {}
OPTIONS = {"follow_deps": True, "follow_launcher": False, "game_dir": ""}
LOAD_PROGRESS = {"active": False, "stage": "", "sub": "", "pct": 0, "t": 0.0}

# ---------------------------------------------------------------- 标量
GAME = ""

_FACADE = "focus_editor"


def _facade():
    """门面模块对象；没加载（或已完全迁移）时返回 None。

    注意 `python focus_editor.py` 直接运行时，模块名是 `__main__`，
    `sys.modules["focus_editor"]` 不存在——只认前者会让 accessor 全部回落，
    表现为「GAME 是空串 → is_under_game 把 cwd 当游戏目录 → 自己的 mod 被判只读」。
    打包成 exe 后同样是 __main__，但 `__file__` 是 exe 路径（`xxx.exe`）而不是
    `focus_editor.py`——只按 basename 判断，同一个故障会在 exe 里重演。
    所以再加两条：(a) `sys.frozen` 为真；(b) `__main__` 真的带着门面的容器属性
    （`ROOTS` list + `TREES` dict），后者不依赖任何打包标记，最稳。
    """
    m = sys.modules.get(_FACADE)
    if m is not None:
        return m
    m = sys.modules.get("__main__")
    if m is None:
        return None
    path = getattr(m, "__file__", "") or ""
    if path and os.path.basename(path).lower() == "focus_editor.py":
        return m
    if getattr(sys, "frozen", False):
        return m
    if isinstance(getattr(m, "ROOTS", None), list) and isinstance(getattr(m, "TREES", None), dict):
        return m
    return None


def _prefer(name, fallback, types):
    """门面优先取同名属性，类型不对就回落。"""
    m = _facade()
    if m is not None:
        v = getattr(m, name, None)
        if isinstance(v, types):
            return v
    return fallback


def roots():
    return _prefer("ROOTS", ROOTS, list)


def trees():
    return _prefer("TREES", TREES, dict)


def loc():
    return _prefer("LOC", LOC, dict)


def options():
    return _prefer("OPTIONS", OPTIONS, dict)


def tree_order():
    return _prefer("TREE_ORDER", TREE_ORDER, list)


def ideas():
    return _prefer("IDEAS", IDEAS, dict)


def shared_focuses():
    return _prefer("SHARED_FOCUSES", SHARED_FOCUSES, list)


def equipments():
    return _prefer("EQUIPMENTS", EQUIPMENTS, dict)


def techs():
    return _prefer("TECHS", TECHS, dict)


def events():
    return _prefer("EVENTS", EVENTS, dict)


def modules():
    return _prefer("MODULES", MODULES, dict)


def orgs():
    return _prefer("ORGS", ORGS, dict)


LOC_EDITS = {}


def loc_edits():
    return _prefer("LOC_EDITS", LOC_EDITS, dict)


def countries():
    return _prefer("COUNTRIES", COUNTRIES, dict)


def states():
    return _prefer("STATES", STATES, dict)


def changed():
    return _prefer("CHANGED", CHANGED, dict)


LAST_FILE = ""


def last_file():
    return _prefer("LAST_FILE", LAST_FILE, str)


def set_last_file(v):
    global LAST_FILE
    LAST_FILE = v or ""
    m = _facade()
    if m is not None:
        try:
            m.LAST_FILE = LAST_FILE
        except Exception:
            pass


def history():
    return _prefer("HISTORY", HISTORY, dict)


def prov_rgb():
    return _prefer("PROV_RGB", PROV_RGB, dict)


# ---- 2C：图标索引三张表与精灵映射（原来只在门面里，handlers 只能经门面读）----
def icons():
    return _prefer("ICONS", ICONS, dict)


def equip_icons():
    return _prefer("EQUIP_ICONS", EQUIP_ICONS, dict)


def tech_icons():
    return _prefer("TECH_ICONS", TECH_ICONS, dict)


def sprite_map():
    return _prefer("SPRITE_MAP", SPRITE_MAP, dict)


OUTPUT_MODE = False
OUTPUT_ROOT = ""


def _app_dir():
    """本文件往上两级（work/）；打包后会被门面用 set_output_root 覆盖。"""
    import os
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def output_mode():
    return bool(_prefer("OUTPUT_MODE", OUTPUT_MODE, bool))


def set_output_mode(v):
    global OUTPUT_MODE
    OUTPUT_MODE = bool(v)
    m = _facade()
    if m is not None:
        try:
            m.OUTPUT_MODE = OUTPUT_MODE
        except Exception:
            pass


def output_root():
    v = _prefer("OUTPUT_ROOT", "", str)
    return v or globals().get("OUTPUT_ROOT") or __import__("os").path.join(_app_dir(), "output")


def set_output_root(v):
    global OUTPUT_ROOT
    OUTPUT_ROOT = v or ""
    m = _facade()
    if m is not None:
        try:
            m.OUTPUT_ROOT = OUTPUT_ROOT
        except Exception:
            pass


def progress():
    return _prefer("LOAD_PROGRESS", LOAD_PROGRESS, dict)


def game():
    return _prefer("GAME", GAME, str)


def set_game(v):
    """写 GAME。注意：同时写门面，否则门面里的旧值会把这里盖掉（见 module doc 第 3 条）。"""
    global GAME
    GAME = v or ""
    m = _facade()
    if m is not None:
        try:
            m.GAME = GAME
        except Exception:
            pass


def bind_facade():
    """门面加载完自己的变量后调用一次：把门面的容器对象挂进本模块。

    只挂**对象身份**，不拷贝内容——之后 `state.ROOTS is fe.ROOTS` 为真，
    谁 append 都看得见。P0-2 起由 `focus_editor` 在模块尾部调用。
    """
    m = _facade()
    if m is None:
        return False
    for name, typ in (_CONTAINERS):
        v = getattr(m, name, None)
        if isinstance(v, typ):
            globals()[name] = v
    g = getattr(m, "GAME", None)
    if isinstance(g, str):
        globals()["GAME"] = g
    return True


_CONTAINERS = (
    ("ROOTS", list), ("TREE_ORDER", list), ("SHARED_FOCUSES", list),
    ("TREES", dict), ("LOC", dict), ("CHANGED", dict), ("EQUIPMENTS", dict),
    ("TECHS", dict), ("EVENTS", dict), ("IDEAS", dict), ("MODULES", dict),
    ("ORGS", dict), ("COUNTRIES", dict), ("STATES", dict), ("HISTORY", dict),
    ("PROV_RGB", dict), ("SPRITE_MAP", dict), ("ICONS", dict),
    ("EQUIP_ICONS", dict), ("TECH_ICONS", dict), ("OPTIONS", dict),
    ("LOAD_PROGRESS", dict), ("OUTPUT_MODE", bool), ("OUTPUT_ROOT", str), ("LAST_FILE", str), ("LOC_EDITS", dict),
)

# ---------------------------------------------------------------- 地图域容器（P2-map）
# 地图这一域的状态特别散（17 个：资产名单、缓存、编辑会话、河流撤销…），
# 与其给每个都写一对 accessor，不如统一走 "名字 -> 值" 的槽位：
#   读：state.map_var("PROV_RGB")      写：state.set_map_var("PROV_RGB", {})
# 注意：槽位里装的是容器对象时，原地改（d[k]=v / .append）不需要 set；
# 只有「整个换掉」才需要 set_map_var，否则各模块会各拿一份旧对象。
_MAP_VARS = {
    "MAP_ASSETS": (),
    "MAP_CACHE_DIR": "",
    "MAP_EDIT": None,
    "MAP_UNDO_DIR": "",
    "PROV_RGB": {},
    "RIVER_KINDS": (),
    "RIVER_KIND_IDX": {},
    "RIVER_LAND": 255,
    "RIVER_SEA": 254,
    "_NB_CACHE": {},
    "_REFINE_IDS_CACHE": {},
    "_RIVER_LAST": None,
    "_RIVER_UNDO": None,
    "MAP_PALETTE": (),
    "_DEF_RGB_CACHE": {},
    "_PROV_RGB_CACHE": {},
    "_REGION_CACHE": {},
}


def map_var(name):
    return _MAP_VARS[name]


def set_map_var(name, val):
    _MAP_VARS[name] = val


# ---------------------------------------------------------------- 启动期路径槽位（2C）
# RES_DIR / ICON_DIR / INDEX 都是启动时算一次的路径：RES_DIR 看 sys._MEIPASS（打包后是解压
# 目录），ICON_DIR 跟着 WORK，INDEX 跟着 RES_DIR。它们只在门面里算得出（依赖 FROZEN / APP_DIR
# 那一串），但 handlers 要读（静态资源目录、首页模板路径），所以放槽位里由门面写一次。
#
# 和 _MAP_VARS 的区别：这些**只在启动时写一次**，运行期不变，所以不给 setter 之外的入口，
# 也不参与缓存失效判断。
_PATHS = {
    "RES_DIR": "",
    "ICON_DIR": "",
    "INDEX": "",
}


def path_var(name):
    return _PATHS[name]


def set_path_var(name, val):
    _PATHS[name] = val or ""


# ---------------------------------------------------------------- 州/省份常量（P2-state）
# 原来定义在 focus_editor.py，model/state.py 也要用；挪到这里一处定义，
# 门面顶部 from xuerong.state import ... 引回去。
STATE_CATEGORIES = ("wasteland", "enclave", "tiny_island", "small_island", "pastoral",
                    "rural", "town", "large_town", "city", "large_city",
                    "metropolis", "megalopolis")

STATE_BUILDINGS = ("infrastructure", "arms_factory", "industrial_complex", "dockyard",
                   "air_base", "anti_air_building", "radar_station", "synthetic_refinery",
                   "fuel_silo", "rocket_site", "nuclear_reactor", "naval_base",
                   "naval_supply_hub")

STATE_BUILDING_META = (
    ("infrastructure",     "基础设施",      5, False),
    ("industrial_complex", "民用工厂",      20, False),
    ("arms_factory",       "军工厂",        20, False),
    ("dockyard",           "船坞",          20, True),
    ("naval_base",         "海军基地",      10, True),
    ("air_base",           "空军基地",      10, False),
    ("anti_air_building",  "防空炮",         5, False),
    ("radar_station",      "雷达站",         6, False),
    ("naval_supply_hub",   "海军补给中心",    3, True),
    ("fuel_silo",          "燃料仓",         3, False),
    ("synthetic_refinery", "合成炼油厂",      3, False),
)

PROV_BUILDING_META = (
    ("bunker",         "陆上要塞", 10),
    ("coastal_bunker", "海岸要塞", 10),
    ("naval_facility", "海军设施",  3),
    ("land_facility",  "陆军设施",  3),
    ("air_facility",   "空军设施",  3),
)

RESOURCE_META = (
    ("oil",       "石油", "原版常见 0–60"),
    ("rubber",    "橡胶", "原版常见 0–40"),
    ("steel",     "钢铁", "原版常见 0–80"),
    ("aluminium", "铝",   "原版常见 0–60"),
    ("tungsten",  "钨",   "原版常见 0–40"),
    ("chromium",  "铬",   "原版常见 0–40"),
)

STATE_RESOURCES = ("oil", "rubber", "steel", "aluminium", "tungsten", "chromium")


# ---------------------------------------------------------------- 决议常量（P2-rest/decision）
# 两个白名单都只读，只在 load_decisions / decision_set 里用，所以不给访问器。
DECISION_SKIP = ("ai_will_do", "modifier", "available", "visible", "complete_effect",
                 "remove_effect", "cancel_effect", "timeout_effect", "target_trigger",
                 "target_array", "targets", "custom_effect_tooltip", "highlight_states",
                 "state_target", "news_event", "scripted_effect", "selectable_mission")

DECISION_SCALARS = ("icon", "priority", "cost", "fire_only_once", "days_remove",
                    "days_re_enable", "days_mission_timeout", "activation",
                    "selectable_mission", "target_array", "target_trigger",
                    "state_target", "is_good", "news_event", "modifier")


# ---------------------------------------------------------------- 人物常量（P2-rest/character）
# 人物类型 → 块名；头像尺寸任务书写了「小头像 64x64」，实际大图是 156x210（不是正方形），
# portrait_import 按这四个值算画布，别顺手「修正」成正方形。
CHAR_TYPES = ("field_marshal", "corps_commander", "country_leader", "operative",
              "navy_leader", "advisor", "scientist")

PORTRAIT_W, PORTRAIT_H = 156, 210
PORTRAIT_SMALL = 64


# ---------------------------------------------------------------- 开局日期（P2-state）
START_DATE = (1936, 1, 1)


def start_date():
    return _prefer("START_DATE", START_DATE, tuple)


def set_start_date(v):
    global START_DATE
    START_DATE = tuple(v or (1936, 1, 1))
    m = _facade()
    if m is not None:
        try:
            m.START_DATE = START_DATE
        except Exception:
            pass


# ---------------------------------------------------------------- 写盘提示（P2-state）
# "这个目录的改动会落到哪" 的一句话说明，state_save 写进去，别的域也会写。
_LAYER_HINT = {}


def layer_hint():
    return _LAYER_HINT
