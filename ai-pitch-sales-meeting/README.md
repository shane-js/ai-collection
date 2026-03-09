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

### Basic Usage

Generate a sales pitch:

```bash
uv run pitch-meeting "HuggingFace" "https://huggingface.co" "https://openai.com"
```

### Generate Pitch + Meeting Agenda

Generate both a sales pitch and 3-5 meeting agenda items:

```bash
uv run pitch-meeting "HuggingFace" "https://huggingface.co" "https://openai.com" --agenda
```

### View Cost Information

Display token usage and cost for the API calls:

```bash
uv run pitch-meeting "HuggingFace" "https://huggingface.co" "https://openai.com" --cost
```

You can combine flags:

```bash
uv run pitch-meeting "HuggingFace" "https://huggingface.co" "https://openai.com" --agenda --cost
```

### Generate Agenda from Existing Pitch

If you already have a pitch and just want to generate agenda items:

```bash
uv run pitch-meeting "Company" "https://example.com" "https://product.com" --pitch-text "Your existing pitch text..." --agenda
```

The tool will:
- Scrape both websites to extract content
- Generate a personalized sales pitch using gpt-4o-mini (via LiteLLM)
- Stream the output directly to your terminal
- Optionally generate meeting agenda items if the meeting is agreed to
- Optionally display token usage and cost information

### Help

```bash
uv run pitch-meeting --help
```

## Features

- ✅ AI-powered sales pitch generation
- ✅ Automatic website content extraction
- ✅ Streaming output for immediate feedback
- ✅ Meeting agenda generation (3-5 bullet points)
- ✅ Support for using existing pitch text
- ✅ Token usage and cost tracking with --cost flag
- ✅ SSL error handling and retry logic
- ✅ Best sales framework techniques applied
- ✅ Powered by LiteLLM for flexible LLM provider support

## Requirements

- Python 3.11+
- OpenAI API key (set as `OPENAI_API_KEY` environment variable)
- LiteLLM (supports multiple LLM providers)

## Example Output

The tool generates personalized sales pitches that:
- Address the target company's specific context
- Highlight relevant features of your product/service
- Use proven sales frameworks
- Focus on booking a follow-up meeting

When using the `--agenda` flag, it also generates:
- 3-5 concise meeting agenda items
- Key discussion topics aligned with the pitch
- Value propositions and next steps to cover
