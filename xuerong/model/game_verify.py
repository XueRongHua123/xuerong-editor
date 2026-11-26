# -*- coding: utf-8 -*-
"""7-4 一键进游戏校验（含 6-3 L3 跑道核心、dlc_load.json 备份与异常退出恢复）。

核心能力：
  1. 自动定位 HOI4 游戏目录（hoi4.exe）与 Paradox 用户目录（dlc_load.json），缺一给出明确原因；
  2. 支持首次修改 `dlc_load.json` 前的显式用户确认持久化；
  3. 修改 `dlc_load.json` 前先行落盘 `cache/dlc_load_backup.json`（含临时生成的 `.mod` 路径），
     正常结束时在 `finally` 还原；若发生崩溃或强杀，编辑器下次启动立刻先调用 `recover_pending_dlc_load()` 还原；
  4. 对比基线与目标 `error.log`（去时间戳差分），并精准映射新增报错到 submod 文件路径与具体行号。
"""
import base64
import collections
import hashlib
import io
import json
import os
import re
import subprocess
import tempfile
import threading
import time

from xuerong import state
from xuerong.core.paths import (_mod_descriptor, _resolve_mod_path, _steam_libraries,
                                app_dir, is_under_game, mod_layers, pdx_user_dir)
from xuerong.core.text import _atomic_write, _read_text

NO_WINDOW = 0x08000000
_TS_RE = re.compile(r"^\[\d{2}:\d{2}:\d{2}\]")

_LOCK = threading.Lock()
_CANCEL_EV = threading.Event()
_VERIFY_STATE = {
    "running": False,
    "phase": "idle",       # idle / baseline / target / done / error / cancelled
    "pct": 0,
    "msg": "",
    "recovered_msg": "",
    "result": None,
}


def _cache_dir():
    return os.path.join(app_dir(), "cache")


def _backup_file():
    return os.path.join(_cache_dir(), "dlc_load_backup.json")


def _state_file():
    return os.path.join(_cache_dir(), "game_verify_state.json")


def _read_verify_store():
    p = _state_file()
    if os.path.isfile(p):
        try:
            with io.open(p, encoding="utf-8", errors="replace") as _fh:
                return json.loads(_fh.read())
        except Exception:
            pass
    return {}


def _write_verify_store(obj):
    os.makedirs(_cache_dir(), exist_ok=True)
    _atomic_write(_state_file(), json.dumps(obj, ensure_ascii=False, indent=1).encode("utf-8"))


def is_verify_confirmed():
    return bool(_read_verify_store().get("confirmed"))


def set_verify_confirmed(val=True):
    st = _read_verify_store()
    st["confirmed"] = bool(val)
    _write_verify_store(st)


def find_game_dir(preferred=""):
    """探测含 hoi4.exe 的游戏根目录，优先 preferred / state.game()，再扫 Steam 库。"""
    cands = []
    if preferred:
        cands.append(preferred)
    sg = state.game()
    if sg and sg not in cands:
        cands.append(sg)
    for lib in _steam_libraries():
        c = os.path.join(lib, "steamapps", "common", "Hearts of Iron IV")
        if c not in cands:
            cands.append(c)
    for c in cands:
        if c and os.path.isfile(os.path.join(c, "hoi4.exe")):
            return os.path.abspath(c)
    return ""


def _hoi4_running():
    try:
        out = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq hoi4.exe"],
            capture_output=True, text=True, errors="replace", creationflags=NO_WINDOW,
        ).stdout
        return "hoi4.exe" in (out or "").lower()
    except Exception:
        return False


def _kill_and_wait(timeout=20.0):
    try:
        subprocess.run(
            ["taskkill", "/F", "/IM", "hoi4.exe"],
            capture_output=True, creationflags=NO_WINDOW,
        )
    except Exception:
        pass
    t0 = time.time()
    while time.time() - t0 < timeout:
        if not _hoi4_running():
            time.sleep(0.5)
            return True
        time.sleep(0.4)
    return False


def _crash_dirs(docs_dir):
    d = os.path.join(docs_dir, "crashes")
    return set(os.listdir(d)) if os.path.isdir(d) else set()


def _exception_head(docs_dir, cname):
    p = os.path.join(docs_dir, "crashes", cname, "exception.txt")
    if not os.path.isfile(p):
        return ""
    with io.open(p, encoding="utf-8", errors="replace") as _fh:
        for ln in _fh:
            if "Unhandled Exception" in ln:
                return ln.strip()
    return ""


def normalize_error_line(line):
    return _TS_RE.sub("", line or "").strip()


def diff_error_logs(base_lines, target_lines):
    base_norm = [normalize_error_line(x) for x in base_lines if normalize_error_line(x)]
    base_cnt = collections.Counter(base_norm)
    added = []
    seen = collections.Counter()
    for raw in target_lines:
        norm = normalize_error_line(raw)
        if not norm:
            continue
        seen[norm] += 1
        if seen[norm] > base_cnt[norm]:
            added.append({"norm": norm, "raw": raw.strip()})
    return added


def _read_line_excerpt(fp, line_no):
    if not fp or not os.path.isfile(fp):
        return ""
    try:
        lines = _read_text(fp).splitlines()
        if line_no and 1 <= line_no <= len(lines):
            lo = max(0, line_no - 2)
            hi = min(len(lines), line_no + 1)
            return "\n".join("%d: %s" % (i + 1, lines[i]) for i in range(lo, hi))
    except Exception:
        pass
    return ""


def _extract_probe_tokens(norm):
    """当报错行未直接写出文件路径时（如 Duplicate idea / Unknown modifier），抽出可能对象 ID。"""
    toks = []
    pats = (
        r"Duplicate idea\.\s+([A-Za-z0-9_.\-]+)",
        r"Unknown\s+[A-Za-z_ ]+:\s*([A-Za-z0-9_.\-]+)",
        r"Focus with id\s+([A-Za-z0-9_.\-]+)",
        r"'([A-Za-z0-9_.\-]{3,})'",
        r'"([A-Za-z0-9_.\-]{3,})"',
    )
    for pat in pats:
        for m in re.finditer(pat, norm):
            t = m.group(1).strip()
            if t and not t.lower().endswith((".txt", ".yml", ".dds", ".gui", ".gfx")) and t not in toks:
                toks.append(t)
    return toks


def map_lines_to_files(added_items, mod_dirs):
    """把 error.log 新增行精准映射到被测 mod 目录下的具体文件、行号与代码上下文。"""
    if not added_items:
        return added_items
    rel_map = {}
    ordered_mods = [os.path.abspath(d) for d in (mod_dirs or ()) if d and os.path.isdir(d)]
    text_files = []  # 按从顶层(最子)到基座(最父)顺序收集，用于无路径报错的反查
    need_token_scan = False
    for md in reversed(ordered_mods):
        lname = os.path.basename(md.rstrip("\\/")) or md
        for cur, dirs, fs in os.walk(md):
            dirs[:] = sorted(d for d in dirs if not d.startswith("."))
            for fn in sorted(fs):
                fp = os.path.join(cur, fn)
                rel = os.path.relpath(fp, md).replace("\\", "/")
                rel_map.setdefault(rel.lower(), []).append((lname, fp, rel))
                if fn.lower().endswith((".txt", ".yml", ".gfx", ".gui")):
                    text_files.append((lname, fp, rel))
    del need_token_scan

    for it in added_items:
        norm = it["norm"]
        m_line = re.search(r"(?:near\s+line|line)\s*[:=]?\s*(\d+)", norm, re.I)
        line_no = int(m_line.group(1)) if m_line else None

        locations = []
        matched_paths = []
        seen_fp = set()

        def _add_loc(lname, fp, rel, lno):
            fk = os.path.normcase(fp)
            if fk in seen_fp:
                return
            seen_fp.add(fk)
            matched_paths.append(fp)
            locations.append({
                "layer": lname,
                "file": rel,
                "path": fp,
                "line": lno,
                "excerpt": _read_line_excerpt(fp, lno),
            })

        # 1) 显式文件路径匹配（如 in file: "history/states/1-France.txt" 或常规 rel）
        file_cands = []
        for m in re.finditer(r'in\s+file:\s*"([^"]+)"', norm, re.I):
            file_cands.append(m.group(1))
        for m in re.finditer(r"([A-Za-z0-9_./\\-]+\.(?:txt|yml|gui|gfx|asset|csv|bmp))", norm):
            file_cands.append(m.group(1))

        for raw_f in file_cands:
            cand = raw_f.replace("\\", "/").lstrip("./").lower()
            if cand in rel_map:
                for lname, fp, rel in rel_map[cand]:
                    _add_loc(lname, fp, rel, line_no)
            else:
                for k, tuples in rel_map.items():
                    if k.endswith("/" + cand) or cand.endswith("/" + k):
                        for lname, fp, rel in tuples:
                            _add_loc(lname, fp, rel, line_no)

        # 2) 未写文件路径时，按对象/标识符反查被测 mod 文本行号
        if not locations:
            toks = _extract_probe_tokens(norm)
            for tok in toks:
                pat_tok = re.compile(r"(?<![A-Za-z0-9_])%s(?![A-Za-z0-9_])" % re.escape(tok))
                for lname, fp, rel in text_files:
                    try:
                        lines = _read_text(fp).splitlines()
                    except Exception:
                        continue
                    for idx_l, txt_l in enumerate(lines, 1):
                        if pat_tok.search(txt_l):
                            _add_loc(lname, fp, rel, idx_l)
                            break
                    if len(locations) >= 3:
                        break
                if locations:
                    break

        it["line"] = line_no if locations and locations[0]["line"] == line_no else (locations[0]["line"] if locations else line_no)
        it["matched_files"] = matched_paths
        it["locations"] = locations
    return added_items


def recover_pending_dlc_load(docs_dir=""):
    """检查是否存在未清理的 `dlc_load_backup.json`；若 HOI4 未在运行则恢复原文件并清理临时 .mod。"""
    bk = _backup_file()
    if not os.path.isfile(bk):
        return {"recovered": False, "msg": ""}
    try:
        with io.open(bk, encoding="utf-8", errors="replace") as _fh:
            meta = json.loads(_fh.read())
    except Exception:
        try:
            os.remove(bk)
        except Exception:
            pass
        return {"recovered": False, "msg": ""}

    dlc_path = meta.get("dlc_path") or (os.path.join(docs_dir or pdx_user_dir(), "dlc_load.json"))
    if _hoi4_running():
        return {
            "recovered": False,
            "hoi4_running": True,
            "msg": "检测到上次进游戏校验尚未收尾且 hoi4.exe 仍在运行；关闭游戏后将自动恢复 dlc_load.json。",
        }

    orig_b64 = meta.get("orig_b64") or ""
    try:
        if orig_b64 and os.path.isdir(os.path.dirname(dlc_path)):
            _atomic_write(dlc_path, base64.b64decode(orig_b64.encode("ascii")))
        for tm in (meta.get("temp_mods") or []):
            if tm and os.path.isfile(tm):
                try:
                    os.remove(tm)
                except Exception:
                    pass
        for jc in (meta.get("temp_junctions") or []):
            _remove_junction(jc)
        os.remove(bk)
        msg = "检测到上次进游戏校验意外中断，已自动恢复 dlc_load.json 并清理临时文件。"
        with _LOCK:
            _VERIFY_STATE["recovered_msg"] = msg
        return {"recovered": True, "msg": msg}
    except Exception as e:
        return {"recovered": False, "msg": "自动恢复 dlc_load.json 失败: %s" % e}


def _remove_junction(junc):
    """仅移除 NTFS 目录联接点本身（绝不递归删除原目录内容）。"""
    if not junc:
        return
    try:
        if os.path.islink(junc) or os.path.isdir(junc):
            try:
                os.rmdir(junc)
            except Exception:
                subprocess.run(["cmd", "/c", "rmdir", junc], capture_output=True, creationflags=NO_WINDOW)
        pdir = os.path.dirname(junc)
        if pdir and os.path.basename(pdir).startswith("xr_gvj_") and os.path.isdir(pdir):
            try:
                os.rmdir(pdir)
            except Exception:
                pass
    except Exception:
        pass


def _write_backup(dlc_path, orig_bytes, temp_mods, temp_junctions=()):
    os.makedirs(_cache_dir(), exist_ok=True)
    payload = {
        "dlc_path": dlc_path,
        "orig_b64": base64.b64encode(orig_bytes).decode("ascii"),
        "temp_mods": list(temp_mods or []),
        "temp_junctions": list(temp_junctions or []),
        "saved_at": time.time(),
    }
    _atomic_write(_backup_file(), json.dumps(payload, ensure_ascii=False).encode("utf-8"))


def _remove_backup_and_temps(temp_mods, temp_junctions=()):
    for tm in (temp_mods or []):
        if tm and os.path.isfile(tm):
            try:
                os.remove(tm)
            except Exception:
                pass
    for jc in (temp_junctions or []):
        _remove_junction(jc)
    bk = _backup_file()
    if os.path.isfile(bk):
        try:
            os.remove(bk)
        except Exception:
            pass


def run_once(game_dir, docs_dir, enabled_mods, timeout=140.0, post_ready_wait=5.0,
             temp_mods=(), temp_junctions=(), cancel_ev=None, progress_cb=None, keep_backup=False):
    """修改 dlc_load.json 启动一次 HOI4 到主菜单，采集 error.log 后严格还原现场。"""
    dlc_path = os.path.join(docs_dir, "dlc_load.json")
    err_path = os.path.join(docs_dir, "logs", "error.log")
    game_log_path = os.path.join(docs_dir, "logs", "game.log")

    with io.open(dlc_path, "rb") as _fh:
        orig_dlc = _fh.read()
    _write_backup(dlc_path, orig_dlc, temp_mods, temp_junctions)
    try:
        cfg = json.loads(orig_dlc.decode("utf-8"))
        cfg["enabled_mods"] = list(enabled_mods)
        _atomic_write(dlc_path, json.dumps(cfg, indent=2).encode("utf-8"))

        for lp in (err_path, game_log_path):
            if os.path.exists(lp):
                try:
                    os.remove(lp)
                except Exception:
                    pass

        before_crashes = _crash_dirs(docs_dir)
        t0 = time.time()
        try:
            subprocess.Popen([os.path.join(game_dir, "hoi4.exe")], cwd=game_dir)
        except Exception as e:
            return {"status": "LAUNCH_FAILED", "elapsed": 0.0,
                    "msg": "无法启动 hoi4.exe：%s" % e, "error_lines": [], "new_crashes": []}

        started = False
        for _ in range(60):
            if cancel_ev and cancel_ev.is_set():
                break
            if _hoi4_running():
                started = True
                break
            time.sleep(0.5)
        if cancel_ev and cancel_ev.is_set():
            _kill_and_wait()
            return {"status": "CANCELLED", "elapsed": round(time.time() - t0, 1),
                    "msg": "校验已取消", "error_lines": [], "new_crashes": []}
        if not started:
            return {"status": "LAUNCH_FAILED", "elapsed": round(time.time() - t0, 1),
                    "msg": "hoi4.exe 进程在 30 秒内未启动（请检查 Steam 或防病毒拦截）",
                    "error_lines": [], "new_crashes": []}

        ready = False
        died_early = False
        while time.time() - t0 < timeout:
            if cancel_ev and cancel_ev.is_set():
                _kill_and_wait()
                return {"status": "CANCELLED", "elapsed": round(time.time() - t0, 1),
                        "msg": "校验已取消", "error_lines": [], "new_crashes": []}
            if not _hoi4_running():
                died_early = True
                break
            if os.path.isfile(game_log_path):
                with io.open(game_log_path, encoding="utf-8", errors="replace") as _fh:
                    txt = _fh.read()
                if "Executing History" in txt:
                    ready = True
                    break
            if progress_cb:
                progress_cb(round(time.time() - t0, 1))
            time.sleep(1.0)

        if ready and not died_early and post_ready_wait > 0:
            time.sleep(post_ready_wait)

        new_crashes = sorted(_crash_dirs(docs_dir) - before_crashes)
        alive_at_end = _hoi4_running()
        _kill_and_wait()

        if os.path.isfile(err_path):
            with io.open(err_path, encoding="utf-8", errors="replace") as _fh:
                error_lines = _fh.read().splitlines()
        else:
            error_lines = []
        if os.path.isfile(game_log_path):
            with io.open(game_log_path, encoding="utf-8", errors="replace") as _fh:
                game_tail = [x for x in _fh.read().splitlines() if x.strip()][-10:]
        else:
            game_tail = []
        if new_crashes or not alive_at_end:
            status = "DIED"
        elif ready:
            status = "MENU_OK"
        else:
            status = "TIMEOUT"

        crash_info = [{"dir": c, "head": _exception_head(docs_dir, c)} for c in new_crashes]
        return {
            "status": status,
            "elapsed": round(time.time() - t0, 1),
            "error_lines": error_lines,
            "game_tail": game_tail,
            "new_crashes": crash_info,
        }
    finally:
        _kill_and_wait()
        time.sleep(0.3)
        try:
            _atomic_write(dlc_path, orig_dlc)
        except Exception:
            pass
        if not keep_backup:
            _remove_backup_and_temps(temp_mods, temp_junctions)


def _create_ascii_junction(target_dir, idx):
    """Windows 下为含非 ASCII（如中文）路径的 mod 目录建纯 ASCII 目录联接，供 HOI4 读取。"""
    try:
        if target_dir.isascii():
            return target_dir, ""
    except Exception:
        return target_dir, ""
    tmp_root = tempfile.gettempdir()
    base = None
    if tmp_root and tmp_root.isascii():
        base = tempfile.mkdtemp(prefix="xr_gvj_")
    else:
        drv = os.path.splitdrive(target_dir)[0] or "C:"
        cand_base = os.path.join(drv + os.sep, "_xr_gvj_tmp")
        try:
            os.makedirs(cand_base, exist_ok=True)
            base = tempfile.mkdtemp(prefix="xr_gvj_", dir=cand_base)
        except Exception:
            base = None
    if not base:
        return target_dir, ""
    junc = os.path.join(base, "m_%d" % idx)
    try:
        r = subprocess.run(
            ["cmd", "/c", "mklink", "/J", junc, target_dir],
            capture_output=True, creationflags=NO_WINDOW,
        )
        if r.returncode == 0 and os.path.isdir(junc):
            return junc, junc
    except Exception:
        pass
    try:
        os.rmdir(base)
    except Exception:
        pass
    return target_dir, ""


def _resolve_chain_to_enabled_mods(mod_dirs, docs_dir):
    """将叠加链中非原版目录解析为 `mod/<name>.mod` 条目，缺失启动器映射时生成无冲突临时 `.mod`。"""
    mod_home_dir = os.path.join(docs_dir, "mod")
    os.makedirs(mod_home_dir, exist_ok=True)
    existing_by_path = {}
    existing_names = set()
    for fn in sorted(os.listdir(mod_home_dir)):
        if not fn.lower().endswith(".mod"):
            continue
        fp = os.path.join(mod_home_dir, fn)
        try:
            with io.open(fp, encoding="utf-8-sig", errors="replace") as _fh:
                txt = _fh.read()
        except Exception:
            continue
        mn = re.search(r'(?m)^\s*name\s*=\s*"([^"]*)"', txt)
        if mn and mn.group(1):
            existing_names.add(mn.group(1))
        m = re.search(r'(?m)^\s*path\s*=\s*"([^"]+)"', txt)
        if m:
            rp = _resolve_mod_path(m.group(1), docs_dir)
            if rp:
                existing_by_path[os.path.normcase(os.path.abspath(rp))] = "mod/" + fn

    enabled = []
    temp_mods = []
    temp_junctions = []
    for idx, md in enumerate(mod_dirs):
        ab = os.path.abspath(md)
        key = os.path.normcase(ab)
        if key in existing_by_path:
            enabled.append(existing_by_path[key])
            continue
        temp_name = "zz_xr_verify_%d_%d.mod" % (os.getpid(), idx)
        temp_fp = os.path.join(mod_home_dir, temp_name)
        desc_fp = os.path.join(ab, "descriptor.mod")
        lines = []
        orig_name = ""
        if os.path.isfile(desc_fp):
            with io.open(desc_fp, encoding="utf-8-sig", errors="replace") as _fh:
                raw = _fh.read()
            for ln in raw.splitlines():
                if re.match(r"^\s*(?:path|remote_file_id)\s*=", ln):
                    continue
                m_nm = re.match(r'^\s*name\s*=\s*"([^"]*)"', ln)
                if m_nm:
                    orig_name = m_nm.group(1)
                    continue
                lines.append(ln)
        else:
            lines = ['version="0.1.0"']
        use_name = orig_name if (orig_name and orig_name not in existing_names) else ("XR Verify Temp %d_%d" % (os.getpid(), idx))
        existing_names.add(use_name)
        lines.append('name="%s"' % use_name.replace('"', '\\"'))
        mount_dir, junc = _create_ascii_junction(ab, idx)
        if junc:
            temp_junctions.append(junc)
        lines.append('path="%s"' % mount_dir.replace("\\", "/"))
        with io.open(temp_fp, "w", encoding="utf-8", newline="") as _fh:
            _fh.write("\r\n".join(lines) + "\r\n")
        temp_mods.append(temp_fp)
        enabled.append("mod/" + temp_name)
    return enabled, temp_mods, temp_junctions


def check_environment(game_dir="", docs_dir=""):
    """预检当前机器是否满足进游戏校验，明确给出找不到游戏或配置的原因。"""
    rec = recover_pending_dlc_load(docs_dir)
    gd = find_game_dir(game_dir)
    dd = docs_dir or pdx_user_dir()
    if not gd:
        return {
            "ok": False,
            "reason": "找不到 HOI4 游戏目录（未检测到 hoi4.exe）。请通过 --game 指定游戏目录或确认 Steam 库安装正常。",
            "game_dir": "",
            "docs_dir": dd,
            "hoi4_running": False,
            "recovered_msg": rec.get("msg") or "",
        }
    dlc = os.path.join(dd, "dlc_load.json")
    if not os.path.isfile(dlc):
        return {
            "ok": False,
            "reason": "找不到 Paradox 启动器配置文件 dlc_load.json（预期路径：%s）。请先至少打开一次 HOI4 启动器。" % dlc,
            "game_dir": gd,
            "docs_dir": dd,
            "hoi4_running": False,
            "recovered_msg": rec.get("msg") or "",
        }
    running = _hoi4_running()
    if running:
        return {
            "ok": False,
            "reason": "检测到 hoi4.exe 正在运行，请先关闭当前游戏后再运行进游戏检查。",
            "game_dir": gd,
            "docs_dir": dd,
            "hoi4_running": True,
            "recovered_msg": rec.get("msg") or "",
        }
    return {
        "ok": True,
        "reason": "",
        "game_dir": gd,
        "docs_dir": dd,
        "hoi4_running": False,
        "recovered_msg": rec.get("msg") or "",
    }


def _baseline_cache_path(game_dir, base_dirs):
    sig = json.dumps([game_dir, [os.path.abspath(d) for d in base_dirs]], ensure_ascii=False)
    h = hashlib.sha1(sig.encode("utf-8")).hexdigest()[:12]
    return os.path.join(_cache_dir(), "l3_baseline_%s.json" % h)


def get_verify_status(layers=None, game_dir="", docs_dir=""):
    """返回 7-4 面板所需全量状态：环境预检、确认状态、运行进度、上次结果与恢复消息。"""
    env = check_environment(game_dir=game_dir, docs_dir=docs_dir)
    store = _read_verify_store()
    chain = layers if layers is not None else (mod_layers(None) or [])
    gd_key = os.path.normcase(os.path.abspath(env["game_dir"])) if env.get("game_dir") else ""
    non_game = [
        os.path.abspath(r) for r in chain
        if r and not is_under_game(r) and os.path.normcase(os.path.abspath(r)) != gd_key
    ]
    with _LOCK:
        st = dict(_VERIFY_STATE)
    if st.get("result") is None and store.get("last_result"):
        st["result"] = store["last_result"]
    if not st.get("recovered_msg") and env.get("recovered_msg"):
        st["recovered_msg"] = env["recovered_msg"]
    st.update({
        "confirmed": bool(store.get("confirmed")),
        "env_ok": env["ok"],
        "env_reason": env["reason"],
        "game_dir": env["game_dir"],
        "docs_dir": env["docs_dir"],
        "hoi4_running": env["hoi4_running"],
        "mod_dirs": non_game,
    })
    return st


def _run_verify_worker(mod_dirs, game_dir, docs_dir, baseline_mode, reuse_baseline, runner):
    temp_mods = []
    temp_junctions = []
    try:
        all_enabled, temp_mods, temp_junctions = _resolve_chain_to_enabled_mods(mod_dirs, docs_dir)
        # 基线层：parents 模式对比除去最顶层 submod 的其余前置层；vanilla 模式直接对比纯原版
        if baseline_mode == "vanilla" or len(mod_dirs) <= 1:
            base_dirs = []
            base_enabled = []
        else:
            base_dirs = mod_dirs[:-1]
            base_enabled = all_enabled[:-1]

        b_cache_fp = _baseline_cache_path(game_dir, base_dirs)
        base_lines = None
        base_res = None
        if reuse_baseline and os.path.isfile(b_cache_fp):
            try:
                with io.open(b_cache_fp, encoding="utf-8", errors="replace") as _fh:
                    cj = json.loads(_fh.read())
                if isinstance(cj.get("error_lines"), list):
                    base_lines = cj["error_lines"]
                    base_res = {"status": "CACHED", "elapsed": 0.0, "error_count": len(base_lines)}
            except Exception:
                base_lines = None

        if base_lines is None:
            with _LOCK:
                _VERIFY_STATE.update({"phase": "baseline", "pct": 15,
                                      "msg": "正在启动基线 HOI4（用于过滤前置错误）…"})
            br = runner(
                game_dir, docs_dir, base_enabled,
                timeout=300.0, post_ready_wait=5.0,
                temp_mods=temp_mods, temp_junctions=temp_junctions, cancel_ev=_CANCEL_EV,
                progress_cb=lambda sec: _set_prog(min(45, 15 + int(sec * 0.4)), "基线启动中（已耗时 %.0fs）…" % sec),
                keep_backup=True,
            )
            if br["status"] == "CANCELLED":
                _finish_state("cancelled", 0, "已取消进游戏校验并还原 dlc_load.json", None)
                return
            if br["status"] != "MENU_OK":
                msg = br.get("msg") or ("基线未能到达主菜单（%s）" % br["status"])
                _finish_state("error", 0, msg, {"ok": False, "status": br["status"], "msg": msg, "baseline": br, "added": []})
                return
            base_lines = br["error_lines"]
            base_res = {"status": br["status"], "elapsed": br["elapsed"], "error_count": len(base_lines)}
            os.makedirs(_cache_dir(), exist_ok=True)
            _atomic_write(b_cache_fp, json.dumps({"error_lines": base_lines, "saved_at": time.time()}).encode("utf-8"))

        with _LOCK:
            _VERIFY_STATE.update({"phase": "target", "pct": 55,
                                  "msg": "正在启动被测 submod 进主菜单…"})
        tr = runner(
            game_dir, docs_dir, all_enabled,
            timeout=300.0, post_ready_wait=5.0,
            temp_mods=temp_mods, temp_junctions=temp_junctions, cancel_ev=_CANCEL_EV,
            progress_cb=lambda sec: _set_prog(min(92, 55 + int(sec * 0.5)), "目标 mod 启动中（已耗时 %.0fs）…" % sec),
            keep_backup=True,
        )
        if tr["status"] == "CANCELLED":
            _finish_state("cancelled", 0, "已取消进游戏校验并还原 dlc_load.json", None)
            return

        focus_dirs = [mod_dirs[-1]] if mod_dirs else []
        added = map_lines_to_files(diff_error_logs(base_lines, tr.get("error_lines") or []), mod_dirs)
        passed = (tr["status"] == "MENU_OK" and len(added) == 0)
        summary_msg = (
            "主菜单就绪（%.1fs），相对基线新增 0 条报错！" % tr["elapsed"]
            if passed
            else ("游戏异常退出或超时（%s）" % tr["status"]
                  if tr["status"] != "MENU_OK"
                  else "主菜单就绪（%.1fs），检测到 %d 条新增报错" % (tr["elapsed"], len(added)))
        )
        result = {
            "ok": passed,
            "status": tr["status"],
            "msg": tr.get("msg") or summary_msg,
            "elapsed": tr["elapsed"],
            "baseline": base_res,
            "baseline_mode": baseline_mode,
            "target_error_count": len(tr.get("error_lines") or []),
            "new_crashes": tr.get("new_crashes") or [],
            "added_count": len(added),
            "added": added,
            "checked_dirs": focus_dirs,
        }
        st = _read_verify_store()
        st["last_result"] = result
        _write_verify_store(st)
        _finish_state("done", 100, summary_msg, result)
    except Exception as e:
        _finish_state("error", 0, "校验执行异常：%s" % e, {"ok": False, "status": "ERROR", "msg": str(e), "added": []})
    finally:
        _remove_backup_and_temps(temp_mods, temp_junctions)


def _set_prog(pct, msg):
    with _LOCK:
        if _VERIFY_STATE["running"]:
            _VERIFY_STATE["pct"] = pct
            _VERIFY_STATE["msg"] = msg


def _finish_state(phase, pct, msg, result):
    with _LOCK:
        _VERIFY_STATE["running"] = False
        _VERIFY_STATE["phase"] = phase
        _VERIFY_STATE["pct"] = pct
        _VERIFY_STATE["msg"] = msg
        if result is not None:
            _VERIFY_STATE["result"] = result


def start_game_verify(layers=None, confirm=False, baseline_mode="parents",
                      reuse_baseline=True, game_dir="", docs_dir="",
                      runner=None, sync=False):
    """启动 7-4 进游戏检查：未确认拦截、环境失败明确报错、成功后自动还原现场。"""
    with _LOCK:
        if _VERIFY_STATE["running"]:
            return {"ok": False, "msg": "进游戏检查已在运行中"}

    if confirm:
        set_verify_confirmed(True)
    elif not is_verify_confirmed():
        return {
            "ok": False,
            "need_confirm": True,
            "msg": "首次运行需要修改游戏启动配置文件 dlc_load.json（检查结束或异常退出恢复后自动还原），确认继续吗？",
        }

    env = check_environment(game_dir=game_dir, docs_dir=docs_dir)
    if not env["ok"]:
        return {"ok": False, "msg": env["reason"], "env": env}

    chain = layers if layers is not None else (mod_layers(None) or [])
    gd_key = os.path.normcase(os.path.abspath(env["game_dir"])) if env.get("game_dir") else ""
    non_game = [
        os.path.abspath(r) for r in chain
        if r and not is_under_game(r) and os.path.normcase(os.path.abspath(r)) != gd_key
    ]
    if not non_game:
        return {"ok": False, "msg": "当前未加载任何需要校验的 mod（仅加载了原版）。"}

    _CANCEL_EV.clear()
    with _LOCK:
        _VERIFY_STATE.update({
            "running": True,
            "phase": "starting",
            "pct": 5,
            "msg": "准备备份 dlc_load.json 并校验环境…",
            "recovered_msg": env.get("recovered_msg") or "",
        })

    fn_runner = runner or run_once
    if sync:
        _run_verify_worker(non_game, env["game_dir"], env["docs_dir"], baseline_mode, reuse_baseline, fn_runner)
        return {"ok": True, "msg": _VERIFY_STATE.get("msg") or "完成", "state": get_verify_status(layers=chain, game_dir=game_dir, docs_dir=docs_dir)}

    th = threading.Thread(
        target=_run_verify_worker,
        args=(non_game, env["game_dir"], env["docs_dir"], baseline_mode, reuse_baseline, fn_runner),
        name="game_verify",
        daemon=True,
    )
    th.start()
    return {"ok": True, "msg": "已启动进游戏检查"}


def cancel_game_verify():
    with _LOCK:
        was_running = bool(_VERIFY_STATE["running"])
    _CANCEL_EV.set()
    if was_running:
        return {"ok": True, "msg": "正在中止游戏进程并还原 dlc_load.json…"}
    return {"ok": True, "msg": "当前没有运行中的进游戏检查"}
