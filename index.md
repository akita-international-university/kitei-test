---
title: ホーム
layout: default
---

# {{ site.title }}

> ここに掲載されている内容は、GitHubを用いた規程管理の可能性を検証する作業の一環で作成されたものです。
> 正規の規程については [国際教養大学規程集](https://www4.kitei-kanri.jp/unc/aiu/doc/gakugai/index.html) をご覧ください。

全{{ site.rules | size }}件を、元の規程集の体系（各規程ページのパンくずリストと同じ分類）ごとに掲載している。
{: .rule-total }

{%- comment -%}
規程は front matter の category ごとにグループ化して表示する。

- グループ化のキーは category を " > " で連結した文字列とし、_includes/breadcrumb.html の
  表示と同じ区切りになるようにしている。現時点のcategoryはすべて1階層だが、将来多階層に
  なっても上位階層から順に並び、キーがそのまま見出しになる。
- カテゴリ名は「01 定款・学則」のように連番で始まるため、name でソートすれば元の規程集の
  体系順と一致する。group_by_exp の結果は順序が保証されないので明示的にソートする。
- category が空の規程はキーが空文字列となり、ソートすると先頭に来てしまうため、
  concat で末尾へ移し、「未分類」として最後にまとめる。
- 各カテゴリ内は規程名（title）順とする。規程番号（rule_number）は全角数字で、
  一部の規程には付与されていないため、並び順のキーには使わない。
{%- endcomment -%}
{%- assign rules_sorted = site.rules | sort: "title" -%}
{%- assign category_groups = rules_sorted | group_by_exp: "rule", "rule.category | join: ' > '" | sort: "name" -%}
{%- assign categorized_groups = category_groups | where_exp: "group", "group.name != ''" -%}
{%- assign uncategorized_groups = category_groups | where_exp: "group", "group.name == ''" -%}
{%- assign ordered_groups = categorized_groups | concat: uncategorized_groups -%}
{% for group in ordered_groups %}
{%- if group.name == "" -%}{%- assign group_label = "未分類" -%}{%- else -%}{%- assign group_label = group.name -%}{%- endif %}
## {{ group_label }} <span class="rule-category-count">{{ group.items | size }}件</span>
{: .rule-category id="category-{{ group_label | slugify: 'raw' }}" }

{% for rule in group.items -%}
- [{{ rule.title }}]({{ rule.url | relative_url }})
{% endfor -%}
{: .rule-list }
{% endfor %}
