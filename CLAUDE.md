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
| **Việc đã hẹn** (cam kết lẻ có ngày giờ) | `docs/vows-setup.sql` · `vow.py` · `vow_add.py` · `vow_bot.py` · `.github/workflows/nhac-viec-hen.yml` — xem mục 🤝 dưới |
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
   **Sửa `check_html.py` thì chạy `test-cong-html.py` (+ `--tu-kiem`)** — xem mục 🧪 TEST CHECKER
   HTML. Checker soi bài mà không ai soi checker thì nó câm lúc nào không biết.

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

### 🧪 TEST CHỐT SECRET — `.github/scripts/test-cong-secret.py` (dựng 29/07/2026)

Áp luật mục 17 CLAUDE.md toàn cục: **cổng kiểm nào cũng phải có ít nhất MỘT ca PHẢI CHẶN.**

Chốt *"chưa cấu hình ≠ cấu hình gãy"* trong `send_telegram.py:main()` là cổng loại **"hỏng thì im
lặng cho qua"**: gỡ nó ra thì mốc 21:00 vẫn XANH mỗi ngày, chỉ là không tin nào tới. Chạy thử với
đủ 3 secret KHÔNG phân biệt được cổng còn hay mất — cả hai đều xanh. Chỉ ca **cấu hình gãy → PHẢI
ĐỎ** mới phân biệt được. Đây đúng là con lỗi bắt được 27/07/2026 (run 30250807802 success 10 giây
trong khi `TELEGRAM_BOT_TOKEN` chưa từng được đặt).

```
python3 /Users/Huy/Claude/App/Ren66/.github/scripts/test-cong-secret.py
python3 /Users/Huy/Claude/App/Ren66/.github/scripts/test-cong-secret.py --tu-kiem
```
8 ca, chạy **hoàn toàn offline** (`send_all` và `fetch_state` bị thay bằng bản ghi nhận — không gọi
Telegram, không gọi Supabase): 4 ca **PHẢI ĐỎ** (mất token · mất chat · mất device — ca này vẫn phải
GỬI tin rút gọn rồi mới để đỏ · thông báo phải nêu ĐÚNG tên secret thiếu) + 4 ca chống báo oan
(chưa cấu hình gì → exit 0 · đủ 3 secret · `REN_STATE_FILE` thay được device · `DRY_RUN`).

⚠️ **TEST XANH CHƯA ĐỦ.** `--tu-kiem` dựng 4 bản `send_telegram.py` đã gỡ đúng dòng bảo vệ rồi chạy
lại bộ ca với `REN_SEND_MOD` — ca đã khai phải ĐỎ. Kết quả 29/07: **4/4 bản hỏng đều bị bắt.**
⚠️ **Khai đúng ca nào phải đỏ, đừng khai thừa.** Đã vấp một lần: bản hỏng "nuốt mã thoát" vẫn in
đúng chữ "CẤU HÌNH GÃY" nên ca soi CHỮ không thể đỏ — khai nó vào là tự báo động oan.
⚠️ **KHÔNG test bằng token giả rồi gọi Telegram thật.** `DRY_RUN` lại bỏ qua chính cái chốt cần đo
(`if not dry and thieu`), nên phải thay `send_all` trong tiến trình test — đó là lý do file test
nạp module bằng `importlib` thay vì chạy `subprocess`.

### 🧪 TEST CHECKER HTML — `.github/scripts/test-cong-html.py` (dựng 29/07/2026)

Cùng luật mục 17: `check_html.py` cũng là cổng **"hỏng thì im lặng cho qua"** — tin sạch nó in
`✓`, mà checker chết cũng in `✓` y hệt. Chạy `send_telegram.py | check_html.py` thấy toàn dấu ✓
KHÔNG chứng minh được gì. Thứ nó canh là **bẫy số 1** ở trên: `<b>` lồng `<b>` làm Telegram từ
chối CẢ tin nhắn — checker câm nghĩa là mốc 21:00 vẫn chạy, `send_all` vẫn gọi, tin không tới.

```
python3 /Users/Huy/Claude/App/Ren66/.github/scripts/test-cong-html.py
python3 /Users/Huy/Claude/App/Ren66/.github/scripts/test-cong-html.py --tu-kiem
```
**16 ca, 12 ca PHẢI CHẶN** (thẻ lồng cùng loại · thẻ chưa đóng · đóng sai thứ tự · đóng thẻ chưa
mở · thẻ Telegram không nhận · `<br/>` · `&` `<` `>` trần · **hai message cùng hỏng phải báo cả
hai** · đầu vào không có message nào · **đầu vào CỤT**) + 4 ca chống báo oan, trong đó ca quan
trọng nhất là **tin THẬT do `send_telegram.py` sinh ra bằng DRY_RUN** (đọc đầu ra thật thay vì
bịa định dạng — đúng chuỗi lệnh ở quy tắc 5).

⚠ **TEST XANH CHƯA ĐỦ.** `--tu-kiem` dựng **12 bản `check_html.py` đã gỡ đúng dòng bảo vệ** rồi
chạy lại bộ ca qua `REN_CHECK_HTML` — ca đã khai phải ĐỎ. Kết quả 29/07: **12/12 bản hỏng đều bị
bắt**, không ca nào đỏ ngoài dự kiến.
⚠ **Khai đúng ca nào phải đỏ.** Ca "không có message nào" và ca "đầu vào CỤT" thoát bằng
`sys.exit(1)` RIÊNG, nên bản hỏng *nuốt mã thoát cuối* không đụng tới chúng — khai vào là báo oan.

**Ba lỗ đã vá cùng ngày trong `check_html.py`** (đừng "dọn cho gọn" mất):
1. `all(<generator>)` **dừng ở message hỏng đầu tiên** — các message sau chưa từng được soi lần
   nào. Nay dựng list trước rồi mới `all()`.
2. **Khối `----- nút -----` bị soi như HTML.** Đó là JSON bàn phím inline, Telegram không parse
   HTML trong đó; nhãn nút có `&` hay `<` là báo oan vào message cuối. Nay cắt trước khi soi.
3. **Đầu vào CỤT thì vẫn xanh.** `send_telegram.py` chết giữa chừng thì ống dẫn còn vài khối đầu,
   soi sạch mấy cái đó không nói lên gì. Nay đối chiếu với số khai ở dòng `=== DRY_RUN — N message ===`.
   Kèm chuẩn hóa **NFC** đầu vào vì mốc cắt `----- nút -----` có dấu tiếng Việt (bài học NFD 29/07
   bên QuanSu: NFD trông y hệt NFC, khác byte, cắt trượt).

### 🤝 VIỆC ĐÃ HẸN — cam kết lẻ có ngày giờ (thêm 29/07/2026)

Chỗ nhận **một cam kết lẻ có hạn**, sinh ra cho cuối buổi `/banthan`: skill đó chốt buổi bằng
một việc nhỏ có ngày giờ, trước 29/07 nó chỉ nằm trong file `~/Claude/BanThan/*.md` — **không
có gì nhắc và không có gì đếm**, đúng điểm gãy hồ sơ tính cách mục 10 điểm 5 (*"Huy không tự
công nhận việc mình làm bền khi việc đó không được chấm điểm → phải có chỗ đếm hộ"*).

⛔ **KHÔNG BAO GIỜ nhét cam kết lẻ vào `habits`.** `isHit` tính một ngày là ĐẠT khi tick ĐỦ mọi
việc trong `habits` — thêm một việc lẻ vào là **chuỗi 66 ngày đứt oan** mỗi ngày chưa làm nó.
Thêm nữa `ren_tick` tick tất một nhát, còn việc lẻ phải tick riêng và phải tự biến mất sau khi
xong. Vì thế nó ở **bảng riêng `ren_vows`**, và không hàm nào của nó đọc/ghi `ren_state` —
hỏng ở đây không kéo theo hỏng chuỗi.

| Mảnh | Việc |
|---|---|
| `docs/vows-setup.sql` | Bảng + 4 hàm `security definer`. Cùng mô hình bảo mật `ren_state`: RLS bật, KHÔNG policy, KHÔNG grant bảng cho `anon` |
| `vow.py` | Dùng chung: gọi RPC, `can_nhac()`, soạn tin, dựng nút. `REN_VOWS_FILE` = đường kiểm offline |
| `vow_add.py` | Đẩy một cam kết (skill ban-than gọi). `--liet-ke` xem sổ + số đã giữ. `--han` hiểu "mai 21:00", "30/07", "2026-07-30 21:00" |
| `vow_bot.py` | Nhắc khi tới hạn — `nhac-viec-hen.yml`, cron `*/30 * * * *` |
| `tick_bot.py` → `xu_ly_vow()` | Nhận nút `ren:vow:<id>:<xong\|bo\|mo>` |

**Bốn quyết định, đừng "dọn cho gọn" mất:**
1. **Nút bấm đi CHUNG `tick_bot.py`, không dựng script poll thứ hai.** Bắt buộc, không phải cho
   gọn: `getUpdates` chỉ chấp nhận MỘT người đọc — hai bên cùng poll một token là nuốt update
   của nhau, Huy bấm thấy im rồi bấm lại. Cùng lý do đã tách Rèn khỏi bot Điểm Tin.
2. **Nút "🙅 Chưa làm" KHÔNG phải nút hoãn** — nó ghi lại là không giữ được. Bỏ nó đi thì cách
   duy nhất để tin im là lờ đi, mà lờ thì mẫu số chỉ còn những lần Huy làm được → con số "đã
   giữ 7/9" thành vô nghĩa, mất đúng cái chỗ đếm hộ.
3. **Nhắc lại sau 20 giờ, tối đa 5 lần rồi DỪNG.** 20 chứ không 24 vì cron GitHub trễ (bẫy số
   4) — lấy 24 là lượt hôm sau trượt sang ngày kế rồi trôi dần. Dừng ở 5 vì nhắc mãi thì Huy
   tắt thông báo, mà tắt là mất luôn tin nhắc 21:00. Sau đó cam kết để MỞ và **buổi bạn thân
   sau hỏi** — đừng tự động khai bỏ hộ, bỏ là việc Huy phải tự nói ra.
4. **Gửi hỏng thì KHÔNG ghi `ren_vow_nhac`.** Đếm là đã nhắc trong khi tin không tới = cam kết
   đó im lặng trôi mất, đúng kiểu hỏng tính năng này sinh ra để chống.
5. **`vow_bot.py` mất `REN_DEVICE_ID` thì đỏ luôn**, khác `send_telegram.py` (bên đó vẫn gửi
   được tin rút gọn có ích). Ở đây không có mã thì không biết có cam kết nào — không có gì gửi.

⚠️ Cam kết là chuyện riêng: chỉ **dòng cam kết + hạn** rời khỏi máy Huy, nội dung buổi nói
chuyện ở lại `~/Claude/BanThan/`. Repo này PUBLIC nên tuyệt đối không đưa nội dung cam kết vào
bất kỳ file nào ở đây — nó sống trong Supabase, khoá bằng mã đồng bộ.

### 🧪 TEST CỔNG VIỆC ĐÃ HẸN — `.github/scripts/test-cong-vow.py` (dựng 29/07/2026)

```
python3 /Users/Huy/Claude/App/Ren66/.github/scripts/test-cong-vow.py
python3 /Users/Huy/Claude/App/Ren66/.github/scripts/test-cong-vow.py --tu-kiem
```
**19 ca, 13 ca PHẢI CHẶN** (đã xong · đã bỏ · chưa tới hạn · chưa đủ 20 giờ · quá 5 lần · gửi
hỏng thì không đếm · escape `< & >` · cấu hình gãy → exit 1 · **Supabase lỗi thật → exit 1** ·
chat lạ · trạng thái callback lạ · hạn méo phải báo lỗi chứ không đoán · id không thuộc mã này)
+ 6 ca chống báo oan (trong đó **chưa chạy vows-setup.sql → exit 0 êm**: không tách ca này ra
thì từ lúc đẩy mã lên tới lúc dán SQL, lịch đỏ 48 lần mỗi ngày, mà cổng kêu oan liên tục thì
lần kêu thật cũng bị lờ). Chạy **hoàn toàn offline**. `--tu-kiem` dựng 9 bản code đã gỡ đúng
dòng bảo vệ: **9/9 đều bị bắt** (29/07).

⚠️ **BÀI HỌC MỚI 29/07, áp cho MỌI bộ test kiểu này (kể cả QuanSu, Báo Mới, canary):**
**ca test chạy `subprocess` một file trên đĩa thì `--tu-kiem` KHÔNG đụng tới được** — subprocess
luôn nạp bản thật, nên ca đó xanh trên cả bản đúng lẫn bản hỏng, tức là vô dụng. Chính
`--tu-kiem` bắt được (ca `escape-html` lúc đầu viết bằng subprocess). Cách vá: gọi `main()`
**trong tiến trình** rồi bắt stdout bằng `contextlib.redirect_stdout`. Riêng cái THƯỚC
(`check_html.py`) thì vẫn chạy subprocess bản thật — nó đo, nó không phải thứ bị đo.

⚠️ Phạm vi test là phần **Python**. Chốt phía SQL (regex mã, trần 300 ký tự, `device` trong
`where` của `ren_vow_set`) phải kiểm bằng đoạn lệnh cuối `docs/vows-setup.sql` — bản giả file
KHÔNG chứng minh hộ. Đừng đọc "17/17 xanh" thành "đã kiểm cả phía máy chủ".

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
