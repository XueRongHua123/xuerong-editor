# -*- coding: utf-8 -*-
"""快照 / 备份 / 撤销重做（P0-3 B1 从 focus_editor.py 迁入）。

每次写盘前 `snapshot()` 把原文件复制到 work/history/<sha1>_<ms>.txt，
`undo_last()` / `redo_last()` 在这条链上前后来回；`backup()` 是「第一次写之前留 .bak」。

依赖边界：
  · 容器 HISTORY / 标量 LAST_FILE → xuerong.state（accessor）
  · 历史目录 → paths.app_dir()/history
  · 唯一钩子：reload_data（撤销成功后要让内存里的树跟着变），由门面回注
"""
import hashlib
import os
import shutil
import time

from xuerong import state
from xuerong.core import paths

_HIST_DIR = os.path.join(paths.app_dir(), "history")
os.makedirs(_HIST_DIR, exist_ok=True)

_RELOAD = None


def bind(reload_data):
    """门面启动时回注 reload_data。"""
    global _RELOAD
    _RELOAD = reload_data


def _reload():
    if _RELOAD:
        _RELOAD()


def snapshot(path):
    try:
        if not os.path.exists(path):
            return
        h = state.history().setdefault(path, {"undo": [], "redo": []})
        fn = os.path.join(_HIST_DIR, hashlib.sha1(path.encode("utf-8")).hexdigest()[:10]
                          + "_%d.txt" % int(time.time() * 1000))
        shutil.copyfile(path, fn)
        h["undo"].append(fn)
        h["redo"] = []
        state.set_last_file(path)
    except Exception as e:
        print("snapshot fail:", e)



def undo_last():
    if not state.last_file() or state.last_file() not in state.history():
        return False, "没有可撤销的操作"
    h = state.history()[state.last_file()]
    if not h["undo"]:
        return False, "没有可撤销的操作"
    fn = h["undo"].pop()
    cur = os.path.join(_HIST_DIR, "redo_%d.txt" % int(time.time() * 1000))
    shutil.copyfile(state.last_file(), cur)
    h["redo"].append(cur)
    shutil.copyfile(fn, state.last_file())
    _reload()
    return True, "已撤销：%s" % os.path.basename(state.last_file())



def redo_last():
    if not state.last_file() or state.last_file() not in state.history():
        return False, "没有可重做的操作"
    h = state.history()[state.last_file()]
    if not h["redo"]:
        return False, "没有可重做的操作"
    fn = h["redo"].pop()
    cur = os.path.join(_HIST_DIR, "undo_%d.txt" % int(time.time() * 1000))
    shutil.copyfile(state.last_file(), cur)
    h["undo"].append(cur)
    shutil.copyfile(fn, state.last_file())
    _reload()
    return True, "已重做：%s" % os.path.basename(state.last_file())



# ---------------- 写回 ----------------
def backup(path):
    try:
        if not os.path.exists(path + ".bak"):
            shutil.copyfile(path, path + ".bak")
    except Exception:
        pass
