# -*- coding: utf-8 -*-
"""用编辑器 HTTP 接口造测试模组（不猜函数名）。"""
import sys
import os
import io
import json
import shutil
import time
import threading
import urllib.request
import urllib.error

WORK = r'D:\大肥鱼工作区\HOI4 MUVLUVsub mod 制作\work'
GAME = r'E:\SteamLibrary\steamapps\common\Hearts of Iron IV'
CN = r'E:\SteamLibrary\steamapps\workshop\content\394360\2800380626'
CNSUB = r'E:\SteamLibrary\steamapps\workshop\content\394360\3004109283'
BASE = os.path.join(WORK, 'tmp', '_testmod')
OUT = os.path.join(BASE, 'xuerong_test')
PORT = 8981
URL = 'http://127.0.0.1:%d' % PORT

shutil.rmtree(BASE, ignore_errors=True)
os.makedirs(OUT)
io.open(os.path.join(OUT, 'descriptor.mod'), 'w', encoding='utf-8').write(
    'name="雪绒测试模组"\nversion="1.0.0"\n')

sys.path.insert(0, WORK)
import focus_editor as fe
from http.server import ThreadingHTTPServer

fe.GAME = GAME
# 必须把 CNsub 也加载进来：CNsub 同样 replace 了 common/decisions 等目录，
# 只写 [CN, OUT] 时编辑器看不到 CNsub 层，只能从 CN 复制，拿到的是被覆盖之前的旧版本。
fe.ROOTS = [CN, CNSUB, OUT]
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
    print('  %s %-22s %s' % ('OK ' if ok else 'FAIL', name, msg))
    return r


print('=== 1) 接管目录 ===')
for sub in ('history/countries', 'history/units', 'common/ideas',
            'common/characters', 'common/decisions', 'common/bookmarks',
            'common/country_tags', 'history/states'):
    step('adopt ' + sub.split('/')[-1], '/api/adopt_dir', {'sub': sub})

print()
print('=== 2) 新国家 TAG ===')
step('tag_add', '/api/country_tag_add',
     {'tag': 'XTT', 'color': [70, 140, 200], 'culture': 'western_european_gfx'})

print()
print('=== 3) 国家内容（AFR）===')
r = P('/api/country_techs', {'tag': 'JAP'})
techs = r.get('techs') or r.get('items') or []
ft = None
if techs:
    ft = techs[0].get('id') if isinstance(techs[0], dict) else techs[0]
print('  首个科技:', ft)
if ft:
    step('tech off', '/api/country_tech_toggle', {'tag': 'JAP', 'tech': ft, 'on': False})
    step('tech on', '/api/country_tech_toggle', {'tag': 'JAP', 'tech': ft, 'on': True})

r = P('/api/country_ideas', {'tag': 'JAP'})
ideas = r.get('ideas') or []
fid = None
if ideas:
    fid = ideas[0].get('id') if isinstance(ideas[0], dict) else ideas[0]
print('  首个精神:', fid)
if fid:
    step('idea toggle', '/api/country_idea_toggle', {'tag': 'JAP', 'idea': fid, 'on': True})

step('politics', '/api/politics_save',
     {'tag': 'JAP', 'fields': {'ruling_party': 'neutrality', 'elections_allowed': 'no'}})
step('popularities', '/api/popularities_save',
     {'tag': 'JAP', 'pops': {'neutrality': 60, 'democratic': 40}})
step('war', '/api/war_add', {'tag': 'JAP', 'target': 'USA', 'type': 'annex'})

print()
print('=== 4) 师团模板 ===')
step('template_add', '/api/template_add',
     {'name': 'XTT_TestTpl', 'unit': 'infantry'})

print()
print('=== 5) 部队 ===')
step('unit_add', '/api/unit_add',
     {'location': 104, 'template': 'XTT_TestTpl', 'name': '测试部队', 'exp': 0.5})

print()
print('=== 6) 舰队 ===')
step('navy ship', '/api/navy_add_ship',
     {'fi': 0, 'ti': 0, 'name': '测试舰', 'definition': 'destroyer', 'exp': 0.5})
step('navy tf', '/api/navy_add_tf', {'fi': 0, 'name': '测试战队', 'location': 104})

print()
print('=== 7) 空军 ===')
step('air wing', '/api/air_wing_add',
     {'province': 104, 'name': '测试联队', 'type': 'fighter_equipment_1',
      'owner': 'JAP', 'amount': 10})

print()
print('=== 8) 人物 ===')
step('char add', '/api/character_add',
     {'id': 'XTT_Gen', 'name': '测试将军', 'type': 'field_marshal', 'skill': 5,
      'attack': 6, 'defense': 4, 'planning': 3, 'logistics': 2})

print()
print('=== 9) 决议 ===')
step('dec add', '/api/decision_add',
     {'id': 'xtt_test_decision', 'category': 'XTT_category',
      'icon': 'GFX_decision_generic', 'cost': 30,
      'effect': 'add_political_power = 80'})

print()
print('=== 10) 剧本 ===')
step('bookmark', '/api/bookmark_add',
     {'name': 'XTT_START', 'date': '1936.1.1', 'picture': 'GFX_select_date_1936',
      'default_country': 'JAP'})

print()
print('=== 11) 州资源 ===')
step('state res', '/api/state_save',
     {'id': 104, 'fields': {'resources': {'oil': 8, 'steel': 12}}})

print()
print('=== 12) 图标 ===')
r = P('/api/gfx_list', {})
tex = None
for k, v in (r or {}).items():
    if isinstance(v, list) and v:
        it = v[0]
        tex = it.get('file') if isinstance(it, dict) else None
        break
print('  首个贴图:', tex)
if tex:
    step('gfx sprite', '/api/gfx_sprite_new',
         {'name': 'GFX_xtt_test_icon', 'texturefile': tex})

print()
print('=== 13) 已完成国策 ===')
fid2 = None
for tid, t in (fe.TREES or {}).items():
    if not str(tid).upper().startswith('JAP'):
        continue
    fs = t.get('focuses') or []
    if fs:
        fid2 = fs[0].get('id')
        break
if not fid2:
    for t in (fe.TREES or {}).values():
        fs = t.get('focuses') or []
        if fs:
            fid2 = fs[0].get('id')
            break
print('  首个国策:', fid2)
if fid2:
    step('focus done', '/api/focus_complete_add', {'tag': 'JAP', 'focus': fid2})

bad = [x for x in log if not x[1]]
print('=' * 62)
print('生成 %d 项 | 成功 %d | 失败 %d' % (len(log), len(log) - len(bad), len(bad)))
if bad:
    for n, _, m in bad:
        print('  - %-22s %s' % (n, m))
nfiles = sum(len(fs) for _, _, fs in os.walk(OUT))
print()
print('目录：', OUT)
print('文件数：', nfiles)
srv.shutdown()
