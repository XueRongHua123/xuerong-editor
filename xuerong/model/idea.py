# -*- coding: utf-8 -*-
"""国家精神（idea）域（P0-3 B4-1 从 focus_editor.py 迁入）。

读：common/ideas 的解析（load_ideas）+ 某国开局精神的开关；
写：save_idea / add_idea / delete_idea —— 都落到 common/ideas 的某一层。

依赖边界：
  · IDEAS / LOC / CHANGED → xuerong.state
  · 文本改写 → xuerong.core.text；叠加链 → xuerong.core.paths
  · 国家历史定位 → xuerong.model.country；写前快照 → xuerong.model.history
  · 唯一钩子：reload_data
"""
import io
import os
import re

from xuerong import state
from xuerong.core import paths
from xuerong.core.paths import (_layer_dirs, effective_layer_files,
                                is_readonly_mod, is_under_game, mod_layers,
                                unique_editor_filename)
from xuerong.core.text import (_atomic_write, _bom_for, _strip_keep_len, apply_modifier_props,
                               brace_match, braces_balanced, find_blocks, set_raw_block,
                               set_scalar, strip_comments, top_items)
from xuerong.model.country import _country_hist_file, _country_hist_write_base
from xuerong.model.history import backup, snapshot

_RELOAD = None


def bind(reload_data):
    global _RELOAD
    _RELOAD = reload_data


def _reload():
    if _RELOAD:
        _RELOAD()


def _looks_like_idea(body):
    keys = {"picture", "modifier", "allowed", "research_bonus", "equivalency",
            "rule", "targeted_modifier", "name", "cancel", "on_add", "on_remove"}
    for k, v, b in top_items(body):
        if k in keys:
            return True
    return False



def _build_idea_entry(key, body, rel, src):
    clean = strip_comments(body or "")
    props = {}
    for s, e, inner in find_blocks(clean, "modifier"):
        for pm in re.finditer(r'(?m)^\s*([A-Za-z0-9_]+)\s*=\s*([^\s#]+)\s*$', inner):
            props[pm.group(1)] = pm.group(2)
    pic = re.search(r'(?m)^\s*picture\s*=\s*"?([A-Za-z0-9_]+)"?', clean)
    return {
        "id": key,
        "file": rel,
        "source": src,
        "name": state.loc().get(key, key),
        "desc": state.loc().get(key + "_desc", ""),
        "picture": pic.group(1) if pic else "",
        "props": props,
        "raw": "%s = {\n%s\n}" % (key, (body or "").strip()),
    }


def idea_view(oid):
    item = state.ideas().get(oid)
    if not item:
        return None
    return {k: v for k, v in item.items() if k != "raw"}


def _add_idea(key, body, file, source):
    if not re.match(r'^[A-Za-z0-9_]+$', key or ""):
        return
    state.ideas()[key] = _build_idea_entry(key, body, file, source)



def load_ideas(root):
    n = 0
    for base, d, fn in effective_layer_files("common/ideas", root):
        src = os.path.basename(base.rstrip("\\/")) or base
        rel = os.path.join("common", "ideas", fn)
        try:
            raw = io.open(os.path.join(d, fn), encoding="utf-8-sig",
                          errors="replace", newline="").read()
        except Exception:
            continue
        text = strip_comments(raw)
        for _s, _e, body in find_blocks(text, "ideas"):
            for k, v, b in top_items(body):
                if not b:
                    continue
                if _looks_like_idea(v):
                    _add_idea(k, v, rel, src); n += 1
                else:
                    for k2, v2, b2 in top_items(v):
                        if b2 and _looks_like_idea(v2):
                            _add_idea(k2, v2, rel, src); n += 1
    return n



def _brace_depth_at(text, pos):
    """计算无注释文本在 pos 处的花括号嵌套深度（忽略引号内字符）。"""
    d = 0
    instr = False
    for ch in text[:pos]:
        if ch == '"':
            instr = not instr
        elif not instr:
            if ch == '{':
                d += 1
            elif ch == '}':
                d -= 1
    return d


def _date_block_spans(text):
    """返回顶层日期块 YYYY.MM.DD = { ... } 的起止区间列表。"""
    spans = []
    for m in re.finditer(r'(?m)^[ \t]*\d{3,4}\.\d+\.\d+[ \t]*=\s*\{', text):
        if _brace_depth_at(text, m.start()) != 0:
            continue
        ob = text.find('{', m.end() - 1)
        if ob < 0:
            continue
        ce = brace_match(text, ob)
        if ce > ob:
            spans.append((m.start(), ce))
    return spans


def _collect_add_ideas_blocks(text, include_date=False):
    """收集 add_ideas = { ... } 块，按 (depth == 0, 位置) 排序，可过滤日期块内部。"""
    dspans = _date_block_spans(text)
    out = []
    for a, b, body in find_blocks(text, "add_ideas"):
        if not include_date and any(ds < a < de for ds, de in dspans):
            continue
        hdr = text.rfind("add_ideas", 0, a)
        depth = _brace_depth_at(text, hdr if hdr >= 0 else a)
        out.append((depth, a, b, body))
    out.sort(key=lambda x: (0 if x[0] == 0 else 1, x[1]))
    return out, dspans


def _extract_ideas_from_blocks(blocks):
    out = []
    for _depth, _a, _b, body in blocks:
        for ln in body.splitlines():
            ln = ln.strip()
            if not ln or ln.startswith("#"):
                continue
            m = re.match(r'([A-Za-z][A-Za-z0-9_\-]*)\s*$', ln)
            if m:
                out.append(m.group(1))
    seen, uniq = set(), []
    for x in out:
        if x not in seen:
            seen.add(x)
            uniq.append(x)
    return uniq


def load_country_ideas(root=None, tag=""):
    """解析某国开局有效的 add_ideas（跳过 1939.1.1 等后续日期块）。

    格式和 set_technology 不同：
        add_ideas = {
            limited_exports        ← 直接写 id，没有 = 1
            mvlv_nuclear_winter
        }
    """
    root = paths._pick(root)
    tag = (tag or "").upper()
    if not tag:
        return {"ok": False, "msg": "没给 tag", "ideas": []}
    p, rel = _country_hist_file(root, tag)
    if not p:
        return {"ok": False, "msg": "找不到 %s 的国家历史文件" % tag, "ideas": []}
    try:
        raw = io.open(p, encoding="utf-8-sig", errors="replace").read()
    except Exception as e:
        return {"ok": False, "msg": "读取失败：%s" % e, "ideas": []}
    text = _strip_keep_len(raw)
    blocks, _dspans = _collect_add_ideas_blocks(text, include_date=False)
    uniq = _extract_ideas_from_blocks(blocks)
    return {"ok": True, "tag": tag, "file": os.path.basename(p),
            "blocks": len(blocks), "ideas": uniq, "count": len(uniq),
            "msg": "%s：%d 项国家精神（%d 个 add_ideas 块）" % (tag, len(uniq), len(blocks))}



def country_idea_toggle(root, tag, idea, on=True):
    """给某国开局加上或去掉一项国家精神（写顶层块，绕开日期块与条件块）。"""
    root = paths._pick(root)
    tag = (tag or "").upper()
    idea = (idea or "").strip()
    if not tag or not idea:
        return {"ok": False, "msg": "tag 和 idea id 都要给"}
    src, rel = _country_hist_file(root, tag)
    if not src:
        return {"ok": False, "msg": "找不到 %s 的国家历史文件" % tag}
    tgt, err = _country_hist_write_base(root)
    if not tgt:
        return {"ok": False, "msg": err}
    dst = os.path.join(tgt, rel)
    os.makedirs(os.path.dirname(dst) or tgt, exist_ok=True)
    if not os.path.exists(dst):
        try:
            import shutil as _sh
            _sh.copyfile(src, dst)
        except Exception as e:
            return {"ok": False, "msg": "复制来源失败：%s" % e}

    raw = io.open(dst, encoding="utf-8-sig", errors="replace").read()
    text = _strip_keep_len(raw)
    non_date_blocks, dspans = _collect_add_ideas_blocks(text, include_date=False)
    top_blocks = [blk for blk in non_date_blocks if blk[0] == 0]

    if on:
        if idea in _extract_ideas_from_blocks(top_blocks):
            return {"ok": True, "msg": "已经有 %s 了" % idea}
        if top_blocks:
            _depth, _a, b, _body = top_blocks[0]
            before = raw[:b - 1].rstrip(" \t")
            nl = "" if (not before or before.endswith(("\n", "\r"))) else "\n"
            new_text = before + nl + "\t" + idea + "\n" + raw[b - 1:]
        else:
            ins = "\nadd_ideas = {\n\t%s\n}\n" % idea
            if dspans:
                pos = dspans[0][0]
                new_text = raw[:pos].rstrip(" \t") + "\n" + ins + "\n" + raw[pos:]
            else:
                new_text = raw.rstrip() + "\n" + ins
        snapshot(dst)
        _atomic_write(dst, _bom_for(dst) + new_text.encode("utf-8"))
        msg = "已加 %s" % idea if top_blocks else "已加 %s（新建顶层 add_ideas 块）" % idea
        return {"ok": True, "msg": msg}

    all_blocks, _ = _collect_add_ideas_blocks(text, include_date=True)
    pat = re.compile(r'(?m)^[ \t]*' + re.escape(idea) + r'[ \t]*(?:\r?\n)?')
    new_text = None
    for _depth, a, b, _body in all_blocks:
        seg = raw[a:b - 1]
        seg2 = pat.sub('', seg)
        if seg2 != seg:
            new_text = raw[:a] + seg2 + raw[b - 1:]
            break
    if new_text is None:
        return {"ok": True, "msg": "本来就没有 %s" % idea}

    snapshot(dst)
    _atomic_write(dst, _bom_for(dst) + new_text.encode("utf-8"))
    return {"ok": True, "msg": "已删 %s" % idea}



def country_ideas_payload(root=None, tag=""):
    """界面用：已选中的国家精神 + 全部可选（按 state.ideas() 的分类）。"""
    info = load_country_ideas(root, tag)
    if not info.get("ok"):
        return info
    chosen = set(info["ideas"])
    items = []
    for k, v in sorted(state.ideas().items()):
        items.append({"id": k, "name": v.get("name") or k,
                      "pic": v.get("picture") or "",
                      "source": v.get("source") or "",
                      "on": k in chosen})
    # 已选但 state.ideas() 里没有的（可能是别处定义的）也列出来
    known = {x["id"] for x in items}
    for k in info["ideas"]:
        if k not in known:
            items.append({"id": k, "name": k, "pic": "", "source": "（未在 ideas 里找到定义）",
                          "on": True, "orphan": True})
    return {"ok": True, "tag": tag, "file": info["file"],
            "ideas": info["ideas"], "count": info["count"],
            "items": items, "total": len(items),
            "msg": info["msg"]}



def _adopt_idea_rel(root, rel):
    top = None
    for r in (state.roots() or []):
        lay = mod_layers(r) or [r]
        cand = lay[-1] if lay else r
        if cand and not is_under_game(cand):
            top = cand
    if not top and root and not is_under_game(root):
        top = root
    if not top:
        return None, None, "找不到可写的 mod 目录"
    dst = os.path.join(top, rel)
    if os.path.isfile(dst):
        return top, dst, ""
    cands = []
    if root:
        cands.append(os.path.join(root, rel))
    for b in reversed(mod_layers(top) or []):
        if b:
            cands.append(os.path.join(b, rel))
    src = next((c for c in cands if os.path.isfile(c)), None)
    if not src:
        return None, None, "找不到文件：" + rel
    os.makedirs(os.path.dirname(dst) or top, exist_ok=True)
    import shutil as _sh
    _sh.copyfile(src, dst)
    return top, dst, ""


def save_idea(root, rel, oid, rawtext, props=None, picture=""):
    if not rel or not oid:
        return False, "参数不完整：缺少文件或国家精神 id"
    explicit = {os.path.abspath(r) for r in (state.roots() or []) if r}
    need_adopt = (
        not root
        or is_under_game(root)
        or is_readonly_mod(root)
        or (bool(explicit) and os.path.abspath(root) not in explicit)
    )
    path = os.path.join(root, rel) if root else ""
    if need_adopt or not path or not os.path.isfile(path):
        top, path, err = _adopt_idea_rel(root, rel)
        if not path:
            return False, err
        root = top or root
    with io.open(path, "rb") as f:
        raw_bytes = f.read()
    text = raw_bytes.decode("utf-8-sig" if raw_bytes.startswith(b"\xef\xbb\xbf") else "utf-8", errors="replace")
    m = re.search(r'(?m)^[ \t]*%s\s*=\s*\{' % re.escape(oid), text)
    if not m:
        return False, "未找到国家精神 " + oid
    b = text.find('{', m.start())
    e = brace_match(text, b)
    if picture:
        rawtext = set_scalar(rawtext, "picture", picture)
    rawtext = apply_modifier_props(rawtext, props or {})
    for key, bname in (("allowed_raw", "allowed"), ("trigger_raw", "trigger"),
                       ("possible_raw", "possible")):
        if (props or {}).get(key):
            rawtext = set_raw_block(rawtext, bname, props.get(key))
    if not braces_balanced(rawtext):
        return False, "花括号不匹配，未保存"
    backup(path)
    newtext = text[:m.start()] + rawtext.strip() + "\n" + text[e:]
    snapshot(path)
    _atomic_write(path, _bom_for(path) + newtext.encode("utf-8"))
    state.changed()[path] = rel
    rb = rawtext.find("{")
    re_idx = rawtext.rfind("}")
    inner_body = rawtext[rb + 1:re_idx] if (rb >= 0 and re_idx > rb) else rawtext
    src = os.path.basename((root or "").rstrip("\\/")) or root
    state.ideas()[oid] = _build_idea_entry(oid, inner_body, rel, src)
    return True, "国家精神已保存"



def add_idea(root, oid):
    if not re.match(r'^[A-Za-z0-9_]+$', oid or ""):
        return False, "id 只能包含字母数字下划线"
    d = os.path.join(root, "common", "ideas")
    os.makedirs(d, exist_ok=True)
    fn = unique_editor_filename(root, "common/ideas", "zz_focus_editor_ideas.txt")
    path = os.path.join(d, fn)
    if os.path.exists(path):
        text = io.open(path, encoding="utf-8-sig", errors="replace", newline="").read()
    else:
        text = "ideas = {\n\tcountry = {\n\t}\n}\n"
    if re.search(r'(?m)^\s*%s\s*=\s*\{' % re.escape(oid), text):
        return False, "国家精神已存在: " + oid
    m = re.search(r'(?m)^\s*country\s*=\s*\{', text)
    if not m:
        text = "ideas = {\n\tcountry = {\n\t}\n}\n"
        m = re.search(r'(?m)^\s*country\s*=\s*\{', text)
    b = text.find('{', m.start())
    e = brace_match(text, b)
    block = "\n\t\t%s = {\n\t\t\tpicture = GFX_idea_generic_army_war_college\n\t\t\tmodifier = {\n\t\t\t}\n\t\t}\n" % oid
    prefix = text[:e - 1].rstrip(" \t")
    newtext = prefix + "\n" + block + "\t" + text[e - 1:]
    backup(path)
    snapshot(path)
    _atomic_write(path, _bom_for(path) + newtext.encode("utf-8"))
    rel = os.path.join("common", "ideas", fn)
    state.changed()[path] = rel
    ib = block.find("{")
    ie = block.rfind("}")
    inner_body = block[ib + 1:ie] if (ib >= 0 and ie > ib) else ""
    src = os.path.basename((root or "").rstrip("\\/")) or root
    state.ideas()[oid] = _build_idea_entry(oid, inner_body, rel, src)
    return True, "已新建国家精神 " + oid



def delete_idea(root, rel, oid):
    if not rel or not oid:
        return False, "参数不完整"
    path = os.path.join(root, rel) if root else ""
    if not path or not os.path.isfile(path) or is_under_game(root or ""):
        _top, path, err = _adopt_idea_rel(root, rel)
        if not path:
            return False, err
    text = io.open(path, encoding="utf-8-sig", errors="replace", newline="").read()
    m = re.search(r'(?m)^[ \t]*%s\s*=\s*\{' % re.escape(oid), text)
    if not m:
        return False, "未找到国家精神 " + oid
    b = text.find('{', m.start())
    e = brace_match(text, b)
    newtext = text[:m.start()] + text[e:]
    backup(path)
    snapshot(path)
    _atomic_write(path, _bom_for(path) + newtext.encode("utf-8"))
    state.changed()[path] = rel
    ideas = state.ideas()
    ideas.pop(oid, None)
    roots = list(state.roots() or [])
    if not roots and root:
        roots = [root]
    for r in reversed(roots):
        hit = False
        for base, d, fn in reversed(effective_layer_files("common/ideas", r)):
            fp = os.path.join(d, fn)
            try:
                txt = io.open(fp, encoding="utf-8-sig", errors="replace", newline="").read()
            except Exception:
                continue
            if oid not in txt:
                continue
            src_l = os.path.basename(base.rstrip("\\/")) or base
            rel_l = os.path.join("common", "ideas", fn)
            text_l = strip_comments(txt)
            for _s, _e, body in find_blocks(text_l, "ideas"):
                for k, v, b in top_items(body):
                    if not b:
                        continue
                    if k == oid and _looks_like_idea(v):
                        ideas[oid] = _build_idea_entry(oid, v, rel_l, src_l)
                        hit = True
                        break
                    if not _looks_like_idea(v):
                        for k2, v2, b2 in top_items(v):
                            if b2 and k2 == oid and _looks_like_idea(v2):
                                ideas[oid] = _build_idea_entry(oid, v2, rel_l, src_l)
                                hit = True
                                break
                        if hit:
                            break
                if hit:
                    break
            if hit:
                break
        if hit:
            break
    return True, "已删除国家精神 " + oid
