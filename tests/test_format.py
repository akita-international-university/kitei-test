from unittest.mock import patch

import pytest

from scripts import format as format_script


class TestRun:
    def test_returns_subprocess_call_result(self):
        with patch.object(
            format_script.subprocess, "call", return_value=0
        ) as mock_call:
            result = format_script.run(["black", "scripts"])

        assert result == 0
        mock_call.assert_called_once_with(["black", "scripts"])

    def test_propagates_nonzero_result(self):
        with patch.object(format_script.subprocess, "call", return_value=1):
            assert format_script.run(["black", "scripts"]) == 1


class TestMain:
    def test_exits_zero_when_both_succeed(self):
        with (
            patch.object(format_script, "run", side_effect=[0, 0]) as mock_run,
            pytest.raises(SystemExit) as exc_info,
        ):
            format_script.main()

        assert exc_info.value.code == 0
        assert mock_run.call_args_list[0].args[0] == ["black", "scripts", "tests"]
        assert mock_run.call_args_list[1].args[0] == ["npx", "prettier", "--write", "."]

    def test_exits_nonzero_when_black_fails(self):
        with (
            patch.object(format_script, "run", side_effect=[1, 0]),
            pytest.raises(SystemExit) as exc_info,
        ):
            format_script.main()

        assert exc_info.value.code == 1

    def test_exits_nonzero_when_prettier_fails(self):
        with (
            patch.object(format_script, "run", side_effect=[0, 1]),
            pytest.raises(SystemExit) as exc_info,
        ):
            format_script.main()

        assert exc_info.value.code == 1
