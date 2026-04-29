# FTS Net Mon

**Dual-WAN connectivity monitor** — a single-file-launchable tool that continuously probes your router, ISP gateways, DNS, and an upstream public host over ICMP and TCP, tracks loss / latency / jitter, and surfaces it all through a live local web UI (with an optional Tk desktop GUI).

Built for home-office and small-business environments where a flaky ISP or a degraded LAN link is invisible until something *important* breaks. FTS Net Mon shows you exactly which hop is misbehaving, when, and for how long.

> Pure-stdlib Python. No `pip install` required. One command to run.

---

## Table of contents

- [Highlights](#highlights)
- [Screenshots](#screenshots)
- [Requirements](#requirements)
- [Quick start](#quick-start)
- [CLI flags](#cli-flags)
- [First-run setup](#first-run-setup)
- [Configuration](#configuration)
- [HTTP API](#http-api)
- [How it works](#how-it-works)
- [Project layout](#project-layout)
- [Security notes](#security-notes)
- [Troubleshooting](#troubleshooting)
- [Roadmap / known issues](#roadmap--known-issues)
- [License](#license)

---

## Highlights

- **ICMP + TCP probes per target**, on independent threads, with configurable intervals
- **Group-aware health rollup** — `LAN` / `ISP1` / `ISP2` so you can tell at a glance which side is broken
- **Rolling history** with loss %, recent loss %, avg / min / max latency, jitter
- **Event log** with state transitions: first fail, sustained DOWN (3 consecutive fails), and recovery
- **First-run setup wizard** that auto-detects your router and DNS server from the active network interface
- **Auto-launches a browser tab** when the web server comes up (opt-out with `--no-browser`)
- **Live web UI** — sparkline per target, latency chart (Chart.js), event tail, settings, network info
- **Optional Tk desktop GUI** for users who prefer a native window (`--gui`)
- **Audible alert on drop** (server-side beep + optional in-browser tone)
- **Network info endpoint** — current interface, gateway, DNS, MAC, DHCP server
- **Event log export** as a plain `.log` file
- **Pure-stdlib** — no `requirements.txt` to install (Chart.js is loaded from a CDN by the web UI)

## Screenshots

The web UI lives at `http://127.0.0.1:8765` and looks roughly like:

```
┌─────────────────────────────────────────────────────────────────────┐
│  FTS Net Mon          [Sound] [Save Log] [Clear Log] [Settings]      │
├─────────────────────────────────────────────────────────────────────┤
│  ISP1: UP    ISP2: —    LAN: UP                  2026-04-29 12:34:56│
│                                                  Uptime 02:11:47    │
├─────────────────────────────────────────────────────────────────────┤
│  HOST NETWORK   Hostname / Interface / IPv4 / Gateway / DNS / MAC   │
├─────────────────────────────────────────────────────────────────────┤
│  ┌───────── Router (ICMP) ─────────┐  ┌───── DNS Server (TCP:53) ─┐ │
│  │ ●  OK  •  1 ms                  │  │ ●  OK  •  4 ms             │ │
│  │ LAST AVG MIN MAX JIT LOSS       │  │ LAST AVG MIN MAX JIT LOSS  │ │
│  │ ▁▂▁▁▂▁▁▂▁▁▂▁ sparkline          │  │ ▁▂▂▁▂▁▂▁▂▁ sparkline       │ │
│  └─────────────────────────────────┘  └────────────────────────────┘ │
│  Latency History (Chart.js, all targets)                            │
│  [Events tail]                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

The companion Tk GUI mirrors the web UI in a native window (status banner, per-target cards with sparklines, event log, settings dialog).

## Requirements

| Component | Notes |
| --- | --- |
| Python | **3.10+** (uses `list[T]` / `dict[K, V]` PEP 585 generics) |
| OS | Windows 10 / 11, macOS, or Linux |
| `ping` binary | Used by the ICMP probe — present out of the box on all supported OSes |
| Tk | Only required for `--gui`. Bundled with CPython on Windows/macOS. On Debian/Ubuntu: `sudo apt install python3-tk` |
| Browser | Any modern browser for the web UI; Chart.js is loaded from `cdn.jsdelivr.net` |

## Quick start

Clone the repo and launch:

```bash
git clone https://github.com/<your-org>/FTS-Network-Monitor.git
cd FTS-Network-Monitor
python fts_netmon.py
```

That's it — the web UI opens in your default browser at `http://127.0.0.1:8765`. The first launch shows a quick-setup dialog pre-filled with values from your active network interface; confirm or edit, then save.

### Common variations

```bash
python fts_netmon.py --gui                # web UI + native Tk window
python fts_netmon.py --gui --no-web       # native Tk only, no web server
python fts_netmon.py --no-browser         # don't auto-open a tab
python fts_netmon.py --bind 0.0.0.0       # expose web UI on the LAN (see security notes)
python fts_netmon.py --port 9090          # change the web port
```

By default only the web UI runs — the Tk desktop GUI is **off** unless `--gui` is passed.

## CLI flags

| Flag | Description | Default |
| --- | --- | --- |
| `--gui` | Also launch the Tk desktop GUI | off |
| `--no-web` | Disable the web UI (requires `--gui`) | off |
| `--no-browser` | Don't auto-open a browser tab on startup | off |
| `--bind <addr>` | Web UI bind address. Use `0.0.0.0` to expose on the LAN | `127.0.0.1` |
| `--port <n>` | Web UI port | `8765` |

Run `python fts_netmon.py --help` for the live help text.

## First-run setup

When `config.json` is missing, or its `configured` flag is `false`, the web UI opens a **Quick Setup** dialog pre-populated from your active network interface:

- **Router IP** and **ISP1 Gateway** — the default gateway
- **DNS Server** — the first DNS server reported for that interface
- **Upstream Host** — defaults to `8.8.8.8`

Confirm to save and start monitoring, or skip to accept current defaults. The regular **Settings** dialog can be opened at any time to edit values; it triggers a probe restart on save.

Re-trigger the wizard at any time by deleting `config.json` or by setting `configured: false` in it.

Suggestion data comes from `GET /api/setup/suggest`, which is derived from `/api/netinfo`.

## Configuration

`config.json` lives next to the script and is created on first run. Fields:

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `router_ip` | string | `192.168.1.1` | LAN-side router. Probed via ICMP, grouped under **LAN**. |
| `isp1_gateway` | string | *(empty)* | First ISP next-hop. Probed via ICMP, **ISP1**. |
| `isp2_gateway` | string | *(empty)* | Optional second ISP next-hop. Probed via ICMP, **ISP2**. |
| `dns_server` | string | `1.1.1.1` | DNS server. Probed via ICMP **and** TCP:53, **ISP1**. |
| `upstream_host` | string | `8.8.8.8` | Public reachability target. ICMP **and** TCP:443, **ISP1**. |
| `probe_interval` | float (s) | `1.0` | Delay between ICMP probes per target. |
| `tcp_probe_interval` | float (s) | `2.0` | Delay between TCP probes per target. |
| `timeout_ms` | int (ms) | `1000` | Probe timeout. |
| `history_size` | int | `180` | Samples retained per target (drives sparkline / chart length). |
| `sound_on_drop` | bool | `true` | Server-side audible beep on sustained drop. |
| `configured` | bool | `false` | Internal flag. `true` once the setup wizard has been confirmed/skipped. |

**Tips**

- Leave any host field blank to disable that target entirely.
- The "DOWN" state requires **3 consecutive fails**. A single dropped packet is logged as a `FAILED` event but doesn't flip the light to red — this avoids alarm-fatigue from one-off timeouts.
- Increasing `history_size` enlarges the chart window but also the JSON payload returned by `/api/status` (samples are inlined).

## HTTP API

All endpoints are served by the same web process and are read-only except where noted.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/status` | Per-target snapshots (state, stats, samples) and group rollup |
| GET | `/api/config` | Current config as JSON |
| POST | `/api/config` | Update config (JSON body, dict of field updates); restarts probes |
| GET | `/api/events?since=<seq>` | Event log entries with `seq > since` (for live tailing) |
| GET | `/api/events/export` | Full event log as a plain text `.log` file (download) |
| GET | `/api/netinfo?refresh=1` | Local network info: hostname, interfaces, active gateway/DNS |
| GET | `/api/setup/suggest` | Suggested router/DNS values derived from the active interface |

### `/api/status` response shape

```jsonc
{
  "uptime_seconds": 1234,
  "server_time": 1714400000.0,
  "groups": { "LAN": "ok", "ISP1": "ok", "ISP2": "none" },
  "targets": [
    {
      "name": "Router",
      "host": "10.100.10.1",
      "group": "LAN",
      "kind": "icmp",
      "kind_label": "ICMP",
      "status": "ok",
      "stats": {
        "total": 901, "success": 899, "loss_pct": 0.22, "recent_loss_pct": 0.0,
        "avg": 1.4, "min": 0.7, "max": 12.3, "jitter": 0.3, "last": 1.2,
        "consecutive_fail": 0, "consecutive_ok": 87
      },
      "samples": [{ "ok": true, "latency": 1.2, "ts": 1714400000.0 }, ...]
    }
  ]
}
```

Status values: `ok`, `degraded`, `down`, `init`, `none`.

### `POST /api/config`

```bash
curl -X POST http://127.0.0.1:8765/api/config \
  -H 'Content-Type: application/json' \
  -d '{"isp2_gateway": "10.0.2.1", "probe_interval": 0.5}'
```

The server coerces values to the right type (int/float/bool/str), saves `config.json`, and restarts the monitor threads. Unknown keys are silently ignored.

## How it works

```
┌─────────────────────────────────────────────────────────────────┐
│  fts_netmon.py  ── argparse, browser launch, signal handling    │
└──────────┬──────────────────────────────────────────────────────┘
           │
           ▼
     ┌─────────────┐    ┌──────────────────────────────────────┐
     │  AppState   │◄──►│  config.json  (Config dataclass)     │
     │  (app.py)   │    └──────────────────────────────────────┘
     └──────┬──────┘
            │ holds
            ▼
     ┌─────────────┐         ┌──────────────────────────────┐
     │  Monitor    │ spawns  │  per-target ICMP / TCP loop  │
     │ (monitor.py)│ ──────► │  (probes.py + stats.py)      │
     └──────┬──────┘         └──────────────┬───────────────┘
            │                                │ writes
            │                                ▼
            │                        ┌──────────────┐
            │                        │  Stats       │
            │                        │ (stats.py)   │
            │                        └──────────────┘
            │
            │ on transition
            ▼
     ┌──────────────┐
     │  EventLog    │  consumed by GUI + web UI
     │ (events.py)  │
     └──────────────┘

Concurrent UIs (read-only consumers of AppState):
  • web.py    — ThreadingHTTPServer, JSON API, serves static/index.html
  • gui.py    — Tk window, polls AppState every 250 ms
```

- **Probe loop** (`monitor.py`) — one thread per `(target, kind)` pair. Each loop runs the probe, updates `Stats`, emits transition events to the event log, and `wait()`s on a `stop_event` for the configured interval. Restarting probes (e.g. after a config change) signals `stop_event`, joins, and rebuilds the `Monitor`.
- **ICMP probe** — uses the system `ping` binary (`-n 1` on Windows, `-c 1` on Unix) and parses `time=…ms` from the output, falling back to wall-clock elapsed when the line isn't present.
- **TCP probe** — `socket.create_connection((host, port), timeout=…)`. Latency is the connect time.
- **Stats** — rolling deque of `(ok, latency, ts)` tuples (length = `history_size`). Loss % is lifetime; recent loss % is the last 60 samples.
- **Web UI** (`web.py`) — `http.server.ThreadingHTTPServer` exposing the JSON API and serving the single-page UI from `static/`. The page polls `/api/status` once per second and `/api/events?since=<seq>` for tailing.
- **Network info** (`netinfo.py`) — parses `ipconfig /all` (Windows), `ip addr` + `ip route` (Linux), or `ifconfig` + `netstat` (macOS). Cached for 5 seconds.

## Project layout

```
fts_netmon.py     entry point / CLI
app.py            shared AppState (config, monitor, event log)
config.py         Config + Target dataclasses, JSON persistence
monitor.py        probe scheduler / per-target threads
probes.py         ICMP + TCP probe primitives (subprocess + socket)
stats.py          rolling per-target stats (loss, latency, jitter)
events.py         in-memory event log with sequence numbers
netinfo.py        local network info (interfaces, gateway, DNS, MAC)
sound.py          drop alert (winsound on Windows, BEL fallback)
gui.py            Tk desktop GUI (optional; --gui)
web.py            HTTP server + JSON API
static/
  index.html      single-page web UI
config.json       runtime configuration (created on first run)
```

## Security notes

The web UI **has no authentication or CSRF protection**. By default it binds to `127.0.0.1`, so this is fine for a local-only tool. Be aware of the trade-offs before changing that:

- `--bind 0.0.0.0` exposes the UI **and the `POST /api/config` endpoint** to anyone on your network. They can rewrite probe targets, change intervals, or trigger network-info subprocess calls. Don't do this on an untrusted network.
- The web UI loads Chart.js from `cdn.jsdelivr.net`. If you need an air-gapped install, vendor a copy under `static/` and update the `<script src="…">` reference in `static/index.html`.
- The HTTP server runs on the system Python interpreter — keep it patched.

If you need network exposure, put it behind an SSH tunnel or a reverse proxy that adds authentication.

## Troubleshooting

**"Web UI failed to start: address already in use"**
Another process is using port 8765. Pass `--port <n>` to pick a different one.

**ICMP probe always fails on Linux**
On some distros, the `ping` binary requires `cap_net_raw` (set automatically by most package managers). Verify with `ping -c 1 1.1.1.1` from your shell. If that works but FTS Net Mon still reports `unreachable`, run with `--gui` and check the event log for the precise error.

**The "DNS Server" target shows DOWN on TCP:53 even though DNS resolves**
Some recursive resolvers (Cloudflare, some ISP boxes) only answer TCP:53 for actual DNS queries, not bare TCP connects — but most do. If yours doesn't, set the `tcp_port` to something else by editing `config.py` or simply ignore the TCP card and rely on the ICMP one.

**Wizard keeps reappearing on launch**
You're hitting the back-compat heuristic in `Config.load()`. Open `config.json` and set `"configured": true` explicitly.

**macOS ICMP timeout seems too short**
Known quirk: macOS `ping -W` takes milliseconds, not seconds (Linux takes seconds). The current probe code uses the Linux convention. Increase `timeout_ms` in `config.json` or open an issue.

## Roadmap / known issues

- macOS `ping -W` unit mismatch (see Troubleshooting above).
- No authentication / CSRF on the web API — fine for loopback, risky on `0.0.0.0`.
- Lifetime `loss_pct`, `min`, `max` become less responsive over very long runs; use `recent_loss_pct` for an at-a-glance view.
- Probe thread join timeout in `monitor.py` (2.0 s) can be shorter than the worst-case probe duration.
- Linux `/etc/resolv.conf` DNS is reported per-interface even though it's system-wide.

PRs welcome — see the [issues page](https://github.com/<your-org>/FTS-Network-Monitor/issues).

## License

MIT (or whichever the repo owner specifies in `LICENSE`). Pure-stdlib means there are no upstream license issues from third-party Python packages; the bundled web UI links Chart.js from a CDN, which is MIT-licensed.
