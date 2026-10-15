import asyncio, sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from ratelimit import FixedWindow, SlidingLog, SlidingWindowCounter, TokenBucket, GCRA, ALL, RateLimitServer, client  # noqa


class TestLimiters(unittest.TestCase):
    def test_all_allow_exactly_limit_in_one_burst(self):
        for cls in ALL:
            lim = cls(10, 1.0)
            self.assertEqual(sum(lim.allow("k", 0.5)[0] for _ in range(25)), 10, cls.name)

    def test_keys_are_independent(self):
        for cls in ALL:
            lim = cls(3, 1.0)
            for _ in range(3):
                lim.allow("a", 0.1)
            self.assertTrue(lim.allow("b", 0.1)[0], cls.name)
            self.assertFalse(lim.allow("a", 0.1)[0], cls.name)

    def test_fixed_window_boundary_weakness(self):
        lim = FixedWindow(10, 1.0)
        a = sum(lim.allow("k", 0.99)[0] for _ in range(10)) + sum(lim.allow("k", 1.01)[0] for _ in range(10))
        self.assertEqual(a, 20)                               # 20 requests within 20 ms
        lim = SlidingLog(10, 1.0)
        a = sum(lim.allow("k", 0.99)[0] for _ in range(10)) + sum(lim.allow("k", 1.01)[0] for _ in range(10))
        self.assertEqual(a, 10)

    def test_gcra_equals_token_bucket(self):
        import random
        rng = random.Random(3)
        t, g, b = 0.0, GCRA(50, 10.0), TokenBucket(50, 10.0)
        for _ in range(5000):
            t += rng.expovariate(8.0)
            self.assertEqual(g.allow("x", t)[0], b.allow("x", t)[0])

    def test_retry_after_is_sufficient(self):
        for cls in (SlidingLog, TokenBucket, GCRA, FixedWindow):
            lim = cls(5, 1.0)
            for _ in range(5):
                lim.allow("k", 0.0)
            ok, retry = lim.allow("k", 0.0)
            self.assertFalse(ok)
            self.assertTrue(lim.allow("k", retry + 1e-9)[0], cls.name)

    def test_http_service(self):
        async def run():
            srv = await RateLimitServer(SlidingLog(7, 60.0)).start()
            res = {}
            await client(srv.port, "u1", 20, res)
            await srv.stop()
            return res
        self.assertEqual(asyncio.run(run()), {200: 7, 429: 13})


if __name__ == "__main__":
    unittest.main()
