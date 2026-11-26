# -*- coding: utf-8 -*-
"""世界编排：地图 → tag → 州 → 国家历史 → 军队 → 本地化 → 剧本；以及建 mod 骨架。

本模块是包里唯一的聚合点，依赖其余四个兄弟模块；world_create 里的
world_leader / focus_gen / world_events / world_loc / mapgen_scaffold 仍是函数内 import。
"""
import io
import os
import re

from xuerong import state
from xuerong.core.paths import (_find_mod_by_name, _mod_descriptor,
                                detect_game_version, pdx_user_dir,
                                qa_dir as _qa_dir)
from xuerong.model.map import _ensure_prov_rgb, map_generate
from xuerong.model.state import state_create
from xuerong.model.world._inj import _load_mod, _lp_done
from xuerong.model.world.bookmark import bookmark_add
from xuerong.model.world.country import country_history_create, country_tag_add
from xuerong.model.world.loc import loc_generate
from xuerong.model.world.units import template_add, unit_add

def _centroids_from_map(map_dir, notes=None):
    """从 map/definition.csv + provinces.bmp 反算每省像素质心。

    `world_create` 正常走 mapgen.generate，那边会直接把 centroids 返回；
    这个函数只是兜底：手工改过图、或从别的工具生成的 mod 也能补坐标表。

    返回空字典的两种情况含义完全不同：
      · map/ 下没这两个文件（返回空是正常结论，不报）
      · numpy / PIL / 图片读不开（返回空表示**没算**，必须能说出原因）
    第二种把原因写进 notes（可选 list），调用点拿去拼进步骤消息，
    否则界面上只剩「unitstacks 0 / buildings 0 / weather 0」，看不出是缺库。
    """
    cen = {}

    def _note(msg):
        if notes is not None:
            try:
                notes.append(msg)
            except Exception:
                pass

    map_dir = os.path.abspath(map_dir)
    csvp = os.path.join(map_dir, "definition.csv")
    provp = os.path.join(map_dir, "provinces.bmp")
    if not (os.path.isfile(csvp) and os.path.isfile(provp)):
        return cen
    try:
        import numpy as np
        from PIL import Image
    except Exception as e:
        # 分开写：ImportError 时说清缺哪个模块（exe 里缺 numpy 就是这个），
        # 其它异常说明是哪类错误。
        name = getattr(e, "name", "") or ""
        if isinstance(e, ImportError):
            _note("缺模块 %s，质心表未计算" % (name or str(e)))
        else:
            _note("加载 numpy/PIL 失败 %s: %s，质心表未计算"
                  % (e.__class__.__name__, e))
        return cen
    rgb2pid = {}
    with io.open(csvp, encoding="utf-8", errors="replace") as _f:
        for line in _f:
            p = line.strip().split(";")
            if len(p) < 4:
                continue
            try:
                rgb2pid[(int(p[1]), int(p[2]), int(p[3]))] = int(p[0])
            except Exception:
                continue
    try:
        im = Image.open(provp).convert("RGB")
    except Exception as e:
        _note("provinces.bmp 读不开 %s: %s，质心表未计算"
              % (e.__class__.__name__, e))
        return cen
    a = np.asarray(im, dtype=np.int32)
    h, w = a.shape[:2]
    keys = (a[:, :, 0] << 16) | (a[:, :, 1] << 8) | a[:, :, 2]
    flat = keys.reshape(-1)
    uniq, inv, cnt = np.unique(flat, return_inverse=True, return_counts=True)
    ys, xs = np.mgrid[0:h, 0:w]
    sx = np.bincount(inv, weights=xs.reshape(-1), minlength=len(uniq))
    sy = np.bincount(inv, weights=ys.reshape(-1), minlength=len(uniq))
    for i, k in enumerate(uniq):
        k = int(k)
        pid = rgb2pid.get(((k >> 16) & 255, (k >> 8) & 255, k & 255))
        if not pid or pid <= 0 or cnt[i] <= 0:
            continue
        cen[pid] = (round(sx[i] / cnt[i], 2), round(sy[i] / cnt[i], 2))
    return cen


def world_create(out_dir, source="procedural", width=1024, height=512,
                 n_provinces=40, min_size=300, seed=11, src_path=None,
                 sea_level=0.42, balance=True, min_province_px=800,
                 n_regions=None, n_supply=None,
                 tag="ZZV", country_name="新世界", color=None,
                 per_state=8, mod_name=None, army=True,
                 n_focus=24, focus_shape="tree", gen_focus=True,
                 gen_event=True, unit_name=None):
    """一键建世界：地图 → tag → 州 → 国家历史 → 军队 → 本地化 → 剧本。

    每一步都调用编辑器已有的函数（map_generate / country_tag_add /
    state_create / country_history_create / template_add / unit_add /
    loc_generate / bookmark_add / focus_gen / world_events / world_loc），
    不自己拼文件。任何一步失败都会记进 steps 并终止后续步骤，避免在半成品上继续叠加。

    A2 起多了三个参数：`n_focus`（国策节点数）、`focus_shape`（tree / chain）、
    `gen_focus` / `gen_event`（要不要真内容，关掉就是 A1 的空占位）。

    返回 {"ok", "steps": [{step, ok, msg}], "out_dir", "provinces", "states"}
    """
    steps = []
    out_dir = os.path.abspath(out_dir) if out_dir else ""

    def rec(name, r):
        ok = bool(r.get("ok")) if isinstance(r, dict) else bool(r)
        msg = (r.get("msg") if isinstance(r, dict) else "") or ""
        steps.append({"step": name, "ok": ok, "msg": msg})
        return ok

    if not out_dir:
        return {"ok": False, "msg": "要指定输出目录", "steps": steps}

    def done(extra=None):
        d = {"ok": all(s["ok"] for s in steps), "steps": steps,
             "out_dir": out_dir}
        if extra:
            d.update(extra)
        return d

    # 1) 地图（只出 map/，骨架交给下面的步骤）
    r = map_generate(source=source, out_dir=out_dir, width=width, height=height,
                     n_provinces=n_provinces, min_size=min_size, seed=seed,
                     src_path=src_path, sea_level=sea_level, balance=balance,
                     min_province_px=min_province_px,
                     n_regions=n_regions, n_supply=n_supply)
    if not rec("地图生成", r):
        return done()

    # 2) descriptor：mod_layers / country_tag_add / state_create 都靠它认出
    #    「这是一个 mod」，没有它后面每一步都会报「找不到可写的 mod 目录」。
    try:
        import mapgen_scaffold as _scaf
        _scaf.write_descriptor(out_dir, mod_name or country_name or "新世界")
        steps.append({"step": "写 descriptor", "ok": True, "msg": ""})
    except Exception as e:
        steps.append({"step": "写 descriptor", "ok": False, "msg": str(e)})
        return done()

    # 3) 重载，让 PROV_RGB / COUNTRIES 认识这张新图
    try:
        _load_mod(out_dir)
        _ensure_prov_rgb(out_dir)   # 懒加载，不主动触发就一直是空的
        _lp_done()
        steps.append({"step": "重载地图", "ok": True,
                      "msg": "%d 个省" % len(state.prov_rgb())})
    except Exception as e:
        _lp_done()
        steps.append({"step": "重载地图", "ok": False, "msg": str(e)})
        return done()

    n_prov = max(0, len(state.prov_rgb()) - 1)   # 去掉省 0

    # 3) tag 必须先存在，州和历史的 owner 才能引用
    if not rec("建国家 tag", country_tag_add(out_dir, tag, color)):
        return done()

    # 4) 按每州 per_state 个省切州，全部归这个 tag。
    #    必须只取陆省：HOI4 的州里一旦出现 sea 省，加载期直接报错退出。
    #    definition.csv 第 5 列是 land / sea，用它精确筛。
    land = []
    csvp = os.path.join(out_dir, "map", "definition.csv")
    try:
        with io.open(csvp, encoding="utf-8", errors="replace") as _f:
            for line in _f:
                parts = line.strip().split(";")
                if len(parts) >= 5 and parts[4].strip() == "land":
                    try:
                        pid = int(parts[0])
                    except Exception:
                        continue
                    if pid > 0:
                        land.append(pid)
    except Exception as e:
        steps.append({"step": "读 definition.csv", "ok": False, "msg": str(e)})
        return done()
    land.sort()
    made_states, first_state = 0, None
    state_map = []          # [(州号, [省号...])]，补给图要用真实州号
    try:
        step_n = int(per_state) if int(per_state) > 0 else 8
    except Exception:
        step_n = 8
    for i in range(0, len(land), step_n):
        pids = land[i:i + step_n]
        if not pids:
            continue
        r = state_create(pids, root=out_dir,
                         name="%s_%d" % (tag, made_states + 1),
                         owner=tag)
        if r.get("ok"):
            made_states += 1
            sid = r.get("id") or r.get("state") or made_states
            state_map.append((sid, list(pids)))
            if first_state is None:
                first_state = sid
        elif "已经存在" not in (r.get("msg") or ""):
            steps.append({"step": "建州 %d" % (made_states + 1),
                          "ok": False, "msg": r.get("msg") or ""})
            break
    steps.append({"step": "建州", "ok": made_states > 0,
                  "msg": "建成 %d 个州，每州 %d 省" % (made_states, step_n)})

    # 5) 国家历史：首都取第一个陆省
    capital = land[0] if land else 1
    rec("国家历史", country_history_create(
        out_dir, tag, capital=capital, name=country_name,
        oob=("%s_1936" % tag if army else None)))

    # 6) 开局部队（可选）
    if army:
        try:
            tres = template_add("%s_Infantry" % tag, "infantry",
                                root=out_dir, tag=tag)
            if rec("师团模板", tres):
                # A2-5 方案 B：直接给固定番号。番号组（division_names_group）
                # 需要 common/units/names_divisions 里有对应条目，那一步还没做，
                # 不写名字的话界面上就是一串空白。
                rec("开局部队", unit_add(capital, "%s_Infantry" % tag,
                                         name=unit_name or "第 1 步兵师",
                                         root=out_dir, tag=tag))
        except Exception as e:
            steps.append({"step": "军队", "ok": False, "msg": str(e)})

    # 7) 本地化占位
    try:
        rec("本地化", loc_generate(out_dir))
    except Exception as e:
        steps.append({"step": "本地化", "ok": False, "msg": str(e)})

    # 8) 剧本
    try:
        rec("剧本", bookmark_add(out_dir, country_name or mod_name or "新世界",
                                 "1936.1.1.12", default_country=tag,
                                 countries=[tag]))
    except Exception as e:
        steps.append({"step": "剧本", "ok": False, "msg": str(e)})

    # 8.5) 国家领袖：common/characters 被整目录屏蔽，不写就没有领袖，
    #      「选择国家」按钮会点了没反应（详见 qa/world_leader.py 开头）
    leader_loc = []
    try:
        import world_leader
        lr = world_leader.write(out_dir, tag, leader_name=(country_name or "新世界") + "领袖")
        leader_loc = lr["loc"]
        lk = world_leader.link_history(out_dir, tag, cid=lr.get("id"))
        steps.append({"step": "国家领袖", "ok": True,
                      "msg": "%s；%s" % (lr["path"], lk.get("msg") or "")})
    except Exception as e:
        steps.append({"step": "国家领袖", "ok": False, "msg": str(e)})

    # 9) 国策树（A2-1/A2-2）：一棵 15–30 节点的真树 + 中文名
    focus_text, focus_loc = None, []
    if gen_focus:
        try:
            import sys as _sys
            _qa = _qa_dir()
            if _qa not in _sys.path:
                _sys.path.insert(0, _qa)
            import focus_gen
            fr = focus_gen.build(tag=tag, n_focus=n_focus, shape=focus_shape)
            bad = focus_gen.check(fr["text"], tag)
            focus_text, focus_loc = fr["text"], fr["loc"]
            steps.append({"step": "国策树", "ok": not bad,
                          "msg": "%d 个节点 / %d 层%s" % (
                              len(fr["nodes"]), len(fr["layers"]),
                              "" if not bad else "：" + bad[0])})
        except Exception as e:
            steps.append({"step": "国策树", "ok": False, "msg": str(e)})

    # 10) 开局事件（A2-3）：一条 on_startup 触发的国家事件
    ev_text, oa_text, ev_loc = None, None, []
    if gen_event:
        try:
            import world_events
            er = world_events.build(tag=tag)
            ev_text, oa_text, ev_loc = er["events"], er["on_actions"], er["loc"]
            steps.append({"step": "开局事件", "ok": True,
                          "msg": er["event_id"]})
        except Exception as e:
            steps.append({"step": "开局事件", "ok": False, "msg": str(e)})

    # 11) 被 replace 的目录逐个补占位。
    #    这一步是「能加载」和「能进游戏」的分界：descriptor 里 50 条 replace_path
    #    声明了 50 个只从本 mod 读的目录，缺一个就有一个目录读空。
    #    最要命的是 common/national_focus —— 没有 default = yes 的树必崩，
    #    而且 error.log 一个字都不写（详见 qa/world_stubs.py 开头）。
    try:
        import sys as _sys
        _qa = _qa_dir()
        if _qa not in _sys.path:
            _sys.path.insert(0, _qa)
        import world_stubs
        ov = {}
        if focus_text:
            ov["common/national_focus"] = focus_text
        if ev_text:
            ov["events"] = ev_text
        if oa_text:
            ov["common/on_actions"] = oa_text
        made = world_stubs.write_all(out_dir, tag, overrides=ov)
        bad = [p for p in world_stubs.check(out_dir, dirs=world_stubs.REPLACE_DIRS)
               if p["level"] == "error"]
        steps.append({"step": "目录占位", "ok": not bad,
                      "msg": "%d 个目录" % len(made) if not bad
                             else bad[0]["dir"] + "：" + bad[0]["msg"]})
    except Exception as e:
        steps.append({"step": "目录占位", "ok": False, "msg": str(e)})

    # 10) 补给图：地图阶段不知道州号，这里按真实州号重写
    #     （早期版本把省号写进了 states={}，5 个州的地图写出 207 个州号）
    try:
        import mapgen_write as _mgw
        n_sa = _mgw.write_supply_graph(os.path.join(out_dir, "map"), state_map)
        steps.append({"step": "补给图", "ok": n_sa > 0,
                      "msg": "%d 个补给区 / %d 个补给节点" % (n_sa, len(state_map))})
    except Exception as e:
        steps.append({"step": "补给图", "ok": False, "msg": str(e)})

    # 12) 地标落点：unitstacks / buildings / weatherpositions
    #     这三张表的坐标是**地图像素坐标**，原版那份是 5632×2048 空间的，
    #     在我们 1024×512 的图上每个点都越界。必须按省质心重写。
    try:
        import mapgen_write as _mgw
        cen = (r or {}).get("centroids") or {}
        _cen_notes = []
        if not cen:
            cen = _centroids_from_map(os.path.join(out_dir, "map"), notes=_cen_notes)
        _sz = ((r or {}).get("width"), (r or {}).get("height"))
        mp = _mgw.write_map_positions(os.path.join(out_dir, "map"), cen,
                                      states=state_map,
                                      size=_sz if all(_sz) else None)
        # 三种情况要能区分：算出了坐标 / 图里本来就没有坐标可算 / 库缺失导致没算。
        # 以前后两种都只显示「unitstacks 0 / buildings 0 / weather 0」，看不出区别。
        _msg = ("unitstacks %d / buildings %d / weather %d"
                % (mp["unitstacks"], mp["buildings"], mp["weather"]))
        if _cen_notes:
            _msg = _msg + "；" + "；".join(_cen_notes)
        steps.append({"step": "地标落点", "ok": bool(cen), "msg": _msg})
    except Exception as e:
        steps.append({"step": "地标落点", "ok": False, "msg": str(e)})

    # 13) 世界本地化（A2-2 的国策名 + 国名 + 州名 + 事件文本）
    try:
        import world_loc
        entries = []
        entries += world_loc.country_entries(
            tag, country_name or "新世界",
            desc="%s，一个刚刚被造出来的国家。" % (country_name or "新世界"),
            adjective=(country_name or "新世界"))
        entries += world_loc.state_entries([s for s, _p in state_map])
        entries += focus_loc
        entries += ev_loc
        entries += leader_loc
        n_loc = world_loc.write(out_dir, entries)
        steps.append({"step": "世界本地化", "ok": n_loc >= 0,
                      "msg": "%d 条中文" % n_loc})
    except Exception as e:
        steps.append({"step": "世界本地化", "ok": False, "msg": str(e)})

    return done({"provinces": len(land), "states": made_states, "tag": tag,
                 "focus_nodes": len(focus_loc) // 2 if focus_loc else 0})


# 1x1 深蓝 PNG 兜底，保证无 PIL 环境也能写出合法 thumbnail.png
_FALLBACK_PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\x18\x26\x48"
    b"\x00\x00\x00\x3b\x00\x24\x95\xeb\xd8\x1e\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _write_placeholder_thumbnail(mod_root):
    """生成 256x256 thumbnail.png 占位图，减少发工坊前的手工步骤。"""
    out = os.path.join(mod_root, "thumbnail.png")
    try:
        from PIL import Image, ImageDraw
        w = h = 256
        img = Image.new("RGB", (w, h), (22, 32, 48))
        draw = ImageDraw.Draw(img)
        draw.rectangle([10, 10, w - 11, h - 11], outline=(196, 158, 86), width=3)
        draw.rectangle([20, 20, w - 21, h - 21], outline=(78, 104, 138), width=1)
        cx, cy = w // 2, h // 2
        draw.polygon([(cx, cy - 58), (cx + 58, cy), (cx, cy + 58), (cx - 58, cy)],
                     fill=(36, 54, 78), outline=(196, 158, 86))
        draw.polygon([(cx, cy - 30), (cx + 30, cy), (cx, cy + 30), (cx - 30, cy)],
                     fill=(196, 158, 86))
        img.save(out, format="PNG")
    except Exception:
        with io.open(out, "wb") as _f:
            _f.write(_FALLBACK_PNG_1X1)
    return out


def mod_home():
    return os.path.join(pdx_user_dir(), "mod")


def _resolve_dep_name(dep):
    """把目录路径、文件夹名或 mod 名统一解析成 descriptor.mod 的真实 name=。"""
    raw = str(dep or "").strip()
    if not raw:
        return ""
    dp = os.path.abspath(raw)
    if os.path.isdir(dp):
        return (_mod_descriptor(dp).get("name") or
                os.path.basename(dp.rstrip("\\/")))
    found = _find_mod_by_name(raw, extra_roots=state.roots())
    if found:
        return (_mod_descriptor(found).get("name") or
                os.path.basename(found.rstrip("\\/")))
    return raw


def create_mod(base, mod_id, name, version="0.1.0", game_version="",
               tree_id="", tag="", create_tree=True, dep=""):
    if not re.match(r'^[A-Za-z0-9_]+$', mod_id or ""):
        return False, "模组文件夹名只能包含字母、数字、下划线"
    base = os.path.abspath(base or mod_home())
    if not os.path.isdir(base):
        try:
            os.makedirs(base)
        except Exception as e:
            return False, "无法创建目录: %s" % e
    root = os.path.join(base, mod_id)
    if os.path.exists(root):
        return False, "目标文件夹已存在: " + root
    if create_tree:
        if not re.match(r'^[A-Za-z0-9_]+$', tree_id or ""):
            return False, "国策树 ID 只能包含字母、数字、下划线"
        if not re.match(r'^[A-Z][A-Z0-9]{1,5}$', tag or ""):
            return False, "国家 TAG 格式不正确（例如 GER、UNI）"
    game_version = (game_version or "").strip() or detect_game_version()
    # dep：做 submod 时依赖的本体。给了就在 descriptor 里写 dependencies，
    # 这样只加载本 mod 也能让 mod_layers 自动把本体补进叠加链——本体的
    # replace_path 才会生效，原版的数据才不会漏进来。
    # 做「从原版开始的新 mod」时留空，链里只有原版，行为不变。
    dep_name = _resolve_dep_name(dep)
    try:
        os.makedirs(root)
        _write_placeholder_thumbnail(root)
        desc = ['version="%s"' % version, 'tags={', '\t"Alternative History"', '}',
                'name="%s"' % name, 'supported_version="%s"' % game_version,
                'picture="thumbnail.png"']
        if dep_name:
            desc += ['dependencies={', '\t"%s"' % dep_name, '}']
        with io.open(os.path.join(root, "descriptor.mod"), "w", encoding="utf-8", newline="") as _f:
            _f.write("\r\n".join(desc) + "\r\n")
        # 启动器 .mod 文件
        if os.path.abspath(base) == os.path.abspath(mod_home()):
            launcher = "\r\n".join(desc + ['path="%s"' % root.replace("\\", "/")]) + "\r\n"
            with io.open(os.path.join(base, mod_id + ".mod"), "w", encoding="utf-8", newline="") as _f:
                _f.write(launcher)
        if create_tree:
            nf = os.path.join(root, "common", "national_focus")
            os.makedirs(nf)
            tree = """focus_tree = {
	id = %s

	country = {
		factor = 0
		modifier = {
			add = 10
			tag = %s
		}
	}
	default = no

	focus = {
		id = %s_root
		icon = GFX_goal_generic_national_unity
		x = 0
		y = 0
		cost = 1
	}
}
""" % (tree_id, tag, tree_id)
            with io.open(os.path.join(nf, "zz_%s_focus.txt" % mod_id), "w", encoding="utf-8", newline="") as _f:
                _f.write(tree)
            for lang, header, text in (("simp_chinese", "l_simp_chinese", "新国策"), ("english", "l_english", "New Focus")):
                d = os.path.join(root, "localisation", lang, "replace")
                os.makedirs(d)
                with io.open(os.path.join(d, "zz_%s_l_%s.yml" % (mod_id, lang)), "w",
                             encoding="utf-8", newline="") as _f:
                    _f.write("\ufeff%s:\r\n %s_root:0 \"%s\"\r\n" % (header, tree_id, text))
    except Exception as e:
        return False, "创建失败: %s" % e
    return True, "已创建模组: " + root
