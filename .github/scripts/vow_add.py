#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Đẩy MỘT việc đã hẹn lên Supabase để được nhắc đúng giờ.

    python3 .github/scripts/vow_add.py --viec "nhắn mẹ hỏi giờ rảnh" --han "30/07 21:00"
    python3 .github/scripts/vow_add.py --viec "..." --han "mai 21:00"
    python3 .github/scripts/vow_add.py --liet-ke          # xem cái đang treo + số đã giữ
    python3 .github/scripts/vow_add.py --viec "..." --han "..." --thu   # in ra, KHÔNG đẩy

Mã đồng bộ lấy từ `REN_DEVICE_ID`, không có thì đọc /Users/Huy/Claude/.ren66-device-id.

DÙNG Ở ĐÂU: cuối một buổi `/banthan`, khi đã chốt được đúng một việc nhỏ có ngày giờ. Chỉ dòng
cam kết và hạn rời khỏi máy — nội dung buổi nói chuyện ở lại trong ~/Claude/BanThan/, không đẩy
đi đâu.

Mã thoát: 0 = đã đẩy · 1 = hỏng (in rõ hỏng gì).
"""
import argparse
import datetime
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from send_telegram import VN                              # noqa: E402
from vow import can_nhac, dem, device_id, doc_gio, gio_vn, rpc  # noqa: E402

GIO_MAC_DINH = (21, 0)          # "30/07" không kèm giờ thì hiểu là 21:00 — giờ chốt ngày của Rèn


def doc_han(s, now=None):
    """Đổi cách Huy gõ giờ thành datetime giờ VN. Ném ValueError nếu không hiểu.

    Nhận: 'mai 21:00' · 'tối nay 22h' · '30/07 21:00' · '30/07' · '2026-07-30 21:00' ·
    '2026-07-30T21:00'. Cố ý KHÔNG đoán mò: gõ gì không nằm trong danh sách này thì báo lỗi và
    in ra các dạng hợp lệ, chứ đừng lẳng lặng chọn một mốc rồi nhắc sai ngày.
    """
    now = now or datetime.datetime.now(VN)
    t = " ".join(str(s or "").strip().lower().split())
    if not t:
        raise ValueError("thiếu hạn")

    ngay, phan_gio = None, t
    for tu, cong in (("hôm nay", 0), ("tối nay", 0), ("nay", 0),
                     ("ngày mai", 1), ("mai", 1), ("mốt", 2), ("ngày kia", 2)):
        if t.startswith(tu):
            ngay = (now + datetime.timedelta(days=cong)).date()
            phan_gio = t[len(tu):].strip()
            break

    if ngay is None:
        m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})[t ]?(.*)$", t)
        if m:
            ngay = datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            phan_gio = m.group(4).strip()
        else:
            m = re.match(r"^(\d{1,2})[/-](\d{1,2})(?:[/-](\d{4}))?\s*(.*)$", t)
            if not m:
                raise ValueError(f"không hiểu hạn {s!r}")
            d, thang = int(m.group(1)), int(m.group(2))
            nam = int(m.group(3)) if m.group(3) else now.year
            ngay = datetime.date(nam, thang, d)
            phan_gio = m.group(4).strip()
            # Gõ ngày đã qua mà không ghi năm thì gần như chắc chắn là ý năm sau.
            if not m.group(3) and ngay < now.date():
                ngay = ngay.replace(year=nam + 1)

    gio, phut = GIO_MAC_DINH
    if phan_gio:
        m = re.match(r"^(\d{1,2})(?:[:h](\d{1,2}))?h?$", phan_gio)
        if not m:
            raise ValueError(f"không hiểu phần giờ {phan_gio!r}")
        gio = int(m.group(1))
        phut = int(m.group(2) or 0)
    if not (0 <= gio <= 23 and 0 <= phut <= 59):
        raise ValueError(f"giờ ngoài khoảng: {gio}:{phut}")
    return datetime.datetime(ngay.year, ngay.month, ngay.day, gio, phut, tzinfo=VN)


def bang(rows, now):
    giu, tong = dem(rows)
    mo = [r for r in rows if not r.get("xong_at") and not r.get("bo_at")]
    ra = [f"Đã giữ {giu}/{tong} việc đã hẹn." if tong else "Chưa chốt việc nào."]
    if mo:
        den = {r["id"] for r in can_nhac(rows, now)}
        ra.append(f"Đang treo {len(mo)}:")
        for r in sorted(mo, key=lambda x: doc_gio(x.get("han")) or now):
            h = doc_gio(r.get("han"))
            ra.append(f"  #{r['id']} · {gio_vn(h):%H:%M %d/%m} · {r['viec']}"
                      + ("  ← tới hạn" if r["id"] in den else ""))
    return "\n".join(ra)


def main():
    p = argparse.ArgumentParser(description="Đẩy một việc đã hẹn lên Supabase")
    p.add_argument("--viec", help="nguyên văn việc đã hẹn")
    p.add_argument("--han", help="hạn: 'mai 21:00' · '30/07 21:00' · '2026-07-30 21:00'")
    p.add_argument("--liet-ke", action="store_true", help="chỉ xem, không đẩy")
    p.add_argument("--thu", action="store_true", help="in ra rồi dừng, không đẩy")
    a = p.parse_args()

    now = datetime.datetime.now(VN)
    dev = device_id()
    if not dev:
        print("❌ Không tìm được mã đồng bộ (REN_DEVICE_ID hoặc "
              "/Users/Huy/Claude/.ren66-device-id).", file=sys.stderr)
        return 1

    if a.liet_ke:
        try:
            rows = rpc("ren_vow_list", {"p_device": dev}, now) or []
        except RuntimeError as e:
            print(f"❌ {e}", file=sys.stderr)
            return 1
        print(bang(rows, now))
        return 0

    if not a.viec or not a.viec.strip():
        print("❌ Thiếu --viec.", file=sys.stderr)
        return 1
    if not a.han:
        print("❌ Thiếu --han.", file=sys.stderr)
        return 1
    try:
        han = doc_han(a.han, now)
    except ValueError as e:
        print(f"❌ {e}. Dạng nhận được: 'mai 21:00' · 'tối nay 22h' · '30/07 21:00' · "
              f"'30/07' (mặc định 21:00) · '2026-07-30 21:00'.", file=sys.stderr)
        return 1
    viec = " ".join(a.viec.split())
    if len(viec) > 300:
        print(f"❌ Cam kết dài {len(viec)} ký tự, trần 300. Rút gọn lại — cam kết dài là "
              f"cam kết chưa đủ nhỏ.", file=sys.stderr)
        return 1

    if a.thu:
        print(f"[THỬ] sẽ đẩy: “{viec}” — hạn {gio_vn(han):%H:%M %d/%m/%Y}")
        return 0

    try:
        vid = rpc("ren_vow_add",
                  {"p_device": dev, "p_viec": viec, "p_han": han.isoformat()}, now)
    except RuntimeError as e:
        print(f"❌ Không đẩy được: {e}", file=sys.stderr)
        return 1
    print(f"✅ Đã hẹn #{vid}: “{viec}” — {gio_vn(han):%H:%M %d/%m}. "
          f"Tới giờ bot Rèn sẽ nhắc, bấm nút ngay trong tin.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
