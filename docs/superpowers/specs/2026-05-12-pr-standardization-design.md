# PR Standardization and Merge Design

## Problem statement

The repository has four open PRs that are valuable but inconsistent with evolving scraper patterns:

- PR #42 (`clean/ca/ventura_county_sheriff.py`)
- PR #158 (`clean/ca/pomona_pd.py`, plus dependency/config changes)
- PR #170 (`clean/ca/mesa_city.py`)
- PR #181 (`clean/ca/los_angeles_sheriff.py` and config refresh)

The team wants all four PRs merged while improving consistency and maintainability. The hard requirement is output compatibility with scraper conventions already used on `main`.

## Goals

1. Merge PRs #42, #158, #170, and #181 into mainline flow.
2. Standardize scraper structure where needed, including broader cleanup if it supports consistency.
3. Preserve output compatibility with existing scrapers on `main`.
4. Keep CLI/runner behavior unchanged.

## Non-goals

1. Redesigning the command interface.
2. Replacing agency-specific scraping logic that is not required for output and pattern conformance.
3. Refactoring unrelated modules without merge or consistency value.

## Canonical output contract (source of truth)

Each scraper continues to emit a JSON file at:

- `data_dir/<agency_slug>.json` (typically `exports/<agency_slug>.json`)

Each JSON file is a list of metadata objects with:

- required: `asset_url`, `name`, `parent_page`
- optional (commonly present): `case_id`, `title`, `details`

Cache behavior remains cache-first via `Cache`, with source artifacts stored under cache paths scoped by agency slug.

## Architecture and component design

### 1) Foundation standardization layer

Introduce a shared utility layer for scraper metadata normalization and output writing:

- agency slug derivation helper
- metadata normalization helper enforcing canonical keys and value shaping
- output writer helper that consistently writes to `data_dir/<agency_slug>.json`

This layer establishes a single contract used by incoming PR scrapers and existing scrapers touched during standardization.

### 2) PR conformance adapters

Conform each PR scraper to the standardized contract while preserving scraping behavior:

- #158 Pomona: isolate request capture/browser-dependent pieces behind clearer methods; remove non-production diagnostics and normalize output.
- #170 La Mesa: normalize dedupe and field-shape behavior.
- #42 Ventura County Sheriff: align naming, path formatting, and metadata shape.
- #181 LASD refresh: retain endpoint/config updates while routing output/caching behavior through contract helpers and safer mutable-state handling.

### 3) Runtime compatibility

`Runner.scrape_meta` and CLI command behavior remain unchanged. The integration point stays at `Site.scrape_meta(...) -> Path`.

## Execution workflow

1. Baseline contract discovery:
   - Audit existing `main` scrapers to confirm practical required/optional fields before locking tests.
2. Merge foundation standardization PR:
   - Add helpers and baseline tests informed by real current behavior.
3. Conformance pass by PR:
   - Update #158, #170, #42, #181 against the shared contract.
4. Merge sequence:
   - Foundation refactor PR first, then all four conformed PRs.

## Data flow and error handling

Per scraper:

1. download/cache source artifacts
2. extract records
3. normalize each record with shared helpers
4. write canonical JSON output

Error policy:

- Do not silently shape-invalid records into success output.
- Preserve explicit logging/failure behavior consistent with repository style.
- Keep transient network behavior scraper-specific, but enforce schema integrity at normalization/output boundaries.

## Validation and testing strategy

1. Add targeted tests for metadata normalization and output writing helpers.
2. Add compatibility checks ensuring conformed PR scrapers emit canonical key structure.
3. Run baseline checks against selected existing `main` scrapers so new tests do not incorrectly fail legacy-conformant behavior.
4. Keep regression scope focused on output compatibility and merge safety.

## Subagent-assisted review plan

- Use `code-review` agent per PR for high-signal risk findings.
- Use `rubber-duck` agent before implementation milestones to catch architectural blind spots.
- Use `explore` agent only where deeper cross-file tracing is needed.

## Risks and mitigations

1. **Risk:** PR #158 introduces heavy/browser-specific behavior and dependency concerns.
   **Mitigation:** Isolate browser/request-capture logic and normalize outputs through shared helpers.
2. **Risk:** Very old PRs may conflict with current base and conventions.
   **Mitigation:** Rebase after foundation merge and resolve via contract adapters.
3. **Risk:** Overly strict tests could break on valid legacy patterns.
   **Mitigation:** Derive contract checks from observed `main` scraper behavior before enforcing.

## Acceptance criteria

1. Foundation standardization changes are merged.
2. PRs #42, #158, #170, and #181 are merged after conformance updates.
3. Updated scrapers write output in canonical shape compatible with existing `main` conventions.
4. CLI/runner interfaces and invocation behavior remain unchanged.
