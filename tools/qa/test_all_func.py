# -*- coding: utf-8 -*-
"""阶段 1：原版地图不动，通过 HTTP 测编辑器全部接口。

起真实服务，按路由名逐个请求，覆盖读写两类。
"""
import sys
import os
import io
import json
import shutil
import subprocess
import time
import urllib.request
import urllib.error

WORK = r'D:\大肥鱼工作区\HOI4 MUVLUVsub mod 制作\work'
GAME = r'E:\SteamLibrary\steamapps\common\Hearts of Iron IV'
CN = r'E:\SteamLibrary\steamapps\workshop\content\394360\2800380626'
CNSUB = r'E:\SteamLibrary\steamapps\workshop\content\394360\3004109283'
TMPROOT = os.path.join(WORK, 'tmp', '_func')
COPY = os.path.join(TMPROOT, 'copy')

shutil.rmtree(TMPROOT, ignore_errors=True)
os.makedirs(COPY)
io.open(os.path.join(COPY, 'descriptor.mod'), 'w', encoding='utf-8').write('name="copy"\n')

sys.path.insert(0, WORK)
import focus_editor as fe

PORT = 8971
BASE = 'http://127.0.0.1:%d' % PORT


def post(path, body=None):
    data = json.dumps(body or {}).encode()
    req = urllib.request.Request(BASE + path, data=data, method='POST')
    req.add_header('Content-Type', 'application/json')
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode())
        except Exception:
            return {'ok': False, 'msg': 'HTTP %d' % e.code}
    except Exception as e:
        return {'ok': False, 'msg': str(e)[:80]}


# 起服务
import threading
from http.server import ThreadingHTTPServer

fe.GAME = GAME
fe.ROOTS = [CN]
fe.load_game_loc()
fe.reload_data()

srv = ThreadingHTTPServer(('127.0.0.1', PORT), fe.Handler)
t = threading.Thread(target=srv.serve_forever, daemon=True)
t.start()
time.sleep(2)

R = []


def T(name, path, body=None, expect_ok=True):
    r = post(path, body)
    ok = (r.get('ok') is not False) if expect_ok else (r.get('ok') is False or 'msg' in r)
    note = (r.get('msg') or '')[:60] or ('%d 个字段' % len(r))
    R.append((name, bool(ok), note))


print('=== 阶段 1 接口测试 ===')
print()

# ---- 读接口 ----
reads = [
    ('app_info', '/api/app_info', {}),
    ('countries', '/api/countries', {}),
    ('states', '/api/states', {}),
    ('map_meta', '/api/map_meta', {}),
    ('map_analysis', '/api/map_analysis', {}),
    ('map_integrity', '/api/map_integrity', {}),
    ('terrain_types', '/api/terrain_types', {}),
    ('strategic_regions', '/api/strategic_regions', {}),
    ('supply_areas', '/api/supply_areas', {}),
    ('railways', '/api/railways', {}),
    ('adjacencies', '/api/adjacencies', {}),
    ('battalions', '/api/battalions', {}),
    ('units', '/api/units', {}),
    ('navy', '/api/navy', {}),
    ('air_wings', '/api/air_wings', {}),
    ('country_tags', '/api/country_tags', {}),
    ('focus_trees', '/api/focus_trees', {}),
    ('event_spaces', '/api/event_graph', {'ns': ''}),
    ('characters', '/api/characters', {}),
    ('decisions', '/api/decisions', {}),
    ('bookmarks', '/api/bookmarks', {}),
    ('gfx_list', '/api/gfx_list', {}),
    ('equipment_list', '/api/equipment_list', {}),
    ('backups', '/api/backups', {}),
    ('write_targets', '/api/write_targets', {}),
]
for n, p, b in reads:
    T(n, p, b)

print('--- 读接口 ---')
for n, ok, note in R:
    print('  %s %-24s %s' % ('OK ' if ok else 'FAIL', n, note))

# ---- 单国 ----
print()
print('--- 单国（AFR）---')
R2 = []
for n, p, b in [
    ('country', '/api/country', {'tag': 'AFR'}),
    ('country_history', '/api/country_history', {'tag': 'AFR'}),
    ('country_techs', '/api/country_techs', {'tag': 'AFR'}),
    ('country_ideas', '/api/country_ideas', {'tag': 'AFR'}),
    ('politics', '/api/politics', {'tag': 'AFR'}),
    ('completed_focuses', '/api/completed_focuses', {'tag': 'AFR'}),
    ('state', '/api/state', {'id': 104}),
]:
    r = post(p, b)
    ok = r.get('ok') is not False
    note = (r.get('msg') or '')[:55]
    R2.append((n, ok, note))
    print('  %s %-24s %s' % ('OK ' if ok else 'FAIL', n, note))

# ---- 写接口（副本）----
print()
print('--- 写接口（副本）---')
fe.ROOTS = [CN, COPY]
fe.reload_data()

R3 = []
for n, p, b in [
    ('adopt_dir', '/api/adopt_dir', {'sub': 'common/ideas'}),
    ('adopt_dir2', '/api/adopt_dir', {'sub': 'common/characters'}),
    ('adopt_dir3', '/api/adopt_dir', {'sub': 'common/decisions'}),
    ('adopt_dir4', '/api/adopt_dir', {'sub': 'common/bookmarks'}),
    ('adopt_dir5', '/api/adopt_dir', {'sub': 'history/countries'}),
    ('adopt_dir6', '/api/adopt_dir', {'sub': 'history/units'}),
]:
    r = post(p, b)
    ok = r.get('ok') is not False
    R3.append((n, ok, (r.get('msg') or '')[:50]))
    print('  %s %-24s %s' % ('OK ' if ok else 'FAIL', n, (r.get('msg') or '')[:50]))

writes = [
    ('politics_save', '/api/politics_save', {'tag': 'AFR', 'fields': {'ruling_party': 'neutrality'}}),
    ('popularities_save', '/api/popularities_save', {'tag': 'AFR', 'pops': {'neutrality': 50, 'democratic': 50}}),
    ('war_add', '/api/war_add', {'tag': 'AFR', 'target': 'CHI', 'type': 'annex'}),
    ('character_add', '/api/character_add', {'id': 'TST_GEN', 'name': '测试', 'type': 'corps_commander', 'skill': 3}),
    ('decision_add', '/api/decision_add', {'id': 'tst_dec', 'category': 'tst_cat', 'icon': 'GFX_decision_generic', 'cost': 30}),
    ('bookmark_add', '/api/bookmark_add', {'name': 'TST_BM', 'date': '1940.1.1', 'default_country': 'GER'}),
    ('navy_add_ship', '/api/navy_add_ship', {'fi': 0, 'ti': 0, 'name': '测试舰', 'definition': 'destroyer', 'exp': 0.3}),
    ('air_wing_add', '/api/air_wing_add', {'province': 999, 'name': '测试队', 'type': 'fighter_equipment_1', 'owner': 'CHI', 'amount': 5}),
    ('state_save', '/api/state_save', {'id': 104, 'fields': {'resources': {'oil': 5}}}),
    ('height_paint', '/api/height_paint', {'points': [[100, 100]], 'height': 128, 'brush': 5, 'feather': True}),
    ('height_sample', '/api/height_sample', {'points': [[100, 100]], 'radius': 1}),
]
for n, p, b in writes:
    r = post(p, b)
    ok = r.get('ok') is not False
    note = (r.get('msg') or '')[:50]
    R3.append((n, ok, note))
    print('  %s %-24s %s' % ('OK ' if ok else 'FAIL', n, note))

allr = R + R2 + R3
bad = [x for x in allr if not x[1]]
print()
print('=' * 62)
print('总计 %d 项 | 通过 %d | 失败 %d' % (len(allr), len(allr) - len(bad), len(bad)))
if bad:
    print('失败清单：')
    for n, _, note in bad:
        print('  - %-26s %s' % (n, note))

srv.shutdown()
shutil.rmtree(TMPROOT, ignore_errors=True)
