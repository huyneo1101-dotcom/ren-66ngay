#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TEST HỒI QUY CHO CHECKER HTML TELEGRAM (.github/scripts/check_html.py).

⚠ VÌ SAO CÓ FILE NÀY — luật mục 17 CLAUDE.md toàn cục (đúc 29.7.2026):
`check_html.py` là cổng loại **"hỏng thì im lặng cho qua"**. Tin sạch thì nó in "✓"; mà
checker chết cũng in "✓" y hệt. Chạy `send_telegram.py | check_html.py` thấy toàn dấu ✓
KHÔNG chứng minh được gì — chỉ ca **PHẢI CHẶN** mới phân biệt cổng sống với cổng chết.

Cái nó canh là bẫy số 1 đã vấp thật 27/07/2026: `<b>` lồng `<b>` làm Telegram từ chối CẢ tin
nhắn (HTTP 400 `can't parse entities`) — không phải bỏ qua thẻ. Checker này câm nghĩa là mốc
21:00 vẫn chạy, `send_all` vẫn gọi, và tin nhắc không bao giờ tới.

Chạy:
    python3 /Users/Huy/Claude/App/Ren66/.github/scripts/test-cong-html.py
    python3 /Users/Huy/Claude/App/Ren66/.github/scripts/test-cong-html.py --tu-kiem
"""
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unicodedata

HERE = pathlib.Path(__file__).resolve().parent
# Seam để tự kiểm: trỏ sang một bản check_html.py khác (xem --tu-kiem).
CHECKER = pathlib.Path(os.environ.get("REN_CHECK_HTML") or (HERE / "check_html.py"))
SEND = HERE / "send_telegram.py"


def khoi(*msgs, nut=None, khai=None):
    """Dựng đầu vào đúng định dạng DRY_RUN của send_telegram.py.

    khai=N: cố ý khai N message nhưng chỉ đưa ít hơn — giả lập ống dẫn bị CỤT.
    """
    n = len(msgs) if khai is None else khai
    ra = f"=== DRY_RUN — {n} message ===\n"
    for i, m in enumerate(msgs, 1):
        ra += f"\n----- message {i}/{n} ({len(m)} ký tự) -----\n{m}\n"
    if nut is not None:
        ra += f"\n----- nút -----\n{nut}\n"
    return ra


def chay(dau_vao, checker=None):
    r = subprocess.run([sys.executable, str(checker or CHECKER)],
                       input=dau_vao, capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def chan(out, ma, dau_hieu):
    """PHẢI CHẶN = vừa để mã thoát 1, vừa nêu ĐÚNG lý do (không nhận đỏ vì lý do khác)."""
    return ma == 1 and dau_hieu in out


# ═════════════════════════════ các ca thử ═════════════════════════════
CA = []


def ca(ten):
    def deco(f):
        CA.append((ten, f))
        return f
    return deco


@ca('1. <b> LỒNG trong <b> (bẫy thật 27/07, Telegram trả 400) → PHẢI CHẶN')
def _():
    ma, out = chay(khoi("<b>Rèn · <b>Ngày 12</b></b>\nChuỗi 3 ngày"))
    return chan(out, ma, "LỒNG"), out


@ca('2. Thẻ chưa đóng → PHẢI CHẶN')
def _():
    ma, out = chay(khoi("<b>Rèn · Ngày 12\nChuỗi 3 ngày"))
    return chan(out, ma, "chưa đóng"), out


@ca('3. Đóng SAI THỨ TỰ (<b><i>x</b></i>) → PHẢI CHẶN')
def _():
    ma, out = chay(khoi("<b>Rèn <i>hôm nay</b></i>"))
    return chan(out, ma, "đóng sai chỗ"), out


@ca('4. Thẻ Telegram KHÔNG nhận (<div>) → PHẢI CHẶN')
def _():
    ma, out = chay(khoi("<div>Rèn</div>"))
    return chan(out, ma, "thẻ lạ"), out


@ca('5. Thẻ tự đóng <br/> (hay gõ nhầm nhất) → PHẢI CHẶN')
def _():
    ma, out = chay(khoi("Rèn<br/>Chuỗi 3 ngày"))
    return chan(out, ma, "thẻ lạ"), out


@ca('6. Đóng thẻ chưa từng mở (</b> đơn lẻ) → PHẢI CHẶN')
def _():
    ma, out = chay(khoi("Rèn hôm nay</b>"))
    return chan(out, ma, "đóng sai chỗ"), out


@ca("7. Dấu '&' trần chưa escape → PHẢI CHẶN")
def _():
    ma, out = chay(khoi("<b>Rèn</b>\nChạy bộ & đọc sách"))
    return chan(out, ma, "& trần"), out


@ca("8. Ký tự '<' trần chưa escape → PHẢI CHẶN")
def _():
    ma, out = chay(khoi("<b>Rèn</b>\nHôm nay làm 2 < 3 việc"))
    return chan(out, ma, "chưa escape"), out


@ca("9. Ký tự '>' trần chưa escape → PHẢI CHẶN")
def _():
    ma, out = chay(khoi("<b>Rèn</b>\nHôm nay làm 3 > 2 việc"))
    return chan(out, ma, "chưa escape"), out


@ca('10. HAI message cùng hỏng → PHẢI CHẶN và báo CẢ HAI (chống dừng ở cái đầu)')
def _():
    # all(<generator>) dừng ngay message hỏng đầu tiên: sửa xong cái đầu, chạy lại mới lòi
    # cái sau — mà lần đầu trông như chỉ có một lỗi.
    ma, out = chay(khoi("<b>Một<b>x</b></b>", "<b>Hai</b> & ba"))
    return ma == 1 and "#1" in out and "#2" in out, out


@ca('11. Đầu vào KHÔNG có message nào (đổi định dạng / lệnh trước chết) → PHẢI CHẶN')
def _():
    # Im lặng ở đây là câm hoàn toàn: không soi gì cả mà vẫn xanh.
    ma, out = chay("=== DRY_RUN — 1 message ===\n<b>Rèn<b>lồng</b></b>\n")
    return chan(out, ma, "không tìm thấy message"), out


@ca('12. Đầu vào CỤT (khai 03 message, chỉ đọc được 01) → PHẢI CHẶN')
def _():
    ma, out = chay(khoi("<b>Rèn</b>", khai=3))
    return chan(out, ma, "CỤT"), out


@ca('13. Tin THẬT do send_telegram.py sinh (DRY_RUN) → phải QUA (chống báo oan)')
def _():
    # Ca đối chứng quan trọng nhất: đọc đầu ra THẬT thay vì bịa định dạng. Đúng chuỗi lệnh
    # ghi trong CLAUDE.md của repo (quy tắc 5).
    d = pathlib.Path(tempfile.mkdtemp(prefix="renhtml-"))
    try:
        f = d / "state.json"
        f.write_text(json.dumps({
            "start": "2026-07-01", "cycle": 1,
            "habits": [{"id": "h1", "name": "Chạy bộ & hít đất", "mins": 20},
                       {"id": "h2", "name": "Đọc sách <30 phút>"}],
            "days": {"2026-07-02": {"t": ["h1", "h2"]}}}, ensure_ascii=False),
            encoding="utf-8")
        r = subprocess.run([sys.executable, str(SEND)], capture_output=True, text=True,
                           env=dict(os.environ, DRY_RUN="1", REN_STATE_FILE=str(f)))
        if r.returncode != 0:
            return False, f"send_telegram.py lỗi: {r.stderr[:300]}"
        ma, out = chay(r.stdout)
    finally:
        shutil.rmtree(d, ignore_errors=True)
    # Tên việc cố ý chứa '&' và '<>' — `esc()` bên send_telegram phải escape chúng.
    return ma == 0 and "✗" not in out, out


@ca("14. Nhãn nút chứa '&' → phải QUA (khối '----- nút -----' không phải HTML)")
def _():
    nut = json.dumps({"inline_keyboard": [[{"text": "✅ Xong hết 2 việc & ngủ",
                                            "callback_data": "ren:xong:2026-07-29"}]]},
                     ensure_ascii=False)
    ma, out = chay(khoi("<b>Rèn</b>\nChuỗi 3 ngày", nut=nut))
    return ma == 0, out


@ca("15. Cùng ca 14 nhưng đầu vào dạng NFD (ĐỐI CHỨNG chuẩn hóa) → phải QUA")
def _():
    # Mốc cắt "----- nút -----" có dấu tiếng Việt. Đầu vào NFD (copy qua Finder/file macOS)
    # làm mốc trượt, khối JSON bị soi như HTML và '&' trong nhãn nút bị báo oan.
    nut = json.dumps({"inline_keyboard": [[{"text": "✅ Xong hết 2 việc & ngủ",
                                            "callback_data": "ren:xong:2026-07-29"}]]},
                     ensure_ascii=False)
    ma, out = chay(unicodedata.normalize("NFD", khoi("<b>Rèn</b>\nChuỗi 3 ngày", nut=nut)))
    return ma == 0, out


@ca('16. Escape đúng (&amp; &lt; &gt;) + thẻ lồng khác loại → phải QUA')
def _():
    ma, out = chay(khoi('<b>Rèn · <i>Ngày 12</i></b>\nChạy bộ &amp; đọc &lt;30 phút&gt;\n'
                        '<a href="https://x.dev/ren">Mở Rèn</a> <code>ren:xong</code>'))
    return ma == 0 and "✓" in out, out


# ═══════════════════════════ tự kiểm: bản hỏng ═══════════════════════════
# ⚠ Khai ĐÚNG ca nào phải đỏ, đừng khai thừa: ca 11 và 12 thoát bằng `sys.exit(1)` RIÊNG nên
# bản hỏng "nuốt mã thoát cuối" không đụng tới chúng — khai vào là tự báo động oan.
BAN_HONG = [
    ("tắt kiểm thẻ lạ (Telegram không nhận)",
     ('        if name not in OK:', '        if False:'),
     [4, 5]),
    ("tắt kiểm thẻ LỒNG cùng loại (đúng bẫy 27/07)",
     ('            if name in stack:', '            if False:'),
     [1]),
    ("tắt kiểm thẻ chưa đóng",
     ('    if stack:', '    if False:'),
     [2]),
    ("tắt kiểm đóng sai thứ tự",
     ('            if not stack or stack[-1] != name:', '            if not stack:'),
     [3]),
    ("tắt kiểm '<' '>' trần chưa escape",
     ('    for ch, ent in (("<", "&lt;"), (">", "&gt;")):', '    for ch, ent in ():'),
     [8, 9]),
    ("tắt kiểm '&' trần chưa escape",
     ('    for m in re.finditer(r"&(?!amp;|lt;|gt;|quot;|#\\d+;)", tran):', '    for m in ():'),
     [7]),
    ("tắt chốt 'không tìm thấy message nào' (đầu vào lạ → soi 0 khối mà vẫn xanh)",
     ('    if not parts:', '    if False:'),
     [11]),
    ("tắt chốt đầu vào CỤT",
     ('    if khai and int(khai.group(1)) != len(parts):', '    if False:'),
     [12]),
    ("quay lại all(<generator>) — dừng ở message hỏng đầu tiên",
     ('    ket = [check(p.strip(), f"{lab} #{i}") for i, p in enumerate(parts, 1)]',
      '    ket = (check(p.strip(), f"{lab} #{i}") for i, p in enumerate(parts, 1))'),
     [10]),
    ("bỏ cắt khối '----- nút -----' (JSON bàn phím bị soi như HTML)",
     ('    text = re.split(r"^----- nút -----$", text, flags=re.M)[0]', '    text = text'),
     [14, 15]),
    ("bỏ chuẩn hóa NFC đầu vào",
     ('    text = unicodedata.normalize("NFC", sys.stdin.read())', '    text = sys.stdin.read()'),
     [15]),
    ("nuốt MÃ THOÁT cuối (vẫn in ✗ nhưng trả 0 → workflow xanh, tin không tới)",
     ('    sys.exit(0 if all(ket) else 1)', '    sys.exit(0)'),
     [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]),
]


def tu_kiem() -> int:
    goc = (HERE / "check_html.py").read_text(encoding="utf-8")
    print("TỰ KIỂM — dựng bản check_html.py đã gỡ dòng bảo vệ, ca đã khai PHẢI ĐỎ")
    print("═" * 80)
    hong = 0
    for nhan, (tim, thay), phai_do in BAN_HONG:
        if goc.count(tim) != 1:
            print(f"  ✗ {nhan}\n        │ KHÔNG áp được phép thay: {goc.count(tim)} chỗ khớp "
                  f"(cần đúng 1). Mã nguồn đã đổi → sửa lại test.")
            hong += 1
            continue
        # Bản hỏng để TRONG thư mục thật rồi xoá ở finally (repo này public — đừng để sót).
        f = HERE / "_thu-hong-check_html.py"
        try:
            f.write_text(goc.replace(tim, thay), encoding="utf-8")
            r = subprocess.run([sys.executable, str(pathlib.Path(__file__).resolve())],
                               capture_output=True, text=True,
                               env=dict(os.environ, REN_CHECK_HTML=str(f)))
        finally:
            f.unlink(missing_ok=True)
        do = {int(dong[4:].split(".")[0])
              for dong in r.stdout.splitlines() if dong.startswith("  ✗ ")}
        thieu = sorted(set(phai_do) - do)
        thua = sorted(do - set(phai_do))
        ok = not thieu
        print(f"  {'✓' if ok else '✗'} {nhan}")
        print(f"        │ ca đỏ: {sorted(do) or 'KHÔNG CÓ CA NÀO ĐỎ'} · cần đỏ: {sorted(phai_do)}"
              + (f" · đỏ thêm ngoài dự kiến: {thua}" if thua else ""))
        if not ok:
            hong += 1
            print(f"        │ ⚠ ca {thieu} VẪN XANH trên bản hỏng → test không bắt được lỗi này.")
    print("═" * 80)
    if hong:
        print(f"✗ {hong}/{len(BAN_HONG)} phép thử tự kiểm THẤT BẠI — bộ test chưa chứng minh "
              f"được là nó bắt được lỗi.")
        return 1
    print(f"✓ {len(BAN_HONG)}/{len(BAN_HONG)} bản hỏng đều bị bắt — bộ test này có giá trị.")
    return 0


def main() -> int:
    if "--tu-kiem" in sys.argv:
        return tu_kiem()
    print(f"TEST CHECKER HTML TELEGRAM — mọi ca 'PHẢI CHẶN' phải thật sự chặn\n"
          f"(bản đang thử: {CHECKER})")
    print("─" * 80)
    hong = 0
    for ten, f in CA:
        try:
            ok, out = f()
        except Exception as e:                                   # noqa: BLE001
            ok, out = False, f"LỖI CHẠY: {e.__class__.__name__}: {e}"
        print(f"  {'✓' if ok else '✗'} {ten}")
        if not ok:
            hong += 1
            for dong in str(out or "(không có đầu ra)").strip().split("\n")[:8]:
                print(f"        │ {dong}")
    print("─" * 80)
    if hong:
        print(f"✗ {hong}/{len(CA)} ca HỎNG — checker HTML không còn bắt đúng. Sửa ngay: nó câm "
              f"nghĩa là tin nhắc 21:00 bị Telegram từ chối mà workflow vẫn xanh.")
        return 1
    print(f"✓ {len(CA)}/{len(CA)} ca đạt — checker HTML còn sống.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
