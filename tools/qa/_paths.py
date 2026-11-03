# -*- coding: utf-8 -*-
"""submod 工具链的路径常量：唯一真源，换机器只改这里。

优先级：环境变量 > 本文件默认值。
    MVL_SUBMOD_OUT   本 submod 目录
    MVL_CN           muvluvCN        (workshop 2800380626)
    MVL_SUB          muvluvCNsub     (workshop 2989050816)
    MVL_HIS          个人适配版       (workshop 3823420258)
    MVL_GAME         原版游戏根
"""
import io
import os
import re
import sys

# 控制台中文不乱码（Windows 默认 cp936 会把中文输出成乱码）
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

_DEF = {
    'MODDIR': r'C:\Users\33206\Documents\Paradox Interactive\Hearts of Iron IV\mod',
    'CN': r'E:\SteamLibrary\steamapps\workshop\content\394360\2800380626',
    'SUB': r'E:\SteamLibrary\steamapps\workshop\content\394360\2989050816',
    'HIS': r'E:\SteamLibrary\steamapps\workshop\content\394360\3823420258',
    'GAME': r'E:\SteamLibrary\steamapps\common\Hearts of Iron IV',
    'WORK_MODS': r'D:\大肥鱼工作区\HOI4 MUVLUVsub mod 制作\mods',
}
_ENV = {
    'MODDIR': 'MVL_MODDIR',
    'OUT': 'MVL_SUBMOD_OUT',
    'CN': 'MVL_CN',
    'SUB': 'MVL_SUB',
    'HIS': 'MVL_HIS',
    'GAME': 'MVL_GAME',
    'WORK_MODS': 'MVL_WORK_MODS',
}

MODDIR = os.environ.get(_ENV['MODDIR']) or _DEF['MODDIR']
CN = os.environ.get(_ENV['CN']) or _DEF['CN']
SUB = os.environ.get(_ENV['SUB']) or _DEF['SUB']
HIS = os.environ.get(_ENV['HIS']) or _DEF['HIS']
GAME = os.environ.get(_ENV['GAME']) or _DEF['GAME']
WORK_MODS = os.environ.get(_ENV['WORK_MODS']) or _DEF['WORK_MODS']

# submod 目录名（也是 .mod 文件名，两者必须一致）
# 用 ASCII：Steam 上传、备份、跨工具链都稳。创意工坊显示名见 DISPLAY_NAME。
NAME = 'muvluvCNsub_xuerong'
OUT = os.environ.get(_ENV['OUT']) or os.path.join(MODDIR, NAME)

# 工作副本：日常改动在这里做。
HIS_WORK = os.path.join(WORK_MODS, 'muvluvCN_personal')
OUT_WORK = os.path.join(WORK_MODS, NAME)

# 创意工坊上传成功并订阅之后，Steam 会在 workshop 下放一份，
# 游戏加载的是那一份，不是 OUT。2026-10-30 确认：启动器数据库里
# source=steam、dirPath 指向 STEAM_COPY，Documents\...\mod\ 下那份已无 .mod，没人读。
# 用 SUB 的父目录推，不硬编码盘符。
WORKSHOP_ID = '3829617696'
STEAM_COPY = os.path.join(os.path.dirname(SUB), WORKSHOP_ID)


def load_base():
    """游戏实际加载的那份目录。

    判断顺序（2026-10-31 修正）：
      1. `mod/<NAME>.mod` 存在且 path 指向真实目录 → 返回它。
         本地自建 .mod 与工坊订阅版同名共存时，生效的是启动器里选中的那个；
         有本地 .mod 且路径有效，说明在用本地那份。
      2. 否则退回工坊订阅副本。
      3. 再否则返回 OUT。

    旧实现无条件优先工坊副本，导致工具链一直在检查落后一个系统的 75 文件版，
    而游戏读的是 104 文件版 —— 这也是 2026-10-30 那次「读工坊」结论出现偏差的原因。
    """
    local_mod = os.path.join(MODDIR, NAME + '.mod')
    if os.path.exists(local_mod):
        try:
            t = io.open(local_mod, encoding='utf-8-sig', errors='replace').read()
            m = re.search(r'path\s*=\s*"([^"]+)"', t)
            if m:
                target = m.group(1).replace('/', os.sep)
                if os.path.isdir(target):
                    return target
        except OSError:
            pass
    if os.path.isdir(STEAM_COPY):
        return STEAM_COPY
    return OUT

# 创意工坊标题 / 启动器里显示的名字（.mod 与 descriptor.mod 的 name 字段）
DISPLAY_NAME = 'muvluvCNsub雪绒拓展'

# submod 版本号（写进 descriptor.mod 和外部 .mod）
# x = 架构/系统重构，y = 新功能，z = 修 bug
VERSION = '0.1.3'

# 23 个覆盖基座的文件（整文件替换，长期维护的只有这些）
# 2026-10-30 移除 common/technologies/MVLV_Shell.txt：
#   md5 与 muvluvCNsub 完全一致（180 bytes），属于白拷，删掉后由基座那份生效，效果不变。
CHG = '''common/ai_strategy/doctrines.txt
common/ai_templates/generic.txt
common/ai_templates/templates_BET.txt
common/country_leader/00_traits.txt
common/ideas/MVLV_zzz_generic.txt
common/raids/air_raids.txt
common/raids/air_raids_custom.txt
common/raids/categories/raid_categories.txt
common/raids/nuclear_raids.txt
common/script_enums.txt
common/technologies/air_doctrine.txt
common/technologies/land_doctrine.txt
common/technologies/naval_doctrine.txt
common/technologies/support.txt
common/technology_tags/00_technology.txt
common/units/equipment/MVLV_AL_shell.txt
common/units/equipment/MVLV_shell.txt
common/units/equipment/ship_hull_submarine.txt
credit.txt
localisation/english/replace/MVLV_ideas_l_englishUnfinished.yml
localisation/simp_chinese/replace/MVLV_ideas_l_simp_chinese.yml
music/_songs.txt
music/music.asset'''.split()

# 上面这些里，music/music.asset 不是从适配版拷，而是 _build_submod.py 生成的
# （内容 = CN 当前那份原文 + 本 submod 的 8 首开局曲），见 MUSIC_ASSET

# 只在个人适配版里存在、必须随包的图片（基座和原版都没有）
# 由 _audit_gfx.py 判定，漏拷会导致紫方块/空白图标
ONLY_IN_HIS = '''gfx/interface/equipment/mvlv_hydrogen_strategic.dds
gfx/interface/equipment/mvlv_hydrogen_tactical.dds
gfx/interface/mvlv119/dust_topbar_icon.dds'''.split()

# 开局主题曲：歌曲 key -> 音频文件（路径相对 music/）
#
# 两个层次必须都有，少一个就是静音：
#   1) 本体  写进 music/*.asset 的 music = { name = ... file = ... }   ← 定义哪首歌
#   2) 列表  写进 music/*.txt 的 music_station = "base_music" + song = ...  ← 哪首歌参不参与轮播
# 只写第 2 层，游戏会报 `Could not find music named <key>`，scoped_play_song 静默失败。
# 音频本体由 muvluvCN 提供（music/ 各子目录），本 submod 只提供注册。
SONGS = [
    ('mvlv_start_eea', 'Schwarzesmarken/1.14 仄暗い空の下で.ogg'),
    ('mvlv_start_uni', 'Muv-Luv-Others/07 紫音 -sion-.ogg'),
    ('mvlv_start_geu', 'Muv-Luv-Alternative/14 血を欲する戦場.ogg'),
    ('mvlv_start_chi', 'Muv-Luv-Alternative/15 迎撃.ogg'),
    ('mvlv_start_eur', 'Schwarzesmarken/1.02 覚悟を新たに.ogg'),
    ('mvlv_start_usa', 'Muv-Luv-Others/10 遥かなる地球の歌.ogg'),
    ('mvlv_start_jap', 'Muv-Luv-Alternative/13 臨戦態勢.ogg'),
    ('mvlv_start_sov', 'Muv-Luv-Others/11 Revise the World.ogg'),
]

# 本 submod 自己生成（不是从适配版拷）的文件
#
# 名字必须是 music.asset：CN 的 music/ 顶层只有这一个 .asset，非标准名能否在顶层被扫到
# 没有直接证据（子目录里 CN 确实用了 *_music.asset 这种自定义名，但那不等于顶层）。
# 这里选已验证有效的标准名，覆盖代价由 _verify_submod.py 6.4 那项检查兜住：
# 生成内容 = 基座当前那份的原文 + 我的 8 首，基座以后加歌，检查会 FAIL 提示同步。
MUSIC_ASSET = 'music/music.asset'
MUSIC_SONGS = 'music/_songs.txt'   # 这个是从适配版拷的（CN 那份的超集，覆盖无损失）


def p(base, rel):
    """把 mod 内部相对路径（正斜杠）拼到 base 上。"""
    return os.path.join(base, rel.replace('/', os.sep))


def walk_files(base):
    for dp, _, fs in os.walk(base):
        for f in fs:
            yield os.path.join(dp, f)


def check_roots(strict=True):
    """启动自检：报告哪些根不存在，strict 时返回 False 让人别继续跑。"""
    ok = True
    for name, path in (('OUT', OUT), ('CN', CN), ('SUB', SUB),
                       ('HIS', HIS), ('GAME', GAME),
                       ('HIS_WORK', HIS_WORK), ('OUT_WORK', OUT_WORK)):
        if not os.path.isdir(path):
            print('[路径] %-4s 不存在: %s' % (name, path))
            ok = False
    if not ok and strict:
        print('先改 work/qa/_paths.py，或设环境变量 MVL_SUBMOD_OUT / MVL_CN / MVL_SUB / MVL_HIS / MVL_GAME')
    return ok
