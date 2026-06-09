# -*- coding: utf-8 -*-
"""Configuration management for ZJNU Court Auto-Booking.

Loads credentials from .env, provides interactive setup wizard,
and maintains the court registry for all campuses & sports.
"""

import os
import sys
from pathlib import Path

DIR = Path(__file__).parent.resolve()

# ── Paths ──
ENV_FILE = DIR / ".env"

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


def _parse_env_file(path):
    """Parse a .env file, return dict. Returns empty dict if file missing."""
    env = {}
    if path.exists():
        text = path.read_text(encoding="utf-8")
        if text.startswith("\ufeff"):
            text = text[1:]
        for line in text.splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip("'\"").strip("'")
    return env


def load_env():
    """Parse local .env file, return dict."""
    return _parse_env_file(ENV_FILE)


def setup_env():
    """Interactive setup wizard. Saves credentials to .env."""
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

    sport = "badminton"
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

    # 可选：Server酱微信推送
    print()
    print("--- 可选配置：微信推送通知 ---")
    print("如果配置 Server酱，预约结果会自动推送到微信。")
    print("获取 SendKey: https://sct.ftqq.com/ (微信扫码登录)")
    print("不需要则直接回车跳过")
    sendkey = input("SendKey: ").strip()

    content = (
        f"ZJNU_USERNAME={username}\n"
        f"ZJNU_PASSWORD={password}\n"
        f"ZJNU_CAMPUS={campus}\n"
        f"ZJNU_SPORT={sport}\n"
    )
    if sendkey:
        content += f"SENDKEY={sendkey}\n"

    ENV_FILE.write_text(content, encoding="utf-8")
    print(f"\n✅ 配置已保存到 {ENV_FILE.name}")
    return {
        "ZJNU_USERNAME": username,
        "ZJNU_PASSWORD": password,
        "ZJNU_CAMPUS": campus,
        "ZJNU_SPORT": sport,
        "SENDKEY": sendkey,
    }


def get_credentials():
    """Get username/password from env, or run setup if missing."""
    env = load_env()
    if "ZJNU_USERNAME" in env and "ZJNU_PASSWORD" in env:
        return env["ZJNU_USERNAME"], env["ZJNU_PASSWORD"]
    env = setup_env()
    return env["ZJNU_USERNAME"], env["ZJNU_PASSWORD"]


def get_courts():
    """Get list of courts for the configured campus + sport."""
    env = load_env()
    campus = env.get("ZJNU_CAMPUS", "jinhua")
    sport = env.get("ZJNU_SPORT", "badminton")
    if campus not in COURT_REGISTRY or sport not in COURT_REGISTRY[campus]:
        print(f"Invalid campus/sport: {campus}/{sport}, falling back to jinhua/badminton")
        campus, sport = "jinhua", "badminton"
    return COURT_REGISTRY[campus][sport]


def get_sendkey():
    """Get ServerChan sendkey: local .env first, then parent .env."""
    env = load_env()
    sendkey = env.get("SENDKEY", "")
    if not sendkey:
        # Fallback to parent .env
        parent_env = _parse_env_file(DIR.parent / ".env")
        sendkey = parent_env.get("SENDKEY", "")
    return sendkey

