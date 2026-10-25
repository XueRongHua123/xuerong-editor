# -*- coding: utf-8 -*-
"""检查文本里的“鱼八股”味。用法：
  python work/anti_yubaogu/check.py 文件
  echo "文本" | python work/anti_yubaogu/check.py
命中条目会打印，命中 >=3 时退出码 1。
"""
import re
import sys

PATTERNS = [
    ("人设口癖", r"本鲸|这条我记下了|这条我认|本鱼最喜欢|吃白饭|讨要\s*Token|摸摸鱼"),
    ("不是而是", r"不是[^。！？\n]{1,40}而是"),
    ("不仅而且", r"不仅[^。！？\n]{1,60}而且"),
    ("三段式", r"首先[^。！？\n]{0,60}[。\n][^。！？]{0,80}其次"),
    ("空泛收尾", r"总的来说|总而言之|说到底|归根结底|值得注意的是|需要指出的是|换句话说"),
    ("客套收尾", r"希望(对你|能)有(所)?帮助|如有(其他|任何)问题|随时(问我|找我)|让我们一起"),
    ("强行升华", r"愿(你|我们)|共勉|这就是.{0,12}的意义"),
    ("反问收尾", r"你觉得呢[？?]?\s*$"),
    ("排比堆叠", r"既[^。！？\n]{1,30}又[^。！？\n]{1,30}还"),
]

def main():
    if len(sys.argv) > 1:
        text = open(sys.argv[1], encoding="utf-8", errors="replace").read()
    else:
        text = sys.stdin.read()
    hits = []
    for name, pat in PATTERNS:
        for m in re.finditer(pat, text, re.M):
            hits.append((name, m.group(0)[:80]))
    for name, frag in hits:
        print("[%s] %s" % (name, frag))
    print("命中：%d 条，字数：%d" % (len(hits), len(text)))
    if len(hits) >= 3:
        print("建议重写：鱼八股味偏重。")
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
