# CI Readiness — Mandatory Push/PR Harness

This file is the **single source of truth** for local CI readiness before any push or PR.

## 0) Docs / process-only shortcut

If your diff is **only** documentation or contributor-process files, you may
skip the code-quality and test commands below.

Examples of files that qualify:

- `AGENTS.md`
- `CI.md`
- `CONTRIBUTING.md`
- `README.md`
- `TESTING.md`
- `TOOL_INTEGRATION_CHECKLIST.md`
- `docs/**/*.md`
- `docs/**/*.mdx`
- `docs/docs.json`

You may use the shortcut only when **all** changed files are non-runtime and
non-executable. If the diff touches application code, tests, build tooling,
dependency manifests, CI workflows, scripts, or anything with runtime impact,
run the normal harness.

For docs/process-only changes, the minimum required local check is:

```bash
git status --short
```

If you are unsure whether the shortcut applies, do **not** use it — run the
standard checks below.

## 1) Mandatory baseline checks (every code change that is not docs/process-only)

Run all of these first:

1. Clean working tree

   ```bash
   git status --short
   ```

   - No accidental untracked files
   - Never commit `.env` or secrets

2. Lint

   ```bash
   make lint
   ```

3. Format check

   ```bash
   make format-check
   ```

   If it fails:

   ```bash
   make format && make format-check
   ```

4. Typecheck

   ```bash
   make typecheck
   ```

## 2) Mandatory test harness (scope by touched modules)

**Recommended — run this instead of manually looking up the table below:**

```bash
make test-scope
```

`make test-scope` reads `git diff` against `main`, maps each changed path to
its test target(s) using [`infra/ci/test_scope_rules.py`](infra/ci/test_scope_rules.py),
and runs the minimal `pytest` invocation. It escalates automatically to
`make test-cov` when shared/core code is touched or 3+ app areas change.
Pass `ARGS=--dry-run` to preview without running.

### Manual lookup (reference only)

If you prefer to pick the command yourself, or need a focused `-k` filter,
see the `PathRule` entries in [`infra/ci/test_scope_rules.py`](infra/ci/test_scope_rules.py).
Rules with `always_escalate=True` map to `make test-cov`; all others list their
`test_targets` tuple. Changed files under `tests/` with no app rule run as-is.

## 3) Escalation rules (must run full unit CI suite)

Run `make test-cov` (instead of only targeted tests) when any of these are true:

- Shared/core code changed (`app/utils/`, `app/state/`, `app/types/`, `app/pipeline/`, `app/nodes/`)
- 3+ app areas changed in one diff
- New files with unclear blast radius
- Cross-cutting refactor
- You are unsure test scope is sufficient

```bash
make test-cov
```

## 4) Conditional checks

If integration config, integration wiring, or related tools changed, also run:

```bash
make verify-integrations
```

## 5) Optional extra confidence

You may run `make check` as a final pass, but it is heavier (`test-full`) than the required harness.

## 6) Routing tests

Routing live tests always run with live coverage enabled. Do not use deselection filters like `-k "not live_llm"`. Fix failures by improving planner/tool correctness or updating fixtures only when behavior changes are explicitly approved.

In CI, [`.github/workflows/routing-live.yml`](.github/workflows/routing-live.yml) runs two jobs on same-repo PRs and post-merge `main` pushes: a no-LLM `routing-checks` gate (deterministic routing + fixture integrity, `-m "not live_llm"`) and the sharded `routing-live` job (8 shards, live coverage). The no-LLM gate is a fast guardrail, not a substitute for live coverage.

## 7) Investigation quality scorecard (offline)

When investigation logic, synthetic fixtures, or scorecard code changes, run:

```bash
make test-scorecard-offline
```

This executes the unified RCA rubric ([#1367](https://github.com/Tracer-Cloud/opensre/issues/1367)) against the offline smoke manifest and checks thresholds against [`tests/eval/scorecard/baselines/smoke_offline.json`](tests/eval/scorecard/baselines/smoke_offline.json).

CI: [`.github/workflows/investigation-scorecard.yml`](.github/workflows/investigation-scorecard.yml) runs the offline gate on investigation-path PRs and a weekly live LLM smoke cron on `Tracer-Cloud/opensre` (same-repo only).

Docs: [`docs/eval/investigation-quality-scorecard.mdx`](docs/eval/investigation-quality-scorecard.mdx)

Live smoke (requires API key):

```bash
uv run python -m tests.eval.scorecard run --tier live --write-trends
```

Regenerate the offline baseline after intentional rubric or gold-label changes:

```bash
uv run python -m tests.eval.scorecard run --tier offline --write-baseline
```

### Release gate (maintainers)

After [#1367](https://github.com/Tracer-Cloud/opensre/issues/1367) merges to `main`, mark the **`scorecard-offline`** GitHub Actions check as a **required** status check on the default branch (Settings → Branches → branch protection). The live weekly job is informational only and does not block merges.

## 8) CI-only tests

Some paths require live infrastructure and are excluded from `make test-cov`:

- Kubernetes / EKS scenarios (`tests/e2e/`)
- Chaos Mesh workflows (`tests/chaos_engineering/`)
- Docker-dependent Grafana stack tests

Mark CI-only tests with the appropriate pytest marker or place them in the correct folder so they do not run locally by default.

## Precedence

If readiness instructions conflict across docs, **this file wins** for push/PR checks.
