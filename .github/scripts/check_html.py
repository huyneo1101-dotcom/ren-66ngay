#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Soi tin nhắn theo đúng luật parse_mode=HTML của Telegram:
   - chỉ được dùng b i u s code pre a
   - KHÔNG được lồng hai thẻ cùng loại
   - phải đóng đủ, đóng đúng thứ tự
   - dấu & < > trần (không thuộc thẻ) phải được escape
Chạy: python3 check_html.py < file-tin.txt
"""
import re
import sys

OK = {"b", "strong", "i", "em", "u", "ins", "s", "strike", "del", "code", "pre", "a", "tg-spoiler"}
TAG = re.compile(r"<(/?)([a-zA-Z-]+)([^>]*)>")


def check(msg, label):
    loi = []
    stack = []
    for m in TAG.finditer(msg):
        closing, name, _ = m.group(1), m.group(2).lower(), m.group(3)
        if name not in OK:
            loi.append(f"thẻ lạ <{name}>")
            continue
        if closing:
            if not stack or stack[-1] != name:
                loi.append(f"</{name}> đóng sai chỗ (đang mở: {stack})")
            else:
                stack.pop()
        else:
            if name in stack:
                loi.append(f"<{name}> LỒNG trong <{name}> — Telegram trả 400")
            stack.append(name)
    if stack:
        loi.append(f"còn thẻ chưa đóng: {stack}")

    tran = TAG.sub("", msg)
    for ch, ent in (("<", "&lt;"), (">", "&gt;")):
        if ch in tran:
            loi.append(f"ký tự {ch!r} trần chưa escape thành {ent}")
    for m in re.finditer(r"&(?!amp;|lt;|gt;|quot;|#\d+;)", tran):
        loi.append(f"dấu & trần ở vị trí {m.start()}")

    print(("✗ " + label + ": " + " | ".join(loi)) if loi else ("✓ " + label))
    return not loi


if __name__ == "__main__":
    text = sys.stdin.read()
    parts = re.split(r"^----- message .*-----$", text, flags=re.M)[1:]
    if not parts:
        print("(không tìm thấy message nào trong đầu vào)")
        sys.exit(1)
    lab = sys.argv[1] if len(sys.argv) > 1 else "msg"
    sys.exit(0 if all(check(p.strip(), f"{lab} #{i}")
                      for i, p in enumerate(parts, 1)) else 1)
