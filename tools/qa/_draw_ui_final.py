# -*- coding: utf-8 -*-
"""按代码里的实际坐标画会场页预览图（980×680）。

坐标全部取自 zz_mvlv119_un_window.gui，不是估算：
  信息行 216/234/258 @ 24 / 336 / 648
  议程   296 / 314 / 338（desc 640 宽；effect x=676）
  三栏   chip 386, grid 410-470；列宽 24-224 / 236-436 / 448-956
  按钮   478（各栏下方），标签 484
  倒计时 516；通过投票 534；付/退出 534/564；说明 x=484 y=534
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
    d.rectangle([0, 0, W - 1, H - 1], fill=PANEL, outline=LINE, width=2)

    # 顶栏
    d.rectangle([2, 2, W - 3, 96], fill=(24, 40, 54), outline=LINE, width=1)
    # 联合国徽记（圆形示意）
    d.ellipse([16, 12, 56, 52], outline=LINE, width=2, fill=(30, 52, 68))
    d.text((26, 20), 'UN', font=f(13), fill=(120, 190, 220))
    d.text((66, 14), '安全保障理事会', font=f(22), fill=TEXT)
    d.text((66, 48), '休会', font=f(15, False), fill=DIM)
    d.text((66, 68), '席位 14 · 门槛 8', font=f(13, False), fill=DIM)
    d.text((W - 152, 14), '共识：紧张', font=f(13, False), fill=GOLD)
    d.text((W - 152, 36), '预算：正常', font=f(13, False), fill=TEXT)

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
    tw = d.textlength('（会场背景图）', font=f(13, False))
    d.text(((W - tw) / 2, 168), '（会场背景图）', font=f(13, False), fill=(70, 100, 120))

    # ---- 信息行：三块并排 @24/336/648 ----
    info = [
        (24, '秘书长', '国联推举 · 改革派', '任期 365 天 · 消费品 -2%、政治点 +5%'),
        (336, '观察员席位', '非洲联合作为观察员入席', '理事会 +1 票'),
        (648, '上期表决', '休会期间', '尚无表决'),
    ]
    for x, title, main, sub in info:
        d.text((x, 216), title, font=f(14), fill=TEXT)
        d.text((x, 236), main, font=f(15), fill=TEXT if title != '上期表决' else DIM)
        d.text((x, 260), sub, font=f(11, False), fill=FAINT)

    # ---- 议程 ----
    d.text((24, 296), '本轮议程', font=f(13), fill=FAINT)
    d.text((24, 314), '休会期间 · 没有待表决的议题', font=f(17), fill=DIM)
    d.text((24, 340), '秘书处正在准备下一轮议程。', font=f(11, False), fill=FAINT)
    d.text((676, 340), '效果：—', font=f(11, False), fill=FAINT)

    # ---- 三栏 ----
    lay = [(24, 200, 2, '赞成', GREEN, 3), (236, 200, 2, '反对', RED, 1),
           (448, 508, 5, '弃权', GREY, 10)]
    for x, w, cols, name, color, n in lay:
        # chip
        d.rectangle([x, 386, x + w - 8, 408], fill=(28, 48, 62), outline=LINE, width=1)
        d.text((x + 8, 388), name, font=f(13), fill=color)
        cnt = str(n)
        d.text((x + w - 16 - d.textlength(cnt, font=f(13)), 388), cnt, font=f(13), fill=TEXT)
        # grid 外框
        d.rectangle([x, 410, x + w, 470], fill=(16, 28, 38), outline=(50, 80, 100))
        # 旗子：按 cols 列排
        for k in range(n):
            r, c = divmod(k, cols)
            fx = x + 8 + c * 96
            fy = 414 + r * 14
            d.rectangle([fx, fy, fx + 14, fy + 10],
                        fill=(60, 90, 120) if k % 2 else (88, 68, 98), outline=(150, 180, 200))
        if n == 0:
            d.text((x + 10, 420), '（无）', font=f(11, False), fill=(70, 86, 98))

    # 按钮
    for x, w, _c, name, color, _n in lay:
        d.rectangle([x, 478, x + w, 506], fill=(22, 40, 52), outline=color, width=2)
        t = '投' + name
        d.text((x + (w - d.textlength(t, font=f(14))) / 2, 483), t, font=f(14), fill=color)

    # 倒计时 + 通过投票
    d.text((24, 516), '表决一周后截止；票数达标可点「通过投票」提前结束', font=f(12, False), fill=DIM)
    d.rectangle([24, 534, 224, 562], fill=(24, 44, 56), outline=(90, 120, 140))
    t = '通过投票'
    d.text((24 + (200 - d.textlength(t, font=f(13))) / 2, 539), t, font=f(13), fill=(120, 140, 155))

    # 付/退出
    for i, (label, tip) in enumerate([('缴纳核责任金', '缴清责任金'), ('退出温哥华协议', '退约')]):
        y = 534 + i * 30
        d.rectangle([236, y, 472, y + 26], fill=(22, 40, 52), outline=(70, 110, 130))
        d.text((244, y + 4), label, font=f(12, False), fill=TEXT)

    # 说明
    d.text((484, 534), '本页只负责表决：三栏国旗是各国立场，', font=f(11, False), fill=FAINT)
    d.text((484, 552), '点反对或弃权栏的旗子可以游说。', font=f(11, False), fill=FAINT)
    d.text((484, 570), '休会期间三栏为空，开会后按立场分栏显示。', font=f(11, False), fill=(96, 150, 120))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    im.save(OUT, 'PNG')
    print('已生成', OUT, im.size)


if __name__ == '__main__':
    main()
