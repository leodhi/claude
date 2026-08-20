// Daily check of the two deadline-shaped home utilities -- renewals
// (passports, MOT, insurance) and returns (things to send back) -- pushing a
// phone alert via ntfy when something is close.
//
// Reuses the same FIREBASE_SERVICE_ACCOUNT and NTFY_TOPIC secrets as the
// subscription renewal alerts. The admin SDK bypasses Firestore rules, so
// these alerts work even before the homeApps/ rule is added by hand.
//
// Each item alerts once per threshold per cycle, tracked with lastAlerted on
// the item itself, so a thing due in 30 days doesn't nag every morning.
import { initializeApp, cert } from "firebase-admin/app";
import { getFirestore } from "firebase-admin/firestore";

const ntfyTopic = process.env.NTFY_TOPIC;
if (!ntfyTopic) throw new Error("NTFY_TOPIC is not set");

// Renewals carry their own notice period -- an inspection wants a month, a
// quick errand wants a few days -- so the steps are built per item from
// whatever the app saved, plus a nearer nudge and one on the day.
const DEFAULT_LEAD_DAYS = 30;
function renewalThresholds(item) {
  const lead = Math.max(1, Number(item.leadDays) || DEFAULT_LEAD_DAYS);
  // A short notice period shouldn't get a "7 days" step that fires at the same
  // time as the first one, so the middle nudge scales with the lead.
  const mid = lead > 14 ? 7 : lead > 3 ? 2 : null;
  return [...new Set([lead, mid, 0].filter(v => v !== null))];
}
// Return windows are short and missing one costs real money, so it nags later
// and closer in.
const RETURN_THRESHOLDS = [3, 1, 0];

const DAY = 86400000;

function todayUTC() {
  const d = new Date();
  d.setUTCHours(0, 0, 0, 0);
  return d;
}

function daysUntil(dateStr, today) {
  const t = Date.parse(dateStr + "T00:00:00Z");
  if (Number.isNaN(t)) return null;
  return Math.round((t - today.getTime()) / DAY);
}

function formatDate(dateStr) {
  const dt = new Date(dateStr + "T00:00:00Z");
  return dt.toLocaleDateString("en-GB", { day: "numeric", month: "short", timeZone: "UTC" });
}

// The tightest threshold this item has now reached, or null if it's still far
// off. Anything already overdue reports 0 so it still gets one nudge.
//
// Tightest, not largest: the thresholds are checked smallest-first so that an
// item crossing 30 days alerts at 30, then again at 7, then again on the day.
// Returning the largest match instead would alert once at 30 days and then
// stay silent right through to the deadline.
function thresholdReached(days, thresholds) {
  if (days === null) return null;
  if (days < 0) return 0;
  for (const t of [...thresholds].sort((a, b) => a - b)) if (days <= t) return t;
  return null;
}

// ntfy's "http" action button isn't honoured reliably across clients, so
// snoozing uses the "view" action every client supports: it opens a small page
// on this site that re-publishes the same alert after a delay. Same page the
// subscription alerts already use.
function snoozeAction(title, message, delay) {
  const url = "https://leodhi.github.io/claude/docs/subscriptions/snooze.html"
    + `?topic=${encodeURIComponent(ntfyTopic)}`
    + `&title=${encodeURIComponent(title)}`
    + `&message=${encodeURIComponent(message)}`
    + `&delay=${encodeURIComponent(delay)}`;
  return { action: "view", label: `Snooze ${delay}`, url, clear: true };
}

async function sendNtfy(title, message, tag, snoozeDelay) {
  const url = `https://ntfy.sh/${encodeURIComponent(ntfyTopic)}`
    + `?title=${encodeURIComponent(title)}&priority=3&tags=${encodeURIComponent(tag)}`;
  const res = await fetch(url, {
    method: "POST",
    headers: { Actions: JSON.stringify([snoozeAction(title, message, snoozeDelay || "24h")]) },
    body: message
  });
  if (!res.ok) throw new Error(`ntfy publish failed: ${res.status} ${await res.text()}`);
}

// Snoozing must not push the reminder past the deadline itself. Anything due
// tomorrow or sooner snoozes by hours, not a day.
function snoozeDelayFor(days) {
  if (days === null || days <= 0) return "3h";
  if (days === 1) return "6h";
  return "24h";
}

async function checkDoc(db, docId, thresholdsFor, tag, buildAlert) {
  const ref = db.collection("homeApps").doc(docId);
  const snap = await ref.get();
  if (!snap.exists) {
    console.log(`${docId}: no document yet, nothing to check.`);
    return 0;
  }
  const items = snap.data().items || {};
  const today = todayUTC();
  let sent = 0;

  for (const [id, item] of Object.entries(items)) {
    if (!item || !item.date || item.done) continue;
    const days = daysUntil(item.date, today);
    const reached = thresholdReached(days, thresholdsFor(item));
    if (reached === null) continue;

    // One alert per threshold per date -- moving the date (or renewing)
    // resets this naturally because the stamp includes the date.
    const stamp = `${item.date}:${reached}`;
    if (item.lastAlerted === stamp) continue;

    const { title, message } = buildAlert(item, days);
    await sendNtfy(title, message, tag, snoozeDelayFor(days));
    await ref.set({ items: { [id]: { lastAlerted: stamp } } }, { merge: true });
    console.log(`Alerted (${docId}): ${item.name} — ${days} day(s) out`);
    sent++;
  }
  return sent;
}

function renewalAlert(item, days) {
  const when = days < 0 ? `expired ${Math.abs(days)} day(s) ago`
    : days === 0 ? "is due today"
    : `is due in ${days} day(s)`;
  return {
    title: `${item.name} ${days < 0 ? "has expired" : "renews soon"}`,
    message: `${item.name} ${when} (${formatDate(item.date)})${item.note ? ` · ${item.note}` : ""}`
  };
}

function returnAlert(item, days) {
  const when = days < 0 ? `was due back ${Math.abs(days)} day(s) ago`
    : days === 0 ? "must go back today"
    : `must go back within ${days} day(s)`;
  const where = item.where ? ` to ${item.where}` : "";
  return {
    title: days < 0 ? `Return window missed: ${item.name}` : `Send back: ${item.name}`,
    message: `${item.name}${where} ${when} (by ${formatDate(item.date)})${item.note ? ` · ${item.note}` : ""}`
  };
}

async function main() {
  if (process.env.TEST_ONLY === "true") {
    await sendNtfy("Test alert", "Home deadline alerts are wired up correctly.", "bell");
    console.log("Test notification sent.");
    return;
  }

  const serviceAccount = JSON.parse(process.env.FIREBASE_SERVICE_ACCOUNT);
  initializeApp({ credential: cert(serviceAccount) });
  const db = getFirestore();

  const renewals = await checkDoc(db, "renewals", renewalThresholds, "calendar", renewalAlert);
  const returns = await checkDoc(db, "returns", () => RETURN_THRESHOLDS, "package", returnAlert);
  console.log(`Done. ${renewals} renewal alert(s), ${returns} return alert(s).`);
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});
