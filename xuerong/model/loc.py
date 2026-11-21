# -*- coding: utf-8 -*-
"""本地化写入（P0-3 B2 从 focus_editor.py 迁入）。

读本地化仍在 core/loc.py 与门面的 load_game_loc；这里只负责「写」。

依赖边界：
  · LOC / LOC_EDITS → xuerong.state
  · BOM 读写 → xuerong.core.paths
  · 写前快照 → xuerong.model.history.snapshot（同层，允许）
  · 零钩子
"""
import io
import os
import re

from xuerong import state
from xuerong.core.paths import (_read_bom_text, _write_bom_text, is_readonly_mod,
                                is_under_game, mod_layers, unique_editor_filename)
from xuerong.core.text import _atomic_write
from xuerong.model.history import snapshot


def _loc_write_pairs(root, pairs, lang="simp_chinese"):
    """把 {key: text} 写进 zz_xuerong_evtext_l_<lang>.yml（只覆盖这些键）"""
    if not pairs:
        return ""
    d = os.path.join(root, "localisation", lang)
    os.makedirs(d, exist_ok=True)
    base_fn = unique_editor_filename(root, "localisation/%s" % lang, "zz_xuerong_evtext_l_%s.yml" % lang)
    fn = os.path.join(d, base_fn)
    existing = {}
    if os.path.exists(fn):
        try:
            line_re = re.compile(r'^\s*([A-Za-z0-9_.\-]+):\d*\s+"(.*)"\s*$')
            for ln in io.open(fn, encoding="utf-8-sig", errors="replace").read().splitlines():
                m = line_re.match(ln)
                if m:
                    existing[m.group(1)] = m.group(2)
        except Exception:
            pass
    for k, v in pairs.items():
        existing[k] = str(v).replace('"', "'").replace(chr(10), "\\n")
    lines = ["l_%s:" % lang]
    for k in sorted(existing):
        lines.append(' %s:0 "%s"' % (k, existing[k]))
    _atomic_write(fn, b"\xef\xbb\xbf" + (chr(10).join(lines) + chr(10)).encode("utf-8"))
    return os.path.basename(fn)



def _write_loc(root, lang):
    d = os.path.join(root, "localisation", lang, "replace")
    os.makedirs(d, exist_ok=True)
    fn = unique_editor_filename(root, "localisation/%s/replace" % lang, "zz_focus_editor_l_%s.yml" % lang)
    path = os.path.join(d, fn)
    header = {"simp_chinese": "l_simp_chinese:", "english": "l_english:",
              "japanese": "l_japanese:"}.get(lang, "l_" + lang + ":")
    lines = [header]
    for k, v in sorted(state.loc_edits().get(lang, {}).items()):
        v = (v or "").replace("\\", "\\\\").replace('"', '\\"')
        lines.append(' %s:0 "%s"' % (k, v))
    snapshot(path)
    io.open(path, "w", encoding="utf-8", newline="\n").write("\ufeff" + "\n".join(lines) + "\n")
    return path



def _writable_loc_root(root=None):
    if root and not is_under_game(root) and not is_readonly_mod(root):
        return root
    for r in reversed(state.roots() or []):
        lay = mod_layers(r) or [r]
        for cand in reversed(lay):
            if cand and not is_under_game(cand) and not is_readonly_mod(cand):
                return cand
    return None


def save_loc(root, entries):
    tgt = _writable_loc_root(root)
    if not tgt:
        return False, "没有可写的模组目录"
    for lang, kv in (entries or {}).items():
        if not isinstance(kv, dict) or not kv:
            continue
        state.loc_edits().setdefault(lang, {}).update(kv)
        _write_loc(tgt, lang)
        state.loc().update(kv)
    return True, "本地化已保存"


def _scan_mod_loc_files(top, lang_filter=""):
    """扫描顶层 mod 自己的 localisation/**/*.yml，返回 [(key, text, lang, rel_file)]。"""
    items = []
    if not top or not os.path.isdir(top):
        return items
    loc_dir = os.path.join(top, "localisation")
    if not os.path.isdir(loc_dir):
        return items
    line_re = re.compile(r'^\s*([A-Za-z0-9_.\-]+):\d*\s+"(.*)"\s*$')
    for cur, dirs, files in os.walk(loc_dir):
        dirs[:] = sorted(dirs, key=lambda x: (x.lower() == "replace", x.lower()))
        for fn in sorted(files):
            if not fn.lower().endswith(".yml"):
                continue
            fp = os.path.join(cur, fn)
            rel = os.path.relpath(fp, top).replace("\\", "/")
            parts = rel.split("/")
            flang = parts[1] if len(parts) >= 3 and parts[0] == "localisation" else ""
            if lang_filter and flang and flang != lang_filter:
                continue
            try:
                lines = io.open(fp, encoding="utf-8-sig", errors="replace").read().splitlines()
            except Exception:
                continue
            for ln in lines:
                m = line_re.match(ln)
                if m:
                    items.append((m.group(1), m.group(2), flang or lang_filter or "simp_chinese", rel))
    return items


def loc_browse(root=None, q="", scope="all", lang="simp_chinese", limit=150):
    """独立浏览/检索当前生效或当前 mod 自有的本地化条目。"""
    q_low = (q or "").strip().lower()
    scope = (scope or "all").strip()
    lang = (lang or "simp_chinese").strip()
    try:
        limit = max(1, min(500, int(limit)))
    except Exception:
        limit = 150

    top = _writable_loc_root(root)
    if not top:
        for r in reversed(state.roots() or []):
            lay = mod_layers(r) or [r]
            cand = lay[-1] if lay else r
            if cand and not is_under_game(cand):
                top = cand
                break

    out = []
    if scope == "mod":
        seen = {}
        if top:
            for k, v, fl, rel in _scan_mod_loc_files(top, lang_filter=""):
                seen[k] = {"key": k, "text": v, "lang": fl, "file": rel, "edited": True}
        for k, v in (state.loc_edits().get(lang) or {}).items():
            seen[k] = {"key": k, "text": v, "lang": lang, "file": "replace", "edited": True}
        rows = [seen[k] for k in sorted(seen)]
        for it in rows:
            if q_low and q_low not in it["key"].lower() and q_low not in (it["text"] or "").lower():
                continue
            out.append(it)
    else:
        loc_map = dict(state.loc() or {})
        edits = state.loc_edits().get(lang) or {}
        if edits:
            loc_map.update(edits)
        mod_keys = set()
        if top:
            for k, _v, _fl, _rel in _scan_mod_loc_files(top, lang_filter=""):
                mod_keys.add(k)
        mod_keys.update(edits.keys())
        for k in sorted(loc_map):
            v = loc_map[k]
            if q_low and q_low not in k.lower() and q_low not in (v or "").lower():
                continue
            out.append({
                "key": k,
                "text": v,
                "lang": lang,
                "file": "",
                "edited": k in mod_keys,
            })

    total = len(out)
    return {
        "ok": True,
        "scope": scope,
        "lang": lang,
        "total": total,
        "truncated": total > limit,
        "items": out[:limit],
        "writable": bool(_writable_loc_root(root)),
    }
