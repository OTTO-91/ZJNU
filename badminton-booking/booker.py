# -*- coding: utf-8 -*-
"""Core booking engine for ZJNU sports courts.

Modes:
- scan: Show available slots for tomorrow
- book: Immediate booking attempt
- loop: Pre-fetch + precise-timed booking at 07:00:00
"""

import json
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path

log = logging.getLogger("booker")

DIR = Path(__file__).parent.resolve()
LAST_BOOKING = DIR / "last_booking.json"
DAY_OFFSET = 1  # book for tomorrow


def _time_to_min(time_str):
    """Convert 'HH:MM' to minutes since midnight."""
    h, m = map(int, time_str.split(":"))
    return h * 60 + m


def _build_other_param(price_id, time_id, field_id, court_goods_id, meal_id):
    """Build the other_param JSON string for a booking payload."""
    return json.dumps({
        "price_ids": str(price_id),
        "time_ids": str(time_id),
        "field_ids": str(field_id),
        "price": "0.00",
        "court_id": court_goods_id,
        "meal_id": meal_id,
        "field_type": "1",
    }, ensure_ascii=False)


def _fetch_slots(sess, court, target_date):
    """Fetch available time slots for a single court.

    Returns a list of booking payload dicts.
    """
    cid = court["id"]
    goods_id = court["goods_id"]

    # Get field list
    f_resp = sess.get(f"/api/court/getFieldNoList?product_id={cid}")
    if not f_resp or f_resp.get("code") != 1:
        log.warning("  %s: failed to get field list", court["name"])
        return []

    # Get price/slot data
    p_resp = sess.get(
        f"/api/court/getCourtPrice?product_id={cid}&venue_id={cid}&date={target_date}"
    )
    if not p_resp or p_resp.get("code") != 1:
        log.warning("  %s: failed to get pricing data", court["name"])
        return []

    fields = f_resp["data"]["result"]
    slots = p_resp["data"]["result"]

    payloads = []
    for slot in slots:
        for i, fl in enumerate(slot.get("fieldlist_s", [])):
            if not (fl.get("text") and fl.get("field_id")):
                continue
            payloads.append({
                "court": court["name"],
                "goods_id": goods_id,
                "date": target_date,
                "start_time": slot["start_time"],
                "end_time": slot["end_time"],
                "field_no": fields[i]["seat_number"] if i < len(fields) else "?",
                "body": {
                    "goods_id": goods_id,
                    "order_type": 3,
                    "pay_way": "0",
                    "other_param": _build_other_param(
                        fl["price_id"], slot["id"], fl["field_id"],
                        goods_id, slot["meal_id"],
                    ),
                    "choose_date": target_date,
                },
            })

    return payloads


# ── Scan Mode ──

def scan(sess, courts):
    """Print available slots for each court tomorrow."""
    target_date = (datetime.now() + timedelta(days=DAY_OFFSET)).strftime("%Y-%m-%d")
    log.info("=== Scanning courts for %s ===", target_date)

    print(f"\n{'=' * 50}")
    print(f"  明日 ({target_date}) 场地空闲情况")
    print(f"{'=' * 50}\n")

    for court in courts:
        payloads = _fetch_slots(sess, court, target_date)
        print(f"  {court['name']}:")

        if not payloads:
            print("   (无可用场地)")
            continue

        # Group by time slot
        by_time = {}
        for p in payloads:
            t = p["start_time"]
            if t not in by_time:
                by_time[t] = []
            by_time[t].append(p["field_no"])

        for t in sorted(by_time.keys()):
            fields_str = ", ".join(sorted(by_time[t]))
            print(f"   {t}: #{fields_str}")

        print(f"   共 {len(payloads)} 个可预约时段\n")


# ── Book Mode (immediate) ──

def book(sess, courts):
    """Immediately attempt to book courts for tomorrow."""
    target_date = (datetime.now() + timedelta(days=DAY_OFFSET)).strftime("%Y-%m-%d")

    log.info("=== Immediate booking for %s ===", target_date)

    all_payloads = []
    for court in courts:
        payloads = _fetch_slots(sess, court, target_date)
        log.info("  %s: %d bookable slots", court["name"], len(payloads))
        all_payloads.extend(payloads)

    if not all_payloads:
        log.warning("No bookable slots found!")
        return None

    # Sort: earliest time first, then by court priority
    court_rank = {c["name"]: i for i, c in enumerate(courts)}
    all_payloads.sort(
        key=lambda p: (-_time_to_min(p["start_time"]), court_rank.get(p["court"], 99))
    )

    t_start = datetime.now()
    log.info("Firing %d booking requests...", len(all_payloads))

    for i, p in enumerate(all_payloads):
        r = sess.post("/api/pay/CreateOrder", json_data=p["body"])
        code = r.get("code") if isinstance(r, dict) else -1
        info = r.get("info", "") if isinstance(r, dict) else str(r)[:60]
        elapsed = (datetime.now() - t_start).total_seconds()

        log.info(
            "[%d] %s %s #%s: code=%d delay=%.2fs %s",
            i + 1, p["court"], p["start_time"], p["field_no"],
            code, elapsed, str(info)[:60]
        )

        if code == 1:
            log.info("*** BOOKING SUCCESS! ***")
            log.info("  %s %s-%s #%s", p["court"], p["start_time"], p["end_time"], p["field_no"])

            LAST_BOOKING.write_text(json.dumps({
                "date": target_date,
                "court": p["court"],
                "time": f"{p['start_time']}-{p['end_time']}",
                "field": p["field_no"],
            }, ensure_ascii=False, indent=2), "utf-8")

            return p

        time.sleep(0.3)

    log.warning("All slots exhausted, booking failed.")
    return None


# ── Loop Mode (pre-fetch + precise timing) ──

def loop(sess, courts):
    """Pre-fetch all data, then fire at exactly 07:00:00.

    Phase 1: Pre-fetch and build all payloads
    Phase 2: Wait until 07:00:00.000
    Phase 3: Fire CreateOrder requests
    """
    target_date = (datetime.now() + timedelta(days=DAY_OFFSET)).strftime("%Y-%m-%d")

    # ── Phase 1: Pre-fetch ──
    log.info("=== Loop mode: pre-fetching all data ===")
    all_payloads = []

    for court in courts:
        payloads = _fetch_slots(sess, court, target_date)
        log.info("  %s: %d bookable slots pre-built", court["name"], len(payloads))
        all_payloads.extend(payloads)

    if not all_payloads:
        log.warning("No bookable slots at all!")
        return None

    # Sort: earliest time first, then by court preference order
    court_rank = {c["name"]: i for i, c in enumerate(courts)}
    all_payloads.sort(
        key=lambda p: (-_time_to_min(p["start_time"]), court_rank.get(p["court"], 99))
    )

    best = all_payloads[0]
    log.info(
        "Total %d pre-built payloads, best: %s %s #%s",
        len(all_payloads), best["court"], best["start_time"], best["field_no"]
    )

    # ── Phase 2: Wait until 07:00:00.000 ──
    now = datetime.now()
    target = now.replace(hour=7, minute=0, second=0, microsecond=0)

    if now < target:
        wait = (target - now).total_seconds()
        log.info("Waiting %.0fs until 07:00:00.000", wait)

        # Sleep until ~1.5s before target, then spin-wait
        if wait > 1.5:
            time.sleep(wait - 1.5)

        # Spin-wait for precision
        while datetime.now() < target:
            pass

    # ── Phase 3: Fire! ──
    t_fire = datetime.now()
    log.info("FIRE at %s", t_fire.strftime("%H:%M:%S.%f")[:15])

    for i, p in enumerate(all_payloads):
        r = sess.post("/api/pay/CreateOrder", json_data=p["body"])
        code = r.get("code") if isinstance(r, dict) else -1
        info = r.get("info", "") if isinstance(r, dict) else str(r)[:60]
        elapsed = (datetime.now() - t_fire).total_seconds()

        log.info(
            "[%d] %s %s #%s: code=%d delay=%.2fs %s",
            i + 1, p["court"], p["start_time"], p["field_no"],
            code, elapsed, str(info)[:60]
        )

        if code == 1:
            log.info("*** BOOKING SUCCESS! ***")
            log.info("  %s %s-%s #%s", p["court"], p["start_time"], p["end_time"], p["field_no"])

            LAST_BOOKING.write_text(json.dumps({
                "date": target_date,
                "court": p["court"],
                "time": f"{p['start_time']}-{p['end_time']}",
                "field": p["field_no"],
            }, ensure_ascii=False, indent=2), "utf-8")

            return p

        # Brief delay between attempts to avoid rate-limiting
        time.sleep(0.3)

    log.warning("All pre-built payloads exhausted, booking failed.")
    return None
