import pytest
from bs4 import BeautifulSoup

from scripts import verify_conversion as vc

HTML_TEMPLATE = """
<div class="hyoudai"><div>{title}</div></div>
<div class="body">{body}</div>
"""


class TestStripAllWhitespace:
    def test_removes_all_whitespace_kinds(self):
        assert vc.strip_all_whitespace("a b\tc\n d　e") == "abcde"


class TestSourceText:
    def test_extracts_body_text(self):
        soup = BeautifulSoup('<div class="body">本文 テキスト</div>', "html.parser")
        assert vc.source_text(soup) == "本文テキスト"

    def test_returns_empty_when_no_body(self):
        soup = BeautifulSoup("<div>no body</div>", "html.parser")
        assert vc.source_text(soup) == ""


class TestGeneratedText:
    def test_strips_front_matter_ial_and_div_tags(self, tmp_path):
        md_path = tmp_path / "sample.md"
        md_path.write_text(
            '---\ntitle: t\n---\n\n本文\n{: .jou}\n<div class="table-wrapper">表</div>',
            encoding="utf-8",
        )

        assert vc.generated_text(md_path) == "本文表"


class TestHasComplexTable:
    def test_detects_rowspan(self):
        soup = BeautifulSoup(
            '<div class="body"><table><tr><td rowspan="2">a</td></tr></table></div>',
            "html.parser",
        )
        assert vc.has_complex_table(soup) is True

    def test_detects_colspan(self):
        soup = BeautifulSoup(
            '<div class="body"><table><tr><td colspan="2">a</td></tr></table></div>',
            "html.parser",
        )
        assert vc.has_complex_table(soup) is True

    def test_false_when_no_span(self):
        soup = BeautifulSoup(
            '<div class="body"><table><tr><td>a</td></tr></table></div>',
            "html.parser",
        )
        assert vc.has_complex_table(soup) is False


class TestHasAttachmentLink:
    def test_detects_attachment_extension(self):
        soup = BeautifulSoup(
            '<div class="body"><a href="doc.pdf">添付</a></div>', "html.parser"
        )
        assert vc.has_attachment_link(soup) is True

    def test_false_for_normal_link(self):
        soup = BeautifulSoup(
            '<div class="body"><a href="page.html">通常</a></div>', "html.parser"
        )
        assert vc.has_attachment_link(soup) is False


class TestMain:
    def _prepare_dirs(self, tmp_path, monkeypatch):
        html_dir = tmp_path / "html"
        output_dir = tmp_path / "_rules"
        html_dir.mkdir()
        output_dir.mkdir()
        monkeypatch.setattr(vc, "HTML_DIR", html_dir)
        monkeypatch.setattr(vc, "OUTPUT_DIR", output_dir)
        return html_dir, output_dir

    def test_reports_success_when_content_matches(self, tmp_path, monkeypatch, capsys):
        html_dir, output_dir = self._prepare_dirs(tmp_path, monkeypatch)
        (html_dir / "rule.html").write_text(
            HTML_TEMPLATE.format(title="テスト規程", body="本文テキスト"),
            encoding="utf-8",
        )
        (output_dir / "テスト規程.md").write_text(
            "---\ntitle: t\n---\n\n本文テキスト\n{: .jou}\n",
            encoding="utf-8",
        )

        vc.main()

        output = capsys.readouterr().out
        assert "未変換ファイル (0件)" in output
        assert "内容欠落の疑いがあるファイル (0件)" in output

    def test_exits_nonzero_when_not_converted(self, tmp_path, monkeypatch):
        html_dir, _ = self._prepare_dirs(tmp_path, monkeypatch)
        (html_dir / "rule.html").write_text(
            HTML_TEMPLATE.format(title="未変換規程", body="本文"), encoding="utf-8"
        )

        with pytest.raises(SystemExit) as exc_info:
            vc.main()

        assert exc_info.value.code == 1

    def test_exits_nonzero_when_content_missing(self, tmp_path, monkeypatch):
        html_dir, output_dir = self._prepare_dirs(tmp_path, monkeypatch)
        (html_dir / "rule.html").write_text(
            HTML_TEMPLATE.format(title="欠落規程", body="欠落した本文"),
            encoding="utf-8",
        )
        (output_dir / "欠落規程.md").write_text(
            "---\ntitle: t\n---\n\n短い\n{: .jou}\n", encoding="utf-8"
        )

        with pytest.raises(SystemExit) as exc_info:
            vc.main()

        assert exc_info.value.code == 1
