# One scorecard or many rubrics? Planning the Investigation Quality Scorecard for opensre (#1367)

> **Draft for GitHub Discussions** — category: Ideas  
> **Issue:** [#1367 — Investigation Quality Scorecard](https://github.com/Tracer-Cloud/opensre/issues/1367)

---

## The idea

OpenSRE already measures investigation quality in several places — RDS/EKS/Hermes synthetics, CloudOpsBench, per-alert `--evaluate` — but each uses a different rubric and pass bar. None roll up into one headline view.

**Proposal:** one investigation quality scorecard with five metrics, a shared gold manifest, and (later) PR thresholds plus weekly trends. Core bet: **investigation accuracy is the trust metric** — measure it the same way everywhere.

**Phase 0 (this discussion):** agree on the rubric and gold manifest only. Automation comes in later phases after feedback.

---

## Five headline metrics

| Metric | Simple meaning |
| --- | --- |
| `precision_at_1` | Pehla / top root cause sahi tha? |
| `top3_recall` | Sahi reason top 3 hypotheses mein tha? |
| `evidence_grounding_rate` | Claims ke paas collected evidence tha? |
| `false_confidence_rate` | Agent confident tha par galat tha? |
| `actionability_rate` | Clear next steps the? |

Full definitions: [Investigation Quality Scorecard](investigation-quality-scorecard.mdx) (docs).

---

## Problem today

| Surface | Gap |
| --- | --- |
| Synthetic suites (RDS, Hermes, EKS) | Different gates per suite; no unified metric |
| CloudOpsBench | Manual runs; not a PR gate |
| `validity_score` | Not joined to ground truth ([#1888](https://github.com/Tracer-Cloud/opensre/issues/1888)) |
| `--evaluate` | Per-alert only; no aggregate trend |
| Main CI | No RCA accuracy gate |

Without one scorecard: **did this PR improve investigations, or just make tests easier to pass?**

---

## Phase 0 deliverables (if approved)

1. **Rubric doc** — metric definitions and planned thresholds (`docs/eval/investigation-quality-scorecard.mdx`)
2. **Gold manifest** — owned smoke case list (`tests/eval/manifest.yml`)
3. **Optional `answer.yml` fields** on smoke scenarios: `canonical_root_cause`, `contributing_factors`, `min_actionability_keywords`

No CI gate, no runner package, no trend files in phase 0 — just agreement on *what* to measure and *which* cases count.

---

## Main design choice (for later phases)

| Tier | When | Block PR? |
| --- | --- | --- |
| **Offline** | Investigation-path PRs | Yes (proposed) — fast, deterministic, no LLM |
| **Live** | Weekly cron | No — real agent quality + false-confidence trends |

**Why not live-on-every-PR?** Cost, flake, and `validity_score` reliability ([#1888](https://github.com/Tracer-Cloud/opensre/issues/1888)). Offline and live answer different questions; don't merge into one flaky required check.

---

## Proposed architecture (phase 1+)

```
Gold manifest → Offline or Live runner → 5 metrics → Report / trends / PR comment
```

**Rule:** compose over existing scorers (`rds_postgres/scoring.py`, Hermes suites, CloudOpsBench) — don't rewrite the investigation pipeline.

---

## Later phases (not in scope for phase 0)

| Phase | What |
| --- | --- |
| **1** | Offline runner + PR gate + baseline |
| **2** | Live weekly cron + trend log |
| **3** | Required branch protection + `--evaluate` UX |

---

## Explicit non-goals (v1)

- Rewriting the investigation pipeline
- Full CloudOpsBench 452-case PR gate
- Grafana dashboard in v1 (in-repo trends first)
- Gating every PR on live LLM eval

---

## Open questions

1. Are these five metrics the right headline set?
2. Is offline-first the right PR gate strategy?
3. How many smoke cases for v1 — current manifest has 11 offline + 4 live?
4. Should `top3_recall` fall back to category match when `contributing_factors` are omitted?
5. Weekly vs nightly live cron?
6. Wait for #1888 before alerting on `false_confidence_rate`?

---

## Feedback requested

Does phase 0 (rubric + manifest + schema fields) make sense as a starting point? What would you change before we build automation in phase 1?

Track implementation in [#1367](https://github.com/Tracer-Cloud/opensre/issues/1367) once the idea is approved.

---

*Proposal draft — phase 0 scope only.*
