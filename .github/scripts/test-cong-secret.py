#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TEST HỒI QUY CHO CHỐT "CHƯA CẤU HÌNH ≠ CẤU HÌNH GÃY" (.github/scripts/send_telegram.py).

⚠ VÌ SAO CÓ FILE NÀY — luật đúc 29.7.2026 (CLAUDE.md toàn cục, mục 17) + bài học 27.7.2026:
"Thiếu secret → thoát êm exit 0" chỉ đúng khi repo CHƯA cấu hình lần nào. Đã cắm secret rồi mà
một mảnh biến mất (secret bị xoá, bot bị /revoke, gõ nhầm tên) thì thoát êm biến thành kiểu
hỏng tệ nhất: mốc 21:00 chạy XANH hằng ngày mà không một tin nhắc nào tới. Bắt được thật ngày
27/07/2026 — run 30250807802 success trong 10 giây, TELEGRAM_BOT_TOKEN chưa từng được đặt.

Đây đúng loại cổng "hỏng thì im lặng cho qua": không thể phát hiện bằng cách chạy thử ca đủ
secret (ca đó xanh dù chốt còn hay mất). Chỉ ca CẤU HÌNH GÃY → PHẢI ĐỎ mới phân biệt được.

Test chạy HOÀN TOÀN OFFLINE: `send_all` và `fetch_state` bị thay bằng bản ghi nhận, không gọi
Telegram, không gọi Supabase.

Chạy:
    python3 .github/scripts/test-cong-secret.py
    python3 .github/scripts/test-cong-secret.py --tu-kiem   # chứng minh test này BẮT ĐƯỢC lỗi
"""
import contextlib
import importlib.util
import io
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
# Seam để tự kiểm: trỏ sang một bản send_telegram.py khác (xem --tu-kiem).
MOD_PATH = pathlib.Path(os.environ.get("REN_SEND_MOD") or (HERE / "send_telegram.py"))

BIEN = ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "REN_DEVICE_ID", "REN_STATE_FILE", "DRY_RUN")


def _nap():
    spec = importlib.util.spec_from_file_location("ren_send_duoi_thu", MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def chay(**env):
    """Gọi main() với đúng bộ biến môi trường đã nêu. Trả (mã thoát, đã-gửi?, đầu ra).

    Nạp lại module mỗi ca để không lây trạng thái giữa các ca. `send_all` + `fetch_state`
    bị thay: test này đo QUYẾT ĐỊNH của chốt secret, không đo đường mạng.
    """
    M = _nap()
    da_gui = []
    M.send_all = lambda token, chats, msgs, markup=None: da_gui.append((token, chats)) or 0
    M.fetch_state = lambda device: (None, None)

    cu = {k: os.environ.get(k) for k in BIEN}
    for k in BIEN:
        os.environ.pop(k, None)
    for k, v in env.items():
        os.environ[k] = v
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            ma = M.main()
    finally:
        for k, v in cu.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    return ma, bool(da_gui), buf.getvalue()


DAY = dict(TELEGRAM_BOT_TOKEN="1234:GIA-LAP", TELEGRAM_CHAT_ID="111", REN_DEVICE_ID="abc")


# ═════════════════════════════ các ca thử ═════════════════════════════
CA = []


def ca(ten):
    def deco(f):
        CA.append((ten, f))
        return f
    return deco


@ca('1. Mất TOKEN nhưng còn chat + device → PHẢI ĐỎ (exit 1) và KHÔNG gửi')
def _():
    ma, gui, out = chay(TELEGRAM_CHAT_ID="111", REN_DEVICE_ID="abc")
    return ma == 1 and not gui and "CẤU HÌNH GÃY" in out, f"exit={ma} gửi={gui}\n{out}"


@ca('2. Mất CHAT_ID nhưng còn token + device → PHẢI ĐỎ (exit 1) và KHÔNG gửi')
def _():
    ma, gui, out = chay(TELEGRAM_BOT_TOKEN="1234:GIA-LAP", REN_DEVICE_ID="abc")
    return ma == 1 and not gui and "CẤU HÌNH GÃY" in out, f"exit={ma} gửi={gui}\n{out}"


@ca('3. Mất REN_DEVICE_ID nhưng còn token + chat → PHẢI ĐỎ, nhưng VẪN GỬI tin rút gọn')
def _():
    # Còn đường gửi thì phải gửi (chốt 2: thà nhắc thiếu số còn hơn không nhắc), rồi mới để đỏ.
    ma, gui, out = chay(TELEGRAM_BOT_TOKEN="1234:GIA-LAP", TELEGRAM_CHAT_ID="111")
    return ma == 1 and gui and "CẤU HÌNH GÃY" in out, f"exit={ma} gửi={gui}\n{out}"


@ca('4. Thông báo cấu hình gãy phải nêu ĐÚNG TÊN secret đang thiếu')
def _():
    # "Có gì đó sai" không sửa được. Phải chỉ mặt secret nào mất.
    ma, gui, out = chay(TELEGRAM_BOT_TOKEN="1234:GIA-LAP", TELEGRAM_CHAT_ID="111")
    return "REN_DEVICE_ID" in out and "TELEGRAM_BOT_TOKEN" not in out.split("THIẾU:")[-1], out


@ca('5. CHƯA cấu hình gì cả (không secret nào) → thoát ÊM exit 0, không gửi (chống báo oan)')
def _():
    ma, gui, out = chay()
    return ma == 0 and not gui and "chưa cấu hình" in out, f"exit={ma} gửi={gui}\n{out}"


@ca('6. Đủ cả 3 secret → exit 0 và CÓ gửi (chống báo oan)')
def _():
    ma, gui, out = chay(**DAY)
    return ma == 0 and gui, f"exit={ma} gửi={gui}\n{out}"


@ca('7. REN_STATE_FILE thay được REN_DEVICE_ID → không được coi là cấu hình gãy')
def _():
    d = pathlib.Path(tempfile.mkdtemp(prefix="ren-state-"))
    f = d / "state.json"
    f.write_text("{}", encoding="utf-8")
    ma, gui, out = chay(TELEGRAM_BOT_TOKEN="1234:GIA-LAP", TELEGRAM_CHAT_ID="111",
                        REN_STATE_FILE=str(f))
    shutil.rmtree(d, ignore_errors=True)
    return ma == 0 and gui, f"exit={ma} gửi={gui}\n{out}"


@ca('8. DRY_RUN → chỉ in, KHÔNG gửi, exit 0 kể cả khi thiếu secret')
def _():
    ma, gui, out = chay(DRY_RUN="1")
    return ma == 0 and not gui and "DRY_RUN" in out, f"exit={ma} gửi={gui}\n{out}"


# ═══════════════════════════ tự kiểm: bản hỏng ═══════════════════════════
BAN_HONG = [
    ("gộp lại thành 'thiếu secret nào cũng thoát êm' (đúng con bug 27/07/2026)",
     ('        if not (token or chats or device):', '        if True:'),
     [1, 2, 3, 4]),
    ("bỏ REN_DEVICE_ID khỏi danh sách secret bắt buộc",
     ('        + ([] if (device or state_file) else ["REN_DEVICE_ID"])', '        + []'),
     [3, 4]),
    # Chỉ ca 3 — ca 4 chỉ soi CHỮ trong thông báo, mà bản hỏng này vẫn in đúng chữ, chỉ nuốt
    # mã thoát. Khai [3, 4] là khai sai và sẽ báo động oan.
    ("gửi xong thì nuốt luôn cờ cấu hình gãy (job xanh dù thiếu device)",
     ('    return send_all(token, chats, msgs, kb) or (1 if thieu else 0)',
      '    return send_all(token, chats, msgs, kb)'),
     [3]),
    ("mất đường gửi mà vẫn chạy tiếp (gọi send_all với token/chat rỗng)",
     ('        if not token or not chats:', '        if False:'),
     [1, 2]),
]


def tu_kiem() -> int:
    goc = (HERE / "send_telegram.py").read_text(encoding="utf-8")
    print("TỰ KIỂM — dựng bản send_telegram.py đã gỡ dòng bảo vệ, các ca đã khai PHẢI ĐỎ")
    print("═" * 78)
    hong = 0
    for nhan, (tim, thay), ca_phai_do in BAN_HONG:
        if goc.count(tim) != 1:
            print(f"  ✗ {nhan}\n        │ KHÔNG áp được phép thay: {goc.count(tim)} chỗ khớp "
                  f"(cần đúng 1). Mã nguồn đã đổi → sửa lại test.")
            hong += 1
            continue
        d = pathlib.Path(tempfile.mkdtemp(prefix="ren-hong-"))
        f = d / "send_telegram.py"
        f.write_text(goc.replace(tim, thay), encoding="utf-8")
        env = dict(os.environ, REN_SEND_MOD=str(f))
        r = subprocess.run([sys.executable, str(pathlib.Path(__file__).resolve())],
                           capture_output=True, text=True, env=env)
        do = {int(dong[4:].split(".")[0])
              for dong in r.stdout.splitlines() if dong.startswith("  ✗ ")}
        thieu = set(ca_phai_do) - do
        thua = do - set(ca_phai_do)
        ok = not thieu
        print(f"  {'✓' if ok else '✗'} {nhan}")
        print(f"        │ ca đỏ: {sorted(do) or 'KHÔNG CÓ CA NÀO ĐỎ'} · cần đỏ: {ca_phai_do}"
              + (f" · đỏ thêm ngoài dự kiến: {sorted(thua)}" if thua else ""))
        if not ok:
            hong += 1
            print(f"        │ ⚠ ca {sorted(thieu)} VẪN XANH trên bản hỏng → test không bắt được lỗi này.")
        shutil.rmtree(d, ignore_errors=True)
    print("═" * 78)
    if hong:
        print(f"✗ {hong}/{len(BAN_HONG)} phép thử tự kiểm THẤT BẠI — bộ test chưa chứng minh được "
              f"là nó bắt được lỗi.")
        return 1
    print(f"✓ {len(BAN_HONG)}/{len(BAN_HONG)} bản hỏng đều bị bắt — bộ test này có giá trị.")
    return 0


def main() -> int:
    if "--tu-kiem" in sys.argv:
        return tu_kiem()
    print("TEST CHỐT SECRET RÈN 66 — mọi ca 'CẤU HÌNH GÃY' phải thật sự làm job ĐỎ\n"
          f"(bản đang thử: {MOD_PATH})")
    print("─" * 78)
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
    print("─" * 78)
    if hong:
        print(f"✗ {hong}/{len(CA)} ca HỎNG — chốt secret không còn phân biệt 'chưa cấu hình' với "
              f"'cấu hình gãy'; mốc 21:00 có thể xanh mà không gửi gì.")
        return 1
    print(f"✓ {len(CA)}/{len(CA)} ca đạt — chốt secret còn sống.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
