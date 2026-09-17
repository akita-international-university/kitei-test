"""`poetry run formatters` によるコード整形と pytest によるテストをまとめて実行する。

`poetry run tests` で呼び出される。formattersの結果に関わらずpytestも実行し、
いずれかが失敗した場合は全体を非ゼロ終了させる。pytestはカバレッジレポート
(pyproject.tomlの[tool.pytest.ini_options]で設定)を併せて表示する。
"""

import subprocess
import sys


def run(command: list[str]) -> int:
    print(f"$ {' '.join(command)}")
    return subprocess.call(command)


def main() -> None:
    formatters_result = run(["poetry", "run", "formatters"])
    pytest_result = run(["pytest"])
    sys.exit(formatters_result or pytest_result)


if __name__ == "__main__":
    main()
