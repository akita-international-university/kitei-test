"""スクレイピング済みの規程HTML（./html/*.html）を、Jekyll向けのMarkdown（_rules/*.md）に変換する。

対象HTMLは意味づけされたdivクラス（shou=章、setsu=節、jou/jou2=条、jou-hyoudai=条見出し、
kou=項、rui/moku2=号、fuki-title/fuki-text/fuki-number=附則、maegaki=別表様式見出し、
table=別表様式の表）で構成されたフラットな一覧であり、条・項・号の番号は諸規程管理規程の
定めに従い地の文としてすでに書き出されている。本スクリプトはその視覚的な階層構造を
kramdownのブロック属性リスト（{: .classname}）を使ってMarkdown+CSSへ移植する。

別表・様式の表（rowspan/colspanを含む）は、大学のWebアクセシビリティ方針
（JIS X 8341-3:2016 レベルAA準拠目標）に沿って、忠実な見た目の再現よりも内容を保った
単純な行×列構造を優先し、標準的なMarkdown表（ヘッダー行1つ）に変換する。

使い方:
    python scripts/convert_to_markdown.py html/<file>.html [--out _rules/<slug>.md]
    python scripts/convert_to_markdown.py --all
"""

import argparse
import re
import sys
from pathlib import Path

import yaml
from bs4 import BeautifulSoup

HTML_DIR = Path(__file__).resolve().parent.parent / "html"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "_rules"

# ファイル名に使えない文字を置き換える（get_kitei.py と同じ考え方）
INVALID_FILENAME_CHARS = re.compile(r'[\\/:*?"<>|]')

# 外部ファイル（Excel/Word等）への添付リンクの拡張子
ATTACHMENT_EXT_RE = re.compile(r"\.(docx?|xlsx?|pptx?|pdf)$", re.IGNORECASE)

# クラス無しdivのテキストから種別を推定するための正規表現
RE_PAREN_HEADING = re.compile(r"^[（(].+[）)]$")
RE_FUKI_TITLE = re.compile(r"^附[\s\u3000]*則$")
RE_NUMBERED_KOU = re.compile(r"^[０-９0-9]+[\s\u3000]")
RE_NUMBERED_SUB = re.compile(r"^([０-９0-9]+[．.]|[•]|[ａ-ｚa-z][．.])")


def sanitize_filename(name: str) -> str:
    """規程名をファイル名として使える文字列に変換する（get_kitei.py と同じ規則）。"""
    name = name.strip().lstrip("○").strip()
    name = INVALID_FILENAME_CHARS.sub("_", name)
    return name


def get_class(div) -> str | None:
    classes = div.get("class")
    return classes[0] if classes else None


def get_cell_text(cell) -> str:
    """セル内の複数<p>を<br>で連結してテキスト化する。"""
    paragraphs = cell.find_all("p")
    parts = []
    for p in paragraphs if paragraphs else [cell]:
        text = p.get_text(strip=True)
        if text:
            parts.append(text)
    return "<br>".join(parts)


def html_table_to_grid(table) -> list[list[str]]:
    """rowspan/colspanを展開し、結合セルの値を対象範囲全体に複製したフラットな行列を返す。

    複雑な表を無理にそのまま(rowspan/colspan付き生HTML)再現するのではなく、
    各行・各列が単独で意味を持つ単純な表として読めるようにするための変換。
    """
    trs = table.find_all("tr")
    span_map: dict[int, list] = {}  # col_idx -> [残り行数, テキスト]
    grid: list[list[str]] = []
    total_cols = None

    for tr in trs:
        cells = tr.find_all(["td", "th"], recursive=False)
        row: dict[int, str] = {}
        col_idx = 0
        ci = 0
        while True:
            if total_cols is not None and col_idx >= total_cols:
                break
            if col_idx in span_map and span_map[col_idx][0] > 0:
                row[col_idx] = span_map[col_idx][1]
                span_map[col_idx][0] -= 1
                if span_map[col_idx][0] == 0:
                    del span_map[col_idx]
                col_idx += 1
                continue
            if ci >= len(cells):
                break
            cell = cells[ci]
            ci += 1
            text = get_cell_text(cell)
            colspan = int(cell.get("colspan", 1) or 1)
            rowspan = int(cell.get("rowspan", 1) or 1)
            for _ in range(colspan):
                row[col_idx] = text
                if rowspan > 1:
                    span_map[col_idx] = [rowspan - 1, text]
                col_idx += 1
        if total_cols is None:
            total_cols = col_idx
        grid.append([row.get(i, "") for i in range(total_cols)])

    return grid


def header_row_count(table) -> int:
    """先頭行のセルの最大rowspanを見出し行数とみなす（ヘッダーが複数行にまたがる表向け）。"""
    trs = table.find_all("tr")
    if not trs:
        return 1
    cells = trs[0].find_all(["td", "th"], recursive=False)
    max_rowspan = 1
    for c in cells:
        rowspan = int(c.get("rowspan", 1) or 1)
        max_rowspan = max(max_rowspan, rowspan)
    return max_rowspan


def escape_cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ").strip()


def grid_to_markdown_table(grid: list[list[str]], header_rows: int) -> str:
    if not grid:
        return ""
    ncols = len(grid[0])
    header_rows = min(header_rows, max(len(grid) - 1, 1))

    header_cells = []
    for col in range(ncols):
        seen = []
        for r in range(header_rows):
            for seg in re.split(r"<br\s*/?>", grid[r][col]):
                seg = seg.strip()
                if seg and seg not in seen:
                    seen.append(seg)
        header_cells.append(" ".join(seen))

    data_rows = grid[header_rows:]

    lines = ["| " + " | ".join(escape_cell(c) for c in header_cells) + " |"]
    lines.append("|" + "|".join(["---"] * ncols) + "|")
    for row in data_rows:
        lines.append("| " + " | ".join(escape_cell(c) for c in row) + " |")
    return "\n".join(lines)


def convert_table_div(div) -> str:
    table = div.find("table")
    if table is None:
        return ""
    grid = html_table_to_grid(table)
    if not grid or len(grid) < 2:
        # 表ではなく単一セルに複数行の箇条書きを詰め込んだレイアウトの場合、
        # <p>ごとの改行を保ったまま段落として出力する（表組みとしては扱わない）。
        lines = [p.get_text(strip=True) for p in table.find_all("p")]
        lines = [line for line in lines if line]
        if lines:
            return "<br>\n".join(lines) + "\n{: .table-list}"
        print(f"警告: 表の解析に失敗、生テキストを出力します (id={div.get('id')})", file=sys.stderr)
        return div.get_text(separator=" ", strip=True)
    hrows = header_row_count(table)
    md_table = grid_to_markdown_table(grid, hrows)
    return f'<div class="table-wrapper" markdown="1">\n\n{md_table}\n\n</div>'


def classify_unclassed(text: str, prev_class: str | None) -> str:
    """クラス無しdivのテキストから、意味的に近いクラス名を推定する。

    このHTMLはワープロ文書からの変換由来と見られ、条見出し・項・附則見出しなどが
    クラス無しのdivとして出現することが多い。テキストのパターンから妥当なクラスを
    推定し、判別できない場合のみ 'unclassified' として警告つきで残す。
    """
    if RE_PAREN_HEADING.match(text):
        return "jou-hyoudai"
    if RE_FUKI_TITLE.match(text):
        return "fuki-title"
    if RE_NUMBERED_SUB.match(text):
        return "jou-text"
    if RE_NUMBERED_KOU.match(text):
        return "kou"
    if prev_class and prev_class.startswith("fuki"):
        return "fuki-text"
    return "unclassified"


def extract_title(soup) -> str:
    node = soup.select_one("div.hyoudai > div")
    return node.get_text(strip=True) if node else ""


def extract_category(soup, title: str) -> list[str]:
    node = soup.select_one("div.taikei_left")
    if node is None:
        return []
    text = node.get_text(strip=True)
    text = text.replace("\u00a0", " ")
    segments = [seg.strip() for seg in text.split(">")]
    segments = [seg for seg in segments if seg]
    if segments and segments[0] == "最上位":
        segments = segments[1:]
    if segments and segments[-1] == title:
        segments = segments[:-1]
    return segments


def extract_seitei(soup) -> dict:
    node = soup.select_one("div.seitei")
    if node is None:
        return {}
    texts = [d.get_text(strip=True) for d in node.find_all("div", recursive=False)]
    texts = [t for t in texts if t]
    result = {}
    if len(texts) >= 1:
        result["enacted_date"] = texts[0]
    if len(texts) >= 2:
        result["enacting_body"] = texts[1]
    if len(texts) >= 3:
        result["rule_number"] = texts[2]
    return result


def is_attachment_link(div) -> bool:
    a = div.find("a")
    return bool(a and a.get("href") and ATTACHMENT_EXT_RE.search(a["href"]))


def render_attachment(div) -> str:
    a = div.find("a")
    label = a.get_text(strip=True) if a else div.get_text(strip=True)
    href = a["href"] if a else "#"
    return (
        f"[{label}（外部ファイル、本PoCでは未移行）]({href})\n"
        "{: .gaibu-fuzoku}"
    )


def convert_body(soup) -> str:
    body = soup.select_one("div.body")
    if body is None:
        return ""

    output_parts: list[str] = []
    in_fuki = False

    pending_text = ""
    pending_class = None

    def flush_pending():
        nonlocal pending_text, pending_class
        if pending_text:
            output_parts.append(emit(pending_class, pending_text))
        pending_text = ""
        pending_class = None

    def emit(cls: str, text: str) -> str:
        if cls == "unclassified":
            print(f"警告: 未分類のコンテンツを検出しました: {text[:40]!r}", file=sys.stderr)
            return text
        return f"{text}\n{{: .{cls}}}"

    for div in body.find_all("div", recursive=False):
        cls = get_class(div)

        if cls is None:
            text = div.get_text(strip=True)
            if not text:
                continue
            if is_attachment_link(div):
                flush_pending()
                output_parts.append(render_attachment(div))
                continue
            inferred = classify_unclassed(text, pending_class or _last_real_class(output_parts))
            is_new_unit_pattern = bool(
                RE_PAREN_HEADING.match(text)
                or RE_FUKI_TITLE.match(text)
                or RE_NUMBERED_KOU.match(text)
                or RE_NUMBERED_SUB.match(text)
            )
            if pending_text and is_new_unit_pattern:
                flush_pending()
                pending_class = inferred
                pending_text = text
            elif not pending_text:
                pending_class = inferred
                pending_text = text
            else:
                # パターンに一致しない断片 = 直前の段落の折り返し継続とみなして連結する
                pending_text += text
            continue

        # クラス付きdivが来たら、保留中のクラス無しテキストを確定させる
        flush_pending()

        if cls == "table":
            if in_fuki:
                output_parts.append("</div>")
                in_fuki = False
            output_parts.append(convert_table_div(div))
            continue

        text = div.get_text(strip=True)
        if not text:
            continue

        if cls == "fuki-title":
            if in_fuki:
                output_parts.append("</div>")
            output_parts.append('<div class="fuki" markdown="1">')
            in_fuki = True
            output_parts.append(emit(cls, text))
            continue

        if cls == "fuki-text" and (text.startswith("別表") or text.startswith("様式")):
            # 別表・様式の見出しは附則の一部ではないため、附則ブロックを閉じてから出力する
            if in_fuki:
                output_parts.append("</div>")
                in_fuki = False
            output_parts.append(emit("maegaki", text))
            continue

        output_parts.append(emit(cls, text))

    flush_pending()
    if in_fuki:
        output_parts.append("</div>")

    return "\n\n".join(output_parts)


def _last_real_class(output_parts: list[str]) -> str | None:
    if not output_parts:
        return None
    match = re.search(r"\{:\s*\.([a-zA-Z0-9_-]+)\s*\}\s*$", output_parts[-1])
    return match.group(1) if match else None


def convert(html_path: Path) -> tuple[str, str]:
    """HTMLファイルを変換し、(front matter込みMarkdown, 出力ファイル名) を返す。"""
    html = html_path.read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")

    title = extract_title(soup)
    front_matter = {
        "title": title,
        "category": extract_category(soup, title),
        "source_file": html_path.name,
    }
    front_matter.update(extract_seitei(soup))

    body_md = convert_body(soup)

    yaml_text = yaml.safe_dump(front_matter, allow_unicode=True, sort_keys=False).strip()
    # front matterはファイル先頭が "---" で始まらないとJekyllに認識されないため、
    # 生成元の注記はHTMLコメントではなくYAMLコメントとしてfront matter内に置く。
    content = (
        "---\n"
        "# このファイルは scripts/convert_to_markdown.py により生成された。\n"
        "# 表以外は直接手編集せず、元HTMLを修正の上スクリプトを再実行すること。\n"
        f"{yaml_text}\n---\n\n{body_md}\n"
    )

    slug = sanitize_filename(title or html_path.stem)
    return content, f"{slug}.md"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("html_file", nargs="?", help="変換対象のHTMLファイル (例: html/xxx.html)")
    parser.add_argument("--out", help="出力先Markdownファイルパス（省略時は _rules/<title>.md）")
    parser.add_argument("--all", action="store_true", help="html/ 以下の全ファイルを変換する")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if args.all:
        targets = sorted(HTML_DIR.glob("*.html"))
    elif args.html_file:
        targets = [Path(args.html_file)]
    else:
        parser.error("html_file を指定するか --all を指定してください。")
        return

    for target in targets:
        content, default_name = convert(target)
        out_path = Path(args.out) if (args.out and not args.all) else OUTPUT_DIR / default_name
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(content, encoding="utf-8")
        print(f"変換完了: {target} -> {out_path}")


if __name__ == "__main__":
    main()
