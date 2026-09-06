---
title: ホーム
layout: default
---

# {{ site.title }}

> ここに掲載されている内容は、GitHubを用いた規程管理の可能性を検証する作業の一環で作成されたものです。
> 正規の規程については [国際教養大学規程集](https://www4.kitei-kanri.jp/unc/aiu/doc/gakugai/index.html) をご覧ください。

## PoC対象規程（5件）

{% for rule in site.rules %}
- [{{ rule.title }}]({{ rule.url | relative_url }})
{% endfor %}
