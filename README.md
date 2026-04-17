# FTS Net Mon

Dual-WAN connectivity monitor. Continuously probes a set of hosts (router, ISP gateways, DNS, upstream) over ICMP and TCP, tracks loss/latency/jitter, and surfaces the state through a local web UI (with an optional Tk desktop GUI).

## Features

- ICMP ping and TCP connect probes per target, on independent threads
- Grouping by `LAN` / `ISP1` / `ISP2` with per-group health rollup
- Rolling history with loss %, recent loss %, avg/min/max latency, jitter
- Event log with transitions (first fail, sustained down after 3 fails, recovery)
- Optional audible alert on drop
- Web UI at `http://127.0.0.1:8765` with live status, events, and config editing
- **First-run setup wizard**: auto-detects your router IP and DNS server from the active network interface and offers them as the initial configuration
- **Auto-launches a browser tab** when the web server comes up
- Optional Tk desktop GUI (opt in with `--gui`)
- Network info endpoint (`/api/netinfo`) and event log export
- Pure Python stdlib — no third-party dependencies

## Requirements

- Python 3.10+
- Windows or Linux/macOS (uses the system `ping` binary)
- Tk (only needed for `--gui`; bundled with CPython on Windows/macOS; on Linux install `python3-tk`)

## Run

```bash
python fts_netmon.py                    # web UI (default) + auto-opens browser
python fts_netmon.py --gui              # web UI + Tk desktop GUI
python fts_netmon.py --gui --no-web     # Tk GUI only
python fts_netmon.py --no-browser       # web UI, don't auto-open browser
python fts_netmon.py --bind 0.0.0.0 --port 8765
```

By default, only the web UI runs — the Tk desktop GUI is **off** unless `--gui` is passed. A browser tab opens automatically to the web UI; pass `--no-browser` to skip that.

### CLI flags

| Flag | Description |
| --- | --- |
| `--gui` | Also launch the Tk desktop GUI (off by default) |
| `--no-web` | Disable the web UI (requires `--gui`) |
| `--no-browser` | Don't auto-open a browser tab on startup |
| `--bind <addr>` | Web UI bind address (default `127.0.0.1`; use `0.0.0.0` to expose on the network) |
| `--port <n>` | Web UI port (default `8765`) |

## First-run setup

On first launch (no `config.json`, or a config that has never been confirmed), the web UI pops a **Quick Setup** dialog pre-filled with values detected from the active network interface:

- **Router IP** and **ISP1 Gateway** — the default gateway of the active interface
- **DNS Server** — the first DNS server reported for that interface
- **Upstream Host** — defaults to `8.8.8.8`

Confirm to save and start monitoring, or skip to accept current defaults. You can re-open the regular **Settings** dialog at any time to edit values.

Suggestion data comes from `GET /api/setup/suggest`, which is derived from `/api/netinfo`.

## Configuration

`config.json` (created next to the script on first run) fields:

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
| `configured` | Internal flag — set `true` after the setup wizard completes. Set to `false` (or delete the file) to re-trigger the wizard. |

Leave a host field blank to disable that target.

## HTTP API

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/status` | Current targets, samples, group health |
| GET | `/api/config` | Current config |
| POST | `/api/config` | Update config (JSON body); restarts probes |
| GET | `/api/events?since=<seq>` | Event log tail |
| GET | `/api/events/export` | Full event log as text |
| GET | `/api/netinfo?refresh=1` | Local network info |
| GET | `/api/setup/suggest` | Suggested router/DNS values from active interface |

## Layout

```
fts_netmon.py   entry point / CLI
app.py          shared AppState (config, monitor, event log)
config.py       Config + Target dataclasses, JSON persistence
monitor.py      probe scheduler / threads
probes.py       ICMP + TCP probe primitives
stats.py        rolling per-target stats
events.py       event log
netinfo.py      local network info
sound.py        drop alert
gui.py          Tk GUI (optional; --gui)
web.py          HTTP server + JSON API
static/         web UI assets
config.json     runtime configuration
```
