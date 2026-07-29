#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Nhận nút bấm từ tin nhắc Telegram và ghi tick vào Supabase.

    TELEGRAM_BOT_TOKEN=... TELEGRAM_CHAT_ID=... REN_DEVICE_ID=... python3 .github/scripts/tick_bot.py
    DRY_RUN=1 python3 .github/scripts/tick_bot.py    # đọc hàng đợi, in ra, KHÔNG ghi, KHÔNG trả lời

Mã thoát: 0 = xong (kể cả khi không có nút nào được bấm) · 1 = có lỗi thật.

VÌ SAO TÁCH KHỎI send_telegram.py: hai việc khác nhịp hẳn nhau. Gửi nhắc chạy MỘT lần lúc
21:00; nhận nút phải chạy đi chạy lại vì không biết Huy bấm lúc nào. Nhét chung thì hoặc phải
gửi nhắc mỗi 5 phút, hoặc phải chờ tới 21:00 hôm sau mới ghi được cái nút bấm tối nay.

⚠️ BOT RIÊNG, ĐỪNG GỘP VỀ BOT ĐIỂM TIN. `getUpdates` chỉ chấp nhận MỘT người đọc: ai xác nhận
`offset` trước thì xoá sạch update cũ hơn khỏi hàng đợi — kể cả loại mình không đọc. Bot Điểm
Tin poll mỗi 5 phút với `allowed_updates:["message"]` rồi xác nhận `max(message_id)+1`, nên nếu
Rèn dùng chung token thì mỗi callback có id nhỏ hơn message cuối sẽ **bị nuốt mất ngẫu nhiên** —
Huy bấm nút, thấy im, bấm lại. Đó là lý do 27/07/2026 Rèn tách sang bot riêng.

⚠️ XÁC NHẬN NGAY SAU KHI ĐỌC, TRƯỚC KHI XỬ LÝ — cùng lý lẽ với bot Điểm Tin: xác nhận sau thì
một callback làm script lỗi sẽ được đọc lại mỗi vòng và lỗi mãi mãi. Đổi lại có thể mất nút bấm
nếu job chết giữa chừng, nên MỌI nhánh lỗi đều phải NHẮN LẠI cho Huy — im lặng ở đây là kiểu
hỏng tệ nhất: Huy tưởng đã chốt ngày, thực tế không có gì được ghi, và mai mới phát hiện chuỗi
đứt.

⚠️ KHÔNG đọc-sửa-đẩy cả state. Ghi bằng RPC `ren_tick` (xem docs/supabase-setup.sql) — nó
đọc-sửa-ghi trong một giao dịch, chỉ đụng `days[ngày].t`. Nếu bot tự đọc state rồi `ren_push`
đè lại thì mọi thay đổi app vừa lưu giữa hai bước đó biến mất, và biến mất im lặng.
"""
import datetime
import json
import os
import pathlib
import sys
import urllib.error
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from send_telegram import (  # noqa: E402
    MAX_LEN, SB_KEY, SB_URL, VN, api, build, fetch_state, nut)
from vow import rpc as vow_rpc, tin_sau_khi_bam  # noqa: E402


def chats_cho_phep():
    return {c.strip() for c in os.environ.get("TELEGRAM_CHAT_ID", "").split(",") if c.strip()}


def doc_nut(token):
    """Lấy các callback đang chờ rồi XÁC NHẬN NGAY. Trả list [(cb_id, chat, msg_id, data)]."""
    # Đường kiểm: nạp update giả từ file thay vì gọi Telegram. Có nó thì luồng lọc/parse kiểm
    # được ngay trên máy, không cần token và không đụng hàng đợi thật — mà đó đúng là chỗ dễ
    # sai nhất (callback lạ, chat lạ, data méo).
    gia = os.environ.get("REN_FAKE_UPDATES", "").strip()
    if gia:
        updates = json.loads(pathlib.Path(gia).read_text(encoding="utf-8"))
        ok = chats_cho_phep()
        out = []
        for u in updates:
            cb = u.get("callback_query") or {}
            data = cb.get("data") or ""
            chat = str(((cb.get("message") or {}).get("chat") or {}).get("id") or "")
            if not data.startswith("ren:"):
                print(f"bỏ callback không phải của Rèn: {data!r}", file=sys.stderr)
                continue
            if ok and chat not in ok:
                print(f"bỏ callback từ chat lạ …{chat[-4:]}", file=sys.stderr)
                continue
            out.append((cb.get("id"), chat, (cb.get("message") or {}).get("message_id"), data))
        return out

    try:
        r = api(token, "getUpdates", {"timeout": 0, "allowed_updates": ["callback_query"]})
    except Exception as e:                                    # noqa: BLE001
        print(f"getUpdates lỗi: {e}", file=sys.stderr)
        return None
    if not r.get("ok"):
        print(f"getUpdates lỗi: {r.get('description')}", file=sys.stderr)
        return None

    updates = r.get("result") or []
    if not updates:
        return []

    last = max(u["update_id"] for u in updates)
    try:
        api(token, "getUpdates", {"offset": last + 1, "limit": 1, "timeout": 0})
    except Exception as e:                                    # noqa: BLE001
        # Không xác nhận được thì DỪNG HẲN, đừng xử lý: xử lý mà không xoá khỏi hàng đợi là
        # vòng sau tick lại lần nữa. Tick lặp không sai kết quả (đặt t = đủ việc, idempotent)
        # nhưng tin nhắn sẽ bị sửa đi sửa lại, trông như bot loạn.
        print(f"không xác nhận được offset ({e}) — bỏ lượt này, thử lại vòng sau", file=sys.stderr)
        return None

    ok = chats_cho_phep()
    out = []
    for u in updates:
        cb = u.get("callback_query") or {}
        data = cb.get("data") or ""
        chat = str(((cb.get("message") or {}).get("chat") or {}).get("id") or "")
        if not data.startswith("ren:"):
            continue
        # Bot công khai: ai cũng nhắn được, nên vẫn lọc dù callback chỉ sinh từ nút bot gửi.
        # Không lọc thì người lạ ghi được vào nhật ký của Huy.
        if ok and chat not in ok:
            print(f"bỏ callback từ chat lạ …{chat[-4:]}", file=sys.stderr)
            continue
        out.append((cb.get("id"), chat, (cb.get("message") or {}).get("message_id"), data))
    return out


def goi_ren_tick(device, ngay, xong):
    """Gọi RPC. Trả (kết quả dict, lỗi str) — đúng một trong hai khác None."""
    body = json.dumps({"p_device": device, "p_ngay": ngay, "p_xong": xong}).encode("utf-8")
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/rpc/ren_tick", data=body,
        headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}",
                 "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8")), None
    except urllib.error.HTTPError as e:
        # Thông điệp của Postgres nằm trong body — lấy ra để Huy biết hỏng gì, đừng chỉ in mã số.
        raw = e.read().decode("utf-8", "replace")[:300]
        try:
            raw = json.loads(raw).get("message") or raw
        except ValueError:
            pass
        return None, f"Supabase {e.code}: {raw}"
    except Exception as e:                                    # noqa: BLE001
        return None, f"không gọi được Supabase: {e}"


def sua_tin(token, chat, msg_id, device):
    """Vẽ lại tin nhắc theo trạng thái MỚI, kèm nút đảo chiều.

    Đây là phản hồi thật sự cho người bấm. `answerCallbackQuery` chỉ hiện một dòng chớp rồi
    tắt, mà job này chạy theo cron nên có thể trả lời muộn vài phút — lúc đó dòng chớp đã hết
    hạn và Huy không thấy gì. Tin nhắn được sửa thì nằm lại đó, mở ra lúc nào cũng thấy.
    """
    state, updated_at = fetch_state(device)
    now = datetime.datetime.now(VN)
    msgs = build(state, updated_at, now)
    text = msgs[-1]
    if len(text) > MAX_LEN:
        text = text[:MAX_LEN - 1] + "…"
    payload = {"chat_id": chat, "message_id": msg_id, "text": text,
               "parse_mode": "HTML", "disable_web_page_preview": True}
    kb = nut(state, now)
    if kb:
        payload["reply_markup"] = kb
    try:
        res = api(token, "editMessageText", payload)
        if not res.get("ok"):
            print(f"editMessageText lỗi: {res.get('description')}", file=sys.stderr)
    except Exception as e:                                    # noqa: BLE001
        print(f"editMessageText lỗi: {e}", file=sys.stderr)


def tra_loi(token, cb_id, text):
    try:
        api(token, "answerCallbackQuery", {"callback_query_id": cb_id, "text": text})
    except Exception as e:                                    # noqa: BLE001
        print(f"answerCallbackQuery lỗi: {e}", file=sys.stderr)


def bao_loi(token, chat, text):
    """Nhắn lỗi cho Huy. Bấm nút mà không có hồi âm nào là kiểu hỏng tệ nhất của tính năng này."""
    try:
        api(token, "sendMessage", {"chat_id": chat, "text": text, "parse_mode": "HTML"})
    except Exception as e:                                    # noqa: BLE001
        print(f"không gửi được tin báo lỗi: {e}", file=sys.stderr)


def xu_ly_vow(token, device, cb_id, chat, msg_id, phan, dry):
    """Nút của VIỆC ĐÃ HẸN: `ren:vow:<id>:<xong|bo|mo>`. Trả 0 nếu ổn, 1 nếu hỏng thật.

    Đi chung bot và chung vòng poll với nút tick của Rèn là BẮT BUỘC, không phải cho gọn:
    `getUpdates` chỉ chấp nhận MỘT người đọc — dựng thêm một script poll nữa trên cùng token thì
    hai bên nuốt update của nhau, Huy bấm nút thấy im rồi bấm lại (xem cảnh báo đầu file).

    Ghi qua RPC `ren_vow_set`, tuyệt đối không đọc-sửa-ghi phía script: hai lịch cron trùng phút
    sẽ đọc cùng một trạng thái cũ rồi đè nhau.
    """
    try:
        vid = int(phan[2])
    except ValueError:
        print(f"callback vow id lạ, bỏ qua: {phan}", file=sys.stderr)
        return 0
    trang_thai = phan[3]
    if trang_thai not in ("xong", "bo", "mo"):
        print(f"callback vow trạng thái lạ, bỏ qua: {phan}", file=sys.stderr)
        return 0

    if dry:
        print(f"[DRY_RUN] sẽ ren_vow_set(device, {vid}, {trang_thai}) rồi sửa tin {msg_id}")
        return 0

    try:
        kq = vow_rpc("ren_vow_set",
                     {"p_device": device, "p_id": vid, "p_trang_thai": trang_thai})
    except RuntimeError as e:
        print(f"ren_vow_set hỏng: {e}", file=sys.stderr)
        tra_loi(token, cb_id, "Không ghi được, xem tin nhắn báo lỗi")
        bao_loi(token, chat,
                f"⚠️ <b>Việc đã hẹn — không ghi được</b>\n#{vid} → {trang_thai}.\n"
                f"<code>{e}</code>\nBấm lại sau, hoặc ghi tay vào file buổi.")
        return 1

    kq = (kq[0] if isinstance(kq, list) else kq) or {}
    kq["id"] = vid
    text, kb = tin_sau_khi_bam(kq, trang_thai)
    tra_loi(token, cb_id, {"xong": "Đã ghi: đã làm", "bo": "Đã ghi: chưa làm",
                           "mo": "Đã mở lại"}[trang_thai])
    try:
        res = api(token, "editMessageText",
                  {"chat_id": chat, "message_id": msg_id, "text": text,
                   "parse_mode": "HTML", "disable_web_page_preview": True,
                   "reply_markup": kb})
        if not res.get("ok"):
            print(f"editMessageText lỗi: {res.get('description')}", file=sys.stderr)
    except Exception as e:                                    # noqa: BLE001
        print(f"editMessageText lỗi: {e}", file=sys.stderr)
    print(f"vow #{vid} → {trang_thai} (đã giữ {kq.get('giu')}/{kq.get('tong')})")
    return 0


def main():
    dry = os.environ.get("DRY_RUN") == "1"
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chats = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    device = os.environ.get("REN_DEVICE_ID", "").strip().lower()

    # Cùng luật "chưa cấu hình ≠ cấu hình gãy" như send_telegram.py — xem bẫy số 5 trong
    # CLAUDE.md. Thêm secret mới thì phải thêm vào cả hai chỗ, không thì nó lọt vùng câm.
    thieu = ([] if token else ["TELEGRAM_BOT_TOKEN"]) \
        + ([] if chats else ["TELEGRAM_CHAT_ID"]) \
        + ([] if device else ["REN_DEVICE_ID"])
    if thieu and not dry:
        if not (token or chats or device):
            print("Chưa đặt secret nào — chưa cấu hình, bỏ qua, KHÔNG coi là lỗi.", file=sys.stderr)
            return 0
        print("❌ CẤU HÌNH GÃY — đã có secret nhưng THIẾU: " + ", ".join(thieu), file=sys.stderr)
        return 1

    nuts = doc_nut(token)
    if nuts is None:
        return 1
    if not nuts:
        print("Không có nút nào được bấm.")
        return 0

    rc = 0
    for cb_id, chat, msg_id, data in nuts:
        phan = data.split(":")
        # Nút của VIỆC ĐÃ HẸN đi trước: nó có 4 phần, còn nút chốt ngày của Rèn có 3.
        if len(phan) == 4 and phan[1] == "vow":
            rc = xu_ly_vow(token, device, cb_id, chat, msg_id, phan, dry) or rc
            continue
        if len(phan) != 3 or phan[1] not in ("xong", "bo"):
            print(f"callback lạ, bỏ qua: {data}", file=sys.stderr)
            continue
        _, hanh_dong, ngay = phan
        xong = hanh_dong == "xong"

        if dry:
            print(f"[DRY_RUN] sẽ ren_tick(device, {ngay}, {xong}) rồi sửa tin {msg_id}")
            continue

        kq, loi = goi_ren_tick(device, ngay, xong)
        if loi:
            print(f"ren_tick hỏng: {loi}", file=sys.stderr)
            tra_loi(token, cb_id, "Không ghi được, xem tin nhắn báo lỗi")
            bao_loi(token, chat,
                    f"⚠️ <b>Rèn — không ghi được tick</b>\nNgày {ngay}, "
                    f"{'chốt xong' if xong else 'bỏ tick'}.\n<code>{loi}</code>\n"
                    f"Mở app tick tay để khỏi đứt chuỗi.")
            rc = 1
            continue

        n, need = kq.get("n"), kq.get("need")
        print(f"đã {'chốt' if xong else 'bỏ tick'} ngày {ngay}: {n}/{need} việc")
        tra_loi(token, cb_id,
                f"Đã chốt ngày {ngay}" if xong else f"Đã bỏ tick ngày {ngay}")
        sua_tin(token, chat, msg_id, device)

    return rc


if __name__ == "__main__":
    sys.exit(main())
