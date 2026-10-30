"""验证 _state_file_for 的写入落点：加载 submod 时改州会写到哪一层。

场景：
  父 mod（有 history/states/1-Parent.txt）
  子 mod（有 history/states/1-Child.txt，同 id 1，不同文件名）
  ROOTS = [子mod]，子 mod descriptor 声明 dependencies = {父mod}

预期：_state_file_for(1) 应返回子 mod 的路径。
"""
import sys
import io
import os
import shutil

sys.path.insert(0, r'D:\大肥鱼工作区\HOI4 MUVLUVsub mod 制作\work')
import focus_editor as fe

fe.GAME = r'E:\SteamLibrary\steamapps\common\Hearts of Iron IV'
TMP = os.path.join(r'D:\大肥鱼工作区\HOI4 MUVLUVsub mod 制作\work', 'tmp', '_sff')
PAR = os.path.join(TMP, 'parent_mod')
CHI = os.path.join(TMP, 'child_mod')

for d in (PAR, CHI):
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(os.path.join(d, 'history', 'states'), exist_ok=True)

# 父 mod：州 1 三个省
io.open(os.path.join(PAR, 'history', 'states', '1-Parent.txt'), 'w', encoding='utf-8').write(
    'state = {\n\tid = 1\n\tname = "STATE_1"\n\tmanpower = 100000\n'
    '\tstate_category = rural\n\thistory = {\n\t\towner = FRA\n\t}\n'
    '\tprovinces = {\n\t\t11 12 13\n\t}\n}\n')
io.open(os.path.join(PAR, 'descriptor.mod'), 'w', encoding='utf-8').write(
    'name="parent_mod"\nversion="1.0"\n')

# 子 mod：同 id 1，两个省
io.open(os.path.join(CHI, 'history', 'states', '1-Child.txt'), 'w', encoding='utf-8').write(
    'state = {\n\tid = 1\n\tname = "STATE_1"\n\tmanpower = 200000\n'
    '\tstate_category = town\n\thistory = {\n\t\towner = GER\n\t}\n'
    '\tprovinces = {\n\t\t11 12\n\t}\n}\n')
io.open(os.path.join(CHI, 'descriptor.mod'), 'w', encoding='utf-8').write(
    'name="child_mod"\nversion="1.0"\ndependencies={\n\t"parent_mod"\n}\n')

fe.ROOTS = [PAR, CHI]   # playset 模式：父在前，子在后
fe.load_game_loc()
fe.reload_data()

print('=== 叠加链 ===')
for x in (fe.mod_layers(CHI) or []):
    print('   ', x)

print('\n=== STATES[1] 记录 ===')
s1 = fe.STATES.get(1) or {}
print('    root =', s1.get('root'))
print('    file =', s1.get('file'))
print('    owner =', s1.get('owner'), '| manpower =', s1.get('manpower'))

print('\n=== _state_file_for(1) ===')
r, rel, p = fe._state_file_for(1)
print('    root =', r)
print('    rel  =', rel)
print('    path =', p)

# 实际改一次，看哪个文件变了
def read(p2):
    return io.open(p2, encoding='utf-8').read() if os.path.exists(p2) else ''

par_file = os.path.join(PAR, 'history', 'states', '1-Parent.txt')
chi_file = os.path.join(CHI, 'history', 'states', '1-Child.txt')
before_par, before_chi = read(par_file), read(chi_file)

res = fe.state_save(1, {'manpower': '999999'})
print('\n=== state_save(1, manpower=999999) ===')
print('    ', res.get('msg') or res.get('ok'))
after_par, after_chi = read(par_file), read(chi_file)
print('    父 mod 文件变了:', before_par != after_par)
print('    子 mod 文件变了:', before_chi != after_chi)

# 再用 _state_file_for 的路径直接测一次写
print('\n=== 用 _state_file_for 的返回值写一次 ==="')
if p:
    before = read(p)
    io.open(p, 'w', encoding='utf-8').write(before.replace('manpower = 200000', 'manpower = 888888')
                                              .replace('manpower = 100000', 'manpower = 888888'))
    print('    写入路径:', p)
    print('    落在父 mod:', os.path.abspath(p).startswith(os.path.abspath(PAR)))
    print('    落在子 mod:', os.path.abspath(p).startswith(os.path.abspath(CHI)))
