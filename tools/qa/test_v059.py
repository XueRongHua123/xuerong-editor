# -*- coding: utf-8 -*-
"""v0.59 科技树位置写回回归。

用法（服务加载 qa/fixtures/country_mod，端口 8898）：
    python work/qa/test_v059.py
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
TECH_DIR = os.path.join(MOD, 'common', 'technologies')
TECH = os.path.join(TECH_DIR, 'test_tech.txt')

TECH_TEXT = """technologies = {
	@1936 = 2

	test_tech_a = {
		start_year = 1936
		research_cost = 1
		# 注释要保留
		folder = {
			name = test_folder
			position = { x = 0 y = @1936 }
		}
		path = {
			leads_to_tech = { test_tech_b }
		}
	}

	test_tech_b = {
		start_year = 1937
		folder = {
			name = test_folder
			position = { x = 1 y = 3 }
		}
	}

	test_tech_c = {
		start_year = 1938
		folder = {
			name = test_folder
		}
	}
}
"""


def build():
    base.build_fixture()
    os.makedirs(TECH_DIR, exist_ok=True)
    io.open(TECH, 'w', encoding='utf-8', newline='\n').write(TECH_TEXT)


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

    d = get('/api/data')
    techs = {t['id']: t for t in d.get('techs', [])}
    check('读到 3 个科技', len([k for k in techs if k.startswith('test_tech')]) == 3, list(techs)[:5])
    a = techs.get('test_tech_a') or {}
    check('a 的 folder', a.get('path') == 'test_folder', a.get('path'))
    check('a 的坐标 x=0 y=2（宏解析）', a.get('fx') == 0 and a.get('fy') == 2, (a.get('fx'), a.get('fy')))
    b = techs.get('test_tech_b') or {}
    check('b 的坐标 1,3', b.get('fx') == 1 and b.get('fy') == 3, (b.get('fx'), b.get('fy')))

    rel = a.get('file') or 'common/technologies/test_tech.txt'
    r = post('/api/tech_move', {'root': MOD, 'rel': rel, 'tid': 'test_tech_a', 'x': 2, 'y': 5})
    check('移动 ok', r.get('ok'), r.get('msg'))

    text = io.open(TECH, encoding='utf-8').read()
    check('a 坐标改成 2,5', 'position = { x = 2 y = 5 }' in text, text[:400])
    check('folder name 保留', 'name = test_folder' in text)
    check('注释保留', '# 注释要保留' in text)
    check('宏定义保留', '@1936 = 2' in text)
    check('path 块保留', 'leads_to_tech = { test_tech_b }' in text)
    check('花括号平衡', text.count('{') == text.count('}'), (text.count('{'), text.count('}')))

    r2 = post('/api/tech_move', {'root': MOD, 'rel': rel, 'tid': 'test_tech_c', 'x': 4, 'y': 1})
    check('无 position 时插入 ok', r2.get('ok'), r2.get('msg'))
    text2 = io.open(TECH, encoding='utf-8').read()
    check('c 插入了 position', 'test_tech_c' in text2 and 'position = { x = 4 y = 1 }' in text2)
    check('插完仍平衡', text2.count('{') == text2.count('}'), (text2.count('{'), text2.count('}')))

    r3 = post('/api/tech_move', {'root': MOD, 'rel': rel, 'tid': 'no_such_tech', 'x': 1, 'y': 1})
    check('不存在的科技被拒', r3.get('ok') is False, r3.get('msg'))
    r4 = post('/api/tech_move', {'root': os.path.dirname(os.path.abspath(__file__)), 'rel': rel,
                                 'tid': 'test_tech_a', 'x': 1, 'y': 1})
    check('非法 root 被拒', r4.get('ok') is False, r4.get('msg'))

    d2 = get('/api/data')
    t2 = {t['id']: t for t in d2.get('techs', [])}
    check('回读 a 新坐标', (t2.get('test_tech_a') or {}).get('fx') == 2 and (t2.get('test_tech_a') or {}).get('fy') == 5,
          (t2.get('test_tech_a') or {}).get('fx'))

    print('\n结果：', '全部通过' if not fails else ('失败 ' + str(fails)))
    return 0 if not fails else 1


if __name__ == '__main__':
    sys.exit(main())
