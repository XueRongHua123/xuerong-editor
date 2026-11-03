# -*- coding: utf-8 -*-
"""最小测试模组：不接管任何目录、不做 replace_path，只往 CN 上叠加新内容。

之前接管目录的做法会断掉 CN 内部的交叉引用（decisions 引用 categories、
国策引用 idea、history 引用 state 等），而且接管多少个目录都不够。
改成纯叠加：CN 的数据一条不动，只新增自己的东西。
"""
import sys
import os
import io
import json
import shutil
import time
import threading
import urllib.request

WORK = r'D:\大肥鱼工作区\HOI4 MUVLUVsub mod 制作\work'
GAME = r'E:\SteamLibrary\steamapps\common\Hearts of Iron IV'
CN = r'E:\SteamLibrary\steamapps\workshop\content\394360\2800380626'
BASE = os.path.join(WORK, 'tmp', '_testmod2')
OUT = os.path.join(BASE, 'xuerong_test')
PORT = 8991
URL = 'http://127.0.0.1:%d' % PORT

shutil.rmtree(BASE, ignore_errors=True)
os.makedirs(OUT)
io.open(os.path.join(OUT, 'descriptor.mod'), 'w', encoding='utf-8').write(
    'name="雪绒测试模组"\nversion="1.0.0"\n')

sys.path.insert(0, WORK)
import focus_editor as fe
from http.server import ThreadingHTTPServer

fe.GAME = GAME
fe.ROOTS = [CN, OUT]
fe.load_game_loc()
fe.reload_data()
srv = ThreadingHTTPServer(('127.0.0.1', PORT), fe.Handler)
threading.Thread(target=srv.serve_forever, daemon=True).start()
time.sleep(2)


def P(path, body=None):
    req = urllib.request.Request(URL + path, data=json.dumps(body or {}).encode(),
                                 method='POST')
    req.add_header('Content-Type', 'application/json')
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        return {'ok': False, 'msg': str(e)[:70]}


log = []


def step(name, path, body=None):
    r = P(path, body)
    ok = r.get('ok') is not False
    msg = (r.get('msg') or '')[:58]
    log.append((name, ok, msg))
    print('  %s %-22s %s' % ('OK ' if ok else 'FAIL', name, msg))
    return r


print('=== 纯叠加：不接管、不 replace ===')
print()
print('=== 1) 新国家 TAG ===')
step('tag_add', '/api/country_tag_add',
     {'tag': 'XTT', 'color': [70, 140, 200], 'culture': 'western_european_gfx'})

print()
print('=== 2) 人物 ===')
step('char add', '/api/character_add',
     {'id': 'XTT_Gen', 'name': '测试将军', 'type': 'field_marshal', 'skill': 5,
      'attack': 6, 'defense': 4, 'planning': 3, 'logistics': 2})

print()
print('=== 3) 决议（含类别注册）===')
step('dec add', '/api/decision_add',
     {'id': 'xtt_test_decision', 'category': 'XTT_category',
      'icon': 'GFX_decision_generic', 'cost': 30,
      'effect': 'add_political_power = 80'})

print()
print('=== 4) 剧本 ===')
step('bookmark', '/api/bookmark_add',
     {'name': 'XTT_START', 'date': '1936.1.1', 'picture': 'GFX_select_date_1936',
      'default_country': 'AFR'})

print()
print('=== 5) 州资源（改一个已有州）===')
step('state res', '/api/state_save',
     {'id': 104, 'fields': {'resources': {'oil': 8, 'steel': 12}}})

print()
print('=== 6) 国家内容（AFR）===')
step('politics', '/api/politics_save',
     {'tag': 'AFR', 'fields': {'ruling_party': 'neutrality'}})
step('popularities', '/api/popularities_save',
     {'tag': 'AFR', 'pops': {'neutrality': 60, 'democratic': 40}})
step('war', '/api/war_add', {'tag': 'AFR', 'target': 'CHI', 'type': 'annex'})
step('focus done', '/api/focus_complete_add',
     {'tag': 'AFR', 'focus': 'AFR_SecureSuezFront'})

print()
print('=== 7) 地形 ===')
step('terrain', '/api/terrain_set', {'prov': 104, 'type': 'plains'})

bad = [x for x in log if not x[1]]
print('=' * 60)
print('%d 项 | 成功 %d | 失败 %d' % (len(log), len(log) - len(bad), len(bad)))
if bad:
    for n, _, m in bad:
        print('  - %-22s %s' % (n, m))
nfiles = sum(len(fs) for _, _, fs in os.walk(OUT))
print()
print('目录：', OUT)
print('文件数：', nfiles)
for root, _, fs in os.walk(OUT):
    for f in fs:
        print('  ', os.path.relpath(os.path.join(root, f), OUT))
srv.shutdown()
