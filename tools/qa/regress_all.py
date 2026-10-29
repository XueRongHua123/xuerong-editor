# -*- coding: utf-8 -*-
"""通用性回归：在多个真实 mod 上跑全部接口，任一异常或关键字段缺失即失败。

用法：
    python work/qa/regress_all.py              # 自动发现
    python work/qa/regress_all.py <mod1> ...   # 指定

规矩来源：AGENTS.md「通用性：不为单个 mod 写死」第 5 条。
"""
import io
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.dirname(HERE)
sys.path.insert(0, WORK)
import focus_editor as fe

GAME = r'E:\SteamLibrary\steamapps\common\Hearts of Iron IV'


def discover():
    roots = []
    ws = r'E:\SteamLibrary\steamapps\workshop\content\394360'
    if os.path.isdir(ws):
        for name in sorted(os.listdir(ws)):
            p = os.path.join(ws, name)
            if not os.path.isdir(p):
                continue
            if not os.path.exists(os.path.join(p, 'descriptor.mod')):
                continue
            if (os.path.exists(os.path.join(p, 'map', 'provinces.bmp'))
                    or os.path.isdir(os.path.join(p, 'history', 'states'))
                    or os.path.isdir(os.path.join(p, 'common', 'countries'))):
                roots.append(p)
    return roots


def _miss(r, keys):
    return [k for k in keys if not (isinstance(r, dict) and k in r)]


def probe(root):
    fe.GAME = GAME
    fe.ROOTS = [root]
    rows = []
    try:
        fe.load_game_loc()
        fe.load_mod(root)
    except Exception as e:
        return 0, 1, [('加载 mod', False, '%s: %s' % (type(e).__name__, e))]

    def run(name, fn, keys=(), min_count=None, count_key='count',
            skip_if=None):
        t0 = time.time()
        try:
            r = fn()
            ms = int((time.time() - t0) * 1000)
            if skip_if and skip_if(r):
                rows.append((name, True, 'SKIP（%s）%dms' % (skip_if(r), ms)))
                return
            if not isinstance(r, dict):
                rows.append((name, False, '返回不是 dict（%dms）' % ms))
                return
            if r.get('ok') is False:
                rows.append((name, False, '%s（%dms）' % (r.get('msg') or 'ok=False', ms)))
                return
            m = _miss(r, keys)
            if m:
                rows.append((name, False, '缺字段 %s（%dms）' % (','.join(m), ms)))
                return
            if min_count is not None:
                c = r.get(count_key)
                if not isinstance(c, int) or c < min_count:
                    rows.append((name, False, '%s=%s < %s（%dms）' % (count_key, c, min_count, ms)))
                    return
            extra = ''
            if 'count' in r:
                extra = 'count=%s' % r['count']
            elif isinstance(r.get('items'), list):
                extra = 'items=%d' % len(r['items'])
            rows.append((name, True, ('%s %dms' % (extra, ms)).strip()))
        except Exception as e:
            rows.append((name, False, '%s: %s' % (type(e).__name__, str(e)[:120])))

    run('国家 payload', fe.countries_payload, ('list', 'count'), min_count=1)
    run('州列表', lambda: {'ok': True, 'count': len(fe.STATES),
                           'list': list(fe.STATES.values())[:3]},
        ('count',), min_count=1)
    run('地图元信息', fe.map_meta, ('ok',))
    run('铁路列表', fe.railways_list, ('items', 'count', 'broken'))
    run('战略区', fe.strategic_regions_list, ('items', 'count'))
    run('补给区', fe.supply_areas, ('items',))
    run('海峡连接', fe.adjacencies_list, ('items', 'types'))
    run('地形类型', fe.terrain_types, ('items',), min_count=1)
    run('装备列表', lambda: fe.equipment_list(None, None), ('items', 'count'), min_count=1)
    run('国策树列表', fe.focus_tree_list, ('ok',))
    run('事件列表', lambda: {'ok': True, 'count': len(fe.EVENTS),
                             'items': list(fe.EVENTS)[:3]}, ('count',))
    # 图层完整性：没构建过就跳过（构建是用户手动触发的）
    run('图层完整性', fe.map_integrity, ('ok',),
        skip_if=lambda r: (not isinstance(r, dict)) or ('prov_id.png' in (r.get('msg') or '')))

    ok = sum(1 for _, p, _ in rows if p)
    return ok, len(rows), rows


def main():
    roots = sys.argv[1:] or discover()
    if not roots:
        print('没有找到可测 mod')
        return 1
    print('待测 mod：%d 个\n' % len(roots))
    total_ok = total_all = 0
    summary = []
    fail_detail = {}
    for r in roots:
        name = os.path.basename(r.rstrip('\\/'))
        print('=' * 66)
        print('MOD: %s' % name)
        ok, n, rows = probe(r)
        total_ok += ok
        total_all += n
        w = max((len(x[0]) for x in rows), default=10)
        for cname, passed, detail in rows:
            print('  %s %-*s %s' % ('PASS' if passed else 'FAIL', w, cname, detail))
            if not passed:
                fail_detail.setdefault(cname, []).append('%s: %s' % (name, detail))
        print('  → %d/%d' % (ok, n))
        summary.append((name, ok, n))
        print()

    print('=' * 66)
    print('汇总')
    w = max(len(x[0]) for x in summary)
    for name, ok, n in summary:
        print('  %s %-*s %d/%d' % ('OK  ' if ok == n else 'FAIL', w, name, ok, n))
    print('\n总计 %d/%d' % (total_ok, total_all))
    if fail_detail:
        print('\n失败项按接口归类：')
        for cname, lst in fail_detail.items():
            print('  %s（%d 个 mod）' % (cname, len(lst)))
            for x in lst[:3]:
                print('      ' + x)
    return 0 if total_ok == total_all else 1


if __name__ == '__main__':
    raise SystemExit(main())
