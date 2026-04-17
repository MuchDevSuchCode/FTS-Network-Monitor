import threading
import time

from config import Config, Target
from events import EventLog
from probes import ProbeResult, icmp_ping, tcp_connect
from sound import play_drop_alert
from stats import Stats


class Monitor:
    def __init__(self, config: Config, event_log: EventLog):
        self.config = config
        self.event_log = event_log
        self.stats: dict[tuple[str, str], Stats] = {}
        self.threads: list[threading.Thread] = []
        self.stop_event = threading.Event()

    def start(self) -> None:
        for target in self.config.targets():
            if target.icmp:
                key = (target.name, "icmp")
                self.stats[key] = Stats(maxlen=self.config.history_size)
                th = threading.Thread(target=self._run_icmp, args=(target,), daemon=True)
                th.start()
                self.threads.append(th)
            if target.tcp_port:
                key = (target.name, f"tcp:{target.tcp_port}")
                self.stats[key] = Stats(maxlen=self.config.history_size)
                th = threading.Thread(target=self._run_tcp, args=(target,), daemon=True)
                th.start()
                self.threads.append(th)

    def stop(self) -> None:
        self.stop_event.set()
        for th in self.threads:
            th.join(timeout=2.0)
        self.threads.clear()

    def _emit_transition(self, target_name: str, host_label: str, kind_label: str,
                         stats: Stats, result: ProbeResult) -> None:
        prefix = f"{target_name} ({host_label}) [{kind_label}]"
        if not result.ok:
            if stats.consecutive_fail == 1:
                self.event_log.add(
                    f"{prefix} FAILED — {result.error or 'no response'}",
                    "fail",
                )
            elif stats.consecutive_fail == 3:
                self.event_log.add(
                    f"{prefix} DOWN — 3 consecutive fails",
                    "fail",
                )
                if self.config.sound_on_drop:
                    play_drop_alert()
        else:
            if stats.consecutive_ok == 1 and stats.total > 1:
                lat = result.latency_ms or 0.0
                self.event_log.add(
                    f"{prefix} RECOVERED ({lat:.1f} ms)",
                    "ok",
                )

    def _run_icmp(self, target: Target) -> None:
        key = (target.name, "icmp")
        stats = self.stats[key]
        while not self.stop_event.is_set():
            start = time.time()
            result = icmp_ping(target.host, self.config.timeout_ms)
            stats.add(result.ok, result.latency_ms, result.timestamp)
            self._emit_transition(target.name, target.host, "ICMP", stats, result)
            elapsed = time.time() - start
            wait = max(0.0, self.config.probe_interval - elapsed)
            if self.stop_event.wait(wait):
                break

    def _run_tcp(self, target: Target) -> None:
        assert target.tcp_port is not None
        key = (target.name, f"tcp:{target.tcp_port}")
        stats = self.stats[key]
        kind_label = f"TCP:{target.tcp_port}"
        host_label = f"{target.host}:{target.tcp_port}"
        while not self.stop_event.is_set():
            start = time.time()
            result = tcp_connect(target.host, target.tcp_port, self.config.timeout_ms)
            stats.add(result.ok, result.latency_ms, result.timestamp)
            self._emit_transition(target.name, host_label, kind_label, stats, result)
            elapsed = time.time() - start
            wait = max(0.0, self.config.tcp_probe_interval - elapsed)
            if self.stop_event.wait(wait):
                break
