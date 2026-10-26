# -*- coding: utf-8 -*-
"""本地 mock OpenAI 流式接口（测试用，端口 8909）。"""
import json
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Mock(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0) or 0)
        self.rfile.read(n)
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        for piece in ["你好", "，这是", "流式", "输出", "测试。"]:
            chunk = {"choices": [{"delta": {"content": piece}}]}
            self.wfile.write(("data: " + json.dumps(chunk, ensure_ascii=False) + "\n\n").encode())
            self.wfile.flush()
            time.sleep(0.12)
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8909
    ThreadingHTTPServer(("127.0.0.1", port), Mock).serve_forever()
