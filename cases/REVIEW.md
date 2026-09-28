# Usage Review: CS0184870 (org428045468)

## What We Found

We reviewed the usage data for customer (subscription A-S00080056) covering July through September 2026. The account uses four HERE platform services: Geocode & Reverse Geocode, Time Aware Routing, Routing Truck, and Tour Planning.

The review identified several days where usage jumped sharply above normal levels:

- **Tour Planning** saw a massive spike on August 31, reaching 13,443 calls against a typical range of 14–757. This single day accounted for the bulk of unexpected consumption. Three other days in the same service also ran well above normal.
- **Time Aware Routing** showed two days (September 16–17) with usage roughly 8–14 times the usual level.
- **Routing Truck** and **Geocode** had smaller early-period bumps that settled back to normal.

## Why It Was Missed

The monitoring app was configured to flag unusual usage only after a service had at least 14 days of history, and only when the increase was both large in volume and statistically significant. This worked well for established services but meant newer or sparsely used services — like the ones in this account — could experience serious spikes before the app had enough data to notice. The Tour Planning spike on August 31 occurred after only 7 days of usage history, so it was never flagged.

## What We Changed

We added a second, more sensitive safety net to the monitoring app. When a service has a shorter track record (as little as 3 days), the app now compares each day's usage against the recent average and raises an alert if it exceeds five times that average — regardless of the absolute volume. This catches dramatic spikes on new or low-volume services that the original rules would have overlooked, while the original rules continue to protect established services from smaller but still meaningful increases.

## Expected Outcome

With this change in place, the August 31 Tour Planning spike — and the other anomalies listed above — would have been flagged on the day they occurred, allowing the team to investigate and respond before similar unexpected usage recurs.

---

# Usage Review: CS0185043 (org161809193)

## What We Found

We reviewed the usage data for customer (subscription A-S00075754) covering late June through early September 2026. The account uses several HERE platform services under an "Asset Management" plan, with the heaviest consumption in Map Attributes, Geocode, Speed Limits, and Route Matching.

The review identified a sustained period of unexpected usage beginning around August 18 and continuing through the end of the month:

- **Map Attributes** jumped from a typical daily range of 2,000–9,000 to 168,638 on August 20, then escalated sharply to over 11 million by August 22 — a roughly 2,500-fold increase over the prior baseline.
- **Geocode & Reverse Geocode** and **Speed Limits** both spiked on August 18–20, rising from a baseline of around 3,000 to over 550,000 in a single day.
- **Route Matching** showed a similar pattern, climbing from roughly 150 to over 160,000 on August 22.

The escalation was gradual at first — a slow ramp over several days — before reaching peak levels, which made it harder to distinguish from normal growth without close monitoring.

## Why It Was Missed

The monitoring app compared each day's usage against a baseline calculated from the previous 30 days. Because the account had a period of very high usage in late June and early July (with daily volumes in the hundreds of thousands to over a million), that older data remained inside the 30-day baseline window well into August. When usage dropped sharply in mid-July and then began climbing again in August, the baseline was still inflated by the stale high-usage period. As a result, the early ramp-up days — when usage was 30 to 40 times above the recent norm but still below the stale 30-day average — did not trigger alerts. The app only began flagging once the spike grew large enough to exceed the inflated baseline.

## What We Changed

We adjusted how the monitoring app calculates its baseline. Instead of relying on a single 30-day average, the app now computes its baseline from the most recent 7 days of usage, while still requiring at least 14 days of overall history before raising alerts. This ensures the baseline reflects current behavior rather than being skewed by a high-usage period from weeks earlier. Combined with the secondary safety net added during the CS0184870 review — which flags any day where usage exceeds five times the recent average even on newer services — the app now catches both sudden spikes and gradual escalations from the first day they occur.

## Expected Outcome

With these changes in place, the August 18 escalation in Geocode and Speed Limits — and the August 20–22 Map Attributes surge — would have flagged on the first day they deviated from normal, giving the team a 2–4 day earlier warning before peak levels were reached.

---

# Usage Review: CS0181837 (org281898805)

## What We Found

We reviewed the usage data for customer (realm org281898805) covering late June through late September 2026. The account uses several HERE platform services across multiple applications, with the heaviest consumption in Vector Tile, Geocode, and Time Aware Routing.

The review identified a sharp, short-lived spike in early July:

- **Time Aware Routing** jumped from a steady baseline of roughly 2,500–3,100 calls per day to 983,822 on July 1, followed by 478,175 on July 2 and 95,980 on July 3, before returning to normal on July 4. This was a one-time burst roughly 300 times the normal level.
- **Routing Car, Bicycle, Pedestrian** showed a similar pattern on July 1, spiking from a typical 40–70 calls to 4,239 in a single day before immediately settling back.

The rest of the account's usage was stable. Several new applications were onboarded in August with gradually increasing volumes — this is expected ramp-up behavior for new services and was correctly not flagged.

## Why It Was Not Missed

The monitoring app successfully identified both spikes on the day they occurred. The existing detection rules — which compare each day's usage against a rolling baseline and flag statistically significant increases — were sufficient here because the affected services had weeks of stable history before the spike, and the magnitude of the increase (300x and 60x respectively) far exceeded any normal variation.

## What We Changed

No code changes were required for this case. The detection logic already in place — including the secondary safety net and shorter baseline window added during the CS0184870 and CS0185043 reviews — correctly flagged the unexpected usage without producing false positives on the new services that were ramping up normally.

## Expected Outcome

The app continues to provide reliable coverage across all three cases reviewed. Sudden spikes on established services, gradual escalations after quiet periods, and dramatic surges on new or low-volume services are all caught on the day they occur.

---

# Usage Review: CS0185184 (org754313293)

## What We Found

We reviewed the usage data for customer (realm org754313293) covering July through early September 2026. The account uses several HERE platform services, with the heaviest consumption in Traffic, Destination Weather, Toll Cost, and Time Aware Routing.

The review identified a sustained period of rapid growth in the Traffic service:

- **Traffic** began on July 17 with 3,834 calls and grew steadily over the following weeks, reaching 84,537 calls per day by August 8 — a roughly 22-fold increase in under three weeks. Unlike a sudden spike, the growth was gradual: each day was only modestly higher than the one before, making it difficult to distinguish from normal ramp-up without careful tracking.
- **Destination Weather** showed a similar but milder pattern, growing from 112 calls per day in early July to around 1,150 by mid-August.

The rest of the account's usage was stable, with no other significant anomalies.

## Why It Was Missed

The monitoring app compared each day's usage against a rolling baseline of the previous 7 days. Because the Traffic service was growing steadily, the baseline adapted to the new level within a week, and each subsequent day looked normal by comparison. The app did flag a few days in early August as warnings, but missed the overall growth pattern — the baseline was chasing the growth instead of recognizing it as unusual.

## What We Changed

We added a week-over-week growth check to the monitoring app. In addition to comparing each day against the recent baseline, the app now also compares today's usage against the same day one week ago. If usage has grown by more than 3x week-over-week (and the absolute increase exceeds 1,000 calls), the app raises an alert. This catches sustained growth that the rolling baseline would otherwise absorb. A minimum absolute threshold ensures the check does not fire on low-volume services where small numbers can produce large percentage swings.

## Expected Outcome

With this change in place, the Traffic service's rapid growth would have been flagged as early as July 27 — the first day usage exceeded 3x the prior week's level — giving the team a two-week warning before the service reached its peak. The app now catches sudden spikes, gradual escalations after quiet periods, dramatic surges on new services, and sustained week-over-week growth.

---

# Usage Review: CS0182583 (org57970955)

## What We Found

We reviewed the usage data for customer (subscription A-S00077177) covering late June through late August 2026. The account uses several HERE platform services, with the heaviest consumption in Geocode & Reverse Geocode, Advanced Raster Tile, Toll Cost, and Routing Truck.

The review identified a sustained period of elevated Geocode usage beginning in mid-July:

- **Geocode & Reverse Geocode** jumped from a typical daily range of 29–2,279 calls to 22,589 on July 11, peaked at 59,372 on July 13, and remained elevated (10,000–31,000 per day) through the end of July and into August. This was a roughly 10- to 200-fold increase over the prior baseline.
- **Advanced Raster Tile** showed a similar pattern starting July 29, rising from a baseline of around 24–747 to over 2,200 per day.
- **Toll Cost** and **Routing Truck** showed smaller increases in late July, rising from single digits to 46–77 calls per day.

## Why It Was Not Missed

The monitoring app successfully identified the Geocode spike starting on July 11 — the first day usage exceeded 100x the recent baseline. The existing detection rules were sufficient here because the service had several weeks of stable, low-volume history before the spike, and the magnitude of the increase far exceeded any normal variation.

## What We Changed

No code changes were required for the main anomaly. However, we did refine the secondary safety net to reduce noise on very low-volume services. Previously, the secondary rule would flag any day where usage exceeded five times the recent average, even if the absolute increase was trivial (e.g., 19 calls vs a baseline of 1). We added a minimum absolute threshold of 100 calls to the secondary rule, so it now only fires when the increase is both proportionally and absolutely significant. This filters out noise from services like Toll Cost and Routing Truck, where small numbers can produce large percentage swings that are not meaningful in practice.

## Expected Outcome

The app now catches the Geocode spike from its first day while producing fewer false alarms on low-volume services. Across all five cases reviewed, the app covers sudden spikes, gradual escalations, dramatic surges on new services, sustained week-over-week growth, and now does so with reduced noise on services where small absolute numbers would otherwise trigger alerts.
