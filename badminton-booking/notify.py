# -*- coding: utf-8 -*-
"""Notification via ServerChan (Server酱)."""

import logging
import re

import requests

log = logging.getLogger("notify")


def sc_send(sendkey, title, desp=""):
    """Send a push notification via ServerChan.

    Args:
        sendkey: ServerChan SENDKEY (supports sctp prefix)
        title: Notification title
        desp: Notification body (optional)

    Returns:
        dict: API response
    """
    if not sendkey:
        log.warning("No SENDKEY configured, skipping notification")
        return None

    # Determine URL based on sendkey format
    if sendkey.startswith("sctp"):
        match = re.match(r"sctp(\d+)t", sendkey)
        if match:
            num = match.group(1)
            url = f"https://{num}.push.ft07.com/send/{sendkey}.send"
        else:
            raise ValueError(f"Invalid sctp sendkey format: {sendkey[:10]}...")
    else:
        url = f"https://sctapi.ftqq.com/{sendkey}.send"

    params = {"title": title, "desp": desp}
    headers = {"Content-Type": "application/json;charset=utf-8"}

    try:
        resp = requests.post(url, json=params, headers=headers, timeout=10)
        result = resp.json()
        log.info("Notification sent: %s", result.get("info", result))
        return result
    except Exception as e:
        log.error("Failed to send notification: %s", e)
        return None
