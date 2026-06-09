"""Quick scan: show available sports courts for tomorrow."""
import pickle, json, sys
from datetime import datetime, timedelta
from pathlib import Path
import requests

DIR = Path(__file__).parent.resolve()
SESS_PKL = DIR / "session.pkl"
ENV_FILE = DIR / ".env"
BASE = "https://tycg.zjnu.edu.cn"

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

def load_env():
    env = {}
    if ENV_FILE.exists():
        text = ENV_FILE.read_text(encoding="utf-8")
        if text.startswith("\ufeff"):
            text = text[1:]
        for line in text.splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip("\"'")
    return env

if not SESS_PKL.exists():
    print("No session found. Run 'python book.py' first to login.")
    sys.exit(1)

env = load_env()
campus = env.get("ZJNU_CAMPUS", "jinhua")
sport = env.get("ZJNU_SPORT", "badminton")
courts = COURT_REGISTRY[campus][sport]

sess = pickle.load(open(SESS_PKL, "rb"))
s = requests.Session()
s.headers.update({
    "User-Agent": "Mozilla/5.0",
    "Authorization": sess["token"],
})

target = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
print(f"=== {target} ===\n")

for court in courts:
    cid = court["id"]
    f = s.get(BASE + f"/api/court/getFieldNoList?product_id={cid}").json()
    fields = f["data"]["result"]
    p = s.get(BASE + f"/api/court/getCourtPrice?product_id={cid}&venue_id={cid}&date={target}").json()
    slots = p["data"]["result"]

    available = 0
    print(f"{court['name']}:")
    for slot in slots:
        free_fields = []
        for i, fl in enumerate(slot["fieldlist_s"]):
            if fl.get("field_id") and fl.get("text"):
                free_fields.append(fields[i]["seat_number"])
        if free_fields:
            available += len(free_fields)
            print(f"  {slot['start_time']}-{slot['end_time']}: {free_fields}")
    if available == 0:
        print("  (none)")
    print(f"  Total: {available} slots\n")