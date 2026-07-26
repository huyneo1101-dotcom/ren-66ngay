# Rèn · Kỷ luật 66 ngày

App web một-file để rèn một việc nhỏ thành thói quen tự động trong 66 ngày.

**Dùng ngay:** https://huyneo1101-dotcom.github.io/ren-66ngay/

## Ý tưởng

Kỷ luật không phải đích đến mà là giai đoạn quá độ: lặp một việc đủ lâu trong bối cảnh cố định thì nó tự động hoá, không còn tốn ý chí. App bám đúng chuỗi đó — **động lực khởi động → kỷ luật duy trì → thói quen tự chạy → kết quả nuôi lại động lực** — và đo cả những đòn bẩy quanh nó (giấc ngủ, môi trường, kèo xã hội).

## Có gì

- **Tổng quan** — chuỗi ngày, vòng tiến độ hôm nay, biểu đồ 14 ngày, pin ý chí, môi trường chưa dọn.
- **Hôm nay** — lời thệ căn tính, việc tối thiểu (mỗi việc có chuỗi riêng), giờ ngủ, mức năng lượng, số đo, ghi chú, chốt sổ.
- **Chuỗi 66** — bản đồ 66 ngày dạng lịch (bấm ô để mở sổ ngày đó), thống kê từng việc, huy hiệu.
- **Phân tích** — tỉ lệ đạt theo thứ và các nhận xét tự sinh từ số liệu (thứ nào yếu, giấc ngủ đổi kết quả bao nhiêu, việc nào hay bị bỏ…).
- **Hệ thống** — sửa việc (icon + màu), số đo, kèo xã hội, checklist môi trường, giao diện sáng/tối, xuất/nhập dữ liệu.
- **Băng giữ chuỗi** — ngày đuối chỉ cần làm một việc là chuỗi không đứt. Thà 2 phút còn hơn nghỉ.

## Kỹ thuật

- Một file `index.html` (~226KB): HTML + CSS + JS thuần, không build step, không framework.
- Font Be Vietnam Pro + Baloo 2 nhúng sẵn dạng data URI (chạy được offline, không phụ thuộc CDN).
- PWA: `manifest.json` + `sw.js` → thêm vào màn hình chính, dùng được khi mất mạng.
- Dữ liệu lưu `localStorage` khoá `ren.v2`, tự di trú từ `ren-v1`. Xuất/nhập `.json` để backup hoặc chuyển máy.

**Lưu ý:** dữ liệu nằm trong trình duyệt của từng máy, không có server. Đổi máy hoặc xoá cache là mất — thỉnh thoảng vào Hệ thống → *Xuất bản sao .json*.

## Deploy

GitHub Pages từ nhánh `main`. Sửa nội dung đáng kể thì bump `CACHE` trong `sw.js` để máy người dùng nhận bản mới.
