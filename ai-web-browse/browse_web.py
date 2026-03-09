import argparse
import json
import sys
import warnings
from urllib.parse import urlparse

import litellm
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from rich.console import Console
from rich.markdown import Markdown

# Suppress SSL warnings when we need to bypass verification
warnings.filterwarnings("ignore", message="Unverified HTTPS request")

load_dotenv(override=True)
console = Console()

# Limit content length to protect from overwhelming token usage on very large websites
MAX_CONTENT_LENGTH = 5000

# Global cost tracker for the browsing session
cost_tracker = {
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "total_tokens": 0,
    "cost_usd": 0.0,
}


def track_usage(response):
    """Update global cost tracker with usage from an API call."""
    if not response:
        return

    # Get usage info
    usage_info = getattr(response, "usage", None)
    if usage_info:
        prompt_tokens = getattr(usage_info, "prompt_tokens", 0)
        completion_tokens = getattr(usage_info, "completion_tokens", 0)
        total_tokens = getattr(usage_info, "total_tokens", 0)

        cost_tracker["prompt_tokens"] += prompt_tokens
        cost_tracker["completion_tokens"] += completion_tokens
        cost_tracker["total_tokens"] += total_tokens

    # Get cost from LiteLLM's built-in cost tracking
    hidden_params = getattr(response, "_hidden_params", {})
    response_cost = hidden_params.get("response_cost", 0) or 0.0
    cost_tracker["cost_usd"] += response_cost


def scrape_page(url: str, timeout: int = 10) -> tuple[str, list[str]]:
    """Fetch a webpage and return its cleaned text and list of absolute links."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        )
    }

    try:
        console.print(f"[dim]Fetching {url}...[/dim]")
        response = requests.get(url, headers=headers, timeout=timeout, verify=True)
        response.raise_for_status()
    except requests.exceptions.SSLError:
        console.print("[yellow]SSL error, retrying without verification...[/yellow]")
        response = requests.get(url, headers=headers, timeout=timeout, verify=False)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        console.print(f"[red]Error: {e}[/red]")
        raise

    soup = BeautifulSoup(response.text, "html.parser")

    # Extract links before stripping tags
    parsed_base = urlparse(url)
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("http"):
            links.append(href)
        elif href.startswith("/"):
            links.append(f"{parsed_base.scheme}://{parsed_base.netloc}{href}")
    links = list(dict.fromkeys(links))  # deduplicate, preserve order

    # Remove non-visible / non-text elements
    for tag in soup(["script", "style", "noscript", "iframe", "head", "meta", "link"]):
        tag.decompose()

    text = soup.get_text(separator="\n")
    lines = [line.strip() for line in text.splitlines()]
    cleaned = "\n".join(line for line in lines if line)

    # Truncate to protect from overwhelming token usage
    if len(cleaned) > MAX_CONTENT_LENGTH:
        cleaned = cleaned[:MAX_CONTENT_LENGTH] + "\n...[content truncated]"

    return cleaned, links


def get_summary(page_text: str) -> str:
    response = litellm.completion(
        model="gpt-4.1-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "Summarize the website's editorial content in concise markdown bullet points "
                    "that take no more than 30 seconds to read. Respond in markdown only.\n\n"
                    "BE SPECIFIC — include real details from the content:\n"
                    "- Actual names of people, countries, teams, or organizations mentioned\n"
                    "- Specific scores, stats, dates, or figures where they appear\n"
                    "- Key outcomes, results, or decisions (not just that something happened)\n"
                    "- Notable quotes or claims if present\n\n"
                    "AVOID vague meta-descriptions like 'the site covers sports and politics' "
                    "or 'various topics are discussed'. If the page is about an event, name the event "
                    "and its specifics. Write as if briefing someone who wants the actual facts.\n\n"
                    "IGNORE and do not mention:\n"
                    "- Cookie notices, consent banners, or tracking preferences\n"
                    "- Ads, ad feedback, or ad-related UI\n"
                    "- Legal boilerplate: Terms of Use, Privacy Policy, GDPR, CCPA, etc.\n"
                    "- Accessibility or language settings\n"
                    "- Navigation menus, footers, or site structure\n"
                    "- Newsletter signups, subscription prompts, or paywalls\n"
                    "- Social media buttons or share counts"
                ),
            },
            {"role": "user", "content": "Website content:\n" + page_text},
        ],
    )

    track_usage(response)
    return response.choices[0].message.content


def get_important_links(page_text: str, links: list[str]) -> list[dict]:
    if not links:
        return []
    response = litellm.completion(
        model="gpt-4.1-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "Given page content and a list of links, pick the 3 most important or "
                    "interesting links a reader would want to follow. Respond with JSON only, "
                    'in this exact format: {"links": [{"label": "Short title", "url": "https://..."}]}'
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Page content:\n{page_text[:3000]}\n\n"
                    "Links found on page:\n" + "\n".join(links[:100])
                ),
            },
        ],
        response_format={"type": "json_object"},
    )

    track_usage(response)
    data = json.loads(response.choices[0].message.content)
    return data.get("links", [])[:3]


def browse(url: str, show_cost: bool = False):
    console.print(f"\n[bold cyan]Fetching:[/bold cyan] {url}\n")

    # Track tokens/cost for this page only
    page_start_tokens = cost_tracker["total_tokens"]
    page_start_cost = cost_tracker["cost_usd"]

    page_text, links = scrape_page(url)
    summary = get_summary(page_text)
    console.print(Markdown(summary))

    important_links = get_important_links(page_text, links)

    # Show cost for this page if requested
    if show_cost:
        page_tokens = cost_tracker["total_tokens"] - page_start_tokens
        page_cost = cost_tracker["cost_usd"] - page_start_cost
        console.print(
            f"\n[dim]This page: {page_tokens:,} tokens, ${page_cost:.4f}[/dim]"
        )

    if not important_links:
        return

    console.print("\n[bold yellow]Top links to explore:[/bold yellow]")
    for i, link in enumerate(important_links, 1):
        console.print(f"  [bold]{i}.[/bold] {link['label']}")
        console.print(f"     [dim]{link['url']}[/dim]")

    valid_choices = [str(i) for i in range(1, len(important_links) + 1)]
    while True:
        choice = (
            input(f"\nChoose a link to follow [{'/'.join(valid_choices)}/q] (q): ")
            .strip()
            .lower()
            or "q"
        )
        if choice == "q":
            break
        if choice in valid_choices:
            browse(important_links[int(choice) - 1]["url"], show_cost)
            break
        console.print(
            f"[red]Invalid choice. Enter {', '.join(valid_choices)}, or q.[/red]"
        )


def main():
    parser = argparse.ArgumentParser(
        description="Browse and explore websites interactively using AI."
    )
    parser.add_argument("url", help="The URL of the website to browse")
    parser.add_argument(
        "--cost",
        action="store_true",
        help="Display token usage and cost information after browsing",
    )
    args = parser.parse_args()

    try:
        browse(args.url, args.cost)

        # Display total cost information if requested
        if args.cost and cost_tracker["total_tokens"] > 0:
            console.print("\n" + "=" * 60)
            console.print("[bold]TOTAL COST FOR SESSION:[/bold]")
            console.print("=" * 60)
            console.print(f"Prompt tokens:     {cost_tracker['prompt_tokens']:,}")
            console.print(f"Completion tokens: {cost_tracker['completion_tokens']:,}")
            console.print(f"Total tokens:      {cost_tracker['total_tokens']:,}")
            console.print(f"Cost (USD):        ${cost_tracker['cost_usd']:.4f}")
    except requests.exceptions.RequestException:
        console.print(
            "\n[red]❌ Failed to fetch website content. Please check the URL and try again.[/red]"
        )
        sys.exit(1)
    except Exception as e:
        console.print(
            f"\n[red]❌ An unexpected error occurred: {type(e).__name__}: {e}[/red]"
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
