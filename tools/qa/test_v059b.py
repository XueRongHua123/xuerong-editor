# -*- coding: utf-8 -*-
"""v0.59 回归：初始外交 + 国策引用体检。

用法（服务加载 qa/fixtures/country_mod，端口 8898）：python work/qa/test_v059b.py
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
FOCUS_DIR = os.path.join(MOD, 'common', 'national_focus')

OPINION = """
add_opinion = {
	target = TSU
	value = 40
}
"""

FOCUS = """focus_tree = {
	id = tst_focus
	country = {
		factor = 0
		modifier = {
			add = 10
			tag = TST
		}
	}
	focus = {
		id = tst_root
		x = 0
		y = 0
		cost = 1
		completion_reward = {
			add_ideas = ghost_idea_not_exist
			country_event = { id = ghost.1 }
		}
	}
}
"""


def build():
    base.build_fixture()
    with io.open(HIST, 'a', encoding='utf-8', newline='\n') as f:
        f.write(OPINION)
    io.open(os.path.join(FOCUS_DIR, 'tst_focus.txt'), 'w', encoding='utf-8', newline='\n').write(FOCUS)


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=300) as r:
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

    d = get('/api/country_history?tag=TST')
    ops = (d.get('fields') or {}).get('opinions') or []
    check('读到 add_opinion', ops == [['TSU', 40]], ops)

    r = post('/api/country_save', {'tag': 'TST', 'fields': {
        'opinions': [['TSU', 60], ['TST', 10]]}})
    check('写回 ok', r.get('ok'), r.get('msg'))
    text = io.open(HIST, encoding='utf-8').read()
    check('两条 add_opinion', text.count('add_opinion') == 2, text.count('add_opinion'))
    check('值改成 60', 'value = 60' in text)
    check('新增 TST 10', 'target = TST' in text and 'value = 10' in text)
    check('花括号平衡', text.count('{') == text.count('}'), (text.count('{'), text.count('}')))

    d2 = get('/api/country_history?tag=TST')
    ops2 = (d2.get('fields') or {}).get('opinions') or []
    check('回读两条', sorted(ops2) == [['TST', 10], ['TSU', 60]], ops2)

    lint = get('/api/lint')
    focus_items = [i for i in lint.get('items', []) if i.get('kind') == 'focus']
    check('体检报出国策引用问题', len(focus_items) >= 2, focus_items[:2])
    check('报出 ghost_idea_not_exist', any('ghost_idea_not_exist' in i['title'] for i in focus_items), focus_items[:2])
    check('报出 ghost.1', any('ghost.1' in i['title'] for i in focus_items), focus_items[:2])

    print('\n结果：', '全部通过' if not fails else ('失败 ' + str(fails)))
    return 0 if not fails else 1


if __name__ == '__main__':
    sys.exit(main())
