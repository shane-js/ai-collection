# ai-web-browse

AI-powered terminal web browser. Fetches a page, summarizes its content, and lets you navigate to the top 3 recommended links interactively.

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- OpenAI API key

## Setup

```bash
cp ../.env.example ../.env  # add your OPENAI_API_KEY
uv sync
```

## Run

```bash
uv run browse-website <url>
```

## .env

```
OPENAI_API_KEY=sk-...
```
