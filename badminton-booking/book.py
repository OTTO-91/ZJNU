# -*- coding: utf-8 -*-
"""ZJNU Court Auto-Booking
Multi-campus, multi-sport court auto-booking.
First run: enter credentials, choose campus & sport.
Usage: python book.py           # auto-book
       python book.py --scan    # scan only
       python book.py --setup   # re-configure
"""
import argparse, base64, json, logging, os, pickle, random, string, sys, time
from datetime import datetime, timedelta
from pathlib import Path
import urllib.parse
import requests
import execjs
from pathlib import Path
from bs4 import BeautifulSoup

# ── Paths ──
# Load CryptoJS from ez.js (same as zjnu.py)
DIR = Path(__file__).parent.resolve()
_EZJS = execjs.compile((DIR / "ez.js").read_text("utf-8"))
ENV_FILE = DIR / ".env"
SESS_PKL = DIR / "session.pkl"
LOG_FILE = DIR / "booking.log"
LAST_BOOKING = DIR / "last_booking.json"

# ── Constants ──
CAS_URL = "http://authserver.zjnu.edu.cn:80/authserver/login"
CAS_SVC = "https://tycg.zjnu.edu.cn/api/cas_auth/auth"
BASE = "https://tycg.zjnu.edu.cn"

# ── Court Registry ──
COURT_REGISTRY = {
    "xiaoshan": {
        "badminton": [
            {"id": 92, "name": "浙师大萧山校区热身馆（羽毛球）", "goods_id": "92"},
        ]
    },
    "jinhua": {
        "badminton": [
            {"id": 87, "name": "北田羽毛球馆", "goods_id": "87"},
            {"id": 84, "name": "综合馆羽毛球馆", "goods_id": "84"},
        ],
        "pingpong": [
            {"id": 86, "name": "风雨操场乒乓球馆", "goods_id": "86"},
        ],
        "volleyball": [
            {"id": 85, "name": "风雨操场排球馆", "goods_id": "85"},
        ],
    },
}

CAMPUS_CHOICES = {"1": "jinhua", "2": "xiaoshan"}
SPORT_CHOICES = {"1": "badminton", "2": "pingpong", "3": "volleyball"}
SPORT_LABELS = {"badminton": "羽毛球", "pingpong": "乒乓球", "volleyball": "排球"}
CAMPUS_LABELS = {"jinhua": "金华校区", "xiaoshan": "萧山校区"}

DAY_OFFSET = 1
DELAY = 2.0

# ── Logging ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8"),
              logging.StreamHandler()])
log = logging.getLogger("book")

# ── Credentials ──
def load_env():
    env = {}
    if ENV_FILE.exists():
        text = ENV_FILE.read_text(encoding="utf-8")
        if text.startswith("﻿"):
            text = text[1:]
        for line in text.splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip("'").strip('"')
    return env

def setup_env():
    print("=" * 50)
    print("  浙江师范大学 体育场地自动预约")
    print("  首次使用，请完成配置")
    print("=" * 50)
    print()

    username = input("学号 (Student ID): ").strip()
    password = input("密码 (Password): ").strip()
    if not username or not password:
        print("错误：学号和密码不能为空")
        sys.exit(1)

    print()
    print("请选择校区:")
    print("  [1] 金华校区")
    print("  [2] 萧山校区")
    campus_choice = input("输入序号 (1/2): ").strip()
    campus = CAMPUS_CHOICES.get(campus_choice)
    if not campus:
        print("错误：无效选择")
        sys.exit(1)

    sport = "badminton"  # default
    if campus == "jinhua":
        print()
        print("请选择运动项目:")
        print("  [1] 羽毛球")
        print("  [2] 乒乓球")
        print("  [3] 排球")
        sport_choice = input("输入序号 (1/2/3): ").strip()
        sport = SPORT_CHOICES.get(sport_choice)
        if not sport:
            print("错误：无效选择")
            sys.exit(1)

    courts = COURT_REGISTRY[campus][sport]
    court_names = ", ".join(c["name"] for c in courts)
    print()
    print(f"校区: {CAMPUS_LABELS[campus]}")
    print(f"项目: {SPORT_LABELS[sport]}")
    print(f"场地: {court_names}")

    ENV_FILE.write_text(
        f"ZJNU_USERNAME={username}\n"
        f"ZJNU_PASSWORD={password}\n"
        f"ZJNU_CAMPUS={campus}\n"
        f"ZJNU_SPORT={sport}\n",
        encoding="utf-8")
    print(f"\n✅ 配置已保存到 {ENV_FILE.name}")
    return {"ZJNU_USERNAME": username, "ZJNU_PASSWORD": password, "ZJNU_CAMPUS": campus, "ZJNU_SPORT": sport}

def get_credentials():
    env = load_env()
    if "ZJNU_USERNAME" in env and "ZJNU_PASSWORD" in env:
        return env["ZJNU_USERNAME"], env["ZJNU_PASSWORD"]
    env = setup_env()
    return env["ZJNU_USERNAME"], env["ZJNU_PASSWORD"]

def get_courts():
    env = load_env()
    campus = env.get("ZJNU_CAMPUS", "jinhua")
    sport = env.get("ZJNU_SPORT", "badminton")
    return COURT_REGISTRY[campus][sport]

# ── AES ──
def encrypt_password(pwd, salt):
    if not salt: return pwd
    return _EZJS.call("encryptPassword", pwd, salt)
class Session:
    def __init__(self):
        self.s = requests.Session()
        self.s.headers["User-Agent"] = "Mozilla/5.0 (X11; Linux x86_64) Chrome/120"
        self.tok = ""
    def load(self):
        if not SESS_PKL.exists(): return False
        d = pickle.load(open(SESS_PKL, "rb"))
        self.s.cookies.update(d.get("cookies", {}))
        self.tok = d.get("token", "")
        return True
    def save(self):
        pickle.dump({"cookies": self.s.cookies, "token": self.tok,
                      "saved_at": datetime.now().isoformat()}, open(SESS_PKL, "wb"))
    def login(self, username, password):
        log.info("=== CAS Login ===")
        r = self.s.get(CAS_URL, params={"service": CAS_SVC}, timeout=15)
        soup = BeautifulSoup(r.text, "lxml")
        salt = (soup.find("input", {"id": "pwdEncryptSalt"}) or {}).get("value", "")
        if not salt: raise RuntimeError("Cannot get encryption salt")
        exe = (soup.find("input", {"id": "execution"}) or {}).get("value", "e1s1")
        enc_pwd = encrypt_password(password, salt)
        data = {"username": username, "password": enc_pwd,
                "_eventId": "submit", "cllt": "userNameLogin",
                "dllt": "generalLogin", "execution": exe}
        r = self.s.post(CAS_URL + "?service=" + requests.utils.quote(CAS_SVC),
            data=data, allow_redirects=True, timeout=15)
        if "authserver" in r.url:
            raise RuntimeError("Login failed, check credentials")
        fragment = urllib.parse.urlparse(r.url).fragment
        if "?" in fragment:
            params = urllib.parse.parse_qs(fragment.split("?")[1])
            self.tok = params.get("token", [""])[0]
        if not self.tok:
            raise RuntimeError("Cannot extract token after login")
        log.info("Login OK"); self.save()
    def _h(self): return {"Authorization": self.tok} if self.tok else {}
    def _req(self, m, path, **kw):
        try:
            r = self.s.request(m, BASE + path, headers=self._h(), timeout=10, **kw)
            return r.json() if r.text.strip().startswith("{") else None
        except Exception: return None
    def get(self, p, **kw): return self._req("GET", p, params=kw.get("p"))
    def post(self, p, d=None): return self._req("POST", p, json=d)

# ── Scan ──
def scan_court(sess, court, day_offset=DAY_OFFSET):
    cid = court["id"]
    target = (datetime.now() + timedelta(days=day_offset)).strftime("%Y-%m-%d")
    f_resp = sess.get(f"/api/court/getFieldNoList?product_id={cid}")
    if not f_resp or f_resp.get("code") != 1:
        log.warning(f"{court['name']}: cannot get fields")
        return []
    fields = f_resp["data"]["result"]
    p_resp = sess.get(f"/api/court/getCourtPrice?product_id={cid}&venue_id={cid}&date={target}")
    if not p_resp or p_resp.get("code") != 1:
        log.warning(f"{court['name']}: cannot get prices")
        return []
    slots = p_resp["data"]["result"]
    available = []
    for slot in slots:
        for i, fl in enumerate(slot["fieldlist_s"]):
            if not (fl.get("field_id") and fl.get("text")):
                continue
            available.append({
                "court": court['name'],
                "goods_id": court['goods_id'],
                "date": target,
                "start_time": slot["start_time"],
                "end_time": slot["end_time"],
                "time_id": slot["id"],
                "meal_id": slot["meal_id"],
                "field_id": fl["field_id"],
                "field_no": fields[i]["seat_number"],
                "price_id": fl["price_id"],
            })
    return available

def _time_to_min(t):
    parts = t.split(":")
    return int(parts[0]) * 60 + int(parts[1])

# ── Book ──
def do_book(sess, courts):
    target = (datetime.now() + timedelta(days=DAY_OFFSET)).strftime("%Y-%m-%d")
    # Check if already booked for this date
    if LAST_BOOKING.exists():
        try:
            lb = json.loads(LAST_BOOKING.read_text("utf-8"))
            if lb.get("date") == target:
                log.info(f"Already booked {target}: {lb.get("court")} {lb.get("time")} #{lb.get("field")}")
                log.info("Skipping - each court allows only 1 booking per day")
                return True
        except:
            pass
    log.info(f"Scanning courts for {target}")
    all_slots = []
    for court in courts:
        slots = scan_court(sess, court)
        log.info(f"  {court['name']}: {len(slots)} available slots")
        all_slots.extend(slots)
    if not all_slots:
        log.warning("No available slots!")
        return False
    court_rank = {c["name"]: i for i, c in enumerate(courts)}
    all_slots.sort(key=lambda s: (-_time_to_min(s['start_time']), court_rank.get(s['court'], 99)))
    log.info("Top candidates:")
    for s in all_slots[:10]:
        log.info(f"  {s['court']} {s['start_time']}-{s['end_time']} #{s['field_no']}")
    for i, s in enumerate(all_slots):
        body = {
            "goods_id": s['goods_id'],
            "order_type": 3, "pay_way": "0",
            "other_param": json.dumps({
                "price_ids": str(s['price_id']),
                "time_ids": str(s['time_id']),
                "field_ids": str(s['field_id']),
                "price": "0.00", "court_id": s['goods_id'],
                "meal_id": s['meal_id'], "field_type": "1",
            }, ensure_ascii=False),
            "choose_date": s['date'],
        }
        r = sess.post("/api/pay/CreateOrder", d=body)
        if not r: continue
        code = r.get("code")
        info = r.get("info", "")
        log.info(f"[{i+1}/{len(all_slots)}] {s['court']} {s['start_time']} #{s['field_no']}: code={code} {str(info)[:80]}")
        if code == 1:
            log.info("*** BOOKING SUCCESS! ***")
            log.info(f"  Court: {s['court']}")
            log.info(f"  Date:  {s['date']}")
            log.info(f"  Time:  {s['start_time']}-{s['end_time']}")
            log.info(f"  Field: #{s['field_no']}")
            return True
        time.sleep(DELAY)
    log.warning("All slots exhausted, no booking made.")
    return False

# ── Scan-only ──
def do_scan(sess, courts):
    target = (datetime.now() + timedelta(days=DAY_OFFSET)).strftime("%Y-%m-%d")
    print(f"\n=== {target} Available Courts ===\n")
    for court in courts:
        slots = scan_court(sess, court)
        print(f"{court['name']}: {len(slots)} slots")
        for s in slots:
            print(f"  {s['start_time']}-{s['end_time']}  #{s['field_no']}")
        print()

# ── Main ──
def main():
    parser = argparse.ArgumentParser(description="ZJNU Court Auto-Booking")
    parser.add_argument("--scan", action="store_true", help="Scan only, do not book")
    parser.add_argument("--loop", action="store_true", help="Wait until 7:00 then book once (for cron)")
    parser.add_argument("--setup", action="store_true", help="Re-configure credentials & courts")
    args = parser.parse_args()
    if args.setup:
        if ENV_FILE.exists(): ENV_FILE.unlink()
        if SESS_PKL.exists(): SESS_PKL.unlink()
    username, password = get_credentials()
    courts = get_courts()
    sess = Session()
    if not sess.load() or not sess.tok:
        log.info("No valid session, logging in...")
        try:
            sess.login(username, password)
        except RuntimeError as e:
            log.error(str(e))
            sys.exit(1)
    if args.scan:
        do_scan(sess, courts)
    elif args.loop:
        from datetime import datetime as dt
        target_date = (dt.now() + timedelta(days=DAY_OFFSET)).strftime("%Y-%m-%d")
        # Phase 1: pre-fetch everything at 6:55
        log.info("=== Loop mode: pre-fetching all data ===")
        all_payloads = []
        for court in courts:
            cid = court["id"]
            f_resp = sess.get(f"/api/court/getFieldNoList?product_id={cid}")
            p_resp = sess.get(f"/api/court/getCourtPrice?product_id={cid}&venue_id={cid}&date={target_date}")
            if not f_resp or f_resp.get("code") != 1:
                continue
            if not p_resp or p_resp.get("code") != 1:
                continue
            fields = f_resp["data"]["result"]
            slots = p_resp["data"]["result"]
            count = 0
            for slot in slots:
                for i, fl in enumerate(slot["fieldlist_s"]):
                    if not (fl.get("text") and fl.get("field_id")):
                        continue
                    count += 1
                    all_payloads.append({
                        "court": court["name"],
                        "goods_id": court["goods_id"],
                        "date": target_date,
                        "start_time": slot["start_time"],
                        "end_time": slot["end_time"],
                        "field_no": fields[i]["seat_number"] if i < len(fields) else "?",
                        "body": {
                            "goods_id": court["goods_id"],
                            "order_type": 3, "pay_way": "0",
                            "other_param": json.dumps({
                                "price_ids": str(fl["price_id"]),
                                "time_ids": str(slot["id"]),
                                "field_ids": str(fl["field_id"]),
                                "price": "0.00",
                                "court_id": court["goods_id"],
                                "meal_id": slot["meal_id"],
                                "field_type": "1",
                            }, ensure_ascii=False),
                            "choose_date": target_date,
                        },
                    })
            log.info(f"  {court['name']}: {count} bookable slots pre-built")
        if not all_payloads:
            log.warning("No bookable slots at all!")
            sys.exit(1)
        court_rank = {c["name"]: i for i, c in enumerate(courts)}
        all_payloads.sort(key=lambda p: (-_time_to_min(p["start_time"]), court_rank.get(p["court"], 99)))
        log.info(f"Total {len(all_payloads)} pre-built payloads, best: {all_payloads[0]['court']} {all_payloads[0]['start_time']} #{all_payloads[0]['field_no']}")
        # Phase 2: wait until 07:00:00.000
        now = dt.now()
        target = now.replace(hour=7, minute=0, second=0, microsecond=0)
        if now < target:
            wait = (target - now).total_seconds()
            log.info(f"Waiting {wait:.0f}s until 07:00:00.000")
            if wait > 1.5:
                time.sleep(wait - 1.5)
            while dt.now() < target:
                pass
        # Phase 3: fire CreateOrder at exactly 07:00:00
        t_fire = dt.now()
        log.info(f"FIRE at {t_fire.strftime('%H:%M:%S.%f')[:15]}")
        for i, p in enumerate(all_payloads):
            r = sess.post("/api/pay/CreateOrder", p["body"])
            code = r.get("code") if r else -1
            info = r.get("info", "") if r else ""
            elapsed = (dt.now() - t_fire).total_seconds()
            log.info(f"[{i+1}] {p['court']} {p['start_time']} #{p['field_no']}: code={code} delay={elapsed:.2f}s {str(info)[:60]}")
            if code == 1:
                log.info("*** BOOKING SUCCESS! ***")
                log.info(f"  {p['court']} {p['start_time']}-{p['end_time']} #{p['field_no']}")
                LAST_BOOKING.write_text(json.dumps({
                    "date": target_date,
                    "court": p["court"],
                    "time": f"{p["start_time"]}-{p["end_time"]}",
                    "field": p["field_no"],
                }, ensure_ascii=False), "utf-8")
                sys.exit(0)
            time.sleep(0.3)
        log.warning("All pre-built payloads exhausted, booking failed")
        sys.exit(1)
    else:
        do_book(sess, courts)

if __name__ == "__main__":
    main()