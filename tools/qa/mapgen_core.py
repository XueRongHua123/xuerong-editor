# -*- coding: utf-8 -*-
"""地图生成器：从多种来源生成 HOI4 完整 map/ 目录。

支持四种来源：
  lineart     黑白线稿 PNG（线条 = 省界）
  mask        海陆掩码 PNG（黑海白陆），自动 Voronoi 切省
  procedural  程序化（分形噪声大陆 + Voronoi 切省）
  image       任意图片，按颜色区块切省

输出：provinces.bmp / definition.csv / heightmap.bmp / world_normal.bmp /
      terrain.bmp / rivers.bmp / cities.bmp / trees.bmp /
      continent.txt / default.map / terrain/ / strategicregions / supplyareas 等
"""
import io
import os
import json
import random
import numpy as np
from PIL import Image


# ============ 连通分量（numpy 两遍扫描 + 并查集） ============

def label_regions(mask):
    """mask: bool 数组（True = 属于某个区域）。

    返回 labels: int32，0 = 背景，1..N = 区域编号（按首次出现顺序）。
    用两遍扫描 + 并查集，numpy 做行内向量化。
    """
    h, w = mask.shape
    labels = np.zeros((h, w), dtype=np.int32)
    parent = [0]

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            if ra < rb:
                parent[rb] = ra
            else:
                parent[ra] = rb

    nxt = 1
    for y in range(h):
        row = mask[y]
        if not row.any():
            continue
        prev_lab = labels[y - 1] if y > 0 else np.zeros(w, dtype=np.int32)
        cur = labels[y]
        prev_mask = mask[y - 1] if y > 0 else np.zeros(w, dtype=bool)
        for x in range(w):
            if not row[x]:
                continue
            up = prev_lab[x] if prev_mask[x] else 0
            left = cur[x - 1] if x > 0 else 0
            if up and left:
                cur[x] = min(up, left)
                union(up, left)
            elif up or left:
                cur[x] = up or left
            else:
                cur[x] = nxt
                parent.append(nxt)
                nxt += 1

    # 归一化
    if nxt > 1:
        lut = np.zeros(nxt, dtype=np.int32)
        for i in range(1, nxt):
            lut[i] = find(i)
        # 重新按出现顺序编号
        uniq = sorted(set(lut[lut > 0].tolist()))
        remap = {old: i + 1 for i, old in enumerate(uniq)}
        for i in range(1, nxt):
            lut[i] = remap.get(lut[i], 0)
        labels = lut[labels]
    return labels


def region_sizes(labels):
    """每块区域的像素数，返回 {id: size}。"""
    ids, counts = np.unique(labels, return_counts=True)
    return {int(i): int(c) for i, c in zip(ids, counts) if i > 0}


def filter_small(labels, min_size):
    """把小于 min_size 的区域并回 0（背景）。"""
    sizes = region_sizes(labels)
    small = {k for k, v in sizes.items() if v < min_size}
    if not small:
        return labels
    out = labels.copy()
    for k in small:
        out[labels == k] = 0
    return out


# ============ 颜色分配 ============

def unique_colors(n, seed=42):
    """生成 n 个互不相同的省颜色（避开 HOI4 保留色）。

    HOI4 的 definition.csv 要求每省 RGB 唯一；海/湖用固定色。
    """
    rng = random.Random(seed)
    used = set()
    out = []
    # 避开纯黑（0,0,0 常被当无效）和纯白（255,255,255 常当边界）
    for i in range(n):
        while True:
            r = rng.randint(1, 254)
            g = rng.randint(1, 254)
            b = rng.randint(1, 254)
            key = (r, g, b)
            if key in used:
                continue
            if r == g == b:      # 灰度容易和边界混淆
                continue
            used.add(key)
            out.append(key)
            break
    return out


# ============ 从各类源构建省图 ============

def from_lineart(path, min_size=400):
    """从黑白线稿生成。

    线条（暗像素）= 边界，空白（亮像素）= 省内部。
    返回 (labels, land_mask)。
    """
    im = Image.open(path).convert("L")
    a = np.array(im)
    # 线条：暗于中位数一半
    thr = max(64, int(a.mean() * 0.6))
    blank = a > thr
    labels = label_regions(blank)
    labels = filter_small(labels, min_size)
    land = labels > 0
    return labels, land


def from_mask(path, n_target=None, min_size=400, seed=7):
    """从海陆掩码生成：陆地上撒种子点做 Voronoi。

    黑 = 海，其余 = 陆。
    """
    im = Image.open(path).convert("L")
    a = np.array(im)
    land = a > 40
    h, w = land.shape
    # 若是全陆地，按面积估算种子数
    if n_target is None:
        n_target = max(1, int(land.sum() / 8000))
    rng = random.Random(seed)
    ys, xs = np.nonzero(land)
    if len(ys) == 0:
        return np.zeros((h, w), dtype=np.int32), np.zeros((h, w), dtype=bool)
    pick = rng.sample(range(len(ys)), min(n_target, len(ys)))
    sy = ys[pick]
    sx = xs[pick]
    # 逐像素找最近种子（只在陆地上算）
    labels = np.zeros((h, w), dtype=np.int32)
    # 分块计算，控制内存
    block = 64
    seeds = np.stack([sy, sx], axis=1).astype(np.float32)
    for y0 in range(0, h, block):
        y1 = min(h, y0 + block)
        yy, xx = np.mgrid[y0:y1, 0:w]
        pts = np.stack([yy.ravel(), xx.ravel()], axis=1).astype(np.float32)
        # 距离平方
        d = ((pts[:, None, :] - seeds[None, :, :]) ** 2).sum(axis=2)
        lab = d.argmin(axis=1).astype(np.int32) + 1
        lab = lab.reshape(yy.shape)
        sub_land = land[y0:y1]
        lab = np.where(sub_land, lab, 0)
        labels[y0:y1] = lab
    labels = filter_small(labels, min_size)
    return labels, labels > 0


def procedural(w=1200, h=440, n_target=180, seed=11, sea_level=0.42):
    """程序化生成：分形噪声造大陆，再 Voronoi 切省。"""
    rng = np.random.default_rng(seed)

    def fractal(w, h, octaves=5):
        acc = np.zeros((h, w), dtype=np.float32)
        amp = 1.0
        total = 0.0
        for o in range(octaves):
            g = rng.random((max(2, h >> (octaves - o)), max(2, w >> (octaves - o))))
            gi = Image.fromarray((g * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC)
            acc += np.array(gi, dtype=np.float32) / 255.0 * amp
            total += amp
            amp *= 0.5
        return acc / total

    noise = fractal(w, h)
    # 边缘衰减，避免大陆被裁成方块
    yy, xx = np.mgrid[0:h, 0:w]
    cy, cx = h / 2, w / 2
    edge = np.minimum.reduce([
        xx / max(1, w * 0.12), (w - 1 - xx) / max(1, w * 0.12),
        yy / max(1, h * 0.12), (h - 1 - yy) / max(1, h * 0.12)])
    edge = np.clip(edge, 0, 1)
    val = noise * 0.7 + edge * 0.3
    land = val > sea_level

    # 撒种子切省
    ys, xs = np.nonzero(land)
    if len(ys) == 0:
        return np.zeros((h, w), dtype=np.int32), np.zeros((h, w), dtype=bool)
    pick = rng.choice(len(ys), size=min(n_target, len(ys)), replace=False)
    sy, sx = ys[pick], xs[pick]
    labels = np.zeros((h, w), dtype=np.int32)
    seeds = np.stack([sy, sx], axis=1).astype(np.float32)
    block = 64
    for y0 in range(0, h, block):
        y1 = min(h, y0 + block)
        yy2, xx2 = np.mgrid[y0:y1, 0:w]
        pts = np.stack([yy2.ravel(), xx2.ravel()], axis=1).astype(np.float32)
        d = ((pts[:, None, :] - seeds[None, :, :]) ** 2).sum(axis=2)
        lab = d.argmin(axis=1).astype(np.int32) + 1
        lab = lab.reshape(yy2.shape)
        labels[y0:y1] = np.where(land[y0:y1], lab, 0)
    labels = filter_small(labels, 300)
    return labels, labels > 0


def from_image(path, min_size=400, tol=12):
    """从任意图片按颜色区块切省：相同颜色（容差内）连成一块。"""
    im = Image.open(path).convert("RGB")
    a = np.array(im)
    # 量化，减少碎块
    q = (a // tol) * tol
    key = q[:, :, 0].astype(np.int32) * 65536 + q[:, :, 1].astype(np.int32) * 256 + q[:, :, 2].astype(np.int32)
    labels = np.zeros(key.shape, dtype=np.int32)
    nxt = 1
    # 逐色块标号（每个唯一颜色一个 label，再按连通性拆）
    uniq = np.unique(key)
    for col in uniq:
        m = key == col
        sub = label_regions(m)
        sub_max = int(sub.max())
        for i in range(1, sub_max + 1):
            sel = sub == i
            if sel.sum() < min_size:
                continue
            labels[sel] = nxt
            nxt += 1
    return labels, labels > 0
