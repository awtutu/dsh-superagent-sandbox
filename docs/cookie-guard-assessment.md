# dsh-cookie-guard assessment for the DSH stack

Scope and method: this is a **read-only** assessment done entirely through the
GitHub REST/search API (`gh api`) and web search. Nothing was cloned, built,
`npm install`ed, or run; no scheduled task, plugin, or script from any
repository mentioned here was executed. No real browser profile, no DSH
profile, and no path under `D:\tuji-homes` was touched — the assessment ran
on a Linux sandbox with no Windows filesystem or browser profile present at
all.

## 0. The two repositories named in Issue #18 do not exist

Issue #18 asks to compare:

- `https://github.com/rockerhxd/dsh-cookie-guard`
- `https://github.com/HongGeng/dsh-cookie-guard`

Verification performed 2026-11-20:

| Check | `rockerhxd` | `HongGeng` |
| --- | --- | --- |
| `gh api repos/<owner>/dsh-cookie-guard` | `404 Not Found` | `404 Not Found` |
| `gh api -X GET "search/users?q=<owner>"` | `0` results — **no GitHub account named `rockerhxd` exists** | `13` results; one exact match, login `honggeng` (id `32153130`) |
| `gh api users/<owner>/repos` (for the account that does exist) | n/a | 6 public repos, all created 2017‑09/10, none named `dsh-cookie-guard` or cookie‑related (`-`, `1019`, `1020`, `exer`, `exer2`, `rong`) |

So: the `rockerhxd` account does not exist at all, and the `honggeng`
account exists but has never owned a `dsh-cookie-guard` repository. **Neither
URL in the issue resolves to a real, inspectable artifact.** Sections 1–6
below cannot describe "the real/upstream implementation" of something that
is not there; this is the primary finding of this assessment, not a gap to
guess around.

### What does exist: a crowded, suspicious "dsh-cookie-guard" namespace

A GitHub code/repo search for `dsh-cookie-guard in:name` (run read-only via
`gh api search/repositories`) turns up a different picture: **at least 17
separate repositories**, all pushed within the last three weeks
(2026‑10‑29 to 2026‑11‑19), owned by unrelated, mostly brand‑new, low‑
reputation accounts, all pitching an almost identical "clean up DSH's
`dsh-auth-*` login cookies before the app crashes" idea:

| Repo | Owner account created | Stars | Notes |
| --- | --- | --- | --- |
| `jitianjiyan/dsh-auth-cookie-guard` | 2025‑08‑03 | 44 | by far the most starred / forked (2 forks); in‑process plugin, see §1 |
| `3150481853/dsh-cookie-guard` | — | 3 | numeric throwaway‑style username |
| `syhliuyiqing/dsh-cookie-guard` | — | 2 | |
| `kevindawn11-hash/dsh-cookie-guard` | — | 2 | |
| `mxw0808/dsh-cookie-guard` | 2026‑11‑01 (same day as the repo) | 1 | account has 2 public repos total, 0 followers; inspected in §1/§3 |
| `M0Yun/dsh-cookie-guard`, `kongbaiwin/…` | — | 0–1 | |
| `Yuki-cutesnow/…`, `bigfatdsh/…`, `AnxietyQAQ/…`, `kr9528/…`, `woshixiaoshuai2333/…`, `1938321675/…`, `dsaf56kjsd/…`, `vi0let-dev/dsh-auth-cookie-guard`, `Ethan1999991231/dsh-auth-cookie-guard`, `20100803Kyle/dsh-cookie-guard-mac` | — | 0 | |

Web search independently surfaces several of the same names plus listings on
unofficial aggregator sites (`awesome-dsh-plugin.com`, `dshplugin.store`, an
npm package page) that promote this plugin family — sites this assessment
did not log into or treat as authoritative. Many owner accounts are days-old
with single-digit repo counts and no followers — a pattern consistent with a
short-lived naming rush (copy/paste forks chasing the same real DSH pain
point) or, less charitably, a coordinated attempt to get a cookie‑reading
tool trusted/installed under a name that sounds official. Issue #18's two
named URLs point at **neither** of the two accounts in this list — they
point at an account that doesn't exist and an unrelated 2017 account — which
is itself consistent with a typo, a stale/removed link, or someone quoting
URLs they never actually opened.

**Because the named subject of this assessment is unverifiable, sections 1–6
describe the general pattern found in two representative, currently public
samples (`mxw0808/dsh-cookie-guard` and `jitianjiyan/dsh-auth-cookie-guard`,
chosen for being the most Python‑script‑like and the most‑starred
respectively) strictly as supporting context — not as a comparison of the
two repositories the issue asked for, since those do not exist.**

## 1. What this plugin family does and how it works

The real bug both samples describe is the same, and matches known DSH
behavior: the desktop Host binds a random loopback port on every launch, and
mints a login cookie named `dsh-auth-<base64url(sha256(host:port))>` with a
30‑day `Max-Age`. Browsers key cookies by host, not port, so every launch
adds one more ~170‑230 byte cookie that nothing ever removes. Once the
`Cookie` header for `127.0.0.1` crosses Node's default 16 KiB
`maxHeaderSize` (after roughly 70 or so launches), the handshake fails with
HTTP 431, which the desktop client reports as a permanent, unrecoverable
"Web authentication failed" — the profile is locked out until its cookie
jar is wiped. Two different fix strategies were found in the family:

- **`mxw0808/dsh-cookie-guard`** — an **external, local, offline** fix. A
  Node "host-plugin" half registers a Windows `schtasks` weekly task (no
  admin rights) that runs a PowerShell wrapper, which in turn runs a Python
  script. That script: waits for DSH to fully exit (the SQLite file is
  locked while running), copies `%APPDATA%\@deepseek-ai\dsh-desktop\Network\
Cookies` to a temp file, counts rows whose `name` starts with `dsh-auth-`,
  and — only above a configurable threshold (default 40) — renames
  (backs up) the whole SQLite file and lets DSH recreate an empty one on
  next launch. It reads cookie **names and byte lengths** via SQL, never
  cookie **values**, and performs no network calls. The plugin's on/off
  switch in DSH's plugin list is read by the scheduled task itself (via the
  profile's `package.json`), so disabling the plugin makes the weekly task a
  no-op without needing to touch Task Scheduler.
- **`jitianjiyan/dsh-auth-cookie-guard`** — an **in-process, no-filesystem,
  no-network** fix. It hooks the Host's own `webServer` and does two things:
  raises `server.maxHeaderSize` to 64 KiB (configurable), and, on each
  request, deletes (`Set-Cookie: ...; Max-Age=0`) all but the newest `keep`
  (default 4) minted `dsh-auth-*` cookies plus whatever cookie the current
  connection is authenticating with. It only ever matches the exact minted
  name shape, never decodes a cookie's value, and the whole module imports
  only `node:crypto`.

Both describe themselves as narrowly scoped to the `dsh-auth-*` cookie name
and claim zero network egress; neither claims to read, store, or transmit
cookie *values*, encryption keys, or other site data. These are **README and
source-comment claims from unverified, low-reputation accounts**, not
independently audited guarantees — see §3.

## 2. Repo comparison

Not meaningfully answerable for the two URLs the issue names, because
neither resolves (§0). Comparing the two illustrative samples instead:

| | `mxw0808/dsh-cookie-guard` | `jitianjiyan/dsh-auth-cookie-guard` |
| --- | --- | --- |
| Upstream vs. fork | Not a fork (`fork: false`) | Not a fork (`fork: false`) |
| Repo created / last push | 2026‑11‑01 / 2026‑11‑04 | 2026‑10‑30 / 2026‑11‑19 |
| Owner account age | Created same day as the repo | Created 2025‑08‑03 |
| Stars / forks | 1 / 0 | 44 / 2 |
| Open issues | 0 | not checked beyond metadata |
| License | MIT | MIT |
| Platform / runtime deps | Windows only; `schtasks`, Python 3.8+, `node:child_process`/`fs`/`os`/`path` | Any OS the Host runs on; `node:crypto` only |
| Release/version | No GitHub Releases seen; `package.json` `1.0.0` | README references published npm package and a `1.0.4` behavior change |

Neither sample is a fork of, or otherwise provably related to, the other —
they are independent reimplementations of a fix for what looks like the same
real, previously-reported DSH defect (one via an external scheduled task and
local SQLite surgery, the other via an in-process HTTP header/cookie patch).
Because of the sheer number of near-duplicate repos found (§0), no claim
here should be read as "these two are *the* two implementations" — they are
two samples out of 17+ found, chosen only to ground the write-up in real
source rather than speculation.

## 3. Security review (of the samples actually inspected — not of the named, non-existent URLs)

- **Data read**: `mxw0808`'s script reads the DSH desktop `Network\Cookies`
  SQLite file (`name`, `length(value)`, `length(encrypted_value)` — never
  the decrypted value) to count/size `dsh-auth-*` rows.
  `jitianjiyan`'s plugin reads only the `Cookie` request header names of
  connections to DSH's own local webserver.
- **Data stored**: `mxw0808` writes a plaintext local log/report
  (`cookie-report.txt`, `%LOCALAPPDATA%\dsh-cookie-guard\cookie-weekly.log`)
  containing counts and byte sizes, and a one-time pre-delete backup of the
  **entire** Cookies SQLite file (`Cookies.bak-<timestamp>`, left on disk
  indefinitely — the README calls this out as something to "periodically
  clean up by hand", i.e. the backup itself is a lingering copy of every
  other cookie too, not just `dsh-auth-*`). `jitianjiyan` stores nothing.
- **Encryption / key handling**: neither sample touches Chromium's
  `encrypted_value`/DPAPI key material or decrypts anything; `mxw0808`
  explicitly reads only `length(encrypted_value)`, never the bytes.
- **Network behavior**: both claim, and their minimal import lists support
  (`node:crypto` only for one; `child_process`/`fs`/`os`/`path` plus a
  Python stdlib script for the other — no `http`, `https`, `net`, `fetch`,
  `requests`, or `urllib` imports seen in the files fetched), **zero**
  outbound network calls. This was checked only at the file level visible
  through the GitHub Contents API for the files listed in each repo tree —
  not a full dependency/supply-chain audit (neither declares any npm
  dependency beyond Node builtins, so there is no transitive package to
  audit either).
- **Elevation**: `mxw0808`'s scheduled task is created with `schtasks
  /Create` under the **current user**, no admin/elevation requested; it
  explicitly notes it cannot override a same-named task created by an
  administrator. `jitianjiyan` requests no elevation (pure in-process JS).
- **Update behavior**: neither sample implements its own auto-update
  mechanism; both rely on DSH's normal plugin install/update flow
  (`dsh plugin add <name>`, or npm version bumps for `jitianjiyan`'s
  published package). There is no self-updating code to review.
- **Uninstall/cleanup**: `mxw0808` deletes its scheduled task in the
  plugin's unload hook (`schtasks /Delete`); `jitianjiyan` restores the
  original `maxHeaderSize` on plugin `dispose`. Neither claims to remove its
  own log files or Cookies backups on uninstall.
- **What this review cannot establish**: these are two samples picked from
  17+ near-identical, largely unaudited, mostly brand-new repositories. The
  claims above hold for the specific files fetched on 2026‑11‑20 from these
  two specific repos and say **nothing** about any other repo in the
  family, about future pushes to the same repos, or — critically — about
  the two repositories Issue #18 actually names, which do not exist to
  review. A plugin that silently decoded, logged, or exfiltrated cookie
  *values* (as opposed to names/lengths) would look almost identical in a
  README to the ones inspected here; README claims of "no network, no
  logging of values" are not independently verifiable without a full,
  ongoing source diff on every version bump.

## 4. DSH fit

If DSH genuinely has the port-bound, ever-growing `dsh-auth-*` cookie defect
both samples describe (consistent with the symptom "431 / permanently
locked-out profile after ~70 launches" referenced in both READMEs), the
natural place to fix it is **inside DSH's own Host/webServer and
client-connection code** — e.g. stop minting a new cookie name per random
port, actively prune on the welcome handshake, or raise the header budget
server-side — not via a third-party browser/profile-touching plugin:

- A plugin that edits the **DSH desktop Cookies SQLite file directly**
  (the `mxw0808` style) sits squarely in "edit a real browser profile" —
  exactly what Issue #18's own constraints forbid touching during this
  assessment, and a production install of such a plugin is functionally
  indistinguishable, from the OS's point of view, from malware that reads a
  browser's cookie store: same file, same permissions, same read API. Any
  bug or malicious revision could trivially widen from "read cookie
  names/lengths" to "read and exfiltrate cookie values" with no visible
  change to the install flow.
- A plugin that only patches the **in-process Node `http.Server` header
  budget and issues `Set-Cookie: Max-Age=0` for its own minted cookie shape**
  (the `jitianjiyan` style) is much better scoped: no filesystem access to a
  browser profile, no new process, no scheduled task, and it only ever acts
  on requests to DSH's own loopback listener — closer to "fix inside DSH"
  without actually being merged into DSH.
- **Can it be scoped to one browser/profile?** The `mxw0808` style is
  already scoped to DSH's own bundled Chromium profile
  (`%APPDATA%\@deepseek-ai\dsh-desktop\...`), not a user's regular browser —
  but "DSH's own profile" is still exactly the kind of real profile the
  issue says not to touch, and there is no dry-run/read-only mode wired into
  DSH's plugin install flow that would let us pilot it without that plugin
  being able to write to that file the moment it is enabled.
- **Does it need a fork?** Given the review in §3 could only cover two
  non-authoritative samples and the two URLs actually named in the issue do
  not exist, adopting *any* variant as-is would mean trusting unaudited code
  from a brand-new, low-reputation GitHub account to run unattended against
  a real credential store. If this is pursued at all, forking a single,
  explicitly chosen, from-source-reviewed copy (not `npm install`ing a
  package by name, since the npm registry entry seen in search results
  cannot be assumed to match any specific GitHub source 1:1) would be the
  minimum bar before any pilot.

## 5. Verdict: **reject (as literally asked) / defer (as a general idea)**

- **Reject** the specific request in Issue #18 as asked: the two named
  repositories do not exist, so there is nothing to adopt, pilot, or even
  meaningfully compare. Recommend closing this specific comparison as "no
  such artifact" rather than treating any other repository as a silent
  substitute for what was asked.
- **Defer** the broader idea of adopting *some* `dsh-cookie-guard`-style
  plugin. The underlying problem (if real) is worth fixing, but:
  1. The entire visible ecosystem around this name is 0–3 weeks old,
     dominated by brand-new/low-reputation accounts, and large enough (17+
     near-duplicate repos) that it reads more like a naming collision or
     swarm than one legitimate project with a canonical home — there is no
     single account here with the standing to call "upstream."
  2. The most defensible fix shape (in-process header/cookie patch, no
     filesystem access) still requires trusting unaudited third-party code
     running inside the Host process; the shape that is easiest to audit
     for "no network calls" (`mxw0808`'s style) is also the shape that
     directly edits a real credential store on disk, which this ticket is
     explicitly forbidden from validating by actually installing it.
  3. If the root cause is real, it is a DSH defect and belongs in a DSH
     issue/fix tracked upstream in DSH itself, not patched around by a
     community plugin whose provenance cannot currently be verified.

## 6. If this is piloted anyway: minimum steps, test profile, rollback

Not recommended given §5, but if a human decides to pilot a *specific,
already-source-reviewed* copy of one variant:

1. **Never** install into a real DSH profile or a real browser profile.
   Create a disposable DSH profile (a fresh, throwaway `userData`/profile
   directory with no real login state) solely for this test, separate from
   any directory a human actually uses day to day.
2. Pin to one specific commit SHA of one specific, already-reviewed fork —
   not a mutable branch, not `npm install <name>@latest` — and diff every
   subsequent update against that SHA before upgrading.
3. Prefer the in-process/no-filesystem shape (`jitianjiyan`-style) over the
   external-scheduled-task/SQLite-editing shape for the pilot, since it has
   no access to the Cookies file at all and nothing to roll back on disk.
4. Run the pilot with outbound network access blocked at the OS/VM level
   for the pilot profile, so "claims no network calls" becomes an enforced
   property instead of a README claim.
5. **Rollback**: disable/remove the plugin from the disposable profile's
   plugin list and discard the disposable profile directory entirely; if
   the external-task variant was used, also confirm via Task Scheduler that
   `schtasks /Delete` actually removed its weekly task, and delete any
   `Cookies.bak-*` backup file it created.

## Sources

- Issue #18's two named URLs: `https://github.com/rockerhxd/dsh-cookie-guard`,
  `https://github.com/HongGeng/dsh-cookie-guard` — both checked via
  `gh api repos/<owner>/dsh-cookie-guard` (`404`) and `gh api "search/users?q=<owner>"`
  (2026‑11‑20).
- [jitianjiyan/dsh-auth-cookie-guard](https://github.com/jitianjiyan/dsh-auth-cookie-guard) — README, `index.js`, repo/owner metadata via `gh api` (2026‑11‑20).
- [mxw0808/dsh-cookie-guard](https://github.com/mxw0808/dsh-cookie-guard) — README, `index.js`/`lib/index.js`, `scripts/dsh_cookie_guard.py`, `scripts/dsh_cookie_weekly.ps1`, `package.json`, repo/owner metadata via `gh api` (2026‑11‑20).
- `gh api search/repositories?q=dsh-cookie-guard+in:name` — full list of 17 matching repositories, their owners, star counts and push dates (2026‑11‑20).
