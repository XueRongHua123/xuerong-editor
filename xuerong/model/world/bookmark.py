# -*- coding: utf-8 -*-
"""剧本（bookmark）：日期 / 国家块 / 本地化键 / bookmark_add。

只依赖 core 与 model.map / model.history，不碰兄弟模块。
"""
import hashlib
import io
import os
import re

from xuerong.core.paths import _top_mod, write_base
from xuerong.core.text import _atomic_write, _bom_for, _strip_keep_len, brace_match
from xuerong.model.history import snapshot
from xuerong.model.map import _map_pick

def _bookmark_write_base(root):
    """common/bookmarks 的写入层，拒写父 mod。"""
    top = _top_mod(root)
    if not top:
        return None, "找不到可写的 mod 目录"
    tgt, why = write_base(root, "common/bookmarks")
    if not tgt:
        return None, "找不到可写目录"
    if os.path.abspath(tgt) != os.path.abspath(top):
        nm = os.path.basename(tgt.rstrip("\\/")) or tgt
        return None, ("common/bookmarks 被 %s 的 replace_path 独占，"
                      "请先在「诊断 → 目录写入目标」里接管该目录" % nm)
    return tgt, ""


def _bookmark_date(date):
    """把 1936.1.1 补成 1936.1.1.12。

    HOI4 的剧本日期是「年.月.日.小时」，只写三段时游戏会把日当小时解析，
    显示成「14月,1939」这种鬼东西。
    """
    parts = [p for p in (date or "").split(".") if p != ""]
    if len(parts) == 3:
        parts.append("12")
    return ".".join(parts)


def _bookmark_country_block(tag, ideology="neutrality"):
    """剧本里的「可选国家」条目。

    国家 tag 必须写成**裸键**（`ZZV = { ... }`），不能加引号。
    原版 blitzkrieg.txt / the_gathering_storm.txt 都是裸键；写成 `"ZZV" = {`
    解析出来是个字符串键而不是国家作用域，于是**选国家界面里一个可选国家都没有**：
    地图在、日期在、剧本名也在，就是没有国家可以点，「选择国家」按钮也不出现。
    （2026-11-03 实测踩到，卡了半晚的自动点击其实就是卡在这个空列表上。）
    """
    return ('\t\t%s = {\n'
            '\t\t\thistory = %s_DESC\n'
            '\t\t\tideology = %s\n'
            '\t\t\tideas = {\n'
            '\t\t\t}\n'
            '\t\t\tfocuses = {\n'
            '\t\t\t}\n'
            '\t\t}\n') % (tag.upper(), tag.upper(), ideology)


def _game_language():
    """读游戏的界面语言。HOI4 只加载和当前语言匹配的 localisation 文件，
    中文语言下写 l_english 的 yml 完全不生效，界面上就是裸 key。"""
    try:
        p = os.path.join(os.path.expanduser("~"), "Documents",
                         "Paradox Interactive", "Hearts of Iron IV", "settings.txt")
        if os.path.exists(p):
            txt = io.open(p, encoding="utf-8", errors="replace").read()
            m = re.search(r'language\s*=\s*"?([a-z_]+)"?', txt)
            if m:
                return m.group(1)
    except Exception:
        pass
    return "l_english"


def _bookmark_loc(root, key, disp, desc_text, countries):
    """给剧本写本地化，否则界面上显示的是 NAME/DESC 这种 key。

    key 是 ASCII 标识符（写进 bookmarks），disp / desc_text 是中文显示名。
    """
    tgt, err = _bookmark_write_base(root)
    if not tgt:
        return False
    lang = _game_language()
    d = os.path.join(tgt, "localisation")
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, "zz_editor_bookmarks_%s.yml" % lang)

    lines = []
    if os.path.exists(p):
        try:
            old = io.open(p, encoding="utf-8-sig", errors="replace").read()
            if old.strip():
                lines = [old.rstrip("\n")]
        except Exception:
            lines = []
    if not lines:
        lines = ["%s:" % lang]

    # 已有内容里出现过的 key 不再重复写
    joined = "\n".join(lines)
    body = []
    def add(k, v):
        if re.search(r'(?m)^\s*' + re.escape(k) + r'\s*:', joined):
            return
        body.append(' %s:0 "%s"' % (k, v))
    add(key, disp)
    if desc_text and desc_text != disp:
        add(key + "_DESC", desc_text)
    else:
        # desc 与 name 同文时也要写一条，否则界面上的「历史简介」显示裸 key
        add(key + "_DESC", disp)
    for c in countries:
        add(c.upper() + "_DESC", c.upper())

    if not body:
        return True
    txt = "\n".join(lines + body) + "\n"
    io.open(p, "w", encoding="utf-8-sig", newline="").write(txt)
    return True


def bookmark_add(root, name, date, desc=None, picture=None, default_country=None,
                 countries=None):
    """新建一个剧本。

    countries: 这个剧本里可选的国家列表，默认只放 default_country。
    HOI4 的选国家界面只列剧本里写了 "TAG" = {} 的那些国家，不写就是空的。
    """
    root = _map_pick(root)
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
    p = os.path.join(d, "zz_editor_bookmarks.txt")

    # 本地化 key 只能是最长 25 字符的 ASCII 标识符，中文名必须放在值那边。
    # 直接把中文名当 key 写进 yml，游戏报 Invalid key name，剧本名也显示不出来。
    bkey = "ZZ_EDITOR_BM_" + hashlib.md5(name.encode("utf-8")).hexdigest()[:8].upper()
    block = ['\tbookmark = {',
             '		name = "%s"' % bkey,
             '		desc = "%s_DESC"' % bkey,
             '\t\tdate = %s' % date,
             '\t\tpicture = "%s"' % (picture or "GFX_select_date_1936"),
             '\t\tdefault_country = "%s"' % tag,
             '\t\tfilters = { new_content continent }',
             '\t\tdefault = yes',
             '']
    for c in clist:
        block.append(_bookmark_country_block(c).rstrip("\n"))
    block.append('\t}')
    block_txt = "\n".join(block) + "\n"

    if os.path.exists(p):
        raw = io.open(p, encoding="utf-8-sig", errors="replace").read()
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
