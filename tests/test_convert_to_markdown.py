from unittest.mock import patch

import yaml
from bs4 import BeautifulSoup

from scripts import convert_to_markdown as ctm


class TestCleanText:
    def test_removes_decorative_whitespace_for_heading_class(self):
        assert ctm.clean_text("附　　則", "fuki-title") == "附則"

    def test_collapses_decorative_whitespace_for_body_class(self):
        assert ctm.clean_text("金額　　１０００円", "moku2") == "金額 １０００円"

    def test_leaves_single_space_untouched(self):
        assert ctm.clean_text("１ 本文", "kou") == "１ 本文"


class TestSanitizeFilename:
    def test_removes_leading_marker_and_invalid_chars(self):
        assert ctm.sanitize_filename('○テスト/規程"') == "テスト_規程_"


class TestGetClass:
    def test_returns_first_class(self):
        div = BeautifulSoup('<div class="jou kou">x</div>', "html.parser").div
        assert ctm.get_class(div) == "jou"

    def test_returns_none_when_no_class(self):
        div = BeautifulSoup("<div>x</div>", "html.parser").div
        assert ctm.get_class(div) is None


class TestGetCellText:
    def test_joins_multiple_paragraphs_with_br(self):
        cell = BeautifulSoup("<td><p>一行目</p><p>二行目</p></td>", "html.parser").td
        assert ctm.get_cell_text(cell) == "一行目<br>二行目"

    def test_falls_back_to_cell_text_without_paragraphs(self):
        cell = BeautifulSoup("<td>単純セル</td>", "html.parser").td
        assert ctm.get_cell_text(cell) == "単純セル"


class TestHtmlTableToGrid:
    def test_simple_grid(self):
        table = BeautifulSoup(
            "<table><tr><td>a</td><td>b</td></tr><tr><td>c</td><td>d</td></tr></table>",
            "html.parser",
        ).table
        assert ctm.html_table_to_grid(table) == [["a", "b"], ["c", "d"]]

    def test_expands_rowspan_and_colspan(self):
        html = (
            "<table>"
            '<tr><td rowspan="2">A</td><td colspan="2">B</td></tr>'
            "<tr><td>C</td><td>D</td></tr>"
            "</table>"
        )
        table = BeautifulSoup(html, "html.parser").table
        assert ctm.html_table_to_grid(table) == [
            ["A", "B", "B"],
            ["A", "C", "D"],
        ]


class TestHeaderRowCount:
    def test_single_header_row_by_default(self):
        table = BeautifulSoup(
            "<table><tr><td>a</td></tr><tr><td>b</td></tr></table>", "html.parser"
        ).table
        assert ctm.header_row_count(table) == 1

    def test_uses_max_rowspan_of_first_row(self):
        table = BeautifulSoup(
            '<table><tr><td rowspan="3">a</td><td>b</td></tr></table>',
            "html.parser",
        ).table
        assert ctm.header_row_count(table) == 3

    def test_returns_one_when_no_rows(self):
        table = BeautifulSoup("<table></table>", "html.parser").table
        assert ctm.header_row_count(table) == 1


class TestEscapeCell:
    def test_escapes_pipe_and_newline(self):
        assert ctm.escape_cell("a|b\nc") == "a\\|b c"

    def test_strips_surrounding_whitespace(self):
        assert ctm.escape_cell("  a  ") == "a"


class TestGridToMarkdownTable:
    def test_builds_table_with_single_header_row(self):
        grid = [["見出し1", "見出し2"], ["a", "b"]]
        result = ctm.grid_to_markdown_table(grid, header_rows=1)
        lines = result.split("\n")
        assert lines[0] == "| 見出し1 | 見出し2 |"
        assert lines[1] == "|---|---|"
        assert lines[2] == "| a | b |"

    def test_merges_br_separated_multi_row_headers(self):
        grid = [
            ["上段<br>下段", "共通見出し"],
            ["共通見出し", "共通見出し"],
            ["a", "b"],
        ]
        result = ctm.grid_to_markdown_table(grid, header_rows=2)
        header_line = result.split("\n")[0]
        assert header_line == "| 上段 下段 共通見出し | 共通見出し |"

    def test_returns_empty_string_for_empty_grid(self):
        assert ctm.grid_to_markdown_table([], header_rows=1) == ""

    def test_clamps_header_rows_to_available_rows(self):
        grid = [["only-row"]]
        result = ctm.grid_to_markdown_table(grid, header_rows=5)
        lines = result.split("\n")
        # ヘッダー行1行・データ行0行(header_rowsが行数-1=0にクランプされないよう1を下限とする)
        assert lines[0] == "| only-row |"
        assert len(lines) == 2


class TestConvertTableDiv:
    def test_converts_table_with_header_and_data_rows(self):
        html = (
            '<div class="table"><table>'
            "<tr><td>見出し</td></tr><tr><td>データ</td></tr>"
            "</table></div>"
        )
        div = BeautifulSoup(html, "html.parser").div
        result = ctm.convert_table_div(div)
        assert '<div class="table-wrapper" markdown="1">' in result
        assert "| 見出し |" in result
        assert "| データ |" in result

    def test_applies_header_row_override(self):
        html = (
            '<div class="table" id="rule_84"><table>'
            "<tr><td>週20時間</td></tr><tr><td>3日</td></tr><tr><td>10</td></tr>"
            "</table></div>"
        )
        div = BeautifulSoup(html, "html.parser").div
        with patch.dict(
            ctm.TABLE_HEADER_ROWS_OVERRIDE,
            {("国際教養大学における短時間労働者就業規程.html", "rule_84"): 2},
        ):
            result = ctm.convert_table_div(
                div, source_name="国際教養大学における短時間労働者就業規程.html"
            )
        # 見出し2行分がヘッダーとして結合され、データ行は1行のみになる
        assert result.count("\n|---|\n") == 1
        assert "週20時間 3日" in result

    def test_falls_back_to_paragraph_list_for_single_row_table(self):
        html = (
            '<div class="table"><table><tr><td><p>箇条書き</p></td></tr></table></div>'
        )
        div = BeautifulSoup(html, "html.parser").div
        assert ctm.convert_table_div(div) == "箇条書き\n{: .table-list}"

    def test_returns_empty_string_when_no_table(self):
        div = BeautifulSoup('<div class="table"></div>', "html.parser").div
        assert ctm.convert_table_div(div) == ""


class TestClassifyUnclassed:
    def test_maegaki_heading(self):
        assert ctm.classify_unclassed("別表第１") == "maegaki"

    def test_paren_heading(self):
        assert ctm.classify_unclassed("（目的）") == "jou-hyoudai"

    def test_fuki_title(self):
        assert ctm.classify_unclassed("附　則") == "fuki-title"

    def test_numbered_sub(self):
        assert ctm.classify_unclassed("１．本文") == "jou-text"

    def test_numbered_kou(self):
        assert ctm.classify_unclassed("２　本文") == "kou"

    def test_unclassified_fallback(self):
        assert ctm.classify_unclassed("分類できない文章") == "unclassified"


class TestExtractTitle:
    def test_extracts_title_text(self):
        soup = BeautifulSoup(
            '<div class="hyoudai"><div>テスト規程</div></div>', "html.parser"
        )
        assert ctm.extract_title(soup) == "テスト規程"

    def test_returns_empty_when_missing(self):
        soup = BeautifulSoup("<div>no title</div>", "html.parser")
        assert ctm.extract_title(soup) == ""


class TestExtractCategory:
    def test_strips_top_level_prefix_and_title_suffix(self):
        soup = BeautifulSoup(
            '<div class="taikei_left">最上位 &gt; 学則関係 &gt; テスト規程</div>',
            "html.parser",
        )
        assert ctm.extract_category(soup, "テスト規程") == ["学則関係"]

    def test_returns_empty_list_when_missing(self):
        soup = BeautifulSoup("<div>no category</div>", "html.parser")
        assert ctm.extract_category(soup, "テスト規程") == []


class TestExtractSeitei:
    def test_extracts_from_seitei_div(self):
        html = (
            '<div class="seitei">'
            "<div>令和１年１月１日</div><div>理事長決定</div><div>規程第１号</div>"
            "</div>"
        )
        soup = BeautifulSoup(html, "html.parser")
        assert ctm.extract_seitei(soup) == {
            "enacted_date": "令和１年１月１日",
            "enacting_body": "理事長決定",
            "rule_number": "規程第１号",
        }

    def test_falls_back_to_leading_right_aligned_body_divs(self):
        html = (
            '<div class="body">'
            '<div align="right">令和１年１月１日</div>'
            '<div align="right">理事長決定</div>'
            "<div>本文の開始</div>"
            "</div>"
        )
        soup = BeautifulSoup(html, "html.parser")

        result = ctm.extract_seitei(soup)

        assert result == {
            "enacted_date": "令和１年１月１日",
            "enacting_body": "理事長決定",
        }
        # フォールバックで検出したdivはdiv.bodyから取り除かれている
        body = soup.select_one("div.body")
        assert "令和１年１月１日" not in body.get_text()
        assert "本文の開始" in body.get_text()

    def test_returns_empty_dict_when_nothing_found(self):
        soup = BeautifulSoup('<div class="body"><div>本文</div></div>', "html.parser")
        assert ctm.extract_seitei(soup) == {}


class TestIsAttachmentLink:
    def test_true_for_office_document_extension(self):
        div = BeautifulSoup(
            '<div><a href="form.docx">様式</a></div>', "html.parser"
        ).div
        assert ctm.is_attachment_link(div) is True

    def test_false_for_normal_link(self):
        div = BeautifulSoup(
            '<div><a href="page.html">通常</a></div>', "html.parser"
        ).div
        assert ctm.is_attachment_link(div) is False

    def test_false_when_no_link(self):
        div = BeautifulSoup("<div>リンク無し</div>", "html.parser").div
        assert ctm.is_attachment_link(div) is False


class TestRenderAttachment:
    def test_renders_markdown_link_with_class(self):
        div = BeautifulSoup(
            '<div>様式１<a href="form.docx">こちら</a></div>', "html.parser"
        ).div
        result = ctm.render_attachment(div)
        assert result.startswith(
            "[様式１こちら（外部ファイル、本PoCでは未移行）](form.docx)"
        )
        assert result.endswith("{: .gaibu-fuzoku}")


class TestConvertBody:
    def test_builds_heading_table_and_continuation(self):
        html = """
        <div class="body">
          <div class="jou-hyoudai">（目的）</div>
          <div>この規程は本学の運営に関する事項を定める</div>
          <div class="table">
            <table><tr><td>見出し</td></tr><tr><td>データ</td></tr></table>
          </div>
          <div class="fuki-title">附　則</div>
          <div class="fuki-text">この規程は令和１年４月１日から施行する</div>
        </div>
        """
        soup = BeautifulSoup(html, "html.parser")
        result = ctm.convert_body(soup)

        assert (
            "（目的）この規程は本学の運営に関する事項を定める\n{: .jou-hyoudai}"
            in result
        )
        assert '<div class="table-wrapper" markdown="1">' in result
        assert '<div class="fuki" markdown="1">' in result
        assert result.strip().endswith("</div>")

    def test_attachment_link_rendered_as_gaibu_fuzoku(self):
        html = """
        <div class="body">
          <div>様式１<a href="form.docx">こちら</a></div>
        </div>
        """
        soup = BeautifulSoup(html, "html.parser")
        result = ctm.convert_body(soup)
        assert "{: .gaibu-fuzoku}" in result

    def test_returns_empty_string_when_no_body(self):
        soup = BeautifulSoup("<div>no body</div>", "html.parser")
        assert ctm.convert_body(soup) == ""


class TestConvert:
    def test_converts_html_file_to_markdown_with_front_matter(self, tmp_path):
        html_path = tmp_path / "テスト規程.html"
        html_path.write_text(
            """
            <div class="hyoudai"><div>テスト規程</div></div>
            <div class="taikei_left">最上位 &gt; 学則関係 &gt; テスト規程</div>
            <div class="seitei">
              <div>令和１年１月１日</div><div>理事長決定</div><div>規程第１号</div>
            </div>
            <div class="body">
              <div class="jou-hyoudai">（目的）</div>
              <div>本規程の目的を定める</div>
            </div>
            """,
            encoding="utf-8",
        )

        content, filename = ctm.convert(html_path)

        assert filename == "テスト規程.md"
        assert content.startswith("---\n")
        front_matter_text = content.split("---")[1]
        front_matter = yaml.safe_load(front_matter_text)
        assert front_matter["title"] == "テスト規程"
        assert front_matter["category"] == ["学則関係"]
        assert front_matter["source_file"] == "テスト規程.html"
        assert front_matter["enacted_date"] == "令和１年１月１日"
        assert "（目的）本規程の目的を定める\n{: .jou-hyoudai}" in content


class TestRunPrettier:
    def test_calls_npx_prettier_with_given_paths(self, tmp_path):
        paths = [tmp_path / "a.md", tmp_path / "b.md"]
        with patch.object(ctm.subprocess, "call") as mock_call:
            ctm.run_prettier(paths)

        mock_call.assert_called_once_with(
            ["npx", "prettier", "--write", str(paths[0]), str(paths[1])]
        )

    def test_does_nothing_for_empty_list(self):
        with patch.object(ctm.subprocess, "call") as mock_call:
            ctm.run_prettier([])

        mock_call.assert_not_called()


class TestMain:
    def test_converts_all_html_files_without_invoking_real_prettier(
        self, tmp_path, monkeypatch
    ):
        html_dir = tmp_path / "html"
        output_dir = tmp_path / "_rules"
        html_dir.mkdir()
        monkeypatch.setattr(ctm, "HTML_DIR", html_dir)
        monkeypatch.setattr(ctm, "OUTPUT_DIR", output_dir)
        monkeypatch.setattr(ctm.sys, "argv", ["convert_to_markdown.py"])

        (html_dir / "rule.html").write_text(
            """
            <div class="hyoudai"><div>テスト規程</div></div>
            <div class="body"><div class="jou-hyoudai">（目的）</div></div>
            """,
            encoding="utf-8",
        )

        with patch.object(ctm, "run_prettier") as mock_run_prettier:
            ctm.main()

        output_file = output_dir / "テスト規程.md"
        assert output_file.exists()
        mock_run_prettier.assert_called_once()
        assert mock_run_prettier.call_args.args[0] == [output_file]

    def test_converts_single_file_to_custom_output_path(self, tmp_path, monkeypatch):
        html_dir = tmp_path / "html"
        output_dir = tmp_path / "_rules"
        html_dir.mkdir()
        monkeypatch.setattr(ctm, "HTML_DIR", html_dir)
        monkeypatch.setattr(ctm, "OUTPUT_DIR", output_dir)

        html_file = html_dir / "rule.html"
        html_file.write_text(
            """
            <div class="hyoudai"><div>テスト規程</div></div>
            <div class="body"><div class="jou-hyoudai">（目的）</div></div>
            """,
            encoding="utf-8",
        )
        custom_out = tmp_path / "custom.md"
        monkeypatch.setattr(
            ctm.sys,
            "argv",
            ["convert_to_markdown.py", str(html_file), "--out", str(custom_out)],
        )

        with patch.object(ctm, "run_prettier"):
            ctm.main()

        assert custom_out.exists()
