#!/bin/bash

echo "🚀 Starting Simple Windsurf AI Traffic Monitor"
echo "📡 Proxy will start on port 8080"
echo "📋 Configure Windsurf proxy: http://127.0.0.1:8080"
echo ""

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
fi

# Start mitmproxy with our script
echo "Starting proxy..."
mitmdump -s simple_interceptor.py -p 8080 --set confdir=~/.mitmproxy