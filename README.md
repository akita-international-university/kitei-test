# 【テスト環境】国際教養大学規程一覧

GitHubを用いた規程管理の可能性を検討するための試験環境。

> [!IMPORTANT]
> ここに掲載されている内容は、GitHubを用いた規程管理の可能性を検証する作業の一環で作成されたものです。  
> 正規の規程については [国際教養大学規程集](https://www4.kitei-kanri.jp/unc/aiu/doc/gakugai/index.html) をご覧ください。

## 開発環境のセットアップ

本リポジトリのPythonスクリプト（`scripts/`）は [Poetry](https://python-poetry.org/) で依存関係を管理する。

```bash
poetry install
```

セットアップ後、以下のコマンドで各スクリプトを実行できる。

```bash
# 現行の規程管理システムからHTML一式を取得し、html/ 以下に保存する
poetry run getkitei

# html/*.html を _rules/ 以下のMarkdownへ変換する（引数を省略すると全件変換）
# 変換後、生成したファイルにPrettierを自動適用する（事前に npm install が必要）
poetry run convert2markdown

# 1件だけ変換したい場合はファイルを指定する
poetry run convert2markdown html/<対象ファイル>.html

# html/*.html から様式等の添付ファイルへのリンクを抽出し、到達性を検証する
# （現行システムへ142回アクセスするため、0.5秒間隔で実行される）
poetry run checkattachments > docs/investigations/attachment-links.md

# 外部アクセスを行わず、リンクの抽出のみを行う
poetry run checkattachments --offline
```

### 旧環境（pip + venv）からの移行

以前は `python -m venv .venv` と `pip install -r requirements.txt` で環境を構築していたが、
現在は Poetry に一本化した。`requirements.txt` は削除済みのため、既存の `.venv/` を削除し、
上記の `poetry install` で環境を再構築すること。

## コードフォーマット

Pythonファイル（`scripts/`）は [Black](https://black.readthedocs.io/)、それ以外のファイルは原則
[Prettier](https://prettier.io/) で整形する。ロックファイルや `LICENSE`、`CODEOWNERS`、`html/` 以下の生HTML、
Jekyll/Liquidテンプレート（`_layouts/`, `_includes/`, `index.md`）は整形対象外（詳細は
[.prettierignore](.prettierignore) を参照）。`_rules/` 以下の生成Markdownは整形対象であり、
`poetry run convert2markdown` の実行時にも自動的にPrettierが適用される。

初回のみ、Prettier用の依存関係をインストールする。

```bash
npm install
```

以下のコマンドでBlack/Prettierをまとめて実行できる。

```bash
poetry run formatters
```

## テスト

`scripts/` 配下の各スクリプトは [pytest](https://docs.pytest.org/) でユニットテストする。テストは
`tests/` 以下に `test_*.py` として配置する。`get_kitei.py` のような外部HTTP通信を伴う処理は
`unittest.mock` でモック化し、テスト実行時に実際の通信が発生しないようにしている。

以下のコマンドで `poetry run formatters`（Black/Prettierによる自動整形）と pytest をまとめて実行できる。
どちらか一方でも失敗すればコマンド全体が非ゼロ終了する。pytestの実行結果には各ファイルの
カバレッジレポート（未カバー行を含む）もあわせて表示される。

```bash
poetry run tests
```

> [!IMPORTANT]
> **コミット前には必ず `poetry run tests` を実行し、成功することを確認すること。**
> 現時点ではgit hookやCIによる自動強制は行っていないため、各自の実行が前提となる。
