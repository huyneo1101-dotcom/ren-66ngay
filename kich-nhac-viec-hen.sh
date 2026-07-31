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
# Xem log:  tail -20 ~/.claude/ren-kich-viec-hen.log
# Tắt tạm:  launchctl unload -w ~/Library/LaunchAgents/com.huy.ren-kich-viec-hen.plist

REPO="huyneo1101-dotcom/ren-66ngay"
WF="nhac-viec-hen.yml"
# Log để ~/.claude chứ KHÔNG /tmp: nội dung ở đây đúng là kỹ thuật thuần (mốc giờ + kết quả
# gọi, không có cam kết nào), nhưng cổng lớp 6 của khoe.py cấm mọi LaunchAgent ghi log vào
# /tmp và cấm đúng — nới cổng cho một log của mình là mở lại chính lỗ nó canh. Thư mục repo
# thì không dùng được: ren-66ngay là repo PUBLIC.
LOG="/Users/Huy/.claude/ren-kich-viec-hen.log"
GIO_DAU=6
GIO_CUOI=23

GIO=$(date +%-H)
if [ "$GIO" -lt "$GIO_DAU" ] || [ "$GIO" -gt "$GIO_CUOI" ]; then
  exit 0
fi

# launchd không nạp .zshrc nên PATH trần không có gh (luật: routine phải gọi đường tuyệt đối).
GH=/opt/homebrew/bin/gh
[ -x "$GH" ] || GH=/usr/local/bin/gh
if [ ! -x "$GH" ]; then
  echo "$(date '+%F %T') LỖI: không thấy gh ở /opt/homebrew/bin hay /usr/local/bin" >> "$LOG"
  exit 1
fi

touch "$LOG" 2>/dev/null && chmod 600 "$LOG" 2>/dev/null

OUT=$("$GH" workflow run "$WF" --repo "$REPO" 2>&1)
MA=$?
if [ "$MA" -eq 0 ]; then
  echo "$(date '+%F %T') đã kích" >> "$LOG"
else
  # Kêu ra log chứ không im: hỏng ở đây nghĩa là tính năng lặng lẽ quay về độ trễ ~2 giờ,
  # và không có dấu hiệu nào khác cho biết.
  echo "$(date '+%F %T') TRƯỢT mã $MA: $OUT" >> "$LOG"
fi

# Giữ log gọn, khỏi phình vô hạn.
if [ -f "$LOG" ] && [ "$(wc -l < "$LOG")" -gt 500 ]; then
  tail -200 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
fi
exit "$MA"
