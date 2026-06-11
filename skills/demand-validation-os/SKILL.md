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

When you need script-generated evidence from 3ue-backed accounts, use:

- `scripts/capture_semrush.py`
- `scripts/capture_similarweb.py`
- `scripts/capture_api.py`
- `scripts/capture_bundle.py`

These scripts now:

- keep the full login flow inside the authenticated 3ue dashboard chain
- emit structured JSON instead of raw screenshots only
- auto-detect 3ue daily-limit pages
- rotate to another configured 3ue node when the current node is exhausted

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

When the inferred page type is `对比页`, `alternative`, `vs`, or `comparison`, the first-batch page output must include:

- one explicit hero CTA
- a `page_blueprint` block
- a comparison-table requirement
- a concrete `适合谁` section rule

Use [references/output-templates.md](references/output-templates.md) for the exact comparison-page structure.
Then use `scripts/page_artifacts.py` or the built-in workflow `artifacts.page_artifacts` output to turn that blueprint into page-level copy and JSON.

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

For repeatable collection, prefer the capture scripts over ad-hoc browser clicking whenever you need data artifacts that another agent or step can consume.

Read [references/data-sources.md](references/data-sources.md) before running if you need the exact responsibility split.

## Automated Capture

This skill now includes script-level capture for the 3ue-backed Similarweb and Semrush accounts.

Read [references/capture-schema.md](references/capture-schema.md) before using the capture scripts so you know what JSON is guaranteed and what is best-effort.

### Shared Browser Executor

`scripts/browser_capture.py` provides:

- automated 3ue login with DOM injection instead of brittle typing
- dashboard home recovery when 3ue falls back to the login screen mid-session
- dashboard card opening for Similarweb and Semrush
- network capture parsing
- shared session helpers for `browse`

Credentials are read from `THREEUE_USERNAME` and `THREEUE_PASSWORD`, or passed via `--username` / `--password`.

### Semrush Capture

Use when you need a structured domain evidence pack:

```bash
export THREEUE_USERNAME='...'
export THREEUE_PASSWORD='...'
python3 scripts/capture_semrush.py \
  --query crazygames.com \
  --output /tmp/semrush-crazygames.json
```

Current behavior:

- logs into `dash.3ue.com`
- opens an authenticated Semrush route
- captures network payloads
- extracts `dpa/rpc` responses into structured JSON
- retries the overview route once if the first pass returns no RPC payloads
- uses a dedicated browser session so Similarweb and Semrush captures do not pollute each other
- closes the automation browser session automatically unless `--keep-session` is passed

Primary sections:

- `domain_overview`
- `organic_competitors`
- `top_organic_keywords`
- `top_pages`
- `top_topics`
- `ai_overview`
- `backlink_overview`

### Similarweb Capture

Use when you need a structured Similarweb evidence pack:

```bash
export THREEUE_USERNAME='...'
export THREEUE_PASSWORD='...'
python3 scripts/capture_similarweb.py \
  --query crazygames.com \
  --output /tmp/similarweb-crazygames.json
```

Current behavior:

- logs into `dash.3ue.com`
- opens Similarweb only through the 3ue card
- waits for the authenticated Similarweb shell to become DOM-ready, with fallback markers when the shell half-loads
- captures account-state and target-domain suggestion evidence
- extracts identity, startup settings, autocomplete suggestions, quick-search report candidates, activation-home priority alerts, and `网站表现` / website-performance report blocks
- uses a dedicated browser session so Similarweb and Semrush captures do not pollute each other
- closes the automation browser session automatically unless `--keep-session` is passed

Current limitation:

- `网站表现` is now the stable Similarweb baseline capture
- landing-pages and some deeper report families are still more session-sensitive than Semrush
- if a deeper report cannot be reached, the script still emits useful `account_state` and route evidence instead of pretending a report was reached

Deeper capture layers now exposed in JSON:

- `website_content_top_pages`
- `keyword_research`
- `landing_pages_research`

These layers group:

- `自然搜索 / 付费搜索` route candidates
- quick-search keyword seeds
- Similarweb top non-brand keyword rows
- paid landing page rows
- website-content folders and 热门页面 / PopularPages attempts
- priority alerts for `Organic keywords` and `Organic landing pages`

### Unified Capture API

Use when you want one stable entrypoint that later scale / skill code can call directly.

```bash
export THREEUE_USERNAME='...'
export THREEUE_PASSWORD='...'
python3 scripts/capture_api.py \
  --query crazygames.com \
  --output /tmp/crazygames-capture-api.json

python3 scripts/capture_service.py \
  --host 127.0.0.1 \
  --port 8765

python3 scripts/workflow_service.py \
  --host 127.0.0.1 \
  --port 8766

python3 scripts/run_scale.py \
  --mode demand \
  --query "ahrefs alternative" \
  --domain ahrefs.com \
  --brand-name "Your Brand" \
  --brand-url "https://example.com" \
  --primary-cta-url "https://example.com/signup" \
  --table-output /tmp/scale-results.xlsx
```

Current behavior:

- is the preferred API/CLI for downstream scale or skill calls
- enforces `single_device`, `single_browser`, `single_active_page`, `serial`
- collapses non-active tabs after 3ue opens a tool page so one live browser stays on one page
- returns both per-attempt telemetry and per-tool structured JSON under one envelope
- adds a top-level `normalized` block with one shared cross-tool schema for traffic, pages, keywords, landing pages, clusters, competitors, geo signals, and per-tool readiness

Service behavior:

- exposes the same capture plan over local HTTP/JSON
- keeps the same serial single-browser policy as the CLI
- rejects concurrent capture requests with HTTP `409`

Workflow service behavior:

- exposes the higher-level `新词验证 / 榜单归因` output over local HTTP/JSON
- returns the final workflow decision, `playbook`, and page-artifact JSON
- can accept live 3ue credentials, `bundle_input`, or an in-memory `bundle_payload`
- keeps one workflow request at a time so the capture layer stays serial

Thin scale behavior:

- `/scale` returns only the compact `scale_output`
- `/scale/playbook` returns `scale_output` plus `playbook`
- `/scale/page-artifacts` returns `scale_output` plus `page_artifacts`
- `scripts/run_scale.py` does the same locally, and also supports batch jobs via `--jobs-input`
- `scripts/run_scale.py` accepts `json / csv / tsv / xlsx` batch inputs and can export flattened rows to `json / csv / tsv / xlsx` with `--table-output`
- leaderboard-style filters are shared across CLI and HTTP scale calls:
  - `min_score`
  - `allowed_actions`
  - `require_tools_ready`
  - `sort_by`
  - `ascending`
  - `top`

Example:

```bash
curl -s http://127.0.0.1:8765/capture \
  -H 'Content-Type: application/json' \
  -d '{
    "query": "crazygames.com",
    "tools": ["semrush", "similarweb"],
    "username": "'"$THREEUE_USERNAME"'",
    "password": "'"$THREEUE_PASSWORD"'",
    "request_id": "svc-1"
  }'

curl -s http://127.0.0.1:8766/workflow/page-artifacts \
  -H 'Content-Type: application/json' \
  -d '{
    "mode": "demand",
    "query": "ahrefs alternative",
    "domain": "ahrefs.com",
    "username": "'"$THREEUE_USERNAME"'",
    "password": "'"$THREEUE_PASSWORD"'",
    "brand_name": "Your Brand",
    "brand_url": "https://example.com",
    "primary_cta_url": "https://example.com/signup",
    "request_id": "wf-1"
  }'

curl -s http://127.0.0.1:8766/workflow/playbook \
  -H 'Content-Type: application/json' \
  -d '{
    "mode": "demand",
    "query": "ahrefs alternative",
    "domain": "ahrefs.com",
    "username": "'"$THREEUE_USERNAME"'",
    "password": "'"$THREEUE_PASSWORD"'",
    "brand_name": "Your Brand",
    "brand_url": "https://example.com",
    "primary_cta_url": "https://example.com/signup"
  }'

curl -s http://127.0.0.1:8766/scale/page-artifacts \
  -H 'Content-Type: application/json' \
  -d '{
    "mode": "demand",
    "query": "ahrefs alternative",
    "domain": "ahrefs.com",
    "username": "'"$THREEUE_USERNAME"'",
    "password": "'"$THREEUE_PASSWORD"'",
    "brand_name": "Your Brand",
    "brand_url": "https://example.com",
    "primary_cta_url": "https://example.com/signup"
  }'

curl -s http://127.0.0.1:8766/scale/playbook \
  -H 'Content-Type: application/json' \
  -d '{
    "mode": "attribution",
    "query": "crazygames.com",
    "domain": "crazygames.com",
    "username": "'"$THREEUE_USERNAME"'",
    "password": "'"$THREEUE_PASSWORD"'"
  }'
```

### Serial Bundle Capture

Use when you want both tools in one run and do not want parallel browser sessions interfering with each other:

```bash
export THREEUE_USERNAME='...'
export THREEUE_PASSWORD='...'
python3 scripts/capture_bundle.py \
  --query crazygames.com \
  --output /tmp/crazygames-bundle.json
```

Current behavior:

- runs `semrush` then `similarweb` serially by default
- records per-attempt runtime, quality, and failure metadata
- retries `similarweb` once by default if the first attempt does not reach the core report layer
- returns a combined JSON bundle under `results.semrush.data` and `results.similarweb.data`
- is a backward-compatible wrapper around `capture_api.py`

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

## One-Click Workflow

If the user wants the whole stack in one run, use:

```bash
export THREEUE_USERNAME='...'
export THREEUE_PASSWORD='...'

python3 scripts/run_demand_workflow.py \
  --mode demand \
  --query "ai image generator" \
  --domain janitorai.com \
  --output /tmp/ai-image-generator-workflow.json
```

This runner:

- calls `gefei` for judgment rules
- calls `chuhai` for Similarweb / Semrush / Trends operating paths
- captures Google Trends into structured JSON
- runs 3ue-backed `capture_bundle.py` when a domain is available
- computes the scorecard
- emits a guided `web.cafe`-style staged flow in the final JSON
- emits a top-level `playbook` for direct execution handoff
- emits `artifacts.page_artifacts` so comparison / alternative pages can move from blueprint to publishable page JSON
- prefers the `normalized` capture layer when that layer is present, so later scale/service code can pass a stable bundle instead of raw Semrush / Similarweb payloads only

If you only need the page-output layer from an existing workflow JSON:

```bash
python3 scripts/page_artifacts.py \
  --workflow-input /tmp/ai-image-generator-workflow.json \
  --brand-name "Your Brand" \
  --brand-url "https://example.com" \
  --primary-cta-url "https://example.com/signup" \
  --output /tmp/ai-image-generator-page-artifacts.json
```

Current artifact behavior:

- keeps the existing `page_json`
- adds `frontend_payload` per page for direct renderer consumption
- adds top-level `frontend_protocol` so frontend code can understand available page template types without guessing
- `frontend_payload` now also includes explicit `blocks`, each with `id`, `type`, `required`, and `data`
- `frontend_protocol` now publishes `block_types` so a renderer can validate available block families before render time

## Google Trends Script

When you need structured Trends evidence outside the full workflow:

```bash
python3 scripts/google_trends.py \
  --query crazygames \
  --geo US \
  --output /tmp/crazygames-trends.json
```

Current behavior:

- tries official Google Trends first
- falls back to a same-origin browser request when Google returns HTTP 429 for widget data
- can fall back again to configured `RapidAPI` or `DataForSEO` Google Trends providers when the official source is unavailable
- keeps a normalized `30d / 90d / 12m / 5y` output shape with trend-shape summaries and related rising queries
- records `provider_attempts` so downstream steps can see whether the data came from official Google, RapidAPI, DataForSEO, or a degraded path

## Guided Flow Layer

When the user wants a `web.cafe`-style staged diagnosis instead of a flat scorecard, the workflow JSON already includes `guided_flow`.

You can also render it separately:

```bash
python3 scripts/guided_flow.py \
  --input /tmp/ai-image-generator-workflow.json \
  --output /tmp/ai-image-generator-guided.json
```

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

If one of the first pages is a `对比页`, include at least:

- `hero_primary_cta`
- `page_blueprint.title_formula`
- `page_blueprint.recommended_h2`
- `page_blueprint.comparison_table_dimensions`
- `page_blueprint.fit_section_rule`

If useful, generate a starter JSON report with:

```bash
python3 scripts/render_report.py --mode demand
```

The templates are in [references/output-templates.md](references/output-templates.md).

## Reading Order

Do not load everything by default.

- Read [references/data-sources.md](references/data-sources.md) when you need tool-role boundaries.
- Read [references/capture-schema.md](references/capture-schema.md) when you need the exact JSON fields and current capture guarantees.
- Read [references/scorecards.md](references/scorecards.md) when you need weights, gates, or thresholds.
- Read [references/output-templates.md](references/output-templates.md) when writing the final diagnosis.
