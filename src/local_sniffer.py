"""
Loopback traffic sniffer for capturing Windsurf's local language server communication.

Windsurf sends prompts via plain HTTP to d.localhost:<dynamic_port> which bypasses
any HTTP proxy. This module uses tcpdump on the loopback interface (lo0) to capture
that traffic directly, reading raw pcap output and reassembling TCP payload.

Requires: sudo (for packet capture on loopback)
"""

import subprocess
import struct
import threading
import json
import os
from datetime import datetime
from typing import Optional, Callable

from prompt_parser import PromptParser
from config import InterceptedPrompt
from rich.console import Console

console = Console()


class LocalSniffer:
    """Sniffs HTTP traffic on loopback to capture Windsurf's local API calls."""

    # The endpoint we're looking for
    TARGET_ENDPOINT = b"SendUserCascadeMessage"
    TARGET_SERVICE = b"LanguageServerService"

    def __init__(self, on_prompt: Optional[Callable[[InterceptedPrompt], None]] = None):
        self.parser = PromptParser()
        self.on_prompt = on_prompt
        self._proc: Optional[subprocess.Popen] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        # Buffer to accumulate payload data across multiple packets
        # keyed by (src_port, dst_port) tuple
        self._stream_buffers: dict = {}

    def start(self):
        """Start sniffing loopback traffic in a background thread."""
        self._running = True
        self._thread = threading.Thread(target=self._run_tcpdump, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop the sniffer."""
        self._running = False
        if self._proc:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=3)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass

    def _run_tcpdump(self):
        """Run tcpdump with raw pcap output and parse binary packet data."""
        try:
            # Use tcpdump -w - to get raw pcap on stdout (binary)
            # -U: packet-buffered output (flush after each packet)
            # Filter: TCP traffic on loopback
            cmd = [
                "tcpdump",
                "-i", "lo0",
                "-w", "-",      # raw pcap to stdout
                "-U",           # packet-buffered (flush each packet immediately)
                "-s", "0",      # no truncation
                "tcp",          # all TCP on loopback
            ]

            self._proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0,
            )

            # Check if tcpdump started successfully
            import time
            time.sleep(0.5)
            if self._proc.poll() is not None:
                stderr = self._proc.stderr.read().decode("utf-8", errors="replace")
                console.print(f"[red]tcpdump failed to start: {stderr.strip()}[/red]")
                return

            console.print("[green]✓ Loopback sniffer started (tcpdump on lo0)[/green]")

            stdout = self._proc.stdout

            # Read pcap global header (24 bytes)
            global_header = self._read_exact(stdout, 24)
            if not global_header or len(global_header) < 24:
                console.print("[red]Failed to read pcap header[/red]")
                return

            magic = struct.unpack("<I", global_header[0:4])[0]
            if magic == 0xa1b2c3d4:
                endian = "<"
            elif magic == 0xd4c3b2a1:
                endian = ">"
            else:
                console.print(f"[red]Unknown pcap magic: {hex(magic)}[/red]")
                return

            # link type is at offset 20
            link_type = struct.unpack(f"{endian}I", global_header[20:24])[0]
            # NULL/Loopback = 0, Ethernet = 1
            # macOS lo0 uses NULL (link_type = 0)

            packet_count = 0

            while self._running:
                # Read pcap packet header (16 bytes)
                pkt_header = self._read_exact(stdout, 16)
                if not pkt_header or len(pkt_header) < 16:
                    break

                ts_sec, ts_usec, incl_len, orig_len = struct.unpack(
                    f"{endian}IIII", pkt_header
                )

                # Read packet data
                pkt_data = self._read_exact(stdout, incl_len)
                if not pkt_data or len(pkt_data) < incl_len:
                    break

                packet_count += 1

                # Parse the packet to extract TCP payload
                self._parse_packet(pkt_data, link_type, endian)

        except FileNotFoundError:
            console.print("[red]tcpdump not found. Is it in your PATH?[/red]")
        except PermissionError:
            console.print("[red]Permission denied. Run with sudo for loopback capture.[/red]")
        except Exception as e:
            if self._running:
                console.print(f"[red]Sniffer error: {e}[/red]")

    def _read_exact(self, stream, n: int) -> Optional[bytes]:
        """Read exactly n bytes from stream."""
        data = b""
        while len(data) < n:
            chunk = stream.read(n - len(data))
            if not chunk:
                return None
            data += chunk
        return data

    def _parse_packet(self, pkt_data: bytes, link_type: int, endian: str):
        """Parse a single captured packet and extract TCP payload."""
        try:
            # Skip link-layer header
            if link_type == 0:
                # NULL/Loopback: 4-byte AF family
                if len(pkt_data) < 4:
                    return
                af_family = struct.unpack(f"{endian}I", pkt_data[0:4])[0]
                # AF_INET = 2, AF_INET6 = 30 (macOS)
                ip_data = pkt_data[4:]
            elif link_type == 1:
                # Ethernet: 14-byte header
                if len(pkt_data) < 14:
                    return
                ip_data = pkt_data[14:]
            else:
                return

            if len(ip_data) < 20:
                return

            # Parse IP header
            version_ihl = ip_data[0]
            version = (version_ihl >> 4) & 0xF
            ihl = version_ihl & 0xF

            if version == 4:
                # IPv4
                ip_header_len = ihl * 4
                if len(ip_data) < ip_header_len:
                    return
                protocol = ip_data[9]
                if protocol != 6:  # TCP
                    return
                tcp_data = ip_data[ip_header_len:]
            elif version == 6:
                # IPv6: 40-byte fixed header
                if len(ip_data) < 40:
                    return
                next_header = ip_data[6]
                if next_header != 6:  # TCP
                    return
                tcp_data = ip_data[40:]
            else:
                return

            if len(tcp_data) < 20:
                return

            # Parse TCP header
            src_port = struct.unpack("!H", tcp_data[0:2])[0]
            dst_port = struct.unpack("!H", tcp_data[2:4])[0]
            data_offset = (tcp_data[12] >> 4) & 0xF
            tcp_header_len = data_offset * 4
            tcp_flags = tcp_data[13]

            # Extract TCP payload
            if len(tcp_data) <= tcp_header_len:
                return  # No payload

            payload = tcp_data[tcp_header_len:]
            if not payload:
                return

            # Check if this payload contains our target
            self._process_payload(payload, src_port, dst_port)

        except Exception:
            pass  # Skip malformed packets silently

    def _process_payload(self, payload: bytes, src_port: int, dst_port: int):
        """Process TCP payload, buffering and looking for Windsurf requests."""
        # Quick check: does this payload contain our target endpoint?
        has_target = (
            self.TARGET_ENDPOINT in payload or
            self.TARGET_SERVICE in payload
        )

        stream_key = (src_port, dst_port)

        if has_target:
            # This packet starts or contains our target request
            # Store/append to buffer
            if stream_key in self._stream_buffers:
                self._stream_buffers[stream_key] += payload
            else:
                self._stream_buffers[stream_key] = payload
        elif stream_key in self._stream_buffers:
            # Continue buffering a stream we're already tracking
            self._stream_buffers[stream_key] += payload

            # Safety limit: don't buffer more than 1MB
            if len(self._stream_buffers[stream_key]) > 1024 * 1024:
                del self._stream_buffers[stream_key]
                return

        # Try to extract and process complete JSON from buffered data
        if stream_key in self._stream_buffers:
            buf = self._stream_buffers[stream_key]
            result = self._try_extract_request(buf)
            if result is not None:
                # Successfully extracted — remove from buffer
                del self._stream_buffers[stream_key]

    def _try_extract_request(self, raw_data: bytes) -> Optional[bool]:
        """Try to extract a complete HTTP request with JSON body from raw data."""
        try:
            text = raw_data.decode("utf-8", errors="replace")

            # Look for HTTP request line
            # POST /exa.language_server_pb.LanguageServerService/SendUserCascadeMessage HTTP/1.1
            if "SendUserCascadeMessage" not in text:
                return None

            # Find the JSON body (after the HTTP headers)
            # Headers end with \r\n\r\n
            header_end = text.find("\r\n\r\n")
            if header_end == -1:
                return None  # Headers not complete yet

            body_start = header_end + 4
            body = text[body_start:]

            if not body.strip():
                return None  # Body not received yet

            # Try to extract and parse JSON from the body
            json_str = self._extract_json(body)
            if not json_str:
                return None

            data = json.loads(json_str)

            # Verify this is a Windsurf cascade message
            if "cascadeId" not in data or "items" not in data:
                return None

            # Extract headers from the raw HTTP
            header_text = text[:header_end]
            headers = {}
            for line in header_text.split("\r\n")[1:]:  # Skip request line
                if ": " in line:
                    k, v = line.split(": ", 1)
                    headers[k.lower()] = v

            # Use the prompt parser
            url = (
                "http://d.localhost/"
                "exa.language_server_pb.LanguageServerService/"
                "SendUserCascadeMessage"
            )

            prompt = self.parser.extract_prompt_from_request(
                url, "POST", json_str, headers
            )

            if prompt and prompt.prompt:
                self._display_prompt(prompt)
                self._log_to_file(prompt)
                if self.on_prompt:
                    self.on_prompt(prompt)

            return True

        except json.JSONDecodeError:
            return None  # Incomplete JSON, keep buffering
        except Exception as e:
            console.print(f"[dim]Sniffer parse warning: {e}[/dim]")
            return None

    def _extract_json(self, text: str) -> Optional[str]:
        """Extract a JSON object from mixed text."""
        brace_depth = 0
        start = -1

        for i, ch in enumerate(text):
            if ch == "{":
                if start == -1:
                    start = i
                brace_depth += 1
            elif ch == "}":
                brace_depth -= 1
                if brace_depth == 0 and start != -1:
                    candidate = text[start : i + 1]
                    try:
                        json.loads(candidate)
                        return candidate
                    except json.JSONDecodeError:
                        start = -1
                        brace_depth = 0
                        continue

        return None

    def _display_prompt(self, prompt: InterceptedPrompt):
        """Display the intercepted prompt in a nice format."""
        console.print()
        console.print("=" * 80)
        console.print(
            f"[bold green]🎯 WINDSURF PROMPT CAPTURED[/bold green]  "
            f"[{datetime.now().strftime('%H:%M:%S')}]  "
            f"[dim](local loopback)[/dim]"
        )
        console.print("=" * 80)

        model = prompt.metadata.get("model", "")
        if model:
            console.print(f"  [magenta]Model:[/magenta]          {model}")

        cascade_id = prompt.metadata.get("cascade_id", "")
        if cascade_id:
            console.print(f"  [magenta]Cascade ID:[/magenta]     {cascade_id}")

        planner_mode = prompt.metadata.get("planner_mode", "")
        if planner_mode:
            console.print(f"  [magenta]Planner Mode:[/magenta]   {planner_mode}")

        ide_name = prompt.metadata.get("ide_name", "")
        ide_ver = prompt.metadata.get("ide_version", "")
        if ide_name:
            console.print(f"  [magenta]IDE:[/magenta]             {ide_name} {ide_ver}")

        ext_ver = prompt.metadata.get("extension_version", "")
        if ext_ver:
            console.print(f"  [magenta]Extension:[/magenta]       v{ext_ver}")

        brain = prompt.metadata.get("brain_enabled", False)
        console.print(
            f"  [magenta]Brain:[/magenta]           {'✅ Enabled' if brain else '❌ Disabled'}"
        )

        console.print()
        console.print(f"  [bold yellow]📝 PROMPT:[/bold yellow]")
        text = prompt.prompt
        if len(text) > 3000:
            text = text[:3000] + f"\n  … (truncated, {len(prompt.prompt)} chars total)"
        for line in text.split("\n"):
            console.print(f"  [white]{line}[/white]")

        console.print("=" * 80)

    def _log_to_file(self, prompt: InterceptedPrompt):
        """Save intercepted prompt to log file."""
        try:
            os.makedirs("logs", exist_ok=True)
            log_file = os.path.join(
                "logs", f"prompts_{datetime.now().strftime('%Y-%m-%d')}.jsonl"
            )
            entry = {
                "id": prompt.id,
                "timestamp": prompt.timestamp.isoformat(),
                "source": prompt.source,
                "url": prompt.url,
                "method": prompt.method,
                "prompt": prompt.prompt,
                "messages": prompt.messages,
                "metadata": prompt.metadata,
                "capture_method": "loopback_sniffer",
            }
            with open(log_file, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            console.print(f"[red]Error writing log: {e}[/red]")


def check_sudo() -> bool:
    """Check if we're running with root/sudo privileges."""
    return os.geteuid() == 0
