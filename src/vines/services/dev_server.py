from functools import partial
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
import time

try:
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer
    HAS_WATCHDOG = True
except ImportError:
    HAS_WATCHDOG = False


if HAS_WATCHDOG:
    class NotesWatchHandler(FileSystemEventHandler):
        def __init__(self, builder):
            super().__init__()
            self.builder = builder
            self._last_trigger = 0.0

        def on_any_event(self, event):
            if event.is_directory:
                return
            src_path = str(event.src_path)
            if src_path.endswith(".md") or src_path.endswith(".css"):
                now = time.time()
                if now - self._last_trigger > 0.5:
                    self._last_trigger = now
                    time.sleep(0.1)
                    print(f"\n[Watchdog] Change detected in '{event.src_path}'. Rebuilding...")
                    try:
                        self.builder.build()
                    except Exception as e:
                        print(f"[Error] Rebuild failed: {e}")


def start_watcher(builder, input_dir: Path):
    if not HAS_WATCHDOG:
        print("\n[Watchdog] Note: 'watchdog' package is not installed (pip install watchdog)\n")
        return None
    handler = NotesWatchHandler(builder)
    observer = Observer()
    observer.schedule(handler, str(input_dir.resolve()), recursive=True)
    observer.daemon = True
    observer.start()
    print(f"[Watchdog] Active. Watching '{input_dir.resolve()}'...")
    return observer


class NoCacheHTTPRequestHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()


def serve_site(output_dir: Path, port: int = 8000):
    handler = partial(NoCacheHTTPRequestHandler, directory=str(output_dir.resolve()))
    httpd = HTTPServer(("0.0.0.0", port), handler)
    print(f"Serving local wiki at http://localhost:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server.")