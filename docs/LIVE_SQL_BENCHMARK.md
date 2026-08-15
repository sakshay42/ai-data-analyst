# Live SQL Benchmark

This report captures a live model-generated SQL run against the bundled `sql_generation`
eval set. It was produced before execution scoring was added, so it should be read as
a structural SQL-quality report. To get row-level correctness, rerun the live benchmark
with `--execution`.

## Setup

- Dataset: `sql_generation`
- Source: bundled local eval cases
- Cases: 16
- Mode: `predictions`
- Model: `gpt-4o-mini`
- Prediction coverage: 100.00%

## Summary

| Metric | Score |
|---|---:|
| Pass rate | 100.00% |
| Average combined score | 0.9038 |
| SQL validity | 1.0000 |
| SQL efficiency | 0.9688 |
| SQL similarity | 0.6685 |
| Execution accuracy | Not measured in this run |

## By Difficulty

| Difficulty | Pass rate | Average score |
|---|---:|---:|
| Easy | 100.00% | 0.9584 |
| Medium | 100.00% | 0.9111 |
| Hard | 100.00% | 0.8523 |

## Weakest Cases

| Score | Case |
|---:|---|
| 0.7524 | Find customers whose average order value is above the overall average order value. |
| 0.7915 | Calculate the running total of daily revenue. |
| 0.8176 | Show monthly revenue for the last 12 months. |
| 0.8385 | Calculate each product's revenue share as a percentage of total revenue, and show the cumulative percentage. |
| 0.8726 | Rank customers by their total spending using a window function. |

## Interpretation

The live model generated valid read-only SQL for every bundled case under the
structural scorer. The harder window-function, CTE, and nested aggregate tasks
remain the main improvement frontier because their generated SQL often differs
from the reference query. The next local run should use:

```bash
uvx poetry run ai-data-analyst-live-sql-benchmark --source local --limit 16 --model gpt-4o-mini --execution
```
