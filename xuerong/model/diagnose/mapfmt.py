# -*- coding: utf-8 -*-
"""地图格式诊断：map_diag 依赖识别与逐像素检查。"""

import os

from xuerong.core.paths import _top_mod, mod_layers, qa_dir as _qa_dir
from xuerong.model.diagnose._base import _finding, _map_diag_skip


_MAP_DIAG_FILES = {
    1: "default.map", 2: "provinces.bmp", 3: "provinces.bmp",
    4: "definition.csv", 5: "definition.csv", 6: "definition.csv",
    7: "definition.csv", 8: "definition.csv", 9: "provinces.bmp",
    10: "continent.txt", 11: "definition.csv", 12: "strategicregions",
}


# map_diag 顶层把 numpy / PIL 的 import 吞成了 np=None / Image=None（它要能单独跑），
# 所以「import map_diag 成功」不等于「检查能跑」。
# np=None 会让 diagnose() 在逐像素那一段抛 AttributeError（'NoneType' has no
# attribute 'frombuffer'），报出来的错跟地图本身毫无关系——必须先单独识别出来。
# Image=None 只降级（24 位图有手写兜底，8 位索引图由它自己出 WARN），不算硬失败。
_MAP_DIAG_HARD_DEPS = (("np", "numpy"),)


def _diag_map_format(root, own_only=False):
    """map/ 目录格式体检：这一项回答"这张地图能不能进游戏"。

    查的是 HOI4 地图加载期的硬约束（尺寸 256 倍数、definition.csv 行尾与列、
    大洲 1..N、continent.txt 是纯列表、海必须是省、省必须归属战略区）。
    判断依据与引擎一致：同一个最小地图，这里报的 FAIL 就是 error.log 里报的那几条。

    实现在 qa/map_diag.py，两边共用一套规则，改一处两边都变。

    检查跑不起来（缺 numpy / map_diag 加载失败 / 它自己抛异常）时**不是**返回空列表，
    而是产出一条 "map.format.skipped" 的 warning：空列表会被面板当"没有发现问题"。
    """
    out = []
    if own_only:
        top = _top_mod(root) or root
        top_map = os.path.join(top, "map") if top else ""
        if not (top_map and os.path.isdir(top_map) and any(
            os.path.isfile(os.path.join(top_map, f))
            for f in ("provinces.bmp", "definition.csv", "default.map", "continent.txt")
        )):
            return out
    # 先定位 map/：没有 provinces.bmp 就没有检查对象，这时静默返回才是对的
    # ——"没有地图可检查"和"地图检查没跑成"是两件不同的事，前者不该出诊断。
    mp = None
    try:
        for b in reversed(mod_layers(root) or [root]):
            cand = os.path.join(b, "map")
            if os.path.isfile(os.path.join(cand, "provinces.bmp")):
                mp = cand
                break
    except Exception as e:
        # 叠加链本身取不出来时定位不到 map/，这与"没有地图"不同：是检查根本没开始。
        # 静默返回空列表会让面板显示"没有发现问题"。
        out.append(_map_diag_skip(
            "地图格式检查未执行（未检查）：解析叠加链时出错 %s: %s，"
            "无法定位 map 目录。这条不代表地图没问题。"
            % (e.__class__.__name__, e),
            "root：%s" % root))
        return out
    if not mp:
        return out

    try:
        import sys as _sys
        _qa = _qa_dir()
        if _qa not in _sys.path:
            _sys.path.insert(0, _qa)
        import map_diag
    except ImportError as e:
        # 缺 numpy 走不到这里（map_diag 自己 try 掉了），到这里是真的找不到 qa/map_diag.py，
        # 或者它依赖的 stdlib 之外的东西缺失。异常里的 name 就是那个模块名。
        name = getattr(e, "name", "") or ""
        out.append(_map_diag_skip(
            "地图格式检查未执行（未检查）：缺少模块「%s」，qa/map_diag.py 加载失败。"
            "这条不代表地图没问题。" % (name or str(e)),
            "map 目录：%s" % mp,
            "确认安装包里带 qa/ 目录（打包用 --add-data 带 qa）"))
        return out
    except Exception as e:
        out.append(_map_diag_skip(
            "地图格式检查未执行（未检查）：加载 qa/map_diag.py 时出错 %s: %s。"
            "这条不代表地图没问题。" % (e.__class__.__name__, e),
            "map 目录：%s" % mp))
        return out

    lost = [nm for attr, nm in _MAP_DIAG_HARD_DEPS if getattr(map_diag, attr, None) is None]
    if lost:
        # 逐像素那一段（孤儿色、空省、海省统计、rivers/terrain/cities 方向）
        # 全压在 numpy 上，缺库时 diagnose() 直接死在 np.frombuffer。
        out.append(_map_diag_skip(
            "地图格式检查未执行（未检查）：缺少 %s，逐像素检查（孤儿色、空省、"
            "海省统计、rivers/terrain/cities 方向）全部跳过。这条不代表地图没问题。"
            % " / ".join(lost),
            "map 目录：%s" % mp,
            "pip install numpy；发行版请用带 numpy 的安装包"))
        return out

    try:
        res = map_diag.diagnose(mp)
    except ImportError as e:
        # map_diag 内部还有几处函数内的延迟 import（比如按需读 csv），
        # 缺模块时它会在这里抛，而不是在 import map_diag 那一行。
        name = getattr(e, "name", "") or ""
        out.append(_map_diag_skip(
            "地图格式检查中断（未完成）：检查过程缺少模块「%s」。"
            "这条不代表地图没问题。" % (name or str(e)),
            "map 目录：%s" % mp,
            "补齐该模块后重跑；发行版请用带 numpy 的安装包"))
        return out
    except Exception as e:
        out.append(_map_diag_skip(
            "地图格式检查中断（未完成）：map_diag.diagnose() 抛出 %s: %s。"
            "这条不代表地图没问题。" % (e.__class__.__name__, e),
            "map 目录：%s" % mp))
        return out
    for it in res.get("items", []):
        if it.get("level") == "PASS":
            continue
        fn = _MAP_DIAG_FILES.get(it.get("id")) or "provinces.bmp"
        msg = it.get("title") or ""
        if it.get("detail"):
            msg = msg + "：" + it["detail"]
        out.append(_finding(
            "map.format.%d" % int(it.get("id") or 0),
            "error" if it.get("level") == "FAIL" else "warning",
            msg, os.path.join("map", fn), 0, "", ""))
    return out
