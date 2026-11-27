# -*- coding: utf-8 -*-
"""剧本（bookmark）：日期 / 国家块 / 本地化键 / bookmark_add。

只依赖 core 与 model.map / model.history，不碰兄弟模块。
"""
import hashlib
import io
import os
import re

from xuerong import state
from xuerong.core.ideologies import load_ideology_names
from xuerong.core.paths import _pick, effective_layer_files, unique_editor_filename
from xuerong.core.text import (_atomic_write, _bom_for, _read_text,
                               _strip_keep_len, brace_match)
from xuerong.model.history import snapshot
from xuerong.model.world._write_guard import world_write_base

def _bookmark_write_base(root):
    """common/bookmarks 的写入层，拒写父 mod。"""
    return world_write_base(root, "common/bookmarks", detail="")


def _bookmark_date(date):
    """把 1936.1.1 补成 1936.1.1.12。

    HOI4 的剧本日期是「年.月.日.小时」，只写三段时游戏会把日当小时解析，
    显示成「14月,1939」这种鬼东西。
    """
    parts = [p for p in (date or "").split(".") if p != ""]
    if len(parts) == 3:
        parts.append("12")
    return ".".join(parts)


def _resolve_country_ideology(tag_up, ides, explicit_ide=None):
    """按 显式指定 -> ruling_party -> neutrality(若存在) -> 首个意识形态 解析规范名。"""
    ide_map = {x.lower(): x for x in (ides or []) if x}
    cands = []
    if explicit_ide:
        cands.append(str(explicit_ide).strip())
    ctry = (state.countries() or {}).get(tag_up) or {}
    if ctry.get("ruling_party"):
        cands.append(str(ctry.get("ruling_party")).strip())
    cands.append("neutrality")
    for cand in cands:
        if cand and cand.lower() in ide_map:
            return ide_map[cand.lower()]
    return ides[0] if ides else "neutrality"


def _detect_bookmark_picture(root):
    """从叠加链已有 common/bookmarks/*.txt 探测非空 picture，否则兜底 GFX_select_date_1936。"""
    try:
        files = list(effective_layer_files("common/bookmarks", root))
    except Exception:
        files = []
    for _b, d, fn in reversed(files):
        try:
            txt = _read_text(os.path.join(d, fn))
        except Exception:
            continue
        for m in re.finditer(r'(?m)^\s*picture\s*=\s*"?([^"\s#]+)"?', txt):
            pic = (m.group(1) or "").strip()
            if pic:
                return pic
    return "GFX_select_date_1936"


def _has_default_bookmark(root):
    """当前叠加链生效 common/bookmarks/*.txt 是否已存在 default = yes。"""
    try:
        files = list(effective_layer_files("common/bookmarks", root))
    except Exception:
        files = []
    for _b, d, fn in files:
        try:
            txt = _read_text(os.path.join(d, fn))
        except Exception:
            continue
        if re.search(r'(?m)^\s*default\s*=\s*yes\b', txt):
            return True
    return False


def _bookmark_country_block(tag, ideology=None, history_key=None):
    """剧本里的「可选国家」条目。

    国家 tag 必须写成**裸键**（`ZZV = { ... }`），不能加引号。
    原版 blitzkrieg.txt / the_gathering_storm.txt 都是裸键；写成 `"ZZV" = {`
    解析出来是个字符串键而不是国家作用域，于是**选国家界面里一个可选国家都没有**：
    地图在、日期在、剧本名也在，就是没有国家可以点，「选择国家」按钮也不出现。
    （2026-11-03 实测踩到，卡了半晚的自动点击其实就是卡在这个空列表上。）
    """
    t_up = (tag or "").upper().strip()
    ide = (ideology or "").strip()
    if not ide:
        ides = load_ideology_names(None)
        ide = _resolve_country_ideology(t_up, ides, None)
    hkey = (history_key or "").strip() or ("%s_DESC" % t_up)
    return ('\t\t%s = {\n'
            '\t\t\thistory = %s\n'
            '\t\t\tideology = %s\n'
            '\t\t\tideas = {\n'
            '\t\t\t}\n'
            '\t\t\tfocuses = {\n'
            '\t\t\t}\n'
            '\t\t}\n') % (t_up, hkey, ide)


def _game_language():
    """读游戏的界面语言。HOI4 只加载和当前语言匹配的 localisation 文件，
    中文语言下写 l_english 的 yml 完全不生效，界面上就是裸 key。"""
    try:
        p = os.path.join(os.path.expanduser("~"), "Documents",
                         "Paradox Interactive", "Hearts of Iron IV", "settings.txt")
        if os.path.exists(p):
            with io.open(p, encoding="utf-8", errors="replace") as _fh:
                txt = _fh.read()
            m = re.search(r'language\s*=\s*"?([a-z_]+)"?', txt)
            if m:
                return m.group(1)
    except Exception:
        pass
    return "l_english"


def _esc_yml_val(val):
    """转义 HOI4 本地化 yml 值中的反斜杠、双引号与真实换行。"""
    s = "" if val is None else str(val)
    return (s.replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\r\n", "\n")
            .replace("\r", "\n")
            .replace("\n", "\\n"))


def _bookmark_loc(root, key, disp, desc_text, countries):
    """给剧本写本地化到 localisation/<lang>/ 子目录，避免裸 key 与父 mod TAG_DESC 碰撞。

    key 是 ASCII 标识符（写进 bookmarks），disp / desc_text 是显示文本。
    """
    tgt, _err = _bookmark_write_base(root)
    if not tgt:
        return False
    gl = (_game_language() or "l_english").strip()
    gl_dir = gl[2:] if gl.startswith("l_") else gl
    langs = ["simp_chinese", "english"]
    if gl_dir and gl_dir not in langs:
        langs.append(gl_dir)

    desc_val = desc_text if (desc_text and desc_text != disp) else disp
    pairs = [
        (key, disp),
        (key + "_DESC", desc_val),
    ]
    for c in countries:
        c_up = (c or "").upper().strip()
        if c_up:
            pairs.append(("%s_%s_DESC" % (key, c_up), c_up))

    wrote_any = False
    for lang_dir in langs:
        sub_rel = "localisation/%s" % lang_dir
        d = os.path.join(tgt, "localisation", lang_dir)
        os.makedirs(d, exist_ok=True)
        fn = unique_editor_filename(tgt, sub_rel, "zz_editor_bookmarks_l_%s.yml" % lang_dir)
        p = os.path.join(d, fn)

        lines = []
        if os.path.exists(p):
            try:
                with io.open(p, encoding="utf-8-sig", errors="replace") as _fh:
                    old = _fh.read()
                if old.strip():
                    lines = [old.rstrip("\n")]
            except Exception:
                lines = []
        if not lines:
            lines = ["l_%s:" % lang_dir]

        joined = "\n".join(lines)
        body = []
        for k, v in pairs:
            if re.search(r'(?m)^\s*' + re.escape(k) + r'\s*:', joined):
                continue
            body.append(' %s:0 "%s"' % (k, _esc_yml_val(v)))

        if not body:
            wrote_any = True
            continue
        txt = "\n".join(lines + body) + "\n"
        if os.path.exists(p):
            snapshot(p)
        _atomic_write(p, b"\xef\xbb\xbf" + txt.encode("utf-8"))
        wrote_any = True
    return wrote_any


def bookmark_add(root, name, date, desc=None, picture=None, default_country=None,
                 countries=None, ideology=None):
    """新建一个剧本。

    countries: 这个剧本里可选的国家列表，默认只放 default_country。
    ideology: 可选显式意识形态；未传时按国家 ruling_party → neutrality → mod 首个意识形态回退。
    """
    root = _pick(root)
    name = (name or "").strip()
    date = (date or "").strip()
    if not name:
        return {"ok": False, "msg": "name 不能为空"}
    if not re.match(r'^\d{4}\.\d{1,2}\.\d{1,2}(\.\d+)?$', date):
        return {"ok": False, "msg": "date 格式要像 1936.1.1 或 1936.1.1.12"}
    date = _bookmark_date(date)
    tag = (default_country or "GER").upper().strip()
    clist = []
    for c in (countries or [tag]):
        c = (c or "").upper().strip()
        if c and c not in clist:
            clist.append(c)
    if tag not in clist:
        clist.insert(0, tag)

    tgt, err = _bookmark_write_base(root)
    if not tgt:
        return {"ok": False, "msg": err}
    d = os.path.join(tgt, "common", "bookmarks")
    os.makedirs(d, exist_ok=True)
    fn_bm = unique_editor_filename(tgt, "common/bookmarks", "zz_editor_bookmarks.txt")
    p = os.path.join(d, fn_bm)

    pic = (picture or "").strip() or _detect_bookmark_picture(root)
    need_default = not _has_default_bookmark(root)
    ides = load_ideology_names(root)

    # 本地化 key 只能是最长 25 字符的 ASCII 标识符，中文名必须放在值那边。
    # 直接把中文名当 key 写进 yml，游戏报 Invalid key name，剧本名也显示不出来。
    bkey = "ZZ_EDITOR_BM_" + hashlib.md5(name.encode("utf-8")).hexdigest()[:8].upper()
    block = ['\tbookmark = {',
             '\t\tname = "%s"' % bkey,
             '\t\tdesc = "%s_DESC"' % bkey,
             '\t\tdate = %s' % date,
             '\t\tpicture = "%s"' % pic,
             '\t\tdefault_country = "%s"' % tag,
             '\t\tfilters = { }']
    if need_default:
        block.append('\t\tdefault = yes')
    block.append('\t\teffect = {')
    block.append('\t\t\trandomize_weather = 12345')
    block.append('\t\t}')
    block.append('')
    for c in clist:
        c_ide = _resolve_country_ideology(c, ides, explicit_ide=ideology)
        hkey = "%s_%s_DESC" % (bkey, c)
        block.append(_bookmark_country_block(c, ideology=c_ide, history_key=hkey).rstrip("\n"))
    block.append('\t}')
    block_txt = "\n".join(block) + "\n"

    if os.path.exists(p):
        with io.open(p, encoding="utf-8-sig", errors="replace") as _fh:
            raw = _fh.read()
    else:
        raw = "bookmarks = {\n}\n"
    text = _strip_keep_len(raw)
    bm = re.search(r'(?m)^[ \t]*bookmarks[ \t]*=\s*\{', text)
    if bm:
        bb = text.find("{", bm.end() - 1)
        be = brace_match(text, bb)
        if be > bb:
            pos = be
            while pos > 0 and raw[pos - 1] in " \t":
                pos -= 1
            if pos > 0 and raw[pos - 1] == "}":
                pos -= 1
            ls = raw.rfind("\n", 0, pos) + 1
            new_text = raw[:ls] + block_txt + raw[ls:]
        else:
            new_text = raw.rstrip() + "\n" + block_txt
    else:
        new_text = raw.rstrip() + "\nbookmarks = {\n" + block_txt + "}\n"
    if os.path.exists(p):
        snapshot(p)
    _atomic_write(p, _bom_for(p) + new_text.encode("utf-8"))
    try:
        _bookmark_loc(root, bkey, name, desc or name, clist)
    except Exception:
        pass
    return {"ok": True,
            "msg": "已新建剧本 %s（%s，%d 个国家可选）" % (name, date, len(clist))}
