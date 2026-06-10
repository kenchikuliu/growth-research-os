# Scorecards

## Use

Use these scorecards after gathering evidence and before writing the final recommendation.

Do not trust the total score until hard gates are checked.

## Mode A: `榜单归因`

### Score 1: `Attribution Confidence`

Scale: 1-5 per dimension.  
Weighted total normalized to 100.

| Key | Weight | What it means |
| --- | ---: | --- |
| page_change_clarity | 20 | Growth is concentrated on identifiable pages |
| keyword_change_confidence | 15 | Those pages can be tied to identifiable terms |
| page_type_pattern | 15 | The winning page type is clear |
| time_window_alignment | 10 | Page, term, and trend movement line up in time |
| structural_expansion | 15 | Similar pages are appearing in a repeatable pattern |
| offsite_amplification | 10 | There is enough evidence for brand/distribution/link support |
| chain_closure | 15 | You can explain `term -> page -> traffic -> action` |

Thresholds:

- `0-39`: weak hypothesis only
- `40-59`: site is growing but cause is not clear
- `60-79`: main cause is explainable
- `80-100`: strong attribution case

### Score 2: `Replication Potential`

Scale: 1-5 per dimension.  
Weighted total normalized to 100.

| Key | Weight | What it means |
| --- | ---: | --- |
| page_shape_replicable | 20 | We can build the same page shape |
| execution_control | 15 | The play does not depend on impossible resources |
| competitive_cut_in | 20 | There is a realistic niche cut-in |
| cluster_expansion | 15 | This can extend beyond one page |
| monetization_fit | 15 | The traffic type fits monetization |
| supply_advantage | 15 | We have a real speed/product/content advantage |

Thresholds:

- `0-39`: record only
- `40-59`: borrow structure, not strategy
- `60-79`: good for a narrowed variant
- `80-100`: strong candidate for cluster or directory

### Hard Gates

All of these must pass:

1. page type is identifiable
2. at least 3 meaningful pages are identifiable
3. user click reason is understandable

## Mode B: `新词 / 新需求验证`

Scale: 1-5 per dimension.  
Weighted total normalized to 100.

| Key | Weight | What it means |
| --- | ---: | --- |
| demand_reality | 20 | Real pain, cost, and desired result are visible |
| search_carry | 15 | Search is already carrying the demand |
| trend_stability | 10 | The trend is not just a short spike |
| serp_entry | 15 | There is a realistic SERP cut-in |
| page_intent_fit | 10 | The correct page type is clear |
| clusterability | 10 | This can extend into a meaningful page set |
| monetization | 10 | There is a path to money, not just traffic |
| execution_fit | 10 | We can execute with an advantage |

### Action Thresholds

- `0-39`: stop
- `40-54`: watch
- `55-69`: ship one page
- `70-84`: ship a page cluster
- `85-100`: build a site or primary directory

### Hard Gates

Apply these before trusting the total:

1. `demand_reality >= 3`
2. `page_intent_fit >= 3` for cluster recommendations
3. `clusterability >= 3` for site recommendations
4. `monetization >= 3` for anything beyond low-cost validation
