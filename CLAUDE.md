# CLAUDE.md

Standing context for anyone (or any Claude session) working in this repo.

## What's in this repo

This single repo hosts multiple unrelated projects, all served from one GitHub Pages site:

- **Root** — four self-contained party games, each a single HTML file with both local pass-and-play mode and Firebase-backed multiplayer mode in one `<script type="module">`:
  - `index.html` — Chameleon
  - `firsttoworst.html` — First to Worst (no AI player option here — deliberately removed, don't re-add it)
  - `trivia.html` — Trivia Party
  - `doodle.html` — Doodle & Guess
- **`docs/packing-list/index.html`** — a family packing-list app (open access, no login).
- **`docs/subscriptions/index.html`** — a subscription tracker, login-protected (see Firebase section below).
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
- Client-side access checks (show/hide UI) are not the real security boundary — the Firestore rule is. Don't treat a client-side gate as sufficient on its own.

## Workflow used in this repo

- Never push directly to `main`. Branch off fresh `origin/main` → commit → push → open a PR → squash-merge via the GitHub MCP tools.
- Other branches/sessions may merge into `main` between your edits — always `git fetch origin main` and branch fresh from `origin/main` before starting new work rather than reusing a stale local branch or continuing on an already-merged branch.
- Before shipping any change to the game/app HTML files, run `node --check` on the extracted `<script type="module">` contents, and where feasible simulate the actual flow with jsdom plus hand-written mocks for Firebase calls, rather than assuming the code works from a read-through. Several real bugs here were only caught this way (an `id="input-name"` scope bug, a falsy-zero rotation bug, a duplicated-header bug, a corrupted `createElement("localCanvas")` typo, and more).

## Lessons learned the hard way (don't repeat these)

- **GitHub Pages settings can be changed by anyone with push access to any branch in this repo**, not just people working on the thing that broke. Don't assume "the site is broken" means a code bug — check Pages settings (Settings → Pages) and do a live `curl` against the actual deployed site before diagnosing further.
- **Firebase's default Google sign-in (popup or redirect) relies on a cross-domain iframe/storage handshake** against the project's `authDomain`, which mobile Safari's default third-party storage blocking (and some managed/corporate device profiles) can break in ways that look like app bugs but aren't. The subscriptions app supports Google, email-link, and email+password sign-in specifically so there's always a fallback that doesn't depend on that handshake.
- **A PR merge from another branch can bring in an older snapshot of a file than that branch's actual current tip**, if the PR was opened before the branch kept evolving. If something looks reverted after a merge, diff against the branch's actual current HEAD, not just the merged commit.
- When a user reports data loss or "this used to work," verify what actually changed (git history, live `curl`, Firestore REST reads) before concluding what happened — and before reassuring anyone nothing was lost.
