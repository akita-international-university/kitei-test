from unittest.mock import MagicMock, patch

import pytest

from scripts import get_kitei


class TestSanitizeFilename:
    def test_removes_leading_marker(self):
        assert get_kitei.sanitize_filename("○テスト規程") == "テスト規程"

    def test_replaces_invalid_chars(self):
        assert get_kitei.sanitize_filename('a/b:c*d?e"f<g>h|i') == "a_b_c_d_e_f_g_h_i"

    def test_strips_surrounding_whitespace(self):
        assert get_kitei.sanitize_filename("  テスト規程  ") == "テスト規程"


class TestFetchRuleList:
    def test_parses_rule_links(self):
        html = """
        <div class="rule"><a href="rule1.html">規程その一</a></div>
        <div class="rule"><a href="rule2.html">規程その二</a></div>
        """
        session = MagicMock()
        response = MagicMock(text=html, apparent_encoding="utf-8")
        session.get.return_value = response

        rules = get_kitei.fetch_rule_list(session)

        assert rules == [
            ("規程その一", get_kitei.urljoin(get_kitei.LIST_URL, "rule1.html")),
            ("規程その二", get_kitei.urljoin(get_kitei.LIST_URL, "rule2.html")),
        ]
        session.get.assert_called_once_with(
            get_kitei.LIST_URL, headers=get_kitei.HEADERS
        )

    def test_skips_entries_without_href(self):
        html = '<div class="rule"><a>リンク無し</a></div>'
        session = MagicMock()
        session.get.return_value = MagicMock(text=html, apparent_encoding="utf-8")

        assert get_kitei.fetch_rule_list(session) == []

    def test_skips_entries_without_link_tag(self):
        html = '<div class="rule">リンクタグ無し</div>'
        session = MagicMock()
        session.get.return_value = MagicMock(text=html, apparent_encoding="utf-8")

        assert get_kitei.fetch_rule_list(session) == []

    def test_raises_for_http_error(self):
        session = MagicMock()
        response = MagicMock()
        response.raise_for_status.side_effect = get_kitei.requests.HTTPError("500")
        session.get.return_value = response

        with pytest.raises(get_kitei.requests.HTTPError):
            get_kitei.fetch_rule_list(session)


class TestDownloadRule:
    def test_saves_html_to_output_dir(self, tmp_path, monkeypatch):
        monkeypatch.setattr(get_kitei, "OUTPUT_DIR", tmp_path)
        session = MagicMock()
        session.get.return_value = MagicMock(
            text="<html>本文</html>", apparent_encoding="utf-8"
        )

        get_kitei.download_rule(session, "○テスト規程", "https://example.com/rule.html")

        output_file = tmp_path / "テスト規程.html"
        assert output_file.read_text(encoding="utf-8") == "<html>本文</html>"
        session.get.assert_called_once_with(
            "https://example.com/rule.html", headers=get_kitei.HEADERS
        )

    def test_raises_for_http_error(self, tmp_path, monkeypatch):
        monkeypatch.setattr(get_kitei, "OUTPUT_DIR", tmp_path)
        session = MagicMock()
        response = MagicMock()
        response.raise_for_status.side_effect = get_kitei.requests.HTTPError("404")
        session.get.return_value = response

        with pytest.raises(get_kitei.requests.HTTPError):
            get_kitei.download_rule(session, "規程", "https://example.com/rule.html")

        assert list(tmp_path.iterdir()) == []


class TestMain:
    def test_fetches_and_downloads_without_real_network(self, tmp_path, monkeypatch):
        monkeypatch.setattr(get_kitei, "OUTPUT_DIR", tmp_path)
        monkeypatch.setattr(get_kitei.time, "sleep", lambda *_args: None)

        fake_rules = [
            ("規程A", "https://example.com/a.html"),
            ("規程B", "https://example.com/b.html"),
        ]

        with (
            patch.object(
                get_kitei, "fetch_rule_list", return_value=fake_rules
            ) as mock_fetch,
            patch.object(get_kitei, "download_rule") as mock_download,
            patch.object(get_kitei.requests, "Session") as mock_session_cls,
        ):
            mock_session = MagicMock()
            mock_session_cls.return_value.__enter__.return_value = mock_session

            get_kitei.main()

        mock_fetch.assert_called_once_with(mock_session)
        assert mock_download.call_args_list == [
            ((mock_session, "規程A", "https://example.com/a.html"),),
            ((mock_session, "規程B", "https://example.com/b.html"),),
        ]
        assert tmp_path.exists()
