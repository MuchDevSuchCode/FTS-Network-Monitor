import argparse
import sys
import threading
import time
import webbrowser
from pathlib import Path

from app import AppState

CONFIG_PATH = Path(__file__).parent / "config.json"


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="fts-netmon",
        description="FTS Net Mon — dual-WAN connectivity monitor",
    )
    parser.add_argument("--gui", action="store_true",
                        help="also launch the Tk desktop GUI "
                             "(off by default; web UI is primary)")
    parser.add_argument("--no-web", action="store_true",
                        help="disable the web UI (requires --gui)")
    parser.add_argument("--no-browser", action="store_true",
                        help="don't auto-open a browser tab on startup")
    parser.add_argument("--port", type=int, default=8765,
                        help="web UI port (default: 8765)")
    parser.add_argument("--bind", default="127.0.0.1",
                        help="web UI bind address (default: 127.0.0.1; "
                             "use 0.0.0.0 to expose on the network)")
    args = parser.parse_args()

    if args.no_web and not args.gui:
        parser.error("--no-web requires --gui (otherwise there's no UI)")

    app = AppState(CONFIG_PATH)
    app.start()

    web = None
    url = None
    if not args.no_web:
        from web import WebServer
        web = WebServer(app, host=args.bind, port=args.port)
        try:
            web.start()
            browse_host = "127.0.0.1" if args.bind in ("0.0.0.0", "::") else args.bind
            url = f"http://{browse_host}:{args.port}"
            app.event_log.add(f"Web UI listening on {url}", "ok")
            print(f"Web UI: {url}")
        except OSError as e:
            app.event_log.add(f"Web UI failed to start: {e}", "fail")
            print(f"Web UI failed to start: {e}", file=sys.stderr)
            web = None

    if web is not None and url and not args.no_browser:
        # Small delay so the server is fully ready before the browser hits it.
        threading.Timer(0.6, lambda: webbrowser.open(url, new=2)).start()

    try:
        if not args.gui:
            print("Press Ctrl+C to stop.")
            while True:
                time.sleep(1)
        else:
            import tkinter as tk
            from gui import NetMonApp

            root = tk.Tk()
            NetMonApp(root, app)

            def on_close() -> None:
                root.destroy()

            root.protocol("WM_DELETE_WINDOW", on_close)
            root.mainloop()
    except KeyboardInterrupt:
        pass
    finally:
        app.stop()
        if web is not None:
            web.stop()


if __name__ == "__main__":
    main()
