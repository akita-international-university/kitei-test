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
RE_MAEGAKI_HEADING = re.compile(r"^(別表|様式)")

# 見出し系クラス。原文では見た目を整えるため(例:「附　　則」「総　　則」)、
# 短い見出し語の中に全角スペース等が装飾目的で挿入されていることがある。
HEADING_CLASSES = {"shou", "setsu", "jou-hyoudai", "fuki-title", "maegaki"}

# 2文字以上連続する空白（半角スペース・タブ・全角スペース）を検出する正規表現。
# 号番号の直後の区切りスペース(1文字)のような意味のある空白は対象にしない。
RE_DECORATIVE_WHITESPACE = re.compile(r"[ \t　]{2,}")


def clean_text(text: str, cls: str | None) -> str:
    """装飾目的で挿入された連続空白を、アクセシビリティの観点から整形する。

    見出し系クラス(HEADING_CLASSES)では、原文の「附　　則」のように見た目を
    整えるためだけに単語の途中へ挿入された連続空白を完全に取り除く(結果は
    「附則」)。一方、条文・項・号などの本文系クラスでは、金額表や保存期間の
    一覧(moku2)のように連続空白が擬似的な列区切りとして使われているケースが
    あり、全て除去すると別々の項目が意図せず連結されてしまう恐れがあるため、
    半角スペース1つに正規化するにとどめる。
    """
    if cls in HEADING_CLASSES:
        return RE_DECORATIVE_WHITESPACE.sub("", text)
    return RE_DECORATIVE_WHITESPACE.sub(" ", text)


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


def convert_table_div(div, source_name: str = "") -> str:
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
        prefix = f"[{source_name}] " if source_name else ""
        print(
            f"警告: {prefix}表の解析に失敗、生テキストを出力します (id={div.get('id')})",
            file=sys.stderr,
        )
        return div.get_text(separator=" ", strip=True)
    hrows = header_row_count(table)
    md_table = grid_to_markdown_table(grid, hrows)
    return f'<div class="table-wrapper" markdown="1">\n\n{md_table}\n\n</div>'


def classify_unclassed(text: str) -> str:
    """クラス無しdivのテキストから、意味的に近いクラス名を推定する。

    このHTMLはワープロ文書からの変換由来と見られ、条見出し・項・附則見出しなどが
    クラス無しのdivとして出現することが多い。呼び出し元で「新しい単位の開始
    パターンに一致する」ことを確認済みの場合のみ呼ばれるため、ここでは
    そのパターンに対応するクラス名を返す。
    """
    if RE_MAEGAKI_HEADING.match(text):
        return "maegaki"
    if RE_PAREN_HEADING.match(text):
        return "jou-hyoudai"
    if RE_FUKI_TITLE.match(text):
        return "fuki-title"
    if RE_NUMBERED_SUB.match(text):
        return "jou-text"
    if RE_NUMBERED_KOU.match(text):
        return "kou"
    # 呼び出し元で is_new_unit を確認済みのため、ここには到達しない想定
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
    """制定日・制定機関・規程番号を抽出する。

    通常は div.seitei から抽出するが、ごく一部のファイルではこれが空で、
    代わりに div.body の先頭にクラス無し・右寄せ(align="right")のdivとして
    同じ情報が埋め込まれている(ワープロ文書の署名欄をそのまま変換した
    形跡)。これを見逃すと、日付・決定者・規程番号が本文の地の文として
    連結され、意味の通らない1文になってしまう(例:「令和１年１月１日理事長
    決定規程第１号」)。そのため、div.seitei が空の場合はこのパターンも
    フォールバックとして検出し、該当divをdiv.bodyから取り除いておく
    (convert_body側で本文として処理させないため)。
    """
    node = soup.select_one("div.seitei")
    texts = (
        [d.get_text(strip=True) for d in node.find_all("div", recursive=False)]
        if node
        else []
    )
    texts = [t for t in texts if t]

    if not texts:
        body = soup.select_one("div.body")
        leading_divs = []
        if body is not None:
            for div in body.find_all("div", recursive=False):
                if div.get("class") or div.get("align") != "right":
                    break
                text = div.get_text(strip=True)
                if not text:
                    break
                leading_divs.append(div)
                if len(leading_divs) >= 3:
                    break
        if leading_divs:
            texts = [d.get_text(strip=True) for d in leading_divs]
            for div in leading_divs:
                div.decompose()

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
    # リンクの前後に「様式１」の「１」のようにaタグの外側にテキストが
    # 続くケースがあるため、aタグ単体ではなくdiv全体のテキストを使う。
    label = clean_text(div.get_text(strip=True), None)
    href = a["href"] if a else "#"
    return f"[{label}（外部ファイル、本PoCでは未移行）]({href})\n" "{: .gaibu-fuzoku}"


def convert_body(soup, source_name: str = "") -> str:
    """div.body直下の要素を、段落・表・附則ブロックのアイテム列として組み立てる。

    クラス無しdivのテキストは、新しい単位（見出し・項番号・号の細分など）の
    開始パターンに一致する場合のみ新しい段落として扱い、一致しない場合は
    「直前の段落の折り返し継続」として直前の段落へ連結する。この判定は
    常に「直前の段落が何であったか」（items中の最後のparaアイテム）を基準にし、
    クラス無しdiv同士が連続しているか、直前がクラス付きdivだったかは区別しない。
    ワープロ文書からの変換由来と見られるHTMLでは、文の途中でdivが分割されている
    ケース（例:「アドバイ」＋「ザーと…」）があり、これを誤って別ブロックとして
    分割すると読み手に文の切れ目だと誤解させてしまうため。
    """
    body = soup.select_one("div.body")
    if body is None:
        return ""

    items: list[dict] = []
    in_fuki = False
    last_para_idx: int | None = None

    def start_para(cls: str | None, text: str):
        nonlocal last_para_idx, in_fuki
        # 附則ブロックの開閉は、クラス付き/クラス無し(推定)を問わず一律にここで扱う。
        # そうしないと、クラス無しdivから推定された「附則見出し」が視覚的な
        # 附則ボックス(.fuki)で囲われない、という不整合が生じるため。
        if cls == "fuki-title":
            if in_fuki:
                close_block("fuki_close")
            items.append({"kind": "fuki_open"})
            in_fuki = True
        elif in_fuki and cls not in ("fuki-text", "fuki-number"):
            close_block("fuki_close")
            in_fuki = False
        items.append({"kind": "para", "cls": cls, "text": clean_text(text, cls)})
        last_para_idx = len(items) - 1

    def append_to_last_para(text: str):
        para = items[last_para_idx]
        para["text"] += clean_text(text, para["cls"])

    def close_block(kind: str):
        nonlocal last_para_idx
        items.append({"kind": kind})
        last_para_idx = None

    for div in body.find_all("div", recursive=False):
        cls = get_class(div)

        if cls is None:
            text = div.get_text(strip=True)
            if not text:
                continue
            if is_attachment_link(div):
                items.append({"kind": "attachment", "div": div})
                last_para_idx = None
                continue

            is_new_unit = bool(
                RE_MAEGAKI_HEADING.match(text)
                or RE_PAREN_HEADING.match(text)
                or RE_FUKI_TITLE.match(text)
                or RE_NUMBERED_KOU.match(text)
                or RE_NUMBERED_SUB.match(text)
            )
            if is_new_unit:
                start_para(classify_unclassed(text), text)
            elif last_para_idx is not None:
                append_to_last_para(text)
            else:
                prefix = f"[{source_name}] " if source_name else ""
                print(
                    f"警告: {prefix}未分類のコンテンツを検出しました: {text[:40]!r}",
                    file=sys.stderr,
                )
                start_para(None, text)
            continue

        # クラス付きdivは常に新しい段落として扱う
        if cls == "table":
            if in_fuki:
                close_block("fuki_close")
                in_fuki = False
            items.append({"kind": "table", "div": div})
            last_para_idx = None
            continue

        text = div.get_text(strip=True)
        if not text:
            continue

        if cls == "fuki-text" and (text.startswith("別表") or text.startswith("様式")):
            # 別表・様式の見出しは附則の一部ではないため、maegakiとして扱う
            # (附則ブロックの close は start_para が cls=="maegaki" を見て行う)
            start_para("maegaki", text)
            continue

        start_para(cls, text)

    if in_fuki:
        close_block("fuki_close")

    rendered = []
    for item in items:
        kind = item["kind"]
        if kind == "fuki_open":
            rendered.append('<div class="fuki" markdown="1">')
        elif kind == "fuki_close":
            rendered.append("</div>")
        elif kind == "table":
            rendered.append(convert_table_div(item["div"], source_name=source_name))
        elif kind == "attachment":
            rendered.append(render_attachment(item["div"]))
        elif kind == "para":
            cls, text = item["cls"], item["text"]
            if cls is None:
                rendered.append(text)
            else:
                rendered.append(f"{text}\n{{: .{cls}}}")

    return "\n\n".join(rendered)


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

    body_md = convert_body(soup, source_name=html_path.name)

    yaml_text = yaml.safe_dump(
        front_matter, allow_unicode=True, sort_keys=False
    ).strip()
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
    parser.add_argument(
        "html_file",
        nargs="?",
        help="変換対象のHTMLファイル (例: html/xxx.html)。省略時はhtml/以下の全ファイルを変換する",
    )
    parser.add_argument(
        "--out", help="出力先Markdownファイルパス（省略時は _rules/<title>.md）"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="html/ 以下の全ファイルを変換する（html_file省略時と同じ）",
    )
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if args.html_file:
        targets = [Path(args.html_file)]
    else:
        # html_fileも--allも指定されない場合は、poetry run convert2markdown を
        # そのまま「全件変換」として使えるよう、--allと同じ挙動をデフォルトとする。
        targets = sorted(HTML_DIR.glob("*.html"))

    is_single_target = len(targets) == 1 and bool(args.html_file)
    for target in targets:
        content, default_name = convert(target)
        out_path = (
            Path(args.out)
            if (args.out and is_single_target)
            else OUTPUT_DIR / default_name
        )
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(content, encoding="utf-8")
        print(f"変換完了: {target} -> {out_path}")


if __name__ == "__main__":
    main()
