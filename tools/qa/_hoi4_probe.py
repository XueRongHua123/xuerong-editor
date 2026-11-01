# -*- coding: utf-8 -*-
"""真机探针：装一个候选 mod，启动 HOI4，判定「崩 / 不崩」。

为什么需要它
------------
2026-11-02 实测发现：50 条 replace_path 的组合**不需要任何人点开始**，
启动后约 2 秒（`Loaded 208 provinces` 之后）就自己崩掉。
所以真机二分可以全自动：装 mod → 等 40 秒 → 看进程还在不在。

用法
----
  # 全量装（对照）
  python qa/_hoi4_probe.py --src tmp/_world5 --tag full

  # 只保留若干目录（其余文件与 replace_path 一起丢掉）
  python qa/_hoi4_probe.py --src tmp/_world5 --tag nomap --drop map

  # 恢复 dlc_load.json 到备份
  python qa/_hoi4_probe.py --restore

判定
----
  ALIVE  进程活到 timeout（能进主菜单，至少没在加载期崩）
  DIED   进程提前退出（崩溃），打印 game.log 尾部与新崩溃目录

注意
----
* 每个候选都装成 mod/zz_probe，互不叠加，dlc_load 只启它一个
* 启动前若已有 hoi4.exe 在跑直接报错，不并行
* 不改动源目录：只读 src，写到 Documents/mod/zz_probe
"""
import argparse
import io
import json
import os
import shutil
import subprocess
import sys
import time

DOCS = r"C:\Users\33206\Documents\Paradox Interactive\Hearts of Iron IV"
MODDIR = os.path.join(DOCS, "mod")
DLC = os.path.join(DOCS, "dlc_load.json")
GAME = r"E:\SteamLibrary\steamapps\common\Hearts of Iron IV"
PROBE = "zz_probe"


def _die(msg):
    print("ERR: " + msg)
    sys.exit(2)


def _hoi4_running():
    out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq hoi4.exe"],
                         capture_output=True, text=True, errors="replace").stdout
    return "hoi4.exe" in out


def _new_crash_dirs(before):
    d = os.path.join(DOCS, "crashes")
    if not os.path.isdir(d):
        return []
    now = set(os.listdir(d))
    return sorted(now - set(before or ()))


def _keep(rel, keeps, drops):
    rel = rel.replace("\\", "/")
    for d in drops:
        if rel == d or rel.startswith(d.rstrip("/") + "/"):
            return False
    if not keeps:
        return True
    for k in keeps:
        if rel == k or rel.startswith(k.rstrip("/") + "/"):
            return True
    return False


def build(src, keeps, drops, name=PROBE, mod_name=None, file_keep=None):
    """把 src 里命中的文件拷到 mod/zz_probe，并写 descriptor + .mod。

    file_keep 只影响「拷哪些文件」，keeps 只影响「留哪些 replace_path」，
    两者分开才能做「整张地图进来、但只 replace 两个子目录」这种组合。
    """
    fk = file_keep if file_keep is not None else keeps
    tgt = os.path.join(MODDIR, name)
    if os.path.isdir(tgt):
        shutil.rmtree(tgt)
    os.makedirs(tgt, exist_ok=True)
    n = 0
    for root, _dirs, files in os.walk(src):
        for fn in files:
            p = os.path.join(root, fn)
            rel = os.path.relpath(p, src).replace("\\", "/")
            if not _keep(rel, fk, drops):
                continue
            q = os.path.join(tgt, rel.replace("/", os.sep))
            os.makedirs(os.path.dirname(q), exist_ok=True)
            shutil.copyfile(p, q)
            n += 1

    desc = os.path.join(tgt, "descriptor.mod")
    body = ""
    for cand in (os.path.join(src, "descriptor.mod"), desc):
        if os.path.exists(cand):
            body = io.open(cand, encoding="utf-8-sig").read()
            break
    if not body:
        _die("源目录没有 descriptor.mod")
    repl = [ln.strip() for ln in body.splitlines()
            if ln.strip().startswith("replace_path=")]
    other = [ln for ln in body.splitlines()
             if not ln.strip().startswith("replace_path=")
             and not ln.strip().startswith("path=")]
    kept = []
    for ln in repl:
        sub = ln.split('"')[1].replace("\\", "/")
        if _keep(sub, keeps, drops):
            kept.append(ln)
    out = [ln for ln in other if ln.strip()]
    # 显示名必须唯一：两个 .mod 同 name 时引擎会把**两个都丢掉**（实测按原版加载）
    disp = mod_name or ("探针_%s" % name)
    out = [('name="%s"' % disp) if ln.strip().startswith("name=") else ln
           for ln in out]
    if not any(ln.strip().startswith("name=") for ln in out):
        out.insert(0, 'name="%s"' % disp)
    # path= 必须紧跟 supported_version，放在 replace_path 之后整条 mod 会被静默忽略
    # （实测：文件在、dlc_load 也对，游戏却按原版加载了 13414 个省）
    pos = 1
    for i, ln in enumerate(out):
        if ln.strip().startswith("supported_version"):
            pos = i + 1
            break
    out.insert(pos, 'path="mod/%s"' % name)
    out += kept
    io.open(desc, "w", encoding="utf-8", newline="").write("\n".join(out) + "\n")
    outer = os.path.join(MODDIR, name + ".mod")
    io.open(outer, "w", encoding="utf-8", newline="").write("\n".join(out) + "\n")
    return tgt, n, len(kept), out, other


def enable(name=PROBE):
    data = {"enabled_mods": ["mod/%s.mod" % name], "disabled_dlcs": []}
    io.open(DLC, "w", encoding="utf-8", newline="").write(json.dumps(data))


def _settle(limit=30):
    """崩溃后 hoi4.exe 有时会残留几十秒（崩溃上报器还在跑），等它自己退。

    等不到就 taskkill，保证每轮只有一个实例。
    """
    t0 = time.time()
    while _hoi4_running() and time.time() - t0 < limit:
        time.sleep(2.0)
    if _hoi4_running():
        subprocess.run(["taskkill", "/F", "/IM", "hoi4.exe"],
                       capture_output=True)
        time.sleep(3.0)
    return not _hoi4_running()


def launch(timeout=45, tag="probe"):
    if not _settle():
        _die("hoi4 关不掉，本轮放弃")
    before = set(_new_crash_dirs([]))
    log = os.path.join(DOCS, "logs", "game.log")
    try:
        os.remove(log)
    except Exception:
        pass
    t0 = time.time()
    p = subprocess.Popen([os.path.join(GAME, "hoi4.exe")], cwd=GAME)
    died = None
    while time.time() - t0 < timeout:
        time.sleep(1.0)
        if p.poll() is not None:
            died = time.time() - t0
            break
    if died is None:
        p.kill()
        try:
            p.wait(15)
        except Exception:
            pass
        alive = True
    else:
        alive = False
    # 等文件落盘
    time.sleep(1.5)
    lines = []
    if os.path.exists(log):
        lines = io.open(log, encoding="utf-8", errors="replace").read().splitlines()
    newc = _new_crash_dirs(before)
    tail = [ln for ln in lines if ln.strip()][-4:]
    return {"alive": alive, "secs": round(died if died else timeout, 1),
            "tail": tail, "crashes": newc, "tag": tag}


def restore():
    for bak in ("dlc_load.json.bak-xuerong", "dlc_load.json.bak_beforemap"):
        p = os.path.join(DOCS, bak)
        if os.path.exists(p):
            shutil.copyfile(p, DLC)
            print("已恢复 dlc_load ← " + bak)
            return
    print("没找到 dlc_load 备份")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=r"D:\大肥鱼工作区\HOI4 MUVLUVsub mod 制作\work\tmp\_world5")
    ap.add_argument("--tag", default="probe")
    ap.add_argument("--keep", default="", help="逗号分隔的目录白名单")
    ap.add_argument("--drop", default="", help="逗号分隔的目录黑名单")
    ap.add_argument("--name", default=PROBE)
    ap.add_argument("--timeout", type=int, default=45)
    ap.add_argument("--restore", action="store_true")
    ap.add_argument("--no-deploy", action="store_true", help="只启动，不重新装 mod")
    a = ap.parse_args()

    if a.restore:
        restore()
        return
    keeps = [x.strip() for x in a.keep.split(",") if x.strip()]
    drops = [x.strip() for x in a.drop.split(",") if x.strip()]
    if not a.no_deploy:
        tgt, n, nr, out, other = build(a.src, keeps, drops, a.name)
        enable(a.name)
        print("装好 %d 个文件，%d 条 replace_path → %s" % (n, nr, tgt))
        print("descriptor 头: %s" % " | ".join(other[:4]))
    r = launch(a.timeout, a.tag)
    print("结果: %s  %.1fs" % ("ALIVE" if r["alive"] else "DIED", r["secs"]))
    for ln in r["tail"]:
        print("  log| " + ln)
    for c in r["crashes"]:
        print("  crash| " + c)


if __name__ == "__main__":
    main()
