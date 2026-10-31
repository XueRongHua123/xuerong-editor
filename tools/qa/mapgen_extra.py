# -*- coding: utf-8 -*-
"""地图生成的进阶处理：质心、省大小均衡、空间聚类。"""
import random
import numpy as np


def centroids(labels):
    """每个省的像素质心，返回 {id: (x, y)}。"""
    out = {}
    n = int(labels.max())
    if n == 0:
        return out
    h, w = labels.shape
    ys, xs = np.nonzero(labels)
    ids = labels[ys, xs]
    order = np.argsort(ids, kind="stable")
    ids = ids[order]
    ys = ys[order]
    xs = xs[order]
    uniq, starts = np.unique(ids, return_index=True)
    ends = np.concatenate([starts[1:], [len(ids)]])
    for u, s, e in zip(uniq, starts, ends):
        out[int(u)] = (float(xs[s:e].mean()), float(ys[s:e].mean()))
    return out


def sizes(labels):
    ids, counts = np.unique(labels, return_counts=True)
    return {int(i): int(c) for i, c in zip(ids, counts) if i > 0}


def balance_sizes(labels, min_size=800, max_rounds=3):
    """把过小的省并到相邻的大省。

    用一次「邻接膨胀」：对每个过小的省，找它周围出现最多的邻居 id，
    把整块改判给那个邻居。重复几轮直到没有过小的省或达到上限。
    """
    cur = labels.copy()
    for _ in range(max_rounds):
        sz = sizes(cur)
        small = [k for k, v in sz.items() if v < min_size]
        if not small:
            break
        small.sort(key=lambda k: sz[k])
        changed = 0
        for k in small:
            m = cur == k
            if not m.any():
                continue
            # 上下左右邻居
            nbrs = []
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                shifted = np.roll(np.roll(cur, dy, 0), dx, 1)
                vals = shifted[m]
                nbrs.append(vals[vals > 0])
            if not nbrs:
                continue
            alln = np.concatenate(nbrs) if nbrs else np.array([], dtype=cur.dtype)
            if len(alln) == 0:
                cur[m] = 0
                changed += 1
                continue
            vals, cnts = np.unique(alln, return_counts=True)
            best = int(vals[np.argmax(cnts)])
            if best == k:
                continue
            cur[m] = best
            changed += 1
        if not changed:
            break
    # 归一化编号
    uniq = np.unique(cur)
    uniq = uniq[uniq > 0]
    lut = np.zeros(int(cur.max()) + 1, dtype=np.int32)
    for i, old in enumerate(uniq, start=1):
        lut[int(old)] = i
    return lut[cur]


def kmeans(points, k, seed=3, iters=25):
    """极简 k-means。points: [(x, y)]；返回 labels（0..k-1）。"""
    n = len(points)
    if n == 0:
        return []
    k = max(1, min(k, n))
    rng = random.Random(seed)
    idx = rng.sample(range(n), k)
    cents = [points[i] for i in idx]
    assign = [0] * n
    for _ in range(iters):
        moved = 0
        for i, (x, y) in enumerate(points):
            best = 0
            bd = None
            for j, (cx, cy) in enumerate(cents):
                d = (x - cx) ** 2 + (y - cy) ** 2
                if bd is None or d < bd:
                    bd = d
                    best = j
            if assign[i] != best:
                assign[i] = best
                moved += 1
        # 更新质心
        sums = [[0.0, 0.0, 0] for _ in range(len(cents))]
        for i, (x, y) in enumerate(points):
            s = sums[assign[i]]
            s[0] += x
            s[1] += y
            s[2] += 1
        for j, s in enumerate(sums):
            if s[2] > 0:
                cents[j] = (s[0] / s[2], s[1] / s[2])
        if not moved:
            break
    return assign


def group_provinces_by_location(labels, n_groups, seed=3):
    """按地理质心把省分成 n_groups 组（用于战略区/补给区）。

    返回 {group_index: [province_id, ...]}
    """
    cents = centroids(labels)
    ids = sorted(cents.keys())
    if not ids:
        return {}
    pts = [cents[i] for i in ids]
    k = max(1, min(n_groups, len(ids)))
    assign = kmeans(pts, k, seed)
    groups = {}
    for i, g in zip(ids, assign):
        groups.setdefault(g, []).append(i)
    return groups
