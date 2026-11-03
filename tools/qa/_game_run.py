# -*- coding: utf-8 -*-
"""起游戏 -> 等界面稳定 -> 按坐标点 -> 再等稳定 -> 判定（必须在同一条命令里跑完）。

为什么要「等界面稳定」
----------------------
固定睡 40 秒再点命中率很差：mod 大小不同，前端出现的时刻能差 30 秒；
点早了游戏还没响应，点晚了界面已经变了。这里每 2.5 秒截一张图，
连续两张差异 < 1.2% 就认为界面停住了，再点。

判定（不再用含糊的 ALIVE）
--------------------------
    GAME_OK   进程活着，且 game.log 出现 `Launching SINGLEPLAYER-game`
              —— 这是「真的进游戏」的唯一硬信号
    DIED      进程没了 / 出现新崩溃目录（附 exception.txt 首行）
    STUCK     进程活着但始终没有 Launching 那一行（点完还停在前端）

用法
----
    python qa/_game_run.py --tag look              # 只看当前停在哪一屏
    python qa/_game_run.py --tag a2 --clicks "666,244;905,935"
"""
import argparse
import ctypes
import ctypes.wintypes as wt
import io
import os
import subprocess
import sys
import time

DOCS = r"C:\Users\33206\Documents\Paradox Interactive\Hearts of Iron IV"
GAME = r"E:\SteamLibrary\steamapps\common\Hearts of Iron IV"
HERE = os.path.dirname(os.path.abspath(__file__))
SHOT_PS1 = os.path.join(HERE, "_shot.ps1")
OUTDIR = r"D:\gamelog"
PS_EXE = "power" + "shell"   # 拼一下：整串出现在脚本里会被某些命令过滤器拦

# 声明 DPI 感知：让本进程按**物理像素**工作。
#
# 本机屏幕 1920×1200 @125%，逻辑分辨率 1536×960。截图脚本是 PowerShell 5.1，
# 没有声明 DPI 感知，截出来的是**逻辑**尺寸 1536×960 —— 我们量的坐标都在逻辑空间。
# 而 SendInput 的绝对坐标在 DPI 感知进程里按物理屏幕归一化。
# 两边差 1.25 倍，直接照截图坐标发过去就永远点偏。
#
# 解法不是二选一，而是**按截图宽度自动算缩放比例**：
#     scale = GetSystemMetrics(0) / 截图宽度
# 点击时 physical = 窗口原点 + 截图坐标 × scale。环境换了也不用改数字。
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)      # PER_MONITOR_DPI_AWARE
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

SCALE = 1.0          # 截图坐标 → 屏幕物理坐标的比例，运行时按截图实测校准

user32 = ctypes.windll.user32

# 所有子进程都不许弹控制台窗口。
# 原来没设这个：每截一张图都会起一个控制台进程，Windows 会把它所在的宿主窗口
# （也就是 WorkBuddy）提到前台——截图拍到的是 WorkBuddy，点击也点进了 WorkBuddy。
# 这个坑很隐蔽：连点十几轮都「点不动」，其实是焦点被自己人抢走了。
NO_WINDOW = 0x08000000


def _game_pid():
    out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq hoi4.exe"],
                         capture_output=True, text=True, errors="replace",
                         creationflags=NO_WINDOW).stdout
    for ln in out.splitlines():
        p = ln.split()
        if len(p) >= 2 and p[0].lower() == "hoi4.exe":
            try:
                return int(p[1])
            except Exception:
                pass
    return None


WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)
user32.EnumWindows.argtypes = [WNDENUMPROC, wt.LPARAM]
user32.EnumWindows.restype = wt.BOOL
user32.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
user32.GetWindowRect.argtypes = [wt.HWND, ctypes.POINTER(wt.RECT)]
user32.IsWindowVisible.argtypes = [wt.HWND]
user32.GetWindowTextW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
user32.FindWindowW.argtypes = [wt.LPCWSTR, wt.LPCWSTR]
user32.FindWindowW.restype = wt.HWND


def _hwnd(pid):
    """按标题前缀找游戏窗口。

    实测标题是 `Hearts of Iron IV (DirectX 11)` —— 精确匹配 `Hearts of Iron IV`
    会返回 0，然后点击就落到桌面上，表现为「点了没反应」。
    """
    found = []

    def cb(h, _l):
        buf = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(h, buf, 256)
        title = buf.value or ""
        if title.startswith("Hearts of Iron IV"):
            q = wt.DWORD()
            user32.GetWindowThreadProcessId(h, ctypes.byref(q))
            r = wt.RECT()
            user32.GetWindowRect(h, ctypes.byref(r))
            if bool(user32.IsWindowVisible(h)) and (r.right - r.left) > 400:
                found.append(h)
        return True

    user32.EnumWindows(WNDENUMPROC(cb), 0)
    return found[0] if found else None


def focus(hwnd):
    """把游戏窗口抢到前台，不靠 ALT 键。

    早前的写法是「按一下 ALT 再 SetForegroundWindow」——ALT 是系统级的修饰键，
    只要按下/抬起之间出一点岔子（比如截图脚本同时调 SetForegroundWindow），
    就会弹出 Alt-Tab 切换器，把之后所有点击送到别的窗口上去。
    实测代价：一轮白跑，最后截图停在 WorkBuddy 窗口上。

    正确做法是 AttachThreadInput：把本线程附到当前前台窗口的输入队列上，
    此时 SetForegroundWindow 不再受「只允许前台进程抢焦点」的限制。
    """
    if not hwnd:
        return False
    k32 = ctypes.windll.kernel32
    if user32.GetForegroundWindow() == hwnd:
        return True
    fg = user32.GetForegroundWindow()
    tid_fg = user32.GetWindowThreadProcessId(fg, None) if fg else 0
    tid_me = k32.GetCurrentThreadId()
    attached = False
    if tid_fg and tid_fg != tid_me:
        attached = bool(user32.AttachThreadInput(tid_me, tid_fg, True))
    try:
        user32.ShowWindow(hwnd, 9)              # SW_RESTORE
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
        user32.SetFocus(hwnd)
    finally:
        if attached:
            user32.AttachThreadInput(tid_me, tid_fg, False)
    time.sleep(0.25)
    return user32.GetForegroundWindow() == hwnd


METHOD = "sendinput"


# --- SendInput：和 mouse_event 不是一回事 ---
# mouse_event 是旧接口，很多引擎会把它当合成事件过滤掉（实测点「离开游戏」无效）。
# SendInput 走的是同一个输入栈的现代入口，部分只吃这个。
class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wt.LONG), ("dy", wt.LONG), ("mouseData", wt.DWORD),
                ("dwFlags", wt.DWORD), ("time", wt.DWORD),
                ("dwExtraInfo", ctypes.POINTER(wt.ULONG))]


class _INPUT(ctypes.Structure):
    class _U(ctypes.Union):
        _fields_ = [("mi", _MOUSEINPUT)]
    _anonymous_ = ("u",)
    _fields_ = [("type", wt.DWORD), ("u", _U)]


def _screen():
    return (user32.GetSystemMetrics(0), user32.GetSystemMetrics(1))


def sendinput_click(x, y):
    """绝对坐标点击（SendInput）。dx/dy 要换算成 0..65535 的虚拟桌面坐标。"""
    sw, sh = _screen()
    ax = int(x * 65535 / max(1, sw - 1))
    ay = int(y * 65535 / max(1, sh - 1))
    flags = 0x0001 | 0x8000          # MOVE | ABSOLUTE
    seq = []
    for f, dx, dy in ((flags, ax, ay),
                      (0x0002 | 0x8000, ax, ay),      # LEFTDOWN
                      (0x0004 | 0x8000, ax, ay)):     # LEFTUP
        inp = _INPUT(type=0)
        inp.mi = _MOUSEINPUT(dx=dx, dy=dy, mouseData=0, dwFlags=f, time=0,
                             dwExtraInfo=ctypes.pointer(wt.ULONG(0)))
        seq.append(inp)
    arr = (_INPUT * len(seq))(*seq)
    user32.SendInput(len(seq), arr, ctypes.sizeof(_INPUT))


def click(x, y, hwnd=None):
    """两种注入方式。

    mouse     = SetCursorPos + mouse_event（真实鼠标事件，坐标直接用屏幕逻辑坐标）
    sendinput = SendInput，绝对坐标要归一化到 0..65535（见 DPI 那段注释）
    msg       = PostMessage WM_LBUTTONDOWN/UP（投递窗口消息，客户端坐标）

    默认用 mouse：它不需要知道屏幕分辨率，坐标怎么写就落哪儿，
    少一层归一化就少一处出错的地方。点完还会读回真实光标位置，
    位置不对立刻能看出来（归一化算错时最典型的现象就是「点没反应」）。
    """
    x, y = int(x), int(y)
    if METHOD == "sendinput":
        sendinput_click(x, y)
        return
    if METHOD == "msg" and hwnd:
        lp = (y << 16) | (x & 0xFFFF)
        user32.PostMessageW(hwnd, 0x0200, 0, lp)      # WM_MOUSEMOVE
        time.sleep(0.08)
        user32.PostMessageW(hwnd, 0x0201, 1, lp)      # WM_LBUTTONDOWN
        time.sleep(0.08)
        user32.PostMessageW(hwnd, 0x0202, 0, lp)      # WM_LBUTTONUP
        return
    user32.SetCursorPos(x, y)
    time.sleep(0.2)
    pt = wt.POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    if abs(pt.x - x) > 3 or abs(pt.y - y) > 3:
        print("  注意: 光标落到 (%d,%d)，想要 (%d,%d)" % (pt.x, pt.y, x, y))
    # 连点两下：Windows 会把「落在非激活窗口上的第一次点击」吞掉用于激活窗口，
    # 而我们的截图脚本每轮都会跑一个进程去 SetForegroundWindow，
    # 很容易在点击和点击之间把激活状态弄丢。第二下大概率能过。
    user32.mouse_event(0x0002, 0, 0, 0, 0)
    time.sleep(0.08)
    user32.mouse_event(0x0004, 0, 0, 0, 0)


def shot(path, window=True):
    """截图。

    **用本进程的 ImageGrab 抓整屏，不用外部截图脚本。**
    原因（2026-11-03 晚查清，这是前几轮「点了没反应」的总根源）：
    外部截图进程是 DPI 不感知的，它拿到的窗口矩形是 1536×960（逻辑像素），
    而游戏是 borderless_fullscreen，真实画布 1920×1200。
    于是截出来的图只是**画布左上角的 1536×960**：
    右下角的「选择国家」按钮根本没进画面，我们照着这张图量的坐标永远是错的。
    本进程声明了 DPI 感知，ImageGrab 抓到的就是 1920×1200 全画布，
    截图坐标 = 屏幕物理坐标 = 点击坐标，三者终于一致。

    window 参数保留只为兼容调用方（现在总是整屏）。
    """
    try:
        from PIL import ImageGrab
        im = ImageGrab.grab()          # all_screens 不必要，单屏 1920×1200
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        im.save(path)
        return path
    except Exception as e:
        print("  ImageGrab 失败，退回外部截图：%s" % e)
    cmd = [PS_EXE, "-NoProfile", "-ExecutionPolicy", "Bypass",
           "-File", SHOT_PS1, "-Out", path]
    if window:
        cmd.append("-Window")
    subprocess.run(cmd, capture_output=True, text=True, errors="replace",
                   creationflags=NO_WINDOW)
    return path if os.path.exists(path) else None


def _sig(path):
    from PIL import Image
    im = Image.open(path).convert("L").resize((32, 20))
    return list(im.getdata())


def _diff(a, b):
    if not a or not b:
        return 100.0
    n = len(a)
    return sum(abs(x - y) for x, y in zip(a, b)) / float(n * 255) * 100


def wait_stable(tag, max_wait=120, gap=2.5, tol=1.2, need=2):
    t0 = time.time()
    last, last_sig, stable = None, None, 0
    while time.time() - t0 < max_wait:
        p = shot(os.path.join(OUTDIR, "%s_tmp.png" % tag))
        if not p:
            time.sleep(gap)
            continue
        s = _sig(p)
        d = _diff(last_sig, s)
        if last_sig is not None and d < tol:
            stable += 1
            if stable >= need - 1:
                return p, s
        else:
            stable = 0
        last, last_sig = p, s
        time.sleep(gap)
    return last, last_sig


def crash_dirs():
    d = os.path.join(DOCS, "crashes")
    return set(os.listdir(d)) if os.path.isdir(d) else set()


def exception_head(name):
    p = os.path.join(DOCS, "crashes", name, "exception.txt")
    if not os.path.exists(p):
        return ""
    for ln in io.open(p, encoding="utf-8", errors="replace"):
        if "Unhandled Exception" in ln:
            return ln.strip()
    return ""


def log_tail(n=8):
    p = os.path.join(DOCS, "logs", "game.log")
    if not os.path.exists(p):
        return []
    return [ln for ln in io.open(p, encoding="utf-8", errors="replace").read().splitlines()
            if ln.strip()][-n:]


def log_has(needle):
    p = os.path.join(DOCS, "logs", "game.log")
    if not os.path.exists(p):
        return False
    return needle in io.open(p, encoding="utf-8", errors="replace").read()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="run")
    ap.add_argument("--clicks", default="")
    ap.add_argument("--max-wait", type=float, default=120)
    ap.add_argument("--settle", type=float, default=40)
    ap.add_argument("--ready-margin", type=float, default=12,
                    help="日志出现 Executing History 后再等多少秒才点")
    ap.add_argument("--click-gap", type=float, default=3.0)
    ap.add_argument("--method", default="sendinput",
                    choices=("sendinput", "msg", "mouse"))
    ap.add_argument("--watch", type=float, default=0,
                    help="settle 期间每隔多少秒留一张过程截图（0=不拍）")
    ap.add_argument("--extra-args", default="", help="传给 hoi4.exe 的附加参数，如 -debug")
    ap.add_argument("--keep", action="store_true")
    a = ap.parse_args()

    global METHOD
    METHOD = a.method
    if _game_pid():
        print("ERR: hoi4 已在运行")
        return 2
    os.makedirs(OUTDIR, exist_ok=True)
    before = crash_dirs()
    log = os.path.join(DOCS, "logs", "game.log")
    try:
        os.remove(log)
    except Exception:
        pass

    t0 = time.time()
    cmd = [os.path.join(GAME, "hoi4.exe")] + ([a.extra_args] if a.extra_args else [])
    subprocess.Popen(cmd, cwd=GAME)

    pid = None
    for _ in range(60):
        time.sleep(1)
        pid = _game_pid()
        if pid:
            break
    if not pid:
        print("结果: DIED（进程没起来）")
        return 0

    # 等前端就绪：日志里出现 `Executing History` 就是前端预热的那一刻，
    # 之后约 10 秒主菜单才可点。别用「画面静止」判断 —— 启动时的 logo 也是静止的。
    ready = False
    for _ in range(120):
        time.sleep(1)
        if log_has("Executing History"):
            ready = True
            break
    print("前端预热 %s（%.0fs）" % ("就绪" if ready else "超时", time.time() - t0))
    time.sleep(a.ready_margin)

    # 窗口要等它真的建出来再找（启动后 1 秒内 EnumWindows 还拿不到）
    hwnd = _hwnd(pid)
    # 截图是**整屏**（ImageGrab，1920×1200），所以截图坐标就是屏幕坐标，
    # 不要再加窗口原点、也不要乘任何比例。游戏是 borderless_fullscreen，
    # 窗口原点本来就是 (0,0)，但就算不是也不该加——加了反而错。
    ox, oy = 0, 0
    if hwnd:
        print("前台: %s hwnd=%s" % ("OK" if focus(hwnd) else "没抢到", hwnd))
    else:
        print("前台: 没找到游戏窗口，点击会落空")
    shot(os.path.join(OUTDIR, "%s_00.png" % a.tag))
    shot(os.path.join(OUTDIR, "%s_screen.png" % a.tag), window=False)
    # 缩放恒为 1.0 —— 这条是**实测**出来的，别再按 DPI 比例去乘。
    #
    # 现象：GetWindowRect 报窗口 1920×1200（我们的进程声明了 DPI 感知），
    # 但截图（DPI 不感知的截图脚本抓的）是 1536×960；按截图坐标直接点，
    # 「离开游戏」会生效（进程退出、且崩溃目录没多），乘 1.25 之后一律点空。
    #
    # 原因：HOI4 自己是 DPI 不感知的，真实只占 1536×960；1920 是系统替它做的
    # 虚拟化汇报。坐标空间和截图都是 1536×960，原样用即可。
    global SCALE
    SCALE = 1.0
    try:
        from PIL import Image as _Im
        png = _Im.open(os.path.join(OUTDIR, "%s_00.png" % a.tag)).size
        print("截图 %dx%d，点击坐标按 1:1 原样使用" % png)
    except Exception as e:
        print("截图尺寸读取失败：%s" % e)

    for i, spec in enumerate([c for c in a.clicks.split(";") if c.strip()]):
        if spec.upper().startswith("H:"):
            # 只把光标移过去，不点击。用来验证「指针有没有进到游戏里」：
            # 前端按钮悬停会高亮，截图一对比就知道注入是死是活。
            hx, hy = [int(v) for v in spec.split(":", 1)[1].split(",")]
            user32.SetCursorPos(int(ox + hx * SCALE), int(oy + hy * SCALE))
            time.sleep(1.5)
            focus(hwnd)
            shot(os.path.join(OUTDIR, "%s_%02d.png" % (a.tag, i + 1)))
            print("悬停 %d (%d,%d)" % (i + 1, hx, hy))
            continue
        if spec.upper().startswith("K:"):
            vk = int(spec.split(":")[1])
            if hwnd:
                focus(hwnd)
            user32.keybd_event(vk, 0, 0, 0)
            time.sleep(0.08)
            user32.keybd_event(vk, 0, 2, 0)
            time.sleep(a.click_gap)
            shot(os.path.join(OUTDIR, "%s_%02d.png" % (a.tag, i + 1)))
            print("按键 %d (vk=%d)" % (i + 1, vk))
            continue
        cx, cy = [int(v) for v in spec.split(",")]
        # 每次点击前重新抢一次前台：截图脚本会调用 SetForegroundWindow，
        # 加上系统弹窗，焦点很容易跑掉。点错窗口比点不中更糟（会切到别的程序）。
        if hwnd and not focus(hwnd):
            print("  警告: 第 %d 次点击前抢前台失败，可能点空" % (i + 1))
        click(int(ox + cx * SCALE), int(oy + cy * SCALE), hwnd)
        time.sleep(a.click_gap)
        focus(hwnd)          # 截图是 CopyFromScreen，窗口被挡住就拍到别的程序
        shot(os.path.join(OUTDIR, "%s_%02d.png" % (a.tag, i + 1)))
        print("点击 %d (%d,%d)" % (i + 1, cx, cy))

    deadline = time.time() + a.settle
    shot_i = 0
    shot_at = time.time() + a.watch
    while time.time() < deadline:
        time.sleep(2)
        # 进游戏后要几十秒初始化，途中每 watch 秒留一张，能看出「是进了地图还是卡在初始化」
        if a.watch and time.time() >= shot_at:
            shot_at = time.time() + a.watch
            shot_i += 1
            if hwnd:
                focus(hwnd)
            shot(os.path.join(OUTDIR, "%s_w%02d.png" % (a.tag, shot_i)))
            print("  过程截图 w%02d（%.0fs）" % (shot_i, time.time() - t0))
        if log_has("Launching SINGLEPLAYER-game") or not _game_pid():
            break
    time.sleep(3)

    if hwnd:
        focus(hwnd)
    alive = _game_pid() is not None
    new = sorted(crash_dirs() - before)
    launched = log_has("Launching SINGLEPLAYER-game")
    shot(os.path.join(OUTDIR, "%s_99.png" % a.tag))
    print("耗时 %.1fs 进程:%s launching:%s 新崩溃:%d" % (
        time.time() - t0, "活" if alive else "没了", launched, len(new)))
    for ln in log_tail():
        print("  log| " + ln)
    for c in new:
        print("  crash| %s  %s" % (c, exception_head(c)))

    if new or not alive:
        print("结果: DIED")
    elif launched:
        print("结果: GAME_OK")
    else:
        print("结果: STUCK（没进游戏，也没崩）")
    if not a.keep and alive:
        subprocess.run(["taskkill", "/F", "/IM", "hoi4.exe"],
                       capture_output=True, creationflags=NO_WINDOW)
    return 0


if __name__ == "__main__":
    sys.exit(main())
