import time
from dataclasses import fields
from pathlib import Path
from threading import Lock

from config import Config
from events import EventLog
from monitor import Monitor


class AppState:
    """Shared state: config, monitor, event log. Accessed by GUI and web UI."""

    def __init__(self, config_path: Path):
        self.config_path = Path(config_path)
        self.config = Config.load(self.config_path)
        self.event_log = EventLog()
        self.start_time = time.time()
        self.monitor = Monitor(self.config, self.event_log)
        self._lock = Lock()

    def start(self) -> None:
        self.monitor.start()
        self.event_log.add("FTS Net Mon started", "ok")

    def stop(self) -> None:
        self.monitor.stop()

    def restart_monitor(self) -> None:
        with self._lock:
            self.monitor.stop()
            self.monitor = Monitor(self.config, self.event_log)
            self.monitor.start()

    def apply_config_changes(self) -> None:
        """Persist the current (already-mutated) config and restart probes."""
        with self._lock:
            self.config.save(self.config_path)
        self.event_log.add("Settings saved — restarting probes", "warn")
        self.restart_monitor()

    def update_config(self, updates: dict) -> None:
        """Apply a dict of config updates (coercing types), save, restart."""
        field_names = {f.name for f in fields(Config)}
        with self._lock:
            for key, value in updates.items():
                if key not in field_names:
                    continue
                current = getattr(self.config, key)
                try:
                    if isinstance(current, bool):
                        if isinstance(value, str):
                            coerced = value.strip().lower() in ("true", "1", "yes", "on")
                        else:
                            coerced = bool(value)
                    elif isinstance(current, int) and not isinstance(current, bool):
                        coerced = int(value)
                    elif isinstance(current, float):
                        coerced = float(value)
                    else:
                        coerced = str(value).strip()
                except (ValueError, TypeError) as e:
                    raise ValueError(f"Invalid value for {key!r}: {e}") from e
                setattr(self.config, key, coerced)
            self.config.save(self.config_path)
        self.event_log.add("Settings updated via API — restarting probes", "warn")
        self.restart_monitor()
