# -*- coding: utf-8 -*-
"""错误码归类（P0-2 从 focus_editor.py 迁入）。

529 个失败分支不可能逐个改。在 Handler._send 出口按文案归类，前端拿 code
翻成人话；需要精确控制的分支可以自己带 code（带了就不覆盖）。
"""
import re

ERR_RULES = (
    (r"找不到 hoi4\.exe|未检测到.*游戏目录|游戏目录不存在|不是有效的 HOI4 目录", "GAME_DIR_MISSING"),
    (r"未找到树|没有这棵树|找不到这棵|树.*不存在|没有树", "TREE_NOT_FOUND"),
    (r"写回后校验", "SAVE_VERIFY_FAILED"),
    (r"找不到可写的\s*mod|没有可写的模组|没有可写的 mod|可写的目录", "NO_WRITABLE_MOD"),
    (r"只读|原版目录", "READONLY"),
    (r"找不到来源文件|找不到文件|文件不存在|不存在：|没有这个文件", "FILE_NOT_FOUND"),
    (r"没有这个州|州不存在|没有这个省", "STATE_NOT_FOUND"),
    (r"没给 tag|没有这个国家|找不到国家|tag 不存在|不是有效 tag", "COUNTRY_NOT_FOUND"),
    (r"参数不完整|参数不合法|不合法|必须是|不能为空|越界|超出", "BAD_PARAM"),
    (r"读取失败|解析失败|读图失败|解析不了|不是合法 JSON", "READ_FAILED"),
    (r"写不进去|写入失败|保存失败|复制来源失败|建不出来", "WRITE_FAILED"),
)


def classify_error(msg):
    for pat, code in ERR_RULES:
        if re.search(pat, msg or ""):
            return code
    return "UNKNOWN"
