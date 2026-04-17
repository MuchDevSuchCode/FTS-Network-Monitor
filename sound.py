import platform
import threading

IS_WIN = platform.system() == "Windows"


def play_drop_alert() -> None:
    """Play a non-blocking alert sound when a target transitions to DOWN."""
    def _play() -> None:
        if IS_WIN:
            try:
                import winsound
                winsound.MessageBeep(winsound.MB_ICONHAND)
                return
            except Exception:
                pass
        try:
            print("\a", end="", flush=True)
        except Exception:
            pass

    threading.Thread(target=_play, daemon=True).start()
