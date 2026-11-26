# -*- coding: utf-8 -*-
"""人物（character）域（P2-rest 第 2 域，从 focus_editor.py 迁入）。

7 个函数：
  load_characters / characters_payload   —— 读 common/characters 的 characters = { … }
  portrait_import                        —— 图片转 DDS（156x210 / 64x64）并注册 sprite
  _char_write_base                       —— 写盘定位（算链顶 + replace_path 独占判定）
  character_add / character_set / character_delete —— 增 / 改 / 删

两处写盘是硬要求，缺一不可（任务书 3.2 的坑 2、坑 3）：
  · character_add 写 common/characters/<TAG>.txt，再往 history/countries/<TAG> - <Name>.txt
    追加 recruit_character；不写后者，人物不会出现在将领列表里。
  · character_delete 两处都要清，只清定义会留下悬空引用。

依赖边界：
  · CHAR_TYPES / PORTRAIT_W / PORTRAIT_H / PORTRAIT_SMALL 四个只读常量 → xuerong.state
  · 叠加链与写盘目标 → xuerong.core.paths；文本定位与写入 → xuerong.core.text
  · 写前快照 → xuerong.model.history
  · 唯一横切口 ensure_file_writable（要判只读/接管）由门面 bind() 回注
"""
import io
import os
import re

from xuerong import state
from xuerong.core.paths import (_layer_files, _replace_owner, is_under_game,
                                mod_layers, unique_editor_filename, write_base)
from xuerong.core.text import (_atomic_write, _bom_for, _first, _strip_keep_len, brace_depth_at,
                               brace_match, date_block_spans, find_blocks,
                               insert_before_date_or_end)
from xuerong.model.history import snapshot
from xuerong.state import CHAR_TYPES, PORTRAIT_H, PORTRAIT_SMALL, PORTRAIT_W

# ---------------------------------------------------------------- 门面回注
_INJ = {}


def bind(**kw):
    _INJ.update(kw)


def ensure_file_writable(*a, **k):
    return _INJ["ensure_file_writable"](*a, **k)


def _pick_root(root=None):
    if root:
        return root
    rs = state.roots()
    if rs:
        return rs[-1]
    return state.game()


def portrait_import(root, src_path, tag, cid=None, overwrite=False, small=False):
    """把一张图导入成人物头像。

    流程：转 DDS（大图 156x210 / 小图 64x64）→ 放 gfx/leaders/<TAG>/
    → 在 interface/zz_editor_portraits.gfx 里注册 sprite → 返回 sprite 名。

    返回 {"ok", "sprite", "file", "msg"}。
    """
    root = _pick_root(root)
    tag = (tag or "").strip().upper()
    if not tag:
        return {"ok": False, "msg": "没给国家 tag"}
    if not src_path or not os.path.isfile(src_path):
        return {"ok": False, "msg": "源文件不存在：%s" % src_path}

    top = None
    for r in (state.roots() or []):
        lay = mod_layers(r) or [r]
        cand = lay[-1] if lay else r
        if cand and not is_under_game(cand):
            top = cand
    if not top:
        return {"ok": False, "msg": "找不到可写的 mod 目录"}

    base = os.path.splitext(os.path.basename(src_path))[0]
    base = re.sub(r'[^A-Za-z0-9_\-]', '_', base) or "portrait"
    if cid:
        stem = re.sub(r'[^A-Za-z0-9_\-]', '_', str(cid))
    else:
        stem = base
    fname = ("small_" if small else "") + stem
    sprite = "GFX_portrait_%s_%s" % (tag, stem)

    W, H = (PORTRAIT_SMALL, PORTRAIT_SMALL) if small else (PORTRAIT_W, PORTRAIT_H)
    try:
        from PIL import Image
        Image.MAX_IMAGE_PIXELS = None
        im = Image.open(src_path).convert("RGBA")
        # 保持比例塞进目标框，剩下的补透明边（不裁切、不拉伸）
        im.thumbnail((W, H), Image.LANCZOS)
        canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        canvas.paste(im, ((W - im.width) // 2, (H - im.height) // 2), im)
    except Exception as e:
        return {"ok": False, "msg": "读图失败：%s" % e}

    rel_dir = "gfx/leaders/%s" % tag
    d = os.path.join(top, rel_dir.replace("/", os.sep))
    os.makedirs(d, exist_ok=True)
    dst = os.path.join(d, fname + ".dds")
    if os.path.exists(dst) and not overwrite:
        return {"ok": False, "need_confirm": True,
                "msg": "头像已存在：%s/%s.dds，要覆盖吗？" % (rel_dir, fname)}

    try:
        canvas.save(dst, format="DDS")
    except Exception as e:
        return {"ok": False, "msg": "存 DDS 失败：%s" % e}

    rel_tex = "%s/%s.dds" % (rel_dir, fname)

    # 注册 sprite
    gfx_dir = os.path.join(top, "interface")
    os.makedirs(gfx_dir, exist_ok=True)
    gfxp = os.path.join(gfx_dir, "zz_editor_portraits.gfx")
    block = ('\tSpriteType = {\n'
             '\t\tname = "%s"\n'
             '\t\ttexturefile = "%s"\n'
             '\t}\n') % (sprite, rel_tex)
    if os.path.exists(gfxp):
        with io.open(gfxp, encoding="utf-8-sig", errors="replace") as f:
            raw = f.read()
    else:
        raw = "spriteTypes = {\n}\n"
    m = re.search(r'spriteTypes\s*=\s*\{', raw)
    if m:
        b = raw.find("{", m.end() - 1)
        e = brace_match(raw, b)
        if e > b:
            if re.search(r'name\s*=\s*"' + re.escape(sprite) + r'"', raw):
                new = raw
            else:
                pos = e
                while pos > 0 and raw[pos - 1] in " \t":
                    pos -= 1
                if pos > 0 and raw[pos - 1] == "}":
                    pos -= 1
                ls = raw.rfind("\n", 0, pos) + 1
                new = raw[:ls] + block + raw[ls:]
        else:
            new = raw.rstrip() + "\n" + block + "}\n"
    else:
        new = raw.rstrip() + "\nspriteTypes = {\n" + block + "}\n"
    if new != raw:
        if os.path.exists(gfxp):
            snapshot(gfxp)
        _atomic_write(gfxp, _bom_for(gfxp) + new.encode("utf-8"))

    return {"ok": True, "sprite": sprite, "file": rel_tex,
            "size": "%dx%d" % (W, H),
            "msg": "头像已导入：%s（%dx%d）" % (sprite, W, H)}



def load_characters(root=None):
    """解析 common/characters 里的人物。

    结构：
        characters = {
            ID = {
                name = "..."
                portraits = { army = { large = GFX_xxx  small = "gfx/..." } }
                field_marshal = { traits = {…} skill = 7 attack_skill = 6 … }
            }
        }
    """
    root = _pick_root(root)
    files, _rep = _layer_files("common/characters", mod_layers(root))
    items, seen = [], set()
    for p in (files or []):
        try:
            with io.open(p, encoding="utf-8-sig", errors="replace") as f:
                raw = f.read()
        except Exception:
            continue
        text = _strip_keep_len(raw)
        rel = os.path.join("common", "characters", os.path.basename(p))
        src = ""
        try:
            for b in (mod_layers(root) or []):
                if os.path.abspath(p).startswith(os.path.abspath(b) + os.sep):
                    src = os.path.basename(b.rstrip("\\/")) or b
                    break
        except Exception:
            pass
        for outer_a, outer_b, outer_body in find_blocks(text, "characters"):
            for ca, cb, body in find_blocks(outer_body, "characters"):
                pass
            # 顶层是 ID = { … }，不是带 key 的块
            for m in re.finditer(r'(?m)^[ \t]*([A-Za-z][A-Za-z0-9_\-\.]*)[ \t]*=\s*\{', outer_body):
                cid = m.group(1)
                if cid in CHAR_TYPES or cid in ("portraits", "traits", "characters"):
                    continue
                cb = outer_body.find("{", m.end() - 1)
                ce = brace_match(outer_body, cb)
                if ce <= cb:
                    continue
                body = outer_body[cb + 1:ce - 1]
                nm = _first(body, r'(?m)^\s*name\s*=\s*"([^"]*)"')
                if not nm:
                    continue
                if cid in seen:
                    continue
                seen.add(cid)
                ctype = ""
                for t in CHAR_TYPES:
                    if re.search(r'(?m)^[ \t]*' + t + r'[ \t]*=\s*\{', body):
                        ctype = t
                        break
                big = _first(body, r'(?m)^\s*large\s*=\s*"?([^"\s#]+)"?')
                small = _first(body, r'(?m)^\s*small\s*=\s*"([^"]*)"')
                traits = []
                tm = re.search(r'(?m)^[ \t]*traits[ \t]*=\s*\{', body)
                if tm:
                    tb = body.find("{", tm.end() - 1)
                    te = brace_match(body, tb)
                    if te > tb:
                        for ln in body[tb + 1:te - 1].splitlines():
                            ln = ln.strip()
                            if ln and not ln.startswith("#"):
                                traits.append(ln)
                sk = {}
                for k in ("skill", "attack_skill", "defense_skill", "planning_skill",
                          "logistics_skill"):
                    v = _first(body, r'(?m)^\s*' + k + r'\s*=\s*(-?\d+)')
                    if v:
                        sk[k] = int(v)
                items.append({"id": cid, "name": nm, "type": ctype,
                              "portrait_large": big, "portrait_small": small,
                              "traits": traits, "skills": sk,
                              "file": rel, "source": src,
                              "start": outer_a + 1 + m.start(),
                              "end": outer_a + 1 + ce})
    return {"ok": True, "items": items, "count": len(items),
            "msg": "共 %d 个人物" % len(items)}



def _char_write_base(root):
    top = None
    for r in (state.roots() or []):
        lay = mod_layers(r) or [r]
        cand = lay[-1] if lay else r
        if cand and not is_under_game(cand):
            top = cand
    if not top and root and not is_under_game(root):
        top = root
    if not top:
        return None, "找不到可写的 mod 目录"
    owner = _replace_owner(root or top, "common/characters")
    if owner and os.path.abspath(owner) != os.path.abspath(top):
        chain = [os.path.abspath(x) for x in (mod_layers(root or top) or []) if x]
        ab_top = os.path.abspath(top)
        ab_own = os.path.abspath(owner)
        if ab_own in chain and ab_top in chain and chain.index(ab_own) > chain.index(ab_top):
            nm = os.path.basename(owner.rstrip("\\/")) or owner
            return None, ("common/characters 被 %s 的 replace_path 独占，"
                          "请先在「诊断 → 目录写入目标」里接管该目录" % nm)
    return top, ""



def character_add(root, cid, name, ctype="corps_commander", skill=3,
                  attack=3, defense=3, planning=3, logistics=3,
                  portrait_large="", portrait_small="", country=None,
                  portrait_src=None, portrait_overwrite=False):
    """新建人物。

    写进 common/characters/zz_editor_characters.txt（不覆盖别人已有的文件）。
    """
    root = _pick_root(root)
    cid = (cid or "").strip()
    name = (name or "").strip()
    ctype = (ctype or "corps_commander").strip()
    if not cid:
        return {"ok": False, "msg": "id 不能为空"}
    if not re.match(r'^[A-Za-z][A-Za-z0-9_\-\.]*$', cid):
        return {"ok": False, "msg": "id 只能用字母数字下划线，且以字母开头"}
    if not name:
        return {"ok": False, "msg": "名字不能为空"}
    if ctype not in CHAR_TYPES:
        return {"ok": False, "msg": "类型只能是 %s" % " / ".join(CHAR_TYPES)}

    info = load_characters(root)
    if any(x["id"] == cid for x in info["items"]):
        return {"ok": False, "msg": "已经有同 id 的人物：%s" % cid}

    def num(v, lo, hi):
        try:
            iv = int(v)
        except Exception:
            return None
        if iv < lo or iv > hi:
            return None
        return iv

    sk = {
        "skill": num(skill, 0, 10),
        "attack_skill": num(attack, 0, 10),
        "defense_skill": num(defense, 0, 10),
        "planning_skill": num(planning, 0, 10),
        "logistics_skill": num(logistics, 0, 10),
    }
    if any(v is None for v in sk.values()):
        return {"ok": False, "msg": "技能值必须是 0-10 的整数"}

    tgt, err = _char_write_base(root)
    if not tgt:
        return {"ok": False, "msg": err}
    d = os.path.join(tgt, "common", "characters")
    os.makedirs(d, exist_ok=True)
    country = (country or "").strip().upper()
    if country:
        p = os.path.join(d, country + ".txt")
        # 这个文件名和原版同名，会被整体覆盖——原版 GER.txt 有 85KB 几百个人物，
        # 直接写只剩我们新增的那一个，等于把整个国家的将领全删了。
        # 所以先把原版那份复制过来，再往里面追加。
        if not os.path.exists(p):
            src = None
            for b in reversed(mod_layers(tgt) or []):
                if not b:
                    continue
                cand = os.path.join(b, "common", "characters", country + ".txt")
                if os.path.isfile(cand):
                    src = cand
                    break
            if src:
                try:
                    import shutil as _sh3
                    _sh3.copyfile(src, p)
                except Exception:
                    pass
    else:
        fn_char = unique_editor_filename(tgt, "common/characters", "zz_editor_characters.txt")
        p = os.path.join(d, fn_char)

    # 给了图片就先导入成头像，自动拿到 sprite 名
    portrait_note = ""
    if portrait_src and country:
        try:
            pr = portrait_import(root, portrait_src, country, cid,
                                 portrait_overwrite or False, False)
            if pr.get("ok"):
                portrait_large = pr.get("sprite")
                portrait_note = "，头像 %s" % pr.get("sprite")
            else:
                portrait_note = "（头像导入失败：%s）" % (pr.get("msg") or "")[:40]
        except Exception as e:
            portrait_note = "（头像导入异常：%s）" % str(e)[:40]

    body = ['\t%s = {' % cid,
            '		name = "%s"' % name.replace('"', "")]
    if portrait_large or portrait_small:
        body.append('\t\tportraits = {')
        body.append('\t\t\tarmy = {')
        if portrait_large:
            body.append('\t\t\t\tlarge = %s' % portrait_large)
        if portrait_small:
            body.append('\t\t\t\tsmall = "%s"' % portrait_small)
        body.append('\t\t\t}')
        body.append('\t\t}')
    body.append('\t\t%s = {' % ctype)
    for k in ("skill", "attack_skill", "defense_skill", "planning_skill",
              "logistics_skill"):
        body.append('\t\t\t%s = %d' % (k, sk[k]))
    body.append('\t\t}')
    body.append('\t}')
    block = "\n".join(body) + "\n"

    if os.path.exists(p):
        with io.open(p, encoding="utf-8-sig", errors="replace") as f:
            raw = f.read()
    else:
        raw = "characters = {\n}\n"
    text = _strip_keep_len(raw)
    cm = re.search(r'(?m)^[ \t]*characters[ \t]*=\s*\{', text)
    if cm:
        cb = text.find("{", cm.end() - 1)
        ce = brace_match(text, cb)
        if ce > cb:
            pos = ce
            while pos > 0 and raw[pos - 1] in " \t":
                pos -= 1
            if pos > 0 and raw[pos - 1] == "}":
                pos -= 1
            ls = raw.rfind("\n", 0, pos) + 1
            new_text = raw[:ls] + block + raw[ls:]
        else:
            new_text = raw.rstrip() + "\n" + block
    else:
        new_text = raw.rstrip() + "\ncharacters = {\n" + block + "}\n"

    if os.path.exists(p):
        snapshot(p)
    _atomic_write(p, _bom_for(p) + new_text.encode("utf-8"))

    # 光在 common/characters 里定义还不够，HOI4 还要求国家历史里写一条
    # recruit_character = <id>，否则人物不会出现在将领列表里。
    rec_note = ""
    if country:
        try:
            hist = None
            for b in reversed(mod_layers(tgt) or []):
                if not b:
                    continue
                hd = os.path.join(b, "history", "countries")
                if not os.path.isdir(hd):
                    continue
                for fn in os.listdir(hd):
                    if fn.upper().startswith(country + " ") and fn.endswith(".txt"):
                        hist = os.path.join(hd, fn)
                        break
                if hist:
                    break
            if hist:
                _hp, _hwhy = ensure_file_writable(tgt, "history/countries",
                                                  os.path.basename(hist))
                hp = _hp or hist
                if hp and not is_under_game(hp):
                    with io.open(hp, encoding="utf-8-sig", errors="replace") as f:
                        hraw = f.read()
                    htext = _strip_keep_len(hraw)
                    if not re.search(r'(?m)^\s*recruit_character\s*=\s*' + re.escape(cid) + r'\b', htext):
                        dspans = date_block_spans(htext)
                        mrec = [
                            m for m in re.finditer(
                                r'(?m)^[ \t]*recruit_character[ \t]*=[ \t]*[A-Za-z0-9_\-\.]+[ \t]*(?:\r?\n|$)',
                                htext,
                            )
                            if brace_depth_at(htext, m.start()) == 0
                            and not any(ds <= m.start() < de for ds, de in dspans)
                        ]
                        if mrec:
                            pos = mrec[-1].end()
                            nl = "" if (not hraw[:pos] or hraw[:pos].endswith(("\n", "\r"))) else "\n"
                            new_h = hraw[:pos] + nl + "recruit_character = %s\n" % cid + hraw[pos:]
                        else:
                            new_h = insert_before_date_or_end(hraw, dspans, "\nrecruit_character = %s\n" % cid)
                        snapshot(hp)
                        _atomic_write(hp, _bom_for(hp) + new_h.encode("utf-8"))
                        rec_note = "，并在 %s 里加了 recruit_character" % os.path.basename(hp)
        except Exception as e:
            rec_note = "（招募写入失败：%s）" % str(e)[:40]

    return {"ok": True, "msg": "已新建人物「%s」（%s，%s）%s%s" % (
        name, cid, ctype, rec_note, portrait_note)}



def character_set(root, cid, fields):
    """改人物：名字 / 技能 / 特质。"""
    root = _pick_root(root)
    cid = (cid or "").strip()
    if not cid:
        return {"ok": False, "msg": "id 不能为空"}
    info = load_characters(root)
    it = next((x for x in info["items"] if x["id"] == cid), None)
    if not it:
        return {"ok": False, "msg": "没有这个人物：%s" % cid}
    tgt, err = _char_write_base(root)
    if not tgt:
        return {"ok": False, "msg": err}
    p = os.path.join(tgt, it["file"])
    os.makedirs(os.path.dirname(p) or tgt, exist_ok=True)
    src = None
    for q in (_layer_files("common/characters", mod_layers(root))[0] or []):
        if os.path.basename(q) == os.path.basename(it["file"]):
            src = q
            break
    if not os.path.exists(p) and src:
        try:
            import shutil as _sh
            _sh.copyfile(src, p)
        except Exception as e:
            return {"ok": False, "msg": "复制来源失败：%s" % e}
    with io.open(p, encoding="utf-8-sig", errors="replace") as f:
        raw = f.read()
    text = _strip_keep_len(raw)
    # 重新定位这个人物
    a = b = -1
    for oa, ob, oBody in find_blocks(text, "characters"):
        for m in re.finditer(r'(?m)^[ \t]*([A-Za-z][A-Za-z0-9_\-\.]*)[ \t]*=\s*\{', oBody):
            if m.group(1) != cid:
                continue
            cb = oBody.find("{", m.end() - 1)
            ce = brace_match(oBody, cb)
            if ce > cb:
                a = oa + 1 + cb
                b = oa + 1 + ce
                break
        if a >= 0:
            break
    if a < 0:
        return {"ok": False, "msg": "重新定位失败"}
    seg = raw[a:b]
    new_seg = seg
    changed = []
    nm = fields.get("name")
    if nm:
        pat = re.compile(r'(?m)^([ \t]*)name\s*=\s*"[^"]*"')
        if pat.search(new_seg):
            new_seg = pat.sub(lambda m: (m.group(1) or "") + 'name = "%s"' % nm.replace('"', ""), new_seg, count=1)
            changed.append("name")
    for k in ("skill", "attack_skill", "defense_skill", "planning_skill", "logistics_skill"):
        v = fields.get(k)
        if v in (None, ""):
            continue
        try:
            iv = int(v)
        except Exception:
            continue
        pat = re.compile(r'(?m)^([ \t]*)' + k + r'\s*=\s*-?\d+')
        if pat.search(new_seg):
            new_seg = pat.sub(lambda m: (m.group(1) or "") + "%s = %d" % (k, iv), new_seg, count=1)
            changed.append(k)

    # 人物类型（陆军将军 / 元帅 / 国家领导人 / 特工）
    # 类型就是块名，改类型等于改块名。技能字段在各类型里通用，不用搬。
    ctype = (fields.get("type") or "").strip()
    if ctype:
        if ctype not in CHAR_TYPES:
            return {"ok": False, "msg": "类型只能是 %s" % " / ".join(CHAR_TYPES)}
        OLD = it.get("type") or ""
        if OLD and OLD != ctype:
            pat = re.compile(r'(?m)^([ \t]*)' + re.escape(OLD) + r'([ \t]*=\s*\{)')
            if pat.search(new_seg):
                new_seg = pat.sub(
                    lambda m: (m.group(1) or "") + ctype + (m.group(2) or ""),
                    new_seg, count=1)
                changed.append("type:" + OLD + "→" + ctype)
        elif not OLD:
            # 原来没有类型块：把技能字段包进新类型块
            pat = re.compile(r'(?m)^([ \t]*)skill\s*=\s*-?\d+')
            m2 = pat.search(new_seg)
            if m2:
                indent = m2.group(1) or "\t\t"
                new_seg = (new_seg[:m2.start()]
                           + "%s%s = {\n" % (indent, ctype)
                           + new_seg[m2.start():]
                           + indent + "}\n")
                changed.append("type:" + ctype)
    if new_seg == seg:
        return {"ok": True, "msg": "没有改动"}
    new_text = raw[:a] + new_seg + raw[b:]
    snapshot(p)
    _atomic_write(p, _bom_for(p) + new_text.encode("utf-8"))
    return {"ok": True, "msg": "%s 已更新：%s" % (it["name"], ", ".join(changed))}



def character_delete(root, cid):
    """删掉一个人物（整块）。"""
    root = _pick_root(root)
    cid = (cid or "").strip()
    if not cid:
        return {"ok": False, "msg": "id 不能为空"}
    info = load_characters(root)
    it = next((x for x in info["items"] if x["id"] == cid), None)
    if not it:
        return {"ok": False, "msg": "没有这个人物：%s" % cid}
    tgt, err = _char_write_base(root)
    if not tgt:
        return {"ok": False, "msg": err}
    p = os.path.join(tgt, it["file"])
    os.makedirs(os.path.dirname(p) or tgt, exist_ok=True)
    src = None
    for q in (_layer_files("common/characters", mod_layers(root))[0] or []):
        if os.path.basename(q) == os.path.basename(it["file"]):
            src = q
            break
    if not os.path.exists(p):
        if not src:
            return {"ok": False, "msg": "找不到来源文件"}
        try:
            import shutil as _sh
            _sh.copyfile(src, p)
        except Exception as e:
            return {"ok": False, "msg": "复制来源失败：%s" % e}
    with io.open(p, encoding="utf-8-sig", errors="replace") as f:
        raw = f.read()
    text = _strip_keep_len(raw)
    a = b = -1
    for oa, ob, oBody in find_blocks(text, "characters"):
        for m in re.finditer(r'(?m)^[ \t]*([A-Za-z][A-Za-z0-9_\-\.]*)[ \t]*=\s*\{', oBody):
            if m.group(1) != cid:
                continue
            cb = oBody.find("{", m.end() - 1)
            ce = brace_match(oBody, cb)
            if ce > cb:
                a = oa + 1 + cb
                b = oa + 1 + ce
                # 起点再往前推到 ID 那一行的行首
                line_start = oBody.rfind("\n", 0, m.start()) + 1
                a = oa + 1 + line_start
                break
        if a >= 0:
            break
    if a < 0:
        return {"ok": False, "msg": "重新定位失败"}
    st = a
    while st > 0 and raw[st - 1] in " \t":
        st -= 1
    if st > 0 and raw[st - 1] == "\n":
        st -= 1
    en = b
    while en < len(raw) and raw[en] in "\r\n":
        en += 1
    snapshot(p)
    _atomic_write(p, _bom_for(p) + (raw[:st] + "\n" + raw[en:]).encode("utf-8"))

    # 同步清掉国家历史里的 recruit_character，否则游戏会引用一个不存在的人物
    rec_note = ""
    try:
        for b in reversed(mod_layers(tgt) or []):
            if not b:
                continue
            hd = os.path.join(b, "history", "countries")
            if not os.path.isdir(hd):
                continue
            for fn in sorted(os.listdir(hd)):
                if not fn.endswith(".txt"):
                    continue
                hp = os.path.join(hd, fn)
                try:
                    with io.open(hp, encoding="utf-8-sig", errors="replace") as f:
                        ht = f.read()
                except Exception:
                    continue
                if not re.search(r'(?m)^\s*recruit_character\s*=\s*' + re.escape(cid) + r'\b', ht):
                    continue
                _hp2, _ = ensure_file_writable(tgt, "history/countries", fn)
                target = _hp2 or hp
                if is_under_game(target):
                    continue
                with io.open(target, encoding="utf-8-sig", errors="replace") as f:
                    ht2 = f.read()
                pat = re.compile(r'(?m)^[ \t]*recruit_character[ \t]*=[ \t]*' + re.escape(cid) + r'[ \t]*\r?\n')
                nh = pat.sub("", ht2)
                if nh != ht2:
                    snapshot(target)
                    _atomic_write(target, _bom_for(target) + nh.encode("utf-8"))
                    rec_note = "，并清掉了 %s 里的 recruit_character" % fn
    except Exception:
        pass

    return {"ok": True, "msg": "已删除人物「%s」%s" % (it["name"], rec_note)}



def characters_payload(root=None):
    info = load_characters(root)
    if not info.get("ok"):
        return info
    return {"ok": True, "items": info["items"], "count": info["count"],
            "types": list(CHAR_TYPES), "msg": info["msg"]}

