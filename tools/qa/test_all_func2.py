# -*- coding: utf-8 -*-
"""阶段 1 补测：剩下 87 个接口。"""
import sys
import os
import io
import json
import shutil
import time
import urllib.request
import urllib.error
import threading

WORK = r'D:\大肥鱼工作区\HOI4 MUVLUVsub mod 制作\work'
GAME = r'E:\SteamLibrary\steamapps\common\Hearts of Iron IV'
CN = r'E:\SteamLibrary\steamapps\workshop\content\394360\2800380626'
TMPROOT = os.path.join(WORK, 'tmp', '_func2')
COPY = os.path.join(TMPROOT, 'copy')

shutil.rmtree(TMPROOT, ignore_errors=True)
os.makedirs(COPY)
io.open(os.path.join(COPY, 'descriptor.mod'), 'w', encoding='utf-8').write('name="copy"\n')

sys.path.insert(0, WORK)
import focus_editor as fe
from http.server import ThreadingHTTPServer

PORT = 8972
BASE = 'http://127.0.0.1:%d' % PORT


def post(path, body=None):
    data = json.dumps(body or {}).encode()
    req = urllib.request.Request(BASE + path, data=data, method='POST')
    req.add_header('Content-Type', 'application/json')
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode())
        except Exception:
            return {'ok': False, 'msg': 'HTTP %d' % e.code}
    except Exception as e:
        return {'ok': False, 'msg': str(e)[:70]}


fe.GAME = GAME
fe.ROOTS = [CN]
fe.load_game_loc()
fe.reload_data()
srv = ThreadingHTTPServer(('127.0.0.1', PORT), fe.Handler)
threading.Thread(target=srv.serve_forever, daemon=True).start()
time.sleep(2)

R = []


def T(name, path, body=None, note_fn=None):
    r = post(path, body)
    ok = r.get('ok') is not False
    note = (r.get('msg') or '')[:58]
    if not note and note_fn:
        try:
            note = note_fn(r)
        except Exception:
            pass
    R.append((name, bool(ok), note))
    print('  %s %-26s %s' % ('OK ' if ok else 'FAIL', name, note))
    return r


print('=== 阶段 1 补测 ===')
print()
print('--- 地图（先建图层）---')
T('map_build', '/api/map_build', {}, lambda r: 'w=%s h=%s' % (r.get('w'), r.get('h')))
T('map_integrity', '/api/map_integrity', {})
T('map_asset', '/api/map_asset', {'kind': 'prov_id'})
T('map_meta', '/api/map_meta', {})
T('map_paint', '/api/map_paint', {'points': [[100, 100]], 'prov': 104})
T('map_repair_cross', '/api/map_repair_cross', {})
T('map_merge', '/api/map_merge', {'src': 99999, 'dst': 104})
T('map_cache_clear', '/api/map_cache_clear', {})

print()
print('--- 地形 ---')
T('terrain_by_type', '/api/terrain_by_type', {'type': 'plains', 'from': 'forest'})
T('terrain_batch', '/api/terrain_batch', {'provinces': [104], 'type': 'plains'})
T('terrain_set', '/api/terrain_set', {'prov': 104, 'type': 'plains'})
T('terrain_paint', '/api/terrain_paint', {'points': [[100, 100]], 'terrain': 'plains', 'brush': 3})

print()
print('--- 铁路 / 海峡 ---')
T('railway_edit', '/api/railway_edit', {'prov': 104, 'level': 1})
T('adj_edit', '/api/adj_edit', {'from': 104, 'to': 105, 'type': 'sea'})

print()
print('--- 战略区 / 补给区 / 州 ---')
T('sr_create', '/api/sr_create', {'id': 9001, 'name': 'TEST_SR'})
T('sr_set_provinces', '/api/sr_set_provinces', {'id': 9001, 'provinces': [104, 105]})
T('supply_save', '/api/supply_save', {'id': 9001, 'value': 10})
T('state_create', '/api/state_create', {'id': 9901, 'name': 'TEST_STATE', 'provinces': [104]})
T('state_province', '/api/state_province', {'state': 9901, 'prov': 106})
T('state_refine_preview', '/api/state_refine_preview', {'id': 104})

print()
print('--- 国策树 ---')
T('focus_graph', '/api/focus_graph', {'tag': 'AFR'})
T('focus_trees', '/api/focus_trees', {})

print()
print('--- 装备 ---')
T('equipment_list', '/api/equipment_list', {})
T('equipment_detail', '/api/equipment_detail', {'archetype': 'infantry_equipment'})

print()
print('--- 图标 / 本地化 ---')
T('gfx_sprites', '/api/gfx_sprites', {'kind': 'goal'})
T('gfx_missing', '/api/gfx_missing', {})
T('loc_missing', '/api/loc_missing', {})

print()
print('--- 检查 ---')
T('orphan_tags', '/api/orphan_tags', {})
T('lint', '/api/lint', {})
T('export', '/api/export', {})
T('errorlog', '/api/errorlog', {})
T('output', '/api/output', {})

print()
print('--- 事件 ---')
T('event_graph', '/api/event_graph', {'ns': ''})

print()
print('--- AI ---')
T('ai_config', '/api/ai_config', {})
T('ai_test', '/api/ai_test', {})

print()
print('--- 杂 ---')
T('playset', '/api/playset', {})
T('data', '/api/data', {})
T('fs', '/api/fs', {'path': '.'})
T('raw', '/api/raw', {'path': 'descriptor.mod'})

allr = R
bad = [x for x in allr if not x[1]]
print()
print('=' * 62)
print('补测 %d 项 | 通过 %d | 失败 %d' % (len(allr), len(allr) - len(bad), len(bad)))
if bad:
    print('失败清单：')
    for n, _, note in bad:
        print('  - %-26s %s' % (n, note))

srv.shutdown()
shutil.rmtree(TMPROOT, ignore_errors=True)
