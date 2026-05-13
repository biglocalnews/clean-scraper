# clean-prefect + clean-scraper CLI Integration Design

## Problem statement

`clean-prefect` is the primary orchestration layer, but today it does not uniformly consume `clean-scraper` through a stable CLI boundary:

1. Metadata flow imports scraper modules directly and calls Python APIs.
2. Asset flow uses a Cosmos-centric path with separate downloader logic.

This creates duplicated execution paths, tighter platform coupling, and harder portability across cloud providers. We want one operational model that preserves scraper outputs, supports both metadata and assets, records runs, and can move between storage backends (including GCP) with minimal code changes.

## Goals

1. Make `clean-prefect` run `clean-scraper` via CLI for both metadata and assets.
2. Preserve output compatibility with scraper behavior already in `main`.
3. Keep run/event observability as a first-class artifact.
4. Remove Cosmos DB as an orchestration dependency.
5. Keep cloud-specific concerns confined to runtime configuration.

## Non-goals

1. Rewriting scraper extraction logic in `clean-scraper`.
2. Changing output schema consumed by downstream systems.
3. Building a new orchestration system outside Prefect.

## Approaches considered

### Approach A (recommended): CLI-first + SQLite run state + object storage artifacts

- Prefect invokes `clean-scraper` subprocess commands for metadata and assets.
- Run/event tracking is persisted in SQLite (`run_id` keyed runs and ordered events).
- Outputs and run snapshots are uploaded to object storage.

**Pros:** clear process boundary, easiest parity verification, cloud-agnostic state model, low operational cost.
**Cons:** requires orchestration flow updates and artifact lifecycle conventions.

### Approach B: direct Python API coupling from Prefect

- Prefect continues importing scraper modules and calling internals.

**Pros:** fewer immediate flow changes.
**Cons:** preserves tight coupling, weakens compatibility boundary, makes portability and versioning harder.

### Approach C: dual long-term paths (CLI + legacy Cosmos path)

- Keep both systems as permanent supported modes.

**Pros:** low short-term migration friction.
**Cons:** long-term maintenance burden, duplicate failure handling, inconsistent observability.

**Recommendation:** Approach A.

## Approved architecture

Use `clean-scraper` CLI as the only execution interface from `clean-prefect` for both metadata and asset operations. Treat run artifacts plus event logs as the source of truth for orchestration visibility.

### Key components

1. **Prefect CLI runner task**
   - Builds command arguments for `clean scrape metadata <slug>` and `clean scrape assets <slug>`.
   - Captures exit code, stdout/stderr, runtime metadata, and run_id.
2. **Run history persistence**
   - Reuse the SQLite run/event model (`scraper_runs`, `scraper_run_events`).
   - Ensure deterministic event ordering via `(run_id, event_seq)`.
3. **Artifact publisher**
   - Publishes exports, optional asset bundles, and run history snapshot to object storage.
4. **Storage adapter boundary**
   - Keep provider-specific wiring (GCS/Azure/S3) in config and runtime credentials, not orchestration logic.

## Approved data flow

1. Prefect selects agency slug(s) and starts a run per agency.
2. Prefect invokes:
   - `clean scrape metadata <slug> --data-dir ... --cache-dir ...`
   - `clean scrape assets <slug> --data-dir ... --cache-dir ... --assets-dir ...`
3. `clean-scraper` writes:
   - metadata export JSON
   - downloaded assets
   - `runs.sqlite3` entries (run + ordered event rows)
4. Prefect publishes artifacts to object storage:
   - `exports/<slug>.json`
   - run/event snapshot artifacts
   - assets under agreed storage key prefixes
5. Downstream consumers read storage artifacts and run snapshots, not Cosmos state.

## Approved error handling and retries

1. **Execution contract:** one CLI invocation = one explicit success/failure unit.
2. **Retry ownership:** Prefect handles retries at the task level; wrappers do not add hidden retry loops.
3. **Run status model:**
   - `running` at invocation start
   - `succeeded` only on zero exit plus expected artifacts
   - `failed` on non-zero exit, timeout, or artifact validation failure
4. **Idempotency and recovery:**
   - reruns always get new `run_id`
   - uploads are idempotent using deterministic object keys and overwrite/exists policy
   - event snapshots remain replayable per run

## Approved rollout and rollback

The selected rollout style is **direct cutover**.

1. Switch metadata + assets orchestration to the CLI-first path in one release.
2. Keep a short-lived fallback flag to route agencies to legacy flow if needed.
3. Enforce parity gate checks on output shape and key artifact counts after cutover.
4. If reliability or parity regresses, roll affected agencies back through the fallback path without schema changes.
5. Remove Cosmos-centric orchestration state once post-cutover stability is confirmed.

## Testing and validation strategy

1. **Contract parity tests**
   - compare metadata output shape and required keys vs current mainline expectations.
2. **Flow integration tests in clean-prefect**
   - assert CLI command construction and exit-code handling.
   - assert run/event snapshot generation and publication.
3. **Failure-path tests**
   - non-zero CLI exits, timeouts, missing artifact scenarios, and retry behavior.
4. **Cloud-agnostic verification**
   - run against at least one non-Azure object storage target using the same orchestration code path.

## Scope check

This design is scoped to a single implementation plan:

1. Introduce/standardize Prefect CLI runner tasks.
2. Replace Cosmos-dependent orchestration state usage.
3. Add artifact and run-history publishing behavior.
4. Validate parity and reliability at integration boundaries.

No additional decomposition is required before implementation planning.
