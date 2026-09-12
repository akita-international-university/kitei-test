"""html/*.html と、対応する _rules/*.md の変換結果を突き合わせて検証する。

各ファイルについて、元HTMLの本文テキストと生成Markdownの本文テキストを
空白正規化した上で文字の多重集合(Counter)として比較し、意図しない内容の
欠落がないかを確認する。装飾的空白の除去(issue #6)や表のMarkdown化に伴う
罫線記号・見出し文言の重複などは「想定される追加」であり欠落ではないため、
欠落(missing)側のみを異常とみなす。

あわせて、rowspan/colspanを含む複雑な表(issue #9の精査対象)や、外部ファイル
への添付リンク(issue #8の精査対象)を含むファイルを一覧化する。

使い方:
    poetry run python scripts/verify_conversion.py > /tmp/verify_report.txt
"""

import re
import sys
from collections import Counter
from pathlib import Path

from bs4 import BeautifulSoup

from scripts.convert_to_markdown import (
    ATTACHMENT_EXT_RE,
    HTML_DIR,
    OUTPUT_DIR,
    extract_seitei,
    extract_title,
    sanitize_filename,
)

WHITESPACE_RE = re.compile(r"\s+")
IAL_RE = re.compile(r"\{:\s*\.[a-zA-Z0-9_-]+\s*\}")
DIV_TAG_RE = re.compile(r"</?div[^>]*>")


def strip_all_whitespace(text: str) -> str:
    return WHITESPACE_RE.sub("", text)


def source_text(soup) -> str:
    """soupの本文テキストを取得する。

    呼び出し前に extract_seitei(soup) を実行し、制定日等が本文冒頭に
    埋め込まれているケースを本文から除去しておくこと(convert_to_markdown
    の convert() と同じ前処理をした状態で比較しないと、front matterへ
    移した内容が「欠落」と誤検出されてしまうため)。
    """
    body = soup.select_one("div.body")
    return strip_all_whitespace(body.get_text()) if body else ""


def generated_text(md_path: Path) -> str:
    md = md_path.read_text(encoding="utf-8")
    body = md.split("---", 2)[-1]
    body = IAL_RE.sub("", body)
    body = DIV_TAG_RE.sub("", body)
    return strip_all_whitespace(body)


def has_complex_table(soup) -> bool:
    for table in soup.select("div.body table"):
        for cell in table.find_all(["td", "th"]):
            if cell.get("rowspan") or cell.get("colspan"):
                return True
    return False


def has_attachment_link(soup) -> bool:
    for a in soup.select("div.body a[href]"):
        if ATTACHMENT_EXT_RE.search(a["href"]):
            return True
    return False


def main() -> None:
    missing_content: list[tuple[str, dict]] = []
    not_converted: list[str] = []
    complex_table_files: list[str] = []
    attachment_files: list[str] = []

    for html_path in sorted(HTML_DIR.glob("*.html")):
        soup = BeautifulSoup(html_path.read_text(encoding="utf-8"), "html.parser")
        title = extract_title(soup)
        slug = sanitize_filename(title or html_path.stem)
        md_path = OUTPUT_DIR / f"{slug}.md"

        if has_complex_table(soup):
            complex_table_files.append(html_path.name)
        if has_attachment_link(soup):
            attachment_files.append(html_path.name)

        if not md_path.exists():
            not_converted.append(html_path.name)
            continue

        # convert()と同じ前処理(制定日等の本文先頭埋め込みパターンの除去)をしてから比較する
        extract_seitei(soup)

        src = Counter(source_text(soup))
        gen = Counter(generated_text(md_path))
        missing = src - gen
        if missing:
            missing_content.append((html_path.name, dict(missing)))

    print(f"# 検証対象: {len(list(HTML_DIR.glob('*.html')))}件")
    print()
    print(f"## 未変換ファイル ({len(not_converted)}件)")
    for name in not_converted:
        print(f"- {name}")
    print()
    print(f"## 内容欠落の疑いがあるファイル ({len(missing_content)}件)")
    for name, missing in missing_content:
        print(f"- {name}: {missing}")
    print()
    print(f"## 複雑な表(rowspan/colspan)を含むファイル — issue #9の精査対象 ({len(complex_table_files)}件)")
    for name in complex_table_files:
        print(f"- {name}")
    print()
    print(f"## 外部ファイルへの添付リンクを含むファイル — issue #8の精査対象 ({len(attachment_files)}件)")
    for name in attachment_files:
        print(f"- {name}")

    if missing_content or not_converted:
        sys.exit(1)


if __name__ == "__main__":
    main()
