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

```
/demand-validation-os
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
