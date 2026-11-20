# AOCI-CODE command cheat sheet

Quick reference only, compiled from the public `aoci-spec/aoci-code` README
and docs at tag `v0.2.0-rc2`. See [`docs/aoci-assessment.md`](aoci-assessment.md)
for the evaluation this cheat sheet supports. None of these commands have been
run as part of that assessment; verify current behavior with the binary's own
`--help` and `aoci capabilities` before relying on this list.

## Setup

```bash
# Build from source (Go version per go.mod, currently 1.26.11)
go mod verify
mkdir -p build
make build
./build/aoci --version

# Or: download+verify a signed release, then use the extracted binary.
# See docs/install.md in aoci-code for checksum / cosign / provenance steps.
```

```bash
# First-time integration (run from the target repo root, or pass --repo)
aoci --repo . init --locale en-US --agent codex   # --agent is host-specific;
                                                    # DSH has no --agent value yet
aoci --repo . scan                                 # establishes the first Baseline
```

## Everyday checks

| Command | Purpose |
| --- | --- |
| `aoci --repo . verify` | Reports Missing, Orphan, Stale, Unbaselined facts |
| `aoci --repo . check` | Aggregated governance gate; exits 1 while findings exist |
| `aoci --repo . capabilities` | Shows what the current binary supports |
| `aoci --repo . doctor` | Diagnoses the repo and host integration |
| `aoci --repo . index agent guide --agent codex --json` | Deterministic "what do I do next" guide — defer to this instead of re-deriving the state machine |

## Building/maintaining the index (agent-driven, via MCP)

These are normally issued by the host model through the MCP tools
(`aoci_maintain`, `aoci_update_entry`, `aoci_remove_entry`), not typed by a
human:

```text
First confirm the AOCI MCP server is connected, then build the AOCI index
for this project. When it is complete, give me the AOCI panel link.
```

```bash
aoci ui --detach --json   # background read-only panel; prints the link
aoci ui --open             # foreground panel, opens a browser
aoci ui --stop              # stop this repo's background panel
```

## Database Cognition (optional, off by default)

```bash
aoci --repo . database source add \
  --source-id primary --engine postgresql \
  --database-name app --namespace public

aoci --repo . database source access --source primary --json   # read-only
                                                                  # preflight,
                                                                  # no connection
aoci --repo . database cognition bootstrap   # adds Database Cognition to an
                                               # aligned Code-only project
```

Then, in the agent: `Build the AOCI database index for this project.`

## Derived System Cognition (read-only projections, not new facts)

```bash
aoci --repo . cognition system lineage
aoci --repo . cognition system relations
aoci --repo . cognition system impact --object database://primary/public/orders
aoci --repo . cognition system snapshot --json > previous.json
aoci --repo . cognition system evolution --snapshot-file previous.json
```

## MCP server

```bash
aoci --repo . mcp   # starts the stdio MCP server; 9 tools; stdout is JSON-RPC only
```

DSH-specific wiring (unofficial, from the `dsh-aoci-keeper` project, not
shipped by `aoci-code` itself) — add to the DSH profile's `cordis.patch.yml`
and restart DSH:

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

## Notes

- Always pass `--repo <absolute-or-relative-path>` explicitly in any
  multi-repo or scripted context; omitting it resolves against the current
  working directory.
- Host-written config files (`.mcp.json`, `.codex/config.toml`, …) hold a
  machine-specific absolute binary path — keep them out of Git
  (`.gitignore`), per the project's own README.
- `verify`/`check`/`index score`/`index inventory` are documented as
  "read-only" for the formal index, but may still append to a local Ledger
  file; they are not strictly zero-filesystem-write.
