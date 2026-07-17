#!/usr/bin/env python3
"""
Scrape AIU regulations from the kitei-kanri website and save them as markdown files.

Usage:
    python3 scripts/fetch_regulations.py

Output:
    Markdown files saved to ./docs/ directory.
"""

import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www4.kitei-kanri.jp/unc/aiu/doc/gakugai/"
LIST_URL = BASE_URL + "listall.html"
DOCS_DIR = Path(__file__).parent.parent / "docs"

# Mapping of full-width digits to half-width digits
FULLWIDTH_DIGITS = str.maketrans("０１２３４５６７８９", "0123456789")


def to_halfwidth(text: str) -> str:
    """Convert full-width digits to half-width digits."""
    return text.translate(FULLWIDTH_DIGITS)


def get_page(url: str, session: requests.Session, retries: int = 3):
    """Fetch a URL and return a BeautifulSoup object, or None on failure."""
    for attempt in range(retries):
        try:
            resp = session.get(url, timeout=30)
            resp.raise_for_status()
            resp.encoding = resp.apparent_encoding or "utf-8"
            return BeautifulSoup(resp.text, "lxml")
        except Exception as exc:
            print(f"  [WARN] Attempt {attempt + 1}/{retries} failed for {url}: {exc}")
            if attempt < retries - 1:
                time.sleep(2)
    return None


def extract_regulation_links(soup: BeautifulSoup) -> list:
    """
    Extract (title, url) pairs for all regulations from the list page.
    Returns a list of (title, absolute_url) tuples.
    """
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        title = a.get_text(strip=True)
        if href and title:
            abs_url = urljoin(LIST_URL, href)
            # Only follow links within the same site
            if urlparse(abs_url).netloc == urlparse(LIST_URL).netloc:
                links.append((title, abs_url))
    return links


def extract_text_lines(soup: BeautifulSoup) -> list:
    """
    Extract plain-text lines from a regulation page.
    Tries to find the main content area.
    """
    # Try common content container elements
    content = None
    for selector in ["#content", ".content", "main", "article", "#main", ".main", "body"]:
        content = soup.select_one(selector)
        if content:
            break

    if content is None:
        content = soup.body or soup

    # Replace <br> with newlines
    for tag in content.find_all(["br"]):
        tag.replace_with("\n")

    lines = []
    for element in content.find_all(["p", "div", "tr", "li", "h1", "h2", "h3", "h4", "td"]):
        text = element.get_text(separator="\n")
        for line in text.splitlines():
            line = line.strip()
            if line:
                lines.append(line)

    # Fallback: get all text
    if not lines:
        text = content.get_text(separator="\n")
        lines = [l.strip() for l in text.splitlines() if l.strip()]

    return lines


def parse_regulation(lines: list) -> str:
    """
    Convert a list of plain-text lines from a regulation page into markdown.

    Structure expected:
      - First non-empty line: document title
      - Lines matching 第n章: chapter headings  -> ## 第n章 ...
      - Lines matching （...）: article title annotations
      - Lines matching 第n条: article headings  -> ### 第n条 (title)
      - Other lines: body text
    """
    # Patterns (full-width or half-width digits allowed)
    chapter_re = re.compile(r"^第[０-９0-9]+章")
    article_re = re.compile(r"^第[０-９0-9]+条")
    annotation_re = re.compile(r"^[（(](.+)[）)]$")

    md_lines = []
    title_found = False
    pending_annotation = None

    for raw_line in lines:
        line = to_halfwidth(raw_line.strip())
        if not line:
            continue

        if not title_found:
            # First non-empty line is the document title
            md_lines.append(f"# {line}\n")
            title_found = True
            continue

        if chapter_re.match(line):
            # Chapter heading
            if pending_annotation:
                # Flush any stray annotation as plain text
                md_lines.append(f"\n{pending_annotation}\n")
                pending_annotation = None
            md_lines.append(f"\n## {line}\n")
            continue

        annotation_match = annotation_re.match(line)
        if annotation_match:
            # Save annotation; it belongs to the NEXT article
            pending_annotation = annotation_match.group(1)
            continue

        if article_re.match(line):
            # Article heading
            # Extract article number and body (e.g. "第1条　この法人は...")
            m = re.match(r"^(第[0-9]+条(?:の[0-9]+)*)([\s　]*)(.*)$", line)
            if m:
                article_num = m.group(1)
                body = m.group(3).strip()
            else:
                article_num = line
                body = ""

            if pending_annotation:
                heading = f"### {article_num} ({pending_annotation})"
                pending_annotation = None
            else:
                heading = f"### {article_num}"

            md_lines.append(f"\n{heading}\n")
            if body:
                md_lines.append(f"\n{body}\n")
            continue

        # Regular body text
        if pending_annotation:
            # Annotation without a following article – emit as plain text
            md_lines.append(f"\n{pending_annotation}\n")
            pending_annotation = None
        md_lines.append(f"\n{line}\n")

    # Flush any remaining annotation
    if pending_annotation:
        md_lines.append(f"\n{pending_annotation}\n")

    return "".join(md_lines).strip() + "\n"


def slugify(title: str) -> str:
    """Create a safe filename from a regulation title."""
    # Remove characters not safe for filenames
    safe = re.sub(r'[\\/*?:"<>|]', "", title)
    safe = safe.strip().replace(" ", "_").replace("\u3000", "_")
    # Limit length
    if len(safe) > 100:
        safe = safe[:100]
    return safe or "regulation"


def main():
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Output directory: {DOCS_DIR}")

    session = requests.Session()
    session.headers.update(
        {"User-Agent": "Mozilla/5.0 (compatible; AIU-regulation-scraper/1.0)"}
    )

    print(f"Fetching regulation list from {LIST_URL} ...")
    list_soup = get_page(LIST_URL, session)
    if list_soup is None:
        print("ERROR: Could not fetch the regulation list page.", file=sys.stderr)
        sys.exit(1)

    links = extract_regulation_links(list_soup)
    if not links:
        print("ERROR: No regulation links found on the list page.", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(links)} regulation link(s).")

    saved = 0
    skipped = 0
    for i, (title, url) in enumerate(links, 1):
        print(f"[{i}/{len(links)}] {title}")
        print(f"  URL: {url}")

        reg_soup = get_page(url, session)
        if reg_soup is None:
            print("  [SKIP] Could not fetch page.")
            skipped += 1
            continue

        lines = extract_text_lines(reg_soup)
        if not lines:
            print("  [SKIP] No text content found.")
            skipped += 1
            continue

        markdown = parse_regulation(lines)
        filename = slugify(title) + ".md"
        filepath = DOCS_DIR / filename
        filepath.write_text(markdown, encoding="utf-8")
        print(f"  Saved -> docs/{filename}")
        saved += 1

        # Be polite to the server
        time.sleep(0.5)

    print(f"\nDone. Saved: {saved}, Skipped: {skipped}")


if __name__ == "__main__":
    main()
