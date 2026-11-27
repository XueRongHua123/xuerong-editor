# -*- coding: utf-8 -*-
"""脱敏诊断包构建模块（8-3：出错时自助导出诊断信息）。

严格遵守边界与脱敏要求：
  · 不读取任何 mod 脚本正文或 ai_config.json；
  · scrub_sensitive_text() 清除系统用户名、用户主目录、常见路径用户名、
    Bearer / sk- / password 等凭据；
  · 绝不 import focus_editor 或 xuerong.api。
"""
import getpass
import io
import json
import os
import platform
import re
import subprocess
import sys
import time
import zipfile

from xuerong import state
from xuerong.core import paths
from xuerong.model.diagnose import diagnose


def _collect_user_names():
    """收集当前系统可能暴露本机身份的用户名。"""
    names = []
    for cand in (
        _safe_getuser(),
        os.environ.get("USERNAME", ""),
        os.environ.get("USER", ""),
        os.path.basename(os.path.expanduser("~").rstrip("\\/")),
    ):
        c = (cand or "").strip()
        if c and c not in names:
            names.append(c)
    names.sort(key=len, reverse=True)
    return names


def _safe_getuser():
    try:
        return getpass.getuser() or ""
    except Exception:
        return ""


def _collect_home_dirs():
    """收集当前用户主目录及常见斜杠变体。"""
    raw = []
    for cand in (
        os.path.expanduser("~"),
        os.environ.get("USERPROFILE", ""),
        os.environ.get("HOME", ""),
    ):
        c = (cand or "").strip().rstrip("\\/")
        if not c or c == "~":
            continue
        for v in (c, os.path.abspath(c), c.replace("\\", "/"), c.replace("/", "\\")):
            v = v.rstrip("\\/")
            # 排除盘符根（如 C:）和根目录 /
            if len(v) >= 4 and v not in raw:
                raw.append(v)
    raw.sort(key=len, reverse=True)
    return raw


def scrub_sensitive_text(text):
    """对任意文本执行严格脱敏：清除凭据、用户目录路径及系统用户名。"""
    if text is None:
        return ""
    s = str(text)
    if not s:
        return ""

    # 1. 凭据先脱敏，避免 token 中恰好包含用户名片段导致部分替换
    s = re.sub(r'(?i)\bBearer\s+[^\s"\',}\]]+', "<REDACTED>", s)
    s = re.sub(r'sk-[A-Za-z0-9_-]{12,}', "<REDACTED>", s)
    s = re.sub(
        r'(?i)\bpassword\s*[:=]\s*(?:"[^"]*"|\'[^\']*\'|[^\s,;}\]]+)',
        "<REDACTED>",
        s,
    )

    # 2. 路径中的用户名段统一替换（大小写不敏感）
    s = re.sub(
        r'([A-Za-z]:[\\/]+Users[\\/]+)([^\\/\s:;\'"<>|]+)',
        r"\1<USER>",
        s,
        flags=re.IGNORECASE,
    )
    s = re.sub(
        r'(/(?:Users|home)/)([^/\s:;\'"<>|]+)',
        r"\1<USER>",
        s,
        flags=re.IGNORECASE,
    )

    # 3. 兜底非标准位置的用户主目录
    for home in _collect_home_dirs():
        s = re.sub(re.escape(home), "<USER>", s, flags=re.IGNORECASE)

    # 4. 当前系统用户名（避免破坏已写入的 <USER> / <REDACTED>）
    for uname in _collect_user_names():
        low = uname.lower()
        if low in ("user", "redacted", "<user>", "<redacted>"):
            continue
        if len(uname) < 2:
            continue
        if low in ("root", "admin", "administrator", "system"):
            pat = r'(?<![A-Za-z0-9_<])' + re.escape(uname) + r'(?![A-Za-z0-9_>])'
        else:
            pat = re.escape(uname)
        s = re.sub(pat, "<USER>", s, flags=re.IGNORECASE)

    return s


def _scrub_obj(obj):
    """递归脱敏 dict / list / str 中的所有文本。"""
    if isinstance(obj, str):
        return scrub_sensitive_text(obj)
    if isinstance(obj, list):
        return [_scrub_obj(x) for x in obj]
    if isinstance(obj, tuple):
        return [_scrub_obj(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _scrub_obj(v) for k, v in obj.items()}
    return obj


def _read_app_version():
    """读取 _version.txt，不存在时回退 git tag 或 'dev'。"""
    here = paths.app_dir()
    for base in (getattr(sys, "_MEIPASS", ""), here, os.getcwd()):
        if not base:
            continue
        vp = os.path.join(base, "_version.txt")
        try:
            if os.path.isfile(vp):
                with io.open(vp, encoding="utf-8", errors="replace") as f:
                    v = f.read().strip()
                if v:
                    return v
        except Exception:
            pass
    try:
        res = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0"],
            cwd=here,
            capture_output=True,
            text=True,
            timeout=2,
        )
        tag = (res.stdout or "").strip().lstrip("v")
        if tag:
            return tag
    except Exception:
        pass
    return "dev"


def _active_layers_summary():
    """生成脱敏后的活跃层清单，每项仅含 name/readonly/reason/masked_path。"""
    roots = state.roots() or []
    if not roots:
        return []
    game_dir = state.game() or ""
    game_abs = os.path.normcase(os.path.abspath(game_dir)) if game_dir else ""
    opts = state.options() or {}

    manual = set()
    for r in roots:
        try:
            manual.add(os.path.abspath(r))
        except Exception:
            pass

    dep_set = set()
    if opts.get("follow_deps", True):
        for r in roots:
            try:
                dep_set |= {os.path.abspath(x) for x in paths._mod_dep_chain(r)[:-1]}
            except Exception:
                pass

    launch_set = set()
    if opts.get("follow_launcher", False):
        try:
            ab_root = os.path.abspath(roots[-1])
            order = [os.path.abspath(x) for x in paths._enabled_mod_order()]
            launch_set = (
                set(order[:order.index(ab_root)])
                if ab_root in order
                else set(order)
            )
        except Exception:
            launch_set = set()

    out = []
    try:
        layers = paths.mod_layers(roots[-1]) or []
    except Exception:
        layers = []
    for r in layers:
        try:
            ab = os.path.abspath(r)
        except Exception:
            continue
        if game_abs and os.path.normcase(ab) == game_abs:
            reason = "game"
        elif ab in manual:
            reason = "manual"
        elif ab in dep_set:
            reason = "dep"
        elif ab in launch_set:
            reason = "launcher"
        else:
            reason = "auto"
        out.append({
            "name": scrub_sensitive_text(paths._mod_display_name(ab)),
            "readonly": bool(paths.is_readonly_mod(ab)),
            "reason": reason,
            "masked_path": scrub_sensitive_text(ab),
        })
    return out


def _build_summary():
    raw_game = state.game() or ""
    has_dir = bool(raw_game and os.path.isdir(raw_game))
    has_exe = bool(has_dir and os.path.isfile(os.path.join(raw_game, "hoi4.exe")))
    has_nf = bool(has_dir and os.path.isdir(os.path.join(raw_game, "common", "national_focus")))
    opts = {}
    for k, v in (state.options() or {}).items():
        opts[k] = scrub_sensitive_text(v) if isinstance(v, str) else v

    return {
        "app_version": _read_app_version(),
        "frozen": bool(getattr(sys, "frozen", False)),
        "os": scrub_sensitive_text(platform.platform()),
        "python": platform.python_version(),
        "game_dir": {
            "masked_path": scrub_sensitive_text(raw_game),
            "exists": has_dir,
            "game_ok": has_exe,
            "has_national_focus": has_nf,
            "game_version": paths.detect_game_version(raw_game),
        },
        "options": opts,
        "layers": _active_layers_summary(),
    }


def _build_layer_chain():
    roots = state.roots() or []
    if not roots:
        return {
            "total_files": 0,
            "interacted_count": 0,
            "overridden_count": 0,
            "blocked_count": 0,
            "layers": [],
            "replace_rules": [],
            "files": [],
        }
    try:
        raw_layers = paths.mod_layers(roots[-1]) or []
    except Exception:
        raw_layers = list(roots)

    if len(raw_layers) < 2:
        return {
            "total_files": 0,
            "interacted_count": 0,
            "overridden_count": 0,
            "blocked_count": 0,
            "layers": [],
            "replace_rules": [],
            "files": [],
        }

    try:
        res = paths.analyze_layer_chain(layers=raw_layers, kind="interacted", limit=60)
    except Exception as e:
        return {
            "error": scrub_sensitive_text(str(e)),
            "total_files": 0,
            "interacted_count": 0,
            "overridden_count": 0,
            "blocked_count": 0,
            "layers": [],
            "replace_rules": [],
            "files": [],
        }

    layers_out = []
    for lm in (res.get("layers") or []):
        layers_out.append({
            "order": lm.get("order"),
            "name": scrub_sensitive_text(lm.get("name") or ""),
            "is_game": bool(lm.get("is_game") or lm.get("game") or paths.is_under_game(lm.get("path") or "")),
            "file_count": lm.get("file_count", 0),
            "override_count": lm.get("override_count", 0),
            "overridden_count": lm.get("overridden_count", 0),
            "blocked_others_count": lm.get("blocked_others_count", 0),
            "blocked_self_count": lm.get("blocked_self_count", 0),
            "replace_paths": [scrub_sensitive_text(p) for p in (lm.get("replace_paths") or [])],
        })

    rules_out = []
    for rl in (res.get("replace_rules") or []):
        rules_out.append({
            "owner_order": rl.get("owner_order"),
            "owner_name": scrub_sensitive_text(rl.get("owner_name") or ""),
            "path": scrub_sensitive_text(rl.get("path") or ""),
            "own_files": rl.get("own_files", 0),
            "blocked_total": rl.get("blocked_total", 0),
            "blocked_unique": rl.get("blocked_unique", 0),
        })

    files_out = []
    for e in (res.get("files") or [])[:60]:
        rb = e.get("replace_by")
        files_out.append({
            "rel": scrub_sensitive_text(e.get("rel") or ""),
            "status": e.get("status") or "",
            "winner_name": scrub_sensitive_text(e.get("winner_name") or ""),
            "replace_by": {
                "order": rb.get("order"),
                "name": scrub_sensitive_text(rb.get("name") or ""),
                "path": scrub_sensitive_text(rb.get("path") or ""),
            } if isinstance(rb, dict) else None,
        })

    return {
        "total_files": res.get("total_files", 0),
        "interacted_count": res.get("matched_count", 0),
        "overridden_count": res.get("overridden_count", 0),
        "blocked_count": res.get("blocked_count", 0),
        "layers": layers_out,
        "replace_rules": rules_out,
        "files": files_out,
    }


def _build_diagnose():
    try:
        res = diagnose(scope="current")
    except Exception as e:
        return {"ok": False, "msg": scrub_sensitive_text(str(e)), "findings": []}
    return _scrub_obj(res)


def _server_error_tail(max_lines=200):
    log_path = os.path.join(paths.app_dir(), "logs", "server_error.log")
    if not os.path.isfile(log_path):
        return ""
    try:
        with io.open(log_path, encoding="utf-8", errors="replace") as f:
            lines = f.read().splitlines()
        return scrub_sensitive_text("\n".join(lines[-max_lines:]))
    except Exception as e:
        return scrub_sensitive_text("读取 logs/server_error.log 失败: %s" % e)


def build_support_bundle():
    """构建脱敏后的诊断包 JSON 预览对象。"""
    return {
        "ok": True,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "summary": _build_summary(),
        "layer_chain": _build_layer_chain(),
        "diagnose": _build_diagnose(),
        "server_error_tail": _server_error_tail(200),
    }


def support_bundle_zip():
    """构建脱敏诊断包 zip 字节流（含 5 个文件，不含 mod 正文与凭据）。"""
    bundle = build_support_bundle()
    readme = "\n".join([
        "雪绒编辑器（Xuerong Editor）脱敏诊断包",
        "生成时间: %s" % bundle["generated_at"],
        "",
        "隐私说明：",
        "- 已移除系统用户名、用户主目录路径及常见 API/密码凭据；",
        "- 不包含任何 mod 脚本正文或 ai_config.json。",
        "",
        "文件清单：",
        "1. README.txt            本说明文件",
        "2. summary.json          版本、系统环境、游戏目录状态、选项与活跃层摘要",
        "3. layer_chain.json      叠加链统计概览与最多 60 条交互文件及 replace_path 声明",
        "4. diagnose.json         当前 mod 诊断条目（scope=current，已脱敏）",
        "5. server_error_tail.txt logs/server_error.log 最近 200 行（已脱敏）",
        "",
    ])
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("README.txt", readme.encode("utf-8"))
        zf.writestr(
            "summary.json",
            json.dumps(bundle["summary"], ensure_ascii=False, indent=2).encode("utf-8"),
        )
        zf.writestr(
            "layer_chain.json",
            json.dumps(bundle["layer_chain"], ensure_ascii=False, indent=2).encode("utf-8"),
        )
        zf.writestr(
            "diagnose.json",
            json.dumps(bundle["diagnose"], ensure_ascii=False, indent=2).encode("utf-8"),
        )
        zf.writestr(
            "server_error_tail.txt",
            (bundle["server_error_tail"] or "").encode("utf-8"),
        )
    return buf.getvalue()
