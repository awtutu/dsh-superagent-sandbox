# evolution-computer-use assessment

Subject: [`chenkezhen480/evolution-computer-use`](https://github.com/chenkezhen480/evolution-computer-use)
(npm: [`evolution-computer-use@0.1.0`](https://www.npmjs.com/package/evolution-computer-use)), per Issue #22.

**Scope and method:** read-only. The repository was `git clone`d to a throwaway directory
for faster/offline reading of source text only — nothing was `npm install`ed, nothing was
built (`tsc`/`npm run build`), and no script, test, PowerShell helper, or MCP server from
this repository was executed. All claims about runtime behavior below are either (a) read
directly from source, (b) the project's own README/test-suite claims (flagged as such), or
(c) explicitly marked unverifiable. No real browser profile, no real desktop/DSH profile,
and no path under `D:\tuji-homes` was touched; this review ran on a Linux sandbox with no
Windows machine available, so the Windows-only code paths (`win32.ps1`, foreground/UAC,
background `PostMessage`/UI Automation) could only be read, never run.

**Provenance (read-only checks against the GitHub API and npm registry):** the repo is
genuine and small — 3 commits, all by one author (`ckz`) within a few hours on
2026-11-18, extracting this plugin out of a larger project, `dsh-world` 0.8. The owner
account (`chenkezhen480`) was created 2025-10-15 (~13 months old), has 8 public repos and 3
followers — not a brand-new throwaway account, but this specific plugin repo is two days
old at the time of this review, with 5 stars, 0 forks, MIT license. `evolution-computer-use@0.1.0`
is published on the public npm registry with a matching file count, corroborating that the
npm package and the GitHub source are the same release.

## 1. What it actually does; architecture; dependencies; install path; Windows support

It is a single Node.js (≥22.16) process that is simultaneously an MCP server (stdio,
JSON-RPC, protocol versions `2025-06-18`/`2025-03-26`/`2024-11-05`) and an embeddable JS/TS
library (`createComputerUse()`). It gives an agent three things:

- **Its own browser**: launches/adopts a system Edge or Chrome on a dedicated profile
  directory, driven purely over the Chrome DevTools Protocol (CDP); 8 page-level MCP tools
  (`page_open/page_read/page_click/page_type/page_press/page_scroll/page_wait/page_shot/page_eval`).
- **The user's Windows desktop** (opt-in, off by default): one `desktop` tool, in
  `background` mode (post input to one window without moving the real mouse/keyboard) or
  `foreground` mode (take over the real mouse/keyboard, behind one UAC elevation per
  session).
- **A procedure library**: `computer_use`/`procedure_run`/`procedure_save`/`procedure_note`/
  `procedure_routines` let the agent save a sequence of page/desktop actions as a named JSON
  "procedure" under `<data>/procedures/<category>/<name>.json`, replay it later without the
  model, and fall back to a kept older version when a replay breaks.
- An `inbox_read` tool (only while desktop control is on) that reports taskbar
  flashes/notifications without persisting anything to disk.

**Architecture** (from reading `src/`): `src/browser/` (`edge.ts` find/launch,
`cdp.ts` minimal CDP session, `page.ts`/`pageLib.ts` in-page element reading/acting,
`browser.ts` a single-queue wrapper so two operations never race on one page); `src/desktop/`
(`win32.ps1`, one 858-line PowerShell helper using only `user32.dll`/`dwmapi.dll`/
`UIAutomationClient` P/Invoke calls; `driver.ts` bridges it over stdin/stdout JSON lines, or
over a one-time-keyed named pipe for the elevated foreground helper; `desktop.ts`/`turns.ts`
turn the helper's primitives into the `desktop` tool's actions; `recording.ts`/`watching.ts`
implement short video capture of a window/screen); `src/procedures/` (`format.ts` schema +
validation, `library.ts` file storage/versioning, `run.ts` the replay/fallback engine,
`routines.ts` the `onAlarm` scheduler, `catalog.ts` fuzzy category matching); `src/mcp/
server.ts` (a ~90-line hand-rolled stdio JSON-RPC server, no MCP SDK dependency);
`src/cli.ts` (the `serve`/`resume`/`routines`/`status` CLI); `src/inbox/inbox.ts` (taskbar
watcher). 22 test files / 161 `test()` calls under `tests/`, consistent with the README's
claim of "154 offline tests, 2 live tests skipped by default".

**Dependencies: genuinely zero at runtime.** `package.json` lists only `devDependencies`
(`typescript`, `@types/node`, `@types/ws`, `ws`); `ws` is used only inside the test suite
(`tests/computerCdp.test.ts`) to mock a WebSocket server — grepping `src/` found no import
of the `ws` package. The browser side uses only Node's built-in global `WebSocket`/`fetch`;
the desktop side is one PowerShell script run via `node:child_process`, using nothing but
Windows' own Win32/COM/UI-Automation APIs — no native Node addon, no .NET project to build,
no driver to install.

**Install path**, three confirmed options:
1. MCP stdio server via `npx -y evolution-computer-use [--desktop background|foreground]`
   (fetches the published npm package on first use; this is the README's primary path for
   Claude Code/Codex/Cursor/Windsurf/Claude Desktop config files).
2. A Claude Code "plugin" (`/plugin marketplace add chenkezhen480/evolution-computer-use`),
   which Claude Code fetches via git and runs straight from source
   (`.claude-plugin/plugin.json` runs `node --experimental-strip-types src/cli.ts`, no build
   step, since Node 22 strips TS types natively).
3. As a library (`npm install evolution-computer-use`; `createComputerUse()`) for a host
   that speaks no MCP — the shape a DSH plugin would use if this were ever embedded.

**Windows support**: desktop control is explicitly Windows-only
(`process.platform === 'win32'` gate in `src/computer.ts`); elsewhere, turning it on returns
a fault string and no `desktop` tool is exposed. The browser/procedure side is in principle
OS-agnostic (CDP works the same on any OS with Edge/Chrome), but the README's own
"Not yet verified" list admits the author never checked the browser side on macOS/Linux or
on a Chrome-only machine either — this review cannot add any first-hand verification of
that, only note that the claim is already hedged by the source.

## 2. How it observes/controls the desktop; own browser vs. existing browser; MCP/JS API; separate runtime

- **Browser**: always a **separate** Edge/Chrome instance on a dedicated
  `--user-data-dir`, launched with `--disable-extensions --disable-sync` (so it never
  inherits the user's signed-in extensions/sync state) and `--remote-debugging-port=0`
  (OS picks an ephemeral port; only this process reads the resulting
  `DevToolsActivePort` file, so no other local process can trivially attach without first
  reading that file). It never touches the user's everyday/default browser profile or
  window.
- **Desktop — background mode**: input is **posted** to a window handle via
  `PostMessageW` (click/type/press/scroll), never through the real mouse/keyboard; the
  screenshot is taken via `PrintWindow` so it works even if the window is covered. Opening a
  program tries, in order: an already-open window, a tray icon (via UI Automation), then the
  Start Menu (`Get-StartApps`). A window belonging to a process running as administrator is
  detected (`Elevated(pid)` in `win32.ps1`) and refused with an explicit "use foreground
  mode" message — background mode structurally cannot act on elevated windows.
- **Desktop — foreground mode**: a separate, **elevated** PowerShell helper, started once
  per session behind a real Windows UAC prompt (`Start-Process -Verb RunAs`), reached over a
  named pipe whose name and a random one-time key are generated fresh each session (so an
  unrelated process finding the pipe cannot drive it); only this elevated helper can move the
  real mouse/keyboard, so it can also reach administrator-owned windows and games. Nothing
  about the elevation persists across a restart — the user is asked again every time.
- **MCP/JS API**: a hand-written ~90-line stdio JSON-RPC server (no MCP SDK), exposing a
  **fixed** list of 14 tools whose shape never changes as the agent learns procedures (so
  learning never invalidates a host's prompt cache); the list changes only with the user's
  `desktop`/foreground/inbox switches, announced via `notifications/tools/list_changed`. The
  JS/TS library form (`createComputerUse()`) exposes the same functionality as plain
  async methods (`tools()`, `call()`, `setDesktop()`, `setForeground()`, `routines()`,
  `status()`) for a host that does not speak MCP at all.
- **Separate runtime**: no daemon, no database, no self-installed scheduled task. The one
  Node process spawns at most: the browser it drives (adopted or launched), one PowerShell
  child for background desktop mode, and one elevated PowerShell child for foreground mode.
  `evolution-computer-use routines` is meant to be invoked by **the host's own** scheduler
  (e.g. cron/Task Scheduler); the plugin does not register anything on its own.

## 3. Comparison with our screen/action/cdp buses

**This section is the weakest part of this assessment and is explicitly flagged as such**:
the issue describes our own stack only in one line — "screen-bus 8765, vision-bus 8766,
action-bus 8768, cdp-bus 8769, and a human-like desktop loop" — and none of that stack's
source lives in this repository or was otherwise made available for read-only inspection
here. The comparison below is therefore a comparison of *what this one line says our stack
is* against *what `evolution-computer-use`'s source actually does*, not a verified,
code-level diff of two systems; a real comparison would need the same depth of source
reading applied to our own buses, which was out of reach for this ticket.

- **Likely overlap**: "drive a browser via CDP" (our `cdp-bus`) and "screenshot + act on
  desktop windows" (our `screen-bus`/`action-bus`/human-like loop) are exactly the two
  capabilities `evolution-computer-use` reimplements itself, independently, inside one
  package (`src/browser/`, `src/desktop/`). If our four buses already cover both at
  production quality, adopting this package wholesale would mean running a second,
  unaudited (by us) implementation of the same two capabilities side by side with our own.
- **Likely gap/addition**: the **procedure library** (learn once → replay without the model
  → stop-and-explain on a broken replay → fall back to the last two working versions →
  shared across agents via one folder) is not implied by the one-line description of our
  stack at all. If true, this is the one piece that is not "the same thing done twice."
- **Token/step savings**: plausible and is the project's own central claim — replay is
  "without the model, with no step-by-step exploration." The project's one internal,
  self-reported experiment (a mock site, three redesigns, five tasks, pre-registered rules,
  described in `docs/experiments/`) found doing a task fresh every time cost "about 4×" a
  stored-procedure replay, and that counting empty results as failures cut silent failures
  from 105 to 0 and the version-fallback rule raised end-to-end success from 9/25 to 16/25.
  This is a single, self-run experiment by the same author, not independently reproduced
  here or elsewhere — treat the specific numbers as directional, not verified.
- **Reliability**: unverifiable in both directions from this review alone. On
  `evolution-computer-use`'s side, the README's own "Verification" section only claims one
  exercise on one specific Windows 11 build via MCP (init, list windows, `page_open`/
  `page_shot`, save+replay+fallback-on-break); it explicitly has not re-run the desktop click/
  type/tray/foreground checks that the parent project (`dsh-world`) once did on real
  hardware. On our side, this review has no equivalent evidence to compare against, since our
  stack's reliability record is outside this repo and outside this ticket's read-only scope.

## 4. Safety

- **Arbitrary clicks**: desktop actions take screenshot pixel coordinates mapped back to
  window pixels (`onWindow()` in `src/desktop/desktop.ts`), not free-form commands; every
  action is followed by a fresh screenshot with a red circle at the actual click point, so a
  misclick is visible to the agent calling the tool, not silently assumed correct. There is
  no guardrail stopping the agent from clicking *anything* visible in a window it opened,
  though — it is exactly as unrestricted as a human using the mouse, by design.
- **Elevated/admin windows**: background mode cannot reach them at all (`ELEVATED` refusal,
  §2); foreground mode can, but only after an explicit, fresh, per-session Windows UAC
  consent — there is no way for the plugin to self-elevate silently.
- **Credentials / sensitive data**: the browser profile (`<data>/browser/`) holds real site
  logins in plaintext on disk, same as any ordinary browser profile; the README's own
  "Risks" section already states this plainly, including that "any program on this machine
  can read `<data>/browser/DevToolsActivePort` and drive the logged-in browser" — i.e. the
  plugin does not claim any extra isolation beyond "it's a separate profile directory," and
  warns the operator not to run untrusted code as the same Windows user. With desktop
  control on, the agent can see and use **everything** signed in on the machine's open
  windows; the only control offered is the on/off switch itself (`--desktop off` to revoke).
- **Prompts for credentials**: nothing in the source auto-detects or specially handles a
  login/password prompt; it would just be another thing the agent sees in a screenshot or
  page read and could type into, same risk as any screen/action-based automation.
- **Sandboxing**: `page_eval` runs arbitrary JS but only inside the dedicated browser's page
  context (CDP `Runtime.evaluate`), with a 10 s timeout and a 2000-character result cap —
  confirmed in `src/tools.ts`/`src/browser/page.ts`; the tool's own description states it
  "cannot reach files on the computer." Desktop/foreground actions have no comparable
  sandbox — they act on real OS windows by design.
- **Logging / data exfiltration**: grepping all of `src/` for network primitives
  (`node:http`, `node:https`, `node:net`, `fetch(`) found exactly one `node:net` import
  (`src/desktop/driver.ts`, the loopback named-pipe used only to talk to its own elevated
  helper) and all `fetch()` calls targeting `http://127.0.0.1:<port>` — the CDP endpoint of
  the browser instance it itself launched. No outbound network call to anything outside the
  machine was found anywhere in the source. Screenshots and recording frames are written to
  the OS temp directory and deleted in `finally`/cleanup blocks right after use (confirmed in
  `src/desktop/desktop.ts` and `recording.ts`); the only thing persisted across runs besides
  procedures themselves is `<data>/messages.jsonl`, and only for procedures that explicitly
  declare a `messages` mapping — this review did not find any default, undeclared logging of
  page or screen content. This is a source-level reading of one 0.1.0 snapshot, not a
  supply-chain audit of the npm package's published tarball byte-for-byte, and not a
  guarantee about future versions.
- **Stopping it**: a double-Esc or an on-screen "stop" button halts the current action and
  refuses every further desktop action until the user runs
  `evolution-computer-use resume`; the stop is written to `<data>/desktop-stopped` so it
  survives a crash/restart of the agent host — a deliberate safety floor, not just a soft
  flag in memory.
- **License/provenance for reuse**: MIT throughout, including the pieces it ported from
  `dsh-inner-browser-use` 0.47.28 (also MIT, attribution kept in `NOTICE.md`) — no license
  obstacle to borrowing code or patterns from it.

## 5. Integration options: recommend **borrow patterns**, not replace/complement/adopt wholesale

- **Replace** (swap our screen/action/cdp buses for this package): not recommended. We
  already operate four working buses plus a human-like desktop loop; swapping in a two-day-
  old, single-author, 0.1.0 package that reimplements the same two capabilities (browser-via-
  CDP, screenshot-and-act desktop control) from scratch would trade a presumably-proven stack
  for an unproven one, for no capability we do not already have in that layer.
- **Complement** (run it alongside, as an independent second plugin): not recommended either.
  It would launch its own separate browser profile and its own separate PowerShell desktop
  helper next to our existing buses, with its own distinct stop/consent/elevation mechanics
  that were not designed to be reconciled with whatever ours already does — two independent
  "hands on the keyboard" is a coordination and safety-review burden with no clear benefit
  over borrowing the one genuinely new piece.
- **Borrow patterns (recommended)**: the one component that is not a duplicate of what we
  already have is the **procedure library** — the JSON step format (`src/procedures/
  format.ts`), the save/replay/version-fallback engine (`src/procedures/library.ts`,
  `run.ts`), and its specific failure-handling rules (empty-result-is-failure, replay stops
  and explains instead of guessing, two kept fallback versions tried newest-first). These are
  self-contained algorithms and a file format, not tied to this package's own browser-launch
  or PowerShell code, and MIT-licensed for reuse with attribution. Porting this pattern on
  top of our **existing** screen/action/cdp buses (so "learn once, replay without the model"
  becomes an optional fast path layered on infrastructure we already trust) captures the
  claimed token/step savings without taking on a second, independent browser/desktop driver
  or its unproven-on-our-stack safety story.
- **Reject** as a literal, whole-package adoption for the reasons above; this is not a
  verdict on the idea of a procedure/replay layer itself, which looks worth borrowing in
  concept.

## 6. If piloted anyway: concrete A/B task, test profile, rollback, success metric

Not recommended as a pilot of the *package* (see §5); if a human wants to pilot the
*procedure-library pattern* specifically (ported on top of our own buses, not this
package's browser/desktop code), a minimal design:

- **A/B task**: a single, low-risk, read-only, no-login task reachable through our existing
  action-bus/cdp-bus — e.g. "read the 5 latest headlines from one fixed public page." Run it
  N times (e.g. 20). **Group A**: our current human-like loop does the task fresh every time
  (full vision+action step-by-step). **Group B**: the same loop does it once by hand, saves
  it as a procedure in the ported format, then replays that procedure on the remaining runs,
  with the empty-result-is-failure rule enforced.
- **Test profile**: an isolated, disposable browser profile and a disposable procedures
  folder created solely for the pilot — never the user's real browser/desktop profile, never
  any path under `D:\tuji-homes`, and only against a public, non-authenticated page.
- **Rollback**: delete the pilot's disposable profile and procedures folder; nothing about
  our existing buses changes, since the pilot only adds an optional "replay without the
  model" shortcut on top of calls our loop already makes — it can be feature-flagged off
  with no residual state anywhere else.
- **Success metric**: token/step count per successful run on the replayed runs (Group B,
  after the first) falls materially (e.g. ≥50%) versus Group A's fresh-every-time cost, at
  equal or better task-success rate, with zero silent "returned nothing but called it a
  success" results — mirroring the source's own K rule, which is the one claim in this
  repository's experiments that is simple enough to check independently in a real pilot.

## Sources

- [`chenkezhen480/evolution-computer-use`](https://github.com/chenkezhen480/evolution-computer-use)
  at commit [`d11bd4b`](https://github.com/chenkezhen480/evolution-computer-use/commit/d11bd4b3c51d31d89d9ee604079e0f6b7103a4a9)
  (2026-11-18), read via `git clone --depth 1` for local text inspection and via
  `gh api repos/chenkezhen480/evolution-computer-use/...` for metadata/commits/contributors
  (2026-11-20). No file from the clone was executed, built, or `npm install`ed.
- Files read in full or in relevant part: `README.md`, `README.zh-CN.md`, `NOTICE.md`,
  `LICENSE`, `package.json`, `package-lock.json`, `server.json`,
  `.claude-plugin/plugin.json`, `src/browser/{edge,cdp,browser}.ts`,
  `src/desktop/{desktop,driver,win32.ps1}`, `src/computer.ts`, `src/cli.ts`,
  `src/mcp/server.ts`, `src/tool.ts`, `src/tools.ts` (grep for `page_eval`),
  `src/procedures/library.ts` (partial), `src/inbox/inbox.ts` (partial),
  `src/desktop/recording.ts` (partial, cleanup paths only), plus a full repo file-tree
  listing and a repo-wide `grep` for network primitives (`node:http`, `node:https`,
  `node:net`, `fetch(`) and for the `ws` package import.
- [`evolution-computer-use` on the npm registry](https://registry.npmjs.org/evolution-computer-use)
  — metadata only (`curl`, no `npm install`), confirming the published `0.1.0` tarball
  matches the GitHub source.
- Repo/owner metadata: `gh api repos/chenkezhen480/evolution-computer-use`,
  `gh api repos/chenkezhen480/evolution-computer-use/commits`,
  `gh api users/chenkezhen480` (2026-11-20).
- Issue [#22](https://github.com/awtutu/dsh-superagent-sandbox/issues/22) — the only source
  of description of our own screen-bus/vision-bus/action-bus/cdp-bus stack available to this
  review; that stack's own source was not available to read in this ticket (see §3).
