# AI Terrible Advice SFT Data Generator

> **🧪 Proof of Concept:** This is a learning/exploration project, not a production-ready tool. It was built to experiment with distilabel pipelines, LLM-as-judge patterns, and synthetic data generation. Expect rough edges.

Generate a synthetic dataset of convincingly wrong advice using HuggingFace's `distilabel` library. By default, a local model (Ollama) generates the advice; a smarter model (OpenAI) judges how convincingly terrible it is on two dimensions. You can optionally use an OpenAI model for generation too via `--generator-model`. Only entries meeting the configured score thresholds are kept.

> **⚠️ Disclaimer:** This project is for **educational and research purposes only**. The generated content is intentionally incorrect advice produced to study synthetic data generation pipelines and LLM-as-judge evaluation patterns. It is not intended to be taken seriously, acted upon, or redistributed as genuine guidance. Actually taking and implementing any advice generated could cause harm and should not be done.
>
> Datasets of this type have legitimate positive societal applications — including training classifiers that detect unhelpful, misleading, or sarcastic content, and reducing false positives in "helpfulness" detection models by teaching them what *convincingly wrong* looks like. The author assumes no responsibility for misuse of generated content.

## How It Works

A three-step distilabel pipeline:

1. **Seed topics** — a list of advice topics (career, cooking, finance, etc.) is loaded into the pipeline
2. **Generate** — `qwen2.5:7b` via Ollama (or any LiteLLM model via `--generator-model`) generates a realistic question + confidently wrong advice for each topic
3. **Judge** — `gpt-5.4-nano` via OpenAI scores each piece on two axes:
   - **impact_score** (0–5): intersection of believability and bad-outcome severity — how likely a typical person is to follow it *and* regret it
   - **humor_score** (0–5): how funny or entertaining the advice is, scored independently

The output is a filtered HuggingFace `Dataset` with columns: `topic`, `question`, `advice`, `impact_score`, `humor_score`, `rationale`.

## Installation

```bash
uv sync
```

**Requirements:**
- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- [Ollama](https://ollama.com) running locally with `qwen2.5:7b` pulled *(only needed without `--generator-model`)*
- OpenAI API key

```bash
ollama pull qwen2.5:7b
```

Add to `.env`:
```
OPENAI_API_KEY=sk-...

# Required only for --push-to-hub
HF_TOKEN=hf_...
```

## Usage

```bash
uv run terrible-advice [OPTIONS]
```

### Options

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--min-impact N` | int | — | Keep only rows with `impact_score >= N` (0–5) |
| `--min-humor N` | int | — | Keep only rows with `humor_score >= N` (0–5) |
| `--num-topics N` | int | all | Number of seed topics to randomly sample per pipeline run |
| `--min-quantity N` | int | — | Re-run the pipeline until N filtered rows are collected |
| `--dry` | flag | — | Print filtered results to terminal only; do not save or push |
| `--auto-push-hub REPO_ID` | string | — | After generation, save results to JSON **and** push to HuggingFace Hub at `username/dataset-name` (requires `HF_TOKEN` in `.env`) |
| `--publish-from-file FILE REPO_ID` | string string | — | Skip generation — push an existing JSON results file to HuggingFace Hub (requires `HF_TOKEN` in `.env`) |
| `--time-budget MINUTES` | int | `10` | Minutes available; won't start a new run once elapsed, but lets the current run finish |

### Examples

```bash
# Inspect results without saving (dry run, filter by both scores, 5 random topics)
uv run terrible-advice --dry --min-impact 4 --min-humor 3 --num-topics 5

# Collect at least 50 high-quality rows across all topics, save to JSON
uv run terrible-advice --min-impact 4 --min-quantity 50

# Collect at least 50 high-quality rows, save to JSON and push to Hub
uv run terrible-advice --min-impact 4 --min-quantity 50 --auto-push-hub username/my-dataset

# Long run with extended timeout, 10 random topics per run
uv run terrible-advice --min-impact 4 --min-quantity 100 --num-topics 10 --auto-push-hub username/my-dataset --time-budget 60

# Use OpenAI for both generation and judging (no Ollama needed)
uv run terrible-advice --generator-model openai/gpt-5.4-nano --min-impact 4 --min-quantity 50

# Publish an already-generated JSON file to Hub (skip generation)
uv run terrible-advice --publish-from-file 20260327-123456-results.json username/my-dataset
```

### Output

| Mode | Output |
|------|--------|
| `--dry` | Terminal only |
| default | `YYYYMMDD-HHMMSS-results.json` in current directory |
| `--auto-push-hub REPO_ID` | `YYYYMMDD-HHMMSS-results.json` + HuggingFace Hub dataset |
| `--publish-from-file FILE REPO_ID` | HuggingFace Hub dataset (no generation, no new file) |
| Timeout, non-dry | `YYYYMMDD-HHMMSS-partial-results.json` in current directory |
| Timeout, `--auto-push-hub` | `YYYYMMDD-HHMMSS-partial-results.json` + HuggingFace Hub dataset |
| Timeout, `--dry` | Terminal only |

### HuggingFace Hub

Set `HF_TOKEN` in `.env`. You must supply a `REPO_ID` in `username/dataset-name` format — the dataset repo will be **auto-created** on HuggingFace if it doesn't already exist, so there's no need to create it manually first.

```bash
# Auto push immediately after generation (also saves JSON locally)
uv run terrible-advice --auto-push-hub username/my-dataset

# Push an existing results file without re-running generation
uv run terrible-advice --publish-from-file 20260327-123456-results.json username/my-dataset
```

## Concepts Explored

- **Distilabel pipelines** — step-by-step (DAG-based) synthetic data generation with `Pipeline`, `Step`, `Task`
- **LLM-as-judge** — using one model to evaluate another's output on multiple dimensions
- **Two-model pipeline** — cheap local model for bulk generation, smarter API model for scoring
- **Multi-loop collection** — re-running until a quality-filtered quantity target is met
- **HuggingFace `datasets`** — structured dataset export and Hub publishing
- **Synthetic SFT data** — the kind of data used downstream for supervised fine-tuning and preference optimization
