// Daily check: reads subscriptionLedgers/family from Firestore, and for any
// subscription renewing within ALERT_DAYS_AHEAD days sends a push notification
// via ntfy. Each subscription is alerted once per renewal cycle (tracked via
// lastAlertedRenewal on the doc itself) -- snoozing is handled entirely by
// ntfy's own scheduled-delivery feature (the button asks ntfy.sh to resend
// the same alert in 24h), so this script never needs to know about a snooze.

import { initializeApp, cert } from "firebase-admin/app";
import { getFirestore } from "firebase-admin/firestore";

const ALERT_DAYS_AHEAD = 7;

const ntfyTopic = process.env.NTFY_TOPIC;
if (!ntfyTopic) throw new Error("NTFY_TOPIC is not set");

function advanceRenewal(renew, cycleInterval, cycleUnit) {
  const dt = new Date(renew + "T00:00:00Z");
  const n = cycleInterval || 1;
  const unit = cycleUnit || "month";
  if (unit === "day") dt.setUTCDate(dt.getUTCDate() + n);
  else if (unit === "week") dt.setUTCDate(dt.getUTCDate() + n * 7);
  else if (unit === "month") dt.setUTCMonth(dt.getUTCMonth() + n);
  else dt.setUTCFullYear(dt.getUTCFullYear() + n);
  return dt.toISOString().slice(0, 10);
}

function daysUntil(dateStr, today) {
  const target = new Date(dateStr + "T00:00:00Z");
  return Math.round((target - today) / 86400000);
}

// Mirrors the app's client-side-only "advance a stale renewal forward for
// display" logic -- never writes the advanced date back, just computes what
// the next real renewal is as of today.
function nextRenewal(sub, today) {
  let renew = sub.renew;
  let d = daysUntil(renew, today);
  while (d < 0) {
    renew = advanceRenewal(renew, sub.cycleInterval, sub.cycleUnit);
    d = daysUntil(renew, today);
  }
  return { renew, daysUntil: d };
}

function formatDate(dateStr) {
  const dt = new Date(dateStr + "T00:00:00Z");
  return dt.toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
}

// Snooze re-publishes via ntfy's plain query-string + text-body form (the
// same shape as `curl -d message ntfy.sh/topic?delay=24h`) rather than a
// JSON body -- that's the form every ntfy client version is guaranteed to
// support for an http action button, where the fancier JSON-body form isn't
// consistently honored.
function snoozeAction(title, message) {
  const url = `https://ntfy.sh/${encodeURIComponent(ntfyTopic)}`
    + `?delay=24h&title=${encodeURIComponent(title)}&priority=3&tags=bell`;
  return { action: "http", label: "Snooze 1 day", url, method: "POST", body: message, clear: true };
}

async function sendNtfy(title, message) {
  const url = `https://ntfy.sh/${encodeURIComponent(ntfyTopic)}`
    + `?title=${encodeURIComponent(title)}&priority=3&tags=bell`;
  const res = await fetch(url, {
    method: "POST",
    headers: { Actions: JSON.stringify([snoozeAction(title, message)]) },
    body: message
  });
  if (!res.ok) throw new Error(`ntfy publish failed: ${res.status} ${await res.text()}`);
}

async function main() {
  // TEST_ONLY sends a single throwaway notification (with a working snooze
  // button) and exits, without touching Firestore -- lets us confirm ntfy
  // delivery/actions work without waiting on a real 7-day-out renewal.
  if (process.env.TEST_ONLY === "true") {
    const title = "Test alert";
    const message = "If you can see this and the Snooze button works, you're all set.";
    await sendNtfy(title, message);
    console.log("Test notification sent.");
    return;
  }

  const serviceAccount = JSON.parse(process.env.FIREBASE_SERVICE_ACCOUNT);
  initializeApp({ credential: cert(serviceAccount) });
  const db = getFirestore();

  const today = new Date();
  today.setUTCHours(0, 0, 0, 0);

  const ref = db.collection("subscriptionLedgers").doc("family");
  const snap = await ref.get();
  const data = snap.exists ? snap.data() : {};
  const subsMap = data.subs || {};

  let alerted = 0;
  for (const [id, sub] of Object.entries(subsMap)) {
    const { renew, daysUntil: d } = nextRenewal(sub, today);
    if (d <= ALERT_DAYS_AHEAD && sub.lastAlertedRenewal !== renew) {
      const title = `${sub.name} renews soon`;
      const message = `$${(sub.cost || 0).toFixed(2)} · renews ${formatDate(renew)}`;
      await sendNtfy(title, message);
      await ref.set({ subs: { [id]: { lastAlertedRenewal: renew } } }, { merge: true });
      console.log(`Alerted: ${sub.name} (renews ${renew}, ${d}d out)`);
      alerted++;
    }
  }
  console.log(`Done. ${alerted} alert(s) sent, ${Object.keys(subsMap).length} subscription(s) checked.`);
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});
