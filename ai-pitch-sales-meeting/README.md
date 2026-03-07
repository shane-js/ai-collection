# AI Pitch Sales Meeting

Generate compelling sales pitches by analyzing company and product websites using AI.

## Installation

```bash
uv sync
```

## Usage

Generate a sales pitch by providing:
1. The name of the company you're pitching to
2. The company's website URL
3. Your product/service website URL

```bash
uv run pitch-meeting "HuggingFace" "https://huggingface.co" "https://openai.com"
```

The tool will:
- Scrape both websites to extract content
- Generate a personalized sales pitch using GPT-4o-mini
- Stream the output directly to your terminal

### Help

```bash
uv run pitch-meeting --help
```

## Features

- ✅ AI-powered sales pitch generation
- ✅ Automatic website content extraction
- ✅ Streaming output for immediate feedback
- ✅ SSL error handling and retry logic
- ✅ Best sales framework techniques applied

## Requirements

- Python 3.11+
- OpenAI API key (set as `OPENAI_API_KEY` environment variable)

## Example Output

The tool generates personalized sales pitches that:
- Address the target company's specific context
- Highlight relevant features of your product/service
- Use proven sales frameworks
- Focus on booking a follow-up meeting
