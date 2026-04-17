import time
from collections import deque
from threading import Lock


def format_log(entries: list[dict]) -> str:
    """Format event entries as a human-readable .log file."""
    lines = [
        "FTS Net Mon event log",
        f"Exported: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Entries:  {len(entries)}",
        "=" * 72,
    ]
    for e in entries:
        ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(e["ts"]))
        lines.append(f"[{ts}] [{e['severity']:<5}] {e['message']}")
    return "\n".join(lines) + "\n"


class EventLog:
    def __init__(self, maxlen: int = 1000):
        self._entries: deque = deque(maxlen=maxlen)
        self._lock = Lock()
        self._seq = 0

    def add(self, message: str, severity: str = "info") -> None:
        with self._lock:
            self._seq += 1
            self._entries.append({
                "seq": self._seq,
                "ts": time.time(),
                "message": message,
                "severity": severity,
            })

    def since(self, last_seq: int = 0) -> list[dict]:
        with self._lock:
            return [e for e in self._entries if e["seq"] > last_seq]

    def all(self) -> list[dict]:
        with self._lock:
            return list(self._entries)

    def latest_seq(self) -> int:
        with self._lock:
            return self._seq
