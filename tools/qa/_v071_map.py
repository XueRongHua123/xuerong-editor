# v0.71 地图图层构建（Pillow，无需 numpy）
MAP_CACHE_DIR = os.path.join(WORK, "cache", "map")
MAP_ASSETS = ("base.png", "province.png", "edges.png", "state.png", "prov_id.png",
              "prov_index.json", "centers.json", "meta.json")


def _map_files(root):
    for base in (root, GAME):
        if not base:
            continue
        b = os.path.join(base, "map", "provinces.bmp")
        d = os.path.join(base, "map", "definition.csv")
        if os.path.exists(b) and os.path.exists(d):
            return b, d, base
    return None, None, None


def _map_key(root):
    b, d, base = _map_files(root)
    if not b:
        return None, None
    key = "%s|%d|%d|%d" % (os.path.abspath(base), os.path.getmtime(b), os.path.getsize(b),
                           os.path.getmtime(d))
    return key, base


def _map_dir(root):
    key, base = _map_key(root)
    if not key:
        return None, None, None
    return os.path.join(MAP_CACHE_DIR, hashlib.md5(key.encode("utf-8")).hexdigest()[:12]), key, base


def map_meta():
    root = ROOTS[0] if ROOTS else GAME
    b, d, base = _map_files(root)
    if not b:
        return {"ok": False, "msg": "找不到 map/provinces.bmp 或 definition.csv"}
    dirp, key, base = _map_dir(root)
    built = bool(dirp and os.path.exists(os.path.join(dirp, "meta.json")))
    meta = {}
    if built:
        try:
            meta = json.loads(io.open(os.path.join(dirp, "meta.json"), encoding="utf-8").read())
        except Exception:
            meta = {}
    return {"ok": True, "built": built, "dir": dirp, "source": base,
            "stamp": key, "meta": meta}


def _hsv_hex(i, sat=0.52, val=0.88):
    h = (i * 0.618033988749895) % 1.0
    r, g, b = colorsys.hsv_to_rgb(h, sat, val)
    return bytes((int(r * 255), int(g * 255), int(b * 255)))


def map_build(force=False):
    """生成地图图层（首次约 5-8 秒），返回 meta。"""
    root = ROOTS[0] if ROOTS else GAME
    if not root:
        return {"ok": False, "msg": "还没有加载任何 mod"}
    bmp, csv, base = _map_files(root)
    if not bmp:
        return {"ok": False, "msg": "找不到 map/provinces.bmp 或 definition.csv"}
    dirp, key, base = _map_dir(root)
    if not dirp:
        return {"ok": False, "msg": "无法创建缓存目录"}
    os.makedirs(dirp, exist_ok=True)
    meta_path = os.path.join(dirp, "meta.json")
    if not force and os.path.exists(meta_path):
        try:
            return {"ok": True, "cached": True,
                    "meta": json.loads(io.open(meta_path, encoding="utf-8").read())}
        except Exception:
            pass

    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    t_all = time.time()

    # 1) definition.csv：颜色 -> 省 id
    color2prov = {}
    prov2type = {}
    with io.open(csv, encoding="utf-8", errors="replace") as f:
        for line in f:
            parts = line.strip().split(";")
            if len(parts) < 5:
                continue
            try:
                pid = int(parts[0])
                rgb = (int(parts[1]), int(parts[2]), int(parts[3]))
            except Exception:
                continue
            color2prov[rgb] = pid
            prov2type[pid] = parts[4] or "land"

    # 2) 读图
    im = Image.open(bmp).convert("RGB")
    w, h = im.size
    raw = im.tobytes()

    # 3) 省 -> 州
    prov2state = {}
    for sid, st in STATES.items():
        try:
            sid_int = int(st.get("id") or sid)
        except Exception:
            continue
        for p in (st.get("provinces") or []):
            try:
                prov2state[int(p)] = sid_int
            except Exception:
                pass

    # 4) 一遍像素：ids、质心累加
    n = w * h
    ids = [0] * n
    sumx = {}
    sumy = {}
    cnts = {}
    lookup = color2prov
    for i in range(n):
        o = i * 3
        pid = lookup.get((raw[o], raw[o + 1], raw[o + 2]))
        if pid is None:
            pid = 0
        ids[i] = pid
        if pid:
            sumx[pid] = sumx.get(pid, 0) + (i % w)
            sumy[pid] = sumy.get(pid, 0) + (i // w)
            cnts[pid] = cnts.get(pid, 0) + 1

    # 5) 图层缓冲
    provbuf = bytearray(n * 3)
    statebuf = bytearray(n * 3)
    edgebuf = bytearray(n * 3)
    idbuf = bytearray(n * 3)
    prov_color = {}
    state_color = {}
    for i in range(n):
        pid = ids[i]
        c = prov_color.get(pid)
        if c is None:
            c = _hsv_hex(pid, 0.5, 0.9) if pid else bytes((24, 28, 26))
            prov_color[pid] = c
        sid = prov2state.get(pid, 0)
        sc = state_color.get(sid)
        if sc is None:
            sc = _hsv_hex(sid + 7, 0.42, 0.8) if sid else bytes((30, 34, 32))
            state_color[sid] = sc
        o = i * 3
        provbuf[o:o + 3] = c
        statebuf[o:o + 3] = sc
        idbuf[o] = (pid >> 16) & 0xFF
        idbuf[o + 1] = (pid >> 8) & 0xFF
        idbuf[o + 2] = pid & 0xFF

    # 6) 省界（4 邻域不同即标白）
    for y in range(h):
        row = y * w
        for x in range(w):
            i = row + x
            pid = ids[i]
            edge = False
            if x + 1 < w and ids[i + 1] != pid:
                edge = True
            elif y + 1 < h and ids[i + w] != pid:
                edge = True
            elif x > 0 and ids[i - 1] != pid:
                edge = True
            elif y > 0 and ids[i - w] != pid:
                edge = True
            if edge:
                o = i * 3
                edgebuf[o] = 250
                edgebuf[o + 1] = 250
                edgebuf[o + 2] = 250

    # 7) 写资产
    Image.frombytes("RGB", (w, h), bytes(provbuf)).save(os.path.join(dirp, "province.png"))
    Image.frombytes("RGB", (w, h), bytes(statebuf)).save(os.path.join(dirp, "state.png"))
    Image.frombytes("RGB", (w, h), bytes(edgebuf)).save(os.path.join(dirp, "edges.png"))
    Image.frombytes("RGB", (w, h), bytes(idbuf)).save(os.path.join(dirp, "prov_id.png"))
    im.resize((max(1, w // 2), max(1, h // 2)), Image.BILINEAR).save(os.path.join(dirp, "base.png"))

    centers = {}
    counts = cnts
    for pid, cnt in counts.items():
        centers[str(pid)] = [round(sumx[pid] / cnt, 1), round(sumy[pid] / cnt, 1)]

    index = {}
    for pid, cnt in counts.items():
        index[str(pid)] = {"state": prov2state.get(pid, 0), "type": prov2type.get(pid, ""), "px": cnt}

    io.open(os.path.join(dirp, "centers.json"), "w", encoding="utf-8", newline="").write(
        json.dumps(centers, ensure_ascii=False))
    io.open(os.path.join(dirp, "prov_index.json"), "w", encoding="utf-8", newline="").write(
        json.dumps(index, ensure_ascii=False))

    meta = {"w": w, "h": h, "provinces": len(counts), "source": base,
            "ms": int((time.time() - t_all) * 1000), "built": time.strftime("%Y-%m-%d %H:%M:%S"),
            "assets": {a: os.path.getsize(os.path.join(dirp, a)) for a in MAP_ASSETS
                       if os.path.exists(os.path.join(dirp, a))}}
    io.open(meta_path, "w", encoding="utf-8", newline="").write(json.dumps(meta, ensure_ascii=False))
    return {"ok": True, "cached": False, "meta": meta}


def map_asset(name):
    """返回缓存目录里的资产路径（白名单，防路径穿越）"""
    if name not in MAP_ASSETS:
        return None
    root = ROOTS[0] if ROOTS else GAME
    dirp, _, _ = _map_dir(root) if root else (None, None, None)
    if not dirp:
        return None
    p = os.path.join(dirp, name)
    return p if os.path.exists(p) else None

