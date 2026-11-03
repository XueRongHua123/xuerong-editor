# -*- coding: utf-8 -*-
"""搭 muvluvCN+sub 扩展 submod：从个人适配版拷自己写的 59 文本 + 14 图片。

默认是「安全同步」，不是「清空重建」：
  * 现有 submod 目录先整份备份到 work/backups/submod_YYYYmmdd_HHMMSS/
  * 只拷内容有变化的文件，没变的跳过，报告每个文件的动作
  * 目标目录里存在、但不在清单里的文件会列出来，但默认不动（--prune 才删）

用法：
    python work/qa/_build_submod.py --dry-run     # 只看会做什么
    python work/qa/_build_submod.py               # 备份 + 同步（推荐）
    python work/qa/_build_submod.py --force       # 删空重建（真需要才用）

路径来自 _paths.py，换机器只改那一处或设 MVL_* 环境变量。
"""
import filecmp
import hashlib
import io
import os
import re
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from _paths import (CHG, CN, DISPLAY_NAME, GAME, HIS, MODDIR,  # noqa: E402
                    MUSIC_ASSET, NAME, ONLY_IN_HIS, OUT, SONGS, SUB, VERSION,
                    WORKSHOP_ID, WORK_MODS, check_roots, p)

BACKUP_ROOT = os.path.join(os.path.dirname(HERE), 'backups')

# 36 个新增（基座没有，全 zz_mvlv119_ 前缀）
NEW = '''common/decisions/categories/zz_mvlv119_nuke_categories.txt
common/decisions/zz_mvlv119_nuke_decisions.txt
common/dynamic_modifiers/zz_mvlv119_dust_modifiers.txt
common/dynamic_modifiers/zz_mvlv119_mine_modifier.txt
common/dynamic_modifiers/zz_mvlv119_nuke_modifiers.txt
common/on_actions/zz_mvlv119_bootstrap.txt
common/on_actions/zz_mvlv119_mine_trigger.txt
common/on_actions/zz_mvlv119_nuke_dust.txt
common/on_actions/zz_mvlv119_nuke_start.txt
common/on_actions/zz_mvlv119_start_music.txt
common/raids/categories/zz_mvlv119_raid_categories.txt
common/raids/zz_mvlv119_artillery_raid.txt
common/raids/zz_mvlv119_hydrogen_raids.txt
common/raids/zz_mvlv119_nuke_raids.txt
common/scripted_effects/zz_mvlv119_dust_effect.txt
common/scripted_guis/zz_mvlv119_dust_topbar.txt
common/scripted_guis/zz_mvlv119_mine_gui.txt
common/scripted_guis/zz_mvlv119_nuke_power_topbar.txt
common/scripted_localisation/zz_mvlv119_dust_loc.txt
common/technologies/zz_mvlv119_nuke_tech.txt
common/units/equipment/zz_mvlv119_nuke_equipment.txt
events/zz_mvlv119_dirty_news.txt
events/zz_mvlv119_doctrine.txt
events/zz_mvlv119_dust_events.txt
events/zz_mvlv119_dust_status.txt
events/zz_mvlv119_mine_events.txt
events/zz_mvlv119_start_music_events.txt
interface/zz_mvlv119_dust_topbar.gui
interface/zz_mvlv119_mine_button.gui
interface/zz_mvlv119_nuke_icons.gfx
interface/zz_mvlv119_nuke_power_topbar.gui
localisation/english/replace/zz_mvlv119_nuke_l_english.yml
localisation/english/replace/zz_mvlv_start_music_l_english.yml
localisation/simp_chinese/replace/MVLV_119_fix_l_simp_chinese.yml
localisation/simp_chinese/replace/zz_mvlv119_nuke_l_simp_chinese.yml
localisation/simp_chinese/replace/zz_mvlv_start_music_l_simp_chinese.yml'''.split()

# 本包自己写、不从适配版拷的文件（构建时不算多余，也不覆盖）
KEEP = '''common/dynamic_modifiers/zz_mvlv119_un_modifiers.txt
common/on_actions/zz_mvlv119_un_sessions.txt
common/on_actions/zz_mvlv119_un_gbomb.txt
common/scripted_effects/zz_mvlv119_un_core.txt
common/scripted_effects/zz_mvlv119_un_resolutions.txt
common/scripted_effects/zz_mvlv119_un_sg.txt
common/scripted_localisation/zz_mvlv119_un_loc.txt
common/scripted_localisation/zz_mvlv119_un_status_loc.txt
common/scripted_triggers/zz_mvlv119_un_rules.txt
common/scripted_guis/zz_mvlv119_un_window.txt
common/scripted_guis/zz_mvlv119_un_entry.txt
events/zz_mvlv119_un_events.txt
interface/zz_mvlv119_un_window.gui
interface/zz_mvlv119_un_entry.gui
interface/zz_mvlv119_un_assets.gfx
localisation/english/replace/zz_mvlv119_un_l_english.yml
localisation/simp_chinese/replace/zz_mvlv119_un_l_simp_chinese.yml
gfx/interface/un/mvlv119_un_chip.png
gfx/interface/un/mvlv119_un_window_bg.png
gfx/interface/un/mvlv119_un_btn_vote.png
gfx/interface/un/mvlv119_un_btn_res.png
gfx/interface/un/mvlv119_un_btn_lobby.png
gfx/interface/un/mvlv119_un_btn_tab.png
gfx/interface/un/mvlv119_un_tab_on.png
gfx/interface/un/mvlv119_un_btn_action.png
gfx/interface/un/mvlv119_un_btn_pass.png
gfx/interface/un/mvlv119_un_btn_pass_grey.png
gfx/interface/un/mvlv119_un_entry.png
gfx/interface/event_pictures/mvlv119_un_session.png'''.split()

# 11 个图片（自己做的）
GFX = '''gfx/interface/equipment/mvlv_nuke_dirty.dds
gfx/interface/equipment/mvlv_nuke_dirty.png
gfx/interface/equipment/mvlv_nuke_strategic.dds
gfx/interface/equipment/mvlv_nuke_strategic.png
gfx/interface/equipment/mvlv_nuke_tactical.dds
gfx/interface/equipment/mvlv_nuke_tactical.png
gfx/interface/event_pictures/zz_mvlv119_dust_disaster.dds
gfx/interface/event_pictures/zz_mvlv119_dust_heavy.dds
gfx/interface/event_pictures/zz_mvlv119_dust_light.dds
gfx/interface/event_pictures/zz_mvlv119_dust_medium.dds
gfx/interface/mvlv119/nuke_power_icon.dds'''.split()

DESC = '''name="%s"
version="%s"
tags={
\t"Alternative History"
\t"Gameplay"
\t"Sound"
}
picture="thumbnail.png"
supported_version="1.19.*"
dependencies={
\t"muvluvCN"
\t"muvluvCNsub"
}
''' % (DISPLAY_NAME, VERSION)


def md5_of(path):
    return hashlib.md5(open(path, 'rb').read()).hexdigest()


def existing_remote_id():
    """找出已上传作品的工坊 id，供重写描述文件时保留。

    启动器上传成功后会把这个字段写进 descriptor.mod 和外部 .mod。
    构建脚本按模板整份重写这两个文件，如果模板里没有它，重跑一次就把 id 抹掉：
    启动器不再认得这是已发布作品，下次「上传」会新建一个工坊条目，
    旧条目的订阅者收不到更新。按优先级从现有文件里读，读到就用。
    """
    cands = [os.path.join(OUT, 'descriptor.mod'),
             os.path.join(MODDIR, NAME + '.mod'),
             os.path.join(WORK_MODS, NAME + '.mod'),
             os.path.join(MODDIR, 'ugc_%s.mod' % WORKSHOP_ID)]
    for path in cands:
        if not os.path.exists(path):
            continue
        t = io.open(path, encoding='utf-8-sig', errors='replace').read()
        m = re.search(r'remote_file_id\s*=\s*"(\d+)"', t)
        if m:
            return m.group(1), path
    return None, None


def music_asset_text():
    """生成歌曲本体注册文件。

    适配版是把这 8 首塞进 music/music.asset（覆盖 CN 的那份）；这里照做，
    但内容取「CN 当前那份原文 + 我的 8 首」，而不是硬抄适配版当年那份 ——
    这样基座给 music.asset 加歌时不会被我盖掉，符合「副本 = 基座最新 + 我的改动」。
    _verify_submod.py 6.4 会检查这一点，基座加歌后不重新生成就会 FAIL。
    """
    base_path = p(CN, MUSIC_ASSET)
    head = ''
    if os.path.exists(base_path):
        head = io.open(base_path, encoding='utf-8-sig',
                       errors='replace').read().replace('\r\n', '\n').rstrip()
    out = [
        '# =====================================================================',
        '# mvlv119 开局主题曲 | 歌曲本体注册',
        '#',
        '# 由 work/qa/_build_submod.py 从 _paths.SONGS 生成，改内容请改那张表。',
        '# 前半段是 muvluvCN 那份 music.asset 的原文（保证不丢基座的歌），',
        '# 后面追加本 submod 的 8 首。',
        '#',
        '# 只写 music/_songs.txt（播放列表）而不写本体，游戏会报',
        '#   Could not find music named <key>',
        '# 然后 scoped_play_song 静默失败 —— 表现就是「开局音乐不响」。',
        '#',
        '# 音频本体由 muvluvCN 提供（music/ 各子目录），这里只做注册。',
        '# =====================================================================',
        '',
    ]
    if head:
        out += ['# ---- begin: 来自 muvluvCN 的同名文件 ----', head, '',
                '# ---- end: muvluvCN 原文 ----', '',
                '# ---- begin: 本 submod 追加 ----']
    for name, file in SONGS:
        if re.search(r'name\s*=\s*"%s"' % re.escape(name), head or ''):
            continue      # 基座已经有了，不重复注册
        out += [
            'music = {',
            '\tname = "%s"' % name,
            '\tfile = "%s"' % file,
            '\tvolume = 0.65',
            '}',
            '',
        ]
    return '\n'.join(out)


def base_music_names():
    """读 CN 那份 music.asset 里定义的所有歌曲名。"""
    names = set()
    path = p(CN, MUSIC_ASSET)
    if not os.path.exists(path):
        return names
    t = io.open(path, encoding='utf-8-sig', errors='replace').read()
    for m in re.finditer(r'music\s*=\s*\{(.*?)\}', t, re.S):
        nm = re.search(r'name\s*=\s*"([^"]+)"', m.group(1))
        if nm:
            names.add(nm.group(1))
    return names


def write_music_asset():
    """写歌曲本体注册文件，返回 (动作, 相对路径)。"""
    text = music_asset_text()
    dst = p(OUT, MUSIC_ASSET)
    if os.path.exists(dst):
        cur = io.open(dst, encoding='utf-8-sig',
                      errors='replace').read().replace('\r\n', '\n')
        if cur.strip() == text.strip():
            return '未变', MUSIC_ASSET
        state = '更新'
    else:
        state = '新增'
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with open(dst, 'wb') as fh:
        fh.write(text.replace('\n', '\r\n').encode('utf-8'))
    return state, MUSIC_ASSET


def write_text(path, text):
    with open(path, 'wb') as fh:
        fh.write(b'\xef\xbb\xbf' + text.replace('\n', '\r\n').encode('utf-8'))


def backup(out):
    """整份备份现有 submod 目录，返回备份路径。"""
    stamp = time.strftime('%Y%m%d_%H%M%S')
    dst = os.path.join(BACKUP_ROOT, 'submod_%s' % stamp)
    os.makedirs(BACKUP_ROOT, exist_ok=True)
    shutil.copytree(out, dst)
    n = sum(len(fs) for _, _, fs in os.walk(dst))
    print('备份 %d 个文件 -> %s' % (n, dst))
    return dst


def main():
    dry = '--dry-run' in sys.argv
    force = '--force' in sys.argv
    prune = '--prune' in sys.argv

    print('OUT  = %s' % OUT)
    print('HIS  = %s' % HIS)
    if not check_roots():
        print('路径不全，停。')
        return 1
    if dry:
        print('（--dry-run：只报告，不写盘）')

    # MUSIC_ASSET 在 CHG 清单里（供验证脚本查覆盖关系），但内容由
    # write_music_asset() 生成，不能从适配版拷，所以从 plan 里排除
    plan = [(r, 'new') for r in NEW] + [(r, 'chg') for r in CHG
                                        if r != MUSIC_ASSET] \
        + [(r, 'gfx') for r in GFX] + [(r, 'gfx') for r in ONLY_IN_HIS]

    # 源文件校验
    miss = [(r, k) for r, k in plan if not os.path.exists(p(HIS, r))]
    if miss:
        print('适配版里缺这些文件，先确认是不是被改动或删了：')
        for r, k in miss:
            print('  缺: %s' % r)
        return 1

    if os.path.isdir(OUT) and os.listdir(OUT):
        if force:
            if dry:
                print('[dry] 会清空 %s 重建' % OUT)
            else:
                print('清空重建:', OUT)
                shutil.rmtree(OUT)

    # 先算出要动哪些文件；真有变化才备份（全未变时不白占磁盘）
    todo, unchanged = [], 0
    for rel, kind in plan:
        src, dst = p(HIS, rel), p(OUT, rel)
        if os.path.exists(dst):
            if filecmp.cmp(src, dst, shallow=False):
                unchanged += 1
                continue
            todo.append((rel, '更新'))
        else:
            todo.append((rel, '新增'))

    if todo and os.path.isdir(OUT) and os.listdir(OUT):
        if dry:
            print('[dry] 有 %d 个文件要改，实跑时会先备份' % len(todo))
        else:
            backup(OUT)

    acted = {'新增': 0, '更新': 0, '未变': unchanged}
    for rel, state in todo:
        acted[state] += 1
        print('  %s %s' % (state, rel))
        if not dry:
            dst = p(OUT, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(p(HIS, rel), dst)

    # descriptor.mod / 外部 .mod
    dpath = os.path.join(OUT, 'descriptor.mod')
    rid, rid_src = existing_remote_id()
    desc_text = DESC
    ext = DESC + 'path="%s"\n' % OUT.replace('\\', '/')
    if rid:
        desc_text += 'remote_file_id="%s"\n' % rid
        ext += 'remote_file_id="%s"\n' % rid
    if not dry:
        os.makedirs(OUT, exist_ok=True)
        write_text(dpath, desc_text)
        write_text(os.path.join(MODDIR, NAME + '.mod'), ext)
    print('  remote_file_id: %s'
          % ('%s（沿用 %s）' % (rid, rid_src) if rid else '无（首次上传时由启动器回写）'))

    # 自己生成的歌曲本体注册（不覆盖 CN 的 music.asset）
    if dry:
        dst = p(OUT, MUSIC_ASSET)
        state = '未变' if os.path.exists(dst) else '新增'
        print('  [dry] %s %s（%d 首）' % (state, MUSIC_ASSET, len(SONGS)))
    else:
        state, rel = write_music_asset()
        print('  %s %s（%d 首）' % (state, rel, len(SONGS)))
    acted[state] = acted.get(state, 0) + 1

    # 包内多余文件
    listed = {p(OUT, r) for r, _ in plan} | {p(OUT, r) for r in KEEP} | {dpath, p(OUT, MUSIC_ASSET),
                                             p(OUT, 'thumbnail.png')}
    extra = [f for f in graph_walk(OUT) if f not in listed]
    if extra:
        print('\n包里有 %d 个文件不在清单内：' % len(extra))
        for f in extra:
            print('  %s' % os.path.relpath(f, OUT))
        if prune and not dry:
            for f in extra:
                os.remove(f)
            print('  已删（--prune）')
        elif not prune:
            print('  （加 --prune 删除）')

    total = sum(len(fs) for _, _, fs in os.walk(OUT))
    size = sum(os.path.getsize(os.path.join(dp, f))
               for dp, _, fs in os.walk(OUT) for f in fs)
    print('\n新增 %d, 更新 %d, 未变 %d' % (acted['新增'], acted['更新'], acted['未变']))
    print('目录现有 %d 个文件, %.2f MB' % (total, size / 1048576))
    print('位置:', OUT)
    return 0


def graph_walk(base):
    for dp, _, fs in os.walk(base):
        for f in fs:
            yield os.path.join(dp, f)


if __name__ == '__main__':
    sys.exit(main())
