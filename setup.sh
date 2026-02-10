#!/bin/bash

echo "🔍 Setting up Windsurf Prompt Interceptor..."

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not installed"
    exit 1
fi

# Check if pip is installed
if ! command -v pip3 &> /dev/null; then
    echo "❌ pip3 is required but not installed"
    exit 1
fi

# Create virtual environment
echo "📦 Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
echo "📥 Installing Python dependencies..."
pip install -r requirements-simple.txt

# Create logs directory
echo "📁 Creating logs directory..."
mkdir -p logs

# Database setup (optional - not needed for print mode)
echo ""
echo "🗃️  Database Setup (OPTIONAL - Skip for print-only mode):"
echo "Current mode: Print-only (no database required)"
echo ""
echo "To enable database storage later:"
echo "1. For PostgreSQL: Create database 'windsurf_prompts'"
echo "   - Install: brew install postgresql"
echo "   - Create DB: createdb windsurf_prompts"
echo ""
echo "2. For MongoDB: Install and start MongoDB"
echo "   - Install: brew install mongodb-community"
echo "   - Start: brew services start mongodb-community"
echo ""

# Copy and customize environment file
if [ ! -f .env ]; then
    echo "⚙️  Environment file (.env) already exists"
    echo "   Please review and customize the settings"
else
    echo "⚙️  Environment file (.env) created"
    echo "   Please customize the database settings and other configuration"
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "📌 PRINT-ONLY MODE ENABLED"
echo "   - AI prompts and responses will be printed to console"
echo "   - No database required for current setup"
echo "   - Database code is preserved for future use"
echo ""
echo "Next steps:"
echo "1. Run: source venv/bin/activate"
echo "2. Run: python src/main.py"
echo "3. Open Windsurf and start chatting with AI"
echo "4. Watch console for captured prompts/responses"
echo ""
echo "📊 Dashboard available at: http://127.0.0.1:5000 (limited functionality in print mode)"
echo "🔧 Proxy will run on port: 8080"
echo ""
echo "⚠️  Important: The tool will configure your system proxy settings."
echo "    Run with sudo if certificate installation fails."