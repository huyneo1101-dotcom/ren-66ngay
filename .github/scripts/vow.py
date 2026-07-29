#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Việc đã hẹn — phần dùng chung: gọi RPC, chọn cái cần nhắc, soạn tin, dựng nút.

Ba script xài module này: `vow_add.py` (đẩy một cam kết), `vow_bot.py` (nhắc khi tới hạn),
`tick_bot.py` (nhận nút bấm).

VÌ SAO TÁCH KHỎI `send_telegram.py` VÀ KHỎI `ren_state`: xem đầu file docs/vows-setup.sql.
Tóm tắt: `habits` là việc LẶP hằng ngày và `isHit` đòi tick đủ mọi việc trong đó — nhét một
việc lẻ vào là chuỗi 66 ngày đứt oan. Module này không đọc, không ghi `ren_state`; hỏng ở đây
không kéo theo hỏng chuỗi.

ĐƯỜNG KIỂM OFFLINE: đặt `REN_VOWS_FILE=<file.json>` thì mọi lời gọi RPC đọc/ghi vào file đó
thay vì gọi Supabase — cùng lối với `REN_STATE_FILE` và `REN_FAKE_UPDATES` đã có sẵn trong repo.
⚠️ Bản giả này chỉ thay ĐƯỜNG TRUYỀN, không thay logic đang được kiểm: chọn ai để nhắc, giãn
cách nhắc, trần số lần, escape HTML, chốt secret — tất cả nằm ở Python. Các chốt phía SQL
(regex mã, trần độ dài, `device` trong mệnh đề `where`) phải kiểm bằng đoạn lệnh cuối
docs/vows-setup.sql, bản giả KHÔNG chứng minh hộ được.
"""
import datetime
import json
import os
import pathlib
import sys
import urllib.error
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from send_telegram import SB_KEY, SB_URL, VN, esc  # noqa: E402

# Nhắc lại sau 20 giờ chứ không phải 24: cron GitHub trễ vài chục phút là chuyện thường (bẫy số
# 4 trong CLAUDE.md), lấy đúng 24 thì lượt nhắc hôm sau trượt sang ngày kế, rồi trôi dần.
NHAC_CACH_GIO = 20
# Nhắc mãi thì Huy tắt thông báo, mà tắt thông báo là mất luôn cả tin nhắc 21:00. Sau 5 lần thì
# dừng — cam kết vẫn để MỞ, và buổi bạn thân sau sẽ mở ra hỏi (đó mới là vai của người, không
# phải của bot). Đừng tự động khai bỏ hộ: bỏ là việc Huy phải tự nói ra.
MAX_NHAC = 5


def device_id():
    """Mã đồng bộ: ưu tiên biến môi trường (GitHub Action), rồi tới file trên máy Huy."""
    d = os.environ.get("REN_DEVICE_ID", "").strip().lower()
    if d:
        return d
    f = pathlib.Path(os.environ.get("REN_DEVICE_FILE", "/Users/Huy/Claude/.ren66-device-id"))
    try:
        return f.read_text(encoding="utf-8").strip().lower()
    except OSError:
        return ""


# ── đường truyền ─────────────────────────────────────────────────────────────────────────
def _gia_doc(path):
    try:
        return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def _gia_ghi(path, rows):
    pathlib.Path(path).write_text(json.dumps(rows, ensure_ascii=False, indent=1),
                                  encoding="utf-8")


def _gia_rpc(path, fn, body, bay_gio):
    """Bản giả file cho đường kiểm. Giữ ĐÚNG các ca lỗi mà SQL ném ra, nhất là 'không có cam
    kết id … của mã này' — nếu bản giả dễ tính hơn SQL thì test xanh mà thật thì đỏ."""
    rows = _gia_doc(path)
    dev = body.get("p_device")
    if fn == "ren_vow_list":
        return [r for r in rows if r.get("device") == dev]
    if fn == "ren_vow_add":
        vid = max([r.get("id", 0) for r in rows] or [0]) + 1
        rows.append({"id": vid, "device": dev, "viec": body["p_viec"].strip(),
                     "han": body["p_han"], "xong_at": None, "bo_at": None,
                     "nhac_lan": 0, "nhac_cuoi": None})
        _gia_ghi(path, rows)
        return vid
    hop = [r for r in rows if r.get("id") == body.get("p_id") and r.get("device") == dev]
    if not hop:
        raise RuntimeError(f"{fn}: không có cam kết id {body.get('p_id')} của mã này")
    r = hop[0]
    if fn == "ren_vow_nhac":
        r["nhac_lan"] = (r.get("nhac_lan") or 0) + 1
        r["nhac_cuoi"] = bay_gio.isoformat()
        _gia_ghi(path, rows)
        return r["nhac_lan"]
    if fn == "ren_vow_set":
        tt = body["p_trang_thai"]
        r["xong_at"] = bay_gio.isoformat() if tt == "xong" else None
        r["bo_at"] = bay_gio.isoformat() if tt == "bo" else None
        _gia_ghi(path, rows)
        cua_toi = [x for x in rows if x.get("device") == dev]
        return [{"viec": r["viec"], "han": r["han"], "xong_at": r["xong_at"],
                 "bo_at": r["bo_at"],
                 "giu": sum(1 for x in cua_toi if x.get("xong_at")),
                 "tong": sum(1 for x in cua_toi if x.get("xong_at") or x.get("bo_at"))}]
    raise RuntimeError(f"hàm lạ: {fn}")


def rpc(fn, body, bay_gio=None):
    """Gọi RPC Supabase. Ném RuntimeError kèm THÔNG ĐIỆP THẬT của Postgres khi hỏng.

    Đọc body lỗi chứ không để `urlopen` raise trần — cùng bài học với `api()` trong
    send_telegram.py: `HTTP Error 400: Bad Request` không cho biết hỏng gì, mà `message` giải
    thích chính xác thì nằm trong cái body vừa bị vứt đi.
    """
    gia = os.environ.get("REN_VOWS_FILE", "").strip()
    if gia:
        return _gia_rpc(gia, fn, body, bay_gio or datetime.datetime.now(VN))

    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/rpc/{fn}", data=json.dumps(body).encode("utf-8"),
        headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}",
                 "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read().decode("utf-8")
            return json.loads(raw) if raw.strip() else None
    except urllib.error.HTTPError as e:
        body_loi = e.read().decode("utf-8", "replace")[:300]
        try:
            body_loi = json.loads(body_loi).get("message") or body_loi
        except ValueError:
            pass
        raise RuntimeError(f"Supabase {e.code}: {body_loi}") from None
    except Exception as e:                                    # noqa: BLE001
        raise RuntimeError(f"không gọi được Supabase: {e}") from None


# ── thời gian ────────────────────────────────────────────────────────────────────────────
def doc_gio(s):
    """Chuỗi ISO của Postgres → datetime có múi giờ. Trả None nếu rỗng/méo."""
    if not s:
        return None
    t = str(s).strip().replace(" ", "T")
    if t.endswith("Z"):
        t = t[:-1] + "+00:00"
    try:
        d = datetime.datetime.fromisoformat(t)
    except ValueError:
        return None
    # Không có múi giờ thì coi là giờ VN — mọi thứ Huy gõ tay đều là giờ VN.
    return d.replace(tzinfo=VN) if d.tzinfo is None else d


def gio_vn(d):
    return d.astimezone(VN)


# ── chọn cái cần nhắc ────────────────────────────────────────────────────────────────────
def can_nhac(rows, now):
    """Lọc ra các cam kết ĐÁNG nhắc lúc `now`, sớm nhất trước.

    Bốn điều kiện, mỗi cái chặn một kiểu hỏng đã lường:
      1. chưa xong và chưa khai bỏ  → nhắc lại việc đã làm là mất tin tưởng ngay lần đầu;
      2. đã tới hạn                 → nhắc sớm là sai hẹn, mà sai hẹn thì cam kết mất nghĩa;
      3. lần trước cách ≥ 20 giờ    → cron chạy 30 phút/lần, không chặn là 48 tin một ngày;
      4. chưa quá MAX_NHAC lần      → xem ghi chú ở hằng số.
    """
    ra = []
    for r in rows:
        if r.get("xong_at") or r.get("bo_at"):
            continue
        han = doc_gio(r.get("han"))
        if han is None or han > now:
            continue
        lan = r.get("nhac_lan") or 0
        if lan >= MAX_NHAC:
            continue
        if lan:
            cuoi = doc_gio(r.get("nhac_cuoi"))
            if cuoi is not None and (now - cuoi).total_seconds() < NHAC_CACH_GIO * 3600:
                continue
        ra.append(r)
    ra.sort(key=lambda r: doc_gio(r.get("han")) or now)
    return ra


def dem(rows):
    """(đã giữ, đã chốt) — con số để đếm hộ. Cam kết còn treo KHÔNG tính vào mẫu số: chưa tới
    lúc phán thì đưa vào là bôi đen tỉ lệ oan, mà tỉ lệ sai thì Huy thôi tin cả bảng."""
    giu = sum(1 for r in rows if r.get("xong_at"))
    tong = sum(1 for r in rows if r.get("xong_at") or r.get("bo_at"))
    return giu, tong


# ── soạn tin ─────────────────────────────────────────────────────────────────────────────
def tin(r, rows, now):
    """Một tin cho một cam kết. `viec` do Huy gõ nên PHẢI escape — dấu `<` hay `&` trần là
    Telegram từ chối CẢ tin nhắn (bẫy số 1 trong CLAUDE.md), không phải bỏ qua ký tự đó."""
    han = doc_gio(r.get("han"))
    lan = r.get("nhac_lan") or 0
    tre = ""
    if han is not None:
        gio = (now - han).total_seconds() / 3600
        if gio >= 24:
            tre = f" · trễ {int(gio // 24)} ngày"
        elif gio >= 1:
            tre = f" · trễ {int(gio)} giờ"

    dong = ["🤝 <b>Việc đã hẹn — tới giờ</b>",
            f"“{esc(r.get('viec'))}”"]
    if han is not None:
        dong.append(f"<i>Hẹn {gio_vn(han):%H:%M %d/%m}{tre}"
                    + (f" · nhắc lần {lan + 1}/{MAX_NHAC}" if lan else "") + "</i>")
    if lan + 1 >= MAX_NHAC:
        dong.append("\n<i>Đây là lần nhắc cuối. Không bấm gì thì nó nằm treo tới buổi sau.</i>")

    giu, tong = dem(rows)
    if tong:
        dong.append(f"\nĐã giữ <b>{giu}/{tong}</b> việc đã hẹn.")
    return "\n".join(dong)


def nut_vow(r):
    """Hai nút, cố ý không có nút thứ ba.

    “Chưa làm” KHÔNG phải nút bỏ qua — nó ghi lại là không giữ được, và đó chính là chỗ đếm.
    Không có nút đó thì cách duy nhất để tin im đi là lờ nó, mà lờ thì con số đếm được thành
    vô nghĩa: mẫu số chỉ còn những lần Huy làm được.
    """
    return {"inline_keyboard": [[
        {"text": "✅ Đã làm", "callback_data": f"ren:vow:{r['id']}:xong"},
        {"text": "🙅 Chưa làm", "callback_data": f"ren:vow:{r['id']}:bo"},
    ]]}


def tin_sau_khi_bam(kq, trang_thai):
    """Tin vẽ lại sau khi bấm, kèm nút đảo chiều — bấm nhầm mà không có đường lùi thì lần sau
    người ta ngại bấm, và ngại bấm là mất luôn số liệu."""
    han = doc_gio(kq.get("han"))
    khi = f" (hẹn {gio_vn(han):%H:%M %d/%m})" if han is not None else ""
    dau = {"xong": "✅ <b>Đã làm</b>", "bo": "🙅 <b>Chưa làm</b>",
           "mo": "↩️ <b>Đã mở lại</b>"}[trang_thai]
    dong = [dau, f"“{esc(kq.get('viec'))}”{khi}"]
    giu, tong = kq.get("giu") or 0, kq.get("tong") or 0
    if tong:
        dong.append(f"\nĐã giữ <b>{giu}/{tong}</b> việc đã hẹn.")
    nhan = "↩️ Bấm nhầm, mở lại" if trang_thai in ("xong", "bo") else "✅ Đã làm"
    data = "mo" if trang_thai in ("xong", "bo") else "xong"
    kb = {"inline_keyboard": [[{"text": nhan,
                                "callback_data": f"ren:vow:{kq['id']}:{data}"}]]}
    return "\n".join(dong), kb
