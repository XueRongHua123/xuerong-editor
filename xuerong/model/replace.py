# -*- coding: utf-8 -*-
"""replace_path 接管与修复（P0-3 从 focus_editor.py 迁入）。

职责：读某一层的 replace_path、判断某个目录被谁独占、把整目录接管到可写层、
批量修补「声明了 replace 但目录是空的」这类断链。

依赖边界：
  · 路径与叠加链 → xuerong.core.paths（_top_mod / _replace_owner / mod_layers / _pick）
  · 全局容器 → xuerong.state（roots）
  · 三个写盘/重载动作留在门面（adopt_dir / snapshot / reload_data），用 bind() 回注。
    这三个都是「写文件 + 更新历史」的横切能力，不属于任何业务域；
    model 层不许 import 门面（规则 1），只能回注。
"""
import io
import json
import os
import re
import time

from xuerong import state
from xuerong.core import paths
from xuerong.core.paths import _mod_descriptor, _replace_owner, _top_mod, is_under_game, mod_layers
from xuerong.core.text import _atomic_write

_REF_KEYWORDS = (
    ("common/ideas", "国家精神", (
        "add_timed_idea", "add_idea", "add_ideas", "remove_idea", "remove_ideas",
        "swap_ideas", "has_idea", "has_idea_with_trait", "modify_idea")),
    ("common/characters", "人物", (
        "recruit_character", "has_character", "kill_character",
        "retire_character", "add_trait")),
    ("common/national_focus", "国策树", (
        "load_focus_tree", "complete_national_focus", "uncomplete_national_focus")),
    ("common/decisions", "决议", (
        "activate_decision", "complete_decision", "remove_decision")),
    ("common/technologies", "科技", (
        "set_technology", "add_tech_bonus", "has_tech")),
    ("common/units/names", "番号命名组", (
        "division_names_group", "ship_names_group", "army_names_group")),
)

_REPLACE_NEVER_ADOPT = (
    ("music", "纯资源目录，换空后引擎报 Could not find music named maintheme"),
    ("gfx/flags", "所有旗帜 sprite 失效"),
    ("gfx/portraits", "所有人像贴图失效"),
    ("portraits", "所有人像贴图失效"),
    ("gfx/loadingscreens", "读盘图缺失"),
    ("common/units", "师团模板与 OOB 全部失效"),
    ("common/technologies", "set_technology 与科技树全部失效"),
    ("common/country_tags", "整目录替换后原版 383 个 tag 全部失效"),
)

_REPLACE_IGNORE_FILE = os.path.join(paths.app_dir(), "cache", "replace_ignore.json")


def _invalidate_layers():
    """改完 descriptor.mod 必须清两级缓存。

    paths._LAYERS_CACHE 管「叠加链是哪几层」，paths._DESC_CACHE 管「这一层的 replace_path 有哪些」。
    只清前者的话 _replace_owner 还拿旧的 replace 列表判断，撤销了也照旧报危险目录。
    """
    for _c in (paths._LAYERS_CACHE, paths._DESC_CACHE):
        try:
            _c.clear()
        except Exception:
            pass


# ---------------------------------------------------------------- 钩子
_ADOPT_DIR = None
_SNAPSHOT = None
_RELOAD = None
_REF_SCAN = None
_ENSURE_WRITABLE = None
_PROGRESS = {"fn": None, "begin": None, "done": None, "fail": None}


def bind(adopt_dir, snapshot, reload_data, ensure_file_writable=None):
    """门面启动时回注横切依赖（见模块 doc）。"""
    global _ADOPT_DIR, _SNAPSHOT, _RELOAD, _ENSURE_WRITABLE
    _ADOPT_DIR = adopt_dir
    _SNAPSHOT = snapshot
    _RELOAD = reload_data
    _ENSURE_WRITABLE = ensure_file_writable


def set_progress_hook(fn, begin=None, done=None, fail=None):
    """门面启动期注入批量接管进度上报钩子；model 层不 import 门面。"""
    _PROGRESS["fn"] = fn
    _PROGRESS["begin"] = begin
    _PROGRESS["done"] = done
    _PROGRESS["fail"] = fail


def _tick(stage, sub="", pct=0):
    fn = _PROGRESS.get("fn")
    if fn:
        try:
            fn(stage, sub, pct)
        except Exception:
            pass


def set_ref_scanner(fn):
    """回注「这个目录还有谁在引用」的扫描器（diagnose 域的 _diag_replace_refs）。

    replace_drop / replace_fix_all 要数「还有几处引用」，这个扫描属于 diagnose。
    直接 import 会成环（diagnose → replace），所以用钩子。
    """
    global _REF_SCAN
    _REF_SCAN = fn


def _refs(root):
    return list(_REF_SCAN(root)) if _REF_SCAN else []


def _snap(path):
    return _SNAPSHOT(path) if _SNAPSHOT else None


def _adopt(mod_root, sub, force=False, reload=True):
    if _ADOPT_DIR is None:
        return {"ok": False, "msg": "adopt_dir 未注入（门面没调 bind）"}
    try:
        return _ADOPT_DIR(mod_root, sub, force=force, reload=reload)
    except TypeError:
        return _ADOPT_DIR(mod_root, sub, force=force)


def _reload():
    if _RELOAD:
        _RELOAD()


def _replace_collect(layer, sub, pat):
    """收集某个层里某个目录下定义的名字集合。"""
    got = set()
    if not layer:
        return got
    d = os.path.join(layer, *sub.split("/"))
    if not os.path.isdir(d):
        return got
    try:
        fns = os.listdir(d)
    except Exception:
        return got
    for fn in fns:
        if not fn.endswith(".txt"):
            continue
        try:
            with io.open(os.path.join(d, fn), encoding="utf-8-sig",
                         errors="replace") as _fh:
                txt = _fh.read()
        except Exception:
            continue
        for m in re.finditer(pat, txt):
            got.add(m.group(1))
    return got


def _replace_norm(sub):
    return (sub or "").replace("\\", "/").strip("/").lower()


def _replace_ref_dir(rel):
    """把诊断里的 file（可能带 vanilla/ 前缀）折成引用方目录。

    'vanilla/common/achievements/x.txt' -> 'common/achievements'
    'common/achievements.txt'           -> 'common'
    'achievements.txt'                  -> ''
    """
    rel = (rel or "").replace("\\", "/").lstrip("/")
    if rel.startswith("vanilla/"):
        rel = rel[len("vanilla/"):]
    return rel.rsplit("/", 1)[0] if "/" in rel else ""


def _replace_adopt_block(sub):
    """这个目录能不能接管：能返回空串，不能返回原因。"""
    n = _replace_norm(sub)
    if not n:
        return "目录名为空"
    for k, why in _REPLACE_NEVER_ADOPT:
        if n == k or n.startswith(k + "/"):
            return "%s 不能接管（%s）" % (sub, why)
    return ""


def _replace_ignore_all():
    try:
        with io.open(_REPLACE_IGNORE_FILE, encoding="utf-8",
                     errors="replace") as _fh:
            data = json.loads(_fh.read())
        return [x for x in data if isinstance(x, dict)] if isinstance(data, list) else []
    except Exception:
        return []


def _replace_ignore_key(root, subs, ref_dir, group=""):
    """忽略项的唯一键：同一个 mod 里，「同一组被 replace 目录 + 同一个引用方分组」。

    键里带 root 是因为不同 mod 到处都有 common/decisions 这种同名目录，
    A mod 里确认过的忽略不该顺手把 B mod 的同名问题也屏蔽掉。

    group 是诊断里的原始分组键（可能带 vanilla/ 前缀）。必须带上它而不是只用
    ref_dir：vanilla/common/ai_strategy 和本 mod 自己的 common/ai_strategy 折出来
    的 ref_dir 是同一个，只用 ref_dir 会把两条互不相干的分组一起按掉。
    """
    base = os.path.abspath(root or "").replace("\\", "/").lower()
    ss = ",".join(sorted({_replace_norm(s) for s in (subs or []) if _replace_norm(s)}))
    tail = (group or ref_dir or "").replace("\\", "/").lower()
    return "%s|%s|%s" % (base, ss, tail)


def _replace_ignored(root):
    return {x.get("key") for x in _replace_ignore_all() if x.get("key")}


def _save_replace_ignore(data):
    os.makedirs(os.path.dirname(_REPLACE_IGNORE_FILE), exist_ok=True)
    _atomic_write(_REPLACE_IGNORE_FILE,
                  json.dumps(data, ensure_ascii=False, indent=1).encode("utf-8"))


def _ignore_root_key(root):
    return os.path.abspath(root).replace("\\", "/").lower() if root else ""


def _resolve_ignore_root(root=None):
    return paths._pick(root) if root else (state.roots()[-1] if state.roots() else None)


def replace_ignore(root, sub="", ref_dir="", subs=None, group="", remove=False):
    """把一条 replace.dangling_refs 标记为已知问题，不再提示。

    记录只存在本地（work/cache/replace_ignore.json），不写进 mod，
    也不改变游戏行为——它只让诊断闭嘴。remove=True 是恢复提示。
    """
    root = _resolve_ignore_root(root)
    if not root:
        return {"ok": False, "msg": "没有打开的 mod"}
    ss = list(subs) if isinstance(subs, (list, tuple, set)) and subs else [sub]
    key = _replace_ignore_key(root, ss, ref_dir, group)
    if not _replace_norm(ref_dir) and not any(_replace_norm(x) for x in ss):
        return {"ok": False, "msg": "参数不完整"}
    data = _replace_ignore_all()
    kept = [x for x in data if x.get("key") != key]
    if remove:
        changed = len(kept) != len(data)
        msg = "已恢复这条提示" if changed else "这条本来就没有被忽略"
        data = kept
    else:
        msg = "已标记为已知问题，不再提示"
        data = kept + [{"key": key, "root": os.path.abspath(root),
                        "subs": sorted({_replace_norm(x) for x in ss if _replace_norm(x)}),
                        "ref_dir": _replace_norm(ref_dir),
                        "group": (group or "").replace("\\", "/"),
                        "ts": time.strftime("%Y-%m-%d %H:%M:%S")}]
    try:
        _save_replace_ignore(data)
    except Exception as e:
        return {"ok": False, "msg": "忽略记录写入失败：%s" % e}
    return {"ok": True, "msg": msg, "key": key, "count": len(data)}


def replace_ignore_list(root=None):
    """查看已忽略的 replace.dangling_refs 条目（传入或当前有 root 时按 root 过滤）。"""
    root = _resolve_ignore_root(root)
    target = _ignore_root_key(root)
    items = []
    for x in _replace_ignore_all():
        xr = (x.get("root") or "").strip()
        if target and xr and _ignore_root_key(xr) != target:
            continue
        items.append({
            "key": x.get("key") or "",
            "root": xr,
            "subs": list(x.get("subs") or []),
            "ref_dir": x.get("ref_dir") or "",
            "group": x.get("group") or "",
            "ts": x.get("ts") or "",
        })
    return {"ok": True, "items": items, "count": len(items)}


def replace_ignore_remove(key, root=None):
    """按 key 单条删除忽略记录并写回 replace_ignore.json。"""
    data = _replace_ignore_all()
    if not key:
        return {"ok": False, "removed": 0, "count": len(data), "msg": "缺少忽略项 key"}
    kept = [x for x in data if x.get("key") != key]
    removed = len(data) - len(kept)
    if removed:
        try:
            _save_replace_ignore(kept)
        except Exception as e:
            return {"ok": False, "removed": 0, "count": len(data),
                    "msg": "忽略记录写入失败：%s" % e}
    msg = ("已移除 %d 条忽略记录" % removed) if removed else "未找到对应的忽略记录"
    return {"ok": True, "removed": removed, "count": len(kept), "msg": msg}


def replace_ignore_clear(root=None):
    """清空当前 root 下（无 root 则全部）忽略项。"""
    root = _resolve_ignore_root(root)
    target = _ignore_root_key(root)
    data = _replace_ignore_all()
    if target:
        kept = [x for x in data
                if (x.get("root") or "").strip() and _ignore_root_key(x.get("root")) != target]
    else:
        kept = []
    removed = len(data) - len(kept)
    if removed:
        try:
            _save_replace_ignore(kept)
        except Exception as e:
            return {"ok": False, "removed": 0, "count": len(data),
                    "msg": "忽略记录写入失败：%s" % e}
    msg = ("已清空 %d 条忽略记录" % removed) if removed else "当前没有可清空的忽略记录"
    return {"ok": True, "removed": removed, "count": len(kept), "msg": msg}


def replace_drop(root, sub, reload=True):
    """从 descriptor.mod 删掉一条 replace_path。

    只动本 mod（链顶）自己的 descriptor，父 mod 和原版一行不碰：
    父 mod 声明的 replace_path 是那边的意图，改它等于替别人的工程做决定。
    返回 {"ok", "msg", "removed"}。
    """
    sub = (sub or "").replace("\\", "/").strip("/")
    if not sub:
        return {"ok": False, "msg": "目录名不能为空", "removed": 0}
    root = paths._pick(root) if root else (state.roots()[-1] if state.roots() else None)
    top = _top_mod(root)
    if not top or is_under_game(top):
        return {"ok": False, "msg": "找不到可写的 mod 目录", "removed": 0}
    desc_path = os.path.join(top, "descriptor.mod")
    if not os.path.exists(desc_path):
        return {"ok": False, "removed": 0,
                "msg": "%s 里没有 descriptor.mod" % (os.path.basename(top.rstrip("\\/")) or top)}

    owner = _replace_owner(top, sub)
    if owner and os.path.abspath(owner) != os.path.abspath(top):
        return {"ok": False, "removed": 0,
                "msg": "replace_path=\"%s\" 是上一层 mod（%s）声明的，本 mod 删不掉；"
                       "要去那边改，或者改用接管" % (
                           sub, os.path.basename(owner.rstrip("\\/")) or owner)}

    try:
        with io.open(desc_path, "rb") as _fh:
            raw = _fh.read()
    except Exception as e:
        return {"ok": False, "msg": "读 descriptor.mod 失败：%s" % e, "removed": 0}
    has_bom = raw.startswith(b"\xef\xbb\xbf")
    try:
        text = raw.decode("utf-8-sig")
    except Exception:
        text = raw.decode("utf-8", "replace")

    target = _replace_norm(sub)
    pat = re.compile(r'^\s*replace_path\s*=\s*"([^"]*)"', re.I)
    keep, removed = [], 0
    # splitlines(True) 保留原行尾，CRLF 的 descriptor 改完还是 CRLF
    for ln in text.splitlines(True):
        m = pat.match(ln)
        if m and _replace_norm(m.group(1)) == target:
            removed += 1
            continue
        keep.append(ln)

    if not removed:
        return {"ok": True, "removed": 0, "descriptor": desc_path,
                "msg": "descriptor.mod 里已经没有 replace_path=\"%s\"，无需撤销" % sub}

    try:
        _snap(desc_path)
        _atomic_write(desc_path,
                      (b"\xef\xbb\xbf" if has_bom else b"") + "".join(keep).encode("utf-8"))
    except Exception as e:
        return {"ok": False, "msg": "写 descriptor.mod 失败：%s" % e, "removed": 0}

    _invalidate_layers()
    if reload:
        try:
            _reload()
        except Exception:
            pass

    msg = "已从 descriptor.mod 删掉 replace_path=\"%s\"" % sub
    still = _replace_owner(top, sub)
    if still:
        msg += "；但 %s 的 descriptor 也声明了这条，仍然生效" % (
            os.path.basename(still.rstrip("\\/")) or still)
    return {"ok": True, "removed": removed, "descriptor": desc_path, "msg": msg}


def replace_fix_all(root, kind="drop_replace", subs=None, force=False):
    """对 replace 断链做批量修复。

    kind:
      "drop_replace"  —— 对每个危险目录，删掉它的 replace_path
      "adopt_ref_dir" —— 对每个危险目录，把引用方目录接管进本 mod
      "adopt_file"    —— 对单个引用文件做单文件接管（只拷贝该文件，不写 replace_path）

    subs: 只处理这些目录（被 replace 的目录名、引用方目录名或 ref_file 都认），None 表示全部
    force: 接管时允许覆盖本 mod 里已有的同名文件（界面上已 confirm 过）

    返回 {"ok", "kind", "done": [{sub, action, ok, msg}], "left": 剩余危险目录数, "msg"}
    """
    root = paths._pick(root) if root else (state.roots()[-1] if state.roots() else None)
    if not root:
        return {"ok": False, "msg": "没有打开的 mod", "done": [], "left": 0}
    kind = kind if kind in ("drop_replace", "adopt_ref_dir", "adopt_file") else "drop_replace"

    want = set()
    raw_subs = []
    if subs:
        if isinstance(subs, str):
            subs = [subs]
        raw_subs = [str(s) for s in subs if s]
        want = {_replace_norm(s) for s in raw_subs if _replace_norm(s)}

    _beg = _PROGRESS.get("begin")
    if _beg:
        try:
            _beg("replace")
        except Exception:
            pass
    _ok = False
    try:
        _tick("扫描 replace 断链", "", 10)
        findings = [f for f in _refs(root)
                    if f.get("code") == "replace.dangling_refs" and (f.get("fix") or {})]
        if not findings and not (kind == "adopt_file" and raw_subs):
            _ok = True
            return {"ok": True, "kind": kind, "done": [], "left": 0,
                    "msg": "没有需要处理的 replace 断链"}

        top = _top_mod(root)
        done, seen, jobs = [], set(), []
        for f in findings:
            fx = f["fix"]
            fsubs = [s for s in (fx.get("subs") or [fx.get("sub") or ""]) if s]
            ref = fx.get("ref_dir") or ""
            ref_file = fx.get("ref_file") or ""
            if want and not (
                want & {_replace_norm(s) for s in fsubs}
                or _replace_norm(ref) in want
                or (ref_file and _replace_norm(ref_file) in want)
            ):
                continue
            if kind == "drop_replace":
                targets = fsubs
            elif kind == "adopt_file":
                targets = [ref_file] if ref_file and "adopt_file" in (fx.get("options") or []) else []
            else:
                targets = [ref] if ref and "adopt_ref_dir" in (fx.get("options") or []) else []
            for t in targets:
                if kind == "drop_replace":
                    key = "drop:" + _replace_norm(t)
                elif kind == "adopt_file":
                    key = "adopt_file:" + _replace_norm(t)
                else:
                    key = "adopt:" + _replace_norm(t)
                if key in seen:
                    continue
                seen.add(key)
                jobs.append(t)

        # 若直接传入了相对文件路径（如 "common/achievements.txt"），兜底按单文件接管处理
        if kind == "adopt_file" and raw_subs:
            for s in raw_subs:
                t_norm = s.replace("\\", "/").strip("/")
                if "/" not in t_norm or "." not in t_norm.rsplit("/", 1)[1]:
                    continue
                key = "adopt_file:" + _replace_norm(t_norm)
                if key in seen:
                    continue
                seen.add(key)
                jobs.append(t_norm)

        def _run_adopt_file(target_rel):
            t_norm = target_rel.replace("\\", "/").strip("/")
            if "/" not in t_norm:
                done.append({"sub": t_norm, "action": "adopt_file",
                             "ok": False, "msg": "单文件接管需要相对文件路径（如 common/achievements.txt）",
                             "copied": 0})
                return
            if _ENSURE_WRITABLE is None:
                done.append({"sub": t_norm, "action": "adopt_file",
                             "ok": False, "msg": "ensure_file_writable 未注入（门面没调 bind）",
                             "copied": 0})
                return
            sub_part, base_part = t_norm.rsplit("/", 1)
            dst, emsg = _ENSURE_WRITABLE(top, sub_part, base_part)
            done.append({"sub": t_norm, "action": "adopt_file",
                         "ok": bool(dst), "msg": emsg or "",
                         "copied": 1 if (dst and emsg != "已存在") else 0})

        total = len(jobs)
        for idx, t in enumerate(jobs, 1):
            _tick("正在处理 %d/%d" % (idx, total), t, 20 + int(55 * idx / max(1, total)))
            if kind == "drop_replace":
                r = replace_drop(root, t, reload=False)
                done.append({"sub": t, "action": "drop_replace",
                             "ok": bool(r.get("ok")), "msg": r.get("msg") or ""})
            elif kind == "adopt_file":
                _run_adopt_file(t)
            else:
                why = _replace_adopt_block(t)
                if why:
                    done.append({"sub": t, "action": "adopt_ref_dir",
                                 "ok": False, "msg": why})
                    continue
                r = _adopt(top, t, force=bool(force), reload=False)
                done.append({"sub": t, "action": "adopt_ref_dir",
                             "ok": bool(r.get("ok")),
                             "msg": r.get("msg") or "",
                             "copied": r.get("copied", 0)})

        ok_n = len([d for d in done if d["ok"]])
        if ok_n and kind in ("drop_replace", "adopt_ref_dir"):
            _tick("重载 mod 数据", "", 80)
            try:
                _reload()
            except Exception:
                pass

        if kind == "drop_replace":
            msg = "撤销 %d 条 replace_path" % ok_n
        elif kind == "adopt_file":
            copied = sum(int(d.get("copied") or 0) for d in done if d["ok"])
            msg = "单文件接管 %d 个文件（新拷贝 %d 个）" % (ok_n, copied)
        else:
            copied = sum(int(d.get("copied") or 0) for d in done if d["ok"])
            msg = "接管 %d 个目录，拷贝 %d 个文件" % (ok_n, copied)
        if len(done) > ok_n:
            msg += "；%d 条未成功（原因见列表）" % (len(done) - ok_n)

        # 全部做完再看还剩多少：不能拿旧清单算，撤销一条会连带别的条目一起消失
        left = 0
        if done:
            _tick("复核剩余断链", "", 92)
            try:
                left = len([f for f in _refs(root)
                            if f.get("code") == "replace.dangling_refs"])
            except Exception:
                left = 0
            msg += "，剩余 %d 个危险目录" % left
        else:
            left = len(findings)
            msg = "没有匹配到要处理的目录"
        _ok = True
        return {"ok": True, "kind": kind, "done": done, "left": left, "msg": msg}
    except Exception as _err:
        _fail = _PROGRESS.get("fail")
        if _fail:
            try:
                _fail(_err)
            except Exception:
                pass
        raise
    finally:
        if _ok:
            _done = _PROGRESS.get("done")
            if _done:
                try:
                    _done()
                except Exception:
                    pass
