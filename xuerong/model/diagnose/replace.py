# -*- coding: utf-8 -*-
"""叠加链诊断：replace 风险、被 replace 目录的引用、stub 覆盖。"""

import io
import os
import re

from xuerong.core.paths import (_mod_descriptor, _replace_owner, _top_mod,
                               mod_layers)
from xuerong.model.diagnose._base import _finding
from xuerong.model.replace import (_REF_KEYWORDS, _replace_adopt_block,
                                   _replace_collect, _replace_ignore_key,
                                   _replace_ignored, _replace_ref_dir)


# replace_path 掉这些目录时，原版内容会整体消失，
# 但原版（以及其他 mod）的脚本仍然在引用它们
_REPLACE_RISK = (
    ("common/country_tags", "国家 tag", r'(?m)^\s*([A-Z][A-Z0-9]{2})\s*='),
    ("common/scripted_triggers", "脚本化 trigger", r'(?m)^\s*([a-z_][a-z0-9_]*)\s*=\s*\{'),
    ("common/scripted_effects", "脚本化 effect", r'(?m)^\s*([a-z_][a-z0-9_]*)\s*=\s*\{'),
    ("common/ideas", "国家精神", r'(?m)^\s*([a-z_][a-z0-9_]*)\s*=\s*\{'),
    ("common/technologies", "科技", r'(?m)^\s*([a-z_][a-z0-9_]*)\s*=\s*\{'),
)


def _diag_replace_risk(root, own_only=False):
    """replace_path 把原版目录整体屏蔽后，原版定义的 tag / trigger / effect
    仍然被原版脚本引用，会变成海量的 Unknown xxx-type 错误。

    这是实测最贵的一类：40 省测试地图 replace 了 common/country_tags，
    只剩自建的 1 个 tag，原版 383 个全部失效，
    error.log 从 0 涨到 58762 行，其中九成是 "Unknown trigger-type: GER"。
    """
    out = []
    layers = mod_layers(root) or [root] or []
    if not layers:
        return out
    game = layers[0]
    top = _top_mod(root)
    top_decl = set(_mod_descriptor(top).get("replace") or []) if (own_only and top) else None
    if own_only and not top_decl:
        return out
    for sub, label, pat in _REPLACE_RISK:
        if top_decl is not None and sub not in top_decl:
            continue
        owner = _replace_owner(root, sub)
        if not owner:
            continue
        if own_only and top and os.path.abspath(owner) != os.path.abspath(top):
            continue
        ours = _replace_collect(owner, sub, pat)
        if sub == "common/country_tags":
            # 别名目录不受这次 replace 影响，合并进来
            ours |= _replace_collect(owner, "common/country_tag_aliases", pat)
        theirs = _replace_collect(game, sub, pat)
        if sub == "common/country_tags":
            theirs |= _replace_collect(game, "common/country_tag_aliases", pat)
        missing = theirs - ours
        if not missing:
            continue
        # 分级：只提供极少数名字的，几乎肯定是「骨架 + 误 replace」，原版会大面积失效；
        # 提供几十上百个的，是 overhaul 型 mod 的有意整体替换，只作提示。
        sev = "error" if len(ours) < 10 else "info"
        sample = "、".join(sorted(missing)[:6])
        kind = "error" if sev == "error" else "info"
        if sev == "error":
            note = ("原版脚本仍在引用这些名字，加载期会刷出海量 Unknown xxx-type 错误"
                    if sub != "common/country_tags" else
                    "原版脚本里的 TAG = { } 一律报 Unknown trigger/effect-type")
        else:
            note = "整体替换是有意为之的话可忽略；若仍有原版脚本在用这些名字，会报 Unknown"
        out.append(_finding(
            "replace.drops_vanilla", sev,
            "%s 被 replace_path 整体替换：原版 %d 个%s，本 mod 提供 %d 个，"
            "缺 %d 个（%s…）。%s"
            % (sub, len(theirs), label, len(ours), len(missing), sample, note),
            "descriptor.mod", 0, 'replace_path="%s"' % sub,
            "去掉这条 replace_path，把自建内容写进 %s 下的新文件与原版合并；"
            "确实要整体替换时，需自行提供被引用到的全部名字" % sub))
    return out


def _diag_replace_refs(root, own_only=False):
    """replace 掉一个数据目录后，还有哪些文件在引用它。

    HOI4 的 replace_path 是整体屏蔽：声明后该目录只从这一层读。
    只替换 common/ideas 而不替换引用它的 achievements / continuous_focus /
    special_projects / factions，这些文件里的 add_timed_idea 就全指向不存在的
    精神，加载期刷出海量 Invalid idea（实测一轮 3879 条）。

    这个检查在动手之前把「会断哪些引用」列出来，省掉一轮 150 秒的真机验证。
    """
    out = []
    from xuerong import state
    from xuerong.core.paths import _mod_display_name, is_under_game
    layers = mod_layers(root) or [root] or []
    if not layers:
        return out
    top = _top_mod(root)
    if not top:
        return out

    replaced = set()
    top_decl = set(_mod_descriptor(top).get("replace") or []) if own_only else None
    if own_only and not top_decl:
        return out
    for sub, _label, _kw in _REF_KEYWORDS:
        if top_decl is not None and sub not in top_decl:
            continue
        owner = _replace_owner(root, sub)
        if owner and (not own_only or os.path.abspath(owner) == os.path.abspath(top)):
            replaced.add(sub)
    if not replaced:
        return out

    # 必须扫全部层：真正在引用被 replace 目录的往往是原版文件
    # （achievements.txt、continuous_focus、special_projects、factions）。
    # 只看本 mod 自己的文件会一条都报不出来。
    hits = {}
    scanned = []
    ignored = _replace_ignored(root)
    for layer in layers:
        if not layer or not os.path.isdir(layer):
            continue
        for dirpath, _dirs, files in os.walk(layer):
            rel_dir = os.path.relpath(dirpath, layer).replace(os.sep, "/")
            if rel_dir.startswith(("localisation", "map", ".git")):
                continue
            if any(rel_dir == d or rel_dir.startswith(d + "/") for d in replaced):
                continue
            scanned.append((layer, dirpath, rel_dir, files))
    if not scanned:
        return out
    for layer, dirpath, rel_dir, files in scanned:
        for fn in sorted(files):
            if not fn.endswith(".txt"):
                continue
            p = os.path.join(dirpath, fn)
            base = (rel_dir + "/" + fn) if rel_dir != "." else fn
            # 原版文件加 vanilla/ 前缀，避免和同名 mod 文件混在一起
            rel = base if layer == top else ("vanilla/" + base)
            try:
                with io.open(p, encoding="utf-8-sig", errors="replace") as _fh:
                    txt = _fh.read()
            except Exception:
                continue
            for sub, label, kws in _REF_KEYWORDS:
                if sub not in replaced:
                    continue
                for kw in kws:
                    idx = txt.find(kw)
                    if idx < 0:
                        continue
                    line = txt.count(chr(10), 0, idx) + 1
                    # 按目录归并：原版里同一个目录往往有几十个文件都在引用，
                    # 逐个报会把界面刷满，也没有额外信息量。
                    gkey = rel.rsplit("/", 1)[0] if rel.endswith(".txt") else rel
                    hits.setdefault(gkey, []).append((sub, label, kw, line, rel))
                    break

    for gkey in sorted(hits):
        items = hits[gkey]
        subs = sorted({(i[0], i[1]) for i in items})
        sub_list = [s[0] for s in subs]
        first = items[0]
        ref_dir = _replace_ref_dir(first[4])
        # 用户点过「忽略」的组合不再提示：这些引用确认不会被执行到。
        if _replace_ignore_key(root, sub_list, ref_dir, gkey) in ignored:
            continue
        desc = "、".join("%s(%s)" % (lb, sb) for sb, lb in subs)
        # 「接管」只对真正的子目录开放：common/achievements.txt 这种直接在
        # common/ 根下的文件，分组键会折成 common，接管它等于把整个原版 common
        # （实测 2267 个文件）搬进 mod 再 replace_path="common"，直接把工程炸掉。
        # 这类文件改为开放单文件接管（adopt_file），只拷贝该文件，不写 replace_path。
        raw_rel = (first[4] or "").replace("\\", "/").lstrip("/")
        if raw_rel.startswith("vanilla/"):
            raw_rel = raw_rel[len("vanilla/"):]
        opts = ["drop_replace"]
        note = ""
        ref_file = ""
        adopt_from = ""
        adopt_files = 0
        if "/" in ref_dir:
            why = _replace_adopt_block(ref_dir)
            if why:
                note = why
            else:
                opts.append("adopt_ref_dir")
                src_layer = _replace_owner(top, ref_dir)
                if src_layer and os.path.abspath(src_layer) == os.path.abspath(top):
                    src_layer = None
                if not src_layer:
                    for b in reversed(layers):
                        if not b or os.path.abspath(b) == os.path.abspath(top):
                            continue
                        if os.path.isdir(os.path.join(b, ref_dir.replace("/", os.sep))):
                            src_layer = b
                            break
                if src_layer:
                    src_d = os.path.join(src_layer, ref_dir.replace("/", os.sep))
                    if os.path.isdir(src_d):
                        for _dp, _dn, _fns in os.walk(src_d):
                            adopt_files += len(_fns)
                    if state.game() and is_under_game(src_layer):
                        adopt_from = "原版"
                    else:
                        adopt_from = (_mod_display_name(src_layer)
                                      or os.path.basename(src_layer.rstrip("\\/"))
                                      or src_layer)
        elif ref_dir and "/" in raw_rel:
            opts.append("adopt_file")
            ref_file = raw_rel
            note = ("引用方是 %s 根目录下的单个文件（%s），可单文件接管"
                    "（仅复制该文件到本 mod，不写 replace_path）" % (ref_dir, ref_file))
        else:
            note = ("引用方是 %s 根目录下的单个文件，接管整个 %s 代价太大，"
                    "只能撤销 replace 或忽略" % (ref_dir or "mod", ref_dir or "mod"))
        opts.append("ignore")
        fix = {"kind": "replace_dangling",
               "sub": sub_list[0] if sub_list else "",
               "subs": sub_list,
               "ref_dir": ref_dir,
               "group": gkey,
               "note": note,
               "options": opts}
        if ref_file:
            fix["ref_file"] = ref_file
        if "adopt_ref_dir" in opts:
            fix["adopt_from"] = adopt_from
            fix["adopt_files"] = adopt_files
        out.append(_finding(
            "replace.dangling_refs", "error",
            "这个目录下有 %d 处引用已被 replace 替换掉的 %s，加载期会报 Invalid / Unknown；"
            "首个是 %s 第 %d 行的 %s" % (len(items), desc, first[4], first[3], first[2]),
            first[4], first[3], first[2],
            "要么去掉对应的 replace_path，要么把这个目录也一并替换并自行提供内容",
            fix=fix))
        if len(out) >= 40:
            out.append(_finding(
                "replace.dangling_refs.more", "info",
                "同类目录还有很多，已列出前 40 个", "", 0, "",
                "先处理这 40 个，再重新跑诊断"))
            break
    return out


def _diag_replace_stub(root, own_only=False):
    """声明了 replace_path 的目录，这一层里到底有没有写东西。

    2026-11-02 真机二分（46 轮）的结论固化成检查项：

    * 目录被 replace 但本 mod 里为空 → 引擎在读一个空目录，等于这一类数据全没了
    * 其中 **common/national_focus 没有 `default = yes` 的国策树 → 进游戏必崩**，
      崩点在 `Loaded N provinces` 之后 1–2 秒，`error.log` 一个字都不写，
      堆栈全是 PHYSFS_swapULE64（符号解析失败），从日志上完全看不出来。

    三条对照：注释占位崩、只匹配本 tag 的树崩、带 `default = yes` 的树过。
    """
    out = []
    layers = mod_layers(root) or [root] or []
    top = _top_mod(root)
    scan_layers = [top] if (own_only and top) else list(reversed(layers))
    seen = set()
    for b in scan_layers:
        if not b:
            continue
        try:
            decl = _mod_descriptor(b).get("replace") or []
        except Exception:
            continue
        for sub in decl:
            sub = (sub or "").strip().replace("\\", "/")
            if not sub or sub in seen:
                continue
            seen.add(sub)
            owner = b
            try:
                owner = _replace_owner(root, sub) or b
            except Exception:
                pass
            d = os.path.join(owner, sub.replace("/", os.sep))
            files = []
            anyfile = []
            if os.path.isdir(d):
                anyfile = [f for f in os.listdir(d)
                           if os.path.isfile(os.path.join(d, f))]
                files = [f for f in anyfile if f.endswith(".txt")]
            if not anyfile:
                # 空目录本身不一定会崩：muvluvCN 就把 common/ai_equipment、
                # common/bop 有意 replace 成空，游戏照常进。所以只报 warning，
                # 只有「已知必崩」的目录才升级成 error。
                hard = sub in ("common/national_focus", "history/states")
                out.append(_finding(
                    "replace.empty_dir", "error" if hard else "warning",
                    "%s 被 replace_path 声明为「只从本 mod 读」，但这一层里是空的"
                    " —— 游戏会读到一个空目录" % sub,
                    "descriptor.mod", 0, 'replace_path="%s"' % sub,
                    "删掉这条 replace_path（改为新增文件与原版合并），"
                    "或往 %s/ 里放内容" % sub,
                    {"kind": "replace_dangling", "sub": sub, "subs": [sub],
                     "options": ["drop_replace", "ignore"]}))
                continue
            if not files and sub.startswith(("common/", "history/", "events")):
                out.append(_finding(
                    "replace.no_txt", "warning",
                    "%s 被 replace_path 整体接管，但目录里没有 .txt，"
                    "引擎读不到任何数据" % sub,
                    "descriptor.mod", 0, 'replace_path="%s"' % sub,
                    "确认这一类数据是不是真的不需要"))
            if sub == "common/national_focus":
                blob = ""
                for f in files:
                    try:
                        with io.open(os.path.join(d, f), encoding="utf-8-sig",
                                     errors="replace") as _fh:
                            blob += _fh.read()
                    except Exception:
                        pass
                if "default = yes" not in blob:
                    out.append(_finding(
                        "replace.focus_no_default", "error",
                        "common/national_focus 被整体替换，但没有 default = yes 的"
                        "国策树 —— 实测进游戏必崩，且 error.log 无任何记录",
                        os.path.join("common", "national_focus", files[0]), 0,
                        "缺少 default = yes",
                        "写一棵带 default = yes 的树（qa/world_stubs.py 的 "
                        "focus_tree_stub 可直接用），或撤销这条 replace_path"))
            if sub == "common/ai_strategy":
                for f in files:
                    try:
                        with io.open(os.path.join(d, f), encoding="utf-8-sig",
                                     errors="replace") as _fh:
                            raw = _fh.read()
                    except Exception:
                        continue
                    if re.match(r'\s*ai_strategy\s*=\s*\{\s*\}', raw):
                        out.append(_finding(
                            "replace.ai_strategy_bare", "warning",
                            "common/ai_strategy 里写了空的 `ai_strategy = { }`，"
                            "引擎会把块名当成策略名，报 missing or empty enable trigger",
                            os.path.join("common", "ai_strategy", f), 0,
                            "ai_strategy = { }",
                            "改成一条永不启用的具名策略（见 qa/world_stubs.py）"))
    return out
