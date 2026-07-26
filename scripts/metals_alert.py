#!/usr/bin/env python3
"""Detect fast, straight-line moves in metals futures and push an ntfy.sh alert.

Fetches 1-minute bars from Yahoo Finance for gold, silver, and copper futures,
fits a line to the trailing LOOKBACK_MINUTES of closes, and alerts when that
window is both highly linear (R^2) and moved more than a percent threshold.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

SYMBOLS = {
    "GC=F": "Gold futures",
    "SI=F": "Silver futures",
    "HG=F": "Copper futures",
}

def _env(name, default):
    value = os.environ.get(name)
    return value if value else default


LOOKBACK_MINUTES = int(_env("LOOKBACK_MINUTES", "5"))
MOVE_THRESHOLD_PCT = float(_env("MOVE_THRESHOLD_PCT", "0.4"))
R2_THRESHOLD = float(_env("R2_THRESHOLD", "0.85"))
COOLDOWN_MINUTES = float(_env("COOLDOWN_MINUTES", "15"))
STALE_DATA_MINUTES = float(_env("STALE_DATA_MINUTES", "20"))

NTFY_TOPIC = os.environ.get("NTFY_TOPIC")
NTFY_SERVER = _env("NTFY_SERVER", "https://ntfy.sh")

STATE_PATH = os.path.join(os.path.dirname(__file__), "..", "state", "alert_state.json")

USER_AGENT = "Mozilla/5.0 (compatible; metals-alert-bot/1.0)"


def fetch_chart(symbol):
    url = (
        "https://query1.finance.yahoo.com/v8/finance/chart/"
        + urllib.parse.quote(symbol)
        + "?interval=1m&range=1d"
    )
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.load(resp)
    result = data["chart"]["result"][0]
    timestamps = result.get("timestamp")
    if not timestamps:
        return []
    closes = result["indicators"]["quote"][0]["close"]
    return list(zip(timestamps, closes))


def trailing_window(bars, minutes):
    clean = [(t, c) for t, c in bars if c is not None]
    if len(clean) < minutes:
        return None
    window = clean[-minutes:]
    now = time.time()
    if now - window[-1][0] > STALE_DATA_MINUTES * 60:
        return None
    return window


def linear_fit(window):
    n = len(window)
    xs = list(range(n))
    ys = [c for _, c in window]
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    ss_xy = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    ss_xx = sum((x - mean_x) ** 2 for x in xs)
    if ss_xx == 0:
        return 0.0, mean_y, 0.0
    slope = ss_xy / ss_xx
    intercept = mean_y - slope * mean_x
    ss_tot = sum((y - mean_y) ** 2 for y in ys)
    if ss_tot == 0:
        r2 = 1.0
    else:
        ss_res = sum((y - (intercept + slope * x)) ** 2 for x, y in zip(xs, ys))
        r2 = 1 - ss_res / ss_tot
    return slope, intercept, r2


def load_state():
    try:
        with open(STATE_PATH) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_state(state):
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2, sort_keys=True)


def send_ntfy(title, message, priority="high", tags="rotating_light"):
    if not NTFY_TOPIC:
        print("NTFY_TOPIC not set; skipping push, would have sent:", title, message)
        return
    url = f"{NTFY_SERVER.rstrip('/')}/{NTFY_TOPIC}"
    req = urllib.request.Request(
        url,
        data=message.encode("utf-8"),
        headers={
            "Title": title,
            "Priority": priority,
            "Tags": tags,
        },
        method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=10)
    except urllib.error.URLError as e:
        print(f"Failed to send ntfy alert: {e}", file=sys.stderr)


def main():
    if _env("TEST_ALERT", "") == "true":
        send_ntfy(
            "Metals alert test",
            "This is a test push from the Metals Spike Alerts workflow. "
            "If you can see this on your phone, the ntfy setup works.",
            priority="default",
            tags="white_check_mark",
        )
        print("Sent test alert.")
        return

    state = load_state()
    now = time.time()
    changed = False

    for symbol, label in SYMBOLS.items():
        try:
            bars = fetch_chart(symbol)
        except Exception as e:
            print(f"[{symbol}] fetch failed: {e}", file=sys.stderr)
            continue

        window = trailing_window(bars, LOOKBACK_MINUTES)
        if window is None:
            print(f"[{symbol}] not enough fresh data, skipping")
            continue

        slope, intercept, r2 = linear_fit(window)
        n = len(window)
        start_fit = intercept
        end_fit = intercept + slope * (n - 1)
        if start_fit == 0:
            continue
        pct_move = (end_fit - start_fit) / start_fit * 100
        last_price = window[-1][1]

        print(
            f"[{symbol}] last={last_price:.2f} pct_move={pct_move:+.3f}% "
            f"r2={r2:.3f} over {n}m"
        )

        if abs(pct_move) < MOVE_THRESHOLD_PCT or r2 < R2_THRESHOLD:
            continue

        last_alert = state.get(symbol, {}).get("last_alert_ts", 0)
        if now - last_alert < COOLDOWN_MINUTES * 60:
            print(f"[{symbol}] spike detected but in cooldown, skipping alert")
            continue

        direction = "UP" if pct_move > 0 else "DOWN"
        title = f"{label} straight-line {direction} move"
        message = (
            f"{label} ({symbol}) moved {pct_move:+.2f}% in the last {n} min "
            f"with a very linear path (R^2={r2:.2f}). Last price: {last_price:.2f}"
        )
        send_ntfy(title, message)
        print(f"[{symbol}] ALERT SENT: {message}")

        state[symbol] = {"last_alert_ts": now, "direction": direction}
        changed = True

    if changed:
        save_state(state)


if __name__ == "__main__":
    main()
