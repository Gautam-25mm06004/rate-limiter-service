"""Accuracy under adversarial traffic, boundary bursts, memory, speed, and an end-to-end HTTP load test."""
import asyncio, bisect, json, random, sys, time, tracemalloc
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from ratelimit import ALL, GCRA, SlidingLog, RateLimitServer, client  # noqa

R = {}
LIMIT, WINDOW = 100, 60.0


def max_in_any_window(times, window):
    """Largest number of accepted requests inside any half-open interval of length `window`."""
    t = np.sort(np.asarray(times))
    if len(t) == 0:
        return 0
    j = np.searchsorted(t, t + window, side="left")
    return int(np.max(j - np.arange(len(t))))


# 1) Boundary burst: 100 requests at t = 59.9 s and 100 at t = 60.1 s
burst = []
for cls in ALL:
    lim = cls(LIMIT, WINDOW)
    acc = [t for t in [59.9] * 100 + [60.1] * 100 if lim.allow("u", t)[0]]
    burst.append({"algorithm": cls.name, "accepted_of_200": len(acc), "max_in_any_60s": max_in_any_window(acc, WINDOW)})
R["boundary_burst"] = burst

# 2) Adversarial random traffic: bursts + Poisson background at 3x the allowed rate, 2 hours
rng = random.Random(0)
times = []
t = 0.0
while t < 7200:
    if rng.random() < 0.02:
        times += [t + rng.random() * 0.5 for _ in range(rng.randint(20, 150))]
    t += rng.expovariate(3 * LIMIT / WINDOW)
    times.append(t)
times.sort()
adv = []
for cls in ALL:
    lim = cls(LIMIT, WINDOW)
    acc = [x for x in times if lim.allow("u", x)[0]]
    m = max_in_any_window(acc, WINDOW)
    adv.append({"algorithm": cls.name, "offered": len(times), "accepted": len(acc),
                "utilisation_%": round(100 * len(acc) / (7200 / WINDOW * LIMIT), 1),
                "max_in_any_60s": m, "worst_overshoot_%": round(100 * (m / LIMIT - 1), 1)})
R["adversarial"] = adv

# 3) Memory per key at steady state, and speed with 10,000 keys
mem, speed = [], []
for cls in ALL:
    tracemalloc.start()
    lim = cls(LIMIT, WINDOW)
    for k in range(2000):
        for i in range(LIMIT):
            lim.allow(k, i * WINDOW / LIMIT * 0.5)
    cur, _ = tracemalloc.get_traced_memory(); tracemalloc.stop()
    mem.append({"algorithm": cls.name, "bytes_per_key": round(cur / 2000)})
    lim = cls(LIMIT, WINDOW)
    keys = [rng.randrange(10000) for _ in range(300000)]
    t0 = time.perf_counter()
    for i, k in enumerate(keys):
        lim.allow(k, i * 0.0001)
    speed.append({"algorithm": cls.name, "decisions_per_s": round(300000 / (time.perf_counter() - t0))})
R["memory"] = mem
R["speed"] = speed

# 4) HTTP load test: 8 concurrent clients (one key each), 500 requests each, limit 200 per 60 s per key
async def load_test(cls):
    srv = await RateLimitServer(cls(200, 60.0)).start()
    results = {}
    t0 = time.perf_counter()
    await asyncio.gather(*(client(srv.port, f"user{i}", 500, results) for i in range(8)))
    el = time.perf_counter() - t0
    await srv.stop()
    return {"algorithm": cls.name, "requests": 4000, "http_200": results.get(200, 0), "http_429": results.get(429, 0),
            "expected_200": 8 * 200, "requests_per_s": round(4000 / el)}
R["http"] = [asyncio.run(load_test(c)) for c in (SlidingLog, GCRA)]

# Figure: accepted-per-window profile for the boundary attack style over time
fig, ax = plt.subplots(figsize=(7, 4))
for cls in ALL:
    lim = cls(LIMIT, WINDOW)
    acc = np.array([x for x in times if lim.allow("u", x)[0]])
    grid = np.arange(60, 3600, 5.0)
    counts = np.searchsorted(acc, grid) - np.searchsorted(acc, grid - WINDOW)
    ax.plot(grid / 60, counts, lw=0.8, label=cls.name)
ax.axhline(LIMIT, color="k", ls="--", lw=0.8)
ax.set_xlabel("minute"); ax.set_ylabel("accepted in trailing 60 s"); ax.legend(fontsize=7); ax.set_title("Limit 100 / 60 s under bursty traffic")
fig.tight_layout(); fig.savefig(ROOT / "results" / "figures" / "trailing_window.png", dpi=130); plt.close(fig)

(ROOT / "results" / "results.json").write_text(json.dumps(R, indent=2))
def tbl(rows):
    cols = list(rows[0]); return "| " + " | ".join(cols) + " |\n|" + "---|" * len(cols) + "\n" + "".join("| " + " | ".join(str(r[c]) for c in cols) + " |\n" for r in rows)
md = "# Results (limit 100 requests per 60 s)\n\n## Boundary burst (100 requests at 59.9 s, 100 at 60.1 s)\n\n" + tbl(burst)
md += "\n## Two hours of bursty traffic at ~3x the limit\n\n" + tbl(adv) + "\n## Memory per key\n\n" + tbl(mem)
md += "\n## Decision speed (10,000 keys)\n\n" + tbl(speed) + "\n## HTTP service load test\n\n" + tbl(R["http"])
(ROOT / "results" / "summary.md").write_text(md)
print(md)
