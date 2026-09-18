"""Black と Prettier をまとめて実行する。

`poetry run formatters` で呼び出される。Pythonファイル(scripts/)はBlackで、
それ以外の整形対象ファイルはPrettierで整形する（除外設定は .prettierignore を参照）。
Prettierの実行には事前に `npm install` が必要。
"""

import subprocess
import sys

PYTHON_TARGETS = ["scripts", "tests"]


def run(command: list[str]) -> int:
    print(f"$ {' '.join(command)}")
    return subprocess.call(command)


def main() -> None:
    black_result = run(["black", *PYTHON_TARGETS])
    prettier_result = run(["npx", "prettier", "--write", "."])
    sys.exit(black_result or prettier_result)


if __name__ == "__main__":
    main()
