# -*- coding: utf-8 -*-
"""会场页改版 UI 预览图（980×680，与游戏窗口同尺寸）。

布局分区：
  顶栏 0-96 / 页签 104-136 / 背景带 146-208
  信息行 216-286（秘书长 | 观察员 | 上期表决，三块并排，省垂直空间）
  议程区 296-352
  三栏 362-466（不等宽：赞成/反对各 200，弃权占余下）
  按钮 478-508 / 倒计时 518 / 通过投票 536-566
  页脚 588-656
"""
import os

from PIL import Image, ImageDraw, ImageFont

W, H = 980, 680
OUT = r'work\tmp\ui_preview_agenda.png'
FB = r'C:\Windows\Fonts\msyhbd.ttc'
FR = r'C:\Windows\Fonts\msyh.ttc'

PANEL = (20, 34, 46)
LINE = (74, 139, 168)
TEXT = (226, 236, 242)
DIM = (150, 172, 186)
FAINT = (108, 128, 142)
GOLD = (214, 168, 96)
GREEN = (96, 190, 130)
RED = (200, 96, 96)
GREY = (140, 150, 160)


def f(s, bold=True):
    return ImageFont.truetype(FB if bold else FR, s)


def main():
    im = Image.new('RGB', (W, H), (10, 16, 22))
    d = ImageDraw.Draw(im, 'RGBA')

    # 窗口
    d.rectangle([0, 0, W - 1, H - 1], fill=PANEL, outline=LINE, width=2)
    d.rectangle([2, 2, W - 3, 96], fill=(24, 40, 54), outline=LINE, width=1)
    d.text((22, 12), '联合国大会', font=f(22), fill=TEXT)
    d.text((22, 44), '休会', font=f(15, False), fill=DIM)
    d.text((22, 66), '席位 14 · 门槛 8', font=f(13, False), fill=DIM)
    d.text((W - 152, 12), '共识：紧张', font=f(13, False), fill=GOLD)
    d.text((W - 152, 34), '预算：正常', font=f(13, False), fill=TEXT)

    # 页签
    for i, t in enumerate(['会场', '决议', '成员', '记录']):
        x = 20 + i * 238
        on = i == 0
        d.rectangle([x, 104, x + 230, 134], fill=(30, 54, 70) if on else (18, 30, 42),
                    outline=LINE if on else (50, 80, 100), width=2 if on else 1)
        tw = d.textlength(t, font=f(15))
        d.text((x + (230 - tw) / 2, 107), t, font=f(15), fill=TEXT if on else DIM)

    # 背景带
    d.rectangle([20, 144, W - 20, 208], fill=(26, 44, 58), outline=(40, 68, 88))
    tw = d.textlength('（会场背景图）', font=f(14, False))
    d.text(((W - tw) / 2, 168), '（会场背景图）', font=f(14, False), fill=(70, 100, 120))

    # ===== 信息行：三块并排 =====
    ix, iy = 24, 216
    blocks = [
        ('秘书长', ['席位空缺', '选举尚未举行，秘书处由副秘书长代管。']),
        ('观察员席位', ['无观察员', '失去领土的国家在走廊里等待着。']),
        ('上期表决', ['休会期间', '尚无表决']),
    ]
    bw = 300
    for k, (title, lines) in enumerate(blocks):
        x = ix + k * (bw + 12)
        d.text((x, iy), title, font=f(14), fill=TEXT)
        d.text((x, iy + 22), lines[0], font=f(13, False), fill=DIM)
        if len(lines) > 1:
            d.text((x, iy + 42), lines[1], font=f(11, False), fill=FAINT)

    # ===== 议程区 =====
    ay = 296
    d.text((ix, ay), '本轮议程', font=f(14), fill=TEXT)
    d.text((ix + 80, ay), '休会期间 · 没有待表决的议题，秘书处正在准备下一轮。',
           font=f(12, False), fill=DIM)
    d.text((ix, ay + 24), '效果：—', font=f(12, False), fill=FAINT)

    # ===== 三栏（新版）=====
    top, bh = 362, 104
    lay = [(ix, 200, '赞成', GREEN, 3), (ix + 212, 200, '反对', RED, 1),
           (ix + 424, W - 24 - (ix + 424), '弃权', GREY, 10)]
    for x0, cw, name, color, n in lay:
        x1 = x0 + cw
        d.rectangle([x0, top, x1, top + bh], fill=(16, 28, 38), outline=LINE, width=1)
        d.rectangle([x0, top, x1, top + 22], fill=(28, 48, 62), outline=LINE, width=1)
        d.text((x0 + 10, top + 2), name, font=f(13), fill=color)
        cnt = str(n)
        d.text((x1 - 10 - d.textlength(cnt, font=f(13)), top + 2), cnt, font=f(13), fill=TEXT)
        # 旗子（示意）
        for k in range(n):
            fx = x0 + 10 + k * 19
            fy = top + 32
            d.rectangle([fx, fy, fx + 14, fy + 10],
                        fill=(60, 90, 120) if k % 2 else (88, 68, 98), outline=(150, 180, 200))
        if n == 0:
            d.text((x0 + 12, top + 38), '（无）', font=f(11, False), fill=(70, 86, 98))

    # 按钮
    by = 480
    for x0, cw, name, color, _n in lay:
        d.rectangle([x0, by, x0 + cw, by + 28], fill=(22, 40, 52), outline=color, width=2)
        t = '投' + name
        d.text((x0 + (cw - d.textlength(t, font=f(14))) / 2, by + 5), t, font=f(14), fill=color)

    d.text((ix, by + 38), '表决一周后截止；票数达标可点「通过投票」提前结束，期间仍可游说',
           font=f(12, False), fill=DIM)
    d.rectangle([ix, by + 60, ix + 200, by + 88], fill=(24, 44, 56), outline=(90, 120, 140))
    t = '通过投票'
    d.text((ix + (200 - d.textlength(t, font=f(13))) / 2, by + 65), t, font=f(13), fill=(120, 140, 155))

    # 页脚
    fy = 592
    d.text((ix, fy), '新议题在「决议」页提交；五个板块：安全与核威慑 / 政治与司法 / 经济与资源 / 科技与计划 / 席位与授权。',
           font=f(11, False), fill=FAINT)
    d.text((ix, fy + 22), '本页只负责表决：三栏国旗是各国立场，点反对或弃权栏的旗子可以游说。',
           font=f(11, False), fill=FAINT)
    d.text((ix, fy + 44), '休会期间三栏为空，开会后按立场分栏显示。',
           font=f(11, False), fill=(96, 150, 120))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    im.save(OUT, 'PNG')
    print('已生成', OUT, im.size)


if __name__ == '__main__':
    main()
