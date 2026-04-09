---
name: propagation-evidence-collector
description: Collect multi-source evidence to reconstruct how a product or keyword spread over time. Use when you need to answer "when did attention start, where did it first appear, where did it scale". DO NOT explain why it spread — only collect and structure evidence. Trigger: /propagation-evidence-collector or when asked to trace viral timeline.
---

# Propagation Evidence Collector

## Purpose
Reconstruct HOW a product or keyword spread over time using multi-source evidence.

This skill answers:
- When did attention start?
- Where did it first appear?
- Where did it scale?
- Do signals align across platforms?

**DO NOT explain why it spread. ONLY collect and structure evidence.**

---

## Input Types

### Type A: Target Only
- product name / domain / keyword

### Type B: Evidence Bundle
- Google Trends screenshots
- X search results
- Reddit threads
- YouTube videos
- notes

---

## Mandatory Pipeline

### Step 1. Google Trends (Demand Signal)

Query the target keyword. Extract:
- First lift date
- Peak date
- Pattern classification: `flat` / `spike` / `gradual`

If no direct access, ask user to provide screenshot or describe trend shape.

---

### Step 2. Google Search (Earliest Mentions)

Query:
```
"keyword" -site:domain
```

Extract:
- Earliest mention (date + source)
- Earliest *meaningful* mention (with engagement signals)

---

### Step 3. X (Twitter) Time Slicing

Use `since:` and `until:` operators to slice by period.

Extract:
- First tweet mentioning the product
- First tweet with traction (replies/retweets/likes)
- Density growth (low → medium → high)

---

### Step 4. Reddit (Community Signal)

Search target on Reddit. Extract:
- First thread
- Upvotes / comments count
- Sentiment: `positive` / `neutral` / `critical`
- Recommendation behavior: did users recommend to others?

---

### Step 5. YouTube (Amplification Signal)

Extract:
- First video
- First high-view video (>10k views)
- Content type: `demo` / `reaction` / `tutorial` / `review`

---

### Step 6. Timeline Reconstruction

Synthesize all sources into a structured timeline:

| Node | Date | Event |
|------|------|-------|
| T0   | ...  | Domain registered / product created |
| T1   | ...  | First mention |
| T2   | ...  | First social signal |
| T3   | ...  | Traction begins |
| T4   | ...  | Growth phase |
| T5   | ...  | Amplification (YouTube / press) |
| T6   | ...  | Decay / plateau |

---

### Step 7. Signal Consistency Check

Compare timing across:
- Google Trends
- X (Twitter)
- Reddit
- YouTube

Output consistency score: `high` / `medium` / `low`

- **High**: all platforms show correlated lift within same 2-week window
- **Medium**: 2–3 platforms align, 1 lags or leads by >1 month
- **Low**: signals disagree or only 1 platform shows activity

---

### Step 8. Exposure Layers

Identify which layer each signal belongs to:

| Layer | Description | Sources |
|-------|-------------|---------|
| Seed | First adopters, creators, niche communities | Early tweets, Reddit, Product Hunt |
| Early Traction | Word-of-mouth begins, organic growth | X threads, upvoted Reddit posts |
| Scale | Mass amplification | YouTube, press, TikTok |

---

## Output Format

```
### Target
[product / keyword]

### Google Trends
Pattern: [flat/spike/gradual]
First lift: [date]
Peak: [date]

### Earliest Mentions
[date] — [source] — [description]
[date] — [source] — [description]

### X Timeline
First tweet: [date] — [content summary]
First traction tweet: [date] — [engagement]
Density: [low/medium/high by period]

### Reddit Signal
First thread: [date] — [title] — [upvotes/comments]
Sentiment: [positive/neutral/critical]
Recommendation: [yes/partial/no]

### YouTube Signal
First video: [date] — [title] — [views]
First high-view video: [date] — [title] — [views]
Content type: [demo/reaction/tutorial/review]

### Timeline
T0: [date] — [event]
T1: [date] — [event]
...

### Exposure Layers
Seed: [sources]
Early Traction: [sources]
Scale: [sources]

### Signal Consistency
Score: [high/medium/low]
Notes: [explanation]

### Evidence Confidence
[high/medium/low] — [reasoning]
```
