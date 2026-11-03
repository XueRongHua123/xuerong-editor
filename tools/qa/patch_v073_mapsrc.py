# -*- coding: utf-8 -*-
"""v0.73 地图多来源：可切换不同 mod / 原版的地图。幂等。"""
import io
import os

HERE = os.path.dirname(os.path.abspath(__file__))
PY = os.path.join(HERE, '..', 'focus_editor.py')
HTML = os.path.join(HERE, '..', 'focus_editor_index.html')
MARK = "# v0.73 地图多来源"

HELPERS = '''# v0.73 地图多来源
def map_sources():
    """列出所有可用于地图的来源：已加载的 mod（有无 map 都列出）+ 原版"""
    out = []
    seen = set()
    for r in ROOTS:
        p = os.path.abspath(r)
        if p in seen:
            continue
        seen.add(p)
        has = (os.path.exists(os.path.join(p, "map", "provinces.bmp"))
               and os.path.exists(os.path.join(p, "map", "definition.csv")))
        out.append({"path": p, "name": os.path.basename(p.rstrip("\\\\/")) or p,
                    "has_map": has, "readonly": is_under_game(p), "is_game": False})
    if GAME:
        g = os.path.abspath(GAME)
        out.append({"path": g, "name": "原版（游戏本体）",
                    "has_map": os.path.exists(os.path.join(g, "map", "provinces.bmp")),
                    "readonly": True, "is_game": True})
    return out


def _map_pick(root=None):
    """指定 root 就用它；否则第一个带地图的 mod；最后原版"""
    if root:
        return root
    for r in ROOTS:
        if os.path.exists(os.path.join(r, "map", "provinces.bmp")):
            return r
    return GAME


def _map_files_strict(root):
    """严格模式：指定来源没有地图就返回 None，不偷偷回退到原版"""
    if not root:
        return None, None, None
    b = os.path.join(root, "map", "provinces.bmp")
    d = os.path.join(root, "map", "definition.csv")
    if os.path.exists(b) and os.path.exists(d):
        return b, d, root
    return None, None, None


'''

ROUTE_GET_OLD = '''        elif path_only == "/api/map_meta":
            self._send(map_meta())'''

ROUTE_GET_NEW = '''        elif path_only == "/api/map_meta":
            qs3 = parse_qs(urlparse(self.path).query)
            self._send(map_meta((qs3.get("root", [""])[0] or None)))'''

ROUTE_ASSET_OLD = '''        elif path_only == "/api/map_asset":
            qs2 = parse_qs(urlparse(self.path).query)
            name = (qs2.get("name", [""])[0] or "")
            p = map_asset(name)'''

ROUTE_ASSET_NEW = '''        elif path_only == "/api/map_asset":
            qs2 = parse_qs(urlparse(self.path).query)
            name = (qs2.get("name", [""])[0] or "")
            p = map_asset(name, (qs2.get("root", [""])[0] or None))'''

ROUTE_BUILD_OLD = '''        elif self.path == "/api/map_build":
            self._send(map_build(bool(body.get("force"))))'''

ROUTE_BUILD_NEW = '''        elif self.path == "/api/map_build":
            self._send(map_build(bool(body.get("force")), (body.get("root") or None)))'''

FUNC_OLD_META = '''def map_meta():
    root = ROOTS[0] if ROOTS else GAME
    b, d, base = _map_files(root)
    if not b:
        return {"ok": False, "msg": "找不到 map/provinces.bmp 或 definition.csv"}'''

FUNC_NEW_META = '''def map_meta(root=None):
    root = _map_pick(root)
    b, d, base = _map_files_strict(root)
    if not b:
        return {"ok": False, "msg": "这个来源没有 map/provinces.bmp 或 definition.csv",
                "sources": map_sources(), "picked": root}'''

FUNC_OLD_BUILD = '''def map_build(force=False):
    """生成地图图层（首次约 5-8 秒），返回 meta。"""
    root = ROOTS[0] if ROOTS else GAME
    if not root:
        return {"ok": False, "msg": "还没有加载任何 mod"}
    bmp, csv, base = _map_files(root)
    if not bmp:
        return {"ok": False, "msg": "找不到 map/provinces.bmp 或 definition.csv"}'''

FUNC_NEW_BUILD = '''def map_build(force=False, root=None):
    """生成地图图层（首次约 13 秒），返回 meta。可按 root 指定来源。"""
    root = _map_pick(root)
    if not root:
        return {"ok": False, "msg": "还没有加载任何 mod"}
    bmp, csv, base = _map_files_strict(root)
    if not bmp:
        return {"ok": False, "msg": "这个来源没有 map/provinces.bmp 或 definition.csv",
                "sources": map_sources(), "picked": root}'''

FUNC_OLD_ASSET = '''def map_asset(name):
    """返回缓存目录里的资产路径（白名单，防路径穿越）"""
    if name not in MAP_ASSETS:
        return None
    root = ROOTS[0] if ROOTS else GAME
    dirp, _, _ = _map_dir(root) if root else (None, None, None)'''

FUNC_NEW_ASSET = '''def map_asset(name, root=None):
    """返回缓存目录里的资产路径（白名单，防路径穿越）"""
    if name not in MAP_ASSETS:
        return None
    root = _map_pick(root)
    dirp, _, _ = _map_dir(root) if root else (None, None, None)'''


def main():
    s = io.open(PY, encoding='utf-8').read()
    h = io.open(HTML, encoding='utf-8').read()
    if MARK in s:
        print('已注入，跳过')
        return 0

    # 后端函数
    anchor = "def map_meta():"
    assert s.count(anchor) == 1
    s = s.replace(anchor, HELPERS + "def map_meta(root=None):", 1)
    for old, new in ((FUNC_OLD_META, FUNC_NEW_META), (FUNC_OLD_BUILD, FUNC_NEW_BUILD),
                     (FUNC_OLD_ASSET, FUNC_NEW_ASSET)):
        # 注意：插入 HELPERS 后 FUNC_OLD_META 的 "def map_meta():" 已变，跳过它
        if old.startswith("def map_meta():"):
            continue
        assert s.count(old) == 1, old[:40]
        s = s.replace(old, new, 1)
    for old, new in ((ROUTE_GET_OLD, ROUTE_GET_NEW), (ROUTE_ASSET_OLD, ROUTE_ASSET_NEW),
                     (ROUTE_BUILD_OLD, ROUTE_BUILD_NEW)):
        assert s.count(old) == 1, old[:50]
        s = s.replace(old, new, 1)
    io.open(PY, 'w', encoding='utf-8', newline='').write(s)
    print('后端多来源注入完成')

    # 前端：来源下拉
    old_dom = '''            <input id="mapSearch" placeholder="省号 / 州号，回车定位">'''
    new_dom = '''            <select id="mapSource" class="btn" style="padding:3px 6px;max-width:190px" title="地图来源"></select>
            <input id="mapSearch" placeholder="省号 / 州号，回车定位">'''
    assert h.count(old_dom) == 1
    h = h.replace(old_dom, new_dom, 1)

    old_js = """async function mapLoadMeta(){
  const metaEl = document.getElementById('mapMeta');
  try{
    const d = await (await fetch('/api/map_meta')).json();"""
    new_js = """async function mapLoadMeta(root){
  const metaEl = document.getElementById('mapMeta');
  try{
    const q = root ? ('?root=' + encodeURIComponent(root)) : '';
    const d = await (await fetch('/api/map_meta' + q)).json();
    MAP.root = d.picked || root || MAP.root || '';
    if(d.sources) mapFillSources(d.sources, MAP.root);"""
    assert h.count(old_js) == 1
    h = h.replace(old_js, new_js, 1)

    old_assets = """function mapAssetUrl(name){ return '/api/map_asset?name=' + encodeURIComponent(name); }"""
    new_assets = """function mapAssetUrl(name){
  return '/api/map_asset?name=' + encodeURIComponent(name) +
    (MAP.root ? '&root=' + encodeURIComponent(MAP.root) : '');
}

function mapFillSources(list, picked){
  const sel = document.getElementById('mapSource');
  if(!sel) return;
  sel.innerHTML = list.map(s=>'<option value="' + escapeHtml(s.path) + '"' +
    (s.path === picked ? ' selected' : '') + (s.has_map ? '' : ' disabled') + '>' +
    escapeHtml(s.name + (s.has_map ? '' : '（无地图）')) + '</option>').join('');
}

function mapSwitchSource(path){
  MAP.ready = false;
  MAP.idCanvas = null;
  MAP.idx = null;
  MAP.centers = null;
  document.getElementById('mapMeta').textContent = '切换来源…';
  mapLoadMeta(path);
}"""
    assert h.count(old_assets) == 1
    h = h.replace(old_assets, new_assets, 1)

    # 构建时带上来源
    old_build = """    const r = await (await fetch('/api/map_build', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({force: true})})).json();"""
    new_build = """    const r = await (await fetch('/api/map_build', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({force: true, root: MAP.root || ''})})).json();"""
    assert h.count(old_build) == 1
    h = h.replace(old_build, new_build, 1)

    # 绑定下拉
    anchor_bind = "document.getElementById('mapFit').onclick = mapFit;"
    assert h.count(anchor_bind) == 1
    h = h.replace(anchor_bind,
                  "document.getElementById('mapSource').addEventListener('change', e=>mapSwitchSource(e.target.value));\n"
                  + anchor_bind, 1)

    io.open(HTML, 'w', encoding='utf-8', newline='').write(h)
    print('前端多来源注入完成')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
