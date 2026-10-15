# Results (limit 100 requests per 60 s)

## Boundary burst (100 requests at 59.9 s, 100 at 60.1 s)

| algorithm | accepted_of_200 | max_in_any_60s |
|---|---|---|
| fixed window | 200 | 200 |
| sliding log | 100 | 100 |
| sliding window counter | 100 | 100 |
| token bucket | 100 | 100 |
| GCRA | 100 | 100 |

## Two hours of bursty traffic at ~3x the limit

| algorithm | offered | accepted | utilisation_% | max_in_any_60s | worst_overshoot_% |
|---|---|---|---|---|---|
| fixed window | 96197 | 12001 | 100.0 | 197 | 97.0 |
| sliding log | 96197 | 11951 | 99.6 | 100 | 0.0 |
| sliding window counter | 96197 | 11876 | 99.0 | 102 | 2.0 |
| token bucket | 96197 | 12099 | 100.8 | 199 | 99.0 |
| GCRA | 96197 | 12099 | 100.8 | 199 | 99.0 |

## Memory per key

| algorithm | bytes_per_key |
|---|---|
| fixed window | 122 |
| sliding log | 4281 |
| sliding window counter | 129 |
| token bucket | 112 |
| GCRA | 88 |

## Decision speed (10,000 keys)

| algorithm | decisions_per_s |
|---|---|
| fixed window | 2851635 |
| sliding log | 1860618 |
| sliding window counter | 1699852 |
| token bucket | 2028888 |
| GCRA | 3211061 |

## HTTP service load test

| algorithm | requests | http_200 | http_429 | expected_200 | requests_per_s |
|---|---|---|---|---|---|
| sliding log | 4000 | 1600 | 2400 | 1600 | 32102 |
| GCRA | 4000 | 1600 | 2400 | 1600 | 30712 |
