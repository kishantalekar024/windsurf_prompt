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
import re
import getpass
from datetime import datetime
from typing import Optional, Callable

from prompt_parser import PromptParser
from config import InterceptedPrompt
from rich.console import Console

console = Console()


class LocalSniffer:
    """Sniffs HTTP traffic on loopback to capture Windsurf's local API calls."""

    # The endpoints we're looking for - using regex for flexibility
    TARGET_ENDPOINT_PATTERN = re.compile(rb"SendUserCascadeMessage")
    TARGET_SERVICE_PATTERN = re.compile(rb"LanguageServerService")
    TARGET_HOST_PATTERN = re.compile(rb"[a-z]\.localhost")

    def __init__(
        self,
        on_prompt: Optional[Callable[[InterceptedPrompt], None]] = None,
        db=None,
        debug: bool = False,
    ):
        self.parser = PromptParser()
        self.on_prompt = on_prompt
        self.db = db  # MongoDB instance
        self.debug = debug  # Enable debug logging
        self._proc: Optional[subprocess.Popen] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        # Buffer to accumulate payload data across multiple packets
        # keyed by (src_port, dst_port, seq_start) tuple to handle connection reuse
        self._stream_buffers: dict = {}
        # Track known language server ports — once identified, capture ALL traffic to them
        self._known_ls_ports: set = set()
        # Track sequence numbers for better stream identification
        self._stream_sequences: dict = {}
        # Debug counters
        self._packet_count = 0
        self._processed_payload_count = 0
        self._prompt_count = 0
        self._extraction_attempts = 0

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
                self._packet_count += 1

                # Parse the packet to extract TCP payload
                self._parse_packet(pkt_data, link_type, endian)
                
                # Debug output every 100 packets
                if self.debug and packet_count % 100 == 0:
                    console.print(
                        f"[dim]Debug: Processed {packet_count} packets, "
                        f"{self._processed_payload_count} payloads, "
                        f"{self._extraction_attempts} extraction attempts, "
                        f"{self._prompt_count} prompts, "
                        f"{len(self._stream_buffers)} active buffers[/dim]"
                    )

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
        self._processed_payload_count += 1
        
        # Check if this packet has explicit target markers
        has_url_target = bool(
            self.TARGET_ENDPOINT_PATTERN.search(payload) or
            self.TARGET_SERVICE_PATTERN.search(payload) or
            self.TARGET_HOST_PATTERN.search(payload)
        )

        # If we see the URL target, remember this destination port as a language server
        if has_url_target:
            self._known_ls_ports.add(dst_port)
            if self.debug:
                console.print(f"[dim]Debug: Found LS port {dst_port}[/dim]")

        # Decide whether to buffer this packet:
        # 1. Has explicit target markers (URL or body)
        # 2. Destination is a known language server port (learned from first request)
        # 3. Already tracking this stream
        # Trigger buffering if we see ANY strong Windsurf marker
        has_body_target = (
            b'"cascadeId"' in payload or 
            b'"items"' in payload or
            b"LanguageServerService" in payload
        )
        is_known_port = dst_port in self._known_ls_ports

        stream_key = (src_port, dst_port)

        should_buffer = has_url_target or has_body_target or is_known_port
        
        if self.debug and (has_url_target or has_body_target):
            console.print(f"[dim]Debug: Buffering packet {src_port}→{dst_port}, "
                         f"url_target={has_url_target}, body_target={has_body_target}[/dim]")

        if should_buffer:
            if stream_key in self._stream_buffers:
                self._stream_buffers[stream_key] += payload
            else:
                self._stream_buffers[stream_key] = payload
        elif stream_key in self._stream_buffers:
            # Continue buffering a stream we're already tracking
            self._stream_buffers[stream_key] += payload

        # Safety limit: don't buffer more than 5MB - but keep some data for debugging
        if stream_key in self._stream_buffers:
            if len(self._stream_buffers[stream_key]) > 5 * 1024 * 1024:
                # Log this event for debugging
                console.print(f"[yellow]⚠️ Buffer overflow for stream {src_port}→{dst_port}, resetting[/yellow]")
                # Keep only the last 256KB in case the JSON spans the boundary
                self._stream_buffers[stream_key] = self._stream_buffers[stream_key][-262144:]
                return

        # Try to extract and process complete JSON from buffered data
        if stream_key in self._stream_buffers:
            buf = self._stream_buffers[stream_key]
            
            # Debug: Log buffer contents for failed extractions
            if self.debug and len(buf) > 100:  # Only log substantial buffers
                preview = buf[:200].decode('utf-8', errors='replace').replace('\n', '\\n').replace('\r', '\\r')
                console.print(f"[dim]Debug: Attempting extraction from buffer {src_port}→{dst_port}, size={len(buf)}, preview: {preview[:100]}...[/dim]")
            
            self._extraction_attempts += 1
            result, consumed_bytes = self._try_extract_request(buf)
            if result is not None and consumed_bytes > 0:
                # Successfully extracted — remove only consumed portion from buffer
                remaining = buf[consumed_bytes:]
                if remaining:
                    self._stream_buffers[stream_key] = remaining
                else:
                    del self._stream_buffers[stream_key]
            elif self.debug and len(buf) > 500:
                # Debug: Log extraction failures for large buffers
                console.print(f"[yellow]Debug: ⚠️ Failed to extract from large buffer {src_port}→{dst_port}, size={len(buf)}[/yellow]")

    def _try_extract_request(self, raw_data: bytes) -> tuple[Optional[bool], int]:
        """Try to extract a complete HTTP request with JSON body from raw data.
        
        Returns:
            tuple: (success, consumed_bytes) - consumed_bytes indicates how many bytes
                  from the start of raw_data were processed and can be removed from buffer
        """
        try:
            text = raw_data.decode("utf-8", errors="replace")

            # Strategy 1: Standard HTTP/1.1 with headers
            # POST /...SendUserCascadeMessage HTTP/1.1\r\n...\r\n\r\n{json}
            header_end = text.find("\r\n\r\n")
            if header_end != -1:
                body_start = header_end + 4
                body = text[body_start:]
                if body.strip():
                    json_str, json_end_offset = self._extract_json_with_position(body)
                    if json_str:
                        try:
                            data = json.loads(json_str)
                            if "cascadeId" in data and "items" in data:
                                # Extract headers
                                header_text = text[:header_end]
                                headers = {}
                                for line in header_text.split("\r\n")[1:]:
                                    if ": " in line:
                                        k, v = line.split(": ", 1)
                                        headers[k.lower()] = v

                                url = self._extract_windsurf_url(header_text) or (
                                    "http://localhost/"
                                    "exa.language_server_pb.LanguageServerService/"
                                    "SendUserCascadeMessage"
                                )

                                prompt = self.parser.extract_prompt_from_request(
                                    url, "POST", json_str, headers
                                )

                                if prompt and prompt.prompt:
                                    self._prompt_count += 1
                                    if self.debug:
                                        console.print(f"[dim]Debug: ✅ Extracted prompt #{self._prompt_count} from HTTP/1.1 request[/dim]")
                                    self._display_prompt(prompt)
                                    self._log_to_file(prompt)
                                    if self.on_prompt:
                                        self.on_prompt(prompt)
                                
                                # Return bytes consumed: headers + body up to end of JSON
                                consumed = body_start + json_end_offset
                                return True, consumed
                        except json.JSONDecodeError:
                            # Invalid JSON, continue to strategy 2
                            pass

            # Strategy 2: HTTP/2 binary framing or Connect framing.
            # Headers are HPACK-compressed or sent separately.
            # The body is JSON, but might be prefixed with 5 bytes (gRPC/Connect framing):
            # [1 byte flag] [4 bytes length] [JSON...]
            
            # Simple heuristic: scan for '{' and try to decode from there
            if "{" in text:
                if self.debug:
                    console.print(f"[dim]Debug: Found {{ in text, attempting JSON extraction...[/dim]")
                    
                json_str, json_end_offset = self._extract_json_with_position(text)
                if json_str:
                    if self.debug:
                        console.print(f"[dim]Debug: Extracted JSON of length {len(json_str)}, checking for Windsurf markers...[/dim]")
                        
                    try:
                        data = json.loads(json_str)
                        # Ensure it's a valid Windsurf message - more comprehensive check
                        has_marker = (
                            ("cascadeId" in data and "items" in data) or
                            ("cascadeId" in data and "metadata" in data) or  # Single message format
                            ("messages" in data and "model" in data) or
                            ("cascadeId" in data)  # Most lenient - any message with cascadeId
                        )
                        
                        if self.debug:
                            console.print(f"[dim]Debug: JSON parsed successfully, has_marker={has_marker}, keys={list(data.keys())[:5]}[/dim]")
                        
                        if has_marker:
                            # Try to extract the actual URL from the data or use a default
                            url = self._extract_windsurf_url_from_data(text) or (
                                "http://localhost/"
                                "exa.language_server_pb.LanguageServerService/"
                                "SendUserCascadeMessage"
                            )

                            prompt = self.parser.extract_prompt_from_request(
                                url, "POST", json_str, {}
                            )

                            if prompt and prompt.prompt:
                                self._prompt_count += 1
                                if self.debug:
                                    console.print(f"[dim]Debug: ✅ Extracted prompt #{self._prompt_count} from HTTP/2 request[/dim]")
                                self._display_prompt(prompt)
                                self._log_to_file(prompt)
                                if self.on_prompt:
                                    self.on_prompt(prompt)
                                return True, json_end_offset
                            elif self.debug:
                                console.print(f"[yellow]Debug: ⚠️ JSON parsed but no prompt extracted[/yellow]")
                    except json.JSONDecodeError as e:
                        if self.debug:
                            console.print(f"[yellow]Debug: ⚠️ JSON decode error: {e}[/yellow]")
                    except Exception as e:
                        if self.debug:
                            console.print(f"[yellow]Debug: ⚠️ Exception during parsing: {e}[/yellow]")
                elif self.debug:
                    console.print(f"[yellow]Debug: ⚠️ Found {{ but could not extract valid JSON[/yellow]")

            return None, 0

        except json.JSONDecodeError:
            return None, 0  # Incomplete JSON, keep buffering
        except Exception as e:
            console.print(f"[dim]Sniffer parse warning: {e}[/dim]")
            return None, 0

    def _extract_json(self, text: str) -> Optional[str]:
        """Extract a JSON object from mixed text."""
        result, _ = self._extract_json_with_position(text)
        return result
        
    def _extract_json_with_position(self, text: str) -> tuple[Optional[str], int]:
        """Extract a JSON object from mixed text, returning the JSON and end position.
        
        Returns:
            tuple: (json_string, end_position) - end_position is relative to start of text
        """
        # Find start of JSON object - try multiple strategies
        start_indices = []
        
        # Strategy 1: Find all standalone '{'
        for i, ch in enumerate(text):
            if ch == "{":
                start_indices.append(i)
        
        # Strategy 2: Look for Connect protocol framing
        # Connect uses: [compression_flag(1)][message_length(4)][message]
        for i in range(0, len(text) - 6):
            # Check for uncompressed message (flag = 0)
            if ord(text[i]) == 0:  # Compression flag = 0
                try:
                    # Next 4 bytes are big-endian message length
                    length_bytes = text[i+1:i+5].encode('latin1')[:4]
                    if len(length_bytes) == 4:
                        message_start = i + 5
                        if message_start < len(text) and text[message_start] == "{":
                            start_indices.insert(0, message_start)  # Prioritize this
                except:
                    pass
                    
        # Strategy 3: Look for gRPC-style length prefixes
        # Common pattern: \x00\x00\x00\x[length]{json}
        for i in range(0, len(text) - 5):
            if i + 5 < len(text) and text[i + 5] == "{":
                # Check if this looks like a length prefix
                if text[i:i+3] == '\x00\x00\x00':
                    start_indices.insert(0, i + 5)  # Prioritize this
                    
        # Strategy 4: Look for HTTP Content-Length
        content_length_pos = text.find("Content-Length:")
        if content_length_pos != -1:
            # Find next { after Content-Length
            search_start = content_length_pos + 15
            brace_pos = text.find("{", search_start)
            if brace_pos != -1:
                start_indices.insert(0, brace_pos)  # Prioritize this
                
        # Strategy 5: Look for cascadeId directly (our most reliable marker)
        cascade_pos = text.find('"cascadeId"')
        if cascade_pos != -1:
            # Search backwards for the opening brace
            for j in range(cascade_pos, -1, -1):
                if text[j] == '{':
                    start_indices.insert(0, j)  # Highest priority
                    break
                    
        if not start_indices:
            return None, 0
            
        # Try from each potential start brace (prioritized order)
        for start in start_indices:
            result = self._extract_json_from_position(text, start)
            if result[0]:  # If successful
                return result
                
        return None, 0
    
    def _extract_json_from_position(self, text: str, start: int) -> tuple[Optional[str], int]:
        """Extract JSON starting from a specific position."""
        brace_depth = 0
        in_string = False
        escaped = False
        
        # Scan forward from this start with proper string handling
        for i in range(start, len(text)):
            ch = text[i]
            
            if not in_string:
                if ch == '"':
                    in_string = True
                elif ch == "{":
                    brace_depth += 1
                elif ch == "}":
                    brace_depth -= 1
                    if brace_depth == 0:
                        # Found a complete balanced block
                        candidate = text[start : i + 1]
                        try:
                            # Additional validation: check for minimum viable JSON size
                            if len(candidate) < 10:
                                return None, 0  # Too small to be real JSON
                                
                            # Quick validation for Windsurf-specific content
                            if 'cascadeId' not in candidate:
                                return None, 0  # Not a Windsurf message
                                
                            json.loads(candidate)  # Validate JSON
                            return candidate, i + 1
                        except json.JSONDecodeError:
                            # Not valid JSON
                            return None, 0
                        # If we get here, exit the main loop
                        return None, 0
            else:
                # Inside string - handle escapes
                if escaped:
                    escaped = False
                elif ch == '\\':
                    escaped = True
                elif ch == '"':
                    in_string = False
                    
        return None, 0

    def _extract_windsurf_url(self, headers: str) -> Optional[str]:
        """Extract the actual Windsurf URL from HTTP headers."""
        # Look for Host header and reconstruct URL
        for line in headers.split('\n'):
            if line.lower().startswith('host:'):
                host = line.split(':', 1)[1].strip()
                if '.localhost' in host:
                    return f"http://{host}/exa.language_server_pb.LanguageServerService/SendUserCascadeMessage"
        return None
        
    def _extract_windsurf_url_from_data(self, text: str) -> Optional[str]:
        """Try to extract Windsurf URL from raw data."""
        # Look for localhost patterns in the text
        patterns = [
            r'http://([a-z])\.localhost:(\d+)(/[^\s]*)?',
            r'([a-z])\.localhost:(\d+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                if len(match.groups()) >= 2:
                    subdomain = match.group(1)
                    port = match.group(2)
                    return f"http://{subdomain}.localhost:{port}/exa.language_server_pb.LanguageServerService/SendUserCascadeMessage"
        
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
        """Save intercepted prompt to log file and MongoDB."""
        try:
            # Save to JSONL file
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
            
            # Save to MongoDB if connected
            if self.db and self.db.is_connected():
                meta = prompt.metadata or {}
                self.db.save_prompt(
                    prompt_text=prompt.prompt,
                    user=os.environ.get("SUDO_USER") or getpass.getuser(),
                    source=prompt.source,
                    model=meta.get("model", ""),
                    cascade_id=meta.get("cascade_id", ""),
                    planner_mode=meta.get("planner_mode", ""),
                    ide_name=meta.get("ide_name", ""),
                    ide_version=meta.get("ide_version", ""),
                    extension_version=meta.get("extension_version", ""),
                    brain_enabled=meta.get("brain_enabled", False),
                    prompt_length=len(prompt.prompt),
                    metadata=meta,
                    timestamp=prompt.timestamp,
                )
        except Exception as e:
            console.print(f"[red]Error writing log: {e}[/red]")


def check_sudo() -> bool:
    """Check if we're running with root/sudo privileges."""
    return os.geteuid() == 0
