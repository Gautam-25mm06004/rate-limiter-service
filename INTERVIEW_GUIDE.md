# Interview guide — Rate limiter

## 30-second version
"I implemented five rate limiters — fixed window, sliding log, sliding window counter, token bucket and GCRA — and an HTTP
service that returns 429 with Retry-After. Under bursty traffic, the fixed window lets almost 2× the limit through at window
edges; the sliding log is exact but uses 35× more memory; the sliding-window counter is within 2% at tiny cost. Token bucket and
GCRA enforce a rate with bursts, which can also mean 2× in a minute if the burst equals the limit."

## Must-know
- **Fixed window problem**: N at the end of one window + N at the start of the next = 2N in a moment.
- **Sliding log**: exact, O(N) memory per client.
- **Sliding window counter**: `prev × overlap + current` — approximate, O(1).
- **Token bucket**: rate r, capacity b → average rate r, bursts up to b.
- **GCRA**: one timestamp per client; same decisions as the token bucket; popular in Redis-based limiters.
- **Retry-After**: tell the client when it can succeed (I test that retrying at that time works).

## Likely questions
1. *How do you rate-limit across many servers?* Shared store (Redis) with atomic scripts, or local limits with a global budget split.
2. *Which would you choose for an API quota?* Sliding window counter for "N per minute"; token bucket/GCRA when you want
   smooth traffic with a small burst.
3. *What happens with clock skew?* Use the store's clock (e.g., Redis TIME) or monotonic local clocks per node.
4. *Why did GCRA need an epsilon?* Adding T = 0.1 nine times gives 0.9000000000000001, so the 10th request was rejected; my test caught it.
