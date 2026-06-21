# AVM Reorg — Move Manifest

**Status:** Executed 2026-06-21 (52 git mv operations: the 51 approved items below, plus 1
corrective item added post-execution — see "Post-execution correction").
**Generated:** 2026-06-20
**Repo root:** `C:\Users\digitalscorpyun\projects_2026`
**Scope root:** `C:\Users\digitalscorpyun\projects_2026\avm`

## Post-execution correction

`time_audit.py` was flagged during the original scan as looking broken/incomplete
(mixes a WSL-style `/mnt/c/...` path with the Windows-path conventions used everywhere
else in `avm/`, and calls `current_time.offset_hours` as a bare attribute rather than a
method) but was never given a manifest entry — an oversight, only caught after execution
when it was the sole file left at `avm/` root. User approved destination `avm/spec/`
(grouped with the other self-evidently unfinished/WIP scripts: `technofeudal_bias_audit.py`,
`cg_scribe.py`). Executed via `git mv` on 2026-06-21. Added to the table below as row 56.

## Zero-edit guarantee

This pass is **zero-edit** for file contents. No `.py`, `.json`, or `.yaml` file
content is modified. No import statements are rewritten. No semantic code edits.
Filesystem moves only, executed via `git mv` (never delete+recreate), except items
marked `inspect_first` or `keep`, which are not touched at all — not moved, not edited.

## Findings required before this manifest could be written

### 1. `ctx_grok_proto.py` import dependency (your decision 3)

Searched the full `projects_2026` tree for `ctx_grok_proto` / `CTXGrokProto`. Exactly
one Python import exists: `synapse_engine.py:51`,
`from scripts.ctx_grok_proto import CTXGrokProto`, inside `run_synapse()`. That import
targets a top-level `scripts` package that **does not exist anywhere in `projects_2026`**.
The same function also imports `from avm_ops.scripts.vs_enc_orchestrator import VSEncOrchestrator`
on line 52 — equally non-existent. Both are leftover references to the old
`C:\Users\digitalscorpyun\projects_2025\avm_ops\scripts\` layout (consistent with the
stale `DEFAULT_SYNAPSE` constant and `path_resolver.py`'s `FORGE_ROOT`, both still
pointing at `projects_2025`).

**Conclusion:** `run_synapse()` is already non-functional today — it would raise
`ModuleNotFoundError` if called, regardless of any reorg. `ctx_grok_proto.py` has no
live, working Python import dependency at its current location.

Separately, `config/vs_enc_invocation_law.yaml` lists `ctx_grok_proto` as the
`allowed_agents` entry for all five invocation types — a governance-config reference
by string name, not a filesystem path, so it's unaffected by where the file lives.

Per your rule, since no working dependency was found, `ctx_grok_proto.py` is kept with
the core cluster this pass (least disruption) and flagged as **prototype debt**, not archived.

### 2. `ontology_core.yaml` header/location mismatch (your decision 2)

Its own header reads `# war_council/avm_syndicate/configs/ontology_core.yaml`, implying
its intended home is under `war_council/`, not `avm/config/`. No code references this
file by path (confirmed via repo-wide grep), so nothing breaks today regardless of
location. Marked `inspect_first`: not moved this pass, flagged for a later
Vault-governance decision.

### 3. `synapse_engine.py` relocation side-effect (newly found, flagged for completeness)

`_bootstrap_path()` computes `project_root` as the parent of its own file's directory.
Today that resolves to `projects_2026/`. After moving to `avm/core/synapse_engine.py`
(unmodified), the same code will resolve `project_root` to `avm/` instead — a pure
side-effect of relocation, not an edit. No functional change in practice: the `scripts`
and `avm_ops.scripts` packages it looks for don't exist at either location, so the
function is broken before and after the move.

## Manifest table

| # | Source | Destination | Action | Reason (short) | Risk (short) |
|---|---|---|---|---|---|
| 1 | `avm\vs_enc.py` | `avm\core\vs_enc.py` | move | Root orchestrator, sibling-imported by core cluster | None if moved with full cluster |
| 2 | `avm\watsonx_client.py` | `avm\core\watsonx_client.py` | move | Watsonx bridge, sibling-imported by core cluster | None if moved with full cluster |
| 3 | `avm\path_resolver.py` | `avm\core\path_resolver.py` | move | Only consumer is synapse_engine.py | None if moved with full cluster |
| 4 | `avm\synapse_engine.py` | `avm\core\synapse_engine.py` | move | Synapse CLI, holds invocation-law abs. path | See finding 3 — non-functional before/after |
| 5 | `avm\ctx_grok.py` | `avm\core\ctx_grok.py` | move | Diagnostic engine, holds taxonomy abs. path | None — vs_enc.py + taxonomy path both preserved |
| 6 | `avm\ctx_grok_proto.py` | `avm\core\ctx_grok_proto.py` | move | See finding 1 — prototype debt | Flagged, not archived per your rule |
| 7 | `avm\qwen_echo.py` | `avm\core\qwen_echo.py` | move | Refinery client, sibling imports | None if moved with full cluster |
| 8 | `avm\kimi_deux.py` | `avm\core\kimi_deux.py` | move | Training client, sibling imports | None if moved with full cluster |
| 9 | `avm\scorpyun_annotator.py` | `avm\core\scorpyun_annotator.py` | move | Annotation emitter, sibling imports | None if moved with full cluster |
| 10 | `avm\scholarly_dive.py` | `avm\core\scholarly_dive.py` | move | Synthesis engine, sibling imports | None if moved with full cluster |
| 11 | `avm\test_synapse_manifest.py` | `avm\core\test_synapse_manifest.py` | move | Manual smoke test, sibling import | None if moved with full cluster |
| 12 | `avm\vault_yaml_normalizer.py` | `avm\vault_tools\vault_yaml_normalizer.py` | move | Most recently active tool (6/13) | None — standalone |
| 13 | `avm\vault_yaml_validator.py` | `avm\vault_tools\vault_yaml_validator.py` | move | Also active 6/13 | None — standalone |
| 14 | `avm\mw_archive.py` | `avm\vault_tools\mw_archive.py` | move | Read-only vault continuity tool | None — standalone |
| 15 | `avm\sanctified_linker.py` | `avm\vault_tools\sanctified_linker.py` | move | Vault linking CLI | None — standalone |
| 16 | `avm\vault_yaml_normalizer_report.csv` | `avm\vault_tools\_reports\vault_yaml_normalizer_report.csv` | move | Generated output, not source | None — regenerable |
| 17 | `avm\yaml_errors_only.csv` | `avm\vault_tools\_reports\yaml_errors_only.csv` | move | Generated output, not source | None — regenerable |
| 18 | `avm\pgn_ingest.py` | `avm\chess\pgn_ingest.py` | move | PGN ingestion engine | None — standalone |
| 19 | `avm\chess_analyze.py` | `avm\chess\chess_analyze.py` | move | Post-ingest enricher (file-based handoff) | None — standalone |
| 20 | `avm\wx_chess_analyst.py` | `avm\chess\wx_chess_analyst.py` | move | Governance-locked production arbiter | None — standalone |
| 21 | `avm\anacostia_sentry.py` | `avm\monitoring\anacostia_sentry.py` | move | Most actively modified file currently | None — uses `Path(__file__).parent` |
| 22 | `avm\sentry_config.json` | `avm\monitoring\sentry_config.json` | move | Must stay sibling to sentry script | Untracked file, git mv adds+moves in one step |
| 23 | `avm\sentry_usage.md` | `avm\monitoring\sentry_usage.md` | move | Docs for sentry script | Untracked file |
| 24 | `avm\vault_logs\` | `avm\monitoring\vault_logs\` | keep (not git-tracked) | Generated/gitignored | Existing log file will not auto-follow; script regenerates fresh dir |
| 25 | `avm\passphrase_forge.py` | `avm\tools\passphrase_forge.py` | move | Generic utility | None — standalone |
| 26 | `avm\search_query_helper.py` | `avm\tools\search_query_helper.py` | move | Generic utility | None — standalone |
| 27 | `avm\write_notes.py` | `avm\tools\write_notes.py` | move | Keeper per decision 4 | None — standalone |
| 28 | `avm\drill_001.py` | `avm\drills\env_vars\drill_001.py` | move | Env-var study series | None — standalone |
| 29 | `avm\drill_002.py` | `avm\drills\env_vars\drill_002.py` | move | Env-var study series | None — standalone |
| 30 | `avm\drill_003.py` | `avm\drills\env_vars\drill_003.py` | move | Env-var study series | None — standalone |
| 31 | `avm\drill_004.py` | `avm\drills\env_vars\drill_004.py` | move | Env-var study series | None — standalone |
| 32 | `avm\drill_005.py` | `avm\drills\env_vars\drill_005.py` | move | Env-var study series | None — standalone |
| 33 | `avm\drill_006.py` | `avm\drills\env_vars\drill_006.py` | move | Env-var study series | None — standalone |
| 34 | `avm\drill_007.py` | `avm\drills\env_vars\drill_007.py` | move | Env-var study series | None — standalone |
| 35 | `avm\drill_008.py` | `avm\drills\env_vars\drill_008.py` | move | Env-var study series | None — standalone |
| 36 | `avm\drill_009.py` | `avm\drills\env_vars\drill_009.py` | move | Env-var study series | None — standalone |
| 37 | `avm\drill_010.py` | `avm\drills\env_vars\drill_010.py` | move | Env-var study series | None — standalone |
| 38 | `avm\net_plus_drill_1.py` | `avm\drills\networking\net_plus_drill_1.py` | move | Different study topic, own subfolder | None — standalone |
| 39 | `avm\technofeudal_bias_audit.py` | `avm\spec\technofeudal_bias_audit.py` | move | Self-labeled "Spec Phase" | None — standalone |
| 40 | `avm\cg_scribe.py` | `avm\spec\cg_scribe.py` | move | Self-labeled "Validation Skeleton" | None — standalone |
| 41 | `avm\vs_enc_orchestrator.DEAD.py` | `avm\archive\vs_enc_orchestrator.DEAD.py` | archive | Self-marked dead, superseded by core/vs_enc.py | None — no importers |
| 42 | `avm\note_generator.py` | `avm\archive\note_generator.py` | archive | write_notes.py is the keeper (decision 4) | None — no importers |
| 43 | `avm\od_comply.py` | `avm\archive\placeholders\od_comply.py` | archive | Decision 1 — 0 bytes since migration ef4fda6 | None — no importers |
| 44 | `avm\validator.py` | `avm\archive\placeholders\validator.py` | archive | Decision 1 — 0 bytes since migration ef4fda6 | None — no importers |
| 45 | `avm\synapse_router.py` | `avm\archive\placeholders\synapse_router.py` | archive | Decision 1 — 0 bytes since migration ef4fda6 | None — no importers |
| 46 | `avm\config\agent_manifest.yaml` | `avm\archive\placeholders\agent_manifest.yaml` | archive | Decision 1 — 0 bytes since af61a9b | None — unread by code |
| 47 | `avm\config\model_profiles.json` | `avm\archive\placeholders\model_profiles.json` | archive | Decision 1 — 0 bytes since af61a9b | None — unread by code |
| 48 | `avm\config\env_loader.py` | `avm\archive\placeholders\env_loader.py` | archive | Decision 1 — 0 bytes since af61a9b | None — unread by code |
| 49 | `avm\config\concept_taxonomy.yaml` | *(same path)* | **keep** | Hardcoded abs. path in core/ctx_grok.py:28 | Breaks ctx_grok.py if moved |
| 50 | `avm\config\vs_enc_invocation_law.yaml` | *(same path)* | **keep** | Hardcoded abs. path in core/synapse_engine.py:36-37 | Breaks synapse_engine.py if moved |
| 51 | `avm\config\ontology_core.yaml` | *(same path)* | **inspect_first** | Decision 2 — header claims war_council/ home | None this pass; flagged for governance review |
| 52 | `avm\config\vault_restructure_phase_01.yaml` | `avm\config\vault_restructure\vault_restructure_phase_01.yaml` | move | Historical migration manifest, unreferenced by code | None |
| 53 | `avm\config\vault_restructure_phase_02.yaml` | `avm\config\vault_restructure\vault_restructure_phase_02.yaml` | move | Historical migration manifest, unreferenced by code | None |
| 54 | `avm\config\vault_restructure_phase_03_audit.yaml` | `avm\config\vault_restructure\vault_restructure_phase_03_audit.yaml` | move | Historical audit manifest, unreferenced by code | None |
| 55 | `avm\config\vault_restructure_phase_04.yaml` | `avm\config\vault_restructure\vault_restructure_phase_04.yaml` | move | Historical migration manifest, unreferenced by code | None |
| 56 | `avm\time_audit.py` | `avm\spec\time_audit.py` | move | Post-execution correction — missed in original scan, looks unfinished | None — standalone, no cross-imports |

*(All paths above are relative to `C:\Users\digitalscorpyun\projects_2026\` for table
readability — `move_manifest.json` carries the full, untruncated absolute path for
every item, as required.)*

## Out of scope / untouched

- `avm\__pycache__\` — generated bytecode cache, already gitignored.
- `avm\_debug\` — generated debug receipts (658 files), already gitignored via `avm/_debug/`.

## Git preservation

Every `move` and `archive` action above will be executed via `git mv`, preserving file
history. Destination directories (`core/`, `vault_tools/`, `vault_tools/_reports/`,
`chess/`, `monitoring/`, `tools/`, `drills/env_vars/`, `drills/networking/`, `spec/`,
`archive/`, `archive/placeholders/`, `config/vault_restructure/`) will be created first;
no file is ever deleted and recreated.

## Execution record

Approved and executed 2026-06-21. All 56 rows above were performed via `git mv`
(rows 1-55 approved before execution; row 56, `time_audit.py`, added and executed as a
post-execution correction once the omission was found). No file contents were edited.
`concept_taxonomy.yaml`, `vs_enc_invocation_law.yaml`, `ontology_core.yaml`, and
`vault_logs/` remain untouched, exactly as specified by their `keep`/`inspect_first`
status. Changes were staged via `git mv` and then committed.
