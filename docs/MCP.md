# MCP Server

This project includes a small Model Context Protocol server that exposes safe,
project-specific tools for AI hosts.

## Install

```bash
poetry install
```

The project depends on the official MCP Python SDK v2:

```toml
mcp = { version = ">=2.0,<3.0", extras = ["cli"] }
```

## Run

```bash
poetry run ai-data-analyst-mcp
```

For local MCP Inspector workflows, you can also run:

```bash
poetry run mcp dev src/mcp_server/server.py
```

## Exposed Tools

- `project_info`: returns the main source, eval, and app entrypoints.
- `score_sql`: scores one SQL query for read-only validity and basic efficiency.
- `list_eval_cases`: lists dataset questions, difficulties, and required tables.
- `list_huggingface_eval_presets`: lists supported external text-to-SQL benchmark presets.
- `list_huggingface_eval_cases`: streams a small Hugging Face benchmark sample and normalizes it.
- `run_sql_eval`: runs the bundled offline SQL eval dataset as JSON or markdown.
- `run_huggingface_sql_eval`: runs scorer baseline on a streamed Hugging Face text-to-SQL sample.
- `evaluate_sql_predictions`: scores generated SQL predictions against a dataset.
- `evaluate_sql_predictions_report`: returns a markdown report for generated SQL predictions.
- `analyze_rows`: runs non-LLM statistical analysis over caller-provided rows.

## Hugging Face Benchmarks

The eval runner supports Hugging Face text-to-SQL datasets through streaming
loads. Current presets:

- `bird`: `birdsql/bird23-train-filtered`
- `bird-chat`: `lianghsun/bird-text2sql-bench`

Example:

```bash
poetry run ai-data-analyst-evals --source huggingface --hf-preset bird --limit 25 --format markdown
```

This scores the benchmark's expected SQL baseline. To evaluate model-generated
SQL, first generate predictions keyed by question, then pass them with
`--predictions`.

## Exposed Resource

- `project://{relative_path}` for allow-listed files:
  - `README.md`
  - `docs/SYSTEM_ARCHITECTURE.md`
  - `conf/config.yaml`
  - `pyproject.toml`

The MCP server does not expose arbitrary file reads.
