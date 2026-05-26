#!/usr/bin/env python3
"""
ZJNU 体育场馆自动预约脚本 v2
用法:
  python zjnu.py                                    # .env 默认值
  python zjnu.py --field 3 --time "20:00-21:00"    # 3号场 20:00-21:00
  python zjnu.py --field 1 --time "18:00-19:00" --date 2026-05-28
  python zjnu.py --try-all --time "20:00-21:00"     # 该时段任意场地
  python zjnu.py --dry-run                           # 模拟
  python zjnu.py --no-dynamic                        # 用硬编码 ID（不调 API）
"""

import argparse
import json
import logging
import os
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

import execjs
import requests
from lxml import etree

# ============================================================
# 路径
# ============================================================
SCRIPT_DIR = Path(__file__).resolve().parent
ENV_FILE = SCRIPT_DIR / ".env"
COOKIE_FILE = SCRIPT_DIR / "cookies.json"
JS_FILE = SCRIPT_DIR / "ez.js"

# ============================================================
# 日志
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("zjnu")

# ============================================================
# 硬编码场地（--no-dynamic 回退用，原版数据）
# ============================================================
STATIC_VENUES = [
    {"field_ids": 449, "price_ids": 10617, "time_ids": 1131, "court_id": 87, "meal_id": 156, "field_type": 1, "seat": "1"},
    {"field_ids": 450, "price_ids": 10630, "time_ids": 1131, "court_id": 87, "meal_id": 156, "field_type": 1, "seat": "2"},
    {"field_ids": 451, "price_ids": 10643, "time_ids": 1131, "court_id": 87, "meal_id": 156, "field_type": 1, "seat": "3"},
    {"field_ids": 452, "price_ids": 10656, "time_ids": 1131, "court_id": 87, "meal_id": 156, "field_type": 1, "seat": "4"},
    {"field_ids": 453, "price_ids": 10669, "time_ids": 1131, "court_id": 87, "meal_id": 156, "field_type": 1, "seat": "5"},
    {"field_ids": 454, "price_ids": 10682, "time_ids": 1131, "court_id": 87, "meal_id": 156, "field_type": 1, "seat": "6"},
    {"field_ids": 455, "price_ids": 10695, "time_ids": 1131, "court_id": 87, "meal_id": 156, "field_type": 1, "seat": "7"},
    {"field_ids": 456, "price_ids": 10708, "time_ids": 1131, "court_id": 87, "meal_id": 156, "field_type": 1, "seat": "8"},
    {"field_ids": 457, "price_ids": 10721, "time_ids": 1131, "court_id": 87, "meal_id": 156, "field_type": 1, "seat": "9"},
]

# ============================================================
# 常量
# ============================================================
SSO_LOGIN_URL = (
    "http://authserver.zjnu.edu.cn:80/authserver/login"
    "?service=https%3A%2F%2Ftycg.zjnu.edu.cn%2Fapi%2Fcas_auth%2Fauth"
)
SERVICE_URL = "https://tycg.zjnu.edu.cn"
BASE_API = f"{SERVICE_URL}/api"
BOOKING_URL = f"{BASE_API}/pay/CreateOrder"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Origin": "https://authserver.zjnu.edu.cn",
}

# ============================================================
# 配置加载
# ============================================================

def load_env() -> dict:
    if not ENV_FILE.exists():
        return {}
    config = {}
    with open(ENV_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            config[k.strip()] = v.strip()
    return config


def load_js():
    if not JS_FILE.exists():
        raise FileNotFoundError(f"ez.js 未找到: {JS_FILE}")
    with open(JS_FILE, "r", encoding="utf-8") as f:
        return execjs.compile(f.read())


# ============================================================
# Cookie 持久化
# ============================================================

def load_cookies(session: requests.Session) -> bool:
    if COOKIE_FILE.exists():
        with open(COOKIE_FILE, "r", encoding="utf-8") as f:
            for c in json.load(f):
                session.cookies.set(c["name"], c["value"], domain=c.get("domain", ""), path=c.get("path", "/"))
        log.info("已加载保存的 cookie")
        return True
    return False


def save_cookies(session: requests.Session) -> None:
    cookies = [
        {"name": c.name, "value": c.value, "domain": c.domain, "path": c.path}
        for c in session.cookies
    ]
    with open(COOKIE_FILE, "w", encoding="utf-8") as f:
        json.dump(cookies, f, ensure_ascii=False, indent=2)
    log.info("Cookie 已保存")


# ============================================================
# SSO 登录
# ============================================================

def cookie_is_valid(session: requests.Session) -> bool:
    try:
        resp = session.get(SERVICE_URL, allow_redirects=True, timeout=10)
        return "统一身份认证" not in resp.text and "authserver" not in resp.url
    except Exception:
        return False


def sso_login(session: requests.Session, username: str, password: str, js_ctx) -> bool:
    log.info("开始 SSO 登录...")
    session.headers.update(HEADERS)

    resp = session.get(SERVICE_URL, allow_redirects=True, timeout=15)
    tree = etree.HTML(resp.text)

    try:
        execution = tree.xpath('//input[@name="execution"]/@value')[0]
        pwd_salt = tree.xpath('//input[@id="pwdEncryptSalt"]/@value')[0]
    except IndexError:
        log.error("无法提取 execution / pwdEncryptSalt，页面可能已变更")
        return False

    encrypted_pw = js_ctx.call("encryptPassword", password, pwd_salt)

    login_data = {
        "username": username,
        "password": encrypted_pw,
        "captcha": "",
        "_eventId": "submit",
        "cllt": "userNameLogin",
        "dllt": "generalLogin",
        "lt": "",
        "execution": execution,
    }
    session.headers["Content-Type"] = "application/x-www-form-urlencoded"
    session.headers["Referer"] = SSO_LOGIN_URL
    session.post(SSO_LOGIN_URL, data=login_data, allow_redirects=True, timeout=15)

    if cookie_is_valid(session):
        log.info("SSO 登录成功")
        save_cookies(session)
        return True
    log.error("SSO 登录失败")
    return False


# ============================================================
# Token
# ============================================================

def get_token(session: requests.Session) -> Optional[str]:
    log.info("获取预约 token...")
    resp = session.get(f"{SERVICE_URL}/venue", allow_redirects=True, timeout=15)
    match = re.search(r"token=([^&]+)", resp.url)
    if match:
        token = match.group(1)
        log.info("Token 获取成功: %s...", token[:20])
        return token
    log.error("未能提取 token, URL: %s", resp.url)
    return None


# ============================================================
# 动态场地解析（查询 API）
# ============================================================

def api_get(session: requests.Session, token: str, path: str, **params) -> Optional[dict]:
    """带上 token 调 API，成功返回 JSON data 字段。"""
    url = f"{BASE_API}/{path}"
    resp = session.get(url, headers={"Authorization": token}, params=params, timeout=10)
    try:
        data = resp.json()
    except Exception:
        log.warning("API %s 返回非 JSON: %s", path, resp.text[:200])
        return None
    if data.get("code") != 1:
        log.warning("API %s 失败: %s", path, data)
        return None
    return data.get("data", {})


def resolve_candidates(session: requests.Session, token: str,
                       product_id: int, venue_id: int, date: str,
                       field_seat: Optional[str], time_range: Optional[str],
                       try_all: bool) -> List[Dict]:
    """
    查场地列表 + 价格表，解析出可预约组合。
    返回 [{field_ids, seat_number, price_ids, time_ids, time_range, meal_id, court_id, field_type, locked}, ...]
    """
    # 1) 场地列表
    field_data = api_get(session, token, "court/getFieldNoList", product_id=product_id)
    if not field_data:
        return []
    fields_map = {}  # field_index -> {field_ids, seat_number}
    for f in field_data["result"]:
        fields_map[len(fields_map)] = {"field_ids": f["id"], "seat_number": f["seat_number"]}

    log.info("场地列表: %s", ", ".join(v["seat_number"] for v in fields_map.values()))

    # 2) 价格表
    price_data = api_get(session, token, "court/getCourtPrice",
                         product_id=product_id, venue_id=venue_id, date=date)
    if not price_data:
        return []

    # 3) 组合
    candidates = []
    available_times = []
    for slot in price_data["result"]:
        slot_range = f"{slot['start_time']}-{slot['end_time']}"
        available_times.append(slot_range)

        if time_range and slot_range != time_range:
            continue

        for fi, field_info in fields_map.items():
            if fi >= len(slot["fieldlist_s"]):
                continue
            price_entry = slot["fieldlist_s"][fi]

            if not try_all and field_seat and field_info["seat_number"] != field_seat:
                continue

            candidates.append({
                "field_ids": field_info["field_ids"],
                "seat_number": field_info["seat_number"],
                "price_ids": price_entry["price_id"],
                "time_ids": slot["id"],
                "time_range": slot_range,
                "meal_id": slot["meal_id"],
                "court_id": product_id,
                "field_type": 1,
                "locked": price_entry.get("lock", 0) == 1,
            })

    if not candidates and time_range:
        log.error("未匹配到时间段 '%s'，可用: %s", time_range, available_times)

    if try_all:
        candidates.sort(key=lambda x: (x["locked"], x["seat_number"]))

    log.info("解析出 %d 个场地×时段组合", len(candidates))
    return candidates


# ============================================================
# 预约
# ============================================================

def build_payload(info: dict, choose_date: str) -> dict:
    other_param = json.dumps({
        "price_ids": str(info["price_ids"]),
        "time_ids": str(info["time_ids"]),
        "field_ids": str(info["field_ids"]),
        "price": "0.00",
        "court_id": str(info["court_id"]),
        "meal_id": info["meal_id"],
        "field_type": str(info["field_type"]),
    })
    return {
        "goods_id": str(info["court_id"]),
        "order_type": 3,
        "pay_way": "0",
        "other_param": other_param,
        "choose_date": choose_date,
    }


def try_book(session: requests.Session, token: str, payload: dict,
             max_retries: int = 10) -> Optional[requests.Response]:
    h = {
        **HEADERS,
        "Authorization": token,
        "Content-Type": "application/json",
        "Origin": "https://tycg.zjnu.edu.cn",
        "Referer": "https://tycg.zjnu.edu.cn/h5/index.html?v=4/",
    }
    for attempt in range(max_retries):
        resp = session.post(BOOKING_URL, json=payload, headers=h, allow_redirects=True, timeout=10)
        if resp.status_code != 502:
            return resp
        if attempt < max_retries - 1:
            time.sleep(0.1)
    return resp


def book_candidates(session: requests.Session, token: str,
                    candidates: List[Dict], target_date: str) -> List[Dict]:
    results = []
    for i, info in enumerate(candidates):
        payload = build_payload(info, target_date)
        label = f"场地 {info['seat_number']} ({info['time_range']})"
        lock_tag = " [已锁定]" if info.get("locked") else ""
        log.info("尝试 %s%s (%d/%d)", label, lock_tag, i + 1, len(candidates))

        resp = try_book(session, token, payload)
        success = resp is not None and resp.status_code == 200 and "成功" in (resp.text or "")

        results.append({
            **info,
            "success": success,
            "status_code": resp.status_code if resp else None,
            "response": (resp.text or "")[:300],
        })
        log.info("%s: HTTP %s — %s", label, resp.status_code if resp else "N/A",
                 "✓ 成功" if success else "✗ 失败")
        if success:
            break
    return results


# ============================================================
# 通知
# ============================================================

def sc_send(sendkey: str, title: str, desp: str = "") -> dict:
    if not sendkey:
        return {}
    if sendkey.startswith("sctp"):
        m = re.match(r"sctp(\d+)t", sendkey)
        if not m:
            raise ValueError(f"无效的 sendkey: {sendkey}")
        url = f"https://{m.group(1)}.push.ft07.com/send/{sendkey}.send"
    else:
        url = f"https://sctapi.ftqq.com/{sendkey}.send"
    try:
        return requests.post(url, json={"title": title, "desp": desp}, timeout=10).json()
    except Exception as e:
        log.warning("通知发送失败: %s", e)
        return {}


# ============================================================
# 主流程
# ============================================================

def parse_date(date_str: str) -> str:
    if date_str == "tomorrow":
        return (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    datetime.strptime(date_str, "%Y-%m-%d")
    return date_str


def main():
    parser = argparse.ArgumentParser(
        description="ZJNU 体育场馆自动预约脚本 v2",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python zjnu.py --field 3 --time "20:00-21:00"
  python zjnu.py --try-all --time "18:00-19:00"
  python zjnu.py --no-dynamic --field 3       # 用硬编码ID
  python zjnu.py --dry-run
        """,
    )
    parser.add_argument("--field", help="场地号 (seat_number), 如 1~9")
    parser.add_argument("--time", help="时间段, 如 '20:00-21:00'")
    parser.add_argument("--date", default="tomorrow", help="预约日期, 'tomorrow' 或 YYYY-MM-DD")
    parser.add_argument("--try-all", action="store_true", help="尝试所有可用场地直到成功")
    parser.add_argument("--product", type=int, default=87, help="场馆 product_id (默认 87=羽毛球)")
    parser.add_argument("--venue", type=int, default=236, help="场馆 venue_id (默认 236)")
    parser.add_argument("--dry-run", action="store_true", help="模拟运行")
    parser.add_argument("--no-notify", action="store_true", help="不发通知")
    parser.add_argument("--no-dynamic", action="store_true", help="使用内置硬编码 ID")
    args = parser.parse_args()

    # ---- 配置 ----
    env = load_env()
    username = env.get("ZJNU_USERNAME", "")
    password = env.get("ZJNU_PASSWORD", "")
    sendkey = env.get("SENDKEY", "")

    if not username or not password:
        log.error("请在 .env 设置 ZJNU_USERNAME 和 ZJNU_PASSWORD")
        sys.exit(1)

    field_seat = args.field or env.get("ZJNU_FIELD")
    time_range = args.time or env.get("ZJNU_TIME")

    try:
        target_date = parse_date(args.date)
        log.info("目标日期: %s", target_date)
    except ValueError:
        log.error("日期格式错误: %s", args.date)
        sys.exit(1)

    # ---- JS ----
    try:
        js_ctx = load_js()
    except FileNotFoundError as e:
        log.error(str(e))
        sys.exit(1)

    # ---- 会话 ----
    session = requests.Session()
    session.headers.update(HEADERS)

    # ---- 登录 ----
    logged_in = False
    if load_cookies(session) and cookie_is_valid(session):
        log.info("Cookie 有效，跳过登录")
        logged_in = True
    else:
        logged_in = sso_login(session, username, password, js_ctx)

    if not logged_in:
        if not args.no_notify:
            sc_send(sendkey, "ZJNU预约 - 登录失败", f"时间: {datetime.now()}")
        sys.exit(1)

    # ---- Token ----
    token = get_token(session)
    if not token:
        if not args.no_notify:
            sc_send(sendkey, "ZJNU预约 - Token获取失败", f"时间: {datetime.now()}")
        sys.exit(1)

    # ---- 解析场地列表 ----
    if args.no_dynamic:
        candidates = [
            {**v, "seat_number": v["seat"], "time_range": "20:00-21:00", "locked": False}
            for v in STATIC_VENUES
            if not field_seat or v["seat"] == field_seat
        ]
        log.info("硬编码模式: %d 个场地", len(candidates))
    else:
        candidates = resolve_candidates(
            session, token,
            product_id=args.product,
            venue_id=args.venue,
            date=target_date,
            field_seat=field_seat,
            time_range=time_range,
            try_all=args.try_all,
        )

    if not candidates:
        log.error("没有可用的场地组合")
        sys.exit(1)

    log.info("=" * 50)
    log.info("候选场地: %d 个", len(candidates))
    for c in candidates[:10]:
        status = "已锁定" if c.get("locked") else "可预约"
        log.info("  场地 %s | %s | %s", c["seat_number"], c["time_range"], status)
    if len(candidates) > 10:
        log.info("  ... 还有 %d 个", len(candidates) - 10)
    log.info("=" * 50)

    # ---- 预约 ----
    if args.dry_run:
        log.info("[DRY RUN] 不会实际发送预约请求，展示第一个候选:")
        payload = build_payload(candidates[0], target_date)
        log.info(json.dumps(payload, ensure_ascii=False, indent=2))
        sys.exit(0)

    results = book_candidates(session, token, candidates, target_date)

    # ---- 通知 ----
    success = any(r["success"] for r in results)
    if success:
        r = next(r for r in results if r["success"])
        msg = f"预约成功！\n日期: {target_date}\n场地: {r['seat_number']}号场\n时段: {r['time_range']}"
        log.info(msg)
    else:
        msg = f"预约失败\n日期: {target_date}\n尝试: {len(results)} 组合\n响应: {results[0].get('response', '')[:200]}"
        log.warning(msg)

    if not args.no_notify:
        sc_send(sendkey, f"ZJNU预约 - {'成功' if success else '失败'}", msg)


if __name__ == "__main__":
    main()
