#!/bin/bash

# Windsurf Proxy Launcher
# Launches Windsurf with proxy settings so all traffic routes through the interceptor.

PROXY_PORT=${1:-8080}
CA_CERT="$HOME/.windsurf-proxy/ca-cert.pem"

echo "🚀 Windsurf Proxy Launcher"
echo "📡 Proxy: 127.0.0.1:$PROXY_PORT"
echo "🔐 CA Cert: $CA_CERT"
echo ""

# ── Check the CA cert exists ──────────────────────────────────────────────────
if [ ! -f "$CA_CERT" ]; then
    echo "❌ CA certificate not found at $CA_CERT"
    echo "   Start the proxy first:  python src/main.py"
    exit 1
fi

# ── Optionally trust the cert system-wide (one-time, needs sudo) ──────────────
echo "💡 If you haven't already, trust the CA cert (one-time):"
echo "   sudo security add-trusted-cert -d -r trustRoot \\"
echo "     -k /Library/Keychains/System.keychain $CA_CERT"
echo ""

# ── Find Windsurf ─────────────────────────────────────────────────────────────
POSSIBLE_PATHS=(
    "/Applications/Windsurf.app/Contents/MacOS/Electron"
    "/Applications/Windsurf.app/Contents/Resources/app/bin/windsurf"
    "/Applications/windsurf.app/Contents/MacOS/Electron"
    "/Applications/WindSurf.app/Contents/MacOS/Electron"
)

FOUND_PATH=""
for path in "${POSSIBLE_PATHS[@]}"; do
    if [ -f "$path" ]; then
        FOUND_PATH="$path"
        echo "✅ Found Windsurf at: $path"
        break
    fi
done

if [ -n "$FOUND_PATH" ]; then
    echo "🚀 Starting Windsurf with proxy..."

    # KEY: --proxy-bypass-list="<-loopback>" removes the default localhost bypass
    # so that Windsurf's local language server traffic (d.localhost:PORT) goes
    # through our proxy — this is where the actual prompts are sent!
    NODE_EXTRA_CA_CERTS="$CA_CERT" \
    NODE_TLS_REJECT_UNAUTHORIZED=0 \
    http_proxy="http://127.0.0.1:$PROXY_PORT" \
    https_proxy="http://127.0.0.1:$PROXY_PORT" \
    HTTP_PROXY="http://127.0.0.1:$PROXY_PORT" \
    HTTPS_PROXY="http://127.0.0.1:$PROXY_PORT" \
    "$FOUND_PATH" \
        --proxy-server="http://127.0.0.1:$PROXY_PORT" \
        --proxy-bypass-list="<-loopback>" \
        --ignore-certificate-errors \
        > /dev/null 2>&1 &

    echo "✅ Windsurf started with proxy configuration"
    echo "   PID: $!"
    echo ""
    echo "   ⚡ Localhost traffic (d.localhost) will route through proxy"
    echo "   ⚡ Windsurf prompts (SendUserCascadeMessage) will be captured"
else
    echo "❌ Windsurf not found automatically"
    echo ""
    echo "📋 Manual Options:"
    echo ""
    echo "🔧 Option 1: Launch manually with env variables"
    echo "   NODE_EXTRA_CA_CERTS=$CA_CERT \\"
    echo "   NODE_TLS_REJECT_UNAUTHORIZED=0 \\"
    echo "   http_proxy=http://127.0.0.1:$PROXY_PORT \\"
    echo "   https_proxy=http://127.0.0.1:$PROXY_PORT \\"
    echo "   /path/to/Windsurf --proxy-server=http://127.0.0.1:$PROXY_PORT --ignore-certificate-errors"
    echo ""
    echo "🔍 Option 2: Find Windsurf path"
    echo "   find / -name '*indsurf*' -type f 2>/dev/null | head -10"
    echo "   Then update this script with the correct path"
    echo ""
    echo "🌐 Option 3: Use system proxy (temporary, affects all apps)"
    echo "   networksetup -setwebproxy \"Wi-Fi\" 127.0.0.1 $PROXY_PORT"
    echo "   networksetup -setsecurewebproxy \"Wi-Fi\" 127.0.0.1 $PROXY_PORT"
    echo "   (Remember to reset: ./reset_proxy.sh)"
fi

echo ""
echo "📊 Monitor traffic in the other terminal window!"