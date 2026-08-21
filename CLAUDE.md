# CLAUDE.md

Standing context for anyone (or any Claude session) working in this repo.

## What's in this repo

This single repo hosts multiple unrelated projects, all served from one GitHub Pages site:

- **Root** — self-contained party games, each a single HTML file with both local pass-and-play mode and Firebase-backed multiplayer mode in one `<script type="module">`. Run `ls *.html` at the repo root before assuming this list is complete — it has gone stale before:
  - `index.html` — Chameleon
  - `firsttoworst.html` — First to Worst (no AI player option here — deliberately removed, don't re-add it)
  - `trivia.html` — Trivia Party
  - `doodle.html` — Doodle & Guess
  - `spillit.html` — Spill It! (family trivia about each other; kid-safe prompt bank only, no adult content)
  - `milim.html` — Milim (guess the meaning of a Hebrew/Aramaic word; typed answers are fuzzy-matched, host can tap any call to correct it)
  - `climbers.html` — Climbers (race up a mountain, climbing your own colored blocks or the shared gray ones)
  - `dontcopyme.html` — Don't Copy Me (don't match anyone else's answer — or the Judge's)
- **`docs/packing-list/index.html`** — a family packing-list app (open access, no login).
- **`docs/subscriptions/index.html`** — a subscription tracker, login-protected (see Firebase section below).
- **Home utilities**, all login-protected and all stored under `homeApps/` in the same Firebase project as the packing list:
  - `docs/medicine/index.html` — Medicine Timer, a shared log of who has had what and when. It is a **log, not medical advice**: it never suggests an amount (no mg, no ml, no weight-based dosing), only the gap between doses and the 24-hour maximum that are printed on the packet.
  - `docs/renewals/index.html` — passports, MOT, insurance and the like, each with its own notice period.
  - `docs/returns/index.html` — things that need sending back before a deadline.
  - The last two are checked daily by `.github/workflows/home-deadline-alerts.yml` and push ntfy alerts.
- **Other branches** in this repo contain unrelated side projects (bombsweeper, bowling, mr-bendy, stock tracking, etc.) started in other sessions. Don't assume they share context with the above, and don't merge them into `main` without understanding what they touch first.

## Deployment

- GitHub Pages serves from `main`, root folder, via `.github/workflows/deploy-pages.yml` (Actions-based deploy).
- **This was deliberately switched from "Deploy from a branch."** That legacy setting let anyone with push access to *any* branch in this repo repoint the live site — it caused two real outages. Do not switch Pages' source back to "Deploy from a branch" in repo Settings.
- Live site root: `https://leodhi.github.io/claude/`
- After merging to `main`, allow a couple minutes for the Actions workflow to redeploy. Verify with a cache-busting `curl` before assuming a fix landed or didn't.

## Firebase

- The four games each use their own Firebase project for multiplayer sync (see `firebase-config.js`).
- The packing list and subscription ledger **share one Firebase project** (`packing-list-3c532` — historically named for the packing list, now used for both). Firestore collections:
  - `packingLists/family` — open, no auth required.
  - `subscriptionLedgers/family` — auth-gated, single owner. Ownership is matched by `ownerEmail` (requires `emailVerified`) or `ownerUid`, so any of three supported sign-in methods (Google, email link, email+password) are recognized as the same person. Whoever signs in first permanently claims the ledger.
- **Firestore security rules are edited manually via the Firebase console** — no API/tool access exists to read or write them from a Claude Code session. When a rule needs to change, give the user the exact rule text to paste, then verify the change actually took effect with a real `curl` test against the Firestore REST API (with and without auth) rather than assuming it worked from the rule text alone.
- **The current rules live in `firestore.rules` at the repo root.** Since they can't be read back out of the console, that file is the only record of what was published — update it in the same commit whenever the pasted text changes, or it silently goes stale.
- **Rules can and should be tested before handing them over.** Java and Node are both available in this environment, so `npx firebase emulators:exec --only firestore` plus `@firebase/rules-unit-testing` runs the real rules engine locally — owner allowed, stranger denied, signed-out denied, and so on. This caught nothing the first time only because it was run first; don't skip it and hope. Note that an unauthenticated `curl` returns 403 both when a rule is missing and when it's correctly locked down, so `curl` alone cannot tell you a private rule is working — the emulator or the app itself can.
- Client-side access checks (show/hide UI) are not the real security boundary — the Firestore rule is. Don't treat a client-side gate as sufficient on its own.

## Workflow used in this repo

- Never push directly to `main`. Branch off fresh `origin/main` → commit → push → open a PR → squash-merge via the GitHub MCP tools.
- Other branches/sessions may merge into `main` between your edits — always `git fetch origin main` and branch fresh from `origin/main` before starting new work rather than reusing a stale local branch or continuing on an already-merged branch.
- Before shipping any change to the game/app HTML files, run `node --check` on the extracted `<script type="module">` contents, and where feasible simulate the actual flow with jsdom plus hand-written mocks for Firebase calls, rather than assuming the code works from a read-through. Several real bugs here were only caught this way (an `id="input-name"` scope bug, a falsy-zero rotation bug, a duplicated-header bug, a corrupted `createElement("localCanvas")` typo, and more).

## Before building anything new, read the existing apps first

Whenever you're building a new app or game — or adding a new screen to an existing one — go and **read the other apps and games in this repo in full first**, and copy anything relevant. Don't work from memory, and don't assume this file captures everything: the apps themselves carry accumulated preferences and quirks that were never written down here. If something in them is relevant and copyable, copy it.

That means layout and wording conventions, the shape of forms, how sheets open and close, sign-in flows, empty states, safety notes, control patterns, the native-feel rules below — all of it.

This is not hypothetical; it has already cost a rebuild. The Medicine Timer's medicines editor was built as a cramped row of unlabelled number boxes plus a `prompt()`, and the user's reaction was "I don't even know what it means, and it's confusing." Meanwhile `docs/renewals/index.html` already had exactly the right pattern sitting in the repo: an add/edit sheet with a plain-English `<label>` above every single field, an example placeholder in each input, and a short note in ordinary words next to any number explaining what the number does. Copying that from the start would have avoided the whole thing.

## Making web apps in this repo feel native (mobile)

These apps are used mostly as "Add to Home Screen" pseudo-apps on phones, so apply these by default whenever creating or touching one of the interactive HTML apps, not just when asked:

- Animate with `transform` (`translateX/Y`, `scale`) and `opacity`, never `top`/`left`/`width`/`height` — transforms are GPU-accelerated, the others force layout/reflow and feel janky.
- Use real easing curves on transitions (e.g. `cubic-bezier(.2,.9,.3,1.1)`-style, with a little overshoot for playful UI), not the browser default linear/ease. This is the single biggest lever on "feel."
- Give every tappable element (buttons, chips, cards) a `:active` state — a quick `transform: scale(0.92–0.96)` — so taps have immediate visual feedback, plus `touch-action: manipulation` to kill any tap delay/double-tap-zoom.
- Modals/sheets should fade and slide or scale in (`opacity` + `transform`, base state hidden via `opacity:0; visibility:hidden; pointer-events:none`), never just snap via `display:none`/`display:flex`.
- Match iOS conventions: cards/panels ~14-16px corner radius, controls/inputs ~8-10px, pill buttons `border-radius:999px`, spacing roughly on an 8px grid. Inconsistent radii/spacing is a big part of what makes something read as "a webpage" instead of "an app."
- Set `-webkit-tap-highlight-color: transparent` on `*` and `overscroll-behavior-y: contain` on `html, body`. Without these, taps flash a gray highlight box and the whole page rubber-bands/threatens a browser refresh when you scroll past the top — both are dead giveaways it's a webpage, not an app.
- Keep it simple — don't add animation/motion beyond this list unless asked; the goal is snappier default interactions, not a redesign.

## Lessons learned the hard way (don't repeat these)

- **GitHub Pages settings can be changed by anyone with push access to any branch in this repo**, not just people working on the thing that broke. Don't assume "the site is broken" means a code bug — check Pages settings (Settings → Pages) and do a live `curl` against the actual deployed site before diagnosing further.
- **Firebase's default Google sign-in (popup or redirect) relies on a cross-domain iframe/storage handshake** against the project's `authDomain`, which mobile Safari's default third-party storage blocking (and some managed/corporate device profiles) can break in ways that look like app bugs but aren't. The subscriptions app supports Google, email-link, and email+password sign-in specifically so there's always a fallback that doesn't depend on that handshake.
- **A PR merge from another branch can bring in an older snapshot of a file than that branch's actual current tip**, if the PR was opened before the branch kept evolving. If something looks reverted after a merge, diff against the branch's actual current HEAD, not just the merged commit.
- When a user reports data loss or "this used to work," verify what actually changed (git history, live `curl`, Firestore REST reads) before concluding what happened — and before reassuring anyone nothing was lost.
- **`vh` on iOS Safari is the height with the toolbars hidden, not the height you can see.** A bottom-pinned sheet capped at `max-height: 88vh` came out 743px tall inside a 640px visible window, so its top rode up off the screen and the title and first field were simply not there — at any scroll position. Headless Chromium resolves `vh` as the viewport you set, so a desktop-driven UI audit passes this every single time and cannot see it. Size sheets and overlays against their own fixed-position container (`max-height: 88%`) or `dvh`, never `vh`, and when a bug is reported on a phone, check whether the mechanism is one the test environment is structurally incapable of reproducing before concluding it's fixed.
- **A jsdom or Playwright mock that is kinder than the real service hides real bugs.** The Firestore mock did a shallow `Object.assign`, replacing whole maps; real Firestore merges nested maps key by key. Deleting anything by writing the map back without that key therefore worked in every test and silently failed in production, with the item returning on the next sync. Mocks must copy the real merge, delete and error semantics, and there must be exactly one copy of the mock — `test-medicine.js` kept its own duplicate and quietly kept the old behaviour after the shared one was fixed.
- **A session's machine gets shut down after a long idle stretch, and it kills anything still running.** Observed in one session: a 45-minute quiet gap survived fine, but a 1h46m gap ended in "The container was restarted... background tasks are now stopped" — which silently killed a `until curl ...; do sleep 10; done` deploy watcher, so a promised deploy confirmation never arrived. Don't leave a long-running watcher as the thing that reports back to the user; finish the check within the turn, or set up a scheduled workflow that doesn't depend on the session staying alive.

## Confirming edits to this file

Whenever CLAUDE.md itself is changed — especially when the user asked for the change — **say so explicitly in the reply**: name the section added or edited and quote the gist of the new wording back. The user can't see the file from their side and has been left unsure whether an update actually landed. A silent edit doesn't count as done.

## Delivering a finished app (do this every time, without being asked)

Whenever an app is created — or an existing one is given a new icon — finish the job like this:

- **Offer 10 icon options to choose from.** Design them, render them as one contact sheet showing each at large size *and* at actual home-screen size (~60px), and send that image. Small-size legibility is the real test; several designs that look great large turn to mush at 60px, so check the render and redraw the ones that don't hold up rather than shipping them.
- **Once the user picks**, commit that icon at 180×180 to match the existing `icon-*.png` files, and send the chosen design back as a **1024×1024 PNG** they can save to their photos.
- **Give a clean, copyable link** to the finished app on its own line, with no surrounding punctuation that would get selected along with it.

Chromium is preinstalled for rendering (see the note about `executablePath` in the environment); there is no ImageMagick or PIL, so draw icons as SVG and screenshot them.

## Notifications / alerts

- The user has the [ntfy](https://ntfy.sh) app installed and is fine using it for push notifications (renewal reminders, alerts, etc.) from apps in this repo. Since these are static sites with no backend, the pattern is: a GitHub Actions scheduled workflow does the periodic check and POSTs to the user's ntfy topic — see the subscription-renewal-alerts feature for the reference implementation (Firebase service account as a GitHub secret, ntfy topic as a GitHub secret, never hardcoded in a workflow file since this repo is public). Default to proposing ntfy for any future "remind me about X" idea rather than re-deriving alerting options from scratch.

## How to communicate with this user

- **The family is American — write all user-facing wording in American English.** Truck, cookie, eggplant, rooster, soccer ball, french fries, candy, soda; not lorry, biscuit, aubergine, cockerel, football, chips, sweets, fizzy drink. Where a voice reads text aloud, prefer an American voice too. This is not hypothetical: Odd One Out shipped with a British picture bank ("my son will have no clue what that is") because this repo contains UK-specific things — MOT reminders, the renewals app — and that was read as the family being British. Don't infer nationality, or anything else about the family, from what happens to be in the repo; ask, or ask here first.
- The user is new to Claude Code and AI coding tools generally. When explaining how to do something, skip unnecessary jargon — explain plainly, or better, just do it directly rather than describing the steps for them to do it.
- **The user is not a coder and asks for plain English, step by step.** Anything technical needs explaining in ordinary words, in order, one point at a time — not a wall of prose and not a pile of terms. Name a thing before using it: "the index (a small list of which lists exist)" rather than assuming `_index`, `merge`, `cache`, `snapshot`, `DOM` or `commit` mean anything. When there are numbered steps to follow, actually number them. Analogies to everyday things are welcome. Never let an explanation trail off into implementation detail the user did not ask for — if the detail matters, say why it matters to them first.
- Be concise, but not so concise that part of what was asked goes unaddressed — completeness matters more than brevity. Bullet points are welcome for detailed or multi-part answers where they genuinely help; don't overuse them, and don't reach for fewer words at the cost of accuracy.
- If you're not sure what the user means, ask. If something needs a factual answer (an API's actual behavior, a product's actual settings layout), look it up rather than guessing and presenting the guess as fact.
- **A question is not an instruction to change something** — but don't be rigid about it. Judge what the user is actually after, and lean towards acting:
  - **Just do it** when what they want is fairly obvious, even if they didn't phrase it as a command. "This looks off", "the button is too small", "shouldn't it do X?", or an instruction about how to work together, are all clear enough — act, then say what you did. Asking here is annoying, not careful.
  - **Answer, don't act**, when it's a genuine question about how something works ("why does X happen?", "can you do Y?"). Give the answer; offer to make the change if one seems wanted.
  - **Ask with `AskUserQuestion`** (tappable options, not a typed reply) only when it genuinely matters: real alternatives that lead to different results, a change that's hard to undo or touches data, or a request that could reasonably be read two ways. One popup, then get on with it — don't stack popups or re-ask something already settled.
  - Read the whole message before acting — a later line often changes or cancels what an earlier one asked for.
  - When unsure, prefer doing the smaller, easily-reversible version and saying so, over stopping to ask.
- Don't decide process changes on the user's behalf. Things like how work is grouped into pull requests, or what gets skipped to save effort, are theirs to choose — propose it and let them answer, rather than announcing a new default.
- Don't give up on a request just because the first approach doesn't pan out. Before concluding something "can't be done" or suggesting a workaround (e.g. "just use a different device"), think through other real approaches and try them — the fix often turns out to exist. If the user has to be the one to suggest the next idea, that's a sign to slow down and think harder before answering, not a one-off.
- When troubleshooting, reach for the simplest viable fix before the more elaborate one. When Google sign-in broke on one device, the right early move was offering a plain email+password fallback — not multiple rounds of debugging popups/redirects/cross-site cookies before finally landing on the simple option. Default to the easy path first; only go deeper into the complex/technical fix if the simple one genuinely doesn't cover the need.

## Verifying a bug fix

- Never declare a bug fixed based on reading the code alone. Reproduce the actual symptom first — render it, run it, simulate it, screenshot it — then confirm the same reproduction no longer shows the symptom after the change.
- Keep looking for other contributing causes even after finding one plausible bug. One explanation that fits isn't the same as the only explanation — don't stop at the first one that seems plausible.

## Git/PR workflow (this repo)

- After pushing a fix or feature branch, always open a pull request. Pushing to a branch alone is not "done."
- Once the fix/feature is verified working (per the reproduction rule above), push the branch, open the PR, and merge it in the same pass — don't stop and wait for approval to merge. Merging is part of finishing the task, not a separate step that needs sign-off.
- Exception: never merge or overwrite changes touching other unrelated projects/branches that already live in this shared repo without explicit confirmation first — this repo hosts multiple people's/sessions' separate projects side by side, and "done" on one project's task never means touching another's.
