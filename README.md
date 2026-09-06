# HERE Usage Alert

Scheduled, organization-wide HERE usage monitoring with no hosted database or dashboard. Each run fetches usage from the HERE Cost Management Usage API v2, stores analysis data under `data/`, writes reports under `reports/`, and checks for abnormal spikes. The GitHub Actions workflows commit those generated files back to the repository so the history stays available for traffic analysis.

## Quick Start

1. Copy [.env.example](.env.example) to `.env` and set `here.client.id`, `here.access.key.id`, and `here.access.key.secret`. `HERE_REALM_ID` is not required: the client discovers the realm from the shared app credential by introspecting `GET /app/me/authorization` on the HERE Account API. Setting `HERE_REALM_ID` still overrides discovery, and the legacy `HERE_CLIENT_ID`, `HERE_MONITOR_ACCESS_KEY_ID`, and `HERE_MONITOR_ACCESS_KEY_SECRET` names remain supported (the lowercase canonical names take precedence when both are set). The example also includes optional remediation and alerting settings.
2. Configure optional remediation using the [Remediation flags](#remediation-flags) below.
3. Run the test suite:

   ```sh
   PYTHONPATH=src python3 -m unittest discover -s tests -v
   ```

4. Run against a recorded fixture:

   ```sh
   PYTHONPATH=src python3 -m usage_alert.main \
     --input tests/fixtures/usage-response.example.json \
     --date 2026-08-18
   ```

5. Run a live collection:

   ```sh
   PYTHONPATH=src python3 -m usage_alert.main --fetch --date 2026-08-18
   ```

6. Classify the realm as a developer or named/partner account:

   ```sh
   PYTHONPATH=src python3 -m usage_alert.main --check-account
   ```

7. Refresh and list the imported usage alert rules from the HERE Usage Alert API:

   ```sh
   PYTHONPATH=src python3 -m usage_alert.main --rules
   ```

8. Smoke-test the imported rules with synthetic over-threshold usage and POST a webhook to the project endpoint only:

   ```sh
   PYTHONPATH=src python3 -m usage_alert.main --test-rules
   ```

   The payload is printed to stdout so you can compare it with what arrives at the alert webhook.

The client authenticates with OAuth client credentials and never logs the client secret or access token. It targets `GET /usage/realms/{realmId}` at `https://usage.bam.api.here.com/v2` with day-level detail and `appId`, `billingTag`, and `project` groups; update [src/usage_alert/normalize.py](src/usage_alert/normalize.py) only if HERE changes its response schema.

The Usage API, OAuth token, and HERE IAM endpoint URLs are fixed in the implementation. No endpoint URL or OAuth scope setting is required in `.env`; usage requests use the default `cold` channel. The active local settings are listed in [.env.example](.env.example).

## Account type check

Advanced features such as HERE Usage Alerts are granted only to named user and partner plans; developer (Base Plan) accounts are not eligible. `--check-account` calls the BAM Customer API (`GET /v1/subscriptions` then `GET /v1/subscriptions/{id}/products` at `https://customer.bam.api.here.com/v1`) and the monitor app's IAM authorization, then classifies the realm as `developer` or `named_or_partner`:

- No BAM subscription, or no active subscription, means a developer/Base Plan realm.
- An active subscription product whose name contains none of the developer markers counts as a commercial product and classifies the realm as `named_or_partner`.
- Otherwise the realm is `developer` when it only carries free-tier products (for example `HERE SDK Explore Edition`) unless the monitor app is linked to IAM plans, which also classifies as `named_or_partner`.

The developer/free product markers are `DEFAULT_DEVELOPER_PRODUCT_MARKERS` in [src/usage_alert/account.py](src/usage_alert/account.py); update them if HERE's product naming changes. The newer BAM model bills even free tiers through subscriptions, so an active subscription alone does not prove a named/partner account.

## Imported Usage Alert rules

Named/partner realms can configure HERE Usage Alert rules in the HERE portal; developer realms get `403 readRules` and no rules are imported. The monitor imports them from `GET /v1/realm/{realmId}/rules` at `https://alert.usage.hereapi.com/v1` (`HereUsageClient.fetch_usage_alert_rules`).

- Every daily and hourly monitoring run refreshes the rules and writes them to `data/usage-alert-rules.json`; if the refresh fails it falls back to the last stored copy. The hourly workflow therefore keeps the imported rules current in the repository.
- Rules are applied by matching each active daily rule's `appId`/`featureId`/`billingTag` query conditions against the monitored day's usage and summing the matched series against the rule's absolute threshold. Matches (and their proposed remediation) surface in the markdown reports and the webhook payload as `rule_alert_count` / `rule_alerts`.
- Notifications always go to the project `ALERT_WEBHOOK_URL` only. The emails or webhook configured on the imported HERE rules are never contacted by this tool.
- `--rules` refreshes and prints the stored rules; `--test-rules` synthesizes one over-threshold record per active rule, runs the evaluation path, prints the webhook payload, and POSTs it to the project webhook as a smoke test.

## Remediation flags

`HERE_AUTO_DISABLE_APP_CREDENTIALS` and `HERE_LIMIT_APP_TO_WITHIN_FREE_TIER_PROJECT` are both disabled by default in `.env.example`:

- `HERE_AUTO_DISABLE_APP_CREDENTIALS=true` disables enabled API keys and non-monitor OAuth access keys for every app associated with a service whose month-to-date usage exceeds its configured free tier. It is used only when project mode is disabled.
- `HERE_LIMIT_APP_TO_WITHIN_FREE_TIER_PROJECT=true` takes precedence over credential disabling. For each app using an exceeded service, the monitor creates or reuses a persistent project named `Service Restriction - {app name} - {app ID}`, removes stale service links, links all valid HERE service resources except the exceeded service(s), sets `scopeAccess=thisProjectOnly`, ensures app membership, and makes the project the app's restricted default scope. When a later month has no current overage for a managed app, its valid service access is restored while the project is retained for reuse.

Project mode requires HERE permissions to read and manage the target app and project. Resources with no resource home in the realm are skipped and reported; the monitor never silently replaces an incomplete allowlist with unrestricted access and does not fall back to credential disabling.

Daily and hourly usage data are generated the same way for local runs and scheduled runs. The project prunes older files automatically: reports are kept for the last 90 days, and analysis data is retained only as long as needed for the configured history window, with a 90-day floor.

## GitHub Actions

Two workflows run the same CLI on a schedule and can also be dispatched manually:

- [usage-monitor.yml](.github/workflows/usage-monitor.yml): daily at 08:20 UTC. Accepts a historical `usage_date` input. It writes the daily analysis files and report, commits generated `data/` and `reports/` changes back to the current branch, and sends a webhook for both alerting and healthy completion events.
- [usage-monitor-hourly.yml](.github/workflows/usage-monitor-hourly.yml): hourly at :20. Checks usage from the last 65 minutes, stores the rolling-window result under the current UTC hour, writes hourly analysis files and any alert report, commits generated `data/` and `reports/` changes back to the current branch, and sends a webhook for alerting and healthy completion events. It still skips markdown report generation when the checked window is healthy.

GitHub repository secrets and variables names cannot contain dots, so the workflows pass the credentials under the legacy `HERE_*` names and the client falls back to them in CI. Add this repository secret: `HERE_MONITOR_ACCESS_KEY_SECRET`.

Add these repository variables: `HERE_CLIENT_ID`, `HERE_MONITOR_ACCESS_KEY_ID`, `HERE_AUTO_DISABLE_APP_CREDENTIALS`, `HERE_LIMIT_APP_TO_WITHIN_FREE_TIER_PROJECT`, `ALERT_WEBHOOK_URL`. The realm is auto-discovered in CI, so no `HERE_REALM_ID` variable is needed.

To verify webhook delivery without querying HERE, manually run **HERE Usage Monitor** with `test_webhook` selected; it sends one synthetic critical event (`metric: synthetic_webhook_test`).

The webhook payload is a compact JSON event, not a copy of the markdown report: it carries `report_path` as a reference plus only the anomaly, quota-alert, and imported-rule-alert summary fields (see [src/usage_alert/notify.py](src/usage_alert/notify.py)), while the full per-metric usage table and free-tier breakdown stay in the markdown report file. Seeing different content between the two is expected.

## Detection and Alerts

For each metric and dimension set, the monitor requires 14 prior daily observations, then compares the target period with the prior 30 days using median and median absolute deviation (MAD). A spike must pass both the percentage/absolute-increase thresholds and a robust z-score threshold; when MAD is zero, a configured minimum absolute increase avoids divide-by-zero and low-volume noise. An alert identifies contributing dimensions, not root cause — deployment, retry, caching, and credential-leak explanations remain unverified hypotheses until corroborated by application telemetry.

Each daily report also includes month-to-date transaction totals for services configured in `config/free_tiers.json`: `APPROACHING` at 80% of the free-tier allowance and `EXCEEDED` at 100%. DataStorage records count toward Data IO totals within their matching billing unit; non-comparable units stay in the usage summary only.

## Reference

Current public HERE Base Plan free-tier allowances are recorded in [docs/here-base-plan-free-tiers.md](docs/here-base-plan-free-tiers.md). This reference is dated and must be checked against HERE's pricing page and the organization's agreement before use in billing decisions.

The current Webhook endpoint for receiving and checking the alers:  
- Receiving: https://usewebhook.com/8c9daaacaa7ddc4ff44cc6443109039c
- Checking: https://usewebhook.com/?id=8c9daaacaa7ddc4ff44cc6443109039c
