---
name: propagation-design-translator
description: Translate viral causality analysis into actionable product design changes. Must consume output from Viral Causality Analyzer. Answers "what should I build or change to replicate the propagation?" Trigger: /propagation-design-translator or when asked to apply viral insights to product design.
---

# Propagation Design Translator

## Purpose
Translate viral analysis into **actionable product design**.

This skill answers:
> "What should I build or change to replicate the propagation?"

---

## Input Requirement

**Must consume output from: Viral Causality Analyzer**

Required fields from input:
- Shareable Unit (type + strength)
- Triggers (top 3)
- Content-by-Use score
- Causal Weights
- Viral Type

Do not generate design recommendations without causality analysis.

---

## Steps

### Step 1. Extract Transferable Mechanisms

From the causality analysis, identify what is *structurally* replicable:

| Element | From Analysis | Transferable? |
|---------|--------------|---------------|
| Shareable unit type | ... | yes/no |
| Primary trigger | ... | yes/no |
| Content-by-use pattern | ... | yes/no |
| Platform distribution hook | ... | yes/no |

**Transferable = can be deliberately designed into another product.**

---

### Step 2. Identify Non-Transferable Factors

Explicitly exclude:
- Luck / timing (high timing weight in causal analysis)
- Specific influencer dependency
- One-off cultural moment
- Platform algorithm state that no longer exists

**If causal weight of timing + exposure > 60%, the viral event may not be replicable. State this clearly.**

---

### Step 3. Gap Analysis — Map to My Product

Answer each question for the user's own product:

| Question | Answer |
|----------|--------|
| What is my shareable unit? | ... |
| How strong is it? (strong/medium/weak) | ... |
| What is my primary trigger? | ... |
| Does use generate shareable content? | ... |
| Where does my current distribution start? | ... |
| What friction exists between use and share? | ... |
| What is missing compared to reference product? | ... |

---

### Step 4. Design Improvements by Layer

Structure recommendations by change layer:

#### Layer 1: Core Product Mechanic
Changes to what the product does or produces.
- Does it now produce a stronger shareable unit?
- Does it trigger identity/performance/humor more directly?

#### Layer 2: Output / Demo Design
Changes to what users see as the result of using it.
- Is the output immediately screenshot-able?
- Does it contain implicit branding (watermark, style, format)?
- Can it be embedded in a social post without explanation?

#### Layer 3: Friction Reduction
Remove steps between use → share.
- One-click share button?
- Auto-generated caption?
- Auto-formatted for platform (Twitter card, IG story, etc.)?

#### Layer 4: Distribution Hooks
Mechanisms that pull new users in from shared content.
- Does the shared artifact contain a CTA or URL?
- Does it create curiosity in non-users ("what is this?")?
- Is there a referral loop built into sharing?

#### Layer 5: Landing Page / First Impression
What does a new user see when they arrive from shared content?
- Does it match the promise of the shared artifact?
- Is time-to-value under 60 seconds?

---

### Step 5. Generate Concrete Ideas

Output 3–5 specific, implementable ideas. Each idea must:
- Be buildable (no "improve UX" vague suggestions)
- Be traceable to a specific gap identified in Step 3
- Have a predicted impact on shareability

Format:
```
Idea N: [name]
Gap addressed: [from Step 3]
What to build/change: [specific]
Expected effect: [on shareable unit / trigger / friction]
Effort estimate: [low/medium/high]
```

---

## Output Format

```
### Reference Product
[name from causality analysis]

### Transferable Mechanisms
1. [mechanism] — [why transferable]
2. [mechanism] — [why transferable]
3. [mechanism] — [why transferable]

### Non-Transferable Factors
1. [factor] — [why excluded]
2. [factor] — [why excluded]

### My Product Gap Analysis
Shareable unit: [current state] → [target state]
Primary trigger: [current] → [target]
Content-by-use: [current] → [target]
Distribution hook: [current] → [target]
Key friction: [description]

### Design Improvements

#### Core Product Mechanic
[specific changes]

#### Output / Demo Design
[specific changes]

#### Friction Reduction
[specific changes]

#### Distribution Hooks
[specific changes]

#### Landing Page / First Impression
[specific changes]

### Concrete Ideas
Idea 1: [name]
Gap: [...]
Build: [...]
Effect: [...]
Effort: [low/medium/high]

Idea 2: ...

Idea 3: ...

Idea 4: ...

Idea 5: ...

### Priority Order
[ranked list of ideas by expected impact / effort ratio]
```
