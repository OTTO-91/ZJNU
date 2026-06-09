#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ZJNU Court Auto-Booking

Multi-campus, multi-sport sports court auto-booking for Zhejiang Normal University.

Usage:
    python main.py              # Immediate booking for tomorrow
    python main.py --scan       # Show available slots (no booking)
    python main.py --loop       # Wait until 07:00 and book precisely
    python main.py --setup      # Re-configure credentials

First run will prompt for student ID, password, campus, and sport.
Configuration is saved to .env.
"""

import argparse
import logging
import sys
from pathlib import Path

from config import get_credentials, get_courts, get_sendkey, setup_env, ENV_FILE
from auth import Session, COOKIE_FILE, TOKEN_FILE
from booker import scan, book, loop
from notify import sc_send

DIR = Path(__file__).parent.resolve()
LOG_FILE = DIR / "booking.log"

# ── Logging ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("main")


def _handle_result(result, sendkey, mode):
    """Handle booking result: log and send notification."""
    if result:
        log.info("✅ Booking successful!")
        msg = (
            f"场地: {result['court']}\n"
            f"时间: {result['start_time']}-{result['end_time']}\n"
            f"场号: #{result['field_no']}\n"
            f"日期: {result['date']}"
        )
        sc_send(sendkey, "预约成功 🎉", msg)
    else:
        log.warning("❌ Booking failed")
        if mode == "loop":
            sc_send(sendkey, "预约失败", "场地已被锁定或无可预约时段")


def main():
    parser = argparse.ArgumentParser(
        description="ZJNU Court Auto-Booking",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py              # Book now for tomorrow
  python main.py --scan       # Check availability
  python main.py --loop       # Auto-book at 07:00 (for cron)
  python main.py --setup      # Re-configure
        """,
    )
    parser.add_argument(
        "--scan", action="store_true",
        help="Show available slots for tomorrow (no booking)"
    )
    parser.add_argument(
        "--loop", action="store_true",
        help="Pre-fetch then book precisely at 07:00:00"
    )
    parser.add_argument(
        "--setup", action="store_true",
        help="Re-configure credentials and preferences"
    )

    args = parser.parse_args()

    # ── Setup mode ──
    if args.setup:
        if ENV_FILE.exists():
            ENV_FILE.unlink()
        if COOKIE_FILE.exists():
            COOKIE_FILE.unlink()
        if TOKEN_FILE.exists():
            TOKEN_FILE.unlink()
        log.info("Old config cleared. Starting setup wizard...")
        setup_env()
        print("\n✅ Setup complete! Run 'python main.py' to book.")
        return

    # ── Get credentials & courts ──
    try:
        username, password = get_credentials()
        courts = get_courts()
        sendkey = get_sendkey()
    except (KeyboardInterrupt, EOFError):
        print("\nSetup cancelled.")
        sys.exit(1)

    log.info("Campus sport: %s", ", ".join(c["name"] for c in courts))

    # ── Initialize session ──
    sess = Session()

    # Try to restore existing session
    if not sess.load() or not sess.tok:
        log.info("No valid session, logging in...")
        try:
            sess.login(username, password)
        except RuntimeError as e:
            log.error("Login failed: %s", e)
            sc_send(sendkey, "登录失败", str(e))
            sys.exit(1)
    else:
        log.info("Using saved session.")

    # Ensure token is fresh
    if not sess.ensure_token():
        log.info("Token expired, re-logging in...")
        try:
            sess.login(username, password)
        except RuntimeError as e:
            log.error("Re-login failed: %s", e)
            sc_send(sendkey, "重新登录失败", str(e))
            sys.exit(1)

    # ── Execute mode ──
    if args.scan:
        scan(sess, courts)
    elif args.loop:
        result = loop(sess, courts)
        _handle_result(result, sendkey, "loop")
    else:
        # Default: immediate book
        result = book(sess, courts)
        _handle_result(result, sendkey, "book")


if __name__ == "__main__":
    main()
