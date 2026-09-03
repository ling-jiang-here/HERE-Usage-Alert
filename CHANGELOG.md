# Changelog

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
