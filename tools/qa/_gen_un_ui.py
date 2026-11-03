# -*- coding: utf-8 -*-
"""生成联合国大会面板的界面素材。

照片源：work/assets/un_hq_flags.jpg（联合国大会厅实拍）
产出（直接写进 submod 包内）：
  gfx/interface/un/mvlv119_un_panel_bg.png   502x320  照片底 + 深色承托板 + 六边形网格 + 边框
  gfx/interface/un/mvlv119_un_chip.png       150x20   投票栏标题底
  gfx/interface/un/mvlv119_un_divider.png    478x3    分隔线

依赖 Pillow。改配色/尺寸改本文件重跑，不手改图片。
"""

import os

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, 'work', 'assets', 'un_hq_flags.jpg')
OUT_DIR = os.path.join(ROOT, 'mods', 'muvluvCNsub_xuerong', 'gfx', 'interface', 'un')

W, H = 502, 320
BODY_TOP = 96          # 深色承托板起点


def duotone_lut():
    """灰度 -> 深海军蓝到青白。"""
    r, g, b = [], [], []
    for i in range(256):
        v = (i / 255.0) ** 1.1
        r.append(int(min(255, 6 + 150 * (v ** 1.9))))
        g.append(int(min(255, 18 + 205 * (v ** 1.35))))
        b.append(int(min(255, 38 + 225 * (v ** 1.05))))
    return r, g, b


def photo_base():
    """顶部照片条 + 下方深蓝底。照片取讲台与会席，能认出是联合国大会厅。"""
    im = Image.open(SRC).convert('RGB').crop((0, 180, 800, 360)).resize((W, 113), Image.LANCZOS)
    gray = ImageOps.autocontrast(im.convert('L'), cutoff=1).filter(ImageFilter.GaussianBlur(0.5))
    gray = ImageEnhance.Contrast(gray).enhance(1.20)
    lr, lg, lb = duotone_lut()
    strip = Image.merge('RGB', (gray.point(lr), gray.point(lg), gray.point(lb)))
    strip = ImageEnhance.Brightness(strip).enhance(0.95).convert('RGBA')

    canvas = Image.new('RGBA', (W, H), (7, 15, 30, 255))
    canvas.paste(strip, (0, 0))

    # 照片条底部渐隐到面板底
    fade = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(fade)
    for y in range(84, 113):
        a = int(255 * (y - 84) / 29.0)
        d.line([(0, y), (W, y)], fill=(7, 15, 30, a))
    return Image.alpha_composite(canvas, fade)


def hex_grid(size, step=17.0, alpha=26):
    layer = Image.new('RGBA', size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    import math
    dx = step * 1.5
    dy = step * math.sqrt(3)
    col = 0
    x = -step
    while x < size[0] + step:
        off = dy / 2 if col % 2 else 0
        y = -step + off
        while y < size[1] + step:
            pts = [(x + math.cos(math.pi / 3 * k) * step,
                    y + math.sin(math.pi / 3 * k) * step) for k in range(6)]
            d.line(pts + [pts[0]], fill=(60, 130, 175, alpha), width=1)
            y += dy
        x += dx
        col += 1
    return layer


def build_panel():
    img = photo_base()

    # 顶部/左侧压暗：标题与状态文字要能读
    shade = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(shade)
    for y in range(0, 120):
        a = int(72 * (1 - y / 120.0) ** 1.2)
        d.line([(0, y), (W, y)], fill=(3, 8, 18, a))
    for x in range(0, 250):
        a = int(62 * (1 - x / 250.0) ** 1.3)
        d.line([(x, 0), (x, H)], fill=(3, 8, 18, a))
    img = Image.alpha_composite(img, shade)

    # 深色承托板：从 BODY_TOP 渐入，下面近乎不透明
    plate = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(plate)
    for y in range(BODY_TOP, H):
        a = int(244 * min(1.0, (y - BODY_TOP) / 18.0))
        d.line([(0, y), (W, y)], fill=(5, 11, 24, a))
    img = Image.alpha_composite(img, plate)

    img = Image.alpha_composite(img, hex_grid((W, H)))

    d = ImageDraw.Draw(img)
    c = 12
    edge = (34, 92, 120, 220)
    bright = (86, 214, 240, 255)
    # 外框
    d.line([(c, 0), (W - c, 0)], fill=edge)
    d.line([(c, H - 1), (W - c, H - 1)], fill=edge)
    d.line([(0, c), (0, H - c)], fill=edge)
    d.line([(W - 1, c), (W - 1, H - c)], fill=edge)
    # 内侧亮线
    d.line([(c, 1), (W - c, 1)], fill=(86, 214, 240, 90))
    d.line([(1, c), (1, H - c)], fill=(86, 214, 240, 90))
    # 四角斜切
    d.line([(0, c), (c, 0)], fill=bright, width=2)
    d.line([(W - 1, c), (W - c - 1, 0)], fill=bright, width=2)
    d.line([(0, H - c - 1), (c, H - 1)], fill=bright, width=2)
    d.line([(W - 1, H - c - 1), (W - c - 1, H - 1)], fill=bright, width=2)

    # 抬头分隔线（右端淡出）
    for x in range(12, 490):
        t = (x - 12) / 478.0
        a = int(235 * (1 - t) ** 0.6)
        d.point((x, 104), fill=(110, 232, 250, a))
        d.point((x, 105), fill=(40, 120, 160, int(a * 0.5)))

    # 脚注线
    for x in range(12, 490):
        t = (x - 12) / 478.0
        d.point((x, 272), fill=(90, 200, 230, int(90 * (1 - t) ** 1.2)))

    # 右上角三道短斜线（HUD 味）
    for k in range(3):
        x0 = W - 96 + k * 14
        d.line([(x0, 6), (x0 + 14, 6)], fill=(70, 200, 235, 150), width=2)

    img.convert('RGB').save(os.path.join(OUT_DIR, 'mvlv119_un_panel_bg.png'))
    print('panel_bg %dx%d %d KB' % (W, H, os.path.getsize(os.path.join(OUT_DIR, 'mvlv119_un_panel_bg.png')) // 1024))


def build_chip():
    w, h = 150, 20
    img = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.polygon([(0, 0), (w, 0), (w, h - 8), (w - 8, h), (0, h)], fill=(10, 34, 56, 225))
    d.line([(1, 1), (1, h - 1)], fill=(86, 220, 245, 245), width=2)
    d.line([(2, h - 2), (w - 9, h - 2)], fill=(64, 178, 210, 140))
    img.save(os.path.join(OUT_DIR, 'mvlv119_un_chip.png'))
    print('chip %dx%d' % (w, h))


def build_divider():
    w, h = 478, 3
    img = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for x in range(w):
        t = x / (w - 1)
        a = int(140 * max(0.0, 1 - abs(t - 0.35) / 0.75))
        d.point((x, 1), fill=(96, 220, 245, a))
        d.point((x, 0), fill=(60, 150, 190, int(a * 0.3)))
        d.point((x, 2), fill=(60, 150, 190, int(a * 0.3)))
    img.save(os.path.join(OUT_DIR, 'mvlv119_un_divider.png'))
    print('divider %dx%d' % (w, h))




# ---------------- 独立窗口（千禧黎明式） ----------------

WIN_W, WIN_H = 980, 680
WIN_STRIP = 200
WIN_PLATE = 182


def well(d, box, fill=(9, 24, 41, 200), bar=(86, 220, 245, 235)):
    x0, y0, x1, y1 = box
    d.rectangle([x0, y0, x1, y1], fill=fill)
    d.line([(x0, y0), (x1, y0)], fill=(60, 150, 190, 120))
    d.line([(x0, y1), (x1, y1)], fill=(30, 90, 120, 160))
    d.line([(x0 + 1, y0 + 2), (x0 + 1, y1 - 2)], fill=bar, width=3)


def build_window():
    im = Image.open(SRC).convert('RGB').crop((0, 150, 800, 313)).resize((WIN_W, WIN_STRIP), Image.LANCZOS)
    gray = ImageOps.autocontrast(im.convert('L'), cutoff=1).filter(ImageFilter.GaussianBlur(0.5))
    gray = ImageEnhance.Contrast(gray).enhance(1.20)
    lr, lg, lb = duotone_lut()
    strip = Image.merge('RGB', (gray.point(lr), gray.point(lg), gray.point(lb)))
    strip = ImageEnhance.Brightness(strip).enhance(0.95).convert('RGBA')

    canvas = Image.new('RGBA', (WIN_W, WIN_H), (7, 15, 30, 255))
    canvas.paste(strip, (0, 0))

    fade = Image.new('RGBA', (WIN_W, WIN_H), (0, 0, 0, 0))
    d = ImageDraw.Draw(fade)
    for y in range(168, WIN_STRIP):
        a = int(255 * (y - 168) / float(WIN_STRIP - 168))
        d.line([(0, y), (WIN_W, y)], fill=(7, 15, 30, a))
    canvas = Image.alpha_composite(canvas, fade)

    shade = Image.new('RGBA', (WIN_W, WIN_H), (0, 0, 0, 0))
    d = ImageDraw.Draw(shade)
    for y in range(0, 210):
        a = int(70 * (1 - y / 210.0) ** 1.2)
        d.line([(0, y), (WIN_W, y)], fill=(3, 8, 18, a))
    for x in range(0, 420):
        a = int(60 * (1 - x / 420.0) ** 1.3)
        d.line([(x, 0), (x, WIN_H)], fill=(3, 8, 18, a))
    canvas = Image.alpha_composite(canvas, shade)

    plate = Image.new('RGBA', (WIN_W, WIN_H), (0, 0, 0, 0))
    d = ImageDraw.Draw(plate)
    for y in range(WIN_PLATE, WIN_H):
        a = int(246 * min(1.0, (y - WIN_PLATE) / 18.0))
        d.line([(0, y), (WIN_W, y)], fill=(5, 11, 24, a))
    canvas = Image.alpha_composite(canvas, plate)
    canvas = Image.alpha_composite(canvas, hex_grid((WIN_W, WIN_H)))

    d = ImageDraw.Draw(canvas)
    c = 14
    edge = (34, 92, 120, 220)
    bright = (86, 214, 240, 255)
    d.line([(c, 0), (WIN_W - c, 0)], fill=edge)
    d.line([(c, WIN_H - 1), (WIN_W - c, WIN_H - 1)], fill=edge)
    d.line([(0, c), (0, WIN_H - c)], fill=edge)
    d.line([(WIN_W - 1, c), (WIN_W - 1, WIN_H - c)], fill=edge)
    d.line([(c, 1), (WIN_W - c, 1)], fill=(86, 214, 240, 90))
    d.line([(1, c), (1, WIN_H - c)], fill=(86, 214, 240, 90))
    d.line([(0, c), (c, 0)], fill=bright, width=2)
    d.line([(WIN_W - 1, c), (WIN_W - c - 1, 0)], fill=bright, width=2)
    d.line([(0, WIN_H - c - 1), (c, WIN_H - 1)], fill=bright, width=2)
    d.line([(WIN_W - 1, WIN_H - c - 1), (WIN_W - c - 1, WIN_H - 1)], fill=bright, width=2)

    # 抬头分隔线
    for x in range(14, WIN_W - 14):
        t = (x - 14) / float(WIN_W - 28)
        d.point((x, 196), fill=(110, 232, 250, int(235 * (1 - t) ** 0.6)))
        d.point((x, 197), fill=(40, 120, 160, int(100 * (1 - t) ** 0.6)))

    # 页签条：压在照片下缘，三格
    band = Image.new('RGBA', (WIN_W, WIN_H), (0, 0, 0, 0))
    db = ImageDraw.Draw(band)
    for y in range(72, 110):
        a = int(246 * min(1.0, (y - 72) / 5.0) * min(1.0, (110 - y) / 5.0))
        db.line([(0, y), (WIN_W, y)], fill=(4, 10, 20, a))
    for x in range(14, WIN_W - 14):
        tt = (x - 14) / float(WIN_W - 28)
        db.point((x, 110), fill=(86, 214, 240, int(150 * (1 - tt) ** 0.7)))
    canvas = Image.alpha_composite(canvas, band)

    d = ImageDraw.Draw(canvas)
    for i in range(4):
        x0 = 24 + i * 156
        d.rectangle([x0, 78, x0 + 148, 106], fill=(8, 21, 37, 238), outline=(44, 112, 144, 200))

    # 右上角三道短斜线
    for k in range(3):
        x0 = WIN_W - 130 + k * 16
        d.line([(x0, 8), (x0 + 16, 8)], fill=(70, 200, 235, 150), width=2)

    out = os.path.join(OUT_DIR, 'mvlv119_un_window_bg.png')
    canvas.convert('RGB').save(out)
    print('window_bg %dx%d %d KB' % (WIN_W, WIN_H, os.path.getsize(out) // 1024))




# ---------------- 事件配图（397x153） ----------------

PIC_W, PIC_H = 397, 153


def build_event_pic():
    im = Image.open(SRC).convert('RGB').crop((0, 120, 800, 428)).resize((PIC_W, PIC_H), Image.LANCZOS)
    gray = ImageOps.autocontrast(im.convert('L'), cutoff=1).filter(ImageFilter.GaussianBlur(0.4))
    gray = ImageEnhance.Contrast(gray).enhance(1.25)
    lr, lg, lb = duotone_lut()
    canvas = Image.merge('RGB', (gray.point(lr), gray.point(lg), gray.point(lb))).convert('RGBA')

    # 左右压暗，中间留亮
    shade = Image.new('RGBA', (PIC_W, PIC_H), (0, 0, 0, 0))
    d = ImageDraw.Draw(shade)
    for x in range(PIC_W):
        edge = min(x, PIC_W - 1 - x) / (PIC_W * 0.28)
        a = int(120 * max(0.0, 1 - edge))
        d.line([(x, 0), (x, PIC_H)], fill=(3, 8, 18, a))
    canvas = Image.alpha_composite(canvas, shade)

    # 徽记水印
    logo = Image.open(os.path.join(ROOT, 'work', 'preview', 'un_logo.png')).convert('RGBA')
    alpha = logo.split()[3].point(lambda v: int(v * 0.38))
    tint = Image.new('RGBA', logo.size, (150, 228, 248, 255))
    tint.putalpha(alpha)
    tint = tint.resize((104, 104), Image.LANCZOS)
    canvas.alpha_composite(tint, (PIC_W - 116, 24))

    d = ImageDraw.Draw(canvas)
    d.rectangle([0, 0, PIC_W - 1, PIC_H - 1], outline=(86, 214, 240, 110))
    d.line([(0, 0), (18, 0)], fill=(120, 230, 250, 255), width=2)
    d.line([(0, 0), (0, 16)], fill=(120, 230, 250, 255), width=2)
    d.line([(PIC_W - 1, PIC_H - 1), (PIC_W - 19, PIC_H - 1)], fill=(120, 230, 250, 255), width=2)
    d.line([(PIC_W - 1, PIC_H - 1), (PIC_W - 1, PIC_H - 17)], fill=(120, 230, 250, 255), width=2)

    out = os.path.join(ROOT, 'mods', 'muvluvCNsub_xuerong', 'gfx', 'interface', 'event_pictures',
                       'mvlv119_un_session.png')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    canvas.convert('RGB').save(out)
    print('event_pic %dx%d %d KB' % (PIC_W, PIC_H, os.path.getsize(out) // 1024))




# ---------------- 顶栏圆形入口按钮 ----------------

BTN = 44


def build_topbar_button():
    canvas = Image.new('RGBA', (BTN, BTN), (0, 0, 0, 0))
    d = ImageDraw.Draw(canvas)
    cx = cy = BTN / 2.0

    # 外圈暗底
    for r in range(int(cx), 0, -1):
        a = 235 if r > cx - 4 else 210
        col = (8, 22, 38, a) if r > 4 else (10, 30, 50, a)
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=col)
    # 青色双环
    d.ellipse([1, 1, BTN - 2, BTN - 2], outline=(86, 214, 240, 235), width=2)
    d.ellipse([5, 5, BTN - 6, BTN - 6], outline=(60, 150, 190, 120), width=1)

    # 徽记
    logo = Image.open(os.path.join(ROOT, 'work', 'preview', 'un_logo.png')).convert('RGBA')
    alpha = logo.split()[3].point(lambda v: int(v * 0.95))
    tint = Image.new('RGBA', logo.size, (196, 238, 252, 255))
    tint.putalpha(alpha)
    tint = tint.resize((30, 30), Image.LANCZOS)
    canvas.alpha_composite(tint, (7, 7))

    # 顶部高光
    d.arc([4, 3, BTN - 5, BTN - 5], 200, 340, fill=(180, 240, 255, 90), width=2)

    out = os.path.join(OUT_DIR, 'mvlv119_un_entry.png')
    canvas.save(out)
    print('entry button %dx%d %d KB' % (BTN, BTN, os.path.getsize(out) // 1024))


def button_face(size, fill=(8, 23, 40, 210), border=(48, 132, 168, 170),
                accent=(86, 214, 240, 225), bar=3):
    """带描边与左侧亮条的按钮底。"""
    w, h = size
    im = Image.new('RGBA', size, (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, w - 1, h - 1], fill=fill, outline=border)
    d.line([(1, 1), (w - 2, 1)], fill=(120, 220, 245, 70))
    if bar:
        d.rectangle([1, 2, bar, h - 3], fill=accent)
    return im


def build_buttons():
    out = button_face((196, 30))
    out.save(os.path.join(OUT_DIR, 'mvlv119_un_btn_vote.png'))
    out = button_face((448, 28), fill=(8, 22, 38, 170), border=(38, 104, 136, 140),
                      accent=(70, 180, 210, 190), bar=3)
    out.save(os.path.join(OUT_DIR, 'mvlv119_un_btn_res.png'))
    out = button_face((86, 20), fill=(10, 28, 46, 220), border=(58, 160, 190, 170),
                      accent=(86, 214, 240, 200), bar=2)
    out.save(os.path.join(OUT_DIR, 'mvlv119_un_btn_lobby.png'))
    out = button_face((268, 24), fill=(8, 24, 40, 200))
    out.save(os.path.join(OUT_DIR, 'mvlv119_un_btn_action.png'))
    # 通过投票：达标亮绿 / 未达标灰
    out = button_face((196, 30), fill=(10, 44, 36, 240), border=(54, 200, 148, 210),
                      accent=(88, 234, 170, 240), bar=4)
    out.save(os.path.join(OUT_DIR, 'mvlv119_un_btn_pass.png'))
    out = button_face((196, 30), fill=(28, 32, 40, 215), border=(72, 80, 92, 175),
                      accent=(112, 122, 134, 185), bar=4)
    out.save(os.path.join(OUT_DIR, 'mvlv119_un_btn_pass_grey.png'))
    Image.new('RGBA', (148, 28), (0, 0, 0, 0)).save(
        os.path.join(OUT_DIR, 'mvlv119_un_btn_tab.png'))
    # 当前页签的下划线：左亮右淡
    line = Image.new('RGBA', (148, 3), (0, 0, 0, 0))
    dl = ImageDraw.Draw(line)
    for x in range(148):
        a = int(240 * (1 - x / 148.0) ** 0.7)
        dl.line([(x, 0), (x, 2)], fill=(96, 226, 248, a))
    line.save(os.path.join(OUT_DIR, 'mvlv119_un_tab_on.png'))
    print('buttons: vote/res/lobby/action/tab/tab_on')


if __name__ == '__main__':
    os.makedirs(OUT_DIR, exist_ok=True)
    build_chip()
    build_window()
    build_event_pic()
    build_topbar_button()
    build_buttons()
