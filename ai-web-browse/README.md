# AI Web Browse

Interactively browse and explore websites using AI to get summaries and discover important links.

## Installation

```bash
uv sync
```

## Usage

Browse any website and get an AI-generated summary with suggested links to explore:

```bash
uv run browse-website "https://github.com"
```

### View Cost Information

Display token usage and cost for the browsing session:

```bash
uv run browse-website "https://github.com" --cost
```

The tool will:
- Fetch and parse the website content
- Generate a concise summary of the page
- Suggest the 3 most important/interesting links to explore
- Allow you to interactively follow links and continue exploring

### Interactive Navigation

After each summary, you can:
- Choose a suggested link by entering its number (1, 2, or 3)
- Press `q` to quit
- Continue browsing deeper into the website

### Help

```bash
uv run browse-website --help
```

## Features

- ✅ AI-powered content summarization
- ✅ Smart link extraction and prioritization
- ✅ Interactive browsing experience
- ✅ Rich terminal formatting with colors
- ✅ SSL error handling
- ✅ Filters out navigation, ads, and boilerplate
- ✅ Token usage and cost tracking with --cost flag
- ✅ Powered by LiteLLM for flexible LLM provider support

## Requirements

- Python 3.11+
- OpenAI API key (set as `OPENAI_API_KEY` environment variable)
- LiteLLM (supports multiple LLM providers)

## Example Session

```bash
$ uv run browse-website "https://news.ycombinator.com"

Fetching: https://news.ycombinator.com

[AI generates summary of Hacker News front page]

Top links to explore:
  1. Interesting Article About X
     https://example.com/article
  2. Cool Project on GitHub
     https://github.com/user/project
  3. Discussion Thread
     https://news.ycombinator.com/item?id=123456

Choose a link to follow [1/2/3/q] (q): 1
[Fetches and summarizes the chosen link...]
```
