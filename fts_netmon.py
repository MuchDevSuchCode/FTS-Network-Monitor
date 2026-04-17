import argparse
import sys
import time
from pathlib import Path

from app import AppState

CONFIG_PATH = Path(__file__).parent / "config.json"


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="fts-netmon",
        description="FTS Net Mon — dual-WAN connectivity monitor",
    )
    parser.add_argument("--headless", action="store_true",
                        help="run without the Tk GUI (web UI only)")
    parser.add_argument("--no-web", action="store_true",
                        help="disable the web UI (Tk GUI only)")
    parser.add_argument("--port", type=int, default=8765,
                        help="web UI port (default: 8765)")
    parser.add_argument("--bind", default="127.0.0.1",
                        help="web UI bind address (default: 127.0.0.1; "
                             "use 0.0.0.0 to expose on the network)")
    args = parser.parse_args()

    if args.headless and args.no_web:
        parser.error("cannot combine --headless with --no-web")

    app = AppState(CONFIG_PATH)
    app.start()

    web = None
    if not args.no_web:
        from web import WebServer
        web = WebServer(app, host=args.bind, port=args.port)
        try:
            web.start()
            url = f"http://{args.bind}:{args.port}"
            app.event_log.add(f"Web UI listening on {url}", "ok")
            print(f"Web UI: {url}")
        except OSError as e:
            app.event_log.add(f"Web UI failed to start: {e}", "fail")
            print(f"Web UI failed to start: {e}", file=sys.stderr)
            web = None

    try:
        if args.headless:
            print("Running headless. Press Ctrl+C to stop.")
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
