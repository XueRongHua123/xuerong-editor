# -*- coding: utf-8 -*-
"""画会场页改版 UI 的预览图（PIL 绘制，980×680，与游戏窗口同尺寸）。

新版三栏按实际数据分布设计：赞成/反对通常是少数，弃权是常态，
所以三栏不等宽（200 / 200 / 520），旗子排成一行而不是网格。
"""
import os

from PIL import Image, ImageDraw, ImageFont

W, H = 980, 680
OUT = r'work\tmp\ui_preview_agenda.png'
F_BOLD = r'C:\Windows\Fonts\msyhbd.ttc'
F_REG = r'C:\Windows\Fonts\msyh.ttc'

BG = (14, 24, 34, 255)
PANEL = (20, 34, 46, 255)
LINE = (74, 139, 168, 255)
TEXT = (226, 236, 242, 255)
DIM = (150, 172, 186, 255)
GOLD = (214, 168, 96, 255)
GREEN = (96, 190, 130, 255)
RED = (200, 96, 96, 255)
GREY = (130, 140, 150, 255)


def f(size, bold=True):
    return ImageFont.truetype(F_BOLD if bold else F_REG, size)


def main():
    im = Image.new('RGB', (W, H), (10, 16, 22))
    d = ImageDraw.Draw(im, 'RGBA')

    # 窗口底板
    d.rectangle([0, 0, W - 1, H - 1], fill=PANEL, outline=LINE, width=2)
    # 顶部标题栏
    d.rectangle([2, 2, W - 3, 96], fill=(24, 40, 54, 255), outline=LINE, width=1)
    d.text((22, 14), '联合国大会', font=f(22), fill=TEXT)
    d.text((22, 44), '休会', font=f(16, False), fill=DIM)
    d.text((22, 66), '席位 14 · 门槛 8', font=f(14, False), fill=DIM)
    d.text((W - 150, 14), '共识：紧张', font=f(14, False), fill=GOLD)
    d.text((W - 150, 36), '预算：正常', font=f(14, False), fill=TEXT)

    # 页签
    tabs = ['会场', '决议', '成员', '记录']
    for i, t in enumerate(tabs):
        x = 20 + i * 238
        on = (i == 0)
        d.rectangle([x, 104, x + 230, 136], fill=(30, 54, 70) if on else (18, 30, 42),
                    outline=LINE if on else (50, 80, 100), width=2 if on else 1)
        d.text((x + 100, 108), t, font=f(16), fill=TEXT if on else DIM)

    # 会场背景带（示意）
    d.rectangle([20, 146, W - 20, 230], fill=(26, 44, 58, 255), outline=(40, 68, 88))
    d.text((W // 2 - 130, 180), '（会场背景图区域）', font=f(15, False), fill=(70, 100, 120))

    # ---- 左栏 ----
    lx = 24
    d.text((lx, 250), '秘书长', font=f(15), fill=TEXT)
    d.text((lx, 272), '席位空缺', font=f(14, False), fill=DIM)
    d.text((lx, 294), '选举尚未举行，秘书处由副秘书长代管。', font=f(12, False), fill=DIM)
    d.text((lx, 336), '观察员席位', font=f(15), fill=TEXT)
    d.text((lx, 358), '无观察员', font=f(14, False), fill=DIM)
    d.text((lx, 380), '失去领土的国家在走廊里等待着。', font=f(12, False), fill=DIM)
    d.text((lx, 422), '上期表决', font=f(15), fill=TEXT)
    d.text((lx, 444), '休会期间 · 尚无表决', font=f(14, False), fill=DIM)

    # ---- 中栏：议程 ----
    mx = 340
    d.text((mx, 250), '本轮议程', font=f(15), fill=TEXT)
    d.text((mx, 272), '休会期间', font=f(14, False), fill=DIM)
    d.text((mx, 294), '没有待表决的议题。秘书处正在准备下一轮议程。', font=f(12, False), fill=DIM)
    d.text((mx, 330), '效果：无待表决议题。', font=f(13, False), fill=DIM)

    # ================= 新版三栏 =================
    top = 372
    bh = 104
    cols = [
        ('赞成', 3, x0, x0 + 196, GREEN),
    ] if False else None
    lay = [(lx, 196, '赞成', GREEN), (lx + 208, 196, '反对', RED), (lx + 416, W - 20 - (lx + 416), '弃权', GREY)]
    for x0, cw, name, color in lay:
        x1 = x0 + cw
        d.rectangle([x0, top, x1, top + bh], fill=(16, 28, 38, 255), outline=LINE, width=1)
        d.rectangle([x0, top, x1, top + 24], fill=(28, 48, 62, 255), outline=LINE, width=1)
        d.text((x0 + 10, top + 3), name, font=f(14), fill=color)
        # 旗子（示意方块，一行）
        flags = {'赞成': 3, '反对': 1, '弃权': 10}[name]
        for k in range(flags):
            fx = x0 + 10 + k * 20
            fy = top + 36
            d.rectangle([fx, fy, fx + 15, fy + 11], fill=(60, 90, 120) if k % 2 else (90, 70, 100),
                        outline=(150, 180, 200))
        if flags == 0:
            d.text((x0 + 12, top + 44), '（无）', font=f(12, False), fill=(80, 96, 108))

    # 游说提示
    d.text((lx, top + bh + 8), '点旗子可游说（+1 合法性），每国每会期一次', font=f(12, False), fill=(110, 130, 145))

    # 三个投票按钮
    by = top + bh + 32
    for x0, cw, name, color in lay:
        d.rectangle([x0, by, x0 + cw, by + 30], fill=(22, 40, 52, 255), outline=color, width=2)
        tw = d.textlength('投' + name, font=f(15))
        d.text((x0 + (cw - tw) / 2, by + 5), '投' + name, font=f(15), fill=color)

    # 倒计时 + 通过投票
    d.text((lx, by + 46), '表决一周后截止；票数达标可点「通过投票」提前结束', font=f(13, False), fill=DIM)
    d.rectangle([lx, by + 70, lx + 196, by + 100], fill=(24, 44, 56, 255), outline=(90, 120, 140), width=1)
    d.text((lx + 46, by + 75), '通过投票', font=f(14, False), fill=(120, 140, 155))

    # 说明
    d.text((mx, by + 46), '休会期间三栏为空；开会后按立场分栏显示', font=f(13, False), fill=(96, 150, 120))

    # 页脚
    d.text((lx, H - 96), '新议题在「决议」页提交。', font=f(13, False), fill=DIM)
    d.text((lx, H - 72), '五个板块：安全与核威慑、政治与司法、经济与资源、科技与计划、席位与授权。', font=f(12, False), fill=DIM)
    d.text((lx, H - 48), '本页只负责表决：三栏国旗是各国立场，点反对或弃权栏的旗子可以游说。', font=f(12, False), fill=DIM)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    im.save(OUT, 'PNG')
    print('已生成', OUT, im.size)


if __name__ == '__main__':
    main()
