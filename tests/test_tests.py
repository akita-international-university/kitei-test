from unittest.mock import patch

import pytest

from scripts import tests as tests_script

FORMATTERS_COMMAND = ["poetry", "run", "formatters"]
PYTEST_COMMAND = ["pytest"]


class TestRun:
    def test_returns_subprocess_call_result(self):
        with patch.object(tests_script.subprocess, "call", return_value=0) as mock_call:
            result = tests_script.run(PYTEST_COMMAND)

        assert result == 0
        mock_call.assert_called_once_with(PYTEST_COMMAND)

    def test_propagates_nonzero_result(self):
        with patch.object(tests_script.subprocess, "call", return_value=1):
            assert tests_script.run(PYTEST_COMMAND) == 1


class TestMain:
    def test_runs_formatters_before_pytest_and_exits_zero(self):
        with (
            patch.object(tests_script, "run", side_effect=[0, 0]) as mock_run,
            pytest.raises(SystemExit) as exc_info,
        ):
            tests_script.main()

        assert exc_info.value.code == 0
        assert mock_run.call_args_list[0].args[0] == FORMATTERS_COMMAND
        assert mock_run.call_args_list[1].args[0] == PYTEST_COMMAND

    def test_runs_pytest_even_when_formatters_fail(self):
        with (
            patch.object(tests_script, "run", side_effect=[1, 0]) as mock_run,
            pytest.raises(SystemExit) as exc_info,
        ):
            tests_script.main()

        assert exc_info.value.code == 1
        assert mock_run.call_args_list[1].args[0] == PYTEST_COMMAND

    def test_exits_nonzero_when_pytest_fails(self):
        with (
            patch.object(tests_script, "run", side_effect=[0, 1]),
            pytest.raises(SystemExit) as exc_info,
        ):
            tests_script.main()

        assert exc_info.value.code == 1

    def test_exits_nonzero_when_both_fail(self):
        with (
            patch.object(tests_script, "run", side_effect=[1, 1]),
            pytest.raises(SystemExit) as exc_info,
        ):
            tests_script.main()

        assert exc_info.value.code == 1
