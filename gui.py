import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox

from app import AppState
from events import format_log
from netinfo import get_network_info

COLOR_BG = "#14141c"
COLOR_CARD = "#1f1f2c"
COLOR_CARD_ALT = "#181824"
COLOR_OK = "#4caf50"
COLOR_WARN = "#ff9800"
COLOR_FAIL = "#f44336"
COLOR_TEXT = "#f0f0f0"
COLOR_MUTED = "#8a8a9a"
COLOR_ACCENT = "#4fc3f7"
COLOR_GRID = "#2a2a38"


class StatusCard(tk.Frame):
    def __init__(self, parent, title: str, subtitle: str):
        super().__init__(parent, bg=COLOR_CARD, bd=0, relief="flat", padx=14, pady=12)
        self.configure(highlightbackground=COLOR_GRID, highlightthickness=1)

        header = tk.Frame(self, bg=COLOR_CARD)
        header.pack(fill="x")

        self.light = tk.Canvas(header, width=18, height=18, bg=COLOR_CARD, highlightthickness=0)
        self.light.pack(side="left", padx=(0, 8))
        self._draw_light(COLOR_MUTED)

        title_frame = tk.Frame(header, bg=COLOR_CARD)
        title_frame.pack(side="left", fill="x", expand=True)
        tk.Label(title_frame, text=title, bg=COLOR_CARD, fg=COLOR_TEXT,
                 font=("Segoe UI", 11, "bold"), anchor="w").pack(anchor="w")
        tk.Label(title_frame, text=subtitle, bg=COLOR_CARD, fg=COLOR_MUTED,
                 font=("Segoe UI", 8), anchor="w").pack(anchor="w")

        self.status_label = tk.Label(self, text="initializing…", bg=COLOR_CARD,
                                     fg=COLOR_MUTED, font=("Segoe UI", 9, "bold"))
        self.status_label.pack(anchor="w", pady=(8, 4))

        stats = tk.Frame(self, bg=COLOR_CARD)
        stats.pack(fill="x", pady=(2, 6))
        self.last_val = self._stat_box(stats, "LAST", 0)
        self.avg_val = self._stat_box(stats, "AVG", 1)
        self.min_val = self._stat_box(stats, "MIN", 2)
        self.max_val = self._stat_box(stats, "MAX", 3)
        self.jit_val = self._stat_box(stats, "JIT", 4)
        self.loss_val = self._stat_box(stats, "LOSS", 5)
        for i in range(6):
            stats.grid_columnconfigure(i, weight=1, uniform="stat")

        self.spark = tk.Canvas(self, height=52, bg=COLOR_CARD_ALT, highlightthickness=0)
        self.spark.pack(fill="x", pady=(4, 0))

    def _stat_box(self, parent, label: str, col: int) -> tk.Label:
        frame = tk.Frame(parent, bg=COLOR_CARD)
        frame.grid(row=0, column=col, sticky="nsew", padx=2)
        tk.Label(frame, text=label, bg=COLOR_CARD, fg=COLOR_MUTED,
                 font=("Segoe UI", 7, "bold")).pack()
        val = tk.Label(frame, text="—", bg=COLOR_CARD, fg=COLOR_TEXT,
                       font=("Consolas", 10, "bold"))
        val.pack()
        return val

    def _draw_light(self, color: str) -> None:
        self.light.delete("all")
        self.light.create_oval(3, 3, 16, 16, fill=color, outline=color)
        self.light.create_oval(5, 5, 10, 10, fill="#ffffff", outline="", stipple="gray50")

    def update_from_snapshot(self, snap: dict, kind_label: str) -> None:
        if snap["consecutive_fail"] >= 3:
            color = COLOR_FAIL
            text = f"DOWN  •  {snap['consecutive_fail']} consecutive fails"
        elif snap["recent_loss_pct"] > 10:
            color = COLOR_WARN
            text = f"DEGRADED  •  {snap['recent_loss_pct']:.0f}% recent loss"
        elif snap["consecutive_fail"] > 0:
            color = COLOR_WARN
            text = f"FLAPPING  •  {snap['consecutive_fail']} fail"
        elif snap["total"] == 0:
            color = COLOR_MUTED
            text = "initializing…"
        else:
            color = COLOR_OK
            text = f"OK  •  {snap['last']:.0f} ms"

        self._draw_light(color)
        self.status_label.config(text=f"{kind_label}   {text}", fg=color)

        def fmt(v):
            return f"{v:.1f}" if v else "—"

        self.last_val.config(text=f"{snap['last']:.1f}" if snap["last"] else "—")
        self.avg_val.config(text=fmt(snap["avg"]))
        self.min_val.config(text=fmt(snap["min"]))
        self.max_val.config(text=fmt(snap["max"]))
        self.jit_val.config(text=fmt(snap["jitter"]))
        self.loss_val.config(text=f"{snap['loss_pct']:.1f}%")

        self._draw_sparkline(snap["samples"])

    def _draw_sparkline(self, samples: list) -> None:
        self.spark.delete("all")
        self.spark.update_idletasks()
        w = max(self.spark.winfo_width(), 200)
        h = int(self.spark["height"])
        n = len(samples)
        if n == 0:
            return

        lats = [l for ok, l, _ in samples if ok and l is not None]
        max_l = max(lats) if lats else 1.0
        max_l = max(max_l, 5.0)

        self.spark.create_line(0, h - 1, w, h - 1, fill=COLOR_GRID)
        mid = h - 2 - 0.5 * (h - 6)
        self.spark.create_line(0, mid, w, mid, fill=COLOR_GRID, dash=(2, 4))

        step = w / max(n - 1, 1)
        points: list[tuple[float, float]] = []
        for i, (ok, l, _) in enumerate(samples):
            x = i * step
            if not ok or l is None:
                self.spark.create_line(x, 2, x, h - 2, fill=COLOR_FAIL, width=1)
                if len(points) >= 2:
                    flat = [c for p in points for c in p]
                    self.spark.create_line(*flat, fill=COLOR_ACCENT, width=1.6)
                points = []
                continue
            y = h - 3 - (min(l, max_l) / max_l) * (h - 8)
            points.append((x, y))

        if len(points) >= 2:
            flat = [c for p in points for c in p]
            self.spark.create_line(*flat, fill=COLOR_ACCENT, width=1.6)

        self.spark.create_text(w - 4, 2, anchor="ne", fill=COLOR_MUTED,
                               font=("Consolas", 7), text=f"{max_l:.0f}ms")


class HostNetworkPane(tk.Frame):
    FIELDS = [
        ("hostname", "Hostname"),
        ("interface", "Interface"),
        ("ipv4", "IPv4 Address"),
        ("subnet", "Subnet"),
        ("gateway", "Default Gateway"),
        ("dns", "DNS Servers"),
        ("mac", "MAC Address"),
        ("dhcp", "DHCP"),
        ("outbound", "Outbound IP"),
    ]

    def __init__(self, parent, on_refresh):
        super().__init__(parent, bg=COLOR_CARD, bd=0,
                         highlightbackground=COLOR_GRID, highlightthickness=1)
        self._on_refresh_cb = on_refresh

        header = tk.Frame(self, bg=COLOR_CARD, padx=16, pady=10)
        header.pack(fill="x")
        tk.Label(header, text="HOST NETWORK", bg=COLOR_CARD, fg=COLOR_MUTED,
                 font=("Segoe UI", 8, "bold")).pack(side="left")
        self.fetched_label = tk.Label(
            header, text="", bg=COLOR_CARD, fg=COLOR_MUTED,
            font=("Segoe UI", 8),
        )
        self.fetched_label.pack(side="left", padx=(10, 0))
        self.refresh_btn = tk.Button(
            header, text="Refresh", command=self._on_refresh_cb,
            bg=COLOR_CARD_ALT, fg=COLOR_TEXT, relief="flat",
            padx=10, pady=2, font=("Segoe UI", 8),
            activebackground=COLOR_GRID, activeforeground=COLOR_TEXT,
        )
        self.refresh_btn.pack(side="right")

        body = tk.Frame(self, bg=COLOR_CARD)
        body.pack(fill="x", padx=16, pady=(0, 12))

        self.value_labels: dict[str, tk.Label] = {}
        for i, (key, label) in enumerate(self.FIELDS):
            row = i // 2
            col = (i % 2) * 2
            tk.Label(body, text=label, bg=COLOR_CARD, fg=COLOR_MUTED,
                     font=("Segoe UI", 8, "bold"),
                     anchor="w").grid(row=row, column=col, sticky="w",
                                      padx=(0, 10), pady=2)
            val = tk.Label(body, text="—", bg=COLOR_CARD, fg=COLOR_TEXT,
                           font=("Consolas", 10), anchor="w")
            val.grid(row=row, column=col + 1, sticky="ew",
                     padx=(0, 24), pady=2)
            self.value_labels[key] = val

        body.grid_columnconfigure(1, weight=1, uniform="netval")
        body.grid_columnconfigure(3, weight=1, uniform="netval")

    def set_loading(self) -> None:
        self.refresh_btn.config(text="Refreshing…", state="disabled")

    def update_data(self, info: dict) -> None:
        self.refresh_btn.config(text="Refresh", state="normal")
        active = info.get("active") or {}

        self.value_labels["hostname"].config(text=info.get("hostname") or "—")

        name = active.get("name", "")
        desc = active.get("description", "")
        iface = name + (f"  —  {desc}" if desc else "")
        self.value_labels["interface"].config(text=iface or "—")

        self.value_labels["ipv4"].config(
            text=active.get("ipv4") or info.get("primary_ip") or "—")
        self.value_labels["subnet"].config(
            text=active.get("cidr") or active.get("subnet_mask") or "—")
        self.value_labels["gateway"].config(text=active.get("gateway") or "—")

        dns = active.get("dns_servers") or []
        self.value_labels["dns"].config(text=", ".join(dns) if dns else "—")

        self.value_labels["mac"].config(text=active.get("mac") or "—")

        dhcp = active.get("dhcp")
        if dhcp is True:
            dhcp_text = "Yes"
            if active.get("dhcp_server"):
                dhcp_text += f"  (server {active['dhcp_server']})"
        elif dhcp is False:
            dhcp_text = "No (static)"
        else:
            dhcp_text = "—"
        self.value_labels["dhcp"].config(text=dhcp_text)

        outbound = info.get("outbound_iface") or {}
        primary_ip = info.get("primary_ip") or "—"
        if outbound and outbound.get("name") and outbound.get("name") != active.get("name"):
            self.value_labels["outbound"].config(
                text=f"{primary_ip}  (via {outbound['name']})",
                fg=COLOR_WARN,
            )
        else:
            self.value_labels["outbound"].config(text=primary_ip, fg=COLOR_TEXT)

        ts = info.get("fetched_at") or time.time()
        self.fetched_label.config(
            text=f"· updated {time.strftime('%H:%M:%S', time.localtime(ts))}"
        )


class SettingsDialog:
    FIELDS = [
        ("router_ip", "Router IP", str),
        ("isp1_gateway", "ISP1 Gateway", str),
        ("dns_server", "DNS Server", str),
        ("upstream_host", "Upstream Host", str),
        ("isp2_gateway", "ISP2 Gateway", str),
        ("probe_interval", "ICMP Interval (s)", float),
        ("tcp_probe_interval", "TCP Interval (s)", float),
        ("timeout_ms", "Timeout (ms)", int),
        ("history_size", "History Size", int),
        ("sound_on_drop", "Beep on Drop", bool),
    ]

    def __init__(self, parent, app: AppState):
        self.app = app
        self.saved = False
        self.top = tk.Toplevel(parent)
        self.top.title("FTS Net Mon — Settings")
        self.top.configure(bg=COLOR_BG)
        self.top.geometry("460x460")
        self.top.transient(parent)
        self.top.grab_set()

        frm = tk.Frame(self.top, bg=COLOR_BG, padx=22, pady=18)
        frm.pack(fill="both", expand=True)

        tk.Label(frm, text="Connectivity Targets", bg=COLOR_BG, fg=COLOR_ACCENT,
                 font=("Segoe UI", 11, "bold")).grid(row=0, column=0, columnspan=2,
                                                     sticky="w", pady=(0, 8))

        self.vars: dict[str, tk.Variable] = {}
        for i, (key, label, typ) in enumerate(self.FIELDS, start=1):
            tk.Label(frm, text=label, bg=COLOR_BG, fg=COLOR_TEXT,
                     font=("Segoe UI", 10)).grid(row=i, column=0, sticky="w", pady=4)
            if typ is bool:
                var = tk.IntVar(value=1 if getattr(app.config, key) else 0)
                tk.Checkbutton(
                    frm, variable=var, bg=COLOR_BG, fg=COLOR_TEXT,
                    selectcolor=COLOR_CARD, activebackground=COLOR_BG,
                    activeforeground=COLOR_TEXT, bd=0, highlightthickness=0,
                ).grid(row=i, column=1, sticky="w", padx=8, pady=4)
            else:
                var = tk.StringVar(value=str(getattr(app.config, key)))
                tk.Entry(
                    frm, textvariable=var, bg=COLOR_CARD, fg=COLOR_TEXT,
                    insertbackground=COLOR_TEXT, relief="flat", width=24,
                    highlightthickness=1, highlightbackground=COLOR_GRID,
                    highlightcolor=COLOR_ACCENT,
                ).grid(row=i, column=1, sticky="ew", padx=8, pady=4, ipady=3)
            self.vars[key] = var

        frm.grid_columnconfigure(1, weight=1)

        btns = tk.Frame(self.top, bg=COLOR_BG)
        btns.pack(fill="x", padx=22, pady=(0, 16))
        tk.Button(btns, text="Cancel", command=self.top.destroy,
                  bg=COLOR_CARD, fg=COLOR_TEXT, relief="flat", padx=16, pady=6,
                  activebackground=COLOR_GRID, activeforeground=COLOR_TEXT,
                  ).pack(side="right", padx=(6, 0))
        tk.Button(btns, text="Save & Restart", command=self._save,
                  bg=COLOR_ACCENT, fg="#000000", relief="flat", padx=16, pady=6,
                  activebackground=COLOR_OK, activeforeground="#000000",
                  font=("Segoe UI", 9, "bold"),
                  ).pack(side="right")

    def _save(self) -> None:
        try:
            for key, _label, typ in self.FIELDS:
                var = self.vars[key]
                if typ is bool:
                    setattr(self.app.config, key, bool(var.get()))
                    continue
                raw = var.get().strip()
                if typ is str:
                    setattr(self.app.config, key, raw)
                elif typ is int:
                    setattr(self.app.config, key, int(raw))
                elif typ is float:
                    setattr(self.app.config, key, float(raw))
            self.saved = True
            self.top.destroy()
        except ValueError as e:
            messagebox.showerror("Invalid Settings", f"Could not parse value: {e}")


class NetMonApp:
    def __init__(self, root: tk.Tk, app: AppState):
        self.root = root
        self.app = app
        self.cards: dict[tuple[str, str], tuple[StatusCard, str, str]] = {}
        self._last_event_seq = 0
        self._last_targets_key = ""

        root.title("FTS Net Mon")
        root.configure(bg=COLOR_BG)
        root.geometry("1000x760")
        root.minsize(820, 600)

        self._build_ui()
        self._schedule_refresh()
        self._refresh_netinfo()
        self.root.after(30000, self._periodic_netinfo)

    def _build_ui(self) -> None:
        header = tk.Frame(self.root, bg=COLOR_BG, padx=18, pady=14)
        header.pack(fill="x")

        title_box = tk.Frame(header, bg=COLOR_BG)
        title_box.pack(side="left")
        tk.Label(title_box, text="FTS Net Mon", bg=COLOR_BG, fg=COLOR_ACCENT,
                 font=("Segoe UI", 20, "bold")).pack(anchor="w")
        tk.Label(title_box, text="Dual-WAN Connectivity Monitor", bg=COLOR_BG,
                 fg=COLOR_MUTED, font=("Segoe UI", 9)).pack(anchor="w")

        btns = tk.Frame(header, bg=COLOR_BG)
        btns.pack(side="right")
        for text, cmd in [("Save Log", self._save_log),
                          ("Clear Log", self._clear_log),
                          ("Settings", self._open_settings)]:
            tk.Button(btns, text=text, command=cmd,
                      bg=COLOR_CARD, fg=COLOR_TEXT, relief="flat",
                      padx=14, pady=6, font=("Segoe UI", 9),
                      activebackground=COLOR_GRID, activeforeground=COLOR_TEXT,
                      ).pack(side="left", padx=4)

        self.banner = tk.Frame(self.root, bg=COLOR_CARD, padx=18, pady=12,
                               highlightbackground=COLOR_GRID, highlightthickness=1)
        self.banner.pack(fill="x", padx=18, pady=(0, 10))

        self.host_net_pane = HostNetworkPane(self.root, on_refresh=self._refresh_netinfo)
        self.host_net_pane.pack(fill="x", padx=18, pady=(0, 10))

        self.isp1_label = self._banner_label(self.banner, "ISP1")
        self.isp2_label = self._banner_label(self.banner, "ISP2")
        self.lan_label = self._banner_label(self.banner, "LAN")

        self.uptime_label = tk.Label(self.banner, text="Uptime: 00:00:00",
                                     bg=COLOR_CARD, fg=COLOR_MUTED,
                                     font=("Consolas", 10))
        self.uptime_label.pack(side="right")
        self.clock_label = tk.Label(self.banner, text="", bg=COLOR_CARD,
                                    fg=COLOR_MUTED, font=("Consolas", 10))
        self.clock_label.pack(side="right", padx=(0, 16))

        container = tk.Frame(self.root, bg=COLOR_BG)
        container.pack(fill="both", expand=True, padx=18, pady=(0, 8))

        self.cards_frame = tk.Frame(container, bg=COLOR_BG)
        self.cards_frame.pack(fill="both", expand=True)

        self._build_cards()

        log_frame = tk.Frame(self.root, bg=COLOR_BG)
        log_frame.pack(fill="x", padx=18, pady=(0, 14))
        tk.Label(log_frame, text="EVENTS", bg=COLOR_BG, fg=COLOR_MUTED,
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(0, 4))
        self.log = tk.Text(log_frame, height=8, bg=COLOR_CARD, fg=COLOR_TEXT,
                           font=("Consolas", 9), relief="flat", bd=0,
                           highlightthickness=1, highlightbackground=COLOR_GRID)
        self.log.pack(fill="x")
        self.log.tag_config("ok", foreground=COLOR_OK)
        self.log.tag_config("warn", foreground=COLOR_WARN)
        self.log.tag_config("fail", foreground=COLOR_FAIL)
        self.log.tag_config("info", foreground=COLOR_TEXT)
        self.log.tag_config("muted", foreground=COLOR_MUTED)

    def _banner_label(self, parent, group: str) -> tk.Label:
        frame = tk.Frame(parent, bg=COLOR_CARD)
        frame.pack(side="left", padx=(0, 22))
        tk.Label(frame, text=group, bg=COLOR_CARD, fg=COLOR_MUTED,
                 font=("Segoe UI", 8, "bold")).pack(anchor="w")
        lbl = tk.Label(frame, text="—", bg=COLOR_CARD, fg=COLOR_MUTED,
                       font=("Segoe UI", 14, "bold"))
        lbl.pack(anchor="w")
        return lbl

    def _targets_key(self) -> str:
        parts = []
        for t in self.app.config.targets():
            if t.icmp:
                parts.append(f"{t.name}|icmp|{t.host}|{t.group}")
            if t.tcp_port:
                parts.append(f"{t.name}|tcp:{t.tcp_port}|{t.host}|{t.group}")
        return ";".join(parts)

    def _build_cards(self) -> None:
        for w in self.cards_frame.winfo_children():
            w.destroy()
        self.cards.clear()

        col = 0
        row = 0
        for target in self.app.config.targets():
            kinds: list[tuple[str, str]] = []
            if target.icmp:
                kinds.append(("icmp", "ICMP"))
            if target.tcp_port:
                kinds.append((f"tcp:{target.tcp_port}", f"TCP:{target.tcp_port}"))
            for kind_key, kind_label in kinds:
                subtitle = f"{target.host}   •   {target.group}"
                card = StatusCard(self.cards_frame,
                                  f"{target.name}  —  {kind_label}", subtitle)
                card.grid(row=row, column=col, sticky="nsew", padx=6, pady=6)
                self.cards[(target.name, kind_key)] = (card, kind_label, target.group)
                col += 1
                if col >= 2:
                    col = 0
                    row += 1

        for c in range(2):
            self.cards_frame.grid_columnconfigure(c, weight=1, uniform="card")

        self._last_targets_key = self._targets_key()

    def _schedule_refresh(self) -> None:
        # Rebuild cards if targets changed (e.g. config updated externally)
        if self._targets_key() != self._last_targets_key:
            self._build_cards()

        # Pull new events
        new_events = self.app.event_log.since(self._last_event_seq)
        for e in new_events:
            self._last_event_seq = max(self._last_event_seq, e["seq"])
            self._log(e["message"], e["severity"])

        # Refresh cards
        for (tname, kkey), (card, kind_label, _g) in self.cards.items():
            stats = self.app.monitor.stats.get((tname, kkey))
            if stats:
                card.update_from_snapshot(stats.snapshot(), kind_label)

        self._update_banner()
        self.root.after(250, self._schedule_refresh)

    def _update_banner(self) -> None:
        groups: dict[str, list[dict]] = {"ISP1": [], "ISP2": [], "LAN": []}
        for (tname, kkey), (_card, _label, group) in self.cards.items():
            stats = self.app.monitor.stats.get((tname, kkey))
            if not stats:
                continue
            groups.setdefault(group, []).append(stats.snapshot())

        def status(snaps: list[dict]) -> tuple[str, str]:
            if not snaps:
                return "—", COLOR_MUTED
            if any(s["total"] == 0 for s in snaps):
                return "…", COLOR_MUTED
            if any(s["consecutive_fail"] >= 3 for s in snaps):
                return "DOWN", COLOR_FAIL
            if any(s["recent_loss_pct"] > 10 or s["consecutive_fail"] > 0 for s in snaps):
                return "DEGRADED", COLOR_WARN
            return "UP", COLOR_OK

        text, color = status(groups.get("ISP1", []))
        self.isp1_label.config(text=text, fg=color)
        text, color = status(groups.get("ISP2", []))
        self.isp2_label.config(text=text, fg=color)
        text, color = status(groups.get("LAN", []))
        self.lan_label.config(text=text, fg=color)

        uptime = int(time.time() - self.app.start_time)
        h, rem = divmod(uptime, 3600)
        m, s = divmod(rem, 60)
        self.uptime_label.config(text=f"Uptime: {h:02d}:{m:02d}:{s:02d}")
        self.clock_label.config(text=time.strftime("%Y-%m-%d %H:%M:%S"))

    def _log(self, msg: str, severity: str = "info") -> None:
        tag = {"ok": "ok", "warn": "warn", "fail": "fail"}.get(severity, "info")
        ts = time.strftime("%H:%M:%S")
        self.log.insert("end", f"[{ts}] ", "muted")
        self.log.insert("end", msg + "\n", tag)
        self.log.see("end")
        lines = int(self.log.index("end-1c").split(".")[0])
        if lines > 500:
            self.log.delete("1.0", f"{lines - 400}.0")

    def _clear_log(self) -> None:
        self.log.delete("1.0", "end")

    def _save_log(self) -> None:
        default_name = f"fts-netmon-{time.strftime('%Y%m%d-%H%M%S')}.log"
        filename = filedialog.asksaveasfilename(
            parent=self.root,
            title="Save Event Log",
            defaultextension=".log",
            initialfile=default_name,
            filetypes=[("Log files", "*.log"), ("Text files", "*.txt"),
                       ("All files", "*.*")],
        )
        if not filename:
            return
        try:
            with open(filename, "w", encoding="utf-8") as f:
                f.write(format_log(self.app.event_log.all()))
        except OSError as e:
            messagebox.showerror("Save Failed", str(e))
            return
        self.app.event_log.add(f"Log saved to {filename}", "ok")

    def _refresh_netinfo(self) -> None:
        self.host_net_pane.set_loading()

        def worker() -> None:
            try:
                info = get_network_info(force_refresh=True)
            except Exception as e:
                info = {"error": str(e)}
            try:
                self.root.after(0, lambda: self.host_net_pane.update_data(info))
            except (RuntimeError, tk.TclError):
                pass  # window closed during fetch

        threading.Thread(target=worker, daemon=True).start()

    def _periodic_netinfo(self) -> None:
        self._refresh_netinfo()
        self.root.after(30000, self._periodic_netinfo)

    def _open_settings(self) -> None:
        dlg = SettingsDialog(self.root, self.app)
        self.root.wait_window(dlg.top)
        if dlg.saved:
            self.app.apply_config_changes()
            self._build_cards()
