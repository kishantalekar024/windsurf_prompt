#!/bin/bash

echo "🔍 Testing mitmproxy setup..."

# Test if mitmproxy is installed
if ! command -v mitmproxy &> /dev/null; then
    echo "❌ mitmproxy not found"
    echo "Installing mitmproxy..."
    pip install mitmproxy
fi

echo "✅ mitmproxy found"

# Generate certificate if needed
if [ ! -f ~/.mitmproxy/mitmproxy-ca-cert.pem ]; then
    echo "📜 Generating mitmproxy certificate..."
    echo "This will start mitmproxy briefly to generate certificates..."
    
    # Start mitmproxy in background for 3 seconds to generate certs
    timeout 3s mitmproxy -p 8888 --set confdir=~/.mitmproxy > /dev/null 2>&1 || true
    
    if [ -f ~/.mitmproxy/mitmproxy-ca-cert.pem ]; then
        echo "✅ Certificate generated"
    else
        echo "❌ Certificate generation failed"
        echo "Please run: mitmproxy"
        echo "Then press 'q' to quit after it starts"
        exit 1
    fi
else
    echo "✅ Certificate already exists"
fi

echo ""
echo "🚀 Ready to run the interceptor!"
echo "Run: python src/main.py"