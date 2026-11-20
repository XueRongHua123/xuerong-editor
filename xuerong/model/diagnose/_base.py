# -*- coding: utf-8 -*-
"""共用小工具：finding 构造、脚本化名字判定、地图检查跳过。

`_is_skip_block` 不在这里：它依赖 schema 层的块名常量，放在那边才能让
依赖单向（schema → _base），见 schema.py 的说明。
"""

import os


def _finding(code, severity, msg, file="", line=0, excerpt="", repair="", fix=None):
    """一条诊断结果。

    fix 非空表示这条 finding 有可执行的动作（诊断面板会渲染成按钮）：

        {"kind": "replace_dangling",        动作类型
         "sub": "common/ideas",             出问题的目录（被 replace 掉的那个）
         "subs": ["common/ideas", ...],     同一行里涉及的多个被 replace 目录
         "ref_dir": "common/achievements",  引用方目录（已去掉 vanilla/ 前缀）
         "options": ["drop_replace", "adopt_ref_dir", "ignore"]}

    空 dict 和不传等价，前端按「没有按钮」处理。
    """
    return {"code": code, "severity": severity, "msg": msg,
            "file": file, "line": line or 0,
            "excerpt": (excerpt or "").strip()[:200], "repair": repair,
            "fix": fix or {}}


def _looks_like_scripted(name):
    """像 mod 自定义脚本化效果/触发器的名字。

    这类东西在 scripted_effects / scripted_triggers 里定义，规则文件里没有，
    命名上通常是「大写 tag 前缀 + 小写描述」，比如 JAP_faction_demand_finalize。
    """
    if not name or len(name) < 3:
        return False
    head = name.split('_', 1)[0]
    if head.isupper() and head.isalpha() and 3 <= len(head) <= 6:
        return True            # 纯 tag 或 tag 前缀
    # 小写开头但内部带 tag 的，比如 is_raj_or_raj_inheritor
    parts = name.split('_')
    for p2 in parts:
        if p2.isupper() and p2.isalpha() and 3 <= len(p2) <= 6:
            return True
    # 以 _trigger / _effect 收尾的，多半是脚本化触发器
    return name.endswith(('_trigger', '_triggers', '_effect', '_effects'))


def _map_diag_skip(msg, excerpt="", repair=""):
    """地图检查没跑成时的那一条诊断。

    统一口径：severity 恒为 warning，msg 里必带「未检查」，因为诊断面板把
    「零条 finding」渲染成"没有发现问题"——缺库时返回空列表等于告诉用户地图没问题。
    """
    return _finding("map.format.skipped", "warning", msg,
                    os.path.join("map", "default.map"), 0, excerpt, repair)

