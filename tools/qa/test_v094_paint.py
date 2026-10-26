"""v0.94 地图像素编辑与撤销——用副本测试，不碰真实 mod。"""
import hashlib
import io
import os
import shutil
import sys

sys.path.insert(0, '.')
import focus_editor as fe

SRC = r"D:\大肥鱼工作区\HOI4 MUVLUVsub mod 制作\muvluvCN_1.19\map\provinces.bmp"
TMP = os.path.join(os.getcwd(), "_paint_test")
os.makedirs(TMP, exist_ok=True)
BAK = os.path.join(TMP, "provinces.bmp")
shutil.copyfile(SRC, BAK)
print("副本:", BAK, "%.1f MB" % (os.path.getsize(BAK) / 1048576))


def md5(p):
    h = hashlib.md5()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


orig_md5 = md5(BAK)
info = fe.bmp_info(BAK)
print("BMP:", info)

# 1) 读一块原始像素
r0 = fe.bmp_read_rect(BAK, 100, 100, 4, 4)
print("读 4x4 首像素 RGB:", r0[0])

# 2) 开始事务并画一个圆
fe.map_edit_begin(BAK)
n = 0
for (x, y) in ((120, 120), (124, 120), (128, 121)):
    n += fe.map_edit_dab(BAK, x, y, 3, (255, 0, 255))
print("待写像素:", n)

# 3) 提交
res = fe.map_edit_commit()
print("提交:", res)
after_md5 = md5(BAK)
print("文件已改变:", after_md5 != orig_md5)

# 4) 检查目标点确实变了、且块外未受影响
px = fe.bmp_read_rect(BAK, 120, 120, 1, 1)[0]
far = fe.bmp_read_rect(BAK, 300, 300, 1, 1)[0]
print("(120,120) 现在:", px, "→ 期望 (255, 0, 255)")
print("(300,300) 未动:", far)

# 5) 撤销
u = fe.map_edit_undo()
print("撤销:", u)
print("恢复原状:", md5(BAK) == orig_md5)

# 6) 重做
r = fe.map_edit_redo()
print("重做:", r)
print("重做后又变了:", fe.bmp_read_rect(BAK, 120, 120, 1, 1)[0] == (255, 0, 255))

# 7) 再撤销，确认可反复
fe.map_edit_undo()
print("二次撤销后恢复:", md5(BAK) == orig_md5)
print("状态:", fe.map_edit_state())
