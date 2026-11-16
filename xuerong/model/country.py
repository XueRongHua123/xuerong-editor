# -*- coding: utf-8 -*-
"""国家域 —— 目前只有 history/countries 的定位与写入层（P0-3 B3）。

country 域主体（国家列表、外交、历史读写）留到后面那一批，这里先把两个
写盘辅助搬过来，idea/tech 的写操作都经它们。

依赖边界：全部在 core/paths，零钩子。
"""
import os
import re

from xuerong.core import paths
from xuerong.core.paths import _layer_files, _top_mod, mod_layers, write_base


def _country_hist_file(root, tag):
    """按 tag 找 history/countries 里的文件，返回 (路径, rel) 或 (None, "")。"""
    root = paths._pick(root)
    files, _rep = _layer_files("history/countries", mod_layers(root))
    tag = (tag or "").upper()
    for p in (files or []):
        fn = os.path.basename(p)
        # 文件名形如 "AFR - Africa.txt"
        m = re.match(r'([A-Z0-9_]{2,8})\s*-', fn.upper())
        if m and m.group(1) == tag:
            return p, os.path.join("history", "countries", fn)
    return None, ""



def _country_hist_write_base(root):
    """history/countries 的写入层，拒写父 mod。"""
    top = _top_mod(root)
    if not top:
        return None, "找不到可写的 mod 目录"
    tgt, why = write_base(root, "history/countries")
    if not tgt:
        return None, "找不到可写目录"
    if os.path.abspath(tgt) != os.path.abspath(top):
        nm = os.path.basename(tgt.rstrip("\\/")) or tgt
        return None, ("history/countries 被 %s 的 replace_path 独占，"
                      "直接写进去会改坏它。请先在「诊断 → 目录写入目标」里接管该目录" % nm)
    return tgt, ""


def _politics_write(root, tag):
    """拿到可写的国家历史文件路径。"""
    src, rel = _country_hist_file(root, tag)
    if not src:
        return None, None, "找不到 %s 的国家历史文件" % tag
    tgt, err = _country_hist_write_base(root)
    if not tgt:
        return None, None, err
    dst = os.path.join(tgt, rel)
    os.makedirs(os.path.dirname(dst) or tgt, exist_ok=True)
    if not os.path.exists(dst):
        try:
            import shutil as _sh
            _sh.copyfile(src, dst)
        except Exception as e:
            return None, None, "复制来源失败：%s" % e
    return dst, rel, ""
