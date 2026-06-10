# Output Templates

## Principle

Write short, decision-first outputs. Separate:

1. facts
2. inference
3. recommendation

## `榜单归因`

### Structure

1. Core conclusion
2. Main growth pages
3. Main growth terms
4. Likely growth action
5. Reusable part
6. Do not copy
7. Confidence and gaps

### Strong conclusion

`This site is not rising evenly. Growth is concentrated in {page type} during {time window}. Similarweb shows {landing-page or click signal}, Semrush shows {top-page or term signal}, and Trends shows {trend pattern}. The most likely play is {new-term capture / page-cluster expansion / tool-led capture / event-led capture}.`

### Medium conclusion

`The site is clearly moving, but the best-supported explanation is only partial. We can see {two strong signals}, while {one missing signal} is still weak. Treat this as a monitored hypothesis, not a closed attribution case.`

### Reuse recommendation

`The reusable part is not “the site is strong”; it is the way {page type} is used to absorb {term cluster or user job}. If we copy anything, copy the page shape and cut narrower.`

## `新词 / 新需求验证`

### Structure

1. Core conclusion
2. Demand reality
3. Search proof
4. Trend pattern
5. Page-type recommendation
6. Recommended action
7. First batch of pages
8. Main uncertainty

### Stop

`This looks more like discussion heat than stable search demand. The demand statement is noisy, the search expression is unstable, and the page shape is not yet reliable enough to justify build time.`

### Watch

`The demand may be real, but the search expression is still forming. Monitor Trends, new landing pages, and SERP page shapes before committing to a build.`

### Ship one page

`The demand is real and the first-page shape is clear, but the cluster is not yet strong enough to justify a site. Start with one high-intent {tool page / scenario page / comparison page}.`

### Ship a cluster

`This should not be treated as a single keyword. The opportunity is better expressed as a small page system: one pillar page plus scenario pages, comparison pages, and a few FAQ/template pages.`

### Build a site

`This is not just one page opportunity. It already passes the tests for real demand, stable search carrying, clear page shape, cluster expansion, and monetization fit.`

## First Batch Of Pages

Always output pages, not only terms.

Minimum fields:

- `working_title`
- `page_type`
- `primary_intent`
- `primary_keyword`
- `evidence_basis`
- `content_or_tool_structure`
- `internal_links_to`
- `monetization_path`

Recommended fields when available:

- `hero_primary_cta`
- `page_blueprint`

## `对比页 / Alternative / Versus` Blueprint

Use this blueprint whenever the query intent is `alternative`, `vs`, `versus`, `compare`, `comparison`, `替代`, or `对比`.

### Goal

Do not write a soft overview. Write a conversion page that can rank for competitor-brand queries and answer the switch question directly.

The page must answer three questions fast:

1. 为什么你是这个竞品的替代方案
2. 你比它更适合哪类用户
3. 用户现在可以马上怎么开始用你

### Required hero

The first screen must:

- explain the replacement reason in one sentence
- show one explicit primary CTA
- remove ambiguity about the next step

Allowed CTA patterns:

- `预约 Demo`
- `免费试用`
- `马上注册`
- `打电话咨询`
- `查看路线`

Do not hide the CTA below the fold.
Do not make the user infer the next step from navigation.

### Recommended title and heading structure

- H1: `{竞品名} Alternative：为什么很多用户选择你的品牌`
- H2: `{竞品名} vs 你的品牌：Comparison`

This heading pattern is intentionally search-friendly for Google, AI Overview, ChatGPT, and Perplexity style comparison retrieval.

### Required sections

1. 标题
2. 首屏一句话替代理由 + 明确 CTA
3. 适合谁
4. 对比表

### `适合谁` section rule

Do not say “适合所有人”.
State exactly who should switch:

- team type
- business type
- workflow maturity
- current bottleneck

Good examples:

- `如果你是 SaaS 团队，需要更快搭建可转化的 comparison 页和替代页，这个方案更适合你。`
- `如果你是跨境卖家，已经知道竞品词有流量，但不会把 Similarweb 和 Semrush 的证据转成页面，这个方案更适合你。`

### Required comparison table

The page must include a comparison table.

Recommended columns:

- `价格`
- `功能`
- `上手难度`
- `支持方式`
- `适用场景`
- `迁移成本`

### SEO / AI search notes

- Prefer `alternative / comparison / versus` wording when it matches intent.
- Keep the comparison H2 and table explicit so structured extraction is easier.
- If the competitor has weak SEO coverage, this page can sometimes outrank or intercept its brand query.
