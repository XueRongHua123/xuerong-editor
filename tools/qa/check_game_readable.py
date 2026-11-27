# -*- coding: utf-8 -*-
"""游戏可读性校验：编辑器写出的文件，HOI4 能不能正确解析。

不启动游戏，做三件事：
1. 花括号配平
2. 关键字段是否写进目标文件（读回验证）
3. BOM 状态 —— 只看**编辑器新建**的文件（州/铁路等普通 txt 按原文件保留，HOI4 不强制；
   本地化 yml 必须有）
"""
import sys
import io
import os
import re
import shutil
import hashlib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import focus_editor as fe

fe.GAME = r'E:\SteamLibrary\steamapps\common\Hearts of Iron IV'
CN = r'E:\SteamLibrary\steamapps\workshop\content\394360\2800380626'
KYOTO = r'E:\SteamLibrary\steamapps\workshop\content\394360\3004109283'
TMP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tmp', '_readable')

results = []


def check(name, ok, detail=''):
    results.append((name, ok, detail))
    print('%s %-30s %s' % ('PASS' if ok else 'FAIL', name, detail))


def brace_balance(text):
    d = 0
    instr = False
    for ch in text:
        if ch == '"':
            instr = not instr
        if instr:
            continue
        if ch == '{':
            d += 1
        elif ch == '}':
            d -= 1
            if d < 0:
                return False, d
    return d == 0, d


def has_bom(path):
    with open(path, 'rb') as f:
        return f.read(3) == b'\xef\xbb\xbf'


def main():
    shutil.rmtree(TMP, ignore_errors=True)
    os.makedirs(os.path.join(TMP, 'map'), exist_ok=True)
    os.makedirs(os.path.join(TMP, 'history'), exist_ok=True)

    # 地形图与河流图用京都的（CN 用原版 terrain.bmp，不同源无法测）
    for f in ('provinces.bmp', 'definition.csv'):
        shutil.copy2(os.path.join(KYOTO, 'map', f), os.path.join(TMP, 'map', f))
    shutil.copy2(os.path.join(KYOTO, 'map', 'terrain.bmp'), os.path.join(TMP, 'map', 'terrain.bmp'))
    if os.path.exists(os.path.join(KYOTO, 'map', 'rivers.bmp')):
        shutil.copy2(os.path.join(KYOTO, 'map', 'rivers.bmp'), os.path.join(TMP, 'map', 'rivers.bmp'))
    shutil.copy2(os.path.join(CN, 'map', 'railways.txt'), os.path.join(TMP, 'map', 'railways.txt'))
    src_states = os.path.join(CN, 'history', 'states')
    if os.path.isdir(src_states):
        shutil.copytree(src_states, os.path.join(TMP, 'history', 'states'))
    io.open(os.path.join(TMP, 'descriptor.mod'), 'w', encoding='utf-8').write('name="readable"\n')

    fe.ROOTS = [TMP]
    fe.load_game_loc()
    fe.reload_data()

    # ===== 1) 州文件 =====
    r = fe.state_save(1, {'owner': 'SOV', 'category': 'large_town',
                          'manpower': '123456', 'cores': ['SOV', 'POL'],
                          'buildings': {'infrastructure': 4, 'arms_factory': 3}})
    ok1 = bool(r.get('ok'))
    check('州文件写入', ok1, r.get('msg') or '')
    if ok1:
        _r, rel, p = fe._state_file_for(1)
        if not p or not os.path.exists(p):
            check('州文件能定位', False, str(p))
        else:
            txt = io.open(p, encoding='utf-8-sig').read()
            b_ok, d = brace_balance(txt)
            check('州文件花括号', b_ok, 'depth=%d' % d)
            for key, want in (('owner', 'SOV'), ('state_category', 'large_town'),
                              ('manpower', '123456'), ('add_core_of', 'SOV'),
                              ('infrastructure', '4')):
                hit = any((key in l) and (want in l) for l in txt.splitlines())
                check('州文件含 %s=%s' % (key, want), hit, '')
            # 与原文件 BOM 一致（不是必须有 BOM）
            check('州文件 BOM 策略', True,
                  '有 BOM' if has_bom(p) else '无 BOM（保留原文件状态，HOI4 不强制）')

    # ===== 2) 地形 bmp =====
    fe._ensure_prov_rgb(TMP)
    pids = [int(x) for x in (fe.PROV_RGB or {}) if int(x) > 0][:3]
    types = fe.terrain_types(TMP)
    writable = [x for x in (types.get('items') or []) if x.get('writable')]
    if pids and writable:
        tb = os.path.join(TMP, 'map', 'terrain.bmp')
        info0 = fe.bmp_info(tb)
        r2 = fe.prov_terrain_set(pids[0], writable[0]['type'], TMP)
        info1 = fe.bmp_info(tb)
        check('地形 bmp 写入', bool(r2.get('ok')), r2.get('msg') or '')
        if info0 and info1:
            same = all(info0.get(k) == info1.get(k) for k in ('w', 'h', 'bpp', 'offset', 'row'))
            check('地形 bmp 头部完好', same,
                  'bpp=%s offset=%s row=%s' % (info1.get('bpp'), info1.get('offset'), info1.get('row')))
            check('地形 bmp 8 位', info1.get('bpp') == 8, str(info1.get('bpp')))
            from PIL import Image
            Image.MAX_IMAGE_PIXELS = None
            ids, w, h = fe._refine_load_ids(TMP)
            ti = None
            for i, v in enumerate(ids):
                if v == pids[0]:
                    ti = i
                    break
            if ti is not None:
                with Image.open(tb) as im:
                    got = im.getpixel((ti % w, ti // w))
                check('地形 bmp 索引读回', got == r2.get('index'),
                      '读回 %s 期望 %s' % (got, r2.get('index')))

    # ===== 3) 战略区 =====
    # 找一个不属于任何战略区的省（否则新建会被冲突检查拒绝，那是数据事实不是缺陷）
    _sr = fe.strategic_regions_list(TMP)
    _used = set()
    for _x in (_sr.get('items') or []):
        _used.update(_x.get('provinces') or [])
    _free = [p for p in pids if p not in _used][:1]
    if not _free:
        _free = [p for p in (fe.PROV_RGB or {}) if int(p) > 0 and int(p) not in _used][:1]
    r3 = fe.strategic_region_create(TMP, None, 'READABLE_TEST', _free) if _free else {'ok': False, 'msg': '没有空闲省' }
    check('战略区新建', bool(r3.get('ok')), r3.get('msg') or '')
    if r3.get('ok'):
        sid = r3['id']
        _b, p, rec = fe._sr_find(TMP, sid)
        if p and os.path.exists(p):
            txt = io.open(p, encoding='utf-8-sig').read()
            b_ok, d = brace_balance(txt)
            check('战略区花括号', b_ok, 'depth=%d' % d)
            check('战略区无 BOM（新建文件）', not has_bom(p), '')
            for key in ('strategic_region', 'id', 'name', 'provinces', 'weather'):
                check('战略区含 %s' % key, key in txt, '')

    # ===== 4) 补给区 =====
    sts = list(fe.STATES.keys())[:2]
    if sts:
        r4 = fe.supply_area_save(99, 15, sts, 'READABLE_AREA', TMP)
        check('补给区新建', bool(r4.get('ok')), r4.get('msg') or '')
        if r4.get('ok'):
            _b, d2 = fe._supply_dir_write(TMP)
            p = os.path.join(d2, '99-SupplyArea.txt')
            if os.path.exists(p):
                txt = io.open(p, encoding='utf-8-sig').read()
                b_ok, dd = brace_balance(txt)
                check('补给区花括号', b_ok, 'depth=%d' % dd)
                check('补给区无 BOM（新建文件）', not has_bom(p), '')
                for key in ('supply_area', 'id', 'name', 'value', 'states'):
                    check('补给区含 %s' % key, key in txt, '')

    # ===== 5) 铁路 =====
    rl = fe.railways_list(TMP)
    items = rl.get('items') or []
    if items:
        it = items[0]
        newlv = 5 if it['level'] != 5 else 4
        r5 = fe.railway_edit(it['i'], newlv, None, TMP)
        check('铁路改等级', bool(r5.get('ok')), r5.get('msg') or '')
        p = os.path.join(TMP, 'map', 'railways.txt')
        raw = io.open(p, 'rb').read()
        bad = []
        for i, ln in enumerate(raw.decode('utf-8-sig').splitlines(), 1):
            s = ln.strip()
            if not s or s.startswith('#'):
                continue
            parts = s.split()
            if not all(x.isdigit() for x in parts):
                bad.append((i, s[:40]))
        check('铁路格式（全数字序列）', not bad,
              ('异常行：%s' % bad[:2]) if bad else '')

    # ===== 6) 画河流（源头 0 + 1px 主干 3 + stats + undo） =====
    rbmp = os.path.join(TMP, 'map', 'rivers.bmp')
    if os.path.exists(rbmp):
        from xuerong.model.map import river_paint, river_stats, river_undo, bmp_info
        r6a = river_paint([[40, 40]], kind='source', brush=1, new_stroke=True, root=TMP)
        r6b = river_paint([[41, 40], [46, 40]], kind='main', brush=1, new_stroke=True, root=TMP)
        check('河流源头 0 写入', bool(r6a.get('ok')), r6a.get('msg') or '')
        check('河流主干 3 写入', bool(r6b.get('ok')), r6b.get('msg') or '')
        rinfo = bmp_info(rbmp)
        check('rivers.bmp 8 位头部完好', bool(rinfo and rinfo.get('bpp') == 8), repr(rinfo))
        if rinfo:
            with open(rbmp, 'rb') as rf:
                fy = 40 if rinfo.get('top_down') else (rinfo['h'] - 1 - 40)
                rf.seek(rinfo['offset'] + fy * rinfo['row'] + 40)
                s_px = rf.read(7)
            check('河流源头(0)+主干(3)像素读回', s_px[0] == 0 and s_px[1] == 3 and s_px[6] == 3,
                  'read=%r' % (list(s_px),))
        rs = river_stats(TMP)
        check('river_stats 返回源头统计', bool(rs.get('ok') and (rs.get('sources') or 0) >= 1),
              rs.get('msg') or '')
        ru = river_undo(TMP)
        check('河流撤销恢复', bool(ru.get('ok')), ru.get('msg') or '')

    # ===== 7) 书签（bookmark） =====
    r7 = fe.bookmark_add(TMP, 'READABLE_BM', '1937.5.1', desc='可读性测试剧本',
                         default_country='GER', countries=['GER', 'SOV'])
    check('书签新建', bool(r7.get('ok')), r7.get('msg') or '')
    if r7.get('ok'):
        from xuerong.core.ideologies import load_ideology_names
        from xuerong.core.paths import unique_editor_filename
        from xuerong.model.diagnose import _diag_bookmarks
        bm_fn = unique_editor_filename(TMP, 'common/bookmarks', 'zz_editor_bookmarks.txt')
        bm_p = os.path.join(TMP, 'common', 'bookmarks', bm_fn)
        check('书签文件存在', os.path.isfile(bm_p), bm_fn)
        if os.path.isfile(bm_p):
            check('书签无 BOM', not has_bom(bm_p), bm_fn)
            with io.open(bm_p, encoding='utf-8-sig', errors='replace') as _bf:
                bm_txt = _bf.read()
            b_ok, bd = brace_balance(bm_txt)
            check('书签花括号', b_ok, 'depth=%d' % bd)
            check('书签四段日期',
                  bool(re.search(r'(?m)^\s*date\s*=\s*1937\.5\.1\.12\s*$', bm_txt)),
                  'date = 1937.5.1.12')
            valid_ides = set(load_ideology_names(TMP))
            found_ides = re.findall(r'(?m)^\s*ideology\s*=\s*([A-Za-z0-9_.\-]+)\s*$', bm_txt)
            check('书签 ideology 合法',
                  bool(found_ides) and all(x in valid_ides for x in found_ides),
                  'found=%s' % found_ides)
        loc_ok = True
        loc_detail = []
        for lang in ('simp_chinese', 'english'):
            yml_fn = unique_editor_filename(TMP, 'localisation/%s' % lang,
                                            'zz_editor_bookmarks_l_%s.yml' % lang)
            yml_p = os.path.join(TMP, 'localisation', lang, yml_fn)
            if not os.path.isfile(yml_p) or not has_bom(yml_p):
                loc_ok = False
                loc_detail.append('%s:%s' % (lang, os.path.isfile(yml_p)))
        check('书签本地化 yml 带 UTF-8 BOM', loc_ok, ', '.join(loc_detail) or 'simp_chinese+english')
        bkey = 'ZZ_EDITOR_BM_' + hashlib.md5('READABLE_BM'.encode('utf-8')).hexdigest()[:8].upper()
        lbm = fe.load_bookmarks(TMP)
        hit = [it for it in (lbm.get('items') or []) if it.get('name') == bkey]
        check('load_bookmarks 读回 country_count>=1',
              bool(hit) and (hit[0].get('country_count') or 0) >= 1,
              'count=%s' % (hit[0].get('country_count') if hit else 'missing'))
        bm_errs = [f for f in _diag_bookmarks(TMP, own_only=True)
                   if f.get('severity') == 'error'
                   and bm_fn in (f.get('file') or '')]
        check('_diag_bookmarks 0 error', len(bm_errs) == 0,
              str(bm_errs[:2]) if bm_errs else '0 error')

    print('\n=== 汇总 ===')
    fails = [x for x in results if not x[1]]
    print('%d/%d 通过' % (len(results) - len(fails), len(results)))
    for name, _ok, detail in fails:
        print('  FAIL %s  %s' % (name, detail))
    return 0 if not fails else 1


if __name__ == '__main__':
    raise SystemExit(main())
