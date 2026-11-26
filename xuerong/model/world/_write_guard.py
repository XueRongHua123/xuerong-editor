# -*- coding: utf-8 -*-
"""world 域共用的写入层守卫：算链顶可写层，仅当更高层声明 replace_path 独占时阻断。"""
import os

from xuerong import state
from xuerong.core.paths import (_replace_owner, is_readonly_mod, is_under_game,
                                mod_layers)


def world_write_base(root, sub_dir, detail="直接写进去会改坏它。"):
    """计算 sub_dir 的写入层。

    有 root 时走 mod_layers(root)，无 root 时合并 state.roots() 的叠加链；
    从高到低挑选第一个可写层，仅当 sub_dir 被严格高于当前可写顶层的 replace_path
    独占时阻断，父层 replace_path 不阻断上层 submod。
    返回 (路径, 错误消息)。
    """
    chain_raw = []
    if root:
        chain_raw = [x for x in (mod_layers(root) or [root]) if x]
    else:
        seen = set()
        for r in (state.roots() or []):
            if not r:
                continue
            for x in (mod_layers(r) or [r]):
                if not x:
                    continue
                nx = os.path.normcase(os.path.abspath(x))
                if nx not in seen:
                    seen.add(nx)
                    chain_raw.append(x)
    if not chain_raw:
        return None, "找不到可写的 mod 目录"

    top = None
    for cand in reversed(chain_raw):
        if cand and not is_under_game(cand) and not is_readonly_mod(cand):
            top = cand
            break
    if not top:
        return None, "找不到可写的 mod 目录"

    owner = _replace_owner(root or top, sub_dir)
    if owner:
        chain = [os.path.normcase(os.path.abspath(x)) for x in chain_raw if x]
        ab_top = os.path.normcase(os.path.abspath(top))
        ab_own = os.path.normcase(os.path.abspath(owner))
        # 只有当独占层严格高于当前可写层时才阻断；父层的 replace_path 不影响上层 submod 新增或单文件覆写
        if ab_own != ab_top and ab_own in chain and ab_top in chain and chain.index(ab_own) > chain.index(ab_top):
            nm = os.path.basename(owner.rstrip("\\/")) or owner
            return None, ("%s 被 %s 的 replace_path 独占，%s"
                          "请先在「地图 → 图层 → 目录写入目标」里接管该目录" % (sub_dir, nm, detail))
    return top, ""
