"""html/*.html に含まれる添付ファイル（様式・別表等）へのリンクを抽出し、到達性を検証する。

現行の規程管理システムのHTMLでは、様式や別表がExcel/Word等の外部ファイルとして
添付されており、そのリンクは `../gakugai/files/<ID>.<ext>` という相対パスで
記述されている。この相対パスは現行システム上でのみ解決可能であり、GitHub Pages
上ではリンク切れとなる（issue #8）。

本スクリプトは全HTMLから添付リンクを抽出し、現行システムの絶対URLへ解決した上で
到達性（HTTPステータス）を確認し、Markdownの一覧表として出力する。

外部サイトへのアクセスを伴うため、get_kitei.py と同じ間隔（REQUEST_INTERVAL_SEC）
を空けてリクエストする。--offline を指定すると到達性確認を省略し、抽出のみを行う。

使い方:
    poetry run checkattachments > docs/investigations/attachment-links.md
    poetry run checkattachments --offline
"""

import argparse
import sys
import time
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from scripts.convert_to_markdown import (
    ATTACHMENT_EXT_RE,
    HTML_DIR,
    clean_text,
    extract_title,
)
from scripts.get_kitei import BASE_URL, HEADERS, REQUEST_INTERVAL_SEC

# 元HTMLのアンカーは `<a href="../gakugai/files/98.doc"">` のように閉じ引用符が
# 重複しており、HTMLとして不正である。HTMLパーサは余分な `"` を別の属性として
# 読み飛ばすためhref自体は取得できるが、元システム由来の不備として記録する。
MALFORMED_ATTR = '"'


def iter_attachment_links(soup):
    """div.body内の添付リンクを (ラベル, href, 引用符不備か) で列挙する。"""
    for a in soup.select("div.body a[href]"):
        href = a["href"]
        if not ATTACHMENT_EXT_RE.search(href):
            continue
        # 「様式１」の「１」のようにaタグの外側へテキストが続くケースがあるため、
        # 親div全体のテキストをラベルとして使う（convert_to_markdownと同じ方針）。
        container = a.find_parent("div") or a
        label = clean_text(container.get_text(strip=True), None)
        yield label, href, MALFORMED_ATTR in a.attrs


def check_url(session: requests.Session, url: str) -> tuple[str, str]:
    """添付ファイルURLの到達性を確認し、(ステータス, Content-Type) を返す。"""
    try:
        response = session.head(url, headers=HEADERS, allow_redirects=True, timeout=30)
    except requests.RequestException as exc:
        return f"ERROR: {type(exc).__name__}", "-"
    content_type = response.headers.get("Content-Type", "-").split(";")[0].strip()
    return str(response.status_code), content_type or "-"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--offline",
        action="store_true",
        help="外部サイトへの到達性確認を省略し、リンクの抽出のみを行う",
    )
    args = parser.parse_args()

    rows: list[dict] = []
    for html_path in sorted(HTML_DIR.glob("*.html")):
        soup = BeautifulSoup(html_path.read_text(encoding="utf-8"), "html.parser")
        title = extract_title(soup) or html_path.stem
        for label, href, malformed in iter_attachment_links(soup):
            rows.append(
                {
                    "rule": title,
                    "label": label,
                    "href": href,
                    "url": urljoin(BASE_URL, href),
                    "malformed": malformed,
                    "status": "-",
                    "content_type": "-",
                }
            )

    if not args.offline:
        with requests.Session() as session:
            # 同一URLが複数の規程から参照される可能性があるため、URL単位で1回だけ確認する
            checked: dict[str, tuple[str, str]] = {}
            for row in rows:
                url = row["url"]
                if url not in checked:
                    checked[url] = check_url(session, url)
                    time.sleep(REQUEST_INTERVAL_SEC)
                row["status"], row["content_type"] = checked[url]

    render_report(rows, offline=args.offline)

    # 到達不能なリンクがあれば異常終了する（CIから利用する場合の判定に使う）
    if not args.offline:
        unreachable = [r for r in rows if not r["status"].startswith("2")]
        if unreachable:
            sys.exit(1)


def render_report(rows: list[dict], offline: bool) -> None:
    rule_count = len({r["rule"] for r in rows})
    file_count = len({r["url"] for r in rows})
    malformed_count = sum(1 for r in rows if r["malformed"])

    ext_counts: dict[str, int] = {}
    for row in rows:
        ext = Path(row["href"]).suffix.lower().lstrip(".")
        ext_counts[ext] = ext_counts.get(ext, 0) + 1

    print("# 添付ファイル（様式・別表等）へのリンクの検証結果")
    print()
    print("- 対応Issue: #8")
    print(
        f"- 生成コマンド: `poetry run checkattachments{' --offline' if offline else ''}`"
    )
    print()
    print("## サマリ")
    print()
    print(f"- 添付リンクを含む規程: {rule_count}件")
    print(
        f"- 添付リンク総数: {len(rows)}本（参照先ファイルはユニークで{file_count}件）"
    )
    print(
        "- 拡張子別: "
        + " / ".join(
            f"{ext} {n}" for ext, n in sorted(ext_counts.items(), key=lambda kv: -kv[1])
        )
    )
    print(f"- 閉じ引用符が重複した不正なアンカー: {malformed_count}本 / {len(rows)}本")
    if not offline:
        status_counts: dict[str, int] = {}
        for row in rows:
            status_counts[row["status"]] = status_counts.get(row["status"], 0) + 1
        print(
            "- HTTPステータス別: "
            + " / ".join(f"{s} {n}" for s, n in sorted(status_counts.items()))
        )
    print()
    print("## 一覧")
    print()
    columns = ["規程", "ラベル", "元href", "解決後URL", "引用符不備"]
    if not offline:
        columns += ["ステータス", "Content-Type"]
    print("| " + " | ".join(columns) + " |")
    print("| " + " | ".join("---" for _ in columns) + " |")
    for row in rows:
        cells = [
            row["rule"],
            row["label"],
            f"`{row['href']}`",
            row["url"],
            "あり" if row["malformed"] else "",
        ]
        if not offline:
            cells += [row["status"], row["content_type"]]
        print("| " + " | ".join(cells) + " |")


if __name__ == "__main__":
    main()
