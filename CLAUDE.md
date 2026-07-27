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
| Nhận nút tick từ Telegram | `.github/scripts/tick_bot.py` + `.github/workflows/tick-bot.yml` |
| Cắm token Telegram | `.github/scripts/setup-telegram.py` — chạy một lần, xem docstring |
| Lịch nhắc | `.github/workflows/notify-telegram.yml` — 14:00 UTC = 21:00 VN |

Dữ liệu: `localStorage["ren.v2"]` (state), `localStorage["ren.sync"]` (mã đồng bộ — **để riêng
có chủ đích**, xem dưới).

## Quy tắc bắt buộc

1. **Đổi cách tính thì phải đổi ở CẢ BA nơi.** `isHit` · `streak` · `dayIx` · `rateAll` tồn tại
   hai bản: JS trong `index.html` và bản dịch Python trong `send_telegram.py`. Lệch nhau là app
   hiện một con số, tin nhắn Telegram hiện con số khác — kiểu lỗi không ai báo mà tự mất niềm tin.
   **Nơi thứ ba (thêm 27/07/2026): hàm `ren_tick` trong Postgres** — nó quyết định "chốt xong"
   nghĩa là gì, hiện đang là *tick đủ mọi việc trong `habits`*, khớp ngưỡng `isHit` của ngày
   thường. Đổi `isHit` (ví dụ cho phép đạt khi làm 2/3 việc) mà quên sửa `ren_tick` thì nút
   Telegram vẫn tick đủ hết — app tính là đạt, nhưng số việc ghi vào nhật ký sai sự thật.
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
cặp người-bot. Nhưng bot mới **không nhắn trước được**: chưa bấm Start thì `sendMessage` hỏng.
Cái này thì `send_all` trả `rc = 1` nên workflow đỏ và thấy ngay — khác hẳn ba chốt "thoát êm" ở
trên, vốn chỉ êm khi *chưa cấu hình*, chứ đã cấu hình mà gửi hỏng thì phải kêu.

⚠️ **Mã lỗi thật là `400 Bad Request: chat not found`, KHÔNG phải 403** (đo thật 27/07/2026, run
30274126666 — mục này trước ghi 403 `bot can't initiate conversation`, sai). Đừng tra cứu theo
403 nữa: 403 là ca người dùng đã Start rồi CHẶN bot, còn chưa Start lần nào thì với Telegram cặp
chat này đơn giản là *không tồn tại*. Sửa bằng cách mở bot và bấm **Start**, không phải đổi token.
Cũng vì ca này mà `api()` nay **đọc body lỗi** thay vì để `urlopen` raise trần: log cũ chỉ hiện
`HTTP Error 400: Bad Request`, không cách nào biết là "chat not found" hay "can't parse entities".

**Cắm token:** `python3 .github/scripts/setup-telegram.py` — hỏi token bằng `getpass` (không in
ra màn hình), kiểm `getMe`, **chặn nếu dán nhầm token @diemtin24h_bot**, tự dò `chat_id`, gửi tin
thử, `gh secret set` qua stdin, rồi bấm chạy workflow thật và chờ kết quả. Gửi thử hỏng thì
**không đặt secret nào cả** — đặt vào là repo mang cấu hình chưa từng chạy được.

**Trạng thái cấu hình (đo thật 27/07/2026 lúc 21:20):** bảng `ren_state` + **bốn** hàm đã tạo trên
project `ltmlueqkajqmduoqghdf` (đã kiểm: push/pull/forget/tick chạy, đọc thẳng bảng bị chặn 401,
mã sai định dạng bị chặn 400). **Cả ba secret đã đặt** — `TELEGRAM_BOT_TOKEN` cắm lúc 21:08, token
hợp lệ (`getUpdates` trả ok).

⛔ **Còn HAI việc phải làm trên thiết bị, chưa xong thì tin nhắc vẫn đỏ:**
1. **Bấm Start với bot Rèn** trên Telegram — hiện `sendMessage` trả `400 chat not found`.
2. **Bật Đồng bộ trong app Rèn**, với mã trùng `REN_DEVICE_ID` (bản sao ở
   `/Users/Huy/Claude/.ren66-device-id`, 4 ký tự cuối `d52e`). Đo thật: bảng `ren_state` đang
   **rỗng hoàn toàn**, chưa có dòng nào — nên tin nhắc chỉ ra được bản rút gọn "không kéo được
   tiến độ", và **nút tick không hiện** (`nut()` trả None khi không có state, cố ý: không có
   danh sách việc thì không biết tick cái gì).

Bản sao mã đồng bộ để ở `/Users/Huy/Claude/.ren66-device-id` (chmod 600, **ngoài repo** vì repo
này public). Mất file đó mà cũng mất máy thì mất luôn nhật ký trên server — không có đường
khôi phục, vì mã chính là chìa khoá duy nhất.

### 🔘 Nút tick ngay trong tin nhắc (thêm 27/07/2026, chỉ thị Huy)

Tin nhắc 21:00 nay mang **một nút inline**: chưa đạt thì `✅ Xong hết N việc`, đạt rồi thì
`↩️ Bỏ tick hôm nay`. Bấm là ghi thẳng Supabase, không phải mở app.

**Vì sao làm:** tin nhắc cũ là MỘT CHIỀU — nhắc xong để đó, muốn tick vẫn phải mở app. Mà hồ sơ
tính cách chỉ đúng một chỗ: lỗi lõi là **ma sát lúc bị tính điểm**, không phải lười. Mỗi bước
phải làm thêm là một chỗ để bỏ cuộc. Bot sửa lại tin nhắn ngay sau khi ghi, nên nó cũng đóng
luôn vai "người thứ hai đã thấy" — thứ mà nhật ký một mình không tạo được.

| Mảnh | Việc |
|---|---|
| `nut()` trong `send_telegram.py` | Dựng bàn phím. **Một nút mỗi lúc**, `callback_data = ren:xong\|bo:YYYY-MM-DD` |
| `tick_bot.py` | Đọc callback → gọi RPC `ren_tick` → `answerCallbackQuery` + **sửa lại tin nhắc** |
| `ren_tick` (Postgres) | Ghi atomic, chỉ đụng `days[ngày].t` — xem `docs/supabase-setup.sql` |
| `tick-bot.yml` | Cron `*/5 14-17` (21:00–00:59 VN, khung hay bấm) + `*/30 * * * *` vét cả ngày |

**Năm quyết định thiết kế, đừng "dọn cho gọn" mất:**
1. **Ngày khoá cứng trong `callback_data`**, không để lúc xử lý mới suy — Huy hay bấm sau nửa
   đêm, lúc đó "hôm nay" đã sang ngày mới mà cái cần chốt vẫn là ngày của tin nhắc.
2. **Ghi qua `ren_tick` chứ tuyệt đối không đọc-sửa-`ren_push`.** `ren_push` đè cả state; app
   trên máy vừa lưu bản mới hơn là mất sạch thay đổi đó, và mất im lặng.
3. **Sửa lại tin nhắc sau khi ghi.** Job chạy theo cron nên có thể trả lời muộn vài phút, lúc đó
   dòng chớp của `answerCallbackQuery` đã hết hạn và Huy không thấy gì. Tin nhắn sửa thì nằm lại.
4. **Mọi nhánh lỗi phải NHẮN LẠI.** Bấm nút mà không hồi âm là kiểu hỏng tệ nhất ở đây: Huy
   tưởng đã chốt, thực tế không ghi được, mai mới phát hiện chuỗi đứt.
5. **`concurrency` chặn hai lịch cron trùng phút :00/:30.** Không chặn thì hai job cùng đọc một
   lô callback trước khi bên nào kịp xác nhận offset → tin nhắc bị sửa hai lần, nhìn như bot loạn.

⏱️ **Trễ tới 5 phút là đánh đổi đã biết** — poll chứ không webhook. Muốn tức thì phải có server
luôn bật, không đáng cho một nút bấm mỗi ngày.

Kiểm mà không cần token, không đụng hàng đợi thật:
```
DRY_RUN=1 REN_FAKE_UPDATES=<file.json> TELEGRAM_CHAT_ID=111222 python3 .github/scripts/tick_bot.py
```

Ba chốt an toàn trong `send_telegram.py`, giữ nguyên tinh thần khi sửa:

1. **Không** có secret nào → `exit 0` êm ("chưa cấu hình" ≠ "hỏng"). Nhưng có secret mà thiếu
   mảnh → `exit 1` cho ĐỎ; mất `REN_DEVICE_ID` thì vẫn gửi tin rút gọn trước rồi mới đỏ.
2. Supabase hỏng / chưa có dòng nào → **vẫn gửi** một tin nhắc rút gọn. App kỷ luật mà im lặng vì
   hạ tầng là hỏng đúng cái việc nó sinh ra để làm.
3. State cũ quá `STALE_HOURS` (mặc định 36) → gắn cảnh báo lên đầu tin. Báo "chuỗi 12 ngày" bằng
   dữ liệu ba ngày trước còn tệ hơn không báo, vì nó làm người ta yên tâm nhầm.
