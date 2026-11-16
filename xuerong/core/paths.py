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

from xuerong import state
from xuerong.core.text import _atomic_write, _read_text

# ---------------------------------------------------------------- 缓存
_START_DATE_CACHE = {}
_DESC_CACHE = {}
_SEARCH_BASES_CACHE = {}
_MOD_ORDER_CACHE = {}
_LAYERS_CACHE = {}

# 应用目录（打包后是 exe 目录，源码运行是 work/）。由门面在 import 后写入；
# 没写就用本文件往上三级推导，保证 `python -c "import xuerong.core.paths"` 也能用。
APP_DIR = ""


def app_dir():
    if APP_DIR:
        return APP_DIR
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


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
    rs = state.roots()
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

# ---------------------------------------------------------------- _find_mod_by_name

def _find_mod_by_name(name, extra_roots=()):
    """按 mod 名（descriptor 里的 name）找目录。

    查找顺序：已加载的 root → 启动器里启用的（最可靠，游戏就是这么认的）→
    扫本地 mod 目录与各 Steam 库的 workshop。**不写死盘符。**
    """
    want = (name or "").strip().lower()
    if not want:
        return None
    cands = []
    for r in list(state.roots()) + list(extra_roots):
        if r:
            cands.append(os.path.abspath(r))
    cands.extend(_enabled_mod_order())
    for base in _mod_search_bases():
        try:
            for d in os.listdir(base):
                p = os.path.join(base, d)
                if os.path.isdir(p):
                    cands.append(p)
        except Exception:
            continue
    seen = set()
    for p in cands:
        if p in seen:
            continue
        seen.add(p)
        d = _mod_descriptor(p)
        if d["name"] and d["name"].strip().lower() == want:
            return p
        # 也允许目录名直接等于 mod 名
        if os.path.basename(p.rstrip("\\/")).lower() == want:
            return p
    return None

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
            p = _find_mod_by_name(dep, extra_roots=[r])
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
    - 某层声明了 replace_path 覆盖该目录时：只看那一层（整目录替换，不合并）
    - 否则从链尾往链首收集，同名文件子层优先
    返回 (文件路径列表, 是否被 replace_path 接管)"""
    from collections import OrderedDict
    rel_n = rel_dir.replace(chr(92), "/").strip("/")
    repl = None
    for r in reversed(layers or []):
        for rp in _mod_descriptor(r)["replace"]:
            if rp.replace(chr(92), "/").strip("/") == rel_n:
                repl = r
                break
        if repl:
            break
    scan = [repl] if repl else list(reversed(layers or []))
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
