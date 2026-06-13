import json
import logging
import random
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests

log = logging.getLogger("booker")

DIR = Path(__file__).parent.resolve()
LAST_BOOKING = DIR / "last_booking.json"
DAY_OFFSET = 1  # book for tomorrow

MAX_RETRIES = 3         # max retries per payload on transient errors
BASE_BACKOFF = 0.5      # base backoff seconds (doubles each retry)
BOOK_TIMEOUT = 60       # max total seconds to keep trying (from fire time)
REFEECTH_RETRIES = 3    # re-fetch attempts before falling back to warm-up data


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
    """Fetch available time slots for a single court."""
    cid = court["id"]
    goods_id = court["goods_id"]

    f_resp = sess.get(f"/api/court/getFieldNoList?product_id={cid}")
    if not isinstance(f_resp, dict) or f_resp.get("code") != 1:
        log.warning("  %s: failed to get field list (type=%s)", court["name"],
                     type(f_resp).__name__)
        return []

    p_resp = sess.get(
        f"/api/court/getCourtPrice?product_id={cid}&venue_id={cid}&date={target_date}"
    )
    if not isinstance(p_resp, dict) or p_resp.get("code") != 1:
        log.warning("  %s: failed to get pricing data (type=%s)", court["name"],
                     type(p_resp).__name__)
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

        by_time = {}
        for p in payloads:
            t = p["start_time"]
            by_time.setdefault(t, []).append(p["field_no"])

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

    all_payloads = _shuffle_within_time(all_payloads, courts)

    t_start = datetime.now()
    log.info("Firing %d booking requests...", len(all_payloads))

    for i, p in enumerate(all_payloads):
        result = _try_book(sess, p, t_start, i + 1)
        if result is True:
            _save_last_booking(p, target_date)
            return p
        elif result == "account_limit":
            log.warning("Account limit reached, stopping.")
            return "account_limit"
        elif result == "rate_limited":
            log.info("  Rate limited, waiting 10s...")

        time.sleep(10)

    log.warning("All slots exhausted, booking failed.")
    return None


# ── Loop Mode ──

def loop(sess, courts):
    """Pre-fetch warm-up data, wait until 07:00, then book.

    Phase 1: Pre-fetch for session warm-up (data saved as fallback)
    Phase 2: Wait until 07:00:00.000
    Phase 3: Try warm-up best slot immediately (no re-fetch)
    Phase 4: If failed, re-fetch-and-try loop (10s intervals, 60s max)
    """
    target_date = (datetime.now() + timedelta(days=DAY_OFFSET)).strftime("%Y-%m-%d")
    court_rank = {c["name"]: i for i, c in enumerate(courts)}

    # ── Phase 1: Pre-fetch (warm-up + fallback) ──
    log.info("=== Loop mode: pre-fetching warm-up data ===")
    warm_payloads = []
    for court in courts:
        payloads = _fetch_slots(sess, court, target_date)
        log.info("  %s: %d slots (warm-up)", court["name"], len(payloads))
        warm_payloads.extend(payloads)

    if not warm_payloads:
        log.warning("No bookable slots in warm-up data!")
        return None

    warm_payloads = _shuffle_within_time(warm_payloads, courts)
    log.info("Warm-up: %d slots, best: %s %s #%s",
             len(warm_payloads),
             warm_payloads[0]["court"],
             warm_payloads[0]["start_time"],
             warm_payloads[0]["field_no"])

    # ── Phase 2: Wait until 07:00:00.000 ──
    now = datetime.now()
    target = now.replace(hour=7, minute=0, second=0, microsecond=0)

    if now < target:
        wait = (target - now).total_seconds()
        log.info("Waiting %.0fs until 07:00:00.000", wait)
        if wait > 1.5:
            time.sleep(wait - 1.5)
        while datetime.now() < target:
            pass

    t_fire = datetime.now()
    log.info("FIRE at %s", t_fire.strftime("%H:%M:%S.%f")[:15])

    # ── Phase 3: First strike — use warm-up data immediately ──
    attempted = set()
    attempt_count = 0

    # Pick best from warm-up
    best = warm_payloads[0]
    attempted.add((best["court"], best["start_time"], best["field_no"]))
    attempt_count += 1

    result = _try_book(sess, best, t_fire, attempt_count)
    if result is True:
        _save_last_booking(best, target_date)
        return best
    if result == "account_limit":
        return "account_limit"

    log.info("  First strike missed. Switching to re-fetch loop.")

    # ── Phase 4: Re-fetch-and-try loop ──
    use_warm = True  # keep checking warm-up slots while re-fetching

    while (datetime.now() - t_fire).total_seconds() < BOOK_TIMEOUT:
        elapsed = (datetime.now() - t_fire).total_seconds()

        # Re-fetch live data
        log.info("--- Re-fetching live slots (%.0fs elapsed) ---", elapsed)
        all_payloads = []
        for _ in range(REFEECTH_RETRIES):
            all_payloads = []
            for court in courts:
                try:
                    all_payloads.extend(_fetch_slots(sess, court, target_date))
                except Exception as e:
                    log.warning("  %s: re-fetch failed: %s", court["name"], e)
            if all_payloads:
                break
            time.sleep(2)

        # Fallback: if re-fetch failed, use warm-up data
        if not all_payloads:
            log.warning("  Re-fetch got 0 slots, falling back to warm-up data.")
            all_payloads = warm_payloads
        else:
            all_payloads = _shuffle_within_time(all_payloads, courts)
            log.info("  Live: %d slots available.", len(all_payloads))

        # Pick best untried slot
        best = None
        for p in all_payloads:
            key = (p["court"], p["start_time"], p["field_no"])
            if key not in attempted:
                best = p
                break

        if best is None:
            log.warning("All slots attempted. Giving up.")
            return None

        attempted.add((best["court"], best["start_time"], best["field_no"]))
        attempt_count += 1

        result = _try_book(sess, best, t_fire, attempt_count)
        if result is True:
            _save_last_booking(best, target_date)
            return best
        if result == "account_limit":
            return "account_limit"
        if result == "rate_limited":
            log.info("  Rate limited, waiting 10s...")

        # Wait 10s before next round
        time.sleep(10)

    log.warning("Book timeout (%ds) reached.", BOOK_TIMEOUT)
    return None


# ── Shared helpers ──

def _shuffle_within_time(payloads, courts):
    """Sort by time (latest first), then randomly shuffle within each time group."""
    court_rank = {c["name"]: i for i, c in enumerate(courts)}
    groups = {}
    for p in payloads:
        groups.setdefault(p["start_time"], []).append(p)

    result = []
    for t in sorted(groups.keys(), reverse=True):
        group = groups[t]
        random.shuffle(group)
        group.sort(key=lambda p: court_rank.get(p["court"], 99))
        result.extend(group)

    return result


def _try_book(sess, payload, t_start, idx):
    """Try to book a single payload, with retries for transient errors.

    Returns:
        True             booking succeeded
        False            booking rejected (non-transient, try next slot)
        "rate_limited"   server rate-limiting
        "account_limit"  account maxed out (stop everything)
        None             exhausted retries on transient errors
    """
    for attempt in range(MAX_RETRIES):
        try:
            r = sess.post("/api/pay/CreateOrder", json_data=payload["body"])
            code = r.get("code") if isinstance(r, dict) else -1
            info = str(r.get("info", "")) if isinstance(r, dict) else str(r)[:60]
            elapsed = (datetime.now() - t_start).total_seconds()

            log.info(
                "[%d] %s %s #%s: code=%d delay=%.2fs %s",
                idx, payload["court"], payload["start_time"], payload["field_no"],
                code, elapsed, info[:60]
            )

            if code == 1:
                log.info("*** BOOKING SUCCESS! ***")
                log.info("  %s %s-%s #%s",
                         payload["court"], payload["start_time"],
                         payload["end_time"], payload["field_no"])
                return True

            # Account-level limits — stop everything
            if "最多订" in info or "限购" in info or "只能订购" in info:
                log.warning("  Account limit: %s", info[:60])
                return "account_limit"

            # Slot already taken / full — try next slot
            if "已满" in info or "库存" in info or "已锁定" in info:
                return False

            # Rate-limiting — back off
            if "过于频繁" in info or "频繁" in info:
                return "rate_limited"

            return False

        except (requests.exceptions.ReadTimeout,
                requests.exceptions.ConnectionError,
                requests.exceptions.Timeout) as e:
            if attempt < MAX_RETRIES - 1:
                backoff = BASE_BACKOFF * (2 ** attempt)
                log.warning(
                    "[%d] Network error %d/%d: %s — retrying in %.1fs",
                    idx, attempt + 1, MAX_RETRIES, e, backoff
                )
                time.sleep(backoff)
            else:
                log.error(
                    "[%d] Network error after %d retries: %s — skip",
                    idx, MAX_RETRIES, e
                )
                return None
    return None


def _save_last_booking(payload, target_date):
    """Persist successful booking info to disk."""
    LAST_BOOKING.write_text(json.dumps({
        "date": target_date,
        "court": payload["court"],
        "time": f"{payload['start_time']}-{payload['end_time']}",
        "field": payload["field_no"],
    }, ensure_ascii=False, indent=2), "utf-8")
