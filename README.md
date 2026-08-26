# HERE Usage Alert

Scheduled, organization-wide HERE usage monitoring with no hosted database or dashboard. Each run fetches usage from the HERE Cost Management Usage API v2 and checks for abnormal spikes. Reports and CSV data are written only for local `--input` runs; live `--fetch` runs keep data in memory and do not upload artifacts, commit files, or create GitHub issues.

## Quick Start

1. Copy [.env.example](.env.example) to `.env` and set `HERE_REALM_ID`, the client ID, and the client secret. Keep the default `HERE_USAGE_API_USAGE_PATH=/usage/realms/{realmId}` unless HERE changes the API contract.
2. Run the test suite:

   ```sh
   PYTHONPATH=src python3 -m unittest discover -s tests -v
   ```

3. Run against a recorded fixture:

   ```sh
   PYTHONPATH=src python3 -m usage_alert.main \
     --input tests/fixtures/usage-response.example.json \
     --date 2026-08-18
   ```

4. Run a live collection:

   ```sh
   PYTHONPATH=src python3 -m usage_alert.main --fetch --date 2026-08-18
   ```

The client authenticates with OAuth client credentials and never logs the client secret or access token. It targets `GET /usage/realms/{realmId}` at `https://usage.bam.api.here.com/v2` with day-level detail and `appId`, `billingTag`, and `project` groups; update [src/usage_alert/normalize.py](src/usage_alert/normalize.py) only if HERE changes its response schema.

## GitHub Actions

Two workflows run the same CLI on a schedule and can also be dispatched manually:

- [usage-monitor.yml](.github/workflows/usage-monitor.yml): daily at 08:20 UTC. Accepts a historical `usage_date` input. In live mode it analyzes in memory and only sends a webhook when anomalies are found.
- [usage-monitor-hourly.yml](.github/workflows/usage-monitor-hourly.yml): hourly at :20. Checks the completed UTC hour against the same hour on prior days and only sends a webhook when an anomaly is found.

Add these repository secrets: `HERE_USAGE_API_CLIENT_ID`, `HERE_USAGE_API_CLIENT_SECRET`.

Add these repository variables: `HERE_USAGE_API_BASE_URL`, `HERE_REALM_ID`, `HERE_OAUTH_TOKEN_URL`, `HERE_OAUTH_SCOPE` (can be empty), `HERE_USAGE_API_USAGE_PATH`, `ALERT_WEBHOOK_URL`.

To verify webhook delivery without querying HERE, manually run **HERE Usage Monitor** with `test_webhook` selected; it sends one synthetic critical event (`metric: synthetic_webhook_test`).

## Detection and Alerts

For each metric and dimension set, the monitor requires 14 prior daily observations, then compares the target period with the prior 30 days using median and median absolute deviation (MAD). A spike must pass both the percentage/absolute-increase thresholds and a robust z-score threshold; when MAD is zero, a configured minimum absolute increase avoids divide-by-zero and low-volume noise. An alert identifies contributing dimensions, not root cause — deployment, retry, caching, and credential-leak explanations remain unverified hypotheses until corroborated by application telemetry.

Each daily report also includes month-to-date transaction totals for services configured in `config/free_tiers.json`: `APPROACHING` at 80% of the free-tier allowance and `EXCEEDED` at 100%. DataStorage records count toward Data IO totals within their matching billing unit; non-comparable units stay in the usage summary only.

## Reference

Current public HERE Base Plan free-tier allowances are recorded in [docs/here-base-plan-free-tiers.md](docs/here-base-plan-free-tiers.md). This reference is dated and must be checked against HERE's pricing page and the organization's agreement before use in billing decisions.