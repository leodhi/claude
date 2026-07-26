# claude

## Metals spike alerts

Detects fast, straight-line moves in gold (GC=F), silver (SI=F), and copper
(HG=F) futures and pushes a phone notification via [ntfy.sh](https://ntfy.sh)
when one happens.

**How it works:** every 5 minutes, `scripts/metals_alert.py` pulls 1-minute
bars from Yahoo Finance's free (delayed) quote feed for each future, fits a
straight line to the trailing 5-minute window of closes, and fires an alert
when that window is both highly linear (R² above threshold — i.e. it really
looks like a straight line, not a choppy back-and-forth) and has moved more
than a percent threshold. Each symbol has a cooldown so it won't spam repeat
alerts on the same move.

### One-time setup

1. Install the [ntfy app](https://ntfy.sh/) on your phone (iOS/Android) and
   pick a private topic name (e.g. `metals-alerts-<random string>` — anyone
   who knows the exact topic name can read or post to it, so don't use
   something guessable). Subscribe to that topic in the app.
2. In this repo's GitHub settings, add a repository **secret** named
   `NTFY_TOPIC` with that topic name (Settings → Secrets and variables →
   Actions → New repository secret).
3. Optionally tune behavior with repository **variables** (same settings
   page, Variables tab) — all optional, defaults shown:
   - `MOVE_THRESHOLD_PCT` (default `0.4`) — minimum % move over the window
     to trigger an alert.
   - `R2_THRESHOLD` (default `0.85`) — how linear the move must be (0–1).
   - `LOOKBACK_MINUTES` (default `5`) — window size in minutes.
   - `COOLDOWN_MINUTES` (default `15`) — minimum gap between repeat alerts
     for the same future.
   - `NTFY_SERVER` (default `https://ntfy.sh`) — only needed if you're
     self-hosting ntfy.
4. Merge this branch to the repo's default branch — GitHub Actions only
   runs *scheduled* workflows (`.github/workflows/metals-alert.yml`) off the
   default branch, so the cron job stays dormant until then. You can still
   test it manually beforehand from the Actions tab via "Run workflow"
   (workflow_dispatch) on this branch.

### Testing the phone notification

Clicking "Run workflow" normally just checks live prices — if the market
hasn't made a sharp move (or is closed), nothing gets sent, which is
expected and not a failure. To confirm the phone notification path itself
works, regardless of market conditions: go to the Actions tab → "Metals
Spike Alerts" → **Run workflow**, and check the **"Send a test push
notification instead of checking prices"** box before running. That sends
a fixed test message straight to your ntfy topic so you can confirm it
reaches your phone.

### Notes and caveats

- Yahoo's free feed for futures is delayed (typically 10–15 min), so this
  is meant for catching "that was a fast move" shortly after the fact, not
  for split-second trade execution.
- 1-minute bars only exist while the futures market is in session; outside
  trading hours the job simply logs "not enough fresh data" and does
  nothing.
- Run it manually any time with `python3 scripts/metals_alert.py` (set
  `NTFY_TOPIC` in your environment first, or leave it unset to dry-run and
  just print what would have been sent).