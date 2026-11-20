# -*- coding: utf-8 -*-
"""地图的读侧底座：叠加链与路径、CSV、BMP 读写、元信息与缓存。

本模块不 import 本包任何兄弟模块（包内别处只往这里要，反向没有边）。
文件名叫 io 会撞标准库：模块内 `import io` 走绝对导入拿标准库，
本模块自己的函数由兄弟模块按 `xuerong.model.map.io` 全名 import，两者不会串。
"""
import hashlib
import io
import json
import os
import shutil
import struct

from xuerong import state
from xuerong.core.paths import (_dir_mtime, _layers_find, _mod_descriptor, _out_path,
                                _out_read_path, is_under_game, mod_layers)


def _map_files(root):
    """沿叠加链找地图（子 mod → 父 mod → 原版），返回 (bmp, csv, 提供者)"""
    if root:
        b, d, provider, _layers = _map_files_layered(root)
        if b and d:
            return b, d, (provider or root)
    if state.game():
        b = os.path.join(state.game(), "map", "provinces.bmp")
        d = os.path.join(state.game(), "map", "definition.csv")
        if os.path.exists(b) and os.path.exists(d):
            return b, d, state.game()
    return None, None, None

def _map_key(root):
    """缓存键必须覆盖所有会影响图层的输入：
    省位图、definition.csv、州 history、战略区定义。
    少一项就会出现"改了数据但地图没变"的错觉。"""
    b, d, base = _map_files(root)
    if not b:
        return None, None
    layers = mod_layers(root)
    layer_sig = "|".join("%s:%d:%d" % (os.path.abspath(x), _dir_mtime(os.path.join(x, "history", "states")),
                                       _dir_mtime(os.path.join(x, "map", "strategicregions")))
                         for x in layers)
    key = "%s|%d|%d|%d|%s" % (
        os.path.abspath(base), os.path.getmtime(b), os.path.getsize(b), os.path.getmtime(d), layer_sig)
    return key, base

def _map_dir(root):
    key, base = _map_key(root)
    if not key:
        return None, None, None
    return os.path.join(state.map_var("MAP_CACHE_DIR"), hashlib.md5(key.encode("utf-8")).hexdigest()[:12]), key, base

def _csv_path_for(root):
    layers = mod_layers(root)
    csvp, prov = _layers_find("map/definition.csv", layers)
    return csvp, prov

def _refine_load_ids(root):
    """载入 省号数组（按 provinces.bmp + definition.csv 的 mtime 缓存）"""
    from PIL import Image, ImageDraw
    Image.MAX_IMAGE_PIXELS = None
    layers = mod_layers(root)
    bmp, _ = _layers_find("map/provinces.bmp", layers)
    csvp, _ = _layers_find("map/definition.csv", layers)
    if not bmp or not csvp:
        return None, 0, 0
    key = (bmp, os.path.getmtime(bmp), csvp, os.path.getmtime(csvp))
    hit = state.map_var("_REFINE_IDS_CACHE").get("cur")
    if hit and hit[0] == key:
        return hit[1], hit[2], hit[3]
    with Image.open(bmp) as im:
        w, h = im.size
        raw = im.convert("RGB").tobytes()
    rgb2pid = {}
    with io.open(csvp, encoding="utf-8", errors="replace") as f:
        for line in f:
            p = line.strip().split(";")
            if len(p) >= 8 and p[0].isdigit():
                rgb2pid[(int(p[1]), int(p[2]), int(p[3]))] = int(p[0])
    ids = [0] * (w * h)
    for i in range(w * h):
        ids[i] = rgb2pid.get((raw[i * 3], raw[i * 3 + 1], raw[i * 3 + 2]), 0)
    state.map_var("_REFINE_IDS_CACHE")["cur"] = (key, ids, w, h)
    return ids, w, h

def map_sources():
    """列出所有可用于地图的来源：已加载的 mod（有无 map 都列出）+ 原版"""
    out = []
    seen = set()
    for r in state.roots():
        p = os.path.abspath(r)
        if p in seen:
            continue
        seen.add(p)
        # 用叠加链判断：submod 自己没有 bmp，但父 mod 有
        try:
            _b, _d, _prov, _layers = _map_files_layered(p)
        except Exception:
            _b = _d = _prov = None
        has = bool(_b and _d)
        prov_name = ""
        if _prov and os.path.abspath(_prov) != os.path.abspath(p):
            prov_name = os.path.basename(_prov.replace(chr(92), "/").rstrip("/"))
        out.append({"path": p, "name": os.path.basename(p.replace(chr(92), "/").rstrip("/")) or p,
                    "has_map": has, "map_from": prov_name,
                    "readonly": is_under_game(p), "is_game": False})
    if state.game():
        g = os.path.abspath(state.game())
        out.append({"path": g, "name": "原版（游戏本体）",
                    "has_map": os.path.exists(os.path.join(g, "map", "provinces.bmp")),
                    "readonly": True, "is_game": True})
    return out

def _map_pick(root=None):
    """指定 root 就用它；否则第一个在叠加链里能找到地图的 mod；最后原版。
    注意：submod 自己可能没有 provinces.bmp（由父 mod 提供），所以判断要走整条链。"""
    if root:
        return root
    for r in state.roots():
        try:
            b, d, _provider, _layers = _map_files_layered(r)
        except Exception:
            b = d = None
        if b and d:
            return r
    return state.game()

def _map_files_layered(root):
    """在叠加链里找 provinces.bmp / definition.csv，返回 (bmp, csv, 提供地图的 root, layers)"""
    layers = mod_layers(root)
    b, rb = _layers_find("map/provinces.bmp", layers)
    d, rd = _layers_find("map/definition.csv", layers)
    if b and d:
        return b, d, (rb or rd), layers
    return None, None, None, layers

def bmp_info(path):
    """读 BMP 头，返回 (width, height, bpp, data_offset, row_size, top_down)"""
    with open(path, "rb") as f:
        head = f.read(54)
        if len(head) < 54 or head[:2] != b"BM":
            return None
        data_off = struct.unpack("<I", head[10:14])[0]
        w = struct.unpack("<i", head[18:22])[0]
        h = struct.unpack("<i", head[22:26])[0]
        bpp = struct.unpack("<H", head[28:30])[0]
        top_down = h < 0
        h = abs(h)
        row_size = ((w * bpp // 8) + 3) // 4 * 4
        return {"w": w, "h": h, "bpp": bpp, "offset": data_off,
                "row": row_size, "top_down": top_down, "bytes_pp": bpp // 8}

def bmp_read_rect(path, x0, y0, w, h):
    path = _out_read_path(path)          # 输出模式下读改过的副本
    """读矩形区域的原始像素（RGB 三元组列表，行优先）。
    走 Pillow 的 C 实现；逐行手工解析在 1100 万像素时要 7 秒以上。"""
    info = bmp_info(path)
    if not info or info["bpp"] != 24:
        return None
    try:
        from PIL import Image
        Image.MAX_IMAGE_PIXELS = None
        with Image.open(path) as im:
            box = im.convert("RGB").crop((x0, y0, x0 + w, y0 + h))
            raw = box.tobytes()
        return [(raw[i], raw[i + 1], raw[i + 2]) for i in range(0, len(raw), 3)]
    except Exception:
        pass
    out = []
    with open(path, "rb") as f:
        for y in range(y0, y0 + h):
            row_idx = y if info["top_down"] else (info["h"] - 1 - y)
            f.seek(info["offset"] + row_idx * info["row"] + x0 * 3)
            data = f.read(w * 3)
            for i in range(0, len(data), 3):
                out.append((data[i + 2], data[i + 1], data[i]))
    return out

def bmp_write_rect(path, x0, y0, w, h, pixels):
    """把 RGB 像素列表原位写回 bmp（不重存文件，保持原有结构）。
    输出模式下：先把源 bmp 复制到 output/ 再改副本，源文件不动。"""
    if state.output_mode():
        _dst = _out_path(path)
        if os.path.abspath(_dst) != os.path.abspath(path):
            if not os.path.exists(_dst):
                os.makedirs(os.path.dirname(_dst) or ".", exist_ok=True)
                shutil.copyfile(path, _dst)
            path = _dst
    info = bmp_info(path)
    if not info or info["bpp"] != 24:
        return False
    buf = bytearray()
    if pixels and isinstance(pixels[0], (list, tuple)) and len(pixels[0]) == 3:
        for (r, g, b) in pixels:
            buf += bytes((b, g, r))
    else:
        buf = bytearray(pixels)
    with open(path, "r+b") as f:
        stride = w * 3
        for row in range(h):
            row_idx = (y0 + row) if info["top_down"] else (info["h"] - 1 - (y0 + row))
            f.seek(info["offset"] + row_idx * info["row"] + x0 * 3)
            f.write(bytes(buf[row * stride:(row + 1) * stride]))
    return True

def _ensure_prov_rgb(root=None):
    """按需从 definition.csv 加载省颜色，**按 mod 缓存**。

    原来用全局单例：第一个 mod 加载完就再也不更新，换 mod 后它的省号全部「不存在」。
    实测后果：跑回归时先测 CN 再测京都，京都的 17214/17217 被判为不存在，州细化失败。"""
    _root = _map_pick(root or None)
    key = os.path.abspath(_root or "")
    if key in state.map_var("_PROV_RGB_CACHE"):
        state.map_var("PROV_RGB").clear()
        state.map_var("PROV_RGB").update(state.map_var("_PROV_RGB_CACHE")[key])
        return state.map_var("PROV_RGB")
    state.map_var("PROV_RGB").clear()
    try:
        _layers = mod_layers(_root)
        csvp, _prov = _layers_find("map/definition.csv", _layers)
        if not csvp or not os.path.exists(csvp):
            return state.map_var("PROV_RGB")
        with io.open(csvp, encoding="utf-8", errors="replace") as f:
            for line in f:
                parts = line.strip().split(";")
                if len(parts) < 4:
                    continue
                try:
                    state.map_var("PROV_RGB")[int(parts[0])] = (int(parts[1]), int(parts[2]), int(parts[3]))
                except Exception:
                    continue
    except Exception as e:
        print("加载 definition.csv 颜色失败:", e)
    state.map_var("_PROV_RGB_CACHE")[key] = dict(state.map_var("PROV_RGB"))
    return state.map_var("PROV_RGB")

def _map_files_strict(root):


    """严格模式：沿叠加链找地图（子 mod 没有地图时用父 mod 的），整条链都没有才返回 None。
    返回的地图 bmp 可能来自父 mod，但 base 仍报请求的 root，便于界面区分"数据来自哪里"。"""
    if not root:
        return None, None, None
    b, d, provider, layers = _map_files_layered(root)
    if not b or not d:
        return None, None, None
    return b, d, provider

def map_meta(root=None):
    root = _map_pick(root)
    b, d, base = _map_files_strict(root)
    if not b:
        return {"ok": False, "msg": "这个来源没有 map/provinces.bmp 或 definition.csv",
                "sources": map_sources(), "picked": root}
    dirp, key, base = _map_dir(root)
    built = bool(dirp and os.path.exists(os.path.join(dirp, "meta.json")))
    meta = {}
    if built:
        try:
            meta = json.loads(io.open(os.path.join(dirp, "meta.json"), encoding="utf-8").read())
        except Exception:
            meta = {}
    # 缓存过期：同一来源以前构建过，但缓存键变了（数据或版本改动）
    stale = False
    prev = {}
    lastp = os.path.join(state.map_var("MAP_CACHE_DIR"), "_last.json")
    if os.path.exists(lastp):
        try:
            prev = json.loads(io.open(lastp, encoding="utf-8").read())
        except Exception:
            prev = {}
    if not built and prev.get("root") and os.path.abspath(prev.get("root")) == os.path.abspath(base or ""):
        stale = prev.get("key") != key
    layers = mod_layers(root)
    return {"ok": True, "built": built, "stale": stale, "dir": dirp, "source": base, "stamp": key,
            "prev_built": prev.get("built"), "meta": meta, "picked": root,
            "layers": [{"path": x,
                        "name": os.path.basename(x.replace("\\", "/").rstrip("/")) or x,
                        "is_game": os.path.abspath(x) == os.path.abspath(state.game() or ""),
                        "descriptor_file": os.path.join(x, "descriptor.mod"),
                        "has_descriptor": os.path.exists(os.path.join(x, "descriptor.mod")),
                        "mod_name": _mod_descriptor(x)["name"],
                        "deps": _mod_descriptor(x)["deps"],
                        "replace_count": len(_mod_descriptor(x)["replace"])}
                       for x in layers],
            "sources": map_sources()}

def map_cache_clear():
    """清空所有地图图层缓存（源文件不动，下次打开自动重建）"""
    total = 0
    n = 0
    if os.path.isdir(state.map_var("MAP_CACHE_DIR")):
        for name in sorted(os.listdir(state.map_var("MAP_CACHE_DIR"))):
            p = os.path.join(state.map_var("MAP_CACHE_DIR"), name)
            if not os.path.isdir(p):
                continue
            size = 0
            for dp, _, fs in os.walk(p):
                for f in fs:
                    try:
                        size += os.path.getsize(os.path.join(dp, f))
                    except Exception:
                        pass
            shutil.rmtree(p, ignore_errors=True)
            total += size
            n += 1
    return {"ok": True, "dirs": n, "bytes": total,
            "msg": "已清理 %d 个来源的缓存，释放 %.1f MB" % (n, total / 1e6)}

def _map_ids_from_cache(dirp):


    """从缓存的 prov_id.png 还原 ids 数组（省 id 按 RGB 编码）"""
    from array import array
    from PIL import Image
    p = os.path.join(dirp, "prov_id.png")
    if not os.path.exists(p):
        return None, 0, 0, None
    im = Image.open(p).convert("RGB")
    w, h = im.size
    raw = im.tobytes()
    n = w * h
    ids = array("I", bytes(4 * n))
    a = ids
    for i in range(n):
        o = i * 3
        a[i] = (raw[o] << 16) | (raw[o + 1] << 8) | raw[o + 2]
    return ids, w, h, raw

def _prov_state_map():
    """省 → 州 的映射。

    同一省被多个州声明时（原版和 mod 都有这个省，mod 的州覆盖原版的州），
    按 state.roots() 的加载顺序取优先级最高的那一层 —— 后面的 mod 覆盖前面的。
    只有在同一层内部冲突时才记为真实数据问题。"""
    layers = {}
    for i, r in enumerate(state.roots() or []):
        layers[os.path.abspath(r)] = i
    best = {}      # pid -> (priority, sid)
    dups = {}
    for _s in (state.states().values() if isinstance(state.states(), dict) else []):
        try:
            sid = int(_s.get("id") or 0)
        except Exception:
            continue
        pri = layers.get(os.path.abspath(_s.get("root") or ""), 0)
        for _p in (_s.get("provinces") or []):
            try:
                pid = int(_p)
            except Exception:
                continue
            cur = best.get(pid)
            if cur is None or pri > cur[0]:
                best[pid] = (pri, sid)
            elif pri == cur[0] and cur[1] != sid:
                # 同一层里两个州都声明了这个省 —— 这才是真冲突
                dups.setdefault(pid, [cur[1]]).append(sid)
    return {k: v[1] for k, v in best.items()}, dups

def bmp_write_rect_8(path, x0, y0, w, h, values):
    """8 位索引图（terrain.bmp 这类）的矩形写入，每像素 1 字节。

    bmp_write_rect 只处理 24 位；索引图必须单独写，否则会把 P 模式 bmp 改成 RGB，
    HOI4 就读不出来了。"""
    info = bmp_info(path)
    if not info or info.get("bpp") != 8:
        return False
    bpp_bytes = info.get("bytes_pp") or 1
    if bpp_bytes != 1:
        return False
    row_bytes = info["row"]
    W, H = info["w"], info["h"]
    if x0 < 0 or y0 < 0 or x0 + w > W or y0 + h > H:
        return False
    with open(path, "r+b") as f:
        for r in range(h):
            y = y0 + r
            fy = y if info.get("top_down") else (H - 1 - y)
            off = info["offset"] + fy * row_bytes + x0
            f.seek(off)
            f.write(bytes(values[r * w:(r + 1) * w]))
    return True

def _prov_type_map(root):
    """省号 → definition.csv 第 5 列（land / sea / lake 等）。

    政治图层要区分「海洋」和「无主陆地」：前者给海色，后者给中性灰，
    否则大片海洋会被画成深色，看起来像地图缺了一块。"""
    cache = getattr(_prov_type_map, "_cache", None)
    layers = mod_layers(root or None)
    csvp, _ = _layers_find("map/definition.csv", layers)
    if not csvp:
        return {}
    key = (os.path.abspath(csvp), int(os.path.getmtime(csvp)))
    if cache and cache[0] == key:
        return cache[1]
    out = {}
    try:
        with io.open(csvp, encoding="utf-8", errors="replace") as f:
            for line in f:
                p = line.strip().split(";")
                if len(p) >= 5 and p[0].isdigit():
                    out[int(p[0])] = (p[4] or "").strip().lower()
    except Exception:
        pass
    _prov_type_map._cache = (key, out)
    return out

def map_asset(name, root=None):


    """返回缓存目录里的资产路径（白名单，防路径穿越）"""
    if name not in state.map_var("MAP_ASSETS"):
        return None
    root = _map_pick(root)
    dirp, _, _ = _map_dir(root) if root else (None, None, None)
    if not dirp:
        return None
    p = os.path.join(dirp, name)
    return p if os.path.exists(p) else None
