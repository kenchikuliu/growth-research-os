---
name: demand-validation-os
description: Score and diagnose SEO opportunities with a staged evidence workflow. Use when Codex needs to validate a new keyword, new demand, or new niche; decide whether to ship a single page, a page cluster, or a new site; explain why a leaderboard site is growing; or combine gefei, chuhai, Google Trends, Similarweb, and Semrush into one decision output.
---

# Demand Validation OS

Use this skill as the workflow wrapper for two recurring SEO research jobs:

1. `榜单归因`
   Explain why a site is growing and what part is actually reusable.
2. `新词 / 新需求验证`
   Judge whether a term or demand is real, searchable, winnable, expandable, and worth building.

This is not a generic SEO brainstorming skill. It is a decision system with fixed stages, scorecards, hard gates, and standardized outputs.

## Quick Start

Pick one mode first.

- Use `榜单归因` when the input is a site, leaderboard entry, growth list, or competitor domain.
- Use `新词 / 新需求验证` when the input is a keyword, phrase, Reddit/community demand cluster, or niche idea.

Then follow this order:

1. Gather evidence from the required sources.
2. Normalize the evidence into page-level opportunities.
3. Score the case with the appropriate scorecard.
4. Apply hard gates before trusting the total score.
5. Output a decision, why it is not more aggressive, and the next step.

## Required Inputs

Collect as many as available. Do not block if one tool is unavailable; state the missing evidence explicitly.

### For `榜单归因`

- target site or leaderboard entry
- time window
- Similarweb landing-page or click-change evidence when available
- Semrush top pages / organic positions evidence when available
- Google Trends evidence for the main terms when relevant

### For `新词 / 新需求验证`

- keyword, phrase, or demand statement
- Reddit/community evidence or equivalent user-pain evidence
- Similarweb landing-page evidence when available
- Semrush top pages / organic positions evidence when available
- Google Trends evidence

## Workflow

### Mode A: `榜单归因`

Answer three questions in order:

1. Which pages actually moved
2. Which terms or page types drove the movement
3. Which part is reusable for us

Run this sequence:

1. Identify the time window.
2. Pull the main growth pages.
3. Classify page types.
4. Pull the main growth terms.
5. Check whether growth matches trend or event windows.
6. Score `Attribution Confidence` and `Replication Potential`.
7. Output the attribution summary with reusable and non-reusable parts separated.

Use the rules in [references/scorecards.md](references/scorecards.md) and the wording patterns in [references/output-templates.md](references/output-templates.md).

### Mode B: `新词 / 新需求验证`

Answer five questions in order:

1. Is this a real demand
2. Is it search-carried or just community noise
3. Is the page type clear
4. Can it expand into a cluster
5. Should we stop, watch, ship one page, ship a cluster, or build a site

Run this sequence:

1. Extract the user demand, not just the keyword.
2. Judge the likely page type from SERP and intent.
3. Check whether Similarweb shows real landing-page clicks.
4. Check whether Semrush can decompose the opportunity into stable pages and terms.
5. Check Trends for stability, geography, and wording migration.
6. Score the case.
7. Apply hard gates.
8. Output the recommended action and first batch of pages.

## Evidence Rules

Always separate:

- `facts from tools`
- `inferences from rules`
- `final recommendation`

Do not say “worth doing” unless you can point to a chain like:

`user pain -> stable search expression -> page-level proof -> page type -> monetization path`

Do not rely on total traffic alone.
Do not rely on search volume alone.
Do not hand over a keyword list without a page list.

## Tool Roles

Use each source for a narrow job:

- `gefei`
  Provide judgment rules such as “用户要什么页面就做什么页面” and “不要只交关键词列表”.
- `chuhai`
  Provide the practical operating path for Similarweb landing pages, Semrush top pages, and Trends usage.
- `Google Trends`
  Judge stability, short spike vs durable demand, geography, and wording migration.
- `Similarweb`
  Look for already-validated clicks, especially landing pages and new-click changes.
- `Semrush`
  Map pages back to terms, page clusters, competitive cut-ins, and supporting domain signals.

Read [references/data-sources.md](references/data-sources.md) before running if you need the exact responsibility split.

## Scorecards

Use `scripts/scorecard.py` whenever you already have sub-scores and need deterministic totals and thresholds.

Supported modes:

- `attribution`
- `demand`

Example:

```bash
python3 scripts/scorecard.py \
  --mode demand \
  --scores demand_reality=4 search_carry=4 trend_stability=3 serp_entry=4 \
           page_intent_fit=5 clusterability=4 monetization=3 execution_fit=4
```

If you need the weights, hard gates, and action thresholds, read [references/scorecards.md](references/scorecards.md).

## Output Format

Prefer this structure.

### For `榜单归因`

1. `Core conclusion`
2. `Main growth pages`
3. `Main growth terms`
4. `Likely growth action`
5. `Reusable part`
6. `Do not copy`
7. `Confidence and gaps`

### For `新词 / 新需求验证`

1. `Core conclusion`
2. `Demand reality`
3. `Search proof`
4. `Trend pattern`
5. `Page-type recommendation`
6. `Recommended action`
7. `First batch of pages`
8. `Main uncertainty`

If useful, generate a starter JSON report with:

```bash
python3 scripts/render_report.py --mode demand
```

The templates are in [references/output-templates.md](references/output-templates.md).

## Reading Order

Do not load everything by default.

- Read [references/data-sources.md](references/data-sources.md) when you need tool-role boundaries.
- Read [references/scorecards.md](references/scorecards.md) when you need weights, gates, or thresholds.
- Read [references/output-templates.md](references/output-templates.md) when writing the final diagnosis.
