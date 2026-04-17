import ipaddress
import platform
import re
import socket
import subprocess
import sys
import threading
import time

_CACHE_TTL = 5.0
_cache_lock = threading.Lock()
_cache_data: dict | None = None
_cache_time = 0.0

_CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


def get_network_info(force_refresh: bool = False) -> dict:
    global _cache_data, _cache_time
    with _cache_lock:
        now = time.time()
        if (not force_refresh and _cache_data is not None
                and (now - _cache_time) < _CACHE_TTL):
            return _cache_data
    data = _collect()
    with _cache_lock:
        _cache_data = data
        _cache_time = time.time()
    return data


def _collect() -> dict:
    hostname = socket.gethostname()
    primary_ip = _get_primary_ip()

    if sys.platform == "win32":
        interfaces = _parse_ipconfig_windows(_run_ipconfig())
    elif sys.platform == "darwin":
        interfaces = _collect_macos()
    else:
        interfaces = _collect_linux()

    for iface in interfaces:
        ip = iface.get("ipv4")
        mask = iface.get("subnet_mask")
        if ip and mask:
            try:
                net = ipaddress.IPv4Network(f"{ip}/{mask}", strict=False)
                iface["cidr"] = f"{ip}/{net.prefixlen}"
                iface["network"] = str(net)
            except (ValueError, ipaddress.AddressValueError):
                pass
        iface["outbound"] = (primary_ip is not None and ip == primary_ip)
        iface["active"] = False

    # The "active" interface is the one carrying the default route — i.e.
    # the physical LAN link, which is what the user actually configures.
    # Fall back to the outbound interface if no gateway is advertised.
    active = next((i for i in interfaces if i.get("gateway")), None)
    if active is None:
        active = next((i for i in interfaces if i.get("outbound")), None)
    if active is not None:
        active["active"] = True

    outbound_iface = next((i for i in interfaces if i.get("outbound")), None)

    return {
        "hostname": hostname,
        "primary_ip": primary_ip,
        "platform": f"{platform.system()} {platform.release()}",
        "interfaces": interfaces,
        "active": active,
        "outbound_iface": outbound_iface,
        "fetched_at": time.time(),
    }


def _get_primary_ip() -> str | None:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # No packets are actually sent for a UDP socket's connect().
            s.connect(("8.8.8.8", 53))
            return s.getsockname()[0]
        finally:
            s.close()
    except OSError:
        return None


def _run_ipconfig() -> str:
    try:
        proc = subprocess.run(
            ["ipconfig", "/all"],
            capture_output=True, timeout=5,
            creationflags=_CREATE_NO_WINDOW,
        )
        return proc.stdout.decode("utf-8", errors="replace")
    except (FileNotFoundError, subprocess.SubprocessError, OSError):
        return ""


def _parse_ipconfig_windows(text: str) -> list[dict]:
    interfaces: list[dict] = []
    current: dict | None = None
    last_key: str | None = None

    for raw in text.splitlines():
        if raw and not raw[0].isspace() and raw.strip().endswith(":"):
            if current is not None:
                interfaces.append(current)
            name = raw.rstrip().rstrip(":").strip()
            if " adapter " in name:
                name = name.split(" adapter ", 1)[1]
            current = {"name": name, "dns_servers": []}
            last_key = None
            continue

        if current is None:
            continue

        stripped = raw.strip()
        if not stripped:
            last_key = None
            continue

        if ":" in stripped:
            idx = stripped.index(":")
            key = stripped[:idx].rstrip(". ").strip().lower()
            val = stripped[idx + 1:].strip()
            last_key = key
            _assign_windows(current, key, val)
        else:
            if last_key == "dns servers":
                current["dns_servers"].append(stripped)

    if current is not None:
        interfaces.append(current)

    return [i for i in interfaces if i.get("ipv4")]


def _assign_windows(iface: dict, key: str, val: str) -> None:
    if key == "description":
        iface["description"] = val
    elif key == "physical address":
        iface["mac"] = val
    elif key == "subnet mask":
        iface["subnet_mask"] = val
    elif key == "default gateway":
        if val:
            iface["gateway"] = val
    elif key == "dhcp server":
        iface["dhcp_server"] = val
    elif key == "connection-specific dns suffix":
        iface["dns_suffix"] = val
    elif key == "dhcp enabled":
        iface["dhcp"] = val.lower().startswith("yes")
    elif key.startswith("ipv4 address"):
        iface["ipv4"] = val.split("(")[0].strip()
    elif key == "dns servers":
        if val:
            iface["dns_servers"].append(val)


def _collect_linux() -> list[dict]:
    ifaces: dict[str, dict] = {}
    try:
        addr = subprocess.run(
            ["ip", "-o", "-4", "addr", "show"],
            capture_output=True, text=True, timeout=3, check=False,
        )
        for line in addr.stdout.splitlines():
            m = re.match(r"\d+:\s+(\S+)\s+inet\s+(\S+)", line)
            if not m:
                continue
            name, cidr = m.group(1), m.group(2)
            ip, _, _prefix = cidr.partition("/")
            try:
                net = ipaddress.IPv4Network(cidr, strict=False)
                mask = str(net.netmask)
            except (ValueError, ipaddress.AddressValueError):
                mask = ""
            ifaces[name] = {"name": name, "ipv4": ip, "subnet_mask": mask,
                            "dns_servers": []}
    except (FileNotFoundError, subprocess.SubprocessError):
        return []

    try:
        link = subprocess.run(
            ["ip", "-o", "link", "show"],
            capture_output=True, text=True, timeout=3, check=False,
        )
        for line in link.stdout.splitlines():
            m = re.match(r"\d+:\s+(\S+?):.+?link/ether\s+(\S+)", line)
            if m and m.group(1) in ifaces:
                ifaces[m.group(1)]["mac"] = m.group(2)
    except (FileNotFoundError, subprocess.SubprocessError):
        pass

    try:
        route = subprocess.run(
            ["ip", "route"], capture_output=True, text=True, timeout=3, check=False,
        )
        m = re.search(r"default\s+via\s+(\S+)\s+dev\s+(\S+)", route.stdout)
        if m and m.group(2) in ifaces:
            ifaces[m.group(2)]["gateway"] = m.group(1)
    except (FileNotFoundError, subprocess.SubprocessError):
        pass

    try:
        with open("/etc/resolv.conf") as f:
            dns = [ln.split()[1] for ln in f
                   if ln.startswith("nameserver") and len(ln.split()) > 1]
    except OSError:
        dns = []
    for iface in ifaces.values():
        iface["dns_servers"] = list(dns)

    return list(ifaces.values())


def _collect_macos() -> list[dict]:
    ifaces: dict[str, dict] = {}
    try:
        proc = subprocess.run(
            ["ifconfig"], capture_output=True, text=True, timeout=3, check=False,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return []

    current: dict | None = None
    for line in proc.stdout.splitlines():
        if line and not line[0].isspace():
            name = line.split(":", 1)[0]
            current = {"name": name, "dns_servers": []}
            ifaces[name] = current
            continue
        if current is None:
            continue
        ln = line.strip()
        m = re.match(r"ether\s+(\S+)", ln)
        if m:
            current["mac"] = m.group(1)
        m = re.match(r"inet\s+(\S+)\s+netmask\s+(\S+)", ln)
        if m:
            current["ipv4"] = m.group(1)
            mask = m.group(2)
            if mask.startswith("0x"):
                try:
                    current["subnet_mask"] = str(ipaddress.IPv4Address(int(mask, 16)))
                except (ValueError, ipaddress.AddressValueError):
                    pass
            else:
                current["subnet_mask"] = mask

    try:
        route = subprocess.run(
            ["netstat", "-rn"], capture_output=True, text=True, timeout=3, check=False,
        )
        for line in route.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 4 and parts[0] == "default":
                gw = parts[1]
                dev = parts[-1]
                if dev in ifaces:
                    ifaces[dev]["gateway"] = gw
                    break
    except (FileNotFoundError, subprocess.SubprocessError):
        pass

    try:
        scutil = subprocess.run(
            ["scutil", "--dns"], capture_output=True, text=True, timeout=3, check=False,
        )
        dns: list[str] = []
        for line in scutil.stdout.splitlines():
            m = re.match(r"\s*nameserver\[\d+\]\s*:\s*(\S+)", line)
            if m and m.group(1) not in dns:
                dns.append(m.group(1))
        for iface in ifaces.values():
            iface["dns_servers"] = list(dns)
    except (FileNotFoundError, subprocess.SubprocessError):
        pass

    return [i for i in ifaces.values() if i.get("ipv4")]
