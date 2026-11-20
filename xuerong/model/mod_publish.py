# -*- coding: utf-8 -*-
"""7-5 打包发布：导出工坊就绪的干净 mod 目录与官方启动器 .mod 描述文件。

职责：
  1. 扫描源 mod 目录，剔除编辑器备份（*.bak）、临时/日志/缓存目录与杂项；
  2. 校验并补全 descriptor.mod（name / version / supported_version / tags / picture /
     dependencies 真实 name= / replace_path / remote_file_id）；
  3. 保证 thumbnail.png 存在（缺失时生成 256x256 占位图）；
  4. 按编码约定在导出副本中规范化 UTF-8 BOM：localisation/**/*.yml 带 BOM，
     其余文本文件（.txt / .mod / .gfx / .gui 等）剥离误加的 BOM；
  5. 可选在 Paradox 用户目录 mod/ 下生成 <folder_id>.mod 让官方启动器直接识别，
     并支持同时打包 .zip 压缩包。
"""
import io
import os
import re
import shutil
import time
import zipfile

from xuerong import state
from xuerong.core import paths
from xuerong.core.paths import (
    _mod_descriptor, _resolve_mod_path, detect_game_version, discover_mods,
    is_readonly_mod, is_under_game, mod_layers, pdx_user_dir,
)
from xuerong.core.text import _atomic_write
from xuerong.model.world.create import _resolve_dep_name, _write_placeholder_thumbnail, mod_home

_UTF8_BOM = b"\xef\xbb\xbf"

_SKIP_DIR_NAMES = {
    "__pycache__", ".git", ".svn", ".hg", ".vscode", ".idea",
    ".xr_backups", "backup", "backups", "output", "history",
    "cache", "focus_editor_exports", "map_cache", "tmp",
}
_SKIP_FILE_NAMES = {
    "thumbs.db", ".ds_store", "desktop.ini",
}
_SKIP_EXTS = (".bak", ".tmp", ".orig", ".pyc", ".pyo", ".log", ".swp", ".autosave")
_TEXT_EXTS = {
    ".txt", ".yml", ".mod", ".gfx", ".gui", ".asset", ".sfx",
    ".csv", ".md", ".json", ".shader", ".fxh",
}


def default_export_base():
    """默认导出父目录：app_dir()/focus_editor_exports。"""
    return os.path.join(paths.app_dir(), "focus_editor_exports")


def _safe_folder_id(raw):
    s = (raw or "").strip()
    if not s or s in (".", "..") or not re.match(r"^[A-Za-z0-9_.-]+$", s):
        return ""
    return s


def _quote_val(v):
    return str(v or "").replace("\\", "/").replace('"', '\\"')


def _check_braces(text):
    depth = 0
    in_str = False
    escaped = False
    in_comment = False
    for ch in text:
        if ch in ("\r", "\n"):
            in_comment = False
            continue
        if in_comment:
            continue
        if ch == "#" and not in_str:
            in_comment = True
            continue
        if ch == "\\" and in_str and not escaped:
            escaped = True
            continue
        if ch == '"' and not escaped:
            in_str = not in_str
        escaped = False
        if in_str:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth < 0:
                return False, depth
    return depth == 0, depth


def _read_descriptor_full(mod_root):
    """完整解析 mod 根目录的 descriptor.mod，保留常见元数据与 replace_path。"""
    dp = os.path.join(os.path.abspath(mod_root or ""), "descriptor.mod")
    info = {
        "exists": os.path.isfile(dp),
        "name": "",
        "version": "",
        "supported_version": "",
        "tags": [],
        "dependencies": [],
        "replace_path": [],
        "picture": "",
        "remote_file_id": "",
    }
    if not info["exists"]:
        return info
    try:
        text = io.open(dp, encoding="utf-8-sig", errors="replace").read()
    except Exception:
        return info

    def _scalar(key):
        m = re.search(r'(?m)^\s*%s\s*=\s*"([^"]*)"' % re.escape(key), text)
        return m.group(1) if m else ""

    info["name"] = _scalar("name")
    info["version"] = _scalar("version")
    info["supported_version"] = _scalar("supported_version")
    info["picture"] = _scalar("picture")
    info["remote_file_id"] = _scalar("remote_file_id")

    m_tags = re.search(r'(?ms)^\s*tags\s*=\s*\{([^}]*)\}', text)
    if m_tags:
        info["tags"] = re.findall(r'"([^"]+)"', m_tags.group(1))
    m_deps = re.search(r'(?ms)^\s*dependencies\s*=\s*\{([^}]*)\}', text)
    if m_deps:
        info["dependencies"] = re.findall(r'"([^"]+)"', m_deps.group(1))
    info["replace_path"] = re.findall(r'(?m)^\s*replace_path\s*=\s*"([^"]*)"', text)
    return info


def _validate_dependencies(deps, layers=None):
    """校验依赖项是否为真实 descriptor name=，尝试自动校准路径或文件夹名。"""
    avail = []
    try:
        avail = discover_mods()
    except Exception:
        avail = []
    by_name = {}
    by_folder = {}
    by_path = {}
    for m in avail:
        mp = os.path.abspath(m.get("path") or "") if m.get("path") else ""
        dn = (m.get("descriptor_name") or m.get("name") or "").strip()
        fd = (m.get("folder") or "").strip()
        if dn:
            by_name[dn.lower()] = (dn, mp)
        if fd:
            by_folder[fd.lower()] = (dn or fd, mp)
        if mp:
            by_path[os.path.normcase(mp)] = (dn or fd, mp)
    for lay in (layers or []):
        if not lay or is_under_game(lay):
            continue
        ab = os.path.abspath(lay)
        dn = (_mod_descriptor(ab).get("name") or "").strip()
        fd = os.path.basename(ab.rstrip("\\/"))
        if dn:
            by_name.setdefault(dn.lower(), (dn, ab))
        if fd:
            by_folder.setdefault(fd.lower(), (dn or fd, ab))
        by_path.setdefault(os.path.normcase(ab), (dn or fd, ab))

    out = []
    for raw in (deps or []):
        d = str(raw or "").strip()
        if not d:
            continue
        resolved = _resolve_dep_name(d) or d
        low = resolved.lower()
        found = False
        found_path = ""
        if low in by_name:
            resolved, found_path = by_name[low]
            found = True
        elif low in by_folder:
            resolved, found_path = by_folder[low]
            found = True
        else:
            norm = os.path.normcase(os.path.abspath(d)) if os.path.isdir(d) else ""
            if norm and norm in by_path:
                resolved, found_path = by_path[norm]
                found = True
        out.append({
            "raw": d,
            "resolved": resolved,
            "changed": resolved != d,
            "found": found,
            "path": found_path,
        })
    return out


def _pick_candidates(layers=None):
    """列出可作为打包发布目标的已加载模组（排除游戏本体，可写层优先）。"""
    cands = []
    seen = set()
    raw_layers = list(layers or [])
    if not raw_layers:
        rs = state.roots()
        if rs:
            raw_layers = mod_layers(rs[-1])
    for p in reversed(raw_layers):
        if not p or not os.path.isdir(p) or is_under_game(p):
            continue
        ab = os.path.abspath(p)
        k = os.path.normcase(ab)
        if k in seen:
            continue
        seen.add(k)
        desc = _mod_descriptor(ab)
        ro = is_readonly_mod(ab)
        cands.append({
            "path": ab,
            "folder": os.path.basename(ab.rstrip("\\/")) or ab,
            "name": desc.get("name") or os.path.basename(ab.rstrip("\\/")) or ab,
            "readonly": ro,
        })
    # 可写模组排前面
    cands.sort(key=lambda x: (1 if x["readonly"] else 0))
    return cands


def _is_loc_yml(rel_posix):
    return rel_posix.lower().endswith(".yml")


def _scan_mod_tree(mod_root, picture_rel="thumbnail.png"):
    """扫描源 mod 目录，分类列出纳入文件、被剔除的备份/缓存与 BOM/括号状态。"""
    ab = os.path.abspath(mod_root)
    pic_norm = (picture_rel or "thumbnail.png").replace("\\", "/").lstrip("./").lower()
    included = []
    excluded = []
    has_picture = False
    bom_add = []
    bom_strip = []
    brace_warns = []

    for cur, dirs, files in os.walk(ab, topdown=True):
        kept_dirs = []
        for d in sorted(dirs):
            low_d = d.lower()
            full_d = os.path.join(cur, d)
            rel_d = os.path.relpath(full_d, ab).replace("\\", "/")
            if low_d in _SKIP_DIR_NAMES or d.startswith("."):
                # 记录被剔除目录下的文件数，避免大目录无声消失
                skipped_cnt = 0
                for _c2, _d2, _f2 in os.walk(full_d):
                    skipped_cnt += len(_f2)
                excluded.append({
                    "rel": rel_d + "/",
                    "reason": "skip_dir",
                    "count": skipped_cnt,
                    "detail": "编辑器/缓存/隐藏目录（含 %d 个文件）" % skipped_cnt,
                })
            else:
                kept_dirs.append(d)
        dirs[:] = kept_dirs

        at_root = (os.path.abspath(cur) == ab)
        for fn in sorted(files):
            full = os.path.join(cur, fn)
            rel = os.path.relpath(full, ab).replace("\\", "/")
            low = fn.lower()
            low_rel = rel.lower()
            if at_root and low == "descriptor.mod":
                # descriptor.mod 由发布流程校验并规范写出，不按普通文件复制
                continue
            if at_root and low.endswith(".mod") and low != "descriptor.mod":
                excluded.append({"rel": rel, "reason": "launcher_meta", "count": 1, "detail": "启动器外层 .mod 文件"})
                continue
            if low in _SKIP_FILE_NAMES or low.endswith(_SKIP_EXTS) or fn.endswith("~"):
                reason = "bak" if low.endswith(".bak") else "temp"
                excluded.append({
                    "rel": rel,
                    "reason": reason,
                    "count": 1,
                    "detail": "备份文件 (.bak)" if reason == "bak" else "系统/临时/日志文件",
                })
                continue

            if low_rel == pic_norm:
                has_picture = True

            try:
                sz = os.path.getsize(full)
            except Exception:
                sz = 0
            ext = os.path.splitext(low)[1]
            bom_action = "none"
            if ext in _TEXT_EXTS:
                try:
                    raw = io.open(full, "rb").read()
                except Exception:
                    raw = b""
                has_bom = raw.startswith(_UTF8_BOM)
                if _is_loc_yml(rel):
                    if not has_bom:
                        bom_action = "add_bom"
                        bom_add.append(rel)
                else:
                    if has_bom:
                        bom_action = "strip_bom"
                        bom_strip.append(rel)
                if ext == ".txt":
                    txt_body = raw[3:] if has_bom else raw
                    ok_b, depth_b = _check_braces(txt_body.decode("utf-8", errors="replace"))
                    if not ok_b:
                        brace_warns.append({"rel": rel, "depth": depth_b})

            included.append({
                "rel": rel,
                "abs": full,
                "size": sz,
                "ext": ext,
                "bom_action": bom_action,
            })

    return {
        "included": included,
        "excluded": excluded,
        "has_picture": has_picture,
        "bom_add": bom_add,
        "bom_strip": bom_strip,
        "brace_warns": brace_warns,
    }


def _render_descriptor_lines(meta):
    """生成标准 descriptor.mod 行序列。"""
    lines = [
        'version="%s"' % _quote_val(meta.get("version") or "0.1.0"),
        "tags={",
    ]
    tags = [t for t in (meta.get("tags") or []) if str(t).strip()]
    if not tags:
        tags = ["Alternative History"]
    for t in tags:
        lines.append('\t"%s"' % _quote_val(t))
    lines.append("}")
    lines.append('name="%s"' % _quote_val(meta.get("name") or "My Mod"))
    lines.append('supported_version="%s"' % _quote_val(meta.get("supported_version") or detect_game_version()))
    pic = (meta.get("picture") or "thumbnail.png").strip() or "thumbnail.png"
    lines.append('picture="%s"' % _quote_val(pic))
    deps = [d for d in (meta.get("dependencies") or []) if str(d).strip()]
    if deps:
        lines.append("dependencies={")
        for d in deps:
            lines.append('\t"%s"' % _quote_val(d))
        lines.append("}")
    for rp in (meta.get("replace_path") or []):
        rp_s = str(rp or "").strip()
        if rp_s:
            lines.append('replace_path="%s"' % _quote_val(rp_s))
    rid = (meta.get("remote_file_id") or "").strip()
    if rid:
        lines.append('remote_file_id="%s"' % _quote_val(rid))
    return lines


def _check_launcher_conflict(folder_id, target_dir, docs_dir=""):
    """检查 <docs_dir>/mod/<folder_id>.mod 是否已存在且指向不同目录。"""
    dd = docs_dir or pdx_user_dir()
    mod_dir = os.path.join(dd, "mod")
    mod_file = os.path.join(mod_dir, folder_id + ".mod")
    if not os.path.isfile(mod_file):
        return {"exists": False, "conflict": False, "mod_file": mod_file, "existing_path": ""}
    existing_path = ""
    try:
        txt = io.open(mod_file, encoding="utf-8-sig", errors="replace").read()
        m = re.search(r'(?m)^\s*path\s*=\s*"([^"]+)"', txt)
        if m:
            existing_path = _resolve_mod_path(m.group(1), dd) or m.group(1)
    except Exception:
        existing_path = ""
    if not existing_path:
        return {"exists": True, "conflict": True, "mod_file": mod_file, "existing_path": ""}
    same = os.path.normcase(os.path.abspath(existing_path)) == os.path.normcase(os.path.abspath(target_dir))
    return {
        "exists": True,
        "conflict": not same,
        "mod_file": mod_file,
        "existing_path": existing_path,
    }


def _resolve_meta(mod_root, layers=None, overrides=None):
    ov = overrides or {}
    raw_desc = _read_descriptor_full(mod_root)
    folder_default = os.path.basename(os.path.abspath(mod_root).rstrip("\\/")) or "my_mod"

    name = (ov.get("name") if ov.get("name") is not None else raw_desc["name"]) or folder_default
    version = (ov.get("version") if ov.get("version") is not None else raw_desc["version"]) or "0.1.0"
    supported_version = (
        ov.get("supported_version") if ov.get("supported_version") is not None
        else raw_desc["supported_version"]
    ) or detect_game_version()

    if ov.get("tags") is not None:
        raw_tags = ov.get("tags")
        if isinstance(raw_tags, str):
            tags = [x.strip() for x in re.split(r"[,，\n]+", raw_tags) if x.strip()]
        else:
            tags = [str(x).strip() for x in raw_tags if str(x).strip()]
    else:
        tags = list(raw_desc["tags"] or ["Alternative History"])

    if ov.get("dependencies") is not None:
        raw_deps = ov.get("dependencies")
        if isinstance(raw_deps, str):
            deps_in = [x.strip() for x in re.split(r"[\n,]+", raw_deps) if x.strip()]
        else:
            deps_in = [str(x).strip() for x in raw_deps if str(x).strip()]
    else:
        deps_in = list(raw_desc["dependencies"])

    dep_checks = _validate_dependencies(deps_in, layers=layers)
    resolved_deps = []
    seen_d = set()
    for dc in dep_checks:
        rname = dc["resolved"]
        if rname and rname not in seen_d:
            seen_d.add(rname)
            resolved_deps.append(rname)

    # 若原 descriptor 缺依赖且当前叠加链底下有非游戏父层，给建议提示
    suggested_deps = []
    if not resolved_deps and layers:
        ab_self = os.path.normcase(os.path.abspath(mod_root))
        for p in layers:
            if not p or is_under_game(p):
                continue
            ab_p = os.path.normcase(os.path.abspath(p))
            if ab_p == ab_self:
                break
            pn = (_mod_descriptor(p).get("name") or "").strip()
            if pn and pn not in suggested_deps:
                suggested_deps.append(pn)

    picture = raw_desc["picture"] or "thumbnail.png"
    meta = {
        "name": name.strip(),
        "version": version.strip(),
        "supported_version": supported_version.strip(),
        "tags": tags or ["Alternative History"],
        "dependencies": resolved_deps,
        "replace_path": list(raw_desc["replace_path"]),
        "picture": picture,
        "remote_file_id": raw_desc["remote_file_id"],
    }
    return raw_desc, meta, dep_checks, suggested_deps


def _is_same_or_nested(path_a, path_b):
    a = os.path.normcase(os.path.abspath(path_a))
    b = os.path.normcase(os.path.abspath(path_b))
    if a == b:
        return True
    try:
        return os.path.commonpath([a, b]) in (a, b)
    except ValueError:
        return False


def preview_publish(mod_root="", layers=None, out_dir="", folder_id="", docs_dir="", overrides=None):
    """7-5 打包发布预检：返回待发布 mod 的元数据、依赖校验、剔除清单与 BOM 修正预览。"""
    cands = _pick_candidates(layers)
    chosen = (mod_root or "").strip()
    if not chosen and cands:
        chosen = cands[0]["path"]
    dd = docs_dir or pdx_user_dir()
    base_out = os.path.abspath(out_dir or default_export_base())
    launcher_base = os.path.join(dd, "mod")

    if not chosen or not os.path.isdir(chosen):
        return {
            "ok": False,
            "msg": "请先加载或选择一个本地 mod 根目录再打包发布。",
            "candidates": cands,
            "default_out_dir": base_out,
            "launcher_mod_dir": launcher_base,
        }
    ab = os.path.abspath(chosen)
    if is_under_game(ab):
        return {
            "ok": False,
            "msg": "不能对游戏本体目录执行打包发布，请选择你自己的 mod。",
            "candidates": cands,
            "default_out_dir": base_out,
            "launcher_mod_dir": launcher_base,
        }

    raw_desc, meta, dep_checks, suggested_deps = _resolve_meta(ab, layers=layers, overrides=overrides)
    fid = _safe_folder_id(folder_id) or _safe_folder_id(os.path.basename(ab.rstrip("\\/"))) or "published_mod"
    target_dir = os.path.join(base_out, fid)
    scan = _scan_mod_tree(ab, picture_rel=meta["picture"])
    l_conflict = _check_launcher_conflict(fid, target_dir, docs_dir=dd)

    return {
        "ok": True,
        "mod_root": ab,
        "readonly": is_readonly_mod(ab),
        "candidates": cands,
        "folder_id": fid,
        "default_out_dir": base_out,
        "launcher_mod_dir": launcher_base,
        "target_dir": target_dir,
        "descriptor_exists": raw_desc["exists"],
        "meta": meta,
        "dep_checks": dep_checks,
        "suggested_deps": suggested_deps,
        "has_picture": scan["has_picture"],
        "will_generate_thumbnail": not scan["has_picture"],
        "included_count": len(scan["included"]),
        "total_bytes": sum(x["size"] for x in scan["included"]),
        "excluded_files": scan["excluded"],
        "excluded_count": sum(x["count"] for x in scan["excluded"]),
        "bom_add": scan["bom_add"],
        "bom_strip": scan["bom_strip"],
        "brace_warns": scan["brace_warns"],
        "launcher_conflict": l_conflict,
        "target_nested_warning": _is_same_or_nested(ab, target_dir),
    }


def _verify_exported_tree(export_dir, picture_rel="thumbnail.png"):
    """落盘后自校验导出的工坊目录：descriptor / thumbnail / 无残留 / BOM 合规。"""
    problems = []
    desc_fp = os.path.join(export_dir, "descriptor.mod")
    if not os.path.isfile(desc_fp):
        problems.append("缺少 descriptor.mod")
    else:
        raw_d = io.open(desc_fp, "rb").read()
        if raw_d.startswith(_UTF8_BOM):
            problems.append("descriptor.mod 不应带 UTF-8 BOM")
        txt_d = raw_d.decode("utf-8", errors="replace")
        for req in ("name", "version", "supported_version"):
            if not re.search(r'(?m)^\s*%s\s*=\s*"[^"]+"' % req, txt_d):
                problems.append("descriptor.mod 缺少字段 %s" % req)

    pic_fp = os.path.join(export_dir, (picture_rel or "thumbnail.png").replace("/", os.sep))
    if not os.path.isfile(pic_fp) or os.path.getsize(pic_fp) <= 0:
        problems.append("缺少封面图 %s" % picture_rel)

    yml_checked = 0
    non_yml_checked = 0
    for cur, dirs, files in os.walk(export_dir):
        for d in dirs:
            if d.lower() in _SKIP_DIR_NAMES or d.startswith("."):
                problems.append("残留无关目录: %s" % d)
        for fn in files:
            low = fn.lower()
            if low in _SKIP_FILE_NAMES or low.endswith(_SKIP_EXTS) or fn.endswith("~"):
                problems.append("残留临时/备份文件: %s" % fn)
            fp = os.path.join(cur, fn)
            rel = os.path.relpath(fp, export_dir).replace("\\", "/")
            ext = os.path.splitext(low)[1]
            if ext not in _TEXT_EXTS:
                continue
            raw = io.open(fp, "rb").read()
            has_bom = raw.startswith(_UTF8_BOM)
            if _is_loc_yml(rel):
                yml_checked += 1
                if not has_bom:
                    problems.append("本地化缺少 UTF-8 BOM: %s" % rel)
            else:
                non_yml_checked += 1
                if has_bom:
                    problems.append("非本地化文件不应带 UTF-8 BOM: %s" % rel)
    return {
        "ok": len(problems) == 0,
        "problems": problems,
        "yml_checked": yml_checked,
        "non_yml_checked": non_yml_checked,
    }


def export_publish(mod_root="", layers=None, out_dir="", folder_id="", docs_dir="",
                   register_launcher=True, overwrite_launcher_mod=False,
                   also_zip=False, overrides=None):
    """导出工坊就绪的干净 mod 目录，可选注册到 Paradox 官方启动器并打包 .zip。"""
    cands = _pick_candidates(layers)
    chosen = (mod_root or "").strip() or (cands[0]["path"] if cands else "")
    if not chosen or not os.path.isdir(chosen):
        return {"ok": False, "msg": "找不到待发布的 mod 目录"}
    ab_src = os.path.abspath(chosen)
    if is_under_game(ab_src):
        return {"ok": False, "msg": "不能对游戏本体目录执行打包发布"}

    fid = _safe_folder_id(folder_id)
    if not fid:
        return {"ok": False, "msg": "导出文件夹名只能包含字母、数字、下划线、点或连字符"}

    base_out = os.path.abspath(out_dir or default_export_base())
    target_dir = os.path.join(base_out, fid)
    if _is_same_or_nested(ab_src, target_dir):
        return {
            "ok": False,
            "msg": "导出目录不能与源 mod 目录相同或嵌套（%s），请改用独立输出目录或修改导出文件夹名。" % target_dir,
        }

    dd = docs_dir or pdx_user_dir()
    l_conflict = _check_launcher_conflict(fid, target_dir, docs_dir=dd)
    if register_launcher and l_conflict["conflict"] and not overwrite_launcher_mod:
        return {
            "ok": False,
            "launcher_conflict": True,
            "conflict_path": l_conflict["existing_path"],
            "launcher_mod_file": l_conflict["mod_file"],
            "msg": "启动器目录已存在同名 %s.mod（当前指向 %s）。请勾选「允许更新同名启动器 .mod」或更换导出文件夹名。"
                   % (fid, l_conflict["existing_path"] or "其它位置"),
        }

    _raw_desc, meta, dep_checks, _suggested = _resolve_meta(ab_src, layers=layers, overrides=overrides)
    scan = _scan_mod_tree(ab_src, picture_rel=meta["picture"])

    os.makedirs(base_out, exist_ok=True)
    stage_dir = os.path.join(base_out, ".xr_pub_stage_%s_%d" % (fid, os.getpid()))
    if os.path.exists(stage_dir):
        shutil.rmtree(stage_dir, ignore_errors=True)
    os.makedirs(stage_dir, exist_ok=True)

    try:
        # 1. 复制文件并按扩展名规则在导出副本上修正 UTF-8 BOM
        for item in scan["included"]:
            src = item["abs"]
            rel = item["rel"]
            dst = os.path.join(stage_dir, rel.replace("/", os.sep))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            act = item["bom_action"]
            if act == "add_bom":
                raw = io.open(src, "rb").read()
                if not raw.startswith(_UTF8_BOM):
                    raw = _UTF8_BOM + raw
                _atomic_write(dst, raw)
            elif act == "strip_bom":
                raw = io.open(src, "rb").read()
                if raw.startswith(_UTF8_BOM):
                    raw = raw[3:]
                _atomic_write(dst, raw)
            else:
                shutil.copy2(src, dst)

        # 2. 确保 thumbnail.png（或 picture 目标）存在
        generated_thumb = False
        pic_rel = (meta.get("picture") or "thumbnail.png").replace("\\", "/").lstrip("./")
        pic_dst = os.path.join(stage_dir, pic_rel.replace("/", os.sep))
        if not os.path.isfile(pic_dst) or os.path.getsize(pic_dst) <= 0:
            if pic_rel.lower() != "thumbnail.png":
                meta["picture"] = "thumbnail.png"
            _write_placeholder_thumbnail(stage_dir)
            generated_thumb = True

        # 3. 写出规范化 descriptor.mod（UTF-8 无 BOM）
        desc_lines = _render_descriptor_lines(meta)
        desc_bytes = ("\r\n".join(desc_lines) + "\r\n").encode("utf-8")
        _atomic_write(os.path.join(stage_dir, "descriptor.mod"), desc_bytes)

        # 4. 校验导出暂存目录
        ver = _verify_exported_tree(stage_dir, picture_rel=meta["picture"])
        if not ver["ok"]:
            return {
                "ok": False,
                "msg": "导出校验未通过：" + "；".join(ver["problems"]),
                "verification": ver,
            }

        # 5. 替换目标导出目录
        if os.path.exists(target_dir):
            shutil.rmtree(target_dir)
        os.replace(stage_dir, target_dir)

        # 6. 可选注册到官方启动器（写入 <docs_dir>/mod/<fid>.mod，UTF-8 无 BOM）
        launcher_mod_path = ""
        if register_launcher:
            mod_home_dir = os.path.join(dd, "mod")
            os.makedirs(mod_home_dir, exist_ok=True)
            launcher_mod_path = os.path.join(mod_home_dir, fid + ".mod")
            l_lines = list(desc_lines) + ['path="%s"' % target_dir.replace("\\", "/")]
            _atomic_write(launcher_mod_path, ("\r\n".join(l_lines) + "\r\n").encode("utf-8"))

        # 7. 可选同时产出 .zip 包
        zip_path = ""
        if also_zip:
            ts = time.strftime("%Y%m%d_%H%M%S")
            zip_path = os.path.join(base_out, "%s_%s.zip" % (fid, ts))
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for cur, _dirs, files in os.walk(target_dir):
                    for fn in sorted(files):
                        fp = os.path.join(cur, fn)
                        rel = os.path.relpath(fp, target_dir).replace("\\", "/")
                        zf.write(fp, rel)

        return {
            "ok": True,
            "msg": "打包发布导出成功（%d 个文件，已剔除 %d 个备份/缓存项）"
                   % (len(scan["included"]) + 1 + (1 if generated_thumb else 0),
                      sum(x["count"] for x in scan["excluded"])),
            "export_dir": target_dir,
            "folder_id": fid,
            "launcher_mod": launcher_mod_path,
            "zip_path": zip_path,
            "meta": meta,
            "dep_checks": dep_checks,
            "included_count": len(scan["included"]),
            "excluded_count": sum(x["count"] for x in scan["excluded"]),
            "excluded_files": scan["excluded"],
            "bom_add": scan["bom_add"],
            "bom_strip": scan["bom_strip"],
            "brace_warns": scan["brace_warns"],
            "generated_thumbnail": generated_thumb,
            "verification": ver,
        }
    except Exception as e:
        return {"ok": False, "msg": "导出失败：%s" % e}
    finally:
        if os.path.exists(stage_dir):
            shutil.rmtree(stage_dir, ignore_errors=True)
