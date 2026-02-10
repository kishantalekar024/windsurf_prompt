#!/bin/bash

echo "🔄 Resetting macOS Proxy Settings..."

# Get network services
networksetup -listallnetworkservices | tail -n +2 | while read service; do
    if [[ "$service" != "*"* ]]; then
        echo "🔧 Disabling proxy for: $service"
        networksetup -setwebproxystate "$service" off
        networksetup -setsecurewebproxystate "$service" off
    fi
done

echo "✅ Proxy settings reset - internet should work normally now"
echo ""
echo "💡 To check current proxy status:"
echo "   networksetup -getwebproxy \"Wi-Fi\""