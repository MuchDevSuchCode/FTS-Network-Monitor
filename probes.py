import platform
import re
import socket
import subprocess
import time
from dataclasses import dataclass
from typing import Optional

IS_WIN = platform.system() == "Windows"
_TIME_RE = re.compile(rb"time[=<]\s*(\d+(?:\.\d+)?)\s*ms", re.IGNORECASE)
_CREATE_NO_WINDOW = 0x08000000 if IS_WIN else 0


@dataclass
class ProbeResult:
    ok: bool
    latency_ms: Optional[float]
    error: Optional[str] = None
    timestamp: float = 0.0


def icmp_ping(host: str, timeout_ms: int = 1000) -> ProbeResult:
    if IS_WIN:
        cmd = ["ping", "-n", "1", "-w", str(timeout_ms), host]
    else:
        wait_s = max(1, (timeout_ms + 999) // 1000)
        cmd = ["ping", "-c", "1", "-W", str(wait_s), host]

    start = time.perf_counter()
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            timeout=(timeout_ms / 1000.0) + 1.5,
            creationflags=_CREATE_NO_WINDOW,
        )
    except subprocess.TimeoutExpired:
        return ProbeResult(False, None, "timeout", time.time())
    except FileNotFoundError:
        return ProbeResult(False, None, "ping binary not found", time.time())
    except OSError as e:
        return ProbeResult(False, None, f"ping error: {e}", time.time())

    elapsed_ms = (time.perf_counter() - start) * 1000.0
    if proc.returncode != 0:
        return ProbeResult(False, None, "unreachable", time.time())

    m = _TIME_RE.search(proc.stdout or b"")
    latency = float(m.group(1)) if m else elapsed_ms
    return ProbeResult(True, latency, None, time.time())


def tcp_connect(host: str, port: int, timeout_ms: int = 1000) -> ProbeResult:
    start = time.perf_counter()
    try:
        with socket.create_connection((host, port), timeout=timeout_ms / 1000.0):
            elapsed = (time.perf_counter() - start) * 1000.0
            return ProbeResult(True, elapsed, None, time.time())
    except socket.timeout:
        return ProbeResult(False, None, "timeout", time.time())
    except OSError as e:
        return ProbeResult(False, None, str(e), time.time())
