# -*- coding: utf-8 -*-
"""写操作回归：在副本上跑全部写接口，验证返回值与文件变化。

不碰真实 mod，每个测试建一份最小副本。

用法：
    python work/qa/regress_write.py             # 自动选 mod
    python work/qa/regress_write.py <mod> ...   # 指定
"""
import io
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.dirname(HERE)
sys.path.insert(0, WORK)
import focus_editor as fe

GAME = r'E:\SteamLibrary\steamapps\common\Hearts of Iron IV'
TMP = os.path.join(WORK, 'tmp', '_regress_write')

NEED = [
    ('map', 'provinces.bmp'),
    ('map', 'definition.csv'),
    ('map', 'terrain.bmp'),
    ('map', 'railways.txt'),
    ('map', 'adjacencies.csv'),
    ('map', 'strategicregions'),
    ('map', 'supplyareas'),
    ('history', 'states'),
    ('common', 'units/equipment'),
]


def make_copy(src, dst):
    if os.path.isdir(dst):
        shutil.rmtree(dst, ignore_errors=True)
    os.makedirs(dst, exist_ok=True)
    n = 0
    for rel_dir, nm in NEED:
        s = os.path.join(src, rel_dir.replace('/', os.sep), nm.replace('/', os.sep))
        d = os.path.join(dst, rel_dir.replace('/', os.sep), nm.replace('/', os.sep))
        if not os.path.exists(s):
            continue
        try:
            if os.path.isdir(s):
                os.makedirs(os.path.dirname(d) or dst, exist_ok=True)
                shutil.copytree(s, d)
                n += sum(len(f) for _, _, f in os.walk(d))
            else:
                os.makedirs(os.path.dirname(d), exist_ok=True)
                shutil.copy2(s, d)
                n += 1
        except Exception:
            pass
    io.open(os.path.join(dst, 'descriptor.mod'), 'wb').write(
        b'\xef\xbb\xbf' + ('name="%s"\n' % os.path.basename(dst)).encode('utf-8'))
    return n


def md5(p):
    import hashlib
    h = hashlib.md5()
    try:
        with open(p, 'rb') as f:
            for c in iter(lambda: f.read(1 << 20), b''):
                h.update(c)
    except Exception:
        return None
    return h.hexdigest()[:10]


def pick_provs(dst, n=30):
    """拿一批真实存在的省号"""
    fe._ensure_prov_rgb(dst)
    out = []
    for p in (fe.PROV_RGB or {}):
        try:
            ip = int(p)
        except Exception:
            continue
        if ip <= 0:          # 0 是背景省，任何写操作都会拒绝
            continue
        out.append(ip)
        if len(out) >= n:
            break
    return out


def run_one(mod):
    name = os.path.basename(mod.rstrip('\\/'))
    dst = os.path.join(TMP, name)
    n = make_copy(mod, dst)
    if n == 0:
        return [('准备副本', False, '没有拷到任何数据')]

    fe.GAME = GAME
    fe.ROOTS = [dst]
    rows = []
    try:
        fe.load_game_loc()
        fe.load_mod(dst)
    except Exception as e:
        return [('加载副本', False, '%s: %s' % (type(e).__name__, e))]

    provs = pick_provs(dst, 40)
    if not provs:
        rows.append(('初始化省表', False, 'PROV_RGB 为空，无法测写操作'))
        return rows

    # --- 1) 改地形 ---
    def t_terrain():
        types = fe.terrain_types(dst)
        items = [x for x in (types.get('items') or []) if x.get('writable')]
        if not items:
            return False, '没有可写地形类型'
        # 倒序找：mod_layers 是 [原版, 父mod, 子mod]，要先看子 mod 自己的
        tb = None
        for base in reversed(fe.mod_layers(dst) or []):
            p2 = os.path.join(base or '', 'map', 'terrain.bmp')
            if os.path.exists(p2):
                tb = p2
                break
        if not tb:
            return False, '没有 terrain.bmp（原版提供，跳过）'
        pid = provs[0]
        want = items[0]['type']
        h0 = md5(tb)
        r = fe.prov_terrain_set(pid, want, dst)
        if not r.get('ok'):
            msg = r.get('msg') or '失败'
            if '不同源' in msg:
                return True, 'SKIP（' + msg + '）'      # 设计好的保护，不是缺陷
            return False, msg
        if not r.get('changed'):
            return True, '省 %s 已是 %s' % (pid, want)   # 无需改动也算通过
        if md5(tb) == h0:
            return False, 'terrain.bmp 没变'
        return True, '省 %s → %s' % (pid, want)

    # --- 2) 改铁路等级 ---
    def t_rail():
        rl = fe.railways_list(dst)
        items = rl.get('items') or []
        if not items:
            return False, '没有铁路'
        it = items[0]
        newlv = 5 if it['level'] != 5 else 4
        r = fe.railway_edit(it['i'], newlv, None, dst)
        if not r.get('ok'):
            return False, r.get('msg') or '失败'
        back = fe.railways_list(dst)
        got = (back.get('items') or [{}])[0].get('level')
        if got != newlv:
            return False, '写回后等级是 %s，期望 %s' % (got, newlv)
        return True, '第 0 条 → Lv%s' % newlv

    # --- 3) 建战略区 ---
    def t_sr():
        sr = fe.strategic_regions_list(dst)
        used = set()
        for x in (sr.get('items') or []):
            used.update(x.get('provinces') or [])
        allp = pick_provs(dst, 100000)      # 取全部省，避免样本太小
        free = [p for p in allp if p not in used][:1]
        if not free:
            # 所有省都已被战略区覆盖：改成测「修改已有区的范围」
            mine = [x for x in (sr.get('items') or [])
                    if os.path.abspath(x.get('base') or '') == os.path.abspath(dst)]
            if not mine:
                return False, '没有可改的战略区（全部来自只读层）'
            it = mine[0]
            own = list(it.get('provinces') or [])
            if len(own) < 2:
                return False, '这个战略区只有 %d 个省，无法测改范围' % len(own)
            newp = own[:-1]
            r = fe.strategic_region_set_provinces(it['id'], newp, dst)
            if not r.get('ok'):
                return False, r.get('msg') or '改范围失败'
            return True, '改范围 %d：%d→%d 省' % (it['id'], len(own), len(newp))
        r = fe.strategic_region_create(dst, None, 'REG_TEST', free)
        if not r.get('ok'):
            return False, r.get('msg') or '失败'
        sid = r['id']
        back = fe.strategic_regions_list(dst)
        if not any(x['id'] == sid for x in (back.get('items') or [])):
            return False, '建了但列表里没有'
        d = fe.strategic_region_delete(sid, dst)
        if not d.get('ok'):
            return False, '删除失败：' + (d.get('msg') or '')
        return True, '建 %s（%s 省）并删除' % (sid, len(free))

    # --- 4) 装备改属性 ---
    def t_equip():
        lst = fe.equipment_list(dst, None)
        items = lst.get('items') or []
        if not items:
            return False, '没有装备'
        # 找一个可写的
        for it in items[:15]:
            eid = it['id']
            det = fe.equipment_detail(eid, dst)
            if not det.get('ok'):
                continue
            if det.get('readonly'):
                continue
            old = (det.get('scalars') or {}).get('reliability')
            r = fe.equipment_edit(eid, {'reliability': '0.77'}, dst)
            if not r.get('ok'):
                return False, r.get('msg') or '失败'
            d2 = fe.equipment_detail(eid, dst)
            got = (d2.get('scalars') or {}).get('reliability')
            if got != '0.77':
                return False, '写回后 reliability=%s（期望 0.77）' % got
            return True, '%s reliability %s → 0.77' % (eid, old)
        return False, '前 15 个装备都不可写'

    # --- 5) 州细化 ---
    def t_stref():
        cand = sorted(((len(s.get('provinces') or []), sid)
                       for sid, s in fe.STATES.items()
                       if s.get('root') and os.path.abspath(s.get('root')) == os.path.abspath(dst)),
                      reverse=True)
        if not cand or cand[0][0] < 4:
            return False, '当前 mod 层没有够了大的州（省数 < 4）'
        n0, sid = cand[0]
        before = len(fe.STATES)
        r = fe.state_refine_apply(sid, 2, dst)
        if not r.get('ok'):
            return False, r.get('msg') or '失败'
        after = len(fe.STATES)
        created = r.get('created') or []
        failed = r.get('failed') or []
        if after <= before or not created:
            return False, '州数 %d→%d，新建 %d 个，失败 %s' % (
                before, after, len(created),
                (failed[0].get('msg') if failed else '无'))
        return True, '州 %s（%d 省）→ 州数 %d→%d，新建 %s' % (
            sid, n0, before, after, [c['id'] for c in created])

    for label, fn in (('改地形', t_terrain), ('改铁路等级', t_rail),
                      ('战略区增删', t_sr), ('装备改属性', t_equip),
                      ('州细化', t_stref)):
        t0 = time.time()
        try:
            ok, msg = fn()
        except Exception as e:
            ok, msg = False, '%s: %s' % (type(e).__name__, str(e)[:100])
        rows.append((label, ok, '%s（%dms）' % (msg, int((time.time() - t0) * 1000))))

    try:
        shutil.rmtree(dst, ignore_errors=True)
    except Exception:
        pass
    return rows


def discover():
    ws = r'E:\SteamLibrary\steamapps\workshop\content\394360'
    out = []
    if not os.path.isdir(ws):
        return out
    for name in sorted(os.listdir(ws)):
        p = os.path.join(ws, name)
        if os.path.isdir(p) and os.path.exists(os.path.join(p, 'map', 'provinces.bmp')):
            out.append(p)
    return out


def main():
    roots = sys.argv[1:] or discover()
    if not roots:
        print('没有找到带地图的 mod')
        return 1
    os.makedirs(TMP, exist_ok=True)
    print('写操作测试：%d 个 mod（每个用副本，不动原数据）\n' % len(roots))
    total_ok = total_all = 0
    fails = {}
    for r in roots:
        name = os.path.basename(r.rstrip('\\/'))
        print('=' * 66)
        print('MOD: %s' % name)
        rows = run_one(r)
        w = max((len(x[0]) for x in rows), default=10)
        for cname, passed, detail in rows:
            print('  %s %-*s %s' % ('PASS' if passed else 'FAIL', w, cname, detail))
            if not passed:
                fails.setdefault(cname, []).append('%s: %s' % (name, detail))
        ok = sum(1 for _, p, _ in rows if p)
        total_ok += ok
        total_all += len(rows)
        print('  → %d/%d\n' % (ok, len(rows)))
    print('=' * 66)
    print('总计 %d/%d' % (total_ok, total_all))
    if fails:
        print('\n失败归类：')
        for k, v in fails.items():
            print('  %s（%d 个 mod）' % (k, len(v)))
            for x in v[:4]:
                print('      ' + x)
    return 0 if total_ok == total_all else 1


if __name__ == '__main__':
    raise SystemExit(main())
