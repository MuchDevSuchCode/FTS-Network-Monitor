from collections import deque
from threading import Lock
from typing import Optional


class Stats:
    def __init__(self, maxlen: int = 180):
        self.maxlen = maxlen
        self.samples: deque = deque(maxlen=maxlen)
        self.total = 0
        self.success = 0
        self.consecutive_fail = 0
        self.consecutive_ok = 0
        self.last_ok_ts = 0.0
        self.last_fail_ts = 0.0
        self.last_latency = 0.0
        self.lock = Lock()

    def add(self, ok: bool, latency: Optional[float], ts: float) -> None:
        with self.lock:
            self.total += 1
            if ok:
                self.success += 1
                self.consecutive_fail = 0
                self.consecutive_ok += 1
                self.last_ok_ts = ts
                self.last_latency = latency or 0.0
            else:
                self.consecutive_fail += 1
                self.consecutive_ok = 0
                self.last_fail_ts = ts
                self.last_latency = 0.0
            self.samples.append((ok, latency, ts))

    def snapshot(self) -> dict:
        with self.lock:
            samples = list(self.samples)
            lats = [l for ok, l, _ in samples if ok and l is not None]
            recent = samples[-60:]
            recent_ok = sum(1 for ok, _, _ in recent if ok)
            recent_total = len(recent)

            if lats:
                avg = sum(lats) / len(lats)
                # jitter: mean abs deviation of last 30 successful samples
                tail = lats[-30:]
                j_mean = sum(tail) / len(tail)
                jitter = sum(abs(x - j_mean) for x in tail) / len(tail)
            else:
                avg = 0.0
                jitter = 0.0

            return {
                "total": self.total,
                "success": self.success,
                "loss_pct": ((self.total - self.success) / self.total * 100.0) if self.total else 0.0,
                "recent_loss_pct": ((recent_total - recent_ok) / recent_total * 100.0) if recent_total else 0.0,
                "avg": avg,
                "min": min(lats) if lats else 0.0,
                "max": max(lats) if lats else 0.0,
                "jitter": jitter,
                "last": self.last_latency,
                "consecutive_fail": self.consecutive_fail,
                "consecutive_ok": self.consecutive_ok,
                "samples": samples,
                "last_ok_ts": self.last_ok_ts,
                "last_fail_ts": self.last_fail_ts,
            }
