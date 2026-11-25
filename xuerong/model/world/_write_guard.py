# -*- coding: utf-8 -*-
"""world 域共用的写入层守卫：算链顶可写层，并拒绝写入父 mod 的 replace_path 独占目录。"""
import os

from xuerong.core.paths import _top_mod, write_base


def world_write_base(root, sub_dir, detail="直接写进去会改坏它。"):
    """计算 sub_dir 的写入层，拒绝写进父 mod。

    先按传入的 root 解析叠加链，再回退 state.roots() 查找可写顶层；
    若 sub_dir 被非链顶层的 replace_path 独占，返回明确错误提示。
    返回 (路径, 错误消息)。
    """
    top = _top_mod(root)
    if not top:
        return None, "找不到可写的 mod 目录"
    tgt, _why = write_base(root, sub_dir)
    if not tgt:
        return None, "找不到可写目录"
    if os.path.abspath(tgt) != os.path.abspath(top):
        nm = os.path.basename(tgt.rstrip("\\/")) or tgt
        return None, ("%s 被 %s 的 replace_path 独占，%s"
                      "请先在「诊断 → 目录写入目标」里接管该目录" % (sub_dir, nm, detail))
    return tgt, ""
