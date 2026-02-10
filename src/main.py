import threading
import os
import sys
import signal
import time
import argparse
from pathlib import Path

from local_sniffer import LocalSniffer, check_sudo
from config import Config
from db import get_db
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

console = Console()


class ProxyManager:
    """Main application manager for the Windsurf prompt interceptor"""

    def __init__(self, debug: bool = False):
        self.sniffer = None
        self.running = False
        self.has_sudo = check_sudo()
        self.debug = debug
        self.db = get_db()  # Initialize database connection

    def start_sniffer(self):
        """Start the loopback sniffer for local Windsurf traffic."""
        if not self.has_sudo:
            console.print(
                "[yellow]⚠ Not running as root — loopback sniffer disabled.[/yellow]"
            )
            console.print(
                "[yellow]  To capture Windsurf prompts, run: "
                "[bold]sudo python src/main.py[/bold][/yellow]"
            )
            return

        self.sniffer = LocalSniffer(db=self.db, debug=self.debug)
        self.sniffer.start()
        debug_msg = " (debug mode)" if self.debug else ""
        console.print(f"[green]✓ Loopback sniffer started (capturing d.localhost traffic){debug_msg}[/green]")

    def show_status_panel(self):
        """Display current status information"""
        status_text = Text()
        status_text.append("🔍 Windsurf Prompt Interceptor\n\n", style="bold green")

        # Show database status
        if self.db.is_connected():
            status_text.append("Database: ✅ MongoDB Connected\n", style="green")
        else:
            status_text.append("Database: ❌ MongoDB Disconnected (logging to files)\n", style="yellow")

        # Show sniffer status
        if self.has_sudo:
            status_text.append(
                "Loopback Sniffer: ✅ Active (capturing local Windsurf traffic)\n",
                style="green",
            )
        else:
            status_text.append(
                "Loopback Sniffer: ❌ Inactive (need sudo)\n", style="yellow"
            )

        status_text.append(
            f"Monitoring: {', '.join(Config.get_monitored_patterns()[:5])}…\n",
            style="cyan",
        )

        status_text.append("\n📋 How Windsurf traffic is captured:\n", style="bold yellow")
        status_text.append(
            "🎯 Local prompts (d.localhost) → loopback sniffer (tcpdump)\n",
            style="green" if self.has_sudo else "yellow",
        )

        status_text.append("\n📋 Usage:\n", style="bold yellow")
        if not self.has_sudo:
            status_text.append(
                "⚡ For full capture: sudo python src/main.py\n", style="bold yellow"
            )
        status_text.append(
            "⚡ Open a new Windsurf via: ./launch_windsurf.sh\n", style="yellow"
        )
        status_text.append(
            "⚡ Or just use any Windsurf — sniffer captures ALL local traffic\n",
            style="yellow",
        )
        status_text.append("\nPress Ctrl+C to stop", style="red")

        panel = Panel(status_text, title="Status", border_style="green")
        console.print(panel)

    def start(self):
        """Start the complete interceptor system"""
        try:
            console.print(
                "[bold green]Starting Windsurf Prompt Interceptor…[/bold green]"
            )

            # Connect to database first
            if not self.db.is_connected():
                self.db.connect()

            # Start loopback sniffer (for local d.localhost traffic)
            self.start_sniffer()
            time.sleep(0.5)

            self.running = True
            self.show_status_panel()

            # Keep running until interrupted
            try:
                while self.running:
                    time.sleep(1)
            except KeyboardInterrupt:
                console.print("\n[yellow]Shutting down…[/yellow]")
                self.stop()

        except Exception as e:
            console.print(f"[red]Failed to start interceptor: {e}[/red]")
            self.stop()
            sys.exit(1)

    def stop(self):
        """Stop the interceptor system"""
        try:
            self.running = False

            if self.sniffer:
                self.sniffer.stop()

            if self.db:
                self.db.close()

            console.print("[green]✓ Interceptor stopped[/green]")

        except Exception as e:
            console.print(f"[red]Error during shutdown: {e}[/red]")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Windsurf Prompt Interceptor")
    parser.add_argument(
        "--debug", "-d", 
        action="store_true", 
        help="Enable debug logging for troubleshooting missed prompts"
    )
    args = parser.parse_args()

    def signal_handler(signum, frame):
        console.print("\n[yellow]Received interrupt signal[/yellow]")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Create logs directory
    os.makedirs("logs", exist_ok=True)
    
    if args.debug:
        console.print("[yellow]🐛 Debug mode enabled - verbose logging active[/yellow]")

    # Start the manager
    manager = ProxyManager(debug=args.debug)
    manager.start()


if __name__ == "__main__":
    main()