"""
repo-conn CLI entrypoint.

Usage:
    repo-conn                    # default: http://127.0.0.1:8000
    repo-conn --port 9000
    repo-conn --host 0.0.0.0    # expose on LAN
    repo-conn --no-browser       # skip auto-open
"""
from __future__ import annotations

import argparse
import os
import sys
import threading
import time
import webbrowser


def _open_browser(url: str, delay: float = 1.4) -> None:
    """Open the browser after a short delay so uvicorn has time to bind."""
    time.sleep(delay)
    webbrowser.open(url)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="repo-conn",
        description="GitHub Repository Interconnect — launch the web UI.",
    )
    parser.add_argument(
        "--host",
        default=os.getenv("HOST", "127.0.0.1"),
        help="Bind host (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("PORT", "8000")),
        help="Bind port (default: 8000)",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        default=False,
        help="Do not open the browser automatically",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        default=False,
        help="Enable uvicorn auto-reload (development only)",
    )
    args = parser.parse_args()

    url = f"http://{args.host}:{args.port}"

    print()
    print("  ╔══════════════════════════════════════════╗")
    print("  ║   GitHub Repository Interconnect  v1.1   ║")
    print("  ╚══════════════════════════════════════════╝")
    print()
    print(f"  🚀  Server  →  {url}")
    print(f"  🔌  API     →  {url}/docs")
    print()

    if not args.no_browser:
        threading.Thread(
            target=_open_browser,
            args=(url,),
            daemon=True,
        ).start()

    try:
        import uvicorn
    except ImportError:
        print("ERROR: uvicorn is not installed. Run: pip install 'uvicorn[standard]'")
        sys.exit(1)

    uvicorn.run(
        "backend.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
