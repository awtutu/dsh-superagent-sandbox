#  AOCI-CODE assessment for the DSH / 图图计划 stack

Scope and method: this is read-only research. No part of AOCI-CODE, the
`aoci` binary, or the `dsh-aoci-keeper` plugin was installed, built, or run.
Nothing was written outside this sandbox checkout, and `D:\tuji-homes\anxiaoman`
and `D:\tuji-homes\bupiao` were never touched. Findings come from the public
`aoci-spec/aoci-code` repository (README, `docs/`, `SECURITY.md`,
`docs/supply-chain.md`, `go.mod`, the repository's own self-hosted
`aoci.code.txt` index, GitHub repo/release metadata) at the `v0.2.0-rc2` tag,
and from the `MrKleene/dsh-aoci-keeper` repository (the optional DSH-side
plugin named in issue #15). The Go source implementation itself (the
`internal/`, `engine/`, `cmd/` packages) was **not** audited line by line;
conclusions about behavior rely on the project's own documentation and
published test/CI claims, not on independent code review.

## 1. What AOCI actually is

**AOCI** ("AI-Oriented Cognition Infrastructure") is a protocol plus
implementation for giving a coding agent a durable, Git-versioned summary of
a repository, so the agent reads that summary instead of re-reading the whole
tree on every task. **AOCI-CODE** is the reference implementation: a
single Go binary (`aoci`) that is both a CLI and, via `aoci mcp`, a local
stdio **MCP server** exposing exactly nine tools (`aoci_rules`,
`aoci_overview`, `aoci_get_entries`, `aoci_search`, `aoci_maintain`,
`aoci_update_entry`, `aoci_remove_entry`, `aoci_header`, `aoci_report`).

The **index format** ("Cognition Volumes v1") is plain UTF-8 text committed to
the repo:

- `aoci.txt` — Root: which Volumes are active (manifest/entry point).
- `aoci.meta.txt` — Meta: the tag dictionary and authoring rules (field
  limits, quotas) for the current project.
- `aoci.code.txt` — Code Volume: one **FRAS** line per managed file.
- `aoci.database.txt` — optional Database Volume (table-level entries).

Each code entry looks like:

```text
atomic.go[CG9L]: F:Provides durable replace CAS... | R:code:internal/fs/atomic_exchange_linux.go,... | A:AtomicWrite,... | S:Native publication never degrades to an overwriting rename...
```

`F`/`R`/`A`/`S` = Function / Relations (what else to read) / API (what callers
depend on) / non-obvious constraints. A short tag (`[CG9L]`) encodes layer,
domain, importance and size. The host **model**, not the binary, writes F/R/A/S
from the real source; the binary only governs structure, validation, locking,
atomic writes, and drift detection (missing/orphan/stale entries) through a
Baseline + Ledger state machine. This governance layer (Plan/Stage/Check/Diff/
CAS/Apply, Scope Change, human-approval dialogs, recovery/rollback) is
substantial — the project is explicit that it is not a lookup tool like
CodeGraph/LSP/RAG, but a maintained, auditable "map" layered on top of them.

## 2. Install/runtime requirements and a local install plan

**Requirements**

- A supported MCP host that speaks stdio MCP (Codex, Claude Code, Cursor,
  OpenCode, Qoder have first-class `aoci init --agent <x>` support; anything
  else, including DSH today, is "connect to the standard stdio server,
  configure manually").
- To build from source: the exact Go version declared in `go.mod`
  (currently `go 1.26.11`) plus `make`. The binary itself is `CGO_ENABLED=0`,
  single-file, no runtime Go dependency once built.
- To use a release: one of the six signed archives (linux/darwin/windows ×
  amd64/arm64) from the GitHub Releases page — Windows amd64/arm64 are
  published, matching our Windows hosts.
- Git on PATH for any repo that has a `.git` directory — `scan` fails closed
  (`safe_inventory_git_unavailable`) without it.
- Optional, only if Database Cognition is enabled: network reachability to a
  PostgreSQL/MySQL/openGauss 6.0.5/SQLite source, and a credential supplied
  through an environment variable (never typed into the agent).

**Concrete local install plan (read-only / sandboxed, build-from-source
preferred over an unverified binary):**

1. Clone `aoci-spec/aoci-code` at the pinned tag (`v0.2.0-rc2`) into a
   scratch directory outside any real project tree.
2. `go mod verify && mkdir -p build && make build` → produces `build/aoci`
   (`aoci.exe` on Windows); run `./build/aoci --version` to confirm.
   Alternatively download the signed Windows archive and verify it against
   `SHA256SUMS` (basic) or additionally `cosign verify-blob` against the
   project's GitHub Actions OIDC identity (recommended) before trusting it —
   see [`docs/supply-chain.md` in aoci-code](https://github.com/aoci-spec/aoci-code/blob/v0.2.0-rc2/docs/supply-chain.md).
3. Move the binary to one **stable absolute path** (e.g.
   `C:\tools\aoci\aoci.exe`), outside any repo, since MCP config binds to an
   absolute path and a moved binary silently breaks it.
4. On a **throwaway** copy of a small test repository (never a real
   `tuji-homes` workspace): `aoci --repo . init --locale en-US` then
   `aoci --repo . scan` to establish the first Baseline.
5. **MCP client config for DSH**: AOCI-CODE has no native DSH integration
   (`aoci init --agent` only knows `codex`/`claude`/`opencode`/`cursor`/
   `qoder`); DSH falls in the generic "other MCP hosts" row and must be wired
   by hand. The community `dsh-aoci-keeper` plugin's README documents the
   concrete shape, added to the DSH profile's `cordis.patch.yml`:

   ```yaml
   - insert:
       - id: mcp-aoci
         name: '@deepseek-ai/dsh-mcp-client'
         config:
           transport: stdio
           serverName: aoci
           command: /absolute/path/to/aoci
           args: ['--repo', '/absolute/path/to/repo', 'mcp']
   ```

   This is third-party-documented, not an AOCI-CODE-shipped integration, and
   a DSH restart is needed to pick it up.
6. Only after the above is reviewed would the agent be asked to run
   `aoci_maintain`/`aoci_update_entry` to author the first index — not done in
   this assessment.

`aoci init` also writes host-specific config files (`.mcp.json`,
`.codex/config.toml`, etc.) containing the machine-bound absolute binary path;
these must be `.gitignore`d, never committed (a committed copy breaks on every
other machine and silently blocks re-`init`).

## 3. What it can and cannot index

**Can:**

- Source code, tests, configuration, and **documentation** (the tag
  dictionary has a `DocumentationSpecification` layer), across any language —
  the model, not a language-specific parser, writes the entries, so this is
  language-agnostic by design.
- Database schema: PostgreSQL, MySQL (5.7.6+, not MariaDB), openGauss 6.0.5
  LTS (constrained), and SQLite (read-only catalog collectors) — structure
  only (tables, columns, keys, indexes), never row data, never DDL/DML.
- Repository-relative documentation/knowledge-base files in the same tree,
  since Managed Scope covers any Git-tracked path, not just `*.go`/`*.ts`.

**Cannot / explicitly out of scope:**

- Business data (row contents), secrets, or credential values — only an
  environment-variable *name* is ever recorded.
- Binary or oversize files, which are marked `code_skipped` and left out of
  the index (the model cannot describe what it can't read).
- MariaDB, non-6.0.5 openGauss, MongoDB (a MongoDB collector is only a
  *proposed* profile under discussion), views/routines/triggers.
- Automatic semantic-relationship inference: the `R`/`A`/`S` fields are
  model-authored from evidence, not derived from imports/ASTs/call graphs —
  a wrong or lazy model write is not caught by the tool's governance checks,
  which validate structure, not truth ("All-green ... does not mean every
  statement the model wrote is correct").

**Relevance to our KB and DSH plugins**: our Markdown KB and the plain
TypeScript/JS `apps/web` and plugin packages are both indexable in principle
(code + docs are first-class Managed Scope objects). The main open question is
whether per-file FRAS summaries add enough over our existing
`tools/check_kb_links.py`-style conventions and plain file reading to justify
the governance overhead described below — that is exactly what the pilot in
§6 is meant to test, not something this read-only pass can settle.

## 4. Cost/benefit

Concrete numbers, measured from the project's own self-hosted index
(`aoci.code.txt` at `v0.2.0-rc2`, fetched directly, not estimated):

| Metric | Value |
| --- | --- |
| aoci-code repo size (GitHub `languages` API) | ~8.85 MB source (Go 6.8 MB, TypeScript 1.3 MB, Python 0.56 MB, Shell/Templates/HTML/Makefile the rest) |
| Self-index (`aoci.code.txt`) | 628 entries, 236,764 bytes of index text |
| Rough index/source compression | ≈628 dense one-line summaries replacing several thousand source files; the raw index text alone is ~55–65K tokens at typical English/code token density |
| Vendor's own scaling claim (README, unverified independently) | ~300K-token index for a 700K-line / ~500K-line-practical-limit codebase; first full index build ≈ 1 hour per 200K lines of source, agent-speed dependent |

**Benefit, if the claims hold**: a one-time, incremental-afterward cost buys a
~300-token-per-file summary an agent can read once per session instead of
grepping/opening dozens of files per task — plausible token savings on large,
long-lived repos with many repeat sessions (matches the stated DSH use case of
"understand a codebase before editing, without loading the whole tree").

**Cost / maintenance burden**:

- Build time: trivial (`make build`, seconds, CGO-free Go binary).
- Disk: the index text itself is small (hundreds of KB even for a sizeable
  repo); `.aoci/` adds a Ledger, drafts, transaction/recovery state (normally
  git-ignored) whose size was not measured here.
- Query latency: not benchmarked in this assessment (would need the pilot).
- **Maintenance burden is the real cost.** The governance model —
  Baseline, CAS writes, Ledger, Scope Change workflow, human-approval
  dialogs, Overview chunk/cursor/attestation delivery, recovery/rollback
  states (`applied`/`repair_required`/`stopped`) — is large and
  purpose-built to prevent silent drift, but it is also a second
  state machine every contributor and every agent session has to keep
  "aligned" (`aoci check`/`aoci verify`) alongside normal code review. The
  `CHANGELOG.md` for just the rc1→rc2 step (two weeks apart) lists a dozen+
  host-round and governance fixes, which is healthy responsiveness but also
  signals the workflow is still shaking out edge cases.

## 5. Security and operational risks

- **Local-first, no outbound network by default.** The binary ships no model
  client and has no telemetry/cloud endpoint; the only outbound connections
  are explicitly-triggered, read-only DB schema reads, and the loopback
  (`aoci ui`) status page binds only to loopback addresses and serves
  GET/HEAD only. This matches our "no install, read-only" constraint well.
- **Credential handling**: DSN/credential *values* are never stored or typed
  into the agent — only an env-var *name*. A DB account still has to be
  provisioned, least-privilege, by a human outside AOCI.
- **Loopback status page capability**: its printed URL/registration is a
  bearer-style capability for repository data; SECURITY.md explicitly warns
  not to share it or log it publicly — an operational discipline point for
  whoever runs `aoci ui --detach`.
- **Git-versioned index as an attack surface**: the index text is written by
  the model and committed. A model that is tricked (e.g. by content inside a
  reviewed file) into writing a misleading `S` constraint would have that
  misinformation persist and be trusted by future sessions — the project's
  own FAQ concedes "all-green" governance checks structure, not semantic
  truth. This is a prompt-injection-adjacent risk inherent to *any*
  model-authored persistent memory, not unique to AOCI, but worth a review
  step before trusting `S` fields blindly.
- **Host-bound config files** (`.mcp.json`, `.codex/config.toml`, …) contain
  absolute local paths and must be `.gitignore`d; committing them is a
  footgun (breaks other machines, silently keeps stale paths on reinit) more
  than a secret leak, but it is a real operational risk to call out.
- **Supply chain**: release binaries are keylessly signed (Cosign + GitHub
  OIDC + SLSA provenance + per-archive SBOMs), which is a genuinely strong
  posture for a ~3-month-old project — but full verification needs
  `cosign`/`gh attestation verify`/Go tooling, not just a checksum; "basic"
  verification (SHA256SUMS only) authenticates integrity, not publisher.
- **License**: FSL-1.1-MIT (Functional Source License), **not** OSI-approved
  open source until its 2-year MIT conversion date per release. Our intended
  **internal use** is an explicit "Permitted Purpose" under the license, so
  this is not a blocker for us, but it is not a redistribution-friendly
  license and should be noted for anyone assuming "open source" compliance
  posture.
- **Project maturity**: `aoci-spec/aoci-code` was created 2026-08-08 (~3.5
  months old at the time of this review) and is still pre-1.0 (`v0.2.0-rc2`),
  with 2,726 stars / 257 forks / 17 open issues — real traction, but no
  stability guarantee yet; breaking-ish governance changes between release
  candidates are visible in the changelog.
- **DSH integration specifically**: the `MrKleene/dsh-aoci-keeper` plugin
  that issue #15/#16 name as optional was created **2026-11-16**, four days
  before this ticket, has **0 stars/0 forks**, and is a single-author,
  unreviewed-by-us package. It explicitly does *not* install `aoci`, does not
  register the MCP server, and does not build the first index — it only adds
  a once-per-turn drift reminder once everything else is wired up by hand.
  Treat it, and the DSH wiring step in general, as unvetted and low-maturity
  relative to AOCI-CODE's own first-party host integrations.

## 6. Pilot plan (30–60 minutes)

Run entirely inside this sandbox, on a disposable copy of a small repository
(for example a scratch clone of this very `dsh-superagent-sandbox` repo, or
`examples/minimal-repository` from the aoci-code source) — never on a real
`tuji-homes` workspace or any production DSH profile.

1. **Setup (≈10 min)**: build `aoci` from the pinned tag with `make build`;
   verify `--version`; `init`/`scan` the disposable repo; confirm `aoci
   capabilities`/`aoci doctor` run clean.
2. **Build the index (≈15–20 min)**: wire the MCP server into a scratch DSH
   profile (not the real one) pointed at the disposable repo only; have the
   agent run `aoci_maintain` → author the batch with `aoci_update_entry`
   until `aoci verify`/`aoci check` report `aligned`. Record: wall-clock time,
   number of entries, `aoci.code.txt` size, and whether any file was
   `code_skipped`.
3. **Query comparison (≈10–15 min)** — ask the agent the same 5
   architecture questions twice, once "cold" (no index, must search/read
   files) and once using only `aoci_overview`/`aoci_search`/
   `aoci_get_entries`:
   - "What does module/file X do and what else must I read to change it
     safely?"
   - "What are the public entry points / APIs of this repo?"
   - "What must not break if I touch file Y?" (tests the `S` field)
   - "Which files are untouched/orphaned relative to the index?" (drift)
   - "Summarize the whole system in one paragraph."
   Record for each: wall-clock time, approximate tokens consumed (chat/tool
   token counts), and a correctness judgment (did the AOCI answer match what
   reading the file directly shows?).
4. **Drift check (≈5 min)**: edit one file in the disposable repo, re-run
   `aoci check`, confirm it reports the file `stale` and names the fix.
5. **Teardown**: `aoci ui --stop` if started; delete the scratch binary,
   profile patch, and disposable repo clone; nothing persists outside the
   sandbox.

**Measurable acceptance criteria** (all must hold to move past "pilot"):

- First-index build completes within the session with `aoci verify` reporting
  `aligned` (governance claim is at least mechanically true).
- At least 4 of 5 "warm" (AOCI-backed) answers are judged at least as correct
  as the "cold" answers, with measurably fewer tool calls or lower token
  spend.
- The drift check correctly flags the edited file as `stale` (maintenance
  claim holds).
- No credential value, secret, or host-specific absolute path appears in
  anything committed to Git during the pilot.
- Zero outbound network calls observed other than the expected GitHub
  download/verification traffic (no silent telemetry).

## 7. Verdict: **pilot**

AOCI-CODE's local-first design, explicit no-telemetry/no-credential-storage
posture, and strong release supply chain make it safe to **pilot** inside a
sandbox under the constraints already followed in this ticket. It is not
ready for **adopt now**: the project is ~3.5 months old and pre-1.0, its
governance layer is heavy relative to the benefit it has not yet been
measured to deliver for us, and the only DSH-specific integration path (the
`dsh-aoci-keeper` plugin) is four days old with no community validation.
It does not warrant outright **reject** or **defer** either: the core
local-first/no-network/no-secret-storage properties, signed releases, and a
genuinely relevant problem statement (agent context before editing, Git-versioned,
cross-session) line up well with our stated DSH/KB need, and the vendor
provides a small `examples/minimal-repository` walkthrough specifically for a
cheap pilot. Recommendation: run the pilot in §6 on a disposable repository
and a scratch DSH profile; only consider wiring it into a real workspace, and
only consider installing `dsh-aoci-keeper`, after that pilot's acceptance
criteria are met and someone has reviewed the `dsh-aoci-keeper` source
directly (it is far less scrutinized than AOCI-CODE itself).

## Sources

- [aoci-spec/aoci-code](https://github.com/aoci-spec/aoci-code) — README, `go.mod`, `SECURITY.md`, `docs/install.md`, `docs/supply-chain.md`, `docs/managed-scope-and-budget.md`, `docs/database-evidence.md`, `CHANGELOG.md`, `LICENSE`, `aoci.txt`/`aoci.meta.txt`/`aoci.code.txt`, at tag `v0.2.0-rc2` and GitHub repo metadata (2026-11-20).
- [MrKleene/dsh-aoci-keeper](https://github.com/MrKleene/dsh-aoci-keeper) — README and GitHub repo metadata (2026-11-20).
- `docs/aoci-commands.md` in this PR — command cheat sheet derived from the same sources.
