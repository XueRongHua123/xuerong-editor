# -*- coding: utf-8 -*-
"""成员页预览：常任理事国加 ★（按新名单 JAP/SOV/EUR/OSE/CHI）。"""
import os

from PIL import Image, ImageDraw, ImageFont

W, H = 980, 680
OUT = r'work\tmp\ui_preview_members.png'
FB = r'C:\Windows\Fonts\msyhbd.ttc'
FR = r'C:\Windows\Fonts\msyh.ttc'
PANEL = (20, 34, 46)
LINE = (74, 139, 168)
TEXT = (226, 236, 242)
DIM = (150, 172, 186)
FAINT = (108, 128, 142)
GOLD = (224, 176, 92)

# (名字, 是否常任)
MEMBERS = [
    ('国联联合军', False), ('澳大利亚', True),
    ('欧洲联合', True), ('大东亚联合', False),
    ('中美联合', False), ('南美联合', False),
    ('非洲联合', False), ('东欧社会主义同盟', False),
    ('日本帝国', True), ('美利坚合众国', False),
    ('加拿大', False), ('统一中华战线', True),
    ('苏维埃联盟', True),
]


def f(s, bold=True):
    return ImageFont.truetype(FB if bold else FR, s)


def main():
    im = Image.new('RGB', (W, H), (10, 16, 22))
    d = ImageDraw.Draw(im, 'RGBA')
    d.rectangle([0, 0, W - 1, H - 1], fill=PANEL, outline=LINE, width=2)
    d.rectangle([2, 2, W - 3, 96], fill=(24, 40, 54), outline=LINE, width=1)
    d.ellipse([16, 12, 56, 52], outline=LINE, width=2, fill=(30, 52, 68))
    d.text((26, 20), 'UN', font=f(13), fill=(120, 190, 220))
    d.text((66, 14), '安全保障理事会', font=f(22), fill=TEXT)
    d.text((66, 48), '休会', font=f(15, False), fill=DIM)
    d.text((66, 68), '席位 14 · 门槛 8', font=f(13, False), fill=DIM)
    d.text((W - 152, 14), '共识：紧张', font=f(13, False), fill=GOLD)
    d.text((W - 152, 36), '预算：正常', font=f(13, False), fill=TEXT)

    for i, t in enumerate(['会场', '决议', '成员', '记录']):
        x = 20 + i * 238
        on = i == 2
        d.rectangle([x, 104, x + 230, 134], fill=(30, 54, 70) if on else (18, 30, 42),
                    outline=LINE if on else (50, 80, 100), width=2 if on else 1)
        tw = d.textlength(t, font=f(15))
        d.text((x + (230 - tw) / 2, 107), t, font=f(15), fill=TEXT if on else DIM)

    d.rectangle([20, 144, W - 20, 208], fill=(26, 44, 58), outline=(40, 68, 88))
    tw = d.textlength('（会场背景图）', font=f(13, False))
    d.text(((W - tw) / 2, 168), '（会场背景图）', font=f(13, False), fill=(70, 100, 120))

    # 标题
    d.text((24, 216), '成员国与立场', font=f(15), fill=TEXT)
    d.text((24, 240), '13 个成员国。★ 为常任理事国（安理会可行使否决权）：日本帝国 / 苏维埃联盟 / 欧洲联合 / 澳大利亚 / 统一中华战线。',
           font=f(11, False), fill=DIM)

    # 两列
    top = 272
    rowh = 30
    for i, (name, perm) in enumerate(MEMBERS):
        col, row = divmod(i, 7)
        x = 24 + col * 466
        y = top + row * rowh
        # 旗位
        d.rectangle([x, y + 4, x + 20, y + 18], fill=(60, 90, 120), outline=(150, 180, 200))
        # 名字（常任加 ★，金色）
        label = ('★ ' if perm else '') + name
        d.text((x + 30, y + 3), label, font=f(14), fill=GOLD if perm else TEXT)
        # 立场
        d.text((x + 250, y + 4), '弃权', font=f(13, False), fill=DIM)
        d.rectangle([x + 300, y + 3, x + 396, y + 21], fill=(18, 30, 42), outline=(50, 80, 100))
        d.text((x + 404, y + 4), '游说', font=f(12, False), fill=(110, 140, 160))

    # 底部说明
    d.text((24, 520), '评分是表决原始分：55 以上赞成，40-54 弃权，39 以下反对。常任理事国在安理会类议题上反对，即构成否决。',
           font=f(11, False), fill=FAINT)
    d.text((24, 544), '行尾「游说」花 1 点国际合法性，把该国拉到赞成，每国每会期一次。',
           font=f(11, False), fill=FAINT)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    im.save(OUT, 'PNG')
    print('已生成', OUT, im.size)


if __name__ == '__main__':
    main()
