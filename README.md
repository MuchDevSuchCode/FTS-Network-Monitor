# FTS Net Mon

Dual-WAN connectivity monitor. Continuously probes a set of hosts (router, ISP gateways, DNS, upstream) over ICMP and TCP, tracks loss/latency/jitter, and surfaces the state through a Tk desktop GUI and a local web UI.

## Features

- ICMP ping and TCP connect probes per target, on independent threads
- Grouping by `LAN` / `ISP1` / `ISP2` with per-group health rollup
- Rolling history with loss %, recent loss %, avg/min/max latency, jitter
- Event log with transitions (first fail, sustained down after 3 fails, recovery)
- Optional audible alert on drop
- Web UI at `http://127.0.0.1:8765` with live status, events, and config editing
- Network info endpoint (`/api/netinfo`) and event log export
- Pure Python stdlib — no third-party dependencies

## Requirements

- Python 3.10+
- Windows or Linux/macOS (uses the system `ping` binary)
- Tk (bundled with CPython on Windows/macOS; on Linux install `python3-tk`)

## Run

```bash
python fts_netmon.py                    # Tk GUI + web UI
python fts_netmon.py --headless         # web UI only
python fts_netmon.py --no-web           # GUI only
python fts_netmon.py --bind 0.0.0.0 --port 8765
```

First launch writes a default `config.json` next to the script. Edit it directly or use the web UI; changes restart the probes.

## Configuration

`config.json` fields:

| Field | Description |
| --- | --- |
| `router_ip` | Local router (LAN group) |
| `isp1_gateway` | ISP1 next-hop |
| `dns_server` | DNS server (probed via ICMP + TCP:53) |
| `upstream_host` | Public reachability target (ICMP + TCP:443) |
| `isp2_gateway` | Optional second ISP gateway |
| `probe_interval` | Seconds between ICMP probes |
| `tcp_probe_interval` | Seconds between TCP probes |
| `timeout_ms` | Probe timeout |
| `history_size` | Samples retained per target |
| `sound_on_drop` | Audible alert on sustained drop |

Leave a field blank to disable that target.

## HTTP API

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/status` | Current targets, samples, group health |
| GET | `/api/config` | Current config |
| POST | `/api/config` | Update config (JSON body); restarts probes |
| GET | `/api/events?since=<seq>` | Event log tail |
| GET | `/api/events/export` | Full event log as text |
| GET | `/api/netinfo?refresh=1` | Local network info |

## Layout

```
fts_netmon.py   entry point / CLI
app.py          shared AppState (config, monitor, event log)
config.py       Config + Target dataclasses, JSON persistence
monitor.py     probe scheduler / threads
probes.py       ICMP + TCP probe primitives
stats.py        rolling per-target stats
events.py       event log
netinfo.py      local network info
sound.py        drop alert
gui.py          Tk GUI
web.py          HTTP server + JSON API
static/         web UI assets
config.json     runtime configuration
```
