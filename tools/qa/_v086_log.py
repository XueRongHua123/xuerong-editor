# v0.86 游戏日志检查（error.log）
LOG_PATTERNS = [
    ("railway", "warn", r"Railway level .*MAX_RAILWAY_LEVEL", "铁路等级超过上限",
     "把 railways.txt 里对应线路的 level 降到 5 以内"),
    ("trigger", "warn", r"Invalid trigger", "无效的 trigger",
     "多为拼错或 1.19 已改名的 trigger，对照语法参考改"),
    ("deprecated", "warn", r"Using deprecated property", "使用了已弃用的属性",
     "旧写法仍能跑但会在日志刷屏，建议按提示改名"),
    ("gfx", "info", r"GFX referenced .* does not exist", "引用了不存在的 GFX",
     "装备/单位图标缺图，检查 gfx 定义或图标名拼写"),
    ("entity", "info", r"Failed to find entity", "缺少 3D 实体（模型）",
     "多为模型文件缺失，纯视觉问题，不影响逻辑"),
    ("sound", "info", r"Could not load sound file|already added", "音效缺失或重复",
     "声音定义文件里有重复项或文件不存在"),
    ("version", "info", r"Invalid supported_version", "descriptor 的 supported_version 写法不对",
     "改成 \"1.19.*\" 或与玩家版本一致"),
    ("loc", "warn", r"Unknown loc key|Missing localisation|Localisation key", "本地化缺失",
     "补 loc key，注意 .yml 必须是 UTF-8 带 BOM"),
    ("syntax", "error", r"Unexpected token|Expecting .* but got|Error parsing", "脚本语法错误",
     "括号/引号/赋值写错，按日志里的 file:line 定位"),
]


def _log_paths():
    """候选 error.log 位置"""
    out = []
    home = os.path.expanduser("~")
    for p in (os.path.join(home, "Documents", "Paradox Interactive", "Hearts of Iron IV", "logs", "error.log"),
              os.path.join(home, "OneDrive", "Documents", "Paradox Interactive", "Hearts of Iron IV", "logs", "error.log")):
        if os.path.exists(p):
            out.append(p)
    return out


def read_error_log(path=None, limit_files=40):
    """解析 error.log：按类别聚合，给出计数、样例与涉及文件"""
    cand = [path] if path else _log_paths()
    if not cand or not os.path.exists(cand[0]):
        return {"ok": False, "msg": "没找到 error.log（先运行一次游戏）"}
    p = cand[0]
    try:
        text = io.open(p, encoding="utf-8", errors="replace").read()
    except Exception as e:
        return {"ok": False, "msg": "读取日志失败：%s" % e}
    lines = text.splitlines()
    pat = re.compile(r"^\[(\d\d:\d\d:\d\d)\]\[([^\]]*)\]\[([^\]]+)\]:\s*(.*)$")
    buckets = {}
    unmatched = 0
    files = {}
    for ln in lines:
        ln = ln.strip()
        if not ln:
            continue
        m = pat.match(ln)
        if not m:
            unmatched += 1
            continue
        _t, _d, where, msg = m.groups()
        hit = None
        for key, level, rx, title, hint in LOG_PATTERNS:
            if re.search(rx, msg):
                hit = (key, level, title, hint)
                break
        if not hit:
            continue
        key, level, title, hint = hit
        b = buckets.setdefault(key, {"key": key, "level": level, "title": title, "hint": hint,
                                     "count": 0, "samples": [], "files": {}})
        b["count"] += 1
        if len(b["samples"]) < 3:
            b["samples"].append(msg[:160])
        fm = re.search(r"file:\s*([^\s]+)(?:\s+line:\s*(\d+))?", msg)
        if fm:
            f = fm.group(1)
            b["files"][f] = b["files"].get(f, 0) + 1
            files[f] = files.get(f, 0) + 1
    items = []
    for key, b in sorted(buckets.items(), key=lambda kv: -kv[1]["count"]):
        top_files = sorted(b["files"].items(), key=lambda kv: -kv[1])[:4]
        detail = "；".join("%s ×%d" % (f, n) for f, n in top_files) or "（日志未给出文件名）"
        items.append({"level": b["level"], "kind": "log",
                      "title": "%s（%d 条）" % (b["title"], b["count"]),
                      "detail": detail + "　建议：" + b["hint"],
                      "samples": b["samples"]})
    return {"ok": True, "path": p, "lines": len(lines), "unmatched": unmatched,
            "items": items, "files": sorted(files.items(), key=lambda kv: -kv[1])[:limit_files]}


def lint_project(limit=1500):
