// Safari/iOS lint.
//
// WebKit cannot be installed in this environment (the browser CDN is blocked
// by the network policy), and Chromium is NOT Safari -- that difference is
// exactly how the vh bug shipped. So this encodes the WebKit behaviours that
// have actually bitten this repo, plus the well-known ones, as static checks
// that run every time. It is a backstop, not a substitute for the phone.
const fs = require("fs");
const path = require("path");

const APPS = process.argv.slice(2);
let problems = 0, checks = 0;
const bad = (file, rule, detail) => { problems++; console.log(`  ✗ ${path.basename(path.dirname(file))}: [${rule}] ${detail}`); };
const pass = () => { checks++; };

function styleOf(src) {
  const m = src.match(/<style>([\s\S]*?)<\/style>/);
  return m ? m[1] : "";
}
// Split CSS into { selector, body } blocks, ignoring @media wrappers.
function rules(css) {
  const out = [];
  const re = /([^{}]+)\{([^{}]*)\}/g;
  let m;
  while ((m = re.exec(css))) {
    const sel = m[1].trim().replace(/\s+/g, " ");
    if (sel.startsWith("@")) continue;
    out.push({ sel, body: m[2] });
  }
  return out;
}
const decl = (body, prop) => {
  const re = new RegExp("(?:^|;)\\s*" + prop + "\\s*:\\s*([^;]+)", "i");
  const m = body.match(re);
  return m ? m[1].trim() : null;
};

for (const file of APPS) {
  const src = fs.readFileSync(file, "utf8");
  const css = styleOf(src);
  const rs = rules(css);

  // 1. vh sizing on anything fixed/overlaid. iOS resolves vh against the
  //    toolbars-hidden height, so it is taller than the screen you can see.
  for (const r of rs) {
    for (const prop of ["height", "max-height", "min-height"]) {
      const v = decl(r.body, prop);
      if (v && /\d+vh\b/.test(v) && !/dvh|svh/.test(v)) {
        bad(file, "ios-vh", `${r.sel} { ${prop}: ${v} } — vh is the toolbars-hidden height on iOS; use % of a fixed parent, or dvh`);
      } else pass();
    }
  }

  // 2. iOS zooms the whole page when you focus a form field under 16px.
  for (const r of rs) {
    if (!/input|select|textarea/i.test(r.sel)) { pass(); continue; }
    const fsz = decl(r.body, "font-size");
    if (!fsz) { pass(); continue; }
    let px = null;
    let m = fsz.match(/^([\d.]+)px$/); if (m) px = parseFloat(m[1]);
    m = fsz.match(/^([\d.]+)rem$/);    if (m) px = parseFloat(m[1]) * 16;
    if (px !== null && px < 16) bad(file, "ios-zoom", `${r.sel} { font-size: ${fsz} } — under 16px, so iOS zooms the page when it is focused`);
    else pass();
  }

  // 3. Native form controls need an appearance reset or Safari draws its own
  //    tiny version, ignoring your padding and width. This is the bug that
  //    made the date box 131x21 next to 358x44 fields.
  const nativeControls = [...src.matchAll(/<(input|select|textarea)\b[^>]*?(?:type="([a-z-]+)")?[^>]*>/gi)]
    .map(m => (m[1].toLowerCase() === "input" ? `input[type="${m[2] || "text"}"]` : m[1].toLowerCase()));
  for (const ctrl of [...new Set(nativeControls)]) {
    if (!/date|time|select|month|week/.test(ctrl)) { pass(); continue; }
    const key = ctrl.replace(/input\[type="([a-z-]+)"\]/, '$1');
    const styled = rs.some(r => r.sel.includes(key) && /appearance\s*:\s*none/i.test(r.body));
    if (!styled) bad(file, "ios-native-control", `${ctrl} is used but never gets -webkit-appearance: none — Safari will draw its own, ignoring your sizing`);
    else pass();
  }

  // 4. Prefixes WebKit still wants.
  for (const r of rs) {
    const bf = decl(r.body, "backdrop-filter");
    if (bf && !/-webkit-backdrop-filter/i.test(r.body)) bad(file, "webkit-prefix", `${r.sel} uses backdrop-filter with no -webkit- version`);
    else pass();
  }

  // 5. The house rules from CLAUDE.md that exist because of iOS.
  if (!/-webkit-tap-highlight-color\s*:\s*transparent/.test(css))
    bad(file, "ios-tap-highlight", "no -webkit-tap-highlight-color: transparent — taps flash a grey box");
  else pass();
  if (!/overscroll-behavior-y\s*:\s*contain/.test(css))
    bad(file, "ios-rubber-band", "no overscroll-behavior-y: contain — the page rubber-bands and threatens a refresh");
  else pass();
  if (!/viewport-fit=cover/.test(src))
    bad(file, "ios-safe-area", "viewport meta has no viewport-fit=cover, so env(safe-area-inset-*) does nothing");
  else pass();
  if (!/env\(safe-area-inset-bottom\)/.test(css))
    bad(file, "ios-home-indicator", "nothing pads for env(safe-area-inset-bottom) — content can sit under the home indicator");
  else pass();

  // 6. Safari is stricter than Chrome about date strings it will parse.
  const looseDates = [...src.matchAll(/new Date\(\s*["'][^"']*["']\s*\)/g)]
    .map(m => m[0]).filter(s => !/\d{4}-\d{2}-\d{2}/.test(s));
  if (looseDates.length) bad(file, "safari-date-parse", `non-ISO date strings Safari may refuse: ${looseDates.slice(0,3).join(", ")}`);
  else pass();
}

console.log(`\n${problems ? problems + " PROBLEM(S)" : "Clean"} — ${checks} checks across ${APPS.length} file(s)`);
process.exit(problems ? 1 : 0);
