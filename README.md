# 【テスト環境】規程管理

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
poetry run convert2markdown

# 1件だけ変換したい場合はファイルを指定する
poetry run convert2markdown html/<対象ファイル>.html
```

### 旧環境（pip + venv）からの移行

以前は `python -m venv .venv` と `pip install -r requirements.txt` で環境を構築していたが、
現在は Poetry に一本化した。`requirements.txt` は削除済みのため、既存の `.venv/` を削除し、
上記の `poetry install` で環境を再構築すること。
