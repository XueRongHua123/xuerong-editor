"""v1.1.1 输出目录模式端到端（不起浏览器，直接走接口逻辑）。"""
import hashlib
import io
import json
import os
import shutil
import sys

sys.path.insert(0, '.')
sys.path.insert(0, 'tools')
import focus_editor as fe

W = "E:/SteamLibrary/steamapps/workshop/content/394360"
MOD = os.path.join(W, "3004109283")
fe.GAME = r"E:\SteamLibrary\steamapps\common\Hearts of Iron IV"
fe.ROOTS = [MOD]
fe.load_vanilla() if hasattr(fe, 'load_vanilla') else None


def md5(p):
    if not os.path.exists(p):
        return "缺失"
    h = hashlib.md5()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()[:12]


SRC_BMP = os.path.join(MOD, "map", "provinces.bmp")
print("=== 1) 打开输出模式 ===")
print(fe.output_toggle(True))

bmp_before = md5(SRC_BMP)
print("\n=== 2) 源 bmp md5（改动前）:", bmp_before)

print("\n=== 3) 在输出模式下涂色 ===")
fe.MAP_EDIT['undo'] = []
fe.MAP_EDIT['redo'] = []
fe.map_edit_begin(SRC_BMP)
n = fe.map_edit_dab(SRC_BMP, 1500, 1500, 5, (255, 0, 255))
print("  dab 像素:", n)
r = fe.map_edit_commit()
print("  commit:", {k: r.get(k) for k in ('ok', 'pixels', 'undo_depth')})

bmp_after = md5(SRC_BMP)
out_copy = os.path.join(fe.OUTPUT_ROOT, os.path.basename(MOD), "map", "provinces.bmp")
print("\n=== 4) 源 bmp md5（改动后）:", bmp_after, "→ 源文件未变:", bmp_after == bmp_before)
print("   输出副本存在:", os.path.exists(out_copy), "| md5:", md5(out_copy))
print("   输出副本已改:", md5(out_copy) != bmp_before if os.path.exists(out_copy) else "N/A")

print("\n=== 5) 读取走输出副本（应该读到改过的）===")
px = fe.bmp_read_rect(out_copy, 1500, 1500, 1, 1)
print("   输出副本 (1500,1500):", px[0] if px else None, "→ 期望 (255, 0, 255)")

print("\n=== 6) 关闭输出模式 ===")
print(fe.output_toggle(False))

print("\n=== 7) 清理输出目录 ===")
print(fe.output_clear())
