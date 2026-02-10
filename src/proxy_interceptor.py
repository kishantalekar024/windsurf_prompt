"""
Lightweight HTTP/HTTPS proxy interceptor for capturing AI prompts.
No mitmproxy dependency — uses Python's built-in modules + SSL for MITM.
"""

import http.server
import socketserver
import ssl
import socket
import threading
import json
import os
import subprocess
import select
import gzip
from datetime import datetime
from typing import Dict, Optional, Tuple
from urllib.parse import urlparse

from prompt_parser import PromptParser
from config import Config, InterceptedPrompt
from rich.console import Console

console = Console()


# ─── Certificate generation ────────────────────────────────────────────────────

CA_KEY_FILE = os.path.expanduser("~/.windsurf-proxy/ca-key.pem")
CA_CERT_FILE = os.path.expanduser("~/.windsurf-proxy/ca-cert.pem")
CERTS_DIR = os.path.expanduser("~/.windsurf-proxy/certs")


def _ensure_ca():
    """Generate a self-signed CA key + certificate if they don't already exist."""
    os.makedirs(os.path.dirname(CA_KEY_FILE), exist_ok=True)
    os.makedirs(CERTS_DIR, exist_ok=True)

    if os.path.exists(CA_KEY_FILE) and os.path.exists(CA_CERT_FILE):
        return

    console.print("[yellow]Generating proxy CA certificate…[/yellow]")
    # Generate CA key
    subprocess.run(
        ["openssl", "genrsa", "-out", CA_KEY_FILE, "2048"],
        check=True,
        capture_output=True,
    )
    # Generate self-signed CA cert
    subprocess.run(
        [
            "openssl", "req", "-new", "-x509", "-key", CA_KEY_FILE,
            "-out", CA_CERT_FILE, "-days", "3650",
            "-subj", "/CN=WindsurfPromptProxy CA/O=WindsurfProxy/C=US",
        ],
        check=True,
        capture_output=True,
    )
    console.print(f"[green]✓ CA certificate created at {CA_CERT_FILE}[/green]")
    console.print(
        f"[yellow]To trust it on macOS run:[/yellow]\n"
        f"  sudo security add-trusted-cert -d -r trustRoot "
        f"-k /Library/Keychains/System.keychain {CA_CERT_FILE}"
    )


def _get_cert_for_host(hostname: str) -> Tuple[str, str]:
    """Return (cert_path, key_path) for *hostname*, generating on-the-fly if needed."""
    safe = hostname.replace("*", "_wildcard_")
    cert_path = os.path.join(CERTS_DIR, f"{safe}.pem")
    key_path = os.path.join(CERTS_DIR, f"{safe}-key.pem")

    if os.path.exists(cert_path) and os.path.exists(key_path):
        return cert_path, key_path

    # Generate a key + CSR + cert signed by the CA
    subprocess.run(
        ["openssl", "genrsa", "-out", key_path, "2048"],
        check=True, capture_output=True,
    )

    # Create config with SAN
    ext_file = os.path.join(CERTS_DIR, f"{safe}.ext")
    with open(ext_file, "w") as f:
        f.write(
            f"authorityKeyIdentifier=keyid,issuer\n"
            f"basicConstraints=CA:FALSE\n"
            f"subjectAltName=DNS:{hostname}\n"
        )

    # CSR
    subprocess.run(
        [
            "openssl", "req", "-new", "-key", key_path,
            "-out", cert_path + ".csr",
            "-subj", f"/CN={hostname}",
        ],
        check=True, capture_output=True,
    )

    # Sign with CA
    subprocess.run(
        [
            "openssl", "x509", "-req",
            "-in", cert_path + ".csr",
            "-CA", CA_CERT_FILE, "-CAkey", CA_KEY_FILE,
            "-CAcreateserial",
            "-out", cert_path,
            "-days", "825",
            "-extfile", ext_file,
        ],
        check=True, capture_output=True,
    )

    # Cleanup temp files
    for tmp in (cert_path + ".csr", ext_file):
        if os.path.exists(tmp):
            os.remove(tmp)

    return cert_path, key_path


# ─── Proxy handler ──────────────────────────────────────────────────────────────

class ProxyRequestHandler(http.server.BaseHTTPRequestHandler):
    """Handles both HTTP and HTTPS (via CONNECT) proxy requests."""

    parser_instance = PromptParser()
    lock = threading.Lock()

    # Suppress default logging — we use Rich instead
    def log_message(self, format, *args):
        pass

    def do_CONNECT(self):
        """Handle HTTPS CONNECT tunnelling with optional MITM."""
        host, _, port = self.path.partition(":")
        port = int(port) if port else 443

        if self._is_interesting_host(host):
            self._mitm_connect(host, port)
        else:
            # Log notable connections even if we don't MITM them
            if self._is_log_only_host(host):
                with self.lock:
                    console.print(
                        f"[dim]🔗 [{datetime.now().strftime('%H:%M:%S')}] "
                        f"Tunnel (no MITM): {host}:{port}[/dim]"
                    )
            self._tunnel_connect(host, port)

    # Exact domains to MITM (these carry actual AI prompts/responses)
    MITM_DOMAINS = {
        "api.openai.com",
        "api.anthropic.com",
        "api.codeium.com",
        "copilot-proxy.githubusercontent.com",
        "api.github.com",
        "generativelanguage.googleapis.com",
        "api.groq.com",
        "api.mistral.ai",
        "api.cohere.com",
        "api.together.xyz",
        "api.windsurf.ai",
        "server.windsurf.ai",
    }

    # Domains to log (connection noticed) but NOT MITM — just tunnel through
    LOG_ONLY_DOMAINS = {
        "unleash.codeium.com",
        "telemetry.codeium.com",
        "app.codeium.com",
        "codeium.com",
    }

    def _is_interesting_host(self, host: str) -> bool:
        """Should we MITM this host (i.e. is it an AI API endpoint)?"""
        h = host.lower()
        return h in self.MITM_DOMAINS

    def _is_log_only_host(self, host: str) -> bool:
        """Should we log this connection but just tunnel it through?"""
        h = host.lower()
        return h in self.LOG_ONLY_DOMAINS

    # ── MITM path ───────────────────────────────────────────────────────────

    def _mitm_connect(self, host: str, port: int):
        """Intercept the TLS connection so we can read request/response bodies."""
        try:
            cert_path, key_path = _get_cert_for_host(host)

            # Tell the client the tunnel is established
            self.send_response(200, "Connection Established")
            self.end_headers()

            # Wrap the client socket in TLS (we act as the *server*)
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ctx.load_cert_chain(certfile=cert_path, keyfile=key_path)
            try:
                client_tls = ctx.wrap_socket(self.connection, server_side=True)
            except ssl.SSLError as e:
                # Don't spam the console — this happens when the client doesn't trust our CA
                if "certificate unknown" in str(e).lower() or "eof" in str(e).lower():
                    pass  # Expected when CA not trusted — silently skip
                else:
                    console.print(f"[dim]SSL handshake issue for {host}: {e}[/dim]")
                return

            # Now read the actual HTTP request from the unwrapped stream
            self._handle_mitm_request(client_tls, host, port)

        except Exception as e:
            console.print(f"[red]MITM error for {host}: {e}[/red]")

    def _handle_mitm_request(self, client_conn, host: str, port: int):
        """Read HTTP requests from the decrypted client connection and forward them."""
        try:
            # Read raw request from client
            raw = b""
            client_conn.settimeout(10)

            # Read headers first
            while b"\r\n\r\n" not in raw:
                chunk = client_conn.recv(65536)
                if not chunk:
                    return
                raw += chunk

            header_end = raw.index(b"\r\n\r\n") + 4
            header_bytes = raw[:header_end]
            body_so_far = raw[header_end:]

            # Parse method / path / headers
            header_text = header_bytes.decode("utf-8", errors="replace")
            lines = header_text.split("\r\n")
            request_line = lines[0]
            parts = request_line.split(" ", 2)
            if len(parts) < 2:
                return
            method = parts[0]
            path = parts[1]
            url = f"https://{host}{path}"

            headers: Dict[str, str] = {}
            for line in lines[1:]:
                if ": " in line:
                    k, v = line.split(": ", 1)
                    headers[k.lower()] = v

            # Read remaining body based on Content-Length
            content_length = int(headers.get("content-length", 0))
            while len(body_so_far) < content_length:
                chunk = client_conn.recv(65536)
                if not chunk:
                    break
                body_so_far += chunk

            body = body_so_far[:content_length].decode("utf-8", errors="replace")

            # ── Log the intercepted request ──
            self._log_request(url, method, body, headers)

            # ── Forward to the real server ──
            server_ctx = ssl.create_default_context()
            with socket.create_connection((host, port), timeout=30) as raw_sock:
                with server_ctx.wrap_socket(raw_sock, server_hostname=host) as server_conn:
                    server_conn.sendall(raw)

                    # Read response from server
                    response_raw = b""
                    server_conn.settimeout(30)
                    while True:
                        try:
                            chunk = server_conn.recv(65536)
                            if not chunk:
                                break
                            response_raw += chunk
                        except (socket.timeout, ssl.SSLError):
                            break

            # ── Log response ──
            self._log_response(url, response_raw, headers)

            # Send response back to client
            try:
                client_conn.sendall(response_raw)
            except Exception:
                pass

        except Exception as e:
            console.print(f"[red]MITM request handler error: {e}[/red]")
        finally:
            try:
                client_conn.close()
            except Exception:
                pass

    # ── Plain tunnel (non-interesting hosts) ─────────────────────────────────

    def _tunnel_connect(self, host: str, port: int):
        """Just pipe bytes through — no interception."""
        try:
            remote = socket.create_connection((host, port), timeout=10)
        except Exception as e:
            self.send_error(502, f"Cannot connect to {host}:{port}")
            return

        self.send_response(200, "Connection Established")
        self.end_headers()

        conns = [self.connection, remote]
        keep = True
        try:
            while keep:
                rlist, _, xlist = select.select(conns, [], conns, 30)
                if xlist:
                    break
                for r in rlist:
                    try:
                        data = r.recv(65536)
                    except (ConnectionResetError, BrokenPipeError, OSError):
                        keep = False
                        break
                    if not data:
                        keep = False
                        break
                    other = remote if r is self.connection else self.connection
                    try:
                        other.sendall(data)
                    except (ConnectionResetError, BrokenPipeError, OSError):
                        keep = False
                        break
        except Exception:
            pass
        finally:
            try:
                remote.close()
            except Exception:
                pass

    # ── Plain HTTP requests (GET / POST / …) ─────────────────────────────────

    def do_GET(self):
        self._proxy_http_request()

    def do_POST(self):
        self._proxy_http_request()

    def do_PUT(self):
        self._proxy_http_request()

    def do_DELETE(self):
        self._proxy_http_request()

    def do_PATCH(self):
        self._proxy_http_request()

    def do_OPTIONS(self):
        self._proxy_http_request()

    def do_HEAD(self):
        self._proxy_http_request()

    def _proxy_http_request(self):
        """Forward a plain HTTP request, intercept and log if interesting."""
        url = self.path
        method = self.command
        headers = dict(self.headers)

        content_length = int(headers.get("content-length", 0))
        body_bytes = self.rfile.read(content_length) if content_length else b""
        body = body_bytes.decode("utf-8", errors="replace")

        # Log if interesting
        self._log_request(url, method, body, headers)

        # Parse the target URL
        parsed = urlparse(url)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or 80
        path = parsed.path or "/"
        if parsed.query:
            path += f"?{parsed.query}"

        # Forward via raw socket (urllib doesn't handle d.localhost well)
        try:
            with socket.create_connection((host, port), timeout=30) as sock:
                # Build raw HTTP request
                req_line = f"{method} {path} HTTP/1.1\r\n"
                req_headers = f"Host: {parsed.netloc}\r\n"
                for k, v in headers.items():
                    k_lower = k.lower()
                    if k_lower in ("host", "proxy-connection"):
                        continue
                    req_headers += f"{k}: {v}\r\n"
                req_headers += "\r\n"

                sock.sendall(req_line.encode() + req_headers.encode() + body_bytes)

                # Read response
                response_raw = b""
                sock.settimeout(30)
                while True:
                    try:
                        chunk = sock.recv(65536)
                        if not chunk:
                            break
                        response_raw += chunk
                        # Check if we've received the complete response
                        if b"\r\n\r\n" in response_raw:
                            resp_hdr_end = response_raw.index(b"\r\n\r\n") + 4
                            resp_hdr_text = response_raw[:resp_hdr_end].decode("utf-8", errors="replace")
                            # Check Content-Length
                            for line in resp_hdr_text.split("\r\n"):
                                if line.lower().startswith("content-length:"):
                                    expected_len = int(line.split(":", 1)[1].strip())
                                    resp_body_so_far = response_raw[resp_hdr_end:]
                                    if len(resp_body_so_far) >= expected_len:
                                        # Got full response
                                        response_raw = response_raw[:resp_hdr_end + expected_len]
                                        break
                    except socket.timeout:
                        break

            # Log response if AI traffic
            self._log_response(url, response_raw, headers)

            # Send response back to client
            self.wfile.write(response_raw)
            self.wfile.flush()

        except Exception as e:
            try:
                self.send_error(502, str(e))
            except Exception:
                pass

    # ── Logging helpers ──────────────────────────────────────────────────────

    def _log_request(self, url: str, method: str, body: str, headers: dict):
        """Log request details if it looks like AI traffic."""
        if not self._is_ai_traffic(url, headers):
            return

        with self.lock:
            console.print()
            console.print("=" * 80)
            console.print(f"[bold green]🤖 AI TRAFFIC DETECTED[/bold green]  [{datetime.now().strftime('%H:%M:%S')}]")
            console.print("=" * 80)
            console.print(f"  [cyan]URL:[/cyan]            {url}")
            console.print(f"  [cyan]Method:[/cyan]         {method}")
            console.print(f"  [cyan]User-Agent:[/cyan]     {headers.get('user-agent', 'N/A')[:120]}")
            console.print(f"  [cyan]Content-Type:[/cyan]   {headers.get('content-type', 'N/A')}")
            console.print(f"  [cyan]Content-Len:[/cyan]    {headers.get('content-length', 'N/A')}")
            auth = headers.get("authorization", "")
            if auth:
                console.print(f"  [cyan]Authorization:[/cyan]  {auth[:25]}…" if len(auth) > 25 else f"  [cyan]Authorization:[/cyan]  {auth}")

            # Try to parse prompt from body
            if body:
                prompt = self.parser_instance.extract_prompt_from_request(url, method, body, headers)
                if prompt and prompt.prompt:
                    console.print()
                    console.print(f"  [bold yellow]📝 PROMPT:[/bold yellow]")
                    # Show model if detected
                    model = prompt.metadata.get("model", "")
                    if model:
                        console.print(f"  [magenta]Model:[/magenta] {model}")

                    # Show Windsurf-specific metadata
                    cascade_id = prompt.metadata.get("cascade_id", "")
                    if cascade_id:
                        console.print(f"  [magenta]Cascade ID:[/magenta] {cascade_id}")
                    planner_mode = prompt.metadata.get("planner_mode", "")
                    if planner_mode:
                        console.print(f"  [magenta]Planner Mode:[/magenta] {planner_mode}")
                    ide_ver = prompt.metadata.get("ide_version", "")
                    if ide_ver:
                        console.print(f"  [magenta]IDE Version:[/magenta] {prompt.metadata.get('ide_name', '')} {ide_ver}")

                    # Truncate very long prompts for readability
                    text = prompt.prompt
                    if len(text) > 2000:
                        text = text[:2000] + f"\n  … (truncated, {len(prompt.prompt)} chars total)"
                    console.print()
                    for line in text.split("\n"):
                        console.print(f"  [white]{line}[/white]")

                    if prompt.messages and len(prompt.messages) > 1:
                        console.print(f"\n  [dim]({len(prompt.messages)} messages in conversation)[/dim]")

                    # Log to file
                    self._log_to_file(prompt)

            console.print("=" * 80)

    def _log_response(self, url: str, response_raw: bytes, request_headers: dict):
        """Log response details if it looks like AI traffic."""
        if not self._is_ai_traffic(url, request_headers):
            return

        try:
            # Split headers from body
            if b"\r\n\r\n" in response_raw:
                resp_header_bytes, resp_body_bytes = response_raw.split(b"\r\n\r\n", 1)
                resp_header_text = resp_header_bytes.decode("utf-8", errors="replace")

                # Parse status line
                status_line = resp_header_text.split("\r\n")[0] if resp_header_text else "Unknown"

                # Parse response headers
                resp_headers = {}
                for line in resp_header_text.split("\r\n")[1:]:
                    if ": " in line:
                        k, v = line.split(": ", 1)
                        resp_headers[k.lower()] = v

                # Decompress if gzipped
                if resp_headers.get("content-encoding", "").lower() == "gzip":
                    try:
                        resp_body_bytes = gzip.decompress(resp_body_bytes)
                    except Exception:
                        pass

                resp_body = resp_body_bytes.decode("utf-8", errors="replace")

                with self.lock:
                    console.print()
                    console.print(f"[bold blue]📨 AI RESPONSE[/bold blue]  [{datetime.now().strftime('%H:%M:%S')}]")
                    console.print("-" * 60)
                    console.print(f"  [cyan]Status:[/cyan]         {status_line}")
                    console.print(f"  [cyan]Content-Type:[/cyan]   {resp_headers.get('content-type', 'N/A')}")
                    console.print(f"  [cyan]Size:[/cyan]           {len(resp_body_bytes)} bytes")

                    # Try to extract the AI response text
                    ai_response = self.parser_instance.extract_response(resp_body)
                    if ai_response:
                        text = ai_response
                        if len(text) > 2000:
                            text = text[:2000] + f"\n  … (truncated, {len(ai_response)} chars total)"
                        console.print(f"\n  [bold green]💬 RESPONSE TEXT:[/bold green]")
                        for line in text.split("\n"):
                            console.print(f"  [white]{line}[/white]")

                    console.print("-" * 60)

        except Exception as e:
            console.print(f"[red]Error parsing response: {e}[/red]")

    # Windsurf local language server endpoint patterns
    WINDSURF_ENDPOINTS = [
        "senduserCascademessage",
        "languageserverservice",
        "exa.language_server_pb",
    ]

    def _is_ai_traffic(self, url: str, headers: dict) -> bool:
        """Check if this looks like AI traffic."""
        url_lower = url.lower()
        user_agent = headers.get("user-agent", "").lower()

        # ── Windsurf local language server (highest priority) ──
        for ep in self.WINDSURF_ENDPOINTS:
            if ep in url_lower:
                return True

        ai_domains = [
            "api.openai.com", "api.anthropic.com", "api.codeium.com",
            "copilot-proxy.githubusercontent.com", "api.github.com",
            "generativelanguage.googleapis.com", "api.groq.com",
            "api.mistral.ai", "api.cohere.com", "api.together.xyz",
        ]

        ai_paths = [
            "/v1/chat/completions", "/v1/completions", "/v1/messages",
            "/chat/completions", "/completions", "/generate",
        ]

        for domain in ai_domains:
            if domain in url_lower:
                return True
        for path in ai_paths:
            if path in url_lower:
                return True

        ai_apps = ["windsurf", "cursor", "vscode", "copilot", "electron"]
        for app in ai_apps:
            if app in user_agent:
                return True

        return False

    def _log_to_file(self, prompt: InterceptedPrompt):
        """Append intercepted prompt to a log file."""
        try:
            os.makedirs("logs", exist_ok=True)
            log_file = os.path.join("logs", f"prompts_{datetime.now().strftime('%Y-%m-%d')}.jsonl")
            entry = {
                "id": prompt.id,
                "timestamp": prompt.timestamp.isoformat(),
                "source": prompt.source,
                "url": prompt.url,
                "method": prompt.method,
                "prompt": prompt.prompt,
                "messages": prompt.messages,
                "metadata": prompt.metadata,
            }
            with open(log_file, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            console.print(f"[red]Error writing log: {e}[/red]")


# ─── Threaded TCP server ────────────────────────────────────────────────────────

class ThreadedProxyServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    """Multi-threaded HTTP proxy server."""
    daemon_threads = True
    allow_reuse_address = True


# ─── Public API ──────────────────────────────────────────────────────────────────

def create_proxy_server(port: int = None) -> ThreadedProxyServer:
    """Create and return a configured proxy server (not yet started)."""
    _ensure_ca()
    port = port or Config.PROXY_PORT
    server = ThreadedProxyServer(("0.0.0.0", port), ProxyRequestHandler)
    console.print(f"[green]Proxy server configured on port {port}[/green]")
    return server