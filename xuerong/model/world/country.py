# -*- coding: utf-8 -*-
"""国家 tag：读取 / 写回 country_tags，建国家历史。

写操作前用 _reload() 让门面刷新缓存（原文件经 _INJ 回注，现走 _inj）。
"""
import hashlib
import io
import os
import re

from xuerong import state
from xuerong.core.paths import _LAYERS_CACHE, _layer_files, _pick, mod_layers
from xuerong.core.text import _atomic_write, _bom_for, _strip_keep_len
from xuerong.model.history import snapshot
from xuerong.model.state import _states_dir_for_write
from xuerong.model.world._inj import _reload
from xuerong.model.world._write_guard import world_write_base

def load_country_tags(root=None):
    """解析 common/country_tags 里的所有 tag。

    格式：
        BET = "countries/BETA.txt"
        H00 = "countries/H00.txt"
        dynamic_tags  = yes          ← 特殊行，不是 tag
    """
    root = _pick(root)
    files, _rep = _layer_files("common/country_tags", mod_layers(root))
    out, seen = [], {}
    dyn = False
    for p in reversed(files or []):
        fn = os.path.basename(p)
        try:
            with io.open(p, encoding="utf-8-sig", errors="replace") as _fh:
                raw = _fh.read()
        except Exception:
            continue
        text = _strip_keep_len(raw)
        for ln in text.splitlines():
            s0 = ln.strip()
            if not s0 or s0.startswith("#"):
                continue
            if re.match(r'(?i)dynamic_tags\s*=\s*yes', s0):
                dyn = True
                continue
            m = re.match(r'([A-Z0-9_]{2,8})\s*=\s*"([^"]+)"', s0)
            if m:
                seen[m.group(1)] = {"tag": m.group(1), "def": m.group(2), "file": fn}
    out = sorted(seen.values(), key=lambda x: x["tag"])
    return {"ok": True, "items": out, "count": len(out), "dynamic": dyn,
            "msg": "共 %d 个 tag%s" % (len(out), "，含动态 tag 段" if dyn else "")}


def _country_tags_write_base(root):
    """common/country_tags 的写入层，拒写父 mod。

    先按传入的 root 解析叠加链，再退回全局 ROOTS。
    只看 ROOTS 的话，直接调用（脚本、world_create 这类编排）会因为没有
    全局状态而误报「找不到可写的 mod 目录」，哪怕 root 本身完全可写。
    """
    return world_write_base(root, "common/country_tags")


def country_tag_refs(root, tag):
    """统计一个 tag 在哪些地方被引用，删之前先看清楚。"""
    root = _pick(root)
    tag = (tag or "").upper()
    refs = {"states_owner": 0, "states_core": 0, "history_files": [], "trees": []}
    try:
        for sid, sty in (state.states() or {}).items():
            if (sty.get("owner") or "").upper() == tag:
                refs["states_owner"] += 1
            if tag in [x.upper() for x in (sty.get("cores") or [])]:
                refs["states_core"] += 1
    except Exception:
        pass
    try:
        files, _r = _layer_files("history/countries", mod_layers(root))
        for p in (files or []):
            fn = os.path.basename(p)
            m = re.match(r'([A-Z0-9_]{2,8})\s*-', fn.upper())
            if m and m.group(1) == tag:
                refs["history_files"].append(fn)
    except Exception:
        pass
    try:
        for tid, t in (state.trees() or {}).items():
            tags = [x.upper() for x in (t.get("country_tags") or [])]
            if tag in tags:
                refs["trees"].append(tid)
    except Exception:
        pass
    total = refs["states_owner"] + refs["states_core"] + len(refs["history_files"]) + len(refs["trees"])
    return {"tag": tag, "refs": refs, "total": total,
            "msg": "%s 被引用 %d 处（州归属 %d、核心 %d、国家历史 %d、国策树 %d）" % (
                tag, total, refs["states_owner"], refs["states_core"],
                len(refs["history_files"]), len(refs["trees"]))}


def country_tag_add(root, tag, color=None, culture="western_european_gfx"):
    """新建国家 tag。

    culture 必须在这里兜一次底：路由是 `body.get("culture")` 直传，
    前端不发这个字段时拿到 None，显式传入会盖掉默认值，下面
    `culture.replace("_gfx", "_2d")` 立刻 AttributeError → 接口 500。
    """
    culture = culture or "western_european_gfx"

    root = _pick(root)
    tag = (tag or "").upper().strip()
    if not re.match(r'^[A-Z][A-Z0-9]{1,3}$', tag):
        return {"ok": False, "msg": "tag 格式不对（1 位字母 + 1-3 位字母数字，如 GER、UNI）"}
    cur = load_country_tags(root)
    if any(x["tag"] == tag for x in cur["items"]):
        return {"ok": False, "msg": "已经有 %s 这个 tag 了" % tag}

    rgb = color
    if not rgb:
        # 用 tag 的哈希生成一个稳定颜色
        h = int(hashlib.md5(tag.encode()).hexdigest()[:6], 16)
        rgb = [60 + (h >> 16) % 160, 60 + (h >> 8) % 160, 60 + h % 160]
    try:
        rgb = [int(x) for x in rgb][:3]
        if len(rgb) != 3:
            raise ValueError
        rgb = [max(0, min(255, x)) for x in rgb]
    except Exception:
        return {"ok": False, "msg": "颜色要三个 0-255 的整数"}

    tgt, err = _country_tags_write_base(root)
    if not tgt:
        return {"ok": False, "msg": err}

    # 1) country_tags 追加
    d = os.path.join(tgt, "common", "country_tags")
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, "zz_editor_tags.txt")
    line = '%s = "countries/%s.txt"\n' % (tag, tag)
    if os.path.exists(p):
        with io.open(p, encoding="utf-8-sig", errors="replace") as _fh:
            raw = _fh.read()
        if not raw.endswith("\n"):
            raw += "\n"
        new_text = raw + line
    else:
        new_text = line
    if os.path.exists(p):
        snapshot(p)
    _atomic_write(p, _bom_for(p) + new_text.encode("utf-8"))

    # 2) common/countries 定义
    cd = os.path.join(tgt, "common", "countries")
    os.makedirs(cd, exist_ok=True)
    cp = os.path.join(cd, tag + ".txt")
    body = ("graphical_culture = %s\ngraphical_culture_2d = %s\n\n"
            "color = { %d %d %d }\n") % (
        culture, culture.replace("_gfx", "_2d"), rgb[0], rgb[1], rgb[2])
    if not os.path.exists(cp):
        _atomic_write(cp, _bom_for(cp) + body.encode("utf-8"))

    try:
        _LAYERS_CACHE.clear()
    except Exception:
        pass
    _reload()
    return {"ok": True, "tag": tag, "color": rgb, "file": "zz_editor_tags.txt",
            "msg": "已加 tag %s（颜色 %d,%d,%d，定义 countries/%s.txt）" % (
                tag, rgb[0], rgb[1], rgb[2], tag)}


def country_history_create(root, tag, capital=1, ruling_party="neutrality",
                           name=None, oob=None, research_slots=3):
    """给新 tag 写 history/countries/<TAG> - <Name>.txt。

    country_tag_add 只写 common/country_tags 和 common/countries，
    不写 history —— 新国家在游戏里就是「没有首都、没有政府、没有科技」的空壳。
    这个函数补的就是这一层，格式照原版最简国家（如 NWF）写。
    """
    root = _pick(root)
    tag = (tag or "").upper().strip()
    if not re.match(r'^[A-Z][A-Z0-9]{1,3}$', tag):
        return {"ok": False, "msg": "tag 格式不对（如 GER、UNI）"}
    top, _states = _states_dir_for_write(root)
    if not top:
        return {"ok": False, "msg": "找不到可写的 mod 目录（原版只读）"}
    try:
        cap = int(capital)
    except Exception:
        return {"ok": False, "msg": "capital 必须是省号"}

    d = os.path.join(top, "history", "countries")
    os.makedirs(d, exist_ok=True)
    # HOI4 按 tag 认国家历史、不看文件名，同一个 tag 有两个文件会互相打架。
    # 所以先按「文件名里的 tag」查重，而不是只查同名文件。
    try:
        for fn in os.listdir(d):
            if not fn.endswith(".txt"):
                continue
            head = fn.split(" ")[0].split(".")[0].strip().upper()
            if head == tag:
                return {"ok": False,
                        "msg": "这个 tag 已经有国家历史：%s" % fn}
    except Exception:
        pass
    safe = re.sub(r'[^\w\u4e00-\u9fa5-]+', "_", (name or tag))[:40]
    fname = "%s - %s.txt" % (tag, safe)
    p = os.path.join(d, fname)
    if os.path.exists(p):
        return {"ok": False, "msg": "已经存在：%s" % fname}

    body = 'capital = %d\nset_research_slots = %d\n' % (cap, int(research_slots))
    if oob:
        body += 'oob = "%s"\n' % oob
    body += (
        'set_technology = {\n\tinfantry_weapons = 1\n}\n'
        'set_politics = {\n'
        '\truling_party = %s\n'
        '\tlast_election = "1936.1.1"\n'
        '\telection_frequency = 48\n'
        '\telections_allowed = no\n'
        '}\n'
        'set_popularities = {\n'
        '\tdemocratic = 10\n'
        '\tfascism = 10\n'
        '\tcommunism = 10\n'
        '\tneutrality = 70\n'
        '}\n' % ruling_party)
    try:
        _atomic_write(p, _bom_for(p) + body.encode("utf-8"))
    except Exception as e:
        return {"ok": False, "msg": "写文件失败：%s" % e}
    _reload()
    return {"ok": True, "tag": tag,
            "file": os.path.relpath(p, top).replace(os.sep, "/"),
            "msg": "已建 %s 的国家历史（首都省 %d）" % (tag, cap)}


def country_tag_delete(root, tag):
    """删一个国家 tag（只从自己的 mod 层里摘，且要先看引用）。"""
    root = _pick(root)
    tag = (tag or "").upper().strip()
    if not tag:
        return {"ok": False, "msg": "tag 不能为空"}
    info = country_tag_refs(root, tag)
    if info["total"] > 0:
        return {"ok": False, "need_confirm": True, "refs": info,
                "msg": "%s 还被引用，直接删会留下悬空引用。%s" % (tag, info["msg"])}

    tgt, err = _country_tags_write_base(root)
    if not tgt:
        return {"ok": False, "msg": err}
    d = os.path.join(tgt, "common", "country_tags")
    if not os.path.isdir(d):
        return {"ok": False, "msg": "自己的 mod 里没有 common/country_tags，还没接管"}

    removed = False
    for fn in sorted(os.listdir(d)):
        if not fn.endswith(".txt"):
            continue
        p = os.path.join(d, fn)
        with io.open(p, encoding="utf-8-sig", errors="replace") as _fh:
            raw = _fh.read()
        pat = re.compile(r'(?m)^[ \t]*' + re.escape(tag) + r'\s*=\s*"[^"]*"[ \t]*\r?\n?')
        new_text = pat.sub('', raw)
        if new_text != raw:
            snapshot(p)
            _atomic_write(p, _bom_for(p) + new_text.encode("utf-8"))
            removed = True
            break
    if not removed:
        return {"ok": False, "msg": "自己的 mod 里没找到 %s 这一行（可能在父 mod，只读）" % tag}
    try:
        _LAYERS_CACHE.clear()
    except Exception:
        pass
    _reload()
    return {"ok": True, "tag": tag, "msg": "已删除 tag %s" % tag}
