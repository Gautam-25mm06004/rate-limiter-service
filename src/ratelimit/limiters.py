"""Five rate-limiting algorithms with the same interface: allow(key, now) -> (allowed, retry_after_seconds).
All enforce "at most `limit` requests per `window` seconds" with different accuracy / memory / burst behaviour."""
import collections, math


class FixedWindow:
    """Counter per aligned window. O(1) memory, but allows up to 2x the limit across a window boundary."""
    name = "fixed window"

    def __init__(self, limit, window):
        self.limit, self.window, self.state = limit, window, {}

    def allow(self, key, now):
        w = math.floor(now / self.window)
        cur, n = self.state.get(key, (w, 0))
        if cur != w:
            cur, n = w, 0
        if n < self.limit:
            self.state[key] = (cur, n + 1)
            return True, 0.0
        self.state[key] = (cur, n)
        return False, (w + 1) * self.window - now


class SlidingLog:
    """Exact: keep a timestamp per accepted request in the last window. O(limit) memory per key."""
    name = "sliding log"

    def __init__(self, limit, window):
        self.limit, self.window, self.state = limit, window, collections.defaultdict(collections.deque)

    def allow(self, key, now):
        q = self.state[key]
        while q and q[0] <= now - self.window:
            q.popleft()
        if len(q) < self.limit:
            q.append(now)
            return True, 0.0
        return False, q[0] + self.window - now


class SlidingWindowCounter:
    """Approximation used by many API gateways: weight the previous window's count by its overlap."""
    name = "sliding window counter"

    def __init__(self, limit, window):
        self.limit, self.window, self.state = limit, window, {}

    def allow(self, key, now):
        w = math.floor(now / self.window)
        cur, n_cur, n_prev = self.state.get(key, (w, 0, 0))
        if cur != w:
            n_prev = n_cur if cur == w - 1 else 0
            cur, n_cur = w, 0
        frac = 1 - (now / self.window - w)
        est = n_prev * frac + n_cur
        if est + 1 <= self.limit:
            self.state[key] = (cur, n_cur + 1, n_prev)
            return True, 0.0
        self.state[key] = (cur, n_cur, n_prev)
        return False, self.window * (1 - frac) if n_prev == 0 else min(self.window, (est + 1 - self.limit) / max(n_prev, 1) * self.window)


class TokenBucket:
    """Refill at rate limit/window up to capacity `burst`. Smooths traffic, allows controlled bursts."""
    name = "token bucket"

    def __init__(self, limit, window, burst=None):
        self.rate, self.cap, self.state = limit / window, burst or limit, {}

    def allow(self, key, now):
        tokens, last = self.state.get(key, (self.cap, now))
        tokens = min(self.cap, tokens + (now - last) * self.rate)
        if tokens >= 1:
            self.state[key] = (tokens - 1, now)
            return True, 0.0
        self.state[key] = (tokens, now)
        return False, (1 - tokens) / self.rate


class GCRA:
    """Generic Cell Rate Algorithm (leaky bucket as a meter, ATM Forum TM 4.0): one timestamp per key —
    the theoretical arrival time (TAT). Decision-equivalent to a token bucket, with a single number of state per key."""
    name = "GCRA"

    def __init__(self, limit, window, burst=None):
        self.T = window / limit                      # emission interval
        self.tau = self.T * ((burst or limit) - 1)   # burst tolerance
        self.state = {}

    def allow(self, key, now):
        tat = max(self.state.get(key, now), now)
        if tat - now <= self.tau + 1e-9 * self.T:      # tolerance for floating-point accumulation
            self.state[key] = tat + self.T
            return True, 0.0
        return False, tat - self.tau - now


ALL = [FixedWindow, SlidingLog, SlidingWindowCounter, TokenBucket, GCRA]
