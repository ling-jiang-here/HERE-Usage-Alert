# HERE Base Plan Free Tiers

Source: [HERE Base Plan pricing](https://www.here.com/get-started/pricing)

Last inspected: 2026-08-19

These are the free monthly allowances rendered in HERE's public pricing details. They are a planning reference only; the organization agreement and HERE Platform Portal remain authoritative for billing and entitlement.

## Location Services

| Monthly free allowance | Services |
| --- | --- |
| 30,000 transactions | Vector; Advanced Vector; Raster; Advanced Raster; Map Image; Geocode and Reverse Geocode; Autocomplete; Routing Car, Bicycle, Pedestrian; Traffic Raster Tile; Traffic Vector Tile |
| 5,000 transactions | Discover / Search; EV Charge Points; Autosuggest; Time Aware Routing; Routing scooter / two wheel; Routing Taxi; Routing Truck; Routing Bus; Traffic; Public Transit; Network Positioning |
| 2,500 transactions | Speed Limits; Routing EV; Route Import; Toll Cost; Matrix Routing; Isoline Routing; Waypoints Sequence; Advanced Traffic; Intermodal Routing; Destination Weather |
| 500 transactions | Tour Planning |
| No free tier shown | Fuel Prices: pricing begins at 1 transaction |

The pricing page states that a transaction is generally counted per request, but some services have special rules. For example, Speed Limits can also count a Geocode & Reverse Geocode, Multi Reverse Geocode, or Lookup transaction; Matrix Routing is based on origins and destinations; and Tour Planning is based on locations processed. Consult the service's pricing details before using an allowance for billing forecasts.

## Data Services

| Service | Monthly free allowance |
| --- | --- |
| Data IO | 20 GB |

Data and storage values must not be added to location-service transaction counts. Preserve the HERE-reported unit (`Transactions`, `GB-Months`, `MB/S-Months`, and so on) and compare or summarize only within the same unit. The monitor treats HERE `DataStorage` records as Data IO/storage consumption, totaling values only within matching units.