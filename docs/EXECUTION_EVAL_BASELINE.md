# Execution Eval Baseline

This report verifies the execution-based scorer on the bundled `sql_generation`
dataset. It runs each expected SQL query against a deterministic in-memory
database fixture, then compares result rows.

## Summary

- Mode: `expected_sql_baseline`
- Cases: 16
- Pass rate: 100.00%
- Average combined score: 0.9938
- Average validity: 1.0000
- Average efficiency: 0.9750
- Average SQL similarity: 1.0000
- Execution accuracy: 100.00%

## By Difficulty

- easy: 5 cases, 100.00% pass, execution 100.00%
- medium: 5 cases, 100.00% pass, execution 100.00%
- hard: 6 cases, 100.00% pass, execution 100.00%

## Interpretation

This baseline proves the local fixture and expected SQL are executable. It is
not a model score. Model-generated SQL should be evaluated with the same
execution mode:

```bash
uvx poetry run ai-data-analyst-live-sql-benchmark --source local --limit 16 --model gpt-4o-mini --execution
```
