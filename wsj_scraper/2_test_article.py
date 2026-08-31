"""
Step B: single-article extraction test.

Reuses the authenticated profile from 1_login.py to open one WSJ article
and check whether the real, paywalled article body is readable — as
opposed to just a teaser/paywall message. This is the go/no-go check
before building anything else: if this doesn't work, stop here rather
than trying to defeat whatever is blocking it.

Run:
    venv/bin/python 2_test_article.py "https://www.wsj.com/some-article-url" [--headless]
"""
import re
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

PROFILE_DIR = Path(__file__).parent / "browser_profile"
OUTPUT_DIR = Path(__file__).parent / "output"

PAYWALL_MARKERS = [
    "subscribe now", "sign in to continue", "this content is reserved",
    "already a member", "unlock this article", "become a member",
]


def slugify(url: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", url).strip("_")[:80]


def main():
    if len(sys.argv) < 2:
        print("Usage: python 2_test_article.py <wsj article url> [--headless]")
        sys.exit(1)

    url = sys.argv[1]
    headless = "--headless" in sys.argv

    if not PROFILE_DIR.exists():
        print(f"No saved session found at {PROFILE_DIR}. Run 1_login.py first.")
        sys.exit(1)

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=headless,
        )
        page = context.new_page()
        response = page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(2000)  # let dynamic content settle

        status = response.status if response else None

        paragraphs = page.locator("article p").all_inner_texts()
        if not paragraphs:
            paragraphs = page.locator("p").all_inner_texts()
        text = "\n\n".join(t.strip() for t in paragraphs if t.strip())

        lowered = text.lower()
        hit_markers = [m for m in PAYWALL_MARKERS if m in lowered]

        context.close()

    print(f"HTTP status: {status}")
    print(f"Extracted paragraphs: {len(paragraphs)}")
    print(f"Extracted characters: {len(text)}")

    if len(text) < 600 or hit_markers:
        print("\nLIKELY BLOCKED / PAYWALLED — extraction looks incomplete.")
        if hit_markers:
            print(f"Paywall-like phrases found: {hit_markers}")
        print("Stop here and report this rather than trying to work around it.")
    else:
        print("\nLooks like a real article body was extracted.")

    OUTPUT_DIR.mkdir(exist_ok=True)
    out_path = OUTPUT_DIR / f"{slugify(url)}.txt"
    out_path.write_text(text)
    print(f"\nFull extracted text saved to {out_path}")


if __name__ == "__main__":
    main()
