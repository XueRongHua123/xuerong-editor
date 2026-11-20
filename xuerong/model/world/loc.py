# -*- coding: utf-8 -*-
"""本地化补全：算缺哪些键、扫已定义集合、缺键清单、生成 yml。"""
import io
import os
import re

from xuerong import state
from xuerong.core.paths import mod_layers
from xuerong.core.text import _atomic_write, _bom_for, brace_match, strip_comments
from xuerong.model.history import snapshot
from xuerong.model.map import _map_pick
from xuerong.model.world._inj import _reload

# ref: CWTools "Code actions to generate .yml for missing localisation"
def _loc_need_keys(root, layers):
    """扫 mod 脚本，收集「应该存在」的本地化键 → {key: 类型}

    只收有明确命名规则的三类：
      focus id = X            → X, X_desc
      country_event id = X    → X.title, X.desc, X.a/.b... 的 option 名不猜
      ideas 里的 X = { }      → X, X_desc
    """
    need = {}
    # 只查 mod 自己写的脚本：原版的几千个事件文件不该算进来
    # （原版本地化本来就不全，查它只会得到一屏无意义的报缺）
    for rel_dir in ("common/national_focus", "events", "common/ideas"):
        _d = os.path.join(root, rel_dir)
        if not os.path.isdir(_d):
            continue
        _files = []
        for _dp, _dn, _fs in os.walk(_d):
            for _fn in _fs:
                if _fn.endswith(".txt"):
                    _files.append(os.path.join(_dp, _fn))
        for f in _files:
            try:
                text = strip_comments(io.open(f, encoding="utf-8-sig", errors="replace").read())
            except Exception:
                continue
            # 文件可能来自别的盘（原版在 E:、mod 在 D:），不能按相对目录算
            rel = os.path.basename(f)
            for _b in layers:
                if _b and os.path.abspath(f).startswith(os.path.abspath(_b) + os.sep):
                    try:
                        rel = os.path.relpath(f, _b)
                    except Exception:
                        rel = os.path.basename(f)
                    break
            # 国策
            for m in re.finditer(r'(?m)^\s*focus\s*=\s*\{', text):
                b = text.find("{", m.end() - 1)
                e = brace_match(text, b)
                if e <= b:
                    continue
                body = text[b + 1:e - 1]
                fid = re.search(r'(?m)^\s*id\s*=\s*([A-Za-z0-9_.\-]+)', body)
                if not fid:
                    continue
                k = fid.group(1)
                need.setdefault(k, ("focus", rel))
                need.setdefault(k + "_desc", ("focus", rel))
            # 事件
            for m in re.finditer(r'(?m)^\s*(?:country_event|news_event|state_event)\s*=\s*\{', text):
                b = text.find("{", m.end() - 1)
                e = brace_match(text, b)
                if e <= b:
                    continue
                body = text[b + 1:e - 1]
                eid = re.search(r'(?m)^\s*id\s*=\s*([A-Za-z0-9_.\-]+)', body)
                if not eid:
                    continue
                k = eid.group(1)
                # 事件的本地化键由 title= / desc= 显式给出（常见写法 BETA.1.t / BETA.1.d），
                # 不是固定 id+".title"。没写才回退到默认命名。
                mt = re.search(r'(?m)^\s*title\s*=\s*"?([A-Za-z0-9_.\-]+)"?', body)
                md = re.search(r'(?m)^\s*desc\s*=\s*"?([A-Za-z0-9_.\-]+)"?', body)
                need.setdefault(mt.group(1) if mt else (k + ".title"), ("event", rel))
                need.setdefault(md.group(1) if md else (k + ".desc"), ("event", rel))
            # 国家精神（ideas 里的顶层键；跳过 country/character 这类容器）
            if rel_dir == "common/ideas":
                skip = {"country", "character", "hidden_ideas", "law", "mio", "use_list_view"}
                for m in re.finditer(r'(?m)^\t([A-Za-z0-9_]+)\s*=\s*\{', text):
                    name = m.group(1)
                    if name in skip:
                        continue
                    need.setdefault(name, ("idea", rel))
                    need.setdefault(name + "_desc", ("idea", rel))
    return need


def _loc_defined_set(root):
    """已定义的本地化键 = 原版 LOC + 这个 mod（含所有语言与 replace 子目录）自己的 yml。

    LOC 里只有启动时载入的原版键，mod 的自定义键必须现扫，否则全部误报缺失。"""
    defined = set(state.loc().keys())
    line_re = re.compile(r'^\s*([A-Za-z0-9_.\-]+):\d*\s+"')
    for lang in ("simp_chinese", "english", "japanese", "korean", "russian", "french",
                 "german", "spanish", "polish", "portuguese", "braz_por", "turkish"):
        d = os.path.join(root, "localisation", lang)
        if not os.path.isdir(d):
            continue
        for dirpath, _dn, files in os.walk(d):
            for fn in files:
                if not fn.endswith(".yml"):
                    continue
                try:
                    for ln in io.open(os.path.join(dirpath, fn), encoding="utf-8-sig",
                                      errors="replace").read().splitlines():
                        m = line_re.match(ln)
                        if m:
                            defined.add(m.group(1))
                except Exception:
                    pass
    return defined


def loc_missing(root=None, limit=800):
    """列出缺失的本地化键（引用存在但没有任何 yml 定义）"""
    root = _map_pick(root)
    layers = mod_layers(root)
    _defined = _loc_defined_set(root) if root else set(state.loc().keys())
    need = _loc_need_keys(root, layers)
    if not need:
        return {"ok": True, "total": 0, "missing": [],
                "msg": "没有找到需要本地化的脚本引用"}
    miss = []
    by_kind = {}
    for k, (kind, src) in need.items():
        if k in _defined:
            continue
        miss.append({"key": k, "kind": kind, "file": src})
        by_kind[kind] = by_kind.get(kind, 0) + 1
    miss.sort(key=lambda x: (x["kind"], x["key"]))
    return {"ok": True, "total": len(miss), "by_kind": by_kind,
            "need": len(need), "defined": len(need) - len(miss),
            "missing": miss[:limit],
            "truncated": len(miss) > limit,
            "msg": "引用 %d 个本地化键，缺 %d 个" % (len(need), len(miss))}


def loc_generate(root=None, keys=None, lang="simp_chinese", dry=False):
    """把缺失的键写进 zz_xuerong_autogen_l_<lang>.yml（占位文本，带 BOM）

    参考 CWTools：只补键不猜内容，占位值用键名本身，方便一眼认出还没翻译。
    """
    root = _map_pick(root)
    if not root:
        return {"ok": False, "msg": "没有加载 mod"}
    layers = mod_layers(root)
    if keys is None:
        r = loc_missing(root, limit=100000)
        keys = [x["key"] for x in r.get("missing") or []]
    _defined2 = _loc_defined_set(root)
    keys = [k for k in (keys or []) if k and k not in _defined2]
    if not keys:
        return {"ok": True, "written": 0, "msg": "没有需要生成的键"}

    lang_dir = os.path.join(root, "localisation", lang)
    fn = os.path.join(lang_dir, "zz_xuerong_autogen_l_%s.yml" % lang)
    if dry:
        return {"ok": True, "dry": True, "count": len(keys), "path": fn,
                "msg": "将写入 %d 个键到 %s" % (len(keys), os.path.basename(fn))}

    # 已有的自动生成文件：保留用户改过的行，只追加新键
    existing = {}
    if os.path.exists(fn):
        try:
            line_re = re.compile(r'^\s*([A-Za-z0-9_.\-]+):\d*\s+"(.*)"\s*$')
            for ln in io.open(fn, encoding="utf-8-sig", errors="replace").read().splitlines():
                m = line_re.match(ln)
                if m:
                    existing[m.group(1)] = m.group(2)
        except Exception:
            pass

    added = 0
    for k in keys:
        if k in existing:
            continue
        existing[k] = k        # 占位值 = 键名
        added += 1
    if not added:
        return {"ok": True, "written": 0, "msg": "这些键都已在自动生成文件里"}

    os.makedirs(lang_dir, exist_ok=True)
    lines = ["l_%s:" % lang]
    for k in sorted(existing):
        v = str(existing[k]).replace('"', "'")
        lines.append(' %s:0 "%s"' % (k, v))
    body = chr(10).join(lines) + chr(10)
    snapshot(fn) if os.path.exists(fn) else None
    _atomic_write(fn, _bom_for(fn) + body.encode("utf-8"))
    _reload()
    return {"ok": True, "written": added, "total": len(existing), "path": fn,
            "msg": "已写入 %d 个键到 %s（占位值=键名，改完重新加载本地化）" % (
                added, os.path.basename(fn))}
