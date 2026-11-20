# -*- coding: utf-8 -*-
"""国策树本地编辑器 MVP（Python 本地服务 + 浏览器 UI）

启动：
  python work/focus_editor.py
  python work/focus_editor.py --mod "<mod根目录>" [--mod "..."] [--port 8766]

功能：
- 选择/指定 mod 文件夹（多个 = 按加载顺序覆盖）；
- 可视化查看国策树（图标、前置、互斥、统计）；
- 拖动节点改 x/y、表单改前置/互斥、保存写回原文件（自动 .bak 备份）；
- 导出“覆盖包”ZIP（只含改动文件，解压覆盖到 mod 目录即可）。
"""
import io, os, re, json, zipfile, shutil, time, argparse, threading, webbrowser, sys, string, hashlib, colorsys, zlib
import subprocess
import urllib.request, urllib.error
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, unquote
import editor_i18n as i18n

FROZEN = getattr(sys, "frozen", False)
_HERE = os.path.dirname(os.path.abspath(__file__))

# ---- v2.0.0 拆模块：core 层从这里开始往 xuerong/ 迁（P0-2）----
# 只搬实现，不改行为；下面这些名字仍然可以直接调用（门面兼容）。
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
from xuerong import state as _state
from xuerong.state import (STATE_CATEGORIES, STATE_BUILDINGS, STATE_BUILDING_META,
                          PROV_BUILDING_META, RESOURCE_META, STATE_RESOURCES,
                          DECISION_SKIP, DECISION_SCALARS,
                          CHAR_TYPES, PORTRAIT_W, PORTRAIT_H, PORTRAIT_SMALL)
from xuerong.core import paths as _paths
from xuerong.core.text import (set_scalar, remove_block, braces_balanced, set_raw_block,
                               _first, _first_in, apply_modifier_props,
                               _strip_keep_len, strip_comments, brace_match, unq,
                               top_items, find_blocks, _atomic_write, _bom_for, _read_text)
from xuerong.core.paths import (_layer_dirs, _chain_layers, _start_date_for, pdx_user_dir,
                                _resolve_mod_path, _steam_libraries, _mod_search_bases,
                                _enabled_mod_order, _find_mod_by_name, _mod_display_name, _mod_descriptor,
                                _mod_dep_chain, mod_layers, _layers_find, _replace_owner,
                                _top_mod, write_base, is_under_game, is_readonly_mod,
                                detect_game_version, discover_mods,
                                analyze_layer_chain, invalidate_chain_cache,
                                _load_options, _layer_files, effective_layer_files,
                                unique_editor_filename,
                                _out_path, _out_read_path, _read_bom_text, _write_bom_text,
                                _save_options, _LAYERS_CACHE, _MOD_ORDER_CACHE)
from xuerong.core.i18n import ERR_RULES, classify_error
from xuerong.model.diagnose import (_cwt_rules, _cwt_te, _diag_character_unrecruited, _diag_decision_category, _diag_division_template_missing, _diag_gfx_missing, _diag_localisation_missing, _diag_map_format, _diag_oob_not_referenced, _diag_recruit_last_line, _diag_replace_refs, _diag_replace_risk, _diag_replace_stub, _diag_schema_character, _diag_schema_decision, _diag_schema_focus, _diag_schema_ideas, _diag_schema_unknown_field, _diag_tag_def_missing, _diag_tag_undefined, _finding, _gfx_names, _is_skip_block, _loc_keys, _looks_like_scripted, diagnose)
from xuerong.model.history import snapshot, backup, undo_last, redo_last
from xuerong.model.loc import save_loc, _write_loc, _loc_write_pairs
from xuerong.model.event import (_event_block, _event_fire_targets, event_graph,
                               event_space_create, event_space_delete, event_detail,
                               event_edit, load_events, save_event, add_event, delete_event)
from xuerong.model.tech import (_looks_tech, load_techs, _tech_block_range,
                              _tech_coord_token, tech_move, load_country_techs,
                              country_tech_toggle, tech_tree_graph, country_techs_payload,
                              validate_tech_script, save_tech, add_tech, delete_tech, tech_link)
from xuerong.model.equipment import (load_equipment, _equip_locate, equipment_detail,
                                    equipment_edit, equipment_delete, equipment_list,
                                    save_equipment, add_equipment, delete_equipment)
from xuerong.model.idea import (_looks_like_idea, _add_idea, load_ideas,
                               load_country_ideas, country_idea_toggle,
                               country_ideas_payload, save_idea, add_idea, delete_idea)
from xuerong.model.decision import (load_decisions, decisions_payload, _dec_write_base,
                                    _dec_find, _dec_category_register,
                                    decision_add, decision_set, decision_delete)
from xuerong.model.world import (
    world_create, load_country_tags, _country_tags_write_base, country_tag_refs,
    country_tag_add, country_tag_delete, country_history_create,
    _bookmark_write_base, _bookmark_date, _bookmark_country_block, _game_language,
    _bookmark_loc, bookmark_add,
    _units_write_base, _units_files, _parse_division_template, _parse_division, load_units,
    _oob_files, _tpl_render, template_add, unit_add,
    _loc_need_keys, _loc_defined_set, loc_missing, loc_generate,
    mod_home, create_mod, _centroids_from_map)
from xuerong.model.focus import (load_focus, parse_focus_like, parse_simple_fx,
                                 resolve_positions, _focus_refs, load_completed_focuses,
                                 focus_complete_add, focus_complete_delete, focus_tree_graph,
                                 focus_tree_list, build_blocks, save_focus, _find_tree_span,
                                 add_focus, delete_focus)
from xuerong.model.character import (portrait_import, load_characters, _char_write_base,
                                    character_add, character_set, character_delete,
                                    characters_payload)
from xuerong.model.country import _country_hist_file, _country_hist_write_base, _politics_write
from xuerong.model.object_diff import analyze_objects, invalidate_object_cache
from xuerong.model.game_verify import (cancel_game_verify, get_verify_status,
                                        recover_pending_dlc_load, start_game_verify)
from xuerong.model.mod_publish import export_publish, preview_publish
from xuerong.model import state as _m_state
from xuerong.model.state import (
    state_save, state_create, state_province_edit, state_refine_preview, state_refine_apply,
    state_apply_buildings, state_detail, _state_file_for, _state_owner_effective, states_payload,
    _state_prov_list, _state_fields_from, _states_dir_for_write, state_is_coastal, _state_locate,
    _state_history_range, _set_building, _set_prov_building, _set_owner_all, _set_victory_points,
    _find_state_of_prov, _drop_in_scope, _set_in_scope, _coastal_provinces, _free_state_id,
    _insert_pos, _set_resource,
)
from xuerong.model import map as _m_map
from xuerong.model.map import (
    _map_files, _map_key, _map_dir, _map_files_layered, _map_files_strict,
    _map_pick, _map_ids_from_cache, _prov_state_map, _prov_type_map, map_meta,
    map_sources, map_analysis, map_asset, map_cache_clear, map_integrity,
    map_prov_neighbors, map_edit_state, map_repair_preview, map_repair_ghost, map_generate,
    map_repair_cross, map_merge_preview, map_merge_apply, _scan_cross, _save_point_undo,
    map_edit_begin, map_edit_dab, map_edit_commit, map_edit_undo, map_edit_redo,
    _apply_point_undo, _load_point_undo, _terrain_index_map, _terrain_tex_map, _terrain_index_trusted,
    _terrain_type_to_index, _terrain_common, _terrain_apply, _terrain_colors, terrain_types,
    prov_terrain_set, prov_terrain_batch, prov_terrain_by_type, terrain_paint, height_paint,
    height_sample, _hillshade_mask, _apply_hillshade, _apply_terrain_texture, _render_terrain,
    _hsv_hex, river_paint, river_undo, river_stats, river_preview,
    _def_rgb_kind, _line_pts, _build_rivers_png, map_build, _strategic_regions,
    _tag_fallback_color, _csv_path_for, _ensure_prov_rgb, _refine_load_ids, bmp_write_rect_8,
    bmp_info, bmp_read_rect, bmp_write_rect,
)
from xuerong.model.replace import (_REF_KEYWORDS, _REPLACE_NEVER_ADOPT,
                                 replace_ignore, replace_drop, replace_fix_all,
                                 _replace_ignored, _replace_ignore_all, _replace_ignore_key,
                                 _replace_collect, _replace_norm, _replace_ref_dir,
                                 _replace_adopt_block)
from xuerong.api import router as _router, routes_get, routes_post

_paths.APP_DIR = _HERE          # options.json 等仍写在 work/ 下，不跟着模块跑
_paths.set_root_picker(lambda: _map_pick(None))   # core 不认识 map 层，用钩子回注

# 贴图 / 图标 / 编码规范：实现在 xuerong/core/gfx.py 与 core/loc.py。
# 四个容器（SPRITE_MAP / ICONS / EQUIP_ICONS / TECH_ICONS）与 _GFX_CACHE / GFX_KINDS
# 都是 core 里的对象本体，这里 import 的是同一份 —— 门面不能再各 new 一个，
# 否则表会分裂成两份，图标全丢（state.py 的访问器靠对象身份）。
from xuerong.core.gfx import (                                    # noqa: E402
    GFX_KINDS, SPRITE_MAP, ICONS, EQUIP_ICONS, TECH_ICONS, _GFX_CACHE,
    set_snapshot_hook,
    parse_gfx_file, gfx_list, gfx_sprite_new, gfx_import, gfx_registered,
    gfx_missing, _gfx_collect, _gfx_refs, _gfx_texture_exists,
    all_goal_icons, icon_png, build_icons,
)
from xuerong.core.loc import missing_loc, _bom_issues                # noqa: E402

# snapshot 是 model 层的东西，core 不能 import model —— 启动期注入钩子。
set_snapshot_hook(snapshot)

# qa/ 目录的实现原来在门面与 model/diagnose.py 各写了一份（map/world 又各转发一次），
# 三处逻辑等价，已合并到 core.paths.qa_dir。门面不再保留这个名字——
# 需要的人直接从 core 取，少一层。
W = os.path.dirname(_HERE) if os.path.basename(_HERE).lower() == "work" else _HERE

# 版本号：打包时由 make_release.py 生成 _build_version.py 注入；源码运行则回退到 git tag
def _read_app_version():
    """打包时 make_release.py 生成 _version.txt 并用 --add-data 塞进 exe；
    源码运行时读同目录的文件，都没有则回退到 git tag。"""
    for _b in (getattr(sys, "_MEIPASS", ""), _HERE, os.getcwd()):
        try:
            _p = os.path.join(_b, "_version.txt") if _b else ""
            if _p and os.path.exists(_p):
                v = io.open(_p, encoding="utf-8").read().strip()
                if v:
                    return v
        except Exception:
            pass
    try:
        import subprocess as _sp
        return (_sp.run(["git", "describe", "--tags", "--abbrev=0"], cwd=_HERE,
                        capture_output=True, text=True, timeout=3).stdout.strip().lstrip("v")) or "dev"
    except Exception:
        return "dev"


APP_VERSION = _read_app_version()

REPO = "XueRongHua123/xuerong-editor"
DEFAULT_MOD = None
def _detect_game():
    cands = []
    env = os.environ.get("HOI4_GAME")
    if env:
        cands.append(env)
    for d in "CDEFGH":
        cands += [
            d + r":\SteamLibrary\steamapps\common\Hearts of Iron IV",
            d + r":\Program Files (x86)\Steam\steamapps\common\Hearts of Iron IV",
            d + r":\Steam\steamapps\common\Hearts of Iron IV",
        ]
    for c in cands:
        if os.path.isdir(c):
            return c
    return ""

DEFAULT_GAME = _detect_game()
# exe 模式：可写目录 = exe 所在目录；资源目录 = 打包解压目录
APP_DIR = os.path.dirname(sys.executable) if FROZEN else _HERE
RES_DIR = getattr(sys, "_MEIPASS", APP_DIR)
WORK = APP_DIR
BACKUP_DIR = os.path.join(WORK, "backups")
os.makedirs(BACKUP_DIR, exist_ok=True)
ICON_DIR = os.path.join(WORK, "icons")
os.makedirs(ICON_DIR, exist_ok=True)
GAME = DEFAULT_GAME
MASCOTS = [
    {"id": "card", "name": "经典", "file": "mascot_card.png", "thumb": "mascot_face.png"},
    {"id": "winter", "name": "冬装", "file": "mascot/winter.png", "thumb": "mascot/winter_thumb.png"},
    {"id": "running", "name": "运动", "file": "mascot/running.png", "thumb": "mascot/running_thumb.png"},
    {"id": "flowers", "name": "花田", "file": "mascot/flowers.png", "thumb": "mascot/flowers_thumb.png"},
    {"id": "classroom", "name": "教室", "file": "mascot/classroom.png", "thumb": "mascot/classroom_thumb.png"},
    {"id": "charm", "name": "邻桌小绒", "file": "mascot/charm.png", "thumb": "mascot/charm_thumb.png"},
    {"id": "cafe", "name": "咖啡店", "file": "mascot/cafe.png", "thumb": "mascot/cafe_thumb.png"},
    {"id": "snow", "name": "雪天", "file": "mascot/snow.png", "thumb": "mascot/snow_thumb.png"},
]
LANGS = ("zh", "en", "ja")
LANG_NAMES = {"zh": "中文", "en": "English", "ja": "日本語"}

# ---------------- HOI4 脚本工具 ----------------









# ---------------- 加载 mod 数据 ----------------
ROOTS = []
TREES = {}
TREE_ORDER = []
LOC = {}
CHANGED = {}   # abs file path -> rel path
SHARED_FOCUSES = []
EQUIPMENTS = {}
TECHS = {}
EVENTS = {}
MODULES = {}
ORGS = {}
HISTORY = {}   # abs file path -> {"undo": [snapshot], "redo": [snapshot]}
# P0-3 B1：LAST_FILE / HIST_DIR / 历史目录都搬到 xuerong/model/history.py
# 让 state 拿到同一批容器对象（之后谁改内容大家都看得见）
_state.bind_facade()
OPTIONS = _state.OPTIONS          # 容器，门面与 state 指向同一个 dict

def ensure_file_writable(root, sub, basename):
    """确保 mod 里某个文件可写，返回 (目标路径, 说明) 或 (None, 错误)。

    两种情形：

    1. 目录已经被某一层 replace_path 独占（比如 muvluvCN 占了 history/states）
       → 那一层才是游戏真正读的地方，必须整目录接管，单文件复制没用。
       返回第一个元素仍是想写的路径，第二个元素说明需要先接管。

    2. 目录没有被独占（原版环境都是这种）
       → 只把要改的那一个文件复制到自己的 mod，同名覆盖。
       这样原版其余文件照常生效，不会因为 replace_path 把整个目录清空。
    """
    root = _map_pick(root)
    sub = (sub or "").replace("\\", "/").strip("/")
    basename = os.path.basename(basename or "")
    if not sub or not basename:
        return None, "参数不完整"

    top = None
    for r in (ROOTS or []):
        lay = mod_layers(r) or [r]
        cand = lay[-1] if lay else r
        if cand and not is_under_game(cand):
            top = cand
    if not top and root:
        cand = _top_mod(root)
        if cand and not is_under_game(cand):
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

    # 找源文件：沿 _layer_dirs（已按 replace_path 截断）从子到父找第一个存在它的层
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
        import shutil as _sh
        _sh.copyfile(src, dst)
    except Exception as e:
        return None, "复制失败：%s" % e
    return dst, "已从 %s 复制单个文件" % (os.path.basename(os.path.dirname(src)) or "父层")








def load_game_loc():
    for lang in ("english", "simp_chinese"):
        d = os.path.join(GAME, "localisation", lang)
        if not os.path.isdir(d):
            continue
        line_re = re.compile(r'^\s*([A-Za-z0-9_.\-]+):\d*\s+"(.*)"\s*$')
        for dirpath, _, files in os.walk(d):
            for fn in files:
                if not fn.endswith(".yml"):
                    continue
                try:
                    for ln in io.open(os.path.join(dirpath, fn), encoding="utf-8-sig", errors="replace").read().splitlines():
                        m = line_re.match(ln)
                        if m:
                            LOC[m.group(1)] = m.group(2)
                except Exception:
                    pass





LOAD_PROGRESS = {
    "active": False,      # 有没有加载在跑
    "ready": False,       # 启动期的数据是否全部到位。换 mod 的 reload 不改它
    "failed": False,      # 上一轮加载是不是抛异常了
    "error": "",          # 抛的是什么
    "phase": "",          # boot / mod / reload / map / export
    "stage": "", "sub": "", "pct": 0, "t": 0.0,
    "started_at": 0.0,    # 本 phase 开始的时刻，用来算 elapsed
    "stages": [],         # [{"key", "name", "pct", "done_ms"}]，最多 40 条
}


def _lp_begin(phase):
    """开一个新的加载 phase，清掉上一轮的阶段记录。"""
    LOAD_PROGRESS["phase"] = phase
    LOAD_PROGRESS["started_at"] = time.time()
    LOAD_PROGRESS["stages"] = []
    LOAD_PROGRESS["failed"] = False
    LOAD_PROGRESS["error"] = ""


def _lp(stage, sub="", pct=0):
    """上报加载阶段。前端轮询 /api/load_progress 读这个，做确定性进度条。"""
    LOAD_PROGRESS["active"] = True
    LOAD_PROGRESS["stage"] = stage
    LOAD_PROGRESS["sub"] = sub
    LOAD_PROGRESS["pct"] = max(0, min(100, int(pct)))
    now = time.time()
    LOAD_PROGRESS["t"] = now
    # 同一 (stage, sub) 连续上报只更新最后一条，不刷屏；阶段记录给 boot 页显示「哪几步过了」
    key = "%s|%s" % (stage, sub)
    st = LOAD_PROGRESS["stages"]
    base = LOAD_PROGRESS["started_at"] or now
    if st and st[-1].get("key") == key:
        st[-1]["pct"] = LOAD_PROGRESS["pct"]
    else:
        st.append({"key": key, "name": stage, "pct": LOAD_PROGRESS["pct"],
                   "done_ms": int((now - base) * 1000)})
        del st[:-40]


def _lp_done():
    LOAD_PROGRESS["active"] = False
    LOAD_PROGRESS["stage"] = ""
    LOAD_PROGRESS["sub"] = ""
    LOAD_PROGRESS["pct"] = 100


def _lp_fail(err):
    """加载抛异常时调。别让它停在 active=True —— 旧的 10 秒兜底会把「炸了」显示成「已完成」。"""
    LOAD_PROGRESS["active"] = False
    LOAD_PROGRESS["failed"] = True
    LOAD_PROGRESS["error"] = str(err)


# 启动期后台加载还没跑完时，数据类请求一律 503，避免读到 reload_data 半清空的容器。
# 这几个路径放行：页面本身、进度查询、选项、AI 配置——前端要靠它们把进度条显示出来。
_BOOT_OK_PATHS = ("/api/boot_status", "/api/load_progress", "/api/options", "/api/ai_config")


def _boot_gate(path_only):
    """返回 None 表示放行，返回 dict 表示该拦（调用方直接把这个 dict 按 503 发回去）。"""
    if not LOAD_PROGRESS.get("active") or LOAD_PROGRESS.get("ready"):
        return None
    if path_only in _BOOT_OK_PATHS:
        return None
    if not path_only.startswith("/api/"):
        return None   # 静态资源照常，页面得先出来
    return {"ok": False, "code": "LOADING", "loading": True,
            "msg": "编辑器正在读取 mod 数据，请稍候",
            "phase": LOAD_PROGRESS.get("phase") or "",
            "pct": LOAD_PROGRESS.get("pct") or 0,
            "stage": LOAD_PROGRESS.get("stage") or ""}


def _prune_roots():
    """F13：删掉已经不存在的根目录。

    ROOTS 会从 playset.json / 上次会话恢复，里面可能有已经卸载的 mod。
    留着它会在解析阶段到处 FileNotFoundError，而异常位置和真正的原因
    （某个目录没了）隔着好几层，看上去像是别的功能坏了。
    """
    gone = [r for r in ROOTS if not os.path.isdir(r)]
    if not gone:
        return
    ROOTS[:] = [r for r in ROOTS if os.path.isdir(r)]
    for r in gone:
        _lp("加载 mod", "跳过不存在的 mod 目录：%s" % r)





def load_mod(root):
    _prune_roots()
    root = os.path.abspath(root)
    count = load_focus(root)
    # 本地化
    _lp("解析本地化", "8052 条文本", 59)
    # 先英文后中文：显示优先使用中文。语言内部按叠加链「父 → 子」读，子覆盖父。
    line_re = re.compile(r'^\s*([A-Za-z0-9_.\-]+):\d*\s+"(.*)"\s*$')
    for lang in ("english", "simp_chinese"):
        for ab in _chain_layers(root):
            d = os.path.join(ab, "localisation", lang)
            if not os.path.isdir(d):
                continue
            for dirpath, _, files in os.walk(d):
                for fn in files:
                    if not fn.endswith(".yml"):
                        continue
                    for ln in io.open(os.path.join(dirpath, fn), encoding="utf-8-sig", errors="replace").read().splitlines():
                        m = line_re.match(ln)
                        if m:
                            LOC[m.group(1)] = m.group(2)
    _lp("国家精神与科技", "", 61)
    load_ideas(root)
    load_equipment(root)
    load_modules(root)
    load_orgs(root)
    load_techs(root)
    _lp("事件、国家、州", "", 92)
    load_events(root)
    load_countries(root)
    load_states(root)
    _lp("收尾", "", 96)
    return count

def analyze(tree):
    ids = {f["id"] for f in tree["focuses"]}
    edges, missing = [], []
    graph = {f["id"]: [] for f in tree["focuses"]}
    for f in tree["focuses"]:
        for grp in f["prereq"]:
            for p in grp:
                if p in ids:
                    edges.append((p, f["id"]))
                    graph[p].append(f["id"])
                else:
                    missing.append([f["id"], p])
    color = {i: 0 for i in ids}
    cycles = []
    def dfs(u, stack):
        color[u] = 1
        stack.append(u)
        for v in graph[u]:
            if color[v] == 0:
                dfs(v, stack)
            elif color[v] == 1:
                cycles.append(stack[stack.index(v):] + [v])
        stack.pop()
        color[u] = 2
    for i in ids:
        if color[i] == 0:
            dfs(i, [])
    pos, overlaps = {}, []
    for f in tree["focuses"]:
        fx = f.get("ax", f.get("x"))
        fy = f.get("ay", f.get("y"))
        if fx is None:
            continue
        key = (fx, fy)
        if key in pos:
            overlaps.append([pos[key], f["id"]])
        else:
            pos[key] = f["id"]
    return {"edges": edges, "missing": missing, "cycles": cycles, "overlaps": overlaps}


def reload_data():
    """重新读取所有 mod，保证保存后界面数据是最新的"""
    # 规则 3：清空用 clear()，不要重新赋值。重新赋值只改本模块的名字，
    # 搬迁到 model 的模块会继续看着旧对象（P0-3 障碍 4）。
    _state.trees().clear()
    _state.tree_order().clear()
    _state.loc().clear()
    _state.ideas().clear()
    _state.shared_focuses().clear()
    _state.equipments().clear()
    _state.techs().clear()
    _state.events().clear()
    _state.modules().clear()
    _state.orgs().clear()
    _state.countries().clear()
    _state.states().clear()
    # 逐层加载会把 load_states / load_countries 这类内部已经走 _layer_files 的
    # 函数重复执行（它们每次都处理整条链），州数会从 818 涨到 1081。
    # 所以这里保持只遍历 ROOTS；「父 mod 的 ideas/techs/equipment 读不到」这件事
    # 记在 BACKLOG，等把这批 loader 改成走 _layer_files 之后再统一改。
    total = 0
    for r in ROOTS:
        total += load_mod(r)
    _lp("关联国家", "", 96)
    link_countries()
    _lp_done()
    return total

IDEAS = {}


def _log_loc(ln):
    """从一行日志里抠出「文件 + 行号」。HOI4 常见两种写法：
        ... in file events/xxx.txt line 42
        ... at events/xxx.txt:42
    引擎自己的 cpp 位置（script_persistent.cpp:123）不是 mod 文件，忽略。"""
    m = re.search(r'in file\s+"?([\w./\\-]+\.(?:txt|yml|gfx|gui))"?\s+line\s+(\d+)', ln, re.I)
    if not m:
        m = re.search(r'([\w./\\-]+\.(?:txt|yml|gfx|gui)):(\d+)', ln)
    if m:
        return {"file": m.group(1).replace(chr(92), "/"), "line": int(m.group(2))}
    return None


def error_log(limit=120):
    """返回错误行 + 每行解析出的文件位置（用于跳转）"""
    p = os.path.join(os.path.expanduser("~"), "Documents", "Paradox Interactive",
                     "Hearts of Iron IV", "logs", "error.log")
    items = []
    if os.path.exists(p):
        try:
            raw = io.open(p, encoding="utf-8", errors="replace").read().splitlines()
            keep = [(i, ln) for i, ln in enumerate(raw, 1)
                    if re.search(r'focus|national_focus|idea|mod/|Error', ln, re.I)]
            for i, ln in keep[-limit:]:
                items.append({"n": i, "text": ln, "loc": _log_loc(ln)})
        except Exception as e:
            items = [{"n": 0, "text": "读取失败: %s" % e, "loc": None}]
    return {"path": p, "items": items,
            "lines": [x["text"] for x in items],
            "withLoc": sum(1 for x in items if x.get("loc"))}


def file_excerpt(rel, line, root=None, span=6):
    """取某个文件第 line 行前后 span 行，供日志跳转预览"""
    rel = (rel or "").replace(chr(92), "/").strip("/")
    if not rel:
        return {"ok": False, "msg": "没有文件路径"}
    cands = []
    for base in mod_layers(_map_pick(root)) or [GAME]:
        if base:
            cands.append(os.path.join(base, rel.replace("/", os.sep)))
    for c in cands:
        if os.path.exists(c):
            try:
                lines = io.open(c, encoding="utf-8-sig", errors="replace").read().splitlines()
            except Exception as e:
                return {"ok": False, "msg": "读取失败：%s" % e}
            line = max(1, min(int(line or 1), len(lines) or 1))
            a = max(0, line - 1 - span)
            b = min(len(lines), line + span)
            return {"ok": True, "file": rel, "line": line, "total": len(lines),
                    "from": a + 1, "to": b, "path": c,
                    "excerpt": [{"n": a + i + 1, "text": lines[a + i],
                                 "hit": (a + i + 1) == line} for i in range(b - a)]}
    return {"ok": False, "msg": "在任何 mod 层与原版里都找不到 %s" % rel}




# ---------------- 国家 / 州 / 项目体检（v0.55） ----------------
COUNTRIES = {}
STATES = {}


def _prefer(existing, root):
    """同一个 tag/state 谁说了算。

    HOI4 语义：后加载的覆盖先加载的。所以：
      1. 没有记录 → 收
      2. 现有记录来自原版 → 覆盖（原版是只读参考层）
      3. 现有记录来自同一层 → 覆盖（重复加载要幂等）
      4. 都在叠加链里 → 位置更靠后的优先
      5. 现有记录的层不在链里（游离目录）→ 覆盖

    原来只判断「现有是否来自原版」，导致父 mod 的记录挡住了子 mod，
    加载 submod 时它的州文件永远被跳过、state_save 会报「州文件不存在」。"""
    if not existing:
        return True
    old_root = existing.get("root", "") or ""
    # 原版记录可以被任何 mod 覆盖
    if is_under_game(old_root):
        return True
    # 原版不能覆盖 mod 记录（mod_layers(GAME) 只有一层，index 会抛错并误判为可覆盖）
    if is_under_game(root):
        return False
    if os.path.abspath(old_root) == os.path.abspath(root or ""):
        return True
    # 两个都是 mod：按 ROOTS 展开的完整叠加链判断谁更靠后
    bases = []
    for _r in (ROOTS or []):
        for _b in (mod_layers(_r) or [_r]):
            if _b and os.path.abspath(_b) not in [os.path.abspath(x) for x in bases]:
                bases.append(_b)
    try:
        return bases.index(os.path.abspath(root or "")) >= bases.index(os.path.abspath(old_root))
    except ValueError:
        return True




def load_countries(root):
    """common/country_tags + common/countries + history/countries"""
    root = os.path.abspath(root)
    name = os.path.basename(root.rstrip("\\/")) or root

    _layers_c = mod_layers(root)
    tag_files, _tag_replaced = _layer_files("common/country_tags", _layers_c)
    for path in tag_files:
        fn = os.path.basename(path)
        rel = os.path.join("common", "country_tags", fn)
        for m in re.finditer(r'(?m)^\s*([A-Z0-9_]{2,8})\s*=\s*"([^"]+)"', _read_text(path)):
            tag, defrel = m.group(1), m.group(2)
            cur = COUNTRIES.get(tag)
            if not _prefer(cur, root):
                continue
            COUNTRIES[tag] = {"tag": tag, "def_file": defrel, "tag_file": rel,
                              "root": root, "source": name, "color": None,
                              "history_file": "", "capital": "", "political_power": "",
                              "stability": "", "war_support": "", "ruling_party": "",
                              "ideas": [], "techs": [], "focus_trees": [], "oob": "",
                              "states_owned": [], "states_core": [], "has_def": False}

    # 国家定义文件（颜色 / graphical_culture）
    # mod 的覆盖文件可能只写 graphical_culture 而没有 color，这时要继续往原版找
    for tag, c in list(COUNTRIES.items()):
        if c.get("source") != name:
            continue
        rel = (c.get("def_file") or "").replace("/", os.sep)
        for base in (root, GAME):
            p = os.path.join(base, "common", rel) if rel else ""
            if not (p and os.path.exists(p)):
                continue
            text = _read_text(p)
            if not c.get("has_def"):
                c["has_def"] = True
                c["def_path"] = p
                c["graphical_culture"] = _first(text, r'(?m)^\s*graphical_culture\s*=\s*(\w+)')
            cm = re.search(r'(?m)^\s*color\s*=\s*(rgb|hsv)?\s*\{?\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)', text)
            if cm:
                mode = (cm.group(1) or "").lower()
                a, b2, c3 = float(cm.group(2)), float(cm.group(3)), float(cm.group(4))
                if mode == "hsv":
                    r, g, bl = colorsys.hsv_to_rgb(a, b2, c3)
                    c["color"] = [round(r, 4), round(g, 4), round(bl, 4)]
                else:
                    rgb = [a, b2, c3]
                    if max(rgb) > 1.0:
                        rgb = [round(v / 255.0, 4) for v in rgb]
                    c["color"] = rgb
                c["color_from"] = p
                break

    # 没写 color 的国家：按 tag 派生一个稳定色（游戏里也用引擎兜底色，这里保证不灰、不撞色）
    for tag, c in list(COUNTRIES.items()):
        if c.get("source") != name or c.get("color"):
            continue
        try:
            hue = (zlib.crc32(tag.encode("utf-8")) % 1000) / 1000.0
            r, g, b = colorsys.hsv_to_rgb(hue, 0.45, 0.78)
            c["color"] = [round(r, 4), round(g, 4), round(b, 4)]
            c["color_derived"] = True
        except Exception:
            c["color"] = [0.52, 0.52, 0.52]
            c["color_derived"] = True

    # 开局历史
    _hist_pairs = []
    for _b, _d in _layer_dirs("history/countries", root):
        for _f in sorted(f for f in os.listdir(_d) if f.endswith(".txt")):
            _hist_pairs.append((_b, _d, _f))
    for _hb, d, fn in _hist_pairs:
        if True:
            m = re.match(r'([A-Z0-9_]{2,8})\s*-\s*(.+)\.txt$', fn, re.I)
            tag = m.group(1).upper() if m else fn[:-4].strip().upper()[:4]
            text = _read_text(os.path.join(d, fn))
            cur = COUNTRIES.get(tag)
            if not cur:
                # 有历史文件但 country_tags 里没登记：孤儿，体检会报
                COUNTRIES[tag] = {"tag": tag, "def_file": "", "tag_file": "", "root": root,
                                  "source": name, "color": None, "orphan_history": True,
                                  "history_file": "", "capital": "", "political_power": "",
                                  "stability": "", "war_support": "", "ruling_party": "",
                                  "ideas": [], "techs": [], "focus_trees": [], "oob": "",
                                  "states_owned": [], "states_core": [], "has_def": False}
                cur = COUNTRIES[tag]
            elif not (cur.get("root") == root or is_under_game(cur.get("root", ""))):
                continue
            cur["root"] = root
            cur["source"] = name
            cur["history_file"] = os.path.join("history", "countries", fn)
            cur["history_display"] = m.group(2).strip() if m else tag
            cur["capital"] = _first(text, r'(?m)^\s*capital\s*=\s*(\d+)')
            cur["political_power"] = _first(text, r'(?m)^\s*add_political_power\s*=\s*(-?[\d.]+)')
            cur["stability"] = _first(text, r'(?m)^\s*add_stability\s*=\s*(-?[\d.]+)')
            cur["war_support"] = _first(text, r'(?m)^\s*add_war_support\s*=\s*(-?[\d.]+)')
            cur["ruling_party"] = _first(text, r'ruling_party\s*=\s*(\w+)')
            cur["oob"] = _first(text, r'(?m)^\s*oob\s*=\s*"?([^"\n]+)"?')

            ideas = []
            for im in re.finditer(r'add_ideas\s*=\s*\{', text):
                b = text.find('{', im.start())
                e = brace_match(text, b)
                ideas += [x for x in re.findall(r'[A-Za-z0-9_]+', text[b + 1:e - 1])]
            for im in re.finditer(r'(?m)^\s*add_ideas\s*=\s*([A-Za-z0-9_]+)', text):
                ideas.append(im.group(1))
            cur["ideas"] = sorted(set(ideas))

            techs = []
            for tm in re.finditer(r'set_technology\s*=\s*\{', text):
                b = text.find('{', tm.start())
                e = brace_match(text, b)
                for k, v, has_block in top_items(text[b + 1:e - 1]):
                    if not has_block:
                        techs.append(k)
            cur["techs"] = sorted(set(techs))

            trees = []
            for fm in re.finditer(r'load_focus_tree\s*=\s*\{', text):
                b = text.find('{', fm.start())
                e = brace_match(text, b)
                for k, v, has_block in top_items(text[b + 1:e - 1]):
                    if k == "tree" and not has_block:
                        trees.append(v)
            for fm in re.finditer(r'(?m)^\s*load_focus_tree\s*=\s*([A-Za-z0-9_]+)', text):
                trees.append(fm.group(1))
            cur["focus_trees"] = sorted(set(trees))
    return len(COUNTRIES)


START_DATE = (1936, 1, 1)      # 开局日期，load 时从 bookmarks 刷新
START_DATE_TEXT = "1936.1.1"






def refresh_start_date(roots):
    """从 bookmarks 找最早的开局日期（mod 常用 1999.8.7 这种）"""
    global START_DATE, START_DATE_TEXT
    dates = []
    for base in list(roots) + [GAME]:
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
        START_DATE = min(dates)
        _state.set_start_date(START_DATE)
        START_DATE_TEXT = "%d.%d.%d" % START_DATE
    return START_DATE




def load_states(root):
    """history/states：id / 名称 / 人力 / 类别 / owner / cores / 省份 / 建筑 / 胜利点"""
    root = os.path.abspath(root)
    name = os.path.basename(root.rstrip("\\/")) or root
    layers = mod_layers(root)
    files, _replaced = _layer_files("history/states", layers)
    if not files:
        return 0
    n = 0
    _start = _start_date_for(root)
    for path in files:
        fn = os.path.basename(path)
        rel = os.path.join("history", "states", fn)
        # 文件来自叠加链的哪一层：必须按实际路径反推，不能一律用函数参数 root，
        # 否则原版的 1-France.txt 会被记成「子 mod 的文件」，state_save 就会报文件不存在。
        file_root = None
        _ap = os.path.abspath(path)
        for _b in (layers or []):
            if _b and _ap.startswith(os.path.abspath(_b) + os.sep):
                file_root = _b
                break
        if not file_root:
            continue
        src_name = os.path.basename(file_root.rstrip("\\/")) or file_root
        text = _read_text(path)
        for s, e, body in find_blocks(text, "state"):
            sid = _first(body, r'(?m)^\s*id\s*=\s*(-?\d+)')
            if not sid:
                continue
            sid = int(sid)
            cur = STATES.get(sid)
            if not _prefer(cur, file_root):
                continue

            dep = _hist_depths(body)
            hb = he = -1
            hm = re.search(r'(?m)^[ \t]*history\s*=\s*\{', body)
            if hm:
                hb = body.find('{', hm.end() - 1)
                he = brace_match(body, hb)

            def first_at(pat, want, lo=0, hi=None):
                hi = len(body) if hi is None else hi
                for m in re.finditer(pat, body[lo:hi]):
                    pos = lo + m.start()
                    if pos < len(dep) and dep[pos] == want:
                        return m.group(1).strip()
                return ""

            owner = _state_owner_effective(body, hb, he, dep, _start)

            cores = []
            for m in re.finditer(r'(?m)^[ \t]*add_core_of\s*=\s*([A-Z0-9_]{2,8})', body):
                pos = m.start()
                if pos < len(dep) and dep[pos] in (0, 1, 2):
                    cores.append(m.group(1))

            blds, prov_blds = {}, {}
            bm = re.search(r'(?m)^[ \t]*buildings\s*=\s*\{', body)
            if bm:
                bb = body.find('{', bm.end() - 1)
                be = brace_match(body, bb)
                for bk, bv, has_block in top_items(body[bb + 1:be - 1]):
                    if has_block:
                        sub = {}
                        for sk, sv, sb in top_items(bv):
                            if not sb and sv.strip().isdigit():
                                sub[sk] = int(sv.strip())
                        prov_blds[bk] = sub
                    elif bv.strip().isdigit():
                        blds[bk] = int(bv.strip())

            vps = []
            vm = re.search(r'victory_points\s*=\s*\{([^}]*)\}', body)
            if vm:
                nums = re.findall(r'\d+', vm.group(1))
                for i in range(0, len(nums) - 1, 2):
                    vps.append((int(nums[i]), int(nums[i + 1])))

            pm = re.search(r'provinces\s*=\s*\{([^}]*)\}', body)
            provs = [int(x) for x in re.findall(r'\d+', pm.group(1))] if pm else []
            res = {}
            rm = re.search(r'(?m)^[ \t]*resources\s*=\s*\{', body)
            if rm:
                rb = body.find("{", rm.end() - 1)
                re_ = brace_match(body, rb)
                if re_ > rb:
                    for k, v, has in top_items(body[rb + 1:re_ - 1]):
                        if not has:
                            try:
                                iv = int(str(v).strip())
                            except Exception:
                                continue
                            if iv > 0:
                                res[k] = iv
            hist_date = _first(body, r'(?m)^[ \t]*(\d{3,4}\.\d{1,2}\.\d{1,2})\s*=\s*\{')

            STATES[sid] = {
                "id": sid, "file": rel, "root": file_root, "source": src_name,
                "name": _first(body, r'(?m)^\s*name\s*=\s*"?([A-Za-z0-9_]+)"?'),
                "manpower": _first(body, r'(?m)^\s*manpower\s*=\s*(\d+)'),
                "category": _first(body, r'(?m)^\s*state_category\s*=\s*(\w+)'),
                "owner": owner, "cores": sorted(set(cores)),
                "provinces": provs, "province_count": len(provs),
                "buildings": blds, "province_buildings": prov_blds,
                "resources": res,
                "victory_points": vps,
                "history_date": hist_date,
                "has_history": hb > 0,
            }
            n += 1
    return n


# HOI4 1.19 的 state_category 全集（缺 large_town / city 会让这两类州保存失败）

# 州级建筑面板用：内部名 → 显示名 / 上限 / 是否只能建在沿海州。
# 上限取自原版 common/buildings 的 max_level（基础设施原版 5，这里按任务书放宽到 100，
# 因为不少 mod 会改 max_level；写超了游戏侧会自己截断，但面板要先拦住手滑）。

# 省级建筑（写在 buildings = { 省号 = { ... } } 里）


_COASTAL_CACHE = {"key": None, "set": set()}


# 附庸自治度：内部名 → 中文名。名字与 common/autonomous_states/*.txt 对得上，
# 顺序按「从最松到最紧」排，下拉里看着顺。
AUTONOMY_STATES = (
    ("autonomy_colony",                 "殖民地"),
    ("autonomy_dominion",               "自治领"),
    ("autonomy_associated_dominion",    "联系自治领"),
    ("autonomy_satellite",              "卫星国"),
    ("autonomy_puppet",                 "傀儡国"),
    ("autonomy_integrated_puppet",      "整合傀儡"),
    ("autonomy_personal_union",         "共主邦联"),
    ("autonomy_supervised_state",       "受监管国"),
    ("autonomy_collaboration_government", "合作政府"),
    ("autonomy_reichskommissariat",     "帝国专员辖区"),
    ("autonomy_reichsprotectorate",     "帝国保护国"),
)










































def link_countries():
    """把州、国策树挂到国家上（每轮 reload 后重建）"""
    for c in COUNTRIES.values():
        c["states_owned"] = []
        c["states_core"] = []
    for sid, s in STATES.items():
        o = s.get("owner") or ""
        if o in COUNTRIES:
            COUNTRIES[o]["states_owned"].append(sid)
        for t in s.get("cores", []):
            if t in COUNTRIES and sid not in COUNTRIES[t]["states_core"]:
                COUNTRIES[t]["states_core"].append(sid)
    for tid, t in TREES.items():
        tags = re.findall(r'tag\s*=\s*([A-Z0-9_]{2,8})', t.get("country_raw") or "")
        t["country_tags"] = sorted(set(tags))
        for tag in t["country_tags"]:
            if tag in COUNTRIES and tid not in COUNTRIES[tag]["focus_trees"]:
                COUNTRIES[tag]["focus_trees"].append(tid)
    for c in COUNTRIES.values():
        c["states_owned"].sort()
        c["states_core"].sort()
        c["focus_trees"] = sorted(set(c["focus_trees"]))


def _country_issues(c):
    out = []

    def add(level, text, goto=None):
        out.append({"level": level, "text": text, "goto": goto or {}})

    tag = c["tag"]
    if c.get("orphan_history"):
        add("error", "有 history 文件，但 common/country_tags 里没有 %s" % tag)
    if not c.get("has_def"):
        add("warn", "找不到国家定义文件（%s）" % (c.get("def_file") or "未登记"))
    if not c.get("history_file"):
        add("warn", "没有 history/countries 文件，进游戏会是白板国家")
    if not c.get("capital"):
        add("warn", "没有设置首都 capital")
    if not c.get("focus_trees"):
        add("warn", "没有挂任何国策树（country = { tag } 或 load_focus_tree）")
    for t in c.get("focus_trees", []):
        if t not in TREES:
            add("error", "挂载的国策树 %s 不存在" % t, {"type": "country", "id": tag})
    bad_ideas = [i for i in c.get("ideas", []) if i not in IDEAS]
    if bad_ideas:
        add("warn", "add_ideas 引用了 %d 个不存在的国家精神（如 %s）" % (len(bad_ideas), bad_ideas[0]),
            {"type": "country", "id": tag})
    party = (c.get("ruling_party") or "").lower()
    has_base = bool(LOC.get(tag))
    has_party = bool(party and LOC.get("%s_%s" % (tag, party)))
    if not has_base and not has_party:
        add("warn", "国家名没有本地化：%s 与 %s_<政体> 都缺" % (tag, tag))
    elif party and not has_party:
        add("info", "有国家名但没有 %s_%s，政体一变就会掉回默认名" % (tag, party))
    if not LOC.get(tag + "_ADJ"):
        add("info", "缺少形容词键 %s_ADJ" % tag)
    if not c.get("states_owned"):
        add("warn", "没有任何州把它设为 owner")
    return out


def countries_payload():
    items = []
    for tag in sorted(COUNTRIES):
        c = COUNTRIES[tag]
        items.append({
            "tag": tag,
            "name": (LOC.get("%s_%s" % (tag, (c.get("ruling_party") or "").lower()))
                 or LOC.get(tag) or c.get("history_display") or tag),
            "history_file": c.get("history_file", ""),
            "trees": c.get("focus_trees", []),
            "owned": len(c.get("states_owned", [])),
            "cores": len(c.get("states_core", [])),
            "ideas": len(c.get("ideas", [])),
            "issues": len(_country_issues(c)),
            "capital": c.get("capital", ""),
            "political_power": c.get("political_power", ""),
            "ruling_party": c.get("ruling_party", ""),
            "orphan": bool(c.get("orphan_history")),
        })
    return {"count": len(items), "list": items}


def country_detail(tag):
    c = COUNTRIES.get(tag)
    if not c:
        return {"ok": False, "msg": "没有这个国家 tag"}
    states = []
    for sid in c.get("states_owned", []):
        s = STATES.get(sid) or {}
        states.append({"id": sid, "name": s.get("name", ""),
                       "loc": LOC.get(s.get("name", ""), ""),
                       "manpower": s.get("manpower", ""), "category": s.get("category", ""),
                       "core": sid in c.get("states_core", [])})
    cores_only = [sid for sid in c.get("states_core", []) if sid not in c.get("states_owned", [])]
    trees = []
    for tid in c.get("focus_trees", []):
        t = TREES.get(tid)
        trees.append({"id": tid, "exists": bool(t),
                      "focuses": len(t.get("focuses", [])) if t else 0,
                      "file": t.get("file", "") if t else "",
                      "default": (t or {}).get("default", ""),
                      "country_raw": (t or {}).get("country_raw", "")[:120]})
    return {
        "ok": True,
        "tag": tag,
        "name": (LOC.get("%s_%s" % (tag, (c.get("ruling_party") or "").lower()))
                 or LOC.get(tag) or c.get("history_display") or tag),
        "adj": LOC.get(tag + "_ADJ", ""),
        "source": c.get("source", ""),
        "color": c.get("color"),
        "graphical_culture": c.get("graphical_culture", ""),
        "def_file": c.get("def_file", ""),
        "def_found": bool(c.get("has_def")),
        "history_file": c.get("history_file", ""),
        "capital": c.get("capital", ""),
        "political_power": c.get("political_power", ""),
        "stability": c.get("stability", ""),
        "war_support": c.get("war_support", ""),
        "ruling_party": c.get("ruling_party", ""),
        "oob": c.get("oob", ""),
        "ideas": c.get("ideas", []),
        "techs": c.get("techs", []),
        "trees": trees,
        "states": states,
        "cores_only": cores_only,
        "issues": _country_issues(c),
    }


# ---------------- 国家历史写回（v0.56） ----------------
PARTIES = ("democratic", "fascism", "communism", "neutrality")

HIST_KEYS = {
    "capital": "capital",
    "political_power": "add_political_power",
    "stability": "add_stability",
    "war_support": "add_war_support",
}


def _hist_path(tag):
    c = COUNTRIES.get(tag)
    if not c:
        return None, None, None
    root = c.get("root") or ""
    rel = c.get("history_file") or ""
    p = os.path.join(root, rel) if rel else ""
    return c, root, p









def _hist_block_body(text, key):
    """取顶层 key = { ... } 的块内文本，没有返回空串"""
    m = _hist_find_top(text, re.compile(r'(?m)^[ \t]*%s\s*=\s*\{' % re.escape(key)))
    if not m:
        return ""
    b = text.find('{', m.end() - 1)
    return text[b + 1:brace_match(text, b) - 1]


def _hist_popularities(text):
    out = {}
    for k, v, hb in top_items(_hist_block_body(text, "set_popularities")):
        if hb:
            continue
        try:
            out[k] = int(float(v.strip()))
        except Exception:
            pass
    return out


def _hist_party_of(text):
    """ruling_party 一般在 set_politics 块里，先看顶层再看块内"""
    m = _hist_find_top(text, re.compile(r'(?m)^[ 	]*ruling_party\s*=\s*(\w+)'))
    if m:
        return m.group(1).strip()
    sm = re.search(r'(?m)^[ 	]*set_politics\s*=\s*\{', text)
    if not sm:
        return ""
    b = text.find('{', sm.end() - 1)
    e = brace_match(text, b)
    mm = re.search(r'(?m)^[ 	]*ruling_party\s*=\s*(\w+)', text[b + 1:e - 1])
    return mm.group(1).strip() if mm else ""


# v0.59 初始外交
def _hist_opinions(text):
    """读取 add_opinion 块，返回 [[tag, value], ...]"""
    out = []
    for m in re.finditer(r'(?m)^[ \t]*add_opinion\s*=\s*\{', text):
        b = text.find('{', m.end() - 1)
        e = brace_match(text, b)
        if e <= b:
            continue
        body = text[b + 1:e - 1]
        t = _first(body, r'(?m)^[ \t]*target\s*=\s*([A-Z0-9_]{2,8})')
        v = _first(body, r'(?m)^[ \t]*(?:value|opinion)\s*=\s*(-?\d+)')
        if t:
            out.append([t, int(v or 0)])
    return out


def _hist_set_opinions(text, pairs):
    """删掉所有 add_opinion 块再按 pairs 重建（顶层）"""
    for _ in range(40):
        m = _hist_find_top(text, re.compile(r'(?m)^[ \t]*add_opinion\s*=\s*\{'))
        if not m:
            break
        b = text.find('{', m.end() - 1)
        e = brace_match(text, b)
        line_start = text.rfind("\n", 0, m.start()) + 1
        text = text[:line_start] + text[e:]
    for tag, val in pairs:
        text = text.rstrip() + "\nadd_opinion = {\n\ttarget = %s\n\tvalue = %d\n}\n" % (tag, val)
    return text


# v0.64 开局装备变体
def _hist_variants(text):
    """读取 create_equipment_variant 块（只读展示用）"""
    out = []
    for m in re.finditer(r'(?m)^[ \t]*create_equipment_variant\s*=\s*\{', text):
        b = text.find('{', m.end() - 1)
        e = brace_match(text, b)
        if e <= b:
            continue
        body = text[b + 1:e - 1]
        nm = _first(body, r'(?m)^[ \t]*name\s*=\s*"?([^"\r\n]+)"?')
        ty = _first(body, r'(?m)^[ \t]*type\s*=\s*"?([^\s"\r\n]+)"?')
        ic = _first(body, r'(?m)^[ \t]*icon\s*=\s*"?([^\s"\r\n]+)"?')
        mods = 0
        mm = re.search(r'(?m)^[ \t]*modules\s*=\s*\{', body)
        if mm:
            mb = body.find('{', mm.end() - 1)
            me = brace_match(body, mb)
            if me > mb:
                mods = len([1 for k, v, hb in top_items(body[mb + 1:me - 1]) if not hb])
        out.append({"name": nm or "(未命名)", "type": ty, "icon": ic, "modules": mods})
    return out


# v0.68 开局装备变体写入
def _variant_blocks(text):
    """返回 [(start, end, name, body)]，覆盖所有 create_equipment_variant 块"""
    out = []
    for m in re.finditer(r'(?m)^[ \t]*create_equipment_variant\s*=\s*\{', text):
        b = text.find('{', m.end() - 1)
        e = brace_match(text, b)
        if e <= b:
            continue
        body = text[b + 1:e - 1]
        nm = _first(body, r'(?m)^[ \t]*name\s*=\s*"?([^"\r\n]+)"?')
        out.append((m.start(), e, (nm or "").strip(), body))
    return out


def _hist_append_top(text, block):
    """把 block 插到最后一个顶层块之后（深度 0 处），保证不落进别的块里"""
    depth = 0
    last = 0
    for i, ch in enumerate(text):
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                last = i + 1
    if last == 0:
        return text.rstrip() + "\n\n" + block + "\n"
    return text[:last] + "\n\n" + block + text[last:]


def country_variant_add(tag, spec):
    """新增一个开局变体：spec = {name, type, icon, modules:{slot:module}}"""
    name = (spec.get("name") or "").strip()
    etype = (spec.get("type") or "").strip()
    if not name:
        return {"ok": False, "msg": "变体名称不能为空"}
    if not re.match(r'^[A-Za-z0-9_\- ]{1,60}$', name):
        return {"ok": False, "msg": "名称只能用字母数字、空格、下划线和连字符"}
    if not etype:
        return {"ok": False, "msg": "请选择底盘（type）"}
    if not re.match(r'^[A-Za-z0-9_]+$', etype):
        return {"ok": False, "msg": "底盘 id 只能用字母数字下划线"}
    if EQUIPMENTS and etype not in EQUIPMENTS:
        return {"ok": False, "msg": "底盘 %s 不在装备列表里" % etype}
    mods = spec.get("modules") or {}
    if not isinstance(mods, dict) or not mods:
        return {"ok": False, "msg": "至少要填一个模块（槽位 = 模块）"}
    c, root, path = _hist_path(tag)
    if not path or is_under_game(root):
        return {"ok": False, "msg": "这个国家没有可写的历史文件"}
    text, has_bom = _read_bom_text(path)
    if any(n == name for (_, _, n, _) in _variant_blocks(text)):
        return {"ok": False, "msg": "已经有同名变体 %s" % name}
    lines = ['create_equipment_variant = {', '\tname = "%s"' % name, '\ttype = %s' % etype]
    icon = (spec.get("icon") or "").strip()
    if icon:
        lines.append('\ticon = %s' % icon)
    lines.append('\tmodules = {')
    for slot, mod in mods.items():
        if not re.match(r'^[A-Za-z0-9_]+$', str(slot)) or not re.match(r'^[A-Za-z0-9_]+$', str(mod)):
            return {"ok": False, "msg": "槽位/模块 id 只能用字母数字下划线：%s = %s" % (slot, mod)}
        lines.append('\t\t%s = %s' % (slot, mod))
    lines.append('\t}')
    lines.append('}')
    block = "\n".join(lines)
    new_text = _hist_append_top(text, block)
    snapshot(path)
    _write_bom_text(path, new_text, has_bom)
    CHANGED[path] = os.path.relpath(path, root)
    reload_data()
    link_countries()
    return {"ok": True, "msg": "已新增变体 %s（%d 个模块）" % (name, len(mods)),
            "variants": _hist_variants(_read_bom_text(path)[0])}


def country_variant_del(tag, name):
    """按 name 删除一个开局变体块"""
    name = (name or "").strip()
    if not name:
        return {"ok": False, "msg": "缺少变体名称"}
    c, root, path = _hist_path(tag)
    if not path or is_under_game(root):
        return {"ok": False, "msg": "这个国家没有可写的历史文件"}
    text, has_bom = _read_bom_text(path)
    target = None
    for (s, e, nm, body) in _variant_blocks(text):
        if nm == name:
            target = (s, e)
            break
    if not target:
        return {"ok": False, "msg": "找不到变体 %s" % name}
    s, e = target
    line_start = text.rfind("\n", 0, s)
    if line_start < 0:
        line_start = 0
    new_text = text[:line_start] + text[e:]
    snapshot(path)
    _write_bom_text(path, new_text, has_bom)
    CHANGED[path] = os.path.relpath(path, root)
    reload_data()
    link_countries()
    return {"ok": True, "msg": "已删除变体 %s" % name,
            "variants": _hist_variants(_read_bom_text(path)[0])}


def country_history_raw(tag):
    c, root, p = _hist_path(tag)
    if not c:
        return {"ok": False, "msg": "没有这个国家 tag"}
    writable = bool(root) and not is_under_game(root)
    if not p or not os.path.exists(p):
        return {"ok": True, "exists": False, "writable": writable, "file": c.get("history_file", ""),
                "root": root, "text": "", "fields": {}}
    text, _ = _read_bom_text(p)
    body = strip_comments(text)

    def top_val(pat):
        m = _hist_find_top(body, re.compile(pat))
        return m.group(1).strip() if m else ""

    fields = {
        "capital": top_val(r'(?m)^[ 	]*capital\s*=\s*(\d+)'),
        "ruling_party": _hist_party_of(body),
        "political_power": top_val(r'(?m)^[ 	]*add_political_power\s*=\s*(-?[\d.]+)'),
        "stability": top_val(r'(?m)^[ 	]*add_stability\s*=\s*(-?[\d.]+)'),
        "war_support": top_val(r'(?m)^[ 	]*add_war_support\s*=\s*(-?[\d.]+)'),
        "ideas": (COUNTRIES.get(tag) or {}).get("ideas", []),
        "focus_tree": ((COUNTRIES.get(tag) or {}).get("focus_trees") or [""])[0],
        "oob": top_val(r'(?m)^[ \t]*oob\s*=\s*"([^"]+)"'),
        "techs": [k for k, v, hb in top_items(_hist_block_body(body, "set_technology")) if not hb],
        "popularities": _hist_popularities(body),
        "opinions": _hist_opinions(body),
        "variants": _hist_variants(body),
    }
    return {"ok": True, "exists": True, "writable": writable, "file": c.get("history_file", ""),
            "root": root, "text": text[:60000], "fields": fields}


def _hist_depths(text):
    """每个字符位置的花括号深度（字符串内的括号不计）"""
    depth = 0
    out = []
    instr = False
    for ch in text:
        if ch == '"':
            instr = not instr
            out.append(depth)
            continue
        if instr:
            out.append(depth)
            continue
        if ch == '{':
            out.append(depth)
            depth += 1
        elif ch == '}':
            depth = max(0, depth - 1)
            out.append(depth)
        else:
            out.append(depth)
    return out


def _hist_find_top(text, pat):
    """只返回深度 0 的匹配（块内同名键不算）"""
    d = _hist_depths(text)
    for m in pat.finditer(text):
        if m.start() < len(d) and d[m.start()] == 0:
            return m
    return None


def _hist_set_scalar(text, key, value, at_end=False):
    """只在顶层替换（条件块里的同名键不动）；没有就插到开头或末尾"""
    pat = re.compile(r'(?m)^([ \t]*)%s\s*=\s*[^\s#\r\n]+' % re.escape(key))
    m = _hist_find_top(text, pat)
    if m:
        repl = (m.group(1) or "") + "%s = %s" % (key, value)
        return text[:m.start()] + repl + text[m.end():]
    line = "%s = %s\n" % (key, value)
    return (text.rstrip() + "\n" + line) if at_end else (line + text.lstrip("\r\n"))


def _hist_strip_key(text, key):
    """只删顶层的 key 块与单值行（条件分支里的同名键保留）"""
    block_pat = re.compile(r'(?m)^[ \t]*%s\s*=\s*\{' % re.escape(key))
    for _ in range(8):
        m = _hist_find_top(text, block_pat)
        if not m:
            break
        b = text.find('{', m.end() - 1)
        end = brace_match(text, b)
        line_start = text.rfind('\n', 0, m.start()) + 1
        text = text[:line_start] + text[end:]
    single = re.compile(r'(?m)^[ \t]*%s\s*=\s*[^{\s#][^\r\n]*\r?\n?' % re.escape(key))
    for _ in range(8):
        m = _hist_find_top(text, single)
        if not m:
            break
        text = text[:m.start()] + text[m.end():]
    return text


def _hist_put_block(text, key, inner_lines):
    """整体替换顶层的 key 块（先删旧块/旧单值行，再追加新块）"""
    text = _hist_strip_key(text, key)
    if not inner_lines:
        return text
    body = "\n".join("\t" + x for x in inner_lines)
    return text.rstrip() + "\n" + "%s = {\n%s\n}\n" % (key, body)


def _hist_set_party(text, party):
    m = re.search(r'(?m)^([ 	]{0,4})set_politics\s*=\s*\{', text)
    if not m:
        return "set_politics = {\n\truling_party = %s\n}\n" % party + text.lstrip("\r\n")
    b = text.find('{', m.end() - 1)
    e = brace_match(text, b)
    body = text[b + 1:e - 1]
    pat = re.compile(r'(?m)^(\s*)ruling_party\s*=\s*[^\s#\r\n]+')
    if pat.search(body):
        body2 = pat.sub(lambda mm: (mm.group(1) or "\t") + "ruling_party = " + party, body, count=1)
    else:
        body2 = body.rstrip() + "\n\truling_party = %s\n" % party
    return text[:b + 1] + body2 + text[e - 1:]


def country_history_save(tag, fields):
    """只改 fields 里给出的键，其余原文一律保留；写前 snapshot()"""
    c, root, p = _hist_path(tag)
    if not c:
        return {"ok": False, "msg": "没有这个国家 tag"}
    if not root:
        return {"ok": False, "msg": "这个国家没有来源目录"}
    if is_under_game(root):
        return {"ok": False, "msg": "原版目录只读：请先复制到自己的模组再修改"}

    warnings = []
    party = (fields.get("ruling_party") or "").strip().lower()
    if party and party not in PARTIES:
        return {"ok": False, "msg": "执政党只能是 " + " / ".join(PARTIES)}
    capital = (fields.get("capital") or "").strip()
    if capital and not capital.isdigit():
        return {"ok": False, "msg": "首都必须是州数字 id"}

    ideas = [x.strip() for x in (fields.get("ideas") or []) if x and x.strip()]
    for i in ideas:
        if i not in IDEAS:
            warnings.append("国家精神 %s 目前不存在（先写进去也可以，记得后面补定义）" % i)
    tree = (fields.get("focus_tree") or "").strip()
    if tree and tree not in TREES:
        warnings.append("国策树 %s 目前不存在" % tree)

    diff = []
    exists = bool(p) and os.path.exists(p)
    if exists:
        text, has_bom = _read_bom_text(p)
        before = strip_comments(text)
        def top_old(pat):
            m = _hist_find_top(before, re.compile(pat))
            return m.group(1).strip() if m else ""

        old = {
            "capital": top_old(r'(?m)^[ 	]*capital\s*=\s*(\d+)'),
            "ruling_party": _hist_party_of(before),
            "political_power": top_old(r'(?m)^[ 	]*add_political_power\s*=\s*(-?[\d.]+)'),
            "stability": top_old(r'(?m)^[ 	]*add_stability\s*=\s*(-?[\d.]+)'),
            "war_support": top_old(r'(?m)^[ 	]*add_war_support\s*=\s*(-?[\d.]+)'),
            "ideas": ",".join(c.get("ideas", [])),
            "focus_tree": (c.get("focus_trees") or [""])[0],
            "techs": ",".join(c.get("techs", [])),
            "oob": c.get("oob", ""),
            "popularities": ",".join("%s=%d" % (k, v) for k, v in
                                     sorted(_hist_popularities(before).items())),
            "opinions": ",".join("%s:%d" % (t4, v4) for t4, v4 in _hist_opinions(before)),
        }
        new = dict(old)
        for key, mlkey in HIST_KEYS.items():
            val = (fields.get(key) or "").strip()
            if not val:
                continue
            text = _hist_set_scalar(text, mlkey, val, at_end=(key != "capital"))
            new[key] = val
        if party:
            text = _hist_set_party(text, party)
            new["ruling_party"] = party
        if fields.get("ideas") is not None:
            text = _hist_put_block(text, "add_ideas", ideas)
            new["ideas"] = ",".join(ideas)
        if fields.get("focus_tree") is not None:
            text = _hist_put_block(text, "load_focus_tree", ["tree = " + tree] if tree else [])
            new["focus_tree"] = tree
        # v0.58 历史编辑器补全
        if fields.get("techs") is not None:
            techs = [x.strip() for x in fields.get("techs") or [] if x and x.strip()]
            text = _hist_put_block(text, "set_technology", ["%s = 1" % t for t in techs])
            new["techs"] = ",".join(techs)
        if fields.get("oob") is not None:
            oob = (fields.get("oob") or "").strip()
            if oob:
                text = _hist_set_scalar(text, "oob", '"%s"' % oob)
            new["oob"] = oob
        if fields.get("opinions") is not None:
            pairs = []
            for pair in fields.get("opinions") or []:
                try:
                    tag2, val2 = pair[0], int(pair[1])
                except Exception:
                    continue
                if tag2 in COUNTRIES:
                    pairs.append((tag2, val2))
            old_pairs = _hist_opinions(before)
            if pairs != old_pairs:
                text = _hist_set_opinions(text, pairs)
                new["opinions"] = ",".join("%s:%d" % (t3, v3) for t3, v3 in pairs)
        if fields.get("popularities") is not None:
            pops = {}
            for k, v in (fields.get("popularities") or {}).items():
                if k in PARTIES and str(v).strip():
                    try:
                        pops[k] = int(float(v))
                    except Exception:
                        pass
            if pops:
                text = _hist_put_block(text, "set_popularities",
                                       ["%s = %d" % (k, pops[k]) for k in PARTIES if k in pops])
                new["popularities"] = ",".join("%s=%d" % (k, pops[k]) for k in PARTIES if k in pops)
        shown = {"capital": "首都", "ruling_party": "执政党", "political_power": "政治点",
                 "stability": "稳定度修正", "war_support": "战争支持修正", "ideas": "开局精神",
                 "focus_tree": "国策树", "techs": "开局科技", "oob": "部队编成 oob",
                 "popularities": "政党支持度", "opinions": "初始外交"}
        for k, label in shown.items():
            if old.get(k, "") != new.get(k, ""):
                diff.append({"key": k, "label": label, "old": old.get(k, ""), "new": new.get(k, "")})
        if not diff:
            return {"ok": True, "msg": "没有改动", "diff": [], "warnings": warnings}
        snapshot(p)
        _write_bom_text(p, text, has_bom)
    else:
        name = c.get("history_display") or tag
        rel = os.path.join("history", "countries", "%s - %s.txt" % (tag, name))
        path = os.path.join(root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        lines = []
        if capital:
            lines.append("capital = " + capital)
        if party:
            lines.append("set_politics = {\n\truling_party = %s\n}" % party)
        for key, mlkey in HIST_KEYS.items():
            if key == "capital":
                continue
            val = (fields.get(key) or "").strip()
            if val:
                lines.append("%s = %s" % (mlkey, val))
        if ideas:
            lines.append("add_ideas = {\n" + "\n".join("\t" + x for x in ideas) + "\n}")
        if tree:
            lines.append("load_focus_tree = {\n\ttree = %s\n}" % tree)
        if not lines:
            return {"ok": False, "msg": "没有任何要写入的字段"}
        text = "\n".join(lines) + "\n"
        io.open(path, "w", encoding="utf-8", newline="\r\n").write(text)
        diff = [{"key": "create", "label": "新建文件", "old": "", "new": rel}]

    reload_data()
    link_countries()
    return {"ok": True, "msg": "已写入 " + (c.get("history_file") or tag), "diff": diff, "warnings": warnings}


# ---------- v1.23.48 附庸 / 外交状态 ----------
_DIPLO_INDEX = {"key": None, "idx": {}}


def _diplo_autonomy_blocks(text):
    """拆出文件里所有 set_autonomy = { target=... autonomous_state=... }"""
    out = []
    for m in re.finditer(r'(?m)^[ \t]*set_autonomy\s*=\s*\{', text):
        b = text.find('{', m.end() - 1)
        e = brace_match(text, b)
        if e <= b:
            continue
        body = text[b + 1:e - 1]
        mt = re.search(r'target\s*=\s*([A-Z0-9_]{2,8})', body)
        ma = re.search(r'autonomous_state\s*=\s*(autonomy_[a-z_]+)', body)
        if mt:
            out.append({"target": mt.group(1),
                        "autonomy": ma.group(1) if ma else "autonomy_puppet",
                        "start": m.start(), "end": e})
    return out


def _diplo_index():
    """谁是谁的附庸：{附庸: [(宗主, 自治度)]}。按 countries 目录 mtime 缓存。"""
    key = []
    for r in list(ROOTS) + ([GAME] if GAME else []):
        d = os.path.join(r or "", "history", "countries")
        if r and os.path.isdir(d):
            key.append((os.path.abspath(d), _dir_mtime(d)))
    key = tuple(key)
    if _DIPLO_INDEX.get("key") == key:
        return _DIPLO_INDEX["idx"]
    idx = {}
    for t, c in COUNTRIES.items():
        root = c.get("root") or ""
        rel = c.get("history_file") or ""
        if not root or not rel:
            continue
        p = os.path.join(root, rel)
        if not os.path.exists(p):
            continue
        try:
            txt = strip_comments(io.open(p, encoding="utf-8", errors="replace").read())
        except Exception:
            continue
        for blk in _diplo_autonomy_blocks(txt):
            idx.setdefault(blk["target"], []).append((t, blk["autonomy"]))
    _DIPLO_INDEX["key"] = key
    _DIPLO_INDEX["idx"] = idx
    return idx


def _diplo_block_text(target, autonomy):
    """照原版 DEN 的写法：DLC 在时按自治度，不在时降级成 puppet（else 必须在 if 块内部）。"""
    return ("\nif = {\n"
            "\tlimit = { has_dlc = \"Together for Victory\" }\n"
            "\tset_autonomy = {\n"
            "\t\ttarget = %s\n"
            "\t\tautonomous_state = %s\n"
            "\t}\n"
            "\telse = {\n"
            "\t\tpuppet = %s\n"
            "\t}\n"
            "}\n") % (target, autonomy, target)


def _diplo_drop_blocks(text, targets=None):
    """删掉 set_autonomy 块；targets=None 表示全删。

    同时清掉配套 else 里的对应 puppet = TAG，以及因此变成空壳的 else / if 块
    （用 brace_match 处理嵌套 limit = { OR = { ... } }）。
    """
    blocks = [b for b in _diplo_autonomy_blocks(text)
              if targets is None or b["target"] in targets]
    gone = set()
    for blk in sorted(blocks, key=lambda x: -x["start"]):
        st = text.rfind("\n", 0, blk["start"]) + 1
        en = blk["end"]
        while en < len(text) and text[en] in " \t":
            en += 1
        if en < len(text) and text[en:en + 2] == "\r\n":
            en += 2
        elif en < len(text) and text[en] in "\r\n":
            en += 1
        text = text[:st] + text[en:]
        gone.add(blk["target"])
    if gone:
        for tg in gone:
            text = re.sub(r'(?m)^[ \t]*puppet\s*=\s*%s[ \t]*\r?\n?' % re.escape(tg), "", text)
        # 删掉变空的 else = { ... }（仅剩空白与注释）
        for m in reversed(list(re.finditer(r'(?im)^[ \t]*else\s*=\s*\{', text))):
            b = text.find("{", m.start())
            e = brace_match(text, b)
            inner = strip_comments(text[b + 1:e - 1]).strip()
            if not inner:
                en = e
                while en < len(text) and text[en] in " \t":
                    en += 1
                if en < len(text) and text[en:en + 2] == "\r\n":
                    en += 2
                elif en < len(text) and text[en] in "\r\n":
                    en += 1
                text = text[:m.start()] + text[en:]
        # 删掉仅剩 limit = { ... } 空壳的 if = { ... }
        for m in reversed(list(re.finditer(r'(?im)^[ \t]*if\s*=\s*\{', text))):
            b = text.find("{", m.start())
            e = brace_match(text, b)
            inner = strip_comments(text[b + 1:e - 1])
            lm = re.match(r'\s*limit\s*=\s*\{', inner, re.I)
            if not lm:
                continue
            lb = inner.find("{", lm.start())
            le = brace_match(inner, lb)
            if not inner[le:].strip():
                en = e
                while en < len(text) and text[en] in " \t":
                    en += 1
                if en < len(text) and text[en:en + 2] == "\r\n":
                    en += 2
                elif en < len(text) and text[en] in "\r\n":
                    en += 1
                text = text[:m.start()] + text[en:]
    return text


def _diplo_set_lines(text, key, values):
    """整块替换单行键（give_guarantee / give_military_access）"""
    pat = re.compile(r'(?m)^[ \t]*%s\s*=\s*[A-Z0-9_]{2,8}[ \t]*\r?\n?' % re.escape(key))
    text = pat.sub("", text)
    lines = "".join("\t%s = %s\n" % (key, v) for v in values)
    if not lines:
        return text
    return text.rstrip() + "\n\n" + lines


def _country_write_path(tag):
    """国家历史文件的「可写副本」路径；原版来源会先复制到自己的 mod。"""
    c, root, _p = _hist_path(tag)
    if not c:
        return None, "没有这个国家 tag：" + tag
    rel = c.get("history_file") or ""
    if not rel:
        # 这个国家还没有历史文件（常见于 replace 了 history/countries 的 mod）。
        # 给它新建一个只含外交关系的文件：合法，游戏会读。
        base0 = ROOTS[-1] if ROOTS else root
        if not base0:
            return None, "%s 没有历史文件，也没有可写目录" % tag
        target0, why0 = write_base(base0, "history/countries")
        if not target0:
            return None, why0 or "%s 没有历史文件，也建不出来" % tag
        name = c.get("history_display") or tag
        dst0 = os.path.join(target0, "history", "countries", "%s - %s.txt" % (tag, name))
        if not os.path.exists(dst0):
            try:
                os.makedirs(os.path.dirname(dst0) or ".", exist_ok=True)
                io.open(dst0, "w", encoding="utf-8", newline="\n").write("")
            except Exception as e:
                return None, "给 %s 建历史文件失败：%s" % (tag, str(e)[:60])
        return dst0, why0
    if not root:
        return None, "%s 没有来源目录" % tag
    base = ROOTS[-1] if ROOTS else root
    single, why = ensure_file_writable(base, "history/countries", os.path.basename(rel))
    if single:
        if os.path.abspath(single) == os.path.abspath(os.path.join(root, rel)):
            return single, ""
        src = os.path.join(root, rel)
        if os.path.exists(src) and not os.path.exists(single):
            try:
                os.makedirs(os.path.dirname(single) or ".", exist_ok=True)
                import shutil as _sh
                _sh.copyfile(src, single)
            except Exception:
                pass
        return single, why
    target, why2 = write_base(base, "history/countries")
    if not target:
        return None, why2 or why or "写不进去"
    dst = os.path.join(target, os.path.basename(rel))
    src = os.path.join(root, rel)
    if os.path.exists(src) and not os.path.exists(dst):
        try:
            os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
            import shutil as _sh2
            _sh2.copyfile(src, dst)
        except Exception:
            pass
    return dst, why2


def _diplo_chain(tag, idx=None):
    """往上追宗主链，用来防环（A 是 B 的附庸、B 又是 A 的附庸）"""
    idx = idx if idx is not None else _diplo_index()
    out, cur, guard = [], tag, 0
    while guard < 8:
        guard += 1
        ups = idx.get(cur) or []
        if not ups:
            break
        cur = ups[0][0]
        if cur in out or cur == tag:
            return out, True
        out.append(cur)
    return out, False


def diplomacy_get(tag):
    tag = (tag or "").strip().upper()
    if not tag:
        # 没指定就给「本 mod 里第一个有自己历史文件的国家」——通常是主角国家
        for t2 in sorted(COUNTRIES):
            c2 = COUNTRIES.get(t2) or {}
            r2 = c2.get("root") or ""
            if c2.get("history_file") and r2 and not is_under_game(r2):
                tag = t2
                break
    c, root, p = _hist_path(tag)
    if not c:
        return {"ok": False, "msg": "没有这个国家 tag：" + tag}
    text = ""
    if p and os.path.exists(p):
        text, _ = _read_bom_text(p)
    body = strip_comments(text)
    puppets = [{"tag": b["target"], "autonomy": b["autonomy"],
                "label": dict(AUTONOMY_STATES).get(b["autonomy"], b["autonomy"])}
               for b in _diplo_autonomy_blocks(body)]
    guar = re.findall(r'(?m)^[ \t]*give_guarantee\s*=\s*([A-Z0-9_]{2,8})', body)
    access = re.findall(r'(?m)^[ \t]*give_military_access\s*=\s*([A-Z0-9_]{2,8})', body)
    idx = _diplo_index()
    overlords = [{"tag": o, "autonomy": a,
                  "label": dict(AUTONOMY_STATES).get(a, a)}
                 for o, a in idx.get(tag, [])]
    tags = []
    default = ""
    for t2 in sorted(COUNTRIES):
        c2 = COUNTRIES.get(t2) or {}
        r2 = c2.get("root") or ""
        own = bool(c2.get("history_file")) and bool(r2) and not is_under_game(r2)
        tags.append({"tag": t2, "name": LOC.get(t2, "") or t2, "own": own})
        if own and not default:
            default = t2
    tags.sort(key=lambda x: (not x["own"], x["tag"]))
    return {"ok": True, "tag": tag, "name": LOC.get(tag, "") or tag,
            "default": default or tag, "own": bool(root) and not is_under_game(root),
            "file": c.get("history_file", ""),
            "writable": bool(root) and not is_under_game(root),
            "puppets": puppets, "overlords": overlords,
            "guarantees": sorted(set(guar)), "access": sorted(set(access)),
            "autonomies": [{"key": k, "label": l} for k, l in AUTONOMY_STATES],
            "tags": tags,
            "conflict": _diplo_conflict(tag, body, idx)}


def _diplo_conflict(tag, body, idx=None):
    """返回人类可读的冲突说明（没有冲突就是空串）"""
    idx = idx if idx is not None else _diplo_index()
    ups = [o for o, _a in idx.get(tag, [])]
    guar = set(re.findall(r'(?m)^[ \t]*give_guarantee\s*=\s*([A-Z0-9_]{2,8})', body))
    for o in ups:
        if o in guar:
            return "%s 既是 %s 的附庸，又保证 %s 独立 —— 这两条同时存在时游戏里的关系会互相打架" % (tag, o, o)
    mine = [b["target"] for b in _diplo_autonomy_blocks(body)]
    both = [t for t in mine if t in guar]
    if both:
        return "%s 一边把 %s 当附庸，一边又保证它独立 —— 二选一" % (tag, both[0])
    if tag in ups:
        return "%s 被写成自己的附庸" % tag
    chain, loop = _diplo_chain(tag, idx)
    if loop:
        return "宗主链成环：%s → %s" % (tag, " → ".join(chain))
    return ""


def diplomacy_save(tag, puppets=None, overlord=None, autonomy=None,
                   guarantees=None, access=None):
    """写附庸 / 保证独立 / 军事通行。

    - puppets: 本国的附庸列表 [{"tag","autonomy"}]，None = 不改
    - overlord: 本国的宗主（"" = 解除），None = 不改。**写在宗主国的文件里**，
      因为 HOI4 只在宗主国文件里读 set_autonomy。
    """
    tag = (tag or "").strip().upper()
    if tag not in COUNTRIES:
        return {"ok": False, "msg": "没有这个国家 tag：" + tag}
    items = []
    if puppets is not None:
        seen = set()
        for it in puppets:
            t = (it.get("tag") or "").strip().upper()
            a = (it.get("autonomy") or "autonomy_puppet").strip()
            if not t or t == tag:
                continue
            if t not in COUNTRIES:
                return {"ok": False, "msg": "附庸 tag 不存在：" + t}
            if t in seen:
                continue
            if a not in dict(AUTONOMY_STATES):
                return {"ok": False, "msg": "自治度不认识：" + a}
            seen.add(t)
            items.append({"tag": t, "autonomy": a})
    over = None
    if overlord is not None:
        over = (overlord or "").strip().upper()
        if over == tag:
            return {"ok": False, "msg": "一个国家不能当自己的宗主"}
        if over and over not in COUNTRIES:
            return {"ok": False, "msg": "宗主 tag 不存在：" + over}
        if over:
            aut = (autonomy or "autonomy_puppet").strip()
            if aut not in dict(AUTONOMY_STATES):
                return {"ok": False, "msg": "自治度不认识：" + aut}
            idx = _diplo_index()
            chain, loop = _diplo_chain(over, idx)
            if loop or tag in chain:
                return {"ok": False,
                        "msg": "会让宗主链成环：%s 已经是 %s 的下级" % (over, " → ".join(chain))}

    diff = []
    # 冲突预检：用「保存后」的状态判断（传了什么就以什么为准，没传的沿用文件）
    _c0, _r0, _p0 = _hist_path(tag)
    _cur = ""
    if _p0 and os.path.exists(_p0):
        try:
            _cur = strip_comments(_read_bom_text(_p0)[0])
        except Exception:
            _cur = ""
    _pup_after = ([i["tag"] for i in items] if puppets is not None
                  else [b["target"] for b in _diplo_autonomy_blocks(_cur)])
    _guar_after = ({(x or "").strip().upper() for x in guarantees if (x or "").strip()}
                   if guarantees is not None
                   else set(re.findall(r'(?m)^[ \t]*give_guarantee\s*=\s*([A-Z0-9_]{2,8})', _cur)))
    _bad = [t for t in _pup_after if t in _guar_after]
    if _bad:
        return {"ok": False,
                "msg": "%s 一边把 %s 当附庸，一边又保证它独立 —— 只能留一个（先取消保证，或换个附庸）"
                       % (tag, _bad[0])}
    if over and over in _guar_after:
        return {"ok": False,
                "msg": "本国要当 %s 的附庸，却又保证 %s 独立 —— 只能留一个" % (over, over)}

    # 1) 本文件：自己的附庸 + 保证 + 军通
    if puppets is not None or guarantees is not None or access is not None:
        p, why = _country_write_path(tag)
        if not p:
            return {"ok": False, "msg": why}
        text, has_bom = _read_bom_text(p)
        before = strip_comments(text)
        if puppets is not None:
            old = [b["target"] for b in _diplo_autonomy_blocks(before)]
            text = _diplo_drop_blocks(text, None)
            for it in items:
                text = text.rstrip() + "\n" + _diplo_block_text(it["tag"], it["autonomy"])
            diff.append({"key": "puppets", "label": "本国的附庸",
                         "old": ", ".join(old) or "无",
                         "new": ", ".join("%s(%s)" % (i["tag"], dict(AUTONOMY_STATES).get(i["autonomy"], i["autonomy"])) for i in items) or "无"})
        if guarantees is not None:
            vals = sorted({(x or "").strip().upper() for x in guarantees if (x or "").strip().upper() in COUNTRIES})
            old = sorted(set(re.findall(r'(?m)^[ \t]*give_guarantee\s*=\s*([A-Z0-9_]{2,8})', before)))
            if vals != old:
                text = _diplo_set_lines(text, "give_guarantee", vals)
                diff.append({"key": "guarantees", "label": "保证独立",
                             "old": ", ".join(old) or "无", "new": ", ".join(vals) or "无"})
        if access is not None:
            vals = sorted({(x or "").strip().upper() for x in access if (x or "").strip().upper() in COUNTRIES})
            old = sorted(set(re.findall(r'(?m)^[ \t]*give_military_access\s*=\s*([A-Z0-9_]{2,8})', before)))
            if vals != old:
                text = _diplo_set_lines(text, "give_military_access", vals)
                diff.append({"key": "access", "label": "军事通行",
                             "old": ", ".join(old) or "无", "new": ", ".join(vals) or "无"})
        if diff:
            snapshot(p)
            _write_bom_text(p, text, has_bom)

    # 2) 宗主国文件：把「我是谁的附庸」写进去（或从旧宗主文件里删掉）
    if overlord is not None:
        idx = _diplo_index()
        olds = [o for o, _a in idx.get(tag, [])]
        drop_from = [o for o in olds if o != over]
        for o in drop_from:
            q, why = _country_write_path(o)
            if not q:
                return {"ok": False, "msg": "要从 %s 解除附庸，但写不进去：%s" % (o, why)}
            t2, b2 = _read_bom_text(q)
            t2 = _diplo_drop_blocks(t2, {tag})
            snapshot(q)
            _write_bom_text(q, t2, b2)
            diff.append({"key": "overlord_drop", "label": "%s 的文件里解除附庸" % o,
                         "old": tag, "new": ""})
        if over:
            cur = [a for o, a in idx.get(tag, []) if o == over]
            aut = (autonomy or "autonomy_puppet").strip()
            if not cur or cur[0] != aut:
                q, why = _country_write_path(over)
                if not q:
                    return {"ok": False, "msg": "要写到宗主 %s 的文件里，但写不进去：%s" % (over, why)}
                t2, b2 = _read_bom_text(q)
                t2 = _diplo_drop_blocks(t2, {tag})
                t2 = t2.rstrip() + "\n" + _diplo_block_text(tag, aut)
                snapshot(q)
                _write_bom_text(q, t2, b2)
                diff.append({"key": "overlord", "label": "%s 的文件里写入附庸" % over,
                             "old": ", ".join(cur) or "无",
                             "new": "%s（%s）" % (tag, dict(AUTONOMY_STATES).get(aut, aut))})

    if not diff:
        return {"ok": True, "msg": "没有改动", "diff": []}
    _DIPLO_INDEX["key"] = None
    reload_data()
    link_countries()
    return {"ok": True, "msg": "已写入外交关系", "diff": diff}




# v0.66 全局 flag 配对
def _flag_usage():
    """扫描事件 / 国策原文 / 精神原文里的 set_global_flag 与 has_global_flag

    国策那一段走叠加链：只扫 ROOT 那一层时，加载纯 submod（自己没有
    common/national_focus）会把父 mod / 原版里的 flag 全漏掉。
    两级去重与 _focus_refs 一致：目录去重（多 root 共享同一层）+ 同名文件
    子层优先（父层那份被整体覆盖，扫了只会把死数据当有效引用）。
    """
    sets, haves = {}, {}

    def scan(raw, where):
        if not raw:
            return
        for m in re.finditer(r'set_global_flag\s*=\s*([A-Za-z0-9_]+)', raw):
            sets.setdefault(m.group(1), where)
        for m in re.finditer(r'(?:has_global_flag|clr_global_flag)\s*=\s*([A-Za-z0-9_]+)', raw):
            haves.setdefault(m.group(1), where)

    for eid, ev in EVENTS.items():
        scan(ev.get("raw", ""), "事件 " + eid)
    for iid, idea in IDEAS.items():
        scan(idea.get("raw", ""), "精神 " + iid)
    seen_dirs, seen_files = set(), set()
    for root in ROOTS:
        for _base, d in _layer_dirs("common/national_focus", root):
            ab = os.path.abspath(d)
            if ab in seen_dirs:
                continue
            seen_dirs.add(ab)
            for fn in os.listdir(d):
                if not fn.endswith(".txt"):
                    continue
                rel = os.path.join("common", "national_focus", fn)
                if rel in seen_files:
                    continue
                seen_files.add(rel)
                try:
                    text = strip_comments(io.open(os.path.join(d, fn), encoding="utf-8", errors="replace").read())
                except Exception:
                    continue
                scan(text, "国策 " + fn)
    return sets, haves


# v0.67 脚本检查：定义清单 + 全项目引用计数
LOGIC_WORDS = {"OR", "AND", "NOT", "NOR", "NAND", "XOR", "IF", "ELSE", "LIMIT", "ELSE_IF"}
SCRIPT_CACHE = {"stamp": None, "payload": None}


def _is_logic_word(name):
    return name in LOGIC_WORDS or (name.isupper() and len(name) <= 4)


def _scripted_defs():
    """扫 scripted_triggers / scripted_effects，只认顶格定义（支持中文名）

    走叠加链（父 mod 里定义的 trigger / effect 在子 mod 里能用），但仍然跳过
    原版层 —— 这个清单是给「本 mod 项目」用的，把 Paradox 自带的两千多个脚本
    定义混进来只会让检查面板全是别人的东西。_layer_dirs 子层在前，同名文件
    按子层优先去重。"""
    out = []
    def_re = re.compile(r'(?m)^([^\W\d][\w]*)\s*=\s*\{')
    seen_dirs, seen_files = set(), set()
    for kind, sub in (("trigger", "scripted_triggers"), ("effect", "scripted_effects")):
        for root in ROOTS:
            for base, d in _layer_dirs("common/" + sub, root):
                if is_under_game(base):
                    continue
                ab = os.path.abspath(d)
                if ab in seen_dirs:
                    continue
                seen_dirs.add(ab)
                for fn in sorted(f for f in os.listdir(d) if f.endswith(".txt")):
                    rel = sub + "/" + fn
                    if rel in seen_files:
                        continue
                    seen_files.add(rel)
                    try:
                        text = strip_comments(io.open(os.path.join(d, fn), encoding="utf-8", errors="replace").read())
                    except Exception:
                        continue
                    for m in def_re.finditer(text):
                        k = m.group(1)
                        if _is_logic_word(k) or k in ("scripted_triggers", "scripted_effects"):
                            continue
                        b = text.find('{', m.end() - 1)
                        e = brace_match(text, b)
                        body = text[b + 1:e - 1].strip() if e > b else ""
                        out.append({"kind": kind, "name": k, "file": fn, "empty": not body})
    return out


def _script_ref_scan():
    """一次遍历拿到「引用统计要扫的文件」+「它们的指纹」。

    两个消费者共用这一次遍历：`_script_ref_counts` 要文件内容，
    `scripted_payload` 的缓存戳要 `(相对路径, mtime_ns, size)`。枚举口径只在这里
    定义一次——以前缓存戳只看容器长度、文件内容改了不失效，界面就会拿着旧结果
    说「这条脚本没人引用」，属于显示的是错的。

    口径与 `_script_ref_counts` 的旧实现逐条一致：
      · 走叠加链 reversed（父 → 子），跳过原版层；
      · 目录级去重跨 root 共享：多个 ROOTS 会命中同一条父链（同一个父 mod / 原版），
        不共享会把同一份文件重复计数；
      · 文件级按「相对该层根的路径」去重：HOI4 同名文件后加载的覆盖先加载的，
        从子层往父层扫（reversed），父层被覆盖的那份根本不进游戏、不该计数。

    用 `os.scandir` 而不是 `os.walk`：`DirEntry.stat()` 直接复用目录枚举返回的数据，
    Windows 上 1957 个文件「枚举 + 取 mtime/size」约 15 ms；`os.walk` 单是枚举就要
    54 ms，再逐个 `os.stat` 又要 17 ms。结果按 rel 排序，同样的文件集合总得到同样的
    元组，不会因为目录遍历顺序抖动造成假失效。

    返回 `(files, stamp)`：
      files = [(相对路径, 绝对路径)]，按 rel 升序
      stamp = (层级根元组, ((rel, mtime_ns, size), ...))
    """
    files, rows = [], []
    bases, seen_bases = [], set()
    seen_dirs, seen_files = set(), set()
    for root in ROOTS:
        for base in reversed(_chain_layers(root)):
            if is_under_game(base):
                continue
            _ab_base = os.path.abspath(base)
            if _ab_base in seen_bases:
                continue
            seen_bases.add(_ab_base)
            bases.append(_ab_base)
            # 目录一定在 base 底下，直接切前缀比 os.path.relpath 快 30 倍
            # （3463 个文件：41.5 ms → 1.3 ms），结果逐字符相同。
            _pre = _ab_base if _ab_base.endswith(os.sep) else _ab_base + os.sep
            for sub in ("common", "events", "history"):
                base_dir = os.path.join(_ab_base, sub)
                if not os.path.isdir(base_dir):
                    continue
                if base_dir in seen_dirs:
                    continue
                seen_dirs.add(base_dir)
                stack = [base_dir]
                while stack:
                    d = stack.pop()
                    try:
                        it = os.scandir(d)
                    except Exception:
                        continue
                    with it:
                        for e in it:
                            try:
                                if e.is_dir(follow_symlinks=False):
                                    stack.append(e.path)
                                    continue
                            except Exception:
                                continue
                            if not e.name.endswith(".txt"):
                                continue
                            fp = e.path
                            # 相对该层根的路径，比如 common/scripted_effects/foo.txt
                            if fp.startswith(_pre):
                                rel = fp[len(_pre):].replace(os.sep, "/")
                            else:
                                rel = os.path.relpath(fp, _ab_base).replace(os.sep, "/")
                            if rel in seen_files:
                                continue
                            seen_files.add(rel)
                            try:
                                st = e.stat()
                                rows.append((rel, st.st_mtime_ns, st.st_size))
                            except Exception:
                                rows.append((rel, -1, -1))
                            files.append((rel, fp))
    files.sort()
    rows.sort()
    return files, (tuple(bases), tuple(rows))


def _script_ref_files():
    """引用统计要扫的 .txt 清单：[(相对路径, 绝对路径)]，已按叠加链去重。

    只关心文件集合的调用方用它；要连同指纹一起拿就用 `_script_ref_scan()`，
    免得同一份枚举算两遍。
    """
    return _script_ref_scan()[0]


def _script_ref_stamp():
    """引用统计所涉文件的指纹：(层级根元组, ((rel, mtime_ns, size), ...))。

    只 stat 不读内容：1957 个文件约 15 ms，未命中要 900 ms 量级，两个数量级差。
    """
    return _script_ref_scan()[1]


def _script_ref_counts(names, files=None):
    """全项目扫 `名字 =` 形式的键出现次数（含定义本身）

    走叠加链：定义清单（_scripted_defs）已经能读到父 mod 里的 trigger / effect，
    如果引用计数还只扫 ROOTS，就等于「父层那些定义一个字都找不到」—— 实测 250
    条定义里 248 条被判成没引用，全是假警报。两个口径必须成对走链。

    要扫哪些文件由 `_script_ref_files()` 决定（与缓存戳共用同一份枚举）。
    `files` 可由调用方传入 `_script_ref_scan()` 的结果，省掉重复枚举。
    """
    counts = dict((n, 0) for n in names)
    if not names:
        return counts
    key_re = re.compile(r'(?<!\w)([^\W\d][\w]*)\s*=')
    for _rel, fp in (files if files is not None else _script_ref_files()):
        try:
            text = strip_comments(io.open(fp, encoding="utf-8",
                                          errors="replace").read())
        except Exception:
            continue
        for m in key_re.finditer(text):
            n = m.group(1)
            if n in counts:
                counts[n] += 1
    return counts


def scripted_payload():
    """返回脚本清单（带缓存，数据变了才重扫）

    戳由两部分组成：
      · 内存容器规模（ROOTS / TREES / EVENTS / IDEAS / TECHS）——加载、重载、增删条目后变；
      · 引用统计涉及的每个 .txt 的 (相对路径, mtime_ns, size) 指纹，外加层级根列表——
        用户改一个文件的内容（比如给某个 scripted trigger 加一处引用）时容器长度
        全不变，只有这一项能发现改动。
    少了第二部分，改了文件还能命中旧缓存，界面显示的是错的。

    命中路径只做一次目录枚举 + stat（1957 个文件约 15 ms，原来是 0 ms 但答案是错的）；
    未命中时复用同一次枚举拿到的文件清单，不重复走目录。
    """
    files, fs = _script_ref_scan()
    stamp = (tuple(ROOTS), len(TREES), len(EVENTS), len(IDEAS), len(TECHS), fs)
    if SCRIPT_CACHE["stamp"] == stamp and SCRIPT_CACHE["payload"]:
        hit = dict(SCRIPT_CACHE["payload"])
        hit["cached"] = True
        return hit
    defs = _scripted_defs()
    counts = _script_ref_counts(set(d["name"] for d in defs), files=files)
    items = []
    for d in defs:
        items.append({"name": d["name"], "kind": d["kind"], "file": d["file"],
                      "refs": counts.get(d["name"], 0), "empty": d["empty"]})
    items.sort(key=lambda x: (x["refs"], x["name"]))
    unused = len([i for i in items if i["refs"] <= 1])
    payload = {"ok": True, "items": items, "total": len(items), "unused": unused, "cached": False}
    SCRIPT_CACHE["stamp"] = stamp
    SCRIPT_CACHE["payload"] = payload
    return payload


# v0.71 地图图层构建（Pillow，无需 numpy）
_state.set_map_var("MAP_CACHE_DIR", os.path.join(WORK, "cache", "map"))
_state.set_map_var("MAP_ASSETS", ("base.png", "province.png", "edges.png", "state.png", "political.png", "political_strict.png", "region.png", "terrain.png", "continent.png", "prov_id.png", "rivers.png", "units.png",
              "prov_index.json", "centers.json", "regions.json", "meta.json"))




_dir_mtime = _paths._dir_mtime     # 实现在 core.paths，这里只留名字给本文件第 1550 行附近用






# v0.73 地图多来源
# -*- coding: utf-8 -*-
"""更新检查：查 GitHub 最新 Release，与本地版本比较。

设计要点：
- 只查一次 /releases/latest，GitHub 未认证配额 60 次/小时，缓存 6 小时后足够
- 任何网络失败都静默返回「检查不了」，不打扰用户
- 版本比较按数字段，忽略前缀 v 与后缀
"""
import json
import os
import re
import time

UPDATE_CACHE = os.path.join(WORK, "cache", "update.json")
UPDATE_TTL = 6 * 3600          # 6 小时内不重复请求
UPDATE_STATE = {"last": 0, "result": None}


def _ver_tuple(v):
    """1.2.3 → (1,2,3)；解析不出来的段按 0"""
    parts = re.findall(r"\d+", str(v or ""))
    return tuple(int(x) for x in parts[:4]) if parts else (0,)


def _ver_newer(a, b):
    ta, tb = _ver_tuple(a), _ver_tuple(b)
    n = max(len(ta), len(tb))
    ta = ta + (0,) * (n - len(ta))
    tb = tb + (0,) * (n - len(tb))
    return ta > tb


def check_update(force=False, timeout=6):
    """返回 {ok, current, latest, newer, url, notes, published, checked, msg}"""
    now = time.time()
    if not force:
        # 内存缓存
        if UPDATE_STATE["result"] and now - UPDATE_STATE["last"] < UPDATE_TTL:
            return dict(UPDATE_STATE["result"])
        # 磁盘缓存
        try:
            if os.path.exists(UPDATE_CACHE) and now - os.path.getmtime(UPDATE_CACHE) < UPDATE_TTL:
                cached = json.loads(io.open(UPDATE_CACHE, encoding="utf-8").read())
                UPDATE_STATE["result"] = cached
                UPDATE_STATE["last"] = os.path.getmtime(UPDATE_CACHE)
                return dict(cached)
        except Exception:
            pass

    out = {"ok": False, "current": APP_VERSION, "latest": "", "newer": False,
           "url": "https://github.com/%s/releases/latest" % REPO,
           "notes": "", "published": "", "checked": time.strftime("%Y-%m-%d %H:%M:%S"),
           "msg": ""}
    try:
        req = urllib.request.Request(
            "https://api.github.com/repos/%s/releases/latest" % REPO,
            headers={"User-Agent": "xuerong-editor/%s" % APP_VERSION,
                     "Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.loads(r.read().decode())
        out["ok"] = True
        out["latest"] = (d.get("tag_name") or "").lstrip("v")
        out["url"] = d.get("html_url") or out["url"]
        out["published"] = (d.get("published_at") or "")[:10]
        body = d.get("body") or ""
        out["notes"] = body[:1200]
        out["assets"] = [{"name": a.get("name"), "size": a.get("size"),
                          "url": a.get("browser_download_url")}
                         for a in (d.get("assets") or [])]
        out["newer"] = _ver_newer(out["latest"], APP_VERSION)
    except Exception as e:
        out["msg"] = "检查失败：%s" % str(e)[:120]

    try:
        os.makedirs(os.path.dirname(UPDATE_CACHE), exist_ok=True)
        io.open(UPDATE_CACHE, "w", encoding="utf-8", newline="").write(json.dumps(out, ensure_ascii=False))
    except Exception:
        pass
    UPDATE_STATE["result"] = out
    UPDATE_STATE["last"] = now
    return out


def app_info():
    return {"version": APP_VERSION, "repo": REPO, "frozen": FROZEN,
            "exe": sys.executable if FROZEN else ""}


# v1.0.3 一键更新
UPDATE_PKG_DIR = os.path.join(WORK, "cache", "update_pkg")


def update_download(asset_url=None, expect_size=0, timeout=180):
    """下载新版 exe 到缓存目录并校验（MZ 头 + 体积）。返回 {ok, path, size, msg}"""
    if not asset_url:
        info = check_update(force=True)
        exe_asset = None
        for a in (info.get("assets") or []):
            if str(a.get("name") or "").lower().endswith(".exe"):
                exe_asset = a
                break
        if not exe_asset:
            return {"ok": False, "msg": "最新版本里没有 exe 附件"}
        asset_url = exe_asset["url"]
        expect_size = exe_asset.get("size") or 0
    try:
        os.makedirs(UPDATE_PKG_DIR, exist_ok=True)
        dst = os.path.join(UPDATE_PKG_DIR, "xuerong_new.exe")
        tmp = dst + ".part"
        req = urllib.request.Request(asset_url, headers={"User-Agent": "xuerong-editor/%s" % APP_VERSION})
        got = 0
        with urllib.request.urlopen(req, timeout=timeout) as r, open(tmp, "wb") as f:
            while True:
                chunk = r.read(1 << 20)
                if not chunk:
                    break
                f.write(chunk)
                got += len(chunk)
                if got > 300 * 1024 * 1024:
                    return {"ok": False, "msg": "下载体积异常，已中止"}
        size = os.path.getsize(tmp)
        with open(tmp, "rb") as f:
            magic = f.read(2)
        if magic != b"MZ":
            os.remove(tmp)
            return {"ok": False, "msg": "下载到的不是 exe（缺少 MZ 头）"}
        if expect_size and abs(size - int(expect_size)) > 2048:
            os.remove(tmp)
            return {"ok": False, "msg": "体积不符（期望 %d，实际 %d）" % (int(expect_size), size)}
        os.replace(tmp, dst)
        return {"ok": True, "path": dst, "size": size,
                "msg": "已下载 %.1f MB，校验通过" % (size / 1048576)}
    except Exception as e:
        return {"ok": False, "msg": "下载失败：%s" % str(e)[:160]}


def update_apply(launch=False):
    """把新版 zip 解压到 exe 旁边的独立目录，不改动正在运行的文件。
    零风险：解压失败不影响当前版本；用户从新目录启动即可。"""
    info = check_update(force=True)
    latest = info.get("latest") or ""
    zip_asset = None
    for a in (info.get("assets") or []):
        if str(a.get("name") or "").lower().endswith(".zip"):
            zip_asset = a
            break
    if not zip_asset:
        return {"ok": False, "msg": "最新版本里没有 zip 附件，请到 Release 页手动下载"}

    base_dir = os.path.dirname(sys.executable) if FROZEN else WORK
    out_dir = os.path.join(base_dir, "_update_%s" % (latest or "latest"))
    try:
        os.makedirs(os.path.dirname(out_dir), exist_ok=True)
    except Exception:
        pass

    zpath = os.path.join(UPDATE_PKG_DIR, "update.zip")
    try:
        os.makedirs(UPDATE_PKG_DIR, exist_ok=True)
        req = urllib.request.Request(zip_asset["url"],
                                     headers={"User-Agent": "xuerong-editor/%s" % APP_VERSION})
        got = 0
        with urllib.request.urlopen(req, timeout=300) as r, open(zpath, "wb") as f:
            while True:
                chunk = r.read(1 << 20)
                if not chunk:
                    break
                f.write(chunk)
                got += len(chunk)
        if got < 1024 * 1024:
            return {"ok": False, "msg": "下载不完整（%.1f KB）" % (got / 1024)}
    except Exception as e:
        return {"ok": False, "msg": "下载失败：%s" % str(e)[:160]}

    try:
        if os.path.isdir(out_dir):
            shutil.rmtree(out_dir, ignore_errors=True)
        with zipfile.ZipFile(zpath) as z:
            z.extractall(out_dir)
        # zip 里通常多一层同名目录，找到真正的 exe
        real_exe = None
        for dp, _dn, fs in os.walk(out_dir):
            for fn in fs:
                if fn.lower().endswith(".exe"):
                    real_exe = os.path.join(dp, fn)
                    break
            if real_exe:
                break
        if not real_exe:
            return {"ok": False, "msg": "解压后没找到 exe"}
        if launch:
            try:
                os.startfile(os.path.dirname(real_exe))      # 打开所在文件夹
            except Exception:
                pass
        return {"ok": True, "version": latest, "dir": out_dir, "exe": real_exe,
                "size": round(got / 1048576, 1),
                "msg": "新版已解压到：%s（当前窗口可以关闭，从新目录启动即可，旧版本不改动）"
                       % os.path.dirname(real_exe)}
    except Exception as e:
        return {"ok": False, "msg": "解压失败：%s" % str(e)[:160]}












_state.set_map_var("_REFINE_IDS_CACHE", {})




def _refine_grow_units(unit_ids, neighbors, k, coord=None):
    """通用水位生长：把一组单元分成 k 组，每组尽量等量，组内连通。

    unit_ids: 单元 id 列表
    neighbors: {unit_id: [相邻 unit_id, ...]}
    k: 分成几组
    coord: {unit_id: (x, y)} —— 用于选种子；缺省则按 unit_ids 顺序取

    返回 {group_i: [unit_id, ...]}
    """
    from collections import deque
    units = list(unit_ids)
    if not units:
        return {}
    k = max(1, min(k, len(units)))
    c = coord or {u: (i, 0) for i, u in enumerate(units)}

    # 最远点采样选种子
    cx = sum(c[u][0] for u in units) / len(units)
    cy = sum(c[u][1] for u in units) / len(units)
    first = min(units, key=lambda u: (c[u][0] - cx) ** 2 + (c[u][1] - cy) ** 2)
    seeds = [first]
    dist = {u: (c[u][0] - c[first][0]) ** 2 + (c[u][1] - c[first][1]) ** 2 for u in units}
    guard = 0
    while len(seeds) < k and guard < 2000:
        guard += 1
        nxt = max(dist, key=dist.get)
        if dist[nxt] <= 0:
            break
        seeds.append(nxt)
        for u in units:
            d = (c[u][0] - c[nxt][0]) ** 2 + (c[u][1] - c[nxt][1]) ** 2
            if d < dist[u]:
                dist[u] = d

    K = len(seeds)
    total = len(units)
    budget = [total // K + (1 if i < total % K else 0) for i in range(K)]
    owner = {}
    grown = [0] * K
    fronts = []
    for i, s in enumerate(seeds):
        owner[s] = i
        grown[i] = 1
        fronts.append([s])
    active = True
    guard = 0
    while active and guard < 200000:
        guard += 1
        active = False
        for i in range(K):
            if grown[i] >= budget[i] or not fronts[i]:
                continue
            nxt = []
            for u in fronts[i]:
                for nb in (neighbors.get(u) or []):
                    if nb not in owner:
                        owner[nb] = i
                        grown[i] += 1
                        nxt.append(nb)
                        if grown[i] >= budget[i]:
                            break
                if grown[i] >= budget[i]:
                    break
            fronts[i] = nxt
            if grown[i] < budget[i] and nxt:
                active = True
    # 剩余单元归最近的已分配邻居
    rest = [u for u in units if u not in owner]
    if rest:
        q = deque(rest)
        while q:
            u = q.popleft()
            if u in owner:
                continue
            best = None
            for nb in (neighbors.get(u) or []):
                if nb in owner:
                    best = owner[nb]
                    break
            if best is None:
                continue
            owner[u] = best
            for nb in (neighbors.get(u) or []):
                if nb not in owner:
                    q.append(nb)

    groups = {}
    for u, g in owner.items():
        groups.setdefault(g, []).append(u)
    return groups


def _refine_split(ids, w, h, pid, k):
    """省细化：像素为单元（保留原接口，内部走通用逻辑）"""
    px = [i for i in range(len(ids)) if ids[i] == pid]
    if not px:
        return None
    # 像素邻居按 4 邻域现算太慢，直接用座标构造邻居（只在同省内）
    pxset = set(px)
    nb = {}
    for i in px:
        x, y = i % w, i // w
        lst = []
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if 0 <= nx < w and 0 <= ny < h:
                j = ny * w + nx
                if j in pxset:
                    lst.append(j)
        nb[i] = lst
    coord = {i: (i % w, i // w) for i in px}
    groups = _refine_grow_units(px, nb, k, coord)
    owner = {}
    for g, members in groups.items():
        for i in members:
            owner[i] = g
    return {"owner": owner, "seeds": [], "px": px}


def refine_preview(pid, k=2, root=None):
    """预览切分：不写盘，返回每块的像素数与包围盒"""
    pid = int(pid or 0)
    k = max(2, min(64, int(k or 2)))
    if pid <= 0:
        return {"ok": False, "msg": "先选一个省"}
    root = _map_pick(root)
    ids, w, h = _refine_load_ids(root)
    if not ids:
        return {"ok": False, "msg": "读不到 provinces.bmp / definition.csv"}
    res = _refine_split(ids, w, h, pid, k)
    if not res:
        return {"ok": False, "msg": "省 %d 没有像素" % pid}
    from collections import Counter
    owner = res["owner"]
    cnt = Counter(owner.values())
    parts = []
    for kk in sorted(cnt):
        pts = [i for i, v in owner.items() if v == kk]
        xs = [p % w for p in pts]
        ys = [p // w for p in pts]
        parts.append({"i": kk, "px": cnt[kk],
                      "bbox": [min(xs), min(ys), max(xs) - min(xs) + 1, max(ys) - min(ys) + 1],
                      # 描边用：只回包围盒内的相对坐标，前端按比例画
                      "pts": [(p % w - min(xs)) * 100000 + (p // w - min(ys)) for p in pts][:20000]})
    # 细化前把风险讲清楚：VP 会移动、首都会偏、新省要不要进州
    _p2s, _dups = _prov_state_map()
    _warn, _sid = _refine_state_warnings(pid, _p2s)
    if pid in _dups:
        _warn.insert(0, "省 %d 同时被州 %s 声明（数据冲突），本次按第一个州处理，建议先修正" % (
            pid, " / ".join(str(x) for x in _dups[pid])))
    return {"ok": True, "pid": pid, "k": len(cnt), "total": len(res["px"]),
            "state": _sid, "warnings": _warn,
            "parts": parts, "msg": "切成 %d 块，面积 %s" % (
                len(cnt), sorted(cnt.values(), reverse=True))}


def refine_apply(pid, k=2, root=None, base_pid=None):
    """应用切分：分配新省号 → 写 bmp + definition.csv"""
    pid = int(pid or 0)
    k = max(2, min(64, int(k or 2)))
    if pid <= 0:
        return {"ok": False, "msg": "先选一个省"}
    root = _map_pick(root)
    layers = mod_layers(root)
    bmp, _ = _layers_find("map/provinces.bmp", layers)
    csvp, _ = _layers_find("map/definition.csv", layers)
    if not bmp or not csvp:
        return {"ok": False, "msg": "找不到地图文件"}
    if is_under_game(bmp):
        return {"ok": False, "msg": "地图来自原版，只读"}
    ids, w, h = _refine_load_ids(root)
    if not ids:
        return {"ok": False, "msg": "读不到省数据"}
    res = _refine_split(ids, w, h, pid, k)
    if not res:
        return {"ok": False, "msg": "省 %d 没有像素" % pid}
    owner = res["owner"]

    # 读 definition.csv：拿省号上限与已用 RGB
    rows = []
    used_rgb = set()
    max_pid = 0
    with io.open(csvp, encoding="utf-8", errors="replace") as f:
        for line in f:
            s = line.rstrip("\r\n")
            rows.append(s)
            p = s.split(";")
            if len(p) >= 8 and p[0].isdigit():
                n = int(p[0])
                max_pid = max(max_pid, n)
                used_rgb.add((int(p[1]), int(p[2]), int(p[3])))
    # 原省信息（地形/洲等沿用）
    src = None
    for s in rows:
        p = s.split(";")
        if len(p) >= 8 and p[0].isdigit() and int(p[0]) == pid:
            src = p
            break
    if not src:
        return {"ok": False, "msg": "definition.csv 里没有省 %d" % pid}

    from collections import Counter
    cnt = Counter(owner.values())
    keys = sorted(cnt)
    # 第一块沿用原省号，其余分配新号
    assign = {keys[0]: pid}
    nid = max_pid + 1
    for kk in keys[1:]:
        while nid in used_rgb_ids(rows) or nid == pid:
            nid += 1
        assign[kk] = nid
        nid += 1

    # 新 RGB
    new_rows = []
    rgb_map = {keys[0]: (int(src[1]), int(src[2]), int(src[3]))}
    for kk in keys[1:]:
        rgb = _refine_free_rgb(used_rgb)
        used_rgb.add(rgb)
        rgb_map[kk] = rgb
        row = list(src)
        row[0] = str(assign[kk])
        row[1], row[2], row[3] = str(rgb[0]), str(rgb[1]), str(rgb[2])
        new_rows.append(";".join(row))

    if not new_rows:
        return {"ok": False, "msg": "只有一块，不需要新增"}

    # 写 definition.csv
    snapshot(csvp)
    body = chr(10).join(rows + new_rows) + chr(10)
    _atomic_write(csvp, body.encode("utf-8"))

    # 写 bmp：只改这块区域内像素
    xs = [p % w for p in owner]
    ys = [p // w for p in owner]
    bx, by = min(xs), min(ys)
    bw, bh = max(xs) - bx + 1, max(ys) - by + 1
    before = bmp_read_rect(bmp, bx, by, bw, bh)
    if before is None:
        return {"ok": False, "msg": "读 bmp 区域失败"}
    after = list(before)
    for i, kk in owner.items():
        if assign[kk] == pid:
            continue
        _o = (i // w - by) * bw + (i % w - bx)
        if 0 <= _o < len(after):
            after[_o] = rgb_map[kk]
    _lay_ws = _refine_out_bmp(bmp)
    if _lay_ws != bmp:
        os.makedirs(os.path.dirname(_lay_ws) or ".", exist_ok=True)
        shutil.copyfile(bmp, _lay_ws)
        snapshot(_lay_ws)
        bmp = _lay_ws
    bmp_write_rect(bmp, bx, by, bw, bh, after)
    _REFINE_IDS_CACHE.pop("cur", None)

    # 新省必须进州，否则是孤儿地块（没有 owner / 建筑槽 / 人口）
    _new_ids = [assign[kk] for kk in keys[1:]]
    _p2s2, _ = _prov_state_map()
    _sid2 = _p2s2.get(pid, 0)
    _state_rel = _refine_attach_to_state(root, _sid2, _new_ids, pid)
    reload_data()

    _m = "已切成 %d 块，新增省号 %s" % (len(keys), _new_ids)
    if _state_rel:
        _m += "；已加入州 %d（%s）" % (_sid2, _state_rel)
    elif _sid2:
        _m += "；加入州 %d 失败，需手动处理" % _sid2
    else:
        _m += "；原省无州归属，新省也未归属"
    return {"ok": True, "pid": pid, "new_ids": _new_ids, "state": _sid2,
            "stateFile": _state_rel,
            "parts": len(keys), "pixels": len(owner), "rect": [bx, by, bw, bh],
            "msg": _m}


def used_rgb_ids(rows):
    out = set()
    for s in rows:
        p = s.split(";")
        if len(p) >= 8 and p[0].isdigit():
            out.add(int(p[0]))
    return out


def _refine_free_rgb(used):
    """找一个未被使用的省色（避开 0,0,0 与已有色）"""
    for r in range(1, 256):
        for g in range(1, 256, 3):
            for b in range(1, 256, 7):
                if (r, g, b) not in used:
                    return (r, g, b)
    return (250, 250, 250)


def _refine_out_bmp(path):
    """输出模式下把源 bmp 映射到 output/ 的副本"""
    return _out_path(path)








# v1.0.9 playset 编辑器
PLAYSET_FILE = os.path.join(WORK, "playset.json")


# v1.1.1 输出目录模式（P0-3 B0：容器与标量都搬到 state，这里只做实参初始化）
_state.set_output_root(os.path.join(WORK, "output"))


def output_state():
    """输出模式状态与统计"""
    files = 0
    size = 0
    if os.path.isdir(_state.output_root()):
        for dp, _dn, fs in os.walk(_state.output_root()):
            for fn in fs:
                files += 1
                try:
                    size += os.path.getsize(os.path.join(dp, fn))
                except Exception:
                    pass
    return {"ok": True, "on": _state.output_mode(), "root": _state.output_root(),
            "files": files, "size": size}


def output_toggle(on=None):
    _state.set_output_mode(bool(on) if on is not None else (not _state.output_mode()))
    return {"ok": True, "on": _state.output_mode(),
            "msg": "输出模式已开启：改动写到 %s，源 mod 不动" % _state.output_root() if _state.output_mode()
                   else "输出模式已关闭：改动直接写 mod 目录（仍有备份）"}






def output_apply_back(paths=None):
    """把输出目录里的文件复制回对应 mod（复制前给源文件做快照备份）"""
    if not os.path.isdir(_state.output_root()):
        return {"ok": False, "msg": "输出目录为空，没有可回源的文件"}
    done, skipped = [], []
    for modname in os.listdir(_state.output_root()):
        src_mod_dir = os.path.join(_state.output_root(), modname)
        if not os.path.isdir(src_mod_dir):
            continue
        target_root = None
        for r in ROOTS:
            if os.path.basename(os.path.abspath(r).rstrip("\\/")) == modname:
                target_root = os.path.abspath(r)
                break
        if not target_root:
            skipped.append({"mod": modname, "why": "当前没有加载同名的 mod"})
            continue
        for dp, _dn, fs in os.walk(src_mod_dir):
            for fn in fs:
                src = os.path.join(dp, fn)
                rel = os.path.relpath(src, src_mod_dir)
                dst = os.path.join(target_root, rel)
                try:
                    if os.path.exists(dst):
                        snapshot(dst)
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.copy2(src, dst)
                    CHANGED[dst] = rel
                    done.append(rel)
                except Exception as e:
                    skipped.append({"file": rel, "why": str(e)[:80]})
    return {"ok": True, "applied": len(done), "files": done[:40], "skipped": skipped,
            "msg": "已把 %d 个文件复制回 mod（原文件已备份）" % len(done)}


def output_clear():
    """清空输出目录（不动 mod）"""
    try:
        if os.path.isdir(_state.output_root()):
            shutil.rmtree(_state.output_root(), ignore_errors=True)
        return {"ok": True, "msg": "输出目录已清空"}
    except Exception as e:
        return {"ok": False, "msg": "清空失败：%s" % e}


def playset_get():


    """返回当前叠加链（按启动器加载顺序）"""
    layers = []
    for r in ROOTS:
        ab = os.path.abspath(r)
        desc = _mod_descriptor(ab)
        layers.append({
            "path": ab,
            "name": desc["name"] or os.path.basename(ab),
            "has_descriptor": os.path.exists(os.path.join(ab, "descriptor.mod")),
            "has_map": os.path.exists(os.path.join(ab, "map", "provinces.bmp")),
            "replace_count": len(desc["replace"]),
            "deps": desc["deps"],
        })
    return {"ok": True, "layers": layers, "game": GAME or "",
            "saved": os.path.exists(PLAYSET_FILE),
            "order": "列表从下往上覆盖：越靠下加载越晚，优先级越高"}


def playset_validate(paths):
    """校验一组 mod 路径，返回 (可用列表, 问题列表)"""
    good, bad = [], []
    for p in paths or []:
        ab = os.path.abspath(str(p or ""))
        if not os.path.isdir(ab):
            bad.append({"path": ab, "why": "目录不存在"})
            continue
        has_desc = os.path.exists(os.path.join(ab, "descriptor.mod"))
        has_nf = os.path.isdir(os.path.join(ab, "common", "national_focus"))
        has_any = os.path.isdir(os.path.join(ab, "common")) or os.path.isdir(os.path.join(ab, "map"))
        if not (has_desc or has_nf or has_any):
            bad.append({"path": ab, "why": "不像 mod 根目录（无 descriptor.mod / common / map）"})
            continue
        good.append(ab)
    return good, bad


def playset_save(paths):
    """保存播放集到 work/playset.json。重启后生效（运行中切换会打乱已加载的状态）。"""
    good, bad = playset_validate(paths)
    try:
        os.makedirs(WORK, exist_ok=True)
        io.open(PLAYSET_FILE, "w", encoding="utf-8", newline="").write(
            json.dumps({"order": good, "saved": time.strftime("%Y-%m-%d %H:%M:%S")},
                       ensure_ascii=False, indent=1))
    except Exception as e:
        return {"ok": False, "msg": "保存失败：%s" % e}
    _LAYERS_CACHE.clear()
    return {"ok": True, "count": len(good), "bad": bad,
            "msg": "已保存 %d 个 mod（顺序：越靠下优先级越高）。重启编辑器后生效。" % len(good)}


def playset_load_saved():
    """启动时读 playset.json（没有 --mod 参数时使用）"""
    try:
        if not os.path.exists(PLAYSET_FILE):
            return []
        d = json.loads(io.open(PLAYSET_FILE, encoding="utf-8").read())
        out = []
        for p in (d.get("order") or []):
            if p and os.path.isdir(p) and p not in out:
                out.append(p)
        return out
    except Exception:
        return []








# v0.91 mod 叠加链（submod 支持）




# ---- v1.23.45 跟随启动器加载依赖 -----------------------------------------
#
# 玩家在启动器里勾选的顺序写在 dlc_load.json 的 enabled_mods 里，**游戏就是按这个
# 顺序叠加的**；descriptor 的 dependencies 只是启动器用来提示「你缺前置」的元数据，
# 不进加载链。
#
# 两个开关分开（v1.24.0）：
#   follow_deps     → 递归展开 descriptor 的 dependencies。用户写 dependencies 就是
#                     声明「我需要这些」，默认开。
#   follow_launcher → 把启动器里排在自己前面的 mod 也铺进来。这是一个更大的集合，
#                     可能包含音乐包/界面 mod 之类跟当前编辑无关的东西，默认**关**。
#
# 老配置 {"follow_launcher": x} 读进来时 follow_deps 保持默认 True，
# 于是自动迁移成 {"follow_deps": True, "follow_launcher": x}，行为不突变。



































def write_note(mod_root, sub):
    """给界面用的一句话说明：这个目录的改动会落到哪里。"""
    owner = _replace_owner(mod_root, sub)
    if owner:
        return "%s 被 %s 的 replace_path 独占，改动只能写进该 mod" % (
            sub, os.path.basename(owner.rstrip("\\/")) or owner)
    return "%s 未被 replace_path 接管，改动写进当前 mod" % sub




def adopt_dir(mod_root, sub, force=False, reload=True):
    """在自己的 mod 里接管某个目录。

    这是 CNsub 对 CN 做法的自动化：
      1. 从当前生效的那一层全量拷贝该目录的文件
      2. 在自己的 descriptor.mod 里加 replace_path
    之后改这个目录，游戏就会读自己的那份。

    只允许对链顶 mod 操作，不会动父 mod 或原版。
    """
    sub = (sub or "").replace("\\", "/").strip("/")
    if not sub:
        return {"ok": False, "msg": "目录名不能为空"}
    # 顶层桶目录（common / history / gfx…）不能整目录接管：原版 common 有 2267 个
    # 文件，搬进来再写 replace_path="common"，等于把整个游戏数据换成一份残缺副本，
    # 加载期直接崩。这类目录要改只能逐个文件接管。
    if "/" not in sub:
        return {"ok": False,
                "msg": "%s 是顶层目录，整目录接管会把几千个文件搬进 mod 并写 "
                       "replace_path=\"%s\"，等于换掉整个 %s；请改用单文件接管或撤销 replace"
                       % (sub, sub, sub)}

    # 目标必须是链顶（自己可写的那层），不能是原版。
    # 用 _top_mod 而不是只查 ROOTS：脚本调用（world_create 编排、qa 脚本）时
    # ROOTS 是空的，只查 ROOTS 会误报「找不到可写的 mod 目录」。
    top = _top_mod(mod_root)
    if not top or is_under_game(top):
        return {"ok": False, "msg": "找不到可写的 mod 目录"}
    if mod_root and os.path.abspath(mod_root) != os.path.abspath(top):
        return {"ok": False, "msg": "只能对当前加载的最上层 mod 操作"}

    layers = mod_layers(top) or [top]
    # 源：当前生效的那一层（有 replace_path 就取接管层，否则取链里最后有的）。
    # 一定要跳过 top 自己：把自己拷给自己会抛 SameFileError 被吞掉，
    # 结果是「拷贝 0 个文件」却照样写了 replace_path，看起来成功实则什么都没做。
    src = _replace_owner(top, sub)
    if src and os.path.abspath(src) == os.path.abspath(top):
        src = None
    if not src:
        for b in reversed(layers):
            if not b or os.path.abspath(b) == os.path.abspath(top):
                continue
            if os.path.isdir(os.path.join(b, sub.replace("/", os.sep))):
                src = b
                break
    if not src:
        return {"ok": False, "msg": "叠加链里找不到 %s（父层和原版都没有这个目录）" % sub}

    src_d = os.path.join(src, sub.replace("/", os.sep))
    dst_d = os.path.join(top, sub.replace("/", os.sep))
    if not os.path.isdir(src_d):
        return {"ok": False, "msg": "源目录不存在：%s" % src_d}

    already = os.path.isdir(dst_d) and os.listdir(dst_d)
    if already and not force:
        return {"ok": False, "need_confirm": True,
                "msg": "自己的 mod 里已经有 %s（%d 个文件），接管会覆盖同名文件" % (
                    sub, len(os.listdir(dst_d)))}

    # 全量拷贝（必须递归：common/decisions 有 categories 子目录，
    # common/characters 有 dynasty 之类的子目录，只拷一层会让这些定义全部丢失，
    # 游戏加载时报 Invalid Decision Category / Unknown character 之类）
    os.makedirs(dst_d, exist_ok=True)
    copied = 0
    for root_dir, _dirs, files in os.walk(src_d):
        rel = os.path.relpath(root_dir, src_d)
        dst_dir = dst_d if rel == "." else os.path.join(dst_d, rel)
        os.makedirs(dst_dir, exist_ok=True)
        for fn in files:
            sp = os.path.join(root_dir, fn)
            dp = os.path.join(dst_dir, fn)
            try:
                if force or not os.path.exists(dp):
                    import shutil as _sh
                    _sh.copyfile(sp, dp)
                    copied += 1
            except Exception:
                pass

    # 在 descriptor.mod 里加 replace_path
    desc_path = os.path.join(top, "descriptor.mod")
    added = False
    try:
        txt = ""
        if os.path.exists(desc_path):
            txt = io.open(desc_path, encoding="utf-8-sig", errors="replace").read()
        norm = sub.lower()
        have = [x.replace("\\", "/").strip("/").lower()
                for x in re.findall(r'replace_path\s*=\s*"([^"]*)"', txt)]
        if norm not in have:
            if txt and not txt.endswith("\n"):
                txt += "\n"
            txt += 'replace_path="%s"\n' % sub
            _atomic_write(desc_path, _bom_for(desc_path) + txt.encode("utf-8"))
            added = True
    except Exception as e:
        return {"ok": False, "msg": "目录已拷贝，但 descriptor.mod 写入失败：%s" % e}

    # 清缓存，让下次读取按新结构走
    try:
        _LAYERS_CACHE.clear()
        _paths._DESC_CACHE.clear()
    except Exception:
        pass
    if reload:
        reload_data()

    src_name = os.path.basename(src.rstrip("\\/")) or src
    # 接管立刻校验：replace_path 会让上级目录失效，漏一个文件就少一份数据
    chk = verify_adopt(top, sub)
    return {"ok": True, "sub": sub, "from": src_name,
            "copied": copied, "replace_added": added,
            "check": chk,
            "msg": "已从 %s 接管 %s：拷贝 %d 个文件%s；%s" % (
                src_name, sub, copied,
                "，并写入 replace_path" if added else "（replace_path 已存在）",
                chk.get("msg") or "")}


def _file_md5(path, limit=4 << 20):
    """文件的 md5，超过 limit 的只算头部 + 大小，够分辨改动即可。"""
    try:
        h = hashlib.md5()
        sz = os.path.getsize(path)
        with open(path, "rb") as f:
            h.update(f.read(limit))
        h.update(str(sz).encode())
        return h.hexdigest()
    except Exception:
        return ""


def verify_adopt(mod_root, sub):
    """校验某个目录是否被完整接管。

    回答三件事：
      1. 源目录有几个文件、自己的副本有几个
      2. 有没有漏拷（源里有、自己没）
      3. 同名文件内容是否一致（不一致说明改过，这是正常的；未改却不同才是问题）
    """
    sub = (sub or "").replace("\\", "/").strip("/")
    if not sub:
        return {"ok": False, "msg": "目录名不能为空"}

    root = _map_pick(mod_root)
    top = None
    for r in (ROOTS or []):
        lay = mod_layers(r) or [r]
        cand = lay[-1] if lay else r
        if cand and not is_under_game(cand):
            top = cand
    if not top:
        return {"ok": False, "msg": "找不到可写的 mod 目录"}

    dst_d = os.path.join(top, sub.replace("/", os.sep))
    if not os.path.isdir(dst_d):
        return {"ok": False, "msg": "自己的 mod 里没有 %s，还没接管" % sub}

    # 源：接管时读的那一层。已被自己接管时，_replace_owner 会返回自己，
    # 这时要往上找真正的来源。
    src = None
    layers = mod_layers(top) or [top]
    for b in reversed(layers):
        if not b or os.path.abspath(b) == os.path.abspath(top):
            continue
        d = os.path.join(b, sub.replace("/", os.sep))
        if os.path.isdir(d):
            src = b
            break
    if not src:
        return {"ok": False,
                "msg": "叠加链里找不到上级来源（说明该目录只有你自己这一份）"}

    src_d = os.path.join(src, sub.replace("/", os.sep))
    src_files = {f for f in os.listdir(src_d) if os.path.isfile(os.path.join(src_d, f))}
    dst_files = {f for f in os.listdir(dst_d) if os.path.isfile(os.path.join(dst_d, f))}

    missing = sorted(src_files - dst_files)
    extra = sorted(dst_files - src_files)
    differ = []
    for fn in sorted(src_files & dst_files):
        if _file_md5(os.path.join(src_d, fn)) != _file_md5(os.path.join(dst_d, fn)):
            differ.append(fn)

    # 漏拷是致命问题：replace_path 接管后，上级的同名目录不再被读，
    # 缺一个文件游戏里就少一份数据。
    fatal = len(missing) > 0
    parts = ["源 %d 个文件，自己 %d 个" % (len(src_files), len(dst_files))]
    if missing:
        parts.append("缺 %d 个" % len(missing))
    if extra:
        parts.append("多 %d 个（自己新增的）" % len(extra))
    if differ:
        parts.append("内容不同 %d 个（改过的）" % len(differ))

    return {
        "ok": not fatal,
        "sub": sub,
        "src": os.path.basename(src.rstrip("\\/")) or src,
        "src_count": len(src_files),
        "dst_count": len(dst_files),
        "missing": missing[:50],
        "missing_count": len(missing),
        "extra": extra[:50],
        "extra_count": len(extra),
        "differ": differ[:50],
        "differ_count": len(differ),
        "msg": "；".join(parts),
    }


def verify_all_adopted(mod_root=None):
    """把所有被自己接管的目录逐个校验一遍。"""
    root = _map_pick(mod_root)
    top = None
    for r in (ROOTS or []):
        lay = mod_layers(r) or [r]
        cand = lay[-1] if lay else r
        if cand and not is_under_game(cand):
            top = cand
    if not top:
        return {"ok": False, "msg": "找不到可写的 mod 目录", "items": []}
    try:
        desc = _mod_descriptor(top)
    except Exception:
        desc = {}
    subs = [x.replace("\\", "/").strip("/") for x in (desc.get("replace") or [])]
    items = []
    for sub in subs:
        if not sub:
            continue
        if not os.path.isdir(os.path.join(top, sub.replace("/", os.sep))):
            items.append({"sub": sub, "ok": False,
                          "msg": "已声明 replace_path 但目录不存在（会丢掉上级数据）",
                          "missing_count": -1})
            continue
        items.append(verify_adopt(top, sub))
    bad = [x for x in items if not x.get("ok")]
    return {"ok": not bad, "items": items,
            "msg": "接管 %d 个目录，%d 个有问题" % (len(items), len(bad))}


# ================= 开局部队（history/units）=================













_BAT_CACHE = {"root": "", "mtime": 0, "items": []}


def load_battalions(root=None, force=False):
    """解析 common/units 里的 sub_units（营级兵种），供编制格的下拉用。

    每个兵种带 group（infantry / mobile / armor …），界面按组分类。
    """
    root = _map_pick(root)
    base, files = "", []
    try:
        files, _r = _layer_files("common/units", mod_layers(root))
        mt = max([os.path.getmtime(p) for p in files] or [0])
        key = os.path.abspath(root or "")
        if (not force and _BAT_CACHE["root"] == key
                and _BAT_CACHE["mtime"] == mt and mt):
            return _BAT_CACHE
    except Exception:
        files = []
    out = []
    seen = {}
    for p in (files or []):
        fn = os.path.basename(p)
        if fn.endswith("equipment") or "equipment" in fn:
            continue
        try:
            raw = io.open(p, encoding="utf-8-sig", errors="replace").read()
        except Exception:
            continue
        text = _strip_keep_len(raw)
        for a, b, body in find_blocks(text, "sub_units"):
            for k, v, has in top_items(body):
                if not has:
                    continue
                grp = _first(v, r'(?m)^\s*group\s*=\s*([a-z_]+)')
                tp = _first(v, r'(?m)^\s*type\s*=\s*\{([^}]*)\}')
                spr = _first(v, r'(?m)^\s*sprite\s*=\s*"([^"]*)"')
                icon = _first(v, r'(?m)^\s*map_icon_category\s*=\s*([a-z_]+)')
                seen[k] = {"id": k, "group": grp or "other",
                           "type": " ".join((tp or "").split()),
                           "sprite": spr, "icon": icon, "file": fn}
    out = sorted(seen.values(), key=lambda x: (x["group"], x["id"]))
    groups = {}
    for x in out:
        groups.setdefault(x["group"], []).append(x)
    res = {"root": os.path.abspath(root or ""), "mtime": 0,
           "items": out, "groups": groups, "total": len(out)}
    try:
        res["mtime"] = max([os.path.getmtime(p) for p in files] or [0])
    except Exception:
        pass
    _BAT_CACHE.update(res)
    return _BAT_CACHE


def battalions_payload(root=None):
    b = load_battalions(root)
    return {"ok": True, "total": b["total"],
            "groups": [{"group": k, "items": v} for k, v in sorted(b["groups"].items())],
            "msg": "共 %d 个兵种，%d 组" % (b["total"], len(b["groups"]))}


# ---------- 诊断系统 ----------
# 每条诊断的形状统一：改前端、写检查项、做修复按钮都吃这一套。
#   code      稳定的错误码，前端按它分组/给图标，不随文案变
#   severity  error / warning / info
#   file      mod 内相对路径
#   line      1 起的行号，0 表示不知道
#   excerpt   出错那段原文，方便直接看出问题
#   msg       给人看的一句话
#   repair    怎么改，能自动修的填路由名






























# 每个数据目录被 replace 后，其他目录里这些关键词就指向「已经被丢掉的内容」。
# 只匹配「明确引用」的关键词，不做通用标识符匹配，避免满屏误报。






# ---------------- replace 断链的修复动作 ----------------
#
# 诊断只能把「replace 掉了 A，别处还在引用 A」列出来；真省时间的是在面板上直接点掉。
# 对一条 replace.dangling_refs 有三个动作：
#
#   撤销 replace   从 descriptor.mod 删掉那条 replace_path（推荐，最省事）
#   接管该目录     把引用方整个拷进本 mod 并 replace，之后改自己的副本
#   忽略           确认这些引用不会被执行到，不再提示
#
# 为什么「接管」也要做：换地图时原版目录里按省号/州号写的引用全部失效，
# 必须整体替换，这时「撤销 replace」不成立，只能连引用方一起接管。

# 这几类目录整体替换后游戏直接起不来（实测，见 DEV_LESSONS 里 replace_path 那条）：
# 只允许「撤销 replace」，不允许接管。


def country_tags_payload(root=None):
    info = load_country_tags(root)
    if not info.get("ok"):
        return info
    return {"ok": True, "items": info["items"], "count": info["count"],
            "dynamic": info["dynamic"],
            "cultures": ["western_european_gfx", "commonwealth_gfx", "eastern_european_gfx",
                         "middle_eastern_gfx", "asian_gfx", "south_american_gfx",
                         "african_gfx", "generic_gfx"],
            "msg": info["msg"]}


def load_country_offsite(root=None, tag=""):
    """解析某国的 add_offsite_building（离岸建筑，不占州建筑位）。

    格式（多个独立块，不是一个大块）：
        add_offsite_building = {
            type = arms_factory
            level = 5
        }
    """
    root = _map_pick(root)
    tag = (tag or "").upper()
    if not tag:
        return {"ok": False, "msg": "没给 tag", "items": []}
    p, rel = _country_hist_file(root, tag)
    if not p:
        return {"ok": False, "msg": "找不到 %s 的国家历史文件" % tag, "items": []}
    try:
        raw = io.open(p, encoding="utf-8-sig", errors="replace").read()
    except Exception as e:
        return {"ok": False, "msg": "读取失败：%s" % e, "items": []}
    text = _strip_keep_len(raw)
    items = []
    for idx, (a, b, body) in enumerate(find_blocks(text, "add_offsite_building")):
        tp = _first(body, r'(?m)^\s*type\s*=\s*([a-z_]+)')
        lv = _first(body, r'(?m)^\s*level\s*=\s*(\d+)')
        items.append({"i": idx, "type": tp or "", "level": int(lv or 0),
                      "start": a, "end": b})
    total = sum(x["level"] for x in items)
    return {"ok": True, "tag": tag, "file": os.path.basename(p),
            "items": items, "count": len(items), "total_level": total,
            "msg": "%s：%d 项离岸建筑，合计 %d 级" % (tag, len(items), total)}


def country_offsite_add(root, tag, btype, level=1):
    """加一项离岸建筑。"""
    root = _map_pick(root)
    tag = (tag or "").upper()
    btype = (btype or "").strip()
    if not tag or not btype:
        return {"ok": False, "msg": "tag 和建筑类型都要给"}
    try:
        level = int(level)
    except Exception:
        return {"ok": False, "msg": "level 必须是整数"}
    if level <= 0:
        return {"ok": False, "msg": "level 要大于 0"}
    src, rel = _country_hist_file(root, tag)
    if not src:
        return {"ok": False, "msg": "找不到 %s 的国家历史文件" % tag}
    tgt, err = _country_hist_write_base(root)
    if not tgt:
        return {"ok": False, "msg": err}
    dst = os.path.join(tgt, rel)
    os.makedirs(os.path.dirname(dst) or tgt, exist_ok=True)
    if not os.path.exists(dst):
        try:
            import shutil as _sh
            _sh.copyfile(src, dst)
        except Exception as e:
            return {"ok": False, "msg": "复制来源失败：%s" % e}
    raw = io.open(dst, encoding="utf-8-sig", errors="replace").read()
    ins = "\nadd_offsite_building = {\n\ttype = %s\n\tlevel = %d\n}\n" % (btype, level)
    new_text = raw.rstrip() + "\n" + ins
    snapshot(dst)
    _atomic_write(dst, _bom_for(dst) + new_text.encode("utf-8"))
    return {"ok": True, "msg": "已加 %s ×%d" % (btype, level)}


def country_offsite_delete(root, tag, index):
    """删掉第 index 项离岸建筑。"""
    root = _map_pick(root)
    tag = (tag or "").upper()
    try:
        index = int(index)
    except Exception:
        return {"ok": False, "msg": "index 不合法"}
    info = load_country_offsite(root, tag)
    if not info.get("ok"):
        return {"ok": False, "msg": info.get("msg")}
    items = info["items"]
    if index < 0 or index >= len(items):
        return {"ok": False, "msg": "没有第 %d 项" % (index + 1)}
    it = items[index]
    src, rel = _country_hist_file(root, tag)
    tgt, err = _country_hist_write_base(root)
    if not tgt:
        return {"ok": False, "msg": err}
    dst = os.path.join(tgt, rel)
    os.makedirs(os.path.dirname(dst) or tgt, exist_ok=True)
    if not os.path.exists(dst):
        try:
            import shutil as _sh
            _sh.copyfile(src, dst)
        except Exception as e:
            return {"ok": False, "msg": "复制来源失败：%s" % e}
    raw = io.open(dst, encoding="utf-8-sig", errors="replace").read()
    text = _strip_keep_len(raw)
    blocks = list(find_blocks(text, "add_offsite_building"))
    if index >= len(blocks):
        return {"ok": False, "msg": "重新定位失败"}
    a, b, body = blocks[index]
    # 往前吃掉换行，往后吃掉空行
    st = a
    while st > 0 and raw[st - 1] in " \t":
        st -= 1
    if st > 0 and raw[st - 1] == "\n":
        st -= 1
    en = b
    while en < len(raw) and raw[en] in "\r\n":
        en += 1
    new_text = raw[:st] + "\n" + raw[en:]
    snapshot(dst)
    _atomic_write(dst, _bom_for(dst) + new_text.encode("utf-8"))
    return {"ok": True, "msg": "已删除 %s ×%d" % (it["type"], it["level"])}


def country_offsite_set(root, tag, index, btype=None, level=None):
    """改第 index 项离岸建筑的类型或数量。"""
    root = _map_pick(root)
    tag = (tag or "").upper()
    try:
        index = int(index)
    except Exception:
        return {"ok": False, "msg": "index 不合法"}
    info = load_country_offsite(root, tag)
    if not info.get("ok"):
        return {"ok": False, "msg": info.get("msg")}
    items = info["items"]
    if index < 0 or index >= len(items):
        return {"ok": False, "msg": "没有第 %d 项" % (index + 1)}
    it = items[index]
    nt = (btype or it["type"]).strip()
    try:
        nl = int(level) if level not in (None, "") else it["level"]
    except Exception:
        return {"ok": False, "msg": "level 必须是整数"}
    if nl <= 0:
        return {"ok": False, "msg": "level 要大于 0"}
    src, rel = _country_hist_file(root, tag)
    tgt, err = _country_hist_write_base(root)
    if not tgt:
        return {"ok": False, "msg": err}
    dst = os.path.join(tgt, rel)
    os.makedirs(os.path.dirname(dst) or tgt, exist_ok=True)
    if not os.path.exists(dst):
        try:
            import shutil as _sh
            _sh.copyfile(src, dst)
        except Exception as e:
            return {"ok": False, "msg": "复制来源失败：%s" % e}
    raw = io.open(dst, encoding="utf-8-sig", errors="replace").read()
    text = _strip_keep_len(raw)
    blocks = list(find_blocks(text, "add_offsite_building"))
    if index >= len(blocks):
        return {"ok": False, "msg": "重新定位失败"}
    a, b, body = blocks[index]
    seg = raw[a:b]
    seg2 = re.sub(r'(?m)^([ \t]*)type\s*=\s*[a-z_]+', lambda m: (m.group(1) or "") + "type = " + nt, seg)
    seg2 = re.sub(r'(?m)^([ \t]*)level\s*=\s*\d+', lambda m: (m.group(1) or "") + "level = " + str(nl), seg2)
    if seg2 == seg and nt == it["type"] and nl == it["level"]:
        return {"ok": True, "msg": "没有改动"}
    new_text = raw[:a] + seg2 + raw[b:]
    snapshot(dst)
    _atomic_write(dst, _bom_for(dst) + new_text.encode("utf-8"))
    return {"ok": True, "msg": "已改为 %s ×%d" % (nt, nl)}


def country_starter_payload(root=None, tag=""):
    """给界面用：离岸建筑清单 + 可选建筑类型（来自州建筑常量）。"""
    info = load_country_offsite(root, tag)
    if not info.get("ok"):
        return info
    return {"ok": True, "tag": tag, "file": info["file"],
            "items": info["items"], "count": info["count"],
            "total_level": info["total_level"],
            "types": list(STATE_BUILDINGS) + ["ammunition_plant", "ammunition_silo"],
            "msg": info["msg"]}












def load_navy(root=None):
    """解析 history/units 里的舰队编制。

    结构（三层）：
        units = {
            fleet = {
                name = "第一舰队"
                naval_base = 12736
                task_force = {
                    name = "第一炮击分队"
                    location = 12736
                    ship = { name = "..." definition = carrier ... }
                }
            }
        }
    """
    root = _map_pick(root)
    _base, files = _units_files(root)
    fleets = []
    for p in (files or []):
        fn = os.path.basename(p)
        rel = os.path.join("history", "units", fn)
        try:
            raw = io.open(p, encoding="utf-8-sig", errors="replace").read()
        except Exception:
            continue
        text = _strip_keep_len(raw)
        src = ""
        try:
            for b in (mod_layers(root) or []):
                if os.path.abspath(p).startswith(os.path.abspath(b) + os.sep):
                    src = os.path.basename(b.rstrip("\\/")) or b
                    break
        except Exception:
            pass
        for um in re.finditer(r'(?m)^[ \t]*units[ \t]*=\s*\{', text):
            ub = text.find("{", um.end() - 1)
            ue = brace_match(text, ub)
            if ue <= ub:
                continue
            ubody = text[ub + 1:ue - 1]
            # find_blocks 返回 (start, end, body)：start 是 { 的位置，end 是 } 的位置
            for fb, fend, fbody in find_blocks(ubody, "fleet"):
                _line = ubody.rfind("\n", 0, fb) + 1
                fo = ub + 1 + _line
                fo_end = ub + 1 + fend + 1
                fname = _first(fbody, r'(?m)^\s*name\s*=\s*"([^"]*)"')
                nbase = _first(fbody, r'(?m)^\s*naval_base\s*=\s*(\d+)')
                tfs = []
                for tstart, tend, tbody in find_blocks(fbody, "task_force"):
                    tname = _first(tbody, r'(?m)^\s*name\s*=\s*"([^"]*)"')
                    tloc = _first(tbody, r'(?m)^\s*location\s*=\s*(\d+)')
                    ships = []
                    # ship 是单行：ship = { name = "X" definition = Y ... }
                    for sm in re.finditer(r'(?m)^[ \t]*ship\s*=\s*\{[^\n]*', tbody):
                        line = sm.group(0)
                        nm = re.search(r'name\s*=\s*"([^"]*)"', line)
                        df = re.search(r'definition\s*=\s*([A-Za-z0-9_]+)', line)
                        ships.append({"name": nm.group(1) if nm else "",
                                      "definition": df.group(1) if df else ""})
                    _tline = fbody.rfind("\n", 0, tstart) + 1
                    tfs.append({"name": tname, "location": int(tloc or 0),
                                "ships": ships, "ship_count": len(ships),
                                "start": ub + 1 + fb + 1 + _tline,
                                "end": ub + 1 + fb + 1 + tend + 1})
                fleets.append({"name": fname, "naval_base": int(nbase or 0),
                               "file": rel, "source": src,
                               "task_forces": tfs, "tf_count": len(tfs),
                               "ship_total": sum(x["ship_count"] for x in tfs),
                               "start": fo, "end": fo_end})
    total_ships = sum(x["ship_total"] for x in fleets)
    return {"ok": True, "fleets": fleets, "fleet_count": len(fleets),
            "ship_total": total_ships,
            "msg": "%d 支舰队，%d 艘船" % (len(fleets), total_ships)}



































def load_bookmarks(root=None):
    """解析 common/bookmarks 里的所有剧本。

    结构：
        bookmarks = {
            bookmark = {
                name = "1973_START_NAME"
                desc = "1973_START_DESC"
                date = 2073.1.1.12
                picture = "GFX_select_date_1939"
                default_country = "GER"
                "FRA" = { history = ... ideology = ... }
            }
        }
    """
    root = _map_pick(root)
    files, _rep = _layer_files("common/bookmarks", mod_layers(root))
    items = []
    for p in (files or []):
        try:
            raw = io.open(p, encoding="utf-8-sig", errors="replace").read()
        except Exception:
            continue
        text = _strip_keep_len(raw)
        rel = os.path.join("common", "bookmarks", os.path.basename(p))
        src = ""
        try:
            for b in (mod_layers(root) or []):
                if os.path.abspath(p).startswith(os.path.abspath(b) + os.sep):
                    src = os.path.basename(b.rstrip("\\/")) or b
                    break
        except Exception:
            pass
        for outer_a, outer_b, outer_body in find_blocks(text, "bookmarks"):
            for ba, bb, body in find_blocks(outer_body, "bookmark"):
                nm = _first(body, r'(?m)^\s*name\s*=\s*"([^"]*)"')
                ds = _first(body, r'(?m)^\s*desc\s*=\s*"([^"]*)"')
                dt = _first(body, r'(?m)^\s*date\s*=\s*([\d.]+)')
                pic = _first(body, r'(?m)^\s*picture\s*=\s*"([^"]*)"')
                dc = _first(body, r'(?m)^\s*default_country\s*=\s*"([A-Z0-9]+)"')
                countries = re.findall(r'(?m)^[ \t]*"([A-Z0-9_]{2,8})"[ \t]*=\s*\{', body)
                items.append({"i": len(items), "name": nm, "desc": ds, "date": dt,
                              "picture": pic, "default_country": dc,
                              "countries": countries, "country_count": len(countries),
                              "file": rel, "source": src,
                              "start": outer_a + 1 + ba,
                              "end": outer_a + 1 + bb})
    return {"ok": True, "items": items, "count": len(items),
            "msg": "共 %d 个剧本" % len(items)}














def bookmark_set(root, index, fields):
    """改某个剧本的 date / name / desc / picture / default_country。"""
    root = _map_pick(root)
    try:
        index = int(index)
    except Exception:
        return {"ok": False, "msg": "index 不合法"}
    info = load_bookmarks(root)
    items = info["items"]
    if index < 0 or index >= len(items):
        return {"ok": False, "msg": "没有第 %d 个剧本" % (index + 1)}
    it = items[index]
    tgt, err = _bookmark_write_base(root)
    if not tgt:
        return {"ok": False, "msg": err}
    p = os.path.join(tgt, it["file"])
    os.makedirs(os.path.dirname(p) or tgt, exist_ok=True)
    # 父 mod 里的文件要先复制过来
    src = None
    for q in (_layer_files("common/bookmarks", mod_layers(root))[0] or []):
        if os.path.basename(q) == os.path.basename(it["file"]):
            src = q
            break
    if src and not os.path.exists(p):
        try:
            import shutil as _sh
            _sh.copyfile(src, p)
        except Exception as e:
            return {"ok": False, "msg": "复制来源失败：%s" % e}
    raw = io.open(p, encoding="utf-8-sig", errors="replace").read()
    text = _strip_keep_len(raw)
    # 全局索引 → 本文件内序号
    local = 0
    for j, x in enumerate(items):
        if j == index:
            break
        if os.path.basename(x["file"]) == os.path.basename(it["file"]):
            local += 1
    cnt = -1
    a = b = -1
    for oa, ob, oBody in find_blocks(text, "bookmarks"):
        for ba, bb, body in find_blocks(oBody, "bookmark"):
            cnt += 1
            if cnt == local:
                a = oa + 1 + ba
                b = oa + 1 + bb
                break
        if a >= 0:
            break
    if a < 0:
        return {"ok": False, "msg": "重新定位失败（本文件内第 %d 个）" % (local + 1)}
    seg = raw[a:b]
    new_seg = seg
    changed = []
    for key, val in (("date", fields.get("date")),
                     ("name", fields.get("name")),
                     ("desc", fields.get("desc")),
                     ("picture", fields.get("picture")),
                     ("default_country", fields.get("default_country"))):
        if not val:
            continue
        pat = re.compile(r'(?m)^([ \t]*)' + key + r'\s*=\s*[^\s#\r\n]+')
        if pat.search(new_seg):
            new_seg = pat.sub(lambda m: (m.group(1) or "") + '%s = %s' % (
                key, ('"%s"' % val) if key in ("name", "desc", "picture", "default_country") else val),
                new_seg, count=1)
            changed.append(key)
    if new_seg == seg:
        return {"ok": True, "msg": "没有改动"}
    new_text = raw[:a] + new_seg + raw[b:]
    snapshot(p)
    _atomic_write(p, _bom_for(p) + new_text.encode("utf-8"))
    return {"ok": True, "msg": "剧本「%s」已更新：%s" % (it["name"], ", ".join(changed))}


def bookmark_delete(root, index):
    """删掉第 index 个剧本。"""
    root = _map_pick(root)
    try:
        index = int(index)
    except Exception:
        return {"ok": False, "msg": "index 不合法"}
    info = load_bookmarks(root)
    items = info["items"]
    if index < 0 or index >= len(items):
        return {"ok": False, "msg": "没有第 %d 个剧本" % (index + 1)}
    it = items[index]
    tgt, err = _bookmark_write_base(root)
    if not tgt:
        return {"ok": False, "msg": err}
    p = os.path.join(tgt, it["file"])
    src = None
    for q in (_layer_files("common/bookmarks", mod_layers(root))[0] or []):
        if os.path.basename(q) == os.path.basename(it["file"]):
            src = q
            break
    if not os.path.exists(p):
        if not src:
            return {"ok": False, "msg": "找不到来源文件"}
        os.makedirs(os.path.dirname(p) or tgt, exist_ok=True)
        try:
            import shutil as _sh
            _sh.copyfile(src, p)
        except Exception as e:
            return {"ok": False, "msg": "复制来源失败：%s" % e}
    raw = io.open(p, encoding="utf-8-sig", errors="replace").read()
    text = _strip_keep_len(raw)
    local = 0
    for j, x in enumerate(items):
        if j == index:
            break
        if os.path.basename(x["file"]) == os.path.basename(it["file"]):
            local += 1
    cnt = -1
    a = b = -1
    for oa, ob, oBody in find_blocks(text, "bookmarks"):
        for ba, bb, body in find_blocks(oBody, "bookmark"):
            cnt += 1
            if cnt == local:
                a = oa + 1 + ba
                b = oa + 1 + bb
                break
        if a >= 0:
            break
    if a < 0:
        return {"ok": False, "msg": "重新定位失败（本文件内第 %d 个）" % (local + 1)}
    st = a
    while st > 0 and raw[st - 1] in " \t":
        st -= 1
    if st > 0 and raw[st - 1] == "\n":
        st -= 1
    en = b
    while en < len(raw) and raw[en] in "\r\n":
        en += 1
    snapshot(p)
    _atomic_write(p, b"\xef\xbb\xbf" + (raw[:st] + "\n" + raw[en:]).encode("utf-8"))
    return {"ok": True, "msg": "已删除剧本「%s」" % it["name"]}


def bookmarks_payload(root=None):
    info = load_bookmarks(root)
    if not info.get("ok"):
        return info
    return {"ok": True, "items": info["items"], "count": info["count"],
            "msg": info["msg"]}








def completed_focuses_payload(root=None, tag=""):
    info = load_completed_focuses(root, tag)
    if not info.get("ok"):
        return info
    items = info["items"]
    out = []
    for x in items:
        name = ""
        tree = ""
        for tid, t in (TREES or {}).items():
            for f in (t.get("focuses") or []):
                if f.get("id") == x["focus"]:
                    name = f.get("name") or ""
                    tree = tid
                    break
            if name or tree:
                break
        out.append({"focus": x["focus"], "form": x["form"],
                    "name": name, "tree": tree, "known": bool(name or tree)})
    return {"ok": True, "tag": tag, "file": info["file"],
            "items": out, "count": info["count"],
            "tree_completed": info["tree_completed"],
            "msg": info["msg"]}


IDEOLOGIES = ("democratic", "fascism", "communism", "neutrality")


def load_politics(root=None, tag=""):
    """解析某国的开局政治与外交状态。

    set_politics = { ruling_party / last_election / election_frequency / elections_allowed }
    set_popularities = { democratic = 75  fascism = 10 … }
    declare_war_on = { target = X  type = Y }
    """
    root = _map_pick(root)
    tag = (tag or "").upper()
    if not tag:
        return {"ok": False, "msg": "没给 tag"}
    p, rel = _country_hist_file(root, tag)
    if not p:
        return {"ok": False, "msg": "找不到 %s 的国家历史文件" % tag}
    try:
        raw = io.open(p, encoding="utf-8-sig", errors="replace").read()
    except Exception as e:
        return {"ok": False, "msg": "读取失败：%s" % e}
    text = _strip_keep_len(raw)

    pol = {"ruling_party": "", "last_election": "", "election_frequency": "",
           "elections_allowed": "", "origin": ""}
    pol_text = text.find("set_politics")
    if pol_text >= 0:
        pb = text.find("{", pol_text)
        pe = brace_match(text, pb)
        if pe > pb:
            body = text[pb + 1:pe - 1]
            pol["ruling_party"] = _first(body, r'(?m)^\s*ruling_party\s*=\s*([a-z_]+)')
            pol["last_election"] = _first(body, r'(?m)^\s*last_election\s*=\s*"([^"]*)"')
            pol["election_frequency"] = _first(body, r'(?m)^\s*election_frequency\s*=\s*(\d+)')
            pol["elections_allowed"] = _first(body, r'(?m)^\s*elections_allowed\s*=\s*(yes|no)')
            pol["origin"] = "文件里已有"

    pops = {}
    for a, b, body in find_blocks(text, "set_popularities"):
        for ide in IDEOLOGIES:
            v = _first(body, r'(?m)^\s*' + ide + r'\s*=\s*(\d+)')
            if v:
                pops[ide] = int(v)
    wars = []
    for a, b, body in find_blocks(text, "declare_war_on"):
        wars.append({"target": _first(body, r'(?m)^\s*target\s*=\s*([A-Z0-9]+)'),
                     "type": _first(body, r'(?m)^\s*type\s*=\s*([a-z_]+)')})
    return {"ok": True, "tag": tag, "file": os.path.basename(p),
            "politics": pol, "popularities": pops, "wars": wars,
            "msg": "%s：%s，支持率 %d 项，战争 %d 场" % (
                tag, pol["ruling_party"] or "(未定义)", len(pops), len(wars))}




def politics_save(root, tag, fields):
    """改开局政治：执政党 / 选举 / 频率 / 是否允许选举。

    fields 里给什么改什么，没给的保留原值。
    """
    root = _map_pick(root)
    tag = (tag or "").upper()
    cur = load_politics(root, tag)
    if not cur.get("ok"):
        return {"ok": False, "msg": cur.get("msg")}
    pol = cur["politics"]
    want = {
        "ruling_party": (fields.get("ruling_party") or pol["ruling_party"]),
        "last_election": (fields.get("last_election") or pol["last_election"]),
        "election_frequency": (fields.get("election_frequency") or pol["election_frequency"]),
        "elections_allowed": (fields.get("elections_allowed") or pol["elections_allowed"]),
    }
    if want["ruling_party"] and want["ruling_party"] not in IDEOLOGIES:
        return {"ok": False, "msg": "执政党只能是 %s" % " / ".join(IDEOLOGIES)}
    if want["elections_allowed"] and want["elections_allowed"] not in ("yes", "no"):
        return {"ok": False, "msg": "elections_allowed 只能是 yes / no"}

    dst, rel, err = _politics_write(root, tag)
    if not dst:
        return {"ok": False, "msg": err}
    raw = io.open(dst, encoding="utf-8-sig", errors="replace").read()
    text = _strip_keep_len(raw)
    changed = []

    def set_in(block_key, body, lo, hi):
        out = body
        for k, v in (("ruling_party", want["ruling_party"]),
                     ("last_election", '"%s"' % want["last_election"] if want["last_election"] else ""),
                     ("election_frequency", want["election_frequency"]),
                     ("elections_allowed", want["elections_allowed"])):
            if not v:
                continue
            pat = re.compile(r'(?m)^([ \t]*)' + k + r'\s*=\s*[^\s#\r\n]+')
            if pat.search(out):
                out2 = pat.sub(lambda m: (m.group(1) or "") + "%s = %s" % (k, v), out, count=1)
                if out2 != out:
                    changed.append(k)
                    out = out2
        return out

    pk = text.find("set_politics")
    if pk >= 0:
        pb = text.find("{", pk)
        pe = brace_match(text, pb)
        if pe > pb:
            body = raw[pb + 1:pe - 1]
            nb = set_in("set_politics", body, pb + 1, pe - 1)
            if nb == body:
                return {"ok": True, "msg": "没有改动"}
            new_text = raw[:pb + 1] + nb + raw[pe - 1:]
            snapshot(dst)
            _atomic_write(dst, _bom_for(dst) + new_text.encode("utf-8"))
            return {"ok": True, "msg": "%s 已更新：%s" % (tag, ", ".join(changed) or "无变化")}
    # 没有 set_politics：在 history 里新建
    block = ('\n\tset_politics = {\n'
             '\t\truling_party = %s\n'
             '\t\tlast_election = "%s"\n'
             '\t\telection_frequency = %s\n'
             '\t\telections_allowed = %s\n'
             '\t}\n') % (want["ruling_party"] or "neutrality",
                          want["last_election"] or "1936.1.1",
                          want["election_frequency"] or "48",
                          want["elections_allowed"] or "no")
    hi = text.find("history = {")
    if hi >= 0:
        br = text.find("{", hi)
        pos = br + 1
        new_text = raw[:pos] + block + raw[pos:]
    else:
        new_text = raw.rstrip() + "\nhistory = {" + block + "}\n"
    snapshot(dst)
    _atomic_write(dst, _bom_for(dst) + new_text.encode("utf-8"))
    return {"ok": True, "msg": "%s 新建 set_politics 块" % tag}


def popularities_save(root, tag, pops):
    """改四党支持率（整组替换，和为 100 时提示）。"""
    root = _map_pick(root)
    tag = (tag or "").upper()
    if not isinstance(pops, dict) or not pops:
        return {"ok": False, "msg": "要传 {democratic: 60, ...}"}
    clean = {}
    for k, v in pops.items():
        if k not in IDEOLOGIES:
            return {"ok": False, "msg": "未知意识形态：%s" % k}
        try:
            iv = int(v)
        except Exception:
            return {"ok": False, "msg": "%s 的支持率必须是整数" % k}
        if iv < 0 or iv > 100:
            return {"ok": False, "msg": "%s 的支持率要在 0-100" % k}
        clean[k] = iv
    total = sum(clean.values())
    dst, rel, err = _politics_write(root, tag)
    if not dst:
        return {"ok": False, "msg": err}
    raw = io.open(dst, encoding="utf-8-sig", errors="replace").read()
    text = _strip_keep_len(raw)
    blocks = list(find_blocks(text, "set_popularities"))
    body = "".join("\n\t\t%s = %d" % (k, v) for k, v in clean.items())
    if blocks:
        a, b, _old = blocks[0]
        # a 是 { 的位置，b 是 } 的位置：替换整段块体 raw[a+1:b-1]
        new_text = raw[:a + 1] + body + "\n\t" + raw[b - 1:]
    else:
        block = "\n\tset_popularities = {" + body + "\n\t}\n"
        hi = text.find("history = {")
        if hi >= 0:
            br = text.find("{", hi)
            pos = br + 1
            new_text = raw[:pos] + block + raw[pos:]
        else:
            new_text = raw.rstrip() + "\nhistory = {" + block + "}\n"
    snapshot(dst)
    _atomic_write(dst, _bom_for(dst) + new_text.encode("utf-8"))
    tip = "（合计 %d）" % total
    return {"ok": True, "msg": "%s 支持率已更新%s" % (tag, tip)}


def war_add(root, tag, target, wargoal_type="annex"):
    """给某国加一条 declare_war_on。"""
    root = _map_pick(root)
    tag = (tag or "").upper()
    target = (target or "").upper()
    if not tag or not target:
        return {"ok": False, "msg": "tag 和 target 都要给"}
    if tag == target:
        return {"ok": False, "msg": "不能对自己宣战"}
    cur = load_politics(root, tag)
    if not cur.get("ok"):
        return {"ok": False, "msg": cur.get("msg")}
    if any(w["target"] == target for w in cur["wars"]):
        return {"ok": True, "msg": "已经有对 %s 的战争了" % target}
    dst, rel, err = _politics_write(root, tag)
    if not dst:
        return {"ok": False, "msg": err}
    raw = io.open(dst, encoding="utf-8-sig", errors="replace").read()
    block = ('\n\tdeclare_war_on = {\n'
             '\t\ttarget = %s\n'
             '\t\ttype = %s\n'
             '\t}\n') % (target, wargoal_type or "annex")
    text = _strip_keep_len(raw)
    hi = text.find("history = {")
    if hi >= 0:
        br = text.find("{", hi)
        pos = br + 1
        new_text = raw[:pos] + block + raw[pos:]
    else:
        new_text = raw.rstrip() + "\nhistory = {" + block + "}\n"
    snapshot(dst)
    _atomic_write(dst, _bom_for(dst) + new_text.encode("utf-8"))
    return {"ok": True, "msg": "%s 对 %s 宣战（%s）" % (tag, target, wargoal_type)}


def war_delete(root, tag, index):
    """删掉第 index 条宣战。"""
    root = _map_pick(root)
    tag = (tag or "").upper()
    try:
        index = int(index)
    except Exception:
        return {"ok": False, "msg": "index 不合法"}
    cur = load_politics(root, tag)
    if not cur.get("ok"):
        return {"ok": False, "msg": cur.get("msg")}
    if index < 0 or index >= len(cur["wars"]):
        return {"ok": False, "msg": "没有第 %d 条宣战" % (index + 1)}
    dst, rel, err = _politics_write(root, tag)
    if not dst:
        return {"ok": False, "msg": err}
    raw = io.open(dst, encoding="utf-8-sig", errors="replace").read()
    text = _strip_keep_len(raw)
    blocks = list(find_blocks(text, "declare_war_on"))
    if index >= len(blocks):
        return {"ok": False, "msg": "重新定位失败"}
    a, b, body = blocks[index]
    st = a
    while st > 0 and raw[st - 1] in " \t":
        st -= 1
    if st > 0 and raw[st - 1] == "\n":
        st -= 1
    en = b
    while en < len(raw) and raw[en] in "\r\n":
        en += 1
    tgt_tag = cur["wars"][index]["target"]
    snapshot(dst)
    _atomic_write(dst, b"\xef\xbb\xbf" + (raw[:st] + "\n" + raw[en:]).encode("utf-8"))
    return {"ok": True, "msg": "已删除对 %s 的宣战" % tgt_tag}


def politics_payload(root=None, tag=""):
    info = load_politics(root, tag)
    if not info.get("ok"):
        return info
    return {"ok": True, "tag": tag, "file": info["file"],
            "politics": info["politics"], "popularities": info["popularities"],
            "wars": info["wars"], "ideologies": list(IDEOLOGIES),
            "msg": info["msg"]}


def load_air_wings(root=None):
    """解析 history/units 里的 air_wings（开局空军联队）。

    结构：
        air_wings = {
            524 = {                              ← 省号（基地）
                name = "中华太空舰队"
                transport_plane_equipment_1 = {
                    owner = "CHI"
                    amount = 5
                }
            }
        }
    """
    root = _map_pick(root)
    _base, files = _units_files(root)
    wings = []
    for p in (files or []):
        try:
            raw = io.open(p, encoding="utf-8-sig", errors="replace").read()
        except Exception:
            continue
        text = _strip_keep_len(raw)
        rel = os.path.join("history", "units", os.path.basename(p))
        src = ""
        try:
            for b in (mod_layers(root) or []):
                if os.path.abspath(p).startswith(os.path.abspath(b) + os.sep):
                    src = os.path.basename(b.rstrip("\\/")) or b
                    break
        except Exception:
            pass
        for am in re.finditer(r'(?m)^[ \t]*air_wings[ \t]*=\s*\{', text):
            ab = text.find("{", am.end() - 1)
            ae = brace_match(text, ab)
            if ae <= ab:
                continue
            abody = text[ab + 1:ae - 1]
            # 每个顶层的 省号 = { ... }
            for wm in re.finditer(r'(?m)^[ \t]*(\d+)[ \t]*=\s*\{', abody):
                pid = int(wm.group(1))
                wb = abody.find("{", wm.end() - 1)
                we = brace_match(abody, wb)
                if we <= wb:
                    continue
                wbody = abody[wb + 1:we - 1]
                nm = _first(wbody, r'(?m)^\s*name\s*=\s*"([^"]*)"')
                eqs = []
                for em in re.finditer(r'(?m)^[ \t]*([A-Za-z0-9_]+)[ \t]*=\s*\{', wbody):
                    etype = em.group(1)
                    if etype in ("name",):
                        continue
                    eb = wbody.find("{", em.end() - 1)
                    ee = brace_match(wbody, eb)
                    if ee <= eb:
                        continue
                    ebody = wbody[eb + 1:ee - 1]
                    ow = _first(ebody, r'(?m)^\s*owner\s*=\s*"?([A-Z0-9]+)"?')
                    amt = _first(ebody, r'(?m)^\s*amount\s*=\s*(\d+)')
                    eqs.append({"type": etype, "owner": ow,
                                "amount": int(amt or 0)})
                # start 取「省号 = {」那一行的行首，否则删完会剩半截 "999 ="
                _wline = abody.rfind("\n", 0, wm.start()) + 1
                wings.append({"province": pid, "name": nm,
                              "equipment": eqs,
                              "eq_count": sum(x["amount"] for x in eqs),
                              "file": rel, "source": src,
                              "start": ab + 1 + _wline,
                              "end": ab + 1 + we})
    total = sum(x["eq_count"] for x in wings)
    return {"ok": True, "wings": wings, "count": len(wings),
            "eq_total": total,
            "msg": "%d 支航空联队，%d 架飞机" % (len(wings), total)}


def _air_locate(root, idx):
    """按序号重新定位 air_wings 里第 idx 个联队。"""
    info = load_air_wings(root)
    wings = info["wings"]
    if idx < 0 or idx >= len(wings):
        return None, None, -1, -1, "没有第 %d 支联队" % (idx + 1)
    w = wings[idx]
    src = None
    for p in (_units_files(root)[1] or []):
        if os.path.basename(p) == os.path.basename(w["file"]):
            src = p
            break
    if not src:
        return None, None, -1, -1, "找不到来源文件"
    return src, w["file"], w["start"], w["end"], ""


def air_wing_delete(root, idx):
    """删掉第 idx 支航空联队。"""
    root = _map_pick(root)
    try:
        idx = int(idx)
    except Exception:
        return {"ok": False, "msg": "index 不合法"}
    src, rel, st, en, err = _air_locate(root, idx)
    if not src:
        return {"ok": False, "msg": err}
    tgt, werr = _units_write_base(root)
    if not tgt:
        return {"ok": False, "msg": werr}
    dst = os.path.join(tgt, rel)
    os.makedirs(os.path.dirname(dst) or tgt, exist_ok=True)
    if not os.path.exists(dst):
        try:
            import shutil as _sh
            _sh.copyfile(src, dst)
        except Exception as e:
            return {"ok": False, "msg": "复制来源失败：%s" % e}
    raw = io.open(dst, encoding="utf-8-sig", errors="replace").read()
    n = len(raw)
    if not (0 <= st < n and 0 <= en <= n and st < en):
        return {"ok": False, "msg": "偏移不合法"}
    s2 = st
    while s2 > 0 and raw[s2 - 1] in " \t":
        s2 -= 1
    if s2 > 0 and raw[s2 - 1] == "\n":
        s2 -= 1
    e2 = en
    while e2 < n and raw[e2] in "\r\n":
        e2 += 1
    info = load_air_wings(root)
    nm = info["wings"][idx]["name"] if idx < len(info["wings"]) else ""
    snapshot(dst)
    _atomic_write(dst, b"\xef\xbb\xbf" + (raw[:s2] + "\n" + raw[e2:]).encode("utf-8"))
    return {"ok": True, "msg": "已删除联队「%s」" % nm}


def air_wing_add(root, province, name, eq_type, owner, amount=10, tag=None):
    """给某个国家的 history/units 文件加一支航空联队。

    加进哪个文件：优先按 owner 找 TAG_*.txt，找不到就建 zz_air_wings.txt。
    """
    root = _map_pick(root)
    try:
        province = int(province)
    except Exception:
        return {"ok": False, "msg": "省号不合法"}
    if province <= 0:
        return {"ok": False, "msg": "省号不合法"}
    owner = (owner or "").upper()
    if not owner:
        return {"ok": False, "msg": "owner tag 不能为空"}
    try:
        amount = int(amount)
    except Exception:
        return {"ok": False, "msg": "数量必须是整数"}
    if amount <= 0:
        return {"ok": False, "msg": "数量要大于 0"}
    eq_type = eq_type or "fighter_equipment_1"

    tgt, err = _units_write_base(root)
    if not tgt:
        return {"ok": False, "msg": err}
    d = os.path.join(tgt, "history", "units")
    os.makedirs(d, exist_ok=True)

    # 找现有的同 owner 文件里的 air_wings；没有就用 zz_air_wings.txt
    _oobs = _oob_files(root, owner, "air")
    if _oobs:
        dst = os.path.join(d, _oobs[0] + ".txt")
        # 同名文件不能直接覆盖，先复制原版
        if not os.path.exists(dst):
            for b in reversed(mod_layers(tgt) or []):
                if not b:
                    continue
                cand = os.path.join(b, "history", "units", _oobs[0] + ".txt")
                if os.path.isfile(cand):
                    try:
                        import shutil as _sh6
                        _sh6.copyfile(cand, dst)
                    except Exception:
                        pass
                    break
    else:
        dst = os.path.join(d, "%s_1936_zz_air.txt" % owner)
    block = ('\t%d = {\n'
             '\t\tname = "%s"\n'
             '\t\t%s = {\n'
             '\t\t\towner = "%s"\n'
             '\t\t\tamount = %d\n'
             '\t\t}\n'
             '\t}\n') % (province, (name or "新联队").replace('"', ""),
                          eq_type, owner, amount)

    if os.path.exists(dst):
        raw = io.open(dst, encoding="utf-8-sig", errors="replace").read()
    else:
        raw = "air_wings = {\n}\n"
    text = _strip_keep_len(raw)
    am = re.search(r'(?m)^[ \t]*air_wings[ \t]*=\s*\{', text)
    if am:
        ab = text.find("{", am.end() - 1)
        ae = brace_match(text, ab)
        if ae > ab:
            # 插在 air_wings 的 } 所在行的行首前
            p = ae
            while p > 0 and raw[p - 1] in " \t":
                p -= 1
            if p > 0 and raw[p - 1] == "}":
                p -= 1
            ls = raw.rfind("\n", 0, p) + 1
            new_text = raw[:ls] + block + raw[ls:]
        else:
            new_text = raw.rstrip() + "\n" + block
    else:
        new_text = raw.rstrip() + "\nair_wings = {\n" + block + "}\n"

    if os.path.exists(dst):
        snapshot(dst)
    _atomic_write(dst, _bom_for(dst) + new_text.encode("utf-8"))
    return {"ok": True, "msg": "已在省 %d 加联队「%s」（%s ×%d，owner %s）" % (
        province, name or "新联队", eq_type, amount, owner)}


def air_wings_payload(root=None):
    info = load_air_wings(root)
    if not info.get("ok"):
        return info
    return {"ok": True, "wings": info["wings"], "count": info["count"],
            "eq_total": info["eq_total"], "msg": info["msg"]}


def navy_delete_fleet(root, fi):
    """删掉第 fi 支舰队（整块）。"""
    root = _map_pick(root)
    try:
        fi = int(fi)
    except Exception:
        return {"ok": False, "msg": "index 不合法"}
    info = load_navy(root)
    fleets = info["fleets"]
    if fi < 0 or fi >= len(fleets):
        return {"ok": False, "msg": "没有第 %d 支舰队" % (fi + 1)}
    f = fleets[fi]
    return _navy_cut(root, f["file"], f["start"], f["end"],
                     "舰队「%s」" % f["name"])


def navy_delete_taskforce(root, fi, ti):
    """删掉某支舰队里的第 ti 个特遣队。"""
    root = _map_pick(root)
    try:
        fi, ti = int(fi), int(ti)
    except Exception:
        return {"ok": False, "msg": "index 不合法"}
    info = load_navy(root)
    fleets = info["fleets"]
    if fi < 0 or fi >= len(fleets):
        return {"ok": False, "msg": "没有第 %d 支舰队" % (fi + 1)}
    tfs = fleets[fi]["task_forces"]
    if ti < 0 or ti >= len(tfs):
        return {"ok": False, "msg": "没有第 %d 个特遣队" % (ti + 1)}
    t = tfs[ti]
    return _navy_cut(root, fleets[fi]["file"], t["start"], t["end"],
                     "特遣队「%s」" % t["name"])


def _insert_before_close(raw, pos, text_to_insert):
    """把内容插到 pos 所在块的 } 那一行前面。

    只跳过同一行内的缩进，绝不跨行 —— 跨行会退到内层块的 } 上。
    最后定位到 } 所在行的行首，保证 } 的缩进不被吃掉。
    """
    n = len(raw)
    if pos > n:
        pos = n
    p = pos
    while p > 0 and raw[p - 1] in " \t":
        p -= 1
    if p > 0 and raw[p - 1] == "}":
        p -= 1
    # 定位到这一行的行首，插在前面
    ls = raw.rfind("\n", 0, p) + 1
    return raw[:ls] + text_to_insert + raw[ls:]

def _navy_locate(root, fi=None, ti=None):
    """重新定位舰队/特遣队在文件里的偏移。

    返回 (目标路径, rel, start, end, raw) 或 (None, "", -1, -1, "")。
    start/end 直接来自 find_blocks（start 是 { 位置，end 是 } 位置）。
    """
    root = _map_pick(root)
    _base, files = _units_files(root)
    idx = -1
    for p in (files or []):
        try:
            raw = io.open(p, encoding="utf-8-sig", errors="replace").read()
        except Exception:
            continue
        text = _strip_keep_len(raw)
        rel = os.path.join("history", "units", os.path.basename(p))
        for um in re.finditer(r'(?m)^[ \t]*units[ \t]*=\s*\{', text):
            ub = text.find("{", um.end() - 1)
            ue = brace_match(text, ub)
            if ue <= ub:
                continue
            ubody = text[ub + 1:ue - 1]
            for fb, fend, fbody in find_blocks(ubody, "fleet"):
                idx += 1
                if fi is not None and idx != fi:
                    continue
                if ti is None:
                    return p, rel, ub + 1 + fb, ub + 1 + fend, raw
                tjdx = -1
                for tb, tend, tbody in find_blocks(fbody, "task_force"):
                    tjdx += 1
                    if tjdx == ti:
                        return p, rel, ub + 1 + fb + 1 + tb, ub + 1 + fb + 1 + tend, raw
                return None, "", -1, -1, ""
    return None, "", -1, -1, ""


def _ship_line(name, definition, exp=0.3):
    """生成一行 ship 定义（HOI4 允许整支船写在一行）。"""
    nm = (name or "新舰").replace('"', "")
    df = definition or "destroyer"
    try:
        ex = float(exp) if exp not in (None, "") else 0.3
    except Exception:
        ex = 0.3
    return '\t\t\tship = { name = "%s" definition = %s start_experience_factor = %s }\n' % (
        nm, df, ("%g" % ex))


def _navy_pick_tag(root, tag):
    """按国家 tag 过滤舰队，返回 (全局索引列表, 错误)。

    load_navy 是按文件名字母序把所有 mod 的舰队摊平的，
    fi=0 可能是阿根廷的舰队，不是你想要的那个国家。
    """
    tag = (tag or "").strip().upper()
    if not tag:
        return None, ""
    info = load_navy(root)
    fleets = info.get("fleets") or []
    idxs = []
    for i, f in enumerate(fleets):
        fn = os.path.basename((f.get("file") or "")).upper()
        # 文件形如 GER_1936.txt / ARG_1936_naval_legacy.txt
        if fn.startswith(tag + "_") or fn.startswith(tag + "."):
            idxs.append(i)
    if not idxs:
        return None, "没有 %s 的舰队（该国的 history/units 里没有 fleet 定义）" % tag
    return idxs, ""


def navy_add_ship(root, fi, ti, name=None, definition="destroyer", exp=0.3, tag=None):
    """往某个特遣队里加一艘船。

    tag 给了就按国家过滤：fi 变成「该国的第几支舰队」，
    避免默认加到按文件名字母序排在最前的那个国家（通常是 ARG）。
    """
    root = _map_pick(root)
    try:
        fi, ti = int(fi), int(ti)
    except Exception:
        return {"ok": False, "msg": "index 不合法"}
    if tag:
        idxs, err = _navy_pick_tag(root, tag)
        if not idxs:
            return {"ok": False, "msg": err}
        if fi < 0 or fi >= len(idxs):
            return {"ok": False, "msg": "%s 只有 %d 支舰队，没有第 %d 支" % (
                tag.upper(), len(idxs), fi + 1)}
        fi = idxs[fi]
    p, rel, st, en, raw = _navy_locate(root, fi, ti)
    if not p:
        return {"ok": False, "msg": "找不到第 %d 支舰队的第 %d 个特遣队" % (fi + 1, ti + 1)}
    tgt, err = _units_write_base(root)
    if not tgt:
        return {"ok": False, "msg": err}
    dst = os.path.join(tgt, rel)
    os.makedirs(os.path.dirname(dst) or tgt, exist_ok=True)
    if not os.path.exists(dst):
        try:
            import shutil as _sh
            _sh.copyfile(p, dst)
        except Exception as e:
            return {"ok": False, "msg": "复制来源失败：%s" % e}
    raw2 = io.open(dst, encoding="utf-8-sig", errors="replace").read()
    text = _strip_keep_len(raw2)
    # 在目标 task_force 的 } 前插入
    p2, rel2, st2, en2, _r = _navy_locate(root, fi, ti)
    if not p2:
        return {"ok": False, "msg": "重新定位失败"}
    ins = _ship_line(name, definition, exp)
    new_text = _insert_before_close(raw2, en2, ins)
    snapshot(dst)
    _atomic_write(dst, _bom_for(dst) + new_text.encode("utf-8"))
    return {"ok": True, "msg": "已在第 %d 个特遣队加 1 艘 %s" % (ti + 1, definition)}


def navy_add_tf(root, fi, name=None, location=None, tag=None):
    """往某支舰队里加一个特遣队。tag 语义同 navy_add_ship。"""
    root = _map_pick(root)
    try:
        fi = int(fi)
    except Exception:
        return {"ok": False, "msg": "index 不合法"}
    if tag:
        idxs, err = _navy_pick_tag(root, tag)
        if not idxs:
            return {"ok": False, "msg": err}
        if fi < 0 or fi >= len(idxs):
            return {"ok": False, "msg": "%s 只有 %d 支舰队，没有第 %d 支" % (
                tag.upper(), len(idxs), fi + 1)}
        fi = idxs[fi]
    info = load_navy(root)
    fleets = info["fleets"]
    if fi < 0 or fi >= len(fleets):
        return {"ok": False, "msg": "没有第 %d 支舰队" % (fi + 1)}
    f = fleets[fi]
    nm = name or ("新特遣队")
    loc = int(location) if location else f["naval_base"]
    p, rel, st, en, raw = _navy_locate(root, fi, None)
    if not p:
        return {"ok": False, "msg": "找不到第 %d 支舰队" % (fi + 1)}
    tgt, err = _units_write_base(root)
    if not tgt:
        return {"ok": False, "msg": err}
    dst = os.path.join(tgt, rel)
    os.makedirs(os.path.dirname(dst) or tgt, exist_ok=True)
    if not os.path.exists(dst):
        try:
            import shutil as _sh
            _sh.copyfile(p, dst)
        except Exception as e:
            return {"ok": False, "msg": "复制来源失败：%s" % e}
    raw2 = io.open(dst, encoding="utf-8-sig", errors="replace").read()
    p2, rel2, st2, en2, _r = _navy_locate(root, fi, None)
    if not p2:
        return {"ok": False, "msg": "重新定位失败"}
    block = ('\t\t\ttask_force = {\n'
             '\t\t\t\tname = "%s"\n'
             '\t\t\t\tlocation = %d\n'
             '\t\t\t}\n') % (nm.replace('"', ""), loc)
    new_text = _insert_before_close(raw2, en2, block)
    snapshot(dst)
    _atomic_write(dst, _bom_for(dst) + new_text.encode("utf-8"))
    return {"ok": True, "msg": "已在舰队「%s」加特遣队「%s」" % (f["name"], nm)}


def navy_set_ship(root, fi, ti, si, fields):
    """改一艘船的 name / definition / experience。"""
    root = _map_pick(root)
    try:
        fi, ti, si = int(fi), int(ti), int(si)
    except Exception:
        return {"ok": False, "msg": "index 不合法"}
    info = load_navy(root)
    fleets = info["fleets"]
    if fi < 0 or fi >= len(fleets):
        return {"ok": False, "msg": "没有第 %d 支舰队" % (fi + 1)}
    tfs = fleets[fi]["task_forces"]
    if ti < 0 or ti >= len(tfs):
        return {"ok": False, "msg": "没有第 %d 个特遣队" % (ti + 1)}
    ships = tfs[ti]["ships"]
    if si < 0 or si >= len(ships):
        return {"ok": False, "msg": "没有第 %d 艘船" % (si + 1)}
    cur = ships[si]
    nm = fields.get("name", cur["name"])
    df = fields.get("definition", cur["definition"])
    ex = fields.get("exp")

    p, rel, st, en, raw = _navy_locate(root, fi, ti)
    if not p:
        return {"ok": False, "msg": "定位失败"}
    tgt, err = _units_write_base(root)
    if not tgt:
        return {"ok": False, "msg": err}
    dst = os.path.join(tgt, rel)
    os.makedirs(os.path.dirname(dst) or tgt, exist_ok=True)
    if not os.path.exists(dst):
        try:
            import shutil as _sh
            _sh.copyfile(p, dst)
        except Exception as e:
            return {"ok": False, "msg": "复制来源失败：%s" % e}
    raw2 = io.open(dst, encoding="utf-8-sig", errors="replace").read()
    p2, rel2, st2, en2, _r = _navy_locate(root, fi, ti)
    if not p2:
        return {"ok": False, "msg": "重新定位失败"}
    seg = raw2[st2:en2]
    seg2 = seg
    if nm and nm != cur["name"]:
        seg2 = re.sub(r'name\s*=\s*"[^"]*"',
                      lambda m: 'name = "%s"' % nm.replace('"', ""), seg2, count=1)
    if df and df != cur["definition"]:
        seg2 = re.sub(r'definition\s*=\s*[A-Za-z0-9_]+',
                      lambda m: 'definition = %s' % df, seg2, count=1)
    if ex not in (None, ""):
        try:
            exv = "%g" % float(ex)
        except Exception:
            return {"ok": False, "msg": "经验值必须是数字"}
        if re.search(r'start_experience_factor\s*=\s*[\d.]+', seg2):
            seg2 = re.sub(r'start_experience_factor\s*=\s*[\d.]+',
                          lambda m: 'start_experience_factor = %s' % exv, seg2, count=1)
        else:
            seg2 = re.sub(r'(\bship\s*=\s*\{)',
                          lambda m: m.group(1) + ' start_experience_factor = %s' % exv,
                          seg2, count=1)
    # 只在第 si 艘那一行动手：按 ship 出现次序定位
    lines = seg2.splitlines(True)
    cnt = -1
    out = []
    for ln in lines:
        if re.search(r'\bship\s*=\s*\{', ln):
            cnt += 1
        out.append(ln)
    if cnt < si:
        return {"ok": False, "msg": "重新定位第 %d 艘失败" % (si + 1)}
    # 用逐行替换实现（简单可靠）
    idx2 = -1
    res = []
    for ln in seg.splitlines(True):
        if re.search(r'\bship\s*=\s*\{', ln):
            idx2 += 1
            if idx2 == si:
                newln = ln
                if nm and nm != cur["name"]:
                    newln = re.sub(r'name\s*=\s*"[^"]*"',
                                   lambda m: 'name = "%s"' % nm.replace('"', ""), newln, count=1)
                if df and df != cur["definition"]:
                    newln = re.sub(r'definition\s*=\s*[A-Za-z0-9_]+',
                                   lambda m: 'definition = %s' % df, newln, count=1)
                if ex not in (None, ""):
                    exv = "%g" % float(ex)
                    if re.search(r'start_experience_factor\s*=\s*[\d.]+', newln):
                        newln = re.sub(r'start_experience_factor\s*=\s*[\d.]+',
                                       lambda m: 'start_experience_factor = %s' % exv, newln, count=1)
                    else:
                        newln = re.sub(r'(\bship\s*=\s*\{)',
                                       lambda m: m.group(1) + ' start_experience_factor = %s' % exv,
                                       newln, count=1)
                res.append(newln)
                continue
        res.append(ln)
    new_seg = "".join(res)
    if new_seg == seg:
        return {"ok": True, "msg": "没有改动"}
    new_text = raw2[:st2] + new_seg + raw2[en2:]
    snapshot(dst)
    _atomic_write(dst, _bom_for(dst) + new_text.encode("utf-8"))
    return {"ok": True, "msg": "已改第 %d 艘船：%s / %s" % (si + 1, nm, df)}


def _navy_cut(root, rel, start, end, what):
    """按偏移从 history/units 文件里切掉一段（拒绝写父 mod）。"""
    tgt, err = _units_write_base(root)
    if not tgt:
        return {"ok": False, "msg": err}
    src = None
    for p in (_units_files(root)[1] or []):
        if os.path.basename(p) == os.path.basename(rel):
            src = p
            break
    if not src:
        return {"ok": False, "msg": "找不到来源文件"}
    dst = os.path.join(tgt, rel)
    os.makedirs(os.path.dirname(dst) or tgt, exist_ok=True)
    if not os.path.exists(dst):
        try:
            import shutil as _sh
            _sh.copyfile(src, dst)
        except Exception as e:
            return {"ok": False, "msg": "复制来源失败：%s" % e}
    raw = io.open(dst, encoding="utf-8-sig", errors="replace").read()
    n = len(raw)
    if not (0 <= start < n and 0 <= end <= n and start < end):
        return {"ok": False, "msg": "偏移不合法（%s-%s / 文件 %d 字节）" % (start, end, n)}
    st = min(start, n - 1)
    while st > 0 and raw[st - 1] in " \t":
        st -= 1
    if st > 0 and raw[st - 1] == "\n":
        st -= 1
    en = max(end, 1)
    en = min(en, n)
    while en < n and raw[en] in "\r\n":
        en += 1
    if st >= en:
        return {"ok": False, "msg": "偏移不合法（切完为空）"}
    new_text = raw[:st] + "\n" + raw[en:]
    snapshot(dst)
    _atomic_write(dst, _bom_for(dst) + new_text.encode("utf-8"))
    return {"ok": True, "msg": "已删除 %s" % what}


def navy_payload(root=None):
    info = load_navy(root)
    if not info.get("ok"):
        return info
    return {"ok": True, "fleets": [{
        "name": f["name"], "naval_base": f["naval_base"],
        "ship_total": f["ship_total"], "tf_count": f["tf_count"],
        "file": f["file"],
        "task_forces": [{"name": t["name"], "location": t["location"],
                         "ship_count": t["ship_count"],
                         "ships": t["ships"][:20]} for t in f["task_forces"]],
    } for f in info["fleets"]],
        "fleet_count": info["fleet_count"], "ship_total": info["ship_total"],
        "msg": info["msg"]}


def _tpl_locate(root, name):
    """找到某个 division_template 定义在哪个文件、哪个偏移。

    返回 (目标写入路径, 块起, 块止, 原文) 或 (None, -1, -1, "")。
    """
    base, files = _units_files(root)
    # 倒序：和 load_units 的「后者覆盖前者」一致，改到的才是列表里显示的那一份
    for p in reversed(files or []):
        try:
            raw = io.open(p, encoding="utf-8-sig", errors="replace").read()
        except Exception:
            continue
        text = _strip_keep_len(raw)
        for a, b, body in find_blocks(text, "division_template"):
            nm = _first(body, r'(?m)^\s*name\s*=\s*"([^"]*)"')
            if nm == name:
                # 写入层：拒写父 mod
                tgt, err = _units_write_base(root)
                if not tgt:
                    return None, -1, -1, err
                dst = os.path.join(tgt, os.path.join("history", "units",
                                                     os.path.basename(p)))
                os.makedirs(os.path.dirname(dst) or tgt, exist_ok=True)
                if not os.path.exists(dst):
                    import shutil as _sh
                    _sh.copyfile(p, dst)
                return dst, a, b, ""
    return None, -1, -1, "没有这个模板：%s" % name



def template_save(name, fields, root=None):
    """改一个 division_template：名字 / 编制 / 支援 / 锁定。

    fields 里给什么改什么：
      new_name   改名
      regiments  [{unit,x,y}]  整组替换
      support    [{unit,x,y}]  整组替换
      locked     bool
    """
    root = _map_pick(root)
    if not name:
        return {"ok": False, "msg": "模板名不能为空"}
    dst, a, b, err = _tpl_locate(root, name)
    if not dst:
        return {"ok": False, "msg": err or "找不到模板"}

    u = load_units(root, force=True)
    cur = None
    for t in u["templates"]:
        if t["name"] == name:
            cur = t
            break
    if not cur:
        return {"ok": False, "msg": "找不到模板 %s" % name}

    new_name = (fields.get("new_name") or name).strip()
    regs = fields.get("regiments")
    if regs is None:
        regs = cur["regiments"]
    sup = fields.get("support")
    if sup is None:
        sup = cur["support"]
    locked = fields.get("locked")
    if locked is None:
        locked = cur["locked"]

    raw = io.open(dst, encoding="utf-8-sig", errors="replace").read()
    text = _strip_keep_len(raw)
    # 重新定位（raw 和 text 长度一致，偏移可复用）
    A = B = -1
    for _a, _b, body in find_blocks(text, "division_template"):
        if _first(body, r'(?m)^\s*name\s*=\s*"([^"]*)"') == name:
            A, B = _a, _b
            break
    if A < 0:
        return {"ok": False, "msg": "重新定位失败"}

    # A 指向 { 的位置，块文本不能再带 division_template =
    new_block = _tpl_render(new_name, regs, sup, locked, with_key=False)
    new_text = raw[:A] + new_block + raw[B:]
    snapshot(dst)
    _atomic_write(dst, _bom_for(dst) + new_text.encode("utf-8"))
    load_units(root, force=True)
    return {"ok": True, "name": new_name,
            "msg": "模板「%s」已更新（编制 %d、支援 %d）" % (
                new_name, len(regs), len(sup))}


def template_delete(name, root=None):
    """删掉一个 division_template。"""
    root = _map_pick(root)
    dst, a, b, err = _tpl_locate(root, name)
    if not dst:
        return {"ok": False, "msg": err or "找不到模板"}
    raw = io.open(dst, encoding="utf-8-sig", errors="replace").read()
    text = _strip_keep_len(raw)
    A = B = -1
    for _a, _b, body in find_blocks(text, "division_template"):
        if _first(body, r'(?m)^\s*name\s*=\s*"([^"]*)"') == name:
            A, B = _a, _b
            break
    if A < 0:
        return {"ok": False, "msg": "重新定位失败"}
    # 连同后面的换行一起删
    st = A
    while st > 0 and raw[st - 1] in " \t":
        st -= 1
    en = B
    while en < len(raw) and raw[en] in "\r\n":
        en += 1
    new_text = raw[:st] + raw[en:]
    snapshot(dst)
    _atomic_write(dst, _bom_for(dst) + new_text.encode("utf-8"))
    load_units(root, force=True)
    return {"ok": True, "msg": "已删除模板「%s」" % name}




def units_payload(root=None):
    """给界面用的部队概况。"""
    u = load_units(root)
    return {"ok": True, "templates": u["templates"], "divisions": u["divisions"],
            "templates_total": u["templates_total"],
            "divisions_total": u["divisions_total"],
            "by_prov": {k: [{"i": x["i"], "name": x["name"], "template": x["template"]}
                            for x in v] for k, v in u["by_prov"].items()},
            "msg": "模板 %d 个，部队 %d 支" % (u["templates_total"], u["divisions_total"])}


def _units_write_file(root, src_rel):
    """给某个 history/units 文件算出写入路径（按 replace_path）。"""
    tgt, why = write_base(root, "history/units")
    if not tgt:
        return None
    p = os.path.join(tgt, src_rel)
    os.makedirs(os.path.dirname(p) or tgt, exist_ok=True)
    return p




def unit_delete(location, index, root=None):
    """删掉某省的第 index 支部队。"""
    root = _map_pick(root)
    try:
        location = int(location)
        index = int(index)
    except Exception:
        return {"ok": False, "msg": "参数不合法"}
    u = load_units(root)
    lst = u["by_prov"].get(str(location)) or []
    if not lst or index >= len(lst):
        return {"ok": False, "msg": "这一省没有第 %d 支部队" % (index + 1)}
    rec = lst[index]
    rel = rec["file"]
    # 找到真实文件（可能是链里的任意一层，写入转到 replace_path 层）
    src_path = None
    for p in (_units_files(root)[1] or []):
        if os.path.basename(p) == os.path.basename(rel):
            src_path = p
            break
    if not src_path:
        return {"ok": False, "msg": "找不到来源文件"}
    tgt, _err = _units_write_base(root)
    if not tgt:
        return {"ok": False, "msg": _err}
    dst = os.path.join(tgt, rel)
    os.makedirs(os.path.dirname(dst) or tgt, exist_ok=True)
    if not os.path.exists(dst):
        try:
            import shutil as _sh
            _sh.copyfile(src_path, dst)
        except Exception:
            return {"ok": False, "msg": "复制来源文件失败"}
    raw = io.open(dst, encoding="utf-8-sig", errors="replace").read()
    text = _strip_keep_len(raw)
    # 数到第 index 个匹配本省的 division
    cnt = -1
    for um in re.finditer(r'(?m)^[ \t]*units[ \t]*=\s*\{', text):
        ub = text.find("{", um.end() - 1)
        ue = brace_match(text, ub)
        if ue <= ub:
            continue
        for dm in re.finditer(r'(?m)^[ \t]*division[ \t]*=\s*\{', text[ub + 1:ue - 1]):
            db = text.find("{", ub + 1 + dm.end() - 1)
            de = brace_match(text, db)
            if de <= db:
                continue
            body = text[db + 1:de - 1]
            loc = int(_first(body, r'(?m)^\s*location\s*=\s*(\d+)', "0") or 0)
            if loc != location:
                continue
            cnt += 1
            if cnt != index:
                continue
            # 连同前面的空白一起删
            st = db - 1
            while st > 0 and raw[st - 1] in " \t":
                st -= 1
            en = de
            while en < len(raw) and raw[en] in "\r\n":
                en += 1
            new_text = raw[:st] + raw[en:]
            snapshot(dst)
            _atomic_write(dst, _bom_for(dst) + new_text.encode("utf-8"))
            load_units(root, force=True)
            return {"ok": True, "msg": "已删除省 %d 的第 %d 支部队" % (location, index + 1)}
    return {"ok": False, "msg": "没定位到要删的部队"}


def unit_move(location, index, new_location, root=None):
    """把某省的第 index 支部队移到另一个省。"""
    root = _map_pick(root)
    try:
        location = int(location)
        index = int(index)
        new_location = int(new_location)
    except Exception:
        return {"ok": False, "msg": "参数不合法"}
    if new_location <= 0:
        return {"ok": False, "msg": "目标省份号不合法"}
    u = load_units(root)
    lst = u["by_prov"].get(str(location)) or []
    if not lst or index >= len(lst):
        return {"ok": False, "msg": "这一省没有第 %d 支部队" % (index + 1)}
    rec = lst[index]
    rel = rec["file"]
    src_path = None
    for p in (_units_files(root)[1] or []):
        if os.path.basename(p) == os.path.basename(rel):
            src_path = p
            break
    if not src_path:
        return {"ok": False, "msg": "找不到来源文件"}
    tgt, _err = _units_write_base(root)
    if not tgt:
        return {"ok": False, "msg": _err}
    dst = os.path.join(tgt, rel)
    os.makedirs(os.path.dirname(dst) or tgt, exist_ok=True)
    if not os.path.exists(dst):
        try:
            import shutil as _sh
            _sh.copyfile(src_path, dst)
        except Exception:
            return {"ok": False, "msg": "复制来源文件失败"}
    raw = io.open(dst, encoding="utf-8-sig", errors="replace").read()
    text = _strip_keep_len(raw)
    cnt = -1
    for um in re.finditer(r'(?m)^[ \t]*units[ \t]*=\s*\{', text):
        ub = text.find("{", um.end() - 1)
        ue = brace_match(text, ub)
        if ue <= ub:
            continue
        for dm in re.finditer(r'(?m)^[ \t]*division[ \t]*=\s*\{', text[ub + 1:ue - 1]):
            db = text.find("{", ub + 1 + dm.end() - 1)
            de = brace_match(text, db)
            if de <= db:
                continue
            body = text[db + 1:de - 1]
            loc = int(_first(body, r'(?m)^\s*location\s*=\s*(\d+)', "0") or 0)
            if loc != location:
                continue
            cnt += 1
            if cnt != index:
                continue
            lm = re.search(r'(?m)^([ \t]*)location\s*=\s*(\d+)', raw[db + 1:de - 1])
            if not lm:
                return {"ok": False, "msg": "这支队伍没有 location 字段"}
            s0 = db + 1 + lm.start()
            s1 = db + 1 + lm.end()
            new_text = raw[:s0] + (lm.group(1) or "") + "location = %d" % new_location + raw[s1:]
            snapshot(dst)
            _atomic_write(dst, _bom_for(dst) + new_text.encode("utf-8"))
            load_units(root, force=True)
            return {"ok": True, "msg": "省 %d 第 %d 支已移到省 %d" % (
                location, index + 1, new_location)}
    return {"ok": False, "msg": "没定位到要移动的部队"}


def write_targets(root=None):
    """列出各类资源在叠加链里的真实写入目标，给界面做提示。

    回答「我在这里改，游戏到底会不会读到」。"""
    root = _map_pick(root)
    subs = [
        ("history/states", "州"),
        ("history/countries", "国家历史"),
        ("map/strategicregions", "战略区"),
        ("map/supplyareas", "补给区"),
        ("common/ideas", "想法"),
        ("common/national_focus", "国策"),
        ("common/technologies", "科技"),
        ("common/units/equipment", "装备"),
        ("common/units", "单位"),
        ("events", "事件"),
    ]
    items = []
    for sub, label in subs:
        base, why = write_base(root, sub)
        file_count = 0
        if why == "replace_path" and base:
            target_dir = os.path.join(base, sub.replace("/", os.sep))
            if os.path.isdir(target_dir):
                for _dp, _dn, _fns in os.walk(target_dir):
                    file_count += len(_fns)
        items.append({
            "sub": sub, "label": label,
            "base": base or "",
            "mod": os.path.basename((base or "").rstrip("\\/")) or "",
            "blocked": why == "replace_path",
            "file_count": file_count,
            "note": write_note(root, sub),
        })
    return {"ok": True, "items": items,
            "msg": "共 %d 类，%d 类被 replace_path 接管" % (
                len(items), sum(1 for x in items if x["blocked"]))}






# v0.94 地图像素编辑地基：原位写 bmp + 区块撤销
import struct








_state.set_map_var("PROV_RGB", {})  # 省 id -> (r,g,b)，来自 definition.csv


_state.set_map_var("_PROV_RGB_CACHE", {})


_state.set_map_var("MAP_EDIT", {"pending": [], "undo": [], "redo": [], "file": "", "touched": set()})
_state.set_map_var("MAP_UNDO_DIR", os.path.join(WORK, "mapundo"))












# v0.99 省份合并 / 删除




_state.set_map_var("_NB_CACHE", {})


_ALL_NB_CACHE = {}


def _all_prov_neighbors(root):
    """一次扫描算全图省的邻接关系（共用边即邻接）。

    map_prov_neighbors 是按单个省算的、每次整幅扫描 5 秒；
    铁路检查要考虑几千段，必须一次性建表。结果按 bmp mtime 缓存。"""
    root = _map_pick(root)
    layers = mod_layers(root)
    bmp, _ = _layers_find("map/provinces.bmp", layers)
    csvp, _ = _layers_find("map/definition.csv", layers)
    if not bmp or not csvp:
        return {}
    key = (os.path.abspath(bmp), os.path.getmtime(bmp),
           os.path.abspath(csvp), os.path.getmtime(csvp))
    if key in _ALL_NB_CACHE:
        return _ALL_NB_CACHE[key]

    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    rgb2pid = {}
    with io.open(csvp, encoding="utf-8", errors="replace") as f:
        for line in f:
            p = line.strip().split(";")
            if len(p) >= 8 and p[0].isdigit():
                rgb2pid[(int(p[1]), int(p[2]), int(p[3]))] = int(p[0])
    with Image.open(bmp) as im:
        w, h = im.size
        raw = im.convert("RGB").tobytes()
    # RGB 直接比较比先转省号快
    nb = {}
    for y in range(h):
        row = y * w * 3
        nrow = row + w * 3
        for x in range(w):
            o = row + x * 3
            a = raw[o:o + 3]
            if x + 1 < w:
                b = raw[o + 3:o + 6]
                if a != b:
                    pa = rgb2pid.get((a[0], a[1], a[2]), 0)
                    pb = rgb2pid.get((b[0], b[1], b[2]), 0)
                    if pa and pb:
                        nb.setdefault(pa, set()).add(pb)
                        nb.setdefault(pb, set()).add(pa)
            if y + 1 < h:
                b = raw[nrow + x * 3:nrow + x * 3 + 3]
                if a != b:
                    pa = rgb2pid.get((a[0], a[1], a[2]), 0)
                    pb = rgb2pid.get((b[0], b[1], b[2]), 0)
                    if pa and pb:
                        nb.setdefault(pa, set()).add(pb)
                        nb.setdefault(pb, set()).add(pa)
    out = {k: v for k, v in nb.items()}
    _ALL_NB_CACHE.clear()
    _ALL_NB_CACHE[key] = out
    return out






# v1.0 新建州（把若干省组织成一个州）










_state.set_map_var("MAP_PALETTE", ((196, 112, 92), (96, 138, 186), (150, 158, 96),
               (188, 150, 84), (118, 132, 168), (168, 120, 148)))








def _set_state_provinces(body, pids):
    """重建 state 文件里的 provinces = { ... } 列表"""
    pids = sorted(set(int(p) for p in pids))
    inner = "\n" + "".join("\t\t%d\n" % p for p in pids) + "\t"
    m = re.search(r'(?m)^[ \t]*provinces\s*=\s*\{', body)
    if m:
        b = body.find('{', m.end() - 1)
        e = brace_match(body, b)
        if e > b:
            return body[:b + 1] + inner + body[e - 1:]
    line = "provinces={\n" + "".join("\t\t%d\n" % p for p in pids) + "\t}"
    nm = re.search(r'(?m)^[ \t]*name\s*=\s*"[^"]*"', body)
    if nm:
        return body[:nm.end()] + "\n\t" + line + body[nm.end():]
    return body.rstrip() + "\n\t" + line + "\n"


def _parse_state_provinces(body):
    """从 state 块文本里读出 provinces 列表（不依赖内存 STATES）"""
    m = re.search(r'(?m)^[ \t]*provinces\s*=\s*\{', body)
    if not m:
        return []
    b = body.find('{', m.end() - 1)
    e = brace_match(body, b)
    if e <= b:
        return []
    return [int(x) for x in re.findall(r'\d+', body[b + 1:e - 1])]








# v0.80 战略区图层
_state.set_map_var("_REGION_CACHE", {})




# v0.85 地图完整性检查
# v1.2 地形层：游戏配色 + 高度图山体阴影（全 Pillow，快 70 倍）


def _refine_state_warnings(pid, prov2state):
    """细化前的风险提示：VP / 首都 / 州归属"""
    warn = []
    sid = prov2state.get(pid, 0)
    if not sid:
        warn.append("省 %d 不属于任何州，细化出来的新省也不会有归属" % pid)
        return warn, 0

    st = None
    for s in (STATES.values() if isinstance(STATES, dict) else []):
        try:
            if int(s.get("id") or 0) == int(sid):
                st = s
                break
        except Exception:
            continue
    if not st:
        return warn, sid

    provs = st.get("provinces") or []
    if len(provs) <= 1:
        warn.append("州 %d 只有这一个省，细化后新省需要单独建州或并入邻州" % sid)
    else:
        warn.append("新省会加入州 %d（共 %d 省）" % (sid, len(provs)))

    for vp in (st.get("victory_points") or []):
        try:
            if int(vp.get("province") or -1) == int(pid):
                warn.append("省 %d 有 %s 点胜利点，细化后图标会随质心移到原省残留块" % (
                    pid, vp.get("points")))
        except Exception:
            pass

    # 首都：只查已加载的国家，命中就提示
    try:
        for c in (COUNTRIES.values() if isinstance(COUNTRIES, dict) else []):
            if str(c.get("capital") or "") == str(pid):
                warn.append("省 %d 是 %s 的首都，细化后首都位置会落在原省残留块" % (
                    pid, c.get("tag") or c.get("name") or "某国"))
    except Exception:
        pass
    return warn, sid


def _refine_attach_to_state(root, sid, new_ids, pid):
    """把细化出来的新省加进原州（改 history/states/*.txt 的 provinces 列表）"""
    if not sid or not new_ids:
        return ""
    _r, rel, path = _state_file_for(sid)
    if not path:
        return ""
    try:
        text = _read_text(path)
        m = re.search(r'(?m)^[ \t]*provinces\s*=\s*\{', text)
        cur = []
        if m:
            b = text.find("{", m.end() - 1)
            e = brace_match(text, b)
            if e > b:
                cur = [int(x) for x in re.findall(r'\d+', text[b + 1:e - 1])]
        if not cur:
            cur = [pid]
        merged = sorted(set(cur) | set(int(x) for x in new_ids))
        if merged == sorted(set(cur)):
            return ""
        body = _set_state_provinces(text, merged)
        snapshot(path)
        _write_bom_text(path, body, text.startswith("\ufeff") or True)
        return rel
    except Exception as e:
        print("写州归属失败:", e)
        return ""






def _railway_file(root):
    """找 railways.txt（先 mod 后原版），返回 (path, base)"""
    for base in reversed(mod_layers(root) or []):
        if not base:
            continue
        p = os.path.join(base, "map", "railways.txt")
        if os.path.exists(p):
            return p, base
    if GAME:
        p = os.path.join(GAME, "map", "railways.txt")
        if os.path.exists(p):
            return p, GAME
    return None, None


def _railway_parse(path):
    """解析 railways.txt。

    行式：   <level> <count> p1 p2 p3 ...
    块式：   railway = { level = N provinces = { p1 p2 ... } }
    两种都收，返回 [{"level": N, "provs": [...], "raw_i": 行号}]"""
    out = []
    if not path or not os.path.exists(path):
        return out
    try:
        raw = io.open(path, encoding="utf-8-sig", errors="replace").read()
    except Exception:
        return out
    text = strip_comments(raw)
    # 块式
    for m in re.finditer(r'(?m)^\s*railway\s*=\s*\{', text):
        b = text.find("{", m.end() - 1)
        e = brace_match(text, b)
        if e <= b:
            continue
        body = text[b + 1:e - 1]
        lv = re.search(r'level\s*=\s*(\d+)', body)
        pr = re.search(r'provinces\s*=\s*\{([^}]*)\}', body)
        if pr:
            provs = [int(x) for x in re.findall(r'\d+', pr.group(1))]
            if provs:
                out.append({"level": int(lv.group(1)) if lv else 1,
                            "provs": provs, "form": "block"})
    # 行式
    for ln in text.splitlines():
        s = ln.strip()
        if not s or s.startswith("#"):
            continue
        parts = s.split()
        if len(parts) < 3 or not parts[0].isdigit() or not parts[1].isdigit():
            continue
        try:
            level = int(parts[0])
            n = int(parts[1])
        except Exception:
            continue
        provs = []
        for tok in parts[2:2 + n]:
            try:
                provs.append(int(tok))
            except Exception:
                break
        if len(provs) == n and provs:
            out.append({"level": level, "provs": provs, "form": "line"})
    return out


def railways_list(root=None):
    """铁路列表 + 每条的状态（断连 / 等级越界）"""
    root = _map_pick(root)
    path, base = _railway_file(root)
    if not path:
        return {"ok": False, "msg": "找不到 map/railways.txt"}
    rails = _railway_parse(path)
    # 一次算全图邻接，再逐条查表（逐段调 map_prov_neighbors 会把几千段算成几小时）
    allnb = _all_prov_neighbors(root)
    items = []
    broken = 0
    over = 0
    for i2, r in enumerate(rails):
        provs = r["provs"]
        bad = []
        for a, b in zip(provs, provs[1:]):
            if b not in (allnb.get(a) or ()):
                bad.append([a, b])
        if bad:
            broken += 1
        if r["level"] > 5:
            over += 1
        items.append({"i": i2, "level": r["level"], "provs": provs,
                      "len": len(provs), "broken": bad,
                      "over": r["level"] > 5, "form": r["form"]})
    return {"ok": True, "count": len(items), "broken": broken, "over": over,
            "file": os.path.relpath(path, base) if base else path,
            "fromMod": bool(root and base and os.path.abspath(base) == os.path.abspath(root)),
            "items": items,
            "msg": "共 %d 条铁路，%d 条断连，%d 条等级超 5" % (len(items), broken, over)}


def railway_set_level(index, level, root=None):
    """改某条铁路的等级（行式直接改第一个数字，块式改 level = N）"""
    root = _map_pick(root)
    path, base = _railway_file(root)
    if not path:
        return {"ok": False, "msg": "找不到 map/railways.txt"}
    if os.path.abspath(base) == os.path.abspath(GAME or ""):
        return {"ok": False, "msg": "railways.txt 来自原版，只读"}
    try:
        level = max(1, min(10, int(level)))
        index = int(index)
    except Exception:
        return {"ok": False, "msg": "参数不合法"}
    raw = io.open(path, encoding="utf-8-sig", errors="replace").read()
    lines = raw.splitlines(True)
    # 收集行式铁路的行号
    line_rows = []
    for i, ln in enumerate(lines):
        s = ln.strip()
        parts = s.split()
        if len(parts) >= 3 and parts[0].isdigit() and parts[1].isdigit():
            try:
                n = int(parts[1])
                if len(parts[2:2 + n]) == n:
                    line_rows.append(i)
            except Exception:
                pass
    rails = _railway_parse(path)
    if index < 0 or index >= len(rails):
        return {"ok": False, "msg": "没有第 %d 条铁路" % index}
    target = rails[index]
    if target.get("form") == "line" and index < len(line_rows):
        i = line_rows[index]
        parts = lines[i].split(None, 2)
        rest = parts[2] if len(parts) > 2 else ""
        lines[i] = "%d %s %s" % (level, parts[1] if len(parts) > 1 else str(len(target["provs"])), rest)
        if not lines[i].endswith(chr(10)):
            lines[i] += chr(10)
        snapshot(path)
        _atomic_write(path, b"\xef\xbb\xbf" + "".join(lines).encode("utf-8"))
        return {"ok": True, "index": index, "level": level,
                "msg": "第 %d 条铁路等级改为 %d" % (index, level)}
    return {"ok": False, "msg": "这条铁路是块式写法，暂不支持改等级"}


def railway_edit(index, level=None, provs=None, root=None):
    """改某条铁路：等级 / 省份序列（行式直接改该行，块式重建块）"""
    root = _map_pick(root)
    path, base = _railway_file(root)
    if not path:
        return {"ok": False, "msg": "找不到 map/railways.txt"}
    if os.path.abspath(base) == os.path.abspath(GAME or ""):
        return {"ok": False, "msg": "railways.txt 来自原版，只读"}
    try:
        index = int(index)
    except Exception:
        return {"ok": False, "msg": "铁路序号不合法"}

    rails = _railway_parse(path)
    if index < 0 or index >= len(rails):
        return {"ok": False, "msg": "没有第 %d 条铁路" % index}
    cur = rails[index]

    new_level = int(level) if level not in (None, "") else cur["level"]
    new_level = max(1, min(10, new_level))
    new_provs = cur["provs"]
    if provs:
        try:
            cand = [int(x) for x in provs]
        except Exception:
            return {"ok": False, "msg": "省份列表不合法"}
        if len(cand) < 2:
            return {"ok": False, "msg": "铁路至少要有 2 个省"}
        # 邻接校验：相邻两省必须接壤，否则游戏里会断
        allnb = _all_prov_neighbors(root)
        bad = [[a, b] for a, b in zip(cand, cand[1:]) if b not in (allnb.get(a) or ())]
        if bad:
            return {"ok": False,
                    "msg": "这些相邻省不接壤，会断连：%s" % bad[:3]}
        new_provs = cand

    raw = io.open(path, encoding="utf-8-sig", errors="replace").read()
    lines = raw.splitlines(True)

    if cur.get("form") == "line":
        # 行式在原文里的行号
        rows = []
        for i, ln in enumerate(lines):
            parts = ln.strip().split()
            if len(parts) >= 3 and parts[0].isdigit() and parts[1].isdigit():
                try:
                    n = int(parts[1])
                    if len(parts[2:2 + n]) == n:
                        rows.append(i)
                except Exception:
                    pass
        if index >= len(rows):
            return {"ok": False, "msg": "定位不到这一行"}
        i = rows[index]
        tail = chr(10) if lines[i].endswith(chr(10)) else ""
        lines[i] = "%d %d %s%s" % (new_level, len(new_provs),
                                   " ".join(str(p) for p in new_provs), tail)
        snapshot(path)
        _atomic_write(path, b"\xef\xbb\xbf" + "".join(lines).encode("utf-8"))
        return {"ok": True, "index": index, "level": new_level, "provs": new_provs,
                "msg": "第 %d 条铁路已更新：等级 %d，%d 个省" % (
                    index, new_level, len(new_provs))}

    # 块式：整条重建
    text = strip_comments(raw)
    blocks = []
    for m in re.finditer(r'(?m)^\s*railway\s*=\s*\{', text):
        b = text.find("{", m.end() - 1)
        e = brace_match(text, b)
        if e > b:
            blocks.append((b, e))
    if index >= len(blocks):
        return {"ok": False, "msg": "定位不到这个块"}
    b, e = blocks[index]
    body = ("\n\tlevel = %d\n\tprovinces = {\n\t\t%s\n\t}\n" % (
        new_level, "\n\t\t".join(str(p) for p in new_provs)))
    new_raw = raw[:b + 1] + body + raw[e - 1:]
    snapshot(path)
    _atomic_write(path, _bom_for(path) + new_raw.encode("utf-8"))
    return {"ok": True, "index": index, "level": new_level, "provs": new_provs,
            "msg": "第 %d 条铁路（块式）已重建" % index}


def railway_delete(index, root=None):
    """删除一条铁路（行式删行，块式删块）"""
    root = _map_pick(root)
    path, base = _railway_file(root)
    if not path:
        return {"ok": False, "msg": "找不到 map/railways.txt"}
    if os.path.abspath(base) == os.path.abspath(GAME or ""):
        return {"ok": False, "msg": "railways.txt 来自原版，只读"}
    try:
        index = int(index)
    except Exception:
        return {"ok": False, "msg": "序号不合法"}
    rails = _railway_parse(path)
    if index < 0 or index >= len(rails):
        return {"ok": False, "msg": "没有第 %d 条铁路" % index}
    cur = rails[index]
    raw = io.open(path, encoding="utf-8-sig", errors="replace").read()
    lines = raw.splitlines(True)
    if cur.get("form") == "line":
        rows = []
        for i, ln in enumerate(lines):
            parts = ln.strip().split()
            if len(parts) >= 3 and parts[0].isdigit() and parts[1].isdigit():
                try:
                    n = int(parts[1])
                    if len(parts[2:2 + n]) == n:
                        rows.append(i)
                except Exception:
                    pass
        if index >= len(rows):
            return {"ok": False, "msg": "定位不到这一行"}
        del lines[rows[index]]
        snapshot(path)
        _atomic_write(path, b"\xef\xbb\xbf" + "".join(lines).encode("utf-8"))
        return {"ok": True, "msg": "已删除第 %d 条铁路（%d 个省）" % (index, len(cur["provs"]))}
    return {"ok": False, "msg": "块式铁路暂不支持删除"}


def supply_areas(root=None):
    """列出补给区：id、价值、覆盖的州"""
    root = _map_pick(root)
    out = []
    seen_ids = set()
    for base in reversed(mod_layers(root) or []):
        if not base:
            continue
        d = os.path.join(base, "map", "supplyareas")
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            if not fn.endswith(".txt"):
                continue
            p = os.path.join(d, fn)
            try:
                text = strip_comments(io.open(p, encoding="utf-8-sig", errors="replace").read())
            except Exception:
                continue
            for m in re.finditer(r'supply_area\s*=\s*\{', text):
                b = text.find("{", m.end() - 1)
                e = brace_match(text, b)
                if e <= b:
                    continue
                body = text[b + 1:e - 1]
                sid = re.search(r'(?m)^\s*id\s*=\s*(\d+)', body)
                if not sid:
                    continue
                sid = int(sid.group(1))
                val = re.search(r'(?m)^\s*value\s*=\s*(\d+)', body)
                st = re.search(r'states\s*=\s*\{([^}]*)\}', body)
                states = [int(x) for x in re.findall(r'\d+', st.group(1))] if st else []
                out.append({"id": sid, "value": int(val.group(1)) if val else 0,
                            "states": states, "count": len(states),
                            "file": os.path.relpath(p, base),
                            "root": os.path.abspath(base)})
                seen_ids.add(sid)
    # 同名 id 以最后一层（mod）为准
    merged = {}
    for a in out:
        merged[a["id"]] = a
    items = sorted(merged.values(), key=lambda x: x["id"])
    return {"ok": True, "count": len(items), "items": items,
            "msg": "共 %d 个补给区" % len(items)}
























# ---------- v1.23.48 河流绘制 ----------
# rivers.bmp 是 8 位索引图：255=陆地 254=海洋，河道用 3/6/4/11 这几档索引。
# 方向是拿省份类型做面积统计反解出来的（原版 97.7% / ES 98.7%），不是猜的。
_state.set_map_var("RIVER_KINDS", (
    ("main",      "河流（主干）",   3),
    ("tributary", "支流",           6),
    ("stream",    "小溪",           4),
    ("deep",      "深河（可通航）",  11),
))
_state.set_map_var("RIVER_KIND_IDX", {k: i for k, _l, i in _state.map_var("RIVER_KINDS")})
_state.set_map_var("RIVER_LAND", 255)
_state.set_map_var("RIVER_SEA", 254)
_state.set_map_var("_RIVER_UNDO", [])  # [{"path":..., "px": {(x,y): old}}]
_state.set_map_var("_RIVER_LAST", {"path": None, "pt": None})
_state.set_map_var("_DEF_RGB_CACHE", {"key": None, "map": {}})














def _sr_dirs(root):
    """战略区目录（先 mod 后原版），返回 [(base, dir)]"""
    out = []
    for base in reversed(mod_layers(root) or []):
        if not base:
            continue
        d = os.path.join(base, "map", "strategicregions")
        if os.path.isdir(d):
            out.append((base, d))
    if GAME:
        d = os.path.join(GAME, "map", "strategicregions")
        if os.path.isdir(d):
            out.append((GAME, d))
    return out


def _sr_parse_file(path):
    """一个文件里可能有多个 strategic_region 块"""
    out = []
    try:
        text = strip_comments(io.open(path, encoding="utf-8-sig", errors="replace").read())
    except Exception:
        return out
    for m in re.finditer(r'strategic_region\s*=\s*\{', text):
        b = text.find("{", m.end() - 1)
        e = brace_match(text, b)
        if e <= b:
            continue
        body = text[b + 1:e - 1]
        sid = re.search(r'(?m)^\s*id\s*=\s*(\d+)', body)
        if not sid:
            continue
        nm = re.search(r'(?m)^\s*name\s*=\s*"([^"]*)"', body)
        pr = re.search(r'provinces\s*=\s*\{([^}]*)\}', body)
        provs = [int(x) for x in re.findall(r'\d+', pr.group(1))] if pr else []
        out.append({"id": int(sid.group(1)),
                    "name": nm.group(1) if nm else "",
                    "provinces": provs,
                    "span": [b, e]})
    return out


def strategic_regions_list(root=None):
    """列出全部战略区；同 id 以最后一层（mod）为准"""
    root = _map_pick(root)
    seen = {}
    for base, d in _sr_dirs(root):
        for fn in sorted(f for f in os.listdir(d) if f.endswith(".txt")):
            p = os.path.join(d, fn)
            for r in _sr_parse_file(p):
                if r["id"] in seen and os.path.abspath(base) == os.path.abspath(GAME or ""):
                    continue   # 原版的被 mod 覆盖
                seen[r["id"]] = {
                    "id": r["id"], "name": r["name"],
                    "count": len(r["provinces"]),
                    "provinces": r["provinces"][:400],
                    "file": os.path.relpath(p, base),
                    "base": os.path.abspath(base),
                    "fromMod": os.path.abspath(base) != os.path.abspath(GAME or ""),
                }
    items = sorted(seen.values(), key=lambda x: x["id"])
    return {"ok": True, "count": len(items), "items": items,
            "msg": "共 %d 个战略区" % len(items)}


def _sr_weather_template(root):
    """从任意一个现有战略区里抠出 weather 块，新建时作为模板"""
    for base, d in _sr_dirs(root):
        for fn in sorted(os.listdir(d)):
            if not fn.endswith(".txt"):
                continue
            p = os.path.join(d, fn)
            try:
                text = strip_comments(io.open(p, encoding="utf-8-sig", errors="replace").read())
            except Exception:
                continue
            m = re.search(r'weather\s*=\s*\{', text)
            if not m:
                continue
            b = text.find("{", m.end() - 1)
            e = brace_match(text, b)
            if e > b:
                return text[b:e]
    return ""


def _sr_write_dir(root):
    """新建战略区写到 mod 目录（输出模式下写到 output）。

    map/strategicregions 常被某一层用 replace_path 独占（muvluvCN 就是），
    写在别处游戏不读，所以按 write_base 算真实写入层。"""
    root = _map_pick(root)
    _calc = root if root else (ROOTS[-1] if ROOTS else "")
    base, _why = write_base(_calc, "map/strategicregions")
    if not base:
        return None, None
    d = _out_path(base, os.path.join("map", "strategicregions")) if _state.output_mode() else \
        os.path.join(base, "map", "strategicregions")
    os.makedirs(d, exist_ok=True)
    _write_layer_hint["strategicregions"] = _why
    return base, d


def strategic_region_create(root=None, sid=None, name=None, provinces=None):
    """新建战略区。id 不给就取现有最大值 +1；weather 从现有区复制"""
    root = _map_pick(root)
    existing = strategic_regions_list(root)
    used = set(x["id"] for x in existing["items"])
    try:
        sid = int(sid) if sid not in (None, "") else (max(used) + 1 if used else 1)
    except Exception:
        return {"ok": False, "msg": "id 不合法"}
    if sid in used:
        return {"ok": False, "msg": "战略区 %d 已存在" % sid}
    provs = []
    if provinces:
        try:
            provs = sorted(set(int(x) for x in provinces if int(x) > 0))
        except Exception:
            return {"ok": False, "msg": "省份列表不合法"}
    if not provs:
        return {"ok": False, "msg": "至少要指定一个省"}

    # 一个省只能属于一个战略区，先检查
    owner = {}
    for it in existing["items"]:
        for p in it.get("provinces") or []:
            owner[p] = it["id"]
    clash = [(p, owner[p]) for p in provs if p in owner]
    if clash:
        return {"ok": False,
                "msg": "这些省已属于别的战略区：%s" % clash[:3]}

    b, d = _sr_write_dir(root)
    fn = "%d-New Strategic Region.txt" % sid
    path = os.path.join(d, fn)
    weather = _sr_weather_template(root)
    body = "strategic_region={\n\tid=%d\n\tname=\"%s\"\n\tprovinces={\n" % (
        sid, (name or ("STRATEGICREGION_%d" % sid)))
    for i in range(0, len(provs), 12):
        body += "\t\t" + " ".join(str(x) for x in provs[i:i + 12]) + "\n"
    body += "\t}\n"
    if weather:
        body += "\tweather=" + weather + "\n"
    body += "}\n"
    _atomic_write(path, _bom_for(path) + body.encode("utf-8"))
    reload_data()
    return {"ok": True, "id": sid, "file": os.path.relpath(path, b),
            "provinces": len(provs), "weatherCopied": bool(weather),
            "msg": "已新建战略区 %d（%d 个省）%s" % (
                sid, len(provs), "，天气块已复制" if weather else "，没有找到天气模板")}


def _sr_find(root, sid):
    """按 id 找文件与块位置"""
    for base, d in _sr_dirs(root):
        for fn in sorted(f for f in os.listdir(d) if f.endswith(".txt")):
            p = os.path.join(d, fn)
            for r in _sr_parse_file(p):
                if r["id"] == int(sid):
                    return base, p, r
    return None, None, None


def strategic_region_set_provinces(sid, provinces, root=None):
    """改某战略区覆盖的省份（整块替换 provinces = { }）"""
    root = _map_pick(root)
    try:
        sid = int(sid)
        provs = sorted(set(int(x) for x in (provinces or []) if int(x) > 0))
    except Exception:
        return {"ok": False, "msg": "参数不合法"}
    if not provs:
        return {"ok": False, "msg": "至少要有一个省"}
    base, path, rec = _sr_find(root, sid)
    if not path:
        return {"ok": False, "msg": "没有战略区 %d" % sid}
    if os.path.abspath(base) == os.path.abspath(GAME or ""):
        return {"ok": False, "msg": "这个战略区来自原版，只读"}
    text = io.open(path, encoding="utf-8-sig", errors="replace").read()
    b, e = rec["span"]
    body = text[b + 1:e - 1]
    inner = "\n" + "".join("\t\t" + " ".join(str(x) for x in provs[i:i + 12]) + "\n"
                            for i in range(0, len(provs), 12)) + "\t"
    m = re.search(r'provinces\s*=\s*\{', body)
    if m:
        pb = body.find("{", m.end() - 1)
        pe = brace_match(body, pb)
        if pe > pb:
            body2 = body[:pb] + "{" + inner + "}" + body[pe:]
        else:
            body2 = body
    else:
        body2 = body + "\n\tprovinces={" + inner + "}"
    new_text = text[:b + 1] + body2 + text[e - 1:]
    snapshot(path)
    _atomic_write(path, _bom_for(path) + new_text.encode("utf-8"))
    return {"ok": True, "id": sid, "provinces": len(provs),
            "msg": "战略区 %d 现在覆盖 %d 个省" % (sid, len(provs))}


def strategic_region_delete(sid, root=None):
    """删除战略区：整个块从文件里摘掉；文件里没有其它块就删文件"""
    root = _map_pick(root)
    try:
        sid = int(sid)
    except Exception:
        return {"ok": False, "msg": "id 不合法"}
    base, path, rec = _sr_find(root, sid)
    if not path:
        return {"ok": False, "msg": "没有战略区 %d" % sid}
    if os.path.abspath(base) == os.path.abspath(GAME or ""):
        return {"ok": False, "msg": "这个战略区来自原版，只读"}
    text = io.open(path, encoding="utf-8-sig", errors="replace").read()
    others = [r for r in _sr_parse_file(path) if r["id"] != sid]
    if not others:
        snapshot(path)
        try:
            os.remove(path)
        except Exception as e:
            return {"ok": False, "msg": "删文件失败：%s" % e}
        return {"ok": True, "id": sid, "removedFile": True,
                "msg": "已删除战略区 %d 及其文件" % sid}
    b, e = rec["span"]
    # 连同前面的 strategic_region = { 一起摘掉
    start = text.rfind("strategic_region", 0, b)
    if start < 0:
        start = b
    new_text = text[:start] + text[e:]
    snapshot(path)
    _atomic_write(path, _bom_for(path) + new_text.encode("utf-8"))
    return {"ok": True, "id": sid, "removedFile": False,
            "msg": "已从文件里移除战略区 %d（文件里还有 %d 个）" % (sid, len(others))}




def _adj_file(root):
    for base in reversed(mod_layers(root) or []):
        if not base:
            continue
        p = os.path.join(base, "map", "adjacencies.csv")
        if os.path.exists(p):
            return p, base
    if GAME:
        p = os.path.join(GAME, "map", "adjacencies.csv")
        if os.path.exists(p):
            return p, GAME
    return None, None


def adjacencies_list(root=None):
    """海峡 / 陆地连接列表。坐标 -1 表示不画线，用省质心代替"""
    root = _map_pick(root)
    path, base = _adj_file(root)
    if not path:
        return {"ok": False, "msg": "找不到 map/adjacencies.csv"}
    items = []
    try:
        raw = io.open(path, encoding="utf-8-sig", errors="replace").read()
    except Exception as e:
        return {"ok": False, "msg": "读取失败：%s" % e}
    lines = raw.splitlines()
    header = lines[0] if lines else ""
    for i, ln in enumerate(lines[1:], start=2):
        if not ln.strip() or ln.strip().startswith("#"):
            continue
        c = ln.split(";")
        if len(c) < 4:
            continue
        try:
            frm, to = int(c[0]), int(c[1])
        except Exception:
            continue
        through = c[3] if len(c) > 3 else ""
        coords = []
        if len(c) >= 8:
            try:
                sx, sy, ex, ey = int(c[4]), int(c[5]), int(c[6]), int(c[7])
                if sx >= 0 and sy >= 0:
                    coords = [sx, sy, ex, ey]
            except Exception:
                pass
        items.append({"line": i, "from": frm, "to": to,
                      "type": c[2] if len(c) > 2 else "",
                      "through": through, "coords": coords,
                      "rule": c[8] if len(c) > 8 else "",
                      "comment": c[9] if len(c) > 9 else ""})
    types = {}
    for a in items:
        types[a["type"]] = types.get(a["type"], 0) + 1
    return {"ok": True, "count": len(items), "types": types,
            "file": os.path.relpath(path, base) if base else path,
            "fromMod": bool(root and base and os.path.abspath(base) == os.path.abspath(root)),
            "items": items,
            "msg": "共 %d 条连接（%s）" % (
                len(items), "，".join("%s %d" % (k, v) for k, v in sorted(types.items())))}


def adjacency_edit(line, adj_type=None, root=None):
    """改某一条连接的类型（sea / land / lake 等）"""
    root = _map_pick(root)
    path, base = _adj_file(root)
    if not path:
        return {"ok": False, "msg": "找不到 map/adjacencies.csv"}
    if os.path.abspath(base) == os.path.abspath(GAME or ""):
        return {"ok": False, "msg": "adjacencies.csv 来自原版，只读"}
    try:
        line = int(line)
    except Exception:
        return {"ok": False, "msg": "行号不合法"}
    raw = io.open(path, encoding="utf-8-sig", errors="replace").read()
    lines = raw.splitlines(True)
    idx = line - 1
    if idx < 0 or idx >= len(lines):
        return {"ok": False, "msg": "没有第 %d 行" % line}
    c = lines[idx].rstrip("\r\n").split(";")
    if len(c) < 4:
        return {"ok": False, "msg": "这一行格式不对"}
    old = c[2]
    if adj_type:
        c[2] = adj_type
    tail = chr(10) if lines[idx].endswith(chr(10)) else ""
    lines[idx] = ";".join(c) + tail
    snapshot(path)
    _atomic_write(path, b"\xef\xbb\xbf" + "".join(lines).encode("utf-8"))
    return {"ok": True, "line": line, "from": old, "to": c[2],
            "msg": "第 %d 行的类型 %s → %s" % (line, old, c[2])}


def adjacency_delete(line, root=None):
    """删除一条连接"""
    root = _map_pick(root)
    path, base = _adj_file(root)
    if not path:
        return {"ok": False, "msg": "找不到 map/adjacencies.csv"}
    if os.path.abspath(base) == os.path.abspath(GAME or ""):
        return {"ok": False, "msg": "adjacencies.csv 来自原版，只读"}
    try:
        line = int(line)
    except Exception:
        return {"ok": False, "msg": "行号不合法"}
    raw = io.open(path, encoding="utf-8-sig", errors="replace").read()
    lines = raw.splitlines(True)
    idx = line - 1
    if idx < 0 or idx >= len(lines):
        return {"ok": False, "msg": "没有第 %d 行" % line}
    gone = lines[idx].rstrip("\r\n")
    del lines[idx]
    snapshot(path)
    _atomic_write(path, b"\xef\xbb\xbf" + "".join(lines).encode("utf-8"))
    return {"ok": True, "line": line, "removed": gone[:60],
            "msg": "已删除第 %d 行连接" % line}


def adjacency_add(frm, to, adj_type="sea", through="", root=None):
    """新增一条连接（追加到文件末尾）"""
    root = _map_pick(root)
    path, base = _adj_file(root)
    if not path:
        return {"ok": False, "msg": "找不到 map/adjacencies.csv"}
    if os.path.abspath(base) == os.path.abspath(GAME or ""):
        return {"ok": False, "msg": "adjacencies.csv 来自原版，只读"}
    try:
        frm, to = int(frm), int(to)
    except Exception:
        return {"ok": False, "msg": "省号不合法"}
    if frm == to:
        return {"ok": False, "msg": "两端不能是同一个省"}
    raw = io.open(path, encoding="utf-8-sig", errors="replace").read()
    lines = raw.splitlines(True)
    for ln in lines[1:]:
        c = ln.split(";")
        if len(c) >= 2:
            try:
                a, b = int(c[0]), int(c[1])
            except Exception:
                continue
            if (a == frm and b == to) or (a == to and b == frm):
                return {"ok": False, "msg": "这两省之间已经有连接了"}
    row = "%d;%d;%s;%s;-1;-1;-1;-1;;" % (frm, to, adj_type or "sea", through or "")
    if not raw.endswith(chr(10)):
        lines[-1] = lines[-1] + chr(10)
    lines.append(row + chr(10))
    snapshot(path)
    _atomic_write(path, b"\xef\xbb\xbf" + "".join(lines).encode("utf-8"))
    return {"ok": True, "from": frm, "to": to, "type": adj_type,
            "msg": "已新增连接 %d ↔ %d（%s）" % (frm, to, adj_type or "sea")}




















def orphan_tags(root=None):
    """州里引用了 owner，但国家表（COUNTRIES）里不存在的 tag。

    mod 换了国家表但没跟着改 history/states 时会出现这种不一致；
    游戏里这些省会指向不存在的国家，政治图上没法给它们上色。"""
    root = _map_pick(root)
    by_tag = {}
    for sid, st in (STATES.items() if isinstance(STATES, dict) else []):
        ow = (st.get("owner") or "").strip().upper()
        if not ow or ow in COUNTRIES:
            continue
        rec = by_tag.setdefault(ow, {"tag": ow, "states": 0, "provinces": 0,
                                     "sample_states": [], "files": []})
        rec["states"] += 1
        rec["provinces"] += len(st.get("provinces") or [])
        if len(rec["sample_states"]) < 6:
            rec["sample_states"].append(st.get("id"))
        f = st.get("file") or ""
        if f and f not in rec["files"] and len(rec["files"]) < 4:
            rec["files"].append(f)

    items = sorted(by_tag.values(), key=lambda x: -x["provinces"])
    used = set()
    for st in (STATES.values() if isinstance(STATES, dict) else []):
        ow = (st.get("owner") or "").strip().upper()
        if ow:
            used.add(ow)
    unused = sorted(t for t in COUNTRIES if t not in used)
    total_states = sum(x["states"] for x in items)
    total_prov = sum(x["provinces"] for x in items)
    msg = ("%d 个 tag 在国家表里不存在，涉及 %d 个州 / %d 个省" % (
        len(items), total_states, total_prov)) if items else \
        "没有孤儿 tag，州引用的 owner 都在国家表里"
    return {"ok": True, "count": len(items),
            "total_states": total_states, "total_provinces": total_prov,
            "states_all": len(STATES), "countries_all": len(COUNTRIES),
            "items": items, "unused_tags": unused[:40],
            "unused_count": len(unused), "msg": msg}






def _supply_dir_write(root):
    """补给区写到哪：按 replace_path 算真实写入层"""
    root = _map_pick(root)
    _calc = root if root else (ROOTS[-1] if ROOTS else "")
    base, _why = write_base(_calc, "map/supplyareas")
    if not base:
        return None, None
    d = _out_path(base, os.path.join("map", "supplyareas")) if _state.output_mode() else \
        os.path.join(base, "map", "supplyareas")
    os.makedirs(d, exist_ok=True)
    _write_layer_hint["supplyareas"] = _why
    return base, d


def supply_area_save(sid, value=None, states=None, name=None, root=None):
    """新建或修改一个补给区。

    sid 已存在就改（value / states / name），不存在就新建文件。
    写法沿用 HOI4 的 supply_area={ id name value states }。"""
    root = _map_pick(root)
    try:
        sid = int(sid)
    except Exception:
        return {"ok": False, "msg": "补给区 id 不合法"}
    base, d = _supply_dir_write(root)
    if not d:
        return {"ok": False, "msg": "找不到可写的 mod 目录"}

    # 找现有文件
    exist_path = None
    for _b, _d in _layer_dirs("map/supplyareas", root):
        for fn in sorted(os.listdir(_d)):
            if not fn.endswith(".txt"):
                continue
            p = os.path.join(_d, fn)
            try:
                t = strip_comments(io.open(p, encoding="utf-8-sig", errors="replace").read())
            except Exception:
                continue
            for m in re.finditer(r'supply_area\s*=\s*\{', t):
                b = t.find("{", m.end() - 1)
                e = brace_match(t, b)
                if e <= b:
                    continue
                body = t[b + 1:e - 1]
                mm = re.search(r'(?m)^\s*id\s*=\s*(\d+)', body)
                if mm and int(mm.group(1)) == sid:
                    exist_path = p
                    break
            if exist_path:
                break
        if exist_path:
            break

    # 现有值（改的时候保留没传的字段）
    cur_value, cur_states, cur_name = 12, [], "SUPPLYAREA_%d" % sid
    if exist_path:
        try:
            t = strip_comments(io.open(exist_path, encoding="utf-8-sig", errors="replace").read())
            b = t.find("{", t.find("supply_area"))
            e = brace_match(t, b)
            body = t[b + 1:e - 1]
            mv = re.search(r'(?m)^\s*value\s*=\s*(\d+)', body)
            if mv:
                cur_value = int(mv.group(1))
            mn = re.search(r'(?m)^\s*name\s*=\s*"([^"]*)"', body)
            if mn:
                cur_name = mn.group(1)
            ms = re.search(r'states\s*=\s*\{([^}]*)\}', body)
            if ms:
                cur_states = [int(x) for x in re.findall(r'\d+', ms.group(1))]
        except Exception:
            pass

    if value not in (None, ""):
        try:
            cur_value = int(value)
        except Exception:
            return {"ok": False, "msg": "value 必须是整数"}
    if name:
        cur_name = str(name)
    if states:
        try:
            cur_states = sorted({int(x) for x in states})
        except Exception:
            return {"ok": False, "msg": "states 列表不合法"}
    if not cur_states:
        return {"ok": False, "msg": "至少要给一个州"}

    # 州必须存在
    bad = [x for x in cur_states if str(x) not in STATES and x not in STATES]
    if bad:
        return {"ok": False, "msg": "这些州不存在：%s" % bad[:5]}

    fn = os.path.basename(exist_path) if exist_path else ("%d-SupplyArea.txt" % sid)
    path = os.path.join(d, fn)
    inner = "\n" + "".join("\t\t%d\n" % x for x in cur_states) + "\t"
    body = ('supply_area={\n\tid=%d\n\tname="%s"\n\tvalue=%d\n\tstates={%s}\n}\n'
            % (sid, cur_name, cur_value, inner))
    _atomic_write(path, _bom_for(path) + body.encode("utf-8"))
    reload_data()
    return {"ok": True, "id": sid, "file": os.path.basename(path),
            "value": cur_value, "states": cur_states,
            "created": not bool(exist_path),
            "msg": "%s补给区 %d（value=%d，%d 个州）" % (
                "已新建" if not exist_path else "已更新", sid, cur_value, len(cur_states))}


def supply_area_delete(sid, root=None):
    """删除一个补给区：只从当前 mod 层的文件里摘，原版不动"""
    root = _map_pick(root)
    try:
        sid = int(sid)
    except Exception:
        return {"ok": False, "msg": "id 不合法"}
    base, d = _supply_dir_write(root)
    if not d:
        return {"ok": False, "msg": "找不到可写的 mod 目录"}
    # 只处理自己目录里的文件
    for fn in sorted(os.listdir(d)):
        if not fn.endswith(".txt"):
            continue
        p = os.path.join(d, fn)
        try:
            t = io.open(p, encoding="utf-8-sig", errors="replace").read()
        except Exception:
            continue
        ct = strip_comments(t)
        found = False
        for m in re.finditer(r'supply_area\s*=\s*\{', ct):
            b = ct.find("{", m.end() - 1)
            e = brace_match(ct, b)
            if e <= b:
                continue
            mm = re.search(r'(?m)^\s*id\s*=\s*(\d+)', ct[b + 1:e - 1])
            if mm and int(mm.group(1)) == sid:
                found = True
                break
        if not found:
            continue
        try:
            snapshot(p)
            os.remove(p)
        except Exception as ex:
            return {"ok": False, "msg": "删除失败：%s" % ex}
        reload_data()
        return {"ok": True, "id": sid, "msg": "已删除补给区 %d（%s）" % (sid, fn)}
    return {"ok": False,
            "msg": "补给区 %d 不在当前 mod 层里（可能来自原版或父 mod，只读）" % sid}









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


# v0.86 铁路等级静态检查
def _rail_over_level(root, max_level=5):
    """返回 level 超过上限的铁路条数（HOI4 默认上限 5，日志里会刷 Railway level > MAX）"""
    for base in (root, GAME):
        p = os.path.join(base or "", "map", "railways.txt")
        if not os.path.exists(p):
            continue
        try:
            text = strip_comments(io.open(p, encoding="utf-8", errors="replace").read())
        except Exception:
            return 0, 0
        over = 0
        total = 0
        # 格式一：railway = { level = N provinces = { ... } }
        for m in re.finditer(r'railway\s*=\s*\{', text):
            b = text.find('{', m.end() - 1)
            e = brace_match(text, b)
            if e <= b:
                continue
            total += 1
            lv = re.search(r'level\s*=\s*(\d+)', text[b + 1:e - 1])
            if lv and int(lv.group(1)) > max_level:
                over += 1
        # 格式二（MUVLUV 等老 mod）：每行 "level count p1 p2 ..."
        if not total:
            for ln in text.splitlines():
                parts = ln.split()
                if len(parts) >= 3 and parts[0].isdigit() and parts[1].isdigit():
                    total += 1
                    if int(parts[0]) > max_level:
                        over += 1
        return over, total
    return 0, 0


# v0.87 日志快照（防止 error.log 被下一次启动覆盖）
LOG_SNAP_DIR = os.path.join(WORK, "logs")
LOG_KEEP = 10


def _log_snapshot(src):
    """把当前 error.log 复制一份带时间戳的快照，返回 (快照路径, 快照时间, 是否新建)"""
    try:
        os.makedirs(LOG_SNAP_DIR, exist_ok=True)
        st = os.stat(src)
        stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(st.st_mtime))
        dst = os.path.join(LOG_SNAP_DIR, "error_%s.log" % stamp)
        created = not os.path.exists(dst)
        if created:
            shutil.copy2(src, dst)
            # 只保留最近 N 份
            snaps = sorted(f for f in os.listdir(LOG_SNAP_DIR) if f.startswith("error_") and f.endswith(".log"))
            for old in snaps[:-LOG_KEEP]:
                try:
                    os.remove(os.path.join(LOG_SNAP_DIR, old))
                except Exception:
                    pass
        return dst, stamp, created
    except Exception:
        return src, "", False


def read_error_log(path=None, limit_files=40):
    """解析 error.log：按类别聚合，给出计数、样例与涉及文件"""
    cand = [path] if path else _log_paths()
    if not cand or not os.path.exists(cand[0]):
        return {"ok": False, "msg": "没找到 error.log（先运行一次游戏）"}
    p = cand[0]
    snap, stamp, created = _log_snapshot(p)
    try:
        text = io.open(snap if os.path.exists(snap) else p, encoding="utf-8", errors="replace").read()
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
        fm = re.search(r'file:\s*"?([^"\s]+)"?(?:\s+line:\s*(\d+))?', msg)
        if fm:
            f = fm.group(1).replace("\\", "/").lstrip("./")
            owner = "other"
            try:
                root0 = ROOTS[0] if ROOTS else GAME
                if os.path.exists(os.path.join(root0 or "", f)):
                    owner = "mine"
                elif os.path.exists(os.path.join(GAME or "", f)):
                    owner = "vanilla"
            except Exception:
                pass
            b.setdefault("owners", {})
            b["owners"][owner] = b["owners"].get(owner, 0) + 1
            if owner == "mine":
                b["files"][f] = b["files"].get(f, 0) + 1
                files[f] = files.get(f, 0) + 1
    items = []
    for key, b in sorted(buckets.items(), key=lambda kv: -kv[1]["count"]):
        top_files = sorted(b["files"].items(), key=lambda kv: -kv[1])[:4]
        own = b.get("owners") or {}
        mine_n = own.get("mine", 0)
        van_n = own.get("vanilla", 0)
        detail = "；".join("%s ×%d" % (f, n) for f, n in top_files) or "（日志未给出文件名）"
        if own:
            detail += "　[本 mod %d / 原版 %d / 其它 %d]" % (mine_n, van_n, own.get("other", 0))
        lvl = b["level"]
        if lvl == "error" and own and mine_n == 0:
            lvl = "info"   # 报错不来自本 mod，降级
        items.append({"level": lvl, "kind": "log",
                      "title": "%s（%d 条）" % (b["title"], b["count"]),
                      "detail": detail + "　建议：" + b["hint"],
                      "samples": b["samples"]})
    return {"ok": True, "path": p, "snapshot": snap, "snapshot_stamp": stamp,
            "snapshot_created": created, "lines": len(lines), "unmatched": unmatched,
            "items": items, "files": sorted(files.items(), key=lambda kv: -kv[1])[:limit_files]}


def lint_project(limit=1500):



    """跨系统引用检查：树↔国家、历史↔树、州↔国家、事件↔事件、本地化"""
    items = []

    def add(level, kind, title, detail="", goto=None):
        if len(items) < limit:
            items.append({"level": level, "kind": kind, "title": title,
                          "detail": detail, "goto": goto or {}})

    for tid, t in TREES.items():
        raw = t.get("country_raw") or ""
        tags = re.findall(r'tag\s*=\s*([A-Z0-9_]{2,8})', raw)
        if raw.strip() and not tags:
            add("info", "tree", "国策树 %s 的 country 块里没有 tag（按条件或默认挂载）" % tid, raw[:120],
                {"type": "tree", "id": tid})
        for tag in sorted(set(tags)):
            if tag not in COUNTRIES:
                add("error", "tree", "国策树 %s 挂了不存在的国家 %s" % (tid, tag), "",
                    {"type": "tree", "id": tid})

    for tag, c in COUNTRIES.items():
        if c.get("orphan_history"):
            add("error", "country", "%s 有 history 文件但没有 country_tags 登记" % tag,
                c.get("history_file", ""), {"type": "country", "id": tag})
        for t in c.get("focus_trees", []):
            if t not in TREES:
                add("error", "country", "%s 的 load_focus_tree 引用了不存在的树 %s" % (tag, t),
                    c.get("history_file", ""), {"type": "country", "id": tag})
        for i in c.get("ideas", []):
            if i not in IDEAS:
                add("warn", "idea", "%s 的 add_ideas 引用了不存在的国家精神 %s" % (tag, i),
                    c.get("history_file", ""), {"type": "country", "id": tag})

    for sid, s in STATES.items():
        o = s.get("owner")
        if o and o not in COUNTRIES:
            add("error", "state", "州 %s 的 owner = %s 不是有效 tag" % (sid, o), s.get("file", ""),
                {"type": "state", "id": str(sid)})
        for t in s.get("cores", []):
            if t not in COUNTRIES:
                add("error", "state", "州 %s 的 add_core_of = %s 不是有效 tag" % (sid, t), s.get("file", ""),
                    {"type": "state", "id": str(sid)})
        if not s.get("owner"):
            add("info", "state", "州 %s 没有设置 owner" % sid, s.get("file", ""),
                {"type": "state", "id": str(sid)})

    for eid, ev in EVENTS.items():
        raw = ev.get("raw", "")
        for m in re.finditer(r'(?:country_event|news_event|state_event)\s*=\s*\{\s*id\s*=\s*([A-Za-z0-9_.\-]+)', raw):
            ref = m.group(1)
            if ref not in EVENTS:
                add("warn", "event", "事件 %s 触发了不存在的事件 %s" % (eid, ref), ev.get("file", ""),
                    {"type": "event", "id": eid})

    # v0.59：国策里的引用
    try:
        refs = _focus_refs()
    except Exception as e:
        refs = {"ideas": [], "events": []}
        print("focus refs fail:", e)
    for r in refs["ideas"]:
        if r["id"] not in IDEAS:
            add("warn", "focus", "国策 %s 的 %s 引用了不存在的国家精神 %s" % (r["focus"], r["where"], r["id"]),
                r["file"], {"type": "tree", "id": r["tree"]})
    for r in refs["events"]:
        if r["id"] not in EVENTS:
            add("warn", "focus", "国策 %s 触发了不存在的事件 %s" % (r["focus"], r["id"]),
                r["file"], {"type": "tree", "id": r["tree"]})

    # v0.97 科技前置引用闭环
    try:
        _KW = {"focus", "OR", "AND", "NOT", "has_dlc", "has_global_flag", "has_country_flag",
               "has_tech", "if", "else", "limit", "tooltip", "custom_effect_tooltip",
               "has_start_date", "date", "original_tag", "tag"}
        _dangling = []
        for _tid, _t in TECHS.items():
            for _p in (_t.get("prereq") or []):
                if _p in _KW or _p in TECHS:
                    continue
                _dangling.append((_tid, _p))
        if _dangling:
            add("warn", "tech", "%d 处科技前置引用了不存在的科技" % len(_dangling),
                "例如 " + "、".join("%s → %s" % (a, b) for a, b in _dangling[:6]) +
                "；可能是科技改名或删掉后没清 prerequisites", "",
                {"type": "log", "id": ""})
    except Exception as e:
        print("科技前置检查失败:", e)

    # v0.96 编码规范（BOM）
    try:
        _bom, _yml_n, _txt_n, _bom_total = _bom_issues(ROOTS[0] if ROOTS else GAME)
        if _bom_total:
            miss = sum(1 for k, _ in _bom if k == "缺 BOM")
            extra = _bom_total - miss
            parts = []
            if miss:
                parts.append("%d 个 .yml 缺 BOM（游戏会读不到本地化）" % miss)
            if extra:
                parts.append("%d 个 .txt 带多余 BOM" % extra)
            add("warn", "bom", "编码规范问题：" + "；".join(parts),
                "抽查 %d 个 yml / %d 个 txt；示例：" % (_yml_n, _txt_n) +
                "、".join("%s %s" % (k, v) for k, v in _bom[:5]), "", {"type": "log", "id": ""})
    except Exception as e:
        print("BOM 检查失败:", e)

    # v0.86 铁路等级（静态，不必跑游戏）
    try:
        _over, _total = _rail_over_level(ROOTS[0] if ROOTS else GAME)
        if _over:
            add("warn", "rail", "铁路有 %d 条等级超过上限（共 %d 条）" % (_over, _total),
                "游戏日志会刷 Railway level > MAX_RAILWAY_LEVEL，把 level 降到 5 以内", "",
                {"type": "log", "id": ""})
    except Exception as e:
        print("铁路检查失败:", e)

    # v0.86 游戏日志
    try:
        _log = read_error_log()
        if _log.get("ok"):
            for it in _log.get("items", []):
                add(it["level"], "log", it["title"], it["detail"], {"type": "log", "id": ""})
    except Exception as e:
        print("error.log 读取失败:", e)

    # v0.66 全局 flag 配对
    try:
        sets, haves = _flag_usage()
    except Exception as e:
        sets, haves = {}, {}
        print("flag scan fail:", e)
    for f, where in list(haves.items())[:120]:
        if f not in sets:
            add("warn", "flag", "全局 flag %s 只被读取（%s），没有任何 set_global_flag" % (f, where), "",
                {"type": "tree", "id": ""})
    for f, where in list(sets.items())[:120]:
        if f not in haves:
            add("info", "flag", "全局 flag %s 只被设置（%s），目前没人读取" % (f, where), "",
                {"type": "tree", "id": ""})

    for it in missing_loc()[:limit]:
        add("warn", "loc", "缺本地化：%s" % it.get("key", ""), it.get("file", ""),
            {"type": "loc", "id": it.get("key", "")})

    order = {"error": 0, "warn": 1, "info": 2}
    items.sort(key=lambda x: (order.get(x["level"], 3), x["kind"]))
    stats = {"error": 0, "warn": 0, "info": 0}
    for it in items:
        stats[it["level"]] = stats.get(it["level"], 0) + 1
    return {"items": items, "stats": stats, "truncated": len(items) >= limit,
            "scope": {"trees": len(TREES), "countries": len(COUNTRIES), "states": len(STATES),
                      "ideas": len(IDEAS), "events": len(EVENTS), "techs": len(TECHS)}}


def item_raw(kind, iid):
    m = {"idea": IDEAS, "equip": EQUIPMENTS, "tech": TECHS, "event": EVENTS}.get(kind) or {}
    return {"raw": m.get(iid, {}).get("raw", "")}


def expand_shared_trees():
    byid = {}
    for n in SHARED_FOCUSES:
        byid[n["id"]] = n
    for t in TREES.values():
        ids = {f["id"] for f in t.get("focuses", [])}
        for sid in t.get("shared", []):
            if sid in byid and sid not in ids:
                node = dict(byid[sid])
                node["shared"] = True
                t["focuses"].append(node)
                ids.add(sid)

def find_usages(iid):
    out = []
    pat = re.compile(r'(?<![A-Za-z0-9_])%s(?![A-Za-z0-9_])' % re.escape(iid or ""))
    for tid in TREE_ORDER:
        t = TREES.get(tid)
        if not t:
            continue
        for f in t.get("focuses", []):
            txt = (f.get("effect") or "") + "\n" + (f.get("select_effect") or "")
            if pat.search(txt):
                out.append({"type": "国策", "id": f["id"], "where": tid, "file": t["file"]})
    for eid, e in EVENTS.items():
        if pat.search(e.get("raw", "")):
            out.append({"type": "事件", "id": eid, "where": eid, "file": e.get("file", "")})
    for tid, t in TECHS.items():
        if iid in (t.get("prereq") or []) or iid in (t.get("leads") or []):
            out.append({"type": "科技", "id": tid, "where": t.get("path", ""), "file": t.get("file", "")})
    return out[:500]

def load_orgs(root):
    # 整条链（父 → 子）；以前只有 [root, GAME]，中间层的 MIO 全丢
    bases = _chain_layers(root)
    if GAME and os.path.abspath(GAME) not in bases:
        bases.append(os.path.abspath(GAME))
    n = 0
    for base in bases:
        d = os.path.join(base, "common", "military_industrial_organization", "organizations")
        if not os.path.isdir(d):
            continue
        for fn in sorted(f for f in os.listdir(d) if f.endswith(".txt")):
            text = strip_comments(io.open(os.path.join(d, fn), encoding="utf-8", errors="replace").read())
            for k, v, b in top_items(text):
                if b and re.match(r'^[A-Za-z0-9_]+$', k):
                    ORGS[k] = LOC.get(k, k)
                    n += 1
    return n

def load_modules(root):
    # 整条链（父 → 子）；以前只有 [root, GAME]，中间层的装备模块全丢
    bases = _chain_layers(root)
    if GAME and os.path.abspath(GAME) not in bases:
        bases.append(os.path.abspath(GAME))
    n = 0
    for base_root in bases:
        d = os.path.join(base_root, "common", "units", "equipment", "modules")
        if not os.path.isdir(d):
            continue
        for fn in sorted(f for f in os.listdir(d) if f.endswith(".txt")):
            text = strip_comments(io.open(os.path.join(d, fn), encoding="utf-8", errors="replace").read())
            for s, e, body in find_blocks(text, "equipment_modules"):
                for k, v, b in top_items(body):
                    if not b or k in ("limit", "template"):
                        continue
                    if "category" not in v:
                        continue
                    cm = re.search(r'(?m)^\s*category\s*=\s*"?([A-Za-z0-9_]+)"?', v)
                    if not cm:
                        continue
                    gm = re.search(r'(?m)^\s*gfx\s*=\s*"?([A-Za-z0-9_]+)"?', v)
                    stats = {}
                    for am in re.finditer(r'add_stats\s*=\s*\{', v):
                        ab = v.find('{', am.start())
                        ae = brace_match(v, ab)
                        inner = v[ab + 1:ae - 1]
                        for sm in re.finditer(r'(?m)^\s*([A-Za-z0-9_]+)\s*=\s*(-?[0-9.]+)', inner):
                            try:
                                stats[sm.group(1)] = float(sm.group(2))
                            except Exception:
                                pass
                    MODULES[k] = {"id": k, "category": cm.group(1),
                                  "gfx": gm.group(1) if gm else "",
                                  "stats": stats,
                                  "file": os.path.join("common", "units", "equipment", "modules", fn)}
                    n += 1
    return n

def _eq_view(e):
    d = {k: v for k, v in e.items() if k != "raw"}
    d["slots"] = [dict(s, name=(LOC.get("EQ_MOD_SLOT_" + s["slot"] + "_TITLE")
                                 or LOC.get(s["slot"], s["slot"]))) for s in e.get("slots", [])]
    return d

def _readonly_flag(p):
    """侧栏的「只读」标记：原版目录 + 创意工坊目录。

    只判 is_under_game 会把 workshop 的 mod 显示成可写 —— 实际写进去会被 Steam
    校验改回去，所以必须标只读。真正的写保护在 _is_readonly_root 里（同一套判断）。
    """
    try:
        return bool(_is_readonly_root(p))
    except Exception:
        return is_under_game(p)


# ---------- v1.24.0 层间同名文件统计 ----------
_SHADOW_CACHE = {"k": None, "v": {}}
_SHADOW_DIRS = ("common/national_focus", "common/ideas", "common/technologies",
                "common/characters", "events", "history/states", "history/countries")


def layer_shadow_stats():
    """每一层「压住」了下面哪些文件。

    返回 {层的绝对路径: [被它覆盖的相对路径, ...]}。
    HOI4 的规则是同名文件后加载的赢，所以从链尾（最上层）往下扫，
    第二次见到的同名文件就是被覆盖的。
    """
    layers = mod_layers(None) or []
    key = (tuple(os.path.abspath(r) for r in layers),
           bool(OPTIONS.get("follow_deps", True)),
           bool(OPTIONS.get("follow_launcher", False)))
    if _SHADOW_CACHE.get("k") == key:
        return _SHADOW_CACHE["v"]
    seen = {}
    shadow = {}
    for r in reversed(layers):
        try:
            ab = os.path.abspath(r)
        except Exception:
            continue
        for rel in _SHADOW_DIRS:
            d = os.path.join(r, rel.replace("/", os.sep))
            if not os.path.isdir(d):
                continue
            try:
                names = sorted(os.listdir(d))
            except Exception:
                continue
            for fn in names:
                if not fn.lower().endswith(".txt"):
                    continue
                key = rel + "/" + fn
                if key in seen:
                    top = seen[key]
                    if top != ab:
                        shadow.setdefault(top, []).append(key)
                else:
                    seen[key] = ab
    # 只留前 40 条，避免侧栏 hover 里堆几百行
    out = {k: sorted(v)[:40] for k, v in shadow.items()}
    _SHADOW_CACHE["k"] = key
    _SHADOW_CACHE["v"] = out
    return out


def _deps_hint():
    """关掉「带上依赖」时，如果当前 mod 声明了依赖，给一句提醒。

    用户最常见的情况：只加载了子 mod，看到的却是残缺的原版数据，
    却不知道是因为它的父 mod 没被带进来。
    """
    if not ROOTS or OPTIONS.get("follow_deps", True):
        return ""
    try:
        deps = _mod_descriptor(ROOTS[-1]).get("deps") or []
    except Exception:
        deps = []
    if not deps:
        return ""
    return ("这个 mod 声明了 %d 个依赖（%s），但「带上依赖的 mod」没开，"
            "现在看到的数据可能不完整" % (len(deps), "、".join(deps[:3])))


def _payload_layers():
    """给前端的完整叠加链：谁被真正读到了、以及**为什么在这**。

    reason 四种：
      game      游戏本体（只读，不可卸载）
      manual    用户点「添加 mod」显式加载的
      dep       因为 descriptor 的 dependencies 被带上来的
      launcher  因为「同时读启动器已启用列表」被带上来的
    """
    try:
        if not ROOTS:
            return []
        manual = set()
        for r in ROOTS:
            try:
                manual.add(os.path.abspath(r))
            except Exception:
                pass
        root = ROOTS[-1]
        try:
            ab_root = os.path.abspath(root)
        except Exception:
            ab_root = ""
        dep_set = set()
        if OPTIONS.get("follow_deps", True):
            # 自己 + 其他显式加载的 root 的依赖祖先都算 dep
            for _r in (ROOTS or []):
                try:
                    dep_set |= {os.path.abspath(x) for x in _mod_dep_chain(_r)[:-1]}
                except Exception:
                    pass
        launch_set = set()
        if OPTIONS.get("follow_launcher", False):
            try:
                order = [os.path.abspath(x) for x in _enabled_mod_order()]
                # 只算排在自己前面的；自己不在启动器里就整套都算底
                launch_set = (set(order[:order.index(ab_root)])
                              if ab_root in order else set(order))
            except Exception:
                launch_set = set()
        out = []
        for r in mod_layers(root):
            try:
                ab = os.path.abspath(r)
            except Exception:
                continue
            if GAME and ab == os.path.abspath(GAME):
                reason = "game"
            elif ab in manual:
                reason = "manual"
            elif ab in dep_set:
                reason = "dep"
            elif ab in launch_set:
                reason = "launcher"
            else:
                reason = "auto"
            out.append({"name": _mod_display_name(ab),
                        "path": ab,
                        "readonly": _readonly_flag(ab),
                        # game=True 是游戏本体那层。前端靠它排除「自动带上」里的原版——
                        # 不能用 readonly 排除，创意工坊目录也是 readonly，
                        # 那样父 mod（CN/CNsub）会被一起滤掉。
                        "game": bool(GAME) and ab == os.path.abspath(GAME),
                        "auto": ab not in manual,
                        "reason": reason})
        return out
    except Exception:
        return []


def data_payload():
    expand_shared_trees()
    trees = []
    for tid in TREE_ORDER:
        t = TREES[tid]
        resolve_positions(t)
        for f in t["focuses"]:
            f["name"] = LOC.get(f["id"], f["id"])
            f.pop("desc", None)
            f.pop("effect", None)
            f.pop("select_effect", None)
            f.pop("iconPng", None)
        trees.append({"id": tid, "file": t["file"], "source": t["source"],
                      "root": t.get("root", ""),
                      "default": t.get("default", ""), "country_raw": t.get("country_raw", ""),
                      "focuses": t["focuses"], "shared": t["shared"],
                      "analysis": analyze(t)})
    if SHARED_FOCUSES:
        trees.append({"id": "shared_focuses", "file": "", "source": "shared",
                      "root": "",
                      "default": "", "country_raw": "",
                      "focuses": SHARED_FOCUSES, "shared": [],
                      "analysis": analyze({"focuses": SHARED_FOCUSES})})
    return {"trees": trees,
            "ideas": [{k: v for k, v in IDEAS[k].items() if k != "raw"} for k in sorted(IDEAS)],
            "equipment": [_eq_view(EQUIPMENTS[k]) for k in sorted(EQUIPMENTS)],
            "techs": [{k: v for k, v in TECHS[k].items() if k != "raw"} for k in sorted(TECHS)],
            "events": [{k: v for k, v in EVENTS[k].items() if k != "raw"} for k in sorted(EVENTS)],
            "modules": [dict(m, name=LOC.get(m["id"], m["id"])) for m in (MODULES[k] for k in sorted(MODULES))],
            "orgs": [{"id": k, "name": LOC.get(k, k)} for k in sorted(ORGS)],
            "mascots": MASCOTS,
            "mod_home": mod_home(),
            "roots": [{"name": os.path.basename(r.rstrip("\\/")) or r, "path": r,
                       "readonly": _readonly_flag(r),
                       "auto": False} for r in ROOTS],
            # v1.23.45：完整叠加链。roots 只有用户手动加的，layers 里才是真正读到的所有层。
            # auto=True 表示「自动带进来的」（启动器启用 / dependencies 补的），
            # 前端把它淡一点显示，用户才知道数据是从哪来的。
            "layers": _payload_layers(),
            "available_mods": discover_mods(),
            "game_version": detect_game_version(),
            "layer_shadow": layer_shadow_stats(),
            "deps_hint": _deps_hint()}


def layer_chain_payload(query="", kind="interacted", dir_filter="",
                        layer_filter="", replace_filter="", limit=200, refresh=False):
    """7-2 叠加链可视化：汇总链顺序、文件覆盖去向与 replace_path 屏蔽明细。"""
    pl = _payload_layers()
    raw_layers = [x.get("path") for x in pl if x.get("path")]
    if not raw_layers:
        raw_layers = mod_layers(None) or ([GAME] if GAME and os.path.isdir(GAME) else [])
    res = analyze_layer_chain(
        layers=raw_layers,
        query=query,
        kind=kind,
        dir_filter=dir_filter,
        layer_filter=layer_filter,
        replace_filter=replace_filter,
        limit=limit,
        refresh=refresh,
    )
    pl_by_path = {os.path.normcase(os.path.abspath(x["path"])): x for x in pl if x.get("path")}
    for lm in res.get("layers") or []:
        ab = os.path.normcase(os.path.abspath(lm.get("path") or ""))
        extra = pl_by_path.get(ab)
        if extra:
            lm["reason"] = extra.get("reason", "auto")
            lm["readonly"] = bool(extra.get("readonly"))
            lm["game"] = bool(extra.get("game"))
            lm["auto"] = bool(extra.get("auto"))
        else:
            g = bool(GAME) and ab == os.path.normcase(os.path.abspath(GAME))
            lm["reason"] = "game" if g else "auto"
            lm["readonly"] = bool(_readonly_flag(lm.get("path") or ""))
            lm["game"] = g
            lm["auto"] = not g
    return res


def object_diff_payload(cat="all", status="interacted", query="",
                        layer_filter="", obj_key="", limit=200, refresh=False):
    """7-3 对象级覆盖对比：国策 / 事件 / 国家精神跨层定义与实机冲突分析。"""
    pl = _payload_layers()
    raw_layers = [x.get("path") for x in pl if x.get("path")]
    if not raw_layers:
        raw_layers = mod_layers(None) or ([GAME] if GAME and os.path.isdir(GAME) else [])
    return analyze_objects(
        layers=raw_layers,
        cat=cat,
        status=status,
        query=query,
        layer_filter=layer_filter,
        obj_key=obj_key,
        limit=limit,
        refresh=refresh,
    )


def game_verify_status(game_dir="", docs_dir=""):
    """7-4 进游戏检查：返回环境预检、首次确认状态、当前进度与最近报错报告。"""
    pl = _payload_layers()
    raw_layers = [x.get("path") for x in pl if x.get("path")]
    if not raw_layers:
        raw_layers = mod_layers(None) or []
    return get_verify_status(layers=raw_layers, game_dir=game_dir or GAME or "", docs_dir=docs_dir)


def game_verify_start(body=None):
    """7-4 启动进游戏检查（未确认前拦回 need_confirm=True，避免静默改 dlc_load.json）。"""
    b = body or {}
    pl = _payload_layers()
    raw_layers = [x.get("path") for x in pl if x.get("path")]
    if not raw_layers:
        raw_layers = mod_layers(None) or []
    return start_game_verify(
        layers=raw_layers,
        confirm=bool(b.get("confirm", False)),
        baseline_mode=(b.get("baseline_mode") or "parents"),
        reuse_baseline=bool(b.get("reuse_baseline", True)),
        game_dir=b.get("game_dir") or GAME or "",
        docs_dir=b.get("docs_dir") or "",
    )


def game_verify_cancel():
    return cancel_game_verify()


def publish_preview(body=None):
    """7-5 打包发布预检：解析目标 mod 元数据、依赖校验、剔除列表与 BOM 修正。"""
    b = body or {}
    pl = _payload_layers()
    raw_layers = [x.get("path") for x in pl if x.get("path")]
    if not raw_layers:
        raw_layers = mod_layers(None) or list(ROOTS or [])
    return preview_publish(
        mod_root=b.get("mod_root") or "",
        layers=raw_layers,
        out_dir=b.get("out_dir") or "",
        folder_id=b.get("folder_id") or "",
        docs_dir=b.get("docs_dir") or "",
        overrides=b.get("overrides"),
    )


def publish_export(body=None):
    """7-5 打包发布导出：输出工坊就绪目录、可选启动器 .mod 与 .zip 压缩包。"""
    b = body or {}
    pl = _payload_layers()
    raw_layers = [x.get("path") for x in pl if x.get("path")]
    if not raw_layers:
        raw_layers = mod_layers(None) or list(ROOTS or [])
    return export_publish(
        mod_root=b.get("mod_root") or "",
        layers=raw_layers,
        out_dir=b.get("out_dir") or "",
        folder_id=b.get("folder_id") or "",
        docs_dir=b.get("docs_dir") or "",
        register_launcher=bool(b.get("register_launcher", True)),
        overwrite_launcher_mod=bool(b.get("overwrite_launcher_mod", False)),
        also_zip=bool(b.get("also_zip", False)),
        overrides=b.get("overrides"),
    )








def export_zip():
    if not CHANGED:
        return None, "没有改动"
    ts = time.strftime("%Y%m%d_%H%M%S")
    out = os.path.join(WORK, "focus_editor_exports", "mvlv_focus_patch_%s.zip" % ts)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for path, rel in CHANGED.items():
            z.write(path, rel)
        z.writestr("README_覆盖说明.txt",
                   "把压缩包内文件按相同相对路径覆盖到对应 mod 根目录即可。\n"
                   "本包只包含本次编辑的国策文件。\n"
                   "覆盖前建议备份原文件。\n")
    return out, "已导出"

# ---------------- 本地化 / 树级操作 ----------------



def add_tree(root, tree_id):
    if not root:
        return False, "参数不完整：缺少 root"
    if not tree_id:
        return False, "参数不完整：缺少树 id"
    d = os.path.join(root, "common", "national_focus")
    os.makedirs(d, exist_ok=True)
    fn = unique_editor_filename(root, "common/national_focus", "zz_focus_editor_trees.txt")
    path = os.path.join(d, fn)
    text = io.open(path, encoding="utf-8", errors="replace", newline="").read() if os.path.exists(path) else ""
    if re.search(r'(?m)^\s*id\s*=\s*"?%s"?' % re.escape(tree_id), text):
        return False, "树已存在: " + tree_id
    block = "\nfocus_tree = {\n\tid = %s\n\n\tcountry = {\n\t\tfactor = 0\n\t}\n}\n" % tree_id
    backup(path)
    snapshot(path)
    io.open(path, "w", encoding="utf-8", newline="").write(text + block)
    CHANGED[path] = os.path.join("common", "national_focus", fn)
    reload_data()
    return True, "已新建树 " + tree_id

def delete_tree(root, file, tree_id):
    if not root or not file:
        return False, "参数不完整：缺少 root 或 file"
    path = os.path.join(root, file)
    if not os.path.isfile(path):
        return False, "找不到文件：%s" % file
    text = io.open(path, encoding="utf-8", errors="replace", newline="").read()
    for m in re.finditer(r'(?m)^\s*focus_tree\s*=\s*\{', text):
        b = text.find('{', m.end() - 1)
        e = brace_match(text, b)
        body = text[b + 1:e - 1]
        mid = re.search(r'(?m)^\s*id\s*=\s*"?([A-Za-z0-9_]+)"?', body)
        if mid and mid.group(1) == tree_id:
            newtext = text[:m.start()] + text[e:]
            backup(path)
            snapshot(path)
            io.open(path, "w", encoding="utf-8", newline="").write(newtext)
            CHANGED[path] = file
            reload_data()
            return True, "已删除树 " + tree_id
    return False, "未找到树 " + tree_id


# ---------------- 树级设置 ----------------
def save_tree(root, rel, tree_id, default=None, country_raw=None):
    path = os.path.join(root, rel)
    text = io.open(path, encoding="utf-8", errors="replace", newline="").read()
    for m in re.finditer(r'(?m)^\s*focus_tree\s*=\s*\{', text):
        b = text.find('{', m.start())
        e = brace_match(text, b)
        block = text[b + 1:e - 1]
        if re.search(r'(?m)^\s*id\s*=\s*"?%s"?' % re.escape(tree_id), block):
            nb = block
            if default:
                nb = set_scalar(nb, "default", default)
            if country_raw:
                if not braces_balanced(country_raw):
                    return False, "country 块花括号不匹配"
                m2 = re.search(r'(?m)^[ \t]*country\s*=\s*\{', nb)
                if m2:
                    br = nb.find('{', m2.start())
                    en = brace_match(nb, br)
                    nb = nb[:m2.start()] + country_raw.strip() + "\n" + nb[en:]
                else:
                    nb = nb.rstrip() + "\n\t" + country_raw.strip() + "\n"
            snapshot(path)
            io.open(path, "w", encoding="utf-8", newline="").write(text[:b + 1] + nb + text[e - 1:])
            CHANGED[path] = rel
            reload_data()
            return True, "树设置已保存"
    return False, "未找到树 " + tree_id

# ---------------- 国家精神 ----------------













def brace_balance(text):
    depth = 0
    extras = []
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c == '#':
            j = text.find('\n', i)
            if j < 0:
                break
            i = j + 1
            continue
        if c == '"':
            i += 1
            while i < n and text[i] != '"':
                if text[i] == '\\':
                    i += 1
                i += 1
            i += 1
            continue
        if c == '{':
            depth += 1
        elif c == '}':
            if depth == 0:
                extras.append(i)
            else:
                depth -= 1
        i += 1
    return depth, extras

def brace_scan_roots(root):
    out = []
    for sub in ("common", "events"):
        base = os.path.join(root, sub)
        if not os.path.isdir(base):
            continue
        for dp, dns, fns in os.walk(base):
            for fn in fns:
                if fn.endswith(".txt"):
                    p = os.path.join(dp, fn)
                    out.append(p)
    return out

def brace_issues():
    items = []
    for root in ROOTS:
        for p in brace_scan_roots(root):
            try:
                text = io.open(p, encoding="utf-8", errors="replace").read()
            except Exception:
                continue
            d, extras = brace_balance(text)
            if d or extras:
                rel = os.path.relpath(p, root)
                items.append({"kind": "文件花括号不平衡", "id": rel.replace(os.sep, "/"),
                              "file": rel.replace(os.sep, "/"), "root": root,
                              "where": "depth=%s extra=%s" % (d, len(extras))})
    return items

def repair_file_braces(rel):
    for root in ROOTS:
        p = os.path.join(root, rel.replace("/", os.sep))
        if not os.path.exists(p):
            continue
        text = io.open(p, encoding="utf-8", errors="replace", newline="").read()
        depth, extras = brace_balance(text)
        if not depth and not extras:
            return False, "这个文件花括号本来就是平衡的"
        chars = list(text)
        for pos in reversed(extras):
            del chars[pos]
        newtext = "".join(chars)
        d2, _ = brace_balance(newtext)
        if d2 > 0:
            newtext = newtext.rstrip() + "\n" + ("}\n" * d2)
        snapshot(p)
        io.open(p, "w", encoding="utf-8", newline="").write(newtext)
        CHANGED[p] = rel
        return True, "已修复 %s（补 %s 个 / 删 %s 个括号）" % (rel, d2, len(extras))
    return False, "没有找到文件"

def repair_all_braces():
    fixed = 0
    for it in brace_issues():
        try:
            ok, _ = repair_file_braces(it["file"])
            if ok:
                fixed += 1
        except Exception:
            pass
    reload_data()
    return True, "已修复 %s 个文件" % fixed

def mod_conflicts():
    roots = [(r, os.path.basename(r.rstrip("\\/")) or r) for r in ROOTS]
    rps = []
    for r, n in roots:
        rp = set()
        p = os.path.join(r, "descriptor.mod")
        if os.path.exists(p):
            try:
                txt = io.open(p, encoding="utf-8", errors="replace").read()
                rp = set(re.findall(r'replace_path\s*=\s*"([^"]+)"', txt))
            except Exception:
                pass
        rps.append(rp)
    out = []
    seen = set()
    for j, (r2, n2) in enumerate(roots):
        for i, (r1, n1) in enumerate(roots):
            if i == j:
                continue
            for path in rps[j]:
                key = (n2, path, n1)
                if key in seen:
                    continue
                d1 = os.path.join(r1, path.replace("/", os.sep))
                if os.path.isdir(d1):
                    try:
                        has = any(os.scandir(d1))
                    except Exception:
                        has = False
                    if has:
                        seen.add(key)
                        out.append({"kind": "模组路径冲突", "id": path,
                                    "where": n2 + " 的 replace_path 会覆盖/排除 " + n1,
                                    "file": "descriptor.mod", "root": r2})
    return out

def report_items():
    items = []
    for tid in TREE_ORDER:
        t = TREES.get(tid)
        if not t:
            continue
        ids = {f["id"] for f in t["focuses"]}
        for f in t["focuses"]:
            if f["id"] not in LOC or not LOC.get(f["id"], "").strip():
                items.append({"kind": "缺失本地化", "id": f["id"], "where": tid, "file": t["file"]})
            for g in f.get("prereq", []):
                for p in g:
                    if p not in ids:
                        items.append({"kind": "悬空前置", "id": f["id"], "where": p, "file": t["file"]})
    for tid, t in TECHS.items():
        for p in t.get("prereq", []):
            if p not in TECHS:
                items.append({"kind": "科技前置不存在", "id": tid, "where": p, "file": t["file"]})
        for l in t.get("leads", []):
            if l not in TECHS:
                items.append({"kind": "科技 leads 不存在", "id": tid, "where": l, "file": t["file"]})
    for eid, e in EVENTS.items():
        ns = e.get("ns", "")
        if ns and "." in eid and not eid.startswith(ns + "."):
            items.append({"kind": "事件 namespace 不匹配", "id": eid, "where": ns, "file": e.get("file", "")})
    items += brace_issues()
    items += mod_conflicts()
    return items

def unload_mod(root):
    p = os.path.abspath(root or "")
    before = len(ROOTS)
    ROOTS[:] = [r for r in ROOTS if os.path.abspath(r) != p]
    if len(ROOTS) == before:
        return False, "没有找到这个 mod"
    reload_data()
    build_icons(ROOTS, GAME)
    return True, "已卸载：%s" % (os.path.basename(p.rstrip("/").rstrip("\\")) or p)

def writable_root():
    for r in ROOTS:
        if not is_under_game(r):
            return r
    return None

def writable_target(target=""):
    if target:
        t = os.path.abspath(target)
        if t in [os.path.abspath(r) for r in ROOTS] and not is_under_game(t):
            return t
    return writable_root()

def _append_container(path, container, block):
    text = io.open(path, encoding="utf-8", errors="replace", newline="").read() if os.path.exists(path) else (container + " = {\n}\n")
    m = re.search(r'(?m)^\s*%s\s*=\s*\{' % re.escape(container), text)
    if not m:
        text = text.rstrip() + "\n" + container + " = {\n}\n"
        m = re.search(r'(?m)^\s*%s\s*=\s*\{' % re.escape(container), text)
    b = text.find('{', m.start())
    e = brace_match(text, b)
    snapshot(path)
    io.open(path, "w", encoding="utf-8", newline="").write(text[:e - 1] + block + text[e - 1:])
    return os.path.relpath(path, os.path.dirname(path))

def copy_tree(tree_id, new_id):
    t = TREES.get(tree_id)
    if not t:
        return False, "没有找到这棵国策树"
    if not re.match(r'^[A-Za-z0-9_]+$', new_id or ""):
        return False, "新树 ID 只能包含字母数字下划线"
    if new_id in TREES:
        return False, "树 ID 已存在"
    dest = writable_root()
    if not dest:
        return False, "没有可写的模组，请先加载/新建一个模组"
    src = os.path.join(t.get("root") or dest, t["file"])
    if not os.path.exists(src):
        return False, "找不到源文件"
    text = io.open(src, encoding="utf-8", errors="replace", newline="").read()
    block = None
    for m in re.finditer(r'(?m)^\s*focus_tree\s*=\s*\{', text):
        b = text.find('{', m.start())
        e = brace_match(text, b)
        body = text[b + 1:e - 1]
        mid = re.search(r'(?m)^\s*id\s*=\s*"?([A-Za-z0-9_]+)"?', body)
        if mid and mid.group(1) == tree_id:
            block = body
            break
    if block is None:
        return False, "源文件里找不到这棵树的结构"
    ids = []
    for s, e2, fb in find_blocks(block, "focus"):
        node = parse_focus_like(fb)
        if node:
            ids.append(node["id"])
    newblock = block
    for oid in ids:
        newblock = re.sub(r'\b%s\b' % re.escape(oid), new_id + "_" + oid, newblock)
    newblock = re.sub(r'(?m)^(\s*id\s*=\s*)"?%s"?' % re.escape(tree_id), r'\1' + new_id, newblock, count=1)
    path = os.path.join(dest, "common", "national_focus", "zz_focus_editor_copied.txt")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path):
        txt = io.open(path, encoding="utf-8", errors="replace", newline="").read()
        txt = txt.rstrip() + "\nfocus_tree = {\n" + newblock.strip() + "\n}\n"
    else:
        txt = "focus_tree = {\n" + newblock.strip() + "\n}\n"
    snapshot(path)
    io.open(path, "w", encoding="utf-8", newline="").write(txt)
    CHANGED[path] = os.path.join("common", "national_focus", "zz_focus_editor_copied.txt")
    ents = {"simp_chinese": {}}
    for oid in ids:
        nm = LOC.get(oid, "")
        ds = LOC.get(oid + "_desc", "")
        if nm:
            ents["simp_chinese"][new_id + "_" + oid] = nm
        if ds:
            ents["simp_chinese"][new_id + "_" + oid + "_desc"] = ds
    if ents["simp_chinese"]:
        save_loc(dest, ents)
    reload_data()
    return True, "已复制到你的模组：%s（%d 个焦点）" % (new_id, len(ids))

def copy_item(kind, item_id, new_id):
    dest = writable_root()
    if not dest:
        return False, "没有可写的模组，请先加载/新建一个模组"
    if kind == "idea":
        src = IDEAS.get(item_id)
    elif kind == "equip":
        src = EQUIPMENTS.get(item_id)
    elif kind == "tech":
        src = TECHS.get(item_id)
    elif kind == "event":
        src = EVENTS.get(item_id)
    else:
        src = None
    if not src:
        return False, "没有找到要复制的内容"
    if not re.match(r'^[A-Za-z0-9_]+$', new_id or ""):
        return False, "新 ID 只能包含字母数字下划线"
    raw = src.get("raw", "")
    raw = re.sub(r'(?m)^(\s*)%s(\s*=\s*\{)' % re.escape(item_id),
                 lambda m: m.group(1) + new_id + m.group(2), raw, count=1)
    ents = {}
    if kind == "idea":
        block = "\n" + raw.strip() + "\n"
        path = os.path.join(dest, "common", "ideas", "zz_focus_editor_copied.txt")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        _append_container(path, "ideas", block)
        rel = os.path.join("common", "ideas", "zz_focus_editor_copied.txt")
        ents.setdefault("simp_chinese", {})[new_id] = src.get("name", new_id)
        if src.get("desc"):
            ents["simp_chinese"][new_id + "_desc"] = src.get("desc")
    elif kind == "equip":
        block = "\n" + raw.strip() + "\n"
        path = os.path.join(dest, "common", "units", "equipment", "zz_focus_editor_copied.txt")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        _append_container(path, "equipments", block)
        rel = os.path.join("common", "units", "equipment", "zz_focus_editor_copied.txt")
        ents.setdefault("simp_chinese", {})[new_id] = src.get("name", new_id)
    elif kind == "tech":
        old_folder = src.get("path") or "copied_folder"
        raw = re.sub(r'(?m)^(\s*name\s*=\s*)"?%s"?' % re.escape(old_folder),
                     r'\1copied_folder', raw, count=1)
        block = "\n\tcopied_folder = {\n" + raw.strip() + "\n\t}\n"
        path = os.path.join(dest, "common", "technologies", "zz_focus_editor_copied.txt")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        _append_container(path, "technologies", block)
        rel = os.path.join("common", "technologies", "zz_focus_editor_copied.txt")
        ents.setdefault("simp_chinese", {})[new_id] = src.get("name", new_id)
    else:
        path = os.path.join(dest, "events", "zz_focus_editor_copied.txt")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        txt = io.open(path, encoding="utf-8", errors="replace", newline="").read() if os.path.exists(path) else "add_namespace = zzfe_copied\n\n"
        if "add_namespace = zzfe_copied" not in txt:
            txt = "add_namespace = zzfe_copied\n\n" + txt
        txt = txt.rstrip() + "\n" + raw.strip() + "\n"
        snapshot(path)
        io.open(path, "w", encoding="utf-8", newline="").write(txt)
        rel = os.path.join("events", "zz_focus_editor_copied.txt")
        ents.setdefault("simp_chinese", {})[new_id + ".t"] = src.get("title", new_id)
    if ents:
        save_loc(dest, ents)
    reload_data()
    return True, "已复制到你的模组：%s" % new_id

def save_design(archetype, modules, org="", name="", target=""):
    dest = writable_target(target)
    if not dest:
        return False, "没有可写的模组"
    d = os.path.join(dest, "common", "units", "equipment")
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, "zz_focus_editor_designs.txt")
    old = io.open(path, encoding="utf-8", errors="replace", newline="").read() if os.path.exists(path) else ""
    lines = ["# 设计草稿（不会自动生效，供参考/复制）",
             "# archetype = %s" % archetype,
             "# org = %s" % (org or ""),
             "# name = %s" % (name or archetype)]
    for cat, mid in sorted((modules or {}).items()):
        lines.append("# %s = %s" % (cat, mid))
    block = "\n".join(lines) + "\n"
    if old and not old.endswith("\n"):
        old += "\n"
    snapshot(path)
    io.open(path, "w", encoding="utf-8", newline="").write(old + "\n" + block)
    CHANGED[path] = os.path.join("common", "units", "equipment", "zz_focus_editor_designs.txt")
    return True, "设计草稿已保存到模组"

def save_variant(arch, modules, name="", org="", target=""):
    dest = writable_target(target)
    if not dest:
        return False, "没有可写的模组"
    eq = EQUIPMENTS.get(arch)
    if not eq:
        return False, "没有找到底盘 " + str(arch)
    slots = eq.get("slots") or []
    if not slots:
        return False, "这个底盘没有 module_slots 定义，无法生成变体"
    lines = []
    missing = []
    for sl in slots:
        mid = (modules or {}).get(sl["slot"])
        if mid:
            lines.append("\t\t\t\t%s = %s" % (sl["slot"], mid))
        elif sl.get("required"):
            missing.append(sl["slot"])
    if missing:
        return False, "必装槽位未选择：%s" % "、".join(missing)
    if not lines:
        return False, "至少选择一个模块"
    nm = re.sub(r'[^A-Za-z0-9_]', '', (name or arch))[:40] or "design"
    effect_id = "zzfe_variant_" + nm
    effect = ("%s = {\n"
              "\tcreate_equipment_variant = {\n"
              "\t\tname = \"%s\"\n"
              "\t\ttype = %s\n"
              "\t\tparent_version = 0\n"
              "\t\tallow_without_tech = yes\n"
              "\t\tmodules = {\n%s\n\t\t}\n"
              "\t}\n}\n") % (effect_id, (name or arch).replace('"', ""), arch, "\n".join(lines))
    d = os.path.join(dest, "common", "scripted_effects")
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, "zz_focus_editor_variants.txt")
    old = io.open(path, encoding="utf-8", errors="replace", newline="").read() if os.path.exists(path) else ""
    m = re.search(r'(?m)^%s\s*=\s*\{' % re.escape(effect_id), old)
    if m:
        b = old.find('{', m.start())
        e = brace_match(old, b)
        newtext = old[:m.start()] + effect + old[e:]
    else:
        newtext = old.rstrip() + ("\n\n" if old.strip() else "") + effect
    snapshot(path)
    io.open(path, "w", encoding="utf-8", newline="").write(newtext)
    CHANGED[path] = os.path.join("common", "scripted_effects", "zz_focus_editor_variants.txt")
    return True, "已生成装备变体效果（%s），可插入国策/事件或直接调用" % effect_id



def _is_readonly_root(p):
    """原版目录和创意工坊目录都不该被写。

    创意工坊路径形如 <Steam>/steamapps/workshop/content/<appid>/<modid>，
    Steam 会在校验时把它改回去，写进去等于白改，还会污染订阅内容。
    """
    return is_readonly_mod(p)


def entry_source(root, file, layer=None):
    """一条内容到底「从哪层读、保存时会写到哪」。

    R3-2：接管提示前移。以前用户点开来自创意工坊层的节点，面板和写在可写层的
    一模一样，直到点保存才看到「已复制到 XRT1」。这个接口在打开编辑器的那一刻
    就把答案问出来。

    layer 优先：列表项自带 source（loader 按真实所在层记的），比「按文件存在性
    从上往下猜」准——同一个文件名在几层都有时，生效的是顶层，但 loader 读到的
    就是顶层那份，两者一致；万一不一致（缓存等），以 source 为准。
    """
    root = root or (ROOTS[-1] if ROOTS else "")
    rel = (file or "").replace("\\", "/").lstrip("/")
    if not rel:
        return {"ok": False, "msg": "参数不完整：缺少 file"}
    layers = [x for x in (mod_layers(root) or []) if x]

    def _hit(base):
        ro = _readonly_flag(base)
        top = _writable_top(after=base) if ro else ""
        return {"ok": True, "file": rel,
                "layer": os.path.basename(base.rstrip("\\/")) or base,
                "layer_path": base,
                "readonly": bool(ro),
                "game": bool(GAME) and os.path.abspath(base) == os.path.abspath(GAME),
                "adopt_to": (os.path.basename(top.rstrip("\\/")) or top) if (ro and top) else ""}

    if layer:
        for base in layers:
            if (os.path.basename(base.rstrip("\\/")) or base) == layer:
                return _hit(base)
        # source 说的层不在当前链里（可能是刚卸载的层），退回按文件找
    for base in reversed(layers):
        if os.path.isfile(os.path.join(base, rel.replace("/", os.sep))):
            return _hit(base)
    return {"ok": False, "code": "FILE_NOT_FOUND",
            "msg": "加载链里没有这个文件：%s" % rel}


def _writable_top(after=None):
    """最顶层可写的 mod 目录（不是原版、不是创意工坊）。

    给了 after 就从它所在位置往上找：改 A 的内容应该落到「A 之后加载的
    第一个可写层」，而不是全局最后加载的那个。A 不在链上（比如创意工坊
    目录只是被依赖，没进 ROOTS）时退回全局查找。
    """
    try:
        seq = list(ROOTS)
        if after:
            aab = os.path.abspath(after)
            for i, r in enumerate(seq):
                if os.path.abspath(r) == aab:
                    seq = seq[i + 1:]
                    break
        for r in reversed(seq):
            rab = os.path.abspath(r)
            if rab and not _is_readonly_root(rab):
                return rab
    except Exception:
        pass
    return ""


def _adopt_file(dst_root, src_root, rel):
    """把 src_root/rel 复制到 dst_root/rel（目标已存在就不动）。"""
    if not dst_root or not src_root or not rel:
        return False
    try:
        s = os.path.join(src_root, rel)
        d = os.path.join(dst_root, rel)
        if os.path.exists(d) or not os.path.isfile(s):
            return False
        dd = os.path.dirname(d)
        if dd and not os.path.isdir(dd):
            os.makedirs(dd)
        shutil.copy2(s, d)
        return True
    except Exception:
        return False

def load_vanilla():
    if not os.path.isdir(GAME):
        return False, "没有找到游戏目录"
    if GAME not in ROOTS:
        ROOTS.append(GAME)
    n = load_mod(GAME)
    _lp("构建图标索引", "", 98)
    try:
        build_icons(ROOTS, GAME)
    except Exception as e:
        print("图标构建失败:", e)
    _lp_done()
    return True, "已加载原版参考（只读），共 %d 棵树" % n

def list_backups(root, rel):
    path = os.path.abspath(os.path.join(root, rel)) if root else ""
    h = HISTORY.get(path)
    items = []
    if h:
        for i, fn in enumerate(h.get("undo", [])):
            try:
                ts = int(os.path.basename(fn).rsplit("_", 1)[-1].split(".")[0]) // 1000
                t = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))
            except Exception:
                t = "?"
            items.append({"index": i, "time": t, "name": os.path.basename(fn)})
    return items

def restore_backup(root, rel, index):
    path = os.path.abspath(os.path.join(root, rel))
    h = HISTORY.get(path)
    if not h or index < 0 or index >= len(h["undo"]):
        return False, "备份不存在"
    snapshot(path)
    shutil.copyfile(h["undo"][index], path)
    reload_data()
    return True, "已恢复备份"

# ---------------- AI ----------------
AI_CONFIG_PATH = os.path.join(WORK, "ai_config.json")
DEFAULT_AI = {
    "provider": "openai",
    "base_url": "https://api.openai.com/v1",
    "api_key": "",
    "model": "gpt-4o-mini",
    "system": "你是 HOI4 mod 脚本助手，回答要给出可直接使用的脚本片段。",
}

def load_ai():
    cfg = dict(DEFAULT_AI)
    try:
        if os.path.exists(AI_CONFIG_PATH):
            cfg.update(json.loads(io.open(AI_CONFIG_PATH, encoding="utf-8").read()))
    except Exception:
        pass
    return cfg

def save_ai(cfg):
    try:
        old = load_ai()
        data = {k: cfg.get(k, DEFAULT_AI.get(k, "")) for k in DEFAULT_AI}
        if not data.get("api_key"):
            data["api_key"] = old.get("api_key", "")
        io.open(AI_CONFIG_PATH, "w", encoding="utf-8", newline="").write(
            json.dumps(data, ensure_ascii=False, indent=2))
        return True, "AI 配置已保存"
    except Exception as e:
        return False, "保存失败: %s" % e

def _post_json(url, payload, headers, timeout=90):
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                 headers=dict({"Content-Type": "application/json"}, **headers))
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))

# v0.69 AI 流式输出
def _ai_messages(system, prompt, context, history, max_turns=12):
    """把历史消息 + 当前提问拼成 messages 数组。

    history: [{"role": "user"/"assistant", "content": "..."}]
    只保留最近 max_turns 轮，避免上下文过长把模型窗口挤爆。"""
    msgs = [{"role": "system", "content": system}]
    hist = list(history or [])
    if len(hist) > max_turns * 2:
        hist = hist[-max_turns * 2:]
    for h in hist:
        role = h.get("role")
        content = (h.get("content") or "").strip()
        if role in ("user", "assistant") and content:
            msgs.append({"role": role, "content": content})
    cur = prompt if not context else (context + "\n\n---\n\n" + prompt)
    msgs.append({"role": "user", "content": cur})
    return msgs


def ai_chat_stream(cfg, prompt, context, emit, history=None):
    """逐块把模型输出交给 emit(chunk)。返回 (ok, 错误信息)。

    OpenAI 兼容 / Ollama / Anthropic / Gemini 都支持；解析失败时退回一次性返回。
    """
    provider = (cfg.get("provider") or "openai").lower()
    base = (cfg.get("base_url") or "").rstrip("/")
    key = cfg.get("api_key") or ""
    model = cfg.get("model") or ""
    system = cfg.get("system") or DEFAULT_AI["system"]
    msgs = _ai_messages(system, prompt, context, history)
    text = msgs[-1]["content"]
    if not base:
        return False, "请填写 Base URL"

    def _open(url, payload, headers):
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                     headers=dict({"Content-Type": "application/json"}, **headers))
        return urllib.request.urlopen(req, timeout=180)

    try:
        if provider in ("openai", "deepseek", "ollama", "custom"):
            body = {"model": model, "temperature": 0.3, "stream": True,
                    "messages": msgs}
            with _open(base + "/chat/completions", body,
                       {"Authorization": "Bearer " + key} if key else {}) as r:
                for raw in r:
                    line = raw.decode("utf-8", "replace").strip()
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        obj = json.loads(data)
                    except Exception:
                        continue
                    choices = obj.get("choices") or []
                    if not choices:
                        continue
                    delta = choices[0].get("delta") or {}
                    piece = delta.get("content") or ""
                    if piece:
                        emit(piece)
            return True, ""

        if provider == "anthropic":
            body = {"model": model, "max_tokens": 2000, "system": system, "stream": True,
                    "messages": [{"role": "user", "content": text}]}
            with _open(base + "/messages", body,
                       {"x-api-key": key, "anthropic-version": "2023-06-01"}) as r:
                for raw in r:
                    line = raw.decode("utf-8", "replace").strip()
                    if not line.startswith("data:"):
                        continue
                    try:
                        obj = json.loads(line[5:].strip())
                    except Exception:
                        continue
                    if obj.get("type") == "content_block_delta":
                        piece = (obj.get("delta") or {}).get("text") or ""
                        if piece:
                            emit(piece)
            return True, ""

        if provider == "gemini":
            url = base + "/models/" + model + ":streamGenerateContent?alt=sse&key=" + key
            body = {"contents": [{"parts": [{"text": system + "\n\n" + text}]}]}
            with _open(url, body, {}) as r:
                for raw in r:
                    line = raw.decode("utf-8", "replace").strip()
                    if not line.startswith("data:"):
                        continue
                    try:
                        obj = json.loads(line[5:].strip())
                    except Exception:
                        continue
                    cands = obj.get("candidates") or []
                    if not cands:
                        continue
                    parts = (cands[0].get("content") or {}).get("parts") or []
                    piece = "".join(p.get("text", "") for p in parts)
                    if piece:
                        emit(piece)
            return True, ""

        return False, "未知的提供商: " + provider
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode("utf-8", "replace")[:300]
        except Exception:
            detail = ""
        return False, "HTTP %s: %s" % (e.code, detail)
    except Exception as e:
        return False, "请求失败: %s" % e


def ai_chat(cfg, prompt, context="", history=None):

    provider = (cfg.get("provider") or "openai").lower()
    base = (cfg.get("base_url") or "").rstrip("/")
    key = cfg.get("api_key") or ""
    model = cfg.get("model") or ""
    system = cfg.get("system") or DEFAULT_AI["system"]
    text = prompt if not context else (context + "\n\n---\n\n" + prompt)
    try:
        if provider in ("openai", "deepseek", "ollama", "custom"):
            if not base:
                return False, "请填写 Base URL"
            data = _post_json(base + "/chat/completions", {
                "model": model, "temperature": 0.3,
                "messages": [{"role": "system", "content": system},
                             {"role": "user", "content": text}]},
                {"Authorization": "Bearer " + key} if key else {})
            return True, data["choices"][0]["message"]["content"]
        if provider == "anthropic":
            if not base:
                return False, "请填写 Base URL"
            data = _post_json(base + "/messages", {
                "model": model, "max_tokens": 2000, "system": system,
                "messages": [{"role": "user", "content": text}]},
                {"x-api-key": key, "anthropic-version": "2023-06-01"})
            return True, "".join(b.get("text", "") for b in data.get("content", []))
        if provider == "gemini":
            url = base + "/models/" + model + ":generateContent?key=" + key
            data = _post_json(url, {"contents": [{"parts": [{"text": system + "\n\n" + text}]}]}, {})
            return True, data["candidates"][0]["content"]["parts"][0]["text"]
        return False, "未知的提供商: " + provider
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8", "replace")[:300]
        except Exception:
            body = ""
        return False, "HTTP %s: %s" % (e.code, body)
    except Exception as e:
        return False, "请求失败: %s" % e

def add_shared_focus(root, sid):
    if not re.match(r'^[A-Za-z0-9_]+$', sid or ""):
        return False, "id 只能字母数字下划线"
    d = os.path.join(root, "common", "national_focus")
    os.makedirs(d, exist_ok=True)
    fn = unique_editor_filename(root, "common/national_focus", "zz_focus_editor_shared.txt")
    path = os.path.join(d, fn)
    text = io.open(path, encoding="utf-8", errors="replace", newline="").read() if os.path.exists(path) else ""
    if re.search(r'(?m)^\s*id\s*=\s*"?%s"?' % re.escape(sid), text):
        return False, "共享焦点已存在"
    block = ("\nshared_focus = {\n\tid = %s\n\ticon = GFX_goal_generic_national_unity\n"
             "\tx = 0\n\ty = 0\n\tcost = 1\n}\n" % sid)
    snapshot(path)
    io.open(path, "w", encoding="utf-8", newline="").write(text + block)
    CHANGED[path] = os.path.join("common", "national_focus", fn)
    reload_data()
    return True, "已新建共享焦点 " + sid

def delete_shared_focus(root, rel, sid):
    path = os.path.join(root, rel)
    text = io.open(path, encoding="utf-8", errors="replace", newline="").read()
    for m in re.finditer(r'(?m)^\s*shared_focus\s*=\s*\{', text):
        b = text.find('{', m.start())
        e = brace_match(text, b)
        if re.search(r'(?m)^\s*id\s*=\s*"?%s"?' % re.escape(sid), text[b:e]):
            snapshot(path)
            io.open(path, "w", encoding="utf-8", newline="").write(text[:m.start()] + text[e:])
            CHANGED[path] = rel
            reload_data()
            return True, "已删除共享焦点 " + sid
    return False, "未找到共享焦点 " + sid



# ---------------- HTTP 服务 ----------------
INDEX = os.path.join(RES_DIR, "focus_editor_index.html")

# 2C：三个启动期路径写进 state 的槽位，handlers 从此不必为了读目录去摸门面。
# RES_DIR 在打包后是 sys._MEIPASS（解压目录），ICON_DIR 跟着可写的 WORK，INDEX 跟着 RES_DIR。
_state.set_path_var("RES_DIR", RES_DIR)
_state.set_path_var("ICON_DIR", ICON_DIR)
_state.set_path_var("INDEX", INDEX)

# ---------- v1.24.0 错误码 ----------
# 529 个失败分支不可能逐个改。在 _send 出口按文案归类，前端拿 code 翻成人话；
# 需要精确控制的分支可以自己带 code（带了就不覆盖）。


def _lang(path):
    m = re.search(r"[?&]lang=(zh|en|ja)\b", path or "")
    return m.group(1) if m else "zh"

def _prepare_post(h):
    """POST 的横切准备：读 body → 解析 JSON → 只读接管（`self.` 换成了 `h.`）。

    留在门面、不搬进 routes_post：它会改 body["root"]，路由函数拿到的必须是改过的那份。
    出错时自己已经 _send 过，返回 None 让调用方收工。
    """
    n = int(h.headers.get("Content-Length", 0))
    raw = h.rfile.read(n) or b"{}"
    try:
        body = json.loads(raw.decode("utf-8"))
    except Exception:
        try:
            body = json.loads(raw.decode("gbk", errors="replace"))
        except Exception:
            h._send({"ok": False, "msg": "请求体不是合法 JSON"}, 400)
            return
    ro = body.get("root") or body.get("base") or ""
    # 只读保护针对"写文件"的接口；加载/卸载原版参考不改磁盘，必须放行。
    # 原版目录和创意工坊目录都算只读——但不再直接拒绝，而是自动接管到最顶层可写的 mod：
    # 把要改的那个文件复制过去（同名覆盖），其余文件仍走叠加链读原层。
    # 只读保护只针对"写文件"的接口。加载/卸载只读不写，必须放行，
    # 否则连创意工坊的 mod 都加载不进来。
    # entry_source 必须放行：它是「问这条会写到哪」的只读查询，
    # 不放行的话，查询本身就会触发接管、把文件复制进可写层——
    # R3 实测：点开州/科技面板各问一次，XRT1 里就多了 1-Corsica.txt 和 MVLV_UNI.txt。
    _READONLY_OK = ("/api/load_vanilla", "/api/unload_mod", "/api/load_mod",
                    "/api/load_mod_root", "/api/load_progress", "/api/pick_mod",
                    "/api/entry_source")
    if ro and _is_readonly_root(ro) and h.path not in _READONLY_OK:
        _top = _writable_top(after=ro)
        if not _top:
            h._send({"ok": False, "msg": "没有可写的模组目录：请先新建或加载一个自己的 mod"})
            return
        _rel = body.get("rel") or body.get("file") or ""
        _adopted = _adopt_file(_top, ro, _rel)
        body["root"] = _top
        body["base"] = _top
        ro = _top
        if _rel:
            body["_adopted"] = _adopted
        # v1.24.1：磁盘上确实发生了「往你的 mod 里塞文件」这件事，必须让用户看见。
        # 复制成功和「副本早就存在」都要告知——两种情况下写的都不是他指的那一层。
        try:
            h._adopted_to = os.path.basename(_top.rstrip("\\/")) or _top
            h._adopted_copied = bool(_adopted)
        except Exception:
            pass
    return body


def _log_server_error(tag, path, err, tb):
    """未捕获请求异常同时写 stderr 与 work/logs/server_error.log，方便事后查完整堆栈。"""
    msg = "[%s] %s %s -> %s\n%s\n" % (
        time.strftime("%Y-%m-%d %H:%M:%S"), tag, path, err, tb.rstrip())
    try:
        sys.stderr.write(msg)
        sys.stderr.flush()
    except Exception:
        pass
    try:
        log_dir = os.path.join(WORK, "logs")
        os.makedirs(log_dir, exist_ok=True)
        with io.open(os.path.join(log_dir, "server_error.log"), "a", encoding="utf-8", newline="\n") as f:
            f.write(msg)
    except Exception:
        pass


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, obj, code=200, ctype="application/json; charset=utf-8", extra=None):
        # v1.24.1：防重发。崩溃兜底层和内层都会调 _send，一个请求只能回一次；
        # 多发一次的后果是浏览器把第二次响应当成下一个请求的响应，整条连接错位。
        if getattr(self, "_sent", False):
            return
        self._sent = True
        # v1.24.0：失败统一补一个机器可读的 code，前端才能查表给人话解释
        if isinstance(obj, dict) and obj.get("ok") is False and not obj.get("code"):
            obj = dict(obj)
            obj["code"] = classify_error(obj.get("msg") or "")
        # v1.24.1：自动接管了文件（只读层 → 可写层）就把这件事写进 msg
        if isinstance(obj, dict) and obj.get("ok") and getattr(self, "_adopted_to", ""):
            obj = dict(obj)
            _m = obj.get("msg") or "已保存"
            if getattr(self, "_adopted_copied", False):
                obj["msg"] = "%s（文件已复制到 %s，原层未改动）" % (_m, self._adopted_to)
            else:
                obj["msg"] = "%s（写的是 %s 里的副本，原层未改动）" % (_m, self._adopted_to)
            obj["adopted_to"] = self._adopted_to
        body = obj if isinstance(obj, bytes) else json.dumps(obj, ensure_ascii=False).encode("utf-8")
        hdrs = []
        if len(body) > 50000 and "application/json" in ctype and "gzip" in (self.headers.get("Accept-Encoding") or ""):
            try:
                import gzip
                body = gzip.compress(body, 5)
                hdrs.append(("Content-Encoding", "gzip"))
            except Exception:
                pass
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        for k, v in hdrs:
            self.send_header(k, v)
        if extra:
            for k, v in extra:
                self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _ai_stream(self, cfg, prompt, context):
        """SSE 流式输出：每个片段一行 data: {"d": "..."}，结束时 data: {"end": true}"""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()

        def emit(piece):
            self.wfile.write(("data: " + json.dumps({"d": piece}, ensure_ascii=False) + "\n\n").encode("utf-8"))
            self.wfile.flush()

        try:
            ok, err = ai_chat_stream(cfg, prompt, context, emit)
        except Exception as e:
            ok, err = False, "流式中断: %s" % e
        try:
            self.wfile.write(("data: " + json.dumps({"end": True, "ok": ok, "msg": err},
                                                    ensure_ascii=False) + "\n\n").encode("utf-8"))
            self.wfile.flush()
        except Exception:
            pass
        self.close_connection = True

    def do_GET(self):
        # v1.24.1：请求处理里任何一处抛异常，原来都是「连接被断」——前端只看得到
        # 网络层错误，看不到 code。这里兜住，至少回一个能读的错误。
        try:
            path_only = self.path.split("?")[0]
            gate = _boot_gate(path_only)
            if gate is not None:
                # 加载中：告诉浏览器 1 秒后重试，别把 503 缓存成失败
                self._send(gate, 503, extra=[("Retry-After", "1"), ("Cache-Control", "no-store")])
                return
            if not routes_get.dispatch(self, path_only):
                self._send({"err": "not found"}, 404)
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            self.close_connection = True
        except Exception as e:
            import traceback
            _log_server_error("do_GET", self.path, e, traceback.format_exc())
            if not getattr(self, "_sent", False):
                try:
                    self._send({"ok": False, "code": "INTERNAL",
                                "msg": "服务器内部错误：%s" % (e,)}, 500)
                except Exception:
                    self.close_connection = True

    def do_POST(self):
        # v1.24.1：同 do_GET。这里是重点——参数缺失、路径拼不出来这类 TypeError
        # 原来直接冒到 socketserver，浏览器只收到「连接被断」。
        try:
            path_only = self.path.split("?")[0]
            gate = _boot_gate(path_only)
            if gate is not None:
                self._send(gate, 503, extra=[("Retry-After", "1"), ("Cache-Control", "no-store")])
                return
            body = _prepare_post(self)
            if body is None:
                return
            if not routes_post.dispatch(self, self.path, body):
                self._send({"err": "not found"}, 404)
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            self.close_connection = True
        except Exception as e:
            import traceback
            _log_server_error("do_POST", self.path, e, traceback.format_exc())
            if not getattr(self, "_sent", False):
                try:
                    self._send({"ok": False, "code": "INTERNAL",
                                "msg": "服务器内部错误：%s" % (e,)}, 500)
                except Exception:
                    self.close_connection = True


def detect_mods():
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        d = filedialog.askdirectory(title="选择 mod 根目录（含 descriptor.mod 的那一层）")
        root.destroy()
        return [d] if d else []
    except Exception as e:
        print("图形选择失败:", e)
        return []

def fs_list(path):
    path = (path or "").strip()
    if path:
        path = os.path.abspath(path)
    if not path or not os.path.isdir(path):
        drives = []
        for c in string.ascii_uppercase:
            d = c + ":\\"
            if os.path.isdir(d):
                drives.append({"name": c + ":", "path": d, "has_mod": False})
        return {"path": "", "parent": "", "dirs": drives}
    dirs = []
    try:
        with os.scandir(path) as it:
            for e in sorted(it, key=lambda x: x.name.lower()):
                if not e.is_dir():
                    continue
                p = e.path
                has = os.path.exists(os.path.join(p, "descriptor.mod")) or \
                      os.path.isdir(os.path.join(p, "common", "national_focus"))
                dirs.append({"name": e.name, "path": p, "has_mod": has})
    except Exception as ex:
        return {"path": path, "parent": "", "dirs": [], "error": str(ex)}
    parent = os.path.dirname(path.rstrip("\\/"))
    if parent == path.rstrip("\\/") or len(path.rstrip("\\/")) <= 2:
        parent = ""
    return {"path": path, "parent": parent, "dirs": dirs}



def load_mod_root(path):
    if not LOC:
        load_game_loc()
    path = os.path.abspath(path or "")
    if not os.path.isdir(path):
        return False, "目录不存在"
    has_nf = os.path.isdir(os.path.join(path, "common", "national_focus"))
    has_desc = os.path.exists(os.path.join(path, "descriptor.mod"))
    if not (has_nf or has_desc):
        return False, "不是 mod 根目录（缺少 descriptor.mod 或 common/national_focus）"
    if path in ROOTS:
        return False, "这个目录已经加载过了"
    ROOTS.append(path)
    _LAYERS_CACHE.clear()
    invalidate_chain_cache()
    invalidate_object_cache()
    n = load_mod(path)
    _lp("关联国家", "", 96)
    link_countries()
    _lp("构建图标索引", "", 98)
    try:
        build_icons(ROOTS, GAME)
    except Exception as e:
        print("图标构建失败:", e)
    _lp_done()
    return True, "已加载 %s（%d 棵树）" % (os.path.basename(path), n)

def _boot_load(roots):
    """启动期把 mod 读进内存。跑在后台线程里，端口先起来、页面先出来。

    调用方负责在起线程之前就把 LOAD_PROGRESS["active"] 置 True —— 否则
    serve_forever 已经开始接请求、而这里还没跑到第一行，会有一个放行的窗口。
    """
    try:
        try:
            rec = recover_pending_dlc_load()
            if rec and rec.get("msg"):
                print(rec["msg"])
        except Exception:
            pass
        load_game_loc()
        for r in roots:
            r = os.path.abspath(r)
            if r not in ROOTS:
                ROOTS.append(r)
        refresh_start_date(ROOTS)
        # reload_data() 内部已经做了 for r in ROOTS: load_mod(r)，并且自己调了
        # link_countries() 与 _lp_done()。别再在它之前跑一遍 load_mod：成果会被它
        # 开头的 12 个 clear() 整个丢弃，白读 2.5 秒，pct 还会从 96 掉回 59。
        total = reload_data()
        if ROOTS:
            build_icons(ROOTS, GAME)
        else:
            print("未指定 mod：启动后请在网页里选择 mod 文件夹")
        print("已加载 mod:", len(ROOTS), " 树:", total)
        print("开局日期:", START_DATE_TEXT, "| STATES:", len(STATES))
        LOAD_PROGRESS["ready"] = True
    except Exception as e:
        import traceback
        traceback.print_exc()
        _lp_fail(e)
    finally:
        LOAD_PROGRESS["active"] = False
        LOAD_PROGRESS["t"] = time.time()


def main():
    global GAME
    _load_options()
    ap = argparse.ArgumentParser()
    ap.add_argument("--mod", action="append", default=None)
    ap.add_argument("--game", default=DEFAULT_GAME)
    ap.add_argument("--port", type=int, default=8766)
    args = ap.parse_args()
    GAME = args.game
    roots = args.mod or playset_load_saved()   # 没传 --mod 时用上次保存的播放集
    # 端口先起：页面 0.2 秒就出来，数据在后台线程里读，前端轮询 /api/boot_status
    # 显示进度。加载期间数据类请求由 _boot_gate 拦成 503 —— reload_data 会原地
    # 清空 12 个容器，半清空状态下读它们会 KeyError（全仓没有锁，也不为这个加锁）。
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    url = "http://127.0.0.1:%d/" % args.port
    print("打开:", url)
    _lp_begin("boot")
    LOAD_PROGRESS["active"] = True
    threading.Thread(target=_boot_load, args=(roots,), name="boot", daemon=True).start()
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    server.serve_forever()

from xuerong.model import history as _m_history
_m_history.bind(reload_data)
from xuerong.model import idea as _m_idea
_m_idea.bind(reload_data)
from xuerong.model import equipment as _m_equipment
_m_equipment.bind(reload_data)
from xuerong.model import tech as _m_tech
_m_tech.bind(reload_data)
from xuerong.model import event as _m_event
_m_event.bind(reload_data)
from xuerong.model import replace as _m_replace
_m_replace.bind(adopt_dir, snapshot, reload_data, ensure_file_writable)
_m_map.bind(load_units=load_units, _state_locate=_m_state._state_locate,
            _parse_state_provinces=_parse_state_provinces,
            _set_state_provinces=_set_state_provinces)
_m_map.set_progress_hook(_lp, begin=_lp_begin, done=_lp_done, fail=_lp_fail)
_m_state.bind(_all_prov_neighbors=_all_prov_neighbors,
              _hist_depths=_hist_depths, _hist_find_top=_hist_find_top,
              _refine_grow_units=_refine_grow_units,
              _parse_state_provinces=_parse_state_provinces,
              _set_state_provinces=_set_state_provinces,
              ensure_file_writable=ensure_file_writable,
              link_countries=link_countries,
              refresh_start_date=refresh_start_date,
              reload_data=reload_data)
from xuerong.model import world as _m_world
_m_world.bind(reload_data=reload_data, load_mod=load_mod, _lp_done=_lp_done)
from xuerong.model import focus as _m_focus
_m_focus.bind(reload_data=reload_data, lp=_lp)
from xuerong.model import character as _m_character
_m_character.bind(ensure_file_writable=ensure_file_writable)
_m_replace.set_ref_scanner(_diag_replace_refs)
_m_replace.set_progress_hook(_lp, begin=_lp_begin, done=_lp_done, fail=_lp_fail)


# ---- 路由表装配自检（必须在所有顶层名字定义完之后）----
# P3 时代这里调 `_router.install(globals())` 把门面的名字补进各 handler 模块的 globals。
# 2B 之后 handlers 全部改成显式的 `LG.xxx`（xuerong/core/facade_bridge.py）与正常的
# `from xuerong.model.xxx import ...`，install() 已删除，这里改成一条装配断言：
# 三张表任一为空就说明某个 handler 的 import 断了、那个域的装饰器没执行——
# 那种情况下服务照常起来，只是路由变 404，很难发现，所以启动期就炸掉更好。
_ROUTE_STATS = _router.stats()
assert _ROUTE_STATS["post"] and _ROUTE_STATS["get"] and _ROUTE_STATS["prefix"], (
    "路由表装配不完整：%r。检查 xuerong/api/handlers/__init__.py 的 import 名单"
    % (_ROUTE_STATS,))


# 17 个地图容器现在归 xuerong.state 所有；门面保留同名引用，
# 让路由（map_paint）和其它域（world_create / refine_*）继续用原来的名字。
# 只读/原地改，没有重新赋值，所以别名与 state 里的是同一个对象。
MAP_ASSETS = _state.map_var("MAP_ASSETS")
MAP_CACHE_DIR = _state.map_var("MAP_CACHE_DIR")
MAP_EDIT = _state.map_var("MAP_EDIT")
MAP_UNDO_DIR = _state.map_var("MAP_UNDO_DIR")
PROV_RGB = _state.map_var("PROV_RGB")
RIVER_KINDS = _state.map_var("RIVER_KINDS")
RIVER_KIND_IDX = _state.map_var("RIVER_KIND_IDX")
RIVER_LAND = _state.map_var("RIVER_LAND")
RIVER_SEA = _state.map_var("RIVER_SEA")
_NB_CACHE = _state.map_var("_NB_CACHE")
_REFINE_IDS_CACHE = _state.map_var("_REFINE_IDS_CACHE")
_RIVER_LAST = _state.map_var("_RIVER_LAST")
_RIVER_UNDO = _state.map_var("_RIVER_UNDO")
MAP_PALETTE = _state.map_var("MAP_PALETTE")
_DEF_RGB_CACHE = _state.map_var("_DEF_RGB_CACHE")
_PROV_RGB_CACHE = _state.map_var("_PROV_RGB_CACHE")
_REGION_CACHE = _state.map_var("_REGION_CACHE")


# 27 个州/省份函数现在在 xuerong.model.state；门面保留同名引用，
# 让 /api/state* 路由与其它域（country / diplomacy / world）继续用原来的名字。
_write_layer_hint = _state.layer_hint()
state_save = _m_state.state_save
state_create = _m_state.state_create
state_province_edit = _m_state.state_province_edit
state_refine_preview = _m_state.state_refine_preview
state_refine_apply = _m_state.state_refine_apply
state_apply_buildings = _m_state.state_apply_buildings
state_detail = _m_state.state_detail
_state_file_for = _m_state._state_file_for
_state_owner_effective = _m_state._state_owner_effective
states_payload = _m_state.states_payload
_state_prov_list = _m_state._state_prov_list
_state_fields_from = _m_state._state_fields_from
_states_dir_for_write = _m_state._states_dir_for_write
state_is_coastal = _m_state.state_is_coastal
_state_locate = _m_state._state_locate
_state_history_range = _m_state._state_history_range
_set_building = _m_state._set_building
_set_prov_building = _m_state._set_prov_building
_set_owner_all = _m_state._set_owner_all
_set_victory_points = _m_state._set_victory_points
_find_state_of_prov = _m_state._find_state_of_prov
_drop_in_scope = _m_state._drop_in_scope
_set_in_scope = _m_state._set_in_scope
_coastal_provinces = _m_state._coastal_provinces
_free_state_id = _m_state._free_state_id
_insert_pos = _m_state._insert_pos
_set_resource = _m_state._set_resource


# 启动入口必须放在文件最末：上面两个兼容别名区（17 个地图容器 + 27 个 state 函数）
# 是门面同名的落脚点，`python focus_editor.py` 直接运行时靠的就是它们。原先这行
# 写在别名区之前，`main()` 里 `serve_forever()` 一阻塞，别名区永远执行不到——
# refine_apply 第 2672 行读 `_REFINE_IDS_CACHE` 会直接 NameError，而 `import
# focus_editor`（测试与外部脚本的方式）因为整个模块执行完，看不出问题。
if __name__ == "__main__":
    main()

