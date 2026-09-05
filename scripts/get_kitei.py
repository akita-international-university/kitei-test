"""現行の規程管理システムに掲載されている規程一式のHTMLファイルを取得する。

対象: https://www4.kitei-kanri.jp/unc/aiu/doc/gakugai/listall.html
取得したHTMLは、規程名をファイル名として ./html/ 以下に保存する。

使い方:
    python scripts/get_kitei.py
"""

import re
import time
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www4.kitei-kanri.jp/unc/aiu/doc/gakugai/"
LIST_URL = urljoin(BASE_URL, "listall.html")
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "html"
REQUEST_INTERVAL_SEC = 0.5
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; kitei-test/1.0)"}

# ファイル名に使えない文字を置き換える
INVALID_FILENAME_CHARS = re.compile(r'[\\/:*?"<>|]')


def sanitize_filename(name: str) -> str:
    """規程名をファイル名として使える文字列に変換する。"""
    name = name.strip().lstrip("○").strip()
    name = INVALID_FILENAME_CHARS.sub("_", name)
    return name


def fetch_rule_list(session: requests.Session) -> list[tuple[str, str]]:
    """一覧ページから (規程名, 規程URL) の一覧を取得する。"""
    response = session.get(LIST_URL, headers=HEADERS)
    response.raise_for_status()
    response.encoding = response.apparent_encoding

    soup = BeautifulSoup(response.text, "html.parser")
    rules = []
    for rule_div in soup.select("div.rule"):
        link = rule_div.find("a")
        if link is None or not link.get("href"):
            continue
        name = link.get_text(strip=True)
        url = urljoin(LIST_URL, link["href"])
        rules.append((name, url))
    return rules


def download_rule(session: requests.Session, name: str, url: str) -> None:
    """1件の規程HTMLを取得し、./html/ 以下にファイル名を付けて保存する。"""
    response = session.get(url, headers=HEADERS)
    response.raise_for_status()
    response.encoding = response.apparent_encoding

    filename = sanitize_filename(name) + ".html"
    output_path = OUTPUT_DIR / filename
    output_path.write_text(response.text, encoding="utf-8")
    print(f"saved: {output_path}")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with requests.Session() as session:
        rules = fetch_rule_list(session)
        print(f"{len(rules)} 件の規程URLを取得しました。")

        for name, url in rules:
            download_rule(session, name, url)
            time.sleep(REQUEST_INTERVAL_SEC)

    print("完了しました。")


if __name__ == "__main__":
    main()
