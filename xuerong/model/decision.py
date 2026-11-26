# -*- coding: utf-8 -*-
"""决议（decision）域（P2-rest 第 1 域，从 focus_editor.py 迁入）。

8 个函数：
  load_decisions / decisions_payload        —— 读 common/decisions 的类别与决议
  _dec_write_base / _dec_find               —— 写盘定位（自己算目标层 + 重新定位块）
  _dec_category_register                    —— 注册 common/decisions/categories/zz_editor_categories.txt
  decision_add / decision_set / decision_delete  —— 增 / 改 / 删

依赖边界：
  · DECISION_SKIP / DECISION_SCALARS 两个只读白名单 → xuerong.state
  · 叠加链与写盘目标 → xuerong.core.paths；文本定位与写入 → xuerong.core.text
  · 写前快照 → xuerong.model.history
  · 没有横切钩子，也不需要 bind()

注意 HOI4 语义：decisions 文件里出现的类别必须先在 categories 目录注册，
否则加载时报 "Unknown category: X" 并把该类别下所有决议忽略——见 _dec_category_register。
"""
import io
import os
import re

from xuerong import state
from xuerong.core.paths import (_layer_files, _replace_owner, is_under_game,
                                mod_layers, unique_editor_filename, write_base)
from xuerong.core.text import _atomic_write, _bom_for, _first, _strip_keep_len, brace_match
from xuerong.model.history import snapshot
from xuerong.state import DECISION_SCALARS, DECISION_SKIP


def _pick_root(root=None):
    if root:
        return root
    rs = state.roots()
    if rs:
        return rs[-1]
    return state.game()


def load_decisions(root=None):
    """解析 common/decisions 的类别与决策。

    结构：
        category_key = {
            decision_key = {
                icon = GFX_xxx
                priority = 1
                cost = 50
                fire_only_once = yes
                available = { … }        ← 脚本块，不动
                complete_effect = { … }  ← 脚本块，不动
            }
        }
    """
    root = _pick_root(root)
    files, _rep = _layer_files("common/decisions", mod_layers(root))
    cats, decisions = [], []
    seen_cat = set()
    for p in (files or []):
        try:
            with io.open(p, encoding="utf-8-sig", errors="replace") as f:
                raw = f.read()
        except Exception:
            continue
        text = _strip_keep_len(raw)
        rel = os.path.join("common", "decisions", os.path.basename(p))
        src = ""
        try:
            for b in (mod_layers(root) or []):
                if os.path.abspath(p).startswith(os.path.abspath(b) + os.sep):
                    src = os.path.basename(b.rstrip("\\/")) or b
                    break
        except Exception:
            pass
        # 顶层类别：行首无缩进的 key = {
        for m in re.finditer(r'(?m)^([A-Za-z][A-Za-z0-9_\-\.]*)[ \t]*=\s*\{', text):
            cname = m.group(1)
            if cname in ("decisions", "decision"):
                continue
            cb = text.find("{", m.end() - 1)
            ce = brace_match(text, cb)
            if ce <= cb:
                continue
            cbody = text[cb + 1:ce - 1]
            cid = cname
            if cid in seen_cat:
                continue
            seen_cat.add(cid)
            dlist = []
            for dm in re.finditer(r'(?m)^[ \t]*([A-Za-z][A-Za-z0-9_\-\.]*)[ \t]*=\s*\{', cbody):
                dname = dm.group(1)
                if dname in DECISION_SCALARS or dname in DECISION_SKIP:
                    continue
                db = cbody.find("{", dm.end() - 1)
                de = brace_match(cbody, db)
                if de <= db:
                    continue
                dbody = cbody[db + 1:de - 1]
                # 决策块里应该有至少一个已知字段，否则可能是别的结构
                scal = {}
                for k in DECISION_SCALARS:
                    if k in ("activation", "target_array", "target_trigger",
                             "state_target", "news_event"):
                        continue
                    v = _first(dbody, r'(?m)^\s*' + k + r'\s*=\s*"?([^"\s#]+)"?')
                    if v and v != "{":
                        scal[k] = v
                if not scal:
                    continue
                dline = cbody.rfind("\n", 0, dm.start()) + 1
                dlist.append({"id": dname, "cat": cid, "fields": scal,
                              "file": rel, "source": src,
                              "start": cb + 1 + dline,
                              "end": cb + 1 + de})
            cats.append({"id": cid, "count": len(dlist), "file": rel})
            decisions.extend(dlist)
    return {"ok": True, "categories": cats, "decisions": decisions,
            "cat_count": len(cats), "count": len(decisions),
            "msg": "%d 个类别，%d 条决议" % (len(cats), len(decisions))}



def _dec_write_base(root):
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
    owner = _replace_owner(root or top, "common/decisions")
    if owner and os.path.abspath(owner) != os.path.abspath(top):
        chain = [os.path.abspath(x) for x in (mod_layers(root or top) or []) if x]
        ab_top = os.path.abspath(top)
        ab_own = os.path.abspath(owner)
        # 只有当独占层严格高于当前可写层时才阻断；父层的 replace_path 不影响上层 submod 新增或单文件覆写
        if ab_own in chain and ab_top in chain and chain.index(ab_own) > chain.index(ab_top):
            nm = os.path.basename(owner.rstrip("\\/")) or owner
            return None, ("common/decisions 被 %s 的 replace_path 独占，"
                          "请先在「诊断 → 目录写入目标」里接管该目录" % nm)
    return top, ""



def _dec_find(root, did, info=None):
    """在文件里重新定位决策块，返回 (路径, start, end, record)。"""
    info = info or load_decisions(root)
    it = next((x for x in info["decisions"] if x["id"] == did), None)
    if not it:
        return None, -1, -1, None, "没有这条决议：%s" % did
    tgt, err = _dec_write_base(root)
    if not tgt:
        return None, -1, -1, None, err
    p = os.path.join(tgt, it["file"])
    os.makedirs(os.path.dirname(p) or tgt, exist_ok=True)
    src = None
    for q in (_layer_files("common/decisions", mod_layers(root))[0] or []):
        if os.path.basename(q) == os.path.basename(it["file"]):
            src = q
            break
    if not os.path.exists(p) and src:
        try:
            import shutil as _sh
            _sh.copyfile(src, p)
        except Exception as e:
            return None, -1, -1, None, "复制来源失败：%s" % e
    with io.open(p, encoding="utf-8-sig", errors="replace") as f:
        raw = f.read()
    text = _strip_keep_len(raw)
    a = b = -1
    for m in re.finditer(r'(?m)^([A-Za-z][A-Za-z0-9_\-\.]*)[ \t]*=\s*\{', text):
        cname = m.group(1)
        if cname in ("decisions", "decision"):
            continue
        cb = text.find("{", m.end() - 1)
        ce = brace_match(text, cb)
        if ce <= cb:
            continue
        cbody = text[cb + 1:ce - 1]
        for dm in re.finditer(r'(?m)^[ \t]*([A-Za-z][A-Za-z0-9_\-\.]*)[ \t]*=\s*\{', cbody):
            if dm.group(1) != did:
                continue
            db = cbody.find("{", dm.end() - 1)
            de = brace_match(cbody, db)
            if de > db:
                a = cb + 1 + db
                b = cb + 1 + de
                break
        if a >= 0:
            break
    if a < 0:
        return None, -1, -1, None, "重新定位失败"
    return p, a, b, it, ""



def _dec_category_register(root, category, icon="GFX_decision_category_generic"):
    """在 common/decisions/categories/ 注册一个决策类别。

    HOI4 1.13 起，decisions 文件里出现的类别必须先在 categories 目录注册，
    否则加载时报 "Unknown category: X" 并把该类别下的决议全部忽略。
    """
    tgt, err = _dec_write_base(root)
    if not tgt:
        return False, err
    d = os.path.join(tgt, "common", "decisions", "categories")
    os.makedirs(d, exist_ok=True)
    fn = unique_editor_filename(tgt, "common/decisions/categories", "zz_editor_categories.txt")
    p = os.path.join(d, fn)
    body = ('%s = {\n'
            '\ticon = %s\n'
            '\tvisible = {\n'
            '\t\talways = yes\n'
            '\t}\n'
            '\tallowed = {\n'
            '\t\talways = yes\n'
            '\t}\n'
            '}\n') % (category, icon)
    if os.path.exists(p):
        with io.open(p, encoding="utf-8-sig", errors="replace") as f:
            raw = f.read()
        if re.search(r'(?m)^[ \t]*' + re.escape(category) + r'[ \t]*=\s*\{', raw):
            return True, "类别已注册"
        new_text = raw.rstrip() + "\n\n" + body
    else:
        new_text = body
    if os.path.exists(p):
        snapshot(p)
    _atomic_write(p, _bom_for(p) + new_text.encode("utf-8"))
    return True, "已注册类别"



def decision_add(root, did, category, icon="GFX_decision_category_generic", cost=50,
                 fire_only_once=True, effect="add_political_power = 50",
                 category_new=None):
    """新建一条决议。

    最简结构：
        CATEGORY = {
            DID = {
                icon = GFX_xxx
                cost = 50
                fire_only_once = yes
                available = { always = yes }
                complete_effect = { add_political_power = 50 }
            }
        }
    effect 是要塞进 complete_effect 的脚本文本（一行或多行）。
    """
    root = _pick_root(root)
    did = (did or "").strip()
    category = (category_new or category or "").strip()
    if not did:
        return {"ok": False, "msg": "决议 id 不能为空"}
    if not category:
        return {"ok": False, "msg": "类别不能为空"}
    if not re.match(r'^[A-Za-z][A-Za-z0-9_\-\.]*$', did):
        return {"ok": False, "msg": "决议 id 只能用字母数字下划线，且以字母开头"}
    if not re.match(r'^[A-Za-z][A-Za-z0-9_\-\.]*$', category):
        return {"ok": False, "msg": "类别 id 格式不对"}
    try:
        cost = int(cost)
    except Exception:
        return {"ok": False, "msg": "cost 必须是整数"}
    if cost < 0:
        return {"ok": False, "msg": "cost 不能为负"}

    info = load_decisions(root)
    if any(x["id"] == did for x in info["decisions"]):
        return {"ok": False, "msg": "已经有同 id 的决议：%s" % did}

    tgt, err = _dec_write_base(root)
    if not tgt:
        return {"ok": False, "msg": err}
    d = os.path.join(tgt, "common", "decisions")
    os.makedirs(d, exist_ok=True)
    fn = unique_editor_filename(tgt, "common/decisions", "zz_editor_decisions.txt")
    p = os.path.join(d, fn)

    eff_lines = [ln.rstrip() for ln in (effect or "").splitlines() if ln.strip()]
    if not eff_lines:
        eff_lines = ["add_political_power = 50"]

    cat_exists = any(c["id"] == category for c in info["categories"])
    if not cat_exists:
        # 新类别必须先注册，否则 HOI4 报 Unknown category 并忽略整段决议
        _dec_category_register(root, category)
    if cat_exists:
        # 已有类别：往那个文件里加
        for c in info["categories"]:
            if c["id"] == category:
                p = os.path.join(tgt, c["file"])
                os.makedirs(os.path.dirname(p) or tgt, exist_ok=True)
                src = None
                for q in (_layer_files("common/decisions", mod_layers(root))[0] or []):
                    if os.path.basename(q) == os.path.basename(c["file"]):
                        src = q
                        break
                if not os.path.exists(p) and src:
                    try:
                        import shutil as _sh
                        _sh.copyfile(src, p)
                    except Exception as e:
                        return {"ok": False, "msg": "复制来源失败：%s" % e}
                break

    block = ['\t%s = {' % did,
             '\t\ticon = %s' % icon,
             '\t\tcost = %d' % cost,
             '\t\tfire_only_once = %s' % ("yes" if fire_only_once else "no"),
             '\t\tavailable = {',
             '\t\t\talways = yes',
             '\t\t}',
             '\t\tcomplete_effect = {']
    for ln in eff_lines:
        block.append('\t\t\t%s' % ln)
    block.append('\t\t}')
    block.append('\t}')
    block_txt = "\n".join(block) + "\n"

    if os.path.exists(p):
        with io.open(p, encoding="utf-8-sig", errors="replace") as f:
            raw = f.read()
    else:
        raw = ""

    text = _strip_keep_len(raw) if raw else ""
    if cat_exists and text:
        # 找那个类别块，插到它的 } 前
        cm = re.search(r'(?m)^[ \t]*' + re.escape(category) + r'[ \t]*=\s*\{', text)
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
                new_text = raw[:ls] + block_txt + raw[ls:]
            else:
                new_text = raw.rstrip() + "\n" + block_txt
        else:
            new_text = raw.rstrip() + "\n" + block_txt
    else:
        # 新文件或新类别
        cat_block = "%s = {\n%s}\n" % (category, block_txt)
        if raw.strip():
            new_text = raw.rstrip() + "\n\n" + cat_block
        else:
            new_text = cat_block

    if os.path.exists(p):
        snapshot(p)
    _atomic_write(p, _bom_for(p) + new_text.encode("utf-8"))
    where = "已有类别 %s" % category if cat_exists else "新建类别 %s" % category
    return {"ok": True, "msg": "已新建决议 %s（%s，cost %d）" % (did, where, cost)}



def decision_set(root, did, fields):
    """改决议的标量字段（icon / priority / cost / fire_only_once / days_remove 等）。"""
    root = _pick_root(root)
    did = (did or "").strip()
    if not did:
        return {"ok": False, "msg": "id 不能为空"}
    p, a, b, it, err = _dec_find(root, did)
    if not p:
        return {"ok": False, "msg": err}
    with io.open(p, encoding="utf-8-sig", errors="replace") as f:
        raw = f.read()
    seg = raw[a:b]
    new_seg = seg
    changed = []
    for k, v in (fields or {}).items():
        if k not in DECISION_SCALARS:
            continue
        if v in (None, ""):
            continue
        sv = str(v).strip()
        pat = re.compile(r'(?m)^([ \t]*)' + k + r'\s*=\s*[^\s#\r\n]+')
        if pat.search(new_seg):
            quoted = k in ("icon", "activation", "news_event")
            val = ('"%s"' % sv) if quoted else sv
            new_seg = pat.sub(lambda m: (m.group(1) or "") + "%s = %s" % (k, val),
                              new_seg, count=1)
            changed.append(k)
    if new_seg == seg:
        return {"ok": True, "msg": "没有改动（字段不存在或未变）"}
    new_text = raw[:a] + new_seg + raw[b:]
    snapshot(p)
    _atomic_write(p, _bom_for(p) + new_text.encode("utf-8"))
    return {"ok": True, "msg": "决议 %s 已更新：%s" % (did, ", ".join(changed))}



def decision_delete(root, did):
    """删掉一条决议（整块）。"""
    root = _pick_root(root)
    did = (did or "").strip()
    if not did:
        return {"ok": False, "msg": "id 不能为空"}
    p, a, b, it, err = _dec_find(root, did)
    if not p:
        return {"ok": False, "msg": err}
    with io.open(p, encoding="utf-8-sig", errors="replace") as f:
        raw = f.read()
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
    return {"ok": True, "msg": "已删除决议 %s" % did}



def decisions_payload(root=None):
    info = load_decisions(root)
    if not info.get("ok"):
        return info
    return {"ok": True, "categories": info["categories"],
            "decisions": info["decisions"], "count": info["count"],
            "cat_count": info["cat_count"],
            "scalars": list(DECISION_SCALARS), "msg": info["msg"]}

