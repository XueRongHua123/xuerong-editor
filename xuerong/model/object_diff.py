# -*- coding: utf-8 -*-
"""7-3 对象级覆盖对比（国策 / 事件 / 国家精神）。

依据 2026-11-20 HOI4 v1.19.5 实机 L3 对照结果（已归档至 `work/REFERENCES.md`）：
  · 三类对象对「同相对路径同名文件」均为整文件覆写（后加载层替代前加载层，0 报错）；
  · 若上层声明 `replace_path`，下层该目录文件全部被屏蔽；
  · 对「不同文件名定义的同一 ID」：
      - `events` 与 `ideas` 会在实机 `error.log` 报 Duplicate / Already exists 错误，标 `duplicate_error`；
      - `focus_tree` / `shared_focus` 实机 0 报错且按后加载覆写，跨树同名 `focus` 则各自留在所属树中。
"""
import difflib
import os
import re

from xuerong import state
from xuerong.core.paths import (_mod_descriptor, _mod_display_name, is_under_game,
                                mod_layers)
from xuerong.core.text import (_read_text, find_blocks, strip_comments, top_items)
from xuerong.model.focus import parse_focus_like
from xuerong.model.idea import _looks_like_idea

_OBJ_CACHE = {}

_CAT_DIRS = {
    "focus": "common/national_focus",
    "event": "events",
    "idea": "common/ideas",
}


def invalidate_object_cache():
    """清空对象级覆盖分析缓存。"""
    _OBJ_CACHE.clear()


def _extract_focus_records(layer_dir, layer_idx, layer_name):
    """从单层 `common/national_focus` 抽取 focus_tree / focus / shared_focus 摘要列表。"""
    d = os.path.join(layer_dir, "common", "national_focus")
    if not os.path.isdir(d):
        return []
    recs = []
    for fn in sorted(f for f in os.listdir(d) if f.lower().endswith(".txt")):
        rel = "common/national_focus/" + fn
        text = strip_comments(_read_text(os.path.join(d, fn)))
        for _, _, body in find_blocks(text, "shared_focus"):
            node = parse_focus_like(body, rel, layer_name)
            if node and node.get("id"):
                nid = node["id"]
                recs.append({
                    "cat": "focus",
                    "key": "focus:sf:" + nid,
                    "id": nid,
                    "subtype": "shared_focus",
                    "tree_id": "",
                    "layer": layer_idx,
                    "order": layer_idx + 1,
                    "layer_name": layer_name,
                    "rel": rel,
                    "summary": "shared_focus · cost=%s (%s,%s)" % (node.get("cost", ""), node.get("x", ""), node.get("y", "")),
                })
        for _, _, body in find_blocks(text, "focus_tree"):
            items = top_items(body)
            tid = ""
            f_nodes = []
            for k, v, b in items:
                if k == "id" and not b:
                    tid = (v or "").strip()
                elif k == "focus" and b:
                    node = parse_focus_like(v, rel, layer_name)
                    if node and node.get("id"):
                        f_nodes.append(node)
            if tid:
                recs.append({
                    "cat": "focus",
                    "key": "focus:tree:" + tid,
                    "id": tid,
                    "subtype": "focus_tree",
                    "tree_id": tid,
                    "layer": layer_idx,
                    "order": layer_idx + 1,
                    "layer_name": layer_name,
                    "rel": rel,
                    "summary": "focus_tree · 含 %d 个焦点" % len(f_nodes),
                })
            for node in f_nodes:
                nid = node["id"]
                recs.append({
                    "cat": "focus",
                    "key": "focus:node:" + nid,
                    "id": nid,
                    "subtype": "focus",
                    "tree_id": tid,
                    "layer": layer_idx,
                    "order": layer_idx + 1,
                    "layer_name": layer_name,
                    "rel": rel,
                    "summary": "tree=%s · cost=%s (%s,%s)" % (tid or "?", node.get("cost", ""), node.get("x", ""), node.get("y", "")),
                })
    return recs


def _extract_event_records(layer_dir, layer_idx, layer_name):
    """从单层 `events` 抽取 *_event 摘要列表。"""
    d = os.path.join(layer_dir, "events")
    if not os.path.isdir(d):
        return []
    recs = []
    for fn in sorted(f for f in os.listdir(d) if f.lower().endswith(".txt")):
        rel = "events/" + fn
        text = strip_comments(_read_text(os.path.join(d, fn)))
        for k, v, b in top_items(text):
            if not b or not k.endswith("_event"):
                continue
            m = re.search(r'(?m)^\s*id\s*=\s*"?([A-Za-z0-9_.\-]+)"?', v)
            if not m:
                continue
            eid = m.group(1)
            tm = re.search(r'(?m)^\s*title\s*=\s*"?([^"\r\n]+)"?', v)
            trig = "仅触发" if re.search(r'(?m)^\s*is_triggered_only\s*=\s*yes\b', v) else "MTTH/常规"
            opt_n = len(re.findall(r'(?m)^\s*option\s*=\s*\{', v))
            recs.append({
                "cat": "event",
                "key": "event:" + eid,
                "id": eid,
                "subtype": k,
                "tree_id": "",
                "layer": layer_idx,
                "order": layer_idx + 1,
                "layer_name": layer_name,
                "rel": rel,
                "summary": "%s · %s · %d 选项%s" % (k, trig, opt_n, (" · " + tm.group(1).strip()) if tm else ""),
            })
    return recs


def _extract_idea_records(layer_dir, layer_idx, layer_name):
    """从单层 `common/ideas` 抽取 idea 条目摘要列表。"""
    d = os.path.join(layer_dir, "common", "ideas")
    if not os.path.isdir(d):
        return []
    recs = []
    for fn in sorted(f for f in os.listdir(d) if f.lower().endswith(".txt")):
        rel = "common/ideas/" + fn
        text = strip_comments(_read_text(os.path.join(d, fn)))
        for _, _, body in find_blocks(text, "ideas"):
            for k, v, b in top_items(body):
                if not b:
                    continue
                if _looks_like_idea(v):
                    _append_idea_rec(recs, k, "ideas", v, rel, layer_idx, layer_name)
                else:
                    for k2, v2, b2 in top_items(v):
                        if b2 and _looks_like_idea(v2):
                            _append_idea_rec(recs, k2, k, v2, rel, layer_idx, layer_name)
    return recs


def _append_idea_rec(recs, iid, slot, body, rel, layer_idx, layer_name):
    mods = []
    for _, _, inner in find_blocks(body or "", "modifier"):
        for pm in re.finditer(r'(?m)^\s*([A-Za-z0-9_]+)\s*=\s*([^\s#]+)', inner):
            mods.append("%s=%s" % (pm.group(1), pm.group(2)))
            if len(mods) >= 3:
                break
        if len(mods) >= 3:
            break
    recs.append({
        "cat": "idea",
        "key": "idea:" + iid,
        "id": iid,
        "subtype": slot,
        "tree_id": "",
        "layer": layer_idx,
        "order": layer_idx + 1,
        "layer_name": layer_name,
        "rel": rel,
        "summary": "slot=%s%s" % (slot, (" · " + ", ".join(mods)) if mods else ""),
    })


def _highest_replace_idx(norm_layers, sub_rel):
    """找出声明了匹配 `sub_rel` 的 `replace_path` 的最高层索引，没有返回 None。"""
    norm_sub = sub_rel.replace("\\", "/").strip("/").lower()
    hit = None
    for idx, ab in enumerate(norm_layers):
        for rp in (_mod_descriptor(ab).get("replace") or []):
            rp_n = (rp or "").replace("\\", "/").strip("/").lower()
            if rp_n and (norm_sub == rp_n or norm_sub.startswith(rp_n + "/")):
                hit = idx
    return hit


def _build_object_index(norm_layers):
    layer_names = [_mod_display_name(r) for r in norm_layers]
    layer_meta = [
        {"index": i, "order": i + 1, "name": layer_names[i], "path": r}
        for i, r in enumerate(norm_layers)
    ]

    rep_idx_by_cat = {
        cat: _highest_replace_idx(norm_layers, sub)
        for cat, sub in _CAT_DIRS.items()
    }

    raw_recs = []
    for idx, ab in enumerate(norm_layers):
        ln = layer_names[idx]
        raw_recs.extend(_extract_focus_records(ab, idx, ln))
        raw_recs.extend(_extract_event_records(ab, idx, ln))
        raw_recs.extend(_extract_idea_records(ab, idx, ln))

    # 算出每个 (cat, rel.lower()) 在非被屏蔽层中的最高生效层（决定同名同路径文件覆写）
    eff_file_layer = {}
    for rec in raw_recs:
        cat = rec["cat"]
        rep_idx = rep_idx_by_cat.get(cat)
        if rep_idx is not None and rec["layer"] < rep_idx:
            continue
        fk = (cat, rec["rel"].lower())
        prev = eff_file_layer.get(fk)
        if prev is None or rec["layer"] > prev:
            eff_file_layer[fk] = rec["layer"]

    # 按 (cat, key) 聚合对象出现记录
    buckets = {}
    for rec in raw_recs:
        bk = (rec["cat"], rec["key"])
        b = buckets.get(bk)
        if b is None:
            b = {
                "cat": rec["cat"],
                "key": rec["key"],
                "id": rec["id"],
                "subtype": rec["subtype"],
                "records": [],
            }
            buckets[bk] = b
        b["records"].append(dict(rec))

    items = []
    for bk in sorted(buckets, key=lambda x: (x[0], buckets[x]["id"].lower(), x[1])):
        b = buckets[bk]
        cat = b["cat"]
        recs = b["records"]
        rep_idx = rep_idx_by_cat.get(cat)

        active_recs = []
        for r in recs:
            fk = (cat, r["rel"].lower())
            if rep_idx is not None and r["layer"] < rep_idx:
                r["state"] = "blocked_by_replace"
            elif eff_file_layer.get(fk, r["layer"]) > r["layer"]:
                r["state"] = "file_replaced"
            else:
                r["state"] = "active"
                active_recs.append(r)

        winner_layer = None
        winner_name = ""
        rule_note = ""

        if not active_recs:
            has_rep_block = any(r["state"] == "blocked_by_replace" for r in recs)
            status = "blocked" if has_rep_block else "removed_by_file"
            rule_note = (
                "已被上层 replace_path 屏蔽（游戏中不存在生效定义）"
                if has_rep_block
                else "上层同名同路径文件未保留此 ID（被整文件覆写移除）"
            )
        elif len(active_recs) == 1:
            win = active_recs[0]
            win["state"] = "winner"
            winner_layer = win["layer"]
            winner_name = win["layer_name"]
            if len(recs) > 1:
                status = "file_override"
                rule_note = "通过同名同路径文件整文件覆写下层版本，HOI4 零报错"
            else:
                status = "unique"
                rule_note = "仅单层定义"
        else:
            # >=2 个未被整文件覆写的存活定义（不同文件名或同文件内重复定义）
            if cat in ("event", "idea"):
                status = "duplicate_error"
                for r in active_recs:
                    r["state"] = "conflict_dup"
                rule_note = (
                    "不同文件名重复定义同一 ID：HOI4 1.19 实机报重复错误；"
                    "安全覆写请改写入与下层同相对路径的同名文件"
                )
            else:
                # focus 域：不同树同 node id vs 同树/shared_focus/focus_tree 后覆盖前
                trees = {r.get("tree_id") or "" for r in active_recs}
                if b["subtype"] == "focus" and len(trees) > 1 and len(trees) == len(active_recs):
                    status = "cross_tree"
                    for r in active_recs:
                        r["state"] = "cross_tree"
                    rule_note = "跨不同 focus_tree 定义同名节点：HOI4 主菜单不报冲突，分别保留在各自树中"
                else:
                    status = "id_override"
                    for r in active_recs[:-1]:
                        r["state"] = "def_overridden"
                    win = active_recs[-1]
                    win["state"] = "winner"
                    winner_layer = win["layer"]
                    winner_name = win["layer_name"]
                    rule_note = "国策树 / shared_focus 不同文件同名按加载顺序后覆盖前（实机零报错）"

        items.append({
            "cat": cat,
            "key": b["key"],
            "id": b["id"],
            "subtype": b["subtype"],
            "status": status,
            "winner_layer": winner_layer,
            "winner_order": (winner_layer + 1) if winner_layer is not None else None,
            "winner_name": winner_name,
            "rule_note": rule_note,
            "records": recs,
        })

    return {"layers": layer_meta, "items": items}


def _extract_raw_snippet(layer_dir, cat, subtype, obj_id, rel, tree_id=""):
    """按对象类别与 ID 从磁盘截取对应脚本原文块（最多 150 行）。"""
    fp = os.path.join(layer_dir, rel.replace("/", os.sep))
    if not os.path.isfile(fp):
        return ""
    text = strip_comments(_read_text(fp))
    block = ""
    if cat == "focus":
        if subtype == "shared_focus":
            for _, _, body in find_blocks(text, "shared_focus"):
                if re.search(r'(?m)^\s*id\s*=\s*"?%s"?\b' % re.escape(obj_id), body):
                    block = "shared_focus = {\n%s\n}" % body.strip()
                    break
        elif subtype == "focus_tree":
            for _, _, body in find_blocks(text, "focus_tree"):
                if re.search(r'(?m)^\s*id\s*=\s*"?%s"?\b' % re.escape(obj_id), body):
                    block = "focus_tree = {\n%s\n}" % body.strip()
                    break
        else:
            for _, _, body in find_blocks(text, "focus_tree"):
                if tree_id:
                    m_tid = re.search(r'(?m)^\s*id\s*=\s*"?([A-Za-z0-9_.\-]+)"?', body)
                    if m_tid and m_tid.group(1) != tree_id:
                        continue
                for _, _, fbody in find_blocks(body, "focus"):
                    if re.search(r'(?m)^\s*id\s*=\s*"?%s"?\b' % re.escape(obj_id), fbody):
                        block = "focus = {\n%s\n}" % fbody.strip()
                        break
                if block:
                    break
    elif cat == "event":
        for k, v, is_blk in top_items(text):
            if is_blk and k.endswith("_event") and re.search(r'(?m)^\s*id\s*=\s*"?%s"?\b' % re.escape(obj_id), v):
                block = "%s = {\n%s\n}" % (k, v.strip())
                break
    elif cat == "idea":
        for _, _, body in find_blocks(text, "ideas"):
            for k, v, is_blk in top_items(body):
                if not is_blk:
                    continue
                if k == obj_id and _looks_like_idea(v):
                    block = "%s = {\n%s\n}" % (k, v.strip())
                    break
                for k2, v2, b2 in top_items(v):
                    if b2 and k2 == obj_id and _looks_like_idea(v2):
                        block = "%s = {\n%s\n}" % (k2, v2.strip())
                        break
                if block:
                    break
            if block:
                break
    lines = block.splitlines()
    if len(lines) > 150:
        return "\n".join(lines[:150]) + "\n# ...（共 %d 行，已截断）" % len(lines)
    return block


def analyze_objects(layers=None, cat="all", status="interacted", query="",
                    layer_filter="", obj_key="", limit=200, refresh=False):
    """7-3 入口：返回各层对象覆盖汇总；传入 obj_key 时附加逐层源码与 unified diff。"""
    if layers is None:
        layers = mod_layers(None) or ([state.game()] if state.game() else [])
    norm_layers = [os.path.abspath(r) for r in (layers or []) if r and os.path.isdir(r)]
    ck = tuple(
        (r, tuple(_mod_descriptor(r).get("replace") or []))
        for r in norm_layers
    )
    if refresh or ck not in _OBJ_CACHE:
        if len(_OBJ_CACHE) >= 4:
            _OBJ_CACHE.clear()
        _OBJ_CACHE[ck] = _build_object_index(norm_layers)
    idx_data = _OBJ_CACHE[ck]

    # 单条对象源码对比请求
    if obj_key:
        hit = next((it for it in idx_data["items"] if it["key"] == obj_key), None)
        if not hit:
            return {"ok": False, "msg": "找不到对象: " + obj_key}
        enriched = []
        for rec in hit["records"]:
            r_copy = dict(rec)
            r_copy["raw"] = _extract_raw_snippet(
                norm_layers[rec["layer"]], hit["cat"], hit["subtype"],
                hit["id"], rec["rel"], rec.get("tree_id", ""),
            )
            enriched.append(r_copy)
        diff_text = ""
        if len(enriched) >= 2:
            base_rec = enriched[0]
            top_rec = next((r for r in reversed(enriched) if r.get("state") == "winner"), enriched[-1])
            if base_rec is not top_rec:
                diff_lines = list(difflib.unified_diff(
                    (base_rec.get("raw") or "").splitlines(),
                    (top_rec.get("raw") or "").splitlines(),
                    fromfile="#%d %s (%s)" % (base_rec["order"], base_rec["layer_name"], base_rec["rel"]),
                    tofile="#%d %s (%s)" % (top_rec["order"], top_rec["layer_name"], top_rec["rel"]),
                    lineterm="",
                ))
                diff_text = "\n".join(diff_lines[:240])
        return {
            "ok": True,
            "item": dict(hit, records=enriched, diff=diff_text),
        }

    # 列表过滤统计
    c_filter = (cat or "all").strip().lower()
    s_filter = (status or "interacted").strip().lower()
    q = (query or "").strip().lower()
    lf = None
    if str(layer_filter).strip() != "":
        try:
            lf = int(layer_filter)
        except Exception:
            lf = None
    lim = max(1, min(int(limit or 200), 1000))

    stats = {
        "total": 0,
        "interacted": 0,
        "duplicate_error": 0,
        "file_override": 0,
        "id_override": 0,
        "blocked": 0,
        "by_cat": {"focus": 0, "event": 0, "idea": 0},
    }
    matched = []
    for it in idx_data["items"]:
        st = it["status"]
        stats["total"] += 1
        stats["by_cat"][it["cat"]] = stats["by_cat"].get(it["cat"], 0) + 1
        if st != "unique":
            stats["interacted"] += 1
        if st == "duplicate_error":
            stats["duplicate_error"] += 1
        elif st == "file_override":
            stats["file_override"] += 1
        elif st in ("id_override", "cross_tree"):
            stats["id_override"] += 1
        elif st in ("blocked", "removed_by_file"):
            stats["blocked"] += 1

        if c_filter != "all" and it["cat"] != c_filter:
            continue
        if s_filter == "interacted" and st == "unique":
            continue
        elif s_filter == "duplicate_error" and st != "duplicate_error":
            continue
        elif s_filter == "file_override" and st != "file_override":
            continue
        elif s_filter == "id_override" and st not in ("id_override", "cross_tree"):
            continue
        elif s_filter == "blocked" and st not in ("blocked", "removed_by_file"):
            continue
        elif s_filter == "non_vanilla":
            wl = it.get("winner_layer")
            if wl is None or is_under_game(norm_layers[wl]):
                continue

        if q:
            in_id = q in it["id"].lower()
            in_file = any(q in r["rel"].lower() for r in it["records"])
            if not (in_id or in_file):
                continue
        if lf is not None and not any(r["layer"] == lf for r in it["records"]):
            continue
        matched.append(it)

    return {
        "ok": True,
        "layers": idx_data["layers"],
        "stats": stats,
        "matched_count": len(matched),
        "items": matched[:lim],
    }
