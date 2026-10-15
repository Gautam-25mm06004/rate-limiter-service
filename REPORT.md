# Accuracy, Memory and Burst Behaviour of Common Rate-Limiting Algorithms

**Gautam Jain** — IIT Bhubaneswar

## 1. Problem
A quota "at most N requests per T seconds" can be read as (a) per calendar window, (b) per trailing window, or (c) as a
long-run rate with some burst allowance. Algorithms differ in which reading they enforce, how much state they keep per
client and how they behave at window edges.

## 2. Algorithms
- **Fixed window**: counter reset at multiples of T.
- **Sliding log**: deque of accepted timestamps; evict those older than T. Exact for (b).
- **Sliding window counter**: estimate = previous-window count × fraction of the trailing window still overlapping it +
  current count.
- **Token bucket**: tokens refill continuously at N/T up to capacity B; a request spends one token.
- **GCRA** (ATM Forum Traffic Management 4.0): keep the theoretical arrival time TAT; accept if `TAT − now ≤ τ` with emission
  interval `T/N` and tolerance `τ = (B − 1)·T/N`, then `TAT ← max(TAT, now) + T/N`. It is decision-equivalent to a token
  bucket with capacity B; a small tolerance absorbs floating-point accumulation (a bug found by the unit tests).

## 3. Evaluation
- Boundary attack and two hours of synthetic bursty traffic (Poisson at 3× the limit plus random bursts of 20–150
  requests). We measure the maximum number of accepted requests inside any 60-second interval, the long-run utilisation and
  memory per key (tracemalloc, 2,000 keys at steady state).
- An asyncio HTTP/1.1 server with keep-alive connections; clients count status codes.

## 4. Results
See README. Only the sliding log never exceeds the limit in any trailing window. The sliding-window counter exceeds it by at
most 2% while using 3% of the log's memory. Token bucket and GCRA accept up to 2N in a window when B = N, which is correct
for their rate-plus-burst semantics but surprising if a trailing-window quota was intended.

## 5. Limitations
Single process (no shared store such as Redis, no clock skew across nodes); synthetic traffic; Python performance.

## References
1. ATM Forum. *Traffic Management Specification Version 4.0* (GCRA), 1996.
2. J. Turner. New directions in communications (or which way to the information age?). *IEEE Communications Magazine* 24(10), 8–15, 1986 (leaky bucket).
3. IETF RFC 6585, *Additional HTTP Status Codes* (429 Too Many Requests), 2012.
