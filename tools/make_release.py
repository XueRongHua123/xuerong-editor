# -*- coding: utf-8 -*-
"""一条命令出发布包：编译 exe -> 组 <名称>_vX.Y.Z 目录 -> 打 zip。

用法：
    python packaging/make_release.py 0.53.0
    python packaging/make_release.py 0.53.0 --skip-build   # 复用 dist 里的 exe
    python packaging/make_release.py 0.53.0 --archive-old  # 顺便把旧版本挪进 archive/

产物：
    packaging/dist/雪绒的钢铁雄心编辑器.exe
    packaging/雪绒的钢铁雄心编辑器_vX.Y.Z/（exe + docs/*.md）
    packaging/雪绒的钢铁雄心编辑器_vX.Y.Z.zip
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import io
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.dirname(HERE)
NAME = "雪绒的钢铁雄心编辑器"
EXE = NAME + ".exe"


def build(python, version="0.0.0"):
    """打包。打包前把版本号写进 _build_version.py（模块形式打进 exe），结束后删除。"""
    ver_path = os.path.join(WORK, "_build_version.py")
    try:
        io.open(ver_path, "w", encoding="utf-8", newline="").write('VERSION = "%s"' % version + chr(10))
    except Exception as e:
        print("写版本文件失败:", e)
    args = [
        python, "-m", "PyInstaller", "--noconfirm", "--onefile", "--name", NAME,
        "--icon", os.path.join(WORK, "mascot", "xuerong_face.ico"),
        "--add-data", os.path.join(WORK, "focus_editor_index.html") + ";.",
        "--add-data", os.path.join(WORK, "mascot_face.png") + ";.",
        "--add-data", os.path.join(WORK, "mascot_card.png") + ";.",
        "--add-data", os.path.join(WORK, "mascot") + ";mascot",
        # 只用 Image.open/convert/frombytes/save/resize，不需要 AVIF 等特殊解码器（省 ~8MB 解压体积）
        "--exclude-module", "PIL._avif",
        "--exclude-module", "PIL._avif_cffi",
        # Pillow 的 hook 会把机器上装了的 numpy 一并收进来（+11MB 压缩体积），本项目不用
        "--exclude-module", "numpy",
        "--exclude-module", "scipy",
        "--exclude-module", "pandas",
        "--exclude-module", "matplotlib",
        "--distpath", os.path.join(HERE, "dist"),
        "--workpath", os.path.join(HERE, "build"),
        os.path.join(WORK, "focus_editor.py"),
    ]
    print("构建：", " ".join(args[:6]), "...")
    r = subprocess.run(args, cwd=HERE)
    # 无论成功失败都清掉临时版本文件，避免源码运行时读到错误版本
    try:
        if os.path.exists(ver_path):
            os.remove(ver_path)
    except Exception:
        pass
    if r.returncode != 0:
        sys.exit("PyInstaller 失败，退出码 %d" % r.returncode)


def package(version):
    exe_src = os.path.join(HERE, "dist", EXE)
    if not os.path.exists(exe_src):
        sys.exit("找不到 %s，先去掉 --skip-build 重新编译" % exe_src)
    out = os.path.join(HERE, "%s_v%s" % (NAME, version))
    if os.path.isdir(out):
        shutil.rmtree(out)
    os.makedirs(os.path.join(out, "docs"))
    shutil.copy2(exe_src, os.path.join(out, EXE))
    docs = 0
    for n in ("zh", "en", "ja"):
        src = os.path.join(WORK, "docs", "focus_editor_tutorial_%s.md" % n)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(out, "docs", os.path.basename(src)))
            docs += 1
    zpath = out + ".zip"
    if os.path.exists(zpath):
        os.remove(zpath)
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for root, _, files in os.walk(out):
            for f in files:
                full = os.path.join(root, f)
                z.write(full, os.path.relpath(full, HERE))
    return out, zpath, docs


def archive_old(current_version):
    arch = os.path.join(HERE, "archive")
    os.makedirs(arch, exist_ok=True)
    moved = []
    pat = re.compile(r'^' + re.escape(NAME) + r'_v([0-9][0-9A-Za-z.\-]*?)(\.zip)?$')
    for n in sorted(os.listdir(HERE)):
        m = pat.match(n)
        if not m or m.group(1) == current_version:
            continue
        src = os.path.join(HERE, n)
        if not (os.path.isdir(src) or n.endswith(".zip")):
            continue
        dst = os.path.join(arch, n)
        if os.path.exists(dst):
            continue
        shutil.move(src, dst)
        moved.append(n)
    return moved


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("version", help="版本号，例如 0.53.0")
    ap.add_argument("--skip-build", action="store_true", help="复用 dist 里已有的 exe")
    ap.add_argument("--archive-old", action="store_true", help="把其它版本目录/zip 移进 archive/")
    ap.add_argument("--python", default=sys.executable)
    a = ap.parse_args()

    if not a.skip_build:
        build(a.python, a.version)
    out, zpath, docs = package(a.version)
    size = lambda p: os.path.getsize(p) / 1048576
    print("目录：%s（exe %.1f MB，docs %d 篇）" % (out, size(os.path.join(out, EXE)), docs))
    print("发行包：%s（%.1f MB）" % (zpath, size(zpath)))
    if a.archive_old:
        moved = archive_old(a.version)
        print("归档：", moved if moved else "无旧版本")


if __name__ == "__main__":
    main()
