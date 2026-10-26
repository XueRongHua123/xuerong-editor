"""v0.95 涂色端到端（副本上），验证 begin→dab→commit→undo 全链路。"""
import hashlib
import io
import json
import os
import shutil
import urllib.request

SRC = r"D:\大肥鱼工作区\HOI4 MUVLUVsub mod 制作\muvluvCN_1.19\map\provinces.bmp"
TMP = os.path.join(os.getcwd(), "_paint_e2e")
os.makedirs(TMP, exist_ok=True)
BAK = os.path.join(TMP, "provinces.bmp")
shutil.copyfile(SRC, BAK)


def md5(p):
    h = hashlib.md5()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def call(d):
    req = urllib.request.Request("http://127.0.0.1:8891/api/map_paint",
                                 data=json.dumps(d).encode(),
                                 headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=180).read().decode())


orig = md5(BAK)
print("01 begin   :", call({"act": "begin", "bmp": BAK}))
print("02 dab x3  :", sum(call({"act": "dab", "x": 300 + i * 6, "y": 300, "r": 3, "pid": 221}).get("pixels", 0)
                         for i in range(3)))
print("03 state   :", call({"act": "state"}))
print("04 commit  :", call({"act": "commit"}))
print("05 文件变化:", md5(BAK) != orig)
print("06 undo    :", call({"act": "undo"}))
print("07 完全还原:", md5(BAK) == orig)
print("08 redo    :", call({"act": "redo"}))
print("09 再变化  :", md5(BAK) != orig)
call({"act": "undo"})
print("10 终态还原:", md5(BAK) == orig)
shutil.rmtree(TMP, ignore_errors=True)
