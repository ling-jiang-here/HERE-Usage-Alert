# HERE Usage Alert

Scheduled, organization-wide HERE usage anomaly monitoring with no hosted database or dashboard. It stores approved daily aggregates in `data/curated/`, generates Markdown reports in `reports/`, and can create a deduplicated GitHub Issue for a detected spike.

## Status

The processing MVP is runnable from a recorded fixture. Live HERE collection is intentionally blocked until the real Usage API request path, query parameter names, and response schema are verified against a redacted export.

## Local setup

1. Copy [.env.example](.env.example) to `.env` and populate the client ID and client secret.
2. Set `HERE_REALM_ID` to the organization realm ID.
3. Keep the documented default `HERE_USAGE_API_USAGE_PATH=/usage/realms/{realmId}` unless HERE changes the API contract.
4. Run the test suite:

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Run the fixture flow:

```sh
PYTHONPATH=src python3 -m usage_alert.main \
  --input tests/fixtures/usage-response.example.json \
  --date 2026-08-18
```

Run a live collection only after the API contract is verified:

```sh
PYTHONPATH=src python3 -m usage_alert.main --fetch --date 2026-08-18
```

The program uses OAuth client credentials to obtain a short-lived access token. It never logs the client secret or access token.

## HERE API Contract Gate

Before enabling the scheduled workflow, collect one completed UTC day from the HERE Usage Dashboard/export and record:

- The exact endpoint path and request query names, including the realm filter.
- The authentication scope, if the client needs one.
- The JSON response/pagination shape and report latency.
- A redacted response fixture that reconciles to the HERE dashboard total.

The current integration targets Cost Management Usage API v2 at `https://usage.bam.api.here.com/v2`, using `GET /usage/realms/{realmId}` with day-level detail and `appId`, `billingTag`, and `project` groups. Update [src/usage_alert/normalize.py](src/usage_alert/normalize.py) only if HERE changes its documented response schema.

## GitHub Actions

The workflow is at [.github/workflows/usage-monitor.yml](.github/workflows/usage-monitor.yml). Add these repository secrets before enabling it:

- `HERE_USAGE_API_BASE_URL`
- `HERE_REALM_ID`
- `HERE_USAGE_API_CLIENT_ID`
- `HERE_USAGE_API_CLIENT_SECRET`
- `HERE_OAUTH_TOKEN_URL`
- `HERE_OAUTH_SCOPE` (optional, but create it as an empty secret if no scope is required)
- `HERE_USAGE_API_USAGE_PATH`
- `ALERT_WEBHOOK_URL` (optional generic HTTPS endpoint for anomaly delivery)

It runs daily at 08:20 UTC and can be manually dispatched for a historical date. It commits only curated aggregate CSV and Markdown reports; raw API responses are not committed or uploaded. When an anomaly is found, it POSTs one JSON payload to `ALERT_WEBHOOK_URL` and creates or updates the corresponding GitHub Issue.

## Alert Semantics

For each metric and available dimension set, the monitor requires 14 prior daily observations. It compares the target day with the previous 30 days using median and median absolute deviation (MAD). A spike must pass both the percentage/absolute thresholds and a robust z-score threshold. When MAD is zero, the configured absolute increase rule prevents divide-by-zero and low-volume noise.

An alert identifies contributing dimensions, not root cause. Deployment, retry, caching, and credential-leak explanations remain unverified hypotheses until application telemetry is correlated.