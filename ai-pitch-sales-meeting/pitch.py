import argparse
import sys
import warnings
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from openai import OpenAI

# Suppress SSL warnings when we need to bypass verification
warnings.filterwarnings("ignore", message="Unverified HTTPS request")

load_dotenv(override=True)
openai = OpenAI()

# Limit content length to protect from overwhelming token usage on very large websites
MAX_CONTENT_LENGTH = 5000


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
        print(f"Fetching {url}...", file=sys.stderr)
        response = requests.get(url, headers=headers, timeout=timeout, verify=True)
        response.raise_for_status()
    except requests.exceptions.SSLError:
        print("SSL error, retrying without verification...", file=sys.stderr)
        response = requests.get(url, headers=headers, timeout=timeout, verify=False)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}", file=sys.stderr)
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


def create_sales_pitch_user_prompt(
    company_name_being_sold_to, company_name_being_sold_to_url, product_or_service_url
):
    company_being_sold_to_web_content = scrape_page(company_name_being_sold_to_url)
    product_or_service_web_content = scrape_page(product_or_service_url)
    return f"""You are pitching to {company_name_being_sold_to}, a company with the
        following website content:\n {company_being_sold_to_web_content}. \n
        You are selling a product or service with the following website content:\n {product_or_service_web_content}.
    """


def stream_sales_meeting_pitch(
    company_being_sold_to,
    company_being_sold_to_url,
    product_or_service_url,
):
    """Generate and stream a sales pitch, returning the complete pitch text."""
    system_prompt = """
        You are a top-tier sales agent tasked with creating a concise but compelling
        sales pitch for a company based on the contents of its website and the contents
        of a website for a product or service that is to be sold. The sales pitch should
        use techinques found in the best sales frameworks that have been studied in the
        field of sales focusing on booking a meeting with a sales agent to discuss the
        product or service further.
    """
    user_prompt = create_sales_pitch_user_prompt(
        company_name_being_sold_to=company_being_sold_to,
        company_name_being_sold_to_url=company_being_sold_to_url,
        product_or_service_url=product_or_service_url,
    )

    stream = openai.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        stream=True,
    )

    # Capture the full pitch while streaming
    full_pitch = []
    for chunk in stream:
        content = chunk.choices[0].delta.content or ""
        print(content, end="", flush=True)
        full_pitch.append(content)
    print()  # Final newline

    return "".join(full_pitch)


def generate_meeting_agenda(pitch_text: str) -> str:
    """Generate 3-5 bullet point meeting agenda items based on the sales pitch."""
    system_prompt = """
        You are a professional meeting facilitator. Given a sales pitch, generate
        3-5 concise bullet point agenda items that should be covered if the prospect
        agrees to the meeting. Focus on discussing value propositions, addressing
        potential concerns, and next steps. Format as a clean bullet point list.
    """

    response = openai.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"Sales pitch:\n\n{pitch_text}\n\nGenerate 3-5 meeting agenda items.",
            },
        ],
    )

    return response.choices[0].message.content


def main():
    parser = argparse.ArgumentParser(
        description="Generate a sales pitch by analyzing company and product websites."
    )
    parser.add_argument("company_name", help="Name of the company you're pitching to")
    parser.add_argument("company_url", help="URL of the company's website")
    parser.add_argument("product_url", help="URL of the product/service you're selling")
    parser.add_argument(
        "--agenda",
        action="store_true",
        help="Generate meeting agenda items based on the pitch",
    )
    parser.add_argument(
        "--pitch-text",
        help="Pass in existing pitch text to generate agenda (skips pitch generation)",
    )

    args = parser.parse_args()

    try:
        # If pitch text is provided, use it directly for agenda generation
        if args.pitch_text:
            pitch = args.pitch_text
            print("Using provided pitch text...\n", file=sys.stderr)
        else:
            # Generate the pitch
            pitch = stream_sales_meeting_pitch(
                company_being_sold_to=args.company_name,
                company_being_sold_to_url=args.company_url,
                product_or_service_url=args.product_url,
            )

        # Generate agenda if requested
        if args.agenda:
            print("\n" + "=" * 60, file=sys.stderr)
            print("MEETING AGENDA ITEMS:", file=sys.stderr)
            print("=" * 60 + "\n", file=sys.stderr)

            agenda = generate_meeting_agenda(pitch)
            print(agenda)

    except requests.exceptions.RequestException as e:
        print(
            "\n❌ Failed to fetch website content. Please check the URLs and try again.",
            file=sys.stderr,
        )
        print(f"   Error details: {type(e).__name__}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(
            f"\n❌ An unexpected error occurred: {type(e).__name__}: {e}",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
