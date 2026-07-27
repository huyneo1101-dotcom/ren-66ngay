#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cắm token Telegram cho Rèn — chạy MỘT LẦN, trên máy Huy.

    python3 /Users/Huy/Claude/App/Ren66/.github/scripts/setup-telegram.py

Nó làm hết phần máy làm được: hỏi token (gõ ẩn) → kiểm bằng `getMe` → chặn nếu lỡ dán nhầm token
bot Điểm Tin → tự dò `chat_id` → gửi một tin thử → `gh secret set` → bấm chạy workflow thật và
chờ xem xanh hay đỏ. Không phải mở trang web GitHub, không phải chép tay chat_id.

VÌ SAO PHẢI LÀM TAY: secret của GitHub là **chỉ-ghi** — không đọc ngược ra được, kể cả bằng `gh`.
Token chỉ tồn tại trong Telegram và trong đầu @BotFather. Đây là chỗ duy nhất cần tay Huy.

TRƯỚC KHI CHẠY, làm 3 việc trong Telegram:
  1. Mở @BotFather → `/newbot` → đặt tên hiển thị (ví dụ "Rèn 66 ngày") → đặt username kết thúc
     bằng `bot` (ví dụ `ren66ngay_bot`). BotFather trả về một dòng token dạng `1234567890:AA…`.
     ⚠️ BOT RIÊNG, không dùng lại @diemtin24h_bot — xem mục "Telegram" trong CLAUDE.md của repo.
  2. Bấm vào link `t.me/<username>` BotFather vừa đưa, rồi bấm **START** trong khung chat.
     Bỏ bước này là `sendMessage` trả 403 "bot can't initiate conversation with a user" — bot
     không có quyền nhắn trước cho người chưa từng mở chuyện với nó.
  3. Nhắn cho bot một câu bất kỳ ("hi") để script tự dò ra `chat_id`, khỏi phải chép tay.

⚠️ TOKEN KHÔNG ĐƯỢC HIỆN RA MÀN HÌNH: nhận bằng `getpass`, đưa vào `gh` qua **stdin** chứ không
qua tham số dòng lệnh — nếu không, token nằm nguyên trong `ps aux` và trong history của shell.
Bài học có thật bên Điểm Tin 27/07/2026: bản đầu dùng `input()` nên token in nguyên văn ra màn
hình, ảnh chụp gửi đi là lộ, phải `/revoke` lấy token mới.
"""
import getpass
import json
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

REPO = "huyneo1101-dotcom/ren-66ngay"
WORKFLOW = "notify-telegram.yml"
BOT_DIEM_TIN = "diemtin24h_bot"   # bot của app khác — dán nhầm vào đây là hỏng cả hai bên


def tg(token, method, **params):
    """Gọi Bot API. Đi bằng urllib (token không rời tiến trình); SSL hỏng thì lùi sang curl với
    URL đưa qua **stdin** (`-K -`) — vẫn không để token lọt vào dòng lệnh."""
    url = f"https://api.telegram.org/bot{token}/{method}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:          # 401/403/404 vẫn là JSON có ích, đọc tiếp
        try:
            return json.loads(e.read().decode("utf-8"))
        except Exception:
            return {"ok": False, "description": f"HTTP {e.code}"}
    except Exception as e:
        print(f"   (urllib không đi được: {e} — thử lại bằng curl)")
        p = subprocess.run(["curl", "-sS", "-K", "-"], input=f'url = "{url}"\n',
                           capture_output=True, text=True)
        if p.returncode != 0:
            raise RuntimeError(f"curl lỗi {p.returncode}: {(p.stderr or '').strip()[:200]}")
        try:
            return json.loads(p.stdout)
        except ValueError:
            raise RuntimeError(f"đáp án không phải JSON: {p.stdout[:200]}")


def gh(*args, stdin=None):
    return subprocess.run(["gh", *args], input=stdin, capture_output=True, text=True)


def do_chat_id(token):
    """Dò chat_id từ hàng đợi update. Telegram chỉ giữ update ~24h nên nhắn xong hãy chạy ngay."""
    up = tg(token, "getUpdates")
    chats = {}
    for u in (up.get("result") or []):
        m = u.get("message") or u.get("channel_post") or {}
        c = m.get("chat") or {}
        if c.get("id"):
            ten = ((c.get("first_name") or "") + " " + (c.get("last_name") or "")).strip()
            chats[str(c["id"])] = ten or c.get("title") or c.get("username") or "?"

    if not chats:
        print("Hàng đợi trống — chưa nhắn cho bot, hoặc đã quá 24h.")
        return input("Gõ thẳng chat_id (nhiều thì ngăn bằng dấu phẩy): ").strip()

    print("Tìm thấy:")
    ids = list(chats)
    for i, cid in enumerate(ids, 1):
        print(f"  {i}. {chats[cid]} — …{cid[-4:]}")
    chon = input(f"Dùng chat nào? [1-{len(ids)}, Enter = tất cả, hoặc gõ thẳng chat_id]: ").strip()
    if not chon:
        return ",".join(ids)
    if chon.isdigit() and 1 <= int(chon) <= len(ids):
        return ids[int(chon) - 1]
    return chon


def chay_thu_workflow():
    """Bấm chạy thật rồi CHỜ KẾT QUẢ. Bấm xong bỏ đi là đúng cái lỗi đang đi vá: không ai nhìn
    thì xanh hay đỏ cũng như nhau."""
    p = gh("workflow", "run", WORKFLOW, "-R", REPO)
    if p.returncode != 0:
        print(f"⚠️ không bấm chạy được: {(p.stderr or '').strip()[:200]}")
        return
    print("Đã bấm chạy, đang chờ (tối đa 4 phút)…")
    for _ in range(48):
        time.sleep(5)
        q = gh("run", "list", "-R", REPO, "-w", WORKFLOW, "-L", "1",
               "--json", "databaseId,status,conclusion,url")
        try:
            r = (json.loads(q.stdout) or [{}])[0]
        except ValueError:
            continue
        if r.get("status") == "completed":
            if r.get("conclusion") == "success":
                print(f"✅ workflow XANH — kiểm Telegram xem tin đã tới chưa.\n   {r.get('url')}")
            else:
                print(f"❌ workflow {r.get('conclusion')} — xem log:\n   {r.get('url')}")
            return
    print("⏳ quá 4 phút chưa xong. Xem sau bằng:  gh run list -R " + REPO + " -w " + WORKFLOW)


def main():
    print("Cắm token Telegram cho RÈN (repo " + REPO + ")\n")
    print("Chưa tạo bot thì đọc phần đầu file này: @BotFather → /newbot → bấm START → nhắn 'hi'.")
    print("⚠️ Bot RIÊNG của Rèn, KHÔNG dán token của @" + BOT_DIEM_TIN + ".\n")
    token = getpass.getpass("Token (gõ vào sẽ KHÔNG hiện): ").strip()
    if not token or ":" not in token:
        print("❌ Token trống hoặc sai dạng (phải kiểu 1234567890:AA…).")
        return 1

    me = tg(token, "getMe")
    if not me.get("ok"):
        print(f"❌ Token không dùng được: {me.get('description')}")
        return 1
    uname = me["result"].get("username") or "?"
    if uname.lower() == BOT_DIEM_TIN:
        print(f"❌ Đây là token của @{uname} — bot của Điểm Tin. Rèn phải dùng BOT RIÊNG:\n"
              "   dùng chung thì tin nhắc lẫn vào luồng bản tin, và /revoke bên kia là chết bên này.\n"
              "   Mở @BotFather → /newbot tạo bot mới rồi chạy lại.")
        return 1
    print(f"✅ Token OK — bot @{uname}")

    print("\nĐang dò chat_id…")
    chat_id = do_chat_id(token)
    if not chat_id:
        print("❌ Chưa có chat_id.")
        return 1

    hong = False
    for cid in [c.strip() for c in chat_id.split(",") if c.strip()]:
        r = tg(token, "sendMessage", chat_id=cid,
               text="🔥 Rèn — bot đã cắm xong. Từ 21:00 hằng ngày sẽ nhắc chốt ngày ở đây.")
        if r.get("ok"):
            print(f"✅ gửi thử tới …{cid[-4:]} OK")
        else:
            hong = True
            mo_ta = r.get("description") or ""
            print(f"❌ gửi thử tới …{cid[-4:]} hỏng: {mo_ta}")
            if "initiate conversation" in mo_ta:
                print(f"   → Mở t.me/{uname} bấm START rồi chạy lại script này.")

    # Không đặt secret khi gửi thử hỏng: đặt vào là repo mang cấu hình chưa từng chạy được, và
    # sau bản vá 27/07/2026 thì mốc 21:00 sẽ ĐỎ mỗi ngày — bẩn log mà không thêm thông tin gì.
    if hong:
        print("\n⛔ Chưa đặt secret nào cả. Sửa lỗi trên rồi chạy lại.")
        return 1

    # `gh secret set <TÊN> -R <repo>` không kèm `--body` thì ĐỌC TỪ STDIN — cố ý đi đường này để
    # token không xuất hiện trong dòng lệnh (`ps aux`, history của shell).
    for ten, gia_tri in (("TELEGRAM_BOT_TOKEN", token), ("TELEGRAM_CHAT_ID", chat_id)):
        p = gh("secret", "set", ten, "-R", REPO, stdin=gia_tri)
        print(f"✅ đã đặt secret {ten}" if p.returncode == 0
              else f"❌ đặt {ten} hỏng: {(p.stderr or '').strip()[:160]}")

    print("\nChạy thử THẬT (không dry) để chắc đường đi qua GitHub Actions cũng thông:")
    chay_thu_workflow()
    return 0


if __name__ == "__main__":
    sys.exit(main())
