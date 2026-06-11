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
