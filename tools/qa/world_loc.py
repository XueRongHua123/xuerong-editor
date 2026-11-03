# -*- coding: utf-8 -*-
"""本地化（yml）写入器：把中文塞进 `localisation/`。

为什么单独一个模块
------------------
生成的 mod 里所有键都是裸的：`STATE_1`、`zz_editor_tree_1`、`ZZV`。游戏不会猜中文，
没写进 yml 就原样显示裸键。A2 的验收里「国策名、事件文本、国名、州名都是中文」全靠这里。

三条格式硬要求（踩过）
----------------------
1. yml 必须 **UTF-8 带 BOM**，否则整份文件不被读取（而 `.txt` 反过来不能带 BOM）
2. 顶层语言键是 `l_simp_chinese:`，冒号后不能有空格
3. 每行格式 ` KEY:0 "文本"`：冒号后是版本号（写 0），文本里的双引号要换掉
"""
import io
import os
import re

_LINE = re.compile(r'^\s*([A-Za-z0-9_.\-]+):\d*\s+"(.*)"\s*$')


def write(mod_dir, entries, filename="zz_editor_world_l_simp_chinese.yml",
          lang="simp_chinese"):
    """把 entries（[(key, 文本), ...]）合并进 yml 并落盘。

    合并而不是覆盖：同一个文件里可能已经有手工改过的行，保留它们。
    返回写入的键数。
    """
    if not entries:
        return 0
    d = os.path.join(mod_dir, "localisation", lang)
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, filename)

    cur = {}
    if os.path.exists(p):
        try:
            for ln in io.open(p, encoding="utf-8-sig", errors="replace"):
                m = _LINE.match(ln)
                if m:
                    cur[m.group(1)] = m.group(2)
        except Exception:
            cur = {}
    n = 0
    for k, v in entries:
        if not k:
            continue
        v = str(v).replace('"', "'").replace("\n", " ")
        if cur.get(k) == v:
            continue
        cur[k] = v
        n += 1
    if not n:
        return 0

    lines = ["l_%s:" % lang]
    for k in sorted(cur):
        lines.append(' %s:0 "%s"' % (k, cur[k]))
    io.open(p, "w", encoding="utf-8-sig", newline="").write("\n".join(lines) + "\n")
    return n


def country_entries(tag, name, desc=None, adjective=None):
    """国名 / 国名形容词 / 国家描述。

    HOI4 认的键：`<TAG>`（国名）、`<TAG>_ADJ`（形容词）、`<TAG>_DESC`（开局描述）。
    只写 `<TAG>` 也能显示，但外交界面上「德国宣战」那句里会露英文键。
    """
    tag = (tag or "").strip().upper()
    out = [(tag, name or tag)]
    if adjective:
        out.append((tag + "_ADJ", adjective))
    out.append((tag + "_DESC", desc or (name or tag)))
    return out


def state_entries(state_ids, prefix="第", suffix="州"):
    """州名。键盘位是 `STATE_<id>`，与 history/states 里的 name 字段对应。"""
    out = []
    for i, sid in enumerate(state_ids or [], start=1):
        out.append(("STATE_%d" % int(sid), "%s%d%s" % (prefix, i, suffix)))
    return out
