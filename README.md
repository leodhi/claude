# claude

## Tickr — real-time stock tracker

`stocks.html` is a self-contained, single-page stock watchlist and portfolio
tracker in the style of StockMaster. Open the file in a browser (no build
step, no server needed) and:

1. Go to **Settings** and paste a free [Finnhub](https://finnhub.io/register)
   API key (stored only in `localStorage`, never sent anywhere else).
2. Add symbols to your **Watchlist** — prices update live over a WebSocket
   connection to Finnhub, with a REST polling fallback every 15s.
3. Track shares you own in **Portfolio**, with live market value and
   gain/loss.

Tap any watchlist row to see a detail view with a session sparkline, day
range, open, and previous close.
