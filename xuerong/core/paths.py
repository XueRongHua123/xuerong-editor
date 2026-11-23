# -*- coding: utf-8 -*-
"""mod 定位、descriptor 解析与叠加链（P0-2 从 focus_editor.py 迁入）。

这里是「一个 mod 目录在哪、它和谁叠在一起」的唯一实现。所有 loader 都经过
`mod_layers()` / `_layer_dirs()` 读文件，所以这个模块出问题会全站出问题。

三条约定：

1. 读全局走 `state.roots()` / `state.game()` / `state.options()`，不要 import 名字。
   门面（focus_editor）仍是这些变量的持有者，accessor 会先读门面，
   所以外部脚本 `fe.ROOTS = [...]` 依然生效。
2. 缓存（descriptor / 叠加链 / 启动器顺序 / 搜索目录）**只在这里**，别处不许再存一份。
3. 这个模块不认识 map 层。`mod_layers(None)` 需要「挑一个有地图的 root」时，
   通过 `set_root_picker()` 回注——core 不能反向 import model。
"""
import io
import json
import os
import re
import shutil
import sys

from xuerong import state
from xuerong.core.text import _atomic_write, _read_text

# ---------------------------------------------------------------- 缓存
_START_DATE_CACHE = {}
_DESC_CACHE = {}
_SEARCH_BASES_CACHE = {}
_MOD_ORDER_CACHE = {}
_LAYERS_CACHE = {}
_CHAIN_SCAN_CACHE = {}

# 应用目录（打包后是 exe 目录，源码运行是 work/）。由门面在 import 后写入；
# 没写就用本文件往上三级推导，保证 `python -c "import xuerong.core.paths"` 也能用。
APP_DIR = ""


def app_dir():
    if APP_DIR:
        return APP_DIR
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def qa_dir():
    """qa/ 目录在哪。

    四种部署形态都覆盖：源码仓库是 work/qa（公开仓库是 tools/qa），
    打包成 onefile exe 后是平铺的 _MEIPASS/qa，-D 模式是 exe 同级的 qa/。
    三个 base × 两个相对路径依次试，全找不到就返回 app_dir()/qa，让调用方
    自己碰错——比在这里抛异常好定位。

    以前门面、diagnose.py 各写了一份一模一样的实现（map/world 又各转发一次），
    合并到这里之后三处调用方都只认这一个。
    """
    here = app_dir()
    for base in (getattr(sys, "_MEIPASS", "") or "", here, os.path.dirname(here)):
        for rel in (("qa",), ("tools", "qa")):
            p = os.path.join(base, *rel) if base else ""
            if p and os.path.isdir(p):
                return p
    return os.path.join(here, "qa")


def _dir_mtime(p):
    """目录下所有 .txt 的最大 mtime（秒，整型）；目录不存在或读不了返回 0。

    只看 .txt 是因为调用方（地图缓存键、脚本引用缓存键）关心的都是脚本文件，
    .bmp/.png 这些大文件由别的路径单独判新鲜度。单个文件 getmtime 失败不
    影响其它文件——逐文件 try 而不是整段 try，是为了一个坏链接不至于让整个
    目录的缓存永远失效。
    """
    if not os.path.isdir(p):
        return 0
    mt = 0
    try:
        for fn in os.listdir(p):
            if fn.endswith(".txt"):
                try:
                    mt = max(mt, int(os.path.getmtime(os.path.join(p, fn))))
                except Exception:
                    pass
    except Exception:
        pass
    return mt


# ---------------------------------------------------------------- root 选择钩子
_PICK = {"fn": None}


def set_root_picker(fn):
    """注册「没指定 root 时选哪个」的策略（门面注入 _map_pick）。"""
    _PICK["fn"] = fn


def _pick(root=None):
    if root:
        return root
    fn = _PICK["fn"]
    if fn:
        try:
            r = fn()
            if r:
                return r
        except Exception:
            pass
    rs = state.roots() or []
    for r in reversed(rs):
        if r and not is_readonly_mod(r):
            return r
    for r in reversed(rs):
        if r and not is_under_game(r):
            return r
    if rs:
        return rs[-1]
    return state.game()



# ---------------------------------------------------------------- _layer_dirs

def _layer_dirs(sub, root):
    """某类资源在叠加链里的目录列表（子 mod 在前，便于后加载覆盖前）。

    老的 loader 都是「扫 root 下一个目录」，加载纯 submod 时父 mod 的同类文件读不到。
    全部改用它之后，即使 ROOTS 只有 submod，也能沿 mod_layers 读到父 mod 与原版。"""
    layers = mod_layers(root) or []
    # 某层声明了 replace_path 时，该目录只从那一层及其后读取，下层（含原版）全部屏蔽
    try:
        _owner = _replace_owner(root, sub)
    except Exception:
        _owner = None
    if _owner:
        try:
            layers = layers[layers.index(_owner):]
        except ValueError:
            pass
    out = []
    seen = set()
    for base in reversed(layers):
        if not base:
            continue
        d = os.path.join(base, sub.replace("/", os.sep))
        if not os.path.isdir(d):
            continue
        ab = os.path.abspath(d)
        if ab in seen:
            continue
        seen.add(ab)
        out.append((base, d))
    return out


def effective_layer_files(sub, root, exts=(".txt",)):
    """按 HOI4 实机规则返回某目录下有效文件 [(base, dirpath, filename), ...]（底层在前、顶层在后）。

    1) 经过 `_layer_dirs` 自动拦截 `replace_path` 下层；
    2) 同相对路径同名文件（大小写不敏感）由最高层整文件覆写，跳过下层同名文件；
    3) 反转成底层 → 顶层顺序返回。
    """
    seen_fn = set()
    picked = []
    for base, d in _layer_dirs(sub, root):
        try:
            fns = sorted(f for f in os.listdir(d) if f.lower().endswith(exts))
        except Exception:
            continue
        for fn in fns:
            fk = fn.lower()
            if fk in seen_fn:
                continue
            seen_fn.add(fk)
            picked.append((base, d, fn))
    picked.reverse()
    return picked


def unique_editor_filename(root, sub_rel, default_filename):
    """为新建内容挑选不与下层撞名的文件名，避免多级 submod 同名整文件覆写下层新建文件。

    1) 若当前 `root` 自己已建过 `default_filename` 或专属派生名，沿用该文件；
    2) 若更下层均不存在 `default_filename`，直接沿用 `default_filename`（保持单层兼容性）；
    3) 否则按当前 mod 目录名派生 `zz_fe_<slug>_<rest>`（冲突时加序号后缀）。
    """
    ab_root = os.path.abspath(root or "")
    sub_n = (sub_rel or "").replace("\\", "/").strip("/")
    sub_dir = os.path.join(ab_root, sub_n.replace("/", os.sep))
    if os.path.isfile(os.path.join(sub_dir, default_filename)):
        return default_filename
    slug = re.sub(r"[^A-Za-z0-9_]", "", os.path.basename(ab_root.rstrip("\\/")) or "sub").lower() or "sub"
    rest = default_filename[3:] if default_filename.lower().startswith("zz_") else default_filename
    pref = "zz_fe_%s_%s" % (slug, rest)
    if os.path.isfile(os.path.join(sub_dir, pref)):
        return pref
    lower_names = set()
    for base in (mod_layers(ab_root) or []):
        if os.path.normcase(os.path.abspath(base)) == os.path.normcase(ab_root):
            continue
        dp = os.path.join(base, sub_n.replace("/", os.sep))
        if os.path.isdir(dp):
            try:
                for fn in os.listdir(dp):
                    lower_names.add(fn.lower())
            except Exception:
                pass
    if default_filename.lower() not in lower_names:
        return default_filename
    cand = pref
    stem, ext = os.path.splitext(pref)
    n = 2
    while cand.lower() in lower_names or os.path.isfile(os.path.join(sub_dir, cand)):
        cand = "%s_%d%s" % (stem, n, ext)
        n += 1
    return cand

# ---------------------------------------------------------------- _chain_layers

def _chain_layers(root):
    """一个 mod 的完整叠加链目录，从最父（含原版）到最子。

    和 _layer_dirs 的区别：那个按子目录名找并处理 replace_path，
    这个返回整条链本身，给「不知道要找哪个子目录」的场景用
    （图标索引、本地化语言目录、events 这种整目录扫描）。

    顺序是「父 → 子」：后读的覆盖先读的，和 HOI4 语义一致。
    """
    try:
        L = mod_layers(root)
    except Exception:
        L = []
    if not L:
        L = [root]
    out, seen = [], set()
    for ab in L:
        if not ab:
            continue
        try:
            a = os.path.abspath(ab)
        except Exception:
            continue
        if a in seen:
            continue
        seen.add(a)
        out.append(a)
    return out

# ---------------------------------------------------------------- _start_date_for

def _start_date_for(root):
    """读某个 mod（或原版）的 bookmarks 得到开局日期；读不到回退 1936.1.1"""
    key = os.path.abspath(root or "")
    if key in _START_DATE_CACHE:
        return _START_DATE_CACHE[key]
    dates = []
    # 走叠加链，从子 mod 往原版找：第一个有 bookmarks 的层生效。
    # 不能只查 (root, state.game())——submod 通常没有自己的 bookmarks，
    # 开局日期在父 mod 里（MUVLUV 是 1999.8.7，回退 1936 会让所有日期块失效）。
    try:
        _layers = mod_layers(root) or []
    except Exception:
        _layers = []
    if not _layers:
        _layers = [root, state.game()]
    for base in reversed(_layers):
        d = os.path.join(base or "", "common", "bookmarks")
        if not os.path.isdir(d):
            continue
        for fn in sorted(f for f in os.listdir(d) if f.endswith(".txt")):
            try:
                text = _read_text(os.path.join(d, fn))
            except Exception:
                continue
            for m in re.finditer(r'(?m)^[ \t]*date\s*=\s*"?(\d{4})\.(\d{1,2})\.(\d{1,2})', text):
                dates.append((int(m.group(1)), int(m.group(2)), int(m.group(3))))
        if dates:
            break
    val = min(dates) if dates else (1936, 1, 1)
    _START_DATE_CACHE[key] = val
    print("开局日期 %s -> %d.%d.%d" % (os.path.basename(key), val[0], val[1], val[2]))
    return val

# ---------------------------------------------------------------- _OPT_FILE/_load_options/_save_options

# 选项文件跟着应用目录走（打包后是 exe 目录），不是这个模块所在目录。
_OPT_FILE = os.path.join(app_dir(), "cache", "options.json")


def _load_options():
    try:
        if os.path.isfile(_OPT_FILE):
            j = json.loads(io.open(_OPT_FILE, encoding="utf-8-sig",
                                   errors="replace").read())
            for k in list(state.options()):
                if k in j:
                    if k == "game_dir":
                        state.options()[k] = str(j[k] or "").strip()
                    else:
                        state.options()[k] = bool(j[k])
    except Exception:
        pass


def _save_options():
    try:
        _atomic_write(_OPT_FILE, json.dumps(state.options(), ensure_ascii=False,
                                            indent=1).encode("utf-8"))
    except Exception:
        pass

def _mod_descriptor(root):
    """读 mod 根目录的 descriptor.mod，返回 name / dependencies / replace_path。
    带 mtime 缓存：这个函数会被叠加链、图层查找反复调用，不缓存会拖慢所有接口。"""
    try:
        _abs = os.path.abspath(root or "")
        _dp = os.path.join(_abs, "descriptor.mod")
        _sig = None
        if os.path.exists(_dp):
            _st = os.stat(_dp)
            _sig = (_st.st_mtime, _st.st_size)
        _hit = _DESC_CACHE.get(_abs)
        if _hit is not None and _hit[0] == _sig:
            return dict(_hit[1])
    except Exception:
        _abs, _sig = "", None
    info = {"name": "", "deps": [], "replace": [], "path": ""}
    for fn in ("descriptor.mod",):
        p = os.path.join(root, fn)
        if not os.path.exists(p):
            continue
        try:
            text = io.open(p, encoding="utf-8-sig", errors="replace").read()
        except Exception:
            continue
        m = re.search(r'(?m)^\s*name\s*=\s*"([^"]*)"', text)
        if m:
            info["name"] = m.group(1)
        m = re.search(r'dependencies\s*=\s*\{([^}]*)\}', text, re.S)
        if m:
            info["deps"] = re.findall(r'"([^"]+)"', m.group(1))
        info["replace"] = re.findall(r'replace_path\s*=\s*"([^"]*)"', text)
        break
    try:
        if _abs:
            _DESC_CACHE[_abs] = (_sig, dict(info))
    except Exception:
        pass
    return info

# ---------------------------------------------------------------- pdx_user_dir

def pdx_user_dir():
    """Documents/Paradox Interactive/Hearts of Iron IV。

    优先找真的存在的那个（Documents 被 OneDrive 重定向时 ~/Documents 可能是空的），
    都不存在才返回默认路径。
    """
    home = os.path.expanduser("~")
    docs = [os.path.join(home, "Documents"),
            os.path.join(home, "OneDrive", "Documents")]
    up = os.environ.get("USERPROFILE")
    if up:
        docs.append(os.path.join(up, "Documents"))
    for d in docs:
        p = os.path.join(d, "Paradox Interactive", "Hearts of Iron IV")
        if os.path.isdir(p):
            return p
    return os.path.join(home, "Documents", "Paradox Interactive", "Hearts of Iron IV")

# ---------------------------------------------------------------- _resolve_mod_path

def _resolve_mod_path(raw, base):
    """把 .mod 里的 path= 解析成真实目录。

    三种写法都要认：
      绝对路径        E:/SteamLibrary/steamapps/workshop/content/394360/2800380626
      相对用户目录    mod/xxx            （本地 mod）
      相对游戏目录    mod/xxx            （老式安装）
    """
    p = (raw or "").strip().replace("\\", "/")
    if not p:
        return None
    cands = []
    if os.path.isabs(p) or re.match(r"^[A-Za-z]:/", p):
        cands.append(p.replace("/", os.sep))
    else:
        cands.append(os.path.join(base, p.replace("/", os.sep)))
        cands.append(os.path.join(base, "mod", os.path.basename(p.rstrip("/"))))
        if state.game():
            cands.append(os.path.join(state.game(), p.replace("/", os.sep)))
    for c in cands:
        try:
            if os.path.isdir(c):
                return os.path.abspath(c)
        except Exception:
            continue
    return None

# ---------------------------------------------------------------- _steam_libraries

def _steam_libraries():
    """Steam 库根目录列表。从注册表拿 Steam 安装位置，再解析 libraryfolders.vdf。

    不写死盘符：别人的机器、游戏装到别的盘都要能用。
    """
    roots = []
    steam = ""
    try:
        import winreg
        for hive, key in ((winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam"),
                          (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam")):
            try:
                k = winreg.OpenKey(hive, key)
            except Exception:
                continue
            for name in ("SteamPath", "InstallPath"):
                try:
                    v = winreg.QueryValueEx(k, name)[0]
                except Exception:
                    continue
                if v and os.path.isdir(v):
                    steam = v
                    break
            if steam:
                break
    except Exception:
        steam = ""
    # 游戏目录本身也能反推出一个库（--game 指到别的库时最可靠）
    if state.game():
        parts = os.path.abspath(state.game()).replace("\\", "/").split("/")
        low = [x.lower() for x in parts]
        if "steamapps" in low:
            lib = "/".join(parts[:low.index("steamapps")])
            if lib and lib not in roots:
                roots.append(lib.replace("/", os.sep))
    vdf = os.path.join(steam, "steamapps", "libraryfolders.vdf") if steam else ""
    if vdf and os.path.isfile(vdf):
        try:
            txt = io.open(vdf, encoding="utf-8", errors="replace").read()
            for m in re.finditer(r'"path"\s+"([^"]+)"', txt):
                lib = m.group(1).replace("\\\\", "\\")
                if os.path.isdir(lib) and lib not in roots:
                    roots.append(lib)
        except Exception:
            pass
    return roots

# ---------------------------------------------------------------- _mod_search_bases

def _mod_search_bases():
    """可能存放 mod 的目录（本地 mod 目录 + 各 Steam 库的 workshop/394360）。"""
    key = state.game() or ""
    hit = _SEARCH_BASES_CACHE.get(key)
    if hit:
        return list(hit)
    out = []
    local = os.path.join(pdx_user_dir(), "mod")
    if os.path.isdir(local):
        out.append(os.path.abspath(local))
    for lib in _steam_libraries():
        ws = os.path.join(lib, "steamapps", "workshop", "content", "394360")
        if os.path.isdir(ws) and os.path.abspath(ws) not in out:
            out.append(os.path.abspath(ws))
    _SEARCH_BASES_CACHE[key] = list(out)
    return out

# ---------------------------------------------------------------- _enabled_mod_order

def _enabled_mod_order():
    """启动器里勾选的 mod 目录，按实际加载顺序。

    读 dlc_load.json 的 enabled_mods，每项是 mod/<名字>.mod，那个文件里写着 path=。
    拿不到就返回空列表，调用方自己兜底。

    **不受 follow_launcher 开关影响**：这个函数只负责「启动器里有哪些 mod、什么顺序」，
    至于要不要把它们铺进叠加链，由 mod_layers 决定。`_find_mod_by_name` 也靠它找目录，
    那里关掉开关就没法按名字找到 mod 了。
    """
    base = pdx_user_dir()
    jf = os.path.join(base, "dlc_load.json")
    if not os.path.isfile(jf):
        return []
    try:
        st = os.stat(jf)
        sig = (st.st_mtime, st.st_size)
    except Exception:
        sig = None
    hit = _MOD_ORDER_CACHE.get("k")
    if hit is not None and hit[0] == sig:
        return list(hit[1])
    out = []
    try:
        j = json.loads(io.open(jf, encoding="utf-8-sig", errors="replace").read())
    except Exception:
        return out
    for item in (j.get("enabled_mods") or []):
        if not isinstance(item, str) or not item.strip():
            continue
        rel = item.replace("\\", "/")
        fn = os.path.join(base, rel.replace("/", os.sep))
        if not os.path.isfile(fn):
            continue
        raw = None
        try:
            txt = io.open(fn, encoding="utf-8-sig", errors="replace").read()
            m = re.search(r'(?m)^\s*path\s*=\s*"([^"]+)"', txt)
            if m:
                raw = m.group(1)
        except Exception:
            raw = None
        if not raw:
            # 没有 path= 时按文件名猜：mod/ugc_2800380626.mod → workshop/394360/2800380626
            stem = os.path.splitext(os.path.basename(rel))[0]
            mid = re.sub(r"^ugc_", "", stem)
            for b in _mod_search_bases():
                c = os.path.join(b, mid)
                if os.path.isdir(c):
                    raw = c
                    break
        p = _resolve_mod_path(raw, base) if raw else None
        if p and p not in out:
            out.append(p)
    _MOD_ORDER_CACHE["k"] = (sig, list(out))
    return out

# ---------------------------------------------------------------- _iter_mod_candidates / _find_mod_by_name

def _iter_mod_candidates(extra_roots=(), require_descriptor=False):
    """按优先级收集候选 mod 目录，yield (abspath, source)。

    顺序：已加载/指定 root → 启动器启用的 mod → 已加载/指定 root 的同级目录（自定义工作区下的多级 submod）
    → 本地 mod 目录 / Steam workshop（_mod_search_bases）。
    """
    seen = set()

    def _emit(p, src, must_desc=False):
        if not p:
            return None
        try:
            ab = os.path.abspath(p)
        except Exception:
            return None
        key = os.path.normcase(ab)
        if key in seen or not os.path.isdir(ab):
            return None
        if must_desc and not os.path.isfile(os.path.join(ab, "descriptor.mod")):
            return None
        seen.add(key)
        return (ab, src)

    roots_and_extra = []
    for r in (state.roots() or []):
        if r:
            roots_and_extra.append((r, "loaded"))
    for r in (extra_roots or ()):
        if r:
            roots_and_extra.append((r, "extra"))

    for r, src in roots_and_extra:
        item = _emit(r, src, must_desc=False)
        if item:
            yield item

    for p in _enabled_mod_order():
        item = _emit(p, "launcher", must_desc=False)
        if item:
            yield item

    # 同级目录扫描（S8：独立重启自定义目录下的 submod 时，发现同级父/祖父 mod）
    parent_seen = set()
    for r, _ in roots_and_extra:
        try:
            ab = os.path.abspath(r)
            if is_under_game(ab):
                continue
            parent = os.path.dirname(ab)
            pkey = os.path.normcase(parent)
            if not parent or pkey in parent_seen or parent == os.path.dirname(parent) or not os.path.isdir(parent):
                continue
            parent_seen.add(pkey)
            for d in sorted(os.listdir(parent)):
                item = _emit(os.path.join(parent, d), "sibling", must_desc=True)
                if item:
                    yield item
        except Exception:
            continue

    for base in _mod_search_bases():
        b_norm = base.replace("\\", "/").lower()
        src = "workshop" if "/steamapps/workshop/" in b_norm else "local"
        try:
            for d in os.listdir(base):
                item = _emit(os.path.join(base, d), src, must_desc=require_descriptor)
                if item:
                    yield item
        except Exception:
            continue


def _find_mod_by_name(name, extra_roots=()):
    """按 mod 名（descriptor 里的 name）找目录。

    查找顺序：已加载 root → 启动器启用 → 同级目录 → 本地 mod 与 Steam workshop。**不写死盘符。**
    """
    want = (name or "").strip().lower()
    if not want:
        return None
    cands = [p for p, _ in _iter_mod_candidates(extra_roots=extra_roots, require_descriptor=False)]
    # 先按 descriptor name= 精确匹配，避免被同级无关文件夹名截走
    for p in cands:
        d = _mod_descriptor(p)
        if d["name"] and d["name"].strip().lower() == want:
            return p
    # 再允许目录名直接等于 mod 名
    for p in cands:
        if os.path.basename(p.rstrip("\\/")).lower() == want:
            return p
    return None


def discover_mods():
    """列出所有已识别的非原版 mod（供新建 submod 向导选择依赖等使用）。"""
    loaded_keys = {os.path.normcase(os.path.abspath(r)) for r in (state.roots() or []) if r}
    launcher_keys = {os.path.normcase(os.path.abspath(p)) for p in _enabled_mod_order() if p}
    out = []
    for p, src in _iter_mod_candidates(require_descriptor=True):
        if is_under_game(p):
            continue
        desc = _mod_descriptor(p)
        dname = (desc.get("name") or "").strip()
        folder = os.path.basename(p.rstrip("\\/")) or p
        key = os.path.normcase(p)
        out.append({
            "name": dname or folder,
            "descriptor_name": dname,
            "folder": folder,
            "path": p,
            "readonly": is_readonly_mod(p),
            "loaded": key in loaded_keys,
            "in_launcher": key in launcher_keys,
            "source": src,
            "deps": list(desc.get("deps") or []),
        })
    return out

# ---------------------------------------------------------------- _mod_display_name

def _mod_display_name(p):
    """界面上显示用的名字：descriptor 的 name，拿不到就用目录名。"""
    try:
        n = (_mod_descriptor(p) or {}).get("name") or ""
        if n.strip():
            return n.strip()
    except Exception:
        pass
    return os.path.basename(os.path.abspath(p).rstrip("\\/")) or p

# ---------------------------------------------------------------- _mod_dep_chain

def _mod_dep_chain(r, depth=3):
    """从一个 mod 往上走 dependencies，返回 [最父, ..., 自己]（不含原版）。

    **所有**能定位到的父依赖都收进来，不只第一条。
    只跟第一条会丢层：雪绒拓展依赖 muvluvCN + muvluvCNsub，关掉「跟随启动器」时
    以前只找到 CN，链变成 [原版, CN, 雪绒拓展]，少了 CNsub。

    walk 递归完父依赖之后才 append 自己，所以结果天然是「所有祖先在前，自己在最后」。
    带 seen 防环（mod 之间互相 dependencies 的情况真的存在）。
    """
    order = []
    seen = set()

    def walk(cur, d):
        if d <= 0 or not cur:
            return
        ab = os.path.abspath(cur)
        if ab in seen:
            return
        seen.add(ab)
        desc = _mod_descriptor(ab)
        for dep in desc["deps"]:
            p = _find_mod_by_name(dep, extra_roots=[r, ab] + order)
            if p:
                walk(p, d - 1)
        if ab not in order:
            order.append(ab)

    walk(r, depth)
    return order

# ---------------------------------------------------------------- mod_layers

def mod_layers(root=None, depth=3):
    """返回叠加链，从最父到最子：[原版, 父 mod, 子 mod]
    HOI4 语义：后加载的覆盖先加载的；replace_path 的目录是整体替换。"""
    root = _pick(root)
    try:
        _ck = (os.path.abspath(root or ""), tuple(os.path.abspath(r) for r in state.roots()),
               bool(state.options().get("follow_deps", True)),
               bool(state.options().get("follow_launcher", False)))
        _hit = _LAYERS_CACHE.get(_ck)
        if _hit:
            return list(_hit)
    except Exception:
        _ck = None
    # playset 语义：启动时给了多个 --mod（按启动器里的加载顺序），就按它们的顺序叠加，
    # 后面的覆盖前面的。这比只靠 descriptor 的 dependencies 更忠实于启动器的实际行为
    # （很多 mod 根本不写 dependencies）。
    # 但每个 root 的 dependencies 仍然要展开并前置——否则「先加父 mod 再加子 mod」
    # 时子 mod 依赖的中间层会丢，链会断开成 [原版, 父, 子]，中间那层的数据全读不到。
    if len(state.roots()) > 1:
        chain, tails = [], []
        _fdep = state.options().get("follow_deps", True)
        for _r in state.roots():
            d = _mod_dep_chain(_r, depth) if _fdep else [os.path.abspath(_r)]
            if not d:
                continue
            tails.append(d[-1])
            for ab in d[:-1]:
                if ab not in chain:
                    chain.append(ab)
        for ab in tails:
            if ab not in chain:
                chain.append(ab)
        if root and os.path.abspath(root) not in chain:
            for ab in _mod_dep_chain(root, depth):
                if ab not in chain:
                    chain.append(ab)
        if state.game() and os.path.abspath(state.game()) not in chain:
            chain.insert(0, os.path.abspath(state.game()))
        try:
            if _ck:
                _LAYERS_CACHE[_ck] = list(chain)
        except Exception:
            pass
        return chain

    # v1.23.45：先按**启动器里的真实加载顺序**铺一层底，再用 dependencies 补漏。
    #
    # 游戏只认 dlc_load.json 的顺序，dependencies 不进加载链。所以：
    #   · 自己在启动器里 → 排在自己前面的那些 mod 都是前置
    #   · 自己不在启动器里（本地新做的 submod）→ 已启用的整套都是它的底
    # 只跟 dependencies 会丢中间层（CNsub 就是被这么丢掉的）。
    base_chain = []
    _ab_root = os.path.abspath(root) if root else ""
    # 原版（游戏目录）不能挂 mod 前缀，否则「只看原版」会变成「原版 + 一堆 mod」
    _is_vanilla = bool(_ab_root and state.game() and
                       os.path.abspath(_ab_root) == os.path.abspath(state.game()))
    if _ab_root and not _is_vanilla and state.options().get("follow_launcher", False):
        # 注意：这里要**保留自己**再切片。先把自己剔掉会让 `in _order` 永远为假，
        # 于是「排在自己前面」退化成「全部已启用」——雪绒拓展就会跑到 CNsub 前面。
        _order = []
        for p in _enabled_mod_order():
            try:
                ap = os.path.abspath(p)
            except Exception:
                continue
            if ap not in _order:
                _order.append(ap)
        if _order:
            if _ab_root in _order:
                base_chain = _order[:_order.index(_ab_root)]
            else:
                base_chain = list(_order)

    # dependencies：把图谱里**所有**能定位到的祖先都收进来（父在前），不只第一条。
    # 以前这里是内联的一份「只取第一条」的循环，跟 _mod_dep_chain 重复且不同步——
    # 改 _mod_dep_chain 时单 root 分支完全不受影响，雪绒拓展就一直少一层 CNsub。
    dep_chain = (_mod_dep_chain(root, depth)
                 if (root and state.options().get("follow_deps", True)) else [])

    chain = list(base_chain)
    for ab in dep_chain:
        if ab not in chain:
            chain.append(ab)
    # 自己是最后一层（最子上层），必须排在末尾
    if _ab_root:
        if _ab_root in chain:
            chain.remove(_ab_root)
        chain.append(_ab_root)
    if state.game() and os.path.abspath(state.game()) not in chain:
        chain.insert(0, os.path.abspath(state.game()))
    try:
        if _ck:
            _LAYERS_CACHE[_ck] = list(chain)
    except Exception:
        pass
    return chain

# ---------------------------------------------------------------- _layers_find

def _layers_find(rel, layers):
    """按 HOI4 语义在叠加链里找文件：replace_path 的目录整体替换，其余逐文件覆盖。
    返回 (绝对路径 or None, 来源 root)。"""
    if not layers:
        return None, None
    rel_n = rel.replace(chr(92), "/").lstrip("/")
    # 判断这条路径是否落在某个 mod 的 replace_path 目录下
    replace_at = None
    for r in reversed(layers):
        for rp in _mod_descriptor(r)["replace"]:
            rp_n = rp.replace("\\", "/").strip("/")
            if rp_n and (rel_n == rp_n or rel_n.startswith(rp_n + "/")):
                replace_at = r
                break
        if replace_at:
            break
    search = [replace_at] if replace_at else list(reversed(layers))
    for r in search:
        p = os.path.join(r, rel_n.replace("/", os.sep))
        if os.path.exists(p):
            return p, r
    return None, None

# ---------------------------------------------------------------- _replace_owner

def _replace_owner(mod_root, sub):
    """某个目录被哪一层的 replace_path 独占接管。没有则返回 None。

    HOI4 的 replace_path 语义：声明后该目录只从这一层读，其他 mod（含更后加载的）
    在这一目录下的文件全部被忽略。所以想改这类目录，必须写进声明它的那一层。
    """
    norm = (sub or "").replace("\\", "/").strip("/").lower()
    if not norm:
        return None
    for base in reversed(mod_layers(mod_root) or []):
        if not base:
            continue
        try:
            desc = _mod_descriptor(base)
        except Exception:
            continue
        for rp in (desc.get("replace") or []):
            r = (rp or "").replace("\\", "/").strip("/").lower()
            if not r:
                continue
            if norm == r or norm.startswith(r + "/"):
                return base
    return None

# ---------------------------------------------------------------- _top_mod

def _top_mod(root=None):
    """链顶那个可写的 mod 目录（跳过原版）。

    优先用传入的 root 解析叠加链，再退回全局 ROOTS。
    只看 ROOTS 的写法在脚本直接调用时会因为 state.roots() 为空而误报
    「找不到可写的 mod 目录」，哪怕传入的 root 完全可写。
    """
    if root:
        lay = mod_layers(root) or [root]
        cand = lay[-1] if lay else root
        if cand and not is_under_game(cand):
            return cand
    for r in (state.roots() or []):
        lay = mod_layers(r) or [r]
        cand = lay[-1] if lay else r
        if cand and not is_under_game(cand):
            return cand
    return None

# ---------------------------------------------------------------- write_base

def write_base(mod_root, sub):
    """写某目录下的文件时应该写到哪一层。

    返回 (base, why)：
      base = 目标 mod 根目录
      why  = "replace_path"（被某层独占，必须写进去）或 "top"（写链顶）

    没有 replace_path 接管时写链顶，才有「子 mod 覆盖父 mod」的效果；
    有 replace_path 接管时写链顶反而不会生效，必须写进接管层。
    """
    owner = _replace_owner(mod_root, sub)
    if owner:
        return owner, "replace_path"
    # 和 _country_tags_write_base 一样：优先用传入的 mod_root，
    # 全局 ROOTS 为空时（脚本调用、world_create 编排）依然能找到链顶。
    top = None
    if mod_root:
        lay = mod_layers(mod_root) or [mod_root]
        cand = lay[-1] if lay else mod_root
        if cand and not is_under_game(cand):
            top = cand
    if not top:
        for r in (state.roots() or []):
            lay = mod_layers(r) or [r]
            cand = lay[-1] if lay else r
            if cand and not is_under_game(cand):
                top = cand
    return top, "top"

# ---------------------------------------------------------------- is_under_game

def is_under_game(p):
    try:
        p = os.path.abspath(p or "")
        g = os.path.abspath(state.game() or "")
        return g and (p == g or p.startswith(g + os.sep))
    except Exception:
        return False


def is_readonly_mod(p):
    """原版目录和创意工坊目录都不该被写（与门面 `_is_readonly_root` 共用）。"""
    ab = os.path.abspath(p or "")
    if not ab:
        return False
    if is_under_game(ab):
        return True
    return "/steamapps/workshop/" in ab.replace("\\", "/").lower()


def detect_game_version(game_dir=None):
    """从游戏目录 launcher-settings.json 读取主版本号（如 '1.19.*'），读不到回退 '1.19.*'。"""
    gd = game_dir or state.game()
    if gd:
        p = os.path.join(gd, "launcher-settings.json")
        if os.path.isfile(p):
            try:
                obj = json.loads(_read_text(p))
                for key in ("rawVersion", "version"):
                    raw = str(obj.get(key) or "")
                    m = re.search(r"(\d+)\.(\d+)", raw)
                    if m:
                        return "%s.%s.*" % (m.group(1), m.group(2))
            except Exception:
                pass
    return "1.19.*"

def _out_path(path):
    """输出模式下把 mod 内的路径映射到 output/<mod名>/<相对路径>。
    不在任何 mod 内的路径（新建文件等）保持原样。"""
    if not state.output_mode():
        return path
    try:
        ab = os.path.abspath(path)
        for r in state.roots():
            rab = os.path.abspath(r)
            if ab == rab:
                continue
            if ab.startswith(rab + os.sep):
                rel = os.path.relpath(ab, rab)
                dst = os.path.join(state.output_root(), os.path.basename(rab.rstrip("\\/")), rel)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                return dst
    except Exception:
        pass
    return path



def _out_read_path(path):
    """读取时优先看输出目录：这样开了输出模式改完立刻能看到效果，源文件依然不动。"""
    if not state.output_mode():
        return path
    try:
        ab = os.path.abspath(path)
        for r in state.roots():
            rab = os.path.abspath(r)
            if ab == rab:
                continue
            if ab.startswith(rab + os.sep):
                rel = os.path.relpath(ab, rab)
                cand = os.path.join(state.output_root(), os.path.basename(rab.rstrip("\\/")), rel)
                if os.path.exists(cand):
                    return cand
    except Exception:
        pass
    return path



def _layer_files(rel_dir, layers, exts=(".txt",)):
    """按叠加链收集某个目录下的文件。
    - 某层声明了 replace_path 覆盖该目录时：屏蔽该层之下（含原版），保留该层及其上全部子层
    - 从链尾（最顶层子 mod）往链首收集，同名文件子层优先覆写下层
    返回 (文件路径列表, 是否存在 replace_path 截断)"""
    from collections import OrderedDict
    rel_n = rel_dir.replace(chr(92), "/").strip("/")
    layers_list = list(layers or [])
    repl = None
    for r in reversed(layers_list):
        for rp in _mod_descriptor(r)["replace"]:
            if rp.replace(chr(92), "/").strip("/") == rel_n:
                repl = r
                break
        if repl:
            break
    if repl:
        try:
            scan = list(reversed(layers_list[layers_list.index(repl):]))
        except ValueError:
            scan = [repl]
    else:
        scan = list(reversed(layers_list))
    seen = OrderedDict()
    for r in scan:
        dpath = os.path.join(r, rel_n.replace("/", os.sep))
        if not os.path.isdir(dpath):
            continue
        try:
            names = sorted(os.listdir(dpath))
        except Exception:
            continue
        for fn in names:
            if fn.lower().endswith(exts) and fn not in seen:
                seen[fn] = os.path.join(dpath, fn)
    return list(seen.values()), bool(repl)


# ---- P0-3 B0：带 BOM 的读写（依赖 _out_path，所以放在 paths 而不是 text）----
def _read_bom_text(path):
    path = _out_read_path(path)          # 输出模式下读到的是「改过的版本」
    raw = io.open(path, "rb").read()
    has_bom = raw.startswith(b"\xef\xbb\xbf")
    return raw.decode("utf-8-sig", "replace"), has_bom



def _write_bom_text(path, text, has_bom):
    data = text.encode("utf-8")
    if has_bom:
        data = b"\xef\xbb\xbf" + data
    target = _out_path(path)             # 输出模式下写到 output/，源文件不动
    os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
    _atomic_write(target, data)


# ---------------------------------------------------------------- analyze_layer_chain (7-2)
_CHAIN_SKIP_DIRS = {
    ".git", ".svn", ".hg", "__pycache__", "cache", "tmp",
    "output", "backup", "backups", ".xr_backups",
}
_CHAIN_SKIP_FILES = {"descriptor.mod", "thumbnail.png"}
_CHAIN_SKIP_EXTS = (".bak", ".tmp", ".pyc", ".log")


def invalidate_chain_cache():
    """清空叠加链文件索引缓存，文件写入或切换层后调用。"""
    _CHAIN_SCAN_CACHE.clear()


def _walk_layer_files(layer_dir):
    """扫描单层模组目录，返回 [(rel_display, size), ...]（跳过备份与隐藏元数据目录）。"""
    ab = os.path.abspath(layer_dir or "")
    if not os.path.isdir(ab):
        return []
    out = []
    for cur, dirs, files in os.walk(ab, topdown=True):
        dirs[:] = sorted(
            d for d in dirs
            if not d.startswith(".") and d.lower() not in _CHAIN_SKIP_DIRS
        )
        at_root = (os.path.abspath(cur) == ab)
        for fn in sorted(files):
            low = fn.lower()
            if at_root and low in _CHAIN_SKIP_FILES:
                continue
            if low.endswith(_CHAIN_SKIP_EXTS):
                continue
            full = os.path.join(cur, fn)
            rel = os.path.relpath(full, ab).replace("\\", "/")
            try:
                sz = os.path.getsize(full)
            except Exception:
                sz = 0
            out.append((rel, sz))
    return out


def _build_chain_index(layers):
    """复用 mod_layers 与 _mod_descriptor 解析整条叠加链的文件覆盖与 replace_path 屏蔽关系。"""
    norm_layers = [os.path.abspath(r) for r in (layers or []) if r and os.path.isdir(r)]
    layer_meta = []
    rp_rules = []
    file_buckets = {}

    for idx, ab in enumerate(norm_layers):
        desc = _mod_descriptor(ab)
        rpaths = []
        rseen = set()
        for rp in (desc.get("replace") or []):
            rp_n = (rp or "").replace("\\", "/").strip("/")
            rp_l = rp_n.lower()
            if rp_l and rp_l not in rseen:
                rseen.add(rp_l)
                rpaths.append(rp_n)
                rp_rules.append({
                    "id": "%d:%s" % (idx, rp_l),
                    "owner_idx": idx,
                    "owner_name": _mod_display_name(ab),
                    "owner_path": ab,
                    "path": rp_n,
                    "_low": rp_l,
                    "own_files": 0,
                    "blocked_total": 0,
                    "blocked_unique": 0,
                    "blocked_files": [],
                    "_blocked_rels": set(),
                })
        files = _walk_layer_files(ab)
        layer_meta.append({
            "index": idx,
            "order": idx + 1,
            "name": _mod_display_name(ab),
            "folder": os.path.basename(ab.rstrip("\\/")) or ab,
            "path": ab,
            "deps": list(desc.get("deps") or []),
            "replace_paths": rpaths,
            "file_count": len(files),
            "win_count": 0,
            "override_count": 0,
            "overridden_count": 0,
            "blocked_others_count": 0,
            "blocked_self_count": 0,
        })
        for rel, sz in files:
            rk = rel.lower()
            b = file_buckets.get(rk)
            if b is None:
                b = {"rel": rel, "hits": []}
                file_buckets[rk] = b
            b["hits"].append((idx, rel, sz))

    # 让 replace_path 同名路径下层也有清晰归属；按 (rp_low, rule_idx) 查匹配
    entries = []
    dir_counts = {}
    for rk in sorted(file_buckets):
        bucket = file_buckets[rk]
        hits = bucket["hits"]
        rel_disp = hits[-1][1]
        present_map = {h[0]: h for h in hits}

        # 找所有命中此路径的 replace_path 规则（按层级从低到高）
        matched_rules = [
            rl for rl in rp_rules
            if rk == rl["_low"] or rk.startswith(rl["_low"] + "/")
        ]
        for rl in matched_rules:
            r_idx = rl["owner_idx"]
            if r_idx in present_map:
                rl["own_files"] += 1
            for h_idx, h_rel, _ in hits:
                if h_idx < r_idx:
                    rl["blocked_total"] += 1
                    if rk not in rl["_blocked_rels"]:
                        rl["_blocked_rels"].add(rk)
                        rl["blocked_unique"] += 1
                    if len(rl["blocked_files"]) < 500:
                        rl["blocked_files"].append({
                            "rel": h_rel,
                            "from_idx": h_idx,
                            "from_name": layer_meta[h_idx]["name"],
                        })

        win_rule = matched_rules[-1] if matched_rules else None
        if win_rule is not None:
            rep_idx = win_rule["owner_idx"]
            winner_idx = rep_idx if rep_idx in present_map else None
        else:
            winner_idx = hits[-1][0]

        if winner_idx is not None:
            layer_meta[winner_idx]["win_count"] += 1

        sources = []
        has_blocked = False
        has_shadow_above = False
        for h_idx, h_rel, sz in hits:
            if win_rule is not None:
                rep_idx = win_rule["owner_idx"]
                if h_idx == winner_idx:
                    st = "winner"
                elif h_idx < rep_idx:
                    st = "blocked"
                    has_blocked = True
                    layer_meta[rep_idx]["blocked_others_count"] += 1
                    layer_meta[h_idx]["blocked_self_count"] += 1
                else:
                    st = "shadow_above"
                    has_shadow_above = True
            else:
                if h_idx == winner_idx:
                    st = "winner"
                else:
                    st = "overridden"
                    layer_meta[h_idx]["overridden_count"] += 1
            sources.append({
                "layer": h_idx,
                "order": h_idx + 1,
                "name": layer_meta[h_idx]["name"],
                "rel": h_rel,
                "size": sz,
                "state": st,
            })

        if win_rule is None and len(hits) > 1:
            layer_meta[winner_idx]["override_count"] += 1

        if has_blocked or (win_rule is not None and winner_idx is None):
            status = "blocked"
        elif has_shadow_above:
            status = "blocked"
        elif len(hits) > 1:
            status = "overridden"
        else:
            status = "unique"

        parts = rel_disp.split("/")
        top_dir = "/".join(parts[:2]) if len(parts) > 2 else (parts[0] if len(parts) > 1 else "(root)")
        dir_counts[top_dir] = dir_counts.get(top_dir, 0) + 1

        entries.append({
            "rel": rel_disp,
            "rk": rk,
            "dir": top_dir,
            "status": status,
            "winner": winner_idx,
            "winner_order": (winner_idx + 1) if winner_idx is not None else None,
            "winner_name": layer_meta[winner_idx]["name"] if winner_idx is not None else "",
            "replace_by": {
                "layer": win_rule["owner_idx"],
                "order": win_rule["owner_idx"] + 1,
                "name": win_rule["owner_name"],
                "path": win_rule["path"],
            } if win_rule is not None else None,
            "sources": sources,
        })

    clean_rules = []
    for rl in rp_rules:
        clean_rules.append({
            "id": rl["id"],
            "owner_idx": rl["owner_idx"],
            "owner_order": rl["owner_idx"] + 1,
            "owner_name": rl["owner_name"],
            "owner_path": rl["owner_path"],
            "path": rl["path"],
            "own_files": rl["own_files"],
            "blocked_total": rl["blocked_total"],
            "blocked_unique": rl["blocked_unique"],
            "blocked_files": rl["blocked_files"],
        })

    top_dirs = sorted(
        [{"dir": k, "count": v} for k, v in dir_counts.items()],
        key=lambda x: (-x["count"], x["dir"]),
    )
    return {
        "layers": layer_meta,
        "replace_rules": clean_rules,
        "entries": entries,
        "top_dirs": top_dirs,
    }


def analyze_layer_chain(layers=None, query="", kind="interacted", dir_filter="",
                        layer_filter="", replace_filter="", limit=200, refresh=False):
    """分析当前叠加链：每层顺序、文件生效与覆盖来源、每条 replace_path 屏蔽清单。"""
    if layers is None:
        layers = mod_layers(None) or ([state.game()] if state.game() else [])
    norm_layers = [os.path.abspath(r) for r in (layers or []) if r and os.path.isdir(r)]
    ck = tuple(
        (r, tuple(_mod_descriptor(r).get("replace") or []))
        for r in norm_layers
    )
    if refresh or ck not in _CHAIN_SCAN_CACHE:
        if len(_CHAIN_SCAN_CACHE) >= 4:
            _CHAIN_SCAN_CACHE.clear()
        _CHAIN_SCAN_CACHE[ck] = _build_chain_index(norm_layers)
    idx = _CHAIN_SCAN_CACHE[ck]

    q = (query or "").strip().lower()
    df = (dir_filter or "").replace("\\", "/").strip("/").lower()
    rf = (replace_filter or "").replace("\\", "/").strip("/").lower()
    lf = None
    if str(layer_filter).strip() != "":
        try:
            lf = int(layer_filter)
        except Exception:
            lf = None
    k = (kind or "interacted").strip().lower()
    lim = max(1, min(int(limit or 200), 1000))

    entries = idx["entries"]
    matched = []
    cnt_overridden = 0
    cnt_blocked = 0
    for e in entries:
        st = e["status"]
        if st == "overridden":
            cnt_overridden += 1
        elif st == "blocked":
            cnt_blocked += 1

        if k == "interacted" and st not in ("overridden", "blocked"):
            continue
        if k == "overridden" and st != "overridden":
            continue
        if k == "blocked" and st != "blocked":
            continue
        if k == "non_vanilla":
            w = e["winner"]
            if w is None or is_under_game(idx["layers"][w]["path"]):
                continue

        rk = e["rk"]
        if q and q not in rk:
            continue
        if df and not (rk == df or rk.startswith(df + "/")):
            continue
        if rf and not (rk == rf or rk.startswith(rf + "/")):
            continue
        if lf is not None and not any(s["layer"] == lf for s in e["sources"]):
            continue
        matched.append(e)

    # 仅返回前端所需字段，剔除内部 rk 键
    files_out = [{k2: v2 for k2, v2 in e.items() if k2 != "rk"} for e in matched[:lim]]
    return {
        "layers": idx["layers"],
        "replace_rules": idx["replace_rules"],
        "files": files_out,
        "total_files": len(entries),
        "matched_count": len(matched),
        "overridden_count": cnt_overridden,
        "blocked_count": cnt_blocked,
        "top_dirs": idx["top_dirs"][:40],
    }


def ensure_writable_file(root, sub, basename):
    """确保某子目录下的目标文件落入可写顶层（不存在时从叠加链自动单文件接管）。"""
    root = _pick(root)
    sub = (sub or "").replace("\\", "/").strip("/")
    basename = os.path.basename(basename or "")
    if not sub or not basename:
        return None, "参数不完整"

    top = None
    for r in (state.roots() or []):
        lay = mod_layers(r) or [r]
        cand = lay[-1] if lay else r
        if cand and not is_readonly_mod(cand):
            top = cand
    if not top and root:
        cand = _top_mod(root)
        if cand and not is_readonly_mod(cand):
            top = cand
    if not top:
        return None, "找不到可写的 mod 目录"

    owner = _replace_owner(root, sub)
    if owner and os.path.abspath(owner) != os.path.abspath(top):
        chain = [os.path.abspath(x) for x in (mod_layers(root) or []) if x]
        ab_top = os.path.abspath(top)
        ab_own = os.path.abspath(owner)
        if ab_own in chain and ab_top in chain and chain.index(ab_own) > chain.index(ab_top):
            nm = os.path.basename(owner.rstrip("\\/")) or owner
            return None, ("%s 被 %s 的 replace_path 独占，需要先在「诊断 → 目录写入目标」里"
                          "接管该目录（独占后只读那一层，单文件复制不生效）" % (sub, nm))

    rel = os.path.join(sub.replace("/", os.sep), basename)
    dst = os.path.join(top, rel)
    if os.path.exists(dst):
        return dst, "已存在"

    src = None
    for _b, d in (_layer_dirs(sub, root) or []):
        cand = os.path.join(d, basename)
        if os.path.isfile(cand):
            src = cand
            break
    if not src:
        return None, "叠加链里找不到 %s/%s" % (sub, basename)

    os.makedirs(os.path.dirname(dst) or top, exist_ok=True)
    try:
        shutil.copyfile(src, dst)
        invalidate_chain_cache()
    except Exception as e:
        return None, "复制失败：%s" % e
    return dst, "已从 %s 复制单个文件" % (os.path.basename(os.path.dirname(src)) or "父层")
