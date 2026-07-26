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

Bản thiết kế cũ (5 khu vực, xanh lá) giữ ở `v-xanh-cu.html`, dùng chung dữ liệu.

## Kỹ thuật

- Một file `index.html` (~190KB): HTML + CSS + JS thuần, không build step, không framework.
- Font Be Vietnam Pro + Baloo 2 nhúng sẵn dạng data URI (chạy được offline, không phụ thuộc CDN).
- PWA: `manifest.json` + `sw.js` → thêm vào màn hình chính, dùng được khi mất mạng.
- Dữ liệu lưu `localStorage` khoá `ren.v2`, tự di trú từ `ren-v1`; hai bản thiết kế dùng chung khoá này. Xuất/nhập `.json` để backup hoặc chuyển máy.

**Lưu ý:** dữ liệu nằm trong trình duyệt của từng máy, không có server. Đổi máy hoặc xoá cache là mất — thỉnh thoảng vào Hệ thống → *Xuất bản sao .json*.

## Deploy

GitHub Pages từ nhánh `main`. Sửa nội dung đáng kể thì bump `CACHE` trong `sw.js` để máy người dùng nhận bản mới.
