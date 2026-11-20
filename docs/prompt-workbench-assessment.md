# prompt-workbench assessment and merge plan

> Status: **pilot**. Do not migrate the existing library.
> Repo: https://github.com/Overstar66/prompt-workbench (MIT, v1.5.1)
> Reviewed read-only from the upstream README and source layout; not installed, no live profile touched.

## 1. What it is

A local anime-illustration prompt workbench:

- Python 3.10–3.12 standard-library backend + browser frontend, default `127.0.0.1:8901`.
- 18,000+ tag dictionary, ~2,900 characters, 50 style thumbnails.
- Inputs: drag an image → WD14 tagging; Chinese draft → DeepSeek/Ollama expansion; tag picker.
- Outputs: MOSS (Chinese paragraph), WAI (Illustrious tags), Pony (`score_9...`) plus separate negatives.
- Local-first; only expansion/polish goes to an API when selected. `api_config.json` stores URL/model/key in plaintext.

It solves a different problem from our library: **authoring and tag assembly**, not production data governance or the DSH image pipeline.

## 2. Comparison with `D:\tuji-homes\bupiao\提示词库`

Our library is production data:

| File | Role |
|---|---|
| `图图提示词总库.tsv` (~1.34 MB) | canonical rows, sensitivity tiers, scene/category fields |
| `画图提示词实例.tsv` (~184 KB) | accepted picture-prompt instances and provenance |
| `提示词选取规则-v3.md` (~24 KB) | selection rules, A/B/C/D, 16-section B structure, bans |
| `敏感图提示词.B_prime*.tsv` | sensitive tier data |
| `check_sensitive.py` | hard gate before generation |
| `pose_refs.tsv`, `refs_feet.tsv` | pose/reference vocab |
| `_merge/`, `_ref/`, `历史/` | merge staging, references, history |

prompt-workbench overlaps at the tag level but has no concept of our tiers, B/C/D, 16-section B structure, provenance, or the DSH drawing pipeline. Its NSFW filter is a separate three-level text filter, not a replacement for `check_sensitive.py`.

**Do not bulk-import the 1.3 MB TSV into `tags_cn.json`.** The schemas and governance differ; a bulk import would create a second source of truth and lose merge history.

## 3. Integration options

### A. External authoring tool (recommended)

Run prompt-workbench as a separate local tool at `D:\app\prompt-workbench`; use it for:

- WD14 reverse-tagging an image;
- Chinese draft → tag expansion;
- MOSS/WAI/Pony assembly;
- browsing its 18k dictionary and 2.9k character appearances.

Export only **new accepted rows** into `画图提示词实例.tsv` through a thin adapter with our schema and `source=prompt-workbench` provenance. The home library remains the only runtime source. No migration, no dual writes.

### B. Migrate the whole library

Reject: loses A/B/C/D, B_prime, provenance, and the sensitive gate; makes the home library dependent on a single-user web app.

### C. Fork/adapt

Only if we need a custom field or an automated export endpoint. Not justified before a pilot.

## 4. Concrete merge/classification plan

Keep this split:

| Workbench concept | Our equivalent | Action |
|---|---|---|
| `tags_cn.json` | `图图提示词总库.tsv` | use as reference; do not replace |
| `chars_app.json` / `custom_chars.json` | character appearance / A/B library | use as reference; no bulk merge |
| WD14 output | new candidate tags | append to `画图提示词实例.tsv` with our fields |
| MOSS/WAI/Pony | our A/B/C/D and 16-section B | map at export time; do not rewrite our rules |
| NSFW three-level filter | `check_sensitive.py` + B_prime | our gate stays authoritative |
| history (30) | `历史/` + review flow | workbench history is scratch, not canonical |
| style thumbnails | our style tier map | reference only |

Export contract (if built):

```
source=prompt-workbench
source_version=1.5.1
exported_at=<ISO>
row=<our TSV schema, never positional>
```

Only append; never rewrite `图图提示词总库.tsv`. The drawing session owns actual use; this session only defines the interface.

## 5. Security/privacy

- Defaults to `127.0.0.1`; do not expose the port or put it behind a public reverse proxy.
- `api_config.json` contains a plaintext key: keep it out of git, restrict ACL, rotate if leaked.
- WD14 runs locally; no image upload unless the expansion/polish API is selected.
- No telemetry found in the README; still verify `app.py` before enabling network.
- The built-in 18+ dictionary is intentional; do not mix it into the family-safe home library without the existing gate.
- Single process, no auth; anyone on the machine can use it.

## 6. Pilot plan

1. Clone to `D:\app\prompt-workbench` (outside the live DSH profile); Python 3.12; optional `onnxruntime pillow numpy`.
2. Start on 8901; use a dedicated browser profile.
3. Test: one WD14 image, one Chinese draft, one MOSS/WAI/Pony output; record tag quality and time.
4. Test the negative adaptation on 5 known sensitive/normal cases; compare with `check_sensitive.py`.
5. Export 3 synthetic rows to a **copy** of the instance TSV; verify schema/provenance; do not touch the live file.
6. Acceptance: no second source of truth; export is append-only; sensitive gate still blocks; drawing session confirms the output is usable.
7. Rollback: stop the app, delete its directory; no library changes to undo.

## 7. Verdict

**Pilot as an external authoring tool.** It is genuinely useful for WD14, expansion, and multi-format assembly, and it is local-first. It is not a replacement for the home prompt library, and it should not be installed into the live DSH profile before the pilot.
