#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bộ test cho `kich-nhac-viec-hen.sh` — chốt "thử lại khi lỗi mạng, kêu ngay khi lỗi thật".

VÌ SAO CẦN (luật mục 17 CLAUDE.md toàn cục: cổng nào cũng phải có ca PHẢI KÊU):

Script này là cổng loại **hai chiều đều hỏng câm được**:
  · nới tay  → mọi lỗi đều bị coi là lỗi mạng, `gh` chưa đăng nhập hay workflow bị xoá cũng
    được thử lại rồi... vẫn đỏ, nhưng đỏ muộn và lẫn lý do; tệ hơn, nếu ai đó "dọn cho gọn"
    thành nuốt luôn mã thoát thì tính năng lặng lẽ quay về độ trễ ~2 giờ mà bảng vẫn xanh.
  · siết tay → quay lại đúng chỗ đang vá: lỗi mạng thoáng qua lúc máy vừa ngủ dậy làm bảng
    `/khoe` đỏ oan (đo 05/08/2026: 5/187 lượt, cả 5 đều là mạng chập).
Chạy thử bằng mạng thật KHÔNG phân biệt được hai chiều đó — mạng lúc nào cũng chạy thì cả bản
đúng lẫn bản hỏng đều xanh. Chỉ bản `gh` giả theo kịch bản mới đo được.

Chạy:
    python3 /Users/Huy/Claude/App/Ren66/.github/scripts/test-cong-kich-viec-hen.py
    python3 /Users/Huy/Claude/App/Ren66/.github/scripts/test-cong-kich-viec-hen.py --tu-kiem

Hoàn toàn OFFLINE: `REN_GH_BIN` trỏ vào bản `gh` giả, `REN_GIO_EP` ép giờ nên ca TẤT ĐỊNH
(không đổi kết quả theo giờ đồng hồ lúc chạy), `REN_CHO_GIAY=0` nên không có `sleep` nào.

⚠ Bản hỏng của `--tu-kiem` ghi vào THƯ MỤC TẠM, không ghi cạnh script thật. Khác luật chung
(mục 17 bắt để cạnh bản thật) vì lý do đó chỉ áp cho Python nạp module theo đường dẫn — script
bash chạy ở đâu cũng như nhau. Đổi lại tránh hẳn được họ lỗi "rác mồ côi làm khoe.py kêu oan",
và repo này PUBLIC nên càng không nên rơi file lạ vào cây làm việc.
"""

import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.environ.get(
    "REN_KICH_SH", os.path.join(os.path.dirname(os.path.dirname(HERE)), "kich-nhac-viec-hen.sh")
)

CAC_CA = []


def ca(ten):
    def deco(fn):
        CAC_CA.append((ten, fn))
        return fn

    return deco


# ─────────────────────────────────────────────────────────────────────────────
# Bộ giàn: `gh` giả chạy theo kịch bản, đếm số lượt bị gọi.
# ─────────────────────────────────────────────────────────────────────────────

GH_GIA = """#!/bin/bash
# `gh` giả: mỗi lượt bị gọi thì ghi một dòng vào $DEM, rồi trả kết quả của dòng thứ N trong
# $KICH_BAN. Quá số dòng thì lặp lại dòng cuối — nhờ vậy dựng được ca "mạng hỏng liên tục".
echo "goi" >> "$DEM"
N=$(wc -l < "$DEM" | tr -d ' ')
DONG=$(sed -n "${N}p" "$KICH_BAN")
if [ -z "$DONG" ]; then DONG=$(tail -1 "$KICH_BAN"); fi
MA="${DONG%%|*}"
THONG_DIEP="${DONG#*|}"
if [ "$MA" != "0" ]; then
  echo "$THONG_DIEP" >&2
fi
exit "$MA"
"""

LOI_MANG = "error connecting to api.github.com\ncheck your internet connection"
LOI_MANG_2 = 'unable to determine default branch: Post "https://api.github.com/graphql": dial tcp 20.205.243.168:443: i/o timeout'
LOI_THAT = "gh: To use GitHub CLI, run: gh auth login"
LOI_THAT_2 = "could not find any workflows named nhac-viec-hen.yml"


def chay(kich_ban, gio=9, lan_toi_da=None, script=None):
    """Chạy script với `gh` giả. Trả (mã thoát, số lượt gọi gh, nội dung log)."""
    script = script or SCRIPT
    tmp = tempfile.mkdtemp(prefix="test-kich-")
    try:
        p_dem = os.path.join(tmp, "dem")
        p_kb = os.path.join(tmp, "kich-ban")
        p_log = os.path.join(tmp, "log")
        p_gh = os.path.join(tmp, "gh-gia")

        open(p_dem, "w").close()
        with open(p_kb, "w") as f:
            f.write("\n".join("%d|%s" % (ma, td.replace("\n", " ")) for ma, td in kich_ban) + "\n")
        with open(p_gh, "w") as f:
            f.write(GH_GIA)
        os.chmod(p_gh, 0o755)

        env = dict(os.environ)
        env.update(
            {
                "DEM": p_dem,
                "KICH_BAN": p_kb,
                "REN_GH_BIN": p_gh,
                "REN_LOG": p_log,
                "REN_GIO_EP": str(gio),
                "REN_CHO_GIAY": "0",
            }
        )
        if lan_toi_da is not None:
            env["REN_LAN_TOI_DA"] = str(lan_toi_da)

        r = subprocess.run(["/bin/bash", script], env=env, capture_output=True, timeout=60)
        with open(p_dem) as f:
            so_lan = len([x for x in f.read().splitlines() if x.strip()])
        log = open(p_log).read() if os.path.exists(p_log) else ""
        return r.returncode, so_lan, log
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ─────────────────────────────────────────────────────────────────────────────
# CÁC CA
# ─────────────────────────────────────────────────────────────────────────────


@ca("01. Kích được ngay lượt đầu → thoát 0, gọi gh đúng 1 lượt")
def _():
    ma, lan, log = chay([(0, "")])
    if ma != 0:
        return False, "mã thoát %d, phải là 0" % ma
    if lan != 1:
        return False, "gọi gh %d lượt, phải đúng 1" % lan
    if "đã kích" not in log:
        return False, "log không ghi 'đã kích': %r" % log
    return True, "mã 0 · 1 lượt · log ghi 'đã kích'"


@ca("02. Lỗi MẠNG lượt 1 rồi kích được lượt 2 → thoát 0 (ca chính của bản vá 05/08)")
def _():
    ma, lan, log = chay([(1, LOI_MANG), (0, "")])
    if ma != 0:
        return False, "mã thoát %d — lỗi mạng thoáng qua vẫn làm đỏ, đúng lỗi đang vá" % ma
    if lan != 2:
        return False, "gọi gh %d lượt, phải đúng 2" % lan
    if "lượt thứ 2" not in log:
        return False, "log không ghi rõ đã phải thử lại: %r" % log
    return True, "mã 0 · 2 lượt · log ghi 'lượt thứ 2'"


@ca("03. Lỗi mạng lượt 1+2 rồi kích được lượt 3 → thoát 0, đúng trần mặc định")
def _():
    ma, lan, _ = chay([(1, LOI_MANG), (1, LOI_MANG_2), (0, "")])
    if ma != 0:
        return False, "mã thoát %d, phải là 0" % ma
    if lan != 3:
        return False, "gọi gh %d lượt, phải đúng 3" % lan
    return True, "mã 0 · 3 lượt"


@ca("04. Lỗi MẠNG liên tục → PHẢI KÊU (thoát 1) sau đúng 3 lượt mặc định")
def _():
    # Ghim CỨNG con số 3, không suy từ hằng số của script: ca neo động theo hằng số chỉ chứng
    # minh "phép so có chạy", nới trần lên 99 thì nó vẫn xanh.
    ma, lan, log = chay([(1, LOI_MANG)])
    if ma == 0:
        return False, "mã thoát 0 — mạng chết liền 3 lượt mà vẫn báo êm, fail-open"
    if lan != 3:
        return False, "gọi gh %d lượt, trần mặc định phải là 3" % lan
    if "TRƯỢT" not in log:
        return False, "log không ghi TRƯỢT: %r" % log
    return True, "mã %d · 3 lượt · log ghi TRƯỢT" % ma


@ca("05. Lỗi THẬT (chưa đăng nhập gh) → PHẢI KÊU NGAY, gọi gh đúng 1 lượt")
def _():
    # Đối chứng chống NỚI TAY: nếu `la_loi_mang` bắt rộng thành khớp mọi thứ thì số lượt
    # thành 3 và ca này đỏ. Đây là ca duy nhất phân biệt được hai chiều hỏng.
    ma, lan, log = chay([(1, LOI_THAT)])
    if ma == 0:
        return False, "mã thoát 0 — lỗi cấu hình mà báo êm"
    if lan != 1:
        return False, "gọi gh %d lượt — lỗi thật không được thử lại, phải đúng 1" % lan
    if "TRƯỢT" not in log:
        return False, "log không ghi TRƯỢT: %r" % log
    return True, "mã %d · 1 lượt · không thử lại" % ma


@ca("06. Lỗi THẬT thứ hai (workflow bị xoá) → PHẢI KÊU NGAY, 1 lượt")
def _():
    ma, lan, _ = chay([(1, LOI_THAT_2)])
    if ma == 0:
        return False, "mã thoát 0 — workflow bị xoá mà báo êm"
    if lan != 1:
        return False, "gọi gh %d lượt, phải đúng 1" % lan
    return True, "mã %d · 1 lượt" % ma


@ca("07. Trần thử lại đọc được từ REN_LAN_TOI_DA → đặt 2 thì gọi đúng 2 lượt")
def _():
    ma, lan, _ = chay([(1, LOI_MANG)], lan_toi_da=2)
    if ma == 0:
        return False, "mã thoát 0, phải kêu"
    if lan != 2:
        return False, "gọi gh %d lượt, phải đúng 2" % lan
    return True, "mã %d · 2 lượt" % ma


@ca("08. Ngoài khung giờ (03 giờ sáng) → thoát 0 êm và KHÔNG gọi gh lượt nào")
def _():
    ma, lan, _ = chay([(0, "")], gio=3)
    if ma != 0:
        return False, "mã thoát %d, ngoài khung phải êm" % ma
    if lan != 0:
        return False, "gọi gh %d lượt — ngoài khung giờ không được gọi" % lan
    return True, "mã 0 · 0 lượt"


@ca("09. Trong khung giờ sát biên (23 giờ) → VẪN gọi (chống siết oan ca 08)")
def _():
    ma, lan, _ = chay([(0, "")], gio=23)
    if ma != 0 or lan != 1:
        return False, "mã %d · %d lượt — 23 giờ vẫn thuộc khung thức" % (ma, lan)
    return True, "mã 0 · 1 lượt"


@ca("10. Trượt thì log phải ghi lại — không được im lặng")
def _():
    _, _, log = chay([(1, LOI_THAT)])
    if "TRƯỢT" not in log or "auth login" not in log:
        return False, "log không nêu nguyên văn lỗi: %r" % log
    return True, "log giữ nguyên văn thông điệp lỗi"


# ─────────────────────────────────────────────────────────────────────────────
# CHẠY
# ─────────────────────────────────────────────────────────────────────────────


def chay_bo(script=None):
    goc = globals().get("_SCRIPT_EP")
    if script:
        globals()["_SCRIPT_EP"] = script
    do = []
    for ten, fn in CAC_CA:
        try:
            ok, ghi_chu = fn()
        except Exception as e:  # noqa: BLE001
            ok, ghi_chu = False, "NGOẠI LỆ: %s" % e
        print("  %s %s" % ("✓" if ok else "✗", ten))
        if not ok:
            print("        │ %s" % ghi_chu)
            do.append(int(re.match(r"\s*(\d+)", ten).group(1)))
    globals()["_SCRIPT_EP"] = goc
    return do


def main():
    global SCRIPT
    if not os.path.exists(SCRIPT):
        print("✗ KHÔNG thấy script cần đo: %s" % SCRIPT)
        return 2

    if "--tu-kiem" in sys.argv:
        return tu_kiem()

    print("── CỔNG KÍCH NHẮC VIỆC ĐÃ HẸN ─ %s" % SCRIPT)
    do = chay_bo()
    print("─" * 78)
    if do:
        print("✗ %d/%d ca HỎNG — cổng kích nhắc việc hẹn không còn phân biệt được lỗi mạng "
              "với lỗi thật." % (len(do), len(CAC_CA)))
        return 1
    print("✓ %d/%d ca đạt." % (len(CAC_CA), len(CAC_CA)))
    return 0


def tu_kiem():
    """Dựng các bản script đã gỡ đúng dòng bảo vệ, chứng minh ca đã khai thật sự bắt được."""
    global SCRIPT
    goc_path = SCRIPT
    nguon = open(goc_path, encoding="utf-8").read()
    tmp = tempfile.mkdtemp(prefix="tu-kiem-kich-")
    tong_hong = 0
    try:
        print("── TỰ KIỂM: %d bản hỏng" % len(BAN_HONG))
        for ten, tim, thay, phai_do in BAN_HONG:
            if nguon.count(tim) != 1:
                print("  ✗ %s — chuỗi neo khớp %d chỗ (phải đúng 1)" % (ten, nguon.count(tim)))
                tong_hong += 1
                continue
            hong = nguon.replace(tim, thay)
            sha = hashlib.sha1(hong.encode("utf-8")).hexdigest()[:8]
            p = os.path.join(tmp, "_thu-hong-%d-%s-kich.sh" % (os.getpid(), sha))
            with open(p, "w", encoding="utf-8") as f:
                f.write(hong)
            os.chmod(p, 0o755)

            SCRIPT = p
            do = chay_bo()
            SCRIPT = goc_path

            if len(do) == len(CAC_CA):
                print("  ✗ %s — MỌI ca đều đỏ ⇒ phép thay làm hỏng cú pháp, không chứng minh "
                      "được gì. Sửa lại phép thay." % ten)
                tong_hong += 1
                continue
            thieu = [x for x in phai_do if x not in do]
            if thieu:
                print("  ✗ %s — ca %s VẪN XANH (đỏ thực tế: %s)" % (ten, thieu, do or "không ca nào"))
                tong_hong += 1
            else:
                print("  ✓ %s — bắt được (đỏ: %s)" % (ten, do))
    finally:
        SCRIPT = goc_path
        shutil.rmtree(tmp, ignore_errors=True)

    print("─" * 78)
    if tong_hong:
        print("✗ %d/%d bản hỏng LỌT — bộ test chưa đủ răng." % (tong_hong, len(BAN_HONG)))
        return 1
    print("✓ %d/%d bản hỏng đều bị bắt." % (len(BAN_HONG), len(BAN_HONG)))
    return 0


# ─────────────────────────────────────────────────────────────────────────────
# BẢNG BẢN HỎNG — ĐẶT CUỐI FILE, SAU MÃ (luật mục 17: neo đặt trước mã thì phép thay khớp
# vào chính dòng khai báo, bản hỏng "hỏng" ở bảng chứ không ở script cần đo).
# Neo kèm dòng liền kề để không trùng chính bảng này.
# ─────────────────────────────────────────────────────────────────────────────

BAN_HONG = [
    (
        "gỡ nhánh 'lỗi thật thì kêu ngay' (mọi lỗi đều được thử lại)",
        '  if ! la_loi_mang "$OUT"; then\n    # Lỗi thật: kêu NGAY, không thử lại.',
        '  if false; then\n    # Lỗi thật: kêu NGAY, không thử lại.',
        [5, 6],
    ),
    (
        # ⚠ Bản đầu của phép thay này chèn `|` vào đầu regex, tưởng là nới thành "khớp mọi
        # thứ". Đo thật 05/08: BSD grep trên macOS coi nhánh rỗng đứng đầu là lỗi cú pháp nên
        # `grep` trả khác 0 ⇒ hàm thành KHÔNG khớp gì, tức một bản SIẾT trùng hệt bản hỏng kế
        # tiếp (đỏ [2,3,4,7] thay vì [5,6]). Phép thay đi sai CHIỀU thì bản hỏng không chứng
        # minh được điều nó khai. Nay nới bằng `return 0` — không phụ thuộc phương ngữ regex.
        "nới `la_loi_mang` thành khớp mọi thông điệp",
        "la_loi_mang() {\n  printf '%s' \"$1\" | grep -qiE 'error connecting to",
        "la_loi_mang() {\n  return 0\n  printf '%s' \"$1\" | grep -qiE 'error connecting to",
        [5, 6],
    ),
    (
        "siết `la_loi_mang` thành không khớp gì (quay lại lỗi đang vá)",
        "  printf '%s' \"$1\" | grep -qiE 'error connecting to",
        "  printf '%s' \"$1\" | grep -qiE 'KHONG_BAO_GIO_KHOP_error connecting to",
        [2, 3],
    ),
    (
        "nới trần thử lại lên 99 (mạng chết cũng thử mãi)",
        'LAN_TOI_DA="${REN_LAN_TOI_DA:-3}"',
        'LAN_TOI_DA="${REN_LAN_TOI_DA:-99}"',
        [4],
    ),
    (
        "nuốt mã thoát cuối (trượt mà báo êm)",
        'fi\nexit "$MA"',
        "fi\nexit 0",
        [4, 5, 6, 7],
    ),
    (
        "bỏ hẳn phép thử lại (break ngay lượt đầu)",
        '  [ "$CHO_GIAY" -gt 0 ] && sleep "$CHO_GIAY"\n  LAN=$((LAN + 1))',
        "  break",
        [2, 3],
    ),
    (
        "bỏ kiểm khung giờ thức",
        'if [ "$GIO" -lt "$GIO_DAU" ] || [ "$GIO" -gt "$GIO_CUOI" ]; then\n  exit 0',
        'if false; then\n  exit 0',
        [8],
    ),
    (
        "im lặng khi trượt (không ghi log)",
        "    echo \"$(date '+%F %T') TRƯỢT mã $MA: $OUT\" >> \"$LOG\"\n    break",
        "    break",
        [5, 10],
    ),
]


if __name__ == "__main__":
    sys.exit(main())
