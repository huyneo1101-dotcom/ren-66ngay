# Rèn · Kỷ luật 66 ngày

App web một-file để rèn một việc nhỏ thành thói quen tự động trong 66 ngày. Thiết kế **thẻ lật**: mỗi lần mở chỉ thấy đúng một việc, quẹt phải là xong, quẹt trái để sau.

**Dùng ngay:** https://huyneo1101-dotcom.github.io/ren-66ngay/

## Ý tưởng

Kỷ luật không phải đích đến mà là giai đoạn quá độ: lặp một việc đủ lâu trong bối cảnh cố định thì nó tự động hoá, không còn tốn ý chí. App bám đúng chuỗi đó — **động lực khởi động → kỷ luật duy trì → thói quen tự chạy → kết quả nuôi lại động lực** — và đo cả những đòn bẩy quanh nó (giấc ngủ, môi trường, kèo xã hội).

## Có gì

- **Chồng thẻ mỗi ngày** — app tự chia: thẻ giấc ngủ (nếu chưa ghi) → từng việc → thẻ số đo → thẻ chốt ngày. Không có danh sách để ngợp.
- **Quẹt thật** — kéo ngang bằng ngón, có dấu XONG / ĐỂ SAU hiện dần theo lực kéo. Bàn phím: mũi tên trái/phải.
- **Hoãn có giá** — quẹt trái đẩy thẻ xuống cuối và đếm vào "đã hoãn tuần này", hiện ngay trên thẻ lần sau.
- **Sổ 66 ngày** — bản đồ ngày, chuỗi hiện tại/dài nhất, tỉ lệ đạt, chuỗi riêng từng việc, giấc ngủ trung bình.
- **Cài đặt** — căn tính, việc + số phút tối thiểu, số đo, kèo xã hội, giao diện Giấy/Đêm, xuất/nhập dữ liệu.
- **Băng giữ chuỗi** — ngày đuối chỉ cần một việc là chuỗi không đứt; ngủ dưới 6 tiếng thì app tự bật giúp.
- **Đồng bộ & nhắc Telegram** *(tuỳ chọn, mặc định tắt)* — bật thì tiến độ được đẩy lên Supabase: có backup, mở được ở máy khác, và mỗi 21h bot Telegram nhắn hôm nay là ngày thứ mấy, chuỗi bao nhiêu, còn việc nào chưa tick, hôm qua có đạt không.

Bản thiết kế cũ (5 khu vực, xanh lá) giữ ở `v-xanh-cu.html`, dùng chung dữ liệu — nhưng **không có phần đồng bộ**: tick bên bản cũ chỉ nằm ở máy, phải mở lại `index.html` một lần thì bản trên máy chủ mới được cập nhật.

## Kỹ thuật

- Một file `index.html` (~190KB): HTML + CSS + JS thuần, không build step, không framework.
- Font Be Vietnam Pro + Baloo 2 nhúng sẵn dạng data URI (chạy được offline, không phụ thuộc CDN).
- PWA: `manifest.json` + `sw.js` → thêm vào màn hình chính, dùng được khi mất mạng.
- Dữ liệu lưu `localStorage` khoá `ren.v2`, tự di trú từ `ren-v1`; hai bản thiết kế dùng chung khoá này. Xuất/nhập `.json` để backup hoặc chuyển máy.
- Đồng bộ (nếu bật): ba hàm RPC `security definer` trên Supabase — `ren_push` / `ren_pull` / `ren_forget`. Lược đồ và mô hình bảo mật ở [`docs/supabase-setup.sql`](docs/supabase-setup.sql). Mã đồng bộ nằm ở khoá localStorage **riêng** `ren.sync`, không đi kèm file `.json` xuất ra.
- Nhắc: `.github/workflows/notify-telegram.yml` chạy `.github/scripts/send_telegram.py` lúc 14:00 UTC (21:00 VN), gửi qua Telegram Bot API bằng `urllib` thuần — dùng chung bot với Điểm Tin Thế Giới.

**Lưu ý:** mặc định dữ liệu vẫn chỉ nằm trong trình duyệt của từng máy. Chưa bật Đồng bộ thì đổi máy hoặc xoá cache là mất — thỉnh thoảng vào Cài đặt → *Xuất bản sao .json*.

## Deploy

GitHub Pages từ nhánh `main`. Sửa nội dung đáng kể thì bump `CACHE` trong `sw.js` để máy người dùng nhận bản mới.

Muốn bot nhắc chạy, cần làm ba việc một lần:

1. Chạy [`docs/supabase-setup.sql`](docs/supabase-setup.sql) trong Supabase SQL Editor.
2. Trong app: Cài đặt → **Đồng bộ & nhắc Telegram** → *Bật đồng bộ* → *Copy mã*.
3. Đặt secret cho repo:

```bash
gh secret set REN_DEVICE_ID --repo huyneo1101-dotcom/ren-66ngay
```

```bash
gh secret set TELEGRAM_BOT_TOKEN --repo huyneo1101-dotcom/ren-66ngay
```

```bash
gh secret set TELEGRAM_CHAT_ID --repo huyneo1101-dotcom/ren-66ngay
```

Thử trước khi chờ tới 21h: Actions → *Nhắc kỷ luật qua Telegram* → **Run workflow** → tick `dry` để chỉ in ra log.
