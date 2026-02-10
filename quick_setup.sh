#!/bin/bash

echo "🔍 Quick Setup - Windsurf Prompt Interceptor (Print Mode)"
echo ""


# Activate virtual environment
echo "🔌 Activating virtual environment..."
source venv/bin/activate

# Upgrade pip to latest
echo "⬆️  Upgrading pip to latest..."
python -m pip install --upgrade pip

# Install dependencies with proper dependency resolution
echo "📥 Installing dependencies (print mode)..."
pip install mitmproxy==9.0.1
pip install flask==2.2.5 flask-cors==4.0.0 
pip install requests==2.28.2 python-dotenv==1.0.0 
pip install rich==13.7.0 colorama==0.4.6

# Create logs directory
echo "📁 Creating logs directory..."
mkdir -p logs

echo ""
echo "🎉 Quick setup complete!"
echo ""
echo "🚀 Ready to intercept Windsurf prompts!"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📌 PRINT-ONLY MODE"
echo "   ✓ No database setup required"
echo "   ✓ Prompts printed to console in real-time"
echo "   ✓ Easy to run and test"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "🎯 Next steps:"
echo "1. source venv/bin/activate"
echo "2. python src/main.py"
echo "3. Open Windsurf and start AI chat"
echo "4. Watch console for intercepted prompts!"
echo ""
echo "🔧 The tool will:"
echo "   • Install SSL certificate automatically"
echo "   • Configure system proxy (port 8080)"
echo "   • Display captured AI conversations"
echo ""
echo "⚠️  Note: Run with 'sudo python src/main.py' if certificate installation fails"