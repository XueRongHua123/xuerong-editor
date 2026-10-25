# -*- coding: utf-8 -*-
"""v0.57 州写回回归：owner / cores / manpower / category / 建筑，保留注释与省份子块。

用法：
    python work/focus_editor.py --mod work/qa/fixtures/country_mod --port 8898
    python work/qa/test_state_save.py [--keep]
"""
import io
import json
import os
import sys
import urllib.request

BASE = os.environ.get('TEST_BASE', 'http://127.0.0.1:8898')
HERE = os.path.dirname(os.path.abspath(__file__))
MOD = os.path.join(HERE, 'fixtures', 'country_mod')
ST_DIR = os.path.join(MOD, 'history', 'states')
ST = os.path.join(ST_DIR, '900-TestState.txt')

STATE_TEXT = """state={
\tid=900
\tname="STATE_900"

\thistory = {
\t\t1999.8.7 = {
\t\t\towner = TST
\t\t\tvictory_points = {
\t\t\t\t111 1
\t\t\t\t222 2
\t\t\t}
\t\t}
\t\t# 这是注释，别动
\t\towner = TST
\t\tadd_core_of = TST
\t\tbuildings = {
\t\t\tinfrastructure = 2
\t\t\tarms_factory = 1
\t\t\t111 = {
\t\t\t\tnaval_base = 1
\t\t\t}
\t\t}
\t}

\tmanpower=100000
\tstate_category=town
\tprovinces={
\t\t111 222 333
\t}
}
"""


def build():
    os.makedirs(ST_DIR, exist_ok=True)
    io.open(ST, 'w', encoding='utf-8', newline='\n').write(STATE_TEXT)


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=180) as r:
        return json.loads(r.read().decode())


def post(path, body):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(),
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read().decode())


def main():
    fails = []

    def check(name, cond, extra=''):
        print(('PASS ' if cond else 'FAIL ') + name + (('  ' + str(extra)) if not cond else ''))
        if not cond:
            fails.append(name)

    if '--keep' not in sys.argv:
        build()
        try:
            post('/api/unload_mod', {'root': MOD})
        except Exception:
            pass
        print('重载:', post('/api/load_mod', {'path': MOD}).get('msg'))

    lst = get('/api/states')
    check('州列表含 900', any(x['id'] == 900 for x in (lst.get('list') or [])), lst.get('count'))
    row = [x for x in lst['list'] if x['id'] == 900][0]
    check('列表 owner=TST', row['owner'] == 'TST', row['owner'])
    check('列表 省份数 3', row['provinces'] == 3, row['provinces'])

    d = get('/api/state?id=900')
    check('详情 ok', d.get('ok'))
    check('owner TST', d['owner'] == 'TST', d['owner'])
    check('cores [TST]', d['cores'] == ['TST'], d['cores'])
    check('manpower', d['manpower'] == '100000', d['manpower'])
    check('category town', d['category'] == 'town', d['category'])
    check('建筑状态级', d['buildings'] == {'infrastructure': 2, 'arms_factory': 1}, d['buildings'])
    check('省份建筑只读解析', d['province_buildings'].get('111') == {'naval_base': 1}, d['province_buildings'])
    check('胜利点 2 处', len(d['victory_points']) == 2, d['victory_points'])
    check('可写', d['writable'] is True)

    r = post('/api/state_save', {'id': 900, 'fields': {
        'owner': 'TSU', 'cores': ['TST', 'TSU'], 'manpower': '200000',
        'category': 'large_city', 'buildings': {'arms_factory': 3, 'air_base': 1}}})
    check('保存 ok', r.get('ok'), r.get('msg'))
    check('diff 至少 4 条', len(r.get('diff') or []) >= 4, r.get('diff'))

    text = io.open(ST, encoding='utf-8').read()
    check('owner 改成 TSU', 'owner = TSU' in text, '')
    check('注释保留', '# 这是注释，别动' in text)
    check('province 子块保留', '111 = {' in text and 'naval_base = 1' in text)
    check('cores 两条', text.count('add_core_of') == 2, text.count('add_core_of'))
    check('arms_factory 改 3', 'arms_factory = 3' in text)
    check('新增 air_base 1', 'air_base = 1' in text)
    check('manpower 改 200000', 'manpower=200000' in text or 'manpower = 200000' in text)
    check('category 改 large_city', 'large_city' in text)
    check('花括号平衡', text.count('{') == text.count('}'), (text.count('{'), text.count('}')))

    d2 = get('/api/state?id=900')
    check('回读 owner TSU', d2['owner'] == 'TSU', d2['owner'])
    check('回读 cores 2', sorted(d2['cores']) == ['TST', 'TSU'], d2['cores'])
    check('回读建筑', d2['buildings'].get('arms_factory') == 3 and d2['buildings'].get('air_base') == 1, d2['buildings'])

    bad = post('/api/state_save', {'id': 900, 'fields': {'owner': 'ZZZ'}})
    check('非法 owner 被拒', bad.get('ok') is False, bad.get('msg'))
    bad2 = post('/api/state_save', {'id': 900, 'fields': {'category': 'huge'}})
    check('非法类别被拒', bad2.get('ok') is False, bad2.get('msg'))
    bad3 = post('/api/state_save', {'id': 900, 'fields': {'manpower': 'abc'}})
    check('非法人力被拒', bad3.get('ok') is False, bad3.get('msg'))

    print('\n结果：', '全部通过' if not fails else ('失败 ' + str(fails)))
    return 0 if not fails else 1


if __name__ == '__main__':
    sys.exit(main())
