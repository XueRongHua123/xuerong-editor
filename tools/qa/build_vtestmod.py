# -*- coding: utf-8 -*-
"""在原版 HOI4 上做测试模组。

原版没有任何 replace_path，所以不需要接管任何目录，直接写自己的 mod 就能生效。
这也顺便验证了编辑器在「干净环境」下的行为。
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
BASE = os.path.join(WORK, 'tmp', '_testmod_v')
OUT = os.path.join(BASE, 'xuerong_vtest')
PORT = 8993
URL = 'http://127.0.0.1:%d' % PORT

shutil.rmtree(BASE, ignore_errors=True)
os.makedirs(OUT)
io.open(os.path.join(OUT, 'descriptor.mod'), 'w', encoding='utf-8').write(
    'name="雪绒原版测试"\nversion="1.0.0"\n')

sys.path.insert(0, WORK)
import focus_editor as fe
from http.server import ThreadingHTTPServer

fe.GAME = GAME
fe.ROOTS = [OUT]          # 只加载自己的 mod，底下是原版
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
    msg = (r.get('msg') or '')[:60]
    log.append((name, ok, msg))
    print('  %s %-24s %s' % ('OK ' if ok else 'FAIL', name, msg))
    return r


print('=== 原版环境测试 ===')
print()
print('=== 0) 先确认原版数据 ===')
r = P('/api/countries', {})
print('  国家数:', len(r.get('countries') or r.get('items') or []) or r.get('msg'))
r = P('/api/states', {})
print('  州数:', len(r.get('states') or r.get('items') or []) or r.get('msg'))

TAG = 'GER'

print()
print('=== 1) 新国家 TAG ===')
step('tag_add', '/api/country_tag_add',
     {'tag': 'XTT', 'color': [70, 140, 200], 'culture': 'western_european_gfx'})

print()
print('=== 2) 人物（带头像）===')
# 造一张测试头像图
try:
    from PIL import Image as _Img
    _face = os.path.join(BASE, 'test_face.png')
    _im = _Img.new('RGB', (300, 400), (190, 110, 85))
    _im.save(_face)
    print('  测试头像:', _face)
except Exception:
    _face = None
step('char add', '/api/character_add',
     {'id': 'XTT_Gen', 'name': '测试将军', 'type': 'field_marshal', 'skill': 5,
      'attack': 6, 'defense': 4, 'planning': 3, 'logistics': 2, 'country': TAG,
      'portrait_src': _face})

print()
print('=== 2b) 用编辑器把人物类型改成陆军将军 ===')
step('char set type', '/api/character_set',
     {'id': 'XTT_Gen', 'fields': {'type': 'corps_commander'}})

print()
print('=== 3) 决议 ===')
step('dec add', '/api/decision_add',
     {'id': 'xtt_test_decision', 'category': 'XTT_category',
      'icon': 'GFX_decision_generic', 'cost': 30,
      'effect': 'add_political_power = 80'})

print()
print('=== 4) 剧本 ===')
step('bookmark', '/api/bookmark_add',
     {'name': 'XTT_VSTART', 'date': '1936.1.1', 'picture': 'GFX_select_date_1936',
      'default_country': TAG, 'countries': ['GER', 'SOV', 'USA', 'ENG', 'FRA']})

print()
print('=== 5) %s 的国家内容 ===' % TAG)
r = P('/api/country_techs', {'tag': TAG})
techs = r.get('techs') or r.get('items') or []
ft = None
if techs:
    ft = techs[0].get('id') if isinstance(techs[0], dict) else techs[0]
print('  首个科技:', ft)
if ft:
    step('tech off', '/api/country_tech_toggle', {'tag': TAG, 'tech': ft, 'on': False})
    step('tech on', '/api/country_tech_toggle', {'tag': TAG, 'tech': ft, 'on': True})

r = P('/api/country_ideas', {'tag': TAG})
ideas = r.get('ideas') or []
fid = None
if ideas:
    fid = ideas[0].get('id') if isinstance(ideas[0], dict) else ideas[0]
print('  首个精神:', fid)
if fid:
    step('idea toggle', '/api/country_idea_toggle', {'tag': TAG, 'idea': fid, 'on': True})

step('politics', '/api/politics_save',
     {'tag': TAG, 'fields': {'ruling_party': 'fascism', 'elections_allowed': 'no'}})
step('popularities', '/api/popularities_save',
     {'tag': TAG, 'pops': {'fascism': 70, 'democratic': 30}})
step('war', '/api/war_add', {'tag': TAG, 'target': 'SOV', 'type': 'annex'})

print()
print('=== 6) 师团模板 ===')
step('template_add', '/api/template_add', {'name': 'XTT_TestTpl', 'unit': 'infantry', 'tag': TAG})

print()
print('=== 7) 部队 ===')
step('unit_add', '/api/unit_add',
     {'location': 1, 'template': 'XTT_TestTpl', 'name': '测试部队', 'exp': 0.5, 'tag': TAG})

print()
print('=== 8) 舰队 ===')
step('navy ship', '/api/navy_add_ship',
     {'fi': 0, 'ti': 0, 'name': '测试舰', 'definition': 'destroyer', 'exp': 0.5, 'tag': TAG})

print()
print('=== 9) 空军 ===')
step('air wing', '/api/air_wing_add',
     {'province': 1, 'name': '测试联队', 'type': 'fighter_equipment_1',
      'owner': TAG, 'amount': 10})

print()
print('=== 10) 州资源 ===')
step('state res', '/api/state_save', {'id': 1, 'fields': {'resources': {'oil': 5}}})

print()
print('=== 11) 图标 ===')
r = P('/api/gfx_list', {})
tex = None
for k, v in (r or {}).items():
    if isinstance(v, list) and v:
        it = v[0]
        tex = it.get('file') if isinstance(it, dict) else None
        break
print('  首个贴图:', tex)
if tex:
    step('gfx sprite', '/api/gfx_import',
         {'name': 'GFX_xtt_vtest_icon', 'texturefile': tex})

print()
print('=== 12) 已完成国策 ===')
fid2 = None
for tid, t in (fe.TREES or {}).items():
    if not str(tid).upper().startswith(TAG):
        continue
    fs = t.get('focuses') or []
    if fs:
        fid2 = fs[0].get('id')
        break
print('  首个国策:', fid2)
if fid2:
    step('focus done', '/api/focus_complete_add', {'tag': TAG, 'focus': fid2})

bad = [x for x in log if not x[1]]
print('=' * 62)
print('%d 项 | 成功 %d | 失败 %d' % (len(log), len(log) - len(bad), len(bad)))
if bad:
    for n, _, m in bad:
        print('  - %-24s %s' % (n, m))
print()
print('目录：', OUT)
nfiles = sum(len(fs) for _, _, fs in os.walk(OUT))
print('文件数：', nfiles)
for root, _, fs in os.walk(OUT):
    for f in fs:
        print('  ', os.path.relpath(os.path.join(root, f), OUT))
srv.shutdown()
