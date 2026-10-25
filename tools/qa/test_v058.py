# -*- coding: utf-8 -*-
"""v0.58 回归：历史编辑器补全（科技/oob/政党支持度）+ 省份建筑与胜利点。

用法（服务加载 qa/fixtures/country_mod，端口 8898）：
    python work/qa/test_v058.py
"""
import io
import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import test_country_save as base  # noqa: E402

BASE = os.environ.get('TEST_BASE', 'http://127.0.0.1:8898')
MOD = base.MOD
HIST = base.HIST
ST_DIR = os.path.join(MOD, 'history', 'states')
ST = os.path.join(ST_DIR, '900-TestState.txt')

EXTRA = """
oob = "TEST_OOB"
set_technology = {
	infantry_weapons = 1
	tech_support_weapons = 1
	support_weapons = 1
}
set_popularities = {
	democratic = 40
	fascism = 30
	communism = 10
	neutrality = 20
}
"""

STATE_TEXT = """state={
	id=900
	name="STATE_900"
	history = {
		1999.8.7 = {
			owner = TST
			victory_points = {
				111 1
				222 2
			}
		}
		# 注释保留测试
		owner = TST
		add_core_of = TST
		buildings = {
			infrastructure = 2
			arms_factory = 1
			111 = {
				naval_base = 1
			}
		}
	}
	manpower=100000
	state_category=town
	provinces={
		111 222 333
	}
}
"""


def build():
    base.build_fixture()
    with io.open(HIST, 'a', encoding='utf-8', newline='\n') as f:
        f.write(EXTRA)
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

    build()
    try:
        post('/api/unload_mod', {'root': MOD})
    except Exception:
        pass
    print('重载:', post('/api/load_mod', {'path': MOD}).get('msg'))

    # ---------- 历史补全 ----------
    d = get('/api/country_history?tag=TST')
    f = d.get('fields') or {}
    check('读到 oob', f.get('oob') == 'TEST_OOB', f.get('oob'))
    check('读到科技 3 项', sorted(f.get('techs') or []) == ['infantry_weapons', 'support_weapons', 'tech_support_weapons'], f.get('techs'))
    check('读到政党支持度', (f.get('popularities') or {}).get('democratic') == 40, f.get('popularities'))

    r = post('/api/country_save', {'tag': 'TST', 'fields': {
        'techs': ['infantry_weapons', 'tech_support_weapons'],
        'oob': 'NEW_OOB',
        'popularities': {'democratic': 55, 'fascism': 25, 'communism': 5, 'neutrality': 15}}})
    check('保存 ok', r.get('ok'), r.get('msg'))

    text = io.open(HIST, encoding='utf-8').read()
    check('tech block rewritten (one removed)', '\tsupport_weapons = 1' not in text, '')
    check('科技项还在', 'infantry_weapons = 1' in text)
    check('oob 改成 NEW_OOB', 'oob = "NEW_OOB"' in text, '')
    check('支持度改成 55', 'democratic = 55' in text)
    check('旧注释仍保留', '# 旧首都' in text or '# 这是注释' in text or 'capital = 200' in text)
    check('花括号平衡', text.count('{') == text.count('}'), (text.count('{'), text.count('}')))

    d2 = get('/api/country_history?tag=TST')
    f2 = d2.get('fields') or {}
    check('回读科技 2 项', len(f2.get('techs') or []) == 2, f2.get('techs'))
    check('回读 oob', f2.get('oob') == 'NEW_OOB', f2.get('oob'))
    check('回读支持度', (f2.get('popularities') or {}).get('fascism') == 25, f2.get('popularities'))

    # ---------- 省份编辑 ----------
    s = get('/api/state?id=900')
    check('省 111 现有 naval_base=1', (s.get('province_buildings') or {}).get('111', {}).get('naval_base') == 1,
          s.get('province_buildings'))

    r2 = post('/api/state_save', {'id': 900, 'fields': {
        'province_buildings': {'111': {'naval_base': 3, 'coastal_bunker': 2}, '222': {'naval_base': 1}},
        'victory_points': [[111, 5], [222, 2], [333, 1]]}})
    check('省份保存 ok', r2.get('ok'), r2.get('msg'))
    check('diff 含省份', any('省份' in (x.get('label') or '') for x in r2.get('diff') or []), r2.get('diff'))

    st = io.open(ST, encoding='utf-8').read()
    check('省 111 加了 coastal_bunker', 'coastal_bunker = 2' in st, '')
    check('省 111 naval_base 改 3', 'naval_base = 3' in st)
    check('新增省 222 块', '222 = {' in st)
    check('状态级建筑保留', 'infrastructure = 2' in st and 'arms_factory = 1' in st)
    check('胜利点更新到 3 处', st.count('111 5') == 1 and '333 1' in st, '')
    check('注释保留', '# 注释保留测试' in st)
    check('花括号平衡', st.count('{') == st.count('}'), (st.count('{'), st.count('}')))

    s2 = get('/api/state?id=900')
    check('回读省 111 建筑', (s2.get('province_buildings') or {}).get('111', {}).get('coastal_bunker') == 2,
          s2.get('province_buildings'))
    check('回读胜利点 3 处', len(s2.get('victory_points') or []) == 3, s2.get('victory_points'))

    # 省份建筑归零 → 删除该省块
    r3 = post('/api/state_save', {'id': 900, 'fields': {'province_buildings': {'222': {}}}})
    check('归零保存 ok', r3.get('ok'), r3.get('msg'))
    st2 = io.open(ST, encoding='utf-8').read()
    check('省 222 块被删掉', '222 = {' not in st2, '')

    print('\n结果：', '全部通过' if not fails else ('失败 ' + str(fails)))
    return 0 if not fails else 1


if __name__ == '__main__':
    sys.exit(main())
