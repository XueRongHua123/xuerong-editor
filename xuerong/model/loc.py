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
from xuerong.core.paths import _read_bom_text, _write_bom_text
from xuerong.core.text import _atomic_write
from xuerong.model.history import snapshot


def _loc_write_pairs(root, pairs, lang="simp_chinese"):
    """把 {key: text} 写进 zz_xuerong_evtext_l_<lang>.yml（只覆盖这些键）"""
    if not pairs:
        return ""
    d = os.path.join(root, "localisation", lang)
    os.makedirs(d, exist_ok=True)
    fn = os.path.join(d, "zz_xuerong_evtext_l_%s.yml" % lang)
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
    path = os.path.join(d, "zz_focus_editor_l_%s.yml" % lang)
    header = {"simp_chinese": "l_simp_chinese:", "english": "l_english:",
              "japanese": "l_japanese:"}.get(lang, "l_" + lang + ":")
    lines = [header]
    for k, v in sorted(state.loc_edits().get(lang, {}).items()):
        v = (v or "").replace("\\", "\\\\").replace('"', '\\"')
        lines.append(' %s:0 "%s"' % (k, v))
    snapshot(path)
    io.open(path, "w", encoding="utf-8", newline="\n").write("\ufeff" + "\n".join(lines) + "\n")
    return path



def save_loc(root, entries):
    for lang, kv in entries.items():
        state.loc_edits().setdefault(lang, {}).update(kv)
        _write_loc(root, lang)
        state.loc().update(kv)
    return True, "本地化已保存"
