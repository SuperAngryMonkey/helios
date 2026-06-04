# 0002 — Flask, not Grafana

Date: 2026-06-04 · Status: Accepted

## Context

After Postgres was filling with telemetry, we needed a visualization
layer. Default reach in this corner of the industry is Grafana — and we
did install it and stand up a provisioned dashboard.

## Options considered

1. **Grafana** with provisioned datasource + dashboard JSON.
2. **Flask app** with Chart.js, served from the same LXC.
3. Both (Grafana for deep dives, Flask for daily glance).

## Decision

Option 2: Flask.

## Rationale

- Consistency with the rest of the SuperAngryMonkey project ecosystem.
  watchmen, deathwobble, precious, argus, sommelier, photosith all use
  Flask + Monkey Theme. Grafana breaks the house style.
- One LXC running fewer components.
- Code lives in the same repo as the daemon — one deploy, one CI target.
- For a single Wanderer with low data rate, most of Grafana's strengths
  (multi-datasource, templating, alerting at scale, ad-hoc explore mode)
  are unused.
- Grafana 13's new provisioning module is unstable in practice — our
  standard YAML was rejected with misleading "data source not found"
  errors. Net cost of using Grafana exceeded the net cost of writing
  Flask.

## What Grafana would do better (kept for future reference)

- Time range controls with click-and-drag zoom.
- Ad-hoc query mode for slicing data we didn't pre-design dashboards for.
- Alerting with built-in routing (PagerDuty / Slack / webhook).
- Multi-datasource dashboards (helpful when collecting from many sites).
- Annotations overlaid on timeseries.

These are reserved for **Heimdall** (the FastAPI gateway), where the
multi-tenant collection and alerting cases are real.

## Consequences

- helios ships its own UI code. CSS is pinned from
  `.shared/monkey-theme.css`; sync workflow is `scp` from the canonical
  copy on each update.
- No alerting yet. To be added in a future iteration as a simple
  threshold checker + webhook poster.
