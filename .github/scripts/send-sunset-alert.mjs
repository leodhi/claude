// Sends today's sunset time for Cedarhurst, NY (zip 11516) as an ntfy push.
//
// Sunset is computed locally with the standard NOAA solar equations rather
// than fetched from a sunset API: this runs once a week, and a self-contained
// calculation can't be broken by a third-party API going down, rate-limiting,
// or changing its response shape. Accuracy is well under a minute for this
// latitude, which is far tighter than the alert needs.

import { fileURLToPath } from "node:url";

const LAT = 40.6237;   // Cedarhurst, NY 11516
const LON = -73.7246;  // negative = west
const TZ = "America/New_York";

const rad = (d) => (d * Math.PI) / 180;
const deg = (r) => (r * 180) / Math.PI;

// Julian day for 00:00 UTC on a given Y-M-D (Gregorian).
function julianDay(year, month, day) {
  if (month <= 2) {
    year -= 1;
    month += 12;
  }
  const a = Math.floor(year / 100);
  const b = 2 - a + Math.floor(a / 4);
  return (
    Math.floor(365.25 * (year + 4716)) +
    Math.floor(30.6001 * (month + 1)) +
    day +
    b -
    1524.5
  );
}

// Minutes after 00:00 UTC at which the sun sets, for the given UTC date.
// Returns null when the sun doesn't set that day (never happens at this
// latitude, but the guard keeps a bad input from silently becoming NaN).
function sunsetMinutesUTC(year, month, day) {
  const t = (julianDay(year, month, day) - 2451545) / 36525;

  const L0 = (280.46646 + t * (36000.76983 + t * 0.0003032)) % 360;
  const M = 357.52911 + t * (35999.05029 - 0.0001537 * t);
  const e = 0.016708634 - t * (0.000042037 + 0.0000001267 * t);

  const C =
    Math.sin(rad(M)) * (1.914602 - t * (0.004817 + 0.000014 * t)) +
    Math.sin(rad(2 * M)) * (0.019993 - 0.000101 * t) +
    Math.sin(rad(3 * M)) * 0.000289;

  const trueLong = L0 + C;
  const omega = 125.04 - 1934.136 * t;
  const lambda = trueLong - 0.00569 - 0.00478 * Math.sin(rad(omega));

  const epsilon0 =
    23 + (26 + (21.448 - t * (46.815 + t * (0.00059 - t * 0.001813))) / 60) / 60;
  const epsilon = epsilon0 + 0.00256 * Math.cos(rad(omega));

  const decl = Math.asin(Math.sin(rad(epsilon)) * Math.sin(rad(lambda)));

  const y = Math.tan(rad(epsilon / 2)) ** 2;
  const eqTime =
    4 *
    deg(
      y * Math.sin(2 * rad(L0)) -
        2 * e * Math.sin(rad(M)) +
        4 * e * y * Math.sin(rad(M)) * Math.cos(2 * rad(L0)) -
        0.5 * y * y * Math.sin(4 * rad(L0)) -
        1.25 * e * e * Math.sin(2 * rad(M))
    );

  // 90.833 deg accounts for refraction plus the sun's apparent radius.
  const cosHA =
    Math.cos(rad(90.833)) / (Math.cos(rad(LAT)) * Math.cos(decl)) -
    Math.tan(rad(LAT)) * Math.tan(decl);
  if (cosHA > 1 || cosHA < -1) return null;

  const ha = deg(Math.acos(cosHA));
  const solarNoon = 720 - 4 * LON - eqTime;
  return solarNoon + 4 * ha;
}

// The calendar date as it currently reads in New York, so a run that fires
// in the evening UTC still reports the correct local "today".
function todayInTZ(now) {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: TZ,
    year: "numeric",
    month: "2-digit",
    day: "2-digit"
  }).formatToParts(now);
  const get = (type) => Number(parts.find((p) => p.type === type).value);
  return { year: get("year"), month: get("month"), day: get("day") };
}

// Formats a UTC instant as a New York wall-clock time, which applies
// EDT/EST automatically rather than us tracking daylight saving by hand.
function formatEastern(instant) {
  return new Intl.DateTimeFormat("en-US", {
    timeZone: TZ,
    hour: "numeric",
    minute: "2-digit",
    hour12: true
  }).format(instant);
}

export function sunsetTimeFor(now) {
  const { year, month, day } = todayInTZ(now);
  const minutes = sunsetMinutesUTC(year, month, day);
  if (minutes === null) throw new Error(`no sunset for ${year}-${month}-${day}`);
  const instant = new Date(
    Date.UTC(year, month - 1, day) + Math.round(minutes * 60000)
  );
  return formatEastern(instant);
}

async function sendNtfy(title, message) {
  const ntfyTopic = process.env.NTFY_TOPIC;
  if (!ntfyTopic) throw new Error("NTFY_TOPIC is not set");
  const url = `https://ntfy.sh/${encodeURIComponent(ntfyTopic)}`
    + `?title=${encodeURIComponent(title)}&priority=3&tags=city_sunset`;
  const res = await fetch(url, { method: "POST", body: message });
  if (!res.ok) throw new Error(`ntfy publish failed: ${res.status} ${await res.text()}`);
}

async function main() {
  const message = `Sunset in Cedarhurst, NY today is ${sunsetTimeFor(new Date())} (Eastern Time).`;
  await sendNtfy("Cedarhurst sunset", message);
  console.log(`sent: ${message}`);
}

// Only send when run directly, so the calculation can be imported and checked
// without firing a notification.
if (process.argv[1] === fileURLToPath(import.meta.url)) {
  await main();
}
