import argparse
import sys
import time
from pathlib import Path

# Fix sys.path if running directly as a script
if __name__ == "__main__" and __package__ is None:
    file_path = Path(__file__).resolve()
    # Add 'src' (parent of 'vines') to sys.path
    sys.path.insert(0, str(file_path.parent.parent))
    __package__ = "vines"

from vines.services.builder import WikiBuilder
from vines.services.dev_server import serve_site, start_watcher


def main():
    parser = argparse.ArgumentParser(description="vines Static Wiki Builder")
    parser.add_argument("--input", "-i", default="notes", help="Source directory containing markdown notes")
    parser.add_argument("--output", "-o", default="dist", help="Target output directory")
    parser.add_argument("--serve", "-s", action="store_true", help="Start development HTTP server with watch mode")
    parser.add_argument("--watch", "-w", action="store_true", help="Watch notes directory for continuous auto-rebuilds")
    parser.add_argument("--port", "-p", type=int, default=8000, help="Dev server port")
    parser.add_argument("--theme", "-t", default="default", help="Theme name (e.g., solarized, basic)")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    builder = WikiBuilder(Path(args.input), Path(args.output), theme_name=args.theme)
    builder.build()

    should_watch = args.watch or args.serve
    observer = start_watcher(builder, input_path) if should_watch else None

    if args.serve:
        serve_site(output_path, args.port)
    elif args.watch:
        print("Press Ctrl+C to stop watching.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            if observer:
                observer.stop()


if __name__ == "__main__":
    main()