-- ═══════════════════════════════════════════════════════════════════════════════════════
-- VIỆC ĐÃ HẸN — bảng cam kết lẻ có hạn ngày giờ
-- Chạy một lần trong SQL Editor của project ltmlueqkajqmduoqghdf (dùng chung với Điểm Tin).
-- ═══════════════════════════════════════════════════════════════════════════════════════
--
-- VÌ SAO PHẢI CÓ BẢNG RIÊNG, KHÔNG NHÉT VÀO `ren_state`:
--   `ren_state.state.habits` là các việc LẶP HẰNG NGÀY, và `isHit` (bên index.html cũng như
--   bản dịch trong send_telegram.py) tính một ngày là ĐẠT khi tick ĐỦ MỌI việc trong `habits`.
--   Nhét một việc lẻ vào đó thì ngày nào chưa làm nó là chuỗi 66 ngày đứt oan — hỏng đúng cái
--   đang chạy để nhét việc khác vào. Thêm nữa `ren_tick` tick tất một nhát, còn việc lẻ thì
--   phải tick riêng, và phải TỰ BIẾN MẤT sau khi xong. Ba thứ đó đều trái với `habits`.
--   Bảng riêng nghĩa là rủi ro với chuỗi 66 ngày bằng KHÔNG: không hàm nào dưới đây đọc hay
--   ghi `ren_state`.
--
-- MÔ HÌNH BẢO MẬT — chép nguyên tinh thần của supabase-setup.sql, đừng nới:
--   • RLS BẬT mà KHÔNG có policy nào, và KHÔNG cấp quyền bảng cho `anon`. Cố ý: PostgREST cho
--     phép `PATCH /rest/v1/ren_vows` **không kèm bộ lọc**, một policy `using(true)` sẽ ngoan
--     ngoãn cho ghi đè cả bảng bằng đúng một request. Đi qua hàm thì bắt buộc có `p_device`.
--   • Mã đồng bộ (uuid v4) là bí mật DUY NHẤT. Ai biết mã thì đọc được mọi cam kết. Dùng chung
--     mã với `ren_state` là cố ý — thêm một bí mật nữa chỉ để quản thêm một chỗ mất.
--   • Tuyệt đối KHÔNG dùng `service_role` key: key đó toàn quyền lên cả project Điểm Tin.

create table if not exists ren_vows (
  id         bigint generated always as identity primary key,
  device     text        not null,
  viec       text        not null,
  han        timestamptz not null,
  xong_at    timestamptz,          -- null = chưa làm
  bo_at      timestamptz,          -- null = chưa khai bỏ. Khai bỏ ≠ xong: nó DỪNG nhắc mà vẫn
                                   -- đếm là không giữ được. Im lặng cho trôi thì mất số thật.
  nhac_lan   int         not null default 0,
  nhac_cuoi  timestamptz,
  created_at timestamptz not null default now()
);

create index if not exists ren_vows_device_han on ren_vows (device, han);

alter table ren_vows enable row level security;
revoke all on ren_vows from anon, authenticated;

-- Trần độ dài, chặn ngay ở tầng DB chứ không chỉ ở script: script sửa được, bảng thì không.
create or replace function ren_vows_guard() returns trigger
language plpgsql as $$
begin
  if length(new.viec) > 300 then
    raise exception 'ren_vows: cam kết quá dài (% ký tự, trần 300)', length(new.viec);
  end if;
  return new;
end $$;

drop trigger if exists trg_ren_vows_guard on ren_vows;
create trigger trg_ren_vows_guard before insert or update on ren_vows
  for each row execute function ren_vows_guard();


-- ── thêm một cam kết ────────────────────────────────────────────────────────────────────
create or replace function ren_vow_add(p_device text, p_viec text, p_han timestamptz)
returns bigint
language plpgsql security definer set search_path = public as $$
declare
  v_id  bigint;
  v_mo  int;
  v_txt text := btrim(coalesce(p_viec, ''));
begin
  if p_device !~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$' then
    raise exception 'ren_vow_add: mã đồng bộ sai định dạng';
  end if;
  if v_txt = '' then
    raise exception 'ren_vow_add: cam kết rỗng';
  end if;
  if p_han is null then
    raise exception 'ren_vow_add: thiếu hạn';
  end if;
  -- Hạn quá xa quá khứ là dấu hiệu gõ nhầm năm; quá xa tương lai thì nhắc chẳng còn nghĩa gì.
  if p_han < now() - interval '30 days' or p_han > now() + interval '2 years' then
    raise exception 'ren_vow_add: hạn ngoài khoảng cho phép (%)', p_han;
  end if;
  -- Trần số cam kết ĐANG MỞ. Không có trần thì một script lặp sai đẩy được vô hạn dòng vào
  -- bảng, và tin nhắc biến thành một bức tường — vừa tốn vừa làm Huy tắt luôn thông báo.
  select count(*) into v_mo from ren_vows
   where device = p_device and xong_at is null and bo_at is null;
  if v_mo >= 50 then
    raise exception 'ren_vow_add: đang có % cam kết chưa chốt, dọn bớt đã', v_mo;
  end if;

  insert into ren_vows (device, viec, han) values (p_device, v_txt, p_han)
  returning id into v_id;
  return v_id;
end $$;


-- ── đọc danh sách ───────────────────────────────────────────────────────────────────────
-- Trả CẢ cam kết đã chốt (trong 180 ngày) chứ không chỉ cái đang mở: con số "đã giữ 7/9" là
-- lý do tính năng này tồn tại — hồ sơ tính cách mục 10 điểm 5, "phải có chỗ đếm hộ".
create or replace function ren_vow_list(p_device text)
returns table (id bigint, viec text, han timestamptz, xong_at timestamptz,
               bo_at timestamptz, nhac_lan int, nhac_cuoi timestamptz)
language plpgsql security definer set search_path = public as $$
begin
  if p_device !~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$' then
    raise exception 'ren_vow_list: mã đồng bộ sai định dạng';
  end if;
  return query
    select v.id, v.viec, v.han, v.xong_at, v.bo_at, v.nhac_lan, v.nhac_cuoi
      from ren_vows v
     where v.device = p_device
       and (v.xong_at is null and v.bo_at is null or v.han > now() - interval '180 days')
     order by v.han
     limit 500;
end $$;


-- ── chốt / khai bỏ / mở lại ─────────────────────────────────────────────────────────────
-- MỘT hàm cho cả ba, và ghi ATOMIC. Đừng tách thành đọc-rồi-ghi ở phía script: hai job cron
-- trùng phút sẽ đọc cùng một trạng thái cũ rồi ghi đè nhau (đúng bẫy số 2 của CLAUDE.md, chỉ
-- khác chỗ nạn nhân). `p_trang_thai` = 'xong' | 'bo' | 'mo'.
create or replace function ren_vow_set(p_device text, p_id bigint, p_trang_thai text)
returns table (viec text, han timestamptz, xong_at timestamptz, bo_at timestamptz,
               giu int, tong int)
language plpgsql security definer set search_path = public as $$
declare
  v_row ren_vows;
begin
  if p_device !~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$' then
    raise exception 'ren_vow_set: mã đồng bộ sai định dạng';
  end if;
  if p_trang_thai not in ('xong', 'bo', 'mo') then
    raise exception 'ren_vow_set: trạng thái lạ (%)', p_trang_thai;
  end if;

  update ren_vows v
     set xong_at = case when p_trang_thai = 'xong' then now() else null end,
         bo_at   = case when p_trang_thai = 'bo'   then now() else null end
   where v.id = p_id and v.device = p_device      -- `device` trong mệnh đề là chốt phân quyền:
   returning v.* into v_row;                      -- biết id mà không biết mã thì không sửa được
  if not found then
    raise exception 'ren_vow_set: không có cam kết id % của mã này', p_id;
  end if;

  select count(*) filter (where v.xong_at is not null),
         count(*) filter (where v.xong_at is not null or v.bo_at is not null)
    into giu, tong
    from ren_vows v where v.device = p_device;

  viec := v_row.viec; han := v_row.han;
  xong_at := v_row.xong_at; bo_at := v_row.bo_at;
  return next;
end $$;


-- ── ghi nhận đã nhắc ────────────────────────────────────────────────────────────────────
-- Gọi SAU khi gửi thành công. Ghi trước rồi gửi hỏng là mất luôn lượt nhắc đó mà không ai biết;
-- gửi trước rồi ghi hỏng thì cùng lắm nhắc lại — hỏng theo chiều làm phiền còn hơn hỏng theo
-- chiều im lặng, vì im lặng đúng là thứ tính năng này sinh ra để chống.
create or replace function ren_vow_nhac(p_device text, p_id bigint)
returns int
language plpgsql security definer set search_path = public as $$
declare v_lan int;
begin
  if p_device !~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$' then
    raise exception 'ren_vow_nhac: mã đồng bộ sai định dạng';
  end if;
  update ren_vows v set nhac_lan = v.nhac_lan + 1, nhac_cuoi = now()
   where v.id = p_id and v.device = p_device
   returning v.nhac_lan into v_lan;
  if not found then
    raise exception 'ren_vow_nhac: không có cam kết id % của mã này', p_id;
  end if;
  return v_lan;
end $$;


-- Chỉ cấp quyền CHẠY HÀM, không cấp quyền bảng.
grant execute on function ren_vow_add(text, text, timestamptz)  to anon, authenticated;
grant execute on function ren_vow_list(text)                    to anon, authenticated;
grant execute on function ren_vow_set(text, bigint, text)       to anon, authenticated;
grant execute on function ren_vow_nhac(text, bigint)            to anon, authenticated;

-- Kiểm nhanh sau khi chạy (thay <mã> bằng mã đồng bộ thật):
--   select ren_vow_add('<mã>', 'thử một cam kết', now() + interval '1 minute');
--   select * from ren_vow_list('<mã>');
--   select * from ren_vow_set('<mã>', <id>, 'xong');
-- Và kiểm cả hai chốt PHẢI CHẶN:
--   select ren_vow_add('khong-phai-uuid', 'x', now());   -- phải LỖI
--   select * from ren_vow_set('<mã khác>', <id>, 'xong'); -- phải LỖI "không có cam kết id …"
