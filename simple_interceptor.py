#!/usr/bin/env python3
"""
Standalone simple interceptor — run directly without src/main.py.
Usage:  python simple_interceptor.py [port]
"""

import sys
import os
import signal

# Allow importing from src/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from proxy_interceptor import create_proxy_server
from rich.console import Console

console = Console()


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080

    server = create_proxy_server(port)

    def shutdown(sig, frame):
        console.print("\n[yellow]Shutting down…[/yellow]")
        server.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    console.print(f"[bold green]Simple interceptor running on :{port}[/bold green]")
    console.print(f"[yellow]Set your proxy to http://127.0.0.1:{port}[/yellow]")
    console.print("[dim]Press Ctrl+C to stop[/dim]\n")

    server.serve_forever()


if __name__ == "__main__":
    main()