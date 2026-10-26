# -*- coding: utf-8 -*-
"""v0.69 UI 流式验证的前置/收尾：起 mock、写配置、起编辑器 / 还原。

用法：
    python work/qa/run_v069_ui.py up      # 起 mock + 配置 + 编辑器 8891
    python work/qa/run_v069_ui.py down    # 还原配置并杀进程
"""
import io
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.dirname(HERE)
CFG = os.path.join(WORK, "ai_config.json")
BACKUP = os.path.join(HERE, "_ai_config_backup.json")
PIDS = os.path.join(HERE, "_v069_pids.json")
MOCK_PORT = 8909
EDITOR_PORT = 8891


class Mock(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        self.rfile.read(n)
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        for piece in ["你好", "，这是", "流式", "输出", "测试。"]:
            chunk = {"choices": [{"delta": {"content": piece}}]}
            self.wfile.write(("data: " + json.dumps(chunk, ensure_ascii=False) + "\n\n").encode())
            self.wfile.flush()
            time.sleep(0.08)
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()


def wait_port(port, timeout=60):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            with socket.create_connection(("127.0.0.1", port), 1):
                return True
        except Exception:
            time.sleep(0.3)
    return False


def up():
    if os.path.exists(CFG):
        shutil.copy2(CFG, BACKUP)
    io.open(CFG, "w", encoding="utf-8", newline="").write(json.dumps({
        "provider": "custom", "base_url": "http://127.0.0.1:%d" % MOCK_PORT,
        "model": "mock", "api_key": "mock", "system": "你是测试助手。"}, ensure_ascii=False))

    env = dict(os.environ)
    mock_proc = subprocess.Popen([sys.executable, os.path.join(HERE, "mock_ai.py"), str(MOCK_PORT)],
                                 cwd=HERE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    proc = subprocess.Popen([sys.executable, os.path.join(WORK, "focus_editor.py"), "--port", str(EDITOR_PORT)],
                            cwd=WORK, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
    io.open(PIDS, "w", encoding="utf-8", newline="").write(json.dumps({"mock": mock_proc.pid, "editor": proc.pid}))
    ok = wait_port(MOCK_PORT, 5) and wait_port(EDITOR_PORT, 60)
    print("up:", "ok" if ok else "fail", "editor pid", proc.pid)
    return 0 if ok else 1


def down():
    try:
        pids = json.loads(io.open(PIDS, encoding="utf-8").read())
    except Exception:
        pids = {}
    for key in ("editor", "mock"):
        pid = pids.get(key)
        if pid:
            subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)
    if os.path.exists(BACKUP):
        shutil.move(BACKUP, CFG)
        print("配置已还原")
    elif os.path.exists(CFG):
        os.remove(CFG)
        print("已删除测试配置")
    if os.path.exists(PIDS):
        os.remove(PIDS)
    print("down: ok")
    return 0


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "up"
    sys.exit(up() if action == "up" else down())
