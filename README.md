# Growth Research OS

A 3-layer skill system for reconstructing viral propagation, diagnosing causality, and translating insights into product design.

## Why

Most "viral analysis" skips directly to conclusions. This system forces evidence first, explanation second, design third — preventing pattern-matching on fake breakouts.

## Skills

### `/propagation-workflow` — Main Entry Point

Runs all 3 steps in sequence. Start here.

```
/propagation-workflow
```

---

### `/demand-validation-os` — SEO Demand And Attribution Entry Point

Scores and diagnoses two SEO research jobs:

- `榜单归因`
- `新词 / 新需求验证`

Combines gefei, chuhai, Google Trends, Similarweb, and Semrush into one evidence-first output.

Output:

- scorecard + hard gates
- attribution or demand decision
- first batch of pages when applicable
- optional structured JSON capture from 3ue-backed Similarweb and Semrush sessions
- optional one-click workflow JSON that also includes gefei, chuhai, Google Trends, and a staged guided flow

Capture scripts:

```bash
export THREEUE_USERNAME='...'
export THREEUE_PASSWORD='...'

python3 skills/demand-validation-os/scripts/capture_semrush.py \
  --query crazygames.com \
  --max-node-rotations 2 \
  --output /tmp/semrush-crazygames.json

python3 skills/demand-validation-os/scripts/capture_similarweb.py \
  --query crazygames.com \
  --max-node-rotations 2 \
  --output /tmp/similarweb-crazygames.json

python3 skills/demand-validation-os/scripts/capture_bundle.py \
  --query crazygames.com \
  --max-node-rotations 2 \
  --output /tmp/crazygames-bundle.json

python3 skills/demand-validation-os/scripts/capture_api.py \
  --query crazygames.com \
  --max-node-rotations 2 \
  --output /tmp/crazygames-capture-api.json

python3 skills/demand-validation-os/scripts/capture_service.py \
  --host 127.0.0.1 \
  --port 8765

python3 skills/demand-validation-os/scripts/workflow_service.py \
  --host 127.0.0.1 \
  --port 8766

python3 skills/demand-validation-os/scripts/run_scale.py \
  --mode demand \
  --query "ahrefs alternative" \
  --domain ahrefs.com \
  --brand-name "Your Brand" \
  --brand-url "https://example.com" \
  --primary-cta-url "https://example.com/signup" \
  --table-output /tmp/scale-results.xlsx

python3 skills/demand-validation-os/scripts/run_scale.py \
  --jobs-input /tmp/scale-jobs.xlsx \
  --min-score 60 \
  --allowed-actions ship_cluster,ship_one_page \
  --require-tools-ready semrush,similarweb \
  --sort-by total_score \
  --top 20 \
  --table-output /tmp/scale-leaderboard.xlsx

python3 skills/demand-validation-os/scripts/google_trends.py \
  --query crazygames \
  --geo US \
  --output /tmp/crazygames-trends.json

python3 skills/demand-validation-os/scripts/run_demand_workflow.py \
  --mode demand \
  --query "ai image generator" \
  --domain janitorai.com \
  --output /tmp/ai-image-generator-workflow.json
```

Current state:

- `Semrush` capture is still the stronger structured source and emits overview, competitors, keywords, pages, trend, market, AI, and backlink sections.
- `Semrush` now retries the overview route once if the first pass returns no RPC payloads.
- `Semrush` and `Similarweb` now auto-detect 3ue daily-limit pages and can rotate to another configured node before retrying.
- `Similarweb` now survives more 3ue shell half-load cases and can still emit activation-home priority-alert signals even when deeper routes are fragile.
- `Similarweb` still has partial gaps for the deepest landing-pages style report automation, but it now emits structured `keyword_research` and `landing_pages_research` layers on top of `网站表现` / website-performance, `网站内容`, `搜索概况`, quick-search seeds, route candidates, and priority alerts.
- `capture_bundle.py` is the preferred way to run both tools together because it executes them serially and avoids cross-session interference from parallel browser-backed runs.
- `capture_api.py` is now the unified capture entrypoint for later scale / skill calls. Its default execution policy is `single_device + single_browser + single_active_page + serial`.
- `capture_bundle.py` remains as a backward-compatible wrapper, but new code should call `capture_api.py` or import `capture_api.run_capture_plan()`.
- `capture_api.py` now also emits a top-level `normalized` layer so downstream scale / skill code can read one stable cross-tool schema instead of stitching raw Similarweb / Semrush payloads manually.
- `capture_service.py` exposes the same capture plan over local HTTP/JSON with `GET /health`, `POST /capture`, and `POST /capture/tool`.
- `capture_service.py` keeps the same strict execution policy as the CLI: `single_device + single_browser + single_active_page + serial`, and rejects concurrent capture requests with HTTP `409`.
- `run_demand_workflow.py` now accepts a full prebuilt `bundle_payload`, not just a file path, so later scale or service code can hand normalized capture data directly into the scoring and artifact layers.
- `workflow_service.py` is the higher-level scale entrypoint. It returns final `新词验证 / 榜单归因` workflow output plus page-artifact JSON in one HTTP call.
- `workflow_scale.py` now holds the reusable thin `scale_output` projection so both CLI and HTTP callers get the same compact result shape.
- `run_scale.py` is the thin local CLI for one-off or batch jobs. It returns `scale_output` plus `page_artifacts`, and only includes full workflow JSON when explicitly requested.
- `run_scale.py` now supports `json / csv / tsv / xlsx` batch-job input and flattened `json / csv / tsv / xlsx` output, so leaderboard-style job lists can be run directly without pandas/openpyxl.
- `run_scale.py` and `workflow_service.py /scale*` now both support leaderboard-style filtering and ranking with `min_score`, `allowed_actions`, `require_tools_ready`, `sort_by`, `ascending`, and `top`.
- `page_artifacts.py` now prefers the `normalized` capture layer when counting proof, landing-page evidence, and page-cluster evidence, so page JSON generation no longer depends on raw tool-specific shapes alone.
- `page_artifacts.py` now also emits a stable `frontend_payload` per page plus a top-level `frontend_protocol` summary, so frontend rendering no longer has to infer layout sections from free-form copy.
- `frontend_payload` now also includes explicit `blocks` metadata with `id`, `type`, `required`, and `data`, while `frontend_protocol` publishes `block_types` so renderer code can validate layouts before rendering.
- `google_trends.py` now tries official Google Trends first, then can fall back to configured RapidAPI or DataForSEO providers, while keeping a normalized `30d / 90d / 12m / 5y` output shape and recording `provider_attempts`.
- `run_demand_workflow.py` is the one-click orchestrator that combines gefei, chuhai, Google Trends, Similarweb, Semrush, scorecard logic, and a staged guided-flow layer.
- `page_artifacts.py` plus `run_demand_workflow.py -> artifacts.page_artifacts` push the workflow one step further into publishable page JSON, especially for `alternative / comparison / versus` pages with direct-answer copy, CTA, fit-for blocks, and comparison-table structure.

HTTP example:

```bash
curl -s http://127.0.0.1:8765/health

curl -s http://127.0.0.1:8765/capture \
  -H 'Content-Type: application/json' \
  -d '{
    "query": "crazygames.com",
    "tools": ["semrush", "similarweb"],
    "username": "'"$THREEUE_USERNAME"'",
    "password": "'"$THREEUE_PASSWORD"'",
    "request_id": "demo-capture-1"
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
    "request_id": "demo-workflow-1"
  }'

curl -s http://127.0.0.1:8766/scale \
  -H 'Content-Type: application/json' \
  -d '{
    "mode": "attribution",
    "query": "crazygames.com",
    "domain": "crazygames.com",
    "username": "'"$THREEUE_USERNAME"'",
    "password": "'"$THREEUE_PASSWORD"'"
  }'

curl -s http://127.0.0.1:8766/scale/page-artifacts \
  -H 'Content-Type: application/json' \
  -d '{
    "jobs": [
      {"mode": "demand", "query": "ahrefs alternative", "domain": "ahrefs.com"},
      {"mode": "attribution", "query": "crazygames.com", "domain": "crazygames.com"}
    ],
    "bundle_payload": {"results": {}, "summary": {}, "normalized": {}},
    "min_score": 60,
    "allowed_actions": "ship_cluster,ship_one_page",
    "require_tools_ready": "semrush,similarweb",
    "sort_by": "total_score",
    "top": 5
  }'
```

```
/demand-validation-os
```

---

### `/demand-guided-simulator` — Web.cafe-Style Staged SEO Workflow

Turns the demand-validation evidence layer into a contradiction-first guided flow:

- guided path vs direct result
- one concept per step
- explicit hidden variable
- stage-based diagnosis for `新词 / 新需求验证` and `榜单归因`
- dedicated simulator wrapper with `simulator` / `guided` / `direct` / `step` views

Primary use:

- when a flat report is not enough
- when the user wants a simulator-like teaching flow
- when recommendations should be tied to discrete diagnostic stages

```
/demand-guided-simulator
```

Example:

```bash
python3 skills/demand-guided-simulator/scripts/demand_guided_simulator.py \
  --workflow-input /tmp/crazygames-attribution-deep.json \
  --view simulator
```

---

### Step 1: `propagation-evidence-collector`

Reconstruct HOW something spread using multi-source evidence.

Collects from: Google Trends · X (Twitter) · Reddit · YouTube · Google Search

Output: structured timeline (T0–T6) + exposure layers + signal consistency score

```
/propagation-evidence-collector
```

---

### Step 2: `viral-causality-analyzer`

Explain WHY it spread. Must consume evidence from Step 1.

Separates:
- **Click cause** — why users entered
- **Spread cause** — why users shared
- **Amplification cause** — what scaled it

Output: causal weights + viral type (burst / hybrid / durable) + final diagnosis

```
/viral-causality-analyzer
```

---

### Step 3: `propagation-design-translator`

Translate causality into actionable product design. Must consume Step 2 output.

Output: gap analysis + 3–5 concrete implementable ideas ranked by impact/effort

```
/propagation-design-translator
```

---

## Quality Gates

Each step has explicit pass criteria before the next step begins:

| Gate | Checks |
|------|--------|
| Step 1 → 2 | Timeline ≥ 4 nodes, ≥ 3 platforms checked, consistency scored |
| Step 2 → 3 | Click cause ≠ spread cause, causal weights sum to 100%, viral type assigned |
| Step 3 done | Each idea traces to a gap, non-transferable factors excluded, priority order given |

## Installation

Copy skill directories into your Claude Code skills folder:

```bash
cp -r skills/* ~/.claude/skills/
```

Then invoke with `/propagation-workflow`.

## Use Cases

- Competitor viral analysis before building a feature
- Demo redesign (why does their demo spread, mine doesn't?)
- Pre-launch distribution strategy
- Post-launch diagnosis (why didn't it spread?)
