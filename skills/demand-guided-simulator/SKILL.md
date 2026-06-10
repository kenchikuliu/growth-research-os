---
name: demand-guided-simulator
description: Run a web.cafe-style staged demand or attribution workflow on top of gefei, chuhai, Google Trends, Similarweb, and Semrush. Use when Codex needs a contradiction-first, step-by-step simulator-like output instead of a flat SEO report, especially for new demand validation, leaderboard attribution, page-type diagnosis, or first-batch page planning.
---

# Demand Guided Simulator

Use this skill when the user wants a `web.cafe`-style teaching and diagnosis flow, not just a tool dump.

This skill assumes the evidence should be:

- staged
- data-backed
- page-level
- decision-oriented

It wraps the existing `demand-validation-os` collection layer and adds a guided `learn step-by-step` style output.

## What It Must Do

The output should follow the same product logic as the `web.cafe` simulator family:

- lead with a contradiction
- expose one hidden variable
- show a guided path and a direct-result path
- unlock one concept per step
- end with a bounded next action, not generic advice

Read [references/stage-model.md](references/stage-model.md) before using this skill so the stage structure stays faithful to the simulator pattern.

## Default Workflow

1. Decide the mode first:
   - `demand` for `新词 / 新需求验证`
   - `attribution` for `榜单归因`
2. Prefer the dedicated simulator wrapper:

```bash
python3 skills/demand-guided-simulator/scripts/demand_guided_simulator.py \
  --mode demand \
  --query "pdf to epub converter" \
  --domain pdftoepub.app \
  --view simulator \
  --output /tmp/demand-simulator.json
```

3. If you need the full workflow artifact first, run the one-click orchestrator:

```bash
python3 skills/demand-validation-os/scripts/run_demand_workflow.py \
  --mode demand \
  --query "pdf to epub converter" \
  --domain pdftoepub.app \
  --output /tmp/demand-workflow.json
```

4. If you already have workflow JSON, render one of these simulator surfaces:

```bash
python3 skills/demand-guided-simulator/scripts/demand_guided_simulator.py \
  --workflow-input /tmp/demand-workflow.json \
  --view guided \
  --output /tmp/demand-guided-flow.json

python3 skills/demand-guided-simulator/scripts/demand_guided_simulator.py \
  --workflow-input /tmp/demand-workflow.json \
  --view direct

python3 skills/demand-guided-simulator/scripts/demand_guided_simulator.py \
  --workflow-input /tmp/demand-workflow.json \
  --view step \
  --step 3
```

5. Present the result in this order:
   - contradiction
   - hidden variable
   - staged diagnosis
   - direct decision
   - first batch of pages or reusable actions

## Evidence Rule

Do not replace missing evidence with prose.

If:

- Trends is missing
- Semrush is partial
- Similarweb only reached baseline website-performance
- Reddit / community proof is missing

say that explicitly inside the stage diagnosis.

## Output Shape

Use two surfaces:

1. `guided path`
   - step count
   - one question per step
   - facts
   - inference
   - diagnosis
   - next action

2. `direct result`
   - score band
   - hard-gate status
   - recommended action
   - first batch of pages or reusable play

## Notes

- `gefei` provides judgment rules.
- `chuhai` provides operator path: Similarweb landing pages, Semrush top pages, Trends usage.
- `Google Trends` provides shape, not absolute demand.
- `Semrush` and `Similarweb` provide the page-level proof layer.
- `web.cafe` contributes the product shape:
  - `https://new.web.cafe/seosimulator/gsc/` -> contradiction-first landing, dual CTA, bounded tutorial flow
  - `https://new.web.cafe/seosimulator/` -> staged SEO growth progression and action-driven state changes
  - `https://new.web.cafe/search-simulator/` -> one hidden mechanism per step, causal decomposition
- This skill is not a generic SEO explainer. It is a staged diagnosis wrapper around the repo's structured workflow JSON.
