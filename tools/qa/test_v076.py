# -*- coding: utf-8 -*-
"""v0.76 回归：地图上改省归属（省份在州之间移动）。"""
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
ST = os.path.join(MOD, 'history', 'states', '900-TestState.txt')


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=180) as r:
        return json.loads(r.read().decode())


def post(path, body):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(),
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read().decode())


STATE_900 = """state={
	id=900
	name="STATE_900"

	history = {
		1999.8.7 = {
			owner = TST
			victory_points = {
				111 1
			}
		}
		# 这是注释，别动
		owner = TSU
		buildings = {
			air_base = 1
			infrastructure = 2
			111 = {
				naval_base = 1
			}
		}
	}

	manpower = 200000
	state_category = large_city
	provinces={
		111
		222
		333
	}
}
"""

STATE_901 = """state={
	id=901
	name="STATE_901"
	provinces={
		444
	}
	manpower=5000
	state_category=town
}
"""


def write_states():
    d = os.path.join(MOD, 'history', 'states')
    os.makedirs(d, exist_ok=True)
    io.open(os.path.join(d, '900-TestState.txt'), 'w', encoding='utf-8', newline=chr(10)).write(STATE_900)
    io.open(os.path.join(d, '901-TestState2.txt'), 'w', encoding='utf-8', newline=chr(10)).write(STATE_901)


def main():
    fails = []

    def check(name, cond, extra=''):
        print(('PASS ' if cond else 'FAIL ') + name + (('  ' + str(extra)) if not cond else ''))
        if not cond:
            fails.append(name)

    base.build_fixture()
    write_states()
    try:
        post('/api/unload_mod', {'root': MOD})
    except Exception:
        pass
    post('/api/load_mod', {'path': MOD})

    st2 = os.path.join(os.path.dirname(ST), '901-TestState2.txt')

    d = get('/api/state?id=900')
    before = sorted(d.get('provinces') or [])
    check('初始 900 有 3 个省', before == [111, 222, 333], before)

    # 111 从 900 移到 901
    r = post('/api/state_province', {'pid': 111, 'target': 901})
    check('移动 ok', r.get('ok'), r.get('msg'))
    check('消息含 900 → 901', '900' in (r.get('msg') or '') and '901' in (r.get('msg') or ''), r.get('msg'))

    s900 = io.open(ST, encoding='utf-8').read()
    s901 = io.open(st2, encoding='utf-8').read()
    check('900 里没有 111 了', '\t\t111\n' not in s900, s900[-200:])
    check('901 里有 111 和 444', '\t\t111\n' in s901 and '\t\t444\n' in s901, s901)
    check('900 花括号平衡', s900.count('{') == s900.count('}'))
    check('901 花括号平衡', s901.count('{') == s901.count('}'))

    d900 = get('/api/state?id=900')
    d901 = get('/api/state?id=901')
    check('回读 900 = 2 省', sorted(d900.get('provinces') or []) == [222, 333], d900.get('provinces'))
    check('回读 901 = 2 省', sorted(d901.get('provinces') or []) == [111, 444], d901.get('provinces'))

    # 移出州（target 空）
    r2 = post('/api/state_province', {'pid': 222})
    check('移出 ok', r2.get('ok'), r2.get('msg'))
    s900b = io.open(ST, encoding='utf-8').read()
    check('900 里 222 没了', '\t\t222\n' not in s900b, s900b[-200:])

    # 重复移动
    r3 = post('/api/state_province', {'pid': 111, 'target': 901})
    check('已在目标州 → noop', r3.get('ok') and r3.get('noop'), r3)

    # 非法参数
    r4 = post('/api/state_province', {'pid': 0, 'target': 901})
    check('非法省 id 被拒', r4.get('ok') is False, r4)
    r5 = post('/api/state_province', {'pid': 111, 'target': 999999})
    check('不存在的州被拒', r5.get('ok') is False, r5.get('msg'))

    print('\n结果：', '全部通过' if not fails else ('失败 ' + str(fails)))
    return 0 if not fails else 1


if __name__ == '__main__':
    sys.exit(main())
