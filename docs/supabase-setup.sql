-- Rèn · Kỷ luật 66 ngày — thiết lập Supabase cho ĐỒNG BỘ + NHẮC TELEGRAM
-- Chạy trong Supabase SQL Editor của project DÙNG CHUNG với Điểm Tin Thế Giới
-- (ltmlueqkajqmduoqghdf). Chạy lại được nhiều lần, không phá dữ liệu cũ.
--
-- VÌ SAO CẦN: app Rèn lưu toàn bộ tiến độ trong localStorage của từng trình duyệt. Không có
-- bản trên server thì GitHub Action KHÔNG THỂ biết hôm qua có tick hay không — nhắc thành ra
-- nhắc mù. Bảng này là bản sao tiến độ để Action đọc, và tiện thể là backup (README vốn cảnh
-- báo "đổi máy hoặc xoá cache là mất").
--
-- ══ MÔ HÌNH BẢO MẬT — đọc kỹ trước khi sửa ══
-- 1. Bảng KHÔNG cấp quyền gì cho `anon`/`authenticated`, và bật RLS mà KHÔNG có policy nào
--    => mọi truy cập thẳng qua PostgREST đều bị chặn. Hai đường vào duy nhất là hai hàm
--    `security definer` bên dưới.
--    Lý do làm vậy thay vì mở policy `using(true)`: PostgREST cho phép `PATCH /rest/v1/ren_state`
--    KHÔNG kèm bộ lọc, và policy `using(true)` sẽ ngoan ngoãn cho ghi đè TOÀN BỘ bảng chỉ bằng
--    một request. Đi qua hàm thì tham số bắt buộc có `p_device`, không có đường xoá sạch.
-- 2. Bí mật duy nhất là `device` — uuid v4 (122 bit ngẫu nhiên) sinh trên máy người dùng, nằm
--    trong localStorage khoá `ren.sync` và trong GitHub Secret `REN_DEVICE_ID`. Ai biết mã đó
--    thì đọc/ghi được đúng một dòng đó, không quét được bảng, không đoán được mã người khác.
--    => KHÔNG dán mã đồng bộ vào chat, ảnh chụp màn hình hay file .json gửi cho người khác.
--    (Chính vì thế mã đồng bộ để ở localStorage RIÊNG, không nằm trong state được xuất ra .json.)
-- 3. KHÔNG dùng `service_role` key ở bất kỳ đâu. Key đó là toàn quyền lên CẢ project Điểm Tin
--    (đọc được `votes`, `saved_items`, `auth.users`); nhét vào repo thứ hai chỉ để đọc một dòng
--    là mở thêm bề mặt lộ mà không được gì. Action gọi `ren_pull` bằng chính publishable key
--    vốn đã công khai trong index.html.

create table if not exists ren_state (
  device     text        primary key,
  state      jsonb       not null,
  updated_at timestamptz not null default now(),
  created_at timestamptz not null default now()
);

-- Bật RLS và KHÔNG tạo policy nào: chặn sạch đường PostgREST trực tiếp (xem ghi chú 1).
alter table ren_state enable row level security;
-- Thu hồi cả quyền bảng, phòng khi Supabase cấp mặc định cho anon ở project cũ.
revoke all on table ren_state from anon, authenticated;

-- Chốt an toàn phía ghi: chặn payload phình và tự làm mới updated_at.
-- Dùng trigger chứ không dùng CHECK vì `pg_column_size` không immutable nên không đặt được
-- trong ràng buộc CHECK; và `default now()` chỉ chạy lúc INSERT, UPDATE sẽ không tự cập nhật.
create or replace function ren_state_guard() returns trigger
language plpgsql as $$
begin
  if pg_column_size(new.state) > 512000 then
    raise exception 'ren_state: state quá lớn (% bytes, trần 512000)', pg_column_size(new.state);
  end if;
  new.updated_at := now();
  return new;
end $$;

drop trigger if exists ren_state_guard_trg on ren_state;
create trigger ren_state_guard_trg before insert or update on ren_state
  for each row execute function ren_state_guard();

-- ── ĐẨY: app gọi sau mỗi lần lưu (đã chống dội) ─────────────────────────────────────────
-- Ép đúng dạng uuid v4 để không ai bơm hàng triệu dòng rác bằng mã tự chế mà làm cạn quota.
create or replace function ren_push(p_device text, p_state jsonb)
returns timestamptz
language plpgsql security definer set search_path = public as $$
declare ts timestamptz;
begin
  if p_device !~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$' then
    raise exception 'ren_push: mã đồng bộ sai định dạng';
  end if;
  if p_state is null or jsonb_typeof(p_state) <> 'object' then
    raise exception 'ren_push: state phải là object';
  end if;
  insert into ren_state (device, state) values (p_device, p_state)
  on conflict (device) do update set state = excluded.state
  returning updated_at into ts;
  return ts;
end $$;

-- ── KÉO: app dùng khi mở máy mới, Action dùng để soạn tin nhắc ───────────────────────────
create or replace function ren_pull(p_device text)
returns table (state jsonb, updated_at timestamptz)
language sql security definer set search_path = public as $$
  select s.state, s.updated_at from ren_state s where s.device = p_device;
$$;

-- ── XOÁ: nút "Tắt và xoá bản trên máy chủ", và cả nút "Xoá sạch, làm lại" ────────────────
-- Không có hàm này thì app xoá cục bộ xong, lần mở sau `mergeState` thấy máy trắng / máy chủ
-- còn dữ liệu => kéo nguyên bản cũ về, người dùng tưởng đã xoá mà nó sống lại.
create or replace function ren_forget(p_device text)
returns void
language sql security definer set search_path = public as $$
  delete from ren_state where device = p_device;
$$;

-- Chỉ ba hàm này là cửa vào. `revoke from public` trước rồi mới grant đúng hai vai — nếu chỉ
-- grant mà quên revoke thì PUBLIC vẫn giữ quyền execute mặc định.
revoke all on function ren_push(text, jsonb) from public;
revoke all on function ren_pull(text)        from public;
revoke all on function ren_forget(text)      from public;
grant execute on function ren_push(text, jsonb) to anon, authenticated;
grant execute on function ren_pull(text)        to anon, authenticated;
grant execute on function ren_forget(text)      to anon, authenticated;
