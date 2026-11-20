# -*- coding: utf-8 -*-
"""贴图与图标：spriteType 解析、图标索引构建、/api/icon 的贴图查找与缓存。

从门面搬来的三批：

    批 1  读侧纯函数   parse_gfx_file / _gfx_collect / _gfx_refs / gfx_missing
                      / gfx_list / gfx_registered / _gfx_texture_exists
    批 2  索引与查找   all_goal_icons / icon_png / build_icons
    批 3  写侧         gfx_sprite_new / gfx_import

跨层依赖一律走钩子或 state 访问器，本模块**不 import 门面**：

    snapshot      model 层的东西，core 不能 import → set_snapshot_hook() 注入
    _map_pick     model.map 的东西 → 用 core.paths._pick（门面已 set_root_picker 注入过）
    ROOTS/GAME/TREE_ORDER/TREES/LOC/ICON_DIR   → state.roots()/game()/tree_order()
                     /trees()/loc()/path_var("ICON_DIR")

四个图标容器与 _GFX_CACHE / GFX_KINDS 都在本模块定义，门面 import 的是同一份对象
（绝不能两边各写一份，否则表会分裂、图标全丢）。
"""
import hashlib
import io
import os
import re

from xuerong import state
from xuerong.core.paths import (_chain_layers, _layer_files, is_under_game,
                                mod_layers, _pick)
from xuerong.core.text import (_atomic_write, _bom_for, _first, _strip_keep_len,
                               brace_match, find_blocks, strip_comments)

# ---------------- 跨层钩子：model 的 snapshot ----------------
# core 不能 import model（qa/_check_import_boundary.py 强制）。门面启动期注入
# history.snapshot；拿不到就跳过 —— 与「snapshot 只在文件已存在时调用」的容错等价。
_SNAPSHOT = None


def set_snapshot_hook(fn):
    """门面在启动期注入 history.snapshot；core 不能 import model。"""
    global _SNAPSHOT
    _SNAPSHOT = fn


# ---------------- 四个图标容器（门面 import 的同一份对象） ----------------
ICONS = {}
EQUIP_ICONS = {}
TECH_ICONS = {}
SPRITE_MAP = {}

# ref: CWTools validator "referenced sprites and graphics files exist"
_GFX_CACHE = {}

GFX_KINDS = {
    "goal":  {"dir": "gfx/interface/goals",   "prefix": "GFX_goal_",   "label": "国策"},
    "idea":  {"dir": "gfx/interface/ideas",   "prefix": "GFX_idea_",   "label": "想法"},
    "tech":  {"dir": "gfx/interface/technologies", "prefix": "GFX_",    "label": "科技"},
    "generic": {"dir": "gfx/interface",       "prefix": "GFX_",         "label": "通用"},
}


def _gfx_collect(root, layers, include_vanilla=True):
    """收集 sprite 定义 → {spriteName: texturefile}，以及 texture 文件集合

    原版的 interface/*.gfx 有 145 个文件、几万个 sprite，只在第一次调用时扫一遍。"""
    key = (os.path.abspath(root or ""), include_vanilla)
    hit = _GFX_CACHE.get(key)
    if hit:
        return hit

    sprites = {}
    textures = set()

    def _scan(base):
        d = os.path.join(base or "", "interface")
        if not os.path.isdir(d):
            return
        for _dp, _dn, files in os.walk(d):
            for fn in files:
                if not fn.endswith(".gfx"):
                    continue
                p = os.path.join(_dp, fn)
                try:
                    text = strip_comments(io.open(p, encoding="utf-8-sig",
                                                  errors="replace").read())
                except Exception:
                    continue
                # 用 brace 配对取每个 spriteType 块：块内还有 frames/instances 等嵌套，
                # 非贪婪正则会在第一个 } 处截断，导致大量 sprite 漏收。
                # 变体：spriteType / corneredTileSpriteType / frameAnimatedSpriteType / progressbartype
                for m in re.finditer(r'(?m)^\s*([A-Za-z_]*[Ss]priteType|progressbartype)\s*=\s*\{',
                                     text):
                    b = text.find("{", m.end() - 1)
                    e = brace_match(text, b)
                    if e <= b:
                        continue
                    body = text[b + 1:e - 1]
                    # name 可以带引号也可以不带（name = GFX_xxx）
                    nm = re.search(r'(?m)^\s*name\s*=\s*"?([^"\s\}]+)"?', body)
                    if not nm:
                        continue
                    name = nm.group(1)
                    tx = re.search(r'(?m)^\s*texturefile\s*=\s*"?([^"\s\}]+)"?', body)
                    sprites[name] = tx.group(1) if tx else ""
                    if tx:
                        textures.add(tx.group(1).replace(chr(92), "/").lower())

    if include_vanilla and state.game():
        _scan(state.game())
    for b in (layers or []):
        if b:
            _scan(b)
    _GFX_CACHE[key] = (sprites, textures)
    return sprites, textures


def _gfx_refs(root, layers):
    """扫 mod 脚本里的 sprite 引用 → {spriteName: (位置描述, 文件)}"""
    refs = {}

    def _note(name, where, f):
        name = (name or "").strip()
        if len(name) <= 4 or not name.startswith("GFX_"):
            return          # icon = aluminium / generic 这种不是 sprite；GFX_ 空名也跳过
        if name not in refs:
            refs[name] = [where, f]

    # 国策 icon / 精神 picture / 事件 picture / 决议 icon / 装备 picture
    # sprite 名可能带非 ASCII（GFX_94式戦車 这种），[A-Za-z0-9_.-] 会把名字截断
    patterns = [
        (r'icon\s*=\s*"?([^"\s\}]+)"?', "icon"),
        (r'picture\s*=\s*"?([^"\s\}]+)"?', "picture"),
    ]
    for rel_dir in ("common/national_focus", "common/ideas", "common/decisions",
                    "common/decisions/categories", "events", "common/units/equipment"):
        d = os.path.join(root, rel_dir)
        if not os.path.isdir(d):
            continue
        for _dp, _dn, files in os.walk(d):
            for fn in files:
                if not fn.endswith(".txt"):
                    continue
                p = os.path.join(_dp, fn)
                try:
                    text = strip_comments(io.open(p, encoding="utf-8-sig",
                                                  errors="replace").read())
                except Exception:
                    continue
                for pat, where in patterns:
                    for m in re.finditer(pat, text):
                        _note(m.group(1), where, os.path.basename(p))
    return refs


def gfx_missing(root=None, limit=600):
    """列出引用了但没定义的 sprite，以及定义了但贴图文件不存在的 sprite"""
    root = _pick(root)
    layers = mod_layers(root)
    sprites, textures = _gfx_collect(root, layers)
    refs = _gfx_refs(root, layers)
    if not refs:
        return {"ok": True, "total": 0, "missing": [],
                "msg": "脚本里没有找到 sprite 引用"}

    missing = []
    by_kind = {}
    for name, (where, f) in refs.items():
        if name in sprites:
            continue
        # 纯色/文字类的值不是 sprite（比如 icon = 3 已被正则过滤，这里防空）
        missing.append({"name": name, "where": where, "file": f})
        by_kind[where] = by_kind.get(where, 0) + 1
    missing.sort(key=lambda x: (x["where"], x["name"]))

    # 顺带查：mod 自己定义的 sprite，贴图文件是否真的存在
    mod_sprites = {}
    for b in (layers or []):
        if not b or os.path.abspath(b) == os.path.abspath(state.game() or ""):
            continue
        s2, _t2 = _gfx_collect(b, [], include_vanilla=False)
        mod_sprites.update(s2)
    bad_texture = []
    for name, tx in mod_sprites.items():
        if not tx:
            continue
        if not _gfx_texture_exists(tx, layers):
            bad_texture.append({"name": name, "texture": tx})

    return {"ok": True, "total": len(missing), "by_kind": by_kind,
            "refs": len(refs), "defined": len(sprites),
            "missing": missing[:limit], "truncated": len(missing) > limit,
            "bad_texture": bad_texture[:limit],
            "bad_texture_total": len(bad_texture),
            "msg": "引用 %d 个 sprite，缺 %d 个；贴图文件缺失 %d 个" % (
                len(refs), len(missing), len(bad_texture))}


def _gfx_texture_exists(rel, layers):
    """贴图文件是否存在于某一层（忽略大小写，游戏在 Windows 上不区分）"""
    rel = (rel or "").replace(chr(92), "/").strip("/")
    if not rel:
        return True
    low = rel.lower()
    for base in (layers or []):
        if not base:
            continue
        cand = os.path.join(base, rel.replace("/", os.sep))
        if os.path.exists(cand):
            return True
        # 大小写不一致时按目录列举比对
        d = os.path.dirname(cand)
        if os.path.isdir(d):
            try:
                for fn in os.listdir(d):
                    if fn.lower() == os.path.basename(cand).lower():
                        return True
            except Exception:
                pass
    return False


def parse_gfx_file(path):
    s = io.open(path, encoding="utf-8-sig", errors="replace").read()
    out = {}
    for m in re.finditer(r'spriteType\s*=\s*\{', s, re.I):
        b = m.end() - 1
        e = brace_match(s, b)
        body = s[b + 1:e - 1]
        name = re.search(r'name\s*=\s*"?([^"\s]+)"?', body, re.I)
        tex = re.search(r'texturefile\s*=\s*"?([^"\s]+)"?', body, re.I)
        frames = re.search(r'noOfFrames\s*=\s*(\d+)', body, re.I)
        if name and tex:
            out[name.group(1)] = (tex.group(1), int(frames.group(1)) if frames else 1)
    return out


def gfx_list(root=None, kind="goal"):
    """列出某类图标目录下已有的图片文件。"""
    root = _pick(root)
    k = GFX_KINDS.get(kind) or GFX_KINDS["goal"]
    d = os.path.join(root, k["dir"].replace("/", os.sep)) if root else ""
    items = []
    if d and os.path.isdir(d):
        for fn in sorted(os.listdir(d)):
            low = fn.lower()
            if low.endswith((".dds", ".tga", ".png", ".jpg", ".jpeg")):
                p = os.path.join(d, fn)
                items.append({"file": fn, "size": os.path.getsize(p),
                              "sprite": k["prefix"] + os.path.splitext(fn)[0]})
    return {"ok": True, "kind": kind, "dir": k["dir"], "items": items,
            "count": len(items), "prefix": k["prefix"],
            "msg": "%s：%d 张图（前缀 %s）" % (k["label"], len(items), k["prefix"])}


def gfx_registered(root=None, pattern=""):
    """列出 interface 里已注册的 spriteType（可选按名字过滤）。"""
    root = _pick(root)
    top = None
    for r in (state.roots() or []):
        lay = mod_layers(r) or [r]
        cand = lay[-1] if lay else r
        if cand and not is_under_game(cand):
            top = cand
    files, _r = _layer_files("interface", mod_layers(root))
    out, seen = [], set()
    pat = (pattern or "").lower()
    for p in (files or []):
        if not p.lower().endswith(".gfx"):
            continue
        try:
            raw = io.open(p, encoding="utf-8-sig", errors="replace").read()
        except Exception:
            continue
        text = _strip_keep_len(raw)
        for a, b, body in find_blocks(text, "spriteType"):
            nm = _first(body, r'(?m)^\s*name\s*=\s*"([^"]*)"')
            tf = _first(body, r'(?m)^\s*texturefile\s*=\s*"([^"]*)"')
            if not nm or nm in seen:
                continue
            if pat and pat not in nm.lower() and pat not in (tf or "").lower():
                continue
            seen.add(nm)
            out.append({"name": nm, "texture": tf, "file": os.path.basename(p)})
    return {"ok": True, "items": out[:500], "count": len(out),
            "msg": "已注册 %d 个 sprite（显示前 500）" % len(out)}


def gfx_sprite_new(root, name, texturefile):
    """往 interface 里写一条 spriteType 注册。"""
    root = _pick(root)
    top = None
    for r in (state.roots() or []):
        lay = mod_layers(r) or [r]
        cand = lay[-1] if lay else r
        if cand and not is_under_game(cand):
            top = cand
    if not top:
        return {"ok": False, "msg": "找不到可写的 mod 目录"}
    if not name or not texturefile:
        return {"ok": False, "msg": "name 和 texturefile 都要给"}
    d = os.path.join(top, "interface")
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, "zz_editor_icons.gfx")
    block = ('\nspriteTypes = {\n'
             '\tspriteType = {\n'
             '\t\tname = "%s"\n'
             '\t\ttexturefile = "%s"\n'
             '\t}\n'
             '}\n') % (name, texturefile.replace("\\", "/"))
    if os.path.exists(p):
        raw = io.open(p, encoding="utf-8-sig", errors="replace").read()
        if ('"%s"' % name) in raw:
            return {"ok": True, "msg": "%s 已经注册过了" % name}
        new_text = raw.rstrip() + "\n" + block
    else:
        new_text = block.lstrip("\n")
    if os.path.exists(p) and _SNAPSHOT:
        _SNAPSHOT(p)
    _atomic_write(p, _bom_for(p) + new_text.encode("utf-8"))
    return {"ok": True, "msg": "已注册 sprite %s → %s" % (name, texturefile),
            "file": "interface/zz_editor_icons.gfx"}


def gfx_import(root, src_path, kind="goal", name=None, sprite_name=None,
               size=None, overwrite=False):
    """把一张图导入成 HOI4 图标：转 DDS + 放到对应目录 + 注册 sprite。

    src_path  可以是 png / jpg / dds / tga，统一转成 DDS 存进去
    size      目标边长（正方形），不给就按 HOI4 惯例：goal 64、idea 64、tech 64
    """
    root = _pick(root)
    k = GFX_KINDS.get(kind) or GFX_KINDS["goal"]
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

    base = name or os.path.splitext(os.path.basename(src_path))[0]
    base = re.sub(r'[^A-Za-z0-9_\-]', '_', base)
    if not base:
        return {"ok": False, "msg": "文件名里没有可用的字符"}

    side = int(size) if size else 64
    side = max(16, min(512, side))

    try:
        from PIL import Image
        Image.MAX_IMAGE_PIXELS = None
        im = Image.open(src_path).convert("RGBA")
        # 保持比例缩放到正方形画布
        im.thumbnail((side, side), Image.LANCZOS)
        canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
        canvas.paste(im, ((side - im.width) // 2, (side - im.height) // 2), im)
    except Exception as e:
        return {"ok": False, "msg": "读图失败：%s" % e}

    d = os.path.join(top, k["dir"].replace("/", os.sep))
    os.makedirs(d, exist_ok=True)
    dst = os.path.join(d, base + ".dds")
    if os.path.exists(dst) and not overwrite:
        return {"ok": False, "need_confirm": True,
                "msg": "目标已存在：%s，要覆盖吗？" % os.path.join(k["dir"], base + ".dds")}
    try:
        if os.path.exists(dst) and _SNAPSHOT:
            _SNAPSHOT(dst)
        canvas.save(dst, format="DDS")
    except Exception as e:
        return {"ok": False, "msg": "写 DDS 失败：%s" % e}

    texture = "%s/%s.dds" % (k["dir"], base)
    sprite = sprite_name or (k["prefix"] + base)
    r2 = gfx_sprite_new(top, sprite, texture)
    if not r2.get("ok"):
        return {"ok": False, "msg": "图已转好但注册失败：%s" % r2.get("msg")}

    return {"ok": True, "sprite": sprite, "texture": texture,
            "size": "%dx%d" % (side, side), "file": os.path.join(k["dir"], base + ".dds"),
            "msg": "已导入 %s：%dx%d DDS + 注册 %s" % (base, side, side, sprite)}


def all_goal_icons():
    out = []
    for g, (tex, frames) in SPRITE_MAP.items():
        tl = tex.lower().replace("\\", "/")
        if "/interface/goals/" in tl:
            out.append(g)
    return sorted(out)


def icon_png(gfx):
    ent = SPRITE_MAP.get(gfx)
    if not ent:
        return None
    tex, frames = ent
    rel = tex.replace("/", os.sep)
    # 找**实际生效的那份**：子 mod 覆盖父 mod，所以按链倒着找（子优先）。
    # 和 build_icons 的读取顺序相反——那边是「后读覆盖先读」，这边是「先找到就用」。
    cands = []
    _seen_i = set()
    for r in state.roots():
        for ab in reversed(_chain_layers(r)):
            p = os.path.join(ab, rel)
            if p not in _seen_i:
                _seen_i.add(p)
                cands.append(p)
    if state.game():
        p = os.path.join(state.game(), rel)
        if p not in _seen_i:
            _seen_i.add(p)
            cands.append(p)
    dlc = os.path.join(state.game(), "dlc")
    if os.path.isdir(dlc):
        for x in os.listdir(dlc):
            p = os.path.join(dlc, x, rel)
            if p not in _seen_i:
                _seen_i.add(p)
                cands.append(p)
    src = next((c for c in cands if os.path.exists(c)), None)
    if not src:
        return None
    png_name = re.sub(r'[^A-Za-z0-9_.-]', '_', gfx) + "_" + \
        hashlib.md5((os.path.abspath(src) + str(os.path.getmtime(src))).encode("utf-8")).hexdigest()[:8] + ".png"
    png = os.path.join(state.path_var("ICON_DIR"), png_name)
    try:
        if not os.path.exists(png):
            from PIL import Image
            im = Image.open(src)
            if frames > 1:
                w, h = im.size
                im = im.crop((0, 0, w // frames, h))
            im = im.convert("RGBA")
            im.thumbnail((64, 64))
            im.save(png)
        return png
    except Exception:
        return None


def build_icons(roots, game):
    # 四个容器一律原地更新（clear + update），不重新绑定：state.py 的访问器
    # （sprite_map() / icons() / equip_icons() / tech_icons()）靠对象身份，
    # 一旦这里换成新对象，早前取过引用的调用方会永久停在旧表上。
    global ICONS, SPRITE_MAP, EQUIP_ICONS, TECH_ICONS
    sprite_map = {}
    dirs = []
    seen = set()

    # v1.23.46：sprite 索引必须扫**整条叠加链**。
    # 只扫 ROOTS 的话，子 mod 自己没有 interface/ 时 sprite_map 就是空的，
    # 于是每个国策节点都变成破图（KaiserReich 子 mod 实测 230 棵树、3253 个图标、
    # SPRITE_MAP 0 条）。
    #
    # 读取顺序（后读覆盖先读）：DLC → 原版 → 父 mod → 子 mod。
    # `_chain_layers` 已经把原版排在最前，所以 DLC 单独补在更前面。
    dlc = os.path.join(game, "dlc")
    if os.path.isdir(dlc):
        for x in sorted(os.listdir(dlc)):
            p = os.path.join(dlc, x, "interface")
            if os.path.isdir(p):
                ap = os.path.abspath(p)
                if ap not in seen:
                    seen.add(ap)
                    dirs.append(p)
    for r in roots:
        for ab in _chain_layers(r):
            d = os.path.join(ab, "interface")
            if os.path.isdir(d):
                ap = os.path.abspath(d)
                if ap not in seen:
                    seen.add(ap)
                    dirs.append(d)
    base = os.path.join(game, "interface")
    if os.path.isdir(base):
        ap = os.path.abspath(base)
        if ap not in seen:
            seen.add(ap)
            dirs.append(base)
    for d in dirs:
        # **必须递归**：HOI4 会加载 interface/ 子目录里的 .gfx，Kaiserreich 的国策图标
        # 全在 interface/kaiserreich/goals.gfx，只 listdir 顶层的话 3000 多个图标一个都读不到。
        for dirpath, _subdirs, _files in os.walk(d):
            for fn in sorted(_files):
                if fn.lower().endswith(".gfx"):
                    try:
                        sprite_map.update(parse_gfx_file(os.path.join(dirpath, fn)))
                    except Exception:
                        pass
    SPRITE_MAP.clear()
    SPRITE_MAP.update(sprite_map)
    used = set()
    for tid in state.tree_order():
        for f in state.trees()[tid]["focuses"]:
            if f.get("icon"):
                used.add(f["icon"])
    # ICONS 原先是只增不清，跨 reload 会累积上一个 mod 的图标
    ICONS.clear()
    for gfx in used:
        if gfx in sprite_map:
            ICONS[gfx] = "/api/icon?gfx=" + gfx
    print("icons:", len(ICONS), "/", len(used))
    EQUIP_ICONS.clear()
    for gfx, (tex, frames) in sprite_map.items():
        tl = tex.lower().replace("\\", "/")
        if "/interface/equipment/" in tl:
            EQUIP_ICONS[gfx] = "/api/icon?gfx=" + gfx
    print("equip icons:", len(EQUIP_ICONS))
    TECH_ICONS.clear()
    for gfx, (tex, frames) in sprite_map.items():
        tl = tex.lower().replace("\\", "/")
        gl = gfx.lower()
        if ("/interface/technologies/" in tl or "/interface/tech/" in tl
                or gl.startswith("gfx_tech") or gl.endswith("_tab")
                or "_technology_" in gl):
            TECH_ICONS[gfx] = "/api/icon?gfx=" + gfx
    print("tech icons:", len(TECH_ICONS))

