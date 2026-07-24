"""In-memory metrics registry (no external deps). Exposed at /metrics."""
from __future__ import annotations

import threading
import time
from collections import defaultdict


class Metrics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._start = time.time()
        self.total = 0
        self.by_status_class: dict[str, int] = defaultdict(int)
        self.by_path: dict[str, dict] = defaultdict(lambda: {"count": 0, "errors": 0, "total_ms": 0.0})
        self.rate_limited = 0

    def record(self, path: str, status: int, ms: float) -> None:
        with self._lock:
            self.total += 1
            self.by_status_class[f"{status // 100}xx"] += 1
            p = self.by_path[path]
            p["count"] += 1
            p["total_ms"] += ms
            if status >= 500:
                p["errors"] += 1

    def note_rate_limited(self) -> None:
        with self._lock:
            self.rate_limited += 1

    @property
    def uptime_seconds(self) -> float:
        return round(time.time() - self._start, 1)

    def snapshot(self) -> dict:
        with self._lock:
            paths = {
                path: {
                    "count": v["count"],
                    "errors": v["errors"],
                    "avg_ms": round(v["total_ms"] / v["count"], 2) if v["count"] else 0.0,
                }
                for path, v in self.by_path.items()
            }
            return {
                "uptime_seconds": self.uptime_seconds,
                "requests_total": self.total,
                "rate_limited_total": self.rate_limited,
                "by_status_class": dict(self.by_status_class),
                "by_path": paths,
            }

    def prometheus(self) -> str:
        snap = self.snapshot()
        lines = [
            "# HELP gateway_uptime_seconds Seconds since start.",
            "# TYPE gateway_uptime_seconds gauge",
            f"gateway_uptime_seconds {snap['uptime_seconds']}",
            "# HELP gateway_requests_total Total handled requests.",
            "# TYPE gateway_requests_total counter",
            f"gateway_requests_total {snap['requests_total']}",
            "# HELP gateway_rate_limited_total Requests rejected by rate limit.",
            "# TYPE gateway_rate_limited_total counter",
            f"gateway_rate_limited_total {snap['rate_limited_total']}",
            "# HELP gateway_requests_by_status Total requests by status class.",
            "# TYPE gateway_requests_by_status counter",
        ]
        for cls, n in snap["by_status_class"].items():
            lines.append(f'gateway_requests_by_status{{class="{cls}"}} {n}')
        lines.append("# HELP gateway_path_requests Requests per route.")
        lines.append("# TYPE gateway_path_requests counter")
        for path, v in snap["by_path"].items():
            safe = path.replace("\\", "\\\\").replace('"', '\\"')
            lines.append(f'gateway_path_requests{{path="{safe}"}} {v["count"]}')
            lines.append(f'gateway_path_errors{{path="{safe}"}} {v["errors"]}')
            lines.append(f'gateway_path_avg_ms{{path="{safe}"}} {v["avg_ms"]}')
        return "\n".join(lines) + "\n"


# Single process-wide registry.
metrics = Metrics()
