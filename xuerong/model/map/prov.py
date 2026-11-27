# -*- coding: utf-8 -*-
"""省的操作与校验：点级撤销、跨省修复、编辑笔刷、合并、邻居、完整性检查、分析。"""
import io
import json
import os
import re
import time

from xuerong import state
from xuerong.core.paths import (_layers_find, _out_path, _out_read_path,
                                _read_bom_text, _write_bom_text,
                                effective_layer_files, ensure_writable_file,
                                is_readonly_mod, is_under_game, mod_layers)
from xuerong.core.text import _atomic_write, _strip_keep_len, brace_match, strip_comments
from xuerong.model.history import snapshot
from xuerong.model.map._inj import (_parse_state_provinces, _set_state_provinces,
                                   _state_locate)
from xuerong.model.map.io import (_csv_path_for, _ensure_map_writable,
                                 _ensure_prov_rgb, _map_dir,
                                 _map_ids_from_cache, _map_pick,
                                 _writable_map_top, bmp_info, bmp_read_rect,
                                 bmp_write_rect)
from xuerong.model.map.render import _strategic_regions


def _save_point_undo(bmp, changes):
    """把「像素索引 → 原 RGB」存成紧凑二进制（4 字节索引 + 3 字节 RGB）。

    散布型改动（十字交叉修复）用包围盒备份会长到几十 MB，实际只改了几百个像素。"""
    import struct
    os.makedirs(state.map_var("MAP_UNDO_DIR"), exist_ok=True)
    seq = int(time.time() * 1000)
    fn = os.path.join(state.map_var("MAP_UNDO_DIR"), "pt%d.bin" % seq)
    buf = bytearray()
    buf += struct.pack("<I", len(changes))
    for idx, rgb in changes:
        buf += struct.pack("<I", idx)
        buf += bytes((rgb[0], rgb[1], rgb[2]))
    _atomic_write(fn, bytes(buf))
    return fn

def _load_point_undo(fn):
    """读回点级备份 → [(idx, (r,g,b)), ...]"""
    import struct
    with io.open(fn, "rb") as _f:
        raw = _f.read()
    if len(raw) < 4:
        return []
    n = struct.unpack("<I", raw[:4])[0]
    out = []
    off = 4
    for _ in range(n):
        if off + 7 > len(raw):
            break
        idx = struct.unpack("<I", raw[off:off + 4])[0]
        r, g, b = raw[off + 4], raw[off + 5], raw[off + 6]
        out.append((idx, (r, g, b)))
        off += 7
    return out

def _apply_point_undo(entry):
    """把点级备份写回 bmp（按行分组批量写，减少 IO）"""
    bmp = entry.get("bmp")
    pts = _load_point_undo(entry.get("file") or "")
    if not bmp or not pts:
        return 0
    info = bmp_info(bmp)
    if not info:
        return 0
    w, h = info["w"], info["h"]
    # 按包围盒一次读、逐点改、一次写
    xs = [i % w for i, _ in pts]
    ys = [i // w for i, _ in pts]
    bx, by = min(xs), min(ys)
    bw, bh = max(xs) - bx + 1, max(ys) - by + 1
    rect = bmp_read_rect(bmp, bx, by, bw, bh)
    if rect is None:
        return 0
    for idx, rgb in pts:
        o = (idx // w - by) * bw + (idx % w - bx)
        if 0 <= o < len(rect):
            rect[o] = rgb
    bmp_write_rect(bmp, bx, by, bw, bh, rect)
    return len(pts)

def _scan_cross(allpx, w, h):
    """找出所有 2x2 十字模式：左上==右下 且 右上==左下 且 A!=B。返回 [(x, y, A, B)]"""
    out = []
    for y in range(h - 1):
        base = y * w
        nxt = base + w
        for x in range(w - 1):
            a = allpx[base + x]
            b = allpx[base + x + 1]
            c = allpx[nxt + x]
            d = allpx[nxt + x + 1]
            if a == d and b == c and a != b:
                out.append((x, y, a, b))
    return out

def map_repair_cross(root=None, apply=False, adopt=False, limit=2000, **kw):
    """修十字交叉像素：把 2x2 的 `A B / B A` 解成 `A A / B B` 或 `A B / A B`。
    选择依据：看 A 在上方还是左方的邻域更多，优先保持那个方向的连通。"""
    apply_fix = bool(apply or kw.get("apply_fix"))
    root = _map_pick(root)
    layers = mod_layers(root)
    bmp, prov = _layers_find("map/provinces.bmp", layers)
    if not bmp:
        return {"ok": False, "msg": "找不到 provinces.bmp"}
    info = bmp_info(_out_read_path(bmp))
    if not info or info["bpp"] != 24:
        return {"ok": False, "msg": "只支持 24 位 BMP"}
    w, h = info["w"], info["h"]
    allpx = bmp_read_rect(bmp, 0, 0, w, h)
    if allpx is None:
        return {"ok": False, "msg": "读图失败"}
    crosses = _scan_cross(allpx, w, h)
    if not crosses:
        return {"ok": True, "found": 0, "fixed": 0, "msg": "没有十字交叉"}

    # 决定每处怎么解
    changes = []      # [(x, y, new_rgb)]
    plan = {"h": 0, "v": 0, "tie": 0}
    for (x, y, a, b) in crosses[:limit]:
        up = allpx[(y - 1) * w + x] if y > 0 else None
        left = allpx[y * w + (x - 1)] if x > 0 else None
        a_up = (up == a)
        a_left = (left == a)
        if a_up and not a_left:
            # A 在上方更连贯 → 纵向切：把 (x, y+1) 的 B 改成 A
            changes.append((x, y + 1, a))
            plan["v"] += 1
        elif a_left and not a_up:
            # A 在左方更连贯 → 横向切：把 (x+1, y) 的 B 改成 A
            changes.append((x + 1, y, a))
            plan["h"] += 1
        else:
            # 无法判断：默认横向（改动更集中在上方）
            changes.append((x + 1, y, a))
            plan["tie"] += 1

    result = {"ok": True, "found": len(crosses), "planned": len(changes),
              "plan": plan, "applied": 0}
    if not apply_fix:
        result["msg"] = "发现 %d 处十字交叉（横向 %d / 纵向 %d / 默认 %d），未改动" % (
            len(crosses), plan["h"], plan["v"], plan["tie"])
        result["sample"] = [{"x": x, "y": y} for (x, y, _c) in changes[:20]]
        return result

    bmp, _prov, berr = _ensure_map_writable("provinces.bmp", root=root, adopt=adopt)
    if not bmp:
        return berr

    # 应用：点级备份（散布改动用包围盒会备份整幅图，30+ MB，实际只改几百个像素）
    # 多轮迭代只记「第一次遇到该像素时的原值」，最后统一存成一个 undo 条目，
    # 否则撤销只能退回到上一轮，而不是修复前的状态。
    xs = [c[0] for c in changes]
    ys = [c[1] for c in changes]
    x0, x1 = max(0, min(xs)), min(w - 1, max(xs))
    y0, y1 = max(0, min(ys)), min(h - 1, max(ys))
    bw, bh = x1 - x0 + 1, y1 - y0 + 1
    before = bmp_read_rect(bmp, x0, y0, bw, bh)
    if before is None:
        return {"ok": False, "msg": "读 bmp 区域失败"}
    after = list(before)
    orig_vals = {}
    for (cx, cy, rgb) in changes:
        o = (cy - y0) * bw + (cx - x0)
        if 0 <= o < len(after):
            gi = cy * w + cx
            if gi not in orig_vals:
                orig_vals[gi] = tuple(before[o])
            after[o] = rgb
    if not bmp_write_rect(bmp, x0, y0, bw, bh, after):
        return {"ok": False, "msg": "provinces.bmp 写入失败（仅支持 24 位无压缩 BMP）"}
    result["applied"] = len(changes)

    # 改像素会产生新的交叉，迭代几轮直到不再减少
    rounds = 1
    prev = len(crosses)
    while rounds < 4:
        allpx2 = bmp_read_rect(bmp, 0, 0, w, h)
        cs2 = _scan_cross(allpx2, w, h) if allpx2 else []
        if not cs2 or len(cs2) >= prev:
            break
        prev = len(cs2)
        ch2 = []
        for (x, y, a, b) in cs2:
            up = allpx2[(y - 1) * w + x] if y > 0 else None
            left = allpx2[y * w + (x - 1)] if x > 0 else None
            ch2.append((x + 1 if (left == a or up != a) else x,
                        y if (left == a or up != a) else y + 1, a))
        xs2 = [c[0] for c in ch2]
        ys2 = [c[1] for c in ch2]
        ax0, ax1 = max(0, min(xs2)), min(w - 1, max(xs2))
        ay0, ay1 = max(0, min(ys2)), min(h - 1, max(ys2))
        aw, ah = ax1 - ax0 + 1, ay1 - ay0 + 1
        bef2 = bmp_read_rect(bmp, ax0, ay0, aw, ah)
        if bef2 is None:
            break
        aft2 = list(bef2)
        for (cx, cy, rgb) in ch2:
            _i = (cy - ay0) * aw + (cx - ax0)
            if 0 <= _i < len(aft2):
                gi2 = cy * w + cx
                if gi2 not in orig_vals:
                    orig_vals[gi2] = tuple(bef2[_i])
                aft2[_i] = rgb
        if not bmp_write_rect(bmp, ax0, ay0, aw, ah, aft2):
            break
        result["applied"] += len(ch2)
        rounds += 1

    # 所有轮次合成一个 undo 条目
    _pts = [(gi, rgb) for gi, rgb in orig_vals.items()]
    _fn = _save_point_undo(bmp, _pts)
    state.map_var("MAP_EDIT")["undo"].append({"file": _fn, "bmp": bmp, "kind": "points",
                             "count": len(_pts), "rect": [x0, y0, bw, bh]})
    state.map_var("MAP_EDIT")["redo"] = []

    result["rounds"] = rounds
    result["remaining"] = prev
    msg = "已修复 %d 处十字交叉（%d 轮），剩余约 %d 处（图层需要重建）" % (
        result["applied"], rounds, prev)
    if berr and berr.get("adopted"):
        adopt_msg = berr.get("adopt_msg") or "已单文件接管 map/provinces.bmp"
        result["adopted"] = True
        result["adopt_msg"] = adopt_msg
        msg = adopt_msg + "；" + msg
    result["msg"] = msg
    return result

def map_repair_preview(root=None):
    """列出能自动修的问题及其影响面（不改文件）"""
    root = _map_pick(root)
    dirp, key, base = _map_dir(root)
    idx_path = os.path.join(dirp or "", "prov_index.json")
    if not os.path.exists(idx_path):
        return {"ok": False, "msg": "请先构建图层"}
    try:
        with io.open(idx_path, encoding="utf-8") as _f:
            idx = json.loads(_f.read())
    except Exception as e:
        return {"ok": False, "msg": "读取索引失败：%s" % e}
    have = set()
    for k, v in idx.items():
        try:
            if int(v.get("px") or 0) > 0:
                have.add(int(k))
        except Exception:
            continue
    csvp, prov = _csv_path_for(root)
    if not csvp:
        return {"ok": False, "msg": "找不到 definition.csv"}
    ghost = []
    total = 0
    try:
        with io.open(_out_read_path(csvp), encoding="utf-8-sig", errors="replace") as _f:
            for line in _f:
                parts = line.strip().split(";")
                if len(parts) < 4 or not parts[0].isdigit():
                    continue
                total += 1
                pid = int(parts[0])
                if pid == 0:
                    continue
                if pid not in have:
                    ghost.append(pid)
    except Exception as e:
        return {"ok": False, "msg": "读 csv 失败：%s" % e}
    return {"ok": True, "csv": csvp, "csv_from": prov, "csv_rows": total,
            "ghost": sorted(ghost)[:500], "ghost_count": len(ghost),
            "repairable": {"ghost": len(ghost)}}

def map_repair_ghost(root=None, adopt=False):
    """删除 definition.csv 末尾连续段的幽灵省（省 0 与中间省号段全部保留，防止断号）。"""
    root = _map_pick(root)
    dirp, _key, _base = _map_dir(root)
    idx_path = os.path.join(dirp or "", "prov_index.json")
    if not os.path.exists(idx_path):
        return {"ok": False, "msg": "请先构建图层"}
    try:
        with io.open(idx_path, encoding="utf-8") as _f:
            idx = json.loads(_f.read())
    except Exception as e:
        return {"ok": False, "msg": "读取索引失败：%s" % e}
    have = set()
    for k, v in idx.items():
        try:
            if int(v.get("px") or 0) > 0:
                have.add(int(k))
        except Exception:
            continue

    csv_src, _prov = _csv_path_for(root)
    if not csv_src:
        return {"ok": False, "msg": "找不到 definition.csv"}
    try:
        with io.open(_out_read_path(csv_src), encoding="utf-8-sig", errors="replace") as _f:
            text_pre = _f.read()
    except Exception as e:
        return {"ok": False, "msg": "读 csv 失败：%s" % e}

    all_pids = []
    ghost_pids = set()
    for line in text_pre.splitlines():
        parts = line.strip().split(";")
        if len(parts) >= 4 and parts[0].isdigit():
            pid = int(parts[0])
            all_pids.append(pid)
            if pid > 0 and pid not in have:
                ghost_pids.add(pid)
    if not ghost_pids:
        return {"ok": True, "removed": 0, "skipped": 0, "msg": "没有幽灵省，不需要修"}

    # 严格只删位于最高有效省号之后末尾段的幽灵省，中间段保留以防省号断号
    max_active = max((pid for pid in all_pids if pid == 0 or pid in have), default=0)
    removable = {pid for pid in ghost_pids if pid > max_active}
    skipped = sorted(pid for pid in ghost_pids if pid <= max_active)
    if not removable:
        return {"ok": True, "removed": 0, "skipped": len(skipped),
                "skipped_ids": skipped[:30], "csv": csv_src,
                "msg": "发现 %d 个幽灵省，但均位于中间省号段（为防断号已全部跳过，未改动）" % len(skipped)}

    csvp, cbase, cerr = _ensure_map_writable("definition.csv", root=root, adopt=adopt)
    if not csvp:
        return cerr

    try:
        with io.open(_out_read_path(csvp), encoding="utf-8-sig", errors="replace", newline="") as _f:
            text = _f.read()
    except Exception as e:
        return {"ok": False, "msg": "读 csv 失败：%s" % e}
    keep = []
    removed = []
    for line in text.splitlines(True):
        parts = line.rstrip("\r\n").split(";")
        if len(parts) >= 4 and parts[0].isdigit():
            pid = int(parts[0])
            if pid in removable:
                removed.append(pid)
                continue
        keep.append(line)
    new_text = "".join(keep)
    snapshot(csvp)
    target_csv = _out_path(csvp)
    try:
        _atomic_write(target_csv, new_text.encode("utf-8"))
    except Exception as e:
        return {"ok": False, "msg": "写 csv 失败：%s" % e}
    try:
        state.changed()[target_csv] = os.path.relpath(csvp, cbase or os.path.dirname(os.path.dirname(csvp)))
    except Exception:
        pass
    state.map_var("PROV_RGB").clear()
    state.map_var("_PROV_RGB_CACHE").clear()
    try:
        state.map_var("_REFINE_IDS_CACHE").pop("cur", None)
    except Exception:
        pass
    msg = "已删除末尾连续幽灵省 %d 个" % len(removed)
    if skipped:
        msg += "（跳过中间断号风险幽灵省 %d 个）" % len(skipped)
    msg += "，图层需要重建"
    out = {"ok": True, "removed": len(removed), "skipped": len(skipped),
           "ids": removed[:30], "skipped_ids": skipped[:30], "csv": target_csv, "msg": msg}
    if cerr and cerr.get("adopted"):
        adopt_msg = cerr.get("adopt_msg") or "已单文件接管 map/definition.csv"
        out["adopted"] = True
        out["adopt_msg"] = adopt_msg
        out["msg"] = adopt_msg + "；" + msg
    return out

def map_analysis(root=None, limit=60, min_px=800, only_land=True):


    """省份排名：按面积（像素数）列出大省，附州/战略区/地形。
    数据直接来自图层缓存的 prov_index.json，不重新扫像素。"""
    root = _map_pick(root)
    if not root:
        return {"ok": False, "msg": "还没有加载 mod"}
    dirp, key, base = _map_dir(root)
    idx_path = os.path.join(dirp or "", "prov_index.json")
    if not os.path.exists(idx_path):
        return {"ok": False, "msg": "请先构建图层（缺少 prov_index.json）"}
    try:
        with io.open(idx_path, encoding="utf-8") as _f:
            idx = json.loads(_f.read())
    except Exception as e:
        return {"ok": False, "msg": "读取索引失败：%s" % e}

    rows = []
    total_px = 0
    for pid_s, rec in idx.items():
        try:
            px = int(rec.get("px") or 0)
            pid = int(pid_s)
        except Exception:
            continue
        if pid <= 0 or px <= 0:
            continue
        _type = rec.get("type") or ""
        if only_land and _type and _type != "land":
            continue          # 海省湖省不需要细化，默认排除
        total_px += px
        rows.append({"pid": pid, "px": px, "state": rec.get("state") or 0,
                     "region": rec.get("region") or 0, "terrain": rec.get("terrain") or "",
                     "continent": rec.get("continent") or 0, "type": rec.get("type") or ""})
    if not rows:
        return {"ok": False, "msg": "索引里没有有效省份"}
    rows.sort(key=lambda r: -r["px"])
    px_all = sorted(r["px"] for r in rows)
    n = len(px_all)
    median = px_all[n // 2] if n else 0
    mean = total_px / n if n else 0
    big = [r for r in rows if r["px"] >= min_px]
    st_agg = {}
    for r in rows:
        sid = r["state"]
        a = st_agg.setdefault(sid, {"state": sid, "n": 0, "px": 0, "max": 0})
        a["n"] += 1
        a["px"] += r["px"]
        a["max"] = max(a["max"], r["px"])
    st_rows = sorted(st_agg.values(), key=lambda a: -(a["px"] / max(1, a["n"])))[:20]
    for a in st_rows:
        a["avg"] = round(a["px"] / max(1, a["n"]))
    return {"ok": True, "count": n, "total_px": total_px, "mean": round(mean),
            "median": median, "min_px": min_px, "big_count": len(big),
            "top": rows[:limit], "big": big[:limit], "states": st_rows, "source": base}

def map_edit_begin(bmp_path):
    """开始一次地图编辑事务：清空待提交队列"""
    state.map_var("MAP_EDIT")["pending"] = []
    state.map_var("MAP_EDIT")["file"] = bmp_path
    state.map_var("MAP_EDIT")["touched"] = set()
    return True

def map_edit_dab(bmp_path, x, y, radius, rgb):
    """在事务里画一笔（圆），记录待写像素；返回实际影响的像素数"""
    info = bmp_info(bmp_path)
    if not info:
        return 0
    w, h = info["w"], info["h"]
    n = 0
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            if dx * dx + dy * dy > radius * radius:
                continue
            px, py = x + dx, y + dy
            if 0 <= px < w and 0 <= py < h:
                state.map_var("MAP_EDIT")["pending"].append((px, py, rgb))
                state.map_var("MAP_EDIT")["touched"].add((px, py))
                n += 1
    return n

def map_edit_commit(bmp_path=None):
    """提交事务：先保存受影响区域的原始像素（供撤销），再原位写入"""
    bmp_path = bmp_path or state.map_var("MAP_EDIT").get("file")
    pend = state.map_var("MAP_EDIT").get("pending") or []
    if not bmp_path or not pend:
        return {"ok": False, "msg": "没有待写入的像素"}
    if is_readonly_mod(bmp_path):
        return {"ok": False, "msg": "原版或工坊只读目录，不能直接提交涂色"}
    info = bmp_info(_out_read_path(bmp_path))
    if not info:
        return {"ok": False, "msg": "读不到 bmp 头"}
    xs = [p[0] for p in pend]
    ys = [p[1] for p in pend]
    x0, x1 = min(xs), max(xs)
    y0, y1 = min(ys), max(ys)
    w, h = x1 - x0 + 1, y1 - y0 + 1
    before = bmp_read_rect(bmp_path, x0, y0, w, h)
    if before is None:
        return {"ok": False, "msg": "只支持 24 位 BMP"}
    # 组装新像素
    grid = {(px - x0, py - y0): rgb for (px, py, rgb) in pend}
    after = list(before)
    for (gx, gy), rgb in grid.items():
        after[gy * w + gx] = rgb
    if not bmp_write_rect(bmp_path, x0, y0, w, h, after):
        return {"ok": False, "msg": "provinces.bmp 写入失败（仅支持 24 位无压缩 BMP）"}
    # 存撤销区块。
    # 包围盒备份的代价是 w*h*3 字节——一次改散布在图两头的几百个像素，
    # 包围盒能覆盖整张 5632x2048 的图，单次 33MB。密度低于 35% 时改存点级
    # （每点 7 字节），同样的改动只要几百字节。
    os.makedirs(state.map_var("MAP_UNDO_DIR"), exist_ok=True)
    seq = int(time.time() * 1000)
    area = w * h
    use_points = area > 0 and len(pend) < area * 0.35
    if use_points:
        W_full = info["w"]
        changes = []
        for (px, py, rgb) in pend:
            old_rgb = before[(py - y0) * w + (px - x0)]
            changes.append((py * W_full + px, old_rgb))
        fn = _save_point_undo(bmp_path, changes)
        state.map_var("MAP_EDIT")["undo"].append({"kind": "points", "file": fn, "bmp": bmp_path,
                                 "count": len(pend)})
    else:
        fn = os.path.join(state.map_var("MAP_UNDO_DIR"), "u%d_%d_%d_%d_%d.bin" % (seq, x0, y0, w, h))
        with open(fn, "wb") as f:
            for (r, g, b) in before:
                f.write(bytes((r, g, b)))
        state.map_var("MAP_EDIT")["undo"].append({"file": fn, "bmp": bmp_path, "x": x0, "y": y0,
                                 "w": w, "h": h, "count": len(pend)})
    state.map_var("MAP_EDIT")["redo"] = []
    state.map_var("MAP_EDIT")["pending"] = []
    state.map_var("MAP_EDIT")["touched"] = set()
    return {"ok": True, "pixels": len(pend), "rect": [x0, y0, w, h],
            "backup": "points" if use_points else "rect",
            "undo_depth": len(state.map_var("MAP_EDIT")["undo"])}

def map_edit_undo():
    if not state.map_var("MAP_EDIT")["undo"]:
        return {"ok": False, "msg": "没有可撤销的地图编辑"}
    u = state.map_var("MAP_EDIT")["undo"].pop()
    # 点级备份（十字交叉修复等散布型改动）：逐点写回，不记录 redo
    if u.get("kind") == "points":
        n = _apply_point_undo(u)
        state.map_var("MAP_EDIT")["redo"] = []
        return {"ok": True, "restored": n, "kind": "points",
                "msg": "已撤销 %d 个像素的改动（点级备份，不支持重做）" % n}
    cur = bmp_read_rect(u["bmp"], u["x"], u["y"], u["w"], u["h"])
    prev = []
    with open(u["file"], "rb") as f:
        data = f.read()
    for i in range(0, len(data), 3):
        prev.append((data[i], data[i + 1], data[i + 2]))
    bmp_write_rect(u["bmp"], u["x"], u["y"], u["w"], u["h"], prev)
    state.map_var("MAP_EDIT")["redo"].append({"file": u["file"], "bmp": u["bmp"], "x": u["x"], "y": u["y"],
                             "w": u["w"], "h": u["h"], "current": cur, "count": u["count"]})
    return {"ok": True, "restored": u["count"], "undo_depth": len(state.map_var("MAP_EDIT")["undo"])}

def map_edit_redo():
    if not state.map_var("MAP_EDIT")["redo"]:
        return {"ok": False, "msg": "没有可重做的地图编辑"}
    r = state.map_var("MAP_EDIT")["redo"].pop()
    # 用当前值回写，再压回 undo
    bmp_write_rect(r["bmp"], r["x"], r["y"], r["w"], r["h"], r["current"])
    state.map_var("MAP_EDIT")["undo"].append({"file": r["file"], "bmp": r["bmp"], "x": r["x"], "y": r["y"],
                             "w": r["w"], "h": r["h"], "count": r["count"]})
    return {"ok": True, "undo_depth": len(state.map_var("MAP_EDIT")["undo"])}

def map_merge_preview(src, dst, root=None):
    """预览合并：返回源省像素数、受影响的州/战略区，不写盘"""
    src, dst = int(src), int(dst)
    if src == dst:
        return {"ok": False, "msg": "源省和目标省相同"}
    root = _map_pick(root)
    _ensure_prov_rgb(root)
    if src not in state.map_var("PROV_RGB"):
        return {"ok": False, "msg": "省 %d 在 definition.csv 里没有定义" % src}
    if dst not in state.map_var("PROV_RGB"):
        return {"ok": False, "msg": "省 %d 在 definition.csv 里没有定义" % dst}
    layers = mod_layers(root)
    bmp, _prov = _layers_find("map/provinces.bmp", layers)
    if not bmp:
        return {"ok": False, "msg": "找不到 provinces.bmp"}
    info = bmp_info(bmp)
    if not info:
        return {"ok": False, "msg": "只支持 24 位 BMP"}
    src_rgb = state.map_var("PROV_RGB")[src]
    # 预览只需计数：优先读图层缓存里的 prov_index.json（构建时已算好每省像素数），零遍历成本
    _n = 0
    try:
        _d, _key, _b = _map_dir(root)
        _idx = os.path.join(_d or "", "prov_index.json")
        if os.path.exists(_idx):
            with io.open(_idx, encoding="utf-8") as _f:
                _j = json.loads(_f.read())
            _n = int((_j.get(str(src)) or {}).get("px") or 0)
    except Exception:
        _n = 0
    if not _n:
        try:
            from PIL import Image
            Image.MAX_IMAGE_PIXELS = None
            with Image.open(bmp) as _im:
                _cols = _im.convert("RGB").getcolors(maxcolors=200000) or []
            _n = next((c for c, col in _cols if tuple(col) == tuple(src_rgb)), 0)
        except Exception:
            allpx = bmp_read_rect(bmp, 0, 0, info["w"], info["h"])
            _n = sum(1 for px in allpx if px == src_rgb)
    hit = [0] * _n
    states_hit = []
    for sid, st in state.states().items():
        if src in (st.get("provinces") or []):
            states_hit.append(sid)
    prov2region, _rl = _strategic_regions(root)
    region_hit = [prov2region.get(src)] if prov2region.get(src) else []
    # 合并后源省的州会不会变空
    empty_after = []
    for sid in states_hit:
        st = state.states().get(sid) or {}
        rest = [p for p in (st.get("provinces") or []) if p != src]
        if not rest:
            empty_after.append(sid)
    return {"ok": True, "src": src, "dst": dst, "pixels": len(hit),
            "src_rgb": list(src_rgb), "dst_rgb": list(state.map_var("PROV_RGB")[dst]),
            "states": states_hit, "states_empty_after": empty_after,
            "regions": region_hit, "bmp": bmp, "w": info["w"], "h": info["h"]}

def _ensure_layer_file_writable(fpath, rel_path, src_base, root, adopt=False):
    """检查州/战略区等文本文件可写性，来自下层或只读层时按需单文件接管。"""
    rel_n = (rel_path or "").replace("\\", "/").lstrip("/")
    layers = mod_layers(root) if root else []
    top = _writable_map_top(root, layers)
    ab_top = os.path.abspath(top) if top else ""
    if ab_top and rel_n:
        top_cand = os.path.join(ab_top, rel_n.replace("/", os.sep))
        if os.path.isfile(top_cand):
            return top_cand, None
    if fpath and not is_readonly_mod(fpath) and ab_top:
        ab_fp = os.path.abspath(fpath)
        if ab_fp.startswith(ab_top + os.sep):
            return fpath, None
    ab_src = os.path.abspath(src_base or "") if src_base else ""
    if not is_readonly_mod(src_base or fpath) and (not ab_top or (ab_src and ab_src == ab_top)):
        return fpath, None
    if not top:
        return None, {
            "ok": False, "readonly": True,
            "msg": "%s 来自只读目录（%s），不能直接改；请先新建或加载可写 submod"
                   % (rel_n or os.path.basename(fpath or ""), os.path.basename(ab_src) or "原版"),
        }
    if not adopt:
        return None, {
            "ok": False, "need_adopt": True,
            "rel": rel_n or os.path.basename(fpath or ""),
            "from": os.path.basename(ab_src) or "父层",
            "to": os.path.basename(ab_top) or "当前 mod",
            "msg": "%s 来自%s（只读或下层），需先单文件复制到 %s 再编辑"
                   % (rel_n or os.path.basename(fpath or ""), os.path.basename(ab_src) or "父层",
                      os.path.basename(ab_top) or "当前 mod"),
        }
    if not rel_n:
        return None, {"ok": False, "msg": "无法确定相对路径，不能接管文件"}
    sub_dir = os.path.dirname(rel_n).replace("\\", "/").strip("/")
    basename = os.path.basename(rel_n)
    dst, msg = ensure_writable_file(root, sub_dir, basename)
    if not dst:
        return None, {"ok": False, "msg": msg}
    return dst, {"adopted": True, "adopt_msg": msg}


def _sr_remove_province(sr_text, pid):
    """在战略区原文里精确移除省号 pid（按 _strip_keep_len 偏移，保留注释与格式）。"""
    clean = _strip_keep_len(sr_text)
    spans = []
    for m in re.finditer(r'\bstrategic_region\s*=\s*\{', clean):
        b = clean.find("{", m.end() - 1)
        e = brace_match(clean, b)
        if e <= b:
            continue
        body_clean = clean[b + 1:e - 1]
        pm = re.search(r'\bprovinces\s*=\s*\{', body_clean)
        if not pm:
            continue
        pb_rel = body_clean.find("{", pm.end() - 1)
        pe_rel = brace_match(body_clean, pb_rel)
        if pe_rel <= pb_rel:
            continue
        pb_abs = b + 1 + pb_rel
        pe_abs = b + 1 + pe_rel
        inner_clean = clean[pb_abs + 1:pe_abs - 1]
        for mt in re.finditer(r'(?<!\d)%d(?!\d)' % pid, inner_clean):
            s = pb_abs + 1 + mt.start()
            t = pb_abs + 1 + mt.end()
            if t < pe_abs - 1 and clean[t] in (' ', '\t'):
                t += 1
            elif s > pb_abs + 1 and clean[s - 1] in (' ', '\t'):
                s -= 1
            spans.append((s, t))
    if not spans:
        return sr_text, False
    out = sr_text
    prev_s = len(out) + 1
    for s, t in sorted(spans, reverse=True):
        t = min(t, prev_s)
        if s < t:
            out = out[:s] + out[t:]
        prev_s = s
    return out, True


def map_merge_apply(src, dst, root=None, adopt=False):
    """合并：把 src 的所有像素涂成 dst 的颜色，并同步更新州与战略区（跨州合并只移出 src 不造一省多州）"""
    pv = map_merge_preview(src, dst, root)
    if not pv.get("ok"):
        return pv
    src, dst = pv["src"], pv["dst"]
    root = _map_pick(root)

    # 先校验跨州合并：仅当 dst 尚无任何所属州时才移入 src 原州；否则只从 src 原州移除 src
    dst_states = []
    for _sid, _st in state.states().items():
        if dst in (_st.get("provinces") or []):
            dst_states.append(_sid)
    add_dst_to_src_state = (len(dst_states) == 0)

    state_targets = []
    for sid in pv["states"]:
        st = state.states().get(sid) or {}
        old_provs = list(st.get("provinces") or [])
        new_provs = [p for p in old_provs if p != src]
        if add_dst_to_src_state and dst not in new_provs:
            new_provs.append(dst)
        if not new_provs:
            return {"ok": False,
                    "msg": "跨州合并会令州 %s 的省份为空（目标省 %d 已属其他州），拒绝操作以防空州报错" % (sid, dst)}
        st_root = st.get("root") or ""
        st_file = st.get("file") or ""
        fpath = st.get("path") or os.path.join(st_root, st_file)
        if not fpath or not os.path.exists(_out_read_path(fpath)):
            continue
        rel_hint = st_file.replace("\\", "/").lstrip("/")
        if not rel_hint and st_root and fpath:
            try:
                rel_hint = os.path.relpath(fpath, st_root).replace("\\", "/").lstrip("/")
            except Exception:
                rel_hint = ""
        state_targets.append((sid, st, fpath, rel_hint, st_root))

    # 扫描包含 src 的战略区文件
    sr_targets = []
    for sr_base, sr_dir, sr_fn in effective_layer_files("map/strategicregions", root):
        sr_path = os.path.join(sr_dir, sr_fn)
        try:
            with io.open(_out_read_path(sr_path), encoding="utf-8-sig", errors="replace") as _f:
                sr_raw = _f.read()
        except Exception:
            continue
        _sr_test, changed_sr = _sr_remove_province(sr_raw, src)
        if changed_sr:
            sr_rel = "map/strategicregions/" + sr_fn
            sr_targets.append((sr_base, sr_path, sr_rel))

    # 写盘前先对所有目标（provinces.bmp / 州 / 战略区）做可写与接管预检，避免写半截
    bmp, _bbase, berr = _ensure_map_writable("provinces.bmp", root=root, adopt=False)
    if not bmp and not adopt:
        return berr
    if not bmp and berr and not berr.get("need_adopt"):
        return berr

    for _sid, _st, fpath, rel_hint, st_root in state_targets:
        _tf, _terr = _ensure_layer_file_writable(fpath, rel_hint, st_root, root, adopt=False)
        if not _tf and not adopt:
            return _terr
        if not _tf and _terr and not _terr.get("need_adopt"):
            return _terr

    for sr_base, sr_path, sr_rel in sr_targets:
        _sf, _serr = _ensure_layer_file_writable(sr_path, sr_rel, sr_base, root, adopt=False)
        if not _sf and not adopt:
            return _serr
        if not _sf and _serr and not _serr.get("need_adopt"):
            return _serr

    adopt_msgs = []
    if adopt:
        bmp, _bbase, berr = _ensure_map_writable("provinces.bmp", root=root, adopt=True)
        if not bmp:
            return berr
        if berr and berr.get("adopted"):
            adopt_msgs.append(berr.get("adopt_msg") or "已单文件接管 map/provinces.bmp")

    resolved_states = []
    for sid, st, fpath, rel_hint, st_root in state_targets:
        target_st, st_err = _ensure_layer_file_writable(fpath, rel_hint, st_root, root, adopt=adopt)
        if not target_st:
            return st_err
        if st_err and st_err.get("adopted"):
            adopt_msgs.append(st_err.get("adopt_msg") or ("已单文件接管 %s" % (rel_hint or os.path.basename(fpath))))
        resolved_states.append((sid, st, target_st, rel_hint))

    resolved_srs = []
    for sr_base, sr_path, sr_rel in sr_targets:
        target_sr, sr_err = _ensure_layer_file_writable(sr_path, sr_rel, sr_base, root, adopt=adopt)
        if not target_sr:
            return sr_err
        if sr_err and sr_err.get("adopted"):
            adopt_msgs.append(sr_err.get("adopt_msg") or ("已单文件接管 %s" % sr_rel))
        resolved_srs.append((target_sr, sr_rel))

    src_rgb = tuple(pv["src_rgb"])
    dst_rgb = tuple(pv["dst_rgb"])
    w, h = pv["w"], pv["h"]
    allpx = bmp_read_rect(bmp, 0, 0, w, h)
    if allpx is None:
        return {"ok": False, "msg": "读取 provinces.bmp 失败（仅支持 24 位 BMP）"}
    changed = 0
    newpx = list(allpx)
    for i, px in enumerate(allpx):
        if px == src_rgb:
            newpx[i] = dst_rgb
            changed += 1
    if not changed:
        return {"ok": False, "msg": "省 %d 在地图上没有像素" % src}
    # 备份整幅原像素（合并影响面可能很大，用整幅更稳，33MB 一次性）
    os.makedirs(state.map_var("MAP_UNDO_DIR"), exist_ok=True)
    seq = int(time.time() * 1000)
    fn = os.path.join(state.map_var("MAP_UNDO_DIR"), "merge%d.bin" % seq)
    with open(fn, "wb") as f:
        for (r, g, b) in allpx:
            f.write(bytes((r, g, b)))
    if not bmp_write_rect(bmp, 0, 0, w, h, newpx):
        return {"ok": False, "msg": "provinces.bmp 写入失败（仅支持 24 位无压缩 BMP）"}

    # 州：按规则更新磁盘与内存
    top_writable = _writable_map_top(root, mod_layers(root))
    touched_states = []
    for sid, st, target_st, rel_hint in resolved_states:
        try:
            _text, _bom = _read_bom_text(target_st)
            _loc = _state_locate(_text)
            if not _loc:
                continue
            _b, _e = _loc
            _body = _text[_b + 1:_e - 1]
            _old = _parse_state_provinces(_body)
            _new = [p for p in _old if p != src]
            if add_dst_to_src_state and dst not in _new:
                _new.append(dst)
            _new_text = _text[:_b + 1] + _set_state_provinces(_body, _new) + _text[_e - 1:]
            snapshot(target_st)
            _write_bom_text(target_st, _new_text, _bom)
            rel_show = rel_hint or os.path.relpath(target_st, top_writable or root or os.path.dirname(target_st))
            state.changed()[_out_path(target_st)] = rel_show
            touched_states.append(rel_show)
            if top_writable and os.path.abspath(target_st).startswith(os.path.abspath(top_writable) + os.sep):
                st["root"] = top_writable
                if "path" in st:
                    st["path"] = target_st
        except Exception as _e2:
            print("合并时写州失败:", target_st, _e2)
    # 内存里的 state.states() 也更新
    for sid in pv["states"]:
        st = state.states().get(sid)
        if not st:
            continue
        lst = [p for p in (st.get("provinces") or []) if p != src]
        if add_dst_to_src_state and dst not in lst:
            lst.append(dst)
        st["provinces"] = sorted(lst)

    # 战略区：从对应战略区移除 src（无 BOM、原文精准替换）
    touched_regions = []
    for target_sr, sr_rel in resolved_srs:
        try:
            with io.open(_out_read_path(target_sr), encoding="utf-8-sig", errors="replace") as _f:
                sr_raw = _f.read()
            new_sr_text, sr_changed = _sr_remove_province(sr_raw, src)
            if sr_changed:
                snapshot(target_sr)
                out_sr = _out_path(target_sr)
                _atomic_write(out_sr, new_sr_text.encode("utf-8"))
                state.changed()[out_sr] = sr_rel
                touched_regions.append(sr_rel)
        except Exception as _e3:
            print("合并时写战略区失败:", target_sr, _e3)
    if touched_regions:
        try:
            state.map_var("_REGION_CACHE").clear()
        except Exception:
            pass

    state.map_var("MAP_EDIT")["undo"].append({"file": fn, "bmp": bmp, "x": 0, "y": 0, "w": w, "h": h,
                             "count": changed, "kind": "merge", "src": src, "dst": dst,
                             "states": touched_states, "regions": touched_regions})
    state.map_var("MAP_EDIT")["redo"] = []
    out = {"ok": True, "src": src, "dst": dst, "pixels": changed,
           "states": touched_states, "regions": touched_regions,
           "undo_depth": len(state.map_var("MAP_EDIT")["undo"]),
           "note": "definition.csv 未改动（省 %d 仍保留定义，可后续手工清理或用「删除省」）" % src}
    if adopt_msgs:
        out["adopted"] = True
        out["adopt_msg"] = "；".join(dict.fromkeys(adopt_msgs))
    return out

def map_prov_neighbors(pid, root=None):
    """返回某省的相邻省（按共享边像素数排序）。整幅扫描约 5 秒，按 bmp mtime 缓存结果。"""
    root = _map_pick(root)
    try:
        _layers0 = mod_layers(root)
        _b0, _p0 = _layers_find("map/provinces.bmp", _layers0)
        _sig = (os.path.abspath(_b0 or ""), int(os.path.getmtime(_b0)) if _b0 and os.path.exists(_b0) else 0, int(pid))
        if _sig in state.map_var("_NB_CACHE"):
            return dict(state.map_var("_NB_CACHE")[_sig])
    except Exception:
        _sig = None
    _ensure_prov_rgb(root)
    layers = mod_layers(root)
    bmp, _prov = _layers_find("map/provinces.bmp", layers)
    if not bmp:
        return {"ok": False, "msg": "找不到 provinces.bmp"}
    info = bmp_info(bmp)
    w, h = info["w"], info["h"]
    if pid not in state.map_var("PROV_RGB"):
        return {"ok": False, "msg": "省 %d 没有颜色定义" % pid}
    rgb = state.map_var("PROV_RGB")[pid]
    allpx = bmp_read_rect(bmp, 0, 0, w, h)
    idx = {v: k for k, v in state.map_var("PROV_RGB").items()}
    nb = {}
    for i, px in enumerate(allpx):
        if px != rgb:
            continue
        x, y = i % w, i // w
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if 0 <= nx < w and 0 <= ny < h:
                other = allpx[ny * w + nx]
                if other != rgb:
                    npid = idx.get(other)
                    if npid:
                        nb[npid] = nb.get(npid, 0) + 1
    out = sorted(nb.items(), key=lambda kv: -kv[1])[:12]
    res = {"ok": True, "pid": pid, "neighbors": [{"pid": p, "share": c} for p, c in out]}
    try:
        if _sig:
            state.map_var("_NB_CACHE")[_sig] = dict(res)
    except Exception:
        pass
    return res

def map_edit_state():

    return {"ok": True, "undo": len(state.map_var("MAP_EDIT")["undo"]), "redo": len(state.map_var("MAP_EDIT")["redo"]),
            "pending": len(state.map_var("MAP_EDIT").get("pending") or []), "file": state.map_var("MAP_EDIT").get("file") or ""}

def map_integrity(root=None, limit=200):
    """地图完整性检查：连通性、州/战略区连续、无效 ID、十字交叉、铁路断连、无主/超大省"""
    root = _map_pick(root)
    if not root:
        return {"ok": False, "msg": "还没有加载 mod"}
    dirp, _, base = _map_dir(root)
    if not dirp or not os.path.exists(os.path.join(dirp, "prov_id.png")):
        return {"ok": False, "msg": "请先构建图层（缺少 prov_id.png）"}
    t0 = time.time()
    ids, w, h, raw = _map_ids_from_cache(dirp)
    if not ids:
        return {"ok": False, "msg": "读取图层缓存失败"}
    n = w * h
    items = []

    def add(level, title, detail, provs=None):
        items.append({"level": level, "kind": "map", "title": title,
                      "detail": detail or "", "provinces": provs or []})

    # 省集合与像素数
    px = {}
    for i in range(n):
        pid = ids[i]
        if pid:
            px[pid] = px.get(pid, 0) + 1
    known = set(px)

    # 4-邻接 + 十字交叉
    adj = {}
    cross = 0
    for y in range(h):
        row = y * w
        for x in range(w):
            i = row + x
            a = ids[i]
            if x + 1 < w:
                b = ids[i + 1]
                if a != b:
                    if a and b:
                        adj.setdefault(a, set()).add(b)
                        adj.setdefault(b, set()).add(a)
            if y + 1 < h:
                b = ids[i + w]
                if a != b:
                    if a and b:
                        adj.setdefault(a, set()).add(b)
                        adj.setdefault(b, set()).add(a)
                # 2x2 十字：左上==右下 且 右上==左下 且 两两不同
                if x + 1 < w:
                    c = ids[i + 1]
                    d = ids[i + w]
                    e = ids[i + w + 1]
                    if a == e and c == d and a != c and a and c:
                        cross += 1

    # 省份像素连通（BFS）
    seen = bytearray(n)
    comp = {}
    for i in range(n):
        if seen[i]:
            continue
        pid = ids[i]
        if not pid:
            seen[i] = 1
            continue
        stack = [i]
        seen[i] = 1
        cnt = 0
        while stack:
            cur = stack.pop()
            cnt += 1
            cy, cx = divmod(cur, w)
            for nb in (cur - 1 if cx > 0 else -1,
                       cur + 1 if cx + 1 < w else -1,
                       cur - w if cy > 0 else -1,
                       cur + w if cy + 1 < h else -1):
                if nb < 0 or seen[nb]:
                    continue
                if ids[nb] == pid:
                    seen[nb] = 1
                    stack.append(nb)
        comp[pid] = comp.get(pid, 0) + 1

    bad_comp = [(pid, c) for pid, c in comp.items() if c > 1]

    # 州 / 战略区归属
    prov2state = {}
    prov2state_one = {}
    for sid, st in state.states().items():
        try:
            sid_int = int(st.get("id") or sid)
        except Exception:
            continue
        for p in (st.get("provinces") or []):
            try:
                pid_i = int(p)
            except Exception:
                continue
            prov2state.setdefault(pid_i, []).append(sid_int)
            if pid_i not in prov2state_one:
                prov2state_one[pid_i] = sid_int
    prov2region, region_list = _strategic_regions(root)

    # 一省多州 / 无效 ID
    multi = [(pid, sids) for pid, sids in prov2state.items() if len(sids) > 1]
    dead_state = [pid for pid in prov2state if pid not in known]
    dead_region = [pid for pid in prov2region if pid not in known]

    def group_split(mapping, label):
        """按州/地区分组，用省邻接图判断每组是否连通"""
        groups = {}
        for pid, v in mapping.items():
            groups.setdefault(v, set()).add(pid)
        bad = []
        for gid, members in groups.items():
            members = set(m for m in members if m in known)
            if len(members) < 2:
                continue
            start = next(iter(members))
            stack = [start]
            visited = {start}
            while stack:
                cur = stack.pop()
                for nb in adj.get(cur, ()):
                    if nb in members and nb not in visited:
                        visited.add(nb)
                        stack.append(nb)
            if len(visited) != len(members):
                bad.append((gid, len(members), len(visited)))
        return bad

    split_state = group_split(prov2state_one, "州")
    split_region = group_split(prov2region, "战略区")

    # 铁路
    rail_bad = 0
    rail_check = 0
    rp, _ = _layers_find("map/railways.txt", mod_layers(root))
    if rp:
        try:
            with io.open(_out_read_path(rp), encoding="utf-8-sig", errors="replace") as _f:
                text = strip_comments(_f.read())
            chains = []
            for m in re.finditer(r'(?m)^\s*railway\s*=\s*\{', text):
                b = text.find("{", m.end() - 1)
                e = brace_match(text, b)
                if e <= b:
                    continue
                body = text[b + 1:e - 1]
                pm = re.search(r'provinces\s*=\s*\{([^}]*)\}', body)
                if pm:
                    provs = [int(x) for x in re.findall(r'\d+', pm.group(1))]
                    if provs:
                        chains.append(provs)
            for ln in text.splitlines():
                s = ln.strip()
                if not s or s.startswith("#"):
                    continue
                parts = s.split()
                if len(parts) < 3 or not parts[0].isdigit() or not parts[1].isdigit():
                    continue
                try:
                    n_cnt = int(parts[1])
                except Exception:
                    continue
                provs = []
                for tok in parts[2:2 + n_cnt]:
                    try:
                        provs.append(int(tok))
                    except Exception:
                        break
                if len(provs) == n_cnt and provs:
                    chains.append(provs)
            for chain in chains:
                for a, b2 in zip(chain, chain[1:]):
                    rail_check += 1
                    if b2 not in adj.get(a, set()):
                        rail_bad += 1
        except Exception:
            pass

    # 无主省 / 超大省
    no_state = [pid for pid in known if pid not in prov2state and px.get(pid, 0) > 0]
    big = sorted(((pid, c) for pid, c in px.items() if c > 2000), key=lambda x: -x[1])[:30]

    # 地图定义一致性（读缓存里的 meta）
    try:
        _mp = os.path.join(dirp, "meta.json")
        if os.path.exists(_mp):
            with io.open(_mp, encoding="utf-8") as _f:
                _m = json.loads(_f.read())
            _c = _m.get("consistency") or {}
            if _c.get("ghost"):
                add("warn", "definition.csv 里有 %d 个省在地图上没有像素" % _c["ghost"],
                    "例如省 " + ", ".join(str(x) for x in (_c.get("ghost_sample") or [])[:12]) +
                    "；可能是删省后没清 definition.csv", (_c.get("ghost_sample") or [])[:20])
            if _c.get("unset_pixels"):
                add("warn", "%.2f%% 的像素颜色在 definition.csv 里找不到（%d 像素）" %
                    (_c.get("unset_ratio", 0), _c["unset_pixels"]),
                    "这些像素会被当成无主地；通常是 bmp 与 csv 不同步，或父子 mod 的 csv/bmp 混用", [])
            if _c.get("dup_rgb"):
                add("error", "%d 组省在 definition.csv 里用了同一个 RGB" % _c["dup_rgb"],
                    "同色会让后定义的省永远不出现；例如 " + json.dumps(
                        (_c.get("dup_rgb_sample") or [])[:3], ensure_ascii=False)[:160], [])
    except Exception as _e:
        print("一致性检查读取失败:", _e)

    # 汇总条目
    if bad_comp:
        items.append({"level": "warn", "kind": "map",
                      "title": "%d 个省份由多块不相连的区域组成（岛屿/飞地或碎片）" % len(bad_comp),
                      "detail": "例如省 " + ", ".join("%d（%d 块）" % (p, c) for p, c in bad_comp[:8]),
                      "provinces": [p for p, c in bad_comp[:20]]})
    if multi:
        add("error", "%d 个省份同时属于多个州" % len(multi),
            "例如省 %s" % ", ".join("%d→州%s" % (p, s) for p, s in multi[:5]),
            [p for p, s in multi[:20]])
    if split_state:
        add("warn", "%d 个州在图上不连续（多为岛屿/飞地，需逐个人工确认）" % len(split_state),
            "例如州 " + ", ".join("%d（%d 省，最大连通 %d）" % g for g in split_state[:6]),
            [])
    if split_region:
        add("warn", "%d 个战略区不连续（多为跨海区域）" % len(split_region),
            "例如地区 " + ", ".join("%d（%d 省，最大连通 %d）" % g for g in split_region[:6]),
            [])
    if dead_state:
        add("error", "州里引用了 %d 个不存在的省" % len(dead_state),
            "例如 " + ", ".join(str(x) for x in dead_state[:10]), dead_state[:20])
    if dead_region:
        add("error", "战略区里引用了 %d 个不存在的省" % len(dead_region),
            "例如 " + ", ".join(str(x) for x in dead_region[:10]), dead_region[:20])
    if cross:
        add("warn", "%d 处十字交叉像素（2×2 对角线歧义）" % cross,
            "会在地图上产生斜角接缝，可用「检查」后手动修或跑修复", [])
    if rail_check and rail_bad:
        add("warn", "铁路有 %d 段两端省份不相邻（共检查 %d 段）" % (rail_bad, rail_check),
            "可能是拆分/删除省份后遗留", [])
    if no_state:
        add("info", "%d 块陆地省份不属于任何州" % len(no_state),
            "例如 " + ", ".join(str(x) for x in no_state[:10]), no_state[:20])
    if big:
        add("info", "%d 个省份面积超过 2000 像素（细化候选）" % len(big),
            "最大：" + ", ".join("%d（%d px）" % (p, c) for p, c in big[:6]), [p for p, c in big[:10]])

    counts = {"error": 0, "warn": 0, "info": 0}
    for it in items:
        counts[it["level"]] = counts.get(it["level"], 0) + 1
    return {"ok": True, "items": items[:limit], "stats": counts,
            "sizes": {"w": w, "h": h, "provinces": len(known)},
            "ms": int((time.time() - t0) * 1000), "source": base}
