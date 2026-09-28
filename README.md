# HERE Usage Alert

Scheduled, organization-wide HERE location-services usage monitoring with no hosted database or dashboard. Each run fetches usage from the HERE Cost Management Usage API v2, stores analysis data under `data/`, writes reports under `reports/`, and checks for abnormal spikes. The CI/CD pipelines commit those generated files back to the repository so the history stays available for traffic analysis.

## Features

- **Multi-strategy anomaly detection** — Combines four complementary detection strategies to catch different types of unexpected usage:
  - **Primary spike detection** — Compares each metric/dimension against a rolling 7-day baseline using median and median absolute deviation (MAD). A spike must pass percentage/absolute-increase thresholds and a robust z-score threshold.
  - **Secondary spike detection** — For services with shorter track records (as little as 3 days), flags any day where usage exceeds 5x the recent average and the absolute increase is at least 100 calls. This catches dramatic spikes on new or low-volume services that the primary rule would overlook.
  - **Week-over-week growth detection** — Compares today's usage against the same day one week ago. If usage has grown by more than 3x (and the absolute increase exceeds 1,000 calls), raises an alert. This catches sustained growth that the rolling baseline would otherwise absorb.
  - **Baseline window** — Uses the most recent 7 days for baseline calculation instead of the full 30-day window, ensuring the baseline reflects current behavior rather than being skewed by stale high-usage periods from weeks earlier.
- **Free-tier quota tracking** — Month-to-date transaction totals for services configured in `config/free_tiers.json`, with `APPROACHING` (80%) and `EXCEEDED` (100%) alerts.
- **HERE Usage Alert rules** — Imports rules configured in the HERE portal and evaluates them against monitored usage each run.
- **Auto-remediation** — Optionally disables API credentials or restricts app project scope when free-tier limits are exceeded.
- **Webhook notifications** — Sends compact JSON events for anomalies, quota alerts, rule alerts, and healthy completions.
- **Self-hosting** — The Git repository is the database, the CI scheduler is the cron, the Markdown reports are the dashboard, and the webhook is the alerting channel.
- **Support ticket case studies** — Real usage data from HERE support tickets under `cases/`, with analysis of how each anomaly was detected (or missed) and the resulting improvements to the detection logic.

## Project Layout

```
src/usage_alert/
  main.py          CLI orchestration
  client.py        HERE API HTTP client (OAuth1, realm discovery)
  normalize.py     Schema normalization/validation
  models.py        Dataclass models
  config.py        Config loading
  detect.py        Multi-strategy anomaly detection
  quota.py         Free-tier quota evaluation
  rules.py         HERE Usage Alert rules import/evaluation
  account.py       Account type classification
  notify.py        Webhook payload builders + sender
  report.py        Markdown report rendering
  storage.py       CSV/JSON persistence + pruning
  remediate.py     Auto-remediation (credential disable + project scope)

config/
  thresholds.json  Anomaly detection thresholds
  free_tiers.json  HERE Base Plan free-tier allowances

cases/             Real support ticket usage data + analysis (see cases/REVIEW.md)
tests/             unittest suite (11 test files)
docs/              Reference documentation
```

## Setup

### Prerequisites

- Python >= 3.12
- HERE platform account with API credentials

### Installation

```sh
pip install -e .
```

### Configuration

1. Copy [.env.example](.env.example) to `.env` and set `here.client.id`, `here.access.key.id`, and `here.access.key.secret`. `HERE_REALM_ID` is not required: the client discovers the realm from the shared app credential by introspecting `GET /app/me/authorization` on the HERE Account API. Setting `HERE_REALM_ID` still overrides discovery, and the legacy `HERE_CLIENT_ID`, `HERE_ACCESS_KEY_ID`, and `HERE_ACCESS_KEY_SECRET` names remain supported (the lowercase canonical names take precedence when both are set). The example also includes optional remediation and alerting settings.

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

## GitHub Actions Integration

Two workflows run the same CLI on a schedule and can also be dispatched manually:

- [usage-monitor.yml](.github/workflows/usage-monitor.yml): daily at 08:20 UTC. Accepts a historical `usage_date` input. It writes the daily analysis files and report, commits generated `data/` and `reports/` changes back to the current branch, and sends a webhook for both alerting and healthy completion events.
- [usage-monitor-hourly.yml](.github/workflows/usage-monitor-hourly.yml): hourly at :20. Checks usage from the last 65 minutes, stores the rolling-window result under the current UTC hour, writes hourly analysis files and any alert report, commits generated `data/` and `reports/` changes back to the current branch, and sends a webhook for alerting and healthy completion events. It still skips markdown report generation when the checked window is healthy.

### Repository Secrets and Variables

GitHub repository secrets and variables names cannot contain dots, so the workflows read the credentials from repository variables/secrets and pass them into the job under the canonical lowercase names.

**Secret:**

| Name | Description |
|------|-------------|
| `HERE_ACCESS_KEY_SECRET` | HERE OAuth access key secret |

**Variables:**

| Name | Description |
|------|-------------|
| `HERE_CLIENT_ID` | HERE OAuth client ID |
| `HERE_ACCESS_KEY_ID` | HERE OAuth access key ID |
| `ALERT_WEBHOOK_URL` | Webhook endpoint for notifications |
| `HERE_AUTO_DISABLE_APP_CREDENTIALS` | Enable credential disabling (optional, default `false`) |
| `HERE_LIMIT_APP_TO_WITHIN_FREE_TIER_PROJECT` | Enable project-scope restriction (optional, default `false`) |

The realm is auto-discovered in CI, so no `HERE_REALM_ID` variable is needed.

### Manual Dispatch

To verify webhook delivery without querying HERE, manually run **HERE Usage Monitor** with `test_webhook` selected; it sends one synthetic critical event (`metric: synthetic_webhook_test`).

## GitLab CI/CD Integration

The project repository at [main.gitlab.in.here.com/jiang1/usage-monitor](https://main.gitlab.in.here.com/jiang1/usage-monitor) runs the monitor on a schedule via [.gitlab-ci.yml](.gitlab-ci.yml):

- `usage_monitor_daily`: daily usage fetch and analysis (optional `USAGE_DATE`, optional `TEST_WEBHOOK` smoke test).
- `usage_monitor_hourly`: hourly check of the last 65 minutes.

Both jobs run in the `python:3.12` image, read credentials from GitLab CI/CD variables, and auto-commit generated `data/`/`reports/` changes back to the current branch using the `CI_JOB_TOKEN` push URL.

### CI/CD Variables

Configure these under **Settings → CI/CD → Variables**:

| Name | Masked | Description |
|------|--------|-------------|
| `HERE_ACCESS_KEY_SECRET` | Yes | HERE OAuth access key secret |
| `HERE_ACCESS_KEY_ID` | No | HERE OAuth access key ID |
| `HERE_CLIENT_ID` | No | HERE OAuth client ID |
| `ALERT_WEBHOOK_URL` | No | Webhook endpoint for notifications |
| `HERE_AUTO_DISABLE_APP_CREDENTIALS` | No | Enable credential disabling (optional) |
| `HERE_LIMIT_APP_TO_WITHIN_FREE_TIER_PROJECT` | No | Enable project-scope restriction (optional) |

### Pipeline Schedules

Set up two pipeline schedules under **Settings → CI/CD → Schedules**:

| Schedule | `RUN_TYPE` | Description |
|----------|------------|-------------|
| Daily | `daily` | Runs `usage_monitor_daily` |
| Hourly | `hourly` | Runs `usage_monitor_hourly` |

## Remediation Flags

`HERE_AUTO_DISABLE_APP_CREDENTIALS` and `HERE_LIMIT_APP_TO_WITHIN_FREE_TIER_PROJECT` are both disabled by default in `.env.example`:

- `HERE_AUTO_DISABLE_APP_CREDENTIALS=true` disables enabled API keys and non-monitor OAuth access keys for every app associated with a service whose month-to-date usage exceeds its configured free tier. It is used only when project mode is disabled.
- `HERE_LIMIT_APP_TO_WITHIN_FREE_TIER_PROJECT=true` takes precedence over credential disabling. For each app using an exceeded service, the monitor creates or reuses a persistent project named `Service Restriction - {app name} - {app ID}`, removes stale service links, links all valid HERE service resources except the exceeded service(s), sets `scopeAccess=thisProjectOnly`, ensures app membership, and makes the project the app's restricted default scope. When a later month has no current overage for a managed app, its valid service access is restored while the project is retained for reuse.

Project mode requires HERE permissions to read and manage the target app and project. Resources with no resource home in the realm are skipped and reported; the monitor never silently replaces an incomplete allowlist with unrestricted access and does not fall back to credential disabling.

Daily and hourly usage data are generated the same way for local runs and scheduled runs. The project prunes older files automatically: reports are kept for the last 90 days, and analysis data is retained only as long as needed for the configured history window, with a 90-day floor.

## Detection and Alerts

For each metric and dimension set, the monitor applies four complementary detection strategies:

1. **Primary spike detection** — Requires 14 prior daily observations, then compares the target day against a rolling 7-day baseline using median and median absolute deviation (MAD). A spike must pass both the percentage/absolute-increase thresholds and a robust z-score threshold; when MAD is zero, a configured minimum absolute increase avoids divide-by-zero and low-volume noise.
2. **Secondary spike detection** — For services with shorter track records (as little as 3 days), flags any day where usage exceeds 5x the recent average and the absolute increase is at least 100 calls. This catches dramatic spikes on new or low-volume services that the primary rule would overlook.
3. **Week-over-week growth detection** — Compares today's usage against the same day one week ago. If usage has grown by more than 3x (and the absolute increase exceeds 1,000 calls), raises an alert. This catches sustained growth that the rolling baseline would otherwise absorb.
4. **Baseline window** — Uses the most recent 7 days for baseline calculation instead of the full 30-day window, ensuring the baseline reflects current behavior rather than being skewed by stale high-usage periods from weeks earlier.

An alert identifies contributing dimensions, not root cause — deployment, retry, caching, and credential-leak explanations remain unverified hypotheses until corroborated by application telemetry.

Each daily report also includes month-to-date transaction totals for services configured in `config/free_tiers.json`: `APPROACHING` at 80% of the free-tier allowance and `EXCEEDED` at 100%. DataStorage records count toward Data IO totals within their matching billing unit; non-comparable units stay in the usage summary only.

The webhook payload is a compact JSON event, not a copy of the markdown report: it carries `report_path` as a reference plus only the anomaly, quota-alert, and imported-rule-alert summary fields (see [src/usage_alert/notify.py](src/usage_alert/notify.py)), while the full per-metric usage table and free-tier breakdown stay in the markdown report file. Seeing different content between the two is expected.

## Account Type Check

Advanced features such as HERE Usage Alerts are granted only to named user and partner plans; developer (Base Plan) accounts are not eligible. `--check-account` calls the BAM Customer API (`GET /v1/subscriptions` then `GET /v1/subscriptions/{id}/products` at `https://customer.bam.api.here.com/v1`) and the monitor app's IAM authorization, then classifies the realm as `developer` or `named_or_partner`:

- No BAM subscription, or no active subscription, means a developer/Base Plan realm.
- An active subscription product whose name contains none of the developer markers counts as a commercial product and classifies the realm as `named_or_partner`.
- Otherwise the realm is `developer` when it only carries free-tier products (for example `HERE SDK Explore Edition`) unless the monitor app is linked to IAM plans, which also classifies as `named_or_partner`.

The developer/free product markers are `DEFAULT_DEVELOPER_PRODUCT_MARKERS` in [src/usage_alert/account.py](src/usage_alert/account.py); update them if HERE's product naming changes. The newer BAM model bills even free tiers through subscriptions, so an active subscription alone does not prove a named/partner account.

## Imported Usage Alert Rules

Named/partner realms can configure HERE Usage Alert rules in the HERE portal; developer realms get `403 readRules` and no rules are imported. The monitor imports them from `GET /v1/realm/{realmId}/rules` at `https://alert.usage.hereapi.com/v1` (`HereUsageClient.fetch_usage_alert_rules`).

- Every daily and hourly monitoring run refreshes the rules and writes them to `data/usage-alert-rules.json`; if the refresh fails it falls back to the last stored copy. The hourly workflow therefore keeps the imported rules current in the repository.
- Rules are applied by matching each active daily rule's `appId`/`featureId`/`billingTag` query conditions against the monitored day's usage and summing the matched series against the rule's absolute threshold. Matches (and their proposed remediation) surface in the markdown reports and the webhook payload as `rule_alert_count` / `rule_alerts`.
- Notifications always go to the project `ALERT_WEBHOOK_URL` only. The emails or webhook configured on the imported HERE rules are never contacted by this tool.
- `--rules` refreshes and prints the stored rules; `--test-rules` synthesizes one over-threshold record per active rule, runs the evaluation path, prints the webhook payload, and POSTs it to the project webhook as a smoke test.

## Support Ticket Case Studies

The `cases/` folder contains real usage data from HERE support tickets, along with analysis of how each anomaly was detected (or missed) and the resulting improvements to the detection logic. See [cases/REVIEW.md](cases/REVIEW.md) for the full write-up.

| Case | Customer | Anomaly | Detection |
|------|----------|---------|-----------|
| CS0184870 | NTT Data | Tour Planning spike (13,443 vs baseline 45) | Secondary spike rule |
| CS0185043 | Wireless Logic | Map Attributes surge (11M vs baseline 370K) | 7-day baseline window |
| CS0181837 | CTP | Time Aware Routing spike (983K vs baseline 2.7K) | Primary spike rule |
| CS0185184 | CAR1983 | Traffic 22x growth over 3 weeks | Week-over-week growth check |
| CS0182583 | ООО "К-авто" | Geocode spike (59K vs baseline 231) | Primary spike rule |

Each case study documents what was found, why it was missed (if applicable), what was changed in the detection logic, and the expected outcome. The cases folder serves as both a regression test suite and a record of how real-world usage patterns have shaped the project's evolution.

## Reference

Current public HERE Base Plan free-tier allowances are recorded in [docs/here-base-plan-free-tiers.md](docs/here-base-plan-free-tiers.md). This reference is dated and must be checked against HERE's pricing page and the organization's agreement before use in billing decisions.

The current Webhook endpoint for receiving and checking the alers:  
- Receiving: https://usewebhook.com/8c9daaacaa7ddc4ff44cc6443109039c
- Checking: https://usewebhook.com/?id=8c9daaacaa7ddc4ff44cc6443109039c
