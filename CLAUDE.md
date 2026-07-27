# Rèn · Kỷ luật 66 ngày — quy tắc làm việc trên repo này

App web một-file. Không build step, không framework, không package.json. Sửa là sửa thẳng
`index.html` (~200KB) rồi mở bằng trình duyệt mà kiểm.

## Nơi để đồ

| Thứ | Ở đâu |
|---|---|
| Toàn bộ app | `index.html` — khối `<script>` chính ~600 dòng, cuối file |
| Bản thiết kế cũ (5 khu vực, xanh lá) | `v-xanh-cu.html` — **dùng chung `localStorage`**, KHÔNG có phần đồng bộ |
| Lược đồ + mô hình bảo mật Supabase | `docs/supabase-setup.sql` |
| Script nhắc Telegram | `.github/scripts/send_telegram.py` |
| Cắm token Telegram | `.github/scripts/setup-telegram.py` — chạy một lần, xem docstring |
| Lịch nhắc | `.github/workflows/notify-telegram.yml` — 14:00 UTC = 21:00 VN |

Dữ liệu: `localStorage["ren.v2"]` (state), `localStorage["ren.sync"]` (mã đồng bộ — **để riêng
có chủ đích**, xem dưới).

## Quy tắc bắt buộc

1. **Đổi cách tính thì phải đổi ở CẢ HAI nơi.** `isHit` · `streak` · `dayIx` · `rateAll` tồn tại
   hai bản: JS trong `index.html` và bản dịch Python trong `send_telegram.py`. Lệch nhau là app
   hiện một con số, tin nhắn Telegram hiện con số khác — kiểu lỗi không ai báo mà tự mất niềm tin.
2. **Bump `CACHE` trong `sw.js`** mỗi lần sửa nội dung đáng kể, nếu không máy đã cài PWA giữ bản cũ.
3. **Giữ đúng phong cách code:** `var`, hàm ngắn một dòng, không arrow function, không template
   literal, không thư viện. Code mới lạc phong cách trong file một-file là rất chướng.
4. **Kiểm thật, đừng suy đoán.** Máy Huy **không có `node`** — dùng `jsc` để parse JS:
   `/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc`.
   Script nhắc thì chạy `DRY_RUN=1 REN_STATE_FILE=<file.json> python3 .github/scripts/send_telegram.py`
   (đọc file thay vì gọi Supabase, không cần mạng, không cần secret).
5. **Sửa chữ trong tin nhắn xong thì soi lại bằng máy, đừng đọc bằng mắt:**
   `DRY_RUN=1 REN_STATE_FILE=<file.json> python3 .github/scripts/send_telegram.py | python3 .github/scripts/check_html.py`
   — bắt thẻ lồng nhau, thẻ Telegram không nhận, thẻ chưa đóng, và `& < >` trần chưa escape.
   Chính nó bắt được bẫy số 1 bên dưới, thứ mà đọc lướt không thấy.

## Đồng bộ Supabase — vì sao thiết kế như vậy

Dùng chung project với Điểm Tin Thế Giới (`ltmlueqkajqmduoqghdf`).

- **Vì sao phải có:** localStorage thuần thì GitHub Action không đọc được tiến độ, tin nhắc sẽ
  không biết hôm qua có tick hay không — nhắc mù. Đây là lý do duy nhất khiến app này cần server.
- **Mặc định TẮT.** App công khai trên GitHub Pages; bật sẵn là đẩy nhật ký của người lạ lên máy
  chủ của Huy mà họ không hề chọn. Đừng đổi mặc định này.
- **KHÔNG dùng `service_role` key.** Key đó toàn quyền lên cả project Điểm Tin (`votes`,
  `saved_items`, `auth.users`). Mọi truy cập đi qua ba hàm `security definer`, gọi bằng
  publishable key vốn đã công khai trong `index.html`.
- **Bảng bật RLS mà KHÔNG có policy nào, và không cấp quyền bảng cho `anon`.** Cố ý: PostgREST
  cho phép `PATCH /rest/v1/ren_state` **không kèm bộ lọc**, và một policy `using(true)` sẽ ngoan
  ngoãn cho ghi đè toàn bộ bảng bằng một request. Đi qua hàm thì bắt buộc có `p_device`.
- **Mã đồng bộ = uuid v4 là bí mật duy nhất.** Ai biết mã thì đọc được toàn bộ nhật ký của mày.
  Nó nằm ở khoá localStorage RIÊNG chứ không nằm trong state, để file `.json` xuất ra đưa cho ai
  cũng không kèm chìa khoá. Đừng gộp nó vào state cho "gọn".

## Bốn cái bẫy đã vấp thật (27/07/2026), đừng vấp lại

1. **`<b>` lồng `<b>` là Telegram từ chối CẢ tin nhắn** (HTTP 400 `can't parse entities`) — không
   phải bỏ qua thẻ. Dòng tiêu đề đã bọc `<b>` thì bên trong tuyệt đối không bold nữa. Soát bằng
   cách chạy DRY_RUN rồi đọc, đừng tin mắt lướt.
2. **Xoá cục bộ mà không xoá trên máy chủ thì dữ liệu SỐNG LẠI.** `mergeState` thấy máy này không
   còn việc nào, máy chủ còn → kéo nguyên bản cũ về. Vì thế nút "Xoá sạch, làm lại" phải gọi
   `ren_forget`. Thêm bất kỳ đường xoá nào khác cũng phải nhớ điều này.
3. **So mốc thời gian thuần thì máy mới nuốt mất bản cũ.** Máy vừa cài có `t = Date.now()` (rất
   lớn) mà chưa có dữ liệu gì; lấy "bản mới hơn thắng" là xoá sạch bản thật. `mergeState` vì thế
   xét trước: bên nào chưa có việc nào thì lấy nguyên cấu hình của bên kia.
4. **Cron GitHub Actions KHÔNG đúng giờ** — hàng chờ đông là trễ 5–15 phút, cá biệt hơn. Đừng
   chỉnh phút trong `cron:` để mong nhắc đúng 21:00:00; không ép được.
5. **"Thiếu secret → thoát êm" mà gộp cả nắm thì nó CHE MẤT sự cố mất secret.** Bắt được thật:
   `TELEGRAM_BOT_TOKEN` chưa từng được đặt, mà run 30250807802 vẫn *success* trong 10 giây —
   mốc 21:00 chạy xanh hằng ngày, không một tin nào tới, không ai biết. Vì thế `main()` nay tách
   **chưa cấu hình** (không có secret nào → êm) khỏi **cấu hình gãy** (có cái này thiếu cái kia →
   `exit 1`, job đỏ). Thêm secret mới thì phải thêm vào cả danh sách `thieu` trong `main()`, nếu
   không nó lại lọt vào vùng câm.

## Telegram

**Bot RIÊNG của Rèn** — 27/07/2026 Huy tách khỏi bot Điểm Tin (`@diemtin24h_bot`). Đừng gộp lại:
tin nhắc kỷ luật hằng ngày lẫn vào luồng bản tin thì cả hai đều bị lướt qua, và token dùng chung
nghĩa là sự cố ở app này kéo sập app kia. Secret cần đặt cho repo này: `TELEGRAM_BOT_TOKEN`,
`TELEGRAM_CHAT_ID`, `REN_DEVICE_ID`.

`TELEGRAM_CHAT_ID` **không đổi khi đổi bot** — nó là id người dùng Telegram, không phải id của
cặp người-bot. Nhưng bot mới **không nhắn trước được**: chưa bấm Start thì `sendMessage` trả 403
`bot can't initiate conversation with a user`. Cái này thì `send_all` trả `rc = 1` nên workflow
đỏ và thấy ngay — khác hẳn ba chốt "thoát êm" ở trên, vốn chỉ êm khi *chưa cấu hình*, chứ đã
cấu hình mà gửi hỏng thì phải kêu.

**Cắm token:** `python3 .github/scripts/setup-telegram.py` — hỏi token bằng `getpass` (không in
ra màn hình), kiểm `getMe`, **chặn nếu dán nhầm token @diemtin24h_bot**, tự dò `chat_id`, gửi tin
thử, `gh secret set` qua stdin, rồi bấm chạy workflow thật và chờ kết quả. Gửi thử hỏng thì
**không đặt secret nào cả** — đặt vào là repo mang cấu hình chưa từng chạy được.

**Trạng thái cấu hình (27/07/2026):** bảng `ren_state` + ba hàm đã tạo trên project
`ltmlueqkajqmduoqghdf` (đã kiểm: push/pull/forget chạy, đọc thẳng bảng bị chặn 401, mã sai định
dạng bị chặn 400). Secret `REN_DEVICE_ID` và `TELEGRAM_CHAT_ID` đã đặt.
⛔ **`TELEGRAM_BOT_TOKEN` CHƯA ĐẶT** — bot riêng chưa được tạo. Tới khi Huy chạy `setup-telegram.py`
thì mốc 21:00 hằng ngày sẽ ĐỎ (cố ý, xem bẫy số 5). Đỏ = "chưa cắm token", không phải hỏng mới.

Bản sao mã đồng bộ để ở `/Users/Huy/Claude/.ren66-device-id` (chmod 600, **ngoài repo** vì repo
này public). Mất file đó mà cũng mất máy thì mất luôn nhật ký trên server — không có đường
khôi phục, vì mã chính là chìa khoá duy nhất.

Ba chốt an toàn trong `send_telegram.py`, giữ nguyên tinh thần khi sửa:

1. **Không** có secret nào → `exit 0` êm ("chưa cấu hình" ≠ "hỏng"). Nhưng có secret mà thiếu
   mảnh → `exit 1` cho ĐỎ; mất `REN_DEVICE_ID` thì vẫn gửi tin rút gọn trước rồi mới đỏ.
2. Supabase hỏng / chưa có dòng nào → **vẫn gửi** một tin nhắc rút gọn. App kỷ luật mà im lặng vì
   hạ tầng là hỏng đúng cái việc nó sinh ra để làm.
3. State cũ quá `STALE_HOURS` (mặc định 36) → gắn cảnh báo lên đầu tin. Báo "chuỗi 12 ngày" bằng
   dữ liệu ba ngày trước còn tệ hơn không báo, vì nó làm người ta yên tâm nhầm.
