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


_YML_LINE_RE = re.compile(r'^\s*([A-Za-z0-9_.\-]+):\d*\s+"(.*)"\s*$')


def _read_yml_pairs(path, unescape=False):
    """读取已有 .yml 文件的键/值映射，避免跨会话写入时丢失旧条目。"""
    existing = {}
    if not os.path.exists(path):
        return existing
    try:
        with io.open(path, encoding="utf-8-sig", errors="replace") as f:
            raw = f.read()
        for ln in raw.splitlines():
            m = _YML_LINE_RE.match(ln)
            if m:
                val = m.group(2)
                if unescape:
                    val = re.sub(r'\\(["\\])', lambda gm: gm.group(1), val)
                existing[m.group(1)] = val
    except Exception:
        pass
    return existing


def _loc_write_pairs(root, pairs, lang="simp_chinese"):
    """把 {key: text} 写进 zz_xuerong_evtext_l_<lang>.yml（只覆盖这些键）"""
    if not pairs:
        return ""
    d = os.path.join(root, "localisation", lang)
    os.makedirs(d, exist_ok=True)
    base_fn = unique_editor_filename(root, "localisation/%s" % lang, "zz_xuerong_evtext_l_%s.yml" % lang)
    fn = os.path.join(d, base_fn)
    existing = _read_yml_pairs(fn, unescape=False)
    for k, v in pairs.items():
        existing[k] = str(v).replace('"', "'").replace(chr(10), "\\n")
    lines = ["l_%s:" % lang]
    for k in sorted(existing):
        lines.append(' %s:0 "%s"' % (k, existing[k]))
    _atomic_write(fn, b"\xef\xbb\xbf" + (chr(10).join(lines) + chr(10)).encode("utf-8"))
    return os.path.basename(fn)



def _sync_later_replace_ymls(d, base_fn, edits):
    """同步更新同目录下字母序排在 base_fn 之后的 .yml 中已存在但被保存覆盖的键，防止重载回盖。"""
    if not edits or not os.path.isdir(d):
        return
    base_low = base_fn.lower()
    line_re = re.compile(r'^(\s*)([A-Za-z0-9_.\-]+)(:\d*\s+)"(.*)"(\s*)$')
    try:
        names = sorted(os.listdir(d))
    except Exception:
        return
    for other_fn in names:
        if not other_fn.lower().endswith(".yml"):
            continue
        if other_fn.lower() <= base_low:
            continue
        other_path = os.path.join(d, other_fn)
        if not os.path.isfile(other_path):
            continue
        try:
            with io.open(other_path, encoding="utf-8-sig", errors="replace") as f:
                raw_text = f.read()
        except Exception:
            continue
        old_lines = raw_text.splitlines()
        new_lines = []
        changed = False
        for ln in old_lines:
            m = line_re.match(ln)
            if m and m.group(2) in edits:
                val = (edits[m.group(2)] or "").replace("\\", "\\\\").replace('"', '\\"')
                new_ln = '%s%s%s"%s"%s' % (m.group(1), m.group(2), m.group(3), val, m.group(5))
                if new_ln != ln:
                    changed = True
                new_lines.append(new_ln)
            else:
                new_lines.append(ln)
        if changed:
            snapshot(other_path)
            _atomic_write(other_path, b"\xef\xbb\xbf" + ("\n".join(new_lines) + "\n").encode("utf-8"))


def _write_loc(root, lang):
    d = os.path.join(root, "localisation", lang, "replace")
    os.makedirs(d, exist_ok=True)
    fn = unique_editor_filename(root, "localisation/%s/replace" % lang, "zz_focus_editor_l_%s.yml" % lang)
    path = os.path.join(d, fn)
    header = {"simp_chinese": "l_simp_chinese:", "english": "l_english:",
              "japanese": "l_japanese:"}.get(lang, "l_" + lang + ":")
    edits = state.loc_edits().get(lang, {})
    merged = _read_yml_pairs(path, unescape=True)
    merged.update(edits)
    lines = [header]
    for k, v in sorted(merged.items()):
        v = (v or "").replace("\\", "\\\\").replace('"', '\\"')
        lines.append(' %s:0 "%s"' % (k, v))
    snapshot(path)
    _atomic_write(path, b"\xef\xbb\xbf" + ("\n".join(lines) + "\n").encode("utf-8"))
    _sync_later_replace_ymls(d, fn, edits)
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
    items = [(lang, kv) for lang, kv in (entries or {}).items()
             if isinstance(kv, dict) and kv]
    items.sort(key=lambda pair: 1 if pair[0] == "simp_chinese" else 0)
    simp_in = entries.get("simp_chinese") if isinstance(entries, dict) and isinstance(entries.get("simp_chinese"), dict) else {}
    simp_edits = state.loc_edits().get("simp_chinese") or {}
    loc_map = state.loc()
    for lang, kv in items:
        state.loc_edits().setdefault(lang, {}).update(kv)
        _write_loc(tgt, lang)
        if lang == "simp_chinese":
            loc_map.update(kv)
        else:
            for k, v in kv.items():
                if k not in simp_edits and k not in simp_in:
                    loc_map[k] = v
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
                with io.open(fp, encoding="utf-8-sig", errors="replace") as f:
                    lines = f.read().splitlines()
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
