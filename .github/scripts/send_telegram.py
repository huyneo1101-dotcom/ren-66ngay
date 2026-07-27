#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Nhắc kỷ luật 66 ngày qua Telegram Bot API — chạy 21h giờ VN bằng GitHub Action.

Chạy:
    TELEGRAM_BOT_TOKEN=... TELEGRAM_CHAT_ID=... REN_DEVICE_ID=... python3 .github/scripts/send_telegram.py
    DRY_RUN=1 REN_STATE_FILE=/tmp/state.json python3 .github/scripts/send_telegram.py   # xem trước, không cần mạng

Biến môi trường:
    TELEGRAM_BOT_TOKEN  bắt buộc (trừ DRY_RUN) — token @BotFather, BOT RIÊNG của Rèn
    TELEGRAM_CHAT_ID    bắt buộc (trừ DRY_RUN) — nhiều nơi nhận thì ngăn bằng dấu phẩy
    REN_DEVICE_ID       bắt buộc — mã đồng bộ lấy trong app: Cài đặt → Đồng bộ → Copy mã
    SUPABASE_URL/KEY    tuỳ chọn — mặc định là project dùng chung với Điểm Tin
    REN_STATE_FILE      tuỳ chọn — đọc state từ file JSON thay vì gọi Supabase (để thử)
    WEB_URL             tuỳ chọn — link mở app trong tin nhắn
    STALE_HOURS         tuỳ chọn — quá bao lâu không đồng bộ thì cảnh báo số có thể cũ (36)
    DRY_RUN             =1 thì chỉ in ra màn hình

VÌ SAO PHẢI CÓ SUPABASE: app Rèn lưu tiến độ trong localStorage, server không đọc được. Không
có bản đồng bộ thì tin nhắc chỉ đếm được "hôm nay ngày thứ mấy", không biết chuỗi và không biết
hôm qua có tick hay không — tức là nhắc mù. Xem docs/supabase-setup.sql.

BA CHỐT AN TOÀN (chép tinh thần từ send_telegram.py của Điểm Tin):
 1. **CHƯA CẤU HÌNH** (không có secret nào trong ba cái) → thoát êm exit 0. Nhưng **CẤU HÌNH GÃY**
    (có secret này, mất secret kia) → exit 1 cho workflow ĐỎ. Xem `main()` để biết vì sao phải
    tách hai ca này — thoát êm cả nắm là kiểu hỏng đã bắt được thật ngày 27/07/2026.
 2. Supabase hỏng / chưa có dòng nào → VẪN GỬI một tin nhắc rút gọn rồi exit 0. App kỷ luật mà
    im lặng vì hạ tầng là hỏng đúng cái việc nó sinh ra để làm; thà nhắc thiếu số còn hơn không nhắc.
 3. State cũ quá STALE_HOURS → gắn cảnh báo lên đầu tin. Báo "chuỗi 12 ngày" bằng dữ liệu ba
    ngày trước còn tệ hơn không báo, vì nó làm người ta yên tâm nhầm.

LOGIC TÍNH PHẢI KHỚP ĐÚNG index.html — `isHit`, `streak`, `dayIx`, `rateAll` là bản dịch
nguyên văn từ JS. Sửa cách tính bên app thì phải sửa cả ở đây, không thì hai nơi ra hai con số.
"""
import datetime
import html
import json
import os
import sys
import urllib.error
import urllib.request
import zoneinfo

VN = zoneinfo.ZoneInfo("Asia/Ho_Chi_Minh")
API = "https://api.telegram.org/bot{token}/{method}"
MAX_LEN = 3800

SB_URL = os.environ.get("SUPABASE_URL", "https://ltmlueqkajqmduoqghdf.supabase.co").rstrip("/")
SB_KEY = os.environ.get("SUPABASE_KEY", "sb_publishable_74Lm6cc0CkoOOzy3A4IRrQ_BX0jHQcg")
WEB_URL = os.environ.get("WEB_URL", "https://huyneo1101-dotcom.github.io/ren-66ngay/")
CYCLE_LEN = 66


def esc(s):
    return html.escape(str(s if s is not None else ""), quote=False)


# ── đọc state ────────────────────────────────────────────────────────────────────────────
def fetch_state(device):
    """Trả (state, updated_at) — (None, None) nếu không lấy được. Không ném lỗi ra ngoài."""
    path = os.environ.get("REN_STATE_FILE", "").strip()
    if path:
        try:
            o = json.loads(open(path, encoding="utf-8").read())
        except Exception as e:
            print(f"[state] không đọc được {path}: {e}", file=sys.stderr)
            return None, None
        # Chấp cả hai dạng: state trần, hoặc bọc {state, updated_at} giống Supabase trả về.
        if isinstance(o, dict) and "state" in o and isinstance(o["state"], dict):
            return o["state"], o.get("updated_at")
        return o, None

    body = json.dumps({"p_device": device}).encode("utf-8")
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/rpc/ren_pull", data=body,
        headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}",
                 "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            rows = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"[state] Supabase {e.code}: {e.read()[:200]!r}", file=sys.stderr)
        return None, None
    except Exception as e:
        print(f"[state] không gọi được Supabase: {e}", file=sys.stderr)
        return None, None
    if not rows:
        print("[state] chưa có dòng nào cho mã đồng bộ này — app đã bật Đồng bộ chưa?",
              file=sys.stderr)
        return None, None
    row = rows[0]
    return row.get("state"), row.get("updated_at")


# ── các hàm tính, dịch nguyên văn từ index.html ──────────────────────────────────────────
def d2k(d):
    return f"{d.year:04d}-{d.month:02d}-{d.day:02d}"


def k2d(k):
    y, m, d = k.split("-")
    return datetime.date(int(y), int(m), int(d))


class Ren:
    def __init__(self, state):
        self.s = state or {}
        self.days = self.s.get("days") or {}
        self.habits = [h for h in (self.s.get("habits") or []) if h.get("id")]
        self.ids = {h["id"] for h in self.habits}
        self.need = len(self.habits)
        st = self.s.get("start")
        self.start = k2d(st) if st else None

    def rec(self, d):
        return self.days.get(d2k(d))

    def got(self, d):
        r = self.rec(d)
        if not r:
            return 0
        return len([i for i in (r.get("t") or []) if i in self.ids])

    def hit(self, d):
        """`isHit` trong app: ngày 'băng' (crisis) chỉ cần 1 việc, ngày thường phải đủ hết."""
        r = self.rec(d)
        if not r:
            return False
        n = self.got(d)
        return n >= 1 if r.get("crisis") else (n > 0 and n >= self.need)

    def streak(self, today):
        """Hôm nay chưa đạt thì đếm lùi từ hôm qua — chuỗi chưa đứt, chỉ là chưa chốt."""
        k = today if self.hit(today) else today - datetime.timedelta(days=1)
        n = 0
        while self.hit(k) and n < 4000:
            n += 1
            k -= datetime.timedelta(days=1)
        return n

    def longest(self, today):
        if not self.start:
            return 0
        best = cur = 0
        k = self.start
        while k <= today:
            cur = cur + 1 if self.hit(k) else 0
            best = max(best, cur)
            k += datetime.timedelta(days=1)
        return best

    def day_ix(self, today):
        return (today - self.start).days + 1 if self.start else 0

    def rate(self, today):
        if not self.start:
            return 0
        n = min((today - self.start).days + 1, CYCLE_LEN)
        h = sum(1 for i in range(n) if self.hit(self.start + datetime.timedelta(days=i)))
        return round(h / n * 100) if n else 0

    def snooze_week(self, today):
        return sum((self.rec(today - datetime.timedelta(days=i)) or {}).get("snz") or 0
                   for i in range(7))

    def missing(self, d):
        r = self.rec(d) or {}
        done = set(r.get("t") or [])
        return [h for h in self.habits if h["id"] not in done]


# ── soạn tin ─────────────────────────────────────────────────────────────────────────────
def stale_line(updated_at, now):
    """Cảnh báo khi bản đồng bộ quá cũ — chống báo số đẹp bằng dữ liệu chết."""
    if not updated_at:
        return ""
    try:
        ts = updated_at.replace("Z", "+00:00")
        if "." in ts:                      # Postgres trả 6 chữ số micro, đôi khi hơn
            head, tail = ts.split(".", 1)
            frac = "".join(c for c in tail if c.isdigit())[:6]
            rest = tail[len(frac):] if tail[len(frac):].startswith(("+", "-")) else "+00:00"
            ts = f"{head}.{frac}{rest}"
        t = datetime.datetime.fromisoformat(ts)
    except Exception as e:
        print(f"[stale] không đọc được updated_at {updated_at!r}: {e}", file=sys.stderr)
        return ""
    hours = (now - t).total_seconds() / 3600
    limit = float(os.environ.get("STALE_HOURS", "36"))
    if hours < limit:
        return ""
    return (f"⚠️ <i>App chưa đồng bộ {int(hours)} giờ (lần cuối "
            f"{t.astimezone(VN):%H:%M %d/%m}) — số dưới đây có thể cũ.</i>\n")


def build(state, updated_at, now):
    today = now.date()
    yday = today - datetime.timedelta(days=1)
    link = f'\n\n<a href="{esc(WEB_URL)}">Mở Rèn</a>'
    warn = stale_line(updated_at, now)

    if state is None:
        return [f"🔥 <b>Rèn — nhắc chốt ngày</b>\n"
                f"Không kéo được tiến độ (app chưa bật Đồng bộ, hoặc máy chủ đang hỏng). "
                f"Cứ mở app chốt ngày đã.{link}"]

    r = Ren(state)
    if not r.start or not r.need:
        return [f"🔥 <b>Rèn</b>\nChưa đặt việc nào để rèn — mở app chọn việc đầu tiên "
                f"rồi ngày 1 mới bắt đầu đếm.{link}"]

    di = r.day_ix(today)
    cyc = r.s.get("cycle") or 1
    # KHÔNG bọc <b> ở đây: dòng tiêu đề đã nằm trong <b>, mà Telegram từ chối cả tin nhắn
    # (HTTP 400 "can't parse entities") khi gặp hai thẻ <b> lồng nhau.
    head = f"Ngày {di}/{CYCLE_LEN}" + (f" · vòng {cyc}" if cyc > 1 else "")
    st, lg, rate = r.streak(today), r.longest(today), r.rate(today)
    done_today = r.hit(today)

    if di > CYCLE_LEN:
        return [f"{warn}🏁 <b>Rèn — hết vòng {cyc}</b>\n"
                f"Đã qua ngày {di}, vòng {CYCLE_LEN} ngày kết thúc. Tỉ lệ đạt {rate}% · "
                f"chuỗi dài nhất {lg} ngày.\nMở app khai vòng mới từ hôm nay.{link}"]

    lines = [f"{warn}{'✅' if done_today else '🔥'} <b>Rèn · {head}</b>",
             f"Chuỗi <b>{st} ngày</b> · dài nhất {lg} · đạt {rate}%"]

    if done_today:
        n = r.got(today)
        lines.append(f"Hôm nay xong {n}/{r.need} việc. Chuỗi giữ nguyên — ngủ ngon.")
        return [ "\n".join(lines) + link ]

    miss = r.missing(today)
    lines.append(f"\nCòn <b>{len(miss)}/{r.need}</b> việc chưa tick:")
    for h in miss:
        mins = h.get("mins")
        lines.append(f"• {esc(h.get('name'))}" + (f" <i>({mins} phút)</i>" if mins else ""))

    if yday >= r.start:
        if r.hit(yday):
            lines.append(f"\nHôm qua: ✅ đạt ({r.got(yday)}/{r.need} việc).")
        else:
            lines.append(f"\nHôm qua: ❌ trượt ({r.got(yday)}/{r.need} việc) — "
                         f"đừng để hai ngày liền.")

    snz = r.snooze_week(today)
    if snz:
        lines.append(f"Đã hoãn {snz} lần trong 7 ngày qua.")
    if r.need > 1:
        lines.append("<i>Ngày đuối thì bật băng giữ chuỗi: làm một việc là chuỗi không đứt.</i>")

    return [ "\n".join(lines) + link ]


# ── gửi ──────────────────────────────────────────────────────────────────────────────────
def api(token, method, payload):
    req = urllib.request.Request(
        API.format(token=token, method=method),
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def send_all(token, chats, msgs):
    rc = 0
    for chat in chats:
        for m in msgs:
            try:
                res = api(token, "sendMessage", {
                    "chat_id": chat, "text": m, "parse_mode": "HTML",
                    "disable_web_page_preview": True})
            except Exception as e:
                print(f"LỖI sendMessage tới {chat}: {e}", file=sys.stderr)
                rc = 1
                continue
            if not res.get("ok"):
                print(f"LỖI sendMessage tới {chat}: {res}", file=sys.stderr)
                rc = 1
        if rc == 0:
            print(f"Đã gửi {len(msgs)} message tới {chat}")
    return rc


def main():
    dry = os.environ.get("DRY_RUN") == "1"
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chats = [c.strip() for c in os.environ.get("TELEGRAM_CHAT_ID", "").split(",") if c.strip()]
    device = os.environ.get("REN_DEVICE_ID", "").strip().lower()
    state_file = os.environ.get("REN_STATE_FILE", "").strip()

    # ── CHƯA CẤU HÌNH ≠ CẤU HÌNH GÃY ─────────────────────────────────────────────────────
    # Thoát êm chỉ đúng ở vế đầu: repo mới, chưa ai đặt secret lần nào — không có gì để hỏng.
    # Đã có dấu vết cấu hình mà thiếu một mảnh thì đó là SỰ CỐ (secret bị xoá, bot bị /revoke,
    # gõ nhầm tên secret), và im lặng ở đây là kiểu hỏng tệ nhất: mốc 21:00 chạy XANH hằng ngày
    # mà không một tin nào tới. Bắt được thật 27/07/2026 — TELEGRAM_BOT_TOKEN chưa từng được
    # đặt, run 30250807802 vẫn success 10 giây, không ai biết cho tới khi soi log.
    thieu = ([] if token else ["TELEGRAM_BOT_TOKEN"]) \
        + ([] if chats else ["TELEGRAM_CHAT_ID"]) \
        + ([] if (device or state_file) else ["REN_DEVICE_ID"])

    if not dry and thieu:
        if not (token or chats or device):
            print("Chưa đặt secret nào (TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID/REN_DEVICE_ID) — "
                  "chưa cấu hình, bỏ qua, KHÔNG coi là lỗi.", file=sys.stderr)
            return 0
        print("❌ CẤU HÌNH GÃY — đã có secret nhưng THIẾU: " + ", ".join(thieu)
              + "\n   Đặt lại bằng: python3 .github/scripts/setup-telegram.py", file=sys.stderr)
        if not token or not chats:
            # Không còn đường gửi → chỉ còn cách kêu bằng job đỏ.
            return 1
        # Còn gửi được thì VẪN GỬI tin rút gọn (chốt 2), nhưng cuối cùng vẫn để đỏ.

    state, updated_at = (fetch_state(device) if (device or state_file) else (None, None))
    msgs = build(state, updated_at, datetime.datetime.now(VN))
    msgs = [m if len(m) <= MAX_LEN else m[:MAX_LEN - 1] + "…" for m in msgs]

    if dry:
        print(f"=== DRY_RUN — {len(msgs)} message ===")
        for i, m in enumerate(msgs, 1):
            print(f"\n----- message {i}/{len(msgs)} ({len(m)} ký tự) -----")
            print(m)
        return 0
    # `thieu` còn sót ở đây nghĩa là mất REN_DEVICE_ID: tin vẫn gửi được (bản rút gọn) nhưng
    # cấu hình đang gãy — gửi xong rồi mới để job đỏ, không nuốt.
    return send_all(token, chats, msgs) or (1 if thieu else 0)


if __name__ == "__main__":
    sys.exit(main())
