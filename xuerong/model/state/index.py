# -*- coding: utf-8 -*-
"""省 ↔ 州索引与定位。

`definition.csv` 的地理查询（`_coastal_provinces` / `state_is_coastal`）、
state 文件枚举与指纹、省 → 州映射表及其两处缓存、`_state_locate` 家族。

`_coastal_provinces` / `state_is_coastal` 留在这里而不是 refine：它们本质是
「读 definition.csv 把省映射到州属性」的地理查询，与索引同族；放 refine 会成为
`io ↔ refine` 环（`io.state_detail` 调 `state_is_coastal`，`refine.state_refine_apply`
调 `io.state_save`）。
"""
import io
import os
import re

from xuerong import state
from xuerong.core.paths import _layer_dirs, _layers_find, mod_layers
from xuerong.core.text import _read_text, brace_match
from xuerong.model.map import _map_pick
from xuerong.model.state._inj import _hist_find_top, _parse_state_provinces


# _coastal_provinces 的缓存：只在这里用，不跨模块
_COASTAL_CACHE = {"key": None, "set": set()}

# 建「省 → 州」表的缓存。key 是叠加链里全部 state 文件的 stat 指纹，
# 写盘后下一次调用自然发现（不用在每个写盘点手动清），参照 _COASTAL_CACHE 的写法。
_PROV_MAP_CACHE = {"key": None, "map": None}

def _coastal_provinces():
    """definition.csv 第 6 列 = coastal（true/false）。按 mtime 缓存。

    注意要走 `_layers_find` 拿源文件；`_map_dir` 给的是缓存目录，里面只有 png。
    """
    root = _map_pick(None)
    layers = mod_layers(root) if root else []
    p, _base = (_layers_find("map/definition.csv", layers) if layers else (None, None))
    if not p and state.game():
        p = os.path.join(state.game(), "map", "definition.csv")
    if not p or not os.path.exists(p):
        return set()
    try:
        stamp = (p, int(os.path.getmtime(p)), os.path.getsize(p))
    except Exception:
        stamp = (p, 0, 0)
    if _COASTAL_CACHE.get("key") == stamp:
        return _COASTAL_CACHE["set"]
    out = set()
    try:
        with io.open(p, encoding="utf-8", errors="replace") as _f:
            for ln in _f:
                f = ln.strip().split(";")
                if len(f) >= 6 and f[5].strip().lower() == "true":
                    try:
                        out.add(int(f[0]))
                    except Exception:
                        pass
    except Exception:
        pass
    _COASTAL_CACHE["key"] = stamp
    _COASTAL_CACHE["set"] = out
    return out

def state_is_coastal(s):
    """州里只要有一个沿海省，就能造海军基地/船坞。"""
    coastal = _coastal_provinces()
    if not coastal:
        return None                      # 拿不到定义，不做限制
    return any(int(p) in coastal for p in (s.get("provinces") or []))

def _state_locate(text):
    m = _hist_find_top(text, re.compile(r'(?m)^[ \t]*state\s*=\s*\{'))
    if not m:
        return None
    b = text.find('{', m.end() - 1)
    return b, brace_match(text, b)

def _state_files_in_layers(root=None):
    """叠加链里所有 history/states 的 .txt：[(州文件绝对路径)]，已按叠加语义去重。

    顺序与 `_find_state_of_prov` 的遍历顺序**完全相同**：`state.roots()` 外层，
    `_layer_dirs("history/states", root)` 内层（子层在前），目录按绝对路径去重。
    所以「先出现的文件」就是「游戏里先生效的文件」。
    """
    seen = set()
    out = []
    for root in (state.roots() if root is None else [root]):
        for _base, d in _layer_dirs("history/states", root):
            ab = os.path.abspath(d)
            if ab in seen:
                continue
            seen.add(ab)
            try:
                names = sorted(f for f in os.listdir(d) if f.endswith(".txt"))
            except Exception:
                continue
            for fn in names:
                out.append(os.path.join(d, fn))
    return out


_STATE_ID_RE = re.compile(r'(?m)^[ \t]*id\s*=\s*(\d+)')
_STATE_OPEN_RE = re.compile(r'(?m)^[ \t]*state\s*=\s*\{')


def _read_raw_state(path):
    """读 state 文件，结果与 `io.open(encoding="utf-8-sig", errors="replace").read()`
    逐字节相同（含换行归一，818/818 实测一致），但快 28%：818 个文件 66 ms → 48 ms。

    `os.read` 直接进 bytes 再一次性解码，避开了 TextIOWrapper 的逐行增量解码；
    CRLF / 孤立 CR 手工归一成 `\\n`，补上文本模式默认的 universal newlines。
    """
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_BINARY", 0))
    try:
        chunks = []
        while True:
            c = os.read(fd, 65536)
            if not c:
                break
            chunks.append(c)
    finally:
        os.close(fd)
    raw = b"".join(chunks)
    if raw[:3] == b"\xef\xbb\xbf":
        raw = raw[3:]
    text = raw.decode("utf-8", "replace")
    if "\r" in text:
        text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text


def _state_locate_fast(text):
    """`_state_locate` 的等价快路径，用于建表时批量解析。

    `_state_locate` 走 `_hist_find_top`，后者为了「只认深度 0 的匹配」会给**整个文本
    逐字符**算一遍括号深度（`_hist_depths`）。818 个 state 文件实测 53 ms，
    占了建表的三分之一。

    state 文件的结构是固定的：整份文件只有一个顶层 `state = {`，它前面不会有
    未闭合的 `{` 或 `"`。这种形状下：
      · 「深度 0」等价于「匹配位置前没有 `{` 也没有 `"`」→ 用 `find` 判一次前缀；
      · 闭合括号就是全文最后一个 `}`（`_hist_depths` + `brace_match` 走一遍
        818 个文件要 30 ms，`rfind` 只要 0.4 ms）。
    形状不满足（多候选 / 前缀里有 `{` / `"` / 尾部 `}` 之后还有非注释内容）
    就回退到原 `_state_locate`，所以结论与它逐字节一致。
    """
    cand = list(_STATE_OPEN_RE.finditer(text))
    if not cand:
        return None
    if len(cand) == 1:
        _pre = text[:cand[0].start()]
        if "{" not in _pre and '"' not in _pre:
            b = text.find('{', cand[0].end() - 1)
            e = text.rfind('}') + 1
            if e > b:
                # 尾部必须是空的或纯注释，否则可能有并列的第二个顶层块
                ok = True
                for line in text[e:].splitlines():
                    s = line.strip()
                    if s and not s.startswith("#"):
                        ok = False
                        break
                if ok:
                    return b, e
    return _state_locate(text)


def _strip_inline_comment(line):
    """行内注释剥离，与 `xuerong.core.text.strip_comments` 对单行的处理一致：
    `#` 在引号外才起效。"""
    if "#" not in line:
        return line
    buf, instr = [], False
    for c in line:
        if c == '"':
            instr = not instr
        if c == "#" and not instr:
            break
        buf.append(c)
    return "".join(buf)


def _state_id_and_provs(raw):
    """从 state 文件原文里取 `(州 id, 省列表)`，不需要先给整份文件去注释。

    与 `_read_text` + `_STATE_ID_RE` + `_state_locate` + `_parse_state_provinces`
    的组合逐字节等价，差别只在「注释在哪一步剥掉」：
      · 已有的解析链是「全文 strip → 找 id → 定 state 块 → 块内找 provinces → 取数字」；
      · 这里改成「定位 state 块 → 只对块内做 strip → 找 id 与 provinces」，
        数学上等价，因为剥注释是逐行的局部操作，块外与块内互不影响。
    剥注释只花在 state 块上（818 个文件约占全文的一部分），省掉全文逐行扫描。

    id 与 provinces 都必须能读到才算成功；读不到返回 None（与解析链一致地跳过该文件）。
    """
    loc = _state_locate_fast(raw)
    if not loc:
        return None
    b, e = loc
    body = raw[b + 1:e - 1]
    if "#" in body:
        body = "\n".join(_strip_inline_comment(line) for line in body.split("\n"))
    m = _STATE_ID_RE.search(body)
    if not m:
        return None
    provs = _parse_state_provinces(body)
    try:
        return int(m.group(1)), provs
    except Exception:
        return None


def _state_files_fingerprint(root=None):
    """叠加链 state 文件的指纹：((路径, mtime_ns, size), ...)，按路径排序。

    用来判断「省 → 州」表还能不能用。818 个文件实测 1–6 ms（`os.scandir` 直接复用
    目录枚举数据），相对建表的 100 ms 便宜两个数量级。

    扫的范围与 `_state_files_in_layers` **严格相同**（同样非递归、同样目录去重、
    同样排序），所以「指纹没变」等价于「建表输入没变」，不会漏失效也不会白重建。

    不用「显式清缓存」的写法：写盘的地方有好几处（state_save / state_apply_buildings /
    state_create / state_province_refine），漏一处就是长期错误数据。指纹自动发现
    任何一处写入，代价只是几毫秒。
    """
    seen = set()
    rows = []
    for _root in (state.roots() if root is None else [root]):
        for _base, d in _layer_dirs("history/states", _root):
            ab = os.path.abspath(d)
            if ab in seen:
                continue
            seen.add(ab)
            try:
                it = os.scandir(ab)
            except Exception:
                continue
            with it:
                for e in it:
                    if not e.name.endswith(".txt"):
                        continue
                    try:
                        if e.is_dir(follow_symlinks=False):
                            continue
                    except Exception:
                        continue
                    try:
                        st = e.stat()
                        rows.append((e.path, st.st_mtime_ns, st.st_size))
                    except Exception:
                        rows.append((e.path, -1, -1))
    rows.sort()
    return tuple(rows)


def _prov_to_state_map(root=None):
    """一次扫完叠加链，返回 {省 id: 州 id}。

    `_find_state_of_prov` 每次调用都要把所有 state 文件读一遍、正则找 `id =`、
    定位 state 块、再解析 provinces 列表。实测 818 个文件、97 ms 一次，移 50 个省
    就是 4.2 秒；同一个州文件会被反复读几十遍。

    语义与 `_find_state_of_prov` 严格一致：
      · 遍历顺序同样是 `state.roots()` → `_layer_dirs("history/states", root)`，
        目录按绝对路径去重（对应那边 `seen` 的写法）；
      · **先到先得**：同一个省在多个州文件里出现时，第一个读到的文件说了算。
        因为子层目录在前，所以效果就是「子层优先覆盖父层」——父层里那份被
        子层改过的归属不会反过来盖掉子层；
      · 文件内出现顺序与那边一致（`sorted()` 排列文件名）；
      · 同一个 `pid` 在一个文件的 provinces 列表里重复出现只记一条（dict 天然如此，
        慢路径也是 `in` 判断，结论一致）。

    与 `_find_state_of_prov` 唯一的差别是：这里扫完全部文件，不再命中即 return。

    结果按 `_state_files_fingerprint` 缓存，语义照 `_COASTAL_CACHE`：
    指纹一变就重建，不依赖任何一处写盘代码记得来清缓存。
    """
    fp = _state_files_fingerprint(root)
    if _PROV_MAP_CACHE.get("key") == fp and _PROV_MAP_CACHE.get("map") is not None:
        return dict(_PROV_MAP_CACHE["map"])

    mapping = {}
    for fpth in _state_files_in_layers(root):
        try:
            raw = _read_raw_state(fpth)
        except Exception:
            continue
        parsed = _state_id_and_provs(raw)
        if not parsed:
            continue
        sid, provs = parsed
        for p in provs:
            if p not in mapping:      # 先到先得 = 子层优先
                mapping[p] = sid
    _PROV_MAP_CACHE["key"] = fp
    _PROV_MAP_CACHE["map"] = mapping
    return dict(mapping)


def _find_state_of_prov(pid):
    """扫 state 文件，找出哪个州包含这个省

    走叠加链：只扫 root 那一层时，加载纯 submod（自己没有 history/states，或者
    该目录被 replace_path 接管）就永远查不到省属于哪个州。_layer_dirs 是子层在前，
    这里遇到第一个命中就 return，语义仍然是「子层优先覆盖父层」。"""
    seen = set()
    for root in state.roots():
        for _base, d in _layer_dirs("history/states", root):
            ab = os.path.abspath(d)
            if ab in seen:
                continue
            seen.add(ab)
            for fn in sorted(f for f in os.listdir(d) if f.endswith(".txt")):
                p = os.path.join(d, fn)
                try:
                    text = _read_text(p)
                except Exception:
                    continue
                m = re.search(r'(?m)^[ \t]*id\s*=\s*(\d+)', text)
                if not m:
                    continue
                loc = _state_locate(text)
                if not loc:
                    continue
                b, e = loc
                if int(pid) in _parse_state_provinces(text[b + 1:e - 1]):
                    return int(m.group(1))
    return None

def _state_file_for(sid):
    """按州 id 找文件路径：(root, rel, path)。

    优先用 state.states() 里已经定下来的那条记录 —— 同一个 id 在多个文件里出现时
    （比如原版有 1-France.txt、mod 又加了 1-Corsica.txt），
    按文件名遍历会挑到和 state.states() 不一致的那一个，后续写入就落到错误文件。"""
    try:
        _s = state.states().get(int(sid)) if isinstance(state.states(), dict) else None
    except Exception:
        _s = None
    if _s and _s.get("root") and _s.get("file"):
        _p = os.path.join(_s["root"], _s["file"])
        if os.path.exists(_p):
            return _s["root"], _s["file"], _p

    _bases = []
    for _r in (state.roots() or []):
        for _b in (mod_layers(_r) or [_r]):
            if _b and os.path.abspath(_b) not in [os.path.abspath(x) for x in _bases]:
                _bases.append(_b)
    for root in reversed(_bases):
        d = os.path.join(root, "history", "states")
        if not os.path.isdir(d):
            continue
        for fn in sorted(f for f in os.listdir(d) if f.endswith(".txt")):
            p = os.path.join(d, fn)
            try:
                text = _read_text(p)
            except Exception:
                continue
            m = re.search(r'(?m)^[ \t]*id\s*=\s*(\d+)', text)
            if m and int(m.group(1)) == int(sid):
                return root, os.path.join("history", "states", fn), p
    return None, None, None
