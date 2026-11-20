# -*- coding: utf-8 -*-
"""国策树生成器：给新建的世界造一棵「有事可做」的树。

为什么需要它
------------
A1 阶段只放了一棵带 `default = yes` 的单节点占位树 —— 那是为了不崩（见
`work/HANDOVER_WORLD.md`）。进游戏之后玩家没有第二个节点可点，等于没事可做。
A2 要的是「点进去有事干」：15–30 个节点、有前置、奖励看得见。

三条硬约束
----------
1. **必须有 `default = yes`**：丢了就回到 A1 那次的崩溃（`Loaded N provinces` 之后
   1–2 秒访问违例，error.log 无记录）
2. **图标必须是真实存在的 sprite**：`GFX_goal_generic_*` 才对，写成
   `GFX_focus_generic_*` 不崩，但界面上是一块空白。本文件只从核对过的池子里取
3. **`prerequisite` 只能指向前一层**：互相指或指后面会让界面报环、点击无响应

坐标约定
--------
`x` / `y` 是国策树网格，1 格 = 96×130 px。原版惯例 x 步长 2、y 步长 2，
这里照做：层与层之间 y+2，同层横向隔 2 格，多出来的节点自动居中。

用法
----
    import focus_gen
    t = focus_gen.build(tag="ZZV", n_focus=24)
    t["text"]        # 写进 common/national_focus/zz_editor_stub.txt
    t["loc"]         # [(key, 中文), ...] 交给 world_loc.write()
    t["nodes"]       # 结构信息，验收脚本用
"""
import io
import os

# 只放核对过的 sprite（`grep -rl 'name = "GFX_goal_generic_x"' 原版/interface/`）。
# 分组是为了让相邻节点图标不重复，看起来像原版。
ICONS = (
    "GFX_goal_generic_political_pressure",
    "GFX_goal_generic_construct_civ_factory",
    "GFX_goal_generic_army_doctrines",
    "GFX_goal_generic_production",
    "GFX_goal_generic_construct_infrastructure",
    "GFX_goal_generic_allies_build_infantry",
    "GFX_focus_research",
    "GFX_goal_generic_construct_mil_factory",
    "GFX_goal_generic_propaganda",
    "GFX_goal_generic_demand_territory",
    "GFX_goal_generic_more_territorial_claims",
)

# 奖励池：分散搭配，别全是政治点（全是同一种的话，玩家点十下等于点一下）
REWARDS = (
    "add_political_power = 80",
    "add_stability = 0.05",
    "army_experience = 15",
    "add_political_power = 120",
    "add_war_support = 0.05",
    "air_experience = 10",
    # 加建筑是州级效果，国策作用域是国家，必须套一层 capital_scope，
    # 否则报 Invalid scope type for effect（实测 2 条）
    "capital_scope = { add_building_construction = { type = industrial_complex level = 1 instant_build = yes } }",
    "navy_experience = 10",
    "add_command_power = 25",
    "army_experience = 10",
)

# 名字池：按层给不同的词，读起来像一棵树而不是批量生成物
NAMES = (
    ("稳固根基", "先把国内的局面定下来，再谈别的。"),
    ("整备行政", "把行政机器搭起来。"),
    ("重建工业", "从废墟里拉起第一条产线。"),
    ("扩充兵源", "前线要人，后方也得有人。"),
    ("恢复秩序", "秩序是一切的前提。"),
    ("技术引进", "买不到的就自己造。"),
    ("道路与铁路", "把国内的运输线接起来。"),
    ("第一个五年", "从数字开始。"),
    ("锻造陆军", "把散兵游勇编成师。"),
    ("海防建设", "海岸线不能空着。"),
    ("空军雏形", "先有飞机，再谈制空。"),
    ("军工体系", "弹药、枪械、零件，自给自足。"),
    ("对外交涉", "世界很大，邻居更重要。"),
    ("边境要塞", "把边境钉住。"),
    ("统一指挥", "令出一门。"),
    ("战略储备", "打起来就晚了。"),
    ("宣传机器", "让人相信自己在为什么而战。"),
    ("科研体系", "实验室比工厂更难建。"),
    ("动员体制", "把国家拧成一台机器。"),
    ("新世界的旗帜", "从这一刻起，这里有了名字。"),
    ("长期规划", "十年之后再说输赢。"),
    ("工业带", "一条从矿到炮的链条。"),
    ("海军的野心", "从近海开始。"),
    ("最终的答案", "该准备最坏的情况了。"),
)


def layer_plan(n):
    """把节点数拆成每层几个。第一层固定 3 个分叉，最后一层做收拢。"""
    n = max(1, int(n))
    if n <= 3:
        return [n]
    l1 = 3
    rest = n - l1
    l2 = max(2, min(9, rest // 2))
    if rest - l2 < 2:                     # 剩不下第三层了，第二层吃干净
        return [l1, rest]
    l4 = max(1, min(3, rest // 6))        # 收拢层，1–3 个
    l3 = rest - l2 - l4
    if l3 < 1:
        return [l1, rest - l4, l4] if rest - l4 > 0 else [l1, rest]
    return [l1, l2, l3, l4]


def _xs(k):
    """k 个节点横向排开，居中，步长 2。"""
    if k <= 0:
        return []
    return [-(k - 1) + 2 * i for i in range(k)]


def _parents(k, pk):
    """第 n 层的 k 个节点各自挂到上一层 pk 个节点里的哪一个。"""
    if pk <= 0:
        return [None] * k
    if k <= 1:
        return [pk // 2]
    return [int(round(i * (pk - 1) / float(k - 1))) for i in range(k)]


def build(tag="ZZV", n_focus=24, tree_id="zz_editor_tree", shape="tree"):
    """生成国策树文本与本地化。shape="chain" 时退化成单线（调试用）。"""
    tag = (tag or "ZZV").strip().upper()
    n = max(1, int(n_focus))
    if shape == "chain":
        plan = [1] * n
    else:
        plan = layer_plan(n)

    nodes = []
    prev = []           # 上一层 (id, x) 列表
    idx = 0
    y = 0
    for depth, k in enumerate(plan):
        xs = _xs(k) if k > 1 else [0]
        parents = _parents(k, len(prev))
        cur = []
        for i in range(k):
            idx += 1
            fid = "%s_%d" % (tree_id, idx)
            pidx = parents[i]
            pre = prev[pidx][0] if pidx is not None and prev else None
            name, desc = NAMES[(idx - 1) % len(NAMES)]
            if depth == 0 and k == 3 and i < 3:
                name, desc = NAMES[i]
            reward = REWARDS[(idx - 1) % len(REWARDS)]
            nodes.append({
                "id": fid, "x": xs[i], "y": y, "depth": depth,
                "name": name, "desc": desc, "prereq": pre,
                "icon": ICONS[(idx - 1) % len(ICONS)],
                "cost": 8 + depth * 4, "reward": reward,
            })
            cur.append((fid, xs[i]))
        prev = cur
        y += 2

    body = ['focus_tree = {',
            '\tid = %s' % tree_id,
            '\tcountry = {',
            '\t\tfactor = 0',
            '\t\tmodifier = {',
            '\t\t\tadd = 10',
            '\t\t\ttag = %s' % tag,
            '\t\t}',
            '\t}',
            # 这一行是 A1 崩溃的解，任何改动都不能把它删掉
            '\tdefault = yes',
            '']
    for nd in nodes:
        body.append('\tfocus = {')
        body.append('\t\tid = %s' % nd["id"])
        body.append('\t\ticon = %s' % nd["icon"])
        body.append('\t\tx = %d' % nd["x"])
        body.append('\t\ty = %d' % nd["y"])
        body.append('\t\tcost = %d' % nd["cost"])
        body.append('\t\tai_will_do = {')
        body.append('\t\t\tfactor = 20')
        body.append('\t\t}')
        if nd["prereq"]:
            body.append('\t\tprerequisite = {')
            body.append('\t\t\tfocus = %s' % nd["prereq"])
            body.append('\t\t}')
        body.append('\t\tcompletion_reward = {')
        body.append('\t\t\t%s' % nd["reward"])
        body.append('\t\t}')
        body.append('\t}')
        body.append('')
    body.append('}')
    text = "\n".join(body) + "\n"

    loc = []
    for nd in nodes:
        loc.append((nd["id"], nd["name"]))
        loc.append((nd["id"] + "_desc", nd["desc"]))
    return {"ok": True, "text": text, "loc": loc, "nodes": nodes,
            "tree_id": tree_id, "layers": plan}


def check(text, tag=None):
    """静态复查：返回问题列表，空表示合规。验收脚本和诊断器共用。"""
    out = []
    t = text or ""
    if "default = yes" not in t:
        out.append("没有 default = yes —— 进游戏必崩")
    if "focus_tree" not in t:
        out.append("没有 focus_tree 块")
    ids = __import__("re").findall(r'^\s*id = (\S+)$', t, __import__("re").M)
    if len(ids) != len(set(ids)):
        out.append("存在重复的 focus id")
    if t.count("\tfocus = {") < 1:
        out.append("一个节点都没有")
    if "GFX_focus_generic" in t:
        out.append("图标用了 GFX_focus_generic_*，界面上会是空白（应为 GFX_goal_generic_*）")
    if tag and ("tag = %s" % tag) not in t:
        out.append("country 块里没有匹配 tag")
    return out


def write(mod_dir, tag="ZZV", n_focus=24, tree_id="zz_editor_tree", shape="tree"):
    """直接写进 mod 的 common/national_focus/，返回 (路径, loc 列表, 结构)。"""
    r = build(tag=tag, n_focus=n_focus, tree_id=tree_id, shape=shape)
    d = os.path.join(mod_dir, "common", "national_focus")
    os.makedirs(d, exist_ok=True)
    try:
        import world_stubs
        fn = world_stubs.stub_name("common/national_focus")
    except Exception:
        fn = "zz_editor_focus.txt"
    p = os.path.join(d, fn)                       # 与 world_stubs 的占位同名，覆盖它
    io.open(p, "w", encoding="utf-8", newline="").write(r["text"])
    r["path"] = p
    return r
