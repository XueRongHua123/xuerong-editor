# -*- coding: utf-8 -*-
"""海省切分。

HOI4 的海不是「没上色的像素」，海必须是一个个 sea 省：
provinces.bmp 里每个像素都得落到 definition.csv 有定义的颜色上，
否则引擎会自动补一个 land 省，海就变成陆地（error.log 里报 prov N has no continent，
MAP_ERROR 直接拦住加载）。

所以生成器必须：
  1. 把 land==False 的区域切成若干连通块，每块一个 id；
  2. 每块 bbox 不超过地图宽/高的 1/8（超了报 Province X has TOO LARGE BOX）；
  3. 给每块分配唯一颜色，写进 definition.csv，类型 sea / terrain ocean / continent 0。

不依赖 scipy：连通域用「行游程 + 并查集」两遍扫描，11M 像素也扛得住。
"""
import numpy as np


def _runs(row):
    """一行布尔里的连续 True 游程，返回 (starts, ends)（end 为开区间）。"""
    d = np.diff(np.concatenate(([0], row.astype(np.int8), [0])))
    return np.flatnonzero(d == 1), np.flatnonzero(d == -1)


def label_components(mask):
    """4 连通域标记。返回 (labels int32, n)，id 从 1 开始。"""
    h, w = mask.shape
    parent = []

    def find(x):
        r = x
        while parent[r] != r:
            r = parent[r]
        while parent[x] != r:
            parent[x], x = r, parent[x]
        return r

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            if ra < rb:
                parent[rb] = ra
            else:
                parent[ra] = rb

    rows = []
    prev = []
    for y in range(h):
        row = mask[y]
        cur = []
        if row.any():
            starts, ends = _runs(row)
            j = 0
            for s, e in zip(starts.tolist(), ends.tolist()):
                lab = len(parent)
                parent.append(lab)
                while j < len(prev) and prev[j][1] <= s:
                    j += 1
                k = j
                while k < len(prev) and prev[k][0] < e:
                    union(lab, prev[k][2])
                    k += 1
                cur.append((s, e, lab))
        rows.append(cur)
        prev = cur

    out = np.zeros((h, w), np.int32)
    roots = {}
    for y, cur in enumerate(rows):
        for s, e, lab in cur:
            r = find(lab)
            rid = roots.get(r)
            if rid is None:
                rid = len(roots) + 1
                roots[r] = rid
            out[y, s:e] = rid
    return out, len(roots)


def absorb_tiny(ids, min_px=32, rounds=8):
    """把面积小于 min_px 的海省并进相邻的海省，然后连续重编号。

    为什么必须做
    ------------
    二分切块是「按块的 bbox 切」的，一个块里可能只有 1–2 个像素属于海
    （其余是陆地）。于是会切出一堆 **1 像素的海省**：实测 167 个海省里有 57 个
    ≤8 像素，其中 10 个只有 1 像素。这种退化省在地图初始化阶段要给引擎算
    邻接、给海军算寻路，是已知的崩因来源。

    做法：小省整体并入 4 邻域里出现最多的那个海省（绝不并入陆地，否则海变陆）。
    真被陆地包死的 1 像素小湖没有海邻居，保持原样——数量极少，不影响。

    最后**连续重编号**：并省之后 id 会出现空洞，而 definition.csv 是按
    1..max 逐个写的，空洞会变成「有定义但 0 像素」的省，比小省更糟。
    """
    ids = ids.copy()
    for _ in range(rounds):
        nid = int(ids.max())
        if nid <= 0:
            return ids, 0
        counts = np.bincount(ids.ravel(), minlength=nid + 1)
        small = [i for i in range(1, nid + 1) if 0 < counts[i] < min_px]
        if not small:
            break
        moved = 0
        for sid in small:
            m = ids == sid
            if not m.any():
                continue
            nb = []
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                v = np.roll(ids, (dy, dx), axis=(0, 1))[m]
                nb.append(v[v != sid])
            if not nb:
                continue
            v = np.concatenate(nb)
            v = v[v > 0]                      # 0 是陆地，不并
            if v.size == 0:
                continue
            ids[m] = int(np.bincount(v).argmax())
            moved += 1
        if not moved:
            break
    # 连续重编号
    uniq = np.unique(ids)
    uniq = uniq[uniq > 0]
    remap = np.zeros(int(ids.max()) + 1, dtype=np.int32)
    for new, old in enumerate(uniq, start=1):
        remap[old] = new
    return remap[ids], len(uniq)


def split_sea(land, max_span=None, min_px=32):
    """把 not-land 切成海省。

    land    (h, w) bool，True = 陆地
    max_span None 时取 宽/8 与 高/8，单省 bbox 超过就二分
    min_px  小于这个面积的海省会被并进邻居（见 absorb_tiny）

    返回 (ids int32, n)：ids 里海省 id 从 1 开始，陆地位置为 0。
    没有被切到的位置（不该出现）保持 0。
    """
    h, w = land.shape
    sea = ~land
    if not sea.any():
        return np.zeros((h, w), np.int32), 0
    if max_span is None:
        max_h, max_w = max(8, h // 8), max(8, w // 8)
    else:
        max_h = max_w = int(max_span)

    comp, n = label_components(sea)
    out = np.zeros((h, w), np.int32)
    nid = 0
    for cid in range(1, n + 1):
        m = comp == cid
        area = int(m.sum())
        ys = np.flatnonzero(m.any(axis=1))
        xs = np.flatnonzero(m.any(axis=0))
        y0, y1 = int(ys[0]), int(ys[-1]) + 1
        x0, x1 = int(xs[0]), int(xs[-1]) + 1
        stack = [(y0, y1, x0, x1)]
        while stack:
            ay0, ay1, ax0, ax1 = stack.pop()
            blk_mask = (comp[ay0:ay1, ax0:ax1] == cid)
            if not blk_mask.any():
                # 切出来的空矩形：分下去只会无限细分，直接丢
                continue
            if (ay1 - ay0) > max_h or (ax1 - ax0) > max_w:
                if (ay1 - ay0) >= (ax1 - ax0):
                    mid = (ay0 + ay1) // 2
                    stack.append((ay0, mid, ax0, ax1))
                    stack.append((mid, ay1, ax0, ax1))
                else:
                    mid = (ax0 + ax1) // 2
                    stack.append((ay0, ay1, ax0, mid))
                    stack.append((ay0, ay1, mid, ax1))
                continue
            nid += 1
            out[ay0:ay1, ax0:ax1][blk_mask] = nid
    return absorb_tiny(out, min_px=min_px)
