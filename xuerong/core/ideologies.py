# -*- coding: utf-8 -*-
"""意识形态名加载（core 层只读：供 model.world / diagnose 等跨层复用）。

只依赖标准库、xuerong.state、xuerong.core.paths、xuerong.core.text，
严守 qa/_check_import_boundary.py 的 core 分层约束。
"""
import os

from xuerong import state
from xuerong.core.paths import _pick, effective_layer_files
from xuerong.core.text import _read_text, find_blocks, top_items

DEFAULT_IDEOLOGIES = ("democratic", "fascism", "communism", "neutrality")
_IDEOLOGIES_CACHE = {"key": None, "items": list(DEFAULT_IDEOLOGIES)}


def load_ideology_names(root=None):
    """从叠加链 common/ideologies/*.txt 解析顶层意识形态规范名列表。

    带 (abspath, mtime) 缓存；解析结果为空或目录缺失时回退原版 4 意识形态。
    """
    cand_roots = []
    if root:
        cand_roots.append(root)
    else:
        picked = _pick(None)
        if picked:
            cand_roots.append(picked)
        for rr in reversed(state.roots() or []):
            if rr and rr not in cand_roots:
                cand_roots.append(rr)
        gdir = state.game()
        if not cand_roots and gdir and os.path.isdir(gdir):
            cand_roots.append(gdir)
    if not cand_roots:
        return list(DEFAULT_IDEOLOGIES)

    pairs = []
    seen_fn = set()
    for cr in cand_roots:
        try:
            got = list(effective_layer_files("common/ideologies", cr))
        except Exception:
            got = []
        # effective_layer_files 返回底层 → 顶层；多 root 汇总时先取顶层同名文件
        for _b, d, fn in reversed(got):
            fk = fn.lower()
            if fk in seen_fn:
                continue
            seen_fn.add(fk)
            pairs.append((_b, d, fn))
    pairs.reverse()
    if not pairs:
        return list(DEFAULT_IDEOLOGIES)

    sig = []
    for _b, d, fn in pairs:
        fp = os.path.join(d, fn)
        try:
            mt = os.path.getmtime(fp)
        except Exception:
            mt = 0
        sig.append((os.path.abspath(fp), mt))
    key = tuple(sig)
    if _IDEOLOGIES_CACHE.get("key") == key:
        return list(_IDEOLOGIES_CACHE["items"])

    ides = []
    seen = set()
    for _b, d, fn in pairs:
        fp = os.path.join(d, fn)
        try:
            text = _read_text(fp)
        except Exception:
            continue
        for _a, _e, ibody in find_blocks(text, "ideologies"):
            for k, _v, hb in top_items(ibody):
                if not hb:
                    continue
                kl = k.strip()
                if kl and kl.lower() not in seen:
                    seen.add(kl.lower())
                    ides.append(kl)
    if not ides:
        ides = list(DEFAULT_IDEOLOGIES)
    _IDEOLOGIES_CACHE["key"] = key
    _IDEOLOGIES_CACHE["items"] = list(ides)
    return list(ides)
