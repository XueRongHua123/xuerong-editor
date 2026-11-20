# -*- coding: utf-8 -*-
"""本地化与编码规范：缺失键检查、BOM 规范检查。

从门面搬来的两个：

    missing_loc    国策 id 在 LOC 里查不到（或空串）
    _bom_issues    localisation/*.yml 该带 BOM、common/history/events 的 .txt 不该带

名字里的 loc 指 _bom_issues 扫的是 localisation 目录，不是本地化读写。
读写本地化（load_game_loc / load_mod 里的内联加载）仍留在门面 —— 两者扫描范围不同
（前者只扫 GAME/localisation/{english,simp_chinese}，后者扫整条 _chain_layers），
合并它们属于独立议题。

跨层依赖走 state 访问器，本模块不 import 门面。
"""
import os

from xuerong import state
from xuerong.core.paths import _layer_dirs, is_under_game

def missing_loc():
    out = []
    loc = state.loc()
    for tid in state.tree_order():
        t = state.trees().get(tid)
        if not t:
            continue
        for f in t["focuses"]:
            if f["id"] not in loc or not loc.get(f["id"], "").strip():
                out.append({"tree": tid, "id": f["id"], "key": f["id"], "file": t["file"]})
    return out


def _bom_issues(root, limit=40):
    """编码规范检查（HOI4 要求）：
    - localisation/*.yml 必须带 UTF-8 BOM（否则游戏读不到本地化）
    - common / history / events 下的 .txt 不应带 BOM
    返回 (问题列表 [(类型, 相对路径)], yml 总数, txt 总数, 真实问题总数)。
    第一个元素只是最多 limit 条示例，判断总数要看第四个值。

    走叠加链但**跳过原版层**：只扫 root 那一层时，加载纯 submod 会漏掉父 mod
    里那些同样会被游戏读取的 yml；而把 Paradox 原版一起算进来，报出来的是
    「游戏本身不遵守这套规范」—— 用户改不了，还会把真问题淹掉
    （本机实测：只查 mod 层 415 条 / 0.4s，含原版 1679 条 / 1.0s，其中 1264
    条来自原版自带文件）。这里只读每个文件头 3 字节，开销只跟文件个数有关。"""
    root = os.path.abspath(root)
    BOM3 = bytes((0xEF, 0xBB, 0xBF))
    issues = []
    yml_n = txt_n = 0
    bad_n = 0            # 真实问题总数，与 issues 长度分开
    # 只限制「示例条数」，不掐扫描：老代码是 issues 攒到 limit*3 就整个 break，
    # 那时扫的文件少（几十个）从没触发，数字恰好等于真实总数；改成扫叠加链后
    # 会提前截断并把 415 条低报成 128 条，所以总数单独计数。
    SAMPLE_CAP = limit * 3
    # 护栏：正常 mod 层远低于此（本机 189 yml + 3451 txt，全量扫完约 0.4s）。
    # 真撞上说明有人把游戏目录整个当 mod 加载了，抽样截断避免 lint 面板卡死。
    MAX_FILES = 10000
    scanned = 0
    stopped = False

    def _note(kind, rel):
        nonlocal bad_n
        bad_n += 1
        if len(issues) < SAMPLE_CAP:
            issues.append((kind, rel))

    def _rel(fp, base):
        """多来源时带上层名，否则不同层里的同名文件看起来是同一条。"""
        r = os.path.relpath(fp, base)
        if os.path.abspath(base) != root:
            r = (os.path.basename(base.rstrip("\\/")) or base) + "/" + r
        return r

    seen_dirs = set()

    def _walk_dirs(sub):
        for base, d in _layer_dirs(sub, root):
            if is_under_game(base):
                continue
            ab = os.path.abspath(d)
            if ab in seen_dirs:
                continue
            seen_dirs.add(ab)
            yield base, d

    for base, locd in _walk_dirs("localisation"):
        for dp, _dn, fs in os.walk(locd):
            for fn in fs:
                if not fn.lower().endswith(".yml"):
                    continue
                if scanned >= MAX_FILES:
                    stopped = True
                    break
                scanned += 1
                yml_n += 1
                fp = os.path.join(dp, fn)
                try:
                    with open(fp, "rb") as f:
                        head = f.read(3)
                except Exception:
                    continue
                if head != BOM3:
                    _note("缺 BOM", _rel(fp, base))
            if stopped:
                break
        if stopped:
            break
    for sub in ("common", "history", "events"):
        if stopped:
            break
        for base, d0 in _walk_dirs(sub):
            for dp, _dn, fs in os.walk(d0):
                for fn in fs:
                    if not fn.lower().endswith(".txt"):
                        continue
                    if scanned >= MAX_FILES:
                        stopped = True
                        break
                    scanned += 1
                    txt_n += 1
                    fp = os.path.join(dp, fn)
                    try:
                        with open(fp, "rb") as f:
                            head = f.read(3)
                    except Exception:
                        continue
                    if head == BOM3:
                        _note("多余 BOM", _rel(fp, base))
                if stopped:
                    break
            if stopped:
                break
    return issues[:limit], yml_n, txt_n, bad_n

