---
name: viral-causality-analyzer
description: Explain WHY a product spread using evidence from Propagation Evidence Collector. Separates click cause vs spread cause vs amplification cause. Must consume structured evidence — do not run standalone without evidence input. Trigger: /viral-causality-analyzer or when asked to explain why something went viral.
---

# Viral Causality Analyzer

## Purpose
Explain **WHY** something spread using evidence.

Must clearly separate:
- **Click cause**: why users entered / tried it
- **Spread cause**: why users shared it
- **Amplification cause**: what scaled it beyond organic

---

## Input Requirement

**Must consume output from: Propagation Evidence Collector**

Do not analyze causality without structured evidence. If evidence is missing, run Propagation Evidence Collector first.

---

## Core Questions (Answer All)

1. What do users actually do with this product?
2. What do users share from this product?
3. Why do they share it (psychological trigger)?
4. What triggered initial attention?
5. What amplified it beyond early adopters?

---

## Analysis Steps

### Step 1. Behavioral Definition

Describe precisely what users do — not the feature, the actual behavior.

Example:
- Bad: "users generate AI images"
- Good: "users type a selfie prompt, get a stylized portrait, screenshot it"

---

### Step 2. Psychological Definition

What does this product represent to users psychologically?

Choose primary frame:
- Identity expression ("this is who I am")
- Performance ("look what I can do")
- Humor ("this is absurd/funny")
- Surprise ("I didn't expect this")
- Belonging ("my group uses this")
- Utility signaling ("I'm smart/efficient")

---

### Step 3. Shareable Unit

Define the atomic shareable object:
- What exactly gets shared? (screenshot / output / reaction video / link)
- Does it contain the product name/branding?
- Strength: `strong` / `medium` / `weak`

Criteria for **strong**:
- Self-contained (tells the story without context)
- Contains identity signal
- Prompts "what is this?" from non-users

---

### Step 4. Propagation Triggers

Pick top 3 triggers from evidence:

| Trigger | Description |
|---------|-------------|
| humor | content is funny |
| surprise | unexpected output |
| identity | reflects user's self-image |
| performance | shows skill or taste |
| social proof | others are doing it |
| FOMO | fear of missing out |
| outrage | generates controversy |
| utility | genuinely useful |
| nostalgia | emotional resonance |
| exclusivity | limited access |

Evidence requirement: each trigger must be traceable to at least one data point (tweet, reddit thread, etc.)

---

### Step 5. Content-by-Use

Does using the product automatically generate shareable content?

- **Yes**: using it produces something worth sharing (e.g. DALL-E outputs)
- **Partial**: possible but requires friction (e.g. need to screenshot manually)
- **No**: usage doesn't produce natural share artifacts

This is the most important structural indicator of viral potential.

---

### Step 6. Click vs Spread Cause (Separation)

**Click cause** (why users entered):
- What did they see first?
- What made them try it?
- Was it curiosity, a recommendation, or ad?

**Spread cause** (why they shared after using):
- What happened during use that prompted sharing?
- What emotional state drove the share action?
- Would they have shared if no one saw their reaction?

These must be different answers. If they are the same, your analysis is incomplete.

---

### Step 7. Platform Roles

Map each platform to its role:

| Role | Platform | Evidence |
|------|----------|---------|
| Seed | ... | First mentions, early community |
| Scale | ... | Where mass reached |
| Amplification | ... | Where it became mainstream |

---

### Step 8. Causal Weight Estimation

Estimate % contribution of each factor:

| Factor | Weight |
|--------|--------|
| Product mechanism (inherent shareability) | __% |
| Seeding / exposure (right person, right time) | __% |
| Platform amplification (algorithm, trending) | __% |
| Timing / cultural moment | __% |
| **Total** | 100% |

High product mechanism % = replicable. High timing % = luck-dependent.

---

### Step 9. Viral Type Classification

| Type | Pattern | Implication |
|------|---------|-------------|
| burst | rapid spike, fast decay | one-time moment, hard to replicate |
| hybrid | spike + sustained tail | strong product + good timing |
| durable | gradual, sustained growth | strong utility, word-of-mouth engine |

---

## Output Format

```
### Product
[name]

### Behavioral Definition
[precise behavior description]

### Psychological Definition
[primary frame] — [explanation]

### Shareable Unit
Type: [screenshot/output/video/link]
Contains branding: [yes/no]
Strength: [strong/medium/weak]
Reason: [why]

### Triggers
1. [trigger] — [evidence]
2. [trigger] — [evidence]
3. [trigger] — [evidence]

### Content-by-Use
[yes/partial/no] — [explanation]

### Click Cause
[what drew users in]

### Spread Cause
[what made users share]

### Platform Roles
Seed: [platform] — [evidence]
Scale: [platform] — [evidence]
Amplification: [platform] — [evidence]

### Causal Weights
Product mechanism: __%
Exposure / seeding: __%
Platform amplification: __%
Timing: __%

### Viral Type
[burst/hybrid/durable] — [reasoning]

### Final Diagnosis
[2-3 sentence summary of WHY it spread]

### Why It Spreads
[core mechanism in 1 sentence]

### Why It Fades
[core decay mechanism in 1 sentence]
```
