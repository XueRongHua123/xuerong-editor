# -*- coding: utf-8 -*-
"""单点注入的真假判定器。

判定用「离开游戏」这个按钮：点中了进程会退，点不中进程还在。
比截图稳妥——前端背景有动画，拿像素差判断「有没有反应」会误判。

用法：
    python qa/_click_test.py --method sendinput --x 1182 --y 775
    python qa/_click_test.py --method msg        --x 946  --y 620
    python qa/_click_test.py --method altmouse   --x 1182 --y 775

坐标是**屏幕物理坐标**（PNG 坐标 ×1.25，窗口在 (0,0) 时两者只差缩放）。
"""
import argparse
import ctypes
import ctypes.wintypes as wt
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _game_run as G


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--method", default="sendinput")
    ap.add_argument("--x", type=int, required=True)
    ap.add_argument("--y", type=int, required=True)
    ap.add_argument("--wait", type=float, default=50)
    a = ap.parse_args()

    if G._game_pid():
        print("ERR: hoi4 已在运行")
        return 2
    t0 = time.time()
    subprocess.Popen([os.path.join(G.GAME, "hoi4.exe")], cwd=G.GAME)
    pid = None
    for _ in range(60):
        time.sleep(1)
        pid = G._game_pid()
        if pid:
            break
    if not pid:
        print("进程没起来")
        return 1
    while time.time() - t0 < a.wait:
        if G.log_has("Executing History"):
            break
        time.sleep(1)
    time.sleep(12)

    hwnd = G._hwnd(pid)
    print("hwnd", hwnd)
    if not hwnd:
        print("没找到窗口")
        return 1

    u = G.user32
    # 老办法：置顶 + ALT 绕前台锁
    u.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x0001 | 0x0002)
    u.keybd_event(0x12, 0, 0, 0)
    u.SetForegroundWindow(hwnd)
    u.keybd_event(0x12, 0, 2, 0)
    time.sleep(0.8)
    print("前台:", "OK" if u.GetForegroundWindow() == hwnd else "不是游戏")

    if a.method == "sendinput":
        G.sendinput_click(a.x, a.y)
    elif a.method == "mouse":
        u.SetCursorPos(a.x, a.y)
        time.sleep(0.2)
        u.mouse_event(0x0002, 0, 0, 0, 0)
        time.sleep(0.08)
        u.mouse_event(0x0004, 0, 0, 0, 0)
    elif a.method == "altmouse":
        # ALT 按住不放，再点，再松 —— 有些引擎只在这个组合下认输入
        u.SetCursorPos(a.x, a.y)
        u.keybd_event(0x12, 0, 0, 0)
        time.sleep(0.1)
        u.mouse_event(0x0002, 0, 0, 0, 0)
        time.sleep(0.1)
        u.mouse_event(0x0004, 0, 0, 0, 0)
        time.sleep(0.1)
        u.keybd_event(0x12, 0, 2, 0)
    elif a.method == "msg":
        pt = wt.POINT(a.x, a.y)
        u.ScreenToClient(hwnd, ctypes.byref(pt))
        lp = ((pt.y & 0xFFFF) << 16) | (pt.x & 0xFFFF)
        print("client", pt.x, pt.y)
        u.PostMessageW(hwnd, 0x0200, 0, lp)
        time.sleep(0.1)
        u.PostMessageW(hwnd, 0x0201, 1, lp)
        time.sleep(0.1)
        u.PostMessageW(hwnd, 0x0202, 0, lp)

    time.sleep(6)
    alive = G._game_pid() is not None
    print("注入 %s 后进程: %s" % (a.method, "还活着（点空了）" if alive else "退了（点中了）"))
    if alive:
        subprocess.run(["taskkill", "/F", "/IM", "hoi4.exe"], capture_output=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
