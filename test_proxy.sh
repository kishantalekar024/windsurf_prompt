#!/bin/bash

echo "🧪 Testing Proxy Setup"
echo ""

# Check if proxy is running
if ! lsof -i :8080 > /dev/null 2>&1; then
    echo "❌ No service running on port 8080"
    echo "   Start the proxy first: python src/main.py"
    exit 1
fi

echo "✅ Proxy running on port 8080"

# Test with curl
echo "🌐 Testing proxy with curl..."
RESULT=$(curl -x 127.0.0.1:8080 -s -w "%{http_code}" http://httpbin.org/ip -o /dev/null)

if [ "$RESULT" = "200" ]; then
    echo "✅ Proxy working! HTTP traffic successful"
else
    echo "❌ Proxy test failed (HTTP code: $RESULT)"
fi

echo ""  
echo "📋 Manual Test Options:"
echo ""
echo "🌐 Browser Test:"
echo "1. Configure browser proxy: 127.0.0.1:8080"
echo "2. Visit: http://httpbin.org/ip" 
echo "3. Check proxy terminal for traffic"
echo ""
echo "🔧 Command Line Test:"
echo "   curl -x 127.0.0.1:8080 http://httpbin.org/json"
echo ""
echo "🤖 Windsurf Test (if you have it):"
echo "1. Find Windsurf: find / -name '*indsurf*' -type f 2>/dev/null | head -5"
echo "2. Launch with proxy: HTTP_PROXY=127.0.0.1:8080 /path/to/windsurf"
echo "3. Use AI features"
echo "4. Watch proxy terminal"