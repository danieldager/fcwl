# `docs/` — Navigation

This folder holds reference material, eval artifacts, and historical snapshots for the misinformation nudging project. Below is a map of what each file is for and **which sources are authoritative for the current state of the system**.

## Authoritative for current state

| File | Purpose |
|---|---|
| `../CLAUDE.md` | **Single source of truth** for the current pipeline architecture, ideas backlog, and resolved decisions. Always read this first. |
| `../clog/DDMMYY.md` | Daily work logs. Most recent entries reflect current thinking. |
| `conversation_log.md` | Chronological session summaries (high-level). Append-only. |

## Source material (do not modify)

| File | Purpose |
|---|---|
| `factchecking_with_LLMs.pdf` | Source theoretical paper (Guriev et al. 2025-adjacent). Defines the model this project empirically tests. |

## Active artifacts

| File | Purpose |
|---|---|
| `pipeline_slides.tex` / `.pdf` | Slide deck for lab presentations. Source + compiled. |
| `pipeline_report.tex` | LaTeX writeup of pipeline design. |
| `proposed_pipeline.tex` | Earlier proposed-pipeline doc. |
| `baselines.md` | Pipeline eval baselines (currently: Baseline 1 from 080526 on AVeriTeC). |
| `eval_verification_notes.md` | Verification-stage eval dataset findings (2026-05-18). |
| `plot_results.py` | Helper script for generating eval plots. |
| `eval_claims.csv`, `eval_results.csv` | Tabular eval data. |
| `compare_*.json`, `eval_ckpt_*.json`, `eval_run_*.log` | Eval run artifacts. |
| `*.png` | Generated plots (accuracy, reliability, ROC, per-label, runs-over-time). |

## Historical (do not treat as current)

| File | Purpose |
|---|---|
| `archive/pipeline_3_5_26.md` | Early design doc (2026-05-03). Superseded by `CLAUDE.md`. |
| `archive/pipeline_7_5_26.md` | Mid-May design doc (2026-05-07). Superseded by `CLAUDE.md`. |

## Convention

When a doc here becomes outdated:
1. Move it to `archive/` (use `git mv` to preserve history)
2. Prepend a `> **⚠️ HISTORICAL SNAPSHOT** — superseded by ...` header noting what replaced it
3. Update this README's tables
