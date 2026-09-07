# Changelog

## 2026-09-07

### Added

- Added a GitLab CI/CD pipeline (`.gitlab-ci.yml`) running in the `python:3.12` image. `usage_monitor_daily` fetches and analyzes the requested/completed UTC usage day (`--fetch`, optional `USAGE_DATE`, optional `TEST_WEBHOOK` smoke test) and `usage_monitor_hourly` checks the last 65 minutes (`--fetch --hourly`). Both jobs run `load_dotenv()`-independent of any `.env` file, read credentials from GitLab CI/CD variables (`HERE_ACCESS_KEY_ID`, `HERE_ACCESS_KEY_SECRET`, `HERE_CLIENT_ID`, `ALERT_WEBHOOK_URL`, remediation flags), and auto-commit generated `data/` and `reports/` changes back to the current branch using the `CI_JOB_TOKEN` push URL. Jobs are gated on scheduled `RUN_TYPE` (`daily` or `hourly`).

### Changed

- Renamed the legacy fallback credential environment variables from `HERE_MONITOR_ACCESS_KEY_ID`/`HERE_MONITOR_ACCESS_KEY_SECRET` to `HERE_ACCESS_KEY_ID`/`HERE_ACCESS_KEY_SECRET` in `client.py` (canonical lowercase `here.access.key.id`/`here.access.key.secret` names take precedence when both are set).
- GitHub Actions workflows `usage-monitor.yml` and `usage-monitor-hourly.yml` now pass the canonical lowercase names `here.client.id`, `here.access.key.id`, and `here.access.key.secret` into the job environment (from `HERE_CLIENT_ID`, `HERE_ACCESS_KEY_ID` repo variables and `HERE_ACCESS_KEY_SECRET` secret), instead of the legacy `HERE_MONITOR_*` names.
- Updated `.env.example` and README to document `HERE_ACCESS_KEY_ID`/`HERE_ACCESS_KEY_SECRET` as the legacy CI forms (the old `HERE_MONITOR_*` names are no longer read by the client). Updated the GitHub Actions setup section to reference the renamed variables and to point to the GitLab CI as the primary scheduled runner.

### Tests

- Manually verified the GitLab CI/CD pipeline and schedules on `https://main.gitlab.in.here.com/jiang1/usage-monitor`: both daily and hourly scheduled jobs run and complete successfully, credentials are injected from CI/CD variables, and generated `data/`/`reports/` changes are committed back to `main` by the jobs.

## 2026-09-06

### Added

- Imported HERE Usage Alert rules: `HereUsageClient.fetch_usage_alert_rules()` reads `GET /v1/realm/{realm}/rules`, and `rules.py` parses, persists (`data/usage-alert-rules.json`), and evaluates them against the monitored day's usage. Every daily and hourly run refreshes the rules and falls back to the stored copy when the API is unreachable. Crossed rules surface in reports and webhook payloads as `rule_alert_count`/`rule_alerts`. Notifications always use the project `ALERT_WEBHOOK_URL`; emails/webhooks configured on the imported HERE rules are never contacted. Added `--rules` (refresh/list) and `--test-rules` (synthetic smoke test posting to the project webhook only).
- Realm auto-discovery: when `HERE_REALM_ID` is unset, `HereUsageClient` now introspects `GET /app/me/authorization` (documented in HERE Account v1 APIs as "Introspect application authorizations") to resolve the realm of the shared app from the credential, validating it against `here.client.id`/`HERE_CLIENT_ID` when configured. This lets the monitor and `--check-account` run from the shared app credentials with no realm ID in `.env`; setting `HERE_REALM_ID` still overrides discovery.
- Added `--check-account`, which classifies the realm as a developer (Base Plan) or named/partner account using the BAM Customer API subscriptions and their licensed products plus the monitor app's IAM plans. This makes the Usage Alert eligibility signal (advanced features such as usage alerts are only granted to named/partner plans) available from the CLI without a portal login.
- Added `HereUsageClient.fetch_bam_subscriptions()`, `fetch_bam_subscription_products()`, and `fetch_app_authorization()` backed by a shared `_request_json` helper; BAM arbitrary-endpoint probing confirmed `GET /v1/subscriptions/{id}/products` works with the monitor token while realm-level Authorization API plan/limit endpoints are not readable.

### Changed

- The shared lowercase credential names `here.client.id`, `here.access.key.id`, and `here.access.key.secret` are now the canonical forms and take precedence over the legacy `HERE_CLIENT_ID`, `HERE_MONITOR_ACCESS_KEY_ID`, and `HERE_MONITOR_ACCESS_KEY_SECRET` names, which remain supported as fallbacks (needed in GitHub Actions, whose variable/secret names cannot contain dots). `remediate.py`'s monitor-app-id comparison now reads the canonical name first as well, and `.env.example` documents the lowercase names as primary with the legacy forms and optional `HERE_REALM_ID` as overrides.
- GitHub Actions workflows `usage-monitor.yml` and `usage-monitor-hourly.yml` no longer read a `HERE_REALM_ID` repository variable (the realm is auto-discovered in CI) and now pass `HERE_CLIENT_ID`; they continue to use the legacy `HERE_MONITOR_*` names because repository variable and secret names cannot contain dots. The hourly workflow now also keeps `data/usage-alert-rules.json` current by committing it with the other generated `data/` files.

### Tests

- Added account classification tests covering no/terminated/active subscriptions, free vs commercial products, case-insensitive developer markers, marker overrides, and IAM plan linkage.
- Added client tests covering realm auto-discovery plus client-id mismatch rejection (canonical environment names), canonical-vs-legacy precedence, lowercase credential names, legacy-name fallback, the Usage Alert rules, BAM and app/authorization request URLs, query parameters, and structured `HTTPError` surfacing with correlation ID.
- Added `tests/test_rules.py` covering rule parsing/validation, active status, absolute-threshold selection, query-condition matching, evaluation (crossing, below-threshold, inactive, non-daily durations, summed series), synthetic over-threshold records, and JSON round-tripping via `data/usage-alert-rules.json`. `test_notify` covers rule-alert payload fields and that only the project webhook is contacted; `test_main` covers `--rules` and `--test-rules` smoke behavior.

## 2026-09-03

### Fixed

- Stopped project-based remediation from re-announcing "service restriction was restored" on every run once a managed app is already fully restored. The recovery note now fires only on the run where the project actually transitions back to allowing all valid service resources. This resolves the duplicate restore note sent for app `So9MjdlTqdm9g3PM9xfO` on both 2026-09-01 and 2026-09-02.
- Kept `RemediationResult.triggered` as `False` on such idempotent no-op runs so no restoration is reported when nothing changed.

### Tests

- Added a regression test covering an existing managed project that already allows all valid service resources, asserting no restore note is emitted and `triggered` stays `False`.

## 2026-09-01

### Changed

- Confirmed daily usage fetches query the requested UTC usage date with a full-day window from `00:00:00Z` to `23:59:59Z`.
- Renamed managed service-restriction projects to follow `Service Restriction - {app name} - {app ID}` for new and reused projects.
- Added recovery behavior so project-based remediation restores all valid service resources when a managed app no longer has current over-free-tier usage.
- Ensured zero-usage healthy daily runs still invoke project service-access recovery.
- Included remediation recovery notes in healthy webhook payloads.
- Made managed project metadata updates best-effort so service restoration can continue if project rename/description updates fail.
- Fixed managed project description parsing for the current `to within-free-tier services` description format.
- Added regression tests for usage query date ranges, zero-record recovery, healthy webhook remediation notes, managed project naming, legacy project recovery, and managed description parsing.

### Operations

- Updated HERE project `hrn:here:authorization::org572296711:project/ua-03e1b55d6906a` to `Service Restriction - HERE TEST - So9MjdlTqdm9g3PM9xfO`.
- Added `hrn:here:service::olp-here:fuel-prices-3` back to that project after the Fuel Prices free-tier overage cleared.
- Verified the project contains all 27 available service resources and has no missing available services.
