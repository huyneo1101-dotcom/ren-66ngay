#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Nhắc việc đã hẹn khi tới giờ — chạy 30 phút/lần bằng GitHub Action.

    TELEGRAM_BOT_TOKEN=... TELEGRAM_CHAT_ID=... REN_DEVICE_ID=... python3 .github/scripts/vow_bot.py
    DRY_RUN=1 REN_VOWS_FILE=/tmp/vows.json python3 .github/scripts/vow_bot.py   # không cần mạng

VÌ SAO KHÔNG GỘP VÀO TIN NHẮC 21:00: cam kết có giờ riêng ("mai 8h gọi cho anh T"), gộp vào một
mốc cố định là nhắc sai hẹn — mà cam kết nhắc sai hẹn thì không còn là cam kết. Hai việc cũng
khác nhịp hẳn nhau, đúng lý lẽ đã tách `tick_bot.py` khỏi `send_telegram.py`.

⏱️ Cron GitHub trễ 5–15 phút là chuyện thường (bẫy số 4, CLAUDE.md). Nhắc ở đây vì thế là
"trong vòng nửa tiếng sau hạn", không phải đúng phút. Muốn đúng phút thì phải có server luôn
bật — không đáng.

Mã thoát: 0 = xong (kể cả khi không có gì để nhắc) · 1 = có lỗi thật hoặc cấu hình gãy.
"""
import datetime
import json
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from send_telegram import MAX_LEN, VN, api                       # noqa: E402
from vow import can_nhac, nut_vow, rpc, tin                      # noqa: E402


def gui(token, chats, text, kb):
    """Gửi một tin kèm bàn phím riêng của nó. Trả True nếu MỌI nơi nhận đều nhận được.

    Chỉ True mới được ghi `ren_vow_nhac`: đếm là đã nhắc trong khi tin không tới thì cam kết đó
    im lặng trôi mất — đúng kiểu hỏng mà tính năng này sinh ra để chống.
    """
    if len(text) > MAX_LEN:
        text = text[:MAX_LEN - 1] + "…"
    ok = True
    for chat in chats:
        payload = {"chat_id": chat, "text": text, "parse_mode": "HTML",
                   "disable_web_page_preview": True, "reply_markup": kb}
        try:
            res = api(token, "sendMessage", payload)
        except Exception as e:                                   # noqa: BLE001
            print(f"LỖI sendMessage tới {chat}: {e}", file=sys.stderr)
            ok = False
            continue
        if not res.get("ok"):
            print(f"LỖI sendMessage tới {chat}: {res}", file=sys.stderr)
            ok = False
    return ok


def main():
    dry = os.environ.get("DRY_RUN") == "1"
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chats = [c.strip() for c in os.environ.get("TELEGRAM_CHAT_ID", "").split(",") if c.strip()]
    device = os.environ.get("REN_DEVICE_ID", "").strip().lower()
    vows_file = os.environ.get("REN_VOWS_FILE", "").strip()

    # CHƯA CẤU HÌNH ≠ CẤU HÌNH GÃY — cùng chốt với send_telegram.py, xem bẫy số 5 trong
    # CLAUDE.md. Thêm secret mới thì phải thêm vào cả ba script, không thì nó lọt vùng câm.
    thieu = ([] if token else ["TELEGRAM_BOT_TOKEN"]) \
        + ([] if chats else ["TELEGRAM_CHAT_ID"]) \
        + ([] if (device or vows_file) else ["REN_DEVICE_ID"])
    if not dry and thieu:
        if not (token or chats or device):
            print("Chưa đặt secret nào (TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID/REN_DEVICE_ID) — "
                  "chưa cấu hình, bỏ qua, KHÔNG coi là lỗi.", file=sys.stderr)
            return 0
        print("❌ CẤU HÌNH GÃY — đã có secret nhưng THIẾU: " + ", ".join(thieu), file=sys.stderr)
        # Khác send_telegram.py ở đúng một chỗ: ở đó mất device vẫn gửi được tin rút gọn có ích,
        # còn ở đây không có mã thì KHÔNG BIẾT có cam kết nào — không có gì để gửi. Đỏ luôn.
        return 1

    now = datetime.datetime.now(VN)
    try:
        rows = rpc("ren_vow_list", {"p_device": device}, now) or []
    except RuntimeError as e:
        # CHƯA DỰNG BẢNG ≠ SUPABASE GÃY — cùng lối tách với "chưa cấu hình ≠ cấu hình gãy".
        # PostgREST trả 404 + PGRST202 khi chưa có hàm, tức là docs/vows-setup.sql chưa được
        # chạy lần nào: chưa có gì để hỏng. Không tách thì từ lúc đẩy mã lên tới lúc Huy dán
        # SQL, lịch này đỏ 48 lần MỖI NGÀY — mà một cổng kêu oan liên tục thì chỉ vài ngày là
        # bị lờ, rồi lần kêu thật cũng bị lờ theo.
        if "PGRST202" in str(e) or "Could not find the function" in str(e):
            print("Chưa dựng bảng việc đã hẹn (chạy docs/vows-setup.sql) — "
                  "chưa cấu hình, bỏ qua, KHÔNG coi là lỗi.", file=sys.stderr)
            return 0
        print(f"❌ không đọc được danh sách: {e}", file=sys.stderr)
        return 1

    den = can_nhac(rows, now)
    msgs = [(r, tin(r, rows, now), nut_vow(r)) for r in den]

    if dry:
        print(f"=== DRY_RUN — {len(msgs)} message ===")
        for i, (_, m, _kb) in enumerate(msgs, 1):
            print(f"\n----- message {i}/{len(msgs)} ({len(m)} ký tự) -----")
            print(m)
        print("\n----- nút -----\n"
              + json.dumps([kb for _, _, kb in msgs], ensure_ascii=False))
        return 0

    if not msgs:
        print("Không có việc đã hẹn nào tới giờ.")
        return 0

    rc = 0
    for r, text, kb in msgs:
        if not gui(token, chats, text, kb):
            rc = 1
            continue                                   # KHÔNG đếm là đã nhắc — xem docstring gui()
        try:
            lan = rpc("ren_vow_nhac", {"p_device": device, "p_id": r["id"]}, now)
            print(f"đã nhắc #{r['id']} (lần {lan}): {r['viec'][:60]}")
        except RuntimeError as e:
            # Gửi rồi mà không ghi được: lần sau nhắc lại: phiền, nhưng không mất. Vẫn để đỏ để
            # còn biết Supabase đang hỏng, chứ không nuốt.
            print(f"⚠️ đã gửi nhưng không ghi được lượt nhắc #{r['id']}: {e}", file=sys.stderr)
            rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
