#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test các chốt của VIỆC ĐÃ HẸN — có ca PHẢI CHẶN, và tự chứng minh test bắt được lỗi.

    python3 .github/scripts/test-cong-vow.py
    python3 .github/scripts/test-cong-vow.py --tu-kiem

Áp luật mục 17 của CLAUDE.md toàn cục: **cổng kiểm nào cũng phải có ít nhất MỘT ca PHẢI CHẶN.**

VÌ SAO CẦN, nói cho cụ thể: gần như mọi chốt trong tính năng này thuộc loại **"hỏng thì im lặng
cho qua"** — chạy thử với một cam kết bình thường thì bản đúng và bản hỏng cho ra kết quả GIỐNG
HỆT nhau.
  • Gỡ chốt "đã xong thì thôi nhắc" → chỉ lộ ra vào ngày Huy đã bấm xong mà tin vẫn nhắc lại.
  • Gỡ chốt giãn cách 20 giờ → chỉ lộ ra sau 30 phút, khi tin thứ hai tới. Trong một lần chạy
    tay thì hai bản không phân biệt được.
  • Gỡ escape HTML → chỉ lộ ra vào đúng lần Huy gõ cam kết có dấu `<` hoặc `&`, và lúc đó
    Telegram từ chối CẢ tin nhắn (bẫy số 1, CLAUDE.md) — nghĩa là im lặng hoàn toàn.
  • Gỡ chốt "gửi hỏng thì đừng đếm là đã nhắc" → cam kết đó trôi mất, không ai biết.
Chạy trăm lần "thấy nó không kêu" không chứng minh được gì. Chỉ ca PHẢI CHẶN mới phân biệt.

CHẠY HOÀN TOÀN OFFLINE: `REN_VOWS_FILE` thay Supabase bằng một file JSON, `api()` bị thay bằng
bản ghi nhận nên không gọi Telegram. Không cần token, không cần mạng, không đụng dữ liệu thật.

⚠️ Phạm vi test này là phần PYTHON. Các chốt phía SQL (regex mã đồng bộ, trần 300 ký tự,
`device` trong mệnh đề `where` của `ren_vow_set`) nằm ở Postgres — kiểm bằng đoạn lệnh cuối
docs/vows-setup.sql, bản giả file KHÔNG chứng minh hộ được. Đừng đọc "12/12 xanh" thành "đã
kiểm cả phía máy chủ".
"""
import argparse
import contextlib
import datetime
import importlib.util
import io
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

SCRIPTS = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))


# ── nạp module (cho phép thay bằng bản hỏng, phục vụ --tu-kiem) ───────────────────────────
def nap(thay=None):
    """Nạp lại send_telegram / vow / vow_bot / tick_bot / vow_add từ đầu.

    `thay` = {"vow": <path>, ...} để tráo một file bằng bản hỏng. Nạp bằng importlib chứ không
    chạy subprocess vì phần lớn ca cần THAY `api()` ngay trong tiến trình — bài học của
    test-cong-secret.py: test bằng token giả rồi gọi Telegram thật là đo nhầm chốt.
    """
    thay = thay or {}
    for m in ("vow", "vow_bot", "tick_bot", "vow_add", "send_telegram"):
        sys.modules.pop(m, None)
    import send_telegram                                        # noqa: F401
    ra = {}
    for ten in ("vow", "vow_bot", "tick_bot", "vow_add"):
        p = pathlib.Path(thay.get(ten, SCRIPTS / f"{ten}.py"))
        spec = importlib.util.spec_from_file_location(ten, p)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[ten] = mod                                  # để module sau `from vow import`
        spec.loader.exec_module(mod)                            # lấy đúng bản vừa nạp
        ra[ten] = mod
    return ra


class GhiNhan:
    """Thay `api()`: ghi lại lời gọi thay vì gọi Telegram. `hong` = ép sendMessage thất bại."""

    def __init__(self, hong=False):
        self.goi, self.hong = [], hong

    def __call__(self, token, method, payload):
        self.goi.append((method, payload))
        if self.hong and method == "sendMessage":
            return {"ok": False, "description": "test ép hỏng"}
        return {"ok": True, "result": {"message_id": 1}}

    def da_gui(self):
        return [p for m, p in self.goi if m == "sendMessage"]


def vows_file(rows):
    f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
    json.dump(rows, f, ensure_ascii=False)
    f.close()
    return f.name


def gio(delta_h, **kw):
    import zoneinfo
    vn = zoneinfo.ZoneInfo("Asia/Ho_Chi_Minh")
    return (datetime.datetime.now(vn) + datetime.timedelta(hours=delta_h, **kw)).isoformat()


DEV = "11111111-2222-3333-4444-555555555555"


def dong(**kw):
    r = {"id": 1, "device": DEV, "viec": "nhắn mẹ hỏi giờ rảnh", "han": gio(-1),
         "xong_at": None, "bo_at": None, "nhac_lan": 0, "nhac_cuoi": None}
    r.update(kw)
    return r


# ── các ca ───────────────────────────────────────────────────────────────────────────────
# (mã, "PHẢI CHẶN"|"chống oan", mô tả, hàm) — hàm trả (đạt: bool, ghi chú: str)

def ca_da_xong(M):
    """Cam kết đã bấm xong thì TUYỆT ĐỐI không nhắc lại. Nhắc lại việc đã làm là mất tin tưởng
    ngay lần đầu, mà mất rồi thì Huy tắt thông báo — tắt là mất luôn cả tin nhắc 21:00."""
    now = datetime.datetime.now(M["vow"].VN)
    ra = M["vow"].can_nhac([dong(xong_at=gio(-0.5))], now)
    return not ra, f"chọn nhắc {len(ra)} cái"


def ca_da_bo(M):
    """Đã khai 'chưa làm' cũng phải thôi nhắc — nút đó là đường thoát trung thực, không phải
    nút hoãn. Vẫn nhắc thì nó thành nút vô nghĩa và Huy quay lại lối lờ đi."""
    now = datetime.datetime.now(M["vow"].VN)
    ra = M["vow"].can_nhac([dong(bo_at=gio(-0.5))], now)
    return not ra, f"chọn nhắc {len(ra)} cái"


def ca_chua_toi_han(M):
    """Chưa tới hạn thì không được nhắc. Nhắc sớm là sai hẹn, mà cam kết nhắc sai hẹn thì
    không còn là cam kết."""
    now = datetime.datetime.now(M["vow"].VN)
    ra = M["vow"].can_nhac([dong(han=gio(+5))], now)
    return not ra, f"chọn nhắc {len(ra)} cái"


def ca_giai_cach_20h(M):
    """Đã nhắc cách đây 2 giờ thì chưa được nhắc lại. Lịch chạy 30 phút/lần: không có chốt này
    là 48 tin một ngày cho cùng một việc."""
    now = datetime.datetime.now(M["vow"].VN)
    ra = M["vow"].can_nhac([dong(nhac_lan=1, nhac_cuoi=gio(-2))], now)
    return not ra, f"chọn nhắc {len(ra)} cái"


def ca_tran_so_lan(M):
    """Nhắc đủ MAX_NHAC lần thì dừng hẳn, kể cả đã quá 20 giờ. Nhắc mãi thì Huy tắt thông báo."""
    now = datetime.datetime.now(M["vow"].VN)
    ra = M["vow"].can_nhac(
        [dong(nhac_lan=M["vow"].MAX_NHAC, nhac_cuoi=gio(-48))], now)
    return not ra, f"chọn nhắc {len(ra)} cái"


def ca_gui_hong_khong_dem(M):
    """Gửi HỎNG thì KHÔNG được ghi 'đã nhắc'. Ghi rồi mà tin không tới là cam kết đó im lặng
    trôi mất — đúng kiểu hỏng mà tính năng này sinh ra để chống."""
    f = vows_file([dong()])
    os.environ.update({"REN_VOWS_FILE": f, "TELEGRAM_BOT_TOKEN": "x",
                       "TELEGRAM_CHAT_ID": "9", "REN_DEVICE_ID": DEV})
    os.environ.pop("DRY_RUN", None)
    M["vow_bot"].api = GhiNhan(hong=True)
    rc = M["vow_bot"].main()
    sau = json.loads(pathlib.Path(f).read_text(encoding="utf-8"))[0]
    os.unlink(f)
    return (sau["nhac_lan"] == 0 and rc == 1,
            f"nhac_lan={sau['nhac_lan']} rc={rc}")


def ca_escape_html(M):
    """`viec` do Huy gõ, có `<` hay `&` trần là Telegram từ chối CẢ tin nhắn (bẫy số 1). Soi
    bằng chính check_html.py, trên đầu ra THẬT do `vow_bot.main()` sinh ra — không bịa định dạng.

    ⚠️ Gọi main() TRONG TIẾN TRÌNH chứ không `subprocess` file trên đĩa: subprocess luôn nạp
    `vow.py` thật, nên `--tu-kiem` tráo bản hỏng vào cũng không đụng tới nó và ca này xanh vĩnh
    viễn — tức là một ca test vô dụng đúng nghĩa. Đã vấp thật ngày 29/07/2026, chính `--tu-kiem`
    bắt được. `check_html.py` thì vẫn chạy bằng subprocess và luôn là bản thật: nó là cái THƯỚC,
    không phải thứ đang được đo.
    """
    f = vows_file([dong(viec="đọc <chương 3> & ghi 5 dòng > hôm qua")])
    os.environ.update({"REN_VOWS_FILE": f, "DRY_RUN": "1", "REN_DEVICE_ID": DEV})
    os.environ.pop("TELEGRAM_BOT_TOKEN", None)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        M["vow_bot"].main()
    p = subprocess.run([sys.executable, str(SCRIPTS / "check_html.py"), "vow"],
                       input=buf.getvalue(), capture_output=True, text=True)
    os.unlink(f)
    return p.returncode == 0, p.stdout.strip().replace("\n", " | ")[:160]


def ca_cau_hinh_gay(M):
    """Có token mà thiếu chat → PHẢI ĐỎ. Thoát êm ở đây là lịch chạy xanh mỗi 30 phút trong khi
    không một lời nhắc nào tới — đúng con lỗi đã bắt được thật 27/07/2026 ở send_telegram.py."""
    for k in ("REN_VOWS_FILE", "DRY_RUN", "TELEGRAM_CHAT_ID", "REN_DEVICE_ID"):
        os.environ.pop(k, None)
    os.environ["TELEGRAM_BOT_TOKEN"] = "x"
    rc = M["vow_bot"].main()
    return rc == 1, f"rc={rc}"


def ca_chat_la(M):
    """Callback từ chat LẠ phải bị bỏ. Bot công khai, ai cũng nhắn được — không lọc thì người
    lạ ghi được vào sổ cam kết của Huy."""
    up = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
    json.dump([{"callback_query": {"id": "1", "data": "ren:vow:1:xong",
                                   "message": {"message_id": 5, "chat": {"id": 777}}}}], up)
    up.close()
    os.environ.update({"REN_FAKE_UPDATES": up.name, "TELEGRAM_CHAT_ID": "9"})
    ra = M["tick_bot"].doc_nut("token-gia")
    os.unlink(up.name)
    os.environ.pop("REN_FAKE_UPDATES", None)
    return not ra, f"nhận {len(ra)} callback từ chat lạ"


def ca_trang_thai_la(M):
    """`ren:vow:1:xoahet` phải bị bỏ, KHÔNG được gọi RPC. Dữ liệu callback đến từ ngoài — coi
    nó là hợp lệ vì 'nút do mình sinh ra' là tin vào thứ mình không kiểm soát."""
    def no(*a, **k):
        raise AssertionError("đã gọi RPC với trạng thái lạ")
    M["tick_bot"].vow_rpc = no
    rc = M["tick_bot"].xu_ly_vow("t", DEV, "1", "9", 5, ["ren", "vow", "1", "xoahet"], False)
    return rc == 0, f"rc={rc}"


def ca_han_meo(M):
    """`--han` không hiểu được thì phải BÁO LỖI, tuyệt đối không lẳng lặng chọn một mốc. Đoán
    mò ở đây là nhắc sai ngày mà không ai biết là đã đoán."""
    try:
        d = M["vow_add"].doc_han("thứ ba tuần sau lúc nào đó")
    except ValueError:
        return True, "đã báo lỗi"
    return False, f"lại tự đoán ra {d}"


def ca_id_khong_phai_cua_minh(M):
    """Bấm id không có trong sổ của mã này → RPC ném lỗi, và script phải BÁO chứ không im.
    (Bản giả giữ đúng ca lỗi này của SQL — `device` nằm trong mệnh đề `where` của ren_vow_set.)"""
    f = vows_file([dong(id=1)])
    os.environ["REN_VOWS_FILE"] = f
    try:
        M["vow"].rpc("ren_vow_set", {"p_device": DEV, "p_id": 99, "p_trang_thai": "xong"})
    except RuntimeError:
        os.unlink(f)
        return True, "đã ném lỗi"
    os.unlink(f)
    return False, "im lặng cho qua"


def ca_supabase_gay_thi_do(M):
    """Supabase lỗi THẬT (500, mất mạng, mã sai định dạng) → PHẢI ĐỎ. Chỉ ca 'chưa dựng bảng'
    mới được thoát êm. Gộp cả nắm là lại đúng con lỗi 27/07/2026: lịch chạy xanh, không tin nào
    tới, không ai biết."""
    for k in ("REN_VOWS_FILE", "DRY_RUN"):
        os.environ.pop(k, None)
    os.environ.update({"TELEGRAM_BOT_TOKEN": "x", "TELEGRAM_CHAT_ID": "9",
                       "REN_DEVICE_ID": DEV})

    def no(*a, **k):
        raise RuntimeError("Supabase 500: máy chủ đang hỏng")
    M["vow_bot"].rpc = no
    rc = M["vow_bot"].main()
    return rc == 1, f"rc={rc}"


# ── chống báo oan ───────────────────────────────────────────────────────────────────────
def ca_chua_dung_bang(M):
    """Chưa chạy vows-setup.sql → thoát ÊM. Không có chốt này thì từ lúc đẩy mã lên tới lúc Huy
    dán SQL, lịch đỏ 48 lần mỗi ngày — cổng kêu oan liên tục thì lần kêu thật cũng bị lờ."""
    for k in ("REN_VOWS_FILE", "DRY_RUN"):
        os.environ.pop(k, None)
    os.environ.update({"TELEGRAM_BOT_TOKEN": "x", "TELEGRAM_CHAT_ID": "9",
                       "REN_DEVICE_ID": DEV})

    def no(*a, **k):
        raise RuntimeError("Supabase 404: Could not find the function "
                           "public.ren_vow_list(p_device) (PGRST202)")
    M["vow_bot"].rpc = no
    rc = M["vow_bot"].main()
    return rc == 0, f"rc={rc}"



def ca_toi_han_thi_nhac(M):
    now = datetime.datetime.now(M["vow"].VN)
    ra = M["vow"].can_nhac([dong()], now)
    return len(ra) == 1, f"chọn {len(ra)}"


def ca_nhac_lai_sau_21h(M):
    now = datetime.datetime.now(M["vow"].VN)
    ra = M["vow"].can_nhac([dong(nhac_lan=1, nhac_cuoi=gio(-21))], now)
    return len(ra) == 1, f"chọn {len(ra)}"


def ca_chua_cau_hinh(M):
    for k in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "REN_DEVICE_ID",
              "REN_VOWS_FILE", "DRY_RUN"):
        os.environ.pop(k, None)
    rc = M["vow_bot"].main()
    return rc == 0, f"rc={rc}"


def ca_doc_han_dung(M):
    import zoneinfo
    vn = zoneinfo.ZoneInfo("Asia/Ho_Chi_Minh")
    now = datetime.datetime(2026, 7, 29, 15, 0, tzinfo=vn)
    d = M["vow_add"].doc_han
    kt = [(d("mai 21:00", now), (2026, 7, 30, 21, 0)),
          (d("tối nay 22h", now), (2026, 7, 29, 22, 0)),
          (d("30/07 21:00", now), (2026, 7, 30, 21, 0)),
          (d("30/07", now), (2026, 7, 30, 21, 0)),
          (d("2026-08-02 08:30", now), (2026, 8, 2, 8, 30))]
    sai = [f"{a}≠{b}" for a, b in kt
           if (a.year, a.month, a.day, a.hour, a.minute) != b]
    return not sai, "; ".join(sai)


def ca_dem_dung(M):
    rows = [dong(id=1, xong_at=gio(-30)), dong(id=2, bo_at=gio(-30)),
            dong(id=3, xong_at=gio(-5)), dong(id=4)]
    giu, tong = M["vow"].dem(rows)
    return (giu, tong) == (2, 3), f"giữ {giu}/{tong}, mong 2/3"


CA = [
    ("da-xong",       1, "cam kết đã xong thì thôi nhắc", ca_da_xong),
    ("da-bo",         1, "cam kết đã khai bỏ thì thôi nhắc", ca_da_bo),
    ("chua-toi-han",  1, "chưa tới hạn thì không nhắc", ca_chua_toi_han),
    ("giai-cach",     1, "chưa đủ 20 giờ thì không nhắc lại", ca_giai_cach_20h),
    ("tran-so-lan",   1, "quá MAX_NHAC lần thì dừng nhắc", ca_tran_so_lan),
    ("gui-hong",      1, "gửi hỏng thì KHÔNG đếm là đã nhắc", ca_gui_hong_khong_dem),
    ("escape-html",   1, "cam kết có < & > phải escape (soi bằng check_html.py)", ca_escape_html),
    ("cau-hinh-gay",  1, "có token mà thiếu chat → exit 1", ca_cau_hinh_gay),
    ("chat-la",       1, "callback từ chat lạ bị bỏ", ca_chat_la),
    ("trang-thai-la", 1, "callback trạng thái lạ không gọi RPC", ca_trang_thai_la),
    ("han-meo",       1, "hạn không hiểu được thì báo lỗi, không đoán", ca_han_meo),
    ("id-nguoi-khac", 1, "id không thuộc mã này → ném lỗi", ca_id_khong_phai_cua_minh),
    ("supabase-gay",  1, "Supabase lỗi thật → exit 1", ca_supabase_gay_thi_do),
    ("chua-dung-bang", 0, "chưa chạy vows-setup.sql → exit 0 êm", ca_chua_dung_bang),
    ("toi-han",       0, "tới hạn, chưa nhắc → có nhắc", ca_toi_han_thi_nhac),
    ("nhac-lai",      0, "đã quá 21 giờ → nhắc lại", ca_nhac_lai_sau_21h),
    ("chua-cau-hinh", 0, "không secret nào → exit 0 êm", ca_chua_cau_hinh),
    ("doc-han",       0, "hiểu đúng các dạng hạn Huy hay gõ", ca_doc_han_dung),
    ("dem",           0, "đếm giữ/chốt đúng, cái treo không vào mẫu số", ca_dem_dung),
]


def chay(thay=None, im=False):
    """Chạy hết bộ ca. Trả {mã: đạt}."""
    ket = {}
    for ma, phai_chan, mo_ta, fn in CA:
        M = nap(thay)                       # nạp lại mỗi ca: ca trước có thay api() / môi trường
        moi_truong_cu = dict(os.environ)
        try:
            dat, ghi = fn(M)
        except Exception as e:              # noqa: BLE001
            dat, ghi = False, f"nổ: {type(e).__name__}: {e}"
        finally:
            os.environ.clear()
            os.environ.update(moi_truong_cu)
        ket[ma] = dat
        if not im:
            nhan = "PHẢI CHẶN" if phai_chan else "chống oan"
            print(f"{'✓' if dat else '✗'} [{nhan}] {ma} — {mo_ta}"
                  + ("" if dat else f"   → {ghi}"))
    return ket


# ── tự kiểm: dựng bản HỎNG, ca đã khai phải ĐỎ ───────────────────────────────────────────
# ⚠️ Khai ĐÚNG ca nào phải đỏ, đừng khai thừa — đã vấp một lần bên test-cong-secret.py: khai
# thừa là tự báo động oan, rồi mất niềm tin vào chính bộ test.
BAN_HONG = [
    ("vow", "bỏ chốt đã-xong/đã-bỏ",
     r'        if r\.get\("xong_at"\) or r\.get\("bo_at"\):\n            continue\n', "",
     ["da-xong", "da-bo"]),
    ("vow", "bỏ chốt chưa-tới-hạn",
     r"        if han is None or han > now:", "        if han is None:",
     ["chua-toi-han"]),
    ("vow", "bỏ chốt giãn cách 20 giờ",
     r"            if cuoi is not None and \(now - cuoi\)\.total_seconds\(\) < NHAC_CACH_GIO \* 3600:\n                continue\n",
     "", ["giai-cach"]),
    ("vow", "bỏ trần số lần nhắc",
     r"        if lan >= MAX_NHAC:\n            continue\n", "", ["tran-so-lan"]),
    ("vow", "bỏ escape HTML cho `viec`",
     r'f"“\{esc\(r\.get\(.viec.\)\)\}”"', 'f"“{r.get(\'viec\')}”"', ["escape-html"]),
    ("vow_bot", "gửi hỏng vẫn đếm là đã nhắc",
     r"            rc = 1\n            continue                                   # KHÔNG đếm",
     "            rc = 1\n            pass                                       # KHÔNG đếm",
     ["gui-hong"]),
    ("vow_bot", "cấu hình gãy thoát êm",
     r"        return 1\n\n    now = datetime", "        return 0\n\n    now = datetime",
     ["cau-hinh-gay"]),
    ("vow_bot", "lỗi Supabase nào cũng thoát êm",
     r'        if "PGRST202" in str\(e\) or "Could not find the function" in str\(e\):',
     "        if True:", ["supabase-gay"]),
    ("tick_bot", "bỏ lọc trạng thái lạ",
     r'    if trang_thai not in \("xong", "bo", "mo"\):\n        print\(f"callback vow trạng thái lạ, bỏ qua: \{phan\}", file=sys\.stderr\)\n        return 0\n',
     "", ["trang-thai-la"]),
]


def tu_kiem():
    """Dựng từng bản hỏng RỒI CHẠY LẠI cả bộ. Ca đã khai phải ĐỎ, ca khác phải giữ nguyên.

    Bản hỏng đặt ngay trong thư mục thật (`_hong_*.py`) chứ không ở /tmp: module ở đây import
    lẫn nhau bằng tên (`from vow import …`) và đọc file cạnh mình — để chỗ khác là test đo một
    thứ khác với thứ đang chạy thật.
    """
    goc = chay(im=True)
    if not all(goc.values()):
        print("✗ Bản THẬT chưa xanh hết — sửa xong hãy tự kiểm.", file=sys.stderr)
        return 1

    loi = []
    for ten, mo_ta, tim, thay_bang, phai_do in BAN_HONG:
        src = (SCRIPTS / f"{ten}.py").read_text(encoding="utf-8")
        moi, n = re.subn(tim, thay_bang, src, count=1)
        if n != 1:
            loi.append(f"{ten}: KHÔNG cắt được đoạn '{mo_ta}' — mã nguồn đã đổi, sửa lại "
                       f"BAN_HONG (test đang tự kiểm một thứ không còn tồn tại)")
            continue
        p = SCRIPTS / f"_hong_{ten}.py"
        p.write_text(moi, encoding="utf-8")
        try:
            ket = chay({ten: str(p)}, im=True)
        finally:
            p.unlink(missing_ok=True)
            shutil.rmtree(SCRIPTS / "__pycache__", ignore_errors=True)

        do = [k for k, v in ket.items() if not v]
        thieu = [k for k in phai_do if k not in do]
        thua = [k for k in do if k not in phai_do]
        dat = not thieu and not thua
        print(f"{'✓' if dat else '✗'} bản hỏng «{mo_ta}» → đỏ: {do or 'KHÔNG CÁI NÀO'}")
        if thieu:
            loi.append(f"«{mo_ta}»: ca {thieu} VẪN XANH trên bản hỏng — test đó vô dụng")
        if thua:
            loi.append(f"«{mo_ta}»: ca {thua} đỏ ngoài dự kiến — khai lại phai_do")

    if loi:
        print("\n".join("✗ " + x for x in loi), file=sys.stderr)
        return 1
    print(f"\n✅ {len(BAN_HONG)}/{len(BAN_HONG)} bản hỏng đều bị bắt.")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tu-kiem", action="store_true",
                    help="dựng bản code hỏng, chứng minh ca PHẢI CHẶN thật sự đỏ")
    a = ap.parse_args()
    if a.tu_kiem:
        sys.exit(tu_kiem())
    ket = chay()
    n = sum(1 for v in ket.values() if v)
    print(f"\n{n}/{len(ket)} ca đạt"
          + ("" if n == len(ket) else " — CÓ CA ĐỎ"))
    sys.exit(0 if n == len(ket) else 1)
