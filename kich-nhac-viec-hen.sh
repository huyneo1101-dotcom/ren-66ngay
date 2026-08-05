#!/bin/bash
# Kích workflow "Nhắc việc đã hẹn" từ máy Mac, vì cron GitHub KHÔNG chạy đúng lịch khai báo.
#
# SỐ ĐO LÀM NỀN (31/07/2026, 22 lần chạy gần nhất của nhac-viec-hen.yml):
#   cron khai `*/30` (nửa tiếng một lần)
#   thực tế  : trung vị 1,78 giờ · p90 3,0 giờ · tệ nhất 3,88 giờ
# Chú thích trong chính file workflow ghi "trễ 5–15 phút là thường" — số đo bác lại điều đó.
# Lời hứa của tính năng là "nhắc trong vòng nửa tiếng sau hạn", và lời hứa ấy đang không được
# giữ: một cam kết có giờ mà nhắc muộn gần hai tiếng thì không còn là cam kết.
#
# `workflow_dispatch` gọi qua API thì chạy NGAY (đo ở Điểm Tin: lệnh phát 21:00:00 → run tạo
# lúc 21:00:20Z). Nên đường vá là máy tự gọi, giống `com.huy.diemtin-bot-telegram`.
#
# VÌ SAO KÍCH MÙ, KHÔNG "NHÌN TRƯỚC" NHƯ BÊN ĐIỂM TIN: nhìn trước phải hỏi Supabase xem có
# cam kết nào quá hạn chưa, mà bảng `ren_vows` chặn theo `device` nên cần `REN_DEVICE_ID` —
# secret đó hiện chỉ nằm trên CI, kéo về máy thì phải cắm thêm khoá. Repo PUBLIC nên phút
# Actions miễn phí, và bản thân workflow đã có hai chốt chống spam (`NHAC_CACH_GIO` 20 giờ,
# `MAX_NHAC` 5 lần) — kích thừa không gửi thừa tin nào.
#
# CHỈ CHẠY TRONG KHUNG GIỜ THỨC: ngoài khung thì thoát ngay, không gọi `gh`. Kích cả đêm chỉ
# đổi lấy việc chôn lấp tab Actions — đúng công cụ dùng để chẩn đoán khi tính năng hỏng.
#
# ĐÁNH ĐỔI ĐÃ BIẾT, ĐỪNG TƯỞNG LÀ ĐÃ KÍN: máy ngủ hoặc ngoài khung giờ thì rơi về cron
# GitHub như cũ, tức cam kết đến hạn lúc 3 giờ sáng vẫn có thể nhắc muộn vài tiếng.
#
# ─────────────────────────────────────────────────────────────────────────────────────────
# THỬ LẠI KHI LỖI MẠNG (thêm 05/08/2026) — VÌ SAO PHẢI CÓ, ĐỪNG "DỌN CHO GỌN" MẤT
#
# Cơ chế gây vấp: `RunAtLoad` + `StartInterval` nghĩa là máy vừa ngủ dậy thì launchd chạy bù
# NGAY — đúng thứ cần cho việc "Huy vừa mở máy và có cam kết vừa tới hạn". Nhưng lúc đó Wi-Fi
# thường chưa lên, `gh` trả `error connecting to api.github.com`, script thoát mã 1, và
# `launchctl list` giữ mã đó tới lần chạy kế tiếp ⇒ bảng `/khoe` 09:00 sáng ra ĐỎ.
#
# Số đo 05/08/2026 trên 187 dòng log: **5 lần trượt, cả 5 đều là lỗi mạng thoáng qua**
# (03/08 16:39 · 04/08 07:44 · 04/08 08:09 · 04/08 10:56 · 05/08 08:02) — không lần nào là
# hỏng thật. Tức cổng này đang kêu oan ~2,7% số lượt, mà cổng chập chờn tệ hơn cổng chết: nó
# dạy người đọc bỏ qua màu đỏ, tới lúc hỏng thật cũng không ai nhìn.
#
# Vá bằng thử lại, KHÔNG bằng nuốt mã thoát:
#   · lỗi thuộc HỌ MẠNG  → chờ rồi thử lại, tối đa `LAN_TOI_DA` lượt; hết lượt vẫn trượt thì
#     ĐỎ thật (mạng chết mấy phút liền không còn là thoáng qua).
#   · lỗi KHÔNG thuộc họ mạng (chưa đăng nhập `gh`, workflow bị xoá, hết quyền, repo sai tên)
#     → TRƯỢT NGAY, không thử lại. Thử lại ở đây chỉ tổ trễ thêm 40 giây rồi vẫn đỏ, mà lại
#     làm mờ ranh giới giữa "mạng chập" và "cấu hình gãy".
# Chiều hỏng cố ý bất đối xứng: nhận nhầm lỗi thật thành lỗi mạng ⇒ fail-open (đỏ muộn 40
# giây rồi vẫn đỏ, không mất gì); nhận nhầm lỗi mạng thành lỗi thật ⇒ quay lại đúng chỗ đang
# vá. Nên bảng mẫu dưới đây bắt HẸP theo chuỗi lỗi mạng có thật trong log, không bắt rộng.
#
# Bộ test: .github/scripts/test-cong-kich-viec-hen.py  (kèm `--tu-kiem`)
# ─────────────────────────────────────────────────────────────────────────────────────────
#
# Xem log:  tail -20 ~/.claude/ren-kich-viec-hen.log
# Tắt tạm:  launchctl unload -w ~/Library/LaunchAgents/com.huy.ren-kich-viec-hen.plist

REPO="huyneo1101-dotcom/ren-66ngay"
WF="nhac-viec-hen.yml"
# Log để ~/.claude chứ KHÔNG /tmp: nội dung ở đây đúng là kỹ thuật thuần (mốc giờ + kết quả
# gọi, không có cam kết nào), nhưng cổng lớp 6 của khoe.py cấm mọi LaunchAgent ghi log vào
# /tmp và cấm đúng — nới cổng cho một log của mình là mở lại chính lỗ nó canh. Thư mục repo
# thì không dùng được: ren-66ngay là repo PUBLIC.
LOG="${REN_LOG:-/Users/Huy/.claude/ren-kich-viec-hen.log}"
GIO_DAU=6
GIO_CUOI=23

# Số lượt gọi tối đa (1 lượt đầu + các lượt thử lại) và thời gian chờ giữa hai lượt.
LAN_TOI_DA="${REN_LAN_TOI_DA:-3}"
CHO_GIAY="${REN_CHO_GIAY:-20}"

# `REN_GIO_EP` chỉ dùng cho bộ test: ca canh phải TẤT ĐỊNH, không được đổi kết quả theo giờ
# đồng hồ lúc chạy test (chạy lúc 2 giờ sáng thì mọi ca đều thoát êm, tức đo nhầm nhánh).
GIO="${REN_GIO_EP:-$(date +%-H)}"
if [ "$GIO" -lt "$GIO_DAU" ] || [ "$GIO" -gt "$GIO_CUOI" ]; then
  exit 0
fi

# launchd không nạp .zshrc nên PATH trần không có gh (luật: routine phải gọi đường tuyệt đối).
# `REN_GH_BIN` để bộ test tráo bản `gh` giả — không có nó thì mọi ca test đều phải gọi mạng
# thật, tức bộ test vừa chậm vừa không dựng được ca "mạng hỏng".
GH="${REN_GH_BIN:-}"
if [ -z "$GH" ]; then
  GH=/opt/homebrew/bin/gh
  [ -x "$GH" ] || GH=/usr/local/bin/gh
fi
if [ ! -x "$GH" ]; then
  echo "$(date '+%F %T') LỖI: không thấy gh ở /opt/homebrew/bin hay /usr/local/bin" >> "$LOG"
  exit 1
fi

touch "$LOG" 2>/dev/null && chmod 600 "$LOG" 2>/dev/null

# Họ lỗi mạng thoáng qua. Bắt HẸP, theo đúng chuỗi đã thấy trong log thật — mẫu rộng kiểu
# `timeout` trần sẽ nuốt cả những lỗi cấu hình có chữ đó trong thông điệp.
la_loi_mang() {
  printf '%s' "$1" | grep -qiE 'error connecting to|dial tcp|i/o timeout|TLS handshake timeout|connection reset by peer|connection refused|no such host|network is unreachable|temporary failure in name resolution|server misbehaving'
}

LAN=1
while true; do
  OUT=$("$GH" workflow run "$WF" --repo "$REPO" 2>&1)
  MA=$?

  if [ "$MA" -eq 0 ]; then
    if [ "$LAN" -eq 1 ]; then
      echo "$(date '+%F %T') đã kích" >> "$LOG"
    else
      # Ghi rõ đã phải thử mấy lượt: mạng chập nhiều lần trong ngày vẫn là tín hiệu đáng đọc,
      # chỉ là chưa tới mức làm đỏ bảng.
      echo "$(date '+%F %T') đã kích (lượt thứ $LAN)" >> "$LOG"
    fi
    break
  fi

  if ! la_loi_mang "$OUT"; then
    # Lỗi thật: kêu NGAY, không thử lại.
    echo "$(date '+%F %T') TRƯỢT mã $MA: $OUT" >> "$LOG"
    break
  fi

  if [ "$LAN" -ge "$LAN_TOI_DA" ]; then
    # Kêu ra log chứ không im: hỏng ở đây nghĩa là tính năng lặng lẽ quay về độ trễ ~2 giờ,
    # và không có dấu hiệu nào khác cho biết.
    echo "$(date '+%F %T') TRƯỢT mã $MA sau $LAN lượt (lỗi mạng): $OUT" >> "$LOG"
    break
  fi

  [ "$CHO_GIAY" -gt 0 ] && sleep "$CHO_GIAY"
  LAN=$((LAN + 1))
done

# Giữ log gọn, khỏi phình vô hạn.
if [ -f "$LOG" ] && [ "$(wc -l < "$LOG")" -gt 500 ]; then
  tail -200 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
fi
exit "$MA"
