import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional


@dataclass
class Target:
    name: str
    host: str
    icmp: bool = True
    tcp_port: Optional[int] = None
    group: str = "ISP1"


@dataclass
class Config:
    router_ip: str = "192.168.1.1"
    isp1_gateway: str = ""
    dns_server: str = "1.1.1.1"
    upstream_host: str = "8.8.8.8"
    isp2_gateway: str = ""
    probe_interval: float = 1.0
    tcp_probe_interval: float = 2.0
    timeout_ms: int = 1000
    history_size: int = 180
    sound_on_drop: bool = True

    def targets(self) -> list[Target]:
        t: list[Target] = []
        if self.router_ip:
            t.append(Target("Router", self.router_ip, icmp=True, group="LAN"))
        if self.isp1_gateway:
            t.append(Target("ISP1 Gateway", self.isp1_gateway, icmp=True, group="ISP1"))
        if self.dns_server:
            t.append(Target("DNS Server", self.dns_server, icmp=True, tcp_port=53, group="ISP1"))
        if self.upstream_host:
            t.append(Target("Upstream", self.upstream_host, icmp=True, tcp_port=443, group="ISP1"))
        if self.isp2_gateway:
            t.append(Target("ISP2 Gateway", self.isp2_gateway, icmp=True, group="ISP2"))
        return t

    @classmethod
    def load(cls, path: Path) -> "Config":
        path = Path(path)
        if not path.exists():
            cfg = cls()
            cfg.save(path)
            return cfg
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        known = {k: data[k] for k in data if k in cls.__dataclass_fields__}
        return cls(**known)

    def save(self, path: Path) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=2)
