---
name: propagation-workflow
description: Full viral propagation analysis pipeline. Runs 3 steps in sequence: (1) evidence collection, (2) causality analysis, (3) design translation. Use when you want to understand WHY something went viral and how to apply it to your own product. Trigger: /propagation-workflow, /viral-analysis, or when asked "why did X go viral" or "how can I make my product spread like X".
---

# Propagation Analysis Workflow

## Overview

A 3-step research system that goes from raw product/keyword → structured evidence → causal explanation → actionable design.

**Do not skip steps. Do not mix steps.**

---

## When to Use This

Use this workflow when you want to:
- Understand why a specific product went viral
- Find replicable mechanisms from a competitor's growth
- Design your own product to spread organically
- Audit why your product isn't spreading

---

## Entry

At the start, ask the user:

> "What product or keyword are we analyzing? Do you have any existing evidence (screenshots, links, notes), or should we start from scratch?"

Then proceed to Step 1.

---

## Step 1 — Evidence Collection

**Goal**: Reconstruct timeline and exposure layers. Find facts, not explanations.

Invoke: `Propagation Evidence Collector`

Collect from:
1. Google Trends — demand curve and first lift
2. Google Search — earliest mentions
3. X (Twitter) — time-sliced signal density
4. Reddit — community first contact
5. YouTube — amplification timing

Output: structured timeline + exposure layers + signal consistency score

**Do not proceed to Step 2 until evidence is structured.**

---

## Step 2 — Causality Analysis

**Goal**: Explain WHY it spread using the evidence from Step 1.

Invoke: `Viral Causality Analyzer`

Analyze:
1. Behavioral definition (what users actually do)
2. Psychological definition (what it means to them)
3. Shareable unit (what gets shared)
4. Propagation triggers (top 3 with evidence)
5. Content-by-use score
6. Click cause vs spread cause (must be different)
7. Platform roles (seed / scale / amplify)
8. Causal weights (product / exposure / platform / timing)
9. Viral type (burst / hybrid / durable)

Output: causal diagnosis + "why it spreads" + "why it fades"

**Do not proceed to Step 3 until causality is diagnosed.**

---

## Step 3 — Design Translation

**Goal**: Apply viral insights to the user's own product.

Invoke: `Propagation Design Translator`

Translate:
1. Extract transferable mechanisms
2. Exclude non-transferable factors (timing, luck)
3. Gap analysis against user's product
4. Design improvements by layer (core mechanic / output / friction / distribution hook / landing page)
5. 3–5 concrete, implementable ideas

Output: gap analysis + ranked design ideas

---

## Full Output Order

```
1. EVIDENCE
   - Timeline (T0 → T6)
   - Exposure layers
   - Signal consistency

2. CAUSALITY
   - Shareable unit
   - Triggers
   - Click vs spread cause
   - Causal weights
   - Viral type + final diagnosis

3. DESIGN
   - My product gaps
   - Design improvements
   - Concrete ideas (ranked)
```

---

## Quality Gates

Before moving between steps, verify:

**Step 1 → Step 2**:
- [ ] Timeline has at least 4 nodes with dates
- [ ] At least 3 platforms checked
- [ ] Signal consistency scored

**Step 2 → Step 3**:
- [ ] Click cause ≠ spread cause
- [ ] Causal weights sum to 100%
- [ ] Viral type assigned

**Step 3 complete**:
- [ ] Each idea traces to a specific gap
- [ ] Non-transferable factors explicitly excluded
- [ ] Priority order provided

---

## Notes

- If evidence is incomplete (e.g., product is new or data is scarce), state confidence level explicitly
- If causal weight of timing > 40%, warn that replication may be luck-dependent
- Always distinguish what you *observed* (evidence) from what you *inferred* (causality)
