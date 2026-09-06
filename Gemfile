source "https://rubygems.org"

# GitHub Pagesの旧来のビルド方式(github-pagesラッパーgem)は、依存先の
# jekyll-theme-primer等が自動的にデフォルトテーマとして選択されてしまい、
# Ruby 3.4系では同梱のSassコンバータ(sass 3.7系)との非互換でビルドが失敗する。
# GitHub Pagesは現在GitHub Actionsによるビルドが標準のため、最新のJekyllを
# 直接使用し、.github/workflows/pages.yml でビルド・デプロイする。
gem "jekyll", "~> 4.4"
gem "webrick"
