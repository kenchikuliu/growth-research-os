# Capture Schema

Use these schemas for script-generated evidence. Prefer `network` payloads over DOM text when both exist.

## Shared Envelope

Every capture JSON should include:

```json
{
  "tool": "semrush | similarweb",
  "query": {
    "type": "domain | keyword",
    "value": "crazygames.com"
  },
  "source": {
    "provider": "3ue",
    "dashboard": "https://dash.3ue.com/zh-Hans/#/page/m/home",
    "tool_url": "",
    "captured_at": "2026-06-10T10:40:00Z"
  },
  "account_context": {},
  "capture_method": {
    "login": "automated_3ue_login | existing_session",
    "primary": "network | page_json_and_dom",
    "fallback": "dom | network"
  },
  "raw_artifacts": {
    "network_dir": "",
    "node_switches": [],
    "usage_limit_events": [],
    "notes": []
  }
}
```

## Unified Capture API Envelope

`scripts/capture_api.py` and `scripts/capture_service.py` now return one shared bundle:

```json
{
  "api": {
    "name": "demand-validation-os.capture_api",
    "version": "2026-06-11"
  },
  "request": {
    "id": "req-1",
    "query": {
      "type": "domain",
      "value": "crazygames.com"
    },
    "tools": ["semrush", "similarweb"]
  },
  "captured_at": "2026-06-11T04:20:00Z",
  "capture_mode": "serial",
  "execution_policy": {
    "device_scope": "single_device",
    "browser_scope": "single_browser",
    "page_scope": "single_active_page",
    "run_mode": "serial"
  },
  "runs": [],
  "results": {
    "semrush": {
      "best_attempt": {},
      "data": {}
    },
    "similarweb": {
      "best_attempt": {},
      "data": {}
    }
  },
  "summary": {
    "core_ready_tools": ["semrush", "similarweb"],
    "all_succeeded": true
  },
  "normalized": {}
}
```

`normalized` is additive. Downstream scale / skill code should prefer it when they need one stable cross-tool schema, but raw tool payloads remain available under `results.<tool>.data`.

## Local HTTP Service

`scripts/capture_service.py` exposes the same bundle over local HTTP/JSON.

Routes:

- `GET /health`
- `POST /capture`
- `POST /capture/tool`

Behavior rules:

- keeps `single_device + single_browser + single_active_page + serial`
- runs only one capture at a time
- returns HTTP `409` with `error.code = "capture_busy"` if another request is already running

Example request:

```json
{
  "query": "crazygames.com",
  "tools": ["semrush", "similarweb"],
  "username": "3ue-user",
  "password": "3ue-pass",
  "session_prefix": "dvos-service",
  "max_node_rotations": 2,
  "continue_on_error": false,
  "request_id": "svc-1"
}
```

Example response envelope:

```json
{
  "service": {
    "name": "demand-validation-os.capture_service",
    "version": "2026-06-11"
  },
  "served_at": "2026-06-11T04:20:05Z",
  "request_id": "svc-1",
  "ok": true,
  "data": {
    "api": {},
    "request": {},
    "execution_policy": {},
    "results": {},
    "summary": {},
    "normalized": {}
  }
}
```

## Workflow Service

`scripts/workflow_service.py` is the higher-level scale wrapper over:

- `capture_api.py`
- `run_demand_workflow.py`
- `page_artifacts.py`

Routes:

- `GET /health`
- `POST /workflow`
- `POST /workflow/page-artifacts`
- `POST /workflow/playbook`
- `POST /scale`
- `POST /scale/playbook`
- `POST /scale/page-artifacts`

Request body supports:

- `mode`
- `query`
- `domain`
- live 3ue `username` / `password`
- `bundle_input`
- `bundle_payload`
- `trends_input`
- `brand_name`
- `brand_url`
- `primary_cta_url`
- `primary_cta_label`
- `kd_input`
- `kd_score`
- `kd_live`
- `kd_gl`
- `kd_hl`
- `kd_force`
- `kd_token`
- `request_id`
- scale batch mode on `/scale` and `/scale/page-artifacts` also supports:
  - `jobs`
  - `include_workflow`
  - `min_score`
  - `allowed_actions`
  - `require_tools_ready`
  - `sort_by`
  - `ascending`
  - `top`

Example request:

```json
{
  "mode": "demand",
  "query": "ahrefs alternative",
  "domain": "ahrefs.com",
  "username": "3ue-user",
  "password": "3ue-pass",
  "brand_name": "Your Brand",
  "brand_url": "https://example.com",
  "primary_cta_url": "https://example.com/signup",
  "kd_score": 65,
  "request_id": "wf-1"
}
```

`kd_score` and `kd_input` remain the fallback adapter fields for `https://seo.web.cafe/kd/`.
By default the workflow can now fetch live KD through the public page token plus `https://seo.web.cafe/kd/api/kd`.
Use KD as a public directional difficulty hint, not as a replacement for Semrush / Similarweb page-level evidence.

Example response shape for `POST /workflow/page-artifacts`:

```json
{
  "service": {
    "name": "demand-validation-os.workflow_service",
    "version": "2026-06-11"
  },
  "request_id": "wf-1",
  "ok": true,
  "data": {
    "workflow_summary": {
      "mode": "demand",
      "query": "ahrefs alternative",
      "decision": {
        "band": "ship_cluster",
        "recommended_action": "ship_cluster",
        "total_score": 74,
        "all_hard_gates_passed": true
      },
      "direct_answer": {},
      "page_plan": {},
      "normalized_snapshot": {}
    },
    "page_artifacts": {
      "available": true,
      "page_count": 1,
      "pages": []
    }
  }
}
```

Example response shape for `POST /workflow/playbook`:

```json
{
  "ok": true,
  "data": {
    "workflow_summary": {
      "mode": "demand",
      "query": "ahrefs alternative",
      "decision": {
        "band": "ship_cluster",
        "recommended_action": "ship_cluster",
        "total_score": 74,
        "all_hard_gates_passed": true
      }
    },
    "playbook": {
      "mode": "demand",
      "goal": "新词 / 新需求验证",
      "decision": {
        "recommended_action": "ship_cluster"
      },
      "playbook_template": {
        "template_type": "new_demand_launch_play"
      },
      "launch_plan": {
        "first_batch_titles": [],
        "artifact_slugs": []
      }
    }
  }
}
```

`POST /scale` returns the thinner compact layer only:

```json
{
  "ok": true,
  "data": {
    "scale_output": {
      "mode": "demand",
      "query": "ahrefs alternative",
      "decision": {},
      "direct_answer": {},
      "page_plan": {},
      "normalized_snapshot": {},
      "artifacts": {}
    },
    "playbook": {}
  }
}
```

Batch `POST /scale` or `POST /scale/page-artifacts` can also return:

```json
{
  "ok": true,
  "data": {
    "job_count": 1,
    "filters": {
      "min_score": 60,
      "allowed_actions": ["ship_cluster", "ship_one_page"],
      "require_tools_ready": ["semrush", "similarweb"],
      "sort_by": "total_score",
      "ascending": false,
      "top": 5
    },
    "results": [],
    "table_rows": []
  }
}
```

## Thin Scale CLI

`scripts/run_scale.py` is the local CLI mirror of the thin scale HTTP layer.

Single job:

```bash
python3 scripts/run_scale.py \
  --mode demand \
  --query "ahrefs alternative" \
  --domain ahrefs.com \
  --brand-name "Your Brand" \
  --brand-url "https://example.com" \
  --primary-cta-url "https://example.com/signup"
```

Batch jobs:

```json
{
  "jobs": [
    {
      "mode": "demand",
      "query": "ahrefs alternative",
      "domain": "ahrefs.com"
    },
    {
      "mode": "attribution",
      "query": "crazygames.com",
      "domain": "crazygames.com"
    }
  ]
}
```

```bash
python3 scripts/run_scale.py \
  --jobs-input /tmp/scale-jobs.json \
  --output /tmp/scale-results.json
```

Default CLI output:

- `scale_output`
- `playbook`
- `page_artifacts`

Only include the full workflow tree when `--include-workflow` is passed.

Tabular support:

- `--jobs-input` supports `json / csv / tsv / xlsx`
- `--table-output` supports `json / csv / tsv / xlsx`
- leaderboard filter args:
  - `--min-score`
  - `--allowed-actions`
  - `--require-tools-ready`
  - `--sort-by`
  - `--ascending`
  - `--top`

Typical flattened table columns:

- `mode`
- `query`
- `domain`
- `band`
- `recommended_action`
- `total_score`
- `tools_ready`
- `top_page_count`
- `top_keyword_count`
- `landing_page_count`
- `page_artifact_count`
- `first_page_titles`
- `artifact_slugs`

## Normalized Cross-Tool Schema

The top-level `normalized` block is the stable shared layer for later scale / skill consumers.

```json
{
  "normalized": {
    "query": {
      "type": "domain",
      "value": "crazygames.com"
    },
    "tools_requested": ["semrush", "similarweb"],
    "tools_attempted": ["semrush", "similarweb"],
    "tools_ready": ["semrush", "similarweb"],
    "coverage": {
      "status": "ok",
      "partial_tools": [],
      "failed_tools": []
    },
    "traffic_summary": {
      "monthly_visits_estimate": 315900000,
      "organic_traffic_estimate": 93600000,
      "paid_traffic_estimate": 576100,
      "organic_share_percent": 42.97,
      "paid_share_percent": 1.11,
      "global_rank": 386,
      "channel_mix": [],
      "top_country_shares": []
    },
    "top_pages": [],
    "top_keywords": [],
    "landing_pages": [],
    "page_clusters": [],
    "competitors": [],
    "geo_signals": [],
    "tool_signals": {
      "semrush": {},
      "similarweb": {}
    },
    "notes": []
  }
}
```

### `traffic_summary`

Use this for the fast cross-tool snapshot:

- Similarweb contributes monthly visits, visit trend, channel mix, and top-country shares when `website_performance` is available.
- Semrush contributes organic traffic, paid traffic, and market/database layers.
- All numbers remain third-party estimates and should be described as estimates in final analysis.

### `top_pages`

Unified page-level rows. Typical fields:

```json
{
  "url": "https://www.crazygames.com/",
  "title": "CrazyGames",
  "page_kind": "organic_top_page | popular_page",
  "traffic_estimate": 3272000,
  "traffic_share_percent": 27.82,
  "traffic_change_percent": null,
  "traffic_change_pp": null,
  "top_keyword": "crazy games",
  "position": 1,
  "source_tool": "semrush | similarweb",
  "source_section": "top_pages | website_content_top_pages"
}
```

### `top_keywords`

Unified keyword rows. Typical fields:

```json
{
  "keyword": "crazy games",
  "keyword_kind": "organic | non_brand",
  "search_channel": "organic | mixed",
  "position": 1,
  "volume": 4090000,
  "traffic_estimate": 3272000,
  "traffic_share_percent": 27.82,
  "organic_share_percent": null,
  "paid_share_percent": null,
  "url": "https://www.crazygames.com/",
  "source_tool": "semrush | similarweb",
  "source_section": "top_organic_keywords | keyword_research.top_non_brand_keywords"
}
```

### `landing_pages`

Current landing-page layer is Similarweb-first:

```json
{
  "url": "https://crazygames.com/game/geometry-dash-online",
  "landing_type": "popular_page | paid_landing_page",
  "clicks_estimate": 18000,
  "traffic_share_percent": 3.94,
  "traffic_change_percent": 0.0,
  "traffic_change_pp": null,
  "top_keyword": "geometry dash",
  "new_keyword_count": 12,
  "source_tool": "similarweb",
  "source_section": "landing_pages_research.top_pages | landing_pages_research.paid_landing_pages"
}
```

### `page_clusters`

Use this to group demand by topic or folder shape:

- Semrush contributes `top_topics`
- Similarweb contributes `landing_pages_research.folder_rows`

### `competitors`

Use this as the shared competitor layer:

- Semrush contributes `organic_competitors`
- Similarweb contributes `similar_sites` when available

### `geo_signals`

Use this to compare geography and market/database evidence:

- Semrush contributes `markets_current`
- Similarweb contributes `website_performance.top_countries`

### `tool_signals`

This block summarizes per-tool readiness and quick operational facts.

Examples:

- `tool_signals.semrush.top_page_count`
- `tool_signals.semrush.top_keyword_count`
- `tool_signals.similarweb.landing_page_count`
- `tool_signals.similarweb.seed_keywords`
- `tool_signals.similarweb.route_navigation_used`

## Normalized To Artifact Path

`page_artifacts.py` now prefers `evidence.tool_capture.normalized` when present.

That means downstream scale / service code can:

1. capture once through `capture_api.py` or `capture_service.py`
2. pass the stable bundle into `run_demand_workflow.py` as `bundle_payload`
3. let `page_artifacts.py` build proof points and comparison-page JSON from the normalized layer

This reduces coupling to raw:

- `results.semrush.data.top_pages`
- `results.semrush.data.top_organic_keywords`
- `results.similarweb.data.website_evidence.search_overview`
- `results.similarweb.data.website_evidence.website_content`

The raw payloads still remain available for deeper debugging or later extraction.

## Playbook Layer

`run_demand_workflow.py` now also emits a top-level `playbook`.

Use it when you need:

- a direct execution handoff for `榜单归因`
- a launch plan for `新词 / 新需求验证`
- a stable result layer that is smaller than full workflow JSON but richer than `scale_output`

Typical `playbook` responsibilities:

- compress the decision into one execution-oriented summary
- separate the next actions from the longer workflow reasoning
- surface first-batch page titles, artifact slugs, reusable parts, and do-not-copy constraints
- expose a stable `playbook_template` so downstream scale / skill / UI code can render a fixed execution scaffold per mode

## web.cafe KD Layer

`run_demand_workflow.py` can also carry:

```json
{
  "evidence": {
    "web_cafe_kd": {
      "query": "ahrefs alternative",
      "available": true,
      "kd_score": 65,
      "kd_bucket": "hard",
      "guidance": "不建议直接正面争夺主词，优先做截流页、替代页或明显更窄的意图页面。"
    }
  }
}
```

Use this layer for:

- direct-vs-narrower page-cut decisions
- deciding whether to prefer `alternative / comparison` pages
- adding a public difficulty hint to playbooks and page artifacts

Do not use this layer alone to claim a market is easy or hard. It is a directional signal that should be combined with page-level evidence from Similarweb / Semrush.

## Frontend Artifact Protocol

Each page artifact now contains both:

- `page_json`
- `frontend_payload`

Top-level artifact bundle also contains:

- `frontend_protocol`
- `publishable_pages`

Example:

```json
{
  "available": true,
  "page_count": 1,
  "frontend_protocol": {
    "version": "2026-06-11",
    "page_template_types": ["comparison_page"],
    "block_types": ["comparison_table", "direct_answers", "evidence", "faq", "fit_for"]
  },
  "publishable_pages": [
    {
      "version": "2026-06-11",
      "slug": "ahrefs-alternative",
      "path": "/alternatives/ahrefs-alternative",
      "template": "comparison_page",
      "seo": {},
      "hero": {},
      "sections": [],
      "navigation": {},
      "editorial": {},
      "source_context": {}
    }
  ],
  "pages": [
    {
      "kind": "comparison_page",
      "slug": "ahrefs-alternative",
      "target_path": "/alternatives/ahrefs-alternative",
      "page_json": {},
      "frontend_payload": {
        "version": "2026-06-11",
        "template": "comparison_page",
        "route": {
          "slug": "ahrefs-alternative",
          "path": "/alternatives/ahrefs-alternative"
        },
        "seo": {},
        "hero": {},
        "sections": [],
        "blocks": [
          {
            "id": "comparison-table",
            "type": "comparison_table",
            "required": true,
            "data": {
              "heading": "ahrefs vs 你的品牌：Comparison",
              "dimensions": ["价格", "功能", "适用场景"],
              "rows": []
            }
          }
        ],
        "navigation": {},
        "editorial": {},
        "source_context": {}
      }
    }
  ]
}
```

Use `frontend_payload` when rendering pages in a frontend app. Use `page_json` when you still want the richer editorial shape.
Use `frontend_payload.blocks` when you want a schema-stable render protocol instead of inferring section semantics from prose or section order.
Use `publishable_pages` when you want a more direct “ready-to-render page copy JSON” layer for CMS, page builders, or static-site ingestion.

If a 3ue tool page shows a daily-limit wall such as `Daily usage limit reached`, the capture scripts should:

- record the event in `raw_artifacts.usage_limit_events`
- rotate to another configured node when available
- record the selected replacement in `raw_artifacts.node_switches`
- retry the capture route before returning partial output

## `semrush`

Minimum sections:

```json
{
  "tool": "semrush",
  "domain_overview": {
    "domain": "crazygames.com",
    "database": "us",
    "snapshot_date": "2026-06-09",
    "authority_score": 90,
    "organic_traffic": 93600000,
    "organic_traffic_change_pct": -1.5,
    "paid_traffic": 576100,
    "paid_traffic_change_pct": 13.0,
    "organic_keywords": 3000000,
    "paid_keywords": 4500,
    "backlinks": 6800000,
    "referring_domains": 32976
  },
  "organic_competitors": [],
  "top_organic_keywords": [],
  "organic_trend": [],
  "top_topics": [],
  "ai_overview": {
    "visibility": 53,
    "cited_pages": 23810,
    "sources": []
  },
  "backlink_overview": {
    "authority_score": 90,
    "backlinks": 6768639,
    "referring_domains": 32976,
    "top_anchors": []
  }
}
```

Operational notes:

- `raw_artifacts.overview_attempts` records whether the overview route had to be retried because the first pass returned no usable RPC payloads.
- `raw_artifacts.node_switches` and `raw_artifacts.usage_limit_events` record 3ue node rotation telemetry when a daily-limit wall is detected.
- Prefer running Semrush serially with Similarweb through `scripts/capture_bundle.py` instead of starting both browser-backed captures in parallel.

Recommended item shapes:

```json
{
  "organic_competitors": [
    {
      "domain": "poki.com",
      "common_keywords": 68911,
      "competition_level": 0.54,
      "organic_positions": 489811,
      "organic_traffic": 11635769,
      "organic_traffic_cost": 1392459
    }
  ],
  "top_organic_keywords": [
    {
      "keyword": "crazy games",
      "position": 1,
      "volume": 4090000,
      "traffic": 3272000,
      "traffic_percent": 27.82,
      "keyword_difficulty": 85,
      "intent_codes": [2],
      "url": "https://www.crazygames.com/"
    }
  ],
  "top_topics": [
    {
      "topic": "Online Multiplayer Games",
      "keywords_count": 25026,
      "top_page_url": "https://www.crazygames.com/",
      "top_page_keyword": "crazy games",
      "top_page_volume": 4090000,
      "top_page_traffic": 1014320
    }
  ]
}
```

Operational notes:

- `raw_artifacts.node_switches` and `raw_artifacts.usage_limit_events` are also emitted for Similarweb when a daily-limit wall is encountered during shell open or report navigation.
- `网站表现` remains the stable structured baseline, but the capture now also attempts deeper `网站内容` and `搜索概况` routes before falling back to shell-only evidence.

## `similarweb`

Because Similarweb is more route-sensitive under 3ue, support two capture levels.

### Level 1: `account_state`

Always collect:

```json
{
  "tool": "similarweb",
  "account_state": {
    "identity": {
      "user_id": 39088801,
      "account_id": 13142404,
      "account_name": "Celina Terrell"
    },
    "favorites": [],
    "recent_items": [],
    "available_components": {}
  }
}
```

### Level 2: `website_evidence`

Collect when a target domain has a reachable report or state artifact.

```json
{
  "website_evidence": {
    "domain": "crazygames.com",
    "report_navigation_used": "hash_route_assign",
    "website_performance": {
      "available": true,
      "route": "https://sim.3ue.com/#/digitalsuite/websiteanalysis/overview/website-performance/*/999/3m?webSource=Total&key=crazygames.com",
      "title": "网站表现",
      "domain": "crazygames.com",
      "total_visits": {
        "date_range": "Mar 2026 - May 2026",
        "geography": "全球",
        "visits": "315.9M",
        "change_pct": "8.56%"
      },
      "ranks": {
        "global_rank": "#386"
      },
      "traffic_channels": {
        "rows": [
          {
            "channel": "直接",
            "share": "48.42%"
          }
        ]
      }
    },
    "website_content": {
      "available": true,
      "route": "https://sim.3ue.com/#/digitalsuite/websiteanalysis/overview/website-content/*/999/3m?webSource=Total&key=crazygames.com&selectedTab=Folders",
      "title": "网站内容",
      "domain": "crazygames.com",
      "summary": {
        "total_folders": 247,
        "selected_folder_count": 0,
        "rows": [
          {
            "rank": 1,
            "folder": "crazygames.com/game",
            "share": "41.96%",
            "month_over_month_change": "0.41 pp"
          }
        ]
      }
    },
    "website_content_top_pages": {
      "available": true,
      "route": "https://sim.3ue.com/#/digitalsuite/websiteanalysis/overview/website-content/*/999/3m?webSource=Total&key=crazygames.com&selectedTab=PopularPages",
      "title": "网站内容",
      "domain": "crazygames.com",
      "summary": {
        "rows": [
          {
            "rank": 1,
            "url": "crazygames.com/game/geometry-dash-online",
            "share": "3.94%",
            "month_over_month_change": "0%"
          }
        ]
      }
    },
    "search_overview": {
      "available": true,
      "route": "https://sim.3ue.com/#/digitalsuite/websiteanalysis/search-overview/*/999/3m?webSource=Total&key=crazygames.com",
      "title": "搜索概况",
      "domain": "crazygames.com",
      "summary": {
        "overview": {
          "traffic": "45.25M",
          "traffic_yoy": "50.38%",
          "share_of_total": "42.97%"
        },
        "brand_vs_non_brand": {
          "branded": "61.06%",
          "non_branded": "38.94%"
        }
      },
      "top_non_brand_keywords": {
        "rows": [
          {
            "keyword": "juegos",
            "clicks": "1.2M",
            "share": "3.22%",
            "year_over_year_change": "52.66%",
            "organic_share": "98.89%",
            "paid_share": "1.11%"
          }
        ]
      },
      "paid_landing_pages": {
        "rows": [
          {
            "url": "crazygames.com/game/geometry-dash-online",
            "clicks": "18K",
            "share": "3.94%",
            "month_over_month_change": "0%",
            "top_keyword": {
              "keyword": "geometry dash",
              "new_keywords": null,
              "raw": "geometry dash"
            }
          }
        ]
      }
    },
    "keyword_research": {
      "available": true,
      "seed_domain": "crazygames.com",
      "quick_search_keywords": ["crazygames", "crazygames.com"],
      "autocomplete_keywords": [],
      "top_non_brand_keywords": {
        "rows": [
          {
            "keyword": "juegos",
            "clicks": "1.2M"
          }
        ]
      },
      "organic_search_overview": {},
      "paid_search_overview": {},
      "priority_keyword_alerts": [
        {
          "domain": "kimi.com",
          "new_count": 195,
          "metric": "keywords"
        }
      ],
      "route_candidates": [
        {
          "label": "自然搜索",
          "href": "#/digitalsuite/websiteanalysis/search-overview/*/999/3m?webSource=Total&key=crazygames.com&Keywords_filters=OP;%3D%3D;0",
          "source": "report_link",
          "reason": "organic-search-route-hint"
        }
      ]
    },
    "landing_pages_research": {
      "available": true,
      "folder_rows": [
        {
          "rank": 1,
          "folder": "crazygames.com/game",
          "share": "41.96%"
        }
      ],
      "top_pages": {
        "summary": {
          "rows": [
            {
              "rank": 1,
              "url": "crazygames.com/game/geometry-dash-online"
            }
          ]
        }
      },
      "paid_landing_pages": {
        "rows": [
          {
            "url": "crazygames.com/game/geometry-dash-online",
            "clicks": "18K"
          }
        ]
      },
      "priority_landing_page_alerts": [
        {
          "domain": "alibabacloud.com",
          "new_count": 97,
          "metric": "landing_pages"
        }
      ],
      "route_candidates": [
        {
          "label": "网站内容 / 热门页面",
          "href": "#/digitalsuite/websiteanalysis/overview/website-content/*/999/3m?webSource=Total&key=crazygames.com&selectedTab=PopularPages",
          "source": "derived",
          "reason": "website-content-top-pages-derived-route"
        }
      ]
    },
    "home_signals": {
      "route": "https://sim.3ue.com/#/activation/home",
      "title": "Activation Setup Page",
      "priority_alerts": [
        {
          "domain": "alibabacloud.com",
          "new_count": 97,
          "metric": "landing_pages",
          "summary": "..."
        }
      ]
    },
    "autocomplete_websites": [],
    "autocomplete_keywords": []
  }
}
```

Recommended item shapes:

```json
{
  "autocomplete_websites": [
    {
      "name": "crazygames.com",
      "blocked": true
    }
  ],
  "recent_items": [
    {
      "main_item": "tranai.app",
      "state_name": "digitalsuite_backlinks_overview",
      "page_title": "digitalsuite.backlinks.overview.title",
      "duration": "365d",
      "country": 999
    }
  ]
}
```

## Notes

- `Similarweb` under 3ue currently has a stronger session coupling than `Semrush`.
- `网站表现` is the current stable Similarweb report baseline in this skill.
- When the shell stays healthy, the capture now also emits structured `website_content` folder rows plus `search_overview` keyword and paid-landing-page rows.
- `home_signals.priority_alerts` is the current fallback growth-signal layer when Similarweb shell routing is only partially ready.
- `keyword_research` groups quick-search keyword seeds, search-overview route candidates, filtered `自然搜索 / 付费搜索` attempts, and Similarweb keyword alerts into one reusable JSON block.
- `landing_pages_research` groups website-content folders, 热门页面 / `selectedTab=PopularPages` attempts, paid landing pages, and Similarweb landing-page alerts into one reusable JSON block.
- If a deeper target-domain report capture is blocked, still emit `account_state` plus any route/state evidence gathered from favorites, recent items, settings, and autocomplete.
- Do not silently fake missing report sections. Emit empty arrays and explain the gap in `raw_artifacts.notes`.

## Serial Bundle

When both tools are needed in one run, prefer:

```bash
python3 scripts/capture_bundle.py --query crazygames.com --max-node-rotations 2 --output /tmp/crazygames-bundle.json
```

The bundle format is:

```json
{
  "query": {
    "type": "domain",
    "value": "crazygames.com"
  },
  "capture_mode": "serial",
  "runs": [
    {
      "tool": "semrush",
      "attempt": 1,
      "status": "ok",
      "quality": {
        "core_ready": true
      }
    },
    {
      "tool": "similarweb",
      "attempt": 1,
      "status": "ok",
      "quality": {
        "core_ready": true
      }
    }
  ],
  "results": {
    "semrush": {
      "best_attempt": {
        "status": "ok",
        "quality": {
          "core_ready": true
        }
      },
      "data": {}
    },
    "similarweb": {
      "best_attempt": {
        "status": "ok",
        "quality": {
          "core_ready": true
        }
      },
      "data": {}
    }
  },
  "summary": {
    "core_ready_tools": [
      "semrush",
      "similarweb"
    ],
    "all_succeeded": true
  }
}
```
