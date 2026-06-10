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
    "notes": []
  }
}
```

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
- If a deeper target-domain report capture is blocked, still emit `account_state` plus any route/state evidence gathered from favorites, recent items, settings, and autocomplete.
- Do not silently fake missing report sections. Emit empty arrays and explain the gap in `raw_artifacts.notes`.
