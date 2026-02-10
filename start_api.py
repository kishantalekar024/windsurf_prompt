#!/usr/bin/env python3
"""
Standalone API server to expose captured Windsurf prompts.

Usage:
    python start_api.py                    # Start on default port 8000
    python start_api.py --port 3000       # Start on custom port
    python start_api.py --host 0.0.0.0    # Bind to all interfaces
"""

import argparse
import os
import sys
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from api import start_api_server
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

console = Console()


def main():
    parser = argparse.ArgumentParser(description="Windsurf Prompt API Server")
    parser.add_argument(
        "--host", 
        default="127.0.0.1", 
        help="Host to bind to (default: 127.0.0.1, use 0.0.0.0 for all interfaces)"
    )
    parser.add_argument(
        "--port", 
        type=int, 
        default=8000, 
        help="Port to run on (default: 8000)"
    )
    
    args = parser.parse_args()
    
    # Show startup info
    status_text = Text()
    status_text.append("🚀 Windsurf Prompt API Server\n\n", style="bold green")
    status_text.append(f"📡 Server: http://{args.host}:{args.port}\n", style="cyan")
    status_text.append(f"📋 Endpoints:\n", style="yellow")
    status_text.append(f"   • GET /prompts - List captured prompts\n", style="white")
    status_text.append(f"   • GET /prompts/count - Get prompt count\n", style="white")
    status_text.append(f"   • GET /prompts/stats - Get statistics\n", style="white")
    status_text.append(f"   • GET /health - Health check\n", style="white")
    status_text.append(f"\n📁 Data sources:\n", style="yellow")
    status_text.append(f"   • MongoDB (if connected)\n", style="green")
    status_text.append(f"   • JSONL files in ./logs/ (fallback)\n", style="white")
    status_text.append(f"\n💡 Example usage:\n", style="yellow")
    status_text.append(f"   curl http://{args.host}:{args.port}/prompts\n", style="dim")
    status_text.append(f"   curl http://{args.host}:{args.port}/prompts?limit=10\n", style="dim")
    status_text.append("\nPress Ctrl+C to stop", style="red")
    
    panel = Panel(status_text, title="API Server", border_style="green")
    console.print(panel)
    
    try:
        # Start the server (blocking)
        start_api_server(host=args.host, port=args.port)
    except KeyboardInterrupt:
        console.print("\n[yellow]API server stopped[/yellow]")
    except Exception as e:
        console.print(f"[red]Error starting server: {e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    main()