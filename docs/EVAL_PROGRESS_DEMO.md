# Eval Progress Demo

This report demonstrates how evals are used as a feedback loop: run the SQL
generator, diagnose weak cases, make targeted improvements, then verify
whether the next run improved without regressions.

## Summary

- Cases: 16
- Pass threshold: 0.90
- Pass rate: 62.50% -> 100.00%
- Average score: 0.9284 -> 0.9938
- Fixed cases: 6
- Regressions: 0

## What Improved

- +0.1997 (fixed): Find the average order value per customer. [cartesian_join -> passed]
- +0.1961 (fixed): Show monthly revenue for the last 12 months. [missing_required_clause -> passed]
- +0.1765 (fixed): Calculate the running total of daily revenue. [missing_required_clause -> passed]
- +0.1511 (fixed): Show total revenue per product category. [missing_required_clause -> passed]
- +0.1222 (fixed): Using a CTE, find the top 3 customers by revenue and show their most recent order date. [missing_required_clause -> passed]

## Remaining Failure Types

- None in the current run.

## Improvement Actions

- Keep the fixed cases as regression tests and expand coverage with harder joins, CTEs, and window-function cases.

## Remaining Weak Cases

- No failing cases in this demo run.

## Artifacts

- Progress chart: `output/eval_progress/eval_progress.png`
- Previous predictions: `output/eval_progress/previous_predictions.json`
- Current predictions: `output/eval_progress/current_predictions.json`
