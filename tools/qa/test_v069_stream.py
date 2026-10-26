# -*- coding: utf-8 -*-
"""v0.69 流式自测：本地 mock OpenAI SSE + 调编辑器 /api/ai_chat?stream"""
import io
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.dirname(HERE)
CFG = os.path.join(WORK, "ai_config.json")
BACKUP = os.path.join(HERE, "_ai_config_backup.json")
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
            time.sleep(0.05)
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


def main():
    fails = []

    def check(name, cond, extra=""):
        print(("PASS " if cond else "FAIL ") + name + (("  " + str(extra)) if not cond else ""))
        if not cond:
            fails.append(name)

    had_cfg = os.path.exists(CFG)
    if had_cfg:
        shutil.copy2(CFG, BACKUP)
    io.open(CFG, "w", encoding="utf-8", newline="").write(json.dumps({
        "provider": "custom", "base_url": "http://127.0.0.1:%d" % MOCK_PORT,
        "model": "mock", "api_key": "mock", "system": "你是测试助手。"}, ensure_ascii=False))

    mock = ThreadingHTTPServer(("127.0.0.1", MOCK_PORT), Mock)
    threading.Thread(target=mock.serve_forever, daemon=True).start()
    check("mock 起来了", wait_port(MOCK_PORT, 5))

    env = dict(os.environ)
    proc = subprocess.Popen([sys.executable, os.path.join(WORK, "focus_editor.py"), "--port", str(EDITOR_PORT)],
                            cwd=WORK, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
    check("编辑器起来了", wait_port(EDITOR_PORT, 60))

    try:
        payload = json.dumps({"prompt": "测试", "context": "", "stream": True}).encode()
        req = urllib.request.Request("http://127.0.0.1:%d/api/ai_chat" % EDITOR_PORT, data=payload,
                                     headers={"Content-Type": "application/json"})
        pieces, ended, first_at, t0 = [], False, None, time.time()
        with urllib.request.urlopen(req, timeout=60) as r:
            ctype = r.headers.get("Content-Type", "")
            for raw in r:
                line = raw.decode("utf-8", "replace").strip()
                if not line.startswith("data:"):
                    continue
                obj = json.loads(line[5:].strip())
                if obj.get("d"):
                    if first_at is None:
                        first_at = time.time() - t0
                    pieces.append(obj["d"])
                if obj.get("end"):
                    ended = obj
        text = "".join(pieces)
        check("Content-Type 是 SSE", "text/event-stream" in ctype, ctype)
        check("收到 5 个片段", len(pieces) == 5, pieces)
        check("拼起来是完整句子", text == "你好，这是流式输出测试。", text)
        check("首片段够快（<2s）", first_at is not None and first_at < 2.0, first_at)
        check("有结束标记", bool(ended) and ended.get("ok") is True, ended)
    finally:
        try:
            proc.terminate()
        except Exception:
            pass
        mock.shutdown()
        time.sleep(1)
        if had_cfg and os.path.exists(BACKUP):
            shutil.move(BACKUP, CFG)
            print("已恢复原 ai_config.json")
        elif not had_cfg and os.path.exists(CFG):
            os.remove(CFG)
            print("已删除测试用 ai_config.json")

    print("\n结果：", "全部通过" if not fails else ("失败 " + str(fails)))
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
