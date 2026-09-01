# Guided Update Flow

## Command

```powershell
job-market-analyzer update --database .\job-market.sqlite3
```

This is a one-shot local workflow. It snapshots an existing SQLite database, updates
an isolated sibling staging database, validates it, atomically publishes it, prints
one concise report, and exits. It does not schedule another run. The previous valid
database remains beside the target as `<name>.previous<suffix>` for one-step rollback.

Optional controls:

```powershell
job-market-analyzer update --database .\job-market.sqlite3 --source remote_ok --source jobicy
job-market-analyzer update --database .\job-market.sqlite3 --limit-analysis 500
```

`--source` is repeatable and accepts only registered enabled provider codes. Without
it, all enabled sources run. Without `--limit-analysis`, each analyzer considers all
current postings.

## Execution and failure policy

1. Validate that every active analyzer kind has the requested input-language
   implementation.
2. Acquire a per-database update lock and create a consistent SQLite backup snapshot.
3. Initialize or migrate only the isolated staging database.
4. Run sources sequentially in registry order and persist each collected batch.
5. Run the registered analyzers for the requested language over current durable rows.
6. Checkpoint staging WAL, switch it to a self-contained rollback journal, and verify
   `integrity_check`, `foreign_key_check`, current schema version, and schema structure.
7. Atomically replace the published file on the same filesystem and print the matching
   `serve` command. An exception before replacement leaves the published file unchanged.

Missing `WEB3_CAREER_API_TOKEN` skips only Web3.career and prints the environment
variable name, never its value. A collector/network failure is recorded and remaining
sources continue. A typed item normalization failure remains an item failure. An
unexpected normalization invariant, repository write, schema, transaction, or SQLite
failure aborts. Analysis still runs after isolated source failures on data that was
successfully persisted. An isolated analyzer failure is reported and other analyzers
continue; database/transaction failures abort. Any source item, source, or analyzer
failure makes the process exit non-zero.

Source-level or analyzer-level failures still publish their internally consistent
partial progress and return exit code 1, preserving the existing update contract.
Systemic collection orchestration, SQLite, migration, validation, or publication
failures do not publish staging data. A second concurrent update fails closed while
the update lock exists; after a confirmed process crash, an operator may remove the
stale `.<database-name>.update.lock` before retrying.

## Idempotency and language

Source identity and deterministic content hashes prevent duplicate postings and raw
observations on unchanged reruns. Analyzer kind, version, and input hash prevent
duplicate skill or role runs. Counts are source-posting counts because complete
cross-source canonical linking does not exist yet.

`--language en` selects analyzer input capability. It does not set source language or
CLI display language. Sources can contain English, Ukrainian, German, or mixed text.
Current registrations are `skills/en`, `roles/en`, `seniority/en`, `geography/en`,
and `salary/en`; `--language uk` is deliberately rejected before database creation
and collection. Future Ukrainian support requires real implementations and registry
entries for each kind, not a source mapping or an English fallback.

## Extension seams

- Add a future source implementation under `src/job_market_analyzer/collectors/` and
  `src/job_market_analyzer/normalization/`, then add one `SourceAdapter` in
  `src/job_market_analyzer/services/update_registry.py`.
- Add future Ukrainian extractor runners, then register `AnalyzerAdapter` entries for
  `skills/uk` and `roles/uk` in the same registry module.

Neither extension requires conditional branches in the update service.
